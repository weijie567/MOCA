from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agent.schemas import InvestigationResult
from src.agent.state import AgentState


def test_investigation_result_accepts_versioned_prompt_contract():
    result = InvestigationResult.model_validate(_complete_investigation_result_payload())

    assert result.schema_version == "v1"
    assert result.confidence == 0.72
    assert result.evidence_refs[0].chunk_id == "chunk_001"


def test_agent_state_investigation_keys_are_optional():
    minimal_state: AgentState = {
        "thread_id": "thread-001",
        "tenant_id": "tenant-001",
        "user_id": "user-001",
        "role": "support_agent",
    }
    investigation_state: AgentState = {
        **minimal_state,
        "investigation_result": {"schema_version": "v1", "facts": []},
        "investigation_steps": [],
        "investigation_trigger_reason": "ambiguous_question",
        "investigation_path": "dormant",
    }

    assert "investigation_result" not in minimal_state
    assert investigation_state["investigation_path"] == "dormant"


def _complete_investigation_result_payload(**overrides):
    payload = {
        "schema_version": "v1",
        "facts": ["订单已付款", "退款仍在处理中"],
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "missing_info": ["支付通道回执"],
        "candidate_action": {"action_type": "manual_review", "target_id": "ORD-001"},
        "confidence": 0.72,
        "stop_reason": "sufficient_evidence",
        "safety_notes": ["仅建议人工复核，不执行补偿动作"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_investigation_result_rejects_invalid_confidence_bounds(confidence: float):
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(_complete_investigation_result_payload(confidence=confidence))


def test_investigation_result_rejects_invalid_stop_reason_literal():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(
            _complete_investigation_result_payload(stop_reason="autonomous_action_completed")
        )


def test_investigation_result_rejects_unsupported_schema_version():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(_complete_investigation_result_payload(schema_version="v2"))


def test_investigation_result_rejects_unknown_prompt_fields():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(
            _complete_investigation_result_payload(raw_tool_payload={"refund_id": "RF-001"})
        )
