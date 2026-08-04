from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import route_after_approval, route_after_risk
from src.agent import routing as routing_module
from src.agent.nodes import risk_gate as risk_module
from src.agent.nodes import risk_gate as risk_gate_module
from src.agent.routing import (
    SLOT_RESOLUTION_ROUTES,
    route_after_claim_verify,
    route_after_contextual_intent,
    route_after_investigate,
    route_after_recommendation,
    route_after_safety,
    route_after_slot_resolution,
)
from src.agent.schemas import IntentResultV3, RiskAssessment
from src.approvals.snapshot_service import compute_action_payload_hash
from src.db.models import ActionSafetySnapshot
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.contracts import BusinessFactRefV1
from tests.approvals.test_service_transitions import _create_run, _evidence_ref
from tests.architecture.graph_baseline import graph_conditional_edge_mappings


VALID_INVESTIGATE_KEYS = {
    "final_response",
    "clarification_gate",
    "recommendation_generation",
    "rag_context_build",
}
ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64
PHASE58_ROUTING_TEST_FILES = (
    Path("tests/test_graph_routing.py"),
    Path("tests/agent/test_intent_routing.py"),
    Path("tests/agent/test_intent_golden_contract.py"),
    Path("tests/agent/test_required_slots.py"),
    Path("tests/agent/test_session_memory_integration.py"),
)


class _FakeRiskLLM:
    def __init__(self, assessment: RiskAssessment):
        self.assessment = assessment

    def with_structured_output(self, schema: type):
        return self

    async def ainvoke(self, messages):
        return self.assessment


def _approved_result(**overrides) -> dict:
    payload = {
        "schema_version": "approval_result.v1",
        "approval_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "run_id": str(uuid4()),
        "decision_type": "approve",
        "status": "approved",
        "revision": 1,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "decided_by": str(uuid4()),
        "decided_at": "2026-06-15T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


def _business_fact_ref_payload(tenant_id: str, *, resource_id: str = "RF-1001") -> dict:
    return BusinessFactRefV1(
        tenant_id=tenant_id,
        source_system="moca_demo",
        resource_type="refund_case",
        resource_id=resource_id,
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 29, 0, 1, tzinfo=UTC),
    ).model_dump(mode="json")


def _evidence_ref_payload(tenant_id: str) -> dict:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": tenant_id,
        "evidence_id": "refund-policy/chunk-001@v3",
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:" + "a" * 64,
        "retrieved_at": "2026-06-29T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "rank": 1,
    }


def _claim_bundle_payload(tenant_id: str) -> dict:
    fact_ref = _business_fact_ref_payload(tenant_id)
    evidence_ref = _evidence_ref_payload(tenant_id)
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": "verified",
        "route": "continue",
        "claim_results": [
            {
                "schema_version": "claim_verification_result.v1",
                "claim_id": "claim-action-1",
                "claim_type": "action_recommendation",
                "support_status": "supported",
                "supporting_evidence_refs": [evidence_ref],
                "business_fact_refs": [fact_ref],
                "rule_checks": [],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": True,
                "allows_action_recommendation": True,
            }
        ],
        "blocked_claims": [],
        "safe_support_refs": [evidence_ref],
        "reason_codes": [],
        "verifier_policy_version": "claim-verifier.v1",
    }


def _approval_plan_payload(state: dict) -> dict:
    return {
        "schema_version": "approval_plan.v1",
        "approval_required": state["risk_assessment"]["approval_required"],
        "policy_id": "default-approval-policy",
        "policy_version": "approval-policy.v1",
        "action_payload_hash": state["action_payload_hash"],
        "safety_snapshot_ref": state["safety_snapshot_ref"],
        "safety_snapshot_hash": state["safety_snapshot_hash"],
        "risk_decision_ref": state["risk_decision_ref"],
        "risk_decision": state["risk_decision"],
        "approval_idempotency_key": "approval:test-key",
        "target_merchant_id": state["target_merchant_id"],
        "target_merchant_ref": state["target_merchant_ref"],
        "business_fact_refs": state["business_fact_refs"],
        "verified_evidence_refs": state["verified_evidence_refs"],
        "claim_verification_ref": None,
        "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
        "allowed_decision_types": ["accept", "approve", "edit", "respond", "reject", "ignore"],
    }


