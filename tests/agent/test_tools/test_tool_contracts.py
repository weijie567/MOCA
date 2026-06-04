from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from src.agent.schemas import InvestigationResult
from src.agent.state import AgentState
from src.agent.tools.contracts import (
    ToolExecutionResult,
    ToolInvocationContext,
    ToolRegistryEntry,
)


class ExampleInput(BaseModel):
    order_id: str


class ExampleOutput(BaseModel):
    order_no: str


def _complete_registry_entry(**overrides):
    payload = {
        "name": "get_order",
        "description": "Read order details for an explicit order identifier.",
        "input_schema": ExampleInput,
        "output_schema": ExampleOutput,
        "risk_level": "read",
        "side_effect": "none",
        "allowed_in_investigator": True,
        "when_to_use": "Use when the user provides an order id and order facts are needed.",
        "required_identifiers": ["order_id"],
        "result_summary_fields": ["order_no"],
    }
    payload.update(overrides)
    return ToolRegistryEntry.model_validate(payload)


def test_registry_entry_accepts_complete_metadata():
    entry = _complete_registry_entry()

    assert entry.name == "get_order"
    assert entry.input_schema is ExampleInput
    assert entry.output_schema is ExampleOutput
    assert entry.allowed_in_investigator is True


def test_registry_entry_accepts_complete_retrieval_metadata():
    entry = _complete_registry_entry(
        name="search_policy",
        description="Retrieve policy evidence for a merchant operations question.",
        risk_level="retrieval",
        side_effect="retrieval",
        required_identifiers=[],
        result_summary_fields=["retrieval_status", "best_score", "evidence_count"],
    )

    assert entry.name == "search_policy"
    assert entry.risk_level == "retrieval"
    assert entry.side_effect == "retrieval"
    assert entry.result_summary_fields == ["retrieval_status", "best_score", "evidence_count"]


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "description",
        "input_schema",
        "output_schema",
        "risk_level",
        "side_effect",
        "allowed_in_investigator",
        "when_to_use",
        "required_identifiers",
        "result_summary_fields",
    ],
)
def test_registry_entry_rejects_missing_required_metadata(field: str):
    payload = _complete_registry_entry().model_dump()
    payload["input_schema"] = ExampleInput
    payload["output_schema"] = ExampleOutput
    payload.pop(field)

    with pytest.raises(ValidationError):
        ToolRegistryEntry.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("risk_level", "dangerous"),
        ("side_effect", "mutates_database"),
    ],
)
def test_registry_entry_rejects_invalid_safety_literals(field: str, value: str):
    with pytest.raises(ValidationError):
        _complete_registry_entry(**{field: value})


def test_registry_entry_rejects_unsafe_investigator_metadata():
    with pytest.raises(ValidationError):
        _complete_registry_entry(risk_level="write", side_effect="write")


def test_invocation_context_rejects_invalid_caller_literal():
    with pytest.raises(ValidationError):
        ToolInvocationContext.model_validate(
            {
                "tenant_id": str(uuid4()),
                "user_id": str(uuid4()),
                "role": "support_agent",
                "session": AsyncMock(),
                "caller": "unbounded_agent",
            }
        )


def test_tool_execution_result_rejects_invalid_status_literal():
    with pytest.raises(ValidationError):
        ToolExecutionResult.model_validate(
            {
                "status": "pending",
                "error": None,
                "evidence_refs": [],
                "summary": {},
            }
        )


def test_tool_execution_result_rejects_invalid_error_code_literal():
    with pytest.raises(ValidationError):
        ToolExecutionResult.model_validate(
            {
                "status": "error",
                "error": {
                    "error_code": "network_timeout",
                    "message": "tool failed",
                    "retryable": False,
                },
                "evidence_refs": [],
                "summary": {},
            }
        )


def test_tool_execution_result_accepts_prompt_declared_summary_container():
    result = ToolExecutionResult.model_validate(
        {
            "status": "success",
            "error": None,
            "evidence_refs": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "退款超时规则",
                    "section": "S1",
                    "confidence": 0.82,
                }
            ],
            "summary": {"retrieval_status": "strong_evidence", "best_score": 0.82},
        }
    )

    assert result.summary == {"retrieval_status": "strong_evidence", "best_score": 0.82}
    assert result.evidence_refs[0].chunk_id == "chunk_001"
    assert result.evidence_refs[0].section == "S1"


def test_tool_execution_result_rejects_unknown_prompt_facing_fields():
    with pytest.raises(ValidationError):
        ToolExecutionResult.model_validate(
            {
                "status": "success",
                "error": None,
                "evidence_refs": [],
                "summary": {"order_no": "ORD-001"},
                "raw_payload": {"buyer_name": "hidden from prompt"},
            }
        )


def test_tool_execution_result_rejects_unknown_evidence_ref_fields():
    with pytest.raises(ValidationError):
        ToolExecutionResult.model_validate(
            {
                "status": "success",
                "error": None,
                "evidence_refs": [
                    {
                        "doc_key": "policy_refund_timeout",
                        "chunk_id": "chunk_001",
                        "title": "退款超时规则",
                        "text": "raw policy text must stay out of prompt-facing refs",
                    }
                ],
                "summary": {},
            }
        )


def test_investigation_result_accepts_versioned_prompt_contract():
    result = InvestigationResult.model_validate(
        _complete_investigation_result_payload()
    )

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
