from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.retrieval import (
    CANDIDATE_MULTIPLIER,
    INTERNAL_SEARCH_THRESHOLD,
    POLICY_NO_EVIDENCE_MESSAGE,
    QUERY_PREFIX,
    PolicyRetrievalEngine,
)
from src.knowledge.config import MIN_SIMILARITY_THRESHOLD
from src.knowledge.schemas import KnowledgeContext


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
        effective_date=date(2026, 1, 1),
        document=SimpleNamespace(doc_key=doc_key, title=title, version=1),
    )


def _context(tenant_id) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=str(tenant_id),
        user_id="user-1",
        role="support_agent",
        merchant_scope=["*"],
        run_id="run-1",
        trace_id="trace-1",
        effective_at="2026-06-14T00:00:00+00:00",
    )


def _engine(results: list[tuple[object, float]]) -> tuple[PolicyRetrievalEngine, AsyncMock, AsyncMock]:
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    chunk_repo = SimpleNamespace(search_similar=AsyncMock(return_value=results))
    return (
        PolicyRetrievalEngine(chunk_repo=chunk_repo, embedder=embedder),
        chunk_repo.search_similar,
        embedder.embed_query,
    )


async def _retrieve_hits(
    engine: PolicyRetrievalEngine,
    query: str,
    tenant_id,
    *,
    max_results: int = 5,
    doc_type: str | None = None,
    risk_level: str | None = None,
):
    return await engine.retrieve_hits(
        query=query,
        context=_context(tenant_id),
        max_results=max_results,
        doc_type=doc_type,
        risk_level=risk_level,
    )


@pytest.mark.asyncio
async def test_strong_evidence_status():
    engine, _, _ = _engine([(_chunk(), 0.72)])

    status, hits, best_score = await _retrieve_hits(engine, "仅退款怎么处理？", uuid4())

    assert status == "strong_evidence"
    assert best_score == 0.72
    assert hits


@pytest.mark.asyncio
async def test_partial_evidence_status():
    engine, _, _ = _engine([(_chunk(), 0.62)])

    status, hits, best_score = await _retrieve_hits(engine, "退款规则是什么？", uuid4())

    assert status == "partial_evidence"
    assert best_score == 0.62
    assert hits


@pytest.mark.asyncio
async def test_no_evidence_status():
    engine, _, _ = _engine([])

    status, hits, best_score = await _retrieve_hits(engine, "如何更换银行卡绑定手机号？", uuid4())

    assert status == "no_evidence"
    assert best_score == 0.0
    assert hits == []
    assert POLICY_NO_EVIDENCE_MESSAGE


@pytest.mark.asyncio
async def test_no_evidence_status_when_best_score_below_threshold():
    engine, _, _ = _engine([(_chunk(), MIN_SIMILARITY_THRESHOLD - 0.01)])

    status, hits, _ = await _retrieve_hits(engine, "低置信问题", uuid4())

    assert status == "no_evidence"
    assert hits == []


@pytest.mark.asyncio
async def test_evidence_item_has_doc_key():
    content = "规则内容" * 100
    engine, _, _ = _engine([(_chunk(content=content), 0.8)])

    _, hits, _ = await _retrieve_hits(engine, "仅退款怎么处理？", uuid4())

    item = hits[0]
    assert item.doc_key == "refund_policy"
    assert item.chunk_id == "refund_policy_001"
    assert item.title == "退款规则"
    assert item.section == "仅退款"
    assert item.score == 0.8
    assert item.text == content


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
    engine = PolicyRetrievalEngine(chunk_repo=chunk_repo, embedder=embedder)

    allowed_status, _, _ = await _retrieve_hits(engine, "仅退款", allowed_tenant_id)
    other_status, _, _ = await _retrieve_hits(engine, "仅退款", other_tenant_id)

    assert allowed_status == "strong_evidence"
    assert other_status == "no_evidence"
    assert chunk_repo.search_similar.await_count == 2