def _auto_action_capability_payload() -> dict:
    return {
        "schema_version": "auto_action_capability_ref.v1",
        "capability_ref": "aac_" + "x" * 43,
        "expires_at": "2026-07-10T00:05:00Z",
    }


def _durable_draft_terminal_state(**overrides) -> dict:
    tenant_id = str(uuid4())
    run_id = str(uuid4())
    draft_id = str(uuid4())
    outcome = {
        "schema_version": "draft_outcome.v1",
        "status": "not_executed_demo",
        "external_side_effect": False,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "draft_id": draft_id,
        "created_at": "2026-07-10T05:00:00Z",
    }
    state = {
        "tenant_id": tenant_id,
        "current_run_id": run_id,
        "proposed_action": {"action_type": "issue_coupon", "target_id": "RF-1001"},
        "risk_assessment": {
            "risk_level": "low",
            "risk_severity": "low",
            "risk_disposition": "allow",
            "approval_required": False,
        },
        "action_draft": {
            "schema_version": "action_draft.v2",
            "tenant_id": tenant_id,
            "run_id": run_id,
            "draft_id": draft_id,
            "status": "draft_created",
            "execution_mode": "demo",
            "lifecycle_status": "active",
            "draft_outcome": outcome,
        },
        "draft_outcome": outcome,
        "execution_mode": "demo",
        "action_result": {
            "status": "draft_created",
            "data": {"draft_id": draft_id, "draft_outcome": outcome},
            "error": {},
        },
        "trace_steps": [
            {
                "node": "action_draft",
                "status": "completed",
                "tool_name": "create_coupon_grant_draft",
            }
        ],
    }
    state.update(overrides)
    return state


def _terminal_projection(state: dict):
    projector = getattr(routing_module, "project_action_draft_terminal")
    return projector(state)


def _post_draft_route(state: dict) -> str:
    router = getattr(routing_module, "route_after_action_draft")
    return router(state)


def _risk_route_state(**overrides) -> dict:
    tenant_id = str(overrides.pop("tenant_id", uuid4()))
    run_id = str(overrides.pop("current_run_id", uuid4()))
    risk_assessment = overrides.pop("risk_assessment", {"approval_required": True, "risk_level": "high"})
    risk_decision_ref = f"risk_decision:{run_id}:{ACTION_HASH}"
    state = {
        "tenant_id": tenant_id,
        "current_run_id": run_id,
        "risk_assessment": risk_assessment,
        "proposed_action": {"action_type": "issue_coupon", "target_id": "RF-1001"},
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
        "target_merchant_id": "merchant-1",
        "target_merchant_ref": {
            "schema_version": "target_merchant_binding.v1",
            "target_merchant_id": "merchant-1",
            "source": "business_fact_ref",
            "business_fact_ref": _business_fact_ref_payload(tenant_id),
        },
        "business_fact_refs": [_business_fact_ref_payload(tenant_id)],
        "verified_evidence_refs": [_evidence_ref_payload(tenant_id)],
        "claim_verification_bundle": _claim_bundle_payload(tenant_id),
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": {
            "schema_version": "risk_decision.v1",
            "tenant_id": tenant_id,
            "run_id": run_id,
            "action_id": "act-1",
            "action_payload_hash": ACTION_HASH,
            "risk_level": risk_assessment.get("risk_level", "high"),
            "reason_codes": ["rule-1"],
            "policy_config_version": "approval-policy.v1",
            "risk_config_version": "risk-rules.v1",
            "approval_required": risk_assessment.get("approval_required") is True,
            "evaluated_at": "2026-06-29T00:00:00.000Z",
        },
    }
    state["approval_plan"] = _approval_plan_payload(state)
    state.update(overrides)
    return state


def _approval_route_state(**overrides) -> dict:
    tenant_id = str(uuid4())
    run_id = str(uuid4())
    state = {
        "tenant_id": tenant_id,
        "current_run_id": run_id,
        "approval_result": _approved_result(tenant_id=tenant_id, run_id=run_id),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }
    approval_overrides = overrides.pop("approval_overrides", None)
    if approval_overrides:
        state["approval_result"].update(approval_overrides)
    state.update(overrides)
    return state


