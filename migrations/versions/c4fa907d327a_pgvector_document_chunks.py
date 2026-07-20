"""pgvector document chunks

Revision ID: c4fa907d327a
Revises: 8e4e9d7592c3
Create Date: 2026-07-20 01:03:58.753704

Adds the vector store for ingestion: enables pgvector, creates the
org-scoped, RLS-enforced document_chunks table, and gives documents the
storage_key / error columns the ingestion pipeline writes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "c4fa907d327a"
down_revision: str | None = "8e4e9d7592c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536
CURRENT_ORG_SQL = "nullif(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("documents", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("error", sa.String(length=1024), nullable=True))

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_document_chunks_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    # Approximate-nearest-neighbour index for cosine similarity search.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Row-Level Security (matches the org_isolation pattern of the other tables).
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_chunks TO app_user")
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY org_isolation ON document_chunks
        USING (org_id = {CURRENT_ORG_SQL})
        WITH CHECK (org_id = {CURRENT_ORG_SQL})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS org_isolation ON document_chunks")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON document_chunks FROM app_user")
    op.drop_index("ix_document_chunks_embedding", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("documents", "error")
    op.drop_column("documents", "storage_key")
