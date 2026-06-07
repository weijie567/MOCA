from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.knowledge.adapters import LegacyRagKnowledgeAdapter
from src.knowledge.schemas import KnowledgeContext


def _chunk(chunk_id: str, effective_date: date) -> object:
    return SimpleNamespace(
        chunk_id=chunk_id,
        section="退款",
        content=f"{chunk_id} 退款规则",
        effective_date=effective_date,
        document=SimpleNamespace(doc_key="refund-policy", title="退款规则", version=2),
    )


def _context() -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=str(uuid4()),
        user_id="user-001",
        role="support",
        run_id="run-001",
        trace_id="trace-001",
        effective_at="2026-06-05T12:00:00Z",
    )


def _adapter(results: list[tuple[object, float]]) -> LegacyRagKnowledgeAdapter:
    repo = SimpleNamespace(search_similar=AsyncMock(return_value=results))
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2]))
    return LegacyRagKnowledgeAdapter(chunk_repo=repo, embedder=embedder)


@pytest.mark.asyncio
async def test_effective_filter_precedes_top_k_truncation():
    future = _chunk("future", date(2026, 7, 1))
    current = _chunk("current", date(2026, 1, 1))

    status, refs, best_score = await _adapter([(future, 0.9), (current, 0.72)]).retrieve(
        query="退款规则",
        context=_context(),
        max_results=1,
    )

    assert status == "strong_evidence"
    assert best_score == 0.72
    assert [ref.chunk_id for ref in refs] == ["current"]


@pytest.mark.asyncio
async def test_same_effective_at_produces_identical_evidence_refs():
    context = _context()
    adapter = _adapter([(_chunk("current", date(2026, 1, 1)), 0.72)])

    first = await adapter.retrieve(query="退款规则", context=context, max_results=1)
    second = await adapter.retrieve(query="退款规则", context=context, max_results=1)

    assert first == second
    assert first[1][0].retrieved_at == context.effective_at


@pytest.mark.asyncio
async def test_effective_date_passed_to_repository():
    """Adapter must pass effective_date to search_similar()."""
    repo = SimpleNamespace(search_similar=AsyncMock(return_value=[]))
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2]))
    adapter = LegacyRagKnowledgeAdapter(chunk_repo=repo, embedder=embedder)

    await adapter.retrieve(query="退款规则", context=_context(), max_results=5)

    call_kwargs = repo.search_similar.call_args[1]
    assert "effective_date" in call_kwargs
    assert call_kwargs["effective_date"] == date(2026, 6, 5)  # from _context().effective_at
