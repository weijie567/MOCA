"""Add conversation memory foundation tables.

Revision ID: 011_memory_foundation_v2
Revises: 010_replay_event_v3
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "011_memory_foundation_v2"
down_revision: str | None = "010_replay_event_v3"
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


def _retention_columns() -> tuple[sa.Column, sa.Column, sa.Column]:
    return (
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    op.create_table(
        "conversation_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_id", sa.String(length=128)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        *_retention_columns(),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_conversation_threads_status"),
    )
    op.create_index("ix_conversation_threads_tenant_id", "conversation_threads", ["tenant_id"])
    op.create_index("ix_conversation_threads_thread_id", "conversation_threads", ["thread_id"])
    op.create_index("ix_conversation_threads_user_id", "conversation_threads", ["user_id"])
    op.create_index("ix_conversation_threads_case_id", "conversation_threads", ["case_id"])
    op.create_index(
        "ix_conversation_threads_tenant_user_thread",
        "conversation_threads",
        ["tenant_id", "user_id", "thread_id"],
    )
    op.create_index(
        "uq_conversation_threads_active_tenant_thread",
        "conversation_threads",
        ["tenant_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("trace_id", sa.String(length=128)),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("prompt_template_version", sa.String(length=64)),
        sa.Column(
            "prompt_block_hashes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column("context_snapshot_ref", sa.String(length=255)),
        sa.Column("redacted_prompt_snapshot_ref", sa.String(length=255)),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        *_retention_columns(),
        *_timestamps(),
        sa.UniqueConstraint("conversation_thread_id", "message_index", name="uq_conversation_messages_thread_index"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_conversation_messages_role"),
        sa.CheckConstraint("message_index > 0", name="ck_conversation_messages_index_positive"),
    )
    op.create_index(
        "ix_conversation_messages_conversation_thread_id",
        "conversation_messages",
        ["conversation_thread_id"],
    )
    op.create_index("ix_conversation_messages_tenant_id", "conversation_messages", ["tenant_id"])
    op.create_index("ix_conversation_messages_thread_id", "conversation_messages", ["thread_id"])
    op.create_index("ix_conversation_messages_run_id", "conversation_messages", ["run_id"])
    op.create_index("ix_conversation_messages_trace_id", "conversation_messages", ["trace_id"])
    op.create_index(
        "ix_conversation_messages_tenant_thread_index",
        "conversation_messages",
        ["tenant_id", "thread_id", "message_index"],
    )
    op.create_index(
        "ix_conversation_messages_tenant_run",
        "conversation_messages",
        ["tenant_id", "run_id"],
    )

    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("message_id", sa.String(length=128)),
        sa.Column(
            "conversation_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_messages.id"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("trace_id", sa.String(length=128)),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("caller_node", sa.String(length=64)),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("attempt", sa.Integer()),
        sa.Column(
            "argument_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("argument_hash", sa.String(length=80)),
        sa.Column(
            "redaction_policy_version",
            sa.String(length=48),
            nullable=False,
            server_default="conversation_redaction.v1",
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="started"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("error_summary", sa.String(length=500)),
        *_retention_columns(),
        *_timestamps(),
        sa.CheckConstraint("attempt IS NULL OR attempt > 0", name="ck_tool_calls_attempt_positive"),
    )
    op.create_index("ix_tool_calls_conversation_thread_id", "tool_calls", ["conversation_thread_id"])
    op.create_index("ix_tool_calls_conversation_message_id", "tool_calls", ["conversation_message_id"])
    op.create_index("ix_tool_calls_tenant_id", "tool_calls", ["tenant_id"])
    op.create_index("ix_tool_calls_thread_id", "tool_calls", ["thread_id"])
    op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"])
    op.create_index("ix_tool_calls_tool_call_id", "tool_calls", ["tool_call_id"])
    op.create_index("ix_tool_calls_tenant_thread_run", "tool_calls", ["tenant_id", "thread_id", "run_id"])
    op.create_index("ix_tool_calls_tenant_operation", "tool_calls", ["tenant_id", "operation_id"])

    op.create_table(
        "tool_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("tool_call_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_calls.id")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("trace_id", sa.String(length=128)),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "conversation_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_messages.id"),
        ),
        sa.Column("tool_call_id", sa.String(length=128)),
        sa.Column("tool_result_id", sa.String(length=128)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("source_system", sa.String(length=128)),
        sa.Column("data_freshness_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("raw_result_ref", sa.String(length=255)),
        sa.Column("raw_result_hash", sa.String(length=80)),
        sa.Column(
            "normalized_result_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_object(),
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("prompt_summary", sa.Text()),
        sa.Column(
            "business_fact_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "policy_evidence_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column("audit_ref", sa.String(length=255)),
        sa.Column("replay_event_id", postgresql.UUID(as_uuid=True)),
        *_retention_columns(),
        *_timestamps(),
    )
    op.create_index("ix_tool_results_conversation_thread_id", "tool_results", ["conversation_thread_id"])
    op.create_index("ix_tool_results_conversation_message_id", "tool_results", ["conversation_message_id"])
    op.create_index("ix_tool_results_tenant_id", "tool_results", ["tenant_id"])
    op.create_index("ix_tool_results_thread_id", "tool_results", ["thread_id"])
    op.create_index("ix_tool_results_run_id", "tool_results", ["run_id"])
    op.create_index("ix_tool_results_tool_result_id", "tool_results", ["tool_result_id"])
    op.create_index("ix_tool_results_replay_event_id", "tool_results", ["replay_event_id"])
    op.create_index("ix_tool_results_tenant_thread_run", "tool_results", ["tenant_id", "thread_id", "run_id"])
    op.create_index("ix_tool_results_tenant_operation", "tool_results", ["tenant_id", "operation_id"])

    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column(
            "conversation_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("case_id", sa.String(length=128)),
        sa.Column("summary_type", sa.String(length=32), nullable=False),
        sa.Column("source_start_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_end_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "source_message_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column(
            "source_tool_result_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_jsonb_empty_array(),
        ),
        sa.Column("summary_text", sa.Text()),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("summary_model", sa.String(length=128)),
        sa.Column("summary_prompt_version", sa.String(length=64)),
        sa.Column("summary_hash", sa.String(length=80)),
        *_retention_columns(),
        *_timestamps(),
        sa.CheckConstraint("summary_type IN ('thread_rolling', 'case_current')", name="ck_summaries_type"),
    )
    op.create_index("ix_summaries_tenant_id", "summaries", ["tenant_id"])
    op.create_index("ix_summaries_thread_id", "summaries", ["thread_id"])
    op.create_index("ix_summaries_conversation_thread_id", "summaries", ["conversation_thread_id"])
    op.create_index("ix_summaries_case_id", "summaries", ["case_id"])
    op.create_index("ix_summaries_tenant_thread_type", "summaries", ["tenant_id", "thread_id", "summary_type"])


def downgrade() -> None:
    op.drop_index("ix_summaries_tenant_thread_type", table_name="summaries")
    op.drop_index("ix_summaries_case_id", table_name="summaries")
    op.drop_index("ix_summaries_conversation_thread_id", table_name="summaries")
    op.drop_index("ix_summaries_thread_id", table_name="summaries")
    op.drop_index("ix_summaries_tenant_id", table_name="summaries")
    op.drop_table("summaries")

    op.drop_index("ix_tool_results_tenant_operation", table_name="tool_results")
    op.drop_index("ix_tool_results_tenant_thread_run", table_name="tool_results")
    op.drop_index("ix_tool_results_replay_event_id", table_name="tool_results")
    op.drop_index("ix_tool_results_tool_result_id", table_name="tool_results")
    op.drop_index("ix_tool_results_run_id", table_name="tool_results")
    op.drop_index("ix_tool_results_thread_id", table_name="tool_results")
    op.drop_index("ix_tool_results_tenant_id", table_name="tool_results")
    op.drop_index("ix_tool_results_conversation_message_id", table_name="tool_results")
    op.drop_index("ix_tool_results_conversation_thread_id", table_name="tool_results")
    op.drop_table("tool_results")

    op.drop_index("ix_tool_calls_tenant_operation", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tenant_thread_run", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tool_call_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_thread_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tenant_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_conversation_message_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_conversation_thread_id", table_name="tool_calls")
    op.drop_table("tool_calls")

    op.drop_index("ix_conversation_messages_tenant_run", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_tenant_thread_index", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_trace_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_run_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_thread_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_tenant_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_thread_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("uq_conversation_threads_active_tenant_thread", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_tenant_user_thread", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_case_id", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_user_id", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_thread_id", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_tenant_id", table_name="conversation_threads")
    op.drop_table("conversation_threads")