@pytest.mark.asyncio
async def test_search_uses_query_prefix_and_deeper_candidate_fetch():
    tenant_id = uuid4()
    engine, search_similar, embed_query = _engine([(_chunk(), 0.8)])

    await _retrieve_hits(
        engine,
        "仅退款怎么处理？",
        tenant_id,
        max_results=5,
        doc_type="sop",
        risk_level="high",
    )

    embed_query.assert_awaited_once_with(f"{QUERY_PREFIX}仅退款怎么处理？")
    search_similar.assert_awaited_once()
    kwargs = search_similar.await_args.kwargs
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["top_k"] == 5 * CANDIDATE_MULTIPLIER
    assert kwargs["min_similarity"] == INTERNAL_SEARCH_THRESHOLD
    assert kwargs["doc_type"] == "sop"
    assert kwargs["risk_level"] == "high"


@pytest.mark.asyncio
async def test_unchanged_production_caller_observes_repository_pointer_cutover():
    tenant_id = uuid4()
    active = {"chunk": _chunk(chunk_id="character_001", content="旧字符语料退款规则。")}

    async def search_similar(**kwargs):
        assert "corpus_version_id" not in kwargs
        assert kwargs["tenant_id"] == tenant_id
        return [(active["chunk"], 0.82)]

    repo = SimpleNamespace(search_similar=AsyncMock(side_effect=search_similar))
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    engine = PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder)

    _, before, _ = await _retrieve_hits(engine, "退款规则", tenant_id)
    active["chunk"] = _chunk(chunk_id="token_001", content="新 token 语料退款规则。")
    _, after, _ = await _retrieve_hits(engine, "退款规则", tenant_id)

    assert [hit.chunk_id for hit in before] == ["character_001"]
    assert [hit.chunk_id for hit in after] == ["token_001"]


@pytest.mark.asyncio
async def test_hybrid_rerank_promotes_lexical_match_from_outside_top5():
    generic_results = [
        (
            _chunk(
                chunk_id=f"generic_{index}",
                doc_key="generic",
                title="通用规则",
                section="常见问题",
                content="退款申请处理规则。",
            ),
            score,
        )
        for index, score in enumerate([0.66, 0.65, 0.64, 0.63, 0.62], start=1)
    ]
    lexical_match = _chunk(
        chunk_id="compensation_approval_sop_002",
        doc_key="compensation_approval_sop",
        title="补偿审批SOP",
        section="提交材料",
        content="补偿券审批需要提交订单号、补偿金额、原因说明和客服处理记录。",
    )
    engine, _, _ = _engine([*generic_results, (lexical_match, 0.60)])

    _, hits, _ = await _retrieve_hits(engine, "补偿券审批需要哪些信息？", uuid4(), max_results=5)

    assert "compensation_approval_sop_002" in [item.chunk_id for item in hits]
    assert hits[0].chunk_id == "compensation_approval_sop_002"


@pytest.mark.asyncio
async def test_hybrid_rerank_does_not_return_low_vector_candidate_with_high_overlap():
    below_threshold = _chunk(
        chunk_id="refund_policy_001",
        doc_key="refund_policy",
        title="退款规则",
        section="七天无理由",
        content="七天无理由退款需要商品不影响二次销售。",
    )
    engine, _, _ = _engine([(below_threshold, MIN_SIMILARITY_THRESHOLD - 0.10)])

    status, hits, _ = await _retrieve_hits(engine, "七天无理由退款商品不影响二次销售", uuid4(), max_results=5)

    assert status == "no_evidence"
    assert hits == []


@pytest.mark.asyncio
async def test_out_of_domain_query_falls_back_even_with_weak_policy_matches():
    engine, _, _ = _engine([(_chunk(section="沟通话术", content="客服应说明证据缺口和申诉入口。"), 0.57)])

    status, hits, _ = await _retrieve_hits(engine, "用户问如何更换银行卡绑定手机号？", uuid4(), max_results=5)

    assert status == "no_evidence"
    assert hits == []


@pytest.mark.asyncio
async def test_valid_no_anchor_policy_query_can_return_strong_evidence():
    chunk = _chunk(
        section="七天无理由",
        content="拆封后不影响二次销售时，可以支持七天无理由退货退款。",
    )
    engine, _, _ = _engine([(chunk, 0.82)])

    status, hits, _ = await _retrieve_hits(engine, "已拆封但不影响二次销售怎么办？", uuid4())

    assert status == "strong_evidence"
    assert hits
    assert hits[0].chunk_id == "refund_policy_001"
