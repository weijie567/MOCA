"""Add durable single-flight approval resume leases.

Revision ID: 024_phase64_1_resume_attempt_lease
Revises: 023_phase64_1_auto_action_capabilities
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "024_phase64_1_resume_attempt_lease"
down_revision: str | None = "023_phase64_1_auto_action_capabilities"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column("resume_attempt_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "approval_requests",
        sa.Column("resume_attempt_decision_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column("approval_requests", sa.Column("resume_attempt_status", sa.String(length=32)))
    op.add_column("approval_requests", sa.Column("resume_lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("approval_requests", sa.Column("resume_attempt_started_at", sa.DateTime(timezone=True)))
    op.add_column("approval_requests", sa.Column("resume_attempt_updated_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_approval_requests_resume_attempt_decision",
        "approval_requests",
        "approval_decisions",
        ["resume_attempt_decision_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_approval_requests_resume_attempt_status",
        "approval_requests",
        "resume_attempt_status IS NULL OR "
        "resume_attempt_status IN ('attempted', 'completed', 'failed', 'abandoned')",
    )
    op.create_check_constraint(
        "ck_approval_requests_resume_attempt_identity",
        "approval_requests",
        "(resume_attempt_status IS NULL AND resume_attempt_id IS NULL "
        "AND resume_attempt_decision_id IS NULL AND resume_attempt_started_at IS NULL "
        "AND resume_attempt_updated_at IS NULL AND resume_lease_expires_at IS NULL) OR "
        "(resume_attempt_status IS NOT NULL AND resume_attempt_id IS NOT NULL "
        "AND resume_attempt_decision_id IS NOT NULL AND resume_attempt_started_at IS NOT NULL "
        "AND resume_attempt_updated_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_approval_requests_resume_attempt_lease",
        "approval_requests",
        "resume_attempt_status <> 'attempted' OR resume_lease_expires_at IS NOT NULL",
    )
    op.create_index(
        "ix_approval_requests_resume_attempt",
        "approval_requests",
        ["resume_attempt_status", "resume_lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_approval_requests_resume_attempt", table_name="approval_requests")
    op.drop_constraint(
        "ck_approval_requests_resume_attempt_lease",
        "approval_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_approval_requests_resume_attempt_identity",
        "approval_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_approval_requests_resume_attempt_status",
        "approval_requests",
        type_="check",
    )
    op.drop_constraint(
        "fk_approval_requests_resume_attempt_decision",
        "approval_requests",
        type_="foreignkey",
    )
    op.drop_column("approval_requests", "resume_attempt_updated_at")
    op.drop_column("approval_requests", "resume_attempt_started_at")
    op.drop_column("approval_requests", "resume_lease_expires_at")
    op.drop_column("approval_requests", "resume_attempt_status")
    op.drop_column("approval_requests", "resume_attempt_decision_id")
    op.drop_column("approval_requests", "resume_attempt_id")
