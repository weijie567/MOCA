"""Add reviewed long-term and case memory tables.

Revision ID: 013_long_term_case_memory
Revises: 012_thread_user_scope
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "013_long_term_case_memory"
down_revision: str | None = "012_thread_user_scope"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


MEMORY_SCOPE_CHECK = "scope_type IN ('tenant', 'merchant', 'user', 'thread', 'case')"
MEMORY_REVIEW_STATUS_CHECK = (
    "review_status IN ("
    "'auto_approved', 'needs_review', 'approved', 'rejected', 'superseded', 'tombstoned', 'deleted'"
    ")"
)
MEMORY_PII_CLASSIFICATION_CHECK = "pii_classification IN ('none', 'low', 'sensitive', 'prohibited')"


def _jsonb_empty_object() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def _jsonb_empty_array() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table("long_term_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="long_term_memory.v2"),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=128), nullable=False),
        sa.Column("memory_kind", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("source_identity_hash", sa.String(length=80)),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("pii_classification", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="needs_review"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes", postgresql.UUID(as_uuid=True), sa.ForeignKey("long_term_memories.id")),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("long_term_memories.id")),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_long_term_memories_scope_type"),
        sa.CheckConstraint(
            "memory_kind IN ('fact', 'preference', 'constraint', 'pattern')",
            name="ck_long_term_memories_memory_kind",
        ),
        sa.CheckConstraint(MEMORY_REVIEW_STATUS_CHECK, name="ck_long_term_memories_review_status"),
        sa.CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_long_term_memories_pii_classification"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_long_term_memories_confidence_range"),
        sa.CheckConstraint("version > 0", name="ck_long_term_memories_version_positive"),
    )
    op.create_index("ix_long_term_memories_tenant_id", "long_term_memories", ["tenant_id"])
    op.create_index(
        "uq_long_term_memories_active_identity",
        "long_term_memories",
        ["tenant_id", "scope_type", "scope_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND is_current IS TRUE"),
    )
    op.create_index(
        "ix_long_term_memories_active_retrieval",
        "long_term_memories",
        ["tenant_id", "scope_type", "scope_id", "review_status", "is_current", "expires_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_long_term_memories_source_identity",
        "long_term_memories",
        ["tenant_id", "scope_type", "scope_id", "source_identity_hash"],
        postgresql_where=sa.text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table("case_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="case_memory.v2"),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=128), nullable=False),
        sa.Column("case_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("applicability", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("caveats", sa.Text()),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("policy_family", sa.String(length=80)),
        sa.Column("policy_version", sa.String(length=80)),
        sa.Column(
            "policy_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("source_identity_hash", sa.String(length=80)),
        sa.Column("embedding", Vector(1024)),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="needs_review"),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_reason", sa.Text()),
        sa.Column("pii_classification", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_case_memories_scope_type"),
        sa.CheckConstraint(MEMORY_REVIEW_STATUS_CHECK, name="ck_case_memories_review_status"),
        sa.CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_case_memories_pii_classification"),
    )
    op.create_index("ix_case_memories_tenant_id", "case_memories", ["tenant_id"])
    op.create_index(
        "ix_case_memories_metadata_filters",
        "case_memories",
        [
            "tenant_id",
            "scope_type",
            "scope_id",
            "case_type",
            "policy_family",
            "policy_version",
            "review_status",
            "expires_at",
        ],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_case_memories_active_content_identity",
        "case_memories",
        ["tenant_id", "scope_type", "scope_id", "content_hash"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_case_memories_source_identity",
        "case_memories",
        ["tenant_id", "scope_type", "scope_id", "source_identity_hash"],
        postgresql_where=sa.text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
    )
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_case_memories_embedding_hnsw
        ON case_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    """)

    op.create_table("memory_tombstones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="memory_tombstone.v1"),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=80)),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("source_identity_hash", sa.String(length=80)),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_memory_tombstones_scope_type"),
        sa.CheckConstraint(
            "memory_type IN ('long_term_fact', 'case_memory')",
            name="ck_memory_tombstones_memory_type",
        ),
        sa.CheckConstraint(
            "content_hash IS NOT NULL OR source_identity_hash IS NOT NULL",
            name="ck_memory_tombstones_identity_present",
        ),
    )
    op.create_index("ix_memory_tombstones_tenant_id", "memory_tombstones", ["tenant_id"])
    op.create_index(
        "ix_memory_tombstones_active_content_identity",
        "memory_tombstones",
        ["tenant_id", "memory_type", "scope_type", "scope_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_memory_tombstones_active_source_identity",
        "memory_tombstones",
        ["tenant_id", "memory_type", "scope_type", "scope_id", "source_identity_hash"],
        postgresql_where=sa.text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_memory_tombstones_active_scope",
        "memory_tombstones",
        ["tenant_id", "memory_type", "scope_type", "scope_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table("memory_write_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True)),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="memory_write_event.v2"),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("pii_classification", sa.String(length=32), nullable=False),
        sa.Column("candidate_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "memory_type IN ('session_slot', 'long_term_fact', 'case_memory', 'none')",
            name="ck_memory_write_events_memory_type",
        ),
        sa.CheckConstraint(
            "decision IN ('write', 'skip', 'needs_review', 'delete', 'supersede', 'tombstone', 'write_blocked')",
            name="ck_memory_write_events_decision",
        ),
        sa.CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_memory_write_events_pii_classification"),
        sa.CheckConstraint(
            "(memory_type = 'none' AND memory_id IS NULL) OR memory_type != 'none'",
            name="ck_memory_write_events_none_has_no_memory_id",
        ),
    )
    op.create_index("ix_memory_write_events_tenant_id", "memory_write_events", ["tenant_id"])
    op.create_index("ix_memory_write_events_tenant_run", "memory_write_events", ["tenant_id", "run_id"])
    op.create_index("ix_memory_write_events_memory", "memory_write_events", ["memory_type", "memory_id"])
    op.create_index(
        "ix_memory_write_events_candidate_hash",
        "memory_write_events",
        ["tenant_id", "candidate_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_write_events_candidate_hash", table_name="memory_write_events")
    op.drop_index("ix_memory_write_events_memory", table_name="memory_write_events")
    op.drop_index("ix_memory_write_events_tenant_run", table_name="memory_write_events")
    op.drop_index("ix_memory_write_events_tenant_id", table_name="memory_write_events")
    op.drop_table("memory_write_events")

    op.drop_index("ix_memory_tombstones_active_scope", table_name="memory_tombstones")
    op.drop_index("ix_memory_tombstones_active_source_identity", table_name="memory_tombstones")
    op.drop_index("ix_memory_tombstones_active_content_identity", table_name="memory_tombstones")
    op.drop_index("ix_memory_tombstones_tenant_id", table_name="memory_tombstones")
    op.drop_table("memory_tombstones")

    op.execute("DROP INDEX IF EXISTS ix_case_memories_embedding_hnsw")
    op.drop_index("ix_case_memories_source_identity", table_name="case_memories")
    op.drop_index("ix_case_memories_active_content_identity", table_name="case_memories")
    op.drop_index("ix_case_memories_metadata_filters", table_name="case_memories")
    op.drop_index("ix_case_memories_tenant_id", table_name="case_memories")
    op.drop_table("case_memories")

    op.drop_index("ix_long_term_memories_source_identity", table_name="long_term_memories")
    op.drop_index("ix_long_term_memories_active_retrieval", table_name="long_term_memories")
    op.drop_index("uq_long_term_memories_active_identity", table_name="long_term_memories")
    op.drop_index("ix_long_term_memories_tenant_id", table_name="long_term_memories")
    op.drop_table("long_term_memories")
