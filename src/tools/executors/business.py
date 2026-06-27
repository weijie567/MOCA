from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.business.service import BusinessFactService, BusinessToolService
from src.tools.contracts import ToolCallContext, ToolResultV2


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
        return self.service.has_tool(name)

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        return await self.service.invoke_tool(name, args, ctx)
