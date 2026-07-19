import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Principal, get_principal, require_role
from api.schemas import DocumentCreate, DocumentOut, DocumentUpdate
from core.enums import UserRole
from core.models import Document

router = APIRouter(prefix="/documents", tags=["documents"])

_WRITER = require_role(UserRole.ADMIN, UserRole.MEMBER)


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
