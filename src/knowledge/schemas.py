"""Canonical knowledge contracts.

Spec Consistency Finding: ``policy_version`` is ``v{PolicyDocument.version}``
and evidence identity uses the ``@v3`` form, rather than the date-like
``policy_version`` shown in the EvidenceRefV1 JSON example. Effective dates
are reserved for effective-time filtering and do not determine identity.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.knowledge.text_hash import evidence_text_hash


class KnowledgeContext(BaseModel):
    """TrustedContext projection fields plus run-derived effective_at."""

    tenant_id: str
    user_id: str
    role: str
    merchant_scope: list[str] | None = None
    run_id: str
    trace_id: str
    locale: str | None = None
    effective_at: str


class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)

    @classmethod
    def build(
        cls,
        *,
        tenant_id: str,
        doc_key: str,
        chunk_id: str,
        policy_version: str,
        text: str,
        retrieved_at: str,
        retrieval_config_version: str,
        score: float | None = None,
        rank: int | None = None,
    ) -> EvidenceRefV1:
        return cls(
            tenant_id=tenant_id,
            evidence_id=f"{doc_key}/{chunk_id}@{policy_version}",
            doc_key=doc_key,
            chunk_id=chunk_id,
            policy_version=policy_version,
            text_hash=evidence_text_hash(text),
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )


class ClaimResult(BaseModel):
    claim_id: str
    claim_text: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    is_member: bool
    missing_evidence_ids: list[str] = Field(default_factory=list)


class CitationValidationResult(BaseModel):
    validator_version: str = "citation_validator.v2"
    claim_results: list[ClaimResult] = Field(default_factory=list)
    is_valid: bool = True


class KnowledgeSearchFilters(BaseModel):
    tenant_id: str
    merchant_id: str | None = None
    policy_types: list[str] | None = None
    effective_at: str | None = None
    locale: str | None = None


class KnowledgeSearchRequest(BaseModel):
    schema_version: Literal["knowledge_search_request.v2"] = "knowledge_search_request.v2"
    query: str
    primary_intent: str | None = None
    business_context_refs: list[dict] = Field(default_factory=list)
    filters: KnowledgeSearchFilters
    retrieval_config_version: str
    rerank_config_version: str
    max_results: int = 5
    allow_partial_evidence: bool = True


class KnowledgeSearchResult(BaseModel):
    schema_version: Literal["knowledge_search_result.v2"] = "knowledge_search_result.v2"
    status: Literal["strong_evidence", "partial_evidence", "no_evidence", "error"]
    query_rewrite: str | None = None
    retrieval_config_version: str
    rerank_config_version: str
    best_score: float
    threshold: float
    evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    citation_validation: CitationValidationResult = Field(default_factory=CitationValidationResult)
    summary: str | None = None
    error: dict | None = None


def canonical_evidence_projection(refs: list[EvidenceRefV1]) -> list[dict]:
    """Strip score and deterministically sort the producer-side hash projection."""
    items = []
    for ref in refs:
        item = ref.model_dump()
        item.pop("score", None)
        items.append(item)

    all_ranked = all(item.get("rank") is not None for item in items) and len(items) > 0
    if all_ranked:
        items.sort(key=lambda item: (item["rank"], item["evidence_id"], item["text_hash"]))
    else:
        items.sort(key=lambda item: (item["evidence_id"], item["text_hash"]))
    return items
