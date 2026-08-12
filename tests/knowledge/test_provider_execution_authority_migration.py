from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/032_phase64_5_provider_execution_authority.py")
MIGRATION_REVISION = "032_phase64_5_provider_execution_authority"

EXPECTED_TABLES = {
    "provider_execution_promotions",
    "provider_execution_authorities",
    "provider_execution_reservations",
    "provider_execution_results",
    "activation_receipt_lineages",
}

EXPECTED_COLUMNS = {
    "provider_execution_promotions": {
        "id",
        "scope",
        "protected_code_c0_commit",
        "protected_code_c0_tree_hash",
        "protected_code_c1_commit",
        "protected_code_c1_tree_hash",
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
        "promoted_at",
    },
    "provider_execution_authorities": {
        "id",
        "tenant_id",
        "promotion_id",
        "run_token",
        "candidate_id",
        "owner_marker",
        "config_schema_version",
        "config_json",
        "config_fingerprint",
        "provider_parity_run_id",
        "provider_parity_report_hash",
        "provider_parity_probe_fixture_sha256",
        "provider_parity_submitted_content_sha256",
        "parity_captured_at",
        "parity_expires_at",
        "source_manifest_revision_id",
        "source_manifest_hash",
        "source_active_corpus_version_id",
        "source_rollout_epoch",
        "evidence_rollout_version",
        "candidate_lease_expires_at",
        "expires_at",
        "provider_name",
        "model_name",
        "dimensions",
        "envelope_contract_hash",
        "issued_at",
    },
    "provider_execution_reservations": {
        "id",
        "tenant_id",
        "authority_id",
        "purpose",
        "subject_kind",
        "subject_index",
        "subject_hash",
        "ordinal",
        "envelope_schema_version",
        "request_envelope_json",
        "request_envelope_hash",
        "max_request_count",
        "predecessor_result_id",
        "reserved_at",
    },
    "provider_execution_results": {
        "id",
        "tenant_id",
        "reservation_id",
        "request_limit",
        "result_code",
        "actual_request_count",
        "result_schema_version",
        "result_json",
        "result_hash",
        "output_candidate_id",
        "terminal_run_hash",
        "terminal_report_hash",
        "selection_id",
        "selection_decision_hash",
        "activation_authorization_hash",
        "completed_at",
    },
    "activation_receipt_lineages": {
        "activation_history_id",
        "event_ordinal",
        "reason_code",
        "prior_corpus_version_id",
        "current_corpus_version_id",
        "prior_rollout_epoch",
        "rollout_epoch",
        "authority_id",
        "reservation_id",
        "result_id",
        "selection_id",
        "selection_decision_hash",
        "terminal_run_hash",
        "terminal_report_hash",
        "activation_authorization_hash",
        "previous_receipt_hash",
        "receipt_hash",
        "created_at",
    },
}

EXPECTED_UNIQUES = {
    "provider_execution_promotions": {
        "uq_provider_execution_promotions_scope": ("scope",),
    },
    "provider_execution_authorities": {
        "uq_provider_execution_authorities_id_tenant": ("id", "tenant_id"),
        "uq_provider_execution_authorities_tenant_run": ("tenant_id", "run_token"),
        "uq_provider_execution_authorities_tenant_candidate": ("tenant_id", "candidate_id"),
    },
    "provider_execution_reservations": {
        "uq_provider_execution_reservations_id_tenant_limit": (
            "id",
            "tenant_id",
            "max_request_count",
        ),
        "uq_provider_execution_reservations_subject_ordinal": (
            "authority_id",
            "purpose",
            "subject_hash",
            "ordinal",
        ),
    },
    "provider_execution_results": {
        "uq_provider_execution_results_id_tenant": ("id", "tenant_id"),
        "uq_provider_execution_results_reservation": ("reservation_id",),
    },
    "activation_receipt_lineages": {},
}

