"""fts tsvector on document_chunks

Revision ID: 41c9396d68b6
Revises: c4fa907d327a
Create Date: 2026-07-20 19:59:38.585552

Adds the lexical (BM25-style) search vector for hybrid retrieval: a generated,
Postgres-maintained tsvector over chunk content, plus a GIN index for fast
full-text matching. Complements the existing HNSW vector index.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "41c9396d68b6"
down_revision: str | None = "c4fa907d327a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "content_tsv",
            TSVECTOR,
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_document_chunks_content_tsv",
        "document_chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_tsv", table_name="document_chunks")
    op.drop_column("document_chunks", "content_tsv")
