from __future__ import annotations

import pytest

from src.agent.nodes.clarification_gate import clarification_gate
from src.agent.nodes.session_memory_load import session_memory_load


@pytest.mark.asyncio
async def test_empty_session_adapter_routing():
    result = await session_memory_load({"trace_steps": []}, {})

    assert result["session_memory"]["active_slots"] == {}
    assert result["session_memory"]["source"] in {"empty_adapter", "unavailable"}
    assert result["session_memory"]["continuity_claimed"] is False
    assert result["session_memory"].get("fallback_reason") in {None, "missing_async_session"}
    assert result["trace_steps"][-1]["node"] == "session_memory_load"


@pytest.mark.asyncio
async def test_clarification_gate_uses_business_context_missing_required_facts():
    result = await clarification_gate(
        {
            "business_context": {"missing_required_facts": ["case_identifier"]},
            "trace_steps": [],
        },
        {},
    )

    assert result["clarification_request"]["reason"] == "missing_required_slots"
    assert result["clarification_request"]["questions"]
    assert result["trace_steps"][-1]["node"] == "clarification_gate"
