from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _load_budget_api():
    from src.agent.rag_context.builder import ContextBuilder
    from src.agent.rag_context.schemas import RagContextBudget

    return ContextBuilder, RagContextBudget


def _evidence_ref(
    *,
    chunk_id: str,
    text: str,
    rank: int,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id=chunk_id,
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.9,
        rank=rank,
    )


def _business_fact_ref() -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=TENANT_ID,
        source_system="moca",
        resource_type="order",
        resource_id="ORD-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 19, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _trusted_context() -> dict:
    return {
        "tenant_id": TENANT_ID,
        "run_id": "run-phase22-budget",
        "thread_id": "thread-phase22-budget",
        "effective_at": "2026-06-19T00:00:00+00:00",
        "scope": {"merchant_ids": ["merchant-001"]},
    }


class FakePolicyKnowledgeService:
    def __init__(self, contents: dict[str, str]) -> None:
        self.contents = contents

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        return {
            ref.evidence_id: self.contents[ref.evidence_id]
            for ref in evidence_refs
            if ref.tenant_id == tenant_id and ref.evidence_id in self.contents
        }


@pytest.mark.asyncio
async def test_budget_trace_preserves_protected_citation_metadata_when_snippets_are_trimmed() -> None:
    """CTX-05: protected citation metadata survives deterministic budget trimming."""
    ContextBuilder, RagContextBudget = _load_budget_api()
    high_priority = _evidence_ref(
        chunk_id="chunk_001",
        text="High-priority rule. " * 40,
        rank=1,
    )
    low_priority = _evidence_ref(
        chunk_id="chunk_002",
        text="Low-priority explanatory text. " * 80,
        rank=2,
    )
    service = FakePolicyKnowledgeService(
        {
            high_priority.evidence_id: "High-priority rule. " * 40,
            low_priority.evidence_id: "Low-priority explanatory text. " * 80,
        }
    )

    bundle = await ContextBuilder(
        policy_service=service,
        budget=RagContextBudget(max_prompt_chars=520, max_snippet_chars=140, max_evidence_items=2),
    ).build(
        candidate_evidence_refs=[high_priority, low_priority],
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    citation_ids = [citation.citation_id for citation in bundle.prompt_context.citations]
    citation_metadata = [citation.metadata for citation in bundle.prompt_context.citations]

    assert citation_ids == ["C1", "C2"]
    assert citation_metadata == [
        {
            "doc_key": high_priority.doc_key,
            "chunk_id": high_priority.chunk_id,
            "policy_version": high_priority.policy_version,
        },
        {
            "doc_key": low_priority.doc_key,
            "chunk_id": low_priority.chunk_id,
            "policy_version": low_priority.policy_version,
        },
    ]
    assert bundle.citation_map["C1"].evidence_ref == high_priority
    assert bundle.citation_map["C2"].evidence_ref == low_priority
    assert bundle.budget_trace.max_prompt_chars == 520
    assert bundle.budget_trace.protected_metadata_preserved is True
    assert any(entry.reason_code == "snippet_truncated" for entry in bundle.budget_trace.truncated)


@pytest.mark.asyncio
async def test_budget_trace_records_included_truncated_and_excluded_reason_codes() -> None:
    """CTX-05: budget trace records included, truncated, and excluded reason codes."""
    ContextBuilder, RagContextBudget = _load_budget_api()
    refs = [
        _evidence_ref(chunk_id=f"chunk_{index:03d}", text=f"Policy section {index}. " * 30, rank=index)
        for index in range(1, 5)
    ]
    service = FakePolicyKnowledgeService({ref.evidence_id: f"Policy section {index}. " * 30 for index, ref in enumerate(refs, 1)})

    bundle = await ContextBuilder(
        policy_service=service,
        budget=RagContextBudget(max_prompt_chars=700, max_snippet_chars=120, max_evidence_items=2),
    ).build(
        candidate_evidence_refs=refs,
        business_fact_refs=[_business_fact_ref()],
        trusted_context=_trusted_context(),
        risk_hints=[],
    )

    assert [entry.evidence_id for entry in bundle.budget_trace.included] == [
        refs[0].evidence_id,
        refs[1].evidence_id,
    ]
    assert {entry.reason_code for entry in bundle.budget_trace.truncated} == {"snippet_truncated"}
    assert [entry.reason_code for entry in bundle.budget_trace.excluded] == [
        "budget_evidence_item_limit",
        "budget_evidence_item_limit",
    ]
    assert refs[2].evidence_id not in bundle.citation_map
    assert refs[3].evidence_id not in bundle.citation_map
