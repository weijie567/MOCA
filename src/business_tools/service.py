"""Business-tool facade with bounded per-call retries."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.business_tools.adapters import get_order_adapter, get_refund_case_adapter, get_ticket_adapter
from src.business_tools.registry import RegisteredTool, ToolRegistry
from src.business_tools.schemas import ToolCallContext, ToolError, ToolResultV2


def _merchant_scope_allows(
    merchant_scope: dict[str, Any] | None,
    *,
    merchant_id: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
) -> bool:
    """Apply deny-first, all-provided-dimensions merchant-scope matching."""

    if not merchant_scope:
        return False

    merchant_ids = merchant_scope.get("merchant_ids")
    if not isinstance(merchant_ids, list) or not merchant_ids:
        return False

    dimensions = (
        (merchant_id, merchant_ids),
        (category, merchant_scope.get("categories")),
        (risk_level, merchant_scope.get("risk_levels")),
    )
    for value, allowed in dimensions:
        if value is None:
            continue
        if not isinstance(allowed, list) or not allowed:
            return False
        if "*" not in allowed and value not in allowed:
            return False
    return True


class BusinessToolService:
    def __init__(self, registry: ToolRegistry, session: AsyncSession) -> None:
        self.registry = registry
        self.session = session

    @classmethod
    def with_default_registry(cls, session: AsyncSession) -> BusinessToolService:
        """Compose the live read registry from canonical descriptors and adapters."""

        descriptors = {descriptor.name: descriptor for descriptor in ToolRegistry().descriptors()}
        adapters = {
            "get_order": get_order_adapter,
            "get_refund_case": get_refund_case_adapter,
            "get_ticket": get_ticket_adapter,
        }
        tools = [
            RegisteredTool(descriptor=descriptor, adapter=adapters.get(name))
            for name, descriptor in descriptors.items()
        ]
        return cls(ToolRegistry(tools), session)

    async def invoke_tool(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        """Invoke one logical tool call, retrying only explicitly retryable results."""

        if not _merchant_scope_allows(ctx.merchant_scope):
            return self._local_error(
                "permission_denied",
                "Merchant scope is required",
                code="EMPTY_MERCHANT_SCOPE",
            )

        # Order/refund/ticket inputs do not expose merchant-identifying dimensions;
        # their resource merchant check remains at the raw merchant_can_access seam.
        if not _merchant_scope_allows(
            ctx.merchant_scope,
            merchant_id=args.get("merchant_id"),
            category=args.get("category"),
            risk_level=args.get("risk_level"),
        ):
            return self._local_error(
                "permission_denied",
                "Business resource is outside merchant scope",
                code="MERCHANT_SCOPE_DENIED",
            )

        if ctx.attempt > ctx.max_attempts:
            return self._local_error(
                "error",
                "Tool retry limit exhausted",
                code="MAX_ATTEMPTS_EXHAUSTED",
            )

        for attempt in range(ctx.attempt, ctx.max_attempts + 1):
            attempt_ctx = ctx.model_copy(update={"attempt": attempt})
            result = await self.registry.invoke(name, args, attempt_ctx, self.session)
            if result.status == "success" or result.retryable is not True:
                return result
        return result

    @staticmethod
    def _local_error(
        status: Literal["permission_denied", "error"],
        summary: str,
        *,
        code: str,
    ) -> ToolResultV2:
        return ToolResultV2(
            status=status,
            data=None,
            summary=summary,
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(code=code, safe_message=summary, retryable=False, source="caller"),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
