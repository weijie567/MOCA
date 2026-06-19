from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.schemas import CaseMemorySearchRequest, CaseMemorySearchResult
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager_results import result


class MemoryToolExecutor:
    executor_name = "memory"

    def __init__(
        self,
        session: AsyncSession | None = None,
        service: Any | None = None,
    ) -> None:
        if service is not None:
            self.service = service
        elif session is not None:
            self.service = CaseMemoryService(CaseMemoryRepository(session))
        else:
            self.service = None

    def has_tool(self, name: str) -> bool:
        return name == "search_case_memory"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "search_case_memory":
            return result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="memory_tool_executor",
            )
        if self.service is None or not hasattr(self.service, "retrieve_reviewed"):
            return result(
                "unavailable",
                "Reviewed case memory search is unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="case_memory_service",
            )
        request = _case_memory_request(query=str(args["query"]), context=ctx)
        if request is None:
            return result(
                "invalid_request",
                "Reviewed case memory search context is invalid",
                code="INVALID_CONTEXT",
                source="caller",
                source_system="case_memory_service",
            )
        search_result = await self.service.retrieve_reviewed(request)
        return _case_memory_result(search_result)


def _case_memory_request(*, query: str, context: ToolCallContext) -> CaseMemorySearchRequest | None:
    query_text = query.strip()
    if not query_text:
        return None
    try:
        tenant_id = UUID(context.tenant_id)
    except ValueError:
        return None

    scopes: list[tuple[str, str]] = [
        ("tenant", str(tenant_id)),
        ("user", context.user_id),
        ("thread", context.thread_id),
    ]
    merchant_ids = _merchant_ids(context.merchant_scope)
    scopes.extend(("merchant", merchant_id) for merchant_id in merchant_ids if merchant_id != "*")

    return CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scopes=scopes,
        query=query_text,
        limit=5,
    )


def _merchant_ids(merchant_scope: dict[str, Any] | list[str]) -> list[str]:
    if isinstance(merchant_scope, dict):
        raw_ids = merchant_scope.get("merchant_ids")
    else:
        raw_ids = merchant_scope
    if not isinstance(raw_ids, list):
        return []
    return [str(item) for item in raw_ids if isinstance(item, str) and item]


def _case_memory_result(search_result: CaseMemorySearchResult) -> ToolResultV2:
    if search_result.status == "success":
        return ToolResultV2(
            status="success",
            data={"items": [item.model_dump(mode="json") for item in search_result.items]},
            summary=f"Found {len(search_result.items)} reviewed case memory precedent item(s)",
            source_system="case_memory_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
    return result(
        "not_found",
        "No reviewed case memory precedent found",
        code="NO_REVIEWED_CASE_MEMORY",
        source="tool",
        source_system="case_memory_service",
    )
