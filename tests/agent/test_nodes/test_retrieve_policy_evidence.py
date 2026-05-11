from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.nodes import retrieve_policy_evidence as retrieve_policy_evidence_module


def _policy_result(*, status: str = "strong_evidence", best_score: float = 0.8, evidence: list[dict] | None = None):
    return {
        "status": "success",
        "data": {
            "retrieval_status": status,
            "evidence": evidence or [],
            "best_score": best_score,
        },
        "error": {},
    }


def _evidence():
    return [
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "chunk_001",
            "title": "退款超时规则",
            "section": "第一条",
            "score": 0.82,
            "text": "规则摘录",
        }
    ]


@pytest.mark.asyncio
async def test_evidence_gate_no_evidence(monkeypatch, base_state):
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(status="no_evidence", best_score=0.0)),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_writes_persistent_evidence_refs(monkeypatch, base_state):
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(best_score=0.82, evidence=_evidence())),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["evidence_refs"][0]["doc_key"] == "policy_refund_timeout"
    assert result["evidence_refs"][0]["chunk_id"] == "chunk_001"
    assert result["evidence_refs"][0]["title"] == "退款超时规则"
    assert result["evidence_refs"][0]["confidence"] == 0.82
    assert result["evidence_refs"][0]["retrieved_at"]
    assert result["trace_steps"][-1]["evidence_refs"][0]["doc_key"] == "policy_refund_timeout"
    assert result["trace_steps"][-1]["evidence_refs"][0]["chunk_id"] == "chunk_001"


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_preserves_previous_refs_on_no_evidence(monkeypatch, base_state):
    prior_ref = {
        "doc_key": "prior_doc",
        "chunk_id": "prior_chunk",
        "title": "上一轮规则",
        "confidence": 0.77,
        "retrieved_at": "2026-05-11T08:00:00+00:00",
    }
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(status="no_evidence", best_score=0.0, evidence=[])),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "evidence_refs": [prior_ref]},
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["evidence_refs"] == [prior_ref]
    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_evidence_gate_low_score(monkeypatch, base_state):
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(best_score=0.3)),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_evidence_gate_passes_with_good_evidence(monkeypatch, base_state):
    evidence = [
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "chunk_001",
            "title": "退款超时规则",
            "section": "第一条",
            "score": 0.8,
            "text": "规则摘录",
        },
        {
            "doc_key": "policy_refund_timeout",
            "chunk_id": "chunk_002",
            "title": "退款超时规则",
            "section": "第二条",
            "score": 0.76,
            "text": "规则摘录",
        },
    ]
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(best_score=0.8, evidence=evidence)),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert "recommendation_draft" not in result


@pytest.mark.asyncio
async def test_search_error_records_node_error_not_insufficient_evidence(monkeypatch, base_state):
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(
            return_value={
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "DB_TIMEOUT",
                    "message": "Policy search timeout",
                    "retryable": True,
                    "should_stop": False,
                },
            }
        ),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["recommendation_draft"]["recommended_action"] == "retrieval_error"
    assert result["node_errors"][0]["node"] == "retrieve_policy_evidence"
    assert result["node_errors"][0]["error"]["error_code"] == "DB_TIMEOUT"
    assert result["trace_steps"][-1]["status"] == "error"
