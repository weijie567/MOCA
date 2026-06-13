from __future__ import annotations

import pytest

from src.agent.nodes.session_memory_load import session_memory_load


@pytest.mark.asyncio
async def test_empty_session_adapter_routing():
    result = await session_memory_load({"trace_steps": []}, {})

    assert result["session_memory"]["active_slots"] == {}
    assert result["session_memory"]["source"] == "empty_adapter"
    assert result["session_memory"]["continuity_claimed"] is False
    assert result["trace_steps"][-1]["node"] == "session_memory_load"
