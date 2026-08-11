from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

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
        ABFormatMetricsV1,
        ABHardProofsV1,
        ABInputIdentityV1,
        ABNamespaceV1,
        ABParityEvidenceV1,
        ABQualityMetricsV1,
        ABResourceMetricsV1,
        ABRuntimeConfigV1,
        ABSelectionBindingV1,
        ExactRatioV1,
        TerminalABRunV1,
        build_terminal_ab_run,
        evaluate_exact_gates,
        load_selection_decision,
        load_terminal_ab_run,
        render_selection_markdown,
        render_terminal_markdown,
        write_selection_create_only,
        write_terminal_run_create_only,
    )

    return {
        "SEALED_DATASET_BASELINE_IDENTITY": SEALED_DATASET_BASELINE_IDENTITY,
        "SEALED_GOLD_HASH": SEALED_GOLD_HASH,
        "SEALED_MANIFEST_HASH": SEALED_MANIFEST_HASH,
        "ABCandidateObservationV1": ABCandidateObservationV1,
        "ABEmbeddingCostV1": ABEmbeddingCostV1,
        "ABFormatMetricsV1": ABFormatMetricsV1,
        "ABHardProofsV1": ABHardProofsV1,
        "ABInputIdentityV1": ABInputIdentityV1,
        "ABNamespaceV1": ABNamespaceV1,
        "ABParityEvidenceV1": ABParityEvidenceV1,
        "ABQualityMetricsV1": ABQualityMetricsV1,
        "ABResourceMetricsV1": ABResourceMetricsV1,
        "ABRuntimeConfigV1": ABRuntimeConfigV1,
        "ABSelectionBindingV1": ABSelectionBindingV1,
        "ExactRatioV1": ExactRatioV1,
        "TerminalABRunV1": TerminalABRunV1,
        "build_terminal_ab_run": build_terminal_ab_run,
        "evaluate_exact_gates": evaluate_exact_gates,
        "load_selection_decision": load_selection_decision,
        "load_terminal_ab_run": load_terminal_ab_run,
        "render_selection_markdown": render_selection_markdown,
        "render_terminal_markdown": render_terminal_markdown,
        "write_selection_create_only": write_selection_create_only,
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


def _selected_run(*, execution_kind: str = "full_provider"):
    api = _api()
    return api["build_terminal_ab_run"](
        run_id=RUN_ID,
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        runtime=_runtime(execution_kind=execution_kind),
        parity=_parity(),
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
async def test_cli_early_execution_error_still_writes_one_create_only_terminal_pair(tmp_path: Path) -> None:
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
        "--run-id",
        str(RUN_ID),
        "--selection-id",
        str(SELECTION_ID),
        "--generated-at",
        GENERATED_AT.isoformat(),
        "--output-root",
        str(output_root),
    ]

    assert await ab_cli.main(argv) == 2
    json_path = output_root / "runs" / f"{RUN_ID}.json"
    markdown_path = output_root / "runs" / f"{RUN_ID}.md"
    before = (json_path.read_bytes(), markdown_path.read_bytes())
    terminal = _api()["load_terminal_ab_run"](json_path)
    assert terminal.outcome == "execution_error"
    assert terminal.safe_reason_codes == ("candidate_state_invalid",)
    assert not (output_root / "selections").exists()
    assert await ab_cli.main(argv) == 2
    assert before == (json_path.read_bytes(), markdown_path.read_bytes())
