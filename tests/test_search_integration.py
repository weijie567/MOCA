from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyChunk, PolicyDocument


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
