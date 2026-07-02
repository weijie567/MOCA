"""Add thread to refund case links.

Revision ID: 021_thread_case_links
Revises: 020_memory_write_event_policy_audit
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "021_thread_case_links"
down_revision: str | None = "020_memory_write_event_policy_audit"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


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
    op.create_table(
        "thread_case_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "conversation_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("refund_cases.id"), nullable=False),
        sa.Column("link_source", sa.String(length=32), nullable=False),
        sa.Column("linked_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="thread_case_link.v1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "link_source IN ('run_auto', 'staff_manual', 'import')",
            name="ck_thread_case_links_link_source",
        ),
    )
    op.create_index("ix_thread_case_links_tenant_id", "thread_case_links", ["tenant_id"])
    op.create_index(
        "ix_thread_case_links_tenant_case",
        "thread_case_links",
        ["tenant_id", "case_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_thread_case_links_active",
        "thread_case_links",
        ["tenant_id", "conversation_thread_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_thread_case_links_active", table_name="thread_case_links")
    op.drop_index("ix_thread_case_links_tenant_case", table_name="thread_case_links")
    op.drop_index("ix_thread_case_links_tenant_id", table_name="thread_case_links")
    op.drop_table("thread_case_links")
