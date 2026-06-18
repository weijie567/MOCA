"""Add RAG production ingestion provenance schema.

Revision ID: 015_rag_production_ingestion_ocr
Revises: 014_rag_hybrid_retrieval
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "015_rag_production_ingestion_ocr"
down_revision: str | None = "014_rag_hybrid_retrieval"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("policy_documents", sa.Column("source_type", sa.String(length=32), nullable=True))
    op.add_column("policy_documents", sa.Column("source_checksum", sa.String(length=128), nullable=True))
    op.add_column("policy_documents", sa.Column("parser_metadata_json", postgresql.JSONB(), nullable=True))
    op.add_column("policy_documents", sa.Column("policy_version_fingerprint", sa.String(length=128), nullable=True))

    op.add_column("policy_chunks", sa.Column("source_block_refs_json", postgresql.JSONB(), nullable=True))
    op.add_column("policy_chunks", sa.Column("ocr_metadata_json", postgresql.JSONB(), nullable=True))
    op.execute("""
        UPDATE policy_chunks
        SET source_block_refs_json = '[]'::jsonb
        WHERE source_block_refs_json IS NULL
    """)
    op.execute("""
        UPDATE policy_chunks
        SET ocr_metadata_json = '{}'::jsonb
        WHERE ocr_metadata_json IS NULL
    """)
    op.alter_column("policy_chunks", "source_block_refs_json", nullable=False)
    op.alter_column("policy_chunks", "ocr_metadata_json", nullable=False)

    op.create_table(
        "document_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_block_id", sa.String(length=128), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=80), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("bbox_json", postgresql.JSONB(), nullable=False),
        sa.Column("table_metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("parser_metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("ocr_metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_uri", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("block_index >= 0", name="ck_document_blocks_block_index_nonnegative"),
        sa.CheckConstraint("char_length(text) <= 20000", name="ck_document_blocks_text_max_length"),
        sa.ForeignKeyConstraint(["doc_id"], ["policy_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "doc_id",
            "source_block_id",
            name="uq_document_blocks_tenant_doc_source_block",
        ),
    )
    op.create_index("ix_document_blocks_tenant_id", "document_blocks", ["tenant_id"])
    op.create_index("ix_document_blocks_doc_id", "document_blocks", ["doc_id"])
    op.create_index(
        "ix_document_blocks_tenant_doc_index",
        "document_blocks",
        ["tenant_id", "doc_id", "block_index"],
    )
    op.create_index(
        "ix_document_blocks_tenant_doc_source_block",
        "document_blocks",
        ["tenant_id", "doc_id", "source_block_id"],
    )

    op.create_table(
        "rag_ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("doc_key", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_checksum", sa.String(length=128), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("ocr_engine", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("safe_message", sa.String(length=500), nullable=True),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=False),
        sa.Column("counts_json", postgresql.JSONB(), nullable=False),
        sa.Column("timings_json", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "stage IN ('received', 'parsing', 'cleaning', 'chunking', 'embedding', 'persisting', 'completed')",
            name="ck_rag_ingestion_jobs_stage",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed')",
            name="ck_rag_ingestion_jobs_status",
        ),
        sa.ForeignKeyConstraint(["doc_id"], ["policy_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_ingestion_jobs_tenant_id", "rag_ingestion_jobs", ["tenant_id"])
    op.create_index("ix_rag_ingestion_jobs_doc_id", "rag_ingestion_jobs", ["doc_id"])
    op.create_index("ix_rag_ingestion_jobs_tenant_doc", "rag_ingestion_jobs", ["tenant_id", "doc_id"])
    op.create_index("ix_rag_ingestion_jobs_tenant_doc_key", "rag_ingestion_jobs", ["tenant_id", "doc_key"])
    op.create_index("ix_rag_ingestion_jobs_tenant_status", "rag_ingestion_jobs", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_rag_ingestion_jobs_tenant_status", table_name="rag_ingestion_jobs")
    op.drop_index("ix_rag_ingestion_jobs_tenant_doc_key", table_name="rag_ingestion_jobs")
    op.drop_index("ix_rag_ingestion_jobs_tenant_doc", table_name="rag_ingestion_jobs")
    op.drop_index("ix_rag_ingestion_jobs_doc_id", table_name="rag_ingestion_jobs")
    op.drop_index("ix_rag_ingestion_jobs_tenant_id", table_name="rag_ingestion_jobs")
    op.drop_index("ix_document_blocks_tenant_doc_source_block", table_name="document_blocks")
    op.drop_index("ix_document_blocks_tenant_doc_index", table_name="document_blocks")
    op.drop_index("ix_document_blocks_doc_id", table_name="document_blocks")
    op.drop_index("ix_document_blocks_tenant_id", table_name="document_blocks")

    op.drop_column("policy_chunks", "ocr_metadata_json")
    op.drop_column("policy_chunks", "source_block_refs_json")

    op.drop_table("rag_ingestion_jobs")
    op.drop_table("document_blocks")

    op.drop_column("policy_documents", "policy_version_fingerprint")
    op.drop_column("policy_documents", "parser_metadata_json")
    op.drop_column("policy_documents", "source_checksum")
    op.drop_column("policy_documents", "source_type")
