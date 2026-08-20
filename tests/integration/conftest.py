import asyncio
import contextlib
import os
from collections.abc import AsyncIterator

# Tests drive ingestion deterministically via run_ingestion; don't also enqueue
# to a real worker (which would double-process and race on the chunk unique key).
os.environ.setdefault("AUTO_INGEST_ON_UPLOAD", "false")
# The rate limiter buckets by client IP, and every test shares one apparent IP
# under httpx's ASGITransport — leaving it on would make unrelated tests trip
# each other's budget. test_rate_limit.py re-enables it for its own assertions.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from core.config import get_settings  # noqa: E402


def _dsn() -> str:
    return get_settings().migration_database_url.replace("+asyncpg", "")


def _check_db() -> bool:
    async def _ping() -> None:
        conn = await asyncpg.connect(_dsn())
        await conn.close()

    try:
        asyncio.run(_ping())
        return True
    except Exception:
        return False


_DB_OK = _check_db()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when Postgres is not reachable (e.g. no local stack)."""
    if _DB_OK:
        return
    skip = pytest.mark.skip(reason="Postgres not reachable; skipping integration tests")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_orgs() -> AsyncIterator[None]:
    yield
    if not _DB_OK:
        return

    async def _cleanup() -> None:
        conn = await asyncpg.connect(_dsn())
        try:
            await conn.execute("DELETE FROM organizations WHERE slug LIKE 'itest-%'")
        finally:
            await conn.close()

    with contextlib.suppress(Exception):
        asyncio.run(_cleanup())


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    import core.db as db
    from api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://itest") as c:
        yield c

    # Engines are module-level singletons with pooled connections bound to this
    # test's event loop. Dispose and reset them so the next test (with its own
    # loop) builds fresh engines instead of reusing closed connections.
    if db._engine is not None:
        await db._engine.dispose()
        db._engine = None
    if db._auth_engine is not None:
        await db._auth_engine.dispose()
        db._auth_engine = None
