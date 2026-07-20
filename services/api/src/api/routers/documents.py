import asyncio
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Principal, get_principal, require_role
from api.schemas import DocumentChunkOut, DocumentCreate, DocumentOut, DocumentUpdate
from api.tasks import enqueue_ingest
from core import storage
from core.config import get_settings
from core.enums import DocumentStatus, UserRole
from core.models import Document, DocumentChunk

router = APIRouter(prefix="/documents", tags=["documents"])

_WRITER = require_role(UserRole.ADMIN, UserRole.MEMBER)


def _safe_filename(name: str | None) -> str:
    base = (name or "document.pdf").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "document.pdf"
    return cleaned[:255]


@router.get("", response_model=list[DocumentOut])
async def list_documents(principal: Principal = Depends(get_principal)) -> list[Document]:
    result = await principal.session.scalars(select(Document).order_by(Document.created_at.desc()))
    return list(result.all())


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    principal: Principal = Depends(_WRITER),
) -> Document:
    doc = Document(
        org_id=principal.org_id,
        title=body.title,
        filename=body.filename,
        content_type=body.content_type,
    )
    principal.session.add(doc)
    await principal.session.flush()
    await principal.session.refresh(doc)
    return doc


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    principal: Principal = Depends(_WRITER),
) -> Document:
    filename = _safe_filename(file.filename)
    is_pdf = (file.content_type == "application/pdf") or filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported",
        )

    data = await file.read()
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_bytes} bytes",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    doc = Document(
        org_id=principal.org_id,
        title=filename,
        filename=filename,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
    )
    principal.session.add(doc)
    await principal.session.flush()

    key = storage.build_key(principal.org_id, doc.id, filename)
    await asyncio.to_thread(storage.upload_bytes, key, data, "application/pdf")
    doc.storage_key = key
    await principal.session.flush()
    await principal.session.refresh(doc)

    # Enqueue only after the request transaction commits (background tasks run
    # post-response), so the worker can see the row under RLS.
    if settings.auto_ingest_on_upload:
        background.add_task(enqueue_ingest, doc.id, principal.org_id)
    return doc


@router.get("/{doc_id}/chunks", response_model=list[DocumentChunkOut])
async def list_document_chunks(
    doc_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> list[DocumentChunk]:
    await _get_owned_document(principal.session, doc_id)
    result = await principal.session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.all())


async def _get_owned_document(session: AsyncSession, doc_id: uuid.UUID) -> Document:
    # RLS guarantees a row is only visible/returned when it belongs to the
    # caller's org, so a cross-tenant id simply yields 404.
    doc = await session.scalar(select(Document).where(Document.id == doc_id))
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> Document:
    return await _get_owned_document(principal.session, doc_id)


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: uuid.UUID,
    body: DocumentUpdate,
    principal: Principal = Depends(_WRITER),
) -> Document:
    doc = await _get_owned_document(principal.session, doc_id)
    if body.title is not None:
        doc.title = body.title
    await principal.session.flush()
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    principal: Principal = Depends(_WRITER),
) -> None:
    doc = await _get_owned_document(principal.session, doc_id)
    await principal.session.delete(doc)
