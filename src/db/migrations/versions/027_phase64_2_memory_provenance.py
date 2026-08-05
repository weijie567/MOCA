"""Add canonical reviewed-memory provenance and normalized lineage.

Revision ID: 027_phase64_2_memory_provenance
Revises: 026_phase64_2_evidence_cutover
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "027_phase64_2_memory_provenance"
down_revision: str | None = "026_phase64_2_evidence_cutover"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("case_memories", sa.Column("identity_algorithm_version", sa.String(length=64)))
    op.add_column("case_memories", sa.Column("candidate_hash", sa.String(length=80)))
    op.add_column("case_memories", sa.Column("identity_resolution_status", sa.String(length=32)))
    op.add_column(
        "case_memories",
        sa.Column("provenance_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.add_column(
        "case_memories",
        sa.Column("lifecycle_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "case_memories",
        sa.Column("corrects_case_memory_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "case_memories",
        sa.Column("supersedes_case_memory_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_unique_constraint("uq_case_memories_id_tenant", "case_memories", ["id", "tenant_id"])
    op.create_foreign_key(
        "fk_case_memories_corrects_tenant",
        "case_memories",
        "case_memories",
        ["corrects_case_memory_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_case_memories_supersedes_tenant",
        "case_memories",
        "case_memories",
        ["supersedes_case_memory_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )

    _backfill_unresolved_legacy_provenance()

    op.alter_column("case_memories", "identity_resolution_status", nullable=False)
    op.alter_column("case_memories", "provenance_json", nullable=False)
    op.create_check_constraint(
        "ck_case_memories_identity_resolution_status",
        "case_memories",
        "identity_resolution_status IN ('canonical', 'legacy_resolved', 'legacy_unresolved')",
    )
    op.create_check_constraint(
        "ck_case_memories_lifecycle_version_positive",
        "case_memories",
        "lifecycle_version > 0",
    )
    op.create_index(
        "ix_case_memories_resolution_status",
        "case_memories",
        ["tenant_id", "identity_resolution_status", "review_status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "case_memory_lineage_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("survivor_case_memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("related_case_memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["survivor_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_lineage_survivor_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_lineage_related_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "survivor_case_memory_id",
            "related_case_memory_id",
            "relation",
            name="uq_case_memory_lineage_pair_relation",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "survivor_case_memory_id",
            "relation",
            "ordinal",
            name="uq_case_memory_lineage_survivor_relation_ordinal",
        ),
        sa.CheckConstraint(
            "survivor_case_memory_id <> related_case_memory_id",
            name="ck_case_memory_lineage_distinct_nodes",
        ),
        sa.CheckConstraint(
            "relation IN ('duplicate', 'correction', 'supersession')",
            name="ck_case_memory_lineage_relation",
        ),
        sa.CheckConstraint("ordinal > 0", name="ck_case_memory_lineage_ordinal_positive"),
    )
    op.create_index(
        "ix_case_memory_lineage_survivor",
        "case_memory_lineage_links",
        ["tenant_id", "survivor_case_memory_id", "relation", "ordinal"],
    )


def downgrade() -> None:
    _assert_downgrade_safe()
    op.drop_index("ix_case_memory_lineage_survivor", table_name="case_memory_lineage_links")
    op.drop_table("case_memory_lineage_links")
    op.drop_index("ix_case_memories_resolution_status", table_name="case_memories")
    op.drop_constraint("ck_case_memories_lifecycle_version_positive", "case_memories", type_="check")
    op.drop_constraint("ck_case_memories_identity_resolution_status", "case_memories", type_="check")
    op.drop_constraint("fk_case_memories_supersedes_tenant", "case_memories", type_="foreignkey")
    op.drop_constraint("fk_case_memories_corrects_tenant", "case_memories", type_="foreignkey")
    op.drop_constraint("uq_case_memories_id_tenant", "case_memories", type_="unique")
    op.drop_column("case_memories", "supersedes_case_memory_id")
    op.drop_column("case_memories", "corrects_case_memory_id")
    op.drop_column("case_memories", "lifecycle_version")
    op.drop_column("case_memories", "provenance_json")
    op.drop_column("case_memories", "identity_resolution_status")
    op.drop_column("case_memories", "candidate_hash")
    op.drop_column("case_memories", "identity_algorithm_version")


def _backfill_unresolved_legacy_provenance() -> None:
    """Preserve literal legacy material; no pre-027 row proves complete authority."""

    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, tenant_id, content_hash, source_identity_hash, source_ref_json, policy_refs_json "
                "FROM case_memories ORDER BY created_at, id"
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        envelope = _legacy_unresolved_payload(row)
        bind.execute(
            sa.text(
                "UPDATE case_memories SET identity_resolution_status = 'legacy_unresolved', "
                "identity_algorithm_version = NULL, candidate_hash = NULL, "
                "provenance_json = CAST(:provenance AS jsonb), lifecycle_version = 1 WHERE id = :id"
            ),
            {"id": row["id"], "provenance": json.dumps(envelope, ensure_ascii=False)},
        )


def _legacy_unresolved_payload(row: Mapping[str, object]) -> dict[str, object]:
    reasons = ["pre_027_provenance_unavailable"]
    if not row.get("content_hash") or not row.get("source_identity_hash"):
        reasons.append("missing_identity_hash")
    else:
        reasons.append("identity_hash_unverified")
    source_ref = row.get("source_ref_json")
    policy_refs = row.get("policy_refs_json")
    if not isinstance(source_ref, dict) or not source_ref:
        reasons.append("incomplete_source_authority")
    if policy_refs and (
        not isinstance(policy_refs, list)
        or any(not _is_complete_canonical_evidence_ref(value, tenant_id=str(row["tenant_id"])) for value in policy_refs)
    ):
        reasons.append("incomplete_evidence_identity")
    return {
        "schema_version": "case_memory_provenance_legacy_unresolved.v1",
        "resolution_status": "legacy_unresolved",
        "tenant_id": str(row["tenant_id"]),
        "case_memory_id": str(row["id"]),
        "legacy_content_hash": row.get("content_hash"),
        "legacy_source_identity_hash": row.get("source_identity_hash"),
        "legacy_source_ref": source_ref if isinstance(source_ref, dict) else {},
        "legacy_policy_refs": policy_refs if isinstance(policy_refs, list) else [],
        "unresolved_reasons": list(dict.fromkeys(reasons)),
    }


def _is_complete_canonical_evidence_ref(value: object, *, tenant_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("tenant_id") == tenant_id
        and value.get("scope_type") == "tenant_policy"
        and value.get("scope_id") == tenant_id
        and all(
            value.get(key) is not None
            for key in (
                "evidence_id",
                "doc_key",
                "chunk_id",
                "policy_version",
                "text_hash",
                "document_version_id",
                "chunk_version_id",
                "document_version",
                "chunk_version",
                "retrieved_at",
                "retrieval_config_version",
            )
        )
    )


def _assert_downgrade_safe() -> None:
    bind = op.get_bind()
    lineage_count = int(bind.execute(sa.text("SELECT count(*) FROM case_memory_lineage_links")).scalar_one())
    resolved_count = int(
        bind.execute(
            sa.text(
                "SELECT count(*) FROM case_memories "
                "WHERE identity_resolution_status IN ('canonical', 'legacy_resolved')"
            )
        ).scalar_one()
    )
    if lineage_count or resolved_count:
        raise RuntimeError("cannot downgrade while canonical provenance or case-memory lineage is retained")
