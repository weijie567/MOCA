from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyChunk, PolicyDocument
from src.knowledge.retrieval import (
    FUZZY_CANDIDATE_TOP_K,
    FUZZY_MIN_SIMILARITY,
    SPARSE_CANDIDATE_TOP_K,
    normalize_sparse_score,
    PolicyRetrievalEngine,
)
from src.knowledge.schemas import KnowledgeContext
from src.rag.search_text import build_policy_chunk_search_text, build_sparse_query_text
from src.rag.search_text_backfill import rebuild_policy_chunk_search_texts
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
async def test_original_and_rewrite_channels_merge_before_rerank() -> None:
    tenant_id = uuid4()
    original_hit = _chunk(
        "refund_policy_001",
        doc_key="refund_policy",
        section="仅退款已发货",
        content="商家已经发货时，客服应先核实物流状态和商家举证。",
    )
    rewrite_duplicate = _chunk(
        "refund_policy_001",
        doc_key="refund_policy",
        section="仅退款已发货",
        content="商家已经发货时，客服应先核实物流状态和商家举证。",
    )
    rewrite_only = _chunk(
        "refund_policy_002",
        doc_key="refund_policy",
        section="商家举证",
        content="仅退款争议需要商家提供物流和履约证据。",
    )
    channel_calls: list[tuple[str, dict]] = []

    async def search_similar(**kwargs):
        channel_calls.append(("dense", kwargs))
        if len([name for name, _ in channel_calls if name == "dense"]) == 1:
            return [(original_hit, 0.72)]
        return [(rewrite_duplicate, 0.71), (rewrite_only, 0.70)]

    async def search_sparse(**kwargs):
        channel_calls.append(("sparse", kwargs))
        if len([name for name, _ in channel_calls if name == "sparse"]) == 1:
            return [(original_hit, 0.16)]
        return [(rewrite_duplicate, 0.15), (rewrite_only, 0.14)]

    async def search_fuzzy(**kwargs):
        channel_calls.append(("fuzzy", kwargs))
        if len([name for name, _ in channel_calls if name == "fuzzy"]) == 1:
            return [(original_hit, 0.78)]
        return [(rewrite_duplicate, 0.77), (rewrite_only, 0.76)]

    repo = SimpleNamespace(
        search_similar=AsyncMock(side_effect=search_similar),
        search_sparse=AsyncMock(side_effect=search_sparse),
        search_fuzzy=AsyncMock(side_effect=search_fuzzy),
    )
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    engine = PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder)

    _status, hits, _best_score = await engine.retrieve_hits(
        query="商家发了货还能只退款吗？",
        context=_context(tenant_id),
        max_results=5,
        doc_type="refund_rule",
        risk_level="high",
    )

    call_order = [name for name, _kwargs in channel_calls]
    assert call_order[:3] == ["dense", "sparse", "fuzzy"]
    assert len([name for name in call_order if name == "dense"]) >= 2
    assert len([name for name in call_order if name == "sparse"]) >= 2
    assert len([name for name in call_order if name == "fuzzy"]) >= 2

    for _name, kwargs in channel_calls:
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["doc_type"] == "refund_rule"
        assert kwargs["risk_level"] == "high"
        assert kwargs["effective_date"] == date(2026, 6, 14)

    hit_keys = [(hit.doc_key, hit.chunk_id, hit.policy_version) for hit in hits]
    assert hit_keys.count(("refund_policy", "refund_policy_001", "v1")) == 1
    assert "refund_policy_002" in [hit.chunk_id for hit in hits]

    failing_repo = SimpleNamespace(
        search_similar=AsyncMock(side_effect=[[(original_hit, 0.72)], RuntimeError("rewrite dense failed")]),
        search_sparse=AsyncMock(side_effect=[[(original_hit, 0.16)], RuntimeError("rewrite sparse failed")]),
        search_fuzzy=AsyncMock(side_effect=[[(original_hit, 0.78)], RuntimeError("rewrite fuzzy failed")]),
    )
    fallback_engine = PolicyRetrievalEngine(chunk_repo=failing_repo, embedder=embedder)

    fallback_status, fallback_hits, fallback_best_score = await fallback_engine.retrieve_hits(
        query="商家发了货还能只退款吗？",
        context=_context(tenant_id),
        max_results=5,
        doc_type="refund_rule",
        risk_level="high",
    )

    assert fallback_status == "strong_evidence"
    assert [hit.chunk_id for hit in fallback_hits] == ["refund_policy_001"]
    assert fallback_best_score >= 0.70


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
async def test_ocr_confidence_metadata_does_not_replace_retrieval_scores() -> None:
    target = _chunk("ocr_refund_policy_001", section="OCR", content="截图政策识别文本。")
    target.source_block_refs_json = [
        {"source_block_id": "block-ocr-001", "ocr": {"average_confidence": 12, "confidence_status": "rejected"}}
    ]
    engine, _ = _engine(sparse=[(target, 0.16)])

    _, hits, best_score = await engine.retrieve_hits(
        query="截图政策识别文本",
        context=_context(),
        max_results=5,
    )
    _, refs, ref_best_score = await engine.retrieve(
        query="截图政策识别文本",
        context=_context(),
        max_results=5,
    )

    assert hits[0].score == pytest.approx(0.8)
    assert best_score == pytest.approx(0.8)
    assert refs[0].score == pytest.approx(0.8)
    assert ref_best_score == pytest.approx(0.8)
    assert "ocr" not in refs[0].model_dump()
    assert "confidence_status" not in refs[0].model_dump()


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
    assert " | " in repo.search_sparse.await_args.kwargs["query_text"]
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
    assert "to_tsquery" in sparse_sql
    assert "ts_rank_cd" in sparse_sql
    assert "similarity" in fuzzy_sql
    for sql in (sparse_sql, fuzzy_sql):
        assert "policy_chunks.tenant_id" in sql
        assert "policy_documents.doc_type" in sql
        assert "policy_chunks.risk_level" in sql
        assert "policy_chunks.effective_date" in sql


