from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.retrieval import (
    FUZZY_CANDIDATE_TOP_K,
    FUZZY_MIN_SIMILARITY,
    SPARSE_CANDIDATE_TOP_K,
    normalize_sparse_score,
    PolicyRetrievalEngine,
)
from src.knowledge.schemas import KnowledgeContext
from src.repositories.policy_chunk_repo import PolicyChunkRepository


def _chunk(
    chunk_id: str,
    *,
    doc_key: str = "refund_policy",
    title: str = "退款规则",
    section: str = "仅退款",
    content: str = "用户申请仅退款时，客服应核实订单状态和商家举证。",
    effective_date: date = date(2026, 1, 1),
):
    return SimpleNamespace(
        chunk_id=chunk_id,
        section=section,
        content=content,
        effective_date=effective_date,
        document=SimpleNamespace(doc_key=doc_key, title=title, version=1),
    )


def _context(tenant_id=None) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=str(tenant_id or uuid4()),
        user_id="user-1",
        role="support_agent",
        merchant_scope=["*"],
        run_id="run-1",
        trace_id="trace-1",
        effective_at="2026-06-14T00:00:00+00:00",
    )


def _engine(
    *,
    dense: list[tuple[object, float]] | None = None,
    sparse: list[tuple[object, float]] | None = None,
    fuzzy: list[tuple[object, float]] | None = None,
) -> tuple[PolicyRetrievalEngine, object]:
    repo = SimpleNamespace(
        search_similar=AsyncMock(return_value=dense or []),
        search_sparse=AsyncMock(return_value=sparse or []),
        search_fuzzy=AsyncMock(return_value=fuzzy or []),
    )
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    return PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder), repo


@pytest.mark.asyncio
async def test_rrf_promotes_candidate_seen_by_multiple_channels() -> None:
    generic = _chunk(
        "generic_001",
        doc_key="generic_policy",
        title="通用规则",
        section="常见问题",
        content="退款申请处理规则。",
    )
    target = _chunk(
        "compensation_approval_sop_002",
        doc_key="compensation_approval_sop",
        title="补偿审批SOP",
        section="提交材料",
        content="补偿券审批需要提交订单号、补偿金额、原因说明和客服处理记录。",
    )
    engine, _ = _engine(
        dense=[(generic, 0.82)],
        sparse=[(target, 0.16)],
        fuzzy=[(target, 0.78)],
    )

    status, hits, _ = await engine.retrieve_hits(
        query="补偿券审批需要哪些信息？",
        context=_context(),
        max_results=5,
    )

    assert status == "strong_evidence"
    assert hits[0].chunk_id == "compensation_approval_sop_002"
    assert hits[0].selected_by == ("sparse", "fuzzy")
    assert hits[0].sparse_rank == 1
    assert hits[0].fuzzy_rank == 1
    assert hits[0].rrf_score is not None


@pytest.mark.asyncio
async def test_rrf_score_does_not_replace_normalized_confidence_score() -> None:
    target = _chunk("refund_timeout_001", section="退款时效", content="退款时效超过48小时需要核实支付通道。")
    engine, _ = _engine(sparse=[(target, 0.16)])

    _, hits, best_score = await engine.retrieve_hits(
        query="退款时效超过48小时怎么办？",
        context=_context(),
        max_results=5,
    )

    assert hits[0].selected_by == ("sparse",)
    assert hits[0].score == pytest.approx(0.8)
    assert best_score == pytest.approx(0.8)
    assert hits[0].rrf_score != hits[0].score
    assert normalize_sparse_score(0.16) == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_retrieval_trace_stays_internal_to_hits() -> None:
    target = _chunk("refund_policy_001")
    engine, _ = _engine(dense=[(target, 0.82)], sparse=[(target, 0.12)])
    context = _context()

    _, hits, _ = await engine.retrieve_hits(query="仅退款怎么处理？", context=context, max_results=5)
    _, refs, _ = await engine.retrieve(query="仅退款怎么处理？", context=context, max_results=5)

    assert hits[0].selected_by == ("dense", "sparse")
    assert hits[0].rrf_score is not None
    assert "selected_by" not in refs[0].model_dump()
    assert "rrf_score" not in refs[0].model_dump()


@pytest.mark.asyncio
async def test_each_hybrid_channel_receives_scope_filters() -> None:
    tenant_id = uuid4()
    engine, repo = _engine(dense=[(_chunk("refund_policy_001"), 0.82)])

    await engine.retrieve_hits(
        query="仅退款怎么处理？",
        context=_context(tenant_id),
        max_results=5,
        doc_type="refund_rule",
        risk_level="high",
    )

    for method_name in ("search_similar", "search_sparse", "search_fuzzy"):
        kwargs = getattr(repo, method_name).await_args.kwargs
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["doc_type"] == "refund_rule"
        assert kwargs["risk_level"] == "high"
        assert kwargs["effective_date"] == date(2026, 6, 14)
    assert repo.search_sparse.await_args.kwargs["top_k"] == SPARSE_CANDIDATE_TOP_K
    assert repo.search_fuzzy.await_args.kwargs["top_k"] == FUZZY_CANDIDATE_TOP_K
    assert repo.search_fuzzy.await_args.kwargs["min_similarity"] == FUZZY_MIN_SIMILARITY


class _EmptyResult:
    def all(self) -> list:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _EmptyResult()


@pytest.mark.asyncio
async def test_repository_sparse_and_fuzzy_methods_apply_scope_filters() -> None:
    session = _RecordingSession()
    repo = PolicyChunkRepository(session)  # type: ignore[arg-type]
    tenant_id = uuid4()

    await repo.search_sparse(
        query_text="仅退款 商家举证",
        tenant_id=tenant_id,
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 6, 14),
    )
    await repo.search_fuzzy(
        query_text="仅退款 商家举证",
        tenant_id=tenant_id,
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 6, 14),
    )

    sparse_sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": False})).lower()
    fuzzy_sql = str(session.statements[1].compile(compile_kwargs={"literal_binds": False})).lower()

    assert "@@" in sparse_sql
    assert "plainto_tsquery" in sparse_sql
    assert "ts_rank_cd" in sparse_sql
    assert "similarity" in fuzzy_sql
    for sql in (sparse_sql, fuzzy_sql):
        assert "policy_chunks.tenant_id" in sql
        assert "policy_documents.doc_type" in sql
        assert "policy_chunks.risk_level" in sql
        assert "policy_chunks.effective_date" in sql
