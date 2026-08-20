"""usage events, org webhooks, monthly budget

Revision ID: f3a8c1d9e5b2
Revises: c5a599c2c4fc
Create Date: 2026-08-20 00:00:00.000000

Phase 5 — usage analytics, per-tenant cost tracking, budget alerts, webhooks:
  * organizations.monthly_budget_usd -> optional soft cap on month-to-date
                                         spend; null = unlimited.
  * usage_events                     -> one row per generation call or
                                         embedding batch (tokens + cost),
                                         recorded regardless of vendor so
                                         token-volume analytics work even
                                         with the zero-cost dev defaults.
  * org_webhooks                     -> tenant-configured outbound webhooks
                                         (document.ready/failed, budget.alert).

Both new tables are org-scoped and RLS-enforced like every other tenant table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f3a8c1d9e5b2"
down_revision: str | None = "c5a599c2c4fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["usage_events", "org_webhooks"]
CURRENT_ORG_SQL = "nullif(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("monthly_budget_usd", sa.Numeric(12, 2), nullable=True)
    )

    op.create_table(
        "usage_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            sa.dialects.postgresql.ENUM("generation", "embedding", name="usage_kind"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_usage_events_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_usage_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_usage_events_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_usage_events_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
    )
    # Powers both /usage/summary (month-to-date sum) and /usage/events (listing).
    op.create_index("ix_usage_events_org_created", "usage_events", ["org_id", "created_at"])

    op.create_table(
        "org_webhooks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=False),
        sa.Column("event_types", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_org_webhooks_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org_webhooks")),
    )

    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY org_isolation ON {table}
            USING (org_id = {CURRENT_ORG_SQL})
            WITH CHECK (org_id = {CURRENT_ORG_SQL})
            """
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS org_isolation ON {table}")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user")
    op.drop_table("org_webhooks")
    op.drop_index("ix_usage_events_org_created", table_name="usage_events")
    op.drop_table("usage_events")
    op.execute("DROP TYPE IF EXISTS usage_kind")
    op.drop_column("organizations", "monthly_budget_usd")
