from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.rag.citation_validator import validate_citations
from src.rag.retriever import (
    CANDIDATE_MULTIPLIER,
    FALLBACK_MESSAGE,
    INTERNAL_SEARCH_THRESHOLD,
    MIN_SIMILARITY_THRESHOLD,
    QUERY_PREFIX,
    Retriever,
)
from src.rag.schemas import RetrievalResult


def _chunk(
    chunk_id: str = "refund_policy_001",
    doc_key: str = "refund_policy",
    title: str = "退款规则",
    section: str = "仅退款",
    content: str = "用户申请仅退款但商家已经发货时，客服应先核实物流状态和商家举证。",
):
    return SimpleNamespace(
        chunk_id=chunk_id,
        section=section,
        content=content,
        document=SimpleNamespace(doc_key=doc_key, title=title),
    )


def _retriever(results: list[tuple[object, float]]) -> tuple[Retriever, AsyncMock, AsyncMock]:
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    chunk_repo = SimpleNamespace(search_similar=AsyncMock(return_value=results))
    return Retriever(chunk_repo=chunk_repo, embedder=embedder), chunk_repo.search_similar, embedder.embed_query


def _retrieval_result(chunk_ids: list[str]) -> RetrievalResult:
    evidence = [
        {
            "doc_key": "refund_policy",
            "chunk_id": chunk_id,
            "title": "退款规则",
            "section": "仅退款",
            "score": 0.8,
            "text": "规则摘录",
        }
        for chunk_id in chunk_ids
    ]
    return RetrievalResult(
        query="如何处理仅退款？",
        retrieval_status="strong_evidence",
        evidence=evidence,
        best_score=0.8 if evidence else 0.0,
    )


@pytest.mark.asyncio
async def test_strong_evidence_status():
    retriever, _, _ = _retriever([(_chunk(), 0.72)])

    result = await retriever.search("仅退款怎么处理？", tenant_id=uuid4())

    assert result.retrieval_status == "strong_evidence"
    assert result.best_score == 0.72
    assert result.fallback_message is None


@pytest.mark.asyncio
async def test_partial_evidence_status():
    retriever, _, _ = _retriever([(_chunk(), 0.62)])

    result = await retriever.search("退款规则是什么？", tenant_id=uuid4())

    assert result.retrieval_status == "partial_evidence"
    assert result.best_score == 0.62
    assert result.fallback_message is None


@pytest.mark.asyncio
async def test_no_evidence_status():
    retriever, _, _ = _retriever([])

    result = await retriever.search("如何更换银行卡绑定手机号？", tenant_id=uuid4())

    assert result.retrieval_status == "no_evidence"
    assert result.best_score == 0.0
    assert result.evidence == []
    assert result.fallback_message == FALLBACK_MESSAGE


@pytest.mark.asyncio
async def test_no_evidence_status_when_best_score_below_threshold():
    retriever, _, _ = _retriever([(_chunk(), MIN_SIMILARITY_THRESHOLD - 0.01)])

    result = await retriever.search("低置信问题", tenant_id=uuid4())

    assert result.retrieval_status == "no_evidence"
    assert result.fallback_message == FALLBACK_MESSAGE


@pytest.mark.asyncio
async def test_evidence_item_has_doc_key():
    content = "规则内容" * 100
    retriever, _, _ = _retriever([(_chunk(content=content), 0.8)])

    result = await retriever.search("仅退款怎么处理？", tenant_id=uuid4())

    item = result.evidence[0]
    assert item.doc_key == "refund_policy"
    assert item.chunk_id == "refund_policy_001"
    assert item.title == "退款规则"
    assert item.section == "仅退款"
    assert item.score == 0.8
    assert item.text == content[:300]


def test_citation_valid():
    result = _retrieval_result(["refund_policy_001", "refund_sop_002"])

    validation = validate_citations(["refund_policy_001", "refund_sop_002"], result)

    assert validation.is_valid is True
    assert validation.invalid_citations == []
    assert validation.reason is None


