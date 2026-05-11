from __future__ import annotations

import pytest

from tests.agent.conftest import FakeLLM

from src.agent.nodes import classify_intent as classify_intent_module


@pytest.mark.asyncio
async def test_classify_intent_success(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "refund_troubleshooting"


@pytest.mark.asyncio
async def test_classify_intent_llm_failure_returns_unknown(monkeypatch, base_state):
    monkeypatch.setattr(
        classify_intent_module,
        "_get_llm",
        lambda: FakeLLM({"intent": "not_valid", "confidence": 0.95, "reasoning": "bad enum"}),
    )

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "unknown"
    assert result["node_errors"]
