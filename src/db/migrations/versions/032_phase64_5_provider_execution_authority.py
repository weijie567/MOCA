"""Add immutable database authority for bounded provider execution.

Revision ID: 032_phase64_5_provider_execution_authority
Revises: 031_phase64_4_policy_corpus_cow
Create Date: 2026-08-13

The database rows created here are the sole durable authority for provider
execution.  Reservations are spent when inserted, results are one-to-one with
their reservation, and receipt files remain projections of activation history.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "032_phase64_5_provider_execution_authority"
down_revision: str | None = "031_phase64_4_policy_corpus_cow"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_PROMOTION_SCOPE = "phase64.5.reviewed-provider-execution"
_GIT_OBJECT_CHECK = "~ '^[0-9a-f]{40}$'"
_SHA256_CHECK = "~ '^sha256:[0-9a-f]{64}$'"
_PURPOSE_CHECK = "purpose IN ('reviewed_build', 'canonical_ab')"
_RESULT_CODE_CHECK = (
    "result_code IN ('success', 'provider_unavailable', 'transient_execution_error', "
    "'quality_fail', 'safety_fail', 'configuration_error', 'parity_error', "
    "'source_drift', 'response_error', 'projection_error', 'unknown_error')"
)
_ACTIVATION_REASON_CHECK = "reason_code IN ('selected_cutover', 'rollback_prior', 'selected_restore')"
_AUTHORITY_TABLES = (
    "provider_execution_promotions",
    "provider_execution_authorities",
    "provider_execution_reservations",
    "provider_execution_results",
    "activation_receipt_lineages",
)


def upgrade() -> None:
    op.create_index(
        "uq_policy_corpus_versions_tenant_run_token",
        "policy_corpus_versions",
        ["tenant_id", "run_token"],
        unique=True,
        postgresql_where=sa.text("run_token IS NOT NULL"),
    )
    _create_promotion_table()
    _create_authority_table()
    _create_reservation_table()
    _create_result_table()
    op.create_foreign_key(
        "fk_provider_execution_reservations_predecessor_result_tenant",
        "provider_execution_reservations",
        "provider_execution_results",
        ["predecessor_result_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    _create_activation_lineage_table()
    _install_append_only_guards()


def downgrade() -> None:
    _assert_downgrade_safe()
    _drop_append_only_guards()
    op.drop_table("activation_receipt_lineages")
    op.drop_constraint(
        "fk_provider_execution_reservations_predecessor_result_tenant",
        "provider_execution_reservations",
        type_="foreignkey",
    )
    op.drop_table("provider_execution_results")
    op.drop_table("provider_execution_reservations")
    op.drop_table("provider_execution_authorities")
    op.drop_table("provider_execution_promotions")
    op.drop_index(
        "uq_policy_corpus_versions_tenant_run_token",
        table_name="policy_corpus_versions",
    )


def _assert_downgrade_safe() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("LOCK TABLE " + ", ".join(_AUTHORITY_TABLES) + " IN ACCESS EXCLUSIVE MODE"))
    any_rows_exist = bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS ("
                + " UNION ALL ".join(f"SELECT 1 FROM {table_name}" for table_name in _AUTHORITY_TABLES)
                + ")"
            )
        ).scalar_one()
    )
    if any_rows_exist:
        raise RuntimeError("refusing downgrade: provider execution authority rows exist")


def _create_promotion_table() -> None:
    op.create_table(
        "provider_execution_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("protected_code_c0_commit", sa.String(length=40), nullable=False),
        sa.Column("protected_code_c0_tree_hash", sa.String(length=40), nullable=False),
        sa.Column("protected_code_c1_commit", sa.String(length=40), nullable=False),
        sa.Column("protected_code_c1_tree_hash", sa.String(length=40), nullable=False),
        sa.Column("c0_to_c1_diff_hash", sa.String(length=71), nullable=False),
        sa.Column("c0_code_review_artifact_sha256", sa.String(length=71), nullable=False),
        sa.Column("c0_security_artifact_sha256", sa.String(length=71), nullable=False),
        sa.Column("c1_code_review_artifact_sha256", sa.String(length=71), nullable=False),
        sa.Column("c1_security_artifact_sha256", sa.String(length=71), nullable=False),
        sa.Column("c0_code_review_attestation_sha256", sa.String(length=71), nullable=False),
        sa.Column("c0_security_attestation_sha256", sa.String(length=71), nullable=False),
        sa.Column("c1_code_review_attestation_sha256", sa.String(length=71), nullable=False),
        sa.Column("c1_security_attestation_sha256", sa.String(length=71), nullable=False),
        sa.Column("c0_gate_report_sha256", sa.String(length=71), nullable=False),
        sa.Column("c1_gate_report_sha256", sa.String(length=71), nullable=False),
        sa.Column("promotion_request_hash", sa.String(length=71), nullable=False),
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", name="uq_provider_execution_promotions_scope"),
        sa.CheckConstraint(
            f"scope = '{_PROMOTION_SCOPE}'",
            name="ck_provider_execution_promotions_scope",
        ),
        sa.CheckConstraint(
            f"protected_code_c0_commit {_GIT_OBJECT_CHECK}",
            name="ck_provider_execution_promotions_c0_commit",
        ),
        sa.CheckConstraint(
            f"protected_code_c0_tree_hash {_GIT_OBJECT_CHECK}",
            name="ck_provider_execution_promotions_c0_tree",
        ),
        sa.CheckConstraint(
            f"protected_code_c1_commit {_GIT_OBJECT_CHECK}",
            name="ck_provider_execution_promotions_c1_commit",
        ),
        sa.CheckConstraint(
            f"protected_code_c1_tree_hash {_GIT_OBJECT_CHECK}",
            name="ck_provider_execution_promotions_c1_tree",
        ),
        sa.CheckConstraint(
            _sha256_columns_check(
                "c0_to_c1_diff_hash",
                "c0_code_review_artifact_sha256",
                "c0_security_artifact_sha256",
                "c1_code_review_artifact_sha256",
                "c1_security_artifact_sha256",
                "c0_code_review_attestation_sha256",
                "c0_security_attestation_sha256",
                "c1_code_review_attestation_sha256",
                "c1_security_attestation_sha256",
                "c0_gate_report_sha256",
                "c1_gate_report_sha256",
                "promotion_request_hash",
            ),
            name="ck_provider_execution_promotions_sha256_values",
        ),
    )


def _create_authority_table() -> None:
    op.create_table(
        "provider_execution_authorities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promotion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_marker", sa.String(length=128), nullable=False),
        sa.Column("config_schema_version", sa.String(length=64), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("provider_parity_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_parity_report_hash", sa.String(length=71), nullable=False),
        sa.Column("provider_parity_probe_fixture_sha256", sa.String(length=71), nullable=False),
        sa.Column("provider_parity_submitted_content_sha256", sa.String(length=71), nullable=False),
        sa.Column("parity_captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parity_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_manifest_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_manifest_hash", sa.String(length=71), nullable=False),
        sa.Column("source_active_corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_rollout_epoch", sa.BigInteger(), nullable=False),
        sa.Column("evidence_rollout_version", sa.BigInteger(), nullable=False),
        sa.Column("candidate_lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("envelope_contract_hash", sa.String(length=71), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_provider_execution_authorities_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            ["provider_execution_promotions.id"],
            name="fk_provider_execution_authorities_promotion",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_provider_execution_authorities_candidate_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_manifest_revision_id", "tenant_id"],
            ["policy_corpus_manifest_revisions.id", "policy_corpus_manifest_revisions.tenant_id"],
            name="fk_provider_execution_authorities_manifest_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_active_corpus_version_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_provider_execution_authorities_source_corpus_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_provider_execution_authorities_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_token",
            name="uq_provider_execution_authorities_tenant_run",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "candidate_id",
            name="uq_provider_execution_authorities_tenant_candidate",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(config_json) = 'object'",
            name="ck_provider_execution_authorities_config_object",
        ),
        sa.CheckConstraint(
            _sha256_columns_check(
                "config_fingerprint",
                "provider_parity_report_hash",
                "provider_parity_probe_fixture_sha256",
                "provider_parity_submitted_content_sha256",
                "source_manifest_hash",
                "envelope_contract_hash",
            ),
            name="ck_provider_execution_authorities_sha256_values",
        ),
        sa.CheckConstraint(
            "source_rollout_epoch > 0 AND evidence_rollout_version >= 0 AND dimensions > 0",
            name="ck_provider_execution_authorities_positive_values",
        ),
        sa.CheckConstraint(
            "parity_captured_at < parity_expires_at "
            "AND issued_at < expires_at "
            "AND expires_at <= parity_expires_at "
            "AND expires_at <= candidate_lease_expires_at",
            name="ck_provider_execution_authorities_expiry_intersection",
        ),
    )
    op.create_index(
        "ix_provider_execution_authorities_tenant_expires",
        "provider_execution_authorities",
        ["tenant_id", "expires_at"],
    )


def _create_reservation_table() -> None:
    op.create_table(
        "provider_execution_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("subject_kind", sa.String(length=64), nullable=False),
        sa.Column("subject_index", sa.Integer(), nullable=False),
        sa.Column("subject_hash", sa.String(length=71), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("envelope_schema_version", sa.String(length=64), nullable=False),
        sa.Column("request_envelope_json", postgresql.JSONB(), nullable=False),
        sa.Column("request_envelope_hash", sa.String(length=71), nullable=False),
        sa.Column("max_request_count", sa.Integer(), nullable=False),
        sa.Column("predecessor_result_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["authority_id", "tenant_id"],
            ["provider_execution_authorities.id", "provider_execution_authorities.tenant_id"],
            name="fk_provider_execution_reservations_authority_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "max_request_count",
            name="uq_provider_execution_reservations_id_tenant_limit",
        ),
        sa.UniqueConstraint(
            "authority_id",
            "purpose",
            "subject_hash",
            "ordinal",
            name="uq_provider_execution_reservations_subject_ordinal",
        ),
        sa.CheckConstraint(_PURPOSE_CHECK, name="ck_provider_execution_reservations_purpose"),
        sa.CheckConstraint(
            "subject_index >= 0 AND ordinal BETWEEN 1 AND 2 AND max_request_count > 0",
            name="ck_provider_execution_reservations_bounded_values",
        ),
        sa.CheckConstraint(
            "((ordinal = 1 AND predecessor_result_id IS NULL) OR (ordinal = 2 AND predecessor_result_id IS NOT NULL))",
            name="ck_provider_execution_reservations_predecessor",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(request_envelope_json) = 'object'",
            name="ck_provider_execution_reservations_envelope_object",
        ),
        sa.CheckConstraint(
            _sha256_columns_check("subject_hash", "request_envelope_hash"),
            name="ck_provider_execution_reservations_sha256_values",
        ),
    )
    op.create_index(
        "ix_provider_execution_reservations_authority_purpose",
        "provider_execution_reservations",
        ["authority_id", "purpose", "subject_hash"],
    )


def _create_result_table() -> None:
    op.create_table(
        "provider_execution_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_limit", sa.Integer(), nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=False),
        sa.Column("actual_request_count", sa.Integer(), nullable=False),
        sa.Column("result_schema_version", sa.String(length=64), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_hash", sa.String(length=71), nullable=False),
        sa.Column("output_candidate_id", postgresql.UUID(as_uuid=True)),
        sa.Column("terminal_run_hash", sa.String(length=71)),
        sa.Column("terminal_report_hash", sa.String(length=71)),
        sa.Column("selection_id", postgresql.UUID(as_uuid=True)),
        sa.Column("selection_decision_hash", sa.String(length=71)),
        sa.Column("activation_authorization_hash", sa.String(length=71)),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reservation_id", "tenant_id", "request_limit"],
            [
                "provider_execution_reservations.id",
                "provider_execution_reservations.tenant_id",
                "provider_execution_reservations.max_request_count",
            ],
            name="fk_provider_execution_results_reservation_tenant_limit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["output_candidate_id", "tenant_id"],
            ["policy_corpus_versions.id", "policy_corpus_versions.tenant_id"],
            name="fk_provider_execution_results_candidate_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_provider_execution_results_id_tenant"),
        sa.UniqueConstraint(
            "reservation_id",
            name="uq_provider_execution_results_reservation",
        ),
        sa.CheckConstraint(_RESULT_CODE_CHECK, name="ck_provider_execution_results_code"),
        sa.CheckConstraint(
            "request_limit > 0 AND actual_request_count BETWEEN 0 AND request_limit",
            name="ck_provider_execution_results_request_bound",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(result_json) = 'object'",
            name="ck_provider_execution_results_result_object",
        ),
        sa.CheckConstraint(
            f"result_hash {_SHA256_CHECK} "
            "AND (terminal_run_hash IS NULL OR terminal_run_hash "
            f"{_SHA256_CHECK}) "
            "AND (terminal_report_hash IS NULL OR terminal_report_hash "
            f"{_SHA256_CHECK}) "
            "AND (selection_decision_hash IS NULL OR selection_decision_hash "
            f"{_SHA256_CHECK}) "
            "AND (activation_authorization_hash IS NULL OR activation_authorization_hash "
            f"{_SHA256_CHECK})",
            name="ck_provider_execution_results_sha256_values",
        ),
    )


def _create_activation_lineage_table() -> None:
    selected_columns = (
        "authority_id",
        "reservation_id",
        "result_id",
        "selection_id",
        "selection_decision_hash",
        "terminal_run_hash",
        "terminal_report_hash",
        "activation_authorization_hash",
    )
    selected_present = " AND ".join(f"{column} IS NOT NULL" for column in selected_columns)
    selected_absent = " AND ".join(f"{column} IS NULL" for column in selected_columns)
    op.create_table(
        "activation_receipt_lineages",
        sa.Column("activation_history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_ordinal", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("prior_corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prior_rollout_epoch", sa.BigInteger(), nullable=False),
        sa.Column("rollout_epoch", sa.BigInteger(), nullable=False),
        sa.Column("authority_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_id", postgresql.UUID(as_uuid=True)),
        sa.Column("selection_id", postgresql.UUID(as_uuid=True)),
        sa.Column("selection_decision_hash", sa.String(length=71)),
        sa.Column("terminal_run_hash", sa.String(length=71)),
        sa.Column("terminal_report_hash", sa.String(length=71)),
        sa.Column("activation_authorization_hash", sa.String(length=71)),
        sa.Column("previous_receipt_hash", sa.String(length=71), nullable=False),
        sa.Column("receipt_hash", sa.String(length=71), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("activation_history_id"),
        sa.ForeignKeyConstraint(
            ["activation_history_id"],
            ["policy_corpus_activation_history.id"],
            name="fk_activation_receipt_lineages_history",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prior_corpus_version_id"],
            ["policy_corpus_versions.id"],
            name="fk_activation_receipt_lineages_prior_corpus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["current_corpus_version_id"],
            ["policy_corpus_versions.id"],
            name="fk_activation_receipt_lineages_current_corpus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["authority_id"],
            ["provider_execution_authorities.id"],
            name="fk_activation_receipt_lineages_authority",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["provider_execution_reservations.id"],
            name="fk_activation_receipt_lineages_reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_id"],
            ["provider_execution_results.id"],
            name="fk_activation_receipt_lineages_result",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_ACTIVATION_REASON_CHECK, name="ck_activation_receipt_lineages_reason"),
        sa.CheckConstraint(
            "event_ordinal BETWEEN 1 AND 3 AND prior_rollout_epoch >= 0 AND rollout_epoch = prior_rollout_epoch + 1",
            name="ck_activation_receipt_lineages_event_sequence",
        ),
        sa.CheckConstraint(
            f"((reason_code IN ('selected_cutover', 'selected_restore') AND {selected_present}) "
            f"OR (reason_code = 'rollback_prior' AND {selected_absent}))",
            name="ck_activation_receipt_lineages_selected_lineage",
        ),
        sa.CheckConstraint(
            _sha256_columns_check("previous_receipt_hash", "receipt_hash"),
            name="ck_activation_receipt_lineages_receipt_hashes",
        ),
        sa.CheckConstraint(
            "(selection_decision_hash IS NULL OR selection_decision_hash "
            f"{_SHA256_CHECK}) "
            "AND (terminal_run_hash IS NULL OR terminal_run_hash "
            f"{_SHA256_CHECK}) "
            "AND (terminal_report_hash IS NULL OR terminal_report_hash "
            f"{_SHA256_CHECK}) "
            "AND (activation_authorization_hash IS NULL OR activation_authorization_hash "
            f"{_SHA256_CHECK})",
            name="ck_activation_receipt_lineages_selected_hashes",
        ),
    )


def _sha256_columns_check(*columns: str) -> str:
    return " AND ".join(f"{column} {_SHA256_CHECK}" for column in columns)


def _install_append_only_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_provider_execution_authority_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'provider execution authority rows are append-only';
        END;
        $$
        """
    )
    for table_name in _AUTHORITY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION guard_provider_execution_authority_mutation()"
        )


def _drop_append_only_guards() -> None:
    for table_name in reversed(_AUTHORITY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS guard_provider_execution_authority_mutation()")
