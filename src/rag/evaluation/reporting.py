"""Canonical reporting for the RAG format-parity evaluator.

JSON is the only metric, gate, outcome, identity, and attribution owner.  The
Markdown renderer below validates that JSON and projects already-computed
fields; it deliberately contains no scoring or threshold logic.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.rag.evaluation.contracts import EvaluationOutcome, FormatParityDataset
from src.rag.evaluation.parser_parity import ParserCaseResultV1, ParserParityRunV1
from src.rag.evaluation.retrieval_rounds import RetrievalCaseObservationV1, RetrievalParityRunV1


REPORT_SCHEMA_VERSION = "rag_format_parity_report.v1"
TARGET_PROFILE_VERSION = "rag_format_parity_targets.v1"
RUNTIME_CONFIG_VERSION = "rag_format_parity_runtime.v1"
_FORMAT_ORDER = {"markdown": 0, "digital_pdf": 1, "scanned_pdf": 2}
_COMPLETED_OUTCOMES = {
    EvaluationOutcome.COMPLETED_PASS,
    EvaluationOutcome.COMPLETED_QUALITY_FAIL,
}
_PRIMARY_STAGES = ("parser", "ocr", "chunking", "retrieval", "provenance")
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "credential",
    "database_url",
    "dsn",
    "password",
    "private_reasoning",
    "prompt",
    "provider_payload",
    "raw_payload",
    "secret",
    "traceback",
)
_FORBIDDEN_VALUE = re.compile(
    r"(?:postgres(?:ql)?://|mysql://|redis://|sk-[a-z0-9_-]{8,}|/Users/|/home/|/private/tmp/|Traceback \(most recent call last\))",
    re.IGNORECASE,
)
_SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]{1,512}$")

FormatName = Literal["markdown", "digital_pdf", "scanned_pdf"]
PrimaryStage = Literal["parser", "ocr", "chunking", "retrieval", "provenance"]
GateMetric = Literal[
    "parse_success_rate",
    "markdown_anchor_coverage",
    "digital_pdf_anchor_coverage",
    "scanned_pdf_anchor_coverage",
    "critical_table_preservation",
    "pdf_locator_coverage",
    "retrieval_hit_at_5",
    "cross_format_hit_at_5_spread",
]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetGateV1(_FrozenModel):
    metric: GateMetric
    operator: Literal[">=", "<="]
    target: float = Field(ge=0.0, le=1.0)


class FormatParityTargetsV1(_FrozenModel):
    schema_version: Literal["rag_format_parity_targets.v1"] = TARGET_PROFILE_VERSION
    profile: Literal["rag_format_parity_targets.v1"] = TARGET_PROFILE_VERSION
    rationale: str
    gates: tuple[TargetGateV1, ...] = Field(min_length=8, max_length=8)


FORMAT_PARITY_TARGETS = FormatParityTargetsV1(
    rationale="Initial targets accepted in docs/quality/rag-quality-plan.md section 5.",
    gates=(
        TargetGateV1(metric="parse_success_rate", operator=">=", target=1.0),
        TargetGateV1(metric="markdown_anchor_coverage", operator=">=", target=1.0),
        TargetGateV1(metric="digital_pdf_anchor_coverage", operator=">=", target=1.0),
        TargetGateV1(metric="scanned_pdf_anchor_coverage", operator=">=", target=0.95),
        TargetGateV1(metric="critical_table_preservation", operator=">=", target=1.0),
        TargetGateV1(metric="pdf_locator_coverage", operator=">=", target=1.0),
        TargetGateV1(metric="retrieval_hit_at_5", operator=">=", target=0.9),
        TargetGateV1(metric="cross_format_hit_at_5_spread", operator="<=", target=0.1),
    ),
)


class FormatParityRuntimeConfigV1(_FrozenModel):
    """Allowlisted identity for a reportable evaluator execution."""

    schema_version: Literal["rag_format_parity_runtime.v1"] = RUNTIME_CONFIG_VERSION
    command: str = Field(min_length=1, max_length=512)
    execution_kind: Literal["full_provider", "contract_test", "fake"]
    tenant_id: str = Field(min_length=1, max_length=64)
    owner_marker: str = Field(min_length=1, max_length=128)
    run_token: str = Field(min_length=1, max_length=64)
    expected_rollout_version: int = Field(gt=0)
    generator_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_provider: str = Field(min_length=1, max_length=64)
    embedding_model: str = Field(min_length=1, max_length=128)
    embedding_dimensions: int = Field(gt=0, le=65536)
    retrieval_config_version: str = Field(min_length=1, max_length=128)
    rrf_config: str = Field(min_length=1, max_length=256)
    rewrite_config: str = Field(min_length=1, max_length=256)
    reranker_config: str = Field(min_length=1, max_length=256)
    no_evidence_threshold: float = Field(ge=0.0, le=1.0)
    parser_toolchain: tuple[str, ...] = Field(min_length=1, max_length=16)
    ocr_toolchain: tuple[str, ...] = Field(min_length=1, max_length=16)


class FixtureIdentityV1(_FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportInputsV1(_FrozenModel):
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_hashes: tuple[FixtureIdentityV1, ...]
    generator_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_baseline_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    configured_baseline_identity: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportPrerequisiteV1(_FrozenModel):
    name: str = Field(min_length=1, max_length=64)
    status: Literal["available", "unavailable", "not_required"]
    reason_code: str = Field(min_length=1, max_length=128)
    version: str | None = Field(default=None, max_length=128)


class MetricValuesV1(_FrozenModel):
    case_count: int = Field(ge=0)
    answerable_count: int = Field(ge=0)
    no_answer_count: int = Field(ge=0)
    hit_at_1: float = Field(ge=0.0, le=1.0)
    hit_at_3: float = Field(ge=0.0, le=1.0)
    hit_at_5: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    semantic_anchor_coverage: float = Field(ge=0.0, le=1.0)
    no_answer_correctness: float = Field(ge=0.0, le=1.0)
    fallback_correctness: float = Field(ge=0.0, le=1.0)
    locator_coverage: float = Field(ge=0.0, le=1.0)


class FormatMetricSliceV1(_FrozenModel):
    format: FormatName
    metrics: MetricValuesV1


class PolicyMetricSliceV1(_FrozenModel):
    policy_id: str
    metrics: MetricValuesV1


class CaseMetricSliceV1(_FrozenModel):
    policy_id: str
    case_id: str
    category: str
    metrics: MetricValuesV1


class ReportMetricsV1(_FrozenModel):
    overall: MetricValuesV1
    by_format: tuple[FormatMetricSliceV1, ...]
    by_policy: tuple[PolicyMetricSliceV1, ...]
    by_case: tuple[CaseMetricSliceV1, ...]
    cross_format_hit_at_5_spread: float = Field(ge=0.0, le=1.0)


class CaseResultRowV1(_FrozenModel):
    policy_id: str
    format: FormatName
    case_id: str
    category: str
    parser_status: Literal["passed", "failed", "not_applicable"]
    service_status: str
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    semantic_anchor_hits: int = Field(ge=0)
    semantic_anchor_total: int = Field(ge=0)
    no_answer_expected: bool
    no_answer_correct: bool
    fallback_correct: bool
    locator_expected: bool
    locator_covered: bool
    passed: bool
    primary_stage: PrimaryStage | None = None
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_primary_stage(self) -> CaseResultRowV1:
        if self.passed and self.primary_stage is not None:
            raise ValueError("passed case cannot have primary failure stage")
        if not self.passed and self.primary_stage is None:
            raise ValueError("completed miss requires one primary failure stage")
        return self


class PrimaryFailureV1(_FrozenModel):
    policy_id: str
    format: FormatName
    case_id: str
    primary_stage: PrimaryStage
    reason_codes: tuple[str, ...] = Field(min_length=1)


class GateObservationV1(_FrozenModel):
    metric: GateMetric
    operator: Literal[">=", "<="]
    target: float = Field(ge=0.0, le=1.0)
    observed: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None


class FormatParityReportV1(_FrozenModel):
    schema_version: Literal["rag_format_parity_report.v1"] = REPORT_SCHEMA_VERSION
    outcome: EvaluationOutcome
    baseline_eligible: bool
    generated_at: str
    reproducibility: Literal[
        "Exact inputs/config/toolchain and attributable observations; live-provider scores may vary between executions."
    ] = "Exact inputs/config/toolchain and attributable observations; live-provider scores may vary between executions."
    inputs: ReportInputsV1
    config: FormatParityRuntimeConfigV1
    prerequisites: tuple[ReportPrerequisiteV1, ...]
    targets: FormatParityTargetsV1
    gates: tuple[GateObservationV1, ...] = Field(min_length=8, max_length=8)
    metrics: ReportMetricsV1 | None
    case_rows: tuple[CaseResultRowV1, ...]
    failures: tuple[PrimaryFailureV1, ...]
    safe_reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_outcome_shape(self) -> FormatParityReportV1:
        completed = self.outcome in _COMPLETED_OUTCOMES
        if completed != (self.metrics is not None):
            raise ValueError("completed outcome and metrics must agree")
        if self.baseline_eligible and (not completed or self.config.execution_kind != "full_provider"):
            raise ValueError("baseline eligibility requires completed full-provider execution")
        if completed:
            failure_keys = {(item.policy_id, item.format, item.case_id) for item in self.failures}
            miss_keys = {(item.policy_id, item.format, item.case_id) for item in self.case_rows if not item.passed}
            if failure_keys != miss_keys or len(failure_keys) != len(self.failures):
                raise ValueError("each completed miss must have exactly one primary failure")
        elif self.case_rows or self.failures:
            raise ValueError("non-completed result cannot expose quality rows")
        return self


def build_format_parity_report(
    *,
    dataset: FormatParityDataset,
    parser_run: ParserParityRunV1,
    retrieval_run: RetrievalParityRunV1,
    runtime_config: FormatParityRuntimeConfigV1,
    generated_at: str,
) -> FormatParityReportV1:
    """Build the one canonical report object from typed intermediate runs."""

    inputs = _build_inputs(dataset, runtime_config=runtime_config)
    prerequisites = _merge_prerequisites(parser_run, retrieval_run)
    terminal = _terminal_input_outcome(parser_run.outcome, retrieval_run.outcome)
    identity_error = _identity_reason(dataset, parser_run=parser_run, retrieval_run=retrieval_run)
    if identity_error is not None:
        terminal = EvaluationOutcome.EXECUTION_ERROR
    if terminal not in _COMPLETED_OUTCOMES:
        reason = identity_error or f"input_outcome:{terminal.value}"
        return _validated_safe_report(
            FormatParityReportV1(
                outcome=terminal,
                baseline_eligible=False,
                generated_at=str(generated_at),
                inputs=inputs,
                config=runtime_config,
                prerequisites=prerequisites,
                targets=FORMAT_PARITY_TARGETS,
                gates=_unevaluated_gates(),
                metrics=None,
                case_rows=(),
                failures=(),
                safe_reason_codes=(reason,),
            )
        )

    indexed = _index_completed_cases(dataset, parser_run=parser_run, retrieval_run=retrieval_run)
    if isinstance(indexed, str):
        return _validated_safe_report(
            FormatParityReportV1(
                outcome=EvaluationOutcome.EXECUTION_ERROR,
                baseline_eligible=False,
                generated_at=str(generated_at),
                inputs=inputs,
                config=runtime_config,
                prerequisites=prerequisites,
                targets=FORMAT_PARITY_TARGETS,
                gates=_unevaluated_gates(),
                metrics=None,
                case_rows=(),
                failures=(),
                safe_reason_codes=(indexed,),
            )
        )

    case_rows = tuple(_case_row(parser_case, retrieval_case) for parser_case, retrieval_case in indexed)
    metrics = _aggregate_metrics(case_rows)
    gates = _evaluate_gates(parser_run, metrics=metrics)
    failures = tuple(
        PrimaryFailureV1(
            policy_id=row.policy_id,
            format=row.format,
            case_id=row.case_id,
            primary_stage=row.primary_stage,
            reason_codes=row.reason_codes,
        )
        for row in case_rows
        if not row.passed and row.primary_stage is not None
    )
    failed_quality = (
        terminal is EvaluationOutcome.COMPLETED_QUALITY_FAIL
        or bool(failures)
        or any(gate.passed is False for gate in gates)
    )
    outcome = EvaluationOutcome.COMPLETED_QUALITY_FAIL if failed_quality else EvaluationOutcome.COMPLETED_PASS
    baseline_eligible = (
        runtime_config.execution_kind == "full_provider"
        and parser_run.mode == "parser_direct"
        and retrieval_run.mode == "provider"
        and retrieval_run.baseline_eligible
        and all(item.status != "unavailable" for item in prerequisites)
    )
    return _validated_safe_report(
        FormatParityReportV1(
            outcome=outcome,
            baseline_eligible=baseline_eligible,
            generated_at=str(generated_at),
            inputs=inputs,
            config=runtime_config,
            prerequisites=prerequisites,
            targets=FORMAT_PARITY_TARGETS,
            gates=gates,
            metrics=metrics,
            case_rows=case_rows,
            failures=failures,
        )
    )


def load_format_parity_report(path: Path) -> FormatParityReportV1:
    """Load strict canonical JSON; never trust selected ad-hoc fields."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("format_parity_report_invalid") from None
    try:
        report = FormatParityReportV1.model_validate(raw)
    except ValidationError:
        raise
    return _validated_safe_report(report)


