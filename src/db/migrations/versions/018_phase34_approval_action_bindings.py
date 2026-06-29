"""Add Phase 34 approval and action binding fields.

Revision ID: 018_phase34_approval_action_bindings
Revises: 017_tool_policy_events
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "018_phase34_approval_action_bindings"
down_revision: str | None = "017_tool_policy_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_APPROVAL_REQUEST_BINDING_COLUMNS = (
    sa.Column("target_merchant_id", sa.String(length=128)),
    sa.Column("target_merchant_ref", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("business_fact_refs", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("verified_evidence_refs", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("claim_verification_ref", sa.String(length=128)),
    sa.Column("claim_verification_summary", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("risk_decision_ref", sa.String(length=128)),
    sa.Column("risk_decision", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("approval_idempotency_key", sa.String(length=256)),
)

_ACTION_DRAFT_BINDING_COLUMNS = (
    sa.Column("target_merchant_id", sa.String(length=128)),
    sa.Column("target_merchant_ref", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("business_fact_refs", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("verified_evidence_refs", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("claim_verification_ref", sa.String(length=128)),
    sa.Column("claim_verification_summary", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("risk_decision_ref", sa.String(length=128)),
    sa.Column("risk_decision", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("auto_allowed_binding_ref", sa.String(length=128)),
)


def upgrade() -> None:
    for column in _APPROVAL_REQUEST_BINDING_COLUMNS:
        op.add_column("approval_requests", column)

    for column in _ACTION_DRAFT_BINDING_COLUMNS:
        op.add_column("action_drafts", column)

    op.create_index(
        "ix_approval_requests_tenant_target_merchant",
        "approval_requests",
        ["tenant_id", "target_merchant_id"],
    )
    op.create_index(
        "ix_action_drafts_tenant_target_merchant",
        "action_drafts",
        ["tenant_id", "target_merchant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_drafts_tenant_target_merchant", table_name="action_drafts")
    op.drop_index("ix_approval_requests_tenant_target_merchant", table_name="approval_requests")

    for column in reversed(_ACTION_DRAFT_BINDING_COLUMNS):
        op.drop_column("action_drafts", column.name)

    for column in reversed(_APPROVAL_REQUEST_BINDING_COLUMNS):
        op.drop_column("approval_requests", column.name)
