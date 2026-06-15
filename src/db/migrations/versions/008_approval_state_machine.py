"""Add approval state machine schema.

Revision ID: 008_approval_state_machine
Revises: 007_session_memories
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "008_approval_state_machine"
down_revision: str | None = "007_session_memories"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


# risk_level and risk_rule_ref already exist from 005_approval_tables; migration 008
# keeps them as the v2 risk binding fields instead of adding duplicate columns.
_APPROVAL_REQUEST_V2_COLUMNS = (
    "schema_version",
    "approval_policy_id",
    "policy_version",
    "risk_level",
    "risk_rule_ref",
    "revision",
    "version",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
    "legacy_non_executable",
    "superseded_by_request_id",
    "clarification_request_id",
)


def upgrade() -> None:
    for column in (
        sa.Column("schema_version", sa.String(length=48)),
        sa.Column("approval_policy_id", sa.String(length=64)),
        sa.Column("policy_version", sa.String(length=64)),
        sa.Column("revision", sa.Integer()),
        sa.Column("version", sa.Integer()),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("safety_snapshot_ref", sa.String(length=128)),
        sa.Column("safety_snapshot_hash", sa.String(length=128)),
        sa.Column("legacy_non_executable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("superseded_by_request_id", postgresql.UUID(as_uuid=True)),
        sa.Column("clarification_request_id", sa.String(length=128)),
    ):
        op.add_column("approval_requests", column)

    op.create_foreign_key(
        "fk_approval_requests_superseded_by",
        "approval_requests",
        "approval_requests",
        ["superseded_by_request_id"],
        ["id"],
    )

    op.execute(
        """
        UPDATE approval_requests
        SET
            schema_version = 'approval_request.v1',
            version = COALESCE(version, 1),
            legacy_non_executable = TRUE
        WHERE action_payload_hash IS NULL
           OR safety_snapshot_hash IS NULL
        """
    )
    op.execute(
        """
        WITH ranked_legacy AS (
            SELECT
                id,
                row_number() over (
                    partition by tenant_id, run_id
                    order by created_at, id
                ) AS deterministic_revision
            FROM approval_requests
            WHERE revision IS NULL
        )
        UPDATE approval_requests
        SET revision = ranked_legacy.deterministic_revision
        FROM ranked_legacy
        WHERE approval_requests.id = ranked_legacy.id
        """
    )

    op.create_check_constraint(
        "ck_approval_requests_status",
        "approval_requests",
        "status IN ('pending', 'needs_info', 'approved', 'rejected', 'cancelled', 'expired', 'superseded')",
    )
    op.create_unique_constraint(
        "uq_approval_requests_tenant_run_revision",
        "approval_requests",
        ["tenant_id", "run_id", "revision"],
    )
    op.create_index(
        "uq_approval_requests_active_revision",
        "approval_requests",
        ["tenant_id", "run_id"],
        unique=True,
        postgresql_where=sa.text("legacy_non_executable IS FALSE AND status IN ('pending', 'needs_info')"),
    )
    op.create_index(
        "ix_approval_requests_tenant_action_hash",
        "approval_requests",
        ["tenant_id", "action_payload_hash"],
    )

    op.create_table(
        "action_safety_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=48),
            nullable=False,
            server_default="action_safety_snapshot.v1",
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("snapshot_ref", sa.String(length=128), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("immutable_hash", sa.String(length=128), nullable=False),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("policy_config_version", sa.String(length=64), nullable=False),
        sa.Column("risk_config_version", sa.String(length=64), nullable=False),
        sa.Column("retrieval_config_version", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "immutable_hash", name="uq_action_safety_snapshots_tenant_hash"),
    )
    op.create_index("ix_action_safety_snapshots_tenant_id", "action_safety_snapshots", ["tenant_id"])
    op.create_index("ix_action_safety_snapshots_run_id", "action_safety_snapshots", ["run_id"])
    op.create_index(
        "ix_action_safety_snapshots_tenant_hash",
        "action_safety_snapshots",
        ["tenant_id", "immutable_hash"],
    )

    op.create_table(
        "approval_levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "approval_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_requests.id"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="approval_level.v2"),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("required_role", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="any_one"),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("escalated_to_level", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("approval_request_id", "level_number", name="uq_approval_levels_request_level"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'skipped')",
            name="ck_approval_levels_status",
        ),
        sa.CheckConstraint("mode IN ('any_one', 'all')", name="ck_approval_levels_mode"),
    )
    op.create_index("ix_approval_levels_request", "approval_levels", ["approval_request_id"])
    op.create_index("ix_approval_levels_status", "approval_levels", ["status"])

    op.create_table(
        "approval_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "approval_level_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_levels.id"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="approval_assignment.v2"),
        sa.Column("assigned_role", sa.String(length=64), nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'skipped')",
            name="ck_approval_assignments_status",
        ),
    )
    op.create_index("ix_approval_assignments_level", "approval_assignments", ["approval_level_id"])
    op.create_index("ix_approval_assignments_status", "approval_assignments", ["status"])

    op.create_table(
        "approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "approval_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_requests.id"),
            nullable=False,
        ),
        sa.Column(
            "approval_level_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_levels.id"),
            nullable=False,
        ),
        sa.Column(
            "approval_assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_assignments.id"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="approval_decision.v2"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("request_version", sa.Integer(), nullable=False),
        sa.Column("level_version", sa.Integer(), nullable=False),
        sa.Column("level_mode", sa.String(length=32), nullable=False),
        sa.Column("assignment_version", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("response_text", sa.Text()),
        sa.Column("edited_action_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "decision_type IN ('accept', 'approve', 'edit', 'reject', 'respond', 'ignore', 'expire')",
            name="ck_approval_decisions_type",
        ),
        sa.CheckConstraint("level_mode IN ('any_one', 'all')", name="ck_approval_decisions_level_mode"),
    )
    op.create_index("ix_approval_decisions_request", "approval_decisions", ["approval_request_id"])
    op.create_index("ix_approval_decisions_level", "approval_decisions", ["approval_level_id"])
    op.create_index("ix_approval_decisions_assignment", "approval_decisions", ["approval_assignment_id"])
    op.create_index("ix_approval_decisions_tenant_run", "approval_decisions", ["tenant_id", "run_id"])
    op.create_index(
        "uq_approval_decisions_active_assignment",
        "approval_decisions",
        ["approval_assignment_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND archived_at IS NULL AND decision_type IN ('accept', 'approve')"
        ),
    )
    op.create_index(
        "uq_approval_decisions_winning_accept_level",
        "approval_decisions",
        ["approval_level_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND level_mode = 'any_one' AND decision_type IN ('accept', 'approve')"
        ),
    )

    op.create_table(
        "approval_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "approval_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_requests.id"),
            nullable=False,
        ),
        sa.Column("approval_decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_decisions.id")),
        sa.Column("replay_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_trace_events.event_id")),
        sa.Column("schema_version", sa.String(length=48), nullable=False, server_default="approval_event.v2"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("request_version", sa.Integer(), nullable=False),
        sa.Column("level_version", sa.Integer()),
        sa.Column("assignment_version", sa.Integer()),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "resource_refs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "redacted_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_approval_events_request", "approval_events", ["approval_request_id"])
    op.create_index("ix_approval_events_decision", "approval_events", ["approval_decision_id"])
    op.create_index("ix_approval_events_replay_event", "approval_events", ["replay_event_id"])
    op.create_index("ix_approval_events_tenant_run", "approval_events", ["tenant_id", "run_id"])
    op.create_index("ix_approval_events_event_type", "approval_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_approval_events_event_type", table_name="approval_events")
    op.drop_index("ix_approval_events_tenant_run", table_name="approval_events")
    op.drop_index("ix_approval_events_replay_event", table_name="approval_events")
    op.drop_index("ix_approval_events_decision", table_name="approval_events")
    op.drop_index("ix_approval_events_request", table_name="approval_events")
    op.drop_table("approval_events")

    op.drop_index("uq_approval_decisions_winning_accept_level", table_name="approval_decisions")
    op.drop_index("uq_approval_decisions_active_assignment", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_tenant_run", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_assignment", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_level", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_request", table_name="approval_decisions")
    op.drop_table("approval_decisions")

    op.drop_index("ix_approval_assignments_status", table_name="approval_assignments")
    op.drop_index("ix_approval_assignments_level", table_name="approval_assignments")
    op.drop_table("approval_assignments")

    op.drop_index("ix_approval_levels_status", table_name="approval_levels")
    op.drop_index("ix_approval_levels_request", table_name="approval_levels")
    op.drop_table("approval_levels")

    op.drop_index("ix_action_safety_snapshots_tenant_hash", table_name="action_safety_snapshots")
    op.drop_index("ix_action_safety_snapshots_run_id", table_name="action_safety_snapshots")
    op.drop_index("ix_action_safety_snapshots_tenant_id", table_name="action_safety_snapshots")
    op.drop_table("action_safety_snapshots")

    op.drop_index("ix_approval_requests_tenant_action_hash", table_name="approval_requests")
    op.drop_index("uq_approval_requests_active_revision", table_name="approval_requests")
    op.drop_constraint("uq_approval_requests_tenant_run_revision", "approval_requests", type_="unique")
    op.drop_constraint("ck_approval_requests_status", "approval_requests", type_="check")
    op.drop_constraint("fk_approval_requests_superseded_by", "approval_requests", type_="foreignkey")

    for column_name in reversed(
        (
            "schema_version",
            "approval_policy_id",
            "policy_version",
            "revision",
            "version",
            "action_payload_hash",
            "safety_snapshot_ref",
            "safety_snapshot_hash",
            "legacy_non_executable",
            "superseded_by_request_id",
            "clarification_request_id",
        )
    ):
        op.drop_column("approval_requests", column_name)
