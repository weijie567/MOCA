from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    INTENT_ROUTE_POLICY,
    ORDINARY_INTENTS,
    PRECEDENCE_INTENTS,
    REQUIRED_SLOT_POLICY,
)


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["positive", "hard-negative"]
    input: str
    expected: dict[str, Any]
    negative_for: str | None = None


class IntentGoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["intent_golden_dataset.v1"]
    dataset_version: Literal["intent-golden.v1"]
    owner: str
    gate_scope: Literal["phase_11_contract"]
    blocking: Literal["phase_exit"]
    failure_impact: Literal["block_phase_11_verification"]
    cases: list[GoldenCase]


class CoverageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["coverage_manifest.v1"]
    dataset_version: str
    dataset_hash: str
    owner: str
    gate_scope: Literal["phase_11_contract"]
    blocking: Literal["phase_exit"]
    failure_impact: Literal["block_phase_11_verification"]
    dedupe_key: str
    coverage_status: Literal["complete", "incomplete", "invalid"]
    m6_statistical_gate_path: str


class M6StatisticalGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m6_statistical_gate.v1"]
    owner: str
    gate_scope: Literal["m6_release"]
    blocking: Literal["release_safety_sensitive_confidence_assisted_routing"]
    failure_impact: Literal["block_m6_release_not_phase_11_exit"]
    dataset_version: str
    dataset_hash: str
    coverage_manifest_hash: str
    required_classes: list[str]
    per_class_expected_min_n: dict[str, int]
    coverage_status: Literal["complete", "incomplete", "missing", "invalid"]
    default_gate_status: Literal["statistical_gate_not_demonstrated"]


class IntentConsistencyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    in_precedence: bool
    in_required_slots: bool
    in_routing: bool
    in_evidence_table: bool
    in_golden_set: bool


class IntentConsistencyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["intent-consistency.v1"]
    dataset_version: str
    dataset_hash: str
    coverage_status: Literal["complete", "incomplete", "invalid"]
    future_intent_admission_fields: list[str]
    deferred_boundaries: dict[str, str]
    entries: list[IntentConsistencyEntry]


class WilsonGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_hash: str
    coverage_manifest_hash: str
    coverage_status: str
    class_name: str
    required_min_n: int
    n: int
    false_negatives: int
    wilson_upper_95_one_sided: float
    formula_version: Literal["wilson_one_sided_95_v1"] = "wilson_one_sided_95_v1"
    confidence_level: float = 0.95
    gate_status: Literal["pass", "fail", "statistical_gate_not_demonstrated"]
    gate_reason: Literal[
        "coverage_missing",
        "coverage_incomplete",
        "coverage_invalid",
        "below_per_class_min_n",
        "false_negatives_present",
        "wilson_upper_exceeded",
        "passed",
    ]


T = TypeVar("T", bound=BaseModel)


def compute_dataset_hash(path: Path) -> str:
    data = json.loads(path.read_text())
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def load_json_model(path: Path, model: type[T]) -> T:
    return model.model_validate(json.loads(path.read_text()))


