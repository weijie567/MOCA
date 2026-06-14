from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.repository import SessionMemoryRepository
from src.memory.search import CaseMemorySearchService
from src.memory.schemas import CaseMemorySearchResult
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager_results import result


class MemoryToolExecutor:
    executor_name = "memory"

    def __init__(
        self,
        session: AsyncSession | None = None,
        service: CaseMemorySearchService | None = None,
    ) -> None:
        if service is not None:
            self.service = service
        elif session is not None:
            self.service = CaseMemorySearchService(SessionMemoryRepository(session))
        else:
            self.service = CaseMemorySearchService()

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
        search_result = await self.service.search(query=str(args["query"]), context=ctx)
        return _memory_result(search_result)


def _memory_result(search_result: CaseMemorySearchResult) -> ToolResultV2:
    if search_result.status == "success":
        return ToolResultV2(
            status="success",
            data={"items": [item.model_dump(mode="json") for item in search_result.items]},
            summary=search_result.summary,
            source_system="case_memory_search_service",
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
        "unavailable",
        search_result.summary,
        code=search_result.error_code or "TOOL_UNAVAILABLE",
        source="tool",
        source_system="case_memory_search_service",
    )
