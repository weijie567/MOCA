from __future__ import annotations

from collections.abc import Sequence
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
from src.business_tools.schemas import BusinessContextV1, ToolResultV2
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult


EVIDENCE = [
    EvidenceRefV1.build(
        tenant_id="tenant",
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v1",
        text="退款超时时，客服应核实支付通道和退款状态。",
        retrieved_at="2026-06-07T02:30:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.82,
        rank=1,
    )
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
    return {
        "configurable": {
            "thread_id": thread_id,
            "session": AsyncMock(),
            "permissions": ["tool:get_order", "tool:get_refund_case", "tool:get_ticket"],
            "merchant_scope": {"merchant_ids": ["*"]},
            "trace_id": "graph-trace",
        }
    }


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


def _policy_result(
    *,
    status: str = "strong_evidence",
    best_score: float = 0.82,
    evidence: list[EvidenceRefV1] | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=best_score,
        threshold=0.55,
        evidence_refs=EVIDENCE if evidence is None else evidence,
    )


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
    search_result: KnowledgeSearchResult | None = None,
    classify_llm=None,
):
    tool_result = ToolResultV2(
        status="success",
        data={"order_no": order_id or "ORD-001", "status": "delivered", "amount": "199.00"},
        summary="order result",
        source_system="test",
        data_freshness_at=None,
        latency_ms=1,
        audit_ref=None,
    )
    business_context = BusinessContextV1(
        tenant_id="tenant",
        status="complete",
        facts={"order": tool_result.data} if order_id else {},
        business_fact_refs=[],
        tool_results=[tool_result] if order_id else [],
        missing_required_facts=[],
        errors=[],
        data_freshness_at=None,
    )
    fetch_context = AsyncMock(return_value=business_context)
    knowledge_search = AsyncMock(return_value=search_result or _policy_result())

    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: classify_llm or FakeLLM(_intent(intent)))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots(order_id)))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    monkeypatch.setattr(load_business_context_module.BusinessToolService, "fetch_context", fetch_context)
    monkeypatch.setattr(retrieve_policy_evidence_module.PolicyKnowledgeService, "search", knowledge_search)
    return {"fetch_context": fetch_context, "knowledge_search": knowledge_search}


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
    assert all(final_state[field] is None for field in INVESTIGATION_STATE_FIELDS)
    assert not any("investigat" in step.get("node", "") for step in final_state["trace_steps"])
    mocks["knowledge_search"].assert_awaited_once()


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
    mocks["fetch_context"].assert_awaited_once()


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
    mocks["fetch_context"].assert_awaited_once()


@pytest.mark.asyncio
async def test_order_not_found_path(monkeypatch):
    mocks = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-MISSING")
    mocks["fetch_context"].return_value = BusinessContextV1(
        tenant_id="tenant",
        status="insufficient",
        facts={},
        business_fact_refs=[],
        tool_results=[],
        missing_required_facts=["order"],
        errors=[],
        data_freshness_at=None,
    )
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

    mocks["knowledge_search"].return_value = _policy_result(status="no_evidence", best_score=0.0, evidence=[])
    second_state = await graph.ainvoke(_state("这个新问题没有规则依据", thread_id), _config(thread_id))

    assert second_state["retrieved_evidence"]["evidence_refs"] == []
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
    assert summary["tools_called"] == ["knowledge_service.search"]
    assert summary["evidence_count"] == 1
    assert summary["final_status"] in ("completed", "insufficient_evidence", "error")
    assert INVESTIGATION_STATE_FIELDS.isdisjoint(summary)
