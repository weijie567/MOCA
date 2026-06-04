from __future__ import annotations

import pytest
from pydantic import BaseModel
from unittest.mock import AsyncMock

from src.agent.tools.contracts import ToolInvocationContext, ToolRegistryEntry
from src.agent.tools.registry import RegisteredTool, ToolRegistry


class _Input(BaseModel):
    identifier: str


class _Output(BaseModel):
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


def test_registry_rejects_investigator_entry_outside_locked_allowlist() -> None:
    adapter = AsyncMock()

    with pytest.raises(ValueError, match="not in the investigator allowlist"):
        ToolRegistry([RegisteredTool(entry=_entry("create_coupon_grant_draft"), adapter=adapter)])


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

