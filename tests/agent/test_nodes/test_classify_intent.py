from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.agent.conftest import FakeLLM

from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.schemas import IntentResultV3


def _intent_v3(**overrides):
    payload = {
        "schema_version": "intent_result.v3",
        "primary_intent": "refund_troubleshooting",
        "requested_operation": "read_status",
        "confidence": 0.95,
        "calibrated_confidence": 0.92,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-001"},
        "routing_hints": {},
        "classifier_version": "intent_classifier.v2",
        "calibration_version": "calibration.unverified",
        "reason_codes": ["test"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_classify_intent_success(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "refund_troubleshooting"
    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 0.95
    assert result["risk_tier"] == "read_only"
    assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
    assert result["required_slots"]["any_of"] == [["order_id", "refund_case_id"]]


@pytest.mark.asyncio
async def test_classify_intent_llm_failure_returns_unknown(monkeypatch, base_state):
    monkeypatch.setattr(
        classify_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            {"primary_intent": "not_valid", "confidence": 0.95, "approval_result": {"decision": "approve"}}
        ),
    )

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "unsupported"
    assert result["risk_tier"] == "read_only"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert "approval_result" not in result
    assert result["node_errors"]


def test_intent_result_v3_rejects_approval_result_extra_field():
    with pytest.raises(ValidationError):
        IntentResultV3.model_validate(_intent_v3(approval_result={"decision": "approve"}))


@pytest.mark.asyncio
async def test_approval_chat_pre_route_overrides_llm(monkeypatch, base_state):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent_v3(primary_intent="policy_qa")))

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

    assert result["current_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "policy_qa"
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "unsupported"
    assert result["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert "approval_result" not in result
    assert "resume" not in result
