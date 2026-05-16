"""Add latency metrics to agent_steps.

Revision ID: 004_latency_metrics
Revises: 003
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "004_latency_metrics"
down_revision: str | None = "003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_steps", sa.Column("provider_latency_ms", sa.Integer))
    op.add_column("agent_steps", sa.Column("retry_count", sa.Integer))
    op.add_column("agent_steps", sa.Column("metrics_json", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("agent_steps", "metrics_json")
    op.drop_column("agent_steps", "retry_count")
    op.drop_column("agent_steps", "provider_latency_ms")