def test_phase58_routing_tests_use_canonical_helpers_and_route_values_only():
    join_fragment = "".join
    forbidden_fragments = [
        join_fragment(("route_after_", "intent")),
        join_fragment(("route_after_", "slots")),
        join_fragment(("needs_long_", "term_memory")),
        join_fragment(("classify_", "intent")),
        join_fragment(("session_memory_", "load")),
        join_fragment(("assess_risk_", "and_approval")),
    ]

    for path in PHASE58_ROUTING_TEST_FILES:
        source = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{path} still references {fragment}"


def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {
        "current_intent": "policy_qa",
        "risk_assessment": {"approval_required": False},
        "proposed_action": None,
    }

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_returns_approval_gate_when_required_snapshot_refs_are_present():
    assert route_after_risk(_risk_route_state()) == "approval_gate"


@pytest.mark.parametrize(
    "claim_results",
    [
        [],
        [
            {
                "schema_version": "claim_verification_result.v1",
                "claim_id": "claim-user-visible-1",
                "claim_type": "user_visible_claim",
                "support_status": "supported",
                "supporting_evidence_refs": [],
                "business_fact_refs": [],
                "rule_checks": [],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": True,
                "allows_action_recommendation": None,
            }
        ],
        [
            {
                **_claim_bundle_payload(str(uuid4()))["claim_results"][0],
                "allows_action_recommendation": False,
            }
        ],
    ],
)
def test_route_after_risk_requires_positive_allowed_action_claim(claim_results):
    state = _risk_route_state()
    state["claim_verification_bundle"]["claim_results"] = claim_results

    assert route_after_risk(state) == "final_response"


def test_route_after_claim_verify_routes_low_risk_verified_action_without_preexisting_proposed_action():
    tenant_id = str(uuid4())
    state = {
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "risk_level": "low",
            "missing_info": [],
        },
        "claim_verification_bundle": _claim_bundle_payload(tenant_id),
    }

    assert route_after_claim_verify(state) == "risk_gate"


def test_route_after_recommendation_routes_actionable_draft_to_claim_verify():
    state = {
        "proposed_action": {"action_type": "issue_coupon"},
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "risk_level": "high",
        },
    }

    assert route_after_recommendation(state) == "claim_verify"


@pytest.mark.parametrize("match_kind", ["unknown", "ambiguous", "schema_invalid", "hard_negative"])
def test_route_after_recommendation_never_completes_unresolved_action_candidate(match_kind):
    state = {
        "canonical_action": {
            "raw_value": "unsafe candidate",
            "executable_action_type": None,
            "disposition": "manual_review",
            "matched_alias": None,
            "match_kind": match_kind,
            "match_provenance": "unresolved",
            "schema_valid": match_kind != "schema_invalid",
        },
        "risk_signals": ["manual_review_required"],
    }

    assert route_after_recommendation(state) == "claim_verify"


def test_route_after_recommendation_prefers_backend_nested_verifier_route():
    state = {
        "rag_verification": {
            "route": {
                "route": "manual_review",
                "selected_by": "backend",
                "model_selected": False,
            }
        },
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "verification_route": "allow",
        },
    }

    assert route_after_recommendation(state) == "final_response"


@pytest.mark.parametrize(
    "state",
    [
        {"pre_route_decision": {"disposition": "none"}, "routing_hints": {}},
        {
            "pre_route_decision": {
                "disposition": "safety_sensitive",
                "requested_operation": "execute_action",
                "reason_codes": ["critical_write"],
                "requires_clarification": False,
            },
            "routing_hints": {"pre_route_disposition": "safety_sensitive"},
        },
    ],
)
def test_route_after_safety_continues_safe_phase53_path_to_session_context(state):
    assert route_after_safety(state) == "session_context_load"


