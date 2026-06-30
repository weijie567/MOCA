"""Add Phase 36 merchant scope hardening.

Revision ID: 019_phase36_merchant_scope_hardening
Revises: 018_phase34_approval_action_bindings
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "019_phase36_merchant_scope_hardening"
down_revision: str | None = "018_phase34_approval_action_bindings"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_LEGACY_USERNAME_UNIQUE_CONSTRAINT = "users_username_key"
_LEGACY_USER_MERCHANT_FK_CONSTRAINT = "users_merchant_id_fkey"

_AGENT_RUN_SCOPE_COLUMNS = (
    sa.Column("target_merchant_id", sa.String(length=128)),
    sa.Column("target_merchant_ref", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("scope_classification", sa.String(length=32)),
    sa.Column("scope_source", sa.String(length=64)),
    sa.Column("scope_reason_codes", postgresql.JSONB(astext_type=sa.Text())),
)

_ACTION_SAFETY_SNAPSHOT_SCOPE_COLUMNS = (
    sa.Column("target_merchant_id", sa.String(length=128)),
    sa.Column("target_merchant_ref", postgresql.JSONB(astext_type=sa.Text())),
    sa.Column("business_fact_refs", postgresql.JSONB(astext_type=sa.Text())),
)


def upgrade() -> None:
    _ensure_active_business_users_have_merchant_binding()
    _ensure_no_same_tenant_username_duplicates()

    op.create_unique_constraint("uq_merchants_id_tenant", "merchants", ["id", "tenant_id"])
    op.create_unique_constraint("uq_users_tenant_username", "users", ["tenant_id", "username"])
    # PostgreSQL names the legacy column-level unique constraint users_username_key. Other generated names
    # should be handled by an operator before applying this migration; Phase 36 keeps the fallback explicit.
    op.drop_constraint(_LEGACY_USERNAME_UNIQUE_CONSTRAINT, "users", type_="unique")
    op.create_foreign_key(
        "fk_users_merchant_tenant",
        "users",
        "merchants",
        ["merchant_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    # PostgreSQL names the legacy column-level FK users_merchant_id_fkey. Dropping it after the composite FK
    # is present preserves referential protection while switching to tenant-consistent merchant binding.
    op.drop_constraint(_LEGACY_USER_MERCHANT_FK_CONSTRAINT, "users", type_="foreignkey")
    op.create_check_constraint(
        "ck_users_active_business_role_has_merchant",
        "users",
        "NOT is_active OR role NOT IN ('support', 'manager', 'merchant') OR merchant_id IS NOT NULL",
    )

    for column in _AGENT_RUN_SCOPE_COLUMNS:
        op.add_column("agent_runs", column)
    for column in _ACTION_SAFETY_SNAPSHOT_SCOPE_COLUMNS:
        op.add_column("action_safety_snapshots", column)

    _backfill_legacy_agent_run_scope()
    _ensure_agent_run_scope_rows_safe()
    _ensure_authorization_root_scope_consistency()
    _ensure_no_forbidden_scope_backfill_sources()

    op.alter_column("agent_runs", "scope_classification", existing_type=sa.String(length=32), nullable=False)
    op.create_check_constraint(
        "ck_agent_runs_scope_classification",
        "agent_runs",
        "scope_classification IN ('business_merchant', 'policy_only', 'merchant_not_required', 'unknown_legacy')",
    )
    op.create_check_constraint(
        "ck_agent_runs_scope_target_consistency",
        "agent_runs",
        "((scope_classification = 'business_merchant' "
        "AND target_merchant_id IS NOT NULL AND target_merchant_ref IS NOT NULL) "
        "OR (scope_classification IN ('policy_only', 'merchant_not_required', 'unknown_legacy') "
        "AND target_merchant_id IS NULL AND target_merchant_ref IS NULL))",
    )
    op.create_index(
        "ix_agent_runs_tenant_target_merchant",
        "agent_runs",
        ["tenant_id", "target_merchant_id"],
    )
    op.create_index(
        "ix_agent_runs_tenant_scope_classification",
        "agent_runs",
        ["tenant_id", "scope_classification"],
    )
    op.create_index(
        "ix_action_safety_snapshots_tenant_target_merchant",
        "action_safety_snapshots",
        ["tenant_id", "target_merchant_id"],
    )


def downgrade() -> None:
    # downgrade/reupgrade: dropping Phase 36 scope metadata is irreversible, but this rollback does not delete
    # legacy business rows from agent_runs, approval_requests, action_drafts, or action_safety_snapshots.
    op.drop_index("ix_action_safety_snapshots_tenant_target_merchant", table_name="action_safety_snapshots")
    op.drop_index("ix_agent_runs_tenant_scope_classification", table_name="agent_runs")
    op.drop_index("ix_agent_runs_tenant_target_merchant", table_name="agent_runs")
    op.drop_constraint("ck_agent_runs_scope_target_consistency", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_scope_classification", "agent_runs", type_="check")
    op.drop_constraint("ck_users_active_business_role_has_merchant", "users", type_="check")
    op.drop_constraint("fk_users_merchant_tenant", "users", type_="foreignkey")
    op.drop_constraint("uq_users_tenant_username", "users", type_="unique")
    op.create_unique_constraint(_LEGACY_USERNAME_UNIQUE_CONSTRAINT, "users", ["username"])
    op.drop_constraint("uq_merchants_id_tenant", "merchants", type_="unique")
    op.create_foreign_key(
        _LEGACY_USER_MERCHANT_FK_CONSTRAINT,
        "users",
        "merchants",
        ["merchant_id"],
        ["id"],
    )

    op.drop_column("action_safety_snapshots", "business_fact_refs")
    op.drop_column("action_safety_snapshots", "target_merchant_ref")
    op.drop_column("action_safety_snapshots", "target_merchant_id")
    op.drop_column("agent_runs", "scope_reason_codes")
    op.drop_column("agent_runs", "scope_source")
    op.drop_column("agent_runs", "scope_classification")
    op.drop_column("agent_runs", "target_merchant_ref")
    op.drop_column("agent_runs", "target_merchant_id")


def _backfill_legacy_agent_run_scope() -> None:
    op.execute(
        sa.text(
            """
            UPDATE agent_runs
            SET scope_classification = 'unknown_legacy',
                scope_source = COALESCE(scope_source, 'migration_preflight'),
                scope_reason_codes = COALESCE(
                    scope_reason_codes,
                    '["no_authoritative_scope_proof", "ambiguous_legacy"]'::jsonb
                )
            WHERE scope_classification IS NULL
              AND target_merchant_id IS NULL
              AND target_merchant_ref IS NULL
            """
        )
    )


def _ensure_active_business_users_have_merchant_binding() -> None:
    bind = op.get_bind()
    violation = (
        bind.execute(
            sa.text(
                """
                SELECT
                    u.id,
                    u.tenant_id,
                    u.role,
                    u.merchant_id,
                    m.tenant_id AS merchant_tenant_id,
                    CASE
                        WHEN u.merchant_id IS NULL THEN 'missing merchant binding'
                        WHEN m.id IS NULL THEN 'missing merchant row'
                        ELSE 'cross-tenant merchant binding'
                    END AS reason
                FROM users AS u
                LEFT JOIN merchants AS m ON m.id = u.merchant_id
                WHERE u.is_active IS TRUE
                  AND u.role IN ('support', 'manager', 'merchant')
                  AND (
                    u.merchant_id IS NULL
                    OR m.id IS NULL
                    OR m.tenant_id <> u.tenant_id
                  )
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if violation is not None:
        reason = _business_user_violation_reason(violation)
        raise RuntimeError(
            "Cannot create ck_users_active_business_role_has_merchant/fk_users_merchant_tenant: "
            "active business users without tenant-consistent merchant binding. "
            f"user_id={_row_value(violation, 'id')} tenant_id={_row_value(violation, 'tenant_id')} "
            f"role={_row_value(violation, 'role')} reason={reason}."
        )


