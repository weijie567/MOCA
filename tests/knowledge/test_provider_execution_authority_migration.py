from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import Base
from tests.migration_helpers import upgrade_to_head_with_evidence_cutover


MIGRATION_PATH = Path("src/db/migrations/versions/032_phase64_5_provider_execution_authority.py")
MIGRATION_REVISION = "032_phase64_5_provider_execution_authority"
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
SHA_F = "sha256:" + "f" * 64

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


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    config.attributes["database_url"] = DATABASE_URL
    return config


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


async def _upgrade_to_032() -> Config:
    await _reset_schema()
    config = _config()
    await upgrade_to_head_with_evidence_cutover(
        config,
        database_url=DATABASE_URL,
        target_revision=MIGRATION_REVISION,
    )
    return config


async def _insert_promotion(connection: AsyncConnection, promotion_id: UUID) -> None:
    await connection.execute(
        text(
            "INSERT INTO provider_execution_promotions "
            "(id, scope, protected_code_c0_commit, protected_code_c0_tree_hash, "
            "protected_code_c1_commit, protected_code_c1_tree_hash, c0_to_c1_diff_hash, "
            "c0_code_review_artifact_sha256, c0_security_artifact_sha256, "
            "c1_code_review_artifact_sha256, c1_security_artifact_sha256, "
            "c0_code_review_attestation_sha256, c0_security_attestation_sha256, "
            "c1_code_review_attestation_sha256, c1_security_attestation_sha256, "
            "c0_gate_report_sha256, c1_gate_report_sha256, promotion_request_hash) "
            "VALUES (:id, 'phase64.5.reviewed-provider-execution', :git_a, :git_b, :git_c, :git_d, "
            ":sha_a, :sha_b, :sha_c, :sha_d, :sha_e, :sha_f, :sha_a, :sha_b, :sha_c, "
            ":sha_d, :sha_e, :sha_f)"
        ),
        {
            "id": promotion_id,
            "git_a": "a" * 40,
            "git_b": "b" * 40,
            "git_c": "c" * 40,
            "git_d": "d" * 40,
            "sha_a": SHA_A,
            "sha_b": SHA_B,
            "sha_c": SHA_C,
            "sha_d": SHA_D,
            "sha_e": SHA_E,
            "sha_f": SHA_F,
        },
    )


