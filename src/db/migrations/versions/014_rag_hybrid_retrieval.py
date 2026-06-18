"""Add policy chunk full-text and trigram search support.

Revision ID: 014_rag_hybrid_retrieval
Revises: 013_long_term_case_memory
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "014_rag_hybrid_retrieval"
down_revision: str | None = "013_long_term_case_memory"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("policy_chunks", sa.Column("search_text", sa.Text(), nullable=True))
    op.execute("""
        UPDATE policy_chunks
        SET search_text = trim(concat_ws(' ', section, content))
        WHERE search_text IS NULL
    """)
    op.alter_column("policy_chunks", "search_text", nullable=False)
    op.execute("""
        ALTER TABLE policy_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_policy_chunks_search_vector_gin
        ON policy_chunks
        USING gin (search_vector)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_policy_chunks_search_text_trgm
        ON policy_chunks
        USING gin (search_text gin_trgm_ops)
    """)
    op.create_index(
        "ix_policy_chunks_retrieval_scope",
        "policy_chunks",
        ["tenant_id", "effective_date", "risk_level"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_retrieval_scope", table_name="policy_chunks")
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_search_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_search_vector_gin")
    op.drop_column("policy_chunks", "search_vector")
    op.drop_column("policy_chunks", "search_text")