@pytest.mark.parametrize(
    "state",
    [
        {
            "pre_route_decision": {
                "disposition": "approval_chat_not_trusted",
                "requested_operation": "advise",
                "reason_codes": ["approval_chat_not_trusted"],
                "requires_clarification": True,
            }
        },
        {
            "pre_route_decision": {
                "disposition": "multi_target_request",
                "requested_operation": None,
                "reason_codes": ["multi_target_request"],
                "requires_clarification": True,
            }
        },
        {"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}},
        {"routing_hints": {"clarification_reason": "approval_chat_not_trusted"}},
        {"routing_hints": {"requires_clarification": True}},
        {"requested_operation": "approval_decision"},
    ],
)
def test_route_after_safety_fails_closed_for_unsafe_or_clarifying_dispositions(state):
    assert route_after_safety(state) == "clarification_gate"


def test_route_after_safety_fails_closed_for_exceptions_or_unregistered_route(monkeypatch):
    monkeypatch.setattr(routing_module, "_route_after_safety", lambda _state: "unknown_safety_route")
    assert route_after_safety({}) == "clarification_gate"

    def raise_error(_state):
        raise RuntimeError("bad safety state")

    monkeypatch.setattr(routing_module, "_route_after_safety", raise_error)
    assert route_after_safety({}) == "clarification_gate"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            {
                "primary_intent": "refund_troubleshooting",
                "requested_operation": "read_status",
                "intent_confidence": 0.95,
            },
            "slot_resolution_gate",
        ),
        (
            {
                "primary_intent": "order_status_inquiry",
                "requested_operation": "read_status",
                "intent_confidence": 0.95,
            },
            "slot_resolution_gate",
        ),
        (
            {
                "primary_intent": "policy_qa",
                "requested_operation": "advise",
                "intent_confidence": 0.95,
            },
            "investigate",
        ),
        (
            {
                "primary_intent": "small_talk",
                "requested_operation": "advise",
                "intent_confidence": 0.95,
            },
            "final_response",
        ),
        (
            {
                "primary_intent": "small_talk",
                "requested_operation": "approval_decision",
                "intent_confidence": 0.95,
            },
            "clarification_gate",
        ),
        (
            {
                "primary_intent": "refund_troubleshooting",
                "requested_operation": "read_status",
                "intent_confidence": 0.1,
            },
            "clarification_gate",
        ),
    ],
)
def test_route_after_contextual_intent_totality_and_phase54_slot_destination(state, expected):
    route = route_after_contextual_intent(state)

    assert route in {"clarification_gate", "final_response", "investigate", "slot_resolution_gate"}
    assert route == expected


def test_route_after_contextual_intent_fails_closed_for_exceptions_or_unregistered_route(monkeypatch):
    monkeypatch.setattr(routing_module, "_route_after_contextual_intent", lambda _state: "unknown_contextual_route")
    assert route_after_contextual_intent({}) == "clarification_gate"

    def raise_error(_state):
        raise RuntimeError("bad contextual intent state")

    monkeypatch.setattr(routing_module, "_route_after_contextual_intent", raise_error)
    assert route_after_contextual_intent({}) == "clarification_gate"


def test_legacy_intent_route_delegate_is_not_public_current_route_authority():
    legacy_route_helper = "".join(("route_after_", "intent"))
    state = {
        "primary_intent": "refund_troubleshooting",
        "requested_operation": "read_status",
        "intent_confidence": 0.95,
    }

    assert route_after_contextual_intent(state) == "slot_resolution_gate"
    assert not hasattr(routing_module, legacy_route_helper)
    assert f"def {legacy_route_helper}(" not in Path("src/agent/routing.py").read_text(encoding="utf-8")


def test_legacy_slot_route_delegate_is_not_public_current_route_authority():
    legacy_route_helper = "".join(("route_after_", "slots"))
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {},
    }

    assert route_after_slot_resolution(state) == "clarification_gate"
    assert not hasattr(routing_module, legacy_route_helper)
    assert f"def {legacy_route_helper}(" not in Path("src/agent/routing.py").read_text(encoding="utf-8")


def test_route_after_slot_resolution_memory_hints_use_canonical_destination():
    base_state = {
        "primary_intent": "policy_qa",
        "required_slots": {"all_of": [], "any_of": [], "optional": []},
        "extracted_slots": {},
    }

    assert SLOT_RESOLUTION_ROUTES == {"clarification_gate", "investigate", "memory_context_load"}
    assert route_after_slot_resolution({**base_state, "routing_hints": {"needs_reviewed_memory_context": True}}) == (
        "memory_context_load"
    )


