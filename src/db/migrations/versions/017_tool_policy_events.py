"""Register explicit tool policy decision event types.

Revision ID: 017_tool_policy_events
Revises: 016_agent_run_memory_idempotency
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "017_tool_policy_events"
down_revision: str | None = "016_agent_run_memory_idempotency"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_trace_events_event_type", "agent_trace_events", type_="check")
    op.create_check_constraint("ck_agent_trace_events_event_type", "agent_trace_events",
        "event_type IN ("
        "'action_draft_created', 'approval_decided', 'approval_expired', 'approval_requested', "
        "'approval_resumed', 'llm_call_completed', 'llm_call_failed', 'llm_call_started', "
        "'memory_write_completed', 'memory_write_failed', 'memory_write_started', 'node_completed', "
        "'node_failed', 'node_started', 'rag_retrieval_completed', 'rag_retrieval_failed', "
        "'rag_retrieval_started', 'run_status_changed', 'tool_call_completed', 'tool_call_failed', "
        "'tool_call_started', 'tool_policy_runtime_auth_recorded', 'tool_policy_visibility_recorded'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_trace_events_event_type", "agent_trace_events", type_="check")
    op.create_check_constraint("ck_agent_trace_events_event_type", "agent_trace_events",
        "event_type IN ("
        "'action_draft_created', 'approval_decided', 'approval_expired', 'approval_requested', "
        "'approval_resumed', 'llm_call_completed', 'llm_call_failed', 'llm_call_started', "
        "'memory_write_completed', 'memory_write_failed', 'memory_write_started', 'node_completed', "
        "'node_failed', 'node_started', 'rag_retrieval_completed', 'rag_retrieval_failed', "
        "'rag_retrieval_started', 'run_status_changed', 'tool_call_completed', 'tool_call_failed', "
        "'tool_call_started'"
        ")",
    )
