import asyncio
import uuid

from core.db import dispose_engines
from core.ingestion import run_ingestion
from worker.celery_app import celery_app


async def _run(document_id: uuid.UUID, org_id: uuid.UUID) -> int:
    try:
        return await run_ingestion(document_id, org_id)
    finally:
        # Release this loop's DB connections so the next task starts clean.
        await dispose_engines()


@celery_app.task(name="worker.ingest_document")  # type: ignore[untyped-decorator]
def ingest_document(document_id: str, org_id: str) -> int:
    """Celery entrypoint: run the async ingestion pipeline to completion."""
    return asyncio.run(_run(uuid.UUID(document_id), uuid.UUID(org_id)))