async def _seed_authority_graph(connection: AsyncConnection) -> dict[str, UUID]:
    ids = {
        "tenant": uuid4(),
        "manifest": uuid4(),
        "active_corpus": uuid4(),
        "candidate": uuid4(),
        "candidate_two": uuid4(),
        "candidate_run": uuid4(),
        "candidate_two_run": uuid4(),
        "promotion": uuid4(),
        "authority": uuid4(),
        "build_reservation": uuid4(),
        "ab_reservation": uuid4(),
        "ab_result": uuid4(),
        "selection": uuid4(),
        "cutover_history": uuid4(),
        "rollback_history": uuid4(),
        "restore_history": uuid4(),
    }
    now = datetime.now(UTC)
    await connection.execute(
        text("INSERT INTO tenants (id, name, status) VALUES (:id, :name, 'active')"),
        {"id": ids["tenant"], "name": f"provider-authority-{ids['tenant']}"},
    )
    await connection.execute(
        text(
            "INSERT INTO policy_corpus_manifest_revisions "
            "(id, tenant_id, revision, manifest_schema_version, manifest_json, manifest_hash, "
            "document_count, block_count, chunk_count) "
            "VALUES (:id, :tenant_id, 1, 'provider-authority-manifest.v1', '{}'::jsonb, :hash, 0, 0, 0)"
        ),
        {"id": ids["manifest"], "tenant_id": ids["tenant"], "hash": SHA_A},
    )
    await connection.execute(
        text(
            "INSERT INTO policy_corpus_versions "
            "(id, tenant_id, generation_name, owner_marker, run_token, config_schema_version, "
            "config_json, config_fingerprint, source_manifest_revision_id, source_manifest_hash, "
            "source_active_corpus_version_id, source_rollout_epoch, expected_evidence_rollout_version, "
            "state, state_version, next_document_index, bootstrap_counts_json, validation_proof_json, "
            "lease_owner, lease_expires_at) "
            "VALUES (:id, :tenant_id, 'character.v1', 'fixture-owner', NULL, 'character.v1', "
            "'{}'::jsonb, :hash, :manifest_id, :hash, NULL, NULL, NULL, 'complete', 1, 0, "
            "'{}'::jsonb, '{}'::jsonb, NULL, NULL)"
        ),
        {
            "id": ids["active_corpus"],
            "tenant_id": ids["tenant"],
            "manifest_id": ids["manifest"],
            "hash": SHA_A,
        },
    )
    for candidate_key, run_key, generation_name in (
        ("candidate", "candidate_run", "token.v1.fixture-a"),
        ("candidate_two", "candidate_two_run", "token.v1.fixture-b"),
    ):
        await connection.execute(
            text(
                "INSERT INTO policy_corpus_versions "
                "(id, tenant_id, generation_name, owner_marker, run_token, config_schema_version, "
                "config_json, config_fingerprint, provider_parity_report_hash, "
                "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
                "source_rollout_epoch, expected_evidence_rollout_version, state, state_version, "
                "lease_owner, lease_expires_at, next_document_index, bootstrap_counts_json, "
                "validation_proof_json) "
                "VALUES (:id, :tenant_id, :generation_name, 'fixture-owner', :run_token, "
                "'token_chunking.v1', '{}'::jsonb, :hash, :hash, :manifest_id, :hash, "
                ":active_corpus_id, 1, 0, 'claimed', 1, 'fixture-owner', :lease_expires_at, 0, "
                "'{}'::jsonb, '{}'::jsonb)"
            ),
            {
                "id": ids[candidate_key],
                "tenant_id": ids["tenant"],
                "generation_name": generation_name,
                "run_token": ids[run_key],
                "hash": SHA_A,
                "manifest_id": ids["manifest"],
                "active_corpus_id": ids["active_corpus"],
                "lease_expires_at": now + timedelta(hours=2),
            },
        )
    await _insert_promotion(connection, ids["promotion"])
    await connection.execute(
        text(
            "INSERT INTO provider_execution_authorities "
            "(id, tenant_id, promotion_id, run_token, candidate_id, owner_marker, "
            "config_schema_version, config_json, config_fingerprint, provider_parity_run_id, "
            "provider_parity_report_hash, provider_parity_probe_fixture_sha256, "
            "provider_parity_submitted_content_sha256, parity_captured_at, parity_expires_at, "
            "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
            "source_rollout_epoch, evidence_rollout_version, candidate_lease_expires_at, expires_at, "
            "provider_name, model_name, dimensions, envelope_contract_hash) "
            "VALUES (:id, :tenant_id, :promotion_id, :run_token, :candidate_id, 'fixture-owner', "
            "'provider-execution-authority.v1', '{}'::jsonb, :sha_a, :parity_run_id, :sha_b, "
            ":sha_c, :sha_d, :captured_at, :parity_expires_at, :manifest_id, :sha_a, "
            ":active_corpus_id, 1, 0, :lease_expires_at, :expires_at, 'dashscope', "
            "'text-embedding-v3', 1024, :sha_e)"
        ),
        {
            "id": ids["authority"],
            "tenant_id": ids["tenant"],
            "promotion_id": ids["promotion"],
            "run_token": ids["candidate_run"],
            "candidate_id": ids["candidate"],
            "parity_run_id": uuid4(),
            "manifest_id": ids["manifest"],
            "active_corpus_id": ids["active_corpus"],
            "captured_at": now - timedelta(minutes=5),
            "parity_expires_at": now + timedelta(hours=2),
            "lease_expires_at": now + timedelta(hours=2),
            "expires_at": now + timedelta(hours=1),
            "sha_a": SHA_A,
            "sha_b": SHA_B,
            "sha_c": SHA_C,
            "sha_d": SHA_D,
            "sha_e": SHA_E,
        },
    )
    for reservation_key, purpose, subject_hash, envelope_hash, max_request_count in (
        ("build_reservation", "reviewed_build", SHA_B, SHA_C, 10),
        ("ab_reservation", "canonical_ab", SHA_D, SHA_E, 500),
    ):
        await connection.execute(
            text(
                "INSERT INTO provider_execution_reservations "
                "(id, tenant_id, authority_id, purpose, subject_kind, subject_index, subject_hash, "
                "ordinal, envelope_schema_version, request_envelope_json, request_envelope_hash, "
                "max_request_count, predecessor_result_id) "
                "VALUES (:id, :tenant_id, :authority_id, :purpose, 'fixture-subject', 0, "
                ":subject_hash, 1, 'provider-request-envelope.v1', '{}'::jsonb, :envelope_hash, "
                ":max_request_count, NULL)"
            ),
            {
                "id": ids[reservation_key],
                "tenant_id": ids["tenant"],
                "authority_id": ids["authority"],
                "purpose": purpose,
                "subject_hash": subject_hash,
                "envelope_hash": envelope_hash,
                "max_request_count": max_request_count,
            },
        )
    await connection.execute(
        text(
            "INSERT INTO provider_execution_results "
            "(id, tenant_id, reservation_id, request_limit, result_code, actual_request_count, "
            "result_schema_version, result_json, result_hash, output_candidate_id, terminal_run_hash, "
            "terminal_report_hash, selection_id, selection_decision_hash, activation_authorization_hash) "
            "VALUES (:id, :tenant_id, :reservation_id, 500, 'success', 3, "
            "'provider-execution-result.v1', '{}'::jsonb, :sha_a, :candidate_id, :sha_b, :sha_c, "
            ":selection_id, :sha_d, :sha_e)"
        ),
        {
            "id": ids["ab_result"],
            "tenant_id": ids["tenant"],
            "reservation_id": ids["ab_reservation"],
            "candidate_id": ids["candidate"],
            "selection_id": ids["selection"],
            "sha_a": SHA_A,
            "sha_b": SHA_B,
            "sha_c": SHA_C,
            "sha_d": SHA_D,
            "sha_e": SHA_E,
        },
    )
    history_specs = (
        ("cutover_history", 1, "selected_cutover", "active_corpus", "candidate", 1, 2, SHA_A),
        ("rollback_history", 2, "rollback_prior", "candidate", "active_corpus", 2, 3, SHA_B),
        ("restore_history", 3, "selected_restore", "active_corpus", "candidate", 3, 4, SHA_C),
    )
    for history_key, _, reason, from_key, to_key, prior_epoch, rollout_epoch, receipt_hash in history_specs:
        await connection.execute(
            text(
                "INSERT INTO policy_corpus_activation_history "
                "(id, tenant_id, from_corpus_version_id, to_corpus_version_id, prior_rollout_epoch, "
                "rollout_epoch, reason_code, actor, selection_decision_hash, receipt_hash) "
                "VALUES (:id, :tenant_id, :from_id, :to_id, :prior_epoch, :rollout_epoch, :reason, "
                "'phase64.5.fixture', :selection_hash, :receipt_hash)"
            ),
            {
                "id": ids[history_key],
                "tenant_id": ids["tenant"],
                "from_id": ids[from_key],
                "to_id": ids[to_key],
                "prior_epoch": prior_epoch,
                "rollout_epoch": rollout_epoch,
                "reason": reason,
                "selection_hash": None if reason == "rollback_prior" else SHA_D,
                "receipt_hash": receipt_hash,
            },
        )
    for history_key, event_ordinal, reason, prior_key, current_key, prior_epoch, rollout_epoch, _ in history_specs:
        selected = reason != "rollback_prior"
        await connection.execute(
            text(
                "INSERT INTO activation_receipt_lineages "
                "(activation_history_id, event_ordinal, reason_code, prior_corpus_version_id, "
                "current_corpus_version_id, prior_rollout_epoch, rollout_epoch, authority_id, "
                "reservation_id, result_id, selection_id, selection_decision_hash, terminal_run_hash, "
                "terminal_report_hash, activation_authorization_hash, previous_receipt_hash, receipt_hash) "
                "VALUES (:history_id, :event_ordinal, :reason, :prior_id, :current_id, :prior_epoch, "
                ":rollout_epoch, :authority_id, :reservation_id, :result_id, :selection_id, "
                ":selection_hash, :terminal_run_hash, :terminal_report_hash, :authorization_hash, "
                ":previous_receipt_hash, :receipt_hash)"
            ),
            {
                "history_id": ids[history_key],
                "event_ordinal": event_ordinal,
                "reason": reason,
                "prior_id": ids[prior_key],
                "current_id": ids[current_key],
                "prior_epoch": prior_epoch,
                "rollout_epoch": rollout_epoch,
                "authority_id": ids["authority"] if selected else None,
                "reservation_id": ids["ab_reservation"] if selected else None,
                "result_id": ids["ab_result"] if selected else None,
                "selection_id": ids["selection"] if selected else None,
                "selection_hash": SHA_D if selected else None,
                "terminal_run_hash": SHA_B if selected else None,
                "terminal_report_hash": SHA_C if selected else None,
                "authorization_hash": SHA_E if selected else None,
                "previous_receipt_hash": {
                    "cutover_history": SHA_F,
                    "rollback_history": SHA_A,
                    "restore_history": SHA_B,
                }[history_key],
                "receipt_hash": {
                    "cutover_history": SHA_A,
                    "rollback_history": SHA_B,
                    "restore_history": SHA_C,
                }[history_key],
            },
        )
    return ids


