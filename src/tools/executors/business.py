from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.business.service import BusinessToolService
from src.tools.contracts import ToolCallContext, ToolResultV2


class BusinessToolExecutor:
    executor_name = "business"

    def __init__(self, session: AsyncSession, service: BusinessToolService | None = None) -> None:
        self.service = service or BusinessToolService.with_default_registry(session)

    def has_tool(self, name: str) -> bool:
        return name in {"get_order", "get_refund_case", "get_ticket"}

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        return await self.service.invoke_tool(name, args, ctx)
