from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, VerifiedEvidencePackageV1
from src.knowledge.service import PolicyKnowledgeService


TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT_ID = "22222222-2222-2222-2222-222222222222"


def _trusted_context() -> dict[str, Any]:
    return {
        "schema_version": "trusted_context.v1",
        "tenant_id": TENANT_ID,
        "user_id": "user-rag-context",
        "role": "support",
        "permissions": ["tool:search_policy"],
        "merchant_scope": {
            "schema_version": "merchant_scope.v1",
            "merchant_ids": ["merchant-001"],
        },
        "thread_id": "thread-rag-context",
        "run_id": "run-rag-context",
        "trace_id": "trace-rag-context",
        "locale": "zh-CN",
    }


def _config(*, service: Any, effective_at: str = "2026-06-19T00:00:00+00:00") -> dict[str, Any]:
    return {
        "configurable": {
            "trusted_context": _trusted_context(),
            "policy_knowledge_service": service,
            "effective_at": effective_at,
        }
    }


def _ref(
    *,
    tenant_id: str = TENANT_ID,
    doc_key: str = "policy_refund_timeout",
    chunk_id: str = "chunk_001",
    policy_version: str = "v3",
    text: str = "Refund timeout compensation requires verified policy evidence.",
    rank: int = 1,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=text,
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=rank,
    )


def _row(ref: EvidenceRefV1, *, content: str | None = None, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "doc_key": ref.doc_key,
        "chunk_id": ref.chunk_id,
        "content": content or "Refund timeout compensation requires verified policy evidence.",
        "policy_document_version": 3,
        "current_policy_version": ref.policy_version,
        "effective_date": "2026-06-01",
        "expires_at": None,
        "doc_type": "refund_rule",
        "risk_level": "medium",
        "merchant_ids": ["merchant-001"],
        "source_locator": {"page": 1, "block_id": "b1"},
    }
    row.update(overrides)
    return row


class RecordingBuildService:
    def __init__(self, package: VerifiedEvidencePackageV1) -> None:
        self.package = package
        self.calls: list[dict[str, Any]] = []

    async def build_verified_context(
        self,
        *,
        candidate_evidence_refs: list[EvidenceRefV1],
        business_fact_refs: list[Any] | None,
        knowledge_context: KnowledgeContext,
        evidence_policy: dict[str, Any] | None = None,
    ) -> VerifiedEvidencePackageV1:
        self.calls.append(
            {
                "candidate_evidence_refs": candidate_evidence_refs,
                "business_fact_refs": business_fact_refs,
                "knowledge_context": knowledge_context,
                "evidence_policy": evidence_policy,
            }
        )
        return self.package


class RaisingBuildService:
    def __init__(self) -> None:
        self.calls = 0

    async def build_verified_context(self, **kwargs: Any) -> VerifiedEvidencePackageV1:
        self.calls += 1
        raise RuntimeError("canonical package build unavailable")


