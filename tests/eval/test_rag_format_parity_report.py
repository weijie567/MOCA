from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.rag.evaluation.contracts import EvaluationOutcome, load_format_parity_contract
from src.rag.evaluation.parser_parity import (
    FixtureHashV1,
    ParserCaseResultV1,
    ParserDimensionV1,
    ParserParityInputsV1,
    ParserParityRunV1,
    ParserPrerequisiteV1,
    ParserRuntimeVersionV1,
    ParserVariantResultV1,
)
from src.rag.evaluation.retrieval_rounds import (
    PrerequisiteStatusV1,
    RetrievalCaseObservationV1,
    RetrievalParityRunV1,
    RetrievalRoundResultV1,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "evaluation/rag_sources/format_parity_manifest.jsonl"
GOLD = ROOT / "evaluation/golden/rag_format_parity_gold.json"
GENERATED_AT = "2026-08-10T00:00:00Z"
RUN_TOKEN = "64300000-0000-4000-8000-000000000004"
TENANT_ID = "64300000-0000-4000-8000-000000000001"
OWNER_MARKER = "moca.rag_format_parity.v1"


def _reporting_api():
    from src.rag.evaluation.reporting import (
        FORMAT_PARITY_TARGETS,
        FormatParityReportV1,
        FormatParityRuntimeConfigV1,
        build_format_parity_report,
        load_format_parity_report,
        render_markdown,
    )

    return (
        FORMAT_PARITY_TARGETS,
        FormatParityReportV1,
        FormatParityRuntimeConfigV1,
        build_format_parity_report,
        load_format_parity_report,
        render_markdown,
    )


@pytest.fixture(scope="module")
def dataset():
    return load_format_parity_contract(MANIFEST, GOLD, repository_root=ROOT)


def _dimension(name: str, *, status: str = "passed", matched: int = 1, expected: int = 1):
    return ParserDimensionV1(
        dimension=name,
        status=status,
        matched=matched,
        expected=expected,
        recall=None if expected == 0 else matched / expected,
        reason_codes=() if status != "failed" else (f"{name}_failed",),
    )


def _parser_run(dataset, *, mode: str = "parser_direct", outcome: EvaluationOutcome = EvaluationOutcome.COMPLETED_PASS):
    variants = []
    for policy in dataset.policies:
        for fixture in policy.variants:
            cases = tuple(
                ParserCaseResultV1(
                    policy_id=policy.doc_key,
                    variant=fixture.format,
                    case_id=case.case_id,
                    category=case.category,
                    status="not_applicable" if case.no_answer else "passed",
                    matched_anchors=len(case.evidence_anchor_ids),
                    expected_anchors=len(case.evidence_anchor_ids),
                    anchor_recall=None if case.no_answer else 1.0,
                )
                for case in policy.gold.cases
            )
            variants.append(
                ParserVariantResultV1(
                    policy_id=policy.doc_key,
                    variant=fixture.format,
                    source_type=fixture.source_type,
                    parser_name="moca_parser_registry",
                    parser_version="21.01",
                    ocr_engine="tesseract" if fixture.format == "scanned_pdf" else None,
                    ocr_engine_version="5.5.2" if fixture.format == "scanned_pdf" else None,
                    ocr_language="chi_sim+eng" if fixture.format == "scanned_pdf" else None,
                    outcome=outcome,
                    parse_status=_dimension("parse_status"),
                    semantic_anchors=_dimension("semantic_anchors", matched=10, expected=10),
                    heading_structure=_dimension("heading_structure", matched=2, expected=2),
                    critical_tables=_dimension("critical_tables", matched=2, expected=2),
                    provenance_locators=_dimension("provenance_locators", matched=10, expected=10),
                    pdf_page_coverage=(
                        _dimension("pdf_page_coverage", status="not_applicable", matched=0, expected=0)
                        if fixture.format == "markdown"
                        else _dimension("pdf_page_coverage", matched=5, expected=5)
                    ),
                    ocr_diagnostics=(
                        _dimension("ocr_diagnostics")
                        if fixture.format == "scanned_pdf"
                        else _dimension("ocr_diagnostics", status="not_applicable", matched=0, expected=0)
                    ),
                    warning_failures=_dimension("warning_failures"),
                    observations=(),
                    case_results=cases,
                    safe_diagnostics=(),
                )
            )
    return ParserParityRunV1(
        mode=mode,
        generated_at=GENERATED_AT,
        outcome=outcome,
        inputs=ParserParityInputsV1(
            manifest_hash=dataset.manifest_hash,
            gold_hash=dataset.gold_hash,
            baseline_identity=dataset.baseline_identity,
            fixture_hashes=tuple(
                FixtureHashV1(path=path, sha256=digest) for path, digest in sorted(dataset.fixture_hashes.items())
            ),
        ),
        prerequisites=(
            ParserPrerequisiteV1(
                name="ocr_runtime",
                status="available",
                reason_code="ocr_runtime_available",
                version="5.5.2",
                required_languages=("chi_sim", "eng"),
            ),
        ),
        runtime_versions=(
            ParserRuntimeVersionV1(kind="parser", name="moca_parser_registry", version="21.01"),
            ParserRuntimeVersionV1(kind="ocr", name="tesseract", version="5.5.2", language="chi_sim+eng"),
        ),
        variant_results=tuple(variants),
        safe_failures=(),
    )


def _retrieval_run(
    dataset,
    *,
    mode: str = "provider",
    outcome: EvaluationOutcome = EvaluationOutcome.COMPLETED_PASS,
    baseline_eligible: bool = True,
):
    rounds = []
    for format_name in ("markdown", "digital_pdf", "scanned_pdf"):
        observations = []
        for policy in dataset.policies:
            answerable_index = 0
            for case in policy.gold.cases:
                if case.no_answer:
                    observations.append(
                        RetrievalCaseObservationV1(
                            policy_id=policy.doc_key,
                            case_id=case.case_id,
                            question=case.question,
                            category=case.category,
                            service_status="no_evidence",
                            hit_at_1=False,
                            hit_at_3=False,
                            hit_at_5=False,
                            reciprocal_rank=0.0,
                            semantic_anchor_hits=0,
                            semantic_anchor_total=0,
                            no_answer_correct=True,
                            locator_expected=False,
                            locator_covered=True,
                            fallback_reason="below_threshold",
                        )
                    )
                    continue
                ranks = (1, 2, 4, None, 1)
                rank = ranks[answerable_index]
                observations.append(
                    RetrievalCaseObservationV1(
                        policy_id=policy.doc_key,
                        case_id=case.case_id,
                        question=case.question,
                        category=case.category,
                        service_status="strong_evidence" if rank is not None else "no_evidence",
                        ranked_doc_keys=() if rank is None else (policy.doc_key,),
                        hit_at_1=rank == 1,
                        hit_at_3=rank is not None and rank <= 3,
                        hit_at_5=rank is not None and rank <= 5,
                        reciprocal_rank=0.0 if rank is None else 1 / rank,
                        semantic_anchor_hits=0 if answerable_index == 2 else 1,
                        semantic_anchor_total=1,
                        no_answer_correct=False,
                        locator_expected=True,
                        locator_covered=answerable_index != 4,
                        rerank_observed=True,
                    )
                )
                answerable_index += 1
        rounds.append(
            RetrievalRoundResultV1(
                round_format=format_name,
                round_token=f"{format_name}-round-token",
                outcome=outcome,
                cases=tuple(observations),
                pre_state_proved=True,
                exactly_three_current_proved=True,
                post_state_proved=True,
                immutable_history_preserved=True,
            )
        )
    return RetrievalParityRunV1(
        mode=mode,
        baseline_eligible=baseline_eligible,
        outcome=outcome,
        generated_at=GENERATED_AT,
        tenant_id=TENANT_ID,
        owner_marker=OWNER_MARKER,
        run_token=RUN_TOKEN,
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        baseline_identity=dataset.baseline_identity,
        rounds=tuple(rounds),
        prerequisites=(
            PrerequisiteStatusV1(name="postgresql_pgvector", available=True),
            PrerequisiteStatusV1(name="embedding_provider", available=True),
            PrerequisiteStatusV1(name="tesseract_chi_sim_eng", available=True),
        ),
    )


def _runtime_config(*, execution_kind: str = "full_provider"):
    *_, RuntimeConfig, _build, _load, _render = _reporting_api()
    return RuntimeConfig(
        command="scripts/eval_rag_format_parity.py --mode full-provider",
        execution_kind=execution_kind,
        tenant_id=TENANT_ID,
        owner_marker=OWNER_MARKER,
        run_token=RUN_TOKEN,
        expected_rollout_version=2,
        generator_identity_hash="0a9f3cead84eeae36244f386a71a770337cd70fe64e7a17603a3e7d4b7ae0f24",
        embedding_provider="dashscope",
        embedding_model="text-embedding-v4",
        embedding_dimensions=1024,
        retrieval_config_version="hybrid.v2",
        rrf_config="rrf_k=60;dense=20;sparse=20;fuzzy=20",
        rewrite_config="query_rewrite.v1:enabled",
        reranker_config="rerank.v1:enabled",
        no_evidence_threshold=0.35,
        parser_toolchain=("moca_parser_registry@21.01",),
        ocr_toolchain=("tesseract@5.5.2:chi_sim+eng",),
    )


def _build_report(dataset, **overrides):
    *_, build_report, _load, _render = _reporting_api()
    return build_report(
        dataset=dataset,
        parser_run=overrides.get("parser_run", _parser_run(dataset)),
        retrieval_run=overrides.get("retrieval_run", _retrieval_run(dataset)),
        runtime_config=overrides.get("runtime_config", _runtime_config()),
        generated_at=GENERATED_AT,
    )


def test_target_profile_is_exact_and_matches_accepted_quality_plan() -> None:
    targets, *_ = _reporting_api()
    assert targets.model_dump(mode="json") == {
        "schema_version": "rag_format_parity_targets.v1",
        "profile": "rag_format_parity_targets.v1",
        "rationale": "Initial targets accepted in docs/quality/rag-quality-plan.md section 5.",
        "gates": [
            {"metric": "parse_success_rate", "operator": ">=", "target": 1.0},
            {"metric": "markdown_anchor_coverage", "operator": ">=", "target": 1.0},
            {"metric": "digital_pdf_anchor_coverage", "operator": ">=", "target": 1.0},
            {"metric": "scanned_pdf_anchor_coverage", "operator": ">=", "target": 0.95},
            {"metric": "critical_table_preservation", "operator": ">=", "target": 1.0},
            {"metric": "pdf_locator_coverage", "operator": ">=", "target": 1.0},
            {"metric": "retrieval_hit_at_5", "operator": ">=", "target": 0.9},
            {"metric": "cross_format_hit_at_5_spread", "operator": "<=", "target": 0.1},
        ],
    }
    quality_plan = (ROOT / "docs/quality/rag-quality-plan.md").read_text(encoding="utf-8")
    for accepted_text in ("100%", "95%", "90%", "10 个百分点"):
        assert accepted_text in quality_plan


def test_metric_math_is_exact_at_case_policy_format_and_overall_levels(dataset) -> None:
    report = _build_report(dataset)
    overall = report.metrics.overall
    assert overall.hit_at_1 == 0.4
    assert overall.hit_at_3 == 0.6
    assert overall.hit_at_5 == 0.8
    assert overall.mrr == 0.55
    assert overall.semantic_anchor_coverage == 0.8
    assert overall.no_answer_correctness == 1.0
    assert overall.fallback_correctness == 0.833333
    assert overall.locator_coverage == 0.8
    assert report.metrics.cross_format_hit_at_5_spread == 0.0
    assert {row.format for row in report.metrics.by_format} == {"markdown", "digital_pdf", "scanned_pdf"}
    assert all(row.metrics.hit_at_5 == 0.8 for row in report.metrics.by_format)
    assert len(report.metrics.by_policy) == 3
    assert all(row.metrics.mrr == 0.55 for row in report.metrics.by_policy)
    assert len(report.metrics.by_case) == 18
    assert all(0.0 <= row.metrics.hit_at_5 <= 1.0 for row in report.metrics.by_case)


def test_every_completed_miss_has_exactly_one_primary_stage(dataset) -> None:
    report = _build_report(dataset)
    failed_rows = [row for row in report.case_rows if not row.passed]
    assert failed_rows
    assert len(report.failures) == len(failed_rows)
    assert {failure.primary_stage for failure in report.failures} == {"chunking", "retrieval", "provenance"}
    assert all(row.primary_stage is not None for row in failed_rows)
    assert len({(f.policy_id, f.format, f.case_id) for f in report.failures}) == len(report.failures)


def test_parser_and_ocr_misses_keep_their_primary_stage(dataset) -> None:
    parser = _parser_run(dataset)
    variants = list(parser.variant_results)
    for wanted_format, wanted_stage in (("markdown", "parser"), ("scanned_pdf", "ocr")):
        variant_index = next(
            index
            for index, variant in enumerate(variants)
            if variant.variant == wanted_format and variant.policy_id == dataset.policies[0].doc_key
        )
        cases = list(variants[variant_index].case_results)
        case_index = next(index for index, case in enumerate(cases) if case.status == "passed")
        cases[case_index] = cases[case_index].model_copy(
            update={
                "status": "failed",
                "primary_stage": wanted_stage,
                "reason_codes": (f"{wanted_stage}_anchor_missing",),
            }
        )
        variants[variant_index] = variants[variant_index].model_copy(update={"case_results": tuple(cases)})
    parser = parser.model_copy(update={"variant_results": tuple(variants)})
    report = _build_report(dataset, parser_run=parser)
    stages = {failure.primary_stage for failure in report.failures}
    assert {"parser", "ocr", "chunking", "retrieval", "provenance"} <= stages


def test_malformed_completed_rows_become_execution_error(dataset) -> None:
    retrieval = _retrieval_run(dataset)
    broken_round = retrieval.rounds[0].model_copy(update={"cases": retrieval.rounds[0].cases[:-1]})
    malformed = retrieval.model_copy(update={"rounds": (broken_round, *retrieval.rounds[1:])})
    report = _build_report(dataset, retrieval_run=malformed)
    assert report.outcome is EvaluationOutcome.EXECUTION_ERROR
    assert report.baseline_eligible is False
    assert report.metrics is None
    assert report.safe_reason_codes == ("completed_case_set_malformed",)


def test_markdown_is_projection_of_canonical_json_and_checked_snapshot(dataset) -> None:
    _targets, _model, _runtime, _build, _load, render_markdown = _reporting_api()
    report = _build_report(dataset)
    canonical = report.model_dump(mode="json")
    projected = render_markdown(canonical)
    assert projected == render_markdown(json.loads(json.dumps(canonical, sort_keys=True)))
    assert projected.startswith("# RAG Format Parity Baseline\n\n")
    assert "Canonical schema: `rag_format_parity_report.v1`" in projected
    assert (
        "Provider reproducibility records exact inputs/config/toolchain and attributable observations; it does not promise bit-identical scores across live runs."
        in projected
    )
    assert (
        "| overall | 0.400000 | 0.600000 | 0.800000 | 0.550000 | 0.800000 | 1.000000 | 0.833333 | 0.800000 |"
        in projected
    )
    reporting_source = (ROOT / "src/rag/evaluation/reporting.py").read_text(encoding="utf-8")
    renderer = reporting_source.split("def render_markdown", maxsplit=1)[1]
    assert "_aggregate" not in renderer
    assert "_build_gates" not in renderer


def test_strict_loader_and_validated_json_dump_reproduce_markdown_byte_for_byte(dataset, tmp_path) -> None:
    _targets, ReportModel, _runtime, _build, load_report, render_markdown = _reporting_api()
    report = _build_report(dataset)
    report_path = tmp_path / "baseline.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    loaded = load_report(report_path)
    assert isinstance(loaded, ReportModel)
    assert loaded.model_config["frozen"] is True
    assert render_markdown(loaded.model_dump(mode="json")) == render_markdown(report.model_dump(mode="json"))

    unsafe = report.model_dump(mode="json")
    unsafe["database_url"] = "postgresql://forbidden"
    report_path.write_text(json.dumps(unsafe), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError)):
        load_report(report_path)

    unsafe = report.model_dump(mode="json")
    unsafe["config"]["embedding_model"] = "sk-secret-value"
    report_path.write_text(json.dumps(unsafe), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe_report_value"):
        load_report(report_path)


@pytest.mark.parametrize(
    ("parser_outcome", "retrieval_outcome", "expected"),
    [
        (EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_QUALITY_FAIL),
        (
            EvaluationOutcome.COMPLETED_QUALITY_FAIL,
            EvaluationOutcome.COMPLETED_PASS,
            EvaluationOutcome.COMPLETED_QUALITY_FAIL,
        ),
        (
            EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
            EvaluationOutcome.COMPLETED_PASS,
            EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
        ),
        (EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.EXECUTION_ERROR, EvaluationOutcome.EXECUTION_ERROR),
    ],
)
def test_outcomes_are_mutually_exclusive_and_safe(dataset, parser_outcome, retrieval_outcome, expected) -> None:
    parser = _parser_run(dataset, outcome=parser_outcome)
    retrieval = _retrieval_run(
        dataset,
        outcome=retrieval_outcome,
        baseline_eligible=retrieval_outcome
        in {EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_QUALITY_FAIL},
    )
    report = _build_report(dataset, parser_run=parser, retrieval_run=retrieval)
    assert report.outcome is expected
    assert sum(report.outcome is candidate for candidate in EvaluationOutcome) == 1
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    for forbidden in ("api_key", "database_url", "postgresql://", "traceback", "raw_provider", "/Users/"):
        assert forbidden not in serialized.lower()


def test_fake_and_contract_test_runs_are_never_baseline_eligible(dataset) -> None:
    report = _build_report(dataset, runtime_config=_runtime_config(execution_kind="contract_test"))
    assert report.baseline_eligible is False
    with pytest.raises(ValidationError):
        _retrieval_run(dataset, mode="contract_test", baseline_eligible=True)
