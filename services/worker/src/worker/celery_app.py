from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "worker",
    broker=settings.broker_url,
    backend=settings.redis_url,
    include=["worker.tasks.ping", "worker.tasks.ingest", "worker.tasks.webhooks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
