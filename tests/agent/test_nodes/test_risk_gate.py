from __future__ import annotations

import pytest

from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes import risk_gate as risk_gate_module
from tests.agent.conftest import FakeLLM
from tests.agent.test_nodes.test_assess_risk_and_approval import (
    RaisingLLM,
    _claim_bundle_with_safe_refs,
    _phase34_business_context,
)


_CANONICAL_NODE = "risk_gate"
_LEGACY_NODE = "assess_risk_and_approval"


def _action_state(base_state: dict) -> dict:
    tenant_id = base_state["tenant_id"]
    return {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
            "compensation_amount": 10,
        },
        "claim_verification_bundle": _claim_bundle_with_safe_refs(tenant_id),
        "business_context": _phase34_business_context(tenant_id),
    }


def _assert_no_current_run_legacy_identity(result: dict) -> None:
    assert _LEGACY_NODE not in (result.get("llm_outputs") or {})
    assert all(step.get("node") != _LEGACY_NODE for step in result.get("trace_steps") or [])
    assert all(error.get("node") != _LEGACY_NODE for error in result.get("node_errors") or [])
    assert result.get("fallback_source") != _LEGACY_NODE
    assert result.get("resume_route") != _LEGACY_NODE


@pytest.mark.asyncio
async def test_canonical_risk_gate_success_writes_risk_gate_identity_only(monkeypatch, base_state):
    """D-57-04/D-57-08: current-run authority belongs to risk_gate."""

    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "low",
                "risk_reason": "Small coupon is auto-allowed.",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )

    result = await risk_gate_module.risk_gate(_action_state(base_state))

    assert _CANONICAL_NODE in result["llm_outputs"]
    assert result["llm_outputs"][_CANONICAL_NODE] == result["risk_assessment"]
    assert result["trace_steps"][-1]["node"] == _CANONICAL_NODE
    _assert_no_current_run_legacy_identity(result)


@pytest.mark.asyncio
async def test_canonical_risk_gate_missing_claim_bundle_fails_closed_with_canonical_trace(
    monkeypatch, base_state
):
    """D-57-06/D-57-17: missing claim support fails closed before risk LLM."""

    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("missing claim bundle must block before risk LLM")

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "business_context": _phase34_business_context(base_state["tenant_id"]),
    }

    result = await risk_gate_module.risk_gate(state)

    assert result["proposed_action"] is None
    assert result["trace_steps"][-1]["status"] == "blocked"
    assert result["trace_steps"][-1]["node"] == _CANONICAL_NODE
    _assert_no_current_run_legacy_identity(result)


@pytest.mark.asyncio
async def test_canonical_risk_gate_binding_failure_keeps_fail_closed_metadata_canonical(
    monkeypatch, base_state
):
    """D-57-05/D-57-06: fail-closed binding behavior keeps canonical current-run identity."""

    monkeypatch.setattr(
        assess_risk_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "high",
                "risk_reason": "Coupon amount requires manager approval.",
                "approval_required": True,
                "rule_ref": "HR-COUPON",
            }
        ),
    )
    state = {
        **_action_state(base_state),
        "business_context": _phase34_business_context(base_state["tenant_id"], merchant_id=None),
    }

    result = await risk_gate_module.risk_gate(state)

    assert result["proposed_action"] is None
    assert result["approval_plan"] is None
    assert result["final_response"] == assess_risk_module.SAFE_MANUAL_REVIEW_RESPONSE
    assert result["llm_outputs"][_CANONICAL_NODE]["risk_level"] == "high"
    assert result["risk_assessment"]["risk_level"] == "manual_review"
    assert result["trace_steps"][-1]["node"] == _CANONICAL_NODE
    _assert_no_current_run_legacy_identity(result)


@pytest.mark.asyncio
async def test_canonical_risk_gate_expected_error_records_node_errors_with_risk_gate(
    monkeypatch, base_state
):
    """D-57-07/D-57-08: structured-output fallback records canonical error identity."""

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: RaisingLLM(ValueError("invalid")))

    result = await risk_gate_module.risk_gate(_action_state(base_state))

    assert result["risk_assessment"]["risk_level"] == "low"
    assert result["node_errors"][0]["node"] == _CANONICAL_NODE
    assert result["node_errors"][0]["retry_count"] == 2
    assert result["trace_steps"][-1]["node"] == _CANONICAL_NODE
    _assert_no_current_run_legacy_identity(result)