def validate_intent_manifest(
    golden_path: Path,
    coverage_path: Path,
    consistency_path: Path,
    m6_gate_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    golden = load_json_model(golden_path, IntentGoldenDataset)
    coverage = load_json_model(coverage_path, CoverageManifest)
    consistency = load_json_model(consistency_path, IntentConsistencyManifest)
    expected_hash = compute_dataset_hash(golden_path)
    if coverage.dataset_hash != expected_hash:
        errors.append("stale dataset_hash in coverage manifest")
    if consistency.dataset_hash != expected_hash:
        errors.append("stale dataset_hash in consistency manifest")
    if coverage.coverage_status != "complete":
        errors.append("coverage_status is not complete")

    positives = {intent: 0 for intent in ORDINARY_INTENTS}
    negatives = {intent: 0 for intent in ORDINARY_INTENTS}
    for case in golden.cases:
        expected_intent = case.expected.get("primary_intent")
        if case.kind == "positive" and expected_intent in positives:
            positives[expected_intent] += 1
        if case.kind == "hard-negative" and case.negative_for in negatives:
            negatives[case.negative_for] += 1
    for intent in ORDINARY_INTENTS:
        if positives[intent] < 5:
            errors.append(f"missing positive golden coverage for {intent}")
        if negatives[intent] < 3:
            errors.append(f"missing hard-negative golden coverage for {intent}")

    entries = {entry.intent: entry for entry in consistency.entries}
    for intent in ORDINARY_INTENTS:
        entry = entries.get(intent)
        if entry is None:
            errors.append(f"missing consistency entry for {intent}")
            continue
        if intent not in PRECEDENCE_INTENTS or not entry.in_precedence:
            errors.append(f"missing precedence coverage for {intent}")
        if intent not in REQUIRED_SLOT_POLICY or not entry.in_required_slots:
            errors.append(f"missing required-slot coverage for {intent}")
        if intent not in INTENT_ROUTE_POLICY or not entry.in_routing:
            errors.append(f"missing routing coverage for {intent}")
        if intent in EVIDENCE_REQUIRED_INTENTS and not entry.in_evidence_table:
            errors.append(f"missing evidence coverage for {intent}")
        if intent in DIRECT_RESPONSE_INTENTS and entry.in_evidence_table:
            errors.append(f"invalid direct-response evidence exemption for {intent}")
        if not entry.in_golden_set:
            errors.append(f"missing golden set coverage for {intent}")

    required_admission = {
        "risk_level",
        "response_mode",
        "tool_allowlist",
        "bounded_loop_allowed",
        "max_iterations",
        "routing_precedence",
        "audit_replay_requirements",
    }
    if not required_admission <= set(consistency.future_intent_admission_fields):
        errors.append("missing GAD-02 future intent admission fields")
    if "generic_qa" in entries:
        errors.append("forbidden generic_qa intent admitted")
    boundary = consistency.deferred_boundaries.get("multi-step read-only QA expansion", "")
    if "GAD-01" not in boundary or "GAD-02" not in boundary:
        errors.append("missing D-31 deferred multi-step read-only QA boundary")

    if m6_gate_path is not None:
        m6 = load_json_model(m6_gate_path, M6StatisticalGate)
        if m6.gate_scope != "m6_release":
            errors.append("M6 gate scope is not release-only")
        if m6.default_gate_status != "statistical_gate_not_demonstrated":
            errors.append("M6 gate incorrectly claims demonstration")
        if coverage.gate_scope == m6.gate_scope:
            errors.append("contract dataset is incorrectly treated as M6 corpus")
    return errors


def wilson_upper_false_negative(false_negatives: int, n: int) -> float:
    if n <= 0:
        return 1.0
    z = 1.6448536269514722
    phat = false_negatives / n
    denominator = 1 + z**2 / n
    centre = phat + z**2 / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) / n) + (z**2 / (4 * n**2)))
    return (centre + margin) / denominator


def evaluate_wilson_gate(
    class_name: str,
    false_negatives: int,
    n: int,
    m6_gate: M6StatisticalGate,
) -> dict[str, Any]:
    required_min_n = m6_gate.per_class_expected_min_n.get(class_name, 0)
    wilson_upper = wilson_upper_false_negative(false_negatives, n)
    status = "pass"
    reason = "passed"
    if m6_gate.coverage_status == "missing":
        status, reason = "statistical_gate_not_demonstrated", "coverage_missing"
    elif m6_gate.coverage_status == "incomplete":
        status, reason = "statistical_gate_not_demonstrated", "coverage_incomplete"
    elif m6_gate.coverage_status == "invalid":
        status, reason = "statistical_gate_not_demonstrated", "coverage_invalid"
    elif n < required_min_n:
        status, reason = "statistical_gate_not_demonstrated", "below_per_class_min_n"
    elif false_negatives > 0:
        status, reason = "fail", "false_negatives_present"
    elif wilson_upper > 0.01:
        status, reason = "fail", "wilson_upper_exceeded"
    result = WilsonGateResult(
        dataset_hash=m6_gate.dataset_hash,
        coverage_manifest_hash=m6_gate.coverage_manifest_hash,
        coverage_status=m6_gate.coverage_status,
        class_name=class_name,
        required_min_n=required_min_n,
        n=n,
        false_negatives=false_negatives,
        wilson_upper_95_one_sided=wilson_upper,
        gate_status=status,
        gate_reason=reason,
    )
    return result.model_dump()
