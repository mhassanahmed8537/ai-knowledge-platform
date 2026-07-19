"""Idempotent database setup: create the app roles, then run migrations.

Usage (from repo root, with Postgres reachable):
    uv run python scripts/prepare_db.py

Runs the cluster-level role bootstrap (app_user / app_auth) followed by
``alembic upgrade head``. Used both for local first-time setup and in CI.
"""

import asyncio
import pathlib

import asyncpg
from alembic import command
from alembic.config import Config

from core.config import get_settings

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_BOOTSTRAP_SQL = _ROOT / "scripts" / "db_bootstrap.sql"


async def _bootstrap_roles() -> None:
    # asyncpg speaks the plain libpq DSN, not SQLAlchemy's "+asyncpg" form.
    dsn = get_settings().migration_database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(_BOOTSTRAP_SQL.read_text())
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(_bootstrap_roles())
    command.upgrade(Config(str(_ROOT / "alembic.ini")), "head")
    print("Database ready: roles bootstrapped and migrations applied.")


if __name__ == "__main__":
    main()