def test_citation_invalid_missing():
    result = _retrieval_result(["refund_policy_001"])

    validation = validate_citations(["refund_policy_001", "missing_chunk"], result)

    assert validation.is_valid is False
    assert validation.invalid_citations == ["missing_chunk"]
    assert "not in retrieval results" in validation.reason


def test_citation_empty():
    result = _retrieval_result(["refund_policy_001"])

    validation = validate_citations([], result)

    assert validation.is_valid is False
    assert validation.invalid_citations == []
    assert "must include citations" in validation.reason


@pytest.mark.asyncio
async def test_tenant_isolation():
    allowed_tenant_id = uuid4()
    other_tenant_id = uuid4()

    async def search_similar(**kwargs):
        if kwargs["tenant_id"] == allowed_tenant_id:
            return [(_chunk(), 0.8)]
        return []

    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    chunk_repo = SimpleNamespace(search_similar=AsyncMock(side_effect=search_similar))
    retriever = Retriever(chunk_repo=chunk_repo, embedder=embedder)

    allowed_result = await retriever.search("仅退款", tenant_id=allowed_tenant_id)
    other_result = await retriever.search("仅退款", tenant_id=other_tenant_id)

    assert allowed_result.retrieval_status == "strong_evidence"
    assert other_result.retrieval_status == "no_evidence"
    assert chunk_repo.search_similar.await_count == 2


@pytest.mark.asyncio
async def test_search_uses_query_prefix_and_deeper_candidate_fetch():
    tenant_id = uuid4()
    retriever, search_similar, embed_query = _retriever([(_chunk(), 0.8)])

    await retriever.search("仅退款怎么处理？", tenant_id=tenant_id, top_k=5, doc_type="sop", risk_level="high")

    embed_query.assert_awaited_once_with(f"{QUERY_PREFIX}仅退款怎么处理？")
    search_similar.assert_awaited_once()
    kwargs = search_similar.await_args.kwargs
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["top_k"] == 5 * CANDIDATE_MULTIPLIER
    assert kwargs["min_similarity"] == INTERNAL_SEARCH_THRESHOLD
    assert kwargs["doc_type"] == "sop"
    assert kwargs["risk_level"] == "high"


@pytest.mark.asyncio
async def test_hybrid_rerank_promotes_lexical_match_from_outside_top5():
    generic_results = [
        (_chunk(chunk_id=f"generic_{index}", doc_key="generic", title="通用规则", section="常见问题", content="退款申请处理规则。"), score)
        for index, score in enumerate([0.66, 0.65, 0.64, 0.63, 0.62], start=1)
    ]
    lexical_match = _chunk(
        chunk_id="compensation_approval_sop_002",
        doc_key="compensation_approval_sop",
        title="补偿审批SOP",
        section="提交材料",
        content="补偿券审批需要提交订单号、补偿金额、原因说明和客服处理记录。",
    )
    retriever, _, _ = _retriever([*generic_results, (lexical_match, 0.60)])

    result = await retriever.search("补偿券审批需要哪些信息？", tenant_id=uuid4(), top_k=5)

    assert "compensation_approval_sop_002" in [item.chunk_id for item in result.evidence]
    assert result.evidence[0].chunk_id == "compensation_approval_sop_002"


@pytest.mark.asyncio
async def test_hybrid_rerank_does_not_return_low_vector_candidate_with_high_overlap():
    below_threshold = _chunk(
        chunk_id="refund_policy_001",
        doc_key="refund_policy",
        title="退款规则",
        section="七天无理由",
        content="七天无理由退款需要商品不影响二次销售。",
    )
    retriever, _, _ = _retriever([(below_threshold, MIN_SIMILARITY_THRESHOLD - 0.10)])

    result = await retriever.search("七天无理由退款商品不影响二次销售", tenant_id=uuid4(), top_k=5)

    assert result.retrieval_status == "no_evidence"
    assert result.evidence == []
