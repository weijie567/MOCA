"""Exact same-run character/token A-B selection and immutable evidence.

All decision arithmetic is integer, :class:`fractions.Fraction`, or
:class:`decimal.Decimal`. Six-place formatting exists only in the Markdown
projection and never feeds a gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Literal, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.rag.evaluation.reporting import canonical_report_json_bytes, validate_safe_report_payload


RUN_SCHEMA_VERSION = "rag_token_chunk_ab.v1"
SELECTION_SCHEMA_VERSION = "rag_token_chunk_selection.v1"
GATE_PROFILE_VERSION = "rag_token_chunk_ab.v1"
SEALED_MANIFEST_HASH = "e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"
SEALED_GOLD_HASH = "c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"
SEALED_DATASET_BASELINE_IDENTITY = "3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"
SEALED_ANSWERABLE_CASE_COUNT = 45
SEALED_TOTAL_CASE_COUNT = 54
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_FORMAT_ORDER = ("markdown", "digital_pdf", "scanned_pdf")
_FRESH_PARITY_MAXIMUM_AGE = timedelta(hours=24)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExactRatioV1(_FrozenModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def from_fraction(cls, value: Fraction) -> ExactRatioV1:
        if value < 0:
            raise ValueError("negative_ratio")
        return cls(numerator=value.numerator, denominator=value.denominator)


class ABFormatMetricsV1(_FrozenModel):
    format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    hit_at_1: ExactRatioV1
    hit_at_3: ExactRatioV1
    hit_at_5: ExactRatioV1
    mrr: ExactRatioV1

    @model_validator(mode="after")
    def validate_rates(self) -> ABFormatMetricsV1:
        if any(value.fraction > 1 for value in (self.hit_at_1, self.hit_at_3, self.hit_at_5, self.mrr)):
            raise ValueError("format_metric_out_of_range")
        return self


class ABQualityMetricsV1(_FrozenModel):
    answerable_case_count: Literal[45]
    total_case_count: Literal[54]
    hit_at_1: ExactRatioV1
    hit_at_3: ExactRatioV1
    hit_at_5: ExactRatioV1
    mrr: ExactRatioV1
    semantic_anchor_coverage: ExactRatioV1
    locator_coverage: ExactRatioV1
    fallback_correctness: ExactRatioV1
    by_format: tuple[ABFormatMetricsV1, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_quality(self) -> ABQualityMetricsV1:
        ratios = (
            self.hit_at_1,
            self.hit_at_3,
            self.hit_at_5,
            self.mrr,
            self.semantic_anchor_coverage,
            self.locator_coverage,
            self.fallback_correctness,
        )
        if any(value.fraction > 1 for value in ratios):
            raise ValueError("quality_metric_out_of_range")
        if tuple(item.format for item in self.by_format) != _FORMAT_ORDER:
            raise ValueError("format_metric_order_mismatch")
        return self

    @property
    def hit_at_5_spread(self) -> ExactRatioV1:
        values = [item.hit_at_5.fraction for item in self.by_format]
        return ExactRatioV1.from_fraction(max(values) - min(values))


class ABEmbeddingCostV1(_FrozenModel):
    basis_version: str = Field(min_length=1, max_length=128)
    currency: Literal["CNY", "USD"]
    unit_tokens: int = Field(gt=0)
    price_per_unit: Decimal = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    observed_cost: Decimal | None = Field(default=None, ge=0)
    observed_cost_status: Literal["provider_reported", "unavailable"]

    @model_validator(mode="after")
    def validate_observed_cost(self) -> ABEmbeddingCostV1:
        if (self.observed_cost is None) != (self.observed_cost_status == "unavailable"):
            raise ValueError("observed_cost_status_mismatch")
        return self


class ABResourceMetricsV1(_FrozenModel):
    chunk_count: int = Field(gt=0)
    duplicate_count: int = Field(ge=0)
    offline_embedding_tokens: int = Field(gt=0)
    provider_embedding_tokens: int | None = Field(default=None, ge=0)
    provider_tokens_status: Literal["provider_reported", "unavailable"]
    retrieval_duration_ms: Decimal = Field(ge=0)
    embedding_cost: ABEmbeddingCostV1

    @model_validator(mode="after")
    def validate_resources(self) -> ABResourceMetricsV1:
        if self.duplicate_count > self.chunk_count:
            raise ValueError("duplicate_count_invalid")
        if (self.provider_embedding_tokens is None) != (self.provider_tokens_status == "unavailable"):
            raise ValueError("provider_token_status_mismatch")
        expected_cost = (
            Decimal(self.offline_embedding_tokens)
            * self.embedding_cost.price_per_unit
            / Decimal(self.embedding_cost.unit_tokens)
        )
        if self.embedding_cost.estimated_cost != expected_cost:
            raise ValueError("estimated_cost_mismatch")
        return self

    @property
    def duplicate_rate(self) -> ExactRatioV1:
        return ExactRatioV1(numerator=self.duplicate_count, denominator=self.chunk_count)


class ABCandidateObservationV1(_FrozenModel):
    role: Literal["incumbent", "candidate"]
    assembler: Literal["CharacterCompatibilityAssembler", "PolicyEmbeddingInputAssembler"]
    config_schema_version: str = Field(min_length=1, max_length=128)
    config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    corpus_version_id: UUID
    deterministic_rebuild_sha256: str = Field(pattern=_SHA256_PATTERN)
    quality: ABQualityMetricsV1
    resources: ABResourceMetricsV1

    @model_validator(mode="after")
    def validate_role_assembler(self) -> ABCandidateObservationV1:
        expected = "CharacterCompatibilityAssembler" if self.role == "incumbent" else "PolicyEmbeddingInputAssembler"
        if self.assembler != expected:
            raise ValueError("candidate_assembler_mismatch")
        return self


class ABInputIdentityV1(_FrozenModel):
    manifest_hash: Literal["e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"] = SEALED_MANIFEST_HASH
    gold_hash: Literal["c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"] = SEALED_GOLD_HASH
    dataset_baseline_identity: Literal["3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"] = (
        SEALED_DATASET_BASELINE_IDENTITY
    )
    baseline_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    ordered_questions_sha256: str = Field(pattern=_SHA256_PATTERN)
    answerable_case_count: Literal[45] = SEALED_ANSWERABLE_CASE_COUNT
    total_case_count: Literal[54] = SEALED_TOTAL_CASE_COUNT


class ABNamespaceV1(_FrozenModel):
    corpus_version_id: UUID
    round_owner: str = Field(min_length=1, max_length=128)


class ABRuntimeConfigV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_ab_runtime.v1"] = "rag_token_chunk_ab_runtime.v1"
    execution_kind: Literal["full_provider", "contract_test"]
    tenant_id: UUID
    owner_marker: Literal["moca.rag_token_chunk_ab.v1"]
    provider: Literal["dashscope"]
    embedding_model: Literal["text-embedding-v4"]
    embedding_dimensions: Literal[1024]
    provider_runtime_identity: str = Field(min_length=1, max_length=128)
    retrieval_config_version: str = Field(min_length=1, max_length=128)
    rrf_config: str = Field(min_length=1, max_length=256)
    rewrite_config: str = Field(min_length=1, max_length=256)
    reranker_config: str = Field(min_length=1, max_length=256)
    no_evidence_threshold: Decimal = Field(ge=0, le=1)
    incumbent: ABNamespaceV1
    candidate: ABNamespaceV1

    @model_validator(mode="after")
    def validate_isolation(self) -> ABRuntimeConfigV1:
        if (
            self.incumbent.corpus_version_id == self.candidate.corpus_version_id
            or self.incumbent.round_owner == self.candidate.round_owner
        ):
            raise ValueError("ab_namespace_not_isolated")
        return self


class ABParityEvidenceV1(_FrozenModel):
    report_sha256: str = Field(pattern=_SHA256_PATTERN)
    run_id: UUID
    captured_at: datetime
    status: Literal["passed", "quarantined", "unavailable"]
    config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    probe_fixture_sha256: str = Field(pattern=_SHA256_PATTERN)
    submitted_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    reason_code: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_parity_status(self) -> ABParityEvidenceV1:
        if self.captured_at.tzinfo is None:
            raise ValueError("parity_capture_time_invalid")
        expected = {
            "passed": {"exact_match"},
            "quarantined": {"single_count_mismatch", "aggregate_count_mismatch"},
            "unavailable": {
                "provider_credentials_unavailable",
                "provider_request_unavailable",
                "provider_usage_unavailable",
            },
        }
        if self.reason_code not in expected[self.status]:
            raise ValueError("parity_reason_mismatch")
        return self


class ABHardProofsV1(_FrozenModel):
    zero_final_input_overflow: bool
    persisted_counts_recomputed: bool
    deterministic_rebuild: bool
    complete_source_coverage: bool
    immutable_identity_replay: bool
    interrupted_resume_safe: bool
    stale_cas_safe: bool
    atomic_cutover_rollback_safe: bool
    evaluation_cleanup_isolated: bool
    fresh_provider_parity_passed: bool

    @property
    def all_passed(self) -> bool:
        return all(self.model_dump().values())


GateName = Literal[
    "hit_at_5",
    "cross_format_hit_at_5_spread",
    "hit_at_1_non_regression",
    "hit_at_3_non_regression",
    "mrr_non_regression",
    "format_hit_at_5_markdown",
    "format_hit_at_5_digital_pdf",
    "format_hit_at_5_scanned_pdf",
    "semantic_anchor_non_regression",
    "locator_non_regression",
    "fallback_non_regression",
    "duplicate_rate",
    "chunk_count_ratio",
    "embedding_token_ratio",
]


class ABGateObservationV1(_FrozenModel):
    profile_version: Literal["rag_token_chunk_ab.v1"] = GATE_PROFILE_VERSION
    gate: GateName
    operator: Literal[">=", "<="]
    candidate: ExactRatioV1
    incumbent: ExactRatioV1 | None
    limit: ExactRatioV1
    passed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> ABGateObservationV1:
        expected = (
            self.candidate.fraction >= self.limit.fraction
            if self.operator == ">="
            else self.candidate.fraction <= self.limit.fraction
        )
        if self.passed is not expected:
            raise ValueError("gate_decision_mismatch")
        return self


class TerminalABRunV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_ab.v1"] = RUN_SCHEMA_VERSION
    run_id: UUID
    generated_at: datetime
    outcome: Literal["selected_pass", "candidate_failed", "unavailable", "execution_error"]
    failure_class: Literal["quality_fail", "safety_fail"] | None
    terminal_stage: Literal["selection", "quality", "safety", "parity", "provider", "execution"]
    safe_reason_codes: tuple[str, ...] = ()
    inputs: ABInputIdentityV1
    runtime: ABRuntimeConfigV1
    parity: ABParityEvidenceV1
    incumbent: ABCandidateObservationV1 | None
    candidate: ABCandidateObservationV1 | None
    hard_proofs: ABHardProofsV1 | None
    gates: tuple[ABGateObservationV1, ...]

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> TerminalABRunV1:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at_invalid")
        completed = self.outcome in {"selected_pass", "candidate_failed"}
        if completed:
            if None in (self.incumbent, self.candidate, self.hard_proofs) or len(self.gates) != 14:
                raise ValueError("completed_observations_missing")
            assert self.incumbent is not None and self.candidate is not None and self.hard_proofs is not None
            if self.incumbent.role != "incumbent" or self.candidate.role != "candidate":
                raise ValueError("candidate_role_mismatch")
            if (
                self.incumbent.corpus_version_id != self.runtime.incumbent.corpus_version_id
                or self.candidate.corpus_version_id != self.runtime.candidate.corpus_version_id
                or self.candidate.config_fingerprint != self.parity.config_fingerprint
            ):
                raise ValueError("candidate_runtime_identity_mismatch")
            recomputed = evaluate_exact_gates(incumbent=self.incumbent, candidate=self.candidate)
            if self.gates != recomputed:
                raise ValueError("gate_observation_mismatch")
            age = self.generated_at.astimezone(UTC) - self.parity.captured_at.astimezone(UTC)
            parity_fresh = (
                self.parity.status == "passed"
                and timedelta(0) <= age <= _FRESH_PARITY_MAXIMUM_AGE
                and self.hard_proofs.fresh_provider_parity_passed
            )
            if not parity_fresh:
                raise ValueError("fresh_passed_parity_required")
            safety_failed = not self.hard_proofs.all_passed
            quality_failed = any(not gate.passed for gate in self.gates)
            if self.outcome == "selected_pass":
                if self.runtime.execution_kind != "full_provider":
                    raise ValueError("selected_pass_requires_full_provider")
                if safety_failed or quality_failed or self.failure_class is not None or self.safe_reason_codes:
                    raise ValueError("selected_pass_shape_invalid")
                if self.terminal_stage != "selection":
                    raise ValueError("selected_pass_stage_invalid")
            else:
                expected_class = "safety_fail" if safety_failed else "quality_fail"
                expected_stage = "safety" if safety_failed else "quality"
                expected_reason = "hard_safety_gate_failed" if safety_failed else "quality_gate_failed"
                if (
                    self.failure_class != expected_class
                    or self.terminal_stage != expected_stage
                    or self.safe_reason_codes != (expected_reason,)
                    or (not safety_failed and not quality_failed)
                ):
                    raise ValueError("candidate_failed_shape_invalid")
        else:
            if any(value is not None for value in (self.incumbent, self.candidate, self.hard_proofs)) or self.gates:
                raise ValueError("non_completed_quality_evidence")
            if self.failure_class is not None or not self.safe_reason_codes:
                raise ValueError("non_completed_reason_missing")
            expected_stages = {"unavailable": {"parity", "provider"}, "execution_error": {"execution"}}
            if self.terminal_stage not in expected_stages[self.outcome]:
                raise ValueError("non_completed_stage_invalid")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


class ABSelectionBindingV1(_FrozenModel):
    selection_id: UUID
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)


class ABSelectionDecisionV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_selection.v1"] = SELECTION_SCHEMA_VERSION
    selection_id: UUID
    selected_at: datetime
    outcome: Literal["selected_pass"] = "selected_pass"
    terminal_run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    manifest_hash: str = Field(pattern=_DIGEST_PATTERN)
    gold_hash: str = Field(pattern=_DIGEST_PATTERN)
    dataset_baseline_identity: str = Field(pattern=_DIGEST_PATTERN)
    runtime_config_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_observation_sha256: str = Field(pattern=_SHA256_PATTERN)
    exact_gate_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    decision_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_decision_hash(self) -> ABSelectionDecisionV1:
        if self.selected_at.tzinfo is None:
            raise ValueError("selection_time_invalid")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"decision_payload_sha256"}))
        if self.decision_payload_sha256 != expected:
            raise ValueError("selection_decision_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


@dataclass(frozen=True, slots=True)
class ImmutableArtifactPairV1:
    json_path: Path
    markdown_path: Path
    json_sha256: str
    markdown_sha256: str


def evaluate_exact_gates(
    *,
    incumbent: ABCandidateObservationV1,
    candidate: ABCandidateObservationV1,
) -> tuple[ABGateObservationV1, ...]:
    """Apply the fixed profile using exact rational comparisons only."""

    if incumbent.role != "incumbent" or candidate.role != "candidate":
        raise ValueError("candidate_role_mismatch")
    rows: list[ABGateObservationV1] = []

    def append(
        gate: GateName,
        operator: Literal[">=", "<="],
        candidate_value: Fraction,
        incumbent_value: Fraction | None,
        limit: Fraction,
    ) -> None:
        rows.append(
            ABGateObservationV1(
                gate=gate,
                operator=operator,
                candidate=ExactRatioV1.from_fraction(candidate_value),
                incumbent=(None if incumbent_value is None else ExactRatioV1.from_fraction(incumbent_value)),
                limit=ExactRatioV1.from_fraction(limit),
                passed=candidate_value >= limit if operator == ">=" else candidate_value <= limit,
            )
        )

    incumbent_quality = incumbent.quality
    candidate_quality = candidate.quality
    append(
        "hit_at_5",
        ">=",
        candidate_quality.hit_at_5.fraction,
        incumbent_quality.hit_at_5.fraction,
        max(Fraction(9, 10), incumbent_quality.hit_at_5.fraction),
    )
    append(
        "cross_format_hit_at_5_spread",
        "<=",
        candidate_quality.hit_at_5_spread.fraction,
        incumbent_quality.hit_at_5_spread.fraction,
        min(Fraction(1, 10), incumbent_quality.hit_at_5_spread.fraction),
    )
    for gate, attribute in (
        ("hit_at_1_non_regression", "hit_at_1"),
        ("hit_at_3_non_regression", "hit_at_3"),
        ("mrr_non_regression", "mrr"),
    ):
        incumbent_value = getattr(incumbent_quality, attribute).fraction
        append(
            gate,
            ">=",
            getattr(candidate_quality, attribute).fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 45)),
        )
    for incumbent_format, candidate_format in zip(
        incumbent_quality.by_format, candidate_quality.by_format, strict=True
    ):
        incumbent_value = incumbent_format.hit_at_5.fraction
        append(
            f"format_hit_at_5_{incumbent_format.format}",  # type: ignore[arg-type]
            ">=",
            candidate_format.hit_at_5.fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 15)),
        )
    for gate, attribute in (
        ("semantic_anchor_non_regression", "semantic_anchor_coverage"),
        ("locator_non_regression", "locator_coverage"),
        ("fallback_non_regression", "fallback_correctness"),
    ):
        incumbent_value = getattr(incumbent_quality, attribute).fraction
        append(
            gate,
            ">=",
            getattr(candidate_quality, attribute).fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 54)),
        )
    append(
        "duplicate_rate",
        "<=",
        candidate.resources.duplicate_rate.fraction,
        incumbent.resources.duplicate_rate.fraction,
        incumbent.resources.duplicate_rate.fraction + Fraction(1, 50),
    )
    append(
        "chunk_count_ratio",
        "<=",
        Fraction(candidate.resources.chunk_count, incumbent.resources.chunk_count),
        Fraction(1),
        Fraction(3, 2),
    )
    append(
        "embedding_token_ratio",
        "<=",
        Fraction(
            candidate.resources.offline_embedding_tokens,
            incumbent.resources.offline_embedding_tokens,
        ),
        Fraction(1),
        Fraction(5, 4),
    )
    return tuple(rows)


def build_terminal_ab_run(
    *,
    run_id: UUID,
    generated_at: datetime,
    inputs: ABInputIdentityV1,
    runtime: ABRuntimeConfigV1,
    parity: ABParityEvidenceV1,
    incumbent: ABCandidateObservationV1,
    candidate: ABCandidateObservationV1,
    hard_proofs: ABHardProofsV1,
) -> TerminalABRunV1:
    if parity.status != "passed":
        return TerminalABRunV1(
            run_id=run_id,
            generated_at=generated_at,
            outcome="unavailable",
            failure_class=None,
            terminal_stage="parity",
            safe_reason_codes=(parity.reason_code,),
            inputs=inputs,
            runtime=runtime,
            parity=parity,
            incumbent=None,
            candidate=None,
            hard_proofs=None,
            gates=(),
        )
    gates = evaluate_exact_gates(incumbent=incumbent, candidate=candidate)
    if not hard_proofs.all_passed:
        outcome = "candidate_failed"
        failure_class = "safety_fail"
        terminal_stage = "safety"
        reasons = ("hard_safety_gate_failed",)
    elif any(not gate.passed for gate in gates):
        outcome = "candidate_failed"
        failure_class = "quality_fail"
        terminal_stage = "quality"
        reasons = ("quality_gate_failed",)
    else:
        outcome = "selected_pass"
        failure_class = None
        terminal_stage = "selection"
        reasons = ()
    return TerminalABRunV1(
        run_id=run_id,
        generated_at=generated_at,
        outcome=outcome,
        failure_class=failure_class,
        terminal_stage=terminal_stage,
        safe_reason_codes=reasons,
        inputs=inputs,
        runtime=runtime,
        parity=parity,
        incumbent=incumbent,
        candidate=candidate,
        hard_proofs=hard_proofs,
        gates=gates,
    )


def render_terminal_markdown(payload: Mapping[str, Any]) -> str:
    report = TerminalABRunV1.model_validate(payload)
    lines = [
        "# RAG Token Chunk A-B Run",
        "",
        f"Schema: `{report.schema_version}`",
        f"Run: `{report.run_id}`",
        f"Outcome: `{report.outcome}`",
        f"Failure class: `{report.failure_class or 'none'}`",
        f"Terminal stage: `{report.terminal_stage}`",
        "",
        "## Sealed inputs",
        "",
        f"- Manifest SHA-256: `{report.inputs.manifest_hash}`",
        f"- Gold SHA-256: `{report.inputs.gold_hash}`",
        f"- Dataset baseline identity: `{report.inputs.dataset_baseline_identity}`",
        f"- Cases: answerable={report.inputs.answerable_case_count}; total={report.inputs.total_case_count}",
        f"- Provider parity report SHA-256: `{report.parity.report_sha256}`",
        "",
        "## Exact gates",
        "",
        "| Gate | Candidate | Incumbent | Operator | Exact limit | Status |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    if not report.gates:
        lines.append("| not evaluated | n/a | n/a | n/a | n/a | NOT_EVALUATED |")
    for gate in report.gates:
        incumbent = "n/a" if gate.incumbent is None else _ratio_display(gate.incumbent)
        lines.append(
            f"| {gate.gate} | {_ratio_display(gate.candidate)} | {incumbent} | "
            f"{gate.operator} | {_ratio_display(gate.limit)} | {'PASS' if gate.passed else 'FAIL'} |"
        )
    lines.extend(["", "## Safe terminal reasons", ""])
    lines.append(", ".join(report.safe_reason_codes) if report.safe_reason_codes else "none")
    return "\n".join(lines) + "\n"


def render_selection_markdown(payload: Mapping[str, Any]) -> str:
    decision = ABSelectionDecisionV1.model_validate(payload)
    return "\n".join(
        (
            "# RAG Token Chunk Selection",
            "",
            f"Schema: `{decision.schema_version}`",
            f"Selection: `{decision.selection_id}`",
            f"Outcome: `{decision.outcome}`",
            f"Terminal run: `{decision.terminal_run_id}`",
            f"Terminal run SHA-256: `{decision.terminal_run_sha256}`",
            f"Provider parity report SHA-256: `{decision.provider_parity_report_sha256}`",
            f"Candidate corpus: `{decision.candidate_corpus_version_id}`",
            f"Candidate config observation SHA-256: `{decision.candidate_observation_sha256}`",
            f"Exact gate profile SHA-256: `{decision.exact_gate_profile_sha256}`",
            f"Decision payload SHA-256: `{decision.decision_payload_sha256}`",
            "",
        )
    )


def write_terminal_run_create_only(report: TerminalABRunV1, *, root: Path) -> ImmutableArtifactPairV1:
    validated = TerminalABRunV1.model_validate(report.model_dump(mode="json"))
    return _write_create_only_pair(
        json_path=root / "runs" / f"{validated.run_id}.json",
        markdown_path=root / "runs" / f"{validated.run_id}.md",
        json_payload=canonical_report_json_bytes(validated.model_dump(mode="json")),
        markdown_payload=render_terminal_markdown(validated.model_dump(mode="json")).encode(),
    )


def load_terminal_ab_run(path: Path) -> TerminalABRunV1:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, TypeError, ValueError):
        raise ValueError("terminal_report_invalid") from None
    try:
        return TerminalABRunV1.model_validate(payload)
    except ValidationError:
        raise


def write_selection_create_only(
    report: TerminalABRunV1,
    *,
    binding: ABSelectionBindingV1,
    terminal_run_sha256: str,
    root: Path,
) -> ImmutableArtifactPairV1:
    if report.outcome != "selected_pass":
        raise ValueError("selected_pass_required")
    validated = TerminalABRunV1.model_validate(report.model_dump(mode="json"))
    if binding.tenant_id != validated.runtime.tenant_id:
        raise ValueError("selection_binding_mismatch")
    if validated.candidate is None or binding.candidate_corpus_version_id != validated.candidate.corpus_version_id:
        raise ValueError("selection_binding_mismatch")
    if not _valid_sha256(terminal_run_sha256):
        raise ValueError("terminal_run_hash_invalid")
    base: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selection_id": binding.selection_id,
        "selected_at": validated.generated_at,
        "outcome": "selected_pass",
        "terminal_run_id": validated.run_id,
        "terminal_run_sha256": terminal_run_sha256,
        "provider_parity_report_sha256": validated.parity.report_sha256,
        "tenant_id": binding.tenant_id,
        "candidate_corpus_version_id": binding.candidate_corpus_version_id,
        "candidate_run_token": binding.candidate_run_token,
        "candidate_lease_owner": binding.candidate_lease_owner,
        "source_manifest_hash": binding.source_manifest_hash,
        "manifest_hash": validated.inputs.manifest_hash,
        "gold_hash": validated.inputs.gold_hash,
        "dataset_baseline_identity": validated.inputs.dataset_baseline_identity,
        "runtime_config_sha256": _sha256_payload(validated.runtime.model_dump(mode="json")),
        "candidate_observation_sha256": _sha256_payload(validated.candidate.model_dump(mode="json")),
        "exact_gate_profile_sha256": _sha256_payload([gate.model_dump(mode="json") for gate in validated.gates]),
    }
    unsealed = ABSelectionDecisionV1.model_construct(
        **base,
        decision_payload_sha256="sha256:" + "0" * 64,
    )
    decision = ABSelectionDecisionV1(
        **base,
        decision_payload_sha256=_sha256_payload(unsealed.model_dump(mode="json", exclude={"decision_payload_sha256"})),
    )
    return _write_create_only_pair(
        json_path=root / "selections" / f"{binding.selection_id}.json",
        markdown_path=root / "selections" / f"{binding.selection_id}.md",
        json_payload=canonical_report_json_bytes(decision.model_dump(mode="json")),
        markdown_payload=render_selection_markdown(decision.model_dump(mode="json")).encode(),
    )


def load_selection_decision(path: Path) -> ABSelectionDecisionV1:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, TypeError, ValueError):
        raise ValueError("selection_decision_invalid") from None
    return ABSelectionDecisionV1.model_validate(payload)


def _ratio_display(value: ExactRatioV1) -> str:
    display = Decimal(value.numerator) / Decimal(value.denominator)
    return f"{value.numerator}/{value.denominator} ({display:.6f})"


def _sha256_payload(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _write_create_only_pair(
    *,
    json_path: Path,
    markdown_path: Path,
    json_payload: bytes,
    markdown_payload: bytes,
) -> ImmutableArtifactPairV1:
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ValueError("write_failed") from None
    if json_path.exists() or markdown_path.exists():
        raise ValueError("create_conflict")
    temporary_paths: list[Path] = []
    linked: list[Path] = []
    try:
        for target, payload in ((json_path, json_payload), (markdown_path, markdown_payload)):
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            temporary = Path(temporary_name)
            temporary_paths.append(temporary)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
            linked.append(target)
    except FileExistsError:
        for target in linked:
            target.unlink(missing_ok=True)
        raise ValueError("create_conflict") from None
    except OSError:
        for target in linked:
            target.unlink(missing_ok=True)
        raise ValueError("write_failed") from None
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return ImmutableArtifactPairV1(
        json_path=json_path,
        markdown_path=markdown_path,
        json_sha256=_sha256_bytes(json_payload),
        markdown_sha256=_sha256_bytes(markdown_payload),
    )


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