class FakeCanonicalRetriever:
    def __init__(self, rows: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        self.calls.append({"tenant_id": str(tenant_id), "keys": keys})
        return {key: row for key, row in self.rows.items() if key in keys}


def _package(ref: EvidenceRefV1) -> VerifiedEvidencePackageV1:
    return VerifiedEvidencePackageV1(
        package_id="verified-evidence:run-rag-context:policy_refund_timeout/chunk_001@v3",
        status="verified",
        evidence_items=[],
        citation_map={"C1": [ref.evidence_id]},
        evidence_map={ref.evidence_id: ref},
        prompt_projection={"citations": [{"citation_id": "C1"}]},
        verifier_projection={"safe_refs": [ref.evidence_id]},
        replay_snapshot_refs=[ref.evidence_id],
        debug_projection={"reason_codes": []},
        stale_refs=[],
        conflict_refs=[],
        rejected_candidate_refs=[],
        reason_codes=[],
        policy_version="v3",
        retrieval_config_version="retrieval.v3",
    )


@pytest.mark.asyncio
async def test_rag_context_build_calls_knowledge_service_once_with_trusted_context_projection() -> None:
    from src.agent.nodes.rag_context_build import rag_context_build

    ref = _ref()
    service = RecordingBuildService(_package(ref))
    state = {
        "tenant_id": OTHER_TENANT_ID,
        "current_run_id": "spoofed-run-from-state",
        "policy_evidence": [ref.model_dump(mode="json"), {"not": "an evidence ref"}],
        "retrieved_evidence": {
            "status": "strong_evidence",
            "evidence_refs": [ref.model_dump(mode="json")],
        },
        "trace_steps": [{"node": "investigate", "status": "completed"}],
    }

    result = await rag_context_build(state, _config(service=service))

    assert set(result) == {
        "rag_context_status",
        "verified_evidence_package",
        "citation_map",
        "evidence_map",
        "trace_steps",
    }
    assert len(service.calls) == 1
    call = service.calls[0]
    assert [item.evidence_id for item in call["candidate_evidence_refs"]] == [ref.evidence_id]
    assert call["knowledge_context"].tenant_id == TENANT_ID
    assert call["knowledge_context"].run_id == "run-rag-context"
    assert call["evidence_policy"]["evidence_required"] is True
    assert result["rag_context_status"] == "verified"
    assert result["verified_evidence_package"]["reason_codes"] == ["candidate_ref_invalid"]
    assert result["citation_map"] == {"C1": [ref.evidence_id]}
    assert result["evidence_map"] == {ref.evidence_id: ref.model_dump(mode="json")}
    assert [step["node"] for step in result["trace_steps"]] == ["investigate", "rag_context_build"]


@pytest.mark.asyncio
async def test_rag_context_build_combined_invalid_scope_stale_policy_version_and_invalid_hash_fail_closed() -> None:
    from src.agent.nodes.rag_context_build import rag_context_build

    wrong_tenant = _ref(
        tenant_id=OTHER_TENANT_ID,
        doc_key="policy_wrong_tenant",
        chunk_id="chunk_wrong_tenant",
        text="Wrong tenant candidate.",
        rank=1,
    )
    stale = _ref(
        doc_key="policy_stale",
        chunk_id="chunk_stale",
        policy_version="v1",
        text="Stale policy_version candidate.",
        rank=2,
    )
    invalid_hash = _ref(
        doc_key="policy_bad_hash",
        chunk_id="chunk_bad_hash",
        text="Original text_hash candidate.",
        rank=3,
    )
    retriever = FakeCanonicalRetriever(
        {
            (wrong_tenant.doc_key, wrong_tenant.chunk_id): _row(wrong_tenant),
            (stale.doc_key, stale.chunk_id): _row(stale, current_policy_version="v4"),
            (invalid_hash.doc_key, invalid_hash.chunk_id): _row(invalid_hash, content="Mutated canonical text."),
        }
    )
    service = PolicyKnowledgeService(retriever)
    malformed = {"schema_version": "evidence_ref.v1", "tenant_id": TENANT_ID}

    result = await rag_context_build(
        {
            "policy_evidence": [wrong_tenant.model_dump(mode="json"), malformed],
            "retrieved_evidence": {
                "evidence_refs": [
                    stale.model_dump(mode="json"),
                    invalid_hash.model_dump(mode="json"),
                ]
            },
        },
        _config(service=service),
    )

    package = result["verified_evidence_package"]
    ordinary_surface = str(package["prompt_projection"]) + str(package["verifier_projection"])
    assert len(retriever.calls) == 1
    assert result["rag_context_status"] == "invalid_hash"
    assert package["evidence_map"] == {}
    assert package["citation_map"] == {}
    assert "candidate_ref_invalid" in package["reason_codes"]
    assert "tenant_mismatch" in package["reason_codes"]
    assert "latest_version_invalid" in package["reason_codes"]
    assert "text_hash_mismatch" in package["reason_codes"]
    assert wrong_tenant.model_dump(mode="json") in package["rejected_candidate_refs"]
    assert stale.model_dump(mode="json") in package["stale_refs"]
    assert invalid_hash.model_dump(mode="json") in package["rejected_candidate_refs"]
    assert wrong_tenant.evidence_id not in ordinary_surface
    assert stale.evidence_id not in ordinary_surface
    assert invalid_hash.evidence_id not in ordinary_surface


@pytest.mark.asyncio
async def test_rag_context_build_returns_build_error_package_when_service_fails() -> None:
    from src.agent.nodes.rag_context_build import rag_context_build

    ref = _ref()
    service = RaisingBuildService()

    result = await rag_context_build(
        {"policy_evidence": [ref.model_dump(mode="json")]},
        _config(service=service),
    )

    package = result["verified_evidence_package"]
    assert service.calls == 1
    assert result["rag_context_status"] == "build_error"
    assert package["status"] == "build_error"
    assert package["reason_codes"] == ["rag_context_build_error"]
    assert package["rejected_candidate_refs"] == [ref.model_dump(mode="json")]
    assert result["citation_map"] == {}
    assert result["evidence_map"] == {}
