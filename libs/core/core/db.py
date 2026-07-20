import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

_engine: AsyncEngine | None = None
_auth_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Runtime engine using the RLS-enforced ``app_user`` role."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_auth_engine() -> AsyncEngine:
    """Auth-subsystem engine using the BYPASSRLS ``app_auth`` role."""
    global _auth_engine
    if _auth_engine is None:
        _auth_engine = create_async_engine(get_settings().auth_database_url, pool_pre_ping=True)
    return _auth_engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def get_auth_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_auth_engine(), expire_on_commit=False)


async def dispose_engines() -> None:
    """Dispose and reset the engine singletons.

    Each Celery task runs a fresh ``asyncio.run`` (new event loop); pooled
    asyncpg connections are bound to the loop that created them. Disposing at the
    end of every task run ensures the next task builds engines on its own loop.
    """
    global _engine, _auth_engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    if _auth_engine is not None:
        await _auth_engine.dispose()
        _auth_engine = None


async def set_org_context(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Bind the current transaction to a tenant so RLS policies filter to it.

    Uses ``set_config(..., is_local => true)`` so the setting is scoped to the
    active transaction and cannot leak across pooled connections.
    """
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, true)"),
        {"org_id": str(org_id)},
    )


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
