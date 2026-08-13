from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError


RUN_ID = UUID("64300000-0000-4000-8000-000000000009")
SELECTION_ID = UUID("64300000-0000-4000-8000-000000000010")
TENANT_ID = UUID("64300000-0000-4000-8000-000000000001")
INCUMBENT_CORPUS_ID = UUID("64300000-0000-4000-8000-000000000011")
CANDIDATE_CORPUS_ID = UUID("64300000-0000-4000-8000-000000000012")
GENERATED_AT = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)


def _api():
    from src.rag.evaluation.token_chunk_ab import (
        SEALED_DATASET_BASELINE_IDENTITY,
        SEALED_GOLD_HASH,
        SEALED_MANIFEST_HASH,
        ABCandidateObservationV1,
        ABEmbeddingCostV1,
        ABExecutionBundleManifestV1,
        ABExecutionDiagnosticV1,
        ABFormatMetricsV1,
        ABHardProofsV1,
        ABInputIdentityV1,
        ABNamespaceV1,
        ABParityEvidenceV1,
        ABQualityMetricsV1,
        ABResourceMetricsV1,
        ABRecoveryBudgetManifestV1,
        ABRecoveryAttemptReservationV1,
        ABRecoveryAuthorizationV1,
        ABRuntimeConfigV1,
        ABSelectionBindingV1,
        ExactRatioV1,
        PLAN10_TERMINAL_RUNS,
        PLAN12_RECOVERY_BUDGET_ID,
        RecoveryLiveAuthorityProofV1,
        RecoveryAttemptRefused,
        TerminalABRunV1,
        build_plan12_recovery_budget_manifest,
        build_terminal_ab_run,
        canonical_recovery_root,
        evaluate_exact_gates,
        evaluate_recovery_retry_authority,
        issue_canonical_recovery_budget_manifest,
        load_execution_error_bundle,
        load_recovery_attempt_reservation,
        load_recovery_authorization,
        load_recovery_budget_manifest,
        load_selection_decision,
        load_terminal_ab_run,
        reserve_recovery_attempt,
        reserve_then_create_provider,
        require_canonical_recovery_root,
        render_selection_markdown,
        render_terminal_markdown,
        validate_fixed_plan10_evidence,
        write_recovery_budget_manifest_create_only,
        write_recovery_authorization_create_only,
        write_selection_create_only,
        write_execution_error_bundle_create_only,
        write_terminal_run_create_only,
    )

    return {
        "SEALED_DATASET_BASELINE_IDENTITY": SEALED_DATASET_BASELINE_IDENTITY,
        "SEALED_GOLD_HASH": SEALED_GOLD_HASH,
        "SEALED_MANIFEST_HASH": SEALED_MANIFEST_HASH,
        "ABCandidateObservationV1": ABCandidateObservationV1,
        "ABEmbeddingCostV1": ABEmbeddingCostV1,
        "ABExecutionBundleManifestV1": ABExecutionBundleManifestV1,
        "ABExecutionDiagnosticV1": ABExecutionDiagnosticV1,
        "ABFormatMetricsV1": ABFormatMetricsV1,
        "ABHardProofsV1": ABHardProofsV1,
        "ABInputIdentityV1": ABInputIdentityV1,
        "ABNamespaceV1": ABNamespaceV1,
        "ABParityEvidenceV1": ABParityEvidenceV1,
        "ABQualityMetricsV1": ABQualityMetricsV1,
        "ABResourceMetricsV1": ABResourceMetricsV1,
        "ABRecoveryBudgetManifestV1": ABRecoveryBudgetManifestV1,
        "ABRecoveryAttemptReservationV1": ABRecoveryAttemptReservationV1,
        "ABRecoveryAuthorizationV1": ABRecoveryAuthorizationV1,
        "ABRuntimeConfigV1": ABRuntimeConfigV1,
        "ABSelectionBindingV1": ABSelectionBindingV1,
        "ExactRatioV1": ExactRatioV1,
        "PLAN10_TERMINAL_RUNS": PLAN10_TERMINAL_RUNS,
        "PLAN12_RECOVERY_BUDGET_ID": PLAN12_RECOVERY_BUDGET_ID,
        "RecoveryLiveAuthorityProofV1": RecoveryLiveAuthorityProofV1,
        "RecoveryAttemptRefused": RecoveryAttemptRefused,
        "TerminalABRunV1": TerminalABRunV1,
        "build_plan12_recovery_budget_manifest": build_plan12_recovery_budget_manifest,
        "build_terminal_ab_run": build_terminal_ab_run,
        "canonical_recovery_root": canonical_recovery_root,
        "evaluate_exact_gates": evaluate_exact_gates,
        "evaluate_recovery_retry_authority": evaluate_recovery_retry_authority,
        "issue_canonical_recovery_budget_manifest": issue_canonical_recovery_budget_manifest,
        "load_execution_error_bundle": load_execution_error_bundle,
        "load_recovery_attempt_reservation": load_recovery_attempt_reservation,
        "load_recovery_authorization": load_recovery_authorization,
        "load_recovery_budget_manifest": load_recovery_budget_manifest,
        "load_selection_decision": load_selection_decision,
        "load_terminal_ab_run": load_terminal_ab_run,
        "reserve_recovery_attempt": reserve_recovery_attempt,
        "reserve_then_create_provider": reserve_then_create_provider,
        "require_canonical_recovery_root": require_canonical_recovery_root,
        "render_selection_markdown": render_selection_markdown,
        "render_terminal_markdown": render_terminal_markdown,
        "validate_fixed_plan10_evidence": validate_fixed_plan10_evidence,
        "write_recovery_budget_manifest_create_only": write_recovery_budget_manifest_create_only,
        "write_recovery_authorization_create_only": write_recovery_authorization_create_only,
        "write_selection_create_only": write_selection_create_only,
        "write_execution_error_bundle_create_only": write_execution_error_bundle_create_only,
        "write_terminal_run_create_only": write_terminal_run_create_only,
    }


def _ratio(numerator: int, denominator: int):
    return _api()["ExactRatioV1"](numerator=numerator, denominator=denominator)


def _format_metrics(*, hit_1: int = 14, hit_3: int = 15, hit_5: int = 15):
    cls = _api()["ABFormatMetricsV1"]
    return tuple(
        cls(
            format=name,
            hit_at_1=_ratio(hit_1, 15),
            hit_at_3=_ratio(hit_3, 15),
            hit_at_5=_ratio(hit_5, 15),
            mrr=_ratio(29, 30),
        )
        for name in ("markdown", "digital_pdf", "scanned_pdf")
    )


def _quality(
    *,
    hit_1: tuple[int, int] = (42, 45),
    hit_3: tuple[int, int] = (45, 45),
    hit_5: tuple[int, int] = (45, 45),
    mrr: tuple[int, int] = (44, 45),
    anchor: tuple[int, int] = (53, 54),
    locator: tuple[int, int] = (53, 54),
    fallback: tuple[int, int] = (53, 54),
    by_format=None,
):
    cls = _api()["ABQualityMetricsV1"]
    return cls(
        answerable_case_count=45,
        total_case_count=54,
        hit_at_1=_ratio(*hit_1),
        hit_at_3=_ratio(*hit_3),
        hit_at_5=_ratio(*hit_5),
        mrr=_ratio(*mrr),
        semantic_anchor_coverage=_ratio(*anchor),
        locator_coverage=_ratio(*locator),
        fallback_correctness=_ratio(*fallback),
        by_format=by_format or _format_metrics(),
    )


def _resources(
    *,
    chunk_count: int = 100,
    duplicate_count: int = 1,
    offline_tokens: int = 10_000,
    provider_tokens: int | None = 10_000,
):
    api = _api()
    return api["ABResourceMetricsV1"](
        chunk_count=chunk_count,
        duplicate_count=duplicate_count,
        offline_embedding_tokens=offline_tokens,
        provider_embedding_tokens=provider_tokens,
        provider_tokens_status="provider_reported" if provider_tokens is not None else "unavailable",
        retrieval_duration_ms=Decimal("125.125"),
        embedding_cost=api["ABEmbeddingCostV1"](
            basis_version="dashscope_text_embedding_v4_cost.v1",
            currency="CNY",
            unit_tokens=1_000,
            price_per_unit=Decimal("0.0007"),
            estimated_cost=Decimal(offline_tokens) * Decimal("0.0007") / Decimal(1_000),
            observed_cost=None,
            observed_cost_status="unavailable",
        ),
    )


def _observation(
    *,
    candidate: bool,
    quality=None,
    resources=None,
):
    cls = _api()["ABCandidateObservationV1"]
    return cls(
        role="candidate" if candidate else "incumbent",
        assembler="PolicyEmbeddingInputAssembler" if candidate else "CharacterCompatibilityAssembler",
        config_schema_version="embedding_tokenizer.v1" if candidate else "character_compatibility.v1",
        config_fingerprint=("sha256:" + ("c" if candidate else "b") * 64),
        corpus_version_id=CANDIDATE_CORPUS_ID if candidate else INCUMBENT_CORPUS_ID,
        deterministic_rebuild_sha256="sha256:" + ("d" if candidate else "a") * 64,
        quality=quality or _quality(),
        resources=resources or _resources(),
    )


def _inputs():
    api = _api()
    return api["ABInputIdentityV1"](
        manifest_hash=api["SEALED_MANIFEST_HASH"],
        gold_hash=api["SEALED_GOLD_HASH"],
        dataset_baseline_identity=api["SEALED_DATASET_BASELINE_IDENTITY"],
        baseline_report_sha256="sha256:" + "e" * 64,
        ordered_questions_sha256="sha256:" + "f" * 64,
        answerable_case_count=45,
        total_case_count=54,
    )


def _runtime(*, execution_kind: str = "full_provider"):
    api = _api()
    return api["ABRuntimeConfigV1"](
        execution_kind=execution_kind,
        tenant_id=TENANT_ID,
        owner_marker="moca.rag_token_chunk_ab.v1",
        provider="dashscope",
        embedding_model="text-embedding-v4",
        embedding_dimensions=1024,
        provider_runtime_identity="dashscope_openai_compatible.v1",
        retrieval_config_version="retrieval.v3",
        rrf_config="rrf_k=60;dense=25;sparse=50;fuzzy=20",
        rewrite_config="query_rewrite.v1:enabled",
        reranker_config="rerank.v2:enabled",
        no_evidence_threshold=Decimal("0.55"),
        incumbent=api["ABNamespaceV1"](
            corpus_version_id=INCUMBENT_CORPUS_ID,
            round_owner="moca.rag_token_chunk_ab.v1:incumbent",
        ),
        candidate=api["ABNamespaceV1"](
            corpus_version_id=CANDIDATE_CORPUS_ID,
            round_owner="moca.rag_token_chunk_ab.v1:candidate",
        ),
    )


def _parity(*, status: str = "passed"):
    cls = _api()["ABParityEvidenceV1"]
    return cls(
        report_sha256="sha256:" + "1" * 64,
        run_id=UUID("64300000-0000-4000-8000-000000000013"),
        captured_at=datetime(2026, 8, 11, 8, 30, tzinfo=UTC),
        status=status,
        config_fingerprint="sha256:" + "c" * 64,
        probe_fixture_sha256="sha256:" + "2" * 64,
        submitted_content_sha256="sha256:" + "3" * 64,
        reason_code="exact_match" if status == "passed" else "provider_usage_unavailable",
    )


def _proofs(**updates):
    values = {
        "zero_final_input_overflow": True,
        "persisted_counts_recomputed": True,
        "deterministic_rebuild": True,
        "complete_source_coverage": True,
        "immutable_identity_replay": True,
        "interrupted_resume_safe": True,
        "stale_cas_safe": True,
        "atomic_cutover_rollback_safe": True,
        "evaluation_cleanup_isolated": True,
        "fresh_provider_parity_passed": True,
    }
    values.update(updates)
    return _api()["ABHardProofsV1"](**values)


def _selected_run(*, execution_kind: str = "full_provider", parity=None):
    api = _api()
    return api["build_terminal_ab_run"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        runtime=_runtime(execution_kind=execution_kind),
        parity=parity or _parity(),
        incumbent=_observation(candidate=False),
        candidate=_observation(candidate=True),
        hard_proofs=_proofs(),
    )


