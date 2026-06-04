from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from tests.agent.conftest import FakeLLM

from src.agent import trace as trace_module
from src.agent.graph import build_graph
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes import extract_slots as extract_slots_module
from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.agent.nodes import load_business_context as load_business_context_module
from src.agent.nodes import retrieve_policy_evidence as retrieve_policy_evidence_module


EVIDENCE = [
    {
        "doc_key": "policy_refund_timeout",
        "chunk_id": "chunk_001",
        "title": "退款超时规则",
        "section": "第一条",
        "score": 0.82,
        "text": "退款超时时，客服应核实支付通道和退款状态。",
    }
]

INVESTIGATION_STATE_FIELDS = {
    "investigation_result",
    "investigation_steps",
    "investigation_trigger_reason",
    "investigation_path",
}


def _state(query: str, thread_id: str = "graph-test-thread") -> dict:
    return {
        "user_query": query,
        "thread_id": thread_id,
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "role": "support_agent",
    }


def _config(thread_id: str = "graph-test-thread") -> dict:
    return {"configurable": {"thread_id": thread_id, "session": AsyncMock()}}


def _intent(intent: str) -> dict:
    return {"intent": intent, "confidence": 0.95, "reasoning": "test"}


def _slots(order_id: str | None = None) -> dict:
    return {
        "order_id": order_id,
        "refund_case_id": None,
        "ticket_id": None,
        "merchant_id": None,
        "customer_id": None,
        "issue_type": "超时未退款" if order_id else None,
    }


def _recommendation(action: str = "建议退款", evidence_refs: list[dict] | None = None) -> dict:
    return {
        "recommended_action": action,
        "reasoning_summary": "根据规则",
        "evidence_refs": evidence_refs
        or [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "confidence": 0.85,
        "risk_level": "low",
        "missing_info": [],
    }


def _risk() -> dict:
    return {"risk_level": "low", "risk_reason": "standard refund", "approval_required": False, "rule_ref": "LR-01"}


def _policy_result(*, status: str = "strong_evidence", best_score: float = 0.82, evidence: list[dict] | None = None):
    return {
        "status": "success",
        "data": {
            "retrieval_status": status,
            "best_score": best_score,
            "evidence": deepcopy(EVIDENCE if evidence is None else evidence),
            "fallback_message": None if evidence else "没有找到相关政策证据。",
        },
        "error": {},
    }


class SequencedFakeLLM:
    def __init__(self, responses: Sequence[dict]):
        self._responses = list(responses)
        self._index = 0

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                response = fake._responses[min(fake._index, len(fake._responses) - 1)]
                fake._index += 1
                if issubclass(schema, BaseModel):
                    return schema.model_validate(response)
                return response

        return _Wrapper()


def _patch_graph_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    intent: str = "policy_qa",
    order_id: str | None = None,
    search_result: dict | None = None,
    classify_llm=None,
):
    get_order = AsyncMock(
        return_value={
            "status": "success",
            "data": {"order_no": order_id or "ORD-001", "status": "delivered", "amount": "199.00"},
            "error": {},
        }
    )
    search_policy = AsyncMock(return_value=search_result or _policy_result())

    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: classify_llm or FakeLLM(_intent(intent)))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots(order_id)))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    monkeypatch.setattr(load_business_context_module, "get_order", get_order)
    monkeypatch.setattr(load_business_context_module, "get_refund_case", AsyncMock())
    monkeypatch.setattr(load_business_context_module, "get_ticket", AsyncMock())
    monkeypatch.setattr(retrieve_policy_evidence_module, "search_policy", search_policy)
    return {"get_order": get_order, "search_policy": search_policy}


@pytest.fixture
def graph_with_fake_llm(monkeypatch):
    mocks = _patch_graph_dependencies(monkeypatch)
    return build_graph(MemorySaver()), mocks


@pytest.mark.asyncio
async def test_happy_path_policy_qa(graph_with_fake_llm):
    graph, mocks = graph_with_fake_llm

    final_state = await graph.ainvoke(_state("退款超时规则是什么？"), _config())

    assert final_state["final_response"]
    assert final_state["current_intent"] == "policy_qa"
    assert final_state["recommendation_draft"]["evidence_refs"]
    assert final_state["risk_assessment"]["risk_level"] in ("low", "medium", "high")
    assert len(final_state["trace_steps"]) == 8
    assert final_state["current_run_id"] is not None
    assert INVESTIGATION_STATE_FIELDS.isdisjoint(final_state)
    assert not any("investigat" in step.get("node", "") for step in final_state["trace_steps"])
    mocks["search_policy"].assert_awaited_once()


@pytest.mark.asyncio
async def test_happy_path_refund_troubleshooting(monkeypatch):
    mocks = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("订单ORD-001退款为什么没到账？"), _config())

    assert final_state["current_intent"] == "refund_troubleshooting"
    assert final_state["business_context"] == {
        "order": {"order_no": "ORD-001", "status": "delivered", "amount": "199.00"}
    }
    assert final_state["final_response"]
    mocks["get_order"].assert_awaited_once()


