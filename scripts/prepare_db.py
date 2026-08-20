"""Idempotent database setup: create the app roles, then run migrations.

Usage (from repo root, with Postgres reachable):
    uv run python scripts/prepare_db.py

Runs the cluster-level role bootstrap (app_user / app_auth) followed by
``alembic upgrade head``. Used both for local first-time setup and in CI.

In a real deployment (the k8s migration Job — see infra/k8s/base/migration-job.yaml)
APP_USER_PASSWORD / APP_AUTH_PASSWORD are set from Terraform-generated secrets
(infra/terraform/modules/database) rather than the dev-only literals baked
into db_bootstrap.sql, so this module builds the CREATE ROLE statements
itself in that case instead of executing the static file — db_bootstrap.sql's
own header already says as much ("In AWS they are provisioned by Terraform
... NOT by this script").
"""

import asyncio
import os
import pathlib

import asyncpg
from alembic import command
from alembic.config import Config

from core.config import get_settings

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_BOOTSTRAP_SQL = _ROOT / "scripts" / "db_bootstrap.sql"
_DATABASE_NAME = "knowledge_platform"


def _quoted_password(password: str) -> str:
    # CREATE ROLE ... PASSWORD takes a string literal, not a bind parameter
    # (DDL isn't parameterizable over the wire — this is a real asyncpg/
    # Postgres limitation, not a stylistic choice), so the value has to be
    # spliced into the statement text. Reject anything a single '' escape
    # can't make safe rather than trying to out-clever SQL-injection here.
    if "\\" in password or "\x00" in password:
        raise ValueError("password contains characters that cannot be safely quoted")
    return "'" + password.replace("'", "''") + "'"


async def _bootstrap_roles_with_passwords(
    conn: asyncpg.Connection, *, app_user_password: str, app_auth_password: str
) -> None:
    statements = [
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user LOGIN PASSWORD {_quoted_password(app_user_password)}
                    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            ELSE
                ALTER ROLE app_user PASSWORD {_quoted_password(app_user_password)};
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_auth') THEN
                CREATE ROLE app_auth LOGIN PASSWORD {_quoted_password(app_auth_password)}
                    NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE;
            ELSE
                ALTER ROLE app_auth PASSWORD {_quoted_password(app_auth_password)};
            END IF;
        END
        $$;
        """,
        f"GRANT CONNECT ON DATABASE {_DATABASE_NAME} TO app_user, app_auth;",
        "GRANT USAGE ON SCHEMA public TO app_user, app_auth;",
    ]
    for statement in statements:
        await conn.execute(statement)


async def _bootstrap_roles() -> None:
    # asyncpg speaks the plain libpq DSN, not SQLAlchemy's "+asyncpg" form.
    dsn = get_settings().migration_database_url.replace("+asyncpg", "")
    app_user_password = os.environ.get("APP_USER_PASSWORD")
    app_auth_password = os.environ.get("APP_AUTH_PASSWORD")

    conn = await asyncpg.connect(dsn)
    try:
        if app_user_password and app_auth_password:
            await _bootstrap_roles_with_passwords(
                conn, app_user_password=app_user_password, app_auth_password=app_auth_password
            )
        else:
            # Local dev / CI: the fixed dev-only passwords in db_bootstrap.sql,
            # matching DATABASE_URL / AUTH_DATABASE_URL's defaults in .env.example.
            await conn.execute(_BOOTSTRAP_SQL.read_text())
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(_bootstrap_roles())
    command.upgrade(Config(str(_ROOT / "alembic.ini")), "head")
    print("Database ready: roles bootstrapped and migrations applied.")


if __name__ == "__main__":
    main()