def test_phase56_recommendation_route_maps_target_canonical_graph_node():
    route_maps = graph_conditional_edge_mappings()

    assert route_maps[("investigate", "route_after_investigate")]["recommendation_generation"] == (
        "recommendation_generation"
    )
    assert route_maps[("rag_context_build", "route_after_rag_context")]["recommendation_generation"] == (
        "recommendation_generation"
    )
    assert route_maps[("recommendation_generation", "route_after_recommendation")] == {
        "claim_verify": "claim_verify",
        "final_response": "final_response",
    }
    legacy_recommendation_edge = ("generate_recommendation", "route_after_recommendation")
    assert legacy_recommendation_edge not in route_maps
    assert route_maps[("claim_verify", "route_after_claim_verify")]["risk_gate"] == "risk_gate"


def test_route_after_risk_returns_final_response_for_auto_allowed_snapshot_verified_action():
    state = _risk_route_state(risk_assessment={"approval_required": False, "risk_level": "low"})

    assert route_after_risk(state) == "final_response"


@pytest.mark.parametrize(
    "missing_field",
    [
        "target_merchant_id",
        "business_fact_refs",
        "verified_evidence_refs",
        "risk_decision_ref",
        "approval_idempotency_key",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    ],
)
def test_route_after_risk_fails_closed_when_approval_plan_binding_missing(missing_field):
    state = _risk_route_state()
    state["approval_plan"].pop(missing_field)

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_fails_closed_when_approval_plan_hash_mismatches_state():
    state = _risk_route_state()
    state["approval_plan"]["action_payload_hash"] = "sha256:" + "9" * 64

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_routes_auto_allowed_only_with_opaque_capability_ref():
    state = _risk_route_state(risk_assessment={"approval_required": False, "risk_level": "low"})
    state["auto_action_capability"] = _auto_action_capability_payload()

    assert route_after_risk(state) == "action_draft"

    state["auto_action_capability"]["capability_ref"] = "client-asserted-binding"
    assert route_after_risk(state) == "final_response"


def test_route_after_action_draft_allows_only_valid_durable_audited_demo_outcome():
    state = _durable_draft_terminal_state()

    terminal = _terminal_projection(state)

    assert terminal.status == "completed"
    assert terminal.final_status == "completed"
    assert terminal.draft_id == state["draft_outcome"]["draft_id"]
    assert terminal.error_code is None
    assert _post_draft_route(state) == "final_response"


@pytest.mark.parametrize(
    ("failure_kind", "mutate", "reason_code"),
    [
        (
            "capability_auth",
            lambda state: state.update(
                action_draft=None,
                draft_outcome=None,
                action_result={
                    "status": "error",
                    "data": {},
                    "error": {"error_code": "AUTO_ACTION_CAPABILITY_REQUIRED", "message": "binding secret"},
                },
                trace_steps=[{"node": "action_draft", "status": "error"}],
            ),
            "authorization_failed",
        ),
        (
            "store_tool_exception",
            lambda state: state.update(
                action_draft=None,
                draft_outcome=None,
                action_result={
                    "status": "error",
                    "data": {},
                    "error": {"error_code": "DRAFT_CREATION_FAILED", "message": "raw database exception"},
                },
                trace_steps=[{"node": "action_draft", "status": "error"}],
            ),
            "draft_persistence_failed",
        ),
        (
            "missing_outcome",
            lambda state: state.update(draft_outcome=None),
            "draft_outcome_invalid",
        ),
        (
            "malformed_outcome",
            lambda state: state.update(draft_outcome={"status": "executed", "external_side_effect": True}),
            "draft_outcome_invalid",
        ),
        (
            "missing_draft_identity",
            lambda state: state["draft_outcome"].update(draft_id=None),
            "draft_identity_invalid",
        ),
        (
            "critical_audit_missing",
            lambda state: state.update(trace_steps=[]),
            "critical_audit_missing",
        ),
    ],
)
def test_route_after_action_draft_failure_matrix_is_stable_terminal_error(
    failure_kind,
    mutate,
    reason_code,
):
    state = _durable_draft_terminal_state()
    mutate(state)

    terminal = _terminal_projection(state)

    assert failure_kind
    assert terminal.status == "error"
    assert terminal.final_status == "error"
    assert terminal.error_code == "ACTION_DRAFT_TERMINAL_FAILED"
    assert terminal.reason_code == reason_code
    assert "secret" not in terminal.safe_message
    assert "exception" not in terminal.safe_message
    assert _post_draft_route(state) == "terminal_error"


