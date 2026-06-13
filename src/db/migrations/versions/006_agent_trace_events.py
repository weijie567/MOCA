"""Add minimal agent trace event table.

Revision ID: 006_agent_trace_events
Revises: 005_approval_tables
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006_agent_trace_events"
down_revision: str | None = "005_approval_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_trace_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128)),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=48),
            nullable=False,
            server_default="minimal_event_envelope.v1",
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", postgresql.JSONB, nullable=False),
        sa.Column("resource_refs", postgresql.JSONB, nullable=False),
        sa.Column("redaction_policy_version", sa.String(length=48), nullable=False),
        sa.Column("redacted_payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
    )
    op.create_index("ix_agent_trace_events_run_id", "agent_trace_events", ["run_id"])
    op.create_index("ix_agent_trace_events_tenant_id", "agent_trace_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_trace_events_tenant_id", table_name="agent_trace_events")
    op.drop_index("ix_agent_trace_events_run_id", table_name="agent_trace_events")
    op.drop_table("agent_trace_events")
