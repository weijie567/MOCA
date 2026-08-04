from __future__ import annotations

import json
from pathlib import Path

from src.agent.intent_manifest import (
    M6StatisticalGate,
    compute_dataset_hash,
    evaluate_wilson_gate,
    load_json_model,
    validate_intent_manifest,
)
from src.agent.intent_policy import ORDINARY_INTENTS


GOLDEN = Path("eval/intent/intent-golden.v1.json")
COVERAGE = Path("eval/intent/coverage-manifest.v1.json")
M6 = Path("eval/intent/m6-statistical-gate.v1.json")
CONSISTENCY = Path("eval/intent/intent-consistency.v1.json")


def test_intent_manifest_files_are_hash_owned_and_complete():
    errors = validate_intent_manifest(GOLDEN, COVERAGE, CONSISTENCY, M6)
    assert errors == []


def test_phase_11_contract_and_m6_release_gate_are_separate():
    coverage = json.loads(COVERAGE.read_text())
    m6 = json.loads(M6.read_text())
    assert coverage["gate_scope"] == "phase_11_contract"
    assert coverage["failure_impact"] == "block_phase_11_verification"
    assert m6["gate_scope"] == "m6_release"
    assert m6["blocking"] == "release_safety_sensitive_confidence_assisted_routing"
    assert m6["failure_impact"] == "block_m6_release_not_phase_11_exit"
    assert m6["default_gate_status"] == "statistical_gate_not_demonstrated"


def test_every_intent_has_positive_and_hard_negative_coverage():
    dataset = json.loads(GOLDEN.read_text())
    for intent in ORDINARY_INTENTS:
        positives = [
            case
            for case in dataset["cases"]
            if case["kind"] == "positive" and case["expected"].get("primary_intent") == intent
        ]
        negatives = [
            case for case in dataset["cases"] if case["kind"] == "hard-negative" and case.get("negative_for") == intent
        ]
        assert len(positives) >= 5
        assert len(negatives) >= 3


def test_business_metric_query_has_generic_golden_coverage_only():
    dataset = json.loads(GOLDEN.read_text())
    cases = dataset["cases"]
    positives = [
        case
        for case in cases
        if case["kind"] == "positive" and case["expected"].get("primary_intent") == "business_metric_query"
    ]
    negatives = [
        case
        for case in cases
        if case["kind"] == "hard-negative" and case.get("negative_for") == "business_metric_query"
    ]
    forbidden = {
        "order_count_query",
        "refund_count_query",
        "refund_case_count_query",
        "pending_ticket_count_query",
        "coupon_record_count_query",
        "merchant_refund_rate_query",
    }

    assert len(positives) >= 5
    assert len(negatives) >= 3
    assert all(case["expected"].get("requested_operation") == "read_status" for case in positives)
    assert forbidden.isdisjoint(
        {case["expected"].get("primary_intent") for case in cases if isinstance(case.get("expected"), dict)}
    )


def test_business_metric_query_has_consistency_manifest_entry():
    consistency = json.loads(CONSISTENCY.read_text())
    entries = {entry["intent"]: entry for entry in consistency["entries"]}

    assert entries["business_metric_query"] == {
        "intent": "business_metric_query",
        "in_precedence": True,
        "in_required_slots": True,
        "in_routing": True,
        "in_evidence_table": False,
        "in_golden_set": True,
    }


def test_stale_dataset_hash_fails(tmp_path):
    stale = json.loads(COVERAGE.read_text())
    stale["dataset_hash"] = "sha256:stale"
    stale_path = tmp_path / "coverage.json"
    stale_path.write_text(json.dumps(stale))

    errors = validate_intent_manifest(GOLDEN, stale_path, CONSISTENCY, M6)

    assert any("stale dataset_hash" in error for error in errors)


def test_stale_m6_coverage_manifest_hash_fails(tmp_path):
    stale = json.loads(M6.read_text())
    stale["coverage_manifest_hash"] = "sha256:stale"
    stale_path = tmp_path / "m6.json"
    stale_path.write_text(json.dumps(stale))

    errors = validate_intent_manifest(GOLDEN, COVERAGE, CONSISTENCY, stale_path)

    assert "stale coverage_manifest_hash in M6 gate" in errors


def test_dataset_hash_matches_manifest():
    coverage = json.loads(COVERAGE.read_text())
    consistency = json.loads(CONSISTENCY.read_text())
    assert coverage["dataset_hash"] == compute_dataset_hash(GOLDEN)
    assert consistency["dataset_hash"] == compute_dataset_hash(GOLDEN)


def test_gad02_gad03_and_d31_deferred_boundaries():
    consistency = json.loads(CONSISTENCY.read_text())
    fields = set(consistency["future_intent_admission_fields"])
    assert {
        "risk_level",
        "response_mode",
        "tool_allowlist",
        "bounded_loop_allowed",
        "max_iterations",
        "routing_precedence",
        "audit_replay_requirements",
    } <= fields
    assert "generic_qa" not in {entry["intent"] for entry in consistency["entries"]}
    boundary = consistency["deferred_boundaries"]["multi-step read-only QA expansion"]
    assert "GAD-01" in boundary
    assert "GAD-02" in boundary


def test_wilson_gate_status_precedence_and_fields():
    m6 = load_json_model(M6, M6StatisticalGate)
    result = evaluate_wilson_gate("critical_write", false_negatives=0, n=0, m6_gate=m6)
    assert result["gate_status"] == "statistical_gate_not_demonstrated"
    assert result["gate_reason"] == "coverage_incomplete"
    assert result["formula_version"] == "wilson_one_sided_95_v1"
    assert result["confidence_level"] == 0.95
    assert set(result) == {
        "dataset_hash",
        "coverage_manifest_hash",
        "coverage_status",
        "class_name",
        "required_min_n",
        "n",
        "false_negatives",
        "wilson_upper_95_one_sided",
        "formula_version",
        "confidence_level",
        "gate_status",
        "gate_reason",
    }

    complete = m6.model_copy(update={"coverage_status": "complete"})
    assert evaluate_wilson_gate("critical_write", 0, 299, complete)["gate_reason"] == "below_per_class_min_n"
    assert evaluate_wilson_gate("critical_write", 1, 300, complete)["gate_reason"] == "false_negatives_present"
    assert evaluate_wilson_gate("critical_write", 0, 300, complete)["gate_status"] in {"pass", "fail"}
