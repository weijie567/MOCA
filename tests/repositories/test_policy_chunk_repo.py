"""Tests for PolicyChunkRepository effective_date filtering."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.repositories.policy_chunk_repo import PolicyChunkRepository


@pytest.mark.asyncio
async def test_search_similar_accepts_effective_date_param():
    """search_similar() should accept effective_date without error."""
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    repo = PolicyChunkRepository(mock_session)

    result = await repo.search_similar(
        query_embedding=[0.1, 0.2],
        tenant_id=uuid4(),
        top_k=5,
        effective_date=date(2026, 6, 1),
    )

    assert result == []


@pytest.mark.asyncio
async def test_get_contents_by_evidence_keys_returns_valid_content_in_one_query():
    tenant_id = uuid4()
    mock_result = MagicMock(all=lambda: [("doc-a", "chunk-a", "content-a"), ("doc-b", "chunk-b", "content-b")])
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    repo = PolicyChunkRepository(mock_session)

    result = await repo.get_contents_by_evidence_keys(
        tenant_id,
        [("doc-a", "chunk-a"), ("doc-b", "chunk-b")],
    )

    assert result == {("doc-a", "chunk-a"): "content-a", ("doc-b", "chunk-b"): "content-b"}
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_contents_by_evidence_keys_empty_keys_skips_query():
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    repo = PolicyChunkRepository(mock_session)

    assert await repo.get_contents_by_evidence_keys(uuid4(), []) == {}
    mock_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_contents_by_evidence_keys_query_is_tenant_scoped():
    tenant_id = uuid4()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    repo = PolicyChunkRepository(mock_session)

    result = await repo.get_contents_by_evidence_keys(tenant_id, [("shared-doc", "shared-chunk")])

    statement = mock_session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert result == {}
    assert str(tenant_id) in {str(value) for value in compiled.params.values()}
    assert "policy_chunks.tenant_id" in str(compiled)
    assert "policy_documents.tenant_id" in str(compiled)


@pytest.mark.asyncio
async def test_get_contents_by_evidence_keys_omits_duplicate_rows():
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            all=lambda: [
                ("doc-a", "chunk-a", "first"),
                ("doc-a", "chunk-a", "second"),
                ("doc-b", "chunk-b", "only"),
            ]
        )
    )
    repo = PolicyChunkRepository(mock_session)

    result = await repo.get_contents_by_evidence_keys(
        uuid4(),
        [("doc-a", "chunk-a"), ("doc-b", "chunk-b")],
    )

    assert result == {("doc-b", "chunk-b"): "only"}
