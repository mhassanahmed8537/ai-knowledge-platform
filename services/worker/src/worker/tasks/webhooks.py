"""Outbound webhook delivery.

``dispatch_webhooks_for_event`` is a plain async function (same philosophy as
``core.ingestion.run_ingestion``): the ingestion task calls it directly in its
own event loop (no broker round-trip needed — it's already running in the
worker), while the API-side producer (``api.tasks.enqueue_webhook_event``)
reaches it indirectly via the ``worker.dispatch_webhook_event`` Celery task,
since the API process has no direct DB access to the worker's event loop.

Delivery is best-effort: a slow or failing endpoint is skipped and logged
rather than retried, so one bad webhook can't back up the queue or block
ingestion/generation.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import select

from core.db import dispose_engines, get_sessionmaker, set_org_context
from core.models import OrgWebhook
from core.webhooks import sign_payload
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


async def dispatch_webhooks_for_event(
    org_id: uuid.UUID, event_type: str, payload: dict[str, Any]
) -> int:
    """POST ``payload`` to every active webhook subscribed to ``event_type``.

    Returns the number of deliveries that succeeded (2xx response).
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await set_org_context(session, org_id)
        result = await session.scalars(select(OrgWebhook).where(OrgWebhook.is_active.is_(True)))
        webhooks = [w for w in result.all() if event_type in w.event_types]

    if not webhooks:
        return 0

    body = json.dumps({"event": event_type, "data": payload, "ts": int(time.time())}).encode()
    delivered = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for webhook in webhooks:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Event": event_type,
                "X-Webhook-Signature": sign_payload(webhook.secret, body),
            }
            try:
                response = await client.post(webhook.url, content=body, headers=headers)
                response.raise_for_status()
                delivered += 1
            except httpx.HTTPError:
                logger.warning(
                    "webhook delivery failed", extra={"webhook_id": str(webhook.id)}, exc_info=True
                )
    return delivered


@celery_app.task(name="worker.dispatch_webhook_event")  # type: ignore[untyped-decorator]
def dispatch_webhook_event(org_id: str, event_type: str, payload: dict[str, Any]) -> int:
    """Celery entrypoint for the API side (see module docstring)."""

    async def _run() -> int:
        try:
            return await dispatch_webhooks_for_event(uuid.UUID(org_id), event_type, payload)
        finally:
            await dispose_engines()

    return asyncio.run(_run())
