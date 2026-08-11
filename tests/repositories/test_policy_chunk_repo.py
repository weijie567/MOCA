"""Tests for PolicyChunkRepository effective_date filtering."""

from __future__ import annotations

from datetime import date
import inspect
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.document_block_repo import DocumentBlockRepository
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.repositories.policy_corpus_scope import ActivePolicyCorpusScope, ExactPolicyCorpusScope


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
async def test_current_chunk_queries_join_the_tenant_active_corpus_authority():
    tenant_id = uuid4()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))
    repo = PolicyChunkRepository(mock_session)

    await repo.get_contents_by_evidence_keys(tenant_id, [("shared-doc", "shared-chunk")])
    statement = mock_session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).lower()

    assert "policy_corpus_rollouts" in sql
    assert "corpus_chunk_bindings" in sql
    assert "active_corpus_version_id" in sql
    assert "policy_corpus_versions" in sql


def test_current_repository_signatures_cannot_select_an_arbitrary_corpus():
    current_methods = (
        PolicyChunkRepository.search_similar,
        PolicyChunkRepository.search_sparse,
        PolicyChunkRepository.search_fuzzy,
        PolicyChunkRepository.get_contents_by_evidence_keys,
        PolicyChunkRepository.get_provenance_by_evidence_keys,
        PolicyChunkRepository.get_canonical_evidence_rows_by_keys,
        PolicyChunkRepository.delete_by_document_id,
        PolicyChunkRepository.bulk_insert,
        DocumentBlockRepository.list_by_document_id,
        DocumentBlockRepository.get_by_source_block_ids,
        DocumentBlockRepository.delete_by_document_id,
        DocumentBlockRepository.bulk_insert,
        EvidenceVersionRepository.get_current_identities_by_keys,
    )

    for method in current_methods:
        parameters = inspect.signature(method).parameters
        assert "corpus_version_id" not in parameters
        assert "corpus_id" not in parameters


def test_exact_scope_is_explicit_and_cannot_cross_tenants():
    tenant_id = uuid4()
    corpus_version_id = uuid4()
    scope = ExactPolicyCorpusScope.for_evaluation(
        tenant_id=tenant_id,
        corpus_version_id=corpus_version_id,
    )

    assert scope.tenant_id == tenant_id
    assert scope.corpus_version_id == corpus_version_id
    assert scope.purpose == "evaluation"
    with pytest.raises(ValueError, match="policy corpus scope tenant mismatch"):
        scope.require_tenant(uuid4())


def test_active_scope_is_the_single_current_scope_dto():
    fields = set(ActivePolicyCorpusScope.__dataclass_fields__)

    assert {
        "tenant_id",
        "corpus_version_id",
        "generation_name",
        "config_schema_version",
        "config_fingerprint",
        "rollout_epoch",
    }.issubset(fields)


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
