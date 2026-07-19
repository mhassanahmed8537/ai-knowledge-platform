import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from core.config import get_settings
from core.db import get_engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    settings = get_settings()

    db_status = "ok"
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    redis_status = "ok"
    client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    try:
        await client.ping()
    except Exception:
        redis_status = "unavailable"
    finally:
        await client.aclose()

    return {"status": "ok", "database": db_status, "redis": redis_status}
