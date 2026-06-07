"""Policy knowledge facade.

Tenant-over-global precedence is DEFERRED_WITH_OWNER to a later policy-scope
phase. It depends on a schema and query migration that introduces global policy
scope, with schema-and-query tenant-over-global tests as the acceptance gate.
"""

from __future__ import annotations

import asyncio

from src.knowledge.adapters import LegacyRagKnowledgeAdapter
from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchRequest, KnowledgeSearchResult


class PolicyKnowledgeService:
    def __init__(self, adapter: LegacyRagKnowledgeAdapter):
        self.adapter = adapter

    async def search(
        self,
        request: KnowledgeSearchRequest,
        context: KnowledgeContext,
    ) -> KnowledgeSearchResult:
        # Merchant filters are authorization inputs only until policy rows gain
        # merchant scope. Unauthorized IDs are dropped and none are sent to the DB.
        merchant_id = request.filters.merchant_id
        merchant_scope = context.merchant_scope
        if merchant_id is not None and merchant_scope is not None and merchant_id not in merchant_scope:
            merchant_id = None
        del merchant_id

        doc_type = request.filters.policy_types[0] if request.filters.policy_types else None
        try:
            status, evidence_refs, best_score = await self.adapter.retrieve(
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
