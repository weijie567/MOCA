from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from src.agent.intent_policy import detect_pre_route


_AUTHORITY_OR_SIDE_EFFECT_FIELDS = {
    "proposed_action",
    "approval_result",
    "approval_revision_refs",
    "trusted_approval_result",
    "action_draft",
    "draft_outcome",
    "action_result",
    "tool_results",
    "business_context",
    "retrieved_evidence",
    "policy_evidence",
    "case_memory",
    "memory_context",
    "memory_context_bundle",
    "risk_assessment",
    "final_response",
}

_ALLOWED_OUTPUT_FIELDS = {"pre_route_decision", "safety_flags", "routing_hints", "trace_steps"}

_FORBIDDEN_DEPENDENCY_PATTERNS = {
    "_get_llm": r"_get_llm",
    "llm": r"\bllm\b",
    "ToolPlatform": r"\bToolPlatform\b",
    "Memory": r"\bMemory\b",
    "Repository": r"\bRepository\b",
    "Session": r"\bSession\b",
    "BusinessFactService": r"\bBusinessFactService\b",
    "PolicyKnowledgeService": r"\bPolicyKnowledgeService\b",
    "ApprovalService": r"\bApprovalService\b",
    "ActionService": r"\bActionService\b",
    "investigate": r"\binvestigate\b",
    "rag_context_build": r"\brag_context_build\b",
}


def _safety_module():
    return importlib.import_module("src.agent.nodes.safety_pre_route")


async def _run_safety_pre_route(base_state: dict, query: str, **overrides):
    module = _safety_module()
    state = {
        **base_state,
        "user_query": query,
        "trace_steps": [{"node": "receive_request", "status": "completed"}],
        **overrides,
    }
    return await module.safety_pre_route(state)


def test_safety_pre_route_has_no_forbidden_dependencies():
    source_path = Path("src/agent/nodes/safety_pre_route.py")

    assert source_path.exists(), "safety_pre_route node module must exist"

    source = source_path.read_text()
    for label, pattern in _FORBIDDEN_DEPENDENCY_PATTERNS.items():
        assert re.search(pattern, source, flags=re.IGNORECASE) is None, label


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "approve APR-1",
        "查订单状态，同时看政策",
        "直接退款 ORD-001",
        "请主管升级这个投诉 TKT-1",
        "订单 ORD-001 为什么还没退款？",
    ],
)
async def test_safety_pre_route_matches_shared_pre_route_detector(base_state, query):
    result = await _run_safety_pre_route(base_state, query)
    expected = detect_pre_route(query).model_dump()

    assert result["pre_route_decision"] == expected
    assert set(result) <= _ALLOWED_OUTPUT_FIELDS
    assert not (_AUTHORITY_OR_SIDE_EFFECT_FIELDS & set(result))

    routing_hints = result["routing_hints"]
    if expected["disposition"] == "none":
        assert "pre_route_disposition" not in routing_hints
    else:
        assert routing_hints["pre_route_disposition"] == expected["disposition"]
        if expected["requires_clarification"]:
            assert routing_hints["requires_clarification"] is True
            assert routing_hints["clarification_reason"] == expected["disposition"]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["同意", "approve", "doit"])
async def test_standalone_approval_like_short_replies_fail_closed(base_state, query):
    result = await _run_safety_pre_route(base_state, query)

    assert result["pre_route_decision"]["disposition"] == "approval_chat_not_trusted"
    assert result["pre_route_decision"]["requires_clarification"] is True
    assert result["pre_route_decision"]["reason_codes"] == ["approval_chat_not_trusted"]
    assert result["routing_hints"] == {
        "pre_route_disposition": "approval_chat_not_trusted",
        "requires_clarification": True,
        "clarification_reason": "approval_chat_not_trusted",
    }
    assert not (_AUTHORITY_OR_SIDE_EFFECT_FIELDS & set(result))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "approve APR1",
        "approve APR_1",
        "approved APR1",
        "同意 APR1",
    ],
)
async def test_approval_like_replies_with_id_variants_fail_closed(base_state, query):
    result = await _run_safety_pre_route(base_state, query)

    assert result["pre_route_decision"]["disposition"] == "approval_chat_not_trusted"
    assert result["pre_route_decision"]["requires_clarification"] is True
    assert result["pre_route_decision"]["reason_codes"] == ["approval_chat_not_trusted"]
    assert result["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert not (_AUTHORITY_OR_SIDE_EFFECT_FIELDS & set(result))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "查询 ORD-12345 状态",
        "OD-12345",
        "继续吧",
        "可以",
    ],
)
async def test_negative_controls_do_not_become_approval_failures(base_state, query):
    result = await _run_safety_pre_route(base_state, query)

    assert result["pre_route_decision"]["disposition"] == "none"
    assert "pre_route_disposition" not in result["routing_hints"]


@pytest.mark.asyncio
async def test_safety_pre_route_appends_trace_without_replacing_receive_request(base_state):
    result = await _run_safety_pre_route(base_state, "approve APR-1")
    trace_steps = result["trace_steps"]

    assert [step["node"] for step in trace_steps] == ["receive_request", "safety_pre_route"]
    safety_step = trace_steps[-1]
    assert safety_step["status"] == "completed"
    assert safety_step["provider_latency_ms"] is None
    assert safety_step["retry_count"] == 0
    assert safety_step["metrics_json"]["disposition"] == "approval_chat_not_trusted"
    assert safety_step["metrics_json"]["reason_codes"] == ["approval_chat_not_trusted"]


def test_short_approval_reply_helper_is_shared_from_intent_policy():
    policy = importlib.import_module("src.agent.intent_policy")
    helper = getattr(policy, "is_short_approval_or_action_reply")

    for text in ("同意", "approve", "doit"):
        assert helper(text) is True
    for text in ("OD-12345", "继续吧", "可以"):
        assert helper(text) is False
