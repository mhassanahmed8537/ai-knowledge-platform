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
    # "enforced" means the runtime role is subject to RLS. If it can bypass
    # (superuser or BYPASSRLS), tenant isolation is silently off — surface it.
    rls_status = "unknown"
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
            can_bypass = await conn.scalar(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
            rls_status = "UNSAFE-bypass" if can_bypass else "enforced"
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

    status = "ok" if rls_status in {"enforced", "unknown"} else "degraded"
    return {
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "rls": rls_status,
    }
