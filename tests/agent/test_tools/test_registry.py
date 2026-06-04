from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.agent.tools.contracts import ToolInvocationContext, ToolRegistryEntry
from src.agent.tools.registry import RegisteredTool, ToolRegistry


class _Input(BaseModel):
    identifier: str


class _Output(BaseModel):
    identifier: str


class _ToolOutput(BaseModel):
    status: str
    data: dict = {}
    error: dict = {}


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
        output_schema=_Output,
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
        output_schema=_ToolOutput,
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
        output_schema=_ToolOutput,
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