def _build_inputs(
    dataset: FormatParityDataset,
    *,
    runtime_config: FormatParityRuntimeConfigV1,
) -> ReportInputsV1:
    stable_config = runtime_config.model_dump(mode="json", exclude={"run_token"})
    configured_identity = _sha256_json(
        {
            "schema_version": "rag_format_parity_baseline_identity.v1",
            "dataset_baseline_identity": dataset.baseline_identity,
            "runtime_config": stable_config,
        }
    )
    return ReportInputsV1(
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        fixture_hashes=tuple(
            FixtureIdentityV1(path=path, sha256=digest) for path, digest in sorted(dataset.fixture_hashes.items())
        ),
        generator_identity_hash=runtime_config.generator_identity_hash,
        dataset_baseline_identity=dataset.baseline_identity,
        configured_baseline_identity=configured_identity,
    )


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _identity_reason(
    dataset: FormatParityDataset,
    *,
    parser_run: ParserParityRunV1,
    retrieval_run: RetrievalParityRunV1,
) -> str | None:
    expected = (dataset.manifest_hash, dataset.gold_hash, dataset.baseline_identity)
    parser_identity = (
        parser_run.inputs.manifest_hash,
        parser_run.inputs.gold_hash,
        parser_run.inputs.baseline_identity,
    )
    retrieval_identity = (
        retrieval_run.manifest_hash,
        retrieval_run.gold_hash,
        retrieval_run.baseline_identity,
    )
    if parser_identity != expected or retrieval_identity != expected:
        return "input_identity_mismatch"
    expected_fixtures = tuple(sorted(dataset.fixture_hashes.items()))
    parser_fixtures = tuple((item.path, item.sha256) for item in parser_run.inputs.fixture_hashes)
    if parser_fixtures != expected_fixtures:
        return "fixture_identity_mismatch"
    return None


