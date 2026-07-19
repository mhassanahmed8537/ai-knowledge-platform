"""rls policies and grants

Revision ID: 011db88c062a
Revises: cb04b0481842
Create Date: 2026-07-19 20:43:00.885283

Enforces multi-tenant isolation via Postgres Row-Level Security.

Design:
  * app_user  -> RLS-enforced runtime role. Every query is transparently
                 filtered to the org bound to the current transaction via the
                 `app.current_org_id` GUC (set by the API per request).
  * app_auth  -> trusted auth subsystem role (BYPASSRLS). Handles the inherently
                 cross-tenant auth-bootstrap lookups (login by email, refresh
                 token validation, oauth linking).

Both ENABLE and FORCE RLS are set so even the table owner is subject to the
policies (defense in depth). `current_setting(..., true)` returns NULL when the
GUC is unset, so every policy denies all rows by default (fail-closed).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011db88c062a"
down_revision: str | None = "cb04b0481842"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Org-scoped tables -> RLS-enforced for app_user.
ORG_SCOPED_TABLES = ["organizations", "users", "api_keys", "documents"]

# app_user handles all authenticated business logic; app_auth only auth-bootstrap.
APP_USER_TABLES = ["organizations", "users", "api_keys", "documents"]
APP_AUTH_TABLES = ["organizations", "users", "refresh_tokens", "oauth_accounts"]

CURRENT_ORG_SQL = "nullif(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    # --- Table privileges ---
    for table in APP_USER_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
    for table in APP_AUTH_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_auth")

    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user"
    )

    # --- Row-Level Security ---
    for table in ORG_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # organizations: the tenant boundary is the row's own id.
    op.execute(
        f"""
        CREATE POLICY org_isolation ON organizations
        USING (id = {CURRENT_ORG_SQL})
        WITH CHECK (id = {CURRENT_ORG_SQL})
        """
    )

    # Child tables: scoped by org_id.
    for table in ["users", "api_keys", "documents"]:
        op.execute(
            f"""
            CREATE POLICY org_isolation ON {table}
            USING (org_id = {CURRENT_ORG_SQL})
            WITH CHECK (org_id = {CURRENT_ORG_SQL})
            """
        )


def downgrade() -> None:
    for table in ORG_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user"
    )
    for table in APP_USER_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user")
    for table in APP_AUTH_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_auth")
