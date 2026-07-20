"""Celery producer: enqueues work for the worker by task name.

The API doesn't import the worker package — it addresses tasks by their
registered name over the shared broker, keeping the two services decoupled.
"""

import uuid
from functools import lru_cache

from celery import Celery

from core.config import get_settings


@lru_cache
def _producer() -> Celery:
    return Celery("api-producer", broker=get_settings().broker_url)


def enqueue_ingest(document_id: uuid.UUID, org_id: uuid.UUID) -> None:
    _producer().send_task("worker.ingest_document", args=[str(document_id), str(org_id)])
