import asyncio
import uuid

from core.ingestion import run_ingestion
from worker.celery_app import celery_app


@celery_app.task(name="worker.ingest_document")  # type: ignore[untyped-decorator]
def ingest_document(document_id: str, org_id: str) -> int:
    """Celery entrypoint: run the async ingestion pipeline to completion."""
    return asyncio.run(run_ingestion(uuid.UUID(document_id), uuid.UUID(org_id)))