def test_sealed_phase64_3_identity_and_case_counts_are_exact() -> None:
    api = _api()
    assert api["SEALED_MANIFEST_HASH"] == "e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"
    assert api["SEALED_GOLD_HASH"] == "c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"
    assert api["SEALED_DATASET_BASELINE_IDENTITY"] == "3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"
    assert _inputs().answerable_case_count == 45
    assert _inputs().total_case_count == 54
    with pytest.raises(ValidationError):
        _inputs().model_copy(update={"total_case_count": 53}).__class__.model_validate(
            {**_inputs().model_dump(), "total_case_count": 53}
        )


def test_canonical_ab_envelope_enumerates_every_provider_call_site() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli
    from src.rag.evaluation.contracts import load_format_parity_contract
    from src.rag.evaluation.retrieval_rounds import (
        ROUND_FORMATS,
        build_knowledge_query,
        ordered_gold_questions,
        run_retrieval_parity,
        run_rollback_only_retrieval_parity,
    )
    from src.rag.evaluation.token_chunk_ab import build_canonical_ab_request_envelope
    from src.rag.embedder import EmbeddingService
    from src.knowledge.rewrite import build_query_rewrite_plan

    dataset = load_format_parity_contract(
        ab_cli.DEFAULT_MANIFEST,
        ab_cli.DEFAULT_GOLD,
        repository_root=ab_cli.REPOSITORY_ROOT,
    )
    base_questions = ordered_gold_questions(dataset)
    role_count = len((ab_cli._character_incumbent(), ab_cli._token_candidate()))
    rewrite_plans = {
        case_id: build_query_rewrite_plan(
            question,
            build_knowledge_query(question=question, generated_at=GENERATED_AT.isoformat())[1],
        )
        for _, case_id, question in base_questions
    }
    expanded = {case_id: plan.rewritten_queries for case_id, plan in rewrite_plans.items() if plan.rewritten_queries}

    assert len(base_questions) == 18
    assert len(ROUND_FORMATS) == 3
    assert role_count == 2
    assert expanded == {
        "refund-case-seven-day-exception": ("哪些商品原则上不适用七天无理由退货？ 七天无理由 二次销售 退货退款",),
        "refund-case-time-limits": ("七天无理由和普通质量问题分别有什么申请时限？ 七天无理由 二次销售 退货退款",),
        "refund-case-shipped-auto-review": (
            "已发货订单长时间无轨迹且商家未响应时，什么时候能自动退款，什么情况要人工复核？ 商家已发货 物流核实",
        ),
    }
    per_role_format_query_count = len(base_questions) + sum(len(value) for value in expanded.values())
    assert per_role_format_query_count == 21
    assert role_count * len(ROUND_FORMATS) * per_role_format_query_count == 126
    assert "for namespace, assembler in zip" in inspect.getsource(ab_cli.run_full_provider_ab)
    assert "for round_format in ROUND_FORMATS" in inspect.getsource(run_rollback_only_retrieval_parity)
    assert "for policy in dataset.policies" in inspect.getsource(run_retrieval_parity)
    assert "for case in policy.gold.cases" in inspect.getsource(run_retrieval_parity)

    envelope = build_canonical_ab_request_envelope(
        dataset=dataset,
        incumbent_assembler=ab_cli._character_incumbent(),
        candidate_assembler=ab_cli._token_candidate(),
    )
    assert envelope.query_request_count == 126
    assert envelope.ingestion_request_count == 16
    assert len(envelope.ordered_ingestion_inputs) == role_count * len(ROUND_FORMATS) * len(dataset.policies)
    assert envelope.ingestion_request_count == sum(
        (item.exact_assembled_input_count + envelope.provider_batch_size - 1) // envelope.provider_batch_size
        for item in envelope.ordered_ingestion_inputs
    )
    assert envelope.sdk_retries == 0
    assert envelope.maximum_outer_attempts == 1
    assert envelope.provider_request_envelope.maximum_attempts_per_site == (1,) * 142
    assert envelope.provider_request_envelope.maximum_request_count == (126 + envelope.ingestion_request_count)
    assert len(set(envelope.provider_request_envelope.ordered_call_sites)) == 142
    assert "max_retries=0" in inspect.getsource(EmbeddingService._get_client)
    constructor_source = inspect.getsource(ab_cli.main)
    assert "max_retries=CANONICAL_AB_OUTER_ATTEMPTS" in constructor_source
    assert "batch_size=CANONICAL_AB_PROVIDER_BATCH_SIZE" in constructor_source


def test_terminal_ab_result_cannot_reserve_ordinal_two() -> None:
    from src.rag.evaluation.token_chunk_ab import canonical_ab_result_code
    from src.rag.provider_execution_authority import RETRYABLE_RESULT_CODES

    api = _api()
    selected = _selected_run()
    candidate_failed = api["build_terminal_ab_run"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        runtime=_runtime(),
        parity=_parity(),
        incumbent=_observation(candidate=False),
        candidate=_observation(candidate=True, quality=_quality(hit_5=(40, 45))),
        hard_proofs=_proofs(),
    )

    assert selected.outcome == "selected_pass"
    assert candidate_failed.outcome == "candidate_failed"
    assert canonical_ab_result_code(selected) not in RETRYABLE_RESULT_CODES
    assert canonical_ab_result_code(candidate_failed) not in RETRYABLE_RESULT_CODES


@pytest.mark.parametrize(
    ("outcome", "stage", "reason_code"),
    (
        ("unavailable", "parity", "provider_usage_unavailable"),
        ("unavailable", "provider", "provider_request_unavailable"),
        ("execution_error", "execution", "rollback_proof_failed"),
        ("execution_error", "execution", "provider_execution_failed"),
    ),
)
def test_all_zero_observation_terminals_reuse_the_exact_reserved_input_identity(
    outcome: str,
    stage: str,
    reason_code: str,
) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    reserved_inputs = _inputs()
    report = ab_cli._terminal_without_observations(
        SimpleNamespace(run_id=RUN_ID, generated_at=GENERATED_AT.isoformat()),
        inputs=reserved_inputs,
        outcome=outcome,
        stage=stage,
        reason_code=reason_code,
        incumbent_corpus_id=INCUMBENT_CORPUS_ID,
        candidate_corpus_id=CANDIDATE_CORPUS_ID,
    )

    assert report.inputs is reserved_inputs


@pytest.mark.asyncio
async def test_persisted_selected_pass_binds_db_result_lineage(tmp_path: Path) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli
    from src.rag.evaluation.contracts import load_format_parity_contract
    from src.rag.evaluation.token_chunk_ab import (
        CanonicalABExecutionService,
        CanonicalABRunResultV1,
        build_canonical_ab_request_envelope,
    )
    from src.rag.provider_execution_authority import (
        ProviderExecutionReservationViewV1,
        ProviderExecutionResultCode,
        ProviderExecutionResultViewV1,
    )

    dataset = load_format_parity_contract(
        ab_cli.DEFAULT_MANIFEST,
        ab_cli.DEFAULT_GOLD,
        repository_root=ab_cli.REPOSITORY_ROOT,
    )
    envelope = build_canonical_ab_request_envelope(
        dataset=dataset,
        incumbent_assembler=ab_cli._character_incumbent(),
        candidate_assembler=ab_cli._token_candidate(),
    )
    selected = _selected_run()
    expected_binding = _api()["ABSelectionBindingV1"](
        selection_id=SELECTION_ID,
        tenant_id=TENANT_ID,
        candidate_corpus_version_id=CANDIDATE_CORPUS_ID,
        candidate_run_token=UUID("64300000-0000-4000-8000-000000000014"),
        candidate_lease_owner="phase64.5-plan04",
        source_manifest_hash="sha256:" + "4" * 64,
    )
    owner = SimpleNamespace(
        tenant_id=TENANT_ID,
        run_token=UUID("64300000-0000-4000-8000-000000000014"),
        corpus_version_id=CANDIDATE_CORPUS_ID,
        source_active_corpus_version_id=INCUMBENT_CORPUS_ID,
        state_version=7,
        config_fingerprint="sha256:" + "c" * 64,
        provider_parity_report_hash=selected.parity.report_sha256,
        source_manifest_revision_id=UUID("64300000-0000-4000-8000-000000000015"),
        source_manifest_hash="sha256:" + "4" * 64,
        lease_owner="phase64.5-plan04",
        source_rollout_epoch=11,
        expected_evidence_rollout_version=13,
        lease_expires_at=GENERATED_AT,
    )
    events: list[str] = []
    recorded = None

    class Authority:
        async def require_current_promotion(self):
            events.append("promotion")

        async def reserve_and_commit(self, request):
            events.append("reserve_commit")
            assert request.purpose.value == "canonical_ab"
            assert request.authority_id == UUID("64300000-0000-4000-8000-000000000099")
            assert request.request_envelope == envelope.provider_request_envelope
            return ProviderExecutionReservationViewV1(
                **request.model_dump(),
                reservation_id=UUID("64300000-0000-4000-8000-000000000098"),
                tenant_id=TENANT_ID,
                reserved_at=GENERATED_AT,
            )

        async def recheck_dispatch(self, reservation):
            events.append("dispatch_recheck")
            return reservation

        async def record_result(self, request):
            nonlocal recorded
            recorded = request
            events.append("result_commit")
            return ProviderExecutionResultViewV1(
                **request.model_dump(),
                tenant_id=TENANT_ID,
                request_limit=envelope.provider_request_envelope.maximum_request_count,
                completed_at=GENERATED_AT,
            )

        async def reconcile_projection(self, **kwargs):
            events.append("projection")
            return SimpleNamespace(**kwargs)

    async def require_shared_root(**kwargs):
        events.append("shared_root")
        assert kwargs["owner"] is owner

    async def run(_provider):
        events.append("provider")
        return CanonicalABRunResultV1(
            report=selected,
            binding=expected_binding,
            diagnostic=None,
            actual_request_count=envelope.provider_request_envelope.maximum_request_count,
            result_code=ProviderExecutionResultCode.SUCCESS,
        )

    def persist_terminal(execution, reservation, result_id):
        assert execution.report == selected
        assert execution.binding == expected_binding
        assert execution.diagnostic is None
        assert reservation.reservation_id == UUID("64300000-0000-4000-8000-000000000098")
        assert isinstance(result_id, UUID)
        events.append("terminal_selection_authorization")
        return {
            "terminal_run_hash": "sha256:" + "1" * 64,
            "terminal_report_hash": "sha256:" + "2" * 64,
            "selection_decision_hash": "sha256:" + "3" * 64,
            "activation_authorization_hash": "sha256:" + "4" * 64,
        }

    outcome = await CanonicalABExecutionService(
        authority_service=Authority(),
        require_shared_root=require_shared_root,
    ).execute(
        authority_id=UUID("64300000-0000-4000-8000-000000000099"),
        owner=owner,
        inputs=selected.inputs,
        envelope=envelope,
        ordinal=1,
        run=run,
        projection_path=tmp_path / "canonical-ab.v2.json",
        persist_terminal=persist_terminal,
    )

    assert outcome.result.result_code is ProviderExecutionResultCode.SUCCESS
    assert recorded is not None
    assert recorded.output_candidate_id == CANDIDATE_CORPUS_ID
    assert recorded.selection_id == SELECTION_ID
    assert recorded.terminal_run_hash == "sha256:" + "1" * 64
    assert recorded.selection_decision_hash == "sha256:" + "3" * 64
    assert recorded.activation_authorization_hash == "sha256:" + "4" * 64
    assert events == [
        "promotion",
        "shared_root",
        "reserve_commit",
        "dispatch_recheck",
        "provider",
        "terminal_selection_authorization",
        "result_commit",
        "projection",
    ]