@pytest.mark.parametrize("missing_field", ["action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"])
def test_route_after_risk_fails_closed_when_snapshot_or_action_hash_missing(missing_field):
    state = _risk_route_state()
    state.pop(missing_field)

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_fails_closed_when_auto_allowed_snapshot_row_not_verified():
    state = _risk_route_state(
        risk_assessment={"approval_required": False, "risk_level": "low"},
        safety_snapshot_verified=False,
    )

    assert route_after_risk(state) == "final_response"


def test_route_after_approval_returns_action_draft_on_trusted_approval_result_v1():
    state = _approval_route_state()

    assert route_after_approval(state) == "action_draft"


def test_requested_operation_execute_action_remains_intent_taxonomy_value():
    parsed = IntentResultV3(
        primary_intent="compensation_suggestion",
        requested_operation="execute_action",
        confidence=0.92,
        calibrated_confidence=0.9,
        secondary_intents=[],
        required_slots={"all_of": [], "any_of": [], "optional": []},
        candidate_slots={},
        routing_hints={},
        classifier_version="test",
        calibration_version="test",
        reason_codes=["write_requested"],
    )

    assert parsed.requested_operation == "execute_action"


def test_route_after_approval_returns_final_response_on_untrusted_ordinary_payload():
    assert route_after_approval({"approval_result": {"decision": "approve"}}) == "final_response"


@pytest.mark.parametrize(
    ("decision_type", "status"),
    [
        ("reject", "rejected"),
        ("ignore", "cancelled"),
        ("respond", "needs_info"),
    ],
)
def test_route_after_approval_sends_terminal_or_needs_info_results_to_safe_path(decision_type, status):
    state = _approval_route_state(approval_overrides={"decision_type": decision_type, "status": status})

    assert route_after_approval(state) == "final_response"


def test_route_after_approval_sends_edit_to_risk_reroute_not_action_draft():
    state = _approval_route_state(
        approval_overrides={
            "decision_type": "edit",
            "status": "superseded",
            "new_action_payload_hash": "sha256:" + "3" * 64,
            "resume_route": "risk_gate",
        }
    )

    assert route_after_approval(state) == "risk_gate"


def test_route_after_approval_rejects_unregistered_edit_resume_route():
    state = _approval_route_state(
        approval_overrides={
            "decision_type": "edit",
            "status": "superseded",
            "new_action_payload_hash": "sha256:" + "3" * 64,
            "resume_route": "unknown_risk_resume_route",
        }
    )

    assert route_after_approval(state) == "final_response"


def test_route_after_approval_rejects_legacy_risk_resume_route_authority():
    state = _approval_route_state(
        approval_overrides={
            "decision_type": "edit",
            "status": "superseded",
            "new_action_payload_hash": "sha256:" + "3" * 64,
            "resume_route": "".join(("assess_risk_", "and_approval")),
        }
    )

    assert route_after_approval(state) == "final_response"


def test_route_after_approval_fails_closed_on_hash_mismatch():
    state = _approval_route_state(approval_overrides={"action_payload_hash": "sha256:" + "9" * 64})

    assert route_after_approval(state) == "final_response"


def test_route_after_approval_fails_closed_when_tenant_or_run_mismatches_state():
    assert (
        route_after_approval(_approval_route_state(approval_overrides={"tenant_id": str(uuid4())})) == "final_response"
    )
    assert route_after_approval(_approval_route_state(approval_overrides={"run_id": str(uuid4())})) == "final_response"


@pytest.mark.parametrize(
    "missing_field",
    ["revision", "request_version", "level_version", "assignment_version"],
)
def test_route_after_approval_fails_closed_when_revision_binding_missing(missing_field):
    state = _approval_route_state()
    approval_result = state["approval_result"]
    approval_result.pop(missing_field)

    assert route_after_approval(state) == "final_response"


