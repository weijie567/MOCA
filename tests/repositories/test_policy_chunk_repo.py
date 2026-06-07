"""Tests for PolicyChunkRepository effective_date filtering."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

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