def test_selected_pass_requires_exact_owner_binding_and_reservation_lineage_before_persistence() -> None:
    from src.rag.evaluation.token_chunk_ab import (
        CanonicalABExecutionService,
        require_exact_canonical_ab_lineage,
    )
    from src.rag.provider_execution_authority import (
        ProviderExecutionPurpose,
        ProviderExecutionReservationRequestV1,
        ProviderExecutionReservationViewV1,
        ProviderRequestEnvelopeV1,
    )

    selected = _selected_run()
    owner = SimpleNamespace(
        tenant_id=TENANT_ID,
        run_token=UUID("64300000-0000-4000-8000-000000000014"),
        corpus_version_id=CANDIDATE_CORPUS_ID,
        source_active_corpus_version_id=INCUMBENT_CORPUS_ID,
        config_fingerprint="sha256:" + "c" * 64,
        provider_parity_report_hash=selected.parity.report_sha256,
        lease_owner="phase64.5-plan04",
        source_manifest_hash="sha256:" + "4" * 64,
    )
    binding = _api()["ABSelectionBindingV1"](
        selection_id=SELECTION_ID,
        tenant_id=owner.tenant_id,
        candidate_corpus_version_id=owner.corpus_version_id,
        candidate_run_token=owner.run_token,
        candidate_lease_owner=owner.lease_owner,
        source_manifest_hash=owner.source_manifest_hash,
    )
    provider_envelope = ProviderRequestEnvelopeV1.seal(
        schema_version="canonical_ab_request_envelope.v1",
        contract_hash="sha256:" + "5" * 64,
        ordered_call_sites=("query:0",),
        maximum_attempts_per_site=(1,),
        maximum_request_count=1,
        provider_name="dashscope",
        model_name="text-embedding-v4",
        dimensions=1024,
    )
    request = ProviderExecutionReservationRequestV1(
        authority_id=UUID("64300000-0000-4000-8000-000000000099"),
        purpose=ProviderExecutionPurpose.CANONICAL_AB,
        subject_kind="canonical_ab_run",
        subject_index=0,
        subject_hash="sha256:" + "6" * 64,
        ordinal=1,
        request_envelope=provider_envelope,
    )
    reservation = ProviderExecutionReservationViewV1(
        **request.model_dump(),
        reservation_id=UUID("64300000-0000-4000-8000-000000000098"),
        tenant_id=TENANT_ID,
        reserved_at=GENERATED_AT,
    )

    require_exact_canonical_ab_lineage(
        report=selected,
        binding=binding,
        owner=owner,
        reservation=reservation,
        request=request,
    )
    mismatches = (
        selected.model_copy(update={"runtime": selected.runtime.model_copy(update={"tenant_id": uuid4()})}),
        selected.model_copy(
            update={
                "runtime": selected.runtime.model_copy(
                    update={"incumbent": selected.runtime.incumbent.model_copy(update={"corpus_version_id": uuid4()})}
                )
            }
        ),
        selected.model_copy(
            update={
                "runtime": selected.runtime.model_copy(
                    update={"candidate": selected.runtime.candidate.model_copy(update={"corpus_version_id": uuid4()})}
                )
            }
        ),
        selected.model_copy(
            update={"parity": selected.parity.model_copy(update={"report_sha256": "sha256:" + "7" * 64})}
        ),
        selected.model_copy(
            update={"candidate": selected.candidate.model_copy(update={"config_fingerprint": "sha256:" + "8" * 64})}
        ),
        binding.model_copy(update={"tenant_id": uuid4()}),
        binding.model_copy(update={"candidate_corpus_version_id": uuid4()}),
        binding.model_copy(update={"candidate_run_token": uuid4()}),
        binding.model_copy(update={"candidate_lease_owner": "other-owner"}),
        binding.model_copy(update={"source_manifest_hash": "sha256:" + "9" * 64}),
        reservation.model_copy(update={"subject_hash": "sha256:" + "a" * 64}),
    )
    for mismatch in mismatches:
        with pytest.raises(ValueError, match="canonical_ab_.*lineage_mismatch"):
            require_exact_canonical_ab_lineage(
                report=mismatch if hasattr(mismatch, "runtime") else selected,
                binding=mismatch if hasattr(mismatch, "selection_id") else binding,
                owner=owner,
                reservation=mismatch if hasattr(mismatch, "reservation_id") else reservation,
                request=request,
            )

    service_source = inspect.getsource(CanonicalABExecutionService.execute)
    assert service_source.index("require_exact_canonical_ab_lineage(") < service_source.index("persist_terminal(")


def test_exact_fraction_boundaries_pass_without_display_rounding() -> None:
    api = _api()
    incumbent = _observation(candidate=False)
    candidate = _observation(
        candidate=True,
        quality=_quality(
            hit_1=(41, 45),
            hit_3=(44, 45),
            hit_5=(45, 45),
            mrr=(43, 45),
            anchor=(52, 54),
            locator=(52, 54),
            fallback=(52, 54),
            by_format=_format_metrics(hit_1=13, hit_3=14, hit_5=14),
        ),
        resources=_resources(chunk_count=150, duplicate_count=4, offline_tokens=12_500),
    )
    gates = api["evaluate_exact_gates"](incumbent=incumbent, candidate=candidate)
    assert all(gate.passed for gate in gates)
    assert {gate.profile_version for gate in gates} == {"rag_token_chunk_ab.v1"}
    payload = [gate.model_dump(mode="json") for gate in gates]
    assert all("numerator" in json.dumps(row) and "denominator" in json.dumps(row) for row in payload)


@pytest.mark.parametrize(
    ("quality", "resources", "failed_gate"),
    [
        (_quality(hit_5=(40, 45)), _resources(), "hit_at_5"),
        (_quality(hit_1=(40, 45)), _resources(), "hit_at_1_non_regression"),
        (_quality(mrr=(42, 45)), _resources(), "mrr_non_regression"),
        (_quality(anchor=(51, 54)), _resources(), "semantic_anchor_non_regression"),
        (_quality(by_format=_format_metrics(hit_5=13)), _resources(), "format_hit_at_5_markdown"),
        (_quality(), _resources(chunk_count=151), "chunk_count_ratio"),
        (_quality(), _resources(offline_tokens=12_501), "embedding_token_ratio"),
        (_quality(), _resources(duplicate_count=5), "duplicate_rate"),
    ],
)
def test_one_exact_unit_past_fixed_boundary_fails(quality, resources, failed_gate) -> None:
    gates = _api()["evaluate_exact_gates"](
        incumbent=_observation(candidate=False),
        candidate=_observation(candidate=True, quality=quality, resources=resources),
    )
    assert next(gate for gate in gates if gate.gate == failed_gate).passed is False


def test_four_terminal_outcomes_are_strict_and_truthful() -> None:
    api = _api()
    selected = _selected_run()
    assert selected.outcome == "selected_pass"
    assert selected.failure_class is None

    quality_failed = api["build_terminal_ab_run"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        runtime=_runtime(),
        parity=_parity(),
        incumbent=_observation(candidate=False),
        candidate=_observation(candidate=True, quality=_quality(hit_5=(40, 45))),
        hard_proofs=_proofs(),
    )
    assert (quality_failed.outcome, quality_failed.failure_class) == ("candidate_failed", "quality_fail")

    safety_failed = api["build_terminal_ab_run"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        runtime=_runtime(),
        parity=_parity(),
        incumbent=_observation(candidate=False),
        candidate=_observation(candidate=True),
        hard_proofs=_proofs(stale_cas_safe=False),
    )
    assert (safety_failed.outcome, safety_failed.failure_class) == ("candidate_failed", "safety_fail")

    for outcome, parity_status in (("unavailable", "unavailable"), ("execution_error", "unavailable")):
        terminal = api["TerminalABRunV1"](
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            outcome=outcome,
            failure_class=None,
            terminal_stage="provider" if outcome == "unavailable" else "execution",
            safe_reason_codes=("provider_usage_unavailable",)
            if outcome == "unavailable"
            else ("provider_execution_failed",),
            inputs=_inputs(),
            runtime=_runtime(),
            parity=_parity(status=parity_status),
            incumbent=None,
            candidate=None,
            hard_proofs=None,
            gates=(),
        )
        assert terminal.outcome == outcome

    with pytest.raises(ValidationError):
        api["TerminalABRunV1"].model_validate(
            {**quality_failed.model_dump(mode="json"), "failure_class": "safety_fail", "safe_reason_codes": []}
        )


def test_contract_test_can_never_claim_selected_pass() -> None:
    with pytest.raises(ValueError, match="selected_pass_requires_full_provider"):
        _selected_run(execution_kind="contract_test")


def test_every_terminal_outcome_writes_a_create_only_canonical_pair(tmp_path: Path) -> None:
    api = _api()
    terminal = _selected_run()
    pair = api["write_terminal_run_create_only"](terminal, root=tmp_path)
    before = (pair.json_path.read_bytes(), pair.markdown_path.read_bytes())
    loaded = api["load_terminal_ab_run"](pair.json_path)
    assert loaded == terminal
    assert pair.markdown_path.read_text(encoding="utf-8") == api["render_terminal_markdown"](
        loaded.model_dump(mode="json")
    )
    with pytest.raises(ValueError, match="create_conflict"):
        api["write_terminal_run_create_only"](terminal, root=tmp_path)
    assert before == (pair.json_path.read_bytes(), pair.markdown_path.read_bytes())


def test_only_selected_pass_creates_separate_immutable_selection_without_activation_fields(tmp_path: Path) -> None:
    api = _api()
    selected = _selected_run()
    run_pair = api["write_terminal_run_create_only"](selected, root=tmp_path)
    binding = api["ABSelectionBindingV1"](
        selection_id=SELECTION_ID,
        tenant_id=TENANT_ID,
        candidate_corpus_version_id=CANDIDATE_CORPUS_ID,
        candidate_run_token=UUID("64300000-0000-4000-8000-000000000014"),
        candidate_lease_owner="moca.rag_token_chunk_ab.v1:candidate",
        source_manifest_hash="sha256:" + "4" * 64,
    )
    pair = api["write_selection_create_only"](
        selected,
        binding=binding,
        terminal_run_sha256=run_pair.json_sha256,
        root=tmp_path,
    )
    decision = api["load_selection_decision"](pair.json_path)
    assert decision.schema_version == "rag_token_chunk_selection.v1"
    assert decision.outcome == "selected_pass"
    assert decision.terminal_run_sha256 == run_pair.json_sha256
    assert decision.provider_parity_report_sha256 == selected.parity.report_sha256
    assert pair.markdown_path.read_text(encoding="utf-8") == api["render_selection_markdown"](
        decision.model_dump(mode="json")
    )
    serialized = json.dumps(decision.model_dump(mode="json"), sort_keys=True).lower()
    for forbidden in ("activation", "pointer", "receipt", "cutover", "rollback", "history"):
        assert forbidden not in serialized

    failed = selected.model_copy(
        update={
            "outcome": "candidate_failed",
            "failure_class": "quality_fail",
            "safe_reason_codes": ("quality_gate_failed",),
        }
    )
    with pytest.raises(ValueError, match="selected_pass_required"):
        api["write_selection_create_only"](
            failed,
            binding=binding,
            terminal_run_sha256=run_pair.json_sha256,
            root=tmp_path / "rejected",
        )


def test_strict_safe_loaders_reject_unknown_or_sensitive_payloads(tmp_path: Path) -> None:
    api = _api()
    pair = api["write_terminal_run_create_only"](_selected_run(), root=tmp_path)
    payload = json.loads(pair.json_path.read_text(encoding="utf-8"))
    payload["database_url"] = "postgresql://forbidden"
    pair.json_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError)):
        api["load_terminal_ab_run"](pair.json_path)


def test_decimal_cost_basis_is_exact_and_versioned() -> None:
    cost = _resources(offline_tokens=12_500).embedding_cost
    assert cost.basis_version == "dashscope_text_embedding_v4_cost.v1"
    assert cost.price_per_unit == Decimal("0.0007")
    assert cost.estimated_cost == Decimal("0.00875")


def test_full_provider_cli_names_only_the_two_approved_assemblers_and_has_no_cutover_surface() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli
    from src.rag.ingestion import CharacterCompatibilityAssembler
    from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler

    assert isinstance(ab_cli._character_incumbent(), CharacterCompatibilityAssembler)
    assert isinstance(ab_cli._token_candidate(), PolicyEmbeddingInputAssembler)
    source = inspect.getsource(ab_cli)
    assert "write_terminal_run_create_only" in source
    assert "write_selection_create_only" in source
    for forbidden in ("activate_corpus(", "activate_rollout", "cas_rollout", "activation_receipt"):
        assert forbidden not in source


