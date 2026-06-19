"""Add authoritative session memory table.

Revision ID: 007_session_memories
Revises: 006_agent_trace_events
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_session_memories"
down_revision: str | None = "006_agent_trace_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=48),
            nullable=False,
            server_default="session_memory.v2",
        ),
        sa.Column(
            "active_slots_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("session_summary", sa.Text()),
        sa.Column(
            "unresolved_questions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("last_intent", sa.String(length=64)),
        sa.Column(
            "last_business_context_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_session_memories_tenant_id", "session_memories", ["tenant_id"])
    op.create_index("ix_session_memories_user_id", "session_memories", ["user_id"])
    op.create_index("ix_session_memories_thread_id", "session_memories", ["thread_id"])
    op.create_index("ix_session_memories_last_run_id", "session_memories", ["last_run_id"])
    op.create_index("ix_session_memories_scope", "session_memories", ["tenant_id", "user_id", "thread_id"])
    op.create_index("ix_session_memories_expires_at", "session_memories", ["expires_at"])
    op.create_index(
        "uq_session_memories_active_scope",
        "session_memories",
        ["tenant_id", "user_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_session_memories_active_scope", table_name="session_memories")
    op.drop_index("ix_session_memories_expires_at", table_name="session_memories")
    op.drop_index("ix_session_memories_scope", table_name="session_memories")
    op.drop_index("ix_session_memories_last_run_id", table_name="session_memories")
    op.drop_index("ix_session_memories_thread_id", table_name="session_memories")
    op.drop_index("ix_session_memories_user_id", table_name="session_memories")
    op.drop_index("ix_session_memories_tenant_id", table_name="session_memories")
    op.drop_table("session_memories")
