"""Add token-aware corpus generations and bootstrap legacy visibility.

Revision ID: 030_phase64_4_token_corpora
Revises: 029_phase64_3_rag_eval_rounds
Create Date: 2026-08-11

The migration creates visibility projections without adding corpus identity to
immutable evidence rows. Every tenant that already owns current policy heads
is bootstrapped into exactly one active ``character.v1`` corpus. The bootstrap
is count checked before the revision may complete.
"""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from uuid import uuid4

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from src.knowledge.text_hash import evidence_text_hash


revision: str = "030_phase64_4_token_corpora"
down_revision: str | None = "029_phase64_3_rag_eval_rounds"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CHARACTER_CORPUS_NAME = "character.v1"
_CHARACTER_CONFIG_SCHEMA_VERSION = "character_compatibility.v1"
_TOKENIZER_CONFIG_FINGERPRINT = "sha256:925446ea470da4da9a0ac9aee81f9103bb4b07bd7292c761bd98a36edd749584"
_CHARACTER_CONFIG = {
    "schema_version": _CHARACTER_CONFIG_SCHEMA_VERSION,
    "embedding_tokenizer_config_fingerprint": _TOKENIZER_CONFIG_FINGERPRINT,
    "max_chars": 1200,
    "target_chars": 800,
    "overlap_chars": 100,
    "provider_input_envelope": "legacy_ingestion.v1",
}
_CHARACTER_CONFIG_FINGERPRINT = (
    "sha256:"
    + hashlib.sha256(
        json.dumps(_CHARACTER_CONFIG, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
)
_HASH_CHECK = "~ '^sha256:[0-9a-f]{64}$'"
_CORPUS_STATE_CHECK = "state IN ('claimed', 'building', 'built', 'validating', 'complete', 'failed', 'source_stale')"


def upgrade() -> None:
    _add_audit_columns()
    _create_corpus_tables()
    _install_append_only_guards()
    _bootstrap_character_corpora()
    _assert_bootstrap_integrity()


def downgrade() -> None:
    _assert_downgrade_safe()
    _drop_append_only_guards()
    op.drop_table("corpus_chunk_bindings")
    op.drop_table("corpus_block_bindings")
    op.drop_table("corpus_document_bindings")
    op.drop_table("policy_corpus_activation_history")
    op.drop_table("policy_corpus_rollouts")
    op.drop_table("policy_corpus_versions")
    op.drop_table("policy_corpus_manifest_revisions")
    _drop_audit_columns()


def _add_audit_columns() -> None:
    op.create_unique_constraint(
        "uq_document_blocks_id_tenant",
        "document_blocks",
        ["id", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_policy_chunks_id_tenant",
        "policy_chunks",
        ["id", "tenant_id"],
    )

    op.add_column("policy_chunks", sa.Column("chunking_config_fingerprint", sa.String(length=71)))
    op.add_column("policy_chunks", sa.Column("embedding_input_hash", sa.String(length=71)))
    op.add_column("policy_chunks", sa.Column("embedding_token_count", sa.Integer()))
    op.create_check_constraint(
        "ck_policy_chunks_embedding_audit_complete",
        "policy_chunks",
        "((chunking_config_fingerprint IS NULL AND embedding_input_hash IS NULL "
        "AND embedding_token_count IS NULL) OR "
        "(chunking_config_fingerprint ~ '^sha256:[0-9a-f]{64}$' "
        "AND embedding_input_hash ~ '^sha256:[0-9a-f]{64}$' "
        "AND embedding_token_count >= 0))",
    )

    op.add_column("policy_document_versions", sa.Column("source_checksum", sa.String(length=128)))
    op.add_column(
        "policy_document_versions",
        sa.Column("canonical_content_schema_version", sa.String(length=64)),
    )
    op.add_column("policy_document_versions", sa.Column("canonical_blocks_json", postgresql.JSONB()))
    op.add_column("policy_document_versions", sa.Column("canonical_blocks_hash", sa.String(length=71)))
    op.create_check_constraint(
        "ck_policy_document_versions_canonical_source_complete",
        "policy_document_versions",
        "((canonical_content_schema_version IS NULL AND source_checksum IS NULL "
        "AND canonical_blocks_json IS NULL AND canonical_blocks_hash IS NULL) OR "
        "(canonical_content_schema_version = 'canonical_document_content.v2' "
        "AND source_checksum IS NOT NULL AND jsonb_typeof(canonical_blocks_json) = 'array' "
        "AND canonical_blocks_hash ~ '^sha256:[0-9a-f]{64}$'))",
    )

    op.add_column("policy_chunk_versions", sa.Column("search_text", sa.Text()))
    op.add_column("policy_chunk_versions", sa.Column("embedding", Vector(1024)))
    op.add_column("policy_chunk_versions", sa.Column("chunking_config_fingerprint", sa.String(length=71)))
    op.add_column("policy_chunk_versions", sa.Column("embedding_input_hash", sa.String(length=71)))
    op.add_column("policy_chunk_versions", sa.Column("embedding_token_count", sa.Integer()))
    op.create_check_constraint(
        "ck_policy_chunk_versions_embedding_audit_complete",
        "policy_chunk_versions",
        "((chunking_config_fingerprint IS NULL AND embedding_input_hash IS NULL "
        "AND embedding_token_count IS NULL) OR "
        "(chunking_config_fingerprint ~ '^sha256:[0-9a-f]{64}$' "
        "AND embedding_input_hash ~ '^sha256:[0-9a-f]{64}$' "
        "AND embedding_token_count >= 0))",
    )

    ingestion_columns = (
        sa.Column("chunking_config_fingerprint", sa.String(length=71)),
        sa.Column("chunk_count", sa.Integer()),
        sa.Column("embedding_token_count_min", sa.Integer()),
        sa.Column("embedding_token_count_max", sa.Integer()),
        sa.Column("embedding_token_count_total", sa.Integer()),
        sa.Column("provider_prompt_tokens", sa.Integer()),
        sa.Column("provider_total_tokens", sa.Integer()),
        sa.Column("provider_usage_status", sa.String(length=32)),
    )
    for column in ingestion_columns:
        op.add_column("rag_ingestion_jobs", column)
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_chunk_count_nonnegative",
        "rag_ingestion_jobs",
        "chunk_count IS NULL OR chunk_count >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_token_min_nonnegative",
        "rag_ingestion_jobs",
        "embedding_token_count_min IS NULL OR embedding_token_count_min >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_token_max_nonnegative",
        "rag_ingestion_jobs",
        "embedding_token_count_max IS NULL OR embedding_token_count_max >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_token_total_nonnegative",
        "rag_ingestion_jobs",
        "embedding_token_count_total IS NULL OR embedding_token_count_total >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_provider_prompt_nonnegative",
        "rag_ingestion_jobs",
        "provider_prompt_tokens IS NULL OR provider_prompt_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_provider_total_nonnegative",
        "rag_ingestion_jobs",
        "provider_total_tokens IS NULL OR provider_total_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_rag_ingestion_jobs_provider_usage_status",
        "rag_ingestion_jobs",
        "provider_usage_status IS NULL OR provider_usage_status IN ('available', 'unavailable')",
    )


def _create_corpus_tables() -> None:
    op.create_table(
        "policy_corpus_manifest_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("manifest_schema_version", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=71), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_policy_corpus_manifest_revisions_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "revision",
            name="uq_policy_corpus_manifest_revisions_tenant_revision",
        ),
        sa.CheckConstraint("revision > 0", name="ck_policy_corpus_manifest_revisions_revision_positive"),
        sa.CheckConstraint(
            f"manifest_hash {_HASH_CHECK}",
            name="ck_policy_corpus_manifest_revisions_hash",
        ),
        sa.CheckConstraint(
            "document_count >= 0 AND block_count >= 0 AND chunk_count >= 0",
            name="ck_policy_corpus_manifest_revisions_counts_nonnegative",
        ),
    )
    op.create_index(
        "ix_policy_corpus_manifest_revisions_tenant_created",
        "policy_corpus_manifest_revisions",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "policy_corpus_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_name", sa.String(length=128), nullable=False),
        sa.Column("owner_marker", sa.String(length=128), nullable=False),
        sa.Column("run_token", postgresql.UUID(as_uuid=True)),
        sa.Column("config_schema_version", sa.String(length=64), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("provider_parity_report_hash", sa.String(length=71)),
        sa.Column("source_manifest_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_manifest_hash", sa.String(length=71), nullable=False),
        sa.Column("source_active_corpus_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_rollout_epoch", sa.Integer()),
        sa.Column("expected_evidence_rollout_version", sa.Integer()),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("lease_owner", sa.String(length=128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_document_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "bootstrap_counts_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "validation_proof_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("deterministic_rebuild_hash", sa.String(length=71)),
        sa.Column("validation_report_hash", sa.String(length=71)),
        sa.Column("failure_code", sa.String(length=64)),
        sa.Column("safe_message", sa.String(length=200)),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_manifest_revision_id", "tenant_id"],
            ["policy_corpus_manifest_revisions.id", "policy_corpus_manifest_revisions.tenant_id"],
            name="fk_policy_corpus_versions_manifest_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_active_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_policy_corpus_versions_source_corpus_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_policy_corpus_versions_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "generation_name",
            name="uq_policy_corpus_versions_tenant_generation",
        ),
        sa.CheckConstraint(
            f"config_fingerprint {_HASH_CHECK}",
            name="ck_policy_corpus_versions_config_fingerprint",
        ),
        sa.CheckConstraint(
            f"source_manifest_hash {_HASH_CHECK}",
            name="ck_policy_corpus_versions_manifest_hash",
        ),
        sa.CheckConstraint(_CORPUS_STATE_CHECK, name="ck_policy_corpus_versions_state"),
        sa.CheckConstraint("state_version > 0", name="ck_policy_corpus_versions_state_version_positive"),
        sa.CheckConstraint(
            "next_document_index >= 0",
            name="ck_policy_corpus_versions_next_document_nonnegative",
        ),
        sa.CheckConstraint(
            "source_rollout_epoch IS NULL OR source_rollout_epoch > 0",
            name="ck_policy_corpus_versions_source_epoch_positive",
        ),
        sa.CheckConstraint(
            "expected_evidence_rollout_version IS NULL OR expected_evidence_rollout_version >= 0",
            name="ck_policy_corpus_versions_evidence_epoch_nonnegative",
        ),
    )
    op.create_index(
        "ix_policy_corpus_versions_tenant_state",
        "policy_corpus_versions",
        ["tenant_id", "state"],
    )
    op.create_index(
        "ix_policy_corpus_versions_run_token",
        "policy_corpus_versions",
        ["tenant_id", "run_token"],
    )

    op.create_table(
        "policy_corpus_rollouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_corpus_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("rollout_epoch", sa.Integer(), nullable=False),
        sa.Column("quarantine_reason", sa.String(length=200)),
        sa.Column("source_drifted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["active_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_policy_corpus_rollouts_active_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_policy_corpus_rollouts_previous_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_policy_corpus_rollouts_tenant"),
        sa.CheckConstraint("rollout_epoch > 0", name="ck_policy_corpus_rollouts_epoch_positive"),
    )

    op.create_table(
        "policy_corpus_activation_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_corpus_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("to_corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rollout_epoch", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("selection_decision_hash", sa.String(length=71)),
        sa.Column("receipt_hash", sa.String(length=71)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_policy_corpus_activation_history_from_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_policy_corpus_activation_history_to_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "rollout_epoch",
            name="uq_policy_corpus_activation_history_tenant_epoch",
        ),
        sa.CheckConstraint(
            "rollout_epoch > 0",
            name="ck_policy_corpus_activation_history_epoch_positive",
        ),
    )
    op.create_index(
        "ix_policy_corpus_activation_history_tenant_created",
        "policy_corpus_activation_history",
        ["tenant_id", "created_at"],
    )

    _create_binding_table(
        table_name="corpus_document_bindings",
        current_column="policy_document_id",
        current_table="policy_documents",
        current_constraint="fk_corpus_document_bindings_current_tenant",
        immutable_column="policy_document_version_id",
        immutable_table="policy_document_versions",
        immutable_constraint="fk_corpus_document_bindings_immutable_tenant",
        current_unique="uq_corpus_document_bindings_current",
        immutable_unique="uq_corpus_document_bindings_immutable",
    )
    _create_block_binding_table()
    _create_binding_table(
        table_name="corpus_chunk_bindings",
        current_column="policy_chunk_id",
        current_table="policy_chunks",
        current_constraint="fk_corpus_chunk_bindings_current_tenant",
        immutable_column="policy_chunk_version_id",
        immutable_table="policy_chunk_versions",
        immutable_constraint="fk_corpus_chunk_bindings_immutable_tenant",
        current_unique="uq_corpus_chunk_bindings_current",
        immutable_unique="uq_corpus_chunk_bindings_immutable",
    )


def _create_binding_table(
    *,
    table_name: str,
    current_column: str,
    current_table: str,
    current_constraint: str,
    immutable_column: str,
    immutable_table: str,
    immutable_constraint: str,
    current_unique: str,
    immutable_unique: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(current_column, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(immutable_column, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name=f"fk_{table_name}_corpus_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [current_column, "tenant_id"],
            [f"{current_table}.id", f"{current_table}.tenant_id"],
            name=current_constraint,
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [immutable_column, "tenant_id"],
            [f"{immutable_table}.id", f"{immutable_table}.tenant_id"],
            name=immutable_constraint,
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "corpus_version_id", current_column, name=current_unique),
        sa.UniqueConstraint("tenant_id", "corpus_version_id", immutable_column, name=immutable_unique),
    )


def _create_block_binding_table() -> None:
    op.create_table(
        "corpus_block_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_block_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_corpus_block_bindings_corpus_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_block_id", "tenant_id"],
            ["document_blocks.id", "document_blocks.tenant_id"],
            name="fk_corpus_block_bindings_current_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_document_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_corpus_block_bindings_document_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "corpus_version_id",
            "document_block_id",
            name="uq_corpus_block_bindings_current",
        ),
    )


def _bootstrap_character_corpora() -> None:
    bind = op.get_bind()
    tenant_ids = [
        row[0] for row in bind.execute(sa.text("SELECT DISTINCT tenant_id FROM policy_documents ORDER BY tenant_id"))
    ]
    for tenant_id in tenant_ids:
        documents = list(
            bind.execute(
                sa.text(
                    "SELECT id, doc_key, version, source_type, source_checksum "
                    "FROM policy_documents WHERE tenant_id = :tenant_id ORDER BY doc_key, id FOR UPDATE"
                ),
                {"tenant_id": tenant_id},
            ).mappings()
        )
        document_bindings: list[tuple[object, object]] = []
        block_bindings: list[tuple[object, object]] = []
        chunk_bindings: list[tuple[object, object]] = []
        manifest_documents: list[dict[str, object]] = []
        for document in documents:
            immutable_documents = list(
                bind.execute(
                    sa.text(
                        "SELECT id FROM policy_document_versions WHERE tenant_id = :tenant_id "
                        "AND policy_document_id = :document_id AND document_version = :document_version"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "document_id": document["id"],
                        "document_version": document["version"],
                    },
                )
            )
            if len(immutable_documents) != 1:
                raise RuntimeError("corpus bootstrap blocked: current document lacks one exact immutable version")
            document_version_id = immutable_documents[0][0]
            document_bindings.append((document["id"], document_version_id))

            blocks = list(
                bind.execute(
                    sa.text(
                        "SELECT id, source_block_id, block_index, text_hash FROM document_blocks "
                        "WHERE tenant_id = :tenant_id AND doc_id = :document_id ORDER BY block_index, id FOR UPDATE"
                    ),
                    {"tenant_id": tenant_id, "document_id": document["id"]},
                ).mappings()
            )
            block_bindings.extend((block["id"], document_version_id) for block in blocks)

            chunks = list(
                bind.execute(
                    sa.text(
                        "SELECT id, chunk_id, content FROM policy_chunks WHERE tenant_id = :tenant_id "
                        "AND doc_id = :document_id ORDER BY chunk_id, id FOR UPDATE"
                    ),
                    {"tenant_id": tenant_id, "document_id": document["id"]},
                ).mappings()
            )
            for chunk in chunks:
                immutable_chunks = list(
                    bind.execute(
                        sa.text(
                            "SELECT id FROM policy_chunk_versions WHERE tenant_id = :tenant_id "
                            "AND policy_document_version_id = :document_version_id AND chunk_id = :chunk_id "
                            "AND text_hash = :text_hash ORDER BY chunk_version, id"
                        ),
                        {
                            "tenant_id": tenant_id,
                            "document_version_id": document_version_id,
                            "chunk_id": chunk["chunk_id"],
                            "text_hash": evidence_text_hash(str(chunk["content"])),
                        },
                    )
                )
                if len(immutable_chunks) != 1:
                    raise RuntimeError("corpus bootstrap blocked: current chunk lacks one exact immutable version")
                chunk_bindings.append((chunk["id"], immutable_chunks[0][0]))

            manifest_documents.append(
                {
                    "policy_document_id": str(document["id"]),
                    "policy_document_version_id": str(document_version_id),
                    "doc_key": str(document["doc_key"]),
                    "document_version": int(document["version"]),
                    "source_type": document["source_type"],
                    "source_checksum": document["source_checksum"],
                    "source_block_ids": [str(block["source_block_id"]) for block in blocks],
                    "chunk_ids": [str(chunk["chunk_id"]) for chunk in chunks],
                }
            )

        manifest = {
            "schema_version": "policy_corpus_source_manifest.v1",
            "tenant_id": str(tenant_id),
            "documents": manifest_documents,
        }
        manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest_hash = "sha256:" + hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
        manifest_id = uuid4()
        corpus_id = uuid4()
        current_job_count = int(
            bind.execute(
                sa.text("SELECT count(*) FROM rag_ingestion_jobs WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            ).scalar_one()
        )
        counts = {
            "current_document_count": len(documents),
            "bound_document_count": len(document_bindings),
            "current_block_count": len(block_bindings),
            "bound_block_count": len(block_bindings),
            "current_chunk_count": len(chunk_bindings),
            "bound_chunk_count": len(chunk_bindings),
            "current_job_count": current_job_count,
            "orphan_binding_count": 0,
            "duplicate_binding_count": 0,
        }
        bind.execute(
            sa.text(
                "INSERT INTO policy_corpus_manifest_revisions "
                "(id, tenant_id, revision, manifest_schema_version, manifest_json, manifest_hash, "
                "document_count, block_count, chunk_count) VALUES (:id, :tenant_id, 1, "
                "'policy_corpus_source_manifest.v1', CAST(:manifest AS jsonb), :manifest_hash, "
                ":document_count, :block_count, :chunk_count)"
            ),
            {
                "id": manifest_id,
                "tenant_id": tenant_id,
                "manifest": manifest_json,
                "manifest_hash": manifest_hash,
                "document_count": len(document_bindings),
                "block_count": len(block_bindings),
                "chunk_count": len(chunk_bindings),
            },
        )
        bind.execute(
            sa.text(
                "INSERT INTO policy_corpus_versions "
                "(id, tenant_id, generation_name, owner_marker, config_schema_version, config_json, "
                "config_fingerprint, source_manifest_revision_id, source_manifest_hash, state, "
                "state_version, next_document_index, bootstrap_counts_json, validation_proof_json, terminal_at) "
                "VALUES (:id, :tenant_id, :generation_name, 'moca.phase64_4.bootstrap', "
                ":config_schema_version, CAST(:config_json AS jsonb), :config_fingerprint, :manifest_id, "
                ":manifest_hash, 'complete', 1, :document_count, CAST(:counts AS jsonb), "
                "CAST(:proof AS jsonb), CURRENT_TIMESTAMP)"
            ),
            {
                "id": corpus_id,
                "tenant_id": tenant_id,
                "generation_name": _CHARACTER_CORPUS_NAME,
                "config_schema_version": _CHARACTER_CONFIG_SCHEMA_VERSION,
                "config_json": json.dumps(_CHARACTER_CONFIG, sort_keys=True, separators=(",", ":")),
                "config_fingerprint": _CHARACTER_CONFIG_FINGERPRINT,
                "manifest_id": manifest_id,
                "manifest_hash": manifest_hash,
                "document_count": len(document_bindings),
                "counts": json.dumps(counts, sort_keys=True),
                "proof": json.dumps(
                    {
                        "bootstrap_contract": "character.v1",
                        "visibility": "exact_current_projection",
                        "immutable_identity_contains_corpus": False,
                    },
                    sort_keys=True,
                ),
            },
        )

        _insert_bindings(
            bind,
            table_name="corpus_document_bindings",
            current_column="policy_document_id",
            immutable_column="policy_document_version_id",
            tenant_id=tenant_id,
            corpus_id=corpus_id,
            bindings=document_bindings,
        )
        _insert_bindings(
            bind,
            table_name="corpus_block_bindings",
            current_column="document_block_id",
            immutable_column="policy_document_version_id",
            tenant_id=tenant_id,
            corpus_id=corpus_id,
            bindings=block_bindings,
        )
        _insert_bindings(
            bind,
            table_name="corpus_chunk_bindings",
            current_column="policy_chunk_id",
            immutable_column="policy_chunk_version_id",
            tenant_id=tenant_id,
            corpus_id=corpus_id,
            bindings=chunk_bindings,
        )
        bind.execute(
            sa.text(
                "INSERT INTO policy_corpus_rollouts "
                "(id, tenant_id, active_corpus_version_id, previous_corpus_version_id, rollout_epoch) "
                "VALUES (:id, :tenant_id, :corpus_id, NULL, 1)"
            ),
            {"id": uuid4(), "tenant_id": tenant_id, "corpus_id": corpus_id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO policy_corpus_activation_history "
                "(id, tenant_id, from_corpus_version_id, to_corpus_version_id, rollout_epoch, reason_code) "
                "VALUES (:id, :tenant_id, NULL, :corpus_id, 1, 'bootstrap_character_v1')"
            ),
            {"id": uuid4(), "tenant_id": tenant_id, "corpus_id": corpus_id},
        )


def _insert_bindings(
    bind: sa.Connection,
    *,
    table_name: str,
    current_column: str,
    immutable_column: str,
    tenant_id: object,
    corpus_id: object,
    bindings: list[tuple[object, object]],
) -> None:
    for current_id, immutable_id in bindings:
        bind.execute(
            sa.text(
                f"INSERT INTO {table_name} "
                f"(id, tenant_id, corpus_version_id, {current_column}, {immutable_column}) "
                f"VALUES (:id, :tenant_id, :corpus_id, :current_id, :immutable_id)"
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "corpus_id": corpus_id,
                "current_id": current_id,
                "immutable_id": immutable_id,
            },
        )


def _assert_bootstrap_integrity() -> None:
    bind = op.get_bind()
    failures = list(
        bind.execute(
            sa.text(
                "WITH current_counts AS ("
                " SELECT d.tenant_id, count(DISTINCT d.id) AS documents, "
                " count(DISTINCT b.id) AS blocks, count(DISTINCT c.id) AS chunks "
                " FROM policy_documents d "
                " LEFT JOIN document_blocks b ON b.tenant_id = d.tenant_id AND b.doc_id = d.id "
                " LEFT JOIN policy_chunks c ON c.tenant_id = d.tenant_id AND c.doc_id = d.id "
                " GROUP BY d.tenant_id"
                "), bootstrap AS ("
                " SELECT r.tenant_id, count(DISTINCT r.id) AS rollouts, "
                " count(DISTINCT v.id) FILTER (WHERE v.generation_name = 'character.v1') AS corpora, "
                " count(DISTINCT db.policy_document_id) AS documents, "
                " count(DISTINCT bb.document_block_id) AS blocks, "
                " count(DISTINCT cb.policy_chunk_id) AS chunks "
                " FROM policy_corpus_rollouts r "
                " JOIN policy_corpus_versions v ON v.tenant_id = r.tenant_id "
                "  AND v.id = r.active_corpus_version_id "
                " LEFT JOIN corpus_document_bindings db ON db.tenant_id = r.tenant_id "
                "  AND db.corpus_version_id = r.active_corpus_version_id "
                " LEFT JOIN corpus_block_bindings bb ON bb.tenant_id = r.tenant_id "
                "  AND bb.corpus_version_id = r.active_corpus_version_id "
                " LEFT JOIN corpus_chunk_bindings cb ON cb.tenant_id = r.tenant_id "
                "  AND cb.corpus_version_id = r.active_corpus_version_id "
                " GROUP BY r.tenant_id"
                ") SELECT c.tenant_id FROM current_counts c LEFT JOIN bootstrap b ON b.tenant_id = c.tenant_id "
                "WHERE b.rollouts IS DISTINCT FROM 1 OR b.corpora IS DISTINCT FROM 1 "
                "OR b.documents IS DISTINCT FROM c.documents OR b.blocks IS DISTINCT FROM c.blocks "
                "OR b.chunks IS DISTINCT FROM c.chunks"
            )
        )
    )
    if failures:
        raise RuntimeError("corpus bootstrap blocked: before/after tenant counts or visibility differ")


def _install_append_only_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_policy_corpus_manifest_revision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'policy corpus manifest revisions are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_corpus_manifest_revisions_append_only
        BEFORE UPDATE OR DELETE ON policy_corpus_manifest_revisions
        FOR EACH ROW EXECUTE FUNCTION guard_policy_corpus_manifest_revision_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_policy_corpus_activation_history_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'policy corpus activation history is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_corpus_activation_history_append_only
        BEFORE UPDATE OR DELETE ON policy_corpus_activation_history
        FOR EACH ROW EXECUTE FUNCTION guard_policy_corpus_activation_history_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_corpus_projection_binding_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'corpus projection bindings are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table_name in ("corpus_document_bindings", "corpus_block_bindings", "corpus_chunk_bindings"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_append_only BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION guard_corpus_projection_binding_mutation()"
        )


def _drop_append_only_guards() -> None:
    for table_name in ("corpus_chunk_bindings", "corpus_block_bindings", "corpus_document_bindings"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS guard_corpus_projection_binding_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_corpus_activation_history_append_only ON policy_corpus_activation_history"
    )
    op.execute("DROP FUNCTION IF EXISTS guard_policy_corpus_activation_history_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_corpus_manifest_revisions_append_only ON policy_corpus_manifest_revisions"
    )
    op.execute("DROP FUNCTION IF EXISTS guard_policy_corpus_manifest_revision_mutation()")


def _assert_downgrade_safe() -> None:
    unsafe = bool(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM policy_corpus_versions "
                "WHERE generation_name <> 'character.v1' "
                "OR config_schema_version <> 'character_compatibility.v1' "
                "OR source_active_corpus_version_id IS NOT NULL OR provider_parity_report_hash IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM policy_corpus_manifest_revisions WHERE revision <> 1) "
                "OR EXISTS (SELECT 1 FROM policy_corpus_activation_history "
                "WHERE rollout_epoch <> 1 OR reason_code <> 'bootstrap_character_v1') "
                "OR EXISTS (SELECT 1 FROM policy_chunks WHERE chunking_config_fingerprint IS NOT NULL "
                "OR embedding_input_hash IS NOT NULL OR embedding_token_count IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM policy_chunk_versions WHERE chunking_config_fingerprint IS NOT NULL "
                "OR embedding_input_hash IS NOT NULL OR embedding_token_count IS NOT NULL "
                "OR search_text IS NOT NULL OR embedding IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM policy_document_versions "
                "WHERE canonical_content_schema_version IS NOT NULL OR source_checksum IS NOT NULL "
                "OR canonical_blocks_json IS NOT NULL OR canonical_blocks_hash IS NOT NULL) "
                "OR EXISTS (SELECT 1 FROM rag_ingestion_jobs WHERE chunking_config_fingerprint IS NOT NULL "
                "OR chunk_count IS NOT NULL OR embedding_token_count_min IS NOT NULL "
                "OR embedding_token_count_max IS NOT NULL OR embedding_token_count_total IS NOT NULL "
                "OR provider_prompt_tokens IS NOT NULL OR provider_total_tokens IS NOT NULL "
                "OR provider_usage_status IS NOT NULL)"
            )
        )
        .scalar_one()
    )
    if unsafe:
        raise RuntimeError("refusing downgrade: token-aware corpus or audit dependencies exist")


def _drop_audit_columns() -> None:
    for constraint in (
        "ck_rag_ingestion_jobs_provider_usage_status",
        "ck_rag_ingestion_jobs_provider_total_nonnegative",
        "ck_rag_ingestion_jobs_provider_prompt_nonnegative",
        "ck_rag_ingestion_jobs_token_total_nonnegative",
        "ck_rag_ingestion_jobs_token_max_nonnegative",
        "ck_rag_ingestion_jobs_token_min_nonnegative",
        "ck_rag_ingestion_jobs_chunk_count_nonnegative",
    ):
        op.drop_constraint(constraint, "rag_ingestion_jobs", type_="check")
    for column in (
        "provider_usage_status",
        "provider_total_tokens",
        "provider_prompt_tokens",
        "embedding_token_count_total",
        "embedding_token_count_max",
        "embedding_token_count_min",
        "chunk_count",
        "chunking_config_fingerprint",
    ):
        op.drop_column("rag_ingestion_jobs", column)

    op.drop_constraint(
        "ck_policy_chunk_versions_embedding_audit_complete",
        "policy_chunk_versions",
        type_="check",
    )
    for column in (
        "embedding_token_count",
        "embedding_input_hash",
        "chunking_config_fingerprint",
        "embedding",
        "search_text",
    ):
        op.drop_column("policy_chunk_versions", column)

    op.drop_constraint(
        "ck_policy_document_versions_canonical_source_complete",
        "policy_document_versions",
        type_="check",
    )
    for column in (
        "canonical_blocks_hash",
        "canonical_blocks_json",
        "canonical_content_schema_version",
        "source_checksum",
    ):
        op.drop_column("policy_document_versions", column)

    op.drop_constraint("ck_policy_chunks_embedding_audit_complete", "policy_chunks", type_="check")
    for column in ("embedding_token_count", "embedding_input_hash", "chunking_config_fingerprint"):
        op.drop_column("policy_chunks", column)
    op.drop_constraint("uq_policy_chunks_id_tenant", "policy_chunks", type_="unique")
    op.drop_constraint("uq_document_blocks_id_tenant", "document_blocks", type_="unique")