EXPECTED_FOREIGN_KEY_DELETES = {
    "provider_execution_authorities": {
        "fk_provider_execution_authorities_tenant": "RESTRICT",
        "fk_provider_execution_authorities_promotion": "RESTRICT",
        "fk_provider_execution_authorities_candidate_tenant": "RESTRICT",
        "fk_provider_execution_authorities_manifest_tenant": "RESTRICT",
        "fk_provider_execution_authorities_source_corpus_tenant": "RESTRICT",
    },
    "provider_execution_reservations": {
        "fk_provider_execution_reservations_authority_tenant": "RESTRICT",
        "fk_provider_execution_reservations_predecessor_result_tenant": "RESTRICT",
    },
    "provider_execution_results": {
        "fk_provider_execution_results_reservation_tenant_limit": "RESTRICT",
        "fk_provider_execution_results_candidate_tenant": "RESTRICT",
    },
    "activation_receipt_lineages": {
        "fk_activation_receipt_lineages_history": "RESTRICT",
        "fk_activation_receipt_lineages_prior_corpus": "RESTRICT",
        "fk_activation_receipt_lineages_current_corpus": "RESTRICT",
        "fk_activation_receipt_lineages_authority": "RESTRICT",
        "fk_activation_receipt_lineages_reservation": "RESTRICT",
        "fk_activation_receipt_lineages_result": "RESTRICT",
    },
}

EXPECTED_CHECKS = {
    "provider_execution_promotions": {
        "ck_provider_execution_promotions_scope",
        "ck_provider_execution_promotions_c0_commit",
        "ck_provider_execution_promotions_c0_tree",
        "ck_provider_execution_promotions_c1_commit",
        "ck_provider_execution_promotions_c1_tree",
        "ck_provider_execution_promotions_sha256_values",
    },
    "provider_execution_authorities": {
        "ck_provider_execution_authorities_config_object",
        "ck_provider_execution_authorities_sha256_values",
        "ck_provider_execution_authorities_positive_values",
        "ck_provider_execution_authorities_expiry_intersection",
    },
    "provider_execution_reservations": {
        "ck_provider_execution_reservations_purpose",
        "ck_provider_execution_reservations_bounded_values",
        "ck_provider_execution_reservations_predecessor",
        "ck_provider_execution_reservations_envelope_object",
        "ck_provider_execution_reservations_sha256_values",
    },
    "provider_execution_results": {
        "ck_provider_execution_results_code",
        "ck_provider_execution_results_request_bound",
        "ck_provider_execution_results_result_object",
        "ck_provider_execution_results_sha256_values",
    },
    "activation_receipt_lineages": {
        "ck_activation_receipt_lineages_reason",
        "ck_activation_receipt_lineages_event_sequence",
        "ck_activation_receipt_lineages_selected_lineage",
        "ck_activation_receipt_lineages_receipt_hashes",
        "ck_activation_receipt_lineages_selected_hashes",
    },
}


def test_migration032_declares_head_and_orm_parity() -> None:
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert f'revision: str = "{MIGRATION_REVISION}"' in source
    assert 'down_revision: str | None = "031_phase64_4_policy_corpus_cow"' in source
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        assert set(table.c.keys()) == expected_columns
        for column_name in expected_columns:
            assert f'"{column_name}"' in source

        unique_constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert unique_constraints == EXPECTED_UNIQUES[table_name]

        check_names = {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}
        assert check_names == EXPECTED_CHECKS[table_name]

        if table_name in EXPECTED_FOREIGN_KEY_DELETES:
            foreign_key_deletes = {constraint.name: constraint.ondelete for constraint in table.foreign_key_constraints}
            assert foreign_key_deletes == EXPECTED_FOREIGN_KEY_DELETES[table_name]

    assert set(Base.metadata.tables["activation_receipt_lineages"].primary_key.columns.keys()) == {
        "activation_history_id"
    }
    assert "phase64.5.reviewed-provider-execution" in source
    assert "purpose IN ('reviewed_build', 'canonical_ab')" in source
    assert "uq_policy_corpus_versions_tenant_run_token" in source
    assert 'postgresql_where=sa.text("run_token IS NOT NULL")' in source
    assert "guard_provider_execution_authority_mutation" in source

    forbidden_authority_columns = {
        "artifact_path",
        "authority_path",
        "caller_id",
        "environment",
        "environment_authorized",
        "reviewer_id",
        "operator_time",
    }
    assert forbidden_authority_columns.isdisjoint(Base.metadata.tables["provider_execution_authorities"].c.keys())
