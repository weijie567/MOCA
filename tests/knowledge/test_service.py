from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.db.models import PolicyChunk, PolicyDocument
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
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
async def test_missing_merchant_scope_returns_no_evidence_without_adapter_call():
    service, retrieve = _service()

    result = await service.search(_request(), _context(None))

    assert result.status == "no_evidence"
    assert result.evidence_refs == []
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_policy_only_empty_business_merchant_scope_calls_adapter():
    service, retrieve = _service()

    # policy-only tenant public search is allowed with merchant_scope=[].
    result = await service.search(_request(), _context(merchant_scope=[]))

    assert result.status == "no_evidence"
    assert result.evidence_refs == []
    retrieve.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("merchant_scope", [[], ["merchant-allowed"]])
async def test_unauthorized_explicit_merchant_filter_returns_no_evidence_without_adapter_call(merchant_scope):
    service, retrieve = _service()

    result = await service.search(_request("merchant-denied"), _context(merchant_scope))

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


@pytest.mark.asyncio
async def test_search_uses_retrieval_run_safe_query_rewrite_summary():
    evidence = _evidence(tenant_id="tenant-001")
    retrieve = AsyncMock(return_value=("no_evidence", [], 0.0))
    retrieve_run = AsyncMock(
        return_value=SimpleNamespace(
            status="strong_evidence",
            evidence_refs=[evidence],
            best_score=0.8,
            query_rewrite_summary="rule_default: rewrite_count=2; triggers=仅退款,已发货",
        )
    )
    service = PolicyKnowledgeService(SimpleNamespace(retrieve=retrieve, retrieve_run=retrieve_run))

    result = await service.search(_request(), _context(["*"]))

    assert result.status == "strong_evidence"
    assert result.evidence_refs == [evidence]
    assert result.query_rewrite == "rule_default: rewrite_count=2; triggers=仅退款,已发货"
    assert "raw_prompt" not in result.query_rewrite
    retrieve_run.assert_awaited_once()
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_legacy_retriever_without_retrieve_run_remains_compatible():
    evidence = _evidence(tenant_id="tenant-001")
    retrieve = AsyncMock(return_value=("strong_evidence", [evidence], 0.8))
    service = PolicyKnowledgeService(SimpleNamespace(retrieve=retrieve))

    result = await service.search(_request(), _context(["*"]))

    assert result.status == "strong_evidence"
    assert result.evidence_refs == [evidence]
    assert result.query_rewrite is None
    retrieve.assert_awaited_once()


def _evidence(*, tenant_id: str, chunk_id: str = "chunk-1", text: str = "退款规则正文") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="refund-policy",
        chunk_id=chunk_id,
        policy_version="v1",
        text=text,
        retrieved_at="2026-06-13T00:00:00Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.8,
        rank=1,
    )


@pytest.mark.asyncio
async def test_verified_evidence_contents_rechecks_hash_and_tenant():
    tenant_id = str(uuid4())
    valid = _evidence(tenant_id=tenant_id, text="真实政策正文")
    wrong_hash = _evidence(tenant_id=tenant_id, chunk_id="chunk-2", text="旧正文")
    wrong_tenant = _evidence(tenant_id=str(uuid4()), chunk_id="chunk-3", text="跨租户正文")
    get_contents = AsyncMock(
        return_value={
            (valid.doc_key, valid.chunk_id): "真实政策正文",
            (wrong_hash.doc_key, wrong_hash.chunk_id): "被修改的正文",
            (wrong_tenant.doc_key, wrong_tenant.chunk_id): "跨租户正文",
        }
    )
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(
        tenant_id=tenant_id,
        evidence_refs=[valid, wrong_hash, wrong_tenant],
    )

    assert result == {valid.evidence_id: "真实政策正文"}


@pytest.mark.asyncio
async def test_verified_evidence_contents_skips_duplicate_keys():
    tenant_id = str(uuid4())
    first = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文一")
    second = _evidence(tenant_id=tenant_id, chunk_id="same", text="正文二")
    get_contents = AsyncMock(return_value={(first.doc_key, first.chunk_id): "正文一"})
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(
        tenant_id=tenant_id,
        evidence_refs=[first, second],
    )

    assert result == {}
    get_contents.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_evidence_contents_returns_empty_on_adapter_error():
    tenant_id = str(uuid4())
    evidence = _evidence(tenant_id=tenant_id)
    get_contents = AsyncMock(side_effect=RuntimeError("raw db error"))
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(
        tenant_id=tenant_id,
        evidence_refs=[evidence],
    )

    assert result == {}


@pytest.mark.asyncio
async def test_verified_evidence_details_uses_real_retrieval_engine_canonical_rows(session, seeded_session):
    tenant_id = str(seeded_session["tenant"].id)
    policy_content = "补偿超过500元需人工审批。"
    policy_document = PolicyDocument(
        tenant_id=seeded_session["tenant"].id,
        doc_key="approval_refund_policy",
        doc_type="refund_rule",
        title="售后补偿政策",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        version=1,
        content=policy_content,
        source_type="test_fixture",
        source_checksum="test-approval-refund-policy-v1",
        parser_metadata_json={},
        policy_version_fingerprint="test-approval-refund-policy-v1",
    )
    session.add(policy_document)
    await session.flush()
    session.add(
        PolicyChunk(
            tenant_id=seeded_session["tenant"].id,
            doc_id=policy_document.id,
            chunk_id="approval_refund_policy#001",
            section="高风险补偿",
            content=policy_content,
            search_text=policy_content,
            source_block_refs_json=[],
            ocr_metadata_json={},
            risk_level="high",
            effective_date=policy_document.effective_date,
            embedding=None,
        )
    )
    await session.flush()

    evidence = EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="approval_refund_policy",
        chunk_id="approval_refund_policy#001",
        policy_version="v1",
        text=policy_content,
        retrieved_at="2026-06-19T00:00:00Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.93,
        rank=1,
    )
    service = PolicyKnowledgeService(PolicyRetrievalEngine(session))

    result = await service.get_verified_evidence_details(
        tenant_id=tenant_id,
        evidence_refs=[evidence],
        effective_at="2026-06-19T00:00:00Z",
    )

    assert evidence.evidence_id in result.included
    assert result.excluded == []
