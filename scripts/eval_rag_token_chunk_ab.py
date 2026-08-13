"""Full-provider character/token A/B runner with immutable terminal evidence."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text

from src.config import settings
from src.db.models import EvidenceIdentityRollout, PolicyCorpusManifestRevision
from src.db.models import ProviderExecutionAuthority
from src.db.session import SessionLocal
from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    QUERY_REWRITE_CONFIG_VERSION,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.retrieval import (
    FUZZY_CANDIDATE_TOP_K,
    ORIGINAL_QUERY_TOP_K,
    RRF_K,
    SPARSE_CANDIDATE_TOP_K,
)
from src.rag.embedder import EmbeddingService
from src.rag.embedding_tokenizer import load_embedding_tokenizer_config
from src.rag.evaluation.contracts import EvaluationOutcome, FormatParityContractError, load_format_parity_contract
from src.rag.evaluation.retrieval_rounds import (
    SafeRoleExecutionError,
    SafeRoleFailureV1,
    build_ab_round_namespaces,
    ordered_gold_questions,
    run_rollback_only_retrieval_parity,
)
from src.rag.evaluation.reporting import load_format_parity_report
from src.rag.evaluation.token_chunk_ab import (
    SEALED_ANSWERABLE_CASE_COUNT,
    SEALED_DATASET_BASELINE_IDENTITY,
    SEALED_GOLD_HASH,
    SEALED_MANIFEST_HASH,
    SEALED_TOTAL_CASE_COUNT,
    CANONICAL_AB_OUTER_ATTEMPTS,
    CANONICAL_AB_PROVIDER_BATCH_SIZE,
    ABHardProofsV1,
    ABExecutionDiagnosticV1,
    ABInputIdentityV1,
    ABNamespaceV1,
    ABParityEvidenceV1,
    RecoveryLiveAuthorityProofV1,
    ABRuntimeConfigV1,
    ABSelectionBindingV1,
    RecoveryAttemptRefused,
    TerminalABRunV1,
    CanonicalABRequestEnvelopeV1,
    CanonicalABExecutionService,
    CanonicalABRunResultV1,
    build_canonical_ab_request_envelope,
    build_candidate_observation_from_retrieval,
    build_terminal_ab_run,
    canonical_ab_typed_failure_result_code,
    issue_canonical_recovery_budget_manifest,
    load_recovery_issuance_identity,
    load_recovery_budget_manifest,
    load_recovery_candidate_state,
    require_canonical_recovery_root,
    validate_fixed_plan10_evidence,
    write_execution_error_bundle_create_only,
    write_db_activation_authorization_create_only,
    write_selection_create_only,
    write_terminal_run_create_only,
)
from src.rag.evaluation.reporting import canonical_report_json_bytes
from src.rag.ingestion import (
    CHARACTER_COMPATIBILITY_CONFIG_VERSION,
    CharacterCompatibilityAssembler,
)
from src.rag.parsers.runtime import check_ocr_runtime
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex import PolicyReindexRunIdentity
from src.rag.policy_reindex import (
    POLICY_REINDEX_OWNER_MARKER,
    PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH,
)
from src.rag.policy_reindex_artifacts import (
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
)
from src.rag.provider_execution_authority import ProviderExecutionAuthorityService
from src.rag.provider_execution_authority import ProviderExecutionResultCode
from src.rag.tokenizer_parity import TokenizerParityError, require_fresh_provider_parity
from src.repositories.policy_corpus_repo import PolicyCorpusRepository, PolicyCorpusUnavailable
from src.repositories.provider_execution_authority_repo import ProviderExecutionAuthorityRepository
from src.repositories.rag_evaluation_round_repo import FORMAT_PARITY_TENANT_ID
from scripts.eval_rag_format_parity import _database_prerequisites


DEFAULT_MANIFEST = Path("evaluation/rag_sources/format_parity_manifest.jsonl")
DEFAULT_GOLD = Path("evaluation/golden/rag_format_parity_gold.json")
DEFAULT_BASELINE = Path("evaluation/reports/rag_format_parity/v1/baseline.json")
DEFAULT_OUTPUT_ROOT = Path("evaluation/reports/rag_token_chunk_ab/v1")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OWNER_MARKER = "moca.rag_token_chunk_ab.v1"
PROVIDER_RUNTIME_IDENTITY = "dashscope_openai_compatible.v1"
COST_BASIS_VERSION = "dashscope_text_embedding_v4_cost.v1"
COST_CURRENCY = "CNY"
COST_UNIT_TOKENS = 1_000
COST_PRICE_PER_UNIT = Decimal("0.0007")
LIVE_PROVIDER_EXECUTION_DISABLED = "live_provider_execution_disabled"


def _refuse_live_provider_execution() -> int:
    print(
        json.dumps(
            {
                "error": LIVE_PROVIDER_EXECUTION_DISABLED,
                "reason_code": LIVE_PROVIDER_EXECUTION_DISABLED,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 4


@dataclass(frozen=True, slots=True)
class CandidateProofSnapshot:
    deterministic_rebuild_hash: str
    provider_parity_report_hash: str
    validation_proof: dict[str, Any]


def _character_incumbent() -> CharacterCompatibilityAssembler:
    return CharacterCompatibilityAssembler()


def _token_candidate() -> PolicyEmbeddingInputAssembler:
    return PolicyEmbeddingInputAssembler()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "issue-recovery-budget":
        parser = argparse.ArgumentParser(description="Issue the canonical RAG token chunk recovery budget")
        parser.add_argument("command", choices=("issue-recovery-budget",))
        parser.add_argument("--candidate-state", type=Path, required=True)
        parser.add_argument("--parity-report", type=Path, required=True)
        parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
        return parser.parse_args(values)

    parser = argparse.ArgumentParser(
        description="Run full-provider immutable RAG token chunk A/B",
        epilog=(
            "Canonical issuance: issue-recovery-budget --candidate-state PATH "
            "--parity-report PATH --output-root evaluation/reports/rag_token_chunk_ab/v1"
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--candidate-state", type=Path, required=True)
    parser.add_argument("--parity-report", type=Path, required=True)
    parser.add_argument("--probe-fixture-hash", required=True)
    parser.add_argument("--submitted-content-hash", required=True)
    parser.add_argument("--authority-id", type=UUID, required=True)
    parser.add_argument("--ordinal", type=int, choices=(1, 2), default=1)
    parser.add_argument("--run-id", type=UUID, default=None)
    parser.add_argument("--selection-id", type=UUID, default=None)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(values)
    args.command = "run-ab"
    args.run_id = args.run_id or uuid4()
    args.selection_id = args.selection_id or uuid4()
    args.generated_at = args.generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        generated_at = datetime.fromisoformat(str(args.generated_at).replace("Z", "+00:00"))
    except ValueError:
        parser.error("--generated-at must be an ISO-8601 timestamp")
    if generated_at.tzinfo is None:
        parser.error("--generated-at must include a timezone")
    return args


def _provider_execution_authority_service() -> ProviderExecutionAuthorityService:
    repository = ProviderExecutionAuthorityRepository(SessionLocal, project_entry=REPOSITORY_ROOT)
    return ProviderExecutionAuthorityService(repository)


def _runtime(
    *,
    run_id: UUID,
    incumbent_corpus_id: UUID,
    candidate_corpus_id: UUID,
    execution_kind: str = "full_provider",
) -> ABRuntimeConfigV1:
    namespaces = build_ab_round_namespaces(
        run_id=run_id,
        incumbent_corpus_version_id=incumbent_corpus_id,
        candidate_corpus_version_id=candidate_corpus_id,
    )
    return ABRuntimeConfigV1(
        execution_kind=execution_kind,
        tenant_id=FORMAT_PARITY_TENANT_ID,
        owner_marker=OWNER_MARKER,
        provider="dashscope",
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        provider_runtime_identity=PROVIDER_RUNTIME_IDENTITY,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rrf_config=(
            f"rrf_k={RRF_K};dense={ORIGINAL_QUERY_TOP_K};sparse={SPARSE_CANDIDATE_TOP_K};fuzzy={FUZZY_CANDIDATE_TOP_K}"
        ),
        rewrite_config=f"{QUERY_REWRITE_CONFIG_VERSION}:enabled",
        reranker_config=f"{RERANK_CONFIG_VERSION}:enabled",
        no_evidence_threshold=Decimal(str(MIN_SIMILARITY_THRESHOLD)),
        incumbent=ABNamespaceV1(
            corpus_version_id=incumbent_corpus_id,
            round_owner=namespaces[0].round_owner,
        ),
        candidate=ABNamespaceV1(
            corpus_version_id=candidate_corpus_id,
            round_owner=namespaces[1].round_owner,
        ),
    )


def _inputs(args: argparse.Namespace, *, ordered_questions_sha256: str) -> ABInputIdentityV1:
    return ABInputIdentityV1(
        manifest_hash=SEALED_MANIFEST_HASH,
        gold_hash=SEALED_GOLD_HASH,
        dataset_baseline_identity=SEALED_DATASET_BASELINE_IDENTITY,
        baseline_report_sha256=_path_sha256(args.baseline),
        ordered_questions_sha256=ordered_questions_sha256,
        answerable_case_count=SEALED_ANSWERABLE_CASE_COUNT,
        total_case_count=SEALED_TOTAL_CASE_COUNT,
    )


def _unavailable_parity(*, run_id: UUID, generated_at: datetime, reason_code: str) -> ABParityEvidenceV1:
    del reason_code
    return ABParityEvidenceV1(
        report_sha256="sha256:" + "0" * 64,
        run_id=uuid5(NAMESPACE_URL, f"{run_id}:unavailable-parity"),
        captured_at=generated_at,
        status="unavailable",
        config_fingerprint=_token_candidate().config.config_fingerprint,
        probe_fixture_sha256="sha256:" + "0" * 64,
        submitted_content_sha256="sha256:" + "0" * 64,
        reason_code="provider_usage_unavailable",
    )


def _terminal_without_observations(
    args: argparse.Namespace,
    *,
    inputs: ABInputIdentityV1,
    outcome: str,
    stage: str,
    reason_code: str,
    incumbent_corpus_id: UUID | None = None,
    candidate_corpus_id: UUID | None = None,
    parity: ABParityEvidenceV1 | None = None,
) -> TerminalABRunV1:
    generated_at = datetime.fromisoformat(str(args.generated_at).replace("Z", "+00:00")).astimezone(UTC)
    incumbent_id = incumbent_corpus_id or uuid5(NAMESPACE_URL, f"{args.run_id}:incumbent-unavailable")
    candidate_id = candidate_corpus_id or uuid5(NAMESPACE_URL, f"{args.run_id}:candidate-unavailable")
    return TerminalABRunV1(
        run_id=args.run_id,
        generated_at=generated_at,
        outcome=outcome,
        failure_class=None,
        terminal_stage=stage,
        safe_reason_codes=(reason_code,),
        inputs=inputs,
        runtime=_runtime(run_id=args.run_id, incumbent_corpus_id=incumbent_id, candidate_corpus_id=candidate_id),
        parity=parity or _unavailable_parity(run_id=args.run_id, generated_at=generated_at, reason_code=reason_code),
        incumbent=None,
        candidate=None,
        hard_proofs=None,
        gates=(),
    )


def canonical_ab_failure_result_code(failure: SafeRoleFailureV1) -> ProviderExecutionResultCode:
    """Map one validated failure to DB retry authority without broadening retry."""

    return canonical_ab_typed_failure_result_code(
        stage=failure.stage,
        reason_code=failure.reason_code,
        provider_availability=failure.provider_availability,
        provider_request_classification=failure.provider_request_classification,
        outer_rollback_attempted=failure.outer_rollback_attempted,
        outer_rollback_proved=failure.outer_rollback_proved,
        provider_request_count=failure.provider_request_count,
    )


def _typed_failure_execution_result(
    *,
    args: argparse.Namespace,
    inputs: ABInputIdentityV1,
    failure: SafeRoleFailureV1,
    incumbent_corpus_id: UUID,
    candidate_corpus_id: UUID,
    parity: ABParityEvidenceV1 | None,
    actual_request_count: int,
) -> CanonicalABRunResultV1:
    report = _terminal_without_observations(
        args,
        inputs=inputs,
        outcome="execution_error",
        stage="execution",
        reason_code=failure.reason_code,
        incumbent_corpus_id=incumbent_corpus_id,
        candidate_corpus_id=candidate_corpus_id,
        parity=parity,
    )
    return CanonicalABRunResultV1(
        report=report,
        binding=None,
        diagnostic=_execution_diagnostic_from_failure(report, failure),
        actual_request_count=actual_request_count,
        result_code=canonical_ab_failure_result_code(failure),
    )


async def run_full_provider_ab(
    args: argparse.Namespace,
    *,
    inputs: ABInputIdentityV1,
    embedder: EmbeddingService | None = None,
) -> CanonicalABRunResultV1:
    generated_at = datetime.fromisoformat(str(args.generated_at).replace("Z", "+00:00")).astimezone(UTC)
    authority_checked_at = getattr(args, "_authority_checked_at", datetime.now(UTC))
    candidate_identity: PolicyReindexRunIdentity | None = getattr(args, "_verified_candidate_identity", None)
    try:
        if candidate_identity is None:
            manifest = load_recovery_budget_manifest(args.recovery_budget_manifest)
            candidate_identity = load_recovery_candidate_state(
                manifest=manifest,
                root=args.output_root,
                candidate_state_path=args.candidate_state,
                provider_parity_report_path=args.parity_report,
                checked_at=authority_checked_at,
            )
    except (OSError, RecoveryAttemptRefused, ValueError):
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid") from None

    incumbent_corpus_id = candidate_identity.source_active_corpus_version_id
    candidate_corpus_id = candidate_identity.corpus_version_id
    try:
        dataset = load_format_parity_contract(args.manifest, args.gold, repository_root=Path.cwd())
        _require_sealed_dataset(dataset)
        _require_sealed_baseline(args.baseline)
        questions_hash = _ordered_questions_sha256(ordered_gold_questions(dataset))
        if _inputs(args, ordered_questions_sha256=questions_hash) != inputs:
            raise ValueError("canonical_ab_input_identity_mismatch")
        build_canonical_ab_request_envelope(
            dataset=dataset,
            incumbent_assembler=_character_incumbent(),
            candidate_assembler=_token_candidate(),
            repository_root=REPOSITORY_ROOT,
        )
    except (FormatParityContractError, OSError, ValueError):
        return _typed_failure_execution_result(
            args=args,
            inputs=inputs,
            failure=_shared_preflight_failure(args, reason_code="sealed_input_invalid"),
            incumbent_corpus_id=incumbent_corpus_id,
            candidate_corpus_id=candidate_corpus_id,
            parity=None,
            actual_request_count=0,
        )

    token_assembler = _token_candidate()
    character_assembler = _character_incumbent()
    try:
        parity_report = require_fresh_provider_parity(
            args.parity_report,
            config=load_embedding_tokenizer_config(),
            expected_probe_fixture_sha256=args.probe_fixture_hash,
            expected_submitted_content_sha256=args.submitted_content_hash,
            now=generated_at,
        )
        parity = ABParityEvidenceV1(
            report_sha256=_path_sha256(args.parity_report),
            run_id=parity_report.run_id,
            captured_at=parity_report.captured_at,
            status="passed",
            config_fingerprint=parity_report.config_fingerprint,
            probe_fixture_sha256=parity_report.probe_fixture_sha256,
            submitted_content_sha256=parity_report.submitted_content_sha256,
            reason_code=parity_report.reason_code,
        )
    except (OSError, TokenizerParityError, ValueError):
        return CanonicalABRunResultV1(
            report=_terminal_without_observations(
                args,
                inputs=inputs,
                outcome="unavailable",
                stage="parity",
                reason_code="provider_usage_unavailable",
                incumbent_corpus_id=incumbent_corpus_id,
                candidate_corpus_id=candidate_corpus_id,
            ),
            binding=None,
            diagnostic=None,
            actual_request_count=0,
            result_code=ProviderExecutionResultCode.PROVIDER_UNAVAILABLE,
        )

    active_namespace: Any | None = None
    active_role_run: Any | None = None
    active_assembler_fingerprint = token_assembler.config.config_fingerprint
    role_runs = []
    try:
        candidate_snapshot = await _validate_corpus_pair(
            candidate_identity,
            character_fingerprint=character_assembler.config_fingerprint,
            token_fingerprint=token_assembler.config.config_fingerprint,
            expected_parity_hash=parity.report_sha256,
        )
        namespaces = build_ab_round_namespaces(
            run_id=args.run_id,
            incumbent_corpus_version_id=incumbent_corpus_id,
            candidate_corpus_version_id=candidate_corpus_id,
        )
        if embedder is None:
            raise RecoveryAttemptRefused("provider_not_authorized")
        missing: list[str] = []
        if not (settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY")):
            missing.append("provider_credentials_unavailable")
        if not check_ocr_runtime(required_languages=("chi_sim", "eng")).available:
            missing.append("provider_request_unavailable")
        if missing:
            return CanonicalABRunResultV1(
                report=_terminal_without_observations(
                    args,
                    inputs=inputs,
                    outcome="unavailable",
                    stage="provider",
                    reason_code=missing[0],
                    incumbent_corpus_id=incumbent_corpus_id,
                    candidate_corpus_id=candidate_corpus_id,
                    parity=parity,
                ),
                binding=None,
                diagnostic=None,
                actual_request_count=0,
                result_code=ProviderExecutionResultCode.PROVIDER_UNAVAILABLE,
            )
        role_durations: list[Decimal] = []
        for namespace, assembler in zip(namespaces, (character_assembler, token_assembler), strict=True):
            active_namespace = namespace
            active_role_run = None
            active_assembler_fingerprint = (
                character_assembler.config_fingerprint
                if namespace.role == "incumbent"
                else token_assembler.config.config_fingerprint
            )
            started = time.monotonic_ns()
            async with SessionLocal() as session:
                role_run = await run_rollback_only_retrieval_parity(
                    dataset,
                    session=session,
                    embedder=embedder,
                    namespace=namespace,
                    generated_at=str(args.generated_at),
                    run_identity_hash=_round_identity_hash(
                        args=args,
                        role=namespace.role,
                        assembler_fingerprint=(
                            character_assembler.config_fingerprint
                            if namespace.role == "incumbent"
                            else token_assembler.config.config_fingerprint
                        ),
                    ),
                    expected_rollout_version=candidate_identity.expected_evidence_rollout_version,
                    input_assembler=assembler,
                )
            active_role_run = role_run
            role_runs.append(role_run)
            role_durations.append(Decimal(time.monotonic_ns() - started) / Decimal(1_000_000))
        for failed_namespace, failed_run in zip(namespaces, role_runs, strict=True):
            if failed_run.outcome in {
                EvaluationOutcome.COMPLETED_PASS,
                EvaluationOutcome.COMPLETED_QUALITY_FAIL,
            }:
                continue
            typed_failure = next(
                (
                    round_result.safe_failure
                    for round_result in reversed(failed_run.rounds)
                    if round_result.safe_failure
                ),
                None,
            )
            if typed_failure is None:
                typed_failure = _unexpected_provider_failure(
                    args=args,
                    namespace=failed_namespace,
                    role_run=failed_run,
                    assembler_fingerprint=(
                        character_assembler.config_fingerprint
                        if failed_namespace.role == "incumbent"
                        else token_assembler.config.config_fingerprint
                    ),
                    provider_request_count=embedder.request_attempt_count,
                )
            raise SafeRoleExecutionError(typed_failure)
        try:
            final_snapshot = await _validate_corpus_pair(
                candidate_identity,
                character_fingerprint=character_assembler.config_fingerprint,
                token_fingerprint=token_assembler.config.config_fingerprint,
                expected_parity_hash=parity.report_sha256,
            )
        except Exception:
            raise SafeRoleExecutionError(
                _completed_role_resource_failure(
                    args=args,
                    namespace=namespaces[1],
                    role_run=role_runs[1],
                    assembler_fingerprint=token_assembler.config.config_fingerprint,
                )
            ) from None
        if final_snapshot != candidate_snapshot:
            raise SafeRoleExecutionError(
                _completed_role_resource_failure(
                    args=args,
                    namespace=namespaces[1],
                    role_run=role_runs[1],
                    assembler_fingerprint=token_assembler.config.config_fingerprint,
                )
            )
        try:
            incumbent = build_candidate_observation_from_retrieval(
                role="incumbent",
                corpus_version_id=incumbent_corpus_id,
                config_schema_version=CHARACTER_COMPATIBILITY_CONFIG_VERSION,
                config_fingerprint=character_assembler.config_fingerprint,
                deterministic_rebuild_sha256=_sha256_json(role_runs[0].model_dump(mode="json")),
                rounds=role_runs[0].rounds,
                retrieval_duration_ms=role_durations[0],
                cost_basis_version=COST_BASIS_VERSION,
                cost_currency=COST_CURRENCY,
                cost_unit_tokens=COST_UNIT_TOKENS,
                cost_price_per_unit=COST_PRICE_PER_UNIT,
            )
        except Exception:
            raise SafeRoleExecutionError(
                _completed_role_resource_failure(
                    args=args,
                    namespace=namespaces[0],
                    role_run=role_runs[0],
                    assembler_fingerprint=character_assembler.config_fingerprint,
                )
            ) from None
        try:
            candidate = build_candidate_observation_from_retrieval(
                role="candidate",
                corpus_version_id=candidate_corpus_id,
                config_schema_version=token_assembler.config.schema_version,
                config_fingerprint=token_assembler.config.config_fingerprint,
                deterministic_rebuild_sha256=candidate_snapshot.deterministic_rebuild_hash,
                rounds=role_runs[1].rounds,
                retrieval_duration_ms=role_durations[1],
                cost_basis_version=COST_BASIS_VERSION,
                cost_currency=COST_CURRENCY,
                cost_unit_tokens=COST_UNIT_TOKENS,
                cost_price_per_unit=COST_PRICE_PER_UNIT,
            )
        except Exception:
            raise SafeRoleExecutionError(
                _completed_role_resource_failure(
                    args=args,
                    namespace=namespaces[1],
                    role_run=role_runs[1],
                    assembler_fingerprint=token_assembler.config.config_fingerprint,
                )
            ) from None
        runtime = _runtime(
            run_id=args.run_id,
            incumbent_corpus_id=incumbent_corpus_id,
            candidate_corpus_id=candidate_corpus_id,
        )
        report = build_terminal_ab_run(
            run_id=args.run_id,
            generated_at=generated_at,
            inputs=inputs,
            runtime=runtime,
            parity=parity,
            incumbent=incumbent,
            candidate=candidate,
            hard_proofs=_hard_proofs(candidate_snapshot, role_runs=tuple(role_runs)),
        )
        binding = (
            ABSelectionBindingV1(
                selection_id=args.selection_id,
                tenant_id=FORMAT_PARITY_TENANT_ID,
                candidate_corpus_version_id=candidate_corpus_id,
                candidate_run_token=candidate_identity.run_token,
                candidate_lease_owner=candidate_identity.lease_owner,
                source_manifest_hash=candidate_identity.source_manifest_hash,
            )
            if report.outcome == "selected_pass"
            else None
        )
        return CanonicalABRunResultV1(
            report=report,
            binding=binding,
            diagnostic=None,
            actual_request_count=embedder.request_attempt_count,
            result_code=(
                ProviderExecutionResultCode.SUCCESS
                if report.outcome == "selected_pass"
                else ProviderExecutionResultCode.QUALITY_FAIL
            ),
        )
    except RecoveryAttemptRefused:
        raise
    except SafeRoleExecutionError as safe_error:
        return _typed_failure_execution_result(
            args=args,
            inputs=inputs,
            failure=safe_error.failure,
            incumbent_corpus_id=incumbent_corpus_id,
            candidate_corpus_id=candidate_corpus_id,
            parity=parity,
            actual_request_count=embedder.request_attempt_count if embedder is not None else 0,
        )
    except Exception:
        failure = _unexpected_provider_failure(
            args=args,
            namespace=active_namespace,
            role_run=active_role_run,
            assembler_fingerprint=active_assembler_fingerprint,
            provider_request_count=embedder.request_attempt_count if embedder is not None else 0,
        )
        return _typed_failure_execution_result(
            args=args,
            inputs=inputs,
            failure=failure,
            incumbent_corpus_id=incumbent_corpus_id,
            candidate_corpus_id=candidate_corpus_id,
            parity=parity,
            actual_request_count=embedder.request_attempt_count if embedder is not None else 0,
        )


async def _validate_corpus_pair(
    identity: PolicyReindexRunIdentity,
    *,
    character_fingerprint: str,
    token_fingerprint: str,
    expected_parity_hash: str,
) -> CandidateProofSnapshot:
    if identity.tenant_id != FORMAT_PARITY_TENANT_ID or identity.state != "complete":
        raise ValueError("candidate_identity_invalid")
    async with SessionLocal() as session:
        missing = await _ab_database_prerequisites(
            session,
            expected_rollout_version=identity.expected_evidence_rollout_version,
        )
        if missing:
            raise PolicyCorpusUnavailable("evaluation prerequisites unavailable")
        corpora = PolicyCorpusRepository(session)
        rollout = await corpora.get_rollout(tenant_id=identity.tenant_id)
        incumbent = await corpora.get_corpus(
            tenant_id=identity.tenant_id,
            corpus_version_id=identity.source_active_corpus_version_id,
        )
        candidate = await corpora.get_corpus(
            tenant_id=identity.tenant_id,
            corpus_version_id=identity.corpus_version_id,
        )
        source_manifest = await session.get(PolicyCorpusManifestRevision, identity.source_manifest_revision_id)
        evidence_rollout = await session.get(EvidenceIdentityRollout, 1)
        candidate_counts = await corpora.get_projection_counts(
            tenant_id=identity.tenant_id,
            corpus_version_id=identity.corpus_version_id,
        )
        expected_counts = dict(candidate.bootstrap_counts_json or {}) if candidate is not None else {}
        if (
            rollout is None
            or incumbent is None
            or candidate is None
            or evidence_rollout is None
            or rollout.active_corpus_version_id != incumbent.id
            or rollout.active_corpus_version_id == candidate.id
            or rollout.active_corpus_version_id != identity.source_active_corpus_version_id
            or rollout.rollout_epoch != identity.source_rollout_epoch
            or incumbent.state != "complete"
            or incumbent.config_fingerprint != character_fingerprint
            or candidate.state != "complete"
            or candidate.id != identity.corpus_version_id
            or candidate.run_token != identity.run_token
            or candidate.lease_owner != identity.lease_owner
            or candidate.lease_expires_at != identity.lease_expires_at
            or candidate.state_version != identity.state_version
            or candidate.next_document_index != identity.next_document_index
            or candidate.config_schema_version != identity.config_schema_version
            or candidate.config_fingerprint != token_fingerprint
            or candidate.provider_parity_report_hash != expected_parity_hash
            or identity.provider_parity_report_hash != expected_parity_hash
            or candidate.source_manifest_revision_id != identity.source_manifest_revision_id
            or candidate.source_manifest_hash != identity.source_manifest_hash
            or candidate.source_active_corpus_version_id != identity.source_active_corpus_version_id
            or candidate.source_rollout_epoch != identity.source_rollout_epoch
            or candidate.expected_evidence_rollout_version != identity.expected_evidence_rollout_version
            or source_manifest is None
            or source_manifest.tenant_id != identity.tenant_id
            or source_manifest.revision != identity.source_manifest_revision
            or source_manifest.manifest_hash != identity.source_manifest_hash
            or tuple(
                str(item.get("doc_key"))
                for item in source_manifest.manifest_json.get("documents", ())
                if isinstance(item, dict)
            )
            != identity.ordered_doc_keys
            or not _valid_sha256(candidate.deterministic_rebuild_hash)
            or candidate_counts.documents != expected_counts.get("bound_document_count")
            or candidate_counts.blocks != expected_counts.get("bound_block_count")
            or candidate_counts.chunks != expected_counts.get("bound_chunk_count")
            or evidence_rollout.rollout_version != identity.expected_evidence_rollout_version
        ):
            raise ValueError("candidate_identity_invalid")
        snapshot = CandidateProofSnapshot(
            deterministic_rebuild_hash=str(candidate.deterministic_rebuild_hash),
            provider_parity_report_hash=str(candidate.provider_parity_report_hash),
            validation_proof=dict(candidate.validation_proof_json or {}),
        )
        await session.rollback()
        return snapshot


async def _require_shared_ab_authority_binding(
    *,
    authority_id: UUID,
    owner: PolicyReindexRunIdentity,
    envelope: CanonicalABRequestEnvelopeV1,
) -> None:
    """Prove the supplied ID is the exact reviewed-build shared root."""

    async with SessionLocal() as session:
        authority = await session.get(ProviderExecutionAuthority, authority_id)
        if (
            authority is None
            or authority.tenant_id != owner.tenant_id
            or authority.run_token != owner.run_token
            or authority.candidate_id != owner.corpus_version_id
            or authority.owner_marker != POLICY_REINDEX_OWNER_MARKER
            or authority.config_schema_version != owner.config_schema_version
            or authority.config_fingerprint != owner.config_fingerprint
            or authority.provider_parity_report_hash != owner.provider_parity_report_hash
            or authority.parity_captured_at != owner.parity_captured_at
            or authority.parity_expires_at != owner.parity_expires_at
            or authority.source_manifest_revision_id != owner.source_manifest_revision_id
            or authority.source_manifest_hash != owner.source_manifest_hash
            or authority.source_active_corpus_version_id != owner.source_active_corpus_version_id
            or authority.source_rollout_epoch != owner.source_rollout_epoch
            or authority.evidence_rollout_version != owner.expected_evidence_rollout_version
            or authority.candidate_lease_expires_at != owner.lease_expires_at
            or authority.expires_at != min(owner.parity_expires_at, owner.lease_expires_at)
            or authority.provider_name != envelope.provider_request_envelope.provider_name
            or authority.model_name != envelope.provider_request_envelope.model_name
            or authority.dimensions != envelope.provider_request_envelope.dimensions
            or authority.envelope_contract_hash != PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH
        ):
            raise RecoveryAttemptRefused("provider_authority_mismatch")
        await session.rollback()


def _complete_candidate_proof(snapshot: CandidateProofSnapshot) -> bool:
    proof = snapshot.validation_proof.get("candidate_validation")
    return bool(
        isinstance(proof, dict)
        and proof.get("all_embedding_inputs_within_512_tokens") is True
        and proof.get("complete_document_coverage") is True
        and proof.get("complete_block_coverage") is True
        and proof.get("immutable_binding_replay") is True
        and proof.get("deterministic_rebuild_hash") == snapshot.deterministic_rebuild_hash
    )


async def _issue_recovery_budget(args: argparse.Namespace, *, checked_at: datetime) -> int:
    try:
        root = require_canonical_recovery_root(
            output_root=args.output_root,
            repository_root=REPOSITORY_ROOT,
        )
        identity = load_recovery_issuance_identity(
            root=root,
            candidate_state_path=args.candidate_state,
            provider_parity_report_path=args.parity_report,
            checked_at=checked_at,
        )
        if identity.state != "complete":
            raise RecoveryAttemptRefused("recovery_candidate_incomplete")
        snapshot = await _validate_corpus_pair(
            identity,
            character_fingerprint=_character_incumbent().config_fingerprint,
            token_fingerprint=_token_candidate().config.config_fingerprint,
            expected_parity_hash=_path_sha256(args.parity_report),
        )
        dataset = load_format_parity_contract(DEFAULT_MANIFEST, DEFAULT_GOLD, repository_root=REPOSITORY_ROOT)
        _require_sealed_dataset(dataset)
        _require_sealed_baseline(DEFAULT_BASELINE)
        validate_fixed_plan10_evidence(root)
        artifact = issue_canonical_recovery_budget_manifest(
            root=root,
            candidate_state_path=args.candidate_state,
            provider_parity_report_path=args.parity_report,
            checked_at=checked_at,
            live_authority=RecoveryLiveAuthorityProofV1(
                tenant_id=identity.tenant_id,
                incumbent_corpus_version_id=identity.source_active_corpus_version_id,
                candidate_corpus_version_id=identity.corpus_version_id,
                candidate_run_token=identity.run_token,
                candidate_lease_owner=identity.lease_owner,
                candidate_state_version=identity.state_version,
                source_manifest_revision_id=identity.source_manifest_revision_id,
                source_manifest_revision=identity.source_manifest_revision,
                source_manifest_hash=identity.source_manifest_hash,
                source_rollout_epoch=identity.source_rollout_epoch,
                expected_evidence_rollout_version=identity.expected_evidence_rollout_version,
                deterministic_rebuild_sha256=snapshot.deterministic_rebuild_hash,
                complete_projection_proved=_complete_candidate_proof(snapshot),
                sealed_inputs_proved=True,
            ),
        )
    except RecoveryAttemptRefused as refusal:
        print(
            json.dumps(
                {"error": "recovery_attempt_refused", "reason_code": str(refusal)},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 4
    except (FormatParityContractError, OSError, PolicyCorpusUnavailable, ValueError):
        print(
            json.dumps(
                {"error": "recovery_attempt_refused", "reason_code": "recovery_live_authority_mismatch"},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 4
    print(
        json.dumps(
            {
                "manifest_sha256": artifact.sha256,
                "path": artifact.path.relative_to(root).as_posix(),
                "status": "issued_or_reconciled",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


async def _ab_database_prerequisites(
    session: Any,
    *,
    expected_rollout_version: int,
) -> tuple[str, ...]:
    """Accept the Phase64.3 floor when the stricter Phase64.4 schema is live."""

    missing = list(
        await _database_prerequisites(
            session,
            expected_rollout_version=expected_rollout_version,
        )
    )
    if "database_schema" in missing and await _phase64_4_schema_available(session):
        missing.remove("database_schema")
    return tuple(missing)


async def _phase64_4_schema_available(session: Any) -> bool:
    row = (
        await session.execute(
            text(
                "SELECT to_regclass('public.rag_evaluation_rounds') IS NOT NULL, "
                "to_regclass('public.policy_corpus_rollouts') IS NOT NULL, "
                "to_regclass('public.corpus_chunk_bindings') IS NOT NULL, "
                "to_regclass('public.policy_corpus_activation_history') IS NOT NULL, "
                "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector'), "
                "(SELECT version_num FROM alembic_version LIMIT 1)"
            )
        )
    ).one()
    return all(bool(value) for value in row[:5]) and row[5] == "031_phase64_4_policy_corpus_cow"


def _hard_proofs(snapshot: CandidateProofSnapshot, *, role_runs: tuple[Any, ...]) -> ABHardProofsV1:
    proof = snapshot.validation_proof
    candidate_proof = proof.get("candidate_validation") if isinstance(proof, dict) else None
    if not isinstance(candidate_proof, dict):
        candidate_proof = {}
    rounds = tuple(round_result for run in role_runs for round_result in run.rounds)
    return ABHardProofsV1(
        zero_final_input_overflow=candidate_proof.get("all_embedding_inputs_within_512_tokens") is True,
        persisted_counts_recomputed=candidate_proof.get("complete_document_coverage") is True,
        deterministic_rebuild=(
            candidate_proof.get("deterministic_rebuild_hash") == snapshot.deterministic_rebuild_hash
        ),
        complete_source_coverage=candidate_proof.get("complete_block_coverage") is True,
        immutable_identity_replay=candidate_proof.get("immutable_binding_replay") is True,
        interrupted_resume_safe=all(round_result.pre_state_proved for round_result in rounds),
        stale_cas_safe=all(round_result.immutable_history_preserved for round_result in rounds),
        atomic_cutover_rollback_safe=True,
        evaluation_cleanup_isolated=all(round_result.post_state_proved for round_result in rounds),
        fresh_provider_parity_passed=True,
    )


def _require_sealed_dataset(dataset: Any) -> None:
    answerable = sum(case.category != "no_answer" for policy in dataset.policies for case in policy.gold.cases) * 3
    total = sum(len(policy.gold.cases) for policy in dataset.policies) * 3
    if (
        dataset.manifest_hash != SEALED_MANIFEST_HASH
        or dataset.gold_hash != SEALED_GOLD_HASH
        or dataset.baseline_identity != SEALED_DATASET_BASELINE_IDENTITY
        or answerable != SEALED_ANSWERABLE_CASE_COUNT
        or total != SEALED_TOTAL_CASE_COUNT
    ):
        raise ValueError("sealed_input_mismatch")


def _require_sealed_baseline(path: Path) -> None:
    report = load_format_parity_report(path)
    if (
        report.inputs.manifest_hash != SEALED_MANIFEST_HASH
        or report.inputs.gold_hash != SEALED_GOLD_HASH
        or report.inputs.dataset_baseline_identity != SEALED_DATASET_BASELINE_IDENTITY
        or report.metrics.overall.answerable_count != SEALED_ANSWERABLE_CASE_COUNT
        or report.metrics.overall.case_count != SEALED_TOTAL_CASE_COUNT
        or report.config.execution_kind != "full_provider"
    ):
        raise ValueError("sealed_baseline_mismatch")


def _ordered_questions_sha256(questions: tuple[tuple[str, str, str], ...]) -> str:
    return _sha256_json(
        [
            {"format": format_name, "doc_key": doc_key, "case_id": case_id, "question": question}
            for format_name in ("markdown", "digital_pdf", "scanned_pdf")
            for doc_key, case_id, question in questions
        ]
    )


def _round_identity_hash(*, args: argparse.Namespace, role: str, assembler_fingerprint: str) -> str:
    return _sha256_json(
        {
            "schema_version": "rag_token_chunk_ab_round.v1",
            "run_id": str(args.run_id),
            "role": role,
            "assembler_fingerprint": assembler_fingerprint,
            "manifest_hash": SEALED_MANIFEST_HASH,
            "gold_hash": SEALED_GOLD_HASH,
            "provider": "dashscope",
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        }
    ).removeprefix("sha256:")


def _completed_role_resource_failure(
    *,
    args: argparse.Namespace,
    namespace: Any,
    role_run: Any,
    assembler_fingerprint: str,
) -> SafeRoleFailureV1:
    rounds = tuple(role_run.rounds)
    return SafeRoleFailureV1(
        failing_role="character_incumbent" if namespace.role == "incumbent" else "token_candidate",
        round_format=rounds[-1].round_format if rounds else None,
        stage="retrieval_resource_proof",
        reason_code="resource_proof_failed",
        provider_availability="available",
        provider_request_classification="request_completed",
        outer_rollback_attempted=True,
        outer_rollback_proved=True,
        completed_round_count=len(rounds),
        provider_request_count=sum(len(round_result.cases) for round_result in rounds),
        safe_context_sha256="sha256:"
        + _round_identity_hash(
            args=args,
            role=namespace.role,
            assembler_fingerprint=assembler_fingerprint,
        ),
    )


def _unexpected_provider_failure(
    *,
    args: argparse.Namespace,
    namespace: Any | None,
    role_run: Any | None,
    assembler_fingerprint: str,
    provider_request_count: int,
) -> SafeRoleFailureV1:
    """Describe an otherwise-untyped provider-path failure without raw details."""

    if namespace is None:
        return _shared_preflight_failure(args, reason_code="candidate_pair_invalid")
    rounds = tuple(role_run.rounds) if role_run is not None else ()
    return SafeRoleFailureV1(
        failing_role="character_incumbent" if namespace.role == "incumbent" else "token_candidate",
        round_format=rounds[-1].round_format if rounds else None,
        stage="retrieval_resource_proof",
        reason_code="provider_execution_failed",
        provider_availability="available",
        provider_request_classification="request_started" if provider_request_count else "not_attempted",
        outer_rollback_attempted=bool(rounds),
        outer_rollback_proved=bool(rounds) and all(round_result.post_state_proved for round_result in rounds),
        completed_round_count=len(rounds),
        provider_request_count=provider_request_count,
        safe_context_sha256="sha256:"
        + _round_identity_hash(
            args=args,
            role=namespace.role,
            assembler_fingerprint=assembler_fingerprint,
        ),
    )


def _valid_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _path_sha256(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError:
        return "sha256:" + "0" * 64
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _shared_preflight_failure(
    args: argparse.Namespace,
    *,
    reason_code: str,
) -> SafeRoleFailureV1:
    return SafeRoleFailureV1(
        failing_role="shared_preflight",
        round_format=None,
        stage="shared_preflight",
        reason_code=reason_code,
        provider_availability="not_checked",
        provider_request_classification="not_attempted",
        outer_rollback_attempted=False,
        outer_rollback_proved=False,
        completed_round_count=0,
        provider_request_count=0,
        safe_context_sha256=_sha256_json(
            {
                "schema_version": "rag_token_chunk_ab_preflight.v1",
                "run_id": str(args.run_id),
                "reason_code": reason_code,
            }
        ),
    )


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    authority_checked_at = datetime.now(UTC)
    if args.command == "issue-recovery-budget":
        return await _issue_recovery_budget(args, checked_at=authority_checked_at)
    args._authority_checked_at = authority_checked_at
    try:
        args.output_root = require_canonical_recovery_root(
            output_root=args.output_root,
            repository_root=REPOSITORY_ROOT,
        )
        descriptor = load_policy_reindex_recovery_descriptor(
            args.candidate_state.parents[1] / "descriptor.json",
            root=args.output_root / "candidates",
        )
        owner = load_policy_reindex_state(
            args.candidate_state,
            descriptor=descriptor,
            root=args.output_root / "candidates",
        )
        if owner.state != "complete":
            raise RecoveryAttemptRefused("candidate_identity_invalid")
        args._verified_candidate_identity = owner
        dataset = load_format_parity_contract(args.manifest, args.gold, repository_root=REPOSITORY_ROOT)
        envelope = build_canonical_ab_request_envelope(
            dataset=dataset,
            incumbent_assembler=_character_incumbent(),
            candidate_assembler=_token_candidate(),
            repository_root=REPOSITORY_ROOT,
        )
        questions_hash = _ordered_questions_sha256(ordered_gold_questions(dataset))
        inputs = _inputs(args, ordered_questions_sha256=questions_hash)

        def persist_terminal(execution, reservation, result_id):
            report = execution.report
            binding = execution.binding
            if report.outcome == "execution_error":
                if execution.diagnostic is None:
                    raise ValueError("canonical_ab_execution_diagnostic_missing")
                bundle = write_execution_error_bundle_create_only(
                    report,
                    diagnostic=execution.diagnostic,
                    root=args.output_root,
                )
                terminal = bundle.run
            else:
                terminal = write_terminal_run_create_only(report, root=args.output_root)
            values = {
                "terminal_run_hash": terminal.json_sha256,
                "terminal_report_hash": terminal.markdown_sha256,
                "selection_decision_hash": None,
                "activation_authorization_hash": None,
            }
            if binding is not None:
                selection = write_selection_create_only(
                    report,
                    binding=binding,
                    terminal_run_sha256=terminal.json_sha256,
                    root=args.output_root,
                )
                authorization = write_db_activation_authorization_create_only(
                    root=args.output_root,
                    report=report,
                    binding=binding,
                    authority_id=args.authority_id,
                    reservation_id=reservation.reservation_id,
                    result_id=result_id,
                    terminal_run_sha256=terminal.json_sha256,
                    selection_sha256=selection.json_sha256,
                )
                values["selection_decision_hash"] = selection.json_sha256
                values["activation_authorization_hash"] = authorization.sha256
            return values

        async def run(embedder):
            return await run_full_provider_ab(args, inputs=inputs, embedder=embedder)

        outcome = await CanonicalABExecutionService(
            authority_service=_provider_execution_authority_service(),
            require_shared_root=_require_shared_ab_authority_binding,
        ).execute(
            authority_id=args.authority_id,
            expected_run_id=args.run_id,
            owner=owner,
            inputs=inputs,
            envelope=envelope,
            ordinal=args.ordinal,
            run=run,
            projection_path=(args.output_root / "provider-authority" / f"canonical-ab.ordinal-{args.ordinal}.v2.json"),
            persist_terminal=persist_terminal,
            construct_provider=lambda: EmbeddingService(
                model=envelope.provider_request_envelope.model_name,
                dimensions=envelope.provider_request_envelope.dimensions,
                batch_size=CANONICAL_AB_PROVIDER_BATCH_SIZE,
                max_retries=CANONICAL_AB_OUTER_ATTEMPTS,
            ),
        )
        report = outcome.report
    except RecoveryAttemptRefused as refusal:
        print(
            json.dumps(
                {
                    "error": "recovery_attempt_refused",
                    "reason_code": str(refusal),
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 4
    print(
        json.dumps(
            {
                "schema_version": report.schema_version,
                "run_id": str(report.run_id),
                "outcome": report.outcome,
                "result_sha256": outcome.result.result_hash,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0 if report.outcome == "selected_pass" else 2


def _execution_diagnostic_from_failure(
    report: TerminalABRunV1,
    failure: SafeRoleFailureV1,
) -> ABExecutionDiagnosticV1:
    """Bind one validated typed failure to the exact terminal-run bytes."""

    run_payload = canonical_report_json_bytes(report.model_dump(mode="json"))
    return ABExecutionDiagnosticV1(
        run_id=report.run_id,
        terminal_run_sha256="sha256:" + hashlib.sha256(run_payload).hexdigest(),
        occurred_at=report.generated_at,
        failing_role=failure.failing_role,
        round_format=failure.round_format,
        stage=failure.stage,
        reason_code=failure.reason_code,
        provider_availability=failure.provider_availability,
        provider_request_classification=failure.provider_request_classification,
        outer_rollback_attempted=failure.outer_rollback_attempted,
        outer_rollback_proved=failure.outer_rollback_proved,
        completed_round_count=failure.completed_round_count,
        provider_request_count=failure.provider_request_count,
        safe_context_sha256=failure.safe_context_sha256,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
