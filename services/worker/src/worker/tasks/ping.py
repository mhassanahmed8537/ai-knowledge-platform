from worker.celery_app import celery_app


@celery_app.task(name="worker.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
