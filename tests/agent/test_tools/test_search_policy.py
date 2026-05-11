from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.tools.search_policy import search_policy
from src.rag.schemas import EvidenceItem, RetrievalResult


def _evidence(chunk_id: str) -> EvidenceItem:
    return EvidenceItem(
        doc_key="policy_refund_timeout",
        chunk_id=chunk_id,
        title="退款超时规则",
        section="第一条",
        score=0.8,
        text="退款超时时，客服应核实支付通道和退款状态。",
    )


def _patch_retriever(monkeypatch: pytest.MonkeyPatch, result: RetrievalResult):
    retriever = SimpleNamespace(search=AsyncMock(return_value=result))
    monkeypatch.setattr("src.agent.tools.search_policy.PolicyChunkRepository", lambda session: object())
    monkeypatch.setattr("src.agent.tools.search_policy.EmbeddingService", lambda: object())
    monkeypatch.setattr("src.agent.tools.search_policy.Retriever", lambda chunk_repo, embedder: retriever)
    return retriever


@pytest.mark.asyncio
async def test_search_policy_no_evidence(monkeypatch):
    _patch_retriever(
        monkeypatch,
        RetrievalResult(query="未知规则", retrieval_status="no_evidence", evidence=[], best_score=0.0),
    )

    result = await search_policy("未知规则", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert result["data"]["retrieval_status"] == "no_evidence"


@pytest.mark.asyncio
async def test_search_policy_success(monkeypatch):
    _patch_retriever(
        monkeypatch,
        RetrievalResult(
            query="退款超时",
            retrieval_status="strong_evidence",
            evidence=[_evidence("chunk_001"), _evidence("chunk_002")],
            best_score=0.8,
        ),
    )

    result = await search_policy("退款超时", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert len(result["data"]["evidence"]) == 2