@pytest.mark.asyncio
async def test_insufficient_evidence_path(monkeypatch):
    _patch_graph_dependencies(
        monkeypatch,
        search_result=_policy_result(status="no_evidence", best_score=0.0, evidence=[]),
    )
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("这个问题没有任何相关规则"), _config())

    assert final_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert "没有找到" in final_state["final_response"] or "insufficient" in final_state["final_response"]
    assert "通常可以退款" not in final_state["final_response"]
    assert "应该退款" not in final_state["final_response"]


@pytest.mark.asyncio
async def test_order_fact_query_keeps_business_context_when_policy_evidence_is_missing(monkeypatch):
    mocks = _patch_graph_dependencies(
        monkeypatch,
        intent="unknown",
        order_id="ORD-001",
        search_result=_policy_result(status="no_evidence", best_score=0.0, evidence=[]),
    )
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("ORD-001 订单是什么？"), _config())

    assert final_state["business_context"]["order"]["order_no"] == "ORD-001"
    assert final_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert "已查询到订单信息" in final_state["final_response"]
    assert "ORD-001" in final_state["final_response"]
    assert "关于退款风险" in final_state["final_response"]
    mocks["get_order"].assert_awaited_once()


@pytest.mark.asyncio
async def test_order_not_found_path(monkeypatch):
    mocks = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-MISSING")
    mocks["get_order"].return_value = {
        "status": "error",
        "data": {},
        "error": {
            "error_code": "ORDER_NOT_FOUND",
            "message": "not found",
            "retryable": False,
            "should_stop": False,
        },
    }
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("订单ORD-MISSING退款为什么没到账？"), _config())

    assert final_state["final_response"]
    assert final_state["node_errors"] or not final_state["business_context"]


@pytest.mark.asyncio
async def test_llm_parse_failure_path(monkeypatch):
    retry_llm = SequencedFakeLLM(
        [
            {"intent": "bad_intent", "confidence": 0.95, "reasoning": "invalid"},
            _intent("policy_qa"),
        ]
    )
    _patch_graph_dependencies(monkeypatch, classify_llm=retry_llm)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("退款超时规则是什么？"), _config())

    assert final_state["current_intent"] == "policy_qa"


@pytest.mark.asyncio
async def test_cross_turn_context_isolation(monkeypatch):
    _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    graph = build_graph(MemorySaver())
    thread_id = "cross-turn-thread"

    await graph.ainvoke(_state("订单ORD-001退款为什么没到账？", thread_id), _config(thread_id))

    _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-002")
    second_state = await graph.ainvoke(_state("订单ORD-002退款为什么没到账？", thread_id), _config(thread_id))

    assert second_state["business_context"]["order"]["order_no"] == "ORD-002"
    assert "ORD-001" not in str(second_state["business_context"])
    assert "ORD-001" not in str(second_state["trace_steps"])


@pytest.mark.asyncio
async def test_same_thread_evidence_refs_survive_next_turn(monkeypatch):
    mocks = _patch_graph_dependencies(monkeypatch, search_result=_policy_result())
    graph = build_graph(MemorySaver())
    thread_id = "evidence-memory-thread"

    first_state = await graph.ainvoke(_state("退款超时规则是什么？", thread_id), _config(thread_id))

    assert any(ref["chunk_id"] == "chunk_001" for ref in first_state["evidence_refs"])

    mocks["search_policy"].return_value = _policy_result(status="no_evidence", best_score=0.0, evidence=[])
    second_state = await graph.ainvoke(_state("这个新问题没有规则依据", thread_id), _config(thread_id))

    assert second_state["retrieved_evidence"]["data"]["evidence"] == []
    assert any(
        ref["doc_key"] == "policy_refund_timeout" and ref["chunk_id"] == "chunk_001"
        for ref in second_state["evidence_refs"]
    )
    assert second_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_same_thread_stale_investigation_state_is_reset_on_next_turn(monkeypatch):
    _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    graph = build_graph(MemorySaver())
    thread_id = "stale-investigation-thread"
    stale_state = _state("订单ORD-001退款为什么没到账？", thread_id) | {
        "investigation_result": {"facts": ["stale"]},
        "investigation_steps": [{"tool": "search_policy"}],
        "investigation_trigger_reason": "stale_reason",
        "investigation_path": "investigation",
    }

    await graph.ainvoke(stale_state, _config(thread_id))

    _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    final_state = await graph.ainvoke(_state("退款超时规则是什么？", thread_id), _config(thread_id))

    assert final_state["investigation_result"] is None
    assert final_state["investigation_steps"] is None
    assert final_state["investigation_trigger_reason"] is None
    assert final_state["investigation_path"] is None


@pytest.mark.asyncio
async def test_trace_summary_shape(graph_with_fake_llm):
    graph, _ = graph_with_fake_llm
    final_state = await graph.ainvoke(_state("退款超时规则是什么？"), _config())

    summary = trace_module.build_trace_summary(final_state["current_run_id"], final_state, 1000)

    assert set(summary) == {
        "run_id",
        "intent",
        "nodes_executed",
        "tools_called",
        "evidence_count",
        "risk_level",
        "total_latency_ms",
        "final_status",
    }
    assert all(isinstance(node, str) for node in summary["nodes_executed"])
    assert summary["tools_called"] == ["search_policy"]
    assert summary["evidence_count"] == 1
    assert summary["final_status"] in ("completed", "insufficient_evidence", "error")
    assert INVESTIGATION_STATE_FIELDS.isdisjoint(summary)
