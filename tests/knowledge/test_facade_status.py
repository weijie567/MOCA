from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService
from src.knowledge.text_hash import evidence_text_hash


def _context(tenant_id: str | None = None) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=tenant_id or str(uuid4()),
        user_id="user-001",
        role="support",
        merchant_scope=["merchant-001"],
        run_id="run-001",
        trace_id="trace-001",
        effective_at="2026-06-05T00:00:00Z",
    )


def _request(
    tenant_id: str,
    max_results: int = 5,
    allow_partial_evidence: bool = True,
) -> KnowledgeSearchRequest:
    return KnowledgeSearchRequest(
        query="退款规则是什么？",
        filters=KnowledgeSearchFilters(tenant_id=tenant_id),
        retrieval_config_version="caller-value-is-not-trusted",
        rerank_config_version="caller-value-is-not-trusted",
        max_results=max_results,
        allow_partial_evidence=allow_partial_evidence,
    )


def _chunk(content: str = "退款规则内容") -> object:
    return SimpleNamespace(
        chunk_id="refund-001",
        section="退款",
        content=content,
        effective_date=date(2026, 1, 1),
        document=SimpleNamespace(doc_key="refund-policy", title="退款规则", version=3),
    )


def _service(results: list[tuple[object, float]]) -> PolicyKnowledgeService:
    repo = SimpleNamespace(search_similar=AsyncMock(return_value=results))
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2]))
    return PolicyKnowledgeService(
        PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("score", "expected_status"),
    [(0.72, "strong_evidence"), (0.62, "partial_evidence")],
)
async def test_facade_preserves_evidence_status(score: float, expected_status: str):
    context = _context()

    result = await _service([(_chunk(), score)]).search(_request(context.tenant_id), context)

    assert result.status == expected_status
    assert result.best_score == score
    assert result.retrieval_config_version == "retrieval.v3"
    assert result.rerank_config_version == "rerank.v2"
    assert result.evidence_refs[0].schema_version == "evidence_ref.v1"
    assert result.evidence_refs[0].evidence_id == "refund-policy/refund-001@v3"
    assert result.evidence_refs[0].text_hash.startswith("sha256:")
    assert result.evidence_refs[0].rank == 1


@pytest.mark.asyncio
async def test_facade_preserves_no_evidence_status():
    context = _context()

    result = await _service([]).search(_request(context.tenant_id), context)

    assert result.status == "no_evidence"
    assert result.best_score == 0.0
    assert result.evidence_refs == []


@pytest.mark.asyncio
async def test_adapter_hashes_full_chunk_content():
    context = _context()
    full_content = "退款规则" * 100

    result = await _service([(_chunk(full_content), 0.8)]).search(
        _request(context.tenant_id), context
    )

    assert result.evidence_refs[0].text_hash == evidence_text_hash(full_content)
    assert result.evidence_refs[0].text_hash != evidence_text_hash(full_content[:300])


@pytest.mark.asyncio
async def test_retrieval_timeout_maps_to_error_status():
    adapter = SimpleNamespace(retrieve=AsyncMock(side_effect=asyncio.TimeoutError))
    context = _context()

    result = await PolicyKnowledgeService(adapter).search(_request(context.tenant_id), context)

    assert result.status == "error"
    assert result.error == {
        "error_code": "DB_TIMEOUT",
        "message": "Policy search timeout",
        "retryable": True,
    }
    assert result.evidence_refs == []


@pytest.mark.asyncio
async def test_partial_evidence_suppressed_when_disallowed():
    context = _context()
    request = _request(context.tenant_id, allow_partial_evidence=False)

    result = await _service([(_chunk(), 0.62)]).search(request, context)

    assert result.status == "no_evidence"
    assert result.evidence_refs == []
    assert result.best_score == 0.62


@pytest.mark.asyncio
async def test_partial_evidence_preserved_when_allowed():
    context = _context()
    request = _request(context.tenant_id, allow_partial_evidence=True)

    result = await _service([(_chunk(), 0.62)]).search(request, context)

    assert result.status == "partial_evidence"
    assert len(result.evidence_refs) == 1