def _terminal_input_outcome(
    parser_outcome: EvaluationOutcome,
    retrieval_outcome: EvaluationOutcome,
) -> EvaluationOutcome:
    outcomes = {parser_outcome, retrieval_outcome}
    if EvaluationOutcome.EXECUTION_ERROR in outcomes:
        return EvaluationOutcome.EXECUTION_ERROR
    if EvaluationOutcome.UNAVAILABLE_PREREQUISITE in outcomes:
        return EvaluationOutcome.UNAVAILABLE_PREREQUISITE
    if EvaluationOutcome.COMPLETED_QUALITY_FAIL in outcomes:
        return EvaluationOutcome.COMPLETED_QUALITY_FAIL
    return EvaluationOutcome.COMPLETED_PASS


def _merge_prerequisites(
    parser_run: ParserParityRunV1,
    retrieval_run: RetrievalParityRunV1,
) -> tuple[ReportPrerequisiteV1, ...]:
    rows: dict[str, ReportPrerequisiteV1] = {}
    for item in parser_run.prerequisites:
        rows[item.name] = ReportPrerequisiteV1(
            name=item.name,
            status=item.status,
            reason_code=item.reason_code,
            version=item.version,
        )
    for item in retrieval_run.prerequisites:
        rows[item.name] = ReportPrerequisiteV1(
            name=item.name,
            status="available" if item.available else "unavailable",
            reason_code=item.reason_code
            or ("prerequisite_available" if item.available else "prerequisite_unavailable"),
        )
    return tuple(rows[name] for name in sorted(rows))


