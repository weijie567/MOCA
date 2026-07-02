"""Add case working context tables.

Revision ID: 022_case_working_context
Revises: 021_thread_case_links
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "022_case_working_context"
down_revision: str | None = "021_thread_case_links"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


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
    op.create_table(
        "case_working_contexts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("refund_cases.id"), nullable=False),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="case_working_context.v1"),
        sa.Column("authority_class", sa.String(length=32), nullable=False, server_default="contextual_only"),
        sa.Column("customer_request", sa.Text()),
        sa.Column("issue_type", sa.String(length=64)),
        sa.Column(
            "claims_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "verified_facts_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "missing_info_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "evidence_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "actions_taken_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "policy_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "agent_recommendations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "pending_tasks_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "commitments_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "next_action_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("pii_classification", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "authority_class = 'contextual_only'",
            name="ck_case_working_contexts_authority_class",
        ),
        sa.CheckConstraint("version > 0", name="ck_case_working_contexts_version_positive"),
        sa.CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_case_working_contexts_pii_classification"),
        sa.ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["refund_cases.id", "refund_cases.tenant_id"],
            name="fk_case_working_contexts_case_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_case_working_contexts_id_tenant"),
    )
    op.create_index("ix_case_working_contexts_tenant_id", "case_working_contexts", ["tenant_id"])
    op.create_index(
        "uq_case_working_contexts_active_scope",
        "case_working_contexts",
        ["tenant_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "case_working_context_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "case_working_context_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("case_working_contexts.id"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("refund_cases.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("edit_source", sa.String(length=32), nullable=False),
        sa.Column("updated_by_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column(
            "source_ref_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "edit_source IN ('run_auto', 'staff_manual')",
            name="ck_cwc_revisions_edit_source",
        ),
        sa.CheckConstraint("version > 0", name="ck_cwc_revisions_version_positive"),
        sa.ForeignKeyConstraint(
            ["case_working_context_id", "tenant_id"],
            ["case_working_contexts.id", "case_working_contexts.tenant_id"],
            name="fk_cwc_revisions_context_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["refund_cases.id", "refund_cases.tenant_id"],
            name="fk_cwc_revisions_case_tenant",
        ),
    )
    op.create_index(
        "uq_cwc_revisions_context_version",
        "case_working_context_revisions",
        ["tenant_id", "case_working_context_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_cwc_revisions_case",
        "case_working_context_revisions",
        ["tenant_id", "case_id", "version"],
    )

    op.drop_constraint("ck_memory_write_events_memory_type", "memory_write_events", type_="check")
    op.create_check_constraint(
        "ck_memory_write_events_memory_type",
        "memory_write_events",
        "memory_type IN ('session_slot', 'long_term_fact', 'case_memory', 'case_working_context', 'none')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_memory_write_events_memory_type", "memory_write_events", type_="check")
    connection = op.get_bind()
    row_count = connection.execute(
        sa.text("SELECT count(*) FROM memory_write_events WHERE memory_type = 'case_working_context'")
    ).scalar_one()
    if row_count:
        raise RuntimeError(
            "Cannot downgrade 022_case_working_context while "
            f"{row_count} memory_write_events rows use memory_type='case_working_context'. "
            "Delete or export those audit rows before retrying."
        )
    op.create_check_constraint(
        "ck_memory_write_events_memory_type",
        "memory_write_events",
        "memory_type IN ('session_slot', 'long_term_fact', 'case_memory', 'none')",
    )

    op.drop_index("ix_cwc_revisions_case", table_name="case_working_context_revisions")
    op.drop_index("uq_cwc_revisions_context_version", table_name="case_working_context_revisions")
    op.drop_table("case_working_context_revisions")

    op.drop_index("uq_case_working_contexts_active_scope", table_name="case_working_contexts")
    op.drop_index("ix_case_working_contexts_tenant_id", table_name="case_working_contexts")
    op.drop_table("case_working_contexts")
