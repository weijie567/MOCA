"""Add immutable evidence identity and retention foundation.

Revision ID: 025_phase64_2_immutable_evidence
Revises: 024_phase64_1_resume_attempt_lease
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "025_phase64_2_immutable_evidence"
down_revision: str | None = "024_phase64_1_resume_attempt_lease"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SOURCE_LOCATOR_CHECK = (
    "jsonb_typeof(source_locator_json) = 'object' "
    "AND source_locator_json ? 'source_type' "
    "AND (source_locator_json - "
    "ARRAY['source_type', 'source_checksum', 'source_uri', 'page_number', 'source_block_refs']::text[]) "
    "= '{}'::jsonb"
)
_LIFECYCLE_CHECK = "lifecycle_status IN ('active', 'superseded', 'corrected', 'expired', 'tombstoned')"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_policy_documents_id_tenant",
        "policy_documents",
        ["id", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_agent_trace_events_event_tenant",
        "agent_trace_events",
        ["event_id", "tenant_id"],
    )
    op.add_column("policy_documents", sa.Column("evidence_write_sequence", sa.BigInteger(), nullable=True))
    op.add_column("policy_chunks", sa.Column("evidence_write_sequence", sa.BigInteger(), nullable=True))
    op.add_column(
        "agent_trace_events",
        sa.Column("evidence_snapshot_refs_json", postgresql.JSONB(), nullable=True),
    )
    op.execute("CREATE SEQUENCE evidence_ingestion_write_seq AS BIGINT START WITH 1 INCREMENT BY 1 MINVALUE 1 NO CYCLE")

    op.create_table(
        "policy_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("doc_key", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.Column("source_locator_json", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrects_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_policy_document_versions_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            name="uq_policy_document_versions_logical",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            name="uq_policy_document_versions_identity",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["policy_document_id", "tenant_id"],
            ["policy_documents.id", "policy_documents.tenant_id"],
            name="fk_policy_document_versions_head_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_policy_document_versions_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corrects_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_policy_document_versions_corrects_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "scope_type = 'tenant_policy' AND scope_id = CAST(tenant_id AS VARCHAR)",
            name="ck_policy_document_versions_tenant_policy_scope",
        ),
        sa.CheckConstraint(
            "document_version > 0",
            name="ck_policy_document_versions_document_version_positive",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_policy_document_versions_content_hash",
        ),
        sa.CheckConstraint(_SOURCE_LOCATOR_CHECK, name="ck_policy_document_versions_source_locator_allowlist"),
        sa.CheckConstraint(_LIFECYCLE_CHECK, name="ck_policy_document_versions_lifecycle_status"),
    )
    op.create_index(
        "ix_policy_document_versions_tenant_doc_version",
        "policy_document_versions",
        ["tenant_id", "doc_key", "document_version"],
    )
    op.create_index(
        "ix_policy_document_versions_retention",
        "policy_document_versions",
        ["retention_until"],
    )

    op.create_table(
        "policy_chunk_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("doc_key", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=71), nullable=False),
        sa.Column("source_locator_json", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrects_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_policy_chunk_versions_id_tenant"),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "policy_document_version_id",
            name="uq_policy_chunk_versions_id_tenant_document",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            "chunk_id",
            "chunk_version",
            name="uq_policy_chunk_versions_identity",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            [
                "policy_document_version_id",
                "tenant_id",
                "scope_type",
                "scope_id",
                "doc_key",
                "document_version",
            ],
            [
                "policy_document_versions.id",
                "policy_document_versions.tenant_id",
                "policy_document_versions.scope_type",
                "policy_document_versions.scope_id",
                "policy_document_versions.doc_key",
                "policy_document_versions.document_version",
            ],
            name="fk_policy_chunk_versions_document_identity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id", "tenant_id"],
            ["policy_chunk_versions.id", "policy_chunk_versions.tenant_id"],
            name="fk_policy_chunk_versions_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corrects_version_id", "tenant_id"],
            ["policy_chunk_versions.id", "policy_chunk_versions.tenant_id"],
            name="fk_policy_chunk_versions_corrects_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "scope_type = 'tenant_policy' AND scope_id = CAST(tenant_id AS VARCHAR)",
            name="ck_policy_chunk_versions_tenant_policy_scope",
        ),
        sa.CheckConstraint(
            "document_version > 0 AND chunk_version > 0",
            name="ck_policy_chunk_versions_versions_positive",
        ),
        sa.CheckConstraint(
            "text_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_policy_chunk_versions_text_hash",
        ),
        sa.CheckConstraint(_SOURCE_LOCATOR_CHECK, name="ck_policy_chunk_versions_source_locator_allowlist"),
        sa.CheckConstraint(_LIFECYCLE_CHECK, name="ck_policy_chunk_versions_lifecycle_status"),
    )
    op.create_index(
        "ix_policy_chunk_versions_tenant_chunk_version",
        "policy_chunk_versions",
        ["tenant_id", "doc_key", "chunk_id", "document_version", "chunk_version"],
    )
    op.create_index(
        "ix_policy_chunk_versions_retention",
        "policy_chunk_versions",
        ["retention_until"],
    )

    op.create_table(
        "evidence_snapshot_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "event_id",
            "document_version_id",
            "chunk_version_id",
            name="uq_evidence_snapshot_dependencies_binding",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["event_id", "tenant_id"],
            ["agent_trace_events.event_id", "agent_trace_events.tenant_id"],
            name="fk_evidence_snapshot_dependencies_event_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_evidence_snapshot_dependencies_document_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_version_id", "tenant_id", "document_version_id"],
            [
                "policy_chunk_versions.id",
                "policy_chunk_versions.tenant_id",
                "policy_chunk_versions.policy_document_version_id",
            ],
            name="fk_evidence_snapshot_dependencies_chunk_tenant_document",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_evidence_snapshot_dependencies_tenant_event",
        "evidence_snapshot_dependencies",
        ["tenant_id", "event_id"],
    )
    op.create_index(
        "ix_evidence_snapshot_dependencies_retention",
        "evidence_snapshot_dependencies",
        ["retention_until"],
    )

    op.create_table(
        "evidence_identity_rollouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rollout_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dual_write_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backfill_watermark_sequence", sa.BigInteger(), nullable=True),
        sa.Column("reconciled_through_sequence", sa.BigInteger(), nullable=True),
        sa.Column("canonical_reads_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("canonical_reads_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_reads_disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantine_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "audit_counts_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_evidence_identity_rollouts_singleton"),
        sa.CheckConstraint("rollout_version >= 0", name="ck_evidence_identity_rollouts_version_nonnegative"),
        sa.CheckConstraint(
            "backfill_watermark_sequence IS NULL OR backfill_watermark_sequence >= 0",
            name="ck_evidence_identity_rollouts_watermark_nonnegative",
        ),
        sa.CheckConstraint(
            "reconciled_through_sequence IS NULL OR reconciled_through_sequence >= 0",
            name="ck_evidence_identity_rollouts_reconciled_nonnegative",
        ),
        sa.CheckConstraint(
            "NOT canonical_reads_enabled OR dual_write_enabled_at IS NOT NULL",
            name="ck_evidence_identity_rollouts_reads_require_dual_write",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO evidence_identity_rollouts "
            "(id, rollout_version, canonical_reads_enabled, audit_counts_json) "
            "VALUES (1, 0, false, '{}'::jsonb)"
        )
    )
    _install_immutable_evidence_guards()


def downgrade() -> None:
    _assert_downgrade_safe()
    _drop_immutable_evidence_guards()
    op.drop_table("evidence_snapshot_dependencies")
    op.drop_table("policy_chunk_versions")
    op.drop_table("policy_document_versions")
    op.drop_table("evidence_identity_rollouts")
    op.execute("DROP SEQUENCE evidence_ingestion_write_seq")
    op.drop_column("agent_trace_events", "evidence_snapshot_refs_json")
    op.drop_column("policy_chunks", "evidence_write_sequence")
    op.drop_column("policy_documents", "evidence_write_sequence")
    op.drop_constraint(
        "uq_agent_trace_events_event_tenant",
        "agent_trace_events",
        type_="unique",
    )
    op.drop_constraint(
        "uq_policy_documents_id_tenant",
        "policy_documents",
        type_="unique",
    )


def _assert_downgrade_safe() -> None:
    unsafe = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT "
                "EXISTS (SELECT 1 FROM policy_document_versions) "
                "OR EXISTS (SELECT 1 FROM policy_chunk_versions) "
                "OR EXISTS (SELECT 1 FROM evidence_snapshot_dependencies) "
                "OR EXISTS (SELECT 1 FROM agent_trace_events "
                "WHERE evidence_snapshot_refs_json IS NOT NULL "
                "AND evidence_snapshot_refs_json <> '[]'::jsonb) "
                "OR EXISTS (SELECT 1 FROM evidence_identity_rollouts "
                "WHERE rollout_version <> 0 OR dual_write_enabled_at IS NOT NULL "
                "OR backfill_watermark_sequence IS NOT NULL OR reconciled_through_sequence IS NOT NULL "
                "OR canonical_reads_enabled OR quarantine_reason IS NOT NULL "
                "OR audit_counts_json <> '{}'::jsonb)"
            )
        )
        .scalar_one()
    )
    if unsafe:
        raise RuntimeError("refusing downgrade: immutable evidence history or active rollout state exists")


def _install_immutable_evidence_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_policy_document_version_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.retention_until > CURRENT_TIMESTAMP THEN
                    RAISE EXCEPTION 'policy document version is retained';
                END IF;
                RETURN OLD;
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                OR NEW.policy_document_id IS DISTINCT FROM OLD.policy_document_id
                OR NEW.scope_type IS DISTINCT FROM OLD.scope_type
                OR NEW.scope_id IS DISTINCT FROM OLD.scope_id
                OR NEW.doc_key IS DISTINCT FROM OLD.doc_key
                OR NEW.document_version IS DISTINCT FROM OLD.document_version
                OR NEW.content IS DISTINCT FROM OLD.content
                OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
                OR NEW.source_locator_json IS DISTINCT FROM OLD.source_locator_json
                OR NEW.supersedes_version_id IS DISTINCT FROM OLD.supersedes_version_id
                OR NEW.corrects_version_id IS DISTINCT FROM OLD.corrects_version_id
                OR NEW.retention_until < OLD.retention_until THEN
                RAISE EXCEPTION 'policy document version immutable material cannot change';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_document_versions_immutable
        BEFORE UPDATE OR DELETE ON policy_document_versions
        FOR EACH ROW EXECUTE FUNCTION guard_policy_document_version_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_policy_chunk_version_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.retention_until > CURRENT_TIMESTAMP THEN
                    RAISE EXCEPTION 'policy chunk version is retained';
                END IF;
                RETURN OLD;
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                OR NEW.policy_document_version_id IS DISTINCT FROM OLD.policy_document_version_id
                OR NEW.scope_type IS DISTINCT FROM OLD.scope_type
                OR NEW.scope_id IS DISTINCT FROM OLD.scope_id
                OR NEW.doc_key IS DISTINCT FROM OLD.doc_key
                OR NEW.document_version IS DISTINCT FROM OLD.document_version
                OR NEW.chunk_id IS DISTINCT FROM OLD.chunk_id
                OR NEW.chunk_version IS DISTINCT FROM OLD.chunk_version
                OR NEW.content IS DISTINCT FROM OLD.content
                OR NEW.text_hash IS DISTINCT FROM OLD.text_hash
                OR NEW.source_locator_json IS DISTINCT FROM OLD.source_locator_json
                OR NEW.supersedes_version_id IS DISTINCT FROM OLD.supersedes_version_id
                OR NEW.corrects_version_id IS DISTINCT FROM OLD.corrects_version_id
                OR NEW.retention_until < OLD.retention_until THEN
                RAISE EXCEPTION 'policy chunk version immutable material cannot change';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_chunk_versions_immutable
        BEFORE UPDATE OR DELETE ON policy_chunk_versions
        FOR EACH ROW EXECUTE FUNCTION guard_policy_chunk_version_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_evidence_snapshot_dependency_delete()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.retention_until > CURRENT_TIMESTAMP THEN
                RAISE EXCEPTION 'evidence snapshot dependency is retained';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidence_snapshot_dependencies_retained
        BEFORE DELETE ON evidence_snapshot_dependencies
        FOR EACH ROW EXECUTE FUNCTION guard_evidence_snapshot_dependency_delete()
        """
    )


def _drop_immutable_evidence_guards() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_snapshot_dependencies_retained ON evidence_snapshot_dependencies")
    op.execute("DROP FUNCTION IF EXISTS guard_evidence_snapshot_dependency_delete()")
    op.execute("DROP TRIGGER IF EXISTS trg_policy_chunk_versions_immutable ON policy_chunk_versions")
    op.execute("DROP FUNCTION IF EXISTS guard_policy_chunk_version_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_policy_document_versions_immutable ON policy_document_versions")
    op.execute("DROP FUNCTION IF EXISTS guard_policy_document_version_mutation()")