def test_raw_retrieval_rows_build_exact_quality_and_truthful_resource_status() -> None:
    from src.rag.evaluation.token_chunk_ab import build_candidate_observation_from_retrieval

    config_fingerprint = "sha256:" + "c" * 64
    rounds = []
    for format_name in ("markdown", "digital_pdf", "scanned_pdf"):
        cases = [
            SimpleNamespace(
                policy_id=f"policy-{index % 3}",
                case_id=f"answerable-{index}",
                category="answerable",
                ranked_doc_keys=(f"policy-{index % 3}",),
                hit_at_1=True,
                hit_at_3=True,
                hit_at_5=True,
                semantic_anchor_hits=1,
                semantic_anchor_total=1,
                no_answer_correct=False,
                locator_expected=True,
                locator_covered=True,
                service_status="strong_evidence",
            )
            for index in range(15)
        ]
        cases.extend(
            SimpleNamespace(
                policy_id=f"policy-{index}",
                case_id=f"no-answer-{index}",
                category="no_answer",
                ranked_doc_keys=(),
                hit_at_1=False,
                hit_at_3=False,
                hit_at_5=False,
                semantic_anchor_hits=0,
                semantic_anchor_total=0,
                no_answer_correct=True,
                locator_expected=False,
                locator_covered=True,
                service_status="no_evidence",
            )
            for index in range(3)
        )
        rounds.append(
            SimpleNamespace(
                round_format=format_name,
                cases=tuple(cases),
                ingestions=tuple(
                    SimpleNamespace(
                        status="success",
                        chunk_count=10,
                        duplicate_count=1,
                        offline_embedding_tokens=100,
                        provider_embedding_tokens=100 if document_index else None,
                        provider_tokens_status="provider_reported" if document_index else "unavailable",
                        config_fingerprint=config_fingerprint,
                    )
                    for document_index in range(3)
                ),
            )
        )

    observation = build_candidate_observation_from_retrieval(
        role="candidate",
        corpus_version_id=CANDIDATE_CORPUS_ID,
        config_schema_version="embedding_tokenizer.v1",
        config_fingerprint=config_fingerprint,
        deterministic_rebuild_sha256="sha256:" + "d" * 64,
        rounds=tuple(rounds),
        retrieval_duration_ms=Decimal("123.456789"),
        cost_basis_version="dashscope_text_embedding_v4_cost.v1",
        cost_currency="CNY",
        cost_unit_tokens=1_000,
        cost_price_per_unit=Decimal("0.0007"),
    )

    assert observation.quality.hit_at_5.model_dump() == {"numerator": 45, "denominator": 45}
    assert observation.quality.mrr.model_dump() == {"numerator": 1, "denominator": 1}
    assert observation.quality.semantic_anchor_coverage.model_dump() == {"numerator": 45, "denominator": 45}
    assert observation.quality.fallback_correctness.model_dump() == {"numerator": 54, "denominator": 54}
    assert observation.resources.chunk_count == 90
    assert observation.resources.duplicate_count == 9
    assert observation.resources.offline_embedding_tokens == 900
    assert observation.resources.provider_embedding_tokens is None
    assert observation.resources.provider_tokens_status == "unavailable"


@pytest.mark.asyncio
async def test_cli_invalid_noncanonical_preflight_writes_no_terminal_or_selection(tmp_path: Path) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    candidate_state = tmp_path / "candidate.json"
    candidate_state.write_text("{}\n", encoding="utf-8")
    output_root = tmp_path / "reports"
    argv = [
        "--candidate-state",
        str(candidate_state),
        "--parity-report",
        str(tmp_path / "missing-parity.json"),
        "--probe-fixture-hash",
        "sha256:" + "1" * 64,
        "--submitted-content-hash",
        "sha256:" + "2" * 64,
        "--authority-id",
        str(uuid4()),
        "--run-id",
        str(RUN_ID),
        "--selection-id",
        str(SELECTION_ID),
        "--generated-at",
        GENERATED_AT.isoformat(),
        "--output-root",
        str(output_root),
    ]

    assert await ab_cli.main(argv) == 4
    json_path = output_root / "runs" / f"{RUN_ID}.json"
    markdown_path = output_root / "runs" / f"{RUN_ID}.md"
    assert not json_path.exists()
    assert not markdown_path.exists()
    assert not (output_root / "selections").exists()
    assert await ab_cli.main(argv) == 4


@pytest.mark.asyncio
async def test_production_run_ab_dispatch_is_disabled_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    calls = {"db": 0, "root": 0, "artifact": 0, "reservation": 0, "provider": 0}

    def forbidden(name: str):
        def fail(*_args, **_kwargs):
            calls[name] += 1
            raise AssertionError(f"{name} work must not start")

        return fail

    async def forbidden_provider(*_args, **_kwargs):
        calls["provider"] += 1
        raise AssertionError("provider work must not start")

    monkeypatch.setattr(
        ab_cli,
        "parse_args",
        lambda _argv: SimpleNamespace(command="run-ab"),
    )
    monkeypatch.setattr(ab_cli, "SessionLocal", forbidden("db"))
    monkeypatch.setattr(ab_cli, "require_canonical_recovery_root", forbidden("root"))
    monkeypatch.setattr(ab_cli, "load_recovery_budget_manifest", forbidden("artifact"))
    monkeypatch.setattr(ab_cli, "_provider_execution_authority_service", forbidden("reservation"))
    monkeypatch.setattr(ab_cli, "run_full_provider_ab", forbidden_provider)

    assert await ab_cli.main([]) == 4
    assert calls == {"db": 0, "root": 0, "artifact": 0, "reservation": 0, "provider": 0}
    assert json.loads(capsys.readouterr().out) == {
        "error": "live_provider_execution_disabled",
        "reason_code": "live_provider_execution_disabled",
    }


@pytest.mark.asyncio
async def test_phase64_4_head_satisfies_ab_database_prerequisite(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    async def phase64_3_prerequisites(_session, *, expected_rollout_version: int):
        assert expected_rollout_version == 1
        return ("database_schema",)

    async def phase64_4_schema_available(_session) -> bool:
        return True

    monkeypatch.setattr(ab_cli, "_database_prerequisites", phase64_3_prerequisites)
    monkeypatch.setattr(ab_cli, "_phase64_4_schema_available", phase64_4_schema_available)

    assert await ab_cli._ab_database_prerequisites(object(), expected_rollout_version=1) == ()


def _execution_error_run(*, parity=None):
    return _api()["TerminalABRunV1"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        outcome="execution_error",
        failure_class=None,
        terminal_stage="execution",
        safe_reason_codes=("provider_execution_failed",),
        inputs=_inputs(),
        runtime=_runtime(),
        parity=parity or _parity(),
        incumbent=None,
        candidate=None,
        hard_proofs=None,
        gates=(),
    )


def _execution_diagnostic(**updates):
    values = {
        "run_id": RUN_ID,
        "terminal_run_sha256": "sha256:" + "a" * 64,
        "occurred_at": GENERATED_AT,
        "failing_role": "character_incumbent",
        "round_format": "digital_pdf",
        "stage": "retrieval_resource_proof",
        "reason_code": "resource_proof_failed",
        "provider_availability": "available",
        "provider_request_classification": "request_completed",
        "outer_rollback_attempted": True,
        "outer_rollback_proved": True,
        "completed_round_count": 1,
        "provider_request_count": 18,
        "safe_context_sha256": "sha256:" + "b" * 64,
    }
    values.update(updates)
    return _api()["ABExecutionDiagnosticV1"](**values)


def test_execution_diagnostic_is_frozen_typed_allowlisted_and_redacted() -> None:
    diagnostic = _execution_diagnostic()
    assert diagnostic.schema_version == "rag_token_chunk_execution_diagnostic.v1"
    assert diagnostic.failing_role == "character_incumbent"
    assert diagnostic.round_format == "digital_pdf"
    assert diagnostic.outer_rollback_proved is True
    with pytest.raises(ValidationError):
        _api()["ABExecutionDiagnosticV1"].model_validate(
            {**diagnostic.model_dump(mode="json"), "reason_code": "RuntimeError: secret"}
        )
    with pytest.raises(ValidationError):
        _api()["ABExecutionDiagnosticV1"].model_validate(
            {**diagnostic.model_dump(mode="json"), "raw_exception": "Traceback (most recent call last)"}
        )
    with pytest.raises((ValidationError, ValueError)):
        _execution_diagnostic(safe_context_sha256="/private/tmp/provider-payload.json")
    with pytest.raises((ValidationError, ValueError)):
        _execution_diagnostic(outer_rollback_attempted=False, outer_rollback_proved=True)

    serialized = diagnostic.model_dump_json().lower()
    for forbidden in (
        "traceback",
        "provider_payload",
        "prompt",
        "credential",
        "database_url",
        "selection",
        "activation",
        "pointer",
        "/users/",
        "/private/",
    ):
        assert forbidden not in serialized


def test_execution_error_bundle_has_one_manifest_visibility_point_and_preserves_run_bytes(tmp_path: Path) -> None:
    api = _api()
    from src.rag.evaluation.reporting import canonical_report_json_bytes

    report = _execution_error_run()
    expected_run_json = canonical_report_json_bytes(report.model_dump(mode="json"))
    expected_run_markdown = api["render_terminal_markdown"](report.model_dump(mode="json")).encode()
    diagnostic = _execution_diagnostic(
        terminal_run_sha256="sha256:" + __import__("hashlib").sha256(expected_run_json).hexdigest()
    )

    bundle = api["write_execution_error_bundle_create_only"](report, diagnostic=diagnostic, root=tmp_path)
    manifest_path = tmp_path / "commits" / str(RUN_ID) / "manifest.json"
    assert bundle.manifest_path == manifest_path
    assert manifest_path.exists()
    assert (tmp_path / "runs" / f"{RUN_ID}.json").read_bytes() == expected_run_json
    assert (tmp_path / "runs" / f"{RUN_ID}.md").read_bytes() == expected_run_markdown
    loaded = api["load_execution_error_bundle"](root=tmp_path, run_id=RUN_ID)
    assert loaded.report == report
    assert loaded.diagnostic == diagnostic
    assert loaded.manifest == api["ABExecutionBundleManifestV1"].model_validate_json(manifest_path.read_bytes())
    assert loaded.manifest.terminal_run_sha256 == bundle.run.json_sha256
    assert loaded.manifest.diagnostic_json_sha256 == bundle.diagnostic.json_sha256
    assert not (tmp_path / "selections").exists()

    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".staging" not in path.parts
    }
    recovered = api["write_execution_error_bundle_create_only"](report, diagnostic=diagnostic, root=tmp_path)
    assert recovered.manifest == bundle.manifest
    assert before == {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".staging" not in path.parts
    }


@pytest.mark.parametrize(
    "boundary",
    [
        *(f"stage_write:{name}" for name in ("run_json", "run_markdown", "diagnostic_json", "diagnostic_markdown")),
        *(f"stage_fsync:{name}" for name in ("run_json", "run_markdown", "diagnostic_json", "diagnostic_markdown")),
        *(f"publish_link:{name}" for name in ("run_json", "run_markdown", "diagnostic_json", "diagnostic_markdown")),
        *(
            f"publish_parent_fsync:{name}"
            for name in ("run_json", "run_markdown", "diagnostic_json", "diagnostic_markdown")
        ),
        "stage_dir_fsync",
        "staging_parent_fsync",
        "output_root_fsync:staging",
        "manifest_stage_write",
        "manifest_stage_fsync",
        "manifest_dir_fsync",
        "manifest_source_parent_fsync",
        "commits_parent_fsync",
        "manifest_rename",
    ],
)
def test_execution_bundle_fault_boundaries_are_invisible_then_byte_identically_resumable(
    tmp_path: Path,
    boundary: str,
) -> None:
    api = _api()
    report = _execution_error_run()
    from src.rag.evaluation.reporting import canonical_report_json_bytes

    run_sha = (
        "sha256:"
        + __import__("hashlib").sha256(canonical_report_json_bytes(report.model_dump(mode="json"))).hexdigest()
    )
    diagnostic = _execution_diagnostic(terminal_run_sha256=run_sha)

    def crash(observed: str) -> None:
        if observed == boundary:
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        api["write_execution_error_bundle_create_only"](
            report,
            diagnostic=diagnostic,
            root=tmp_path,
            fault_injector=crash,
        )
    with pytest.raises(ValueError, match="bundle_uncommitted"):
        api["load_execution_error_bundle"](root=tmp_path, run_id=RUN_ID)

    bundle = api["write_execution_error_bundle_create_only"](report, diagnostic=diagnostic, root=tmp_path)
    loaded = api["load_execution_error_bundle"](root=tmp_path, run_id=RUN_ID)
    assert loaded.manifest == bundle.manifest
    assert loaded.report == report
    assert loaded.diagnostic == diagnostic


