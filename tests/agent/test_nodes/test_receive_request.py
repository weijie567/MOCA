from __future__ import annotations

import pytest

from src.agent.nodes.receive_request import receive_request


@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "business_context": {"old": "data"},
        "trace_steps": [{"node": "old_node"}],
    }

    result = await receive_request(state)

    assert result["current_intent"] is None
    assert result["business_context"] is None
    assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
    assert result["current_run_id"] is not None


@pytest.mark.asyncio
async def test_receive_request_new_run_id_each_call(base_state):
    first = await receive_request(base_state)
    second = await receive_request(base_state)

    assert first["current_run_id"] != second["current_run_id"]


@pytest.mark.asyncio
async def test_receive_request_preserves_api_run_id_when_provided(base_state):
    result = await receive_request({**base_state, "current_run_id": "api-run-001"})

    assert result["current_run_id"] == "api-run-001"