@pytest.mark.asyncio
async def test_auto_allowed_path_persists_durable_snapshot_row_before_action_draft_route(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id, thread_id="auto-allowed-snapshot")
    monkeypatch.setattr(
        risk_module,
        "_get_llm",
        lambda: _FakeRiskLLM(
            RiskAssessment(
                risk_level="low",
                risk_reason="Low value compensation is auto allowed.",
                approval_required=False,
                rule_ref="LR-01",
            )
        ),
    )

    input_state = {
        "thread_id": "auto-allowed-snapshot",
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "role": "support",
        "current_run_id": str(run_id),
        "current_intent": "compensation_suggestion",
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a low value coupon.",
            "confidence": 0.9,
            "risk_level": "low",
            "missing_info": [],
        },
        "business_context": {
            "refund_case": {"id": "RF-TEST-001", "merchant_id": "merchant-1", "requested_amount": "50.00"},
            "business_fact_refs": [
                _business_fact_ref_payload(str(tenant_id), resource_id="RF-TEST-001"),
            ],
        },
        "claim_verification_bundle": {
            **_claim_bundle_payload(str(tenant_id)),
            "claim_results": [
                {
                    **_claim_bundle_payload(str(tenant_id))["claim_results"][0],
                    "business_fact_refs": [_business_fact_ref_payload(str(tenant_id), resource_id="RF-TEST-001")],
                }
            ],
            "safe_support_refs": [_evidence_ref(tenant_id=tenant_id)],
        },
        "trace_steps": [],
    }
    result = await risk_module.risk_gate(
        input_state,
        {
            "configurable": {
                "session": session,
                "trusted_context": TrustedContext(
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                    role="support",
                    permissions=[],
                    merchant_scope=MerchantScopeV1(merchant_ids=["merchant-1"]),
                    thread_id="auto-allowed-snapshot",
                    run_id=str(run_id),
                    trace_id="trace-auto-allowed-snapshot",
                ).model_dump(mode="json"),
            }
        },
    )

    snapshot = (
        await session.execute(select(ActionSafetySnapshot).where(ActionSafetySnapshot.run_id == UUID(str(run_id))))
    ).scalar_one()

    assert result["auto_allowed"] is True, result.get("risk_assessment")
    assert result["action_payload_hash"] == snapshot.action_payload_hash
    assert result["safety_snapshot_ref"] == snapshot.snapshot_ref
    assert result["safety_snapshot_hash"] == snapshot.immutable_hash
    assert result["safety_snapshot_verified"] is True
    assert result["auto_action_capability"]["schema_version"] == "auto_action_capability_ref.v1"
    assert result["auto_action_capability"]["capability_ref"].startswith("aac_")
    assert result["auto_allowed_binding"] is None
    assert route_after_risk({**input_state, **result}) == "action_draft"


@pytest.mark.asyncio
async def test_edit_resume_rerisk_uses_exact_trusted_edited_action(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id, thread_id="edit-rerisk-route")
    old_action_hash = "sha256:" + "1" * 64
    old_snapshot_ref = "snapshot:old-edit"
    old_snapshot_hash = "sha256:" + "2" * 64
    evidence_ref = _evidence_ref(tenant_id=tenant_id)
    edited_action = {
        "schema_version": "proposed_action.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": f"act:{run_id}:issue_coupon:RF-EDIT-001",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "RF-EDIT-001",
        "amount": "88.00",
        "currency": "CNY",
        "args": {"coupon_type": "service_recovery"},
        "reason": "Reviewer reduced the compensation amount.",
        "evidence_refs": [evidence_ref],
    }
    edited_hash = compute_action_payload_hash(edited_action)
    fact_ref = _business_fact_ref_payload(str(tenant_id), resource_id="RF-EDIT-001")
    claim_bundle = _claim_bundle_payload(str(tenant_id))
    claim_bundle["safe_support_refs"] = [evidence_ref]
    claim_bundle["claim_results"][0]["supporting_evidence_refs"] = [evidence_ref]
    claim_bundle["claim_results"][0]["business_fact_refs"] = [fact_ref]
    state = {
        "thread_id": "edit-rerisk-route",
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "role": "support",
        "current_run_id": str(run_id),
        "current_intent": "compensation_suggestion",
        "business_context": {
            "refund_case": {"id": "RF-EDIT-001", "merchant_id": "merchant-1", "requested_amount": "100.00"},
            "business_fact_refs": [fact_ref],
        },
        "claim_verification_bundle": claim_bundle,
        "proposed_action": {
            **edited_action,
            "amount": "120.00",
            "reason": "Original action before manager edit.",
        },
        "action_payload_hash": old_action_hash,
        "safety_snapshot_ref": old_snapshot_ref,
        "safety_snapshot_hash": old_snapshot_hash,
        "approval_result": _approved_result(
            tenant_id=str(tenant_id),
            run_id=str(run_id),
            decision_type="edit",
            status="superseded",
            action_payload_hash=old_action_hash,
            safety_snapshot_ref=old_snapshot_ref,
            safety_snapshot_hash=old_snapshot_hash,
            edited_action=edited_action,
            new_action_payload_hash=edited_hash,
            resume_route="risk_gate",
        ),
        "trace_steps": [],
    }
    monkeypatch.setattr(
        risk_module,
        "_get_llm",
        lambda: _FakeRiskLLM(
            RiskAssessment(
                risk_level="high",
                risk_reason="Edited compensation still needs review.",
                approval_required=True,
                rule_ref="HR-EDIT",
            )
        ),
    )

    result = await risk_gate_module.risk_gate(state, {"configurable": {"session": session}})

    snapshot = (
        await session.execute(
            select(ActionSafetySnapshot).where(ActionSafetySnapshot.action_payload_hash == edited_hash)
        )
    ).scalar_one()
    assert result["proposed_action"] == edited_action
    assert result["action_payload_hash"] == edited_hash
    assert result["action_payload_hash"] == snapshot.action_payload_hash
    assert result["risk_decision"]["action_payload_hash"] == edited_hash
    assert result["approval_plan"]["action_payload_hash"] == edited_hash
    assert result["approval_plan"]["risk_decision"]["action_payload_hash"] == edited_hash
    assert route_after_risk({**state, **result}) == "approval_gate"


