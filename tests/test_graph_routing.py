from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import route_after_approval, route_after_risk
from src.agent.nodes import assess_risk_and_approval as risk_module
from src.agent.routing import route_after_investigate
from src.agent.schemas import RiskAssessment
from src.db.models import ActionSafetySnapshot
from tests.approvals.test_service_transitions import _create_run, _evidence_ref


VALID_INVESTIGATE_KEYS = {"final_response", "clarification_gate", "recommendation_generation"}
ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64


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


def _risk_route_state(**overrides) -> dict:
    state = {
        "risk_assessment": {"approval_required": True, "risk_level": "high"},
        "proposed_action": {"action_type": "issue_coupon"},
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
        "safety_snapshot_verified": True,
    }
    state.update(overrides)
    return state


def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {
        "current_intent": "policy_qa",
        "risk_assessment": {"approval_required": False},
        "proposed_action": None,
    }

    assert route_after_risk(state) == "final_response"


def test_route_after_risk_returns_approval_gate_when_required_snapshot_refs_are_present():
    assert route_after_risk(_risk_route_state()) == "approval_gate"


def test_route_after_risk_returns_execute_action_for_auto_allowed_snapshot_verified_action():
    # Current graph node name is execute_action; this is the target action_draft path.
    state = _risk_route_state(risk_assessment={"approval_required": False, "risk_level": "low"})

    assert route_after_risk(state) == "execute_action"


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


def test_route_after_approval_returns_execute_action_on_trusted_approval_result_v1():
    state = {
        "approval_result": _approved_result(),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

    assert route_after_approval(state) == "execute_action"


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
    state = {"approval_result": _approved_result(decision_type=decision_type, status=status)}

    assert route_after_approval(state) == "final_response"


def test_route_after_approval_sends_edit_to_risk_reroute_not_action_draft():
    state = {
        "approval_result": _approved_result(
            decision_type="edit",
            status="superseded",
            new_action_payload_hash="sha256:" + "3" * 64,
            resume_route="assess_risk_and_approval",
        ),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

    assert route_after_approval(state) == "assess_risk_and_approval"


def test_route_after_approval_fails_closed_on_hash_mismatch():
    state = {
        "approval_result": _approved_result(action_payload_hash="sha256:" + "9" * 64),
        "action_payload_hash": ACTION_HASH,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": SNAPSHOT_HASH,
    }

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

    result = await risk_module.assess_risk_and_approval(
        {
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
            "business_context": {"refund_case": {"id": "RF-TEST-001", "requested_amount": "100.00"}},
            "evidence_refs": [_evidence_ref(tenant_id=tenant_id)],
            "trace_steps": [],
        },
        {"configurable": {"session": session}},
    )

    snapshot = (
        await session.execute(select(ActionSafetySnapshot).where(ActionSafetySnapshot.run_id == UUID(str(run_id))))
    ).scalar_one()

    assert result["auto_allowed"] is True
    assert result["action_payload_hash"] == snapshot.action_payload_hash
    assert result["safety_snapshot_ref"] == snapshot.snapshot_ref
    assert result["safety_snapshot_hash"] == snapshot.immutable_hash
    assert result["safety_snapshot_verified"] is True
    assert route_after_risk(result) == "execute_action"


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


def test_sufficient_context_to_recommendation():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
    }

    assert route_after_investigate(state) == "recommendation_generation"


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


def test_permission_denied_nonrequired_preserved():
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

    assert route_after_investigate(state) == "recommendation_generation"


def test_max_iterations_does_not_force_insufficient():
    state = {
        "primary_intent": "refund_troubleshooting",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
        "retrieval_status": "strong_evidence",
        "best_score": 0.9,
        "termination_reason": "max_iterations_reached",
    }

    assert route_after_investigate(state) == "recommendation_generation"


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
