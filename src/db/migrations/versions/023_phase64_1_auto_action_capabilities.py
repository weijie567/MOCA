"""Add durable one-use auto-action capabilities.

Revision ID: 023_phase64_1_auto_action_capabilities
Revises: 022_case_working_context
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "023_phase64_1_auto_action_capabilities"
down_revision: str | None = "022_case_working_context"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auto_action_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=48),
            nullable=False,
            server_default="auto_action_capability.v1",
        ),
        sa.Column(
            "key_version",
            sa.String(length=48),
            nullable=False,
            server_default="opaque_ref_sha256.v1",
        ),
        sa.Column("opaque_ref", sa.String(length=96), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_merchant_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_action", sa.String(length=64), nullable=False),
        sa.Column("action_payload_hash", sa.String(length=128), nullable=False),
        sa.Column("safety_snapshot_ref", sa.String(length=128), nullable=False),
        sa.Column("safety_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("risk_decision_ref", sa.String(length=128), nullable=False),
        sa.Column("risk_decision_hash", sa.String(length=128), nullable=False),
        sa.Column("risk_disposition", sa.String(length=32), nullable=False),
        sa.Column("handler", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="issued"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("resulting_draft_id", postgresql.UUID(as_uuid=True)),
        sa.Column("idempotency_key", sa.String(length=256)),
        sa.UniqueConstraint("opaque_ref", name="uq_auto_action_capabilities_opaque_ref"),
        sa.UniqueConstraint("nonce", name="uq_auto_action_capabilities_nonce"),
        sa.CheckConstraint(
            "status IN ('issued', 'consumed', 'expired', 'revoked')",
            name="ck_auto_action_capabilities_status",
        ),
        sa.CheckConstraint("expires_at > issued_at", name="ck_auto_action_capabilities_expiry"),
        sa.CheckConstraint(
            "handler = 'create_coupon_grant_draft'",
            name="ck_auto_action_capabilities_handler",
        ),
        sa.CheckConstraint(
            "risk_disposition = 'allow'",
            name="ck_auto_action_capabilities_risk_disposition",
        ),
        sa.CheckConstraint(
            "((status = 'consumed' AND consumed_at IS NOT NULL "
            "AND resulting_draft_id IS NOT NULL AND idempotency_key IS NOT NULL) "
            "OR (status <> 'consumed' AND consumed_at IS NULL "
            "AND resulting_draft_id IS NULL AND idempotency_key IS NULL))",
            name="ck_auto_action_capabilities_consumption_state",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_auto_action_capabilities_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_auto_action_capabilities_actor",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_auto_action_capabilities_run",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_draft_id"],
            ["action_drafts.id"],
            name="fk_auto_action_capabilities_draft",
        ),
    )
    op.create_index(
        "ix_auto_action_capabilities_tenant_run",
        "auto_action_capabilities",
        ["tenant_id", "run_id"],
    )
    op.create_index(
        "ix_auto_action_capabilities_status_expiry",
        "auto_action_capabilities",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auto_action_capabilities_status_expiry",
        table_name="auto_action_capabilities",
    )
    op.drop_index(
        "ix_auto_action_capabilities_tenant_run",
        table_name="auto_action_capabilities",
    )
    op.drop_table("auto_action_capabilities")