def _index_completed_cases(
    dataset: FormatParityDataset,
    *,
    parser_run: ParserParityRunV1,
    retrieval_run: RetrievalParityRunV1,
) -> list[tuple[ParserCaseResultV1, RetrievalCaseObservationV1]] | str:
    expected = {
        (policy.doc_key, format_name, case.case_id)
        for policy in dataset.policies
        for format_name in _FORMAT_ORDER
        for case in policy.gold.cases
    }
    parser_cases: dict[tuple[str, str, str], ParserCaseResultV1] = {}
    parser_variant_keys: set[tuple[str, str]] = set()
    for variant in parser_run.variant_results:
        variant_key = (variant.policy_id, variant.variant)
        if variant_key in parser_variant_keys:
            return "completed_case_set_malformed"
        parser_variant_keys.add(variant_key)
        for case in variant.case_results:
            key = (case.policy_id, case.variant, case.case_id)
            if key in parser_cases:
                return "completed_case_set_malformed"
            parser_cases[key] = case

    retrieval_cases: dict[tuple[str, str, str], RetrievalCaseObservationV1] = {}
    seen_formats: set[str] = set()
    for round_result in retrieval_run.rounds:
        if round_result.round_format in seen_formats:
            return "completed_case_set_malformed"
        seen_formats.add(round_result.round_format)
        if not all(
            (
                round_result.pre_state_proved,
                round_result.exactly_three_current_proved,
                round_result.post_state_proved,
                round_result.immutable_history_preserved,
            )
        ):
            return "completed_isolation_proof_missing"
        for case in round_result.cases:
            key = (case.policy_id, round_result.round_format, case.case_id)
            if key in retrieval_cases:
                return "completed_case_set_malformed"
            retrieval_cases[key] = case
    if set(parser_cases) != expected or set(retrieval_cases) != expected:
        return "completed_case_set_malformed"
    return [
        (parser_cases[key], retrieval_cases[key])
        for key in sorted(expected, key=lambda item: (item[0], _FORMAT_ORDER[item[1]], item[2]))
    ]