@pytest.mark.asyncio
async def test_auto_allowed_missing_durable_snapshot_row_does_not_route_to_action_draft(
    session: AsyncSession,
):
    state = _risk_route_state(
        risk_assessment={"approval_required": False, "risk_level": "low"},
        safety_snapshot_verified=False,
    )

    assert route_after_risk(state) == "final_response"


def test_missing_required_facts_to_clarification():
    state = {"business_context": {"missing_required_facts": ["order_id"]}}

    assert route_after_investigate(state) == "clarification_gate"


def test_fact_only_intent_with_facts_to_final():
    state = {
        "primary_intent": "order_status_inquiry",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
    }

    assert route_after_investigate(state) == "final_response"


@pytest.mark.parametrize(
    "state",
    [
        {"retrieval_status": "no_evidence"},
        {"retrieval_status": "partial_evidence", "best_score": 0.3},
    ],
)
def test_insufficient_evidence_to_final(state):
    assert route_after_investigate(state) == "final_response"


def test_sufficient_context_to_rag_context_build_when_policy_evidence_is_required():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "rag_context_build"


def test_permission_denied_required_blocks():
    state = {
        "business_context": {
            "missing_required_facts": ["merchant_risk"],
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": [
            {
                "claim_id": "risk_claim",
                "depends_on_refs": [{"resource_type": "merchant_risk", "resource_id": "merchant-1"}],
            }
        ],
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "final_response"


@pytest.mark.parametrize(
    "claim_dependency_map",
    [
        None,
        [],
        [{"claim_id": "risk_claim", "depends_on_refs": [{"resource_type": "merchant_risk"}]}],
    ],
)
def test_permission_denied_dependency_map_fail_closed(claim_dependency_map):
    state = {
        "business_context": {
            "facts": {"order": {"status": "delivered"}},
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": claim_dependency_map,
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "final_response"


def test_permission_denied_nonrequired_still_routes_to_rag_context_build():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {
            "facts": {"order": {"status": "delivered"}},
            "errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}],
        },
        "claim_dependency_map": [
            {
                "claim_id": "order_status",
                "depends_on_refs": [{"resource_type": "order", "resource_id": "ORD-001"}],
            }
        ],
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "rag_context_build"


def test_max_iterations_does_not_force_insufficient_before_rag_context_build():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
        "termination_reason": "max_iterations_reached",
    }

    assert route_after_investigate(state) == "rag_context_build"


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "order_status_inquiry"},
        {"business_context": {"missing_required_facts": ["order_id"]}},
        {"business_context": {"errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}]}},
        {"retrieval_status": "error"},
        {"best_score": 0.1},
        {"primary_intent": 123, "business_context": "not-a-dict", "retrieval_status": object()},
    ],
)
def test_route_after_investigate_totality(state):
    assert route_after_investigate(state) in VALID_INVESTIGATE_KEYS


def test_empty_state_safe_default():
    assert route_after_investigate({}) == "final_response"
