from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService
from src.tools.contracts import ToolCallContext, ToolError, ToolResultV2
from src.tools.manager_results import result


class KnowledgeToolExecutor:
    executor_name = "knowledge"

    def __init__(
        self,
        session: AsyncSession,
        service: PolicyKnowledgeService | None = None,
    ) -> None:
        self.service = service or PolicyKnowledgeService(PolicyRetrievalEngine(session))

    def has_tool(self, name: str) -> bool:
        return name == "search_policy"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "search_policy":
            return result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="knowledge_tool_executor",
            )

        effective_at = ctx.effective_at or datetime.now(UTC).isoformat()
        request = KnowledgeSearchRequest(
            query=str(args["query"]),
            primary_intent=args.get("primary_intent"),
            filters=KnowledgeSearchFilters(
                tenant_id=ctx.tenant_id,
                merchant_id=args.get("merchant_id"),
                effective_at=effective_at,
                locale=None,
            ),
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            max_results=int(args.get("max_results") or 5),
            allow_partial_evidence=bool(args.get("allow_partial_evidence", True)),
        )
        search_result = await self.service.search(
            request,
            KnowledgeContext(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                role=ctx.role,
                merchant_scope=_knowledge_merchant_scope(ctx.merchant_scope),
                run_id=ctx.run_id,
                trace_id=ctx.trace_id,
                locale=None,
                effective_at=effective_at,
            ),
        )
        status_map = {
            "strong_evidence": "success",
            "partial_evidence": "success",
            "no_evidence": "not_found",
            "error": "error",
        }
        error = None
        if search_result.error:
            error = ToolError(
                code=str(search_result.error.get("error_code") or "KNOWLEDGE_SEARCH_ERROR"),
                safe_message=str(search_result.error.get("message") or "Policy search failed"),
                retryable=bool(search_result.error.get("retryable", False)),
                source="upstream",
            )
        return ToolResultV2(
            status=status_map[search_result.status],
            data={
                "retrieval_status": search_result.status,
                "best_score": search_result.best_score,
                "threshold": search_result.threshold,
                "summary": search_result.summary,
            },
            summary=search_result.summary or f"Policy search returned {search_result.status}",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=search_result.evidence_refs,
            business_fact_refs=[],
            error=error,
            retryable=bool(error.retryable) if error else False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )


def _knowledge_merchant_scope(value: object) -> list[str]:
    raw_ids: object = value.get("merchant_ids") if isinstance(value, dict) else value
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    if not all(isinstance(item, str) and item for item in raw_ids):
        return []
    return list(raw_ids)
