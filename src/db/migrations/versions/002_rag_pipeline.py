"""RAG pipeline schema: doc_key, embedding dimension fix, HNSW index

Revision ID: 002_rag_pipeline
Revises: 001_initial_schema
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "002_rag_pipeline"
down_revision: str | None = "001_initial_schema"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Add semantic document key column
    op.add_column("policy_documents", sa.Column("doc_key", sa.String(64), nullable=False, server_default=""))
    op.create_unique_constraint("uq_policy_documents_tenant_doc_key", "policy_documents", ["tenant_id", "doc_key"])

    # Fix embedding dimension: 1536 -> 1024
    op.execute("ALTER TABLE policy_chunks ALTER COLUMN embedding TYPE vector(1024)")

    # Add index on chunk_id for citation lookup
    op.create_index("ix_policy_chunks_chunk_id", "policy_chunks", ["chunk_id"])

    # Create HNSW index for cosine similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_policy_chunks_embedding_hnsw
        ON policy_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_embedding_hnsw")
    op.drop_index("ix_policy_chunks_chunk_id", table_name="policy_chunks")
    op.execute("ALTER TABLE policy_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.drop_constraint("uq_policy_documents_tenant_doc_key", "policy_documents", type_="unique")
    op.drop_column("policy_documents", "doc_key")