def _ensure_no_same_tenant_username_duplicates() -> None:
    bind = op.get_bind()
    duplicate = (
        bind.execute(
            sa.text(
                """
                SELECT tenant_id, username, COUNT(*) AS duplicate_count
                FROM users
                GROUP BY tenant_id, username
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot create uq_users_tenant_username: same-tenant duplicate usernames exist. "
            f"tenant_id={_row_value(duplicate, 'tenant_id')} username={_row_value(duplicate, 'username')} "
            f"duplicate_count={_row_value(duplicate, 'duplicate_count')}."
        )


def _ensure_agent_run_scope_rows_safe() -> None:
    bind = op.get_bind()
    violation = (
        bind.execute(
            sa.text(
                """
                SELECT
                    id,
                    tenant_id,
                    scope_classification,
                    target_merchant_id,
                    CASE
                        WHEN scope_classification = 'business_merchant'
                             AND target_merchant_id IS NULL
                            THEN 'missing target_merchant_id'
                        WHEN scope_classification = 'business_merchant'
                             AND target_merchant_ref IS NULL
                            THEN 'missing target_merchant_ref'
                        WHEN scope_classification = 'business_merchant'
                             AND (
                                target_merchant_ref ->> 'schema_version' IS DISTINCT FROM
                                    'target_merchant_binding.v1'
                                OR target_merchant_ref ->> 'target_merchant_id' IS NULL
                                OR target_merchant_ref ->> 'target_merchant_id' IS DISTINCT FROM target_merchant_id
                             )
                            THEN 'malformed target_merchant_ref'
                        WHEN scope_classification = 'unknown_legacy'
                             AND (target_merchant_id IS NOT NULL OR target_merchant_ref IS NOT NULL)
                            THEN 'ambiguous_legacy carries target merchant'
                        ELSE 'non-business scope carries target merchant'
                    END AS reason
                FROM agent_runs
                WHERE (
                    scope_classification = 'business_merchant'
                    AND (
                        target_merchant_id IS NULL
                        OR target_merchant_ref IS NULL
                        OR target_merchant_ref ->> 'schema_version' IS DISTINCT FROM
                            'target_merchant_binding.v1'
                        OR target_merchant_ref ->> 'target_merchant_id' IS NULL
                        OR target_merchant_ref ->> 'target_merchant_id' IS DISTINCT FROM target_merchant_id
                    )
                )
                OR (
                    scope_classification IN ('policy_only', 'merchant_not_required', 'unknown_legacy')
                    AND (target_merchant_id IS NOT NULL OR target_merchant_ref IS NOT NULL)
                )
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if violation is not None:
        raise RuntimeError(
            "Cannot create ck_agent_runs_scope_target_consistency: unsafe AgentRun target scope row. "
            f"run_id={_row_value(violation, 'id')} tenant_id={_row_value(violation, 'tenant_id')} "
            f"classification={_row_value(violation, 'scope_classification')} "
            f"reason={_row_value(violation, 'reason')}. "
            "A business_merchant run needs one valid target binding; multiple target merchants, "
            "missing target_merchant_id, missing target_merchant_ref, or malformed target_merchant_ref block migration."
        )


def _ensure_authorization_root_scope_consistency() -> None:
    bind = op.get_bind()
    violation = (
        bind.execute(
            sa.text(
                """
                WITH root_scope AS (
                    SELECT
                        'approval_requests' AS root_table,
                        id::text AS id,
                        run_id,
                        tenant_id,
                        target_merchant_id,
                        target_merchant_ref
                    FROM approval_requests
                    UNION ALL
                    SELECT
                        'action_drafts' AS root_table,
                        id::text AS id,
                        run_id,
                        tenant_id,
                        target_merchant_id,
                        target_merchant_ref
                    FROM action_drafts
                    UNION ALL
                    SELECT
                        'action_safety_snapshots' AS root_table,
                        id::text AS id,
                        run_id,
                        tenant_id,
                        target_merchant_id,
                        target_merchant_ref
                    FROM action_safety_snapshots
                )
                SELECT
                    root_scope.root_table,
                    root_scope.id,
                    root_scope.run_id,
                    root_scope.tenant_id,
                    root_scope.target_merchant_id AS root_target_merchant_id,
                    agent_runs.target_merchant_id AS run_target_merchant_id,
                    CASE
                        WHEN agent_runs.target_merchant_id IS NULL THEN 'missing target_merchant_id'
                        WHEN agent_runs.target_merchant_ref IS NULL THEN 'missing target_merchant_ref'
                        WHEN root_scope.target_merchant_id IS NULL THEN 'missing target_merchant_id'
                        WHEN root_scope.target_merchant_ref IS NULL THEN 'missing target_merchant_ref'
                        WHEN root_scope.target_merchant_ref ->> 'schema_version' IS DISTINCT FROM
                            'target_merchant_binding.v1'
                            THEN 'malformed target_merchant_ref'
                        WHEN root_scope.target_merchant_ref ->> 'target_merchant_id'
                             IS DISTINCT FROM root_scope.target_merchant_id
                            THEN 'mismatched target_merchant_ref'
                        ELSE 'contradictory target merchant'
                    END AS reason
                FROM root_scope
                JOIN agent_runs
                  ON agent_runs.id = root_scope.run_id
                 AND agent_runs.tenant_id = root_scope.tenant_id
                WHERE agent_runs.scope_classification = 'business_merchant'
                  AND (
                    agent_runs.target_merchant_id IS NULL
                    OR agent_runs.target_merchant_ref IS NULL
                    OR root_scope.target_merchant_id IS NULL
                    OR root_scope.target_merchant_ref IS NULL
                    OR root_scope.target_merchant_ref ->> 'schema_version' IS DISTINCT FROM
                        'target_merchant_binding.v1'
                    OR root_scope.target_merchant_ref ->> 'target_merchant_id'
                        IS DISTINCT FROM root_scope.target_merchant_id
                    OR root_scope.target_merchant_id IS DISTINCT FROM agent_runs.target_merchant_id
                    OR root_scope.target_merchant_ref ->> 'target_merchant_id'
                        IS DISTINCT FROM agent_runs.target_merchant_id
                  )
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if violation is not None:
        raise RuntimeError(
            "Cannot harden authorization root target scope: "
            f"{_row_value(violation, 'root_table')} row contradicts linked business_merchant AgentRun. "
            f"root_id={_row_value(violation, 'id')} run_id={_row_value(violation, 'run_id')} "
            f"reason={_row_value(violation, 'reason')}. "
            "approval_requests, action_drafts, and action_safety_snapshots must match the linked run target."
        )


def _row_value(row: Mapping[str, Any], key: str, default: str = "unknown") -> Any:
    return row[key] if key in row else default


def _business_user_violation_reason(row: Mapping[str, Any]) -> str:
    explicit = _row_value(row, "reason", None)
    if explicit is not None:
        return str(explicit)
    if _row_value(row, "merchant_id", None) is None:
        return "missing merchant binding"
    merchant_tenant_id = _row_value(row, "merchant_tenant_id", None)
    if merchant_tenant_id is None:
        return "missing merchant row"
    if merchant_tenant_id != _row_value(row, "tenant_id", None):
        return "cross-tenant merchant binding"
    return "unknown"


def _ensure_no_forbidden_scope_backfill_sources() -> None:
    forbidden_tokens = (
        "requested_by",
        "user.merchant_id",
        "thread_id",
        "input_query",
        "final_response",
        "prompt",
        "memory",
        "rag",
        "llm",
        "raw_tool_payload",
        "raw_payload",
    )
    source = Path(__file__).read_text(encoding="utf-8")
    guard_marker = "def _ensure_no_forbidden_scope_backfill_sources("
    guarded_prefix = source.split(guard_marker, 1)[0]
    violations = [token for token in forbidden_tokens if token in guarded_prefix]
    if violations:
        raise RuntimeError(
            "Forbidden weak AgentRun scope backfill source tokens found outside the source guard: "
            + ", ".join(violations)
        )