@pytest.mark.parametrize(
    "boundary",
    ["manifest_parent_fsync", "manifest_source_parent_post_rename_fsync"],
)
def test_post_manifest_fault_keeps_the_already_committed_bundle_readable(
    tmp_path: Path,
    boundary: str,
) -> None:
    api = _api()
    from src.rag.evaluation.reporting import canonical_report_json_bytes

    report = _execution_error_run()
    run_sha = (
        "sha256:"
        + __import__("hashlib").sha256(canonical_report_json_bytes(report.model_dump(mode="json"))).hexdigest()
    )
    diagnostic = _execution_diagnostic(terminal_run_sha256=run_sha)

    def crash(observed: str) -> None:
        if observed == boundary:
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        api["write_execution_error_bundle_create_only"](
            report,
            diagnostic=diagnostic,
            root=tmp_path,
            fault_injector=crash,
        )
    loaded = api["load_execution_error_bundle"](root=tmp_path, run_id=RUN_ID)
    assert loaded.report == report
    assert loaded.diagnostic == diagnostic


def test_execution_bundle_partial_conflict_fails_closed_without_manifest(tmp_path: Path) -> None:
    api = _api()
    from src.rag.evaluation.reporting import canonical_report_json_bytes

    report = _execution_error_run()
    run_sha = (
        "sha256:"
        + __import__("hashlib").sha256(canonical_report_json_bytes(report.model_dump(mode="json"))).hexdigest()
    )
    diagnostic = _execution_diagnostic(terminal_run_sha256=run_sha)

    def crash(observed: str) -> None:
        if observed == "publish_link:run_json":
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError):
        api["write_execution_error_bundle_create_only"](
            report,
            diagnostic=diagnostic,
            root=tmp_path,
            fault_injector=crash,
        )
    (tmp_path / "runs" / f"{RUN_ID}.json").write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="bundle_conflict"):
        api["write_execution_error_bundle_create_only"](report, diagnostic=diagnostic, root=tmp_path)
    assert not (tmp_path / "commits" / str(RUN_ID)).exists()
    with pytest.raises(ValueError, match="bundle_uncommitted"):
        api["load_execution_error_bundle"](root=tmp_path, run_id=RUN_ID)


def test_non_execution_outcomes_keep_legacy_pair_path_and_never_create_diagnostics(tmp_path: Path) -> None:
    api = _api()
    selected = _selected_run()
    legacy = api["write_terminal_run_create_only"](selected, root=tmp_path)
    assert legacy.json_path.exists() and legacy.markdown_path.exists()
    with pytest.raises(ValueError, match="execution_error_required"):
        api["write_execution_error_bundle_create_only"](
            selected,
            diagnostic=_execution_diagnostic(),
            root=tmp_path,
        )
    assert not (tmp_path / "diagnostics").exists()
    assert not (tmp_path / "commits").exists()


def test_typed_runtime_failure_drives_exact_diagnostic_without_raw_exception() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli
    from src.rag.evaluation.retrieval_rounds import SafeRoleFailureV1

    failure = SafeRoleFailureV1(
        failing_role="token_candidate",
        round_format="scanned_pdf",
        stage="post_rollback_baseline_verification",
        reason_code="rollback_proof_failed",
        provider_availability="available",
        provider_request_classification="request_completed",
        outer_rollback_attempted=True,
        outer_rollback_proved=False,
        completed_round_count=2,
        provider_request_count=36,
        safe_context_sha256="sha256:" + "7" * 64,
    )
    diagnostic = ab_cli._execution_diagnostic_from_failure(_execution_error_run(), failure)
    assert diagnostic.failing_role == "token_candidate"
    assert diagnostic.round_format == "scanned_pdf"
    assert diagnostic.stage == "post_rollback_baseline_verification"
    assert diagnostic.reason_code == "rollback_proof_failed"
    assert diagnostic.outer_rollback_attempted is True
    assert diagnostic.outer_rollback_proved is False
    serialized = diagnostic.model_dump_json().lower()
    for forbidden in ("traceback", "runtimeerror", "provider payload", "secret", "/private/tmp"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    (
        "stage",
        "reason_code",
        "provider_availability",
        "provider_request_classification",
        "outer_rollback_attempted",
        "outer_rollback_proved",
        "provider_request_count",
        "expected_result_code",
    ),
    (
        (
            "shared_preflight",
            "candidate_state_invalid",
            "not_checked",
            "not_attempted",
            False,
            False,
            0,
            "source_drift",
        ),
        (
            "shared_preflight",
            "sealed_input_invalid",
            "not_checked",
            "not_attempted",
            False,
            False,
            0,
            "configuration_error",
        ),
        ("shared_preflight", "candidate_pair_invalid", "not_checked", "not_attempted", False, False, 0, "source_drift"),
        ("role_setup", "role_setup_failed", "not_checked", "not_attempted", False, False, 0, "configuration_error"),
        (
            "format_ingestion",
            "format_ingestion_failed",
            "not_checked",
            "not_attempted",
            False,
            False,
            0,
            "projection_error",
        ),
        ("format_ingestion", "provider_request_failed", "available", "request_failed", True, True, 1, "response_error"),
        (
            "retrieval_resource_proof",
            "provider_request_failed",
            "available",
            "request_failed",
            True,
            True,
            1,
            "transient_execution_error",
        ),
        (
            "retrieval_resource_proof",
            "resource_proof_failed",
            "available",
            "request_completed",
            True,
            True,
            1,
            "projection_error",
        ),
        (
            "post_rollback_baseline_verification",
            "rollback_proof_failed",
            "available",
            "request_completed",
            True,
            False,
            1,
            "projection_error",
        ),
        (
            "retrieval_resource_proof",
            "provider_execution_failed",
            "available",
            "request_started",
            True,
            True,
            1,
            "unknown_error",
        ),
    ),
)
def test_every_typed_failure_maps_to_exact_db_code_and_only_explicit_transient_can_retry(
    stage: str,
    reason_code: str,
    provider_availability: str,
    provider_request_classification: str,
    outer_rollback_attempted: bool,
    outer_rollback_proved: bool,
    provider_request_count: int,
    expected_result_code: str,
) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli
    from src.rag.evaluation.retrieval_rounds import SafeRoleFailureV1
    from src.rag.provider_execution_authority import RETRYABLE_RESULT_CODES, ProviderExecutionResultCode

    failure = SafeRoleFailureV1(
        failing_role="shared_preflight" if stage == "shared_preflight" else "token_candidate",
        round_format=None if stage in {"shared_preflight", "role_setup"} else "markdown",
        stage=stage,
        reason_code=reason_code,
        provider_availability=provider_availability,
        provider_request_classification=provider_request_classification,
        outer_rollback_attempted=outer_rollback_attempted,
        outer_rollback_proved=outer_rollback_proved,
        completed_round_count=0,
        provider_request_count=provider_request_count,
    )

    result_code = ab_cli.canonical_ab_failure_result_code(failure)

    assert result_code is ProviderExecutionResultCode(expected_result_code)
    assert (result_code in RETRYABLE_RESULT_CODES) is (expected_result_code == "transient_execution_error")


def test_typed_failure_code_and_diagnostic_are_validated_before_terminal_file_writes() -> None:
    from src.rag.evaluation.token_chunk_ab import CanonicalABExecutionService

    service_source = inspect.getsource(CanonicalABExecutionService.execute)
    persistence_offset = service_source.index("persist_terminal(execution")

    assert service_source.index("canonical_ab_execution_diagnostic_mismatch") < persistence_offset
    assert service_source.index("canonical_ab_typed_failure_result_code(") < persistence_offset
    assert service_source.index("canonical_ab_result_code_invalid") < persistence_offset


def test_diagnostic_cli_has_no_selection_activation_or_pointer_write_surface() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    diagnostic_source = inspect.getsource(ab_cli._execution_diagnostic_from_failure)
    main_source = inspect.getsource(ab_cli.main)
    for forbidden in (
        "write_selection_create_only",
        "activate_corpus",
        "cas_rollout",
        "policycorpusactivationhistory",
        "activation_receipt",
    ):
        assert forbidden not in diagnostic_source.lower()
    assert "write_execution_error_bundle_create_only" in main_source
    assert "_failure" not in main_source
    assert "diagnostic=execution.diagnostic" in main_source


def _recovery_budget_manifest(
    *,
    candidate_state_sha256: str = "sha256:" + "4" * 64,
    candidate_state_relative_path: str = (
        "candidates/tenants/64300000-0000-4000-8000-000000000001/runs/"
        "64300000-0000-4000-8000-000000000014/states/00000007.json"
    ),
    candidate_descriptor_sha256: str = "sha256:" + "5" * 64,
    parity_report_sha256: str | None = None,
    parity_run_id: UUID | None = None,
    parity_probe_fixture_sha256: str | None = None,
    parity_submitted_content_sha256: str | None = None,
):
    return _api()["build_plan12_recovery_budget_manifest"](
        created_at=GENERATED_AT,
        tenant_id=TENANT_ID,
        incumbent_corpus_version_id=INCUMBENT_CORPUS_ID,
        candidate_corpus_version_id=CANDIDATE_CORPUS_ID,
        candidate_run_token=UUID("64300000-0000-4000-8000-000000000014"),
        candidate_lease_owner="phase64.4-plan13",
        candidate_state_version=7,
        candidate_state_relative_path=candidate_state_relative_path,
        candidate_state_sha256=candidate_state_sha256,
        candidate_recovery_descriptor_sha256=candidate_descriptor_sha256,
        candidate_config_schema_version="embedding_tokenizer.v1",
        candidate_config_fingerprint="sha256:" + "c" * 64,
        candidate_source_manifest_revision_id=UUID("64300000-0000-4000-8000-000000000015"),
        candidate_source_manifest_revision=7,
        candidate_source_manifest_hash="sha256:" + "4" * 64,
        candidate_source_active_corpus_version_id=INCUMBENT_CORPUS_ID,
        candidate_source_rollout_epoch=11,
        candidate_expected_evidence_rollout_version=13,
        provider_parity_run_id=parity_run_id or _parity().run_id,
        provider_parity_report_sha256=parity_report_sha256 or _parity().report_sha256,
        provider_parity_config_fingerprint=_parity().config_fingerprint,
        provider_parity_probe_fixture_sha256=parity_probe_fixture_sha256 or _parity().probe_fixture_sha256,
        provider_parity_submitted_content_sha256=(
            parity_submitted_content_sha256 or _parity().submitted_content_sha256
        ),
    )


def _write_recovery_budget(tmp_path: Path):
    api = _api()
    candidate_state, parity_path, parity_report = _write_recovery_candidate_authority(tmp_path)
    manifest_value = _recovery_budget_manifest(
        candidate_state_sha256=_file_sha256(candidate_state.path),
        candidate_state_relative_path=candidate_state.path.relative_to(tmp_path).as_posix(),
        candidate_descriptor_sha256=candidate_state.descriptor_sha256,
        parity_report_sha256=_file_sha256(parity_path),
        parity_run_id=parity_report.run_id,
        parity_probe_fixture_sha256=parity_report.probe_fixture_sha256,
        parity_submitted_content_sha256=parity_report.submitted_content_sha256,
    )
    artifact = api["write_recovery_budget_manifest_create_only"](
        manifest_value,
        root=tmp_path,
    )
    loaded = api["load_recovery_budget_manifest"](artifact.path)
    assert loaded == manifest_value
    return loaded, artifact, candidate_state.path, parity_path


def _reserve_first(tmp_path: Path, *, prerequisite_hash: str = "sha256:" + "5" * 64):
    api = _api()
    manifest, artifact, candidate_state_path, parity_path = _write_recovery_budget(tmp_path)
    reservation = api["reserve_recovery_attempt"](
        manifest_path=artifact.path,
        root=tmp_path,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=parity_path,
        run_id=RUN_ID,
        selection_id=SELECTION_ID,
        reserved_at=GENERATED_AT,
        prerequisite_state_sha256=prerequisite_hash,
    )
    return manifest, artifact, reservation, candidate_state_path, parity_path