def _case_row(
    parser_case: ParserCaseResultV1,
    retrieval_case: RetrievalCaseObservationV1,
) -> CaseResultRowV1:
    no_answer = retrieval_case.category == "no_answer"
    fallback_correct = retrieval_case.no_answer_correct if no_answer else retrieval_case.service_status != "no_evidence"
    primary_stage: PrimaryStage | None = None
    reasons: list[str] = []
    if not no_answer and parser_case.status == "failed":
        primary_stage = parser_case.primary_stage or "parser"
        reasons.extend(parser_case.reason_codes or ("parser_case_failed",))
    elif no_answer and not retrieval_case.no_answer_correct:
        primary_stage = "retrieval"
        reasons.append("no_answer_fallback_incorrect")
    elif not no_answer and not retrieval_case.hit_at_5:
        primary_stage = "retrieval"
        reasons.append("expected_policy_missing_top_5")
    elif not no_answer and retrieval_case.semantic_anchor_hits < retrieval_case.semantic_anchor_total:
        primary_stage = "chunking"
        reasons.append("retrieved_evidence_anchor_missing")
    elif retrieval_case.locator_expected and not retrieval_case.locator_covered:
        primary_stage = "provenance"
        reasons.append("retrieved_locator_missing")
    elif not fallback_correct:
        primary_stage = "retrieval"
        reasons.append("fallback_incorrect")
    passed = primary_stage is None
    return CaseResultRowV1(
        policy_id=retrieval_case.policy_id,
        format=parser_case.variant,
        case_id=retrieval_case.case_id,
        category=retrieval_case.category,
        parser_status=parser_case.status,
        service_status=retrieval_case.service_status,
        hit_at_1=retrieval_case.hit_at_1,
        hit_at_3=retrieval_case.hit_at_3,
        hit_at_5=retrieval_case.hit_at_5,
        reciprocal_rank=retrieval_case.reciprocal_rank,
        semantic_anchor_hits=retrieval_case.semantic_anchor_hits,
        semantic_anchor_total=retrieval_case.semantic_anchor_total,
        no_answer_expected=no_answer,
        no_answer_correct=retrieval_case.no_answer_correct,
        fallback_correct=fallback_correct,
        locator_expected=retrieval_case.locator_expected,
        locator_covered=retrieval_case.locator_covered,
        passed=passed,
        primary_stage=primary_stage,
        reason_codes=tuple(sorted(set(reasons))),
    )


