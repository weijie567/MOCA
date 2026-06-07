from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.knowledge.adapters import LegacyRagKnowledgeAdapter
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService


def _chunk() -> object:
    return SimpleNamespace(
        chunk_id="refund-001",
        section="退款",
        content="退款规则",
        effective_date=date(2026, 1, 1),
        document=SimpleNamespace(doc_key="refund-policy", title="退款规则", version=1),
    )


def _context(tenant_id: str, merchant_scope: list[str] | None = None) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=tenant_id,
        user_id="user-001",
        role="support",
        merchant_scope=merchant_scope,
        run_id="run-001",
        trace_id="trace-001",
        effective_at="2026-06-05T00:00:00Z",
    )


def _request(tenant_id: str, merchant_id: str | None = None) -> KnowledgeSearchRequest:
    return KnowledgeSearchRequest(
        query="退款规则",
        filters=KnowledgeSearchFilters(tenant_id=tenant_id, merchant_id=merchant_id),
        retrieval_config_version="retrieval.v3",
        rerank_config_version="rerank.v2",
    )


@pytest.mark.asyncio
async def test_adapter_uses_context_tenant_scope_only():
    allowed_tenant = uuid4()
    other_tenant = uuid4()

    async def search_similar(**kwargs):
        return [(_chunk(), 0.8)] if kwargs["tenant_id"] == allowed_tenant else []

    repo = SimpleNamespace(search_similar=AsyncMock(side_effect=search_similar))
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2]))
    adapter = LegacyRagKnowledgeAdapter(chunk_repo=repo, embedder=embedder)

    allowed = await adapter.retrieve(
        query="退款规则",
        context=_context(str(allowed_tenant)),
        max_results=5,
    )
    excluded = await adapter.retrieve(
        query="退款规则",
        context=_context(str(other_tenant)),
        max_results=5,
    )

    assert allowed[0] == "strong_evidence"
    assert excluded[0] == "no_evidence"
    assert repo.search_similar.await_args_list[0].kwargs["tenant_id"] == UUID(str(allowed_tenant))
    assert repo.search_similar.await_args_list[1].kwargs["tenant_id"] == UUID(str(other_tenant))


@pytest.mark.asyncio
async def test_merchant_filter_is_authorized_but_not_applied_to_policy_query():
    adapter = SimpleNamespace(retrieve=AsyncMock(return_value=("no_evidence", [], 0.0)))
    service = PolicyKnowledgeService(adapter)
    tenant_id = str(uuid4())
    context = _context(tenant_id, merchant_scope=["merchant-allowed"])

    baseline = await service.search(_request(tenant_id), context)
    unauthorized = await service.search(_request("untrusted-tenant", "merchant-denied"), context)
    authorized = await service.search(_request("untrusted-tenant", "merchant-allowed"), context)

    assert baseline == unauthorized == authorized
    assert adapter.retrieve.await_count == 3
    assert all(call.kwargs["context"] is context for call in adapter.retrieve.await_args_list)
    assert all("merchant_id" not in call.kwargs for call in adapter.retrieve.await_args_list)
