"""Expand agent trace events for replay event v3.

Revision ID: 010_replay_event_v3
Revises: 009_action_draft_v2
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "010_replay_event_v3"
down_revision: str | None = "009_action_draft_v2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


REPLAY_EVENT_TYPES: set[str] = {
    "action_draft_created",
    "approval_decided",
    "approval_expired",
    "approval_requested",
    "approval_resumed",
    "llm_call_completed",
    "llm_call_failed",
    "llm_call_started",
    "memory_write_completed",
    "memory_write_failed",
    "memory_write_started",
    "node_completed",
    "node_failed",
    "node_started",
    "rag_retrieval_completed",
    "rag_retrieval_failed",
    "rag_retrieval_started",
    "run_status_changed",
    "tool_call_completed",
    "tool_call_failed",
    "tool_call_started",
}

ck_agent_trace_events_event_type = (
    "event_type IN ('action_draft_created', 'approval_decided', 'approval_expired', 'approval_requested', "
    "'approval_resumed', 'llm_call_completed', 'llm_call_failed', 'llm_call_started', 'memory_write_completed', "
    "'memory_write_failed', 'memory_write_started', 'node_completed', 'node_failed', 'node_started', "
    "'rag_retrieval_completed', 'rag_retrieval_failed', 'rag_retrieval_started', 'run_status_changed', "
    "'tool_call_completed', 'tool_call_failed', 'tool_call_started')"
)


def upgrade() -> None:
    for column in (
        sa.Column("parent_operation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("attempt", sa.Integer()),
        sa.Column("version", sa.Integer()),
        sa.Column("node_name", sa.String(length=64)),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True)),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True)),
        sa.Column("tool_call_id", sa.String(length=128)),
        sa.Column("evidence_refs_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("agent_trace_events", column)

    op.create_check_constraint(
        "ck_agent_trace_events_schema_version",
        "agent_trace_events",
        "schema_version IN ('minimal_event_envelope.v1', 'replay_event.v3')",
    )
    op.create_check_constraint(
        "ck_agent_trace_events_event_type",
        "agent_trace_events",
        ck_agent_trace_events_event_type,
    )
    op.create_check_constraint(
        "ck_agent_trace_events_sequence_positive",
        "agent_trace_events",
        "sequence > 0",
    )
    op.create_check_constraint(
        "ck_agent_trace_events_attempt_positive",
        "agent_trace_events",
        "attempt IS NULL OR attempt > 0",
    )
    op.create_index(
        "ix_agent_trace_events_tenant_run_sequence",
        "agent_trace_events",
        ["tenant_id", "run_id", "sequence"],
    )
    op.create_index(
        "ix_agent_trace_events_tenant_run_operation",
        "agent_trace_events",
        ["tenant_id", "run_id", "operation_id"],
    )
    op.create_index(
        "ix_agent_trace_events_tenant_occurred_at",
        "agent_trace_events",
        ["tenant_id", "occurred_at"],
    )
    op.create_index(
        "ix_agent_trace_events_event_type_occurred_at",
        "agent_trace_events",
        ["event_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_trace_events_event_type_occurred_at", table_name="agent_trace_events")
    op.drop_index("ix_agent_trace_events_tenant_occurred_at", table_name="agent_trace_events")
    op.drop_index("ix_agent_trace_events_tenant_run_operation", table_name="agent_trace_events")
    op.drop_index("ix_agent_trace_events_tenant_run_sequence", table_name="agent_trace_events")
    op.drop_constraint("ck_agent_trace_events_attempt_positive", "agent_trace_events", type_="check")
    op.drop_constraint("ck_agent_trace_events_sequence_positive", "agent_trace_events", type_="check")
    op.drop_constraint("ck_agent_trace_events_event_type", "agent_trace_events", type_="check")
    op.drop_constraint("ck_agent_trace_events_schema_version", "agent_trace_events", type_="check")

    for column_name in (
        "deleted_at",
        "retention_until",
        "archived_at",
        "error_json",
        "evidence_refs_json",
        "tool_call_id",
        "draft_id",
        "approval_id",
        "node_name",
        "version",
        "attempt",
        "parent_operation_id",
    ):
        op.drop_column("agent_trace_events", column_name)
