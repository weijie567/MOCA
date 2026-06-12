"""Business-tool facade with bounded per-call retries."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.business_tools.adapters import get_order_adapter, get_refund_case_adapter, get_ticket_adapter
from src.business_tools.registry import RegisteredTool, ToolRegistry
from src.business_tools.schemas import BusinessContextV1, BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2


_CONTEXT_READS = {
    "order_id": ("get_order", "order", "order_no"),
    "refund_case_id": ("get_refund_case", "refund_case", "refund_case_no"),
    "ticket_id": ("get_ticket", "ticket", "ticket_id"),
}


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

        descriptor = next((item for item in self.registry.descriptors() if item.name == name), None)
        if descriptor is not None and descriptor.required_permission not in ctx.permissions:
            return self._local_error(
                "permission_denied",
                "Required tool permission is missing",
                code="PERMISSION_REQUIRED",
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

    async def fetch_context(self, slots: dict[str, Any], intent: str, ctx: ToolCallContext) -> BusinessContextV1:
        """Conditionally aggregate requested business reads into one typed context."""

        del intent  # Slot presence is the normative conditional read set.
        facts: dict[str, Any] = {}
        fact_refs: list[BusinessFactRefV1] = []
        fact_ref_keys: set[str] = set()
        tool_results: list[ToolResultV2] = []
        missing_required_facts: list[str] = []
        errors: list[ToolError] = []
        freshness_values = []

        try:
            for slot_name, (tool_name, resource_name, argument_name) in _CONTEXT_READS.items():
                identifier = slots.get(slot_name)
                if not identifier:
                    continue

                tool_ctx = ctx.model_copy(update={"tool_call_id": str(uuid4()), "attempt": 1})
                result = await self.invoke_tool(tool_name, {argument_name: identifier}, tool_ctx)
                tool_results.append(result)

                if result.status == "success" and result.data is not None:
                    facts[resource_name] = result.data
                    for fact_ref in result.business_fact_refs:
                        key = fact_ref.model_dump_json()
                        if key not in fact_ref_keys:
                            fact_ref_keys.add(key)
                            fact_refs.append(fact_ref)
                    if result.data_freshness_at is not None:
                        freshness_values.append(result.data_freshness_at)
                else:
                    missing_required_facts.append(resource_name)
                    if result.error is not None:
                        errors.append(result.error)
        except Exception:
            errors.append(
                ToolError(
                    code="BUSINESS_CONTEXT_AGGREGATION_ERROR",
                    safe_message="Business context aggregation failed",
                    retryable=False,
                    source="adapter",
                )
            )
            requested_resources = [
                resource_name
                for slot_name, (_, resource_name, _) in _CONTEXT_READS.items()
                if slots.get(slot_name)
            ]
            missing_required_facts.extend(
                resource_name
                for resource_name in requested_resources
                if resource_name not in facts and resource_name not in missing_required_facts
            )
            status = "error"
        else:
            if facts and not missing_required_facts:
                status = "complete"
            elif facts:
                status = "partial"
            else:
                status = "insufficient"

        return BusinessContextV1(
            tenant_id=ctx.tenant_id,
            status=status,
            facts=facts,
            business_fact_refs=fact_refs,
            tool_results=tool_results,
            missing_required_facts=missing_required_facts,
            errors=errors,
            data_freshness_at=max(freshness_values) if freshness_values else None,
        )

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
