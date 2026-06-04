from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.agent.tools.contracts import ToolInvocationContext, ToolRegistryEntry
from src.agent.tools.registry import RegisteredTool, ToolOutput, ToolRegistry


class _Input(BaseModel):
    identifier: str


def _entry(
    name: str,
    *,
    risk_level: str = "read",
    side_effect: str = "read_only",
    allowed_in_investigator: bool = True,
) -> ToolRegistryEntry:
    return ToolRegistryEntry(
        name=name,
        description=f"{name} test entry",
        input_schema=_Input,
        output_schema=ToolOutput,
        risk_level=risk_level,
        side_effect=side_effect,
        allowed_in_investigator=allowed_in_investigator,
        when_to_use="Use in registry tests.",
        required_identifiers=["identifier"],
        result_summary_fields=["identifier"],
    )


def _context(caller: str = "investigator") -> ToolInvocationContext:
    return ToolInvocationContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support",
        session=object(),
        caller=caller,
    )


def test_default_investigator_allowlist_is_exact_locked_set() -> None:
    registry = ToolRegistry()

    assert set(registry.investigator_tool_names()) == {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "search_policy",
    }


def test_unsafe_and_approval_operations_are_excluded_from_investigator_tools() -> None:
    unsafe_names = {
        "create_coupon_grant_draft",
        "execute_action",
        "approve_request",
        "reject_request",
        "approval_mutation",
    }

    registry = ToolRegistry()

    assert unsafe_names.isdisjoint(registry.investigator_tool_names())


def test_registry_rejects_investigator_entry_outside_locked_allowlist() -> None:
    adapter = AsyncMock()

    with pytest.raises(ValueError, match="not in the investigator allowlist"):
        ToolRegistry([RegisteredTool(entry=_entry("create_coupon_grant_draft"), adapter=adapter)])


def test_registry_creation_fails_on_missing_schema_metadata() -> None:
    adapter = AsyncMock()
    incomplete_entry = ToolRegistryEntry.model_construct(
        name="get_order",
        description="Incomplete metadata",
        output_schema=ToolOutput,
        risk_level="read",
        side_effect="read_only",
        allowed_in_investigator=True,
        when_to_use="Use in tests.",
        required_identifiers=["identifier"],
        result_summary_fields=["identifier"],
    )

    with pytest.raises(ValueError, match="input_schema"):
        ToolRegistry([RegisteredTool(entry=incomplete_entry, adapter=adapter)])


def test_registry_creation_fails_on_unsafe_investigator_metadata() -> None:
    adapter = AsyncMock()
    unsafe_entry = ToolRegistryEntry.model_construct(
        name="get_order",
        description="Unsafe metadata",
        input_schema=_Input,
        output_schema=ToolOutput,
        risk_level="write",
        side_effect="write",
        allowed_in_investigator=True,
        when_to_use="Use in tests.",
        required_identifiers=["identifier"],
        result_summary_fields=["identifier"],
    )

    with pytest.raises(ValueError, match="unsafe investigator risk"):
        ToolRegistry([RegisteredTool(entry=unsafe_entry, adapter=adapter)])


