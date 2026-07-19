"""grant app_auth on api_keys for key auth

Revision ID: 8e4e9d7592c3
Revises: 011db88c062a
Create Date: 2026-07-19 20:54:39.667138

API-key authentication is a cross-tenant bootstrap operation: the key must be
located by its public prefix before the caller's org is known. That lookup (and
the last_used_at touch) therefore runs on the BYPASSRLS app_auth role.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8e4e9d7592c3"
down_revision: str | None = "011db88c062a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT, UPDATE ON api_keys TO app_auth")


def downgrade() -> None:
    op.execute("REVOKE SELECT, UPDATE ON api_keys FROM app_auth")
