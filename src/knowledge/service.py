"""Policy knowledge facade.

Tenant-over-global precedence is DEFERRED_WITH_OWNER to post-Phase 17
Policy Scope. It depends on a schema and query migration that introduces
global/default policy scope, with schema-and-query tenant-over-global tests as
the acceptance gate.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Protocol
from uuid import UUID

from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchRequest, KnowledgeSearchResult
from src.knowledge.text_hash import evidence_text_hash


class PolicyRetriever(Protocol):
    async def retrieve(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[EvidenceRefV1], float]: ...

    async def get_contents_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]: ...


class PolicyKnowledgeService:
    def __init__(self, retriever: PolicyRetriever):
        self.retriever = retriever

    async def search(
        self,
        request: KnowledgeSearchRequest,
        context: KnowledgeContext,
    ) -> KnowledgeSearchResult:
        # Merchant filters are authorization inputs only until policy rows gain
        # merchant scope. Deny before adapter execution rather than widening an
        # unauthorized request into an unfiltered tenant search.
        merchant_id = request.filters.merchant_id
        merchant_scope = context.merchant_scope
        if not merchant_scope:
            return self._no_evidence_result()
        if (
            merchant_id is not None
            and "*" not in merchant_scope
            and merchant_id not in merchant_scope
        ):
            return self._no_evidence_result()

        doc_type = request.filters.policy_types[0] if request.filters.policy_types else None
        try:
            status, evidence_refs, best_score = await self.retriever.retrieve(
                query=request.query,
                context=context,
                max_results=request.max_results,
                doc_type=doc_type,
            )
        except asyncio.TimeoutError:
            return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
        except Exception:
            return self._error_result(
                "SEARCH_ERROR",
                "Failed to search policy evidence",
                retryable=False,
            )

        if status == "partial_evidence" and not request.allow_partial_evidence:
            return KnowledgeSearchResult(
                status="no_evidence",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                rerank_config_version=RERANK_CONFIG_VERSION,
                best_score=best_score,
                threshold=MIN_SIMILARITY_THRESHOLD,
                evidence_refs=[],
            )

        if status == "error":
            return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
        return KnowledgeSearchResult(
            status=status,
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=best_score,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=evidence_refs,
        )

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        try:
            tenant_uuid = UUID(tenant_id)
        except ValueError:
            return {}

        key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
        if not keys:
            return {}

        try:
            contents = await self.retriever.get_contents_by_evidence_keys(
                tenant_id=tenant_uuid,
                keys=keys,
            )
        except Exception:
            return {}

        verified: dict[str, str] = {}
        for ref in evidence_refs:
            key = (ref.doc_key, ref.chunk_id)
            content = contents.get(key)
            if (
                key_counts.get(key) == 1
                and ref.tenant_id == tenant_id
                and content is not None
                and evidence_text_hash(content) == ref.text_hash
            ):
                verified[ref.evidence_id] = content
        return verified

    @staticmethod
    def _no_evidence_result() -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            status="no_evidence",
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=0.0,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=[],
        )

    @staticmethod
    def _error_result(error_code: str, message: str, *, retryable: bool) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            status="error",
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=0.0,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=[],
            error={
                "error_code": error_code,
                "message": message,
                "retryable": retryable,
            },
        )