@pytest.mark.asyncio
async def test_unknown_tool_returns_structured_not_found_without_execution() -> None:
    registry = ToolRegistry([])

    result = await registry.invoke("missing_tool", {"identifier": "abc"}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "not_found"


@pytest.mark.asyncio
async def test_disallowed_invocation_returns_structured_result_without_execution() -> None:
    adapter = AsyncMock(return_value={"status": "success", "data": {"identifier": "abc"}, "error": {}})
    registry = ToolRegistry(
        [
            RegisteredTool(
                entry=_entry("create_coupon_grant_draft", risk_level="write", side_effect="write", allowed_in_investigator=False),
                adapter=adapter,
            )
        ]
    )

    result = await registry.invoke("create_coupon_grant_draft", {"identifier": "abc"}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "unsafe_tool_request"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_schema_invalid_invocation_returns_validation_error_without_execution() -> None:
    adapter = AsyncMock(return_value={"status": "success", "data": {"identifier": "abc"}, "error": {}})
    registry = ToolRegistry([RegisteredTool(entry=_entry("get_order"), adapter=adapter)])

    result = await registry.invoke("get_order", {}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "validation_error"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_malformed_output_status_returns_validation_error_without_prompt_summary() -> None:
    adapter = AsyncMock(return_value={"status": "pending", "data": {"identifier": "abc"}, "error": {}})
    registry = ToolRegistry([RegisteredTool(entry=_entry("get_order"), adapter=adapter)])

    result = await registry.invoke("get_order", {"identifier": "abc"}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "validation_error"
    assert "identifier" not in result.summary
    assert "identifier" not in str(result.model_dump())
    adapter.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_output_conversion_returns_structured_error_without_raising() -> None:
    adapter = AsyncMock(return_value={"data": {"identifier": "abc"}, "error": {}})
    registry = ToolRegistry([RegisteredTool(entry=_entry("get_order"), adapter=adapter)])

    result = await registry.invoke("get_order", {"identifier": "abc"}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code in {"validation_error", "tool_error"}
    adapter.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_business_context_rejects_read_tool_with_write_side_effect() -> None:
    adapter = AsyncMock(return_value={"status": "success", "data": {"identifier": "abc"}, "error": {}})
    unsafe_entry = ToolRegistryEntry.model_construct(
        name="get_order",
        description="Unsafe deterministic read metadata",
        input_schema=_Input,
        output_schema=ToolOutput,
        risk_level="read",
        side_effect="write",
        allowed_in_investigator=False,
        when_to_use="Use in tests.",
        required_identifiers=["identifier"],
        result_summary_fields=["identifier"],
    )
    registry = ToolRegistry([RegisteredTool(entry=unsafe_entry, adapter=adapter)])

    result = await registry.invoke("get_order", {"identifier": "abc"}, _context("load_business_context"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "unsafe_tool_request"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_rejects_retrieval_tool_with_read_only_side_effect() -> None:
    adapter = AsyncMock(return_value={"status": "success", "data": {"identifier": "abc"}, "error": {}})
    unsafe_entry = ToolRegistryEntry.model_construct(
        name="search_policy",
        description="Unsafe retrieval metadata",
        input_schema=_Input,
        output_schema=ToolOutput,
        risk_level="retrieval",
        side_effect="read_only",
        allowed_in_investigator=False,
        when_to_use="Use in tests.",
        required_identifiers=["identifier"],
        result_summary_fields=["identifier"],
    )
    registry = ToolRegistry([RegisteredTool(entry=unsafe_entry, adapter=adapter)])

    result = await registry.invoke("search_policy", {"identifier": "abc"}, _context("retrieve_policy_evidence"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "unsafe_tool_request"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_registry_uses_public_search_adapter_and_sanitizes_raw_policy_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "retrieval_status": "strong_evidence",
                "best_score": 0.91,
                "fallback_message": None,
                "evidence": [
                    {
                        "doc_key": "policy_refund_timeout",
                        "chunk_id": "chunk-1",
                        "title": "Refund timeout policy",
                        "section": "S1",
                        "score": 0.91,
                        "text": "Raw evidence text must remain internal.",
                    }
                ],
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.agent.tools.adapters.search_policy", tool)
    context = ToolInvocationContext(
        tenant_id=str(uuid4()),
        user_id="user-1",
        role="support_agent",
        session=object(),
        caller="investigator",
    )

    result = await ToolRegistry().invoke("search_policy", {"query": "refund timeout"}, context)

    assert result.status == "success"
    assert result.error is None
    assert result.summary == {
        "retrieval_status": "strong_evidence",
        "best_score": 0.91,
        "fallback_message": None,
    }
    assert result.model_dump().keys() == {"status", "error", "evidence_refs", "summary"}
    assert result.evidence_refs[0].doc_key == "policy_refund_timeout"
    assert result.evidence_refs[0].chunk_id == "chunk-1"
    assert result.evidence_refs[0].section == "S1"
    assert "text" not in result.summary
    assert "text" not in result.evidence_refs[0].model_dump(exclude_none=True)
    assert "Raw evidence text" not in str(result.model_dump())
    tool.assert_awaited_once()
