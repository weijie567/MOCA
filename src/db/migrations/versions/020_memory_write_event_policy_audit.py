"""Add memory write event policy audit fields.

Revision ID: 020_memory_write_event_policy_audit
Revises: 019_phase36_merchant_scope_hardening
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "020_memory_write_event_policy_audit"
down_revision: str | None = "019_phase36_merchant_scope_hardening"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memory_write_events",
        sa.Column("policy_version", sa.String(length=64), nullable=False, server_default="memory_write_policy.v1"),
    )
    op.add_column(
        "memory_write_events",
        sa.Column(
            "blocked_by_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "memory_write_events",
        sa.Column("authority_class", sa.String(length=32), nullable=False, server_default="contextual_only"),
    )
    op.alter_column("memory_write_events", "schema_version", server_default="memory_write_event.v3")
    op.execute("UPDATE memory_write_events SET schema_version = 'memory_write_event.v3'")


def downgrade() -> None:
    op.alter_column("memory_write_events", "schema_version", server_default="memory_write_event.v2")
    op.execute("UPDATE memory_write_events SET schema_version = 'memory_write_event.v2'")
    op.drop_column("memory_write_events", "authority_class")
    op.drop_column("memory_write_events", "blocked_by_json")
    op.drop_column("memory_write_events", "policy_version")