async def _expect_integrity_error(
    connection: AsyncConnection,
    statement: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(IntegrityError):
        async with connection.begin_nested():
            await connection.execute(text(statement), parameters)


async def _expect_append_only_error(
    connection: AsyncConnection,
    statement: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        async with connection.begin_nested():
            await connection.execute(text(statement), parameters)


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


@pytest.mark.asyncio
async def test_migration032_real_schema_and_empty_downgrade() -> None:
    config = await _upgrade_to_032()
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == MIGRATION_REVISION

            table_names = set(
                await connection.scalars(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(:table_names)"
                    ),
                    {"table_names": sorted(EXPECTED_TABLES)},
                )
            )
            assert table_names == EXPECTED_TABLES

            for table_name in EXPECTED_TABLES:
                constraint_names = set(
                    await connection.scalars(
                        text(
                            "SELECT c.conname FROM pg_constraint c "
                            "JOIN pg_class t ON t.oid = c.conrelid "
                            "JOIN pg_namespace n ON n.oid = t.relnamespace "
                            "WHERE n.nspname = 'public' AND t.relname = :table_name"
                        ),
                        {"table_name": table_name},
                    )
                )
                assert EXPECTED_CHECKS[table_name].issubset(constraint_names)
                assert set(EXPECTED_UNIQUES[table_name]).issubset(constraint_names)
                assert set(EXPECTED_FOREIGN_KEY_DELETES.get(table_name, {})).issubset(constraint_names)

            trigger_names = set(
                await connection.scalars(
                    text(
                        "SELECT tg.tgname FROM pg_trigger tg "
                        "JOIN pg_class t ON t.oid = tg.tgrelid "
                        "WHERE NOT tg.tgisinternal AND t.relname = ANY(:table_names)"
                    ),
                    {"table_names": sorted(EXPECTED_TABLES)},
                )
            )
            assert trigger_names == {f"trg_{table_name}_append_only" for table_name in EXPECTED_TABLES}

            candidate_index = await connection.scalar(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname = 'uq_policy_corpus_versions_tenant_run_token'"
                )
            )
            assert candidate_index is not None
            assert "UNIQUE INDEX" in candidate_index
            assert "(tenant_id, run_token)" in candidate_index
            assert "WHERE (run_token IS NOT NULL)" in candidate_index
    finally:
        await engine.dispose()

    await asyncio.to_thread(command.downgrade, config, "031_phase64_4_policy_corpus_cow")
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "031_phase64_4_policy_corpus_cow"
            remaining_tables = set(
                await connection.scalars(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(:table_names)"
                    ),
                    {"table_names": sorted(EXPECTED_TABLES)},
                )
            )
            assert remaining_tables == set()
            candidate_index_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname = 'uq_policy_corpus_versions_tenant_run_token'"
                )
            )
            assert candidate_index_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration032_enforces_authority_budget_and_immutability() -> None:
    await _upgrade_to_032()
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            ids = await _seed_authority_graph(connection)
            purposes = set(
                await connection.scalars(
                    text("SELECT purpose FROM provider_execution_reservations WHERE authority_id = :authority_id"),
                    {"authority_id": ids["authority"]},
                )
            )
            assert purposes == {"reviewed_build", "canonical_ab"}

            await _expect_integrity_error(
                connection,
                "INSERT INTO provider_execution_promotions "
                "(id, scope, protected_code_c0_commit, protected_code_c0_tree_hash, "
                "protected_code_c1_commit, protected_code_c1_tree_hash, c0_to_c1_diff_hash, "
                "c0_code_review_artifact_sha256, c0_security_artifact_sha256, "
                "c1_code_review_artifact_sha256, c1_security_artifact_sha256, "
                "c0_code_review_attestation_sha256, c0_security_attestation_sha256, "
                "c1_code_review_attestation_sha256, c1_security_attestation_sha256, "
                "c0_gate_report_sha256, c1_gate_report_sha256, promotion_request_hash) "
                "SELECT :new_id, scope, protected_code_c0_commit, protected_code_c0_tree_hash, "
                "protected_code_c1_commit, protected_code_c1_tree_hash, c0_to_c1_diff_hash, "
                "c0_code_review_artifact_sha256, c0_security_artifact_sha256, "
                "c1_code_review_artifact_sha256, c1_security_artifact_sha256, "
                "c0_code_review_attestation_sha256, c0_security_attestation_sha256, "
                "c1_code_review_attestation_sha256, c1_security_attestation_sha256, "
                "c0_gate_report_sha256, c1_gate_report_sha256, promotion_request_hash "
                "FROM provider_execution_promotions WHERE id = :source_id",
                {"new_id": uuid4(), "source_id": ids["promotion"]},
            )

            authority_clone = (
                "INSERT INTO provider_execution_authorities "
                "(id, tenant_id, promotion_id, run_token, candidate_id, owner_marker, "
                "config_schema_version, config_json, config_fingerprint, provider_parity_run_id, "
                "provider_parity_report_hash, provider_parity_probe_fixture_sha256, "
                "provider_parity_submitted_content_sha256, parity_captured_at, parity_expires_at, "
                "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
                "source_rollout_epoch, evidence_rollout_version, candidate_lease_expires_at, expires_at, "
                "provider_name, model_name, dimensions, envelope_contract_hash) "
                "SELECT :new_id, tenant_id, :promotion_id, :run_token, :candidate_id, owner_marker, "
                "config_schema_version, config_json, config_fingerprint, provider_parity_run_id, "
                "provider_parity_report_hash, provider_parity_probe_fixture_sha256, "
                "provider_parity_submitted_content_sha256, parity_captured_at, parity_expires_at, "
                "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
                "source_rollout_epoch, evidence_rollout_version, candidate_lease_expires_at, expires_at, "
                "provider_name, model_name, dimensions, envelope_contract_hash "
                "FROM provider_execution_authorities WHERE id = :source_id"
            )
            await _expect_integrity_error(
                connection,
                authority_clone,
                {
                    "new_id": uuid4(),
                    "promotion_id": uuid4(),
                    "run_token": uuid4(),
                    "candidate_id": ids["candidate_two"],
                    "source_id": ids["authority"],
                },
            )
            await _expect_integrity_error(
                connection,
                authority_clone,
                {
                    "new_id": uuid4(),
                    "promotion_id": ids["promotion"],
                    "run_token": ids["candidate_run"],
                    "candidate_id": ids["candidate_two"],
                    "source_id": ids["authority"],
                },
            )
            await _expect_integrity_error(
                connection,
                authority_clone,
                {
                    "new_id": uuid4(),
                    "promotion_id": ids["promotion"],
                    "run_token": uuid4(),
                    "candidate_id": ids["candidate"],
                    "source_id": ids["authority"],
                },
            )

            await _expect_integrity_error(
                connection,
                "INSERT INTO policy_corpus_versions "
                "(id, tenant_id, generation_name, owner_marker, run_token, config_schema_version, "
                "config_json, config_fingerprint, provider_parity_report_hash, "
                "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
                "source_rollout_epoch, expected_evidence_rollout_version, state, state_version, "
                "lease_owner, lease_expires_at, next_document_index, bootstrap_counts_json, "
                "validation_proof_json) "
                "SELECT :new_id, tenant_id, :generation_name, owner_marker, run_token, "
                "config_schema_version, config_json, config_fingerprint, provider_parity_report_hash, "
                "source_manifest_revision_id, source_manifest_hash, source_active_corpus_version_id, "
                "source_rollout_epoch, expected_evidence_rollout_version, state, state_version, "
                "lease_owner, lease_expires_at, next_document_index, bootstrap_counts_json, "
                "validation_proof_json FROM policy_corpus_versions WHERE id = :source_id",
                {
                    "new_id": uuid4(),
                    "generation_name": "token.v1.duplicate-run",
                    "source_id": ids["candidate"],
                },
            )

            await _expect_integrity_error(
                connection,
                "INSERT INTO provider_execution_reservations "
                "(id, tenant_id, authority_id, purpose, subject_kind, subject_index, subject_hash, "
                "ordinal, envelope_schema_version, request_envelope_json, request_envelope_hash, "
                "max_request_count, predecessor_result_id) "
                "SELECT :new_id, tenant_id, authority_id, purpose, subject_kind, subject_index, "
                "subject_hash, ordinal, envelope_schema_version, request_envelope_json, "
                "request_envelope_hash, max_request_count, predecessor_result_id "
                "FROM provider_execution_reservations WHERE id = :source_id",
                {"new_id": uuid4(), "source_id": ids["build_reservation"]},
            )
            await _expect_integrity_error(
                connection,
                "INSERT INTO provider_execution_results "
                "(id, tenant_id, reservation_id, request_limit, result_code, actual_request_count, "
                "result_schema_version, result_json, result_hash, output_candidate_id, "
                "terminal_run_hash, terminal_report_hash, selection_id, selection_decision_hash, "
                "activation_authorization_hash) "
                "SELECT :new_id, tenant_id, reservation_id, request_limit, result_code, "
                "actual_request_count, result_schema_version, result_json, result_hash, "
                "output_candidate_id, terminal_run_hash, terminal_report_hash, selection_id, "
                "selection_decision_hash, activation_authorization_hash "
                "FROM provider_execution_results WHERE id = :source_id",
                {"new_id": uuid4(), "source_id": ids["ab_result"]},
            )
            await _expect_integrity_error(
                connection,
                "INSERT INTO provider_execution_results "
                "(id, tenant_id, reservation_id, request_limit, result_code, actual_request_count, "
                "result_schema_version, result_json, result_hash) "
                "SELECT :new_id, tenant_id, id, max_request_count, 'response_error', "
                "max_request_count + 1, 'provider-execution-result.v1', '{}'::jsonb, :result_hash "
                "FROM provider_execution_reservations WHERE id = :reservation_id",
                {
                    "new_id": uuid4(),
                    "reservation_id": ids["build_reservation"],
                    "result_hash": SHA_F,
                },
            )

            protected_rows = {
                "provider_execution_promotions": ("id", ids["promotion"]),
                "provider_execution_authorities": ("id", ids["authority"]),
                "provider_execution_reservations": ("id", ids["build_reservation"]),
                "provider_execution_results": ("id", ids["ab_result"]),
                "activation_receipt_lineages": (
                    "activation_history_id",
                    ids["cutover_history"],
                ),
            }
            for table_name, (key_column, row_id) in protected_rows.items():
                await _expect_append_only_error(
                    connection,
                    f"UPDATE {table_name} SET {key_column} = {key_column} WHERE {key_column} = :row_id",
                    {"row_id": row_id},
                )
                await _expect_append_only_error(
                    connection,
                    f"DELETE FROM {table_name} WHERE {key_column} = :row_id",
                    {"row_id": row_id},
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration032_activation_lineage_reuse_and_rollback_null_contract() -> None:
    await _upgrade_to_032()
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            ids = await _seed_authority_graph(connection)
            selected_rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT authority_id, reservation_id, result_id, selection_id, "
                            "selection_decision_hash, terminal_run_hash, terminal_report_hash, "
                            "activation_authorization_hash FROM activation_receipt_lineages "
                            "WHERE reason_code IN ('selected_cutover', 'selected_restore') "
                            "ORDER BY event_ordinal"
                        )
                    )
                )
                .tuples()
                .all()
            )
            assert len(selected_rows) == 2
            assert selected_rows[0] == selected_rows[1]

            rollback = (
                (
                    await connection.execute(
                        text(
                            "SELECT authority_id, reservation_id, result_id, selection_id, "
                            "selection_decision_hash, terminal_run_hash, terminal_report_hash, "
                            "activation_authorization_hash FROM activation_receipt_lineages "
                            "WHERE reason_code = 'rollback_prior'"
                        )
                    )
                )
                .tuples()
                .one()
            )
            assert rollback == (None,) * 8

            unique_constraints = list(
                await connection.scalars(
                    text(
                        "SELECT c.conname FROM pg_constraint c "
                        "JOIN pg_class t ON t.oid = c.conrelid "
                        "WHERE t.relname = 'activation_receipt_lineages' "
                        "AND c.contype IN ('p', 'u')"
                    )
                )
            )
            assert unique_constraints == ["activation_receipt_lineages_pkey"]

            await _expect_integrity_error(
                connection,
                "INSERT INTO activation_receipt_lineages "
                "SELECT * FROM activation_receipt_lineages "
                "WHERE activation_history_id = :history_id",
                {"history_id": ids["cutover_history"]},
            )

            invalid_rollback_history = uuid4()
            await connection.execute(
                text(
                    "INSERT INTO policy_corpus_activation_history "
                    "(id, tenant_id, from_corpus_version_id, to_corpus_version_id, prior_rollout_epoch, "
                    "rollout_epoch, reason_code, actor, selection_decision_hash, receipt_hash) "
                    "VALUES (:id, :tenant_id, :from_id, :to_id, 4, 5, 'rollback_prior', "
                    "'phase64.5.fixture', NULL, :receipt_hash)"
                ),
                {
                    "id": invalid_rollback_history,
                    "tenant_id": ids["tenant"],
                    "from_id": ids["candidate"],
                    "to_id": ids["active_corpus"],
                    "receipt_hash": SHA_D,
                },
            )
            await _expect_integrity_error(
                connection,
                "INSERT INTO activation_receipt_lineages "
                "(activation_history_id, event_ordinal, reason_code, prior_corpus_version_id, "
                "current_corpus_version_id, prior_rollout_epoch, rollout_epoch, authority_id, "
                "reservation_id, result_id, selection_id, selection_decision_hash, terminal_run_hash, "
                "terminal_report_hash, activation_authorization_hash, previous_receipt_hash, receipt_hash) "
                "VALUES (:history_id, 2, 'rollback_prior', :prior_id, :current_id, 4, 5, "
                ":authority_id, :reservation_id, :result_id, :selection_id, :selection_hash, "
                ":run_hash, :report_hash, :authorization_hash, :previous_hash, :receipt_hash)",
                {
                    "history_id": invalid_rollback_history,
                    "prior_id": ids["candidate"],
                    "current_id": ids["active_corpus"],
                    "authority_id": ids["authority"],
                    "reservation_id": ids["ab_reservation"],
                    "result_id": ids["ab_result"],
                    "selection_id": ids["selection"],
                    "selection_hash": SHA_D,
                    "run_hash": SHA_B,
                    "report_hash": SHA_C,
                    "authorization_hash": SHA_E,
                    "previous_hash": SHA_C,
                    "receipt_hash": SHA_D,
                },
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration032_nonempty_downgrade_is_guarded() -> None:
    await _reset_schema()
    config = _config()
    await upgrade_to_head_with_evidence_cutover(
        config,
        database_url=DATABASE_URL,
        target_revision=MIGRATION_REVISION,
    )

    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO provider_execution_promotions "
                    "(id, scope, protected_code_c0_commit, protected_code_c0_tree_hash, "
                    "protected_code_c1_commit, protected_code_c1_tree_hash, c0_to_c1_diff_hash, "
                    "c0_code_review_artifact_sha256, c0_security_artifact_sha256, "
                    "c1_code_review_artifact_sha256, c1_security_artifact_sha256, "
                    "c0_code_review_attestation_sha256, c0_security_attestation_sha256, "
                    "c1_code_review_attestation_sha256, c1_security_attestation_sha256, "
                    "c0_gate_report_sha256, c1_gate_report_sha256, promotion_request_hash) "
                    "VALUES (:id, 'phase64.5.reviewed-provider-execution', :git, :git, :git, :git, "
                    ":sha, :sha, :sha, :sha, :sha, :sha, :sha, :sha, :sha, :sha, :sha, :sha)"
                ),
                {
                    "id": uuid4(),
                    "git": "a" * 40,
                    "sha": "sha256:" + "b" * 64,
                },
            )
    finally:
        await engine.dispose()

    with pytest.raises(RuntimeError, match="provider execution authority rows exist"):
        await asyncio.to_thread(command.downgrade, config, "031_phase64_4_policy_corpus_cow")

    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            promotion_count = await connection.scalar(text("SELECT count(*) FROM provider_execution_promotions"))
            assert revision == MIGRATION_REVISION
            assert promotion_count == 1
    finally:
        await engine.dispose()
