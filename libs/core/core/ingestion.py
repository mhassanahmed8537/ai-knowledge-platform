"""Document ingestion pipeline: download -> extract -> chunk -> embed -> store.

Written as a plain async function so it can be driven directly in tests. The
Celery task is a thin ``asyncio.run`` wrapper around ``run_ingestion``. All DB
work runs as the RLS-enforced app_user with the tenant's org context bound, so
ingestion cannot cross tenants any more than a user request can.
"""

import asyncio
import io
import uuid

from pypdf import PdfReader
from sqlalchemy import delete

from core import storage
from core.chunking import chunk_text, estimate_tokens
from core.config import get_settings
from core.db import get_sessionmaker, set_org_context
from core.enums import DocumentStatus, UsageKind
from core.models import Document, DocumentChunk
from core.providers.embeddings import get_embedding_provider
from core.providers.pricing import embedding_cost_usd
from core.usage import record_usage


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


async def _set_status(
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    status: DocumentStatus,
    *,
    error: str | None = None,
) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await set_org_context(session, org_id)
        doc = await session.get(Document, document_id)
        if doc is not None:
            doc.status = status
            doc.error = error


async def run_ingestion(document_id: uuid.UUID, org_id: uuid.UUID) -> int:
    """Ingest one document; returns the number of chunks written."""
    settings = get_settings()
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session, session.begin():
        await set_org_context(session, org_id)
        doc = await session.get(Document, document_id)
        if doc is None:
            return 0  # deleted or not visible under RLS
        if not doc.storage_key:
            raise ValueError("document has no storage_key")
        storage_key = doc.storage_key
        doc.status = DocumentStatus.PROCESSING
        doc.error = None

    try:
        data = await asyncio.to_thread(storage.download_bytes, storage_key)
        text = await asyncio.to_thread(extract_pdf_text, data)
        chunks = chunk_text(text, size=settings.chunk_size, overlap=settings.chunk_overlap)

        vectors: list[list[float]] = []
        if chunks:
            provider = get_embedding_provider()
            vectors = await asyncio.to_thread(provider.embed, chunks)

        async with sessionmaker() as session, session.begin():
            await set_org_context(session, org_id)
            # Idempotent re-ingest: clear any prior chunks first.
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            for index, (content, embedding) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(
                    DocumentChunk(
                        org_id=org_id,
                        document_id=document_id,
                        chunk_index=index,
                        content=content,
                        token_count=estimate_tokens(content),
                        embedding=embedding,
                    )
                )
            if chunks:
                total_tokens = sum(estimate_tokens(c) for c in chunks)
                # Budget-crossing is intentionally not checked here: generation
                # (chat.py) already checks on every turn and is the dominant
                # cost driver, so a second alert path for embeddings would
                # mostly just duplicate it.
                await record_usage(
                    session,
                    org_id=org_id,
                    user_id=None,
                    kind=UsageKind.EMBEDDING,
                    provider=provider.name,
                    model=provider.model,
                    input_tokens=total_tokens,
                    output_tokens=0,
                    cost_usd=embedding_cost_usd(provider.name, provider.model, total_tokens),
                    document_id=document_id,
                )
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.status = DocumentStatus.READY
                doc.error = None
    except Exception as exc:
        await _set_status(org_id, document_id, DocumentStatus.FAILED, error=str(exc)[:1024])
        raise

    return len(chunks)
