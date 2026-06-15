"""Add action draft v2 persistence fields.

Revision ID: 009_action_draft_v2
Revises: 008_approval_state_machine
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009_action_draft_v2"
down_revision: str | None = "008_approval_state_machine"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_LEGACY_KEY_CONSTRAINT = "uq_action_drafts" + "_idempotency_key"


def upgrade() -> None:
    op.drop_constraint(_LEGACY_KEY_CONSTRAINT, "action_drafts", type_="unique")

    for column in (
        sa.Column("schema_version", sa.String(length=48), server_default="action_draft.v2"),
        sa.Column("target_id", sa.String(length=128)),
        sa.Column("approval_revision_ref", sa.String(length=128)),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("safety_snapshot_ref", sa.String(length=128)),
        sa.Column("safety_snapshot_hash", sa.String(length=128)),
        sa.Column("draft_outcome", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("execution_mode", sa.String(length=32), server_default="demo"),
        sa.Column("draft_version", sa.Integer(), server_default="1"),
        sa.Column("lifecycle_status", sa.String(length=32), server_default="active"),
        sa.Column("retention_policy", sa.String(length=64), server_default="phase14_demo_draft"),
    ):
        op.add_column("action_drafts", column)

    op.create_unique_constraint(
        "uq_action_drafts_tenant_idempotency_key",
        "action_drafts",
        ["tenant_id", "idempotency_key"],
    )
    op.create_index("ix_action_drafts_tenant_target", "action_drafts", ["tenant_id", "target_id"])
    op.create_index("ix_action_drafts_tenant_action_hash", "action_drafts", ["tenant_id", "action_payload_hash"])


def downgrade() -> None:
    op.drop_index("ix_action_drafts_tenant_action_hash", table_name="action_drafts")
    op.drop_index("ix_action_drafts_tenant_target", table_name="action_drafts")
    op.drop_constraint("uq_action_drafts_tenant_idempotency_key", "action_drafts", type_="unique")

    for column_name in (
        "retention_policy",
        "lifecycle_status",
        "draft_version",
        "execution_mode",
        "draft_outcome",
        "safety_snapshot_hash",
        "safety_snapshot_ref",
        "action_payload_hash",
        "approval_revision_ref",
        "target_id",
        "schema_version",
    ):
        op.drop_column("action_drafts", column_name)

    op.create_unique_constraint(_LEGACY_KEY_CONSTRAINT, "action_drafts", ["idempotency_key"])