def _aggregate_metrics(rows: Sequence[CaseResultRowV1]) -> ReportMetricsV1:
    by_format = defaultdict(list)
    by_policy = defaultdict(list)
    by_case = defaultdict(list)
    for row in rows:
        by_format[row.format].append(row)
        by_policy[row.policy_id].append(row)
        by_case[(row.policy_id, row.case_id, row.category)].append(row)
    format_rows = tuple(
        FormatMetricSliceV1(format=name, metrics=_metric_values(by_format[name]))
        for name in sorted(by_format, key=_FORMAT_ORDER.__getitem__)
    )
    format_hit_5 = [row.metrics.hit_at_5 for row in format_rows]
    spread = round(max(format_hit_5) - min(format_hit_5), 6) if format_hit_5 else 0.0
    return ReportMetricsV1(
        overall=_metric_values(rows),
        by_format=format_rows,
        by_policy=tuple(
            PolicyMetricSliceV1(policy_id=name, metrics=_metric_values(by_policy[name])) for name in sorted(by_policy)
        ),
        by_case=tuple(
            CaseMetricSliceV1(
                policy_id=key[0],
                case_id=key[1],
                category=key[2],
                metrics=_metric_values(by_case[key]),
            )
            for key in sorted(by_case)
        ),
        cross_format_hit_at_5_spread=spread,
    )


