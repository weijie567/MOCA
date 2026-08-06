"""Add durable exact-identity claims and deterministic duplicate lineage.

Revision ID: 028_phase64_2_memory_lifecycle
Revises: 027_phase64_2_memory_provenance
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "028_phase64_2_memory_lifecycle"
down_revision: str | None = "027_phase64_2_memory_provenance"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_RESOLVED_FILTER = "identity_resolution_status IN ('canonical', 'legacy_resolved')"
_ACTIVE_REVIEW_STATUSES = {"auto_approved", "needs_review", "approved"}
_TERMINAL_REVIEW_STATUSES = {"rejected", "superseded", "deleted", "tombstoned"}
_DUPLICATE_REASON = "phase64_2_exact_identity_duplicate"


def upgrade() -> None:
    classified = _classify_identity_rows()
    op.create_table(
        "case_memory_identity_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("identity_algorithm_version", sa.String(length=64), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_hash", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("source_identity_hash", sa.String(length=80), nullable=False),
        sa.Column("owner_case_memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("terminal_status", sa.String(length=32)),
        sa.Column("terminal_reason", sa.String(length=128)),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "identity_algorithm_version",
            "tenant_id",
            "scope_type",
            "scope_id",
            "candidate_hash",
            "content_hash",
            "source_identity_hash",
            name="uq_case_memory_identity_claims_exact_identity",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "owner_case_memory_id",
            name="uq_case_memory_identity_claims_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_identity_claims_owner_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "scope_type IN ('tenant', 'merchant', 'user', 'thread', 'case')",
            name="ck_case_memory_identity_claims_scope_type",
        ),
        sa.CheckConstraint(
            "candidate_hash ~ '^sha256:[0-9a-f]{64}$' "
            "AND content_hash ~ '^sha256:[0-9a-f]{64}$' "
            "AND source_identity_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_case_memory_identity_claims_hashes",
        ),
        sa.CheckConstraint(
            "claim_state IN ('active', 'terminal')",
            name="ck_case_memory_identity_claims_state",
        ),
        sa.CheckConstraint(
            "((claim_state = 'active' AND terminal_status IS NULL "
            "AND terminal_reason IS NULL AND terminal_at IS NULL) OR "
            "(claim_state = 'terminal' "
            "AND terminal_status IN ('rejected', 'superseded', 'deleted', 'tombstoned') "
            "AND terminal_reason IS NOT NULL AND terminal_at IS NOT NULL))",
            name="ck_case_memory_identity_claims_terminal_fields",
        ),
        sa.CheckConstraint(
            "lifecycle_version > 0",
            name="ck_case_memory_identity_claims_lifecycle_version_positive",
        ),
    )
    op.create_index(
        "ix_case_memory_identity_claims_owner",
        "case_memory_identity_claims",
        ["tenant_id", "owner_case_memory_id"],
    )
    op.create_index(
        "ix_case_memory_identity_claims_state",
        "case_memory_identity_claims",
        ["tenant_id", "claim_state"],
    )
    op.create_index(
        "ix_case_memories_active_exact_identity",
        "case_memories",
        [
            "identity_algorithm_version",
            "tenant_id",
            "scope_type",
            "scope_id",
            "candidate_hash",
            "content_hash",
            "source_identity_hash",
        ],
        postgresql_where=sa.text(
            "deleted_at IS NULL "
            "AND identity_resolution_status IN ('canonical', 'legacy_resolved') "
            "AND review_status IN ('auto_approved', 'needs_review', 'approved')"
        ),
    )
    _apply_identity_classification(classified)


def downgrade() -> None:
    _assert_downgrade_safe()
    op.drop_index("ix_case_memories_active_exact_identity", table_name="case_memories")
    op.drop_index("ix_case_memory_identity_claims_state", table_name="case_memory_identity_claims")
    op.drop_index("ix_case_memory_identity_claims_owner", table_name="case_memory_identity_claims")
    op.drop_table("case_memory_identity_claims")


def _classify_identity_rows() -> list[list[Mapping[str, object]]]:
    """Dry-run the full-key grouping before installing any no-resurrection claim."""

    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id, tenant_id, identity_algorithm_version, scope_type, scope_id, candidate_hash, "
                "content_hash, source_identity_hash, review_status, review_reason, lifecycle_version, "
                "expires_at, deleted_at, reviewed_at, created_at, updated_at "
                "FROM case_memories WHERE " + _RESOLVED_FILTER + " ORDER BY created_at, id"
            )
        )
        .mappings()
        .all()
    )
    key_columns = (
        "identity_algorithm_version",
        "tenant_id",
        "scope_type",
        "scope_id",
        "candidate_hash",
        "content_hash",
        "source_identity_hash",
    )
    missing = [str(row["id"]) for row in rows if any(row.get(column) is None for column in key_columns)]
    if missing:
        raise RuntimeError("resolved case-memory rows lack complete exact identity: " + ",".join(missing))

    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[column] for column in key_columns)].append(row)
    return list(groups.values())


def _apply_identity_classification(groups: list[list[Mapping[str, object]]]) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for group in groups:
        owner = group[0]
        for ordinal, duplicate in enumerate(group[1:], start=1):
            audit_reason = f"{_DUPLICATE_REASON}:{owner['id']}"
            bind.execute(
                sa.text(
                    "UPDATE case_memories SET review_status = 'superseded', "
                    "review_reason = CASE WHEN review_reason IS NULL OR btrim(review_reason) = '' "
                    "THEN :reason ELSE review_reason || '; ' || :reason END, "
                    "lifecycle_version = lifecycle_version + 1, updated_at = :now WHERE id = :id"
                ),
                {"id": duplicate["id"], "reason": audit_reason, "now": now},
            )
            bind.execute(
                sa.text(
                    "INSERT INTO case_memory_lineage_links "
                    "(id, tenant_id, survivor_case_memory_id, related_case_memory_id, relation, ordinal) "
                    "VALUES (:id, :tenant_id, :owner, :related, 'duplicate', :ordinal)"
                ),
                {
                    "id": uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"case-memory-duplicate:{owner['tenant_id']}:{owner['id']}:{duplicate['id']}",
                    ),
                    "tenant_id": owner["tenant_id"],
                    "owner": owner["id"],
                    "related": duplicate["id"],
                    "ordinal": ordinal,
                },
            )

        state = _claim_state(owner, now=now)
        if state[0] == "terminal" and state[1] == "superseded" and state[2] == "pending_review_expired":
            bind.execute(
                sa.text(
                    "UPDATE case_memories SET review_status = 'superseded', "
                    "review_reason = CASE WHEN review_reason IS NULL OR btrim(review_reason) = '' "
                    "THEN 'pending_review_expired' ELSE review_reason || '; pending_review_expired' END, "
                    "lifecycle_version = lifecycle_version + 1, updated_at = :now WHERE id = :id"
                ),
                {"id": owner["id"], "now": now},
            )
            owner = dict(owner)
            owner["lifecycle_version"] = int(owner["lifecycle_version"]) + 1
        bind.execute(
            sa.text(
                "INSERT INTO case_memory_identity_claims "
                "(id, identity_algorithm_version, tenant_id, scope_type, scope_id, candidate_hash, "
                "content_hash, source_identity_hash, owner_case_memory_id, claim_state, terminal_status, "
                "terminal_reason, terminal_at, lifecycle_version) "
                "VALUES (:id, :identity_algorithm_version, :tenant_id, :scope_type, :scope_id, "
                ":candidate_hash, :content_hash, :source_identity_hash, :owner_case_memory_id, "
                ":claim_state, :terminal_status, :terminal_reason, :terminal_at, :lifecycle_version)"
            ),
            {
                "id": uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    "case-memory-identity-claim:"
                    + ":".join(
                        str(owner[column])
                        for column in (
                            "identity_algorithm_version",
                            "tenant_id",
                            "scope_type",
                            "scope_id",
                            "candidate_hash",
                            "content_hash",
                            "source_identity_hash",
                        )
                    ),
                ),
                "identity_algorithm_version": owner["identity_algorithm_version"],
                "tenant_id": owner["tenant_id"],
                "scope_type": owner["scope_type"],
                "scope_id": owner["scope_id"],
                "candidate_hash": owner["candidate_hash"],
                "content_hash": owner["content_hash"],
                "source_identity_hash": owner["source_identity_hash"],
                "owner_case_memory_id": owner["id"],
                "claim_state": state[0],
                "terminal_status": state[1],
                "terminal_reason": state[2],
                "terminal_at": state[3],
                "lifecycle_version": owner["lifecycle_version"],
            },
        )


def _claim_state(
    row: Mapping[str, object],
    *,
    now: datetime,
) -> tuple[str, str | None, str | None, datetime | None]:
    review_status = str(row["review_status"])
    expires_at = row.get("expires_at")
    if review_status == "needs_review" and isinstance(expires_at, datetime) and expires_at <= now:
        return "terminal", "superseded", "pending_review_expired", now
    if row.get("deleted_at") is not None:
        status = review_status if review_status in {"deleted", "tombstoned"} else "deleted"
        return "terminal", status, "migration_backfill_terminal", _timestamp(row, now=now)
    if review_status in _TERMINAL_REVIEW_STATUSES:
        return "terminal", review_status, "migration_backfill_terminal", _timestamp(row, now=now)
    if review_status not in _ACTIVE_REVIEW_STATUSES:
        raise RuntimeError(f"unsupported case-memory review status during claim backfill: {review_status}")
    if isinstance(expires_at, datetime) and expires_at <= now:
        return "terminal", "superseded", "migration_backfill_expired", now
    return "active", None, None, None


def _timestamp(row: Mapping[str, object], *, now: datetime) -> datetime:
    for column in ("deleted_at", "reviewed_at", "updated_at", "created_at"):
        value = row.get(column)
        if isinstance(value, datetime):
            return value
    return now


def _assert_downgrade_safe() -> None:
    bind = op.get_bind()
    claim_count = int(bind.execute(sa.text("SELECT count(*) FROM case_memory_identity_claims")).scalar_one())
    lineage_count = int(bind.execute(sa.text("SELECT count(*) FROM case_memory_lineage_links")).scalar_one())
    if claim_count or lineage_count:
        raise RuntimeError("cannot downgrade while case-memory claim or lineage history is retained")
