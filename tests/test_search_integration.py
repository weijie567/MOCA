from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyChunk, PolicyDocument
from src.knowledge.schemas import KnowledgeContext
from src.platform.context_projections import project_to_knowledge_context
from src.platform.trusted_context import MerchantScopeV1, TrustedContext


def _unit_vector(index: int, dimensions: int = 1024) -> list[float]:
    vector = [0.0] * dimensions
    vector[index] = 1.0
    return vector


async def _seed_policy_chunks(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    document = PolicyDocument(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        doc_key="test_refund",
        doc_type="refund_rule",
        title="测试退款规则",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        content="测试用退款规则文档",
    )
    session.add(document)
    await session.flush()

    session.add_all(
        [
            PolicyChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                doc_id=document.id,
                chunk_id="test_refund_001",
                section="七天无理由",
                content="七天无理由退款需要商品不影响二次销售。",
                risk_level="high",
                effective_date=document.effective_date,
                embedding=_unit_vector(0),
            ),
            PolicyChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                doc_id=document.id,
                chunk_id="test_refund_002",
                section="质量问题",
                content="质量问题退款需要买家提供照片或检测证明。",
                risk_level="high",
                effective_date=document.effective_date,
                embedding=_unit_vector(1),
            ),
        ]
    )
    await session.commit()


async def _post_search(client, auth_headers, query: str, username: str = "cs_zhang"):
    return await client.post(
        "/api/v1/search/",
        json={"query": query, "top_k": 5},
        headers=await auth_headers(username),
    )


@pytest.mark.asyncio
async def test_search_uses_factory_projected_knowledge_context_and_rejects_request_identity_override(
    client,
    auth_headers,
    monkeypatch,
):
    from src.api.routers import search as search_router

    calls: dict[str, object] = {}
    request_identity_override = {"tenant_id": "tenant-from-request", "merchant_scope": ["*"]}

    class SpyTrustedContextFactory:
        @staticmethod
        def create_from_request(**kwargs):
            calls["factory_kwargs"] = kwargs
            return TrustedContext(
                tenant_id="tenant-from-factory",
                user_id="user-from-factory",
                role="merchant",
                permissions=["knowledge:search"],
                merchant_scope=MerchantScopeV1(merchant_ids=["merchant-from-factory"]),
                session_id=None,
                thread_id="thread-from-factory",
                run_id="run-from-factory",
                trace_id="trace-from-factory",
                locale=None,
            )

    async def fake_retrieve_hits(self, *, query, context, max_results, doc_type=None, risk_level=None):
        del self, query, max_results, doc_type, risk_level
        calls["knowledge_context"] = context
        assert isinstance(context, KnowledgeContext)
        assert context.merchant_scope == ["merchant-from-factory"]
        return "no_evidence", [], 0.0

    monkeypatch.setattr(search_router, "TrustedContextFactory", SpyTrustedContextFactory)
    monkeypatch.setattr(search_router, "project_to_knowledge_context", project_to_knowledge_context)
    monkeypatch.setattr("src.api.routers.search.PolicyRetrievalEngine.retrieve_hits", fake_retrieve_hits)

    response = await client.post(
        "/api/v1/search/",
        json={"query": "退款规则", "top_k": 5, **request_identity_override},
        headers=await auth_headers("merchant_wang"),
    )

    assert response.status_code == 200
    factory_kwargs = calls["factory_kwargs"]
    assert "request_body" not in factory_kwargs
    assert "tenant_id" not in factory_kwargs
    assert "merchant_scope" not in factory_kwargs
    assert calls["knowledge_context"].tenant_id != request_identity_override["tenant_id"]


@pytest.mark.asyncio
async def test_search_returns_api_response(client, auth_headers, session: AsyncSession, seeded_session):
    """Search endpoint returns ApiResponse with deterministic retrieval evidence."""
    await _seed_policy_chunks(session, seeded_session["tenant"].id)

    with patch("src.api.routers.search.EmbeddingService") as embedding_service:
        embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(0))
        response = await _post_search(client, auth_headers, "七天无理由退款怎么处理？")

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["trace_id"] is not None
    assert payload["data"]["retrieval_status"] == "strong_evidence"
    assert payload["data"]["best_score"] >= 0.70
    assert payload["data"]["evidence"][0]["doc_key"] == "test_refund"
    assert payload["data"]["evidence"][0]["chunk_id"] == "test_refund_001"


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    """Search without auth token returns 401."""
    response = await client.post("/api/v1/search/", json={"query": "test"})
    payload = response.json()

    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_search_no_evidence_fallback(client, auth_headers, session: AsyncSession, seeded_session):
    """Query with no matching vectors returns no_evidence with fallback message."""
    await _seed_policy_chunks(session, seeded_session["tenant"].id)

    with patch("src.api.routers.search.EmbeddingService") as embedding_service:
        embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(2))
        response = await _post_search(client, auth_headers, "如何更换银行卡绑定手机号？")

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["retrieval_status"] == "no_evidence"
    assert payload["data"]["evidence"] == []
    assert payload["data"]["fallback_message"] is not None


@pytest.mark.asyncio
async def test_search_tenant_isolation(client, auth_headers, session: AsyncSession, seeded_session):
    """Tenant B cannot see Tenant A policy chunks even with a matching query vector."""
    await _seed_policy_chunks(session, seeded_session["tenant"].id)

    with patch("src.api.routers.search.EmbeddingService") as embedding_service:
        embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(0))
        response = await _post_search(client, auth_headers, "七天无理由退款怎么处理？", username="other_support")

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["retrieval_status"] == "no_evidence"
    assert payload["data"]["evidence"] == []


@pytest.mark.asyncio
async def test_search_excludes_chunk_with_mismatched_document_tenant(
    client,
    auth_headers,
    session: AsyncSession,
    seeded_session,
):
    """A bad chunk/document tenant mismatch must not leak document metadata."""
    other_document = PolicyDocument(
        id=uuid.uuid4(),
        tenant_id=seeded_session["other_tenant"].id,
        doc_key="other_refund",
        doc_type="refund_rule",
        title="异租户退款规则",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        content="异租户退款规则文档",
    )
    session.add(other_document)
    await session.flush()

    session.add(
        PolicyChunk(
            id=uuid.uuid4(),
            tenant_id=seeded_session["tenant"].id,
            doc_id=other_document.id,
            chunk_id="bad_cross_tenant_001",
            section="错配数据",
            content="该 chunk 的 tenant 与 document tenant 不一致。",
            risk_level="high",
            effective_date=other_document.effective_date,
            embedding=_unit_vector(0),
        )
    )
    await session.commit()

    with patch("src.api.routers.search.EmbeddingService") as embedding_service:
        embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(0))
        response = await _post_search(client, auth_headers, "七天无理由退款怎么处理？")

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["retrieval_status"] == "no_evidence"
    assert payload["data"]["evidence"] == []
