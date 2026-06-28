from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest, MaterialClaimV1
from src.knowledge.service import PolicyKnowledgeService
from src.knowledge.text_hash import evidence_text_hash
from src.platform.context_projections import project_to_knowledge_context
from src.platform.trusted_context import MerchantScopeV1, TrustedContext


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
    adapter = PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder)

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
async def test_merchant_filter_is_authorized_before_policy_query():
    adapter = SimpleNamespace(retrieve=AsyncMock(return_value=("no_evidence", [], 0.0)))
    service = PolicyKnowledgeService(adapter)
    tenant_id = str(uuid4())
    context = _context(tenant_id, merchant_scope=["merchant-allowed"])

    baseline = await service.search(_request(tenant_id), context)
    unauthorized = await service.search(_request("untrusted-tenant", "merchant-denied"), context)
    authorized = await service.search(_request("untrusted-tenant", "merchant-allowed"), context)

    assert baseline == authorized
    assert unauthorized.status == "no_evidence"
    assert unauthorized.evidence_refs == []
    assert adapter.retrieve.await_count == 2
    assert all(call.kwargs["context"] is context for call in adapter.retrieve.await_args_list)
    assert all("merchant_id" not in call.kwargs for call in adapter.retrieve.await_args_list)


@pytest.mark.asyncio
async def test_factory_projected_knowledge_context_preserves_deny_before_query_behavior():
    adapter = SimpleNamespace(retrieve=AsyncMock(return_value=("no_evidence", [], 0.0)))
    service = PolicyKnowledgeService(adapter)
    tenant_id = str(uuid4())
    trusted_context = TrustedContext(
        tenant_id=tenant_id,
        user_id="user-001",
        role="support",
        permissions=["knowledge:search"],
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-allowed"]),
        session_id=None,
        thread_id="thread-001",
        run_id="run-001",
        trace_id="trace-001",
        locale=None,
    )
    context = project_to_knowledge_context(trusted_context, effective_at="2026-06-05T00:00:00Z")

    unauthorized = await service.search(_request(tenant_id, "merchant-denied"), context)
    authorized = await service.search(_request(tenant_id, "merchant-allowed"), context)

    assert context.merchant_scope == ["merchant-allowed"]
    assert unauthorized.status == "no_evidence"
    assert unauthorized.evidence_refs == []
    assert authorized.status == "no_evidence"
    assert adapter.retrieve.await_count == 1


class FakeTenantPolicyRetriever:
    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict]:
        return {
            key: {
                "tenant_id": str(tenant_id),
                "doc_key": key[0],
                "chunk_id": key[1],
                "content": "Tenant public policy describes refund timeout compensation.",
                "policy_document_version": 3,
                "current_policy_version": "v3",
                "effective_date": "2026-06-01",
                "expires_at": None,
                "doc_type": "refund_rule",
                "risk_level": "medium",
                "merchant_ids": [],
                "source_locator": {"page": 1},
            }
            for key in keys
        }


@pytest.mark.asyncio
async def test_tenant_public_policy_does_not_create_merchant_scoped_business_fact_authority():
    """tenant public policy evidence is separate from merchant-scoped BusinessFactRefV1 / BusinessFactResultV1 business fact authority."""
    tenant_id = str(uuid4())
    evidence = EvidenceRefV1(
        tenant_id=tenant_id,
        evidence_id="refund-policy/chunk_001@v3",
        doc_key="refund-policy",
        chunk_id="chunk_001",
        policy_version="v3",
        text_hash=evidence_text_hash("Tenant public policy describes refund timeout compensation."),
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.9,
        rank=1,
    )
    service = PolicyKnowledgeService(FakeTenantPolicyRetriever())
    package = await service.build_verified_context(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[],
        knowledge_context=_context(tenant_id, merchant_scope=["merchant-001"]),
        evidence_policy={"doc_type": "refund_rule", "risk_level": "medium", "evidence_required": True},
    )

    bundle = await service.verify_claims(
        material_claims=[
            MaterialClaimV1(
                claim_id="claim-business-fact-authority",
                claim_text="Refund case RF-1001 has a merchant-scoped timeout.",
                claim_type="business_fact",
                cited_evidence_ids=[evidence.evidence_id],
                business_fact_refs=[],
                risk_hints=[],
                generated_from_step="recommendation_generation",
            )
        ],
        verified_evidence_package=package,
        business_context={"business_fact_refs": []},
        proposed_action=None,
    )

    assert package.status == "verified"
    assert bundle.route == "final_response"
    assert "business_fact_ref_required" in bundle.reason_codes
