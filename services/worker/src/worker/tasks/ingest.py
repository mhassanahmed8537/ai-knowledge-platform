import asyncio
import uuid

from core.db import dispose_engines
from core.enums import WebhookEvent
from core.ingestion import run_ingestion
from worker.celery_app import celery_app
from worker.tasks.webhooks import dispatch_webhooks_for_event


async def _run(document_id: uuid.UUID, org_id: uuid.UUID) -> int:
    try:
        n_chunks = await run_ingestion(document_id, org_id)
    except Exception as exc:
        await dispatch_webhooks_for_event(
            org_id,
            WebhookEvent.DOCUMENT_FAILED.value,
            {"document_id": str(document_id), "error": str(exc)[:500]},
        )
        raise
    else:
        await dispatch_webhooks_for_event(
            org_id,
            WebhookEvent.DOCUMENT_READY.value,
            {"document_id": str(document_id), "chunk_count": n_chunks},
        )
        return n_chunks
    finally:
        # Release this loop's DB connections so the next task starts clean.
        await dispose_engines()


@celery_app.task(name="worker.ingest_document")  # type: ignore[untyped-decorator]
def ingest_document(document_id: str, org_id: str) -> int:
    """Celery entrypoint: run the async ingestion pipeline to completion."""
    return asyncio.run(_run(uuid.UUID(document_id), uuid.UUID(org_id)))