def _metric_values(rows: Sequence[CaseResultRowV1]) -> MetricValuesV1:
    answerable = [row for row in rows if not row.no_answer_expected]
    no_answer = [row for row in rows if row.no_answer_expected]
    anchor_total = sum(row.semantic_anchor_total for row in answerable)
    locator_rows = [row for row in answerable if row.locator_expected]
    return MetricValuesV1(
        case_count=len(rows),
        answerable_count=len(answerable),
        no_answer_count=len(no_answer),
        hit_at_1=_rate(row.hit_at_1 for row in answerable),
        hit_at_3=_rate(row.hit_at_3 for row in answerable),
        hit_at_5=_rate(row.hit_at_5 for row in answerable),
        mrr=_mean(row.reciprocal_rank for row in answerable),
        semantic_anchor_coverage=(
            _rounded(sum(row.semantic_anchor_hits for row in answerable) / anchor_total) if anchor_total else 0.0
        ),
        no_answer_correctness=_rate(row.no_answer_correct for row in no_answer),
        fallback_correctness=_rate(row.fallback_correct for row in rows),
        locator_coverage=_rate(row.locator_covered for row in locator_rows),
    )


def _rate(values: Iterable[bool]) -> float:
    items = list(values)
    return _rounded(sum(bool(item) for item in items) / len(items)) if items else 0.0


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return _rounded(sum(items) / len(items)) if items else 0.0


def _rounded(value: float) -> float:
    return round(float(value), 6)


def _evaluate_gates(
    parser_run: ParserParityRunV1,
    *,
    metrics: ReportMetricsV1,
) -> tuple[GateObservationV1, ...]:
    variants = parser_run.variant_results
    values: dict[GateMetric, float] = {
        "parse_success_rate": _rate(item.parse_status.status == "passed" for item in variants),
        "markdown_anchor_coverage": _dimension_recall(
            item.semantic_anchors for item in variants if item.variant == "markdown"
        ),
        "digital_pdf_anchor_coverage": _dimension_recall(
            item.semantic_anchors for item in variants if item.variant == "digital_pdf"
        ),
        "scanned_pdf_anchor_coverage": _dimension_recall(
            item.semantic_anchors for item in variants if item.variant == "scanned_pdf"
        ),
        "critical_table_preservation": _dimension_recall(item.critical_tables for item in variants),
        "pdf_locator_coverage": _dimension_recall(
            item.provenance_locators for item in variants if item.variant != "markdown"
        ),
        "retrieval_hit_at_5": metrics.overall.hit_at_5,
        "cross_format_hit_at_5_spread": metrics.cross_format_hit_at_5_spread,
    }
    return tuple(
        GateObservationV1(
            metric=gate.metric,
            operator=gate.operator,
            target=gate.target,
            observed=values[gate.metric],
            passed=(
                values[gate.metric] >= gate.target if gate.operator == ">=" else values[gate.metric] <= gate.target
            ),
        )
        for gate in FORMAT_PARITY_TARGETS.gates
    )


def _dimension_recall(dimensions: Iterable[Any]) -> float:
    rows = list(dimensions)
    expected = sum(int(item.expected) for item in rows)
    return _rounded(sum(int(item.matched) for item in rows) / expected) if expected else 0.0


def _unevaluated_gates() -> tuple[GateObservationV1, ...]:
    return tuple(
        GateObservationV1(
            metric=gate.metric,
            operator=gate.operator,
            target=gate.target,
            observed=None,
            passed=None,
        )
        for gate in FORMAT_PARITY_TARGETS.gates
    )


def _validated_safe_report(report: FormatParityReportV1) -> FormatParityReportV1:
    _scan_safe(report.model_dump(mode="json"))
    return report


