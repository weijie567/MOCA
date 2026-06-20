from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import KnowledgeContext

SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD = "SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD"
SHOULD_NOT_LEAK_PRIVATE_REASONING = "SHOULD_NOT_LEAK_PRIVATE_REASONING"
SHOULD_NOT_LEAK_SOURCE_BLOCK = "SHOULD_NOT_LEAK_SOURCE_BLOCK"
SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD = "SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD"
UNBOUNDED_POLICY_TEXT = "SHOULD_NOT_LEAK_UNBOUNDED_POLICY_TEXT " * 80


def _load_rerank_api():
    from src.knowledge.rerank import (
        DefaultLocalReranker,
        RerankCandidate,
        RerankConfig,
        RerankerProviderAdapter,
        rerank_candidates_for_query,
    )

    return DefaultLocalReranker, RerankCandidate, RerankerProviderAdapter, RerankConfig, rerank_candidates_for_query


def _candidate(
    RerankCandidate,
    *,
    doc_key: str,
    chunk_id: str,
    title: str = "退款规则",
    section: str = "仅退款已发货",
    text: str = "用户申请仅退款但商家已经发货时，客服应先核实物流状态和商家举证。",
    score: float = 0.70,
    rank: int = 1,
    selected_by: tuple[str, ...] = ("dense",),
):
    return RerankCandidate(
        candidate_id=f"{doc_key}/{chunk_id}@v1",
        doc_key=doc_key,
        chunk_id=chunk_id,
        title=title,
        section=section,
        policy_version="v1",
        text_snippet=text,
        baseline_score=score,
        baseline_rank=rank,
        selected_by=selected_by,
        rrf_score=0.03,
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _rerank(rerank_candidates_for_query, **kwargs):
    return await _maybe_await(rerank_candidates_for_query(**kwargs))


def _candidate_identity(candidate: object) -> tuple[str, str, str, str]:
    return (
        getattr(candidate, "doc_key"),
        getattr(candidate, "chunk_id"),
        getattr(candidate, "policy_version"),
        getattr(candidate, "text_snippet"),
    )


def _ranked(output):
    return output.ranked_candidates if hasattr(output, "ranked_candidates") else output


def _chunk(
    chunk_id: str,
    *,
    doc_key: str,
    title: str,
    section: str,
    content: str,
):
    return SimpleNamespace(
        chunk_id=chunk_id,
        section=section,
        content=content,
        effective_date=None,
        document=SimpleNamespace(doc_key=doc_key, title=title, version=1),
    )


def _context() -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=str(uuid4()),
        user_id="user-1",
        role="support_agent",
        merchant_scope=["*"],
        run_id="run-1",
        trace_id="trace-1",
        effective_at="2026-06-14T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_reranker_preserves_candidate_identity() -> None:
    _DefaultLocalReranker, RerankCandidate, _Provider, RerankConfig, rerank_candidates_for_query = _load_rerank_api()
    candidates = [
        _candidate(RerankCandidate, doc_key="refund_policy", chunk_id="refund_policy_001", score=0.72, rank=1),
        _candidate(RerankCandidate, doc_key="shipping_policy", chunk_id="shipping_policy_002", score=0.69, rank=2),
    ]

    output = await _rerank(
        rerank_candidates_for_query,
        query="商家已发货还能仅退款吗？",
        candidates=candidates,
        config=RerankConfig(provider_enabled=False),
    )
    ranked = _ranked(output)

    assert {_candidate_identity(candidate) for candidate in ranked} == {
        _candidate_identity(candidate) for candidate in candidates
    }
    assert [candidate.rank for candidate in ranked] == list(range(1, len(ranked) + 1))
    assert all(candidate.baseline_score is not None for candidate in ranked)
    assert all(candidate.final_score is not None for candidate in ranked)


@pytest.mark.asyncio
async def test_default_reranker_is_deterministic_and_local() -> None:
    DefaultLocalReranker, RerankCandidate, _Provider, RerankConfig, _rerank_for_query = _load_rerank_api()
    candidates = [
        _candidate(
            RerankCandidate,
            doc_key="generic_policy",
            chunk_id="generic_policy_001",
            section="通用规则",
            text="客服应按平台规则处理售后申请。",
            score=0.74,
            rank=1,
        ),
        _candidate(
            RerankCandidate,
            doc_key="refund_policy",
            chunk_id="refund_policy_001",
            section="仅退款已发货",
            text="商家已经发货时，客服应先核实物流状态和商家举证，再判断仅退款。",
            score=0.68,
            rank=2,
            selected_by=("dense", "sparse", "fuzzy"),
        ),
    ]
    reranker = DefaultLocalReranker(config=RerankConfig(provider_enabled=False))

    first = _ranked(await _maybe_await(reranker.rerank(query="商家已发货还能仅退款吗？", candidates=candidates)))
    second = _ranked(
        await _maybe_await(reranker.rerank(query="商家已发货还能仅退款吗？", candidates=list(reversed(candidates))))
    )

    assert [candidate.chunk_id for candidate in first] == [candidate.chunk_id for candidate in second]
    assert first[0].chunk_id == "refund_policy_001"
    assert set(first[0].score_components) == {
        "baseline_score",
        "lexical_overlap",
        "title_section_overlap",
        "channel_coverage",
        "rrf_score",
        "final_score",
    }
    assert all(getattr(candidate, "provider_payload", None) is None for candidate in first)


@pytest.mark.asyncio
async def test_provider_adapter_disabled_timeout_error_malformed_and_budget_fallbacks() -> None:
    DefaultLocalReranker, RerankCandidate, RerankerProviderAdapter, RerankConfig, rerank_candidates_for_query = (
        _load_rerank_api()
    )
    candidates = [
        _candidate(RerankCandidate, doc_key="generic_policy", chunk_id="generic_policy_001", score=0.74, rank=1),
        _candidate(
            RerankCandidate,
            doc_key="refund_policy",
            chunk_id="refund_policy_001",
            text="商家已经发货时，客服应先核实物流状态和商家举证。",
            score=0.68,
            rank=2,
            selected_by=("dense", "sparse"),
        ),
    ]
    local_order = [
        candidate.chunk_id
        for candidate in await _maybe_await(
            DefaultLocalReranker(config=RerankConfig(provider_enabled=False)).rerank(
                query="商家已发货还能仅退款吗？",
                candidates=candidates,
            )
        )
    ]

    class TimeoutProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            raise TimeoutError("provider timeout")

    class ErrorProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            raise RuntimeError("provider error")

    class MalformedProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            return [{"chunk_id": "missing-score"}]

    for provider, expected_reason in (
        (None, "provider_disabled"),
        (TimeoutProvider(), "provider_timeout"),
        (ErrorProvider(), "provider_error"),
        (MalformedProvider(), "provider_malformed_output"),
        (MalformedProvider(), "budget_overflow"),
    ):
        config = RerankConfig(
            provider_enabled=provider is not None,
            timeout_seconds=0.01,
            max_candidates=1 if expected_reason == "budget_overflow" else 50,
        )
        output = await _rerank(
            rerank_candidates_for_query,
            query="商家已发货还能仅退款吗？",
            candidates=candidates,
            config=config,
            provider=provider,
        )
        ranked = _ranked(output)

        assert [candidate.chunk_id for candidate in ranked] == local_order
        assert ranked[0].fallback_reason == expected_reason


@pytest.mark.asyncio
async def test_reranker_inputs_exclude_raw_internals_and_unbounded_text() -> None:
    _DefaultLocalReranker, RerankCandidate, RerankerProviderAdapter, RerankConfig, rerank_candidates_for_query = (
        _load_rerank_api()
    )
    captured_payloads: list[dict[str, object]] = []

    class CapturingProvider(RerankerProviderAdapter):
        async def rerank(self, *, candidates, **_kwargs):
            captured_payloads.extend(candidate.model_dump(mode="json") for candidate in candidates)
            return [
                {"candidate_id": candidate.candidate_id, "score": 0.91}
                for candidate in candidates
            ]

    candidate = _candidate(
        RerankCandidate,
        doc_key="refund_policy",
        chunk_id="refund_policy_001",
        text=(
            "商家已经发货时，客服应先核实物流状态和商家举证。"
            + SHOULD_NOT_LEAK_SOURCE_BLOCK
            + SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD
            + SHOULD_NOT_LEAK_PRIVATE_REASONING
            + SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD
            + UNBOUNDED_POLICY_TEXT
        ),
        score=0.70,
        rank=1,
    )

    await _rerank(
        rerank_candidates_for_query,
        query="商家已发货还能仅退款吗？",
        candidates=[candidate],
        config=RerankConfig(provider_enabled=True, text_max_chars=80),
        provider=CapturingProvider(),
    )

    payload_text = repr(captured_payloads)
    assert captured_payloads
    for sentinel in (
        SHOULD_NOT_LEAK_RAW_PROVIDER_PAYLOAD,
        SHOULD_NOT_LEAK_PRIVATE_REASONING,
        SHOULD_NOT_LEAK_SOURCE_BLOCK,
        SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD,
        UNBOUNDED_POLICY_TEXT,
    ):
        assert sentinel not in payload_text
    assert "商家已经发货" in payload_text
    assert len(captured_payloads[0]["text_snippet"]) <= 80


@pytest.mark.asyncio
async def test_rerank_occurs_before_evidence_ref_construction() -> None:
    generic = _chunk(
        "generic_policy_001",
        doc_key="generic_policy",
        title="通用规则",
        section="常见问题",
        content="客服应按平台规则处理售后申请。",
    )
    target = _chunk(
        "refund_policy_001",
        doc_key="refund_policy",
        title="退款规则",
        section="仅退款已发货",
        content="商家已经发货时，客服应先核实物流状态和商家举证，再判断仅退款。",
    )
    repo = SimpleNamespace(
        search_similar=AsyncMock(return_value=[(generic, 0.74), (target, 0.68)]),
        search_sparse=AsyncMock(return_value=[]),
        search_fuzzy=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    engine = PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder)
    context = _context()

    status, hits, best_score = await engine.retrieve_hits(
        query="商家已发货还能仅退款吗？",
        context=context,
        max_results=5,
    )
    _ref_status, refs, ref_best_score = await engine.retrieve(
        query="商家已发货还能仅退款吗？",
        context=context,
        max_results=5,
    )

    assert status == "strong_evidence"
    assert hits[0].chunk_id == "refund_policy_001"
    assert refs[0].chunk_id == "refund_policy_001"
    assert refs[0].rank == hits[0].rank == 1
    assert hits[0].score == pytest.approx(0.68)
    assert refs[0].score == pytest.approx(0.68)
    assert best_score == pytest.approx(0.74)
    assert ref_best_score == pytest.approx(0.74)
    assert "final_score" not in refs[0].model_dump()
    assert "score_components" not in refs[0].model_dump()