def _write_selected_recovery_lineage(tmp_path: Path):
    api = _api()
    manifest, budget_artifact, reservation, candidate_state_path, parity_path = _reserve_first(tmp_path)
    report = _selected_run(parity=_recovery_parity(manifest))
    terminal = api["write_terminal_run_create_only"](report, root=tmp_path)
    selection = api["write_selection_create_only"](
        report,
        binding=api["ABSelectionBindingV1"](
            selection_id=reservation.selection_id,
            tenant_id=manifest.tenant_id,
            candidate_corpus_version_id=manifest.candidate_corpus_version_id,
            candidate_run_token=manifest.candidate_run_token,
            candidate_lease_owner=manifest.candidate_lease_owner,
            source_manifest_hash=manifest.candidate_source_manifest_hash,
        ),
        terminal_run_sha256=terminal.json_sha256,
        root=tmp_path,
    )
    reservation_path = budget_artifact.path.parent / "attempts" / f"{reservation.ordinal:02d}.json"
    authorization = api["write_recovery_authorization_create_only"](
        root=tmp_path,
        manifest_path=budget_artifact.path,
        reservation_path=reservation_path,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=parity_path,
        terminal_run_path=terminal.json_path,
        selection_path=selection.json_path,
        checked_at=GENERATED_AT,
    )
    return SimpleNamespace(
        manifest=manifest,
        budget_artifact=budget_artifact,
        reservation=reservation,
        reservation_path=reservation_path,
        candidate_state_path=candidate_state_path,
        parity_path=parity_path,
        terminal=terminal,
        selection=selection,
        authorization=authorization,
    )


@dataclass(frozen=True, slots=True)
class _CandidateStateArtifact:
    path: Path
    descriptor_sha256: str


def _write_recovery_candidate_authority(
    tmp_path: Path,
    *,
    state: str = "complete",
) -> tuple[_CandidateStateArtifact, Path, object]:
    from datetime import timedelta

    from src.rag.policy_reindex import PolicyReindexRunIdentity
    from src.rag.policy_reindex_artifacts import (
        build_policy_reindex_recovery_descriptor,
        write_policy_reindex_recovery_descriptor_create_only,
        write_policy_reindex_state_create_only,
    )
    from src.rag.tokenizer_parity import (
        EmbeddingTokenizerParityReportV1,
        ParityProbeResultV1,
        parity_content_sha256,
        write_parity_report_create_only,
    )
    from src.rag.embedding_tokenizer import ProviderParityStatus

    run_token = UUID("64300000-0000-4000-8000-000000000014")
    manifest_id = UUID("64300000-0000-4000-8000-000000000015")
    probes = tuple(
        ParityProbeResultV1(
            probe_id=f"probe-{index:02d}",
            category="safe_synthetic",
            embedding_input_sha256=f"sha256:{index:064x}",
            offline_tokens=20 + index,
            provider_prompt_tokens=20 + index,
            provider_total_tokens=20 + index,
            exact_match=True,
        )
        for index in range(10)
    )
    submitted_content_sha256 = parity_content_sha256(probes)
    aggregate_tokens = sum(probe.offline_tokens for probe in probes)
    parity_report = EmbeddingTokenizerParityReportV1(
        schema_version="embedding_tokenizer_parity.v1",
        run_id=_parity().run_id,
        captured_at=_parity().captured_at,
        region_class="dashscope_public",
        provider="dashscope",
        model="text-embedding-v4",
        dimensions=1024,
        tokenizer_contract_version="embedding_tokenizer.v1",
        config_fingerprint="sha256:" + "c" * 64,
        assembly_schema_version="policy_embedding_input.v1",
        probe_fixture_sha256=_parity().probe_fixture_sha256,
        submitted_content_sha256=submitted_content_sha256,
        provider_parity_status=ProviderParityStatus.PASSED,
        reason_code="exact_match",
        probes=probes,
        aggregate_input_count=10,
        aggregate_offline_tokens=aggregate_tokens,
        aggregate_provider_prompt_tokens=aggregate_tokens,
        aggregate_provider_total_tokens=aggregate_tokens,
        aggregate_exact_match=True,
    )
    parity_path = write_parity_report_create_only(parity_report, root=tmp_path / "parity")
    descriptor = build_policy_reindex_recovery_descriptor(
        sealed_at=GENERATED_AT - timedelta(minutes=15),
        tenant_id=TENANT_ID,
        run_token=run_token,
        generation_name=f"token.v1:{run_token.hex}",
        lease_owner="phase64.4-plan13",
        lease_expires_at=GENERATED_AT + timedelta(hours=1),
        config_schema_version="embedding_tokenizer.v1",
        config_json={
            "dimensions": 1024,
            "max_embedding_tokens": 512,
            "overlap_tokens": 48,
            "target_embedding_tokens": 384,
        },
        config_fingerprint="sha256:" + "c" * 64,
        parity_report_sha256=_file_sha256(parity_path),
        parity_config_fingerprint="sha256:" + "c" * 64,
        parity_probe_fixture_sha256=parity_report.probe_fixture_sha256,
        parity_submitted_content_sha256=parity_report.submitted_content_sha256,
        parity_captured_at=parity_report.captured_at,
        parity_expires_at=parity_report.captured_at + timedelta(hours=24),
        source_manifest_revision_id=manifest_id,
        source_manifest_revision=7,
        source_manifest_hash="sha256:" + "4" * 64,
        source_active_corpus_version_id=INCUMBENT_CORPUS_ID,
        source_rollout_epoch=11,
        expected_evidence_rollout_version=13,
    )
    candidates_root = tmp_path / "candidates"
    descriptor_artifact = write_policy_reindex_recovery_descriptor_create_only(descriptor, root=candidates_root)
    state = PolicyReindexRunIdentity(
        corpus_version_id=CANDIDATE_CORPUS_ID,
        tenant_id=TENANT_ID,
        run_token=run_token,
        generation_name=descriptor.generation_name,
        lease_owner=descriptor.lease_owner,
        lease_expires_at=descriptor.lease_expires_at,
        state=state,
        state_version=7,
        next_document_index=3 if state == "complete" else 0,
        ordered_doc_keys=("policy-a", "policy-b", "policy-c"),
        config_schema_version=descriptor.config_schema_version,
        config_fingerprint=descriptor.config_fingerprint,
        provider_parity_report_hash=descriptor.parity_report_sha256,
        source_manifest_revision_id=descriptor.source_manifest_revision_id,
        source_manifest_revision=descriptor.source_manifest_revision,
        source_manifest_hash=descriptor.source_manifest_hash,
        source_active_corpus_version_id=descriptor.source_active_corpus_version_id,
        source_rollout_epoch=descriptor.source_rollout_epoch,
        expected_evidence_rollout_version=descriptor.expected_evidence_rollout_version,
        parity_captured_at=descriptor.parity_captured_at,
        parity_expires_at=descriptor.parity_expires_at,
    )
    state_artifact = write_policy_reindex_state_create_only(state, descriptor=descriptor, root=candidates_root)
    return (
        _CandidateStateArtifact(path=state_artifact.path, descriptor_sha256=_file_sha256(descriptor_artifact.path)),
        parity_path,
        parity_report,
    )


def _live_authority_proof(candidate_state_path: Path):
    from src.rag.policy_reindex_artifacts import (
        load_policy_reindex_recovery_descriptor,
        load_policy_reindex_state,
        policy_reindex_descriptor_path,
    )

    candidates_root = candidate_state_path.parents[5]
    descriptor_path = policy_reindex_descriptor_path(
        candidates_root,
        tenant_id=TENANT_ID,
        run_token=UUID("64300000-0000-4000-8000-000000000014"),
    )
    descriptor = load_policy_reindex_recovery_descriptor(descriptor_path, root=candidates_root)
    identity = load_policy_reindex_state(candidate_state_path, descriptor=descriptor, root=candidates_root)
    return _api()["RecoveryLiveAuthorityProofV1"](
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
        deterministic_rebuild_sha256="sha256:" + "d" * 64,
        complete_projection_proved=True,
        sealed_inputs_proved=True,
    )


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _recovery_parity(manifest):
    return _parity().model_copy(
        update={
            "report_sha256": manifest.provider_parity_report_sha256,
            "run_id": manifest.provider_parity_run_id,
            "config_fingerprint": manifest.provider_parity_config_fingerprint,
            "probe_fixture_sha256": manifest.provider_parity_probe_fixture_sha256,
            "submitted_content_sha256": manifest.provider_parity_submitted_content_sha256,
        }
    )


def _unavailable_run(*, reason_code: str = "provider_request_unavailable", parity=None):
    return _api()["TerminalABRunV1"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        outcome="unavailable",
        failure_class=None,
        terminal_stage="provider",
        safe_reason_codes=(reason_code,),
        inputs=_inputs(),
        runtime=_runtime(),
        parity=parity or _parity(),
        incumbent=None,
        candidate=None,
        hard_proofs=None,
        gates=(),
    )


def test_plan12_recovery_budget_is_frozen_fixed_and_binds_exact_plan10_evidence() -> None:
    api = _api()
    manifest = _recovery_budget_manifest()
    assert manifest.schema_version == "rag_token_chunk_recovery_budget.v1"
    assert manifest.budget_id == "phase64.4-plan12-live-selection-recovery"
    assert manifest.budget_id == api["PLAN12_RECOVERY_BUDGET_ID"]
    assert manifest.phase == "64.4" and manifest.plan == "12"
    assert manifest.max_attempts == 2
    assert manifest.max_embedding_tokens == 512
    assert manifest.target_embedding_tokens == 384
    assert manifest.overlap_tokens == 48
    assert manifest.plan10_terminal_runs == api["PLAN10_TERMINAL_RUNS"]
    assert manifest.plan10_baseline_proof_sha256 == (
        "sha256:4dae8f0ec1c9e4c7b2010786fbd94f05af7b2d8623f0ae4df196d14ff26823f3"
    )
    assert manifest.provider_parity_config_fingerprint == manifest.candidate_config_fingerprint
    assert manifest.candidate_state_version == 7
    assert manifest.candidate_lease_owner == "phase64.4-plan13"
    assert manifest.candidate_source_manifest_revision == 7
    assert manifest.candidate_source_active_corpus_version_id == INCUMBENT_CORPUS_ID
    assert manifest.candidate_expected_evidence_rollout_version == 13
    assert manifest.candidate_state_relative_path.startswith("candidates/tenants/")
    assert manifest.manifest_payload_sha256.startswith("sha256:")
    with pytest.raises((ValidationError, ValueError)):
        api["ABRecoveryBudgetManifestV1"].model_validate({**manifest.model_dump(mode="json"), "max_attempts": 3})

    evidence_root = Path("evaluation/reports/rag_token_chunk_ab/v1")
    assert api["validate_fixed_plan10_evidence"](evidence_root) == api["PLAN10_TERMINAL_RUNS"]


def test_recovery_budget_manifest_and_reservations_are_create_only(tmp_path: Path) -> None:
    api = _api()
    manifest, artifact, reservation, candidate_state_path, parity_path = _reserve_first(tmp_path)
    before = artifact.path.read_bytes()
    assert reservation.ordinal == 1
    assert reservation.run_id == RUN_ID
    assert reservation.selection_id == SELECTION_ID
    assert reservation.budget_manifest_sha256 == artifact.sha256
    assert reservation.candidate_state_sha256 == manifest.candidate_state_sha256
    assert (
        api["load_recovery_attempt_reservation"](
            tmp_path / "recovery-budgets" / manifest.budget_id / "attempts" / "01.json",
            manifest=manifest,
            manifest_sha256=artifact.sha256,
        )
        == reservation
    )
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_attempt_missing_evidence"):
        api["reserve_recovery_attempt"](
            manifest_path=artifact.path,
            root=tmp_path,
            candidate_state_path=candidate_state_path,
            provider_parity_report_path=parity_path,
            run_id=uuid4(),
            selection_id=uuid4(),
            reserved_at=GENERATED_AT,
            prerequisite_state_sha256="sha256:" + "6" * 64,
        )
    assert artifact.path.read_bytes() == before
    assert len(tuple((artifact.path.parent / "attempts").glob("*.json"))) == 1


