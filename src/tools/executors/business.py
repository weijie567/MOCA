from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.query.schemas import BusinessQuerySpec
from src.business.service import BusinessFactService, BusinessToolService
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager_results import result as safe_result


_SAFE_DEFERRED_TOOL_NAMES = frozenset({"business_query"})


class BusinessToolExecutor:
    executor_name = "business"

    def __init__(
        self,
        session: AsyncSession,
        service: BusinessToolService | BusinessFactService | None = None,
    ) -> None:
        if service is None:
            fact_service = BusinessFactService.with_default_registry(session)
            self.service = BusinessToolService(session, fact_service=fact_service)
        elif isinstance(service, BusinessFactService):
            self.service = BusinessToolService(session, fact_service=service)
        else:
            self.service = service

    def has_tool(self, name: str) -> bool:
        return name in _SAFE_DEFERRED_TOOL_NAMES or self.service.has_tool(name)

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name == "business_query":
            return self._business_query_deferred_result(args)
        return await self.service.invoke_tool(name, args, ctx)

    @staticmethod
    def _business_query_deferred_result(args: dict[str, Any]) -> ToolResultV2:
        try:
            BusinessQuerySpec.model_validate(args)
        except ValidationError:
            return safe_result(
                "invalid_request",
                "Business query request is invalid",
                code="BUSINESS_QUERY_INVALID_REQUEST",
                source="caller",
                source_system="business_tool_executor",
            )
        return safe_result(
            "unavailable",
            "Business query runtime is not connected yet",
            code="BUSINESS_QUERY_RUNTIME_DEFERRED",
            source="tool",
            source_system="business_tool_executor",
        )
