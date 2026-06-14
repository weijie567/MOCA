from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.nodes import generate_recommendation as recommendation_module
from src.agent.nodes import retrieve_policy_evidence as retrieval_module
from src.agent.nodes.final_response import final_response
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult
from src.tools.contracts import ToolCallContext, ToolResultV2
from tests.agent.conftest import FakeLLM


def _base_state() -> dict:
    return {
        "thread_id": "facade-integration-thread",
        "tenant_id": "tenant-001",
        "user_id": "user-001",
        "role": "support_agent",
        "user_query": "退款超时规则是什么？",
        "current_intent": "policy_qa",
        "current_run_id": "run-001",
        "run_started_at": "2026-06-07T00:00:00+00:00",
        "business_context": {},
        "evidence_refs": [],
        "trace_steps": [],
        "proposed_action": None,
    }


def _evidence(*, text: str = "退款超时时，应核实支付通道和退款状态。") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id="tenant-001",
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-07T00:00:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.82,
        rank=1,
    )


def _search_result(
    *,
    status: str,
    best_score: float,
    evidence_refs: list[EvidenceRefV1],
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=best_score,
        threshold=0.55,
        evidence_refs=evidence_refs,
    )


class FakePolicyManager:
    def __init__(self, search_result: KnowledgeSearchResult) -> None:
        self.search_result = search_result
        self.calls: list[tuple[str, dict, ToolCallContext]] = []

    async def invoke(self, name: str, args: dict, ctx: ToolCallContext) -> ToolResultV2:
        self.calls.append((name, args, ctx))
        return ToolResultV2(
            status="not_found" if self.search_result.status == "no_evidence" else "success",
            data={
                "retrieval_status": self.search_result.status,
                "best_score": self.search_result.best_score,
                "threshold": self.search_result.threshold,
                "summary": self.search_result.summary,
            },
            summary=self.search_result.summary or f"Policy search returned {self.search_result.status}",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=self.search_result.evidence_refs,
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )


def _recommendation(*, chunk_id: str = "chunk_001", reasoning: str = "根据规则应处理退款。") -> dict:
    return {
        "recommended_action": "建议退款",
        "reasoning_summary": reasoning,
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": chunk_id,
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "confidence": 0.85,
        "risk_level": "low",
        "missing_info": [],
    }


async def _run_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    search_result: KnowledgeSearchResult,
    recommendation: dict | None,
) -> dict:
    if recommendation is None:
        monkeypatch.setattr(
            recommendation_module,
            "_get_llm",
            lambda: pytest.fail("LLM must not run for a retrieval safety draft"),
        )
    else:
        monkeypatch.setattr(recommendation_module, "_get_llm", lambda: FakeLLM(recommendation))

    state = _base_state()
    retrieval_output = await retrieval_module.retrieve_policy_evidence(
        state,
        {
            "configurable": {
                "session": AsyncMock(),
                "permissions": ["tool:search_policy"],
                "merchant_scope": {"merchant_ids": ["*"]},
                "tool_manager": FakePolicyManager(search_result),
            }
        },
    )
    state.update(retrieval_output)
    recommendation_output = await recommendation_module.generate_recommendation(state)
    state.update(recommendation_output)
    response_output = await final_response(state)
    state.update(response_output)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "best_score"),
    [("strong_evidence", 0.82), ("partial_evidence", 0.62)],
)
async def test_facade_path_preserves_actionable_status_and_canonical_evidence(
    monkeypatch,
    status,
    best_score,
):
    evidence = _evidence()

    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status=status, best_score=best_score, evidence_refs=[evidence]),
        recommendation=_recommendation(),
    )

    assert state["retrieved_evidence"]["status"] == status
    assert state["retrieved_evidence"]["evidence_refs"][0]["schema_version"] == "evidence_ref.v1"
    assert state["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert state["evidence_refs"][0]["text_hash"] == evidence.text_hash
    assert state["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert "policy_refund_timeout / chunk_001" in state["final_response"]


@pytest.mark.asyncio
async def test_no_evidence_produces_insufficient_draft_without_action(monkeypatch):
    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="no_evidence", best_score=0.0, evidence_refs=[]),
        recommendation=None,
    )

    assert state["retrieved_evidence"]["status"] == "no_evidence"
    assert state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert state["proposed_action"] is None
    assert state["evidence_refs"] == []


@pytest.mark.asyncio
async def test_all_invalid_membership_produces_citation_invalid_without_action(monkeypatch):
    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="strong_evidence", best_score=0.82, evidence_refs=[_evidence()]),
        recommendation=_recommendation(chunk_id="missing"),
    )

    assert state["recommendation_draft"]["recommended_action"] == "citation_invalid"
    assert state["recommendation_draft"]["confidence"] == 0.0
    assert state["recommendation_draft"]["evidence_refs"] == []
    assert state["proposed_action"] is None
    assert state["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_present_evidence_id_passes_membership_without_semantic_support(monkeypatch):
    evidence = _evidence(text="This evidence discusses refund timing only.")

    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="partial_evidence", best_score=0.62, evidence_refs=[evidence]),
        recommendation=_recommendation(reasoning="The merchant receives a free vacation."),
    )

    assert state["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert state["recommendation_draft"]["recommended_action"] == "建议退款"