def test_canonical_recovery_root_is_repository_relative_resolved_and_rejects_aliases(tmp_path: Path) -> None:
    api = _api()
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    canonical = repository_root / "evaluation" / "reports" / "rag_token_chunk_ab" / "v1"
    canonical.mkdir(parents=True)

    assert api["canonical_recovery_root"](repository_root=repository_root) == canonical.resolve()
    assert (
        api["require_canonical_recovery_root"](
            output_root=canonical,
            repository_root=repository_root,
        )
        == canonical.resolve()
    )

    copied_root = tmp_path / "copied-v1"
    copied_root.mkdir()
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_root_not_canonical"):
        api["require_canonical_recovery_root"](output_root=copied_root, repository_root=repository_root)

    alias = tmp_path / "canonical-alias"
    alias.symlink_to(canonical, target_is_directory=True)
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_root_not_canonical"):
        api["require_canonical_recovery_root"](output_root=alias, repository_root=repository_root)


@pytest.mark.asyncio
async def test_production_cli_refuses_copied_budget_root_before_run_or_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    copied_root = tmp_path / "copied-v1"
    _, artifact, candidate_state_path, parity_path = _write_recovery_budget(copied_root)
    run_calls = 0

    async def forbidden_run(*_args, **_kwargs):
        nonlocal run_calls
        run_calls += 1
        raise AssertionError("provider-capable run must not start")

    monkeypatch.setattr(ab_cli, "run_full_provider_ab", forbidden_run)
    result = await ab_cli.main(
        [
            "--candidate-state",
            str(candidate_state_path),
            "--parity-report",
            str(parity_path),
            "--probe-fixture-hash",
            "sha256:" + "2" * 64,
            "--submitted-content-hash",
            "sha256:" + "3" * 64,
            "--authority-id",
            str(uuid4()),
            "--run-id",
            str(uuid4()),
            "--selection-id",
            str(uuid4()),
            "--generated-at",
            GENERATED_AT.isoformat(),
            "--output-root",
            str(copied_root),
        ]
    )

    assert result == 4
    assert run_calls == 0
    assert not (artifact.path.parent / "attempts").exists()


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("candidate_state_bytes", "recovery_candidate_state_invalid"),
        ("candidate_state_path", "recovery_candidate_state_identity_mismatch"),
        ("parity_bytes", "recovery_parity_invalid"),
    ],
)
def test_reservation_rehashes_strict_candidate_and_fresh_parity_before_ordinal(
    tmp_path: Path,
    mutation: str,
    expected_reason: str,
) -> None:
    api = _api()
    _, artifact, candidate_state_path, parity_path = _write_recovery_budget(tmp_path)
    selected_candidate_path = candidate_state_path
    if mutation == "candidate_state_bytes":
        payload = json.loads(candidate_state_path.read_text(encoding="utf-8"))
        payload["identity"]["lease_owner"] = "copied-owner"
        candidate_state_path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "candidate_state_path":
        selected_candidate_path = tmp_path / "copied-state.json"
        selected_candidate_path.write_bytes(candidate_state_path.read_bytes())
    else:
        parity_path.write_bytes(parity_path.read_bytes()[:-1] + b" ")

    with pytest.raises(api["RecoveryAttemptRefused"], match=expected_reason):
        api["reserve_recovery_attempt"](
            manifest_path=artifact.path,
            root=tmp_path,
            candidate_state_path=selected_candidate_path,
            provider_parity_report_path=parity_path,
            run_id=uuid4(),
            selection_id=uuid4(),
            reserved_at=GENERATED_AT,
            prerequisite_state_sha256="sha256:" + "6" * 64,
        )
    assert not (artifact.path.parent / "attempts").exists()


def test_crash_consumes_slot_and_concurrent_first_reservation_has_exactly_one_winner(tmp_path: Path) -> None:
    api = _api()
    manifest, artifact, candidate_state_path, parity_path = _write_recovery_budget(tmp_path)

    def reserve(index: int):
        return api["reserve_recovery_attempt"](
            manifest_path=artifact.path,
            root=tmp_path,
            candidate_state_path=candidate_state_path,
            provider_parity_report_path=parity_path,
            run_id=UUID(int=100 + index),
            selection_id=UUID(int=200 + index),
            reserved_at=GENERATED_AT,
            prerequisite_state_sha256="sha256:" + "5" * 64,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: _capture_reservation_result(reserve, value), (1, 2)))
    winners = [result for result in results if isinstance(result, api["ABRecoveryAttemptReservationV1"])]
    losers = [result for result in results if isinstance(result, api["RecoveryAttemptRefused"])]
    assert len(winners) == 1 and winners[0].ordinal == 1
    assert len(losers) == 1
    assert len(tuple((artifact.path.parent / "attempts").glob("*.json"))) == 1

    authority = api["evaluate_recovery_retry_authority"](
        manifest=manifest,
        previous_reservation=winners[0],
        root=tmp_path,
        next_prerequisite_state_sha256="sha256:" + "6" * 64,
    )
    assert authority.allowed is False
    assert authority.reason_code == "recovery_attempt_missing_evidence"


def _capture_reservation_result(reserve, value: int):
    try:
        return reserve(value)
    except Exception as error:
        return error


@pytest.mark.parametrize(
    ("outcome", "expected_reason"),
    [
        ("selected_pass", "selected_pass_stops_budget"),
        ("candidate_failed_quality", "candidate_failed_stops_budget"),
        ("candidate_failed_safety", "candidate_failed_stops_budget"),
    ],
)
def test_retry_matrix_always_stops_for_selected_or_candidate_failed(
    tmp_path: Path,
    outcome: str,
    expected_reason: str,
) -> None:
    api = _api()
    manifest, _, reservation, _, _ = _reserve_first(tmp_path)
    parity = _recovery_parity(manifest)
    if outcome == "selected_pass":
        report = _selected_run(parity=parity)
    elif outcome == "candidate_failed_quality":
        report = api["build_terminal_ab_run"](
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inputs=_inputs(),
            runtime=_runtime(),
            parity=parity,
            incumbent=_observation(candidate=False),
            candidate=_observation(candidate=True, quality=_quality(hit_5=(40, 45))),
            hard_proofs=_proofs(),
        )
    else:
        report = api["build_terminal_ab_run"](
            run_id=RUN_ID,
            generated_at=GENERATED_AT,
            inputs=_inputs(),
            runtime=_runtime(),
            parity=parity,
            incumbent=_observation(candidate=False),
            candidate=_observation(candidate=True),
            hard_proofs=_proofs(stale_cas_safe=False),
        )
    api["write_terminal_run_create_only"](report, root=tmp_path)
    authority = api["evaluate_recovery_retry_authority"](
        manifest=manifest,
        previous_reservation=reservation,
        root=tmp_path,
        next_prerequisite_state_sha256="sha256:" + "6" * 64,
    )
    assert authority.allowed is False
    assert authority.reason_code == expected_reason


@pytest.mark.parametrize(
    ("diagnostic_updates", "allowed", "expected_reason"),
    [
        ({}, True, "transient_execution_error_retry_allowed"),
        ({"outer_rollback_proved": False}, False, "rollback_unproved_stops_budget"),
        (
            {
                "stage": "role_setup",
                "reason_code": "role_setup_failed",
                "provider_request_classification": "not_attempted",
                "provider_request_count": 0,
            },
            False,
            "implementation_defect_stops_budget",
        ),
        (
            {"reason_code": "resource_proof_failed"},
            False,
            "implementation_defect_stops_budget",
        ),
    ],
)
def test_execution_error_retry_requires_committed_allowlisted_transient_bundle_and_rollback(
    tmp_path: Path,
    diagnostic_updates: dict[str, object],
    allowed: bool,
    expected_reason: str,
) -> None:
    api = _api()
    manifest, _, reservation, _, _ = _reserve_first(tmp_path)
    report = _execution_error_run(parity=_recovery_parity(manifest))
    payload = canonical_run_bytes(report)
    diagnostic_values: dict[str, object] = {
        "terminal_run_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "stage": "retrieval_resource_proof",
        "reason_code": "provider_request_failed",
        "provider_request_classification": "request_failed",
    }
    diagnostic_values.update(diagnostic_updates)
    diagnostic = _execution_diagnostic(**diagnostic_values)
    api["write_execution_error_bundle_create_only"](
        report,
        diagnostic=diagnostic,
        root=tmp_path,
    )
    authority = api["evaluate_recovery_retry_authority"](
        manifest=manifest,
        previous_reservation=reservation,
        root=tmp_path,
        next_prerequisite_state_sha256="sha256:" + "6" * 64,
    )
    assert authority.allowed is allowed
    assert authority.reason_code == expected_reason


def canonical_run_bytes(report) -> bytes:
    from src.rag.evaluation.reporting import canonical_report_json_bytes

    return canonical_report_json_bytes(report.model_dump(mode="json"))


def test_execution_error_missing_uncommitted_or_mismatched_bundle_stops(tmp_path: Path) -> None:
    api = _api()
    manifest, _, reservation, _, _ = _reserve_first(tmp_path)
    report = _execution_error_run(parity=_recovery_parity(manifest))
    api["write_terminal_run_create_only"](report, root=tmp_path)
    authority = api["evaluate_recovery_retry_authority"](
        manifest=manifest,
        previous_reservation=reservation,
        root=tmp_path,
        next_prerequisite_state_sha256="sha256:" + "6" * 64,
    )
    assert authority.allowed is False
    assert authority.reason_code == "execution_evidence_invalid_stops_budget"


@pytest.mark.parametrize(
    ("reason_code", "next_hash", "sidecar", "allowed", "expected_reason"),
    [
        (
            "provider_request_unavailable",
            "sha256:" + "6" * 64,
            False,
            True,
            "unavailable_prerequisite_change_retry_allowed",
        ),
        (
            "provider_request_unavailable",
            "sha256:" + "5" * 64,
            False,
            False,
            "prerequisite_state_unchanged_stops_budget",
        ),
        (
            "unclassified_outage",
            "sha256:" + "6" * 64,
            False,
            False,
            "unavailable_reason_not_allowlisted_stops_budget",
        ),
        (
            "provider_request_unavailable",
            "sha256:" + "6" * 64,
            True,
            False,
            "unavailable_sidecar_forbidden_stops_budget",
        ),
    ],
)
def test_unavailable_retry_requires_allowlisted_terminal_no_sidecar_and_prerequisite_change(
    tmp_path: Path,
    reason_code: str,
    next_hash: str,
    sidecar: bool,
    allowed: bool,
    expected_reason: str,
) -> None:
    api = _api()
    manifest, _, reservation, _, _ = _reserve_first(tmp_path)
    report = _unavailable_run(reason_code=reason_code, parity=_recovery_parity(manifest))
    api["write_terminal_run_create_only"](report, root=tmp_path)
    if sidecar:
        diagnostic_path = tmp_path / "diagnostics" / f"{RUN_ID}.json"
        diagnostic_path.parent.mkdir(parents=True)
        diagnostic_path.write_text("{}\n", encoding="utf-8")
    authority = api["evaluate_recovery_retry_authority"](
        manifest=manifest,
        previous_reservation=reservation,
        root=tmp_path,
        next_prerequisite_state_sha256=next_hash,
    )
    assert authority.allowed is allowed
    assert authority.reason_code == expected_reason


