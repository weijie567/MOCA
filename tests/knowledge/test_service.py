from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService


def _context(merchant_scope: list[str] | None) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id="tenant-001",
        user_id="user-001",
        role="merchant",
        merchant_scope=merchant_scope,
        run_id="run-001",
        trace_id="trace-001",
        effective_at="2026-06-13T00:00:00Z",
    )


def _request(merchant_id: str | None = None) -> KnowledgeSearchRequest:
    return KnowledgeSearchRequest(
        query="退款规则",
        filters=KnowledgeSearchFilters(tenant_id="tenant-001", merchant_id=merchant_id),
        retrieval_config_version="retrieval.v3",
        rerank_config_version="rerank.v2",
    )


def _service() -> tuple[PolicyKnowledgeService, AsyncMock]:
    retrieve = AsyncMock(return_value=("no_evidence", [], 0.0))
    return PolicyKnowledgeService(SimpleNamespace(retrieve=retrieve)), retrieve


@pytest.mark.asyncio
@pytest.mark.parametrize("merchant_scope", [None, []])
async def test_missing_or_empty_merchant_scope_returns_no_evidence_without_adapter_call(merchant_scope):
    service, retrieve = _service()

    result = await service.search(_request(), _context(merchant_scope))

    assert result.status == "no_evidence"
    assert result.evidence_refs == []
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_explicit_merchant_filter_returns_no_evidence_without_adapter_call():
    service, retrieve = _service()

    result = await service.search(_request("merchant-denied"), _context(["merchant-allowed"]))

    assert result.status == "no_evidence"
    assert result.evidence_refs == []
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("merchant_scope", "merchant_id"),
    [
        (["*"], "merchant-any"),
        (["merchant-allowed"], "merchant-allowed"),
    ],
)
async def test_authorized_merchant_scope_calls_adapter(merchant_scope, merchant_id):
    service, retrieve = _service()

    result = await service.search(_request(merchant_id), _context(merchant_scope))

    assert result.status == "no_evidence"
    retrieve.assert_awaited_once()
