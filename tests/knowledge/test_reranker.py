from __future__ import annotations

import inspect
from typing import Any

import pytest

from src.knowledge.schemas import EvidenceRefV1

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
        doc_key=doc_key,
        chunk_id=chunk_id,
        title=title,
        section=section,
        policy_version="v1",
        text=text,
        score=score,
        rank=rank,
        selected_by=selected_by,
        dense_rank=rank if "dense" in selected_by else None,
        sparse_rank=rank if "sparse" in selected_by else None,
        fuzzy_rank=rank if "fuzzy" in selected_by else None,
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
        getattr(candidate, "text"),
    )


@pytest.mark.asyncio
async def test_reranker_preserves_candidate_identity() -> None:
    _DefaultLocalReranker, RerankCandidate, _Provider, RerankConfig, rerank_candidates_for_query = _load_rerank_api()
    candidates = [
        _candidate(RerankCandidate, doc_key="refund_policy", chunk_id="refund_policy_001", score=0.72, rank=1),
        _candidate(RerankCandidate, doc_key="shipping_policy", chunk_id="shipping_policy_002", score=0.69, rank=2),
    ]

    ranked = await _rerank(
        rerank_candidates_for_query,
        query="商家已发货还能仅退款吗？",
        candidates=candidates,
        config=RerankConfig(provider_enabled=False),
    )

    assert {_candidate_identity(candidate) for candidate in ranked} == {
        _candidate_identity(candidate) for candidate in candidates
    }
    assert [candidate.rank for candidate in ranked] == list(range(1, len(ranked) + 1))
    assert all(candidate.score is not None for candidate in ranked)


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

    first = await _maybe_await(reranker.rerank(query="商家已发货还能仅退款吗？", candidates=candidates))
    second = await _maybe_await(reranker.rerank(query="商家已发货还能仅退款吗？", candidates=list(reversed(candidates))))

    assert [candidate.chunk_id for candidate in first] == [candidate.chunk_id for candidate in second]
    assert first[0].chunk_id == "refund_policy_001"
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
            provider_timeout_seconds=0.01,
            max_candidate_text_chars=20 if expected_reason == "budget_overflow" else 200,
        )
        ranked = await _rerank(
            rerank_candidates_for_query,
            query="商家已发货还能仅退款吗？",
            candidates=candidates,
            config=config,
            provider=provider,
        )

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
            captured_payloads.extend(candidate for candidate in candidates)
            return [
                {"doc_key": candidate["doc_key"], "chunk_id": candidate["chunk_id"], "score": 0.91}
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
        config=RerankConfig(provider_enabled=True, max_candidate_text_chars=80),
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
    assert len(captured_payloads[0]["text"]) <= 80


@pytest.mark.asyncio
async def test_rerank_occurs_before_evidence_ref_construction() -> None:
    _DefaultLocalReranker, RerankCandidate, _Provider, RerankConfig, rerank_candidates_for_query = _load_rerank_api()
    candidate = _candidate(
        RerankCandidate,
        doc_key="refund_policy",
        chunk_id="refund_policy_001",
        score=0.72,
        rank=1,
    )

    ranked = await _rerank(
        rerank_candidates_for_query,
        query="商家已发货还能仅退款吗？",
        candidates=[candidate],
        config=RerankConfig(provider_enabled=False),
    )

    assert not isinstance(ranked[0], EvidenceRefV1)
    assert not hasattr(ranked[0], "evidence_id")
    assert not hasattr(ranked[0], "text_hash")
    assert _candidate_identity(ranked[0]) == _candidate_identity(candidate)