def test_second_valid_slot_then_third_or_plan10_identity_reuse_refuses_before_provider(tmp_path: Path) -> None:
    api = _api()
    manifest, artifact, reservation, candidate_state_path, parity_path = _reserve_first(tmp_path)
    report = _execution_error_run(parity=_recovery_parity(manifest))
    diagnostic = _execution_diagnostic(
        terminal_run_sha256="sha256:" + hashlib.sha256(canonical_run_bytes(report)).hexdigest(),
        stage="retrieval_resource_proof",
        reason_code="provider_request_failed",
        provider_request_classification="request_failed",
    )
    api["write_execution_error_bundle_create_only"](report, diagnostic=diagnostic, root=tmp_path)
    second = api["reserve_recovery_attempt"](
        manifest_path=artifact.path,
        root=tmp_path,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=parity_path,
        run_id=UUID("64300000-0000-4000-8000-000000000020"),
        selection_id=UUID("64300000-0000-4000-8000-000000000021"),
        reserved_at=GENERATED_AT,
        prerequisite_state_sha256="sha256:" + "6" * 64,
    )
    assert second.ordinal == 2
    provider_calls = 0

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        return object()

    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_budget_exhausted"):
        api["reserve_then_create_provider"](
            reserve=lambda: api["reserve_recovery_attempt"](
                manifest_path=artifact.path,
                root=tmp_path,
                candidate_state_path=candidate_state_path,
                provider_parity_report_path=parity_path,
                run_id=uuid4(),
                selection_id=uuid4(),
                reserved_at=GENERATED_AT,
                prerequisite_state_sha256="sha256:" + "7" * 64,
            ),
            require_current_authority=lambda: None,
            provider_factory=provider_factory,
        )
    assert provider_calls == 0

    other_root = tmp_path / "plan10-reuse"
    _, other_artifact, other_state_path, other_parity_path = _write_recovery_budget(other_root)
    plan10_run_id = api["PLAN10_TERMINAL_RUNS"][0].run_id
    with pytest.raises(api["RecoveryAttemptRefused"], match="plan10_identity_reuse_forbidden"):
        api["reserve_then_create_provider"](
            reserve=lambda: api["reserve_recovery_attempt"](
                manifest_path=other_artifact.path,
                root=other_root,
                candidate_state_path=other_state_path,
                provider_parity_report_path=other_parity_path,
                run_id=plan10_run_id,
                selection_id=uuid4(),
                reserved_at=GENERATED_AT,
                prerequisite_state_sha256="sha256:" + "5" * 64,
            ),
            require_current_authority=lambda: None,
            provider_factory=provider_factory,
        )
    assert provider_calls == 0
    assert reservation.ordinal == 1 and manifest.max_attempts == 2


def test_recovery_artifacts_are_redacted_and_db_service_rechecks_before_provider_factory() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    manifest = _recovery_budget_manifest()
    serialized = manifest.model_dump_json().lower()
    for forbidden in (
        "traceback",
        "raw_exception",
        "provider_payload",
        "prompt",
        "credential",
        "database_url",
        "postgresql://",
        "/users/",
        "/private/",
    ):
        assert forbidden not in serialized
    authority_source = inspect.getsource(ab_cli.CanonicalABExecutionService.execute)
    assert authority_source.index("reserve_and_commit") < authority_source.index("recheck_dispatch")
    assert authority_source.index("recheck_dispatch") < authority_source.index("construct_provider()")
    source = inspect.getsource(ab_cli.run_full_provider_ab)
    assert "max_embedding_tokens=512" not in source
    assert "target_embedding_tokens=384" not in source
    assert "overlap_tokens=48" not in source


def test_selected_pass_writes_create_only_reconciled_recovery_authorization(tmp_path: Path) -> None:
    api = _api()
    lineage = _write_selected_recovery_lineage(tmp_path)
    loaded = api["load_recovery_authorization"](lineage.authorization.path)
    before = lineage.authorization.path.read_bytes()

    reconciled = api["write_recovery_authorization_create_only"](
        root=tmp_path,
        manifest_path=lineage.budget_artifact.path,
        reservation_path=lineage.reservation_path,
        candidate_state_path=lineage.candidate_state_path,
        provider_parity_report_path=lineage.parity_path,
        terminal_run_path=lineage.terminal.json_path,
        selection_path=lineage.selection.json_path,
        checked_at=GENERATED_AT,
    )

    assert reconciled == lineage.authorization
    assert reconciled.path.read_bytes() == before
    assert loaded.schema_version == "rag_token_chunk_recovery_authorization.v1"
    assert loaded.budget_manifest_sha256 == lineage.budget_artifact.sha256
    assert loaded.reservation_ordinal == lineage.reservation.ordinal == 1
    assert loaded.reservation_sha256 == _file_sha256(lineage.reservation_path)
    assert loaded.candidate_state_sha256 == lineage.manifest.candidate_state_sha256
    assert loaded.candidate_corpus_version_id == CANDIDATE_CORPUS_ID
    assert loaded.candidate_run_token == lineage.manifest.candidate_run_token
    assert loaded.candidate_config_fingerprint == lineage.manifest.candidate_config_fingerprint
    assert loaded.provider_parity_report_sha256 == lineage.manifest.provider_parity_report_sha256
    assert loaded.source_manifest_hash == lineage.manifest.candidate_source_manifest_hash
    assert loaded.terminal_run_id == RUN_ID
    assert loaded.terminal_run_sha256 == lineage.terminal.json_sha256
    assert loaded.selection_id == SELECTION_ID
    assert loaded.selection_sha256 == lineage.selection.json_sha256
    assert loaded.authorization_payload_sha256.startswith("sha256:")


@pytest.mark.parametrize(
    "mutation",
    ("alternate_manifest", "wrong_state", "wrong_reservation", "fabricated_authorization", "over_budget"),
)
def test_recovery_authorization_refuses_noncanonical_or_fabricated_lineage(
    tmp_path: Path,
    mutation: str,
) -> None:
    api = _api()
    lineage = _write_selected_recovery_lineage(tmp_path)
    manifest_path = lineage.budget_artifact.path
    reservation_path = lineage.reservation_path
    candidate_state_path = lineage.candidate_state_path
    authorization_path = lineage.authorization.path

    if mutation == "alternate_manifest":
        manifest_path = tmp_path / "copied" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_bytes(lineage.budget_artifact.path.read_bytes())
    elif mutation == "wrong_state":
        candidate_state_path = tmp_path / "copied" / "state.json"
        candidate_state_path.parent.mkdir(parents=True)
        candidate_state_path.write_bytes(lineage.candidate_state_path.read_bytes())
    elif mutation == "wrong_reservation":
        reservation_path = tmp_path / "copied" / "01.json"
        reservation_path.parent.mkdir(parents=True)
        reservation_path.write_bytes(lineage.reservation_path.read_bytes())
    else:
        payload = json.loads(authorization_path.read_text(encoding="utf-8"))
        if mutation == "fabricated_authorization":
            payload["candidate_run_token"] = str(uuid4())
        else:
            payload["reservation_ordinal"] = 3
        payload["authorization_payload_sha256"] = _payload_sha256(
            {key: value for key, value in payload.items() if key != "authorization_payload_sha256"}
        )
        authorization_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((ValueError, api["RecoveryAttemptRefused"])):
        if mutation in {"fabricated_authorization", "over_budget"}:
            api["load_recovery_authorization"](
                authorization_path,
                root=tmp_path,
                manifest_path=manifest_path,
                reservation_path=reservation_path,
                candidate_state_path=candidate_state_path,
                provider_parity_report_path=lineage.parity_path,
                terminal_run_path=lineage.terminal.json_path,
                selection_path=lineage.selection.json_path,
                checked_at=GENERATED_AT,
            )
        else:
            api["write_recovery_authorization_create_only"](
                root=tmp_path,
                manifest_path=manifest_path,
                reservation_path=reservation_path,
                candidate_state_path=candidate_state_path,
                provider_parity_report_path=lineage.parity_path,
                terminal_run_path=lineage.terminal.json_path,
                selection_path=lineage.selection.json_path,
                checked_at=GENERATED_AT,
            )


def test_canonical_recovery_budget_issuance_requires_complete_live_authority_and_reconciles(
    tmp_path: Path,
) -> None:
    api = _api()
    candidate_state, parity_path, _ = _write_recovery_candidate_authority(tmp_path)
    proof = _live_authority_proof(candidate_state.path)

    issued = api["issue_canonical_recovery_budget_manifest"](
        root=tmp_path,
        candidate_state_path=candidate_state.path,
        provider_parity_report_path=parity_path,
        checked_at=GENERATED_AT,
        live_authority=proof,
    )
    before = issued.path.read_bytes()
    reconciled = api["issue_canonical_recovery_budget_manifest"](
        root=tmp_path,
        candidate_state_path=candidate_state.path,
        provider_parity_report_path=parity_path,
        checked_at=GENERATED_AT,
        live_authority=proof,
    )

    assert reconciled == issued
    assert reconciled.path.read_bytes() == before
    assert reconciled.path == tmp_path / "recovery-budgets" / api["PLAN12_RECOVERY_BUDGET_ID"] / "manifest.json"
    assert not (issued.path.parent / "attempts").exists()


def test_canonical_recovery_budget_refuses_incomplete_candidate_and_expired_authority(
    tmp_path: Path,
) -> None:
    from src.rag.policy_reindex_artifacts import load_policy_reindex_recovery_descriptor

    api = _api()
    incomplete_root = tmp_path / "incomplete"
    candidate_state, parity_path, _ = _write_recovery_candidate_authority(incomplete_root, state="building")
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_candidate_incomplete"):
        api["issue_canonical_recovery_budget_manifest"](
            root=incomplete_root,
            candidate_state_path=candidate_state.path,
            provider_parity_report_path=parity_path,
            checked_at=GENERATED_AT,
            live_authority=_live_authority_proof(candidate_state.path),
        )
    assert not (incomplete_root / "recovery-budgets").exists()

    current_root = tmp_path / "current"
    candidate_state, parity_path, _ = _write_recovery_candidate_authority(current_root)
    descriptor_path = candidate_state.path.parents[1] / "descriptor.json"
    descriptor = load_policy_reindex_recovery_descriptor(descriptor_path, root=current_root / "candidates")
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_authority_expired"):
        api["issue_canonical_recovery_budget_manifest"](
            root=current_root,
            candidate_state_path=candidate_state.path,
            provider_parity_report_path=parity_path,
            checked_at=descriptor.lease_expires_at,
            live_authority=_live_authority_proof(candidate_state.path),
        )
    assert not (current_root / "recovery-budgets").exists()


def test_reservation_and_provider_boundary_require_current_authority(tmp_path: Path) -> None:
    api = _api()
    candidate_state, parity_path, _ = _write_recovery_candidate_authority(tmp_path)
    issued = api["issue_canonical_recovery_budget_manifest"](
        root=tmp_path,
        candidate_state_path=candidate_state.path,
        provider_parity_report_path=parity_path,
        checked_at=GENERATED_AT,
        live_authority=_live_authority_proof(candidate_state.path),
    )
    manifest = api["load_recovery_budget_manifest"](issued.path)
    from src.rag.policy_reindex_artifacts import load_policy_reindex_recovery_descriptor

    descriptor = load_policy_reindex_recovery_descriptor(
        candidate_state.path.parents[1] / "descriptor.json",
        root=tmp_path / "candidates",
    )
    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_authority_expired"):
        api["reserve_recovery_attempt"](
            manifest_path=issued.path,
            root=tmp_path,
            candidate_state_path=candidate_state.path,
            provider_parity_report_path=parity_path,
            run_id=uuid4(),
            selection_id=uuid4(),
            reserved_at=descriptor.lease_expires_at,
            prerequisite_state_sha256="sha256:" + "6" * 64,
        )
    assert not (issued.path.parent / "attempts").exists()

    provider_calls = 0

    def provider_factory():
        nonlocal provider_calls
        provider_calls += 1
        return object()

    with pytest.raises(api["RecoveryAttemptRefused"], match="recovery_authority_expired"):
        api["reserve_then_create_provider"](
            reserve=lambda: SimpleNamespace(ordinal=1),
            require_current_authority=lambda: (_ for _ in ()).throw(
                api["RecoveryAttemptRefused"]("recovery_authority_expired")
            ),
            provider_factory=provider_factory,
        )
    assert provider_calls == 0
    assert manifest.max_attempts == 2


def test_issue_recovery_budget_cli_has_no_operator_authority_timestamp() -> None:
    import scripts.eval_rag_token_chunk_ab as ab_cli

    args = ab_cli.parse_args(
        [
            "issue-recovery-budget",
            "--candidate-state",
            "candidate.json",
            "--parity-report",
            "parity.json",
            "--output-root",
            str(ab_cli.DEFAULT_OUTPUT_ROOT),
        ]
    )
    assert args.command == "issue-recovery-budget"
    assert not hasattr(args, "checked_at")
    assert not hasattr(args, "generated_at")