def _unit_vector(index: int, dimensions: int = 1024) -> list[float]:
    vector = [0.0] * dimensions
    vector[index] = 1.0
    return vector


@pytest.mark.asyncio
async def test_sparse_repository_matches_chinese_domain_terms_in_postgres(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    document = PolicyDocument(
        tenant_id=tenant_id,
        doc_key="refund_policy",
        doc_type="refund_rule",
        title="退款规则",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        content="退款规则",
    )
    other_document = PolicyDocument(
        tenant_id=other_tenant_id,
        doc_key="other_refund_policy",
        doc_type="refund_rule",
        title="异租户退款规则",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        content="异租户退款规则",
    )
    session.add_all([document, other_document])
    await session.flush()
    target_content = "用户申请仅退款但商家已经发货时，客服应先核实物流状态和商家举证。"
    future_content = "未来规则：用户申请仅退款但商家已经发货时直接转人工。"
    session.add_all(
        [
            PolicyChunk(
                tenant_id=tenant_id,
                doc_id=document.id,
                chunk_id="refund_policy_001",
                section="仅退款已发货",
                content=target_content,
                search_text=build_policy_chunk_search_text(
                    title=document.title,
                    section="仅退款已发货",
                    content=target_content,
                    doc_type=document.doc_type,
                    risk_level="high",
                ),
                risk_level="high",
                effective_date=date(2026, 1, 1),
                embedding=_unit_vector(0),
            ),
            PolicyChunk(
                tenant_id=tenant_id,
                doc_id=document.id,
                chunk_id="refund_policy_future",
                section="未来规则",
                content=future_content,
                search_text=build_policy_chunk_search_text(
                    title=document.title,
                    section="未来规则",
                    content=future_content,
                    doc_type=document.doc_type,
                    risk_level="high",
                ),
                risk_level="high",
                effective_date=date(2026, 7, 1),
                embedding=_unit_vector(1),
            ),
            PolicyChunk(
                tenant_id=other_tenant_id,
                doc_id=other_document.id,
                chunk_id="other_refund_policy_001",
                section="仅退款已发货",
                content=target_content,
                search_text=build_policy_chunk_search_text(
                    title=other_document.title,
                    section="仅退款已发货",
                    content=target_content,
                    doc_type=other_document.doc_type,
                    risk_level="high",
                ),
                risk_level="high",
                effective_date=date(2026, 1, 1),
                embedding=_unit_vector(2),
            ),
        ]
    )
    await session.commit()

    repo = PolicyChunkRepository(session)
    results = await repo.search_sparse(
        query_text=build_sparse_query_text("商家已发货还能仅退款吗"),
        tenant_id=tenant_id,
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 6, 14),
    )

    assert [chunk.chunk_id for chunk, _ in results] == ["refund_policy_001"]


@pytest.mark.asyncio
async def test_rebuild_policy_chunk_search_texts_matches_ingestion_builder(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    document = PolicyDocument(
        tenant_id=tenant_id,
        doc_key="refund_policy",
        doc_type="refund_rule",
        title="退款规则",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        content="退款规则",
    )
    session.add(document)
    await session.flush()
    content = "商品不影响二次销售时，支持七天无理由退货退款。"
    chunk = PolicyChunk(
        tenant_id=tenant_id,
        doc_id=document.id,
        chunk_id="refund_policy_001",
        section="七天无理由",
        content=content,
        search_text="七天无理由 " + content,
        risk_level="high",
        effective_date=date(2026, 1, 1),
        embedding=_unit_vector(0),
    )
    session.add(chunk)
    await session.commit()

    count = await rebuild_policy_chunk_search_texts(session, tenant_id=tenant_id)
    await session.commit()
    await session.refresh(chunk)

    assert count == 1
    assert chunk.search_text == build_policy_chunk_search_text(
        title="退款规则",
        section="七天无理由",
        content=content,
        doc_type="refund_rule",
        risk_level="high",
    )
    assert "refund_rule" in chunk.search_text
    assert "二次销售" in chunk.search_text
