from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

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
