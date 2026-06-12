from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.tools.contracts import ToolInvocationContext
from src.agent.tools.registry import ToolRegistry


def _context(caller: str = "retrieve_policy_evidence") -> ToolInvocationContext:
    return ToolInvocationContext(
        tenant_id="tenant-09",
        user_id="user-09",
        role="support",
        session=object(),
        caller=caller,
    )


@pytest.mark.asyncio
async def test_policy_compatibility_registry_keeps_search_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    search_policy = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "retrieval_status": "strong_evidence",
                "best_score": 0.9,
                "fallback_message": None,
                "evidence": [],
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.agent.tools.adapters.search_policy", search_policy)

    result = await ToolRegistry().invoke("search_policy", {"query": "refund"}, _context())

    assert result.status == "success"
    assert result.summary["retrieval_status"] == "strong_evidence"
    search_policy.assert_awaited_once()


@pytest.mark.asyncio
async def test_policy_compatibility_registry_rejects_non_policy_caller() -> None:
    result = await ToolRegistry().invoke("search_policy", {"query": "refund"}, _context("investigator"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "unsafe_tool_request"


@pytest.mark.asyncio
async def test_prior_line_registry_no_longer_declares_business_reads() -> None:
    result = await ToolRegistry().invoke("get_order", {"order_no": "ORD-09"}, _context())

    assert result.status == "error"
    assert result.error is not None
    assert result.error.error_code == "not_found"