def _scan_safe(value: Any, *, key_path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError("unsafe_report_key")
            _scan_safe(item, key_path=(*key_path, str(key)))
        return
    if isinstance(value, list | tuple):
        for item in value:
            _scan_safe(item, key_path=key_path)
        return
    if isinstance(value, str) and (not _SAFE_TEXT.fullmatch(value) or _FORBIDDEN_VALUE.search(value)):
        raise ValueError("unsafe_report_value")


def render_markdown(report: Mapping[str, Any]) -> str:
    """Deterministically project a strict canonical report without scoring."""

    validated = _validated_safe_report(FormatParityReportV1.model_validate(report))
    lines = [
        "# RAG Format Parity Baseline",
        "",
        f"Canonical schema: `{validated.schema_version}`",
        f"Outcome: `{validated.outcome.value}`",
        f"Baseline eligible: `{'true' if validated.baseline_eligible else 'false'}`",
        f"Generated at: `{validated.generated_at}`",
        f"Target profile: `{validated.targets.profile}`",
        "",
        "Provider reproducibility records exact inputs/config/toolchain and attributable observations; it does not promise bit-identical scores across live runs.",
        "",
        "## Identity and configuration",
        "",
        f"- Manifest SHA-256: `{validated.inputs.manifest_hash}`",
        f"- Gold SHA-256: `{validated.inputs.gold_hash}`",
        f"- Dataset baseline identity: `{validated.inputs.dataset_baseline_identity}`",
        f"- Configured baseline identity: `{validated.inputs.configured_baseline_identity}`",
        f"- Execution kind: `{validated.config.execution_kind}`",
        f"- Command: `{validated.config.command}`",
        f"- Embedding: `{validated.config.embedding_provider}/{validated.config.embedding_model}` ({validated.config.embedding_dimensions})",
        f"- Retrieval: `{validated.config.retrieval_config_version}`",
        f"- RRF: `{validated.config.rrf_config}`",
        f"- Rewrite: `{validated.config.rewrite_config}`",
        f"- Reranker: `{validated.config.reranker_config}`",
        f"- Rollout version: `{validated.config.expected_rollout_version}`",
        "",
        "## Gates",
        "",
        "| Metric | Operator | Target | Observed | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for gate in validated.gates:
        observed = "n/a" if gate.observed is None else f"{gate.observed:.6f}"
        status = "NOT_EVALUATED" if gate.passed is None else ("PASS" if gate.passed else "FAIL")
        lines.append(f"| {gate.metric} | {gate.operator} | {gate.target:.6f} | {observed} | {status} |")
    lines.extend(["", "## Retrieval metrics", ""])
    if validated.metrics is None:
        lines.append("No quality metrics were produced for this unavailable/error execution.")
    else:
        lines.extend(
            [
                "| Slice | Hit@1 | Hit@3 | Hit@5 | MRR | Anchor | No-answer | Fallback | Locator |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                _markdown_metric_row("overall", validated.metrics.overall),
            ]
        )
        for item in validated.metrics.by_format:
            lines.append(_markdown_metric_row(f"format:{item.format}", item.metrics))
        for item in validated.metrics.by_policy:
            lines.append(_markdown_metric_row(f"policy:{item.policy_id}", item.metrics))
        for item in validated.metrics.by_case:
            lines.append(_markdown_metric_row(f"case:{item.case_id}", item.metrics))
    lines.extend(
        [
            "",
            "## Failure attribution",
            "",
            "| Policy | Format | Case | Primary stage | Reason codes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if not validated.failures:
        lines.append("| — | — | — | — | none |")
    else:
        for item in validated.failures:
            lines.append(
                f"| {item.policy_id} | {item.format} | {item.case_id} | {item.primary_stage} | {', '.join(item.reason_codes)} |"
            )
    lines.extend(["", "## Prerequisites", "", "| Name | Status | Reason | Version |", "| --- | --- | --- | --- |"])
    for item in validated.prerequisites:
        lines.append(f"| {item.name} | {item.status} | {item.reason_code} | {item.version or 'n/a'} |")
    return "\n".join(lines) + "\n"


def _markdown_metric_row(label: str, metrics: MetricValuesV1) -> str:
    return (
        f"| {label} | {metrics.hit_at_1:.6f} | {metrics.hit_at_3:.6f} | "
        f"{metrics.hit_at_5:.6f} | {metrics.mrr:.6f} | "
        f"{metrics.semantic_anchor_coverage:.6f} | {metrics.no_answer_correctness:.6f} | "
        f"{metrics.fallback_correctness:.6f} | {metrics.locator_coverage:.6f} |"
    )
