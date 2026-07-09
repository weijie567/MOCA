"""Business-tool facade with bounded per-call retries."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.adapters import (
    GetOrderInput,
    GetRefundCaseInput,
    GetTicketInput,
    get_order_adapter,
    get_refund_case_adapter,
    get_ticket_adapter,
)
from src.business.query.compiler import (
    BusinessQueryCompileError,
    BusinessQueryCompiler,
    BusinessQueryTimeWindow,
    CompiledBusinessQuery,
)
from src.business.query.schemas import (
    BusinessQueryAnswerContext,
    BusinessQueryCursor,
    BusinessQueryResultCursor,
    BusinessQueryResultV1,
    BusinessQueryScopeSummary,
    BusinessQuerySpec,
    metric_input_to_business_query,
)
from src.business.schemas import (
    BusinessContextV1,
    BusinessFactResultV1,
    BusinessMetricFiltersV1,
    BusinessMetricFreshnessV1,
    BusinessMetricQueryInput,
    BusinessMetricResultV1,
    BusinessMetricScopeV1,
    BusinessMetricTimeRangeV1,
)
from src.db.models import ActionDraft, Order, RefundCase, Ticket
from src.platform.trusted_context import MerchantScopeV1
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2


BusinessToolAdapter = Callable[[BaseModel, ToolCallContext, AsyncSession], Awaitable[ToolResultV2]]
BusinessFactAdapterResult = ToolResultV2 | BusinessFactResultV1
BusinessFactAdapter = Callable[[BaseModel, ToolCallContext, AsyncSession], Awaitable[BusinessFactAdapterResult]]

NO_LEAK_BUSINESS_RESOURCE_MESSAGE = "Business resource unavailable for this request"
FACT_BEARING_TOOL_STATUSES = {"success", "partial_success"}
BUSINESS_METRIC_TIMEZONE_NAME = "Asia/Shanghai"
BUSINESS_METRIC_TIMEZONE = ZoneInfo(BUSINESS_METRIC_TIMEZONE_NAME)
COUNT_METRIC_STATUS_ALLOWLISTS = {
    "order_count": {"pending", "paid", "shipped", "delivered", "completed"},
    "refund_case_count": {"submitted", "reviewing", "approved", "rejected", "closed"},
    "pending_ticket_count": {"open", "in_progress"},
}
PENDING_TICKET_DEFAULT_STATUSES = ["open", "in_progress"]
NO_STATUS_FILTER_METRICS = {"coupon_record_count", "merchant_refund_rate"}


@dataclass(frozen=True)
class BusinessReadToolDefinition:
    input_model: type[BaseModel]
    adapter: BusinessToolAdapter
    slot_name: str | None = None
    resource_name: str | None = None
    argument_name: str | None = None


BUSINESS_READ_TOOLS: dict[str, BusinessReadToolDefinition] = {
    "get_order": BusinessReadToolDefinition(
        input_model=GetOrderInput,
        adapter=get_order_adapter,
        slot_name="order_id",
        resource_name="order",
        argument_name="order_no",
    ),
    "get_refund_case": BusinessReadToolDefinition(
        input_model=GetRefundCaseInput,
        adapter=get_refund_case_adapter,
        slot_name="refund_case_id",
        resource_name="refund_case",
        argument_name="refund_case_no",
    ),
    "get_ticket": BusinessReadToolDefinition(
        input_model=GetTicketInput,
        adapter=get_ticket_adapter,
        slot_name="ticket_id",
        resource_name="ticket",
        argument_name="ticket_id",
    ),
}


def _merchant_scope_allows(
    merchant_scope: dict[str, Any] | list[str] | None,
    *,
    merchant_id: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
) -> bool:
    """Apply deny-first, all-provided-dimensions merchant-scope matching."""

    if merchant_scope is None:
        return False
    try:
        scope = (
            MerchantScopeV1(merchant_ids=merchant_scope)
            if isinstance(merchant_scope, list)
            else MerchantScopeV1.model_validate(merchant_scope)
        )
    except (TypeError, ValueError, ValidationError):
        return False
    return scope.allows(merchant_id=merchant_id, category=category, risk_level=risk_level)


class BusinessFactService:
    def __init__(
        self,
        session: AsyncSession,
        adapters: Mapping[str, BusinessFactAdapter] | None = None,
        tools: Mapping[str, BusinessReadToolDefinition] | None = None,
        query_compiler: BusinessQueryCompiler | None = None,
    ) -> None:
        self.session = session
        self.query_compiler = query_compiler or BusinessQueryCompiler()
        self.tools = dict(BUSINESS_READ_TOOLS if tools is None else tools)
        if adapters is not None:
            for name, adapter in adapters.items():
                definition = self.tools.get(name)
                if definition is not None:
                    self.tools[name] = replace(definition, adapter=adapter)

    @classmethod
    def with_default_registry(cls, session: AsyncSession) -> BusinessFactService:
        """Construct the domain service with current data-backed business reads."""

        return cls(session)

    def has_tool(self, name: str) -> bool:
        return name in self.tools or name in {
            "get_logistics",
            "get_merchant_risk",
            "business_query",
            "query_business_metric",
        }

    async def get_order(self, order_no: str, ctx: ToolCallContext) -> BusinessFactResultV1:
        return await self._read_tool("get_order", {"order_no": order_no}, ctx)

    async def get_refund_case(self, refund_case_no: str, ctx: ToolCallContext) -> BusinessFactResultV1:
        return await self._read_tool("get_refund_case", {"refund_case_no": refund_case_no}, ctx)

    async def get_ticket(self, ticket_id: str, ctx: ToolCallContext) -> BusinessFactResultV1:
        return await self._read_tool("get_ticket", {"ticket_id": ticket_id}, ctx)

    async def get_logistics(self, tracking_no: str, ctx: ToolCallContext) -> BusinessFactResultV1:
        del tracking_no
        return self._safe_result(
            "unavailable",
            resource_name="logistics",
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            scope_check_result="not_applicable",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="tool",
        )

    async def get_merchant_risk(self, merchant_id: str, ctx: ToolCallContext) -> BusinessFactResultV1:
        del merchant_id
        return self._safe_result(
            "unavailable",
            resource_name="merchant_risk",
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            scope_check_result="not_applicable",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="tool",
        )

    async def query_business_metric(self, args: dict[str, Any], ctx: ToolCallContext) -> BusinessFactResultV1:
        try:
            query = BusinessMetricQueryInput.model_validate(args)
        except ValidationError:
            return self._safe_result(
                "invalid_request",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_INVALID_REQUEST",
                safe_message="Business metric request is invalid",
                error_source="caller",
            )

        try:
            spec = metric_input_to_business_query(query)
        except ValidationError:
            return self._safe_result(
                "invalid_request",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_INVALID_REQUEST",
                safe_message="Business metric request is invalid",
                error_source="caller",
            )
        query_result = await self.query_business(spec, ctx)
        if query_result.status == "permission_denied":
            return self._permission_denied_result("business_metric", ctx.tenant_id)
        if query_result.status == "invalid_request":
            return self._safe_result(
                "invalid_request",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_INVALID_REQUEST",
                safe_message="Business metric request is invalid",
                error_source="caller",
            )
        if query_result.status != "ok" or query_result.fact is None:
            return self._safe_result(
                "unavailable",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_UNAVAILABLE",
                safe_message="Business metric is unavailable",
                error_source="tool",
            )

        try:
            result_payload = BusinessQueryResultV1.model_validate(query_result.fact["business_query"])
            metric = BusinessMetricResultV1.model_validate(result_payload.rows[0])
        except (KeyError, IndexError, TypeError, ValidationError):
            return self._safe_result(
                "unavailable",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_UNAVAILABLE",
                safe_message="Business metric is unavailable",
                error_source="tool",
            )
        return self._metric_to_business_fact_result(metric, ctx)

    async def query_business(
        self,
        args: dict[str, Any] | BusinessQuerySpec,
        ctx: ToolCallContext,
    ) -> BusinessFactResultV1:
        try:
            spec = args if isinstance(args, BusinessQuerySpec) else BusinessQuerySpec.model_validate(args)
        except ValidationError:
            return self._safe_result(
                "invalid_request",
                resource_name="business_query",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_QUERY_INVALID_REQUEST",
                safe_message="Business query request is invalid",
                error_source="caller",
            )

        merchant_ids = self._authorized_business_query_merchant_ids(spec, ctx)
        if merchant_ids is None:
            return self._business_query_result_to_fact_result(self._denied_business_query_result(spec), ctx)

        try:
            compiled = self.query_compiler.compile(
                spec,
                tenant_id=ctx.tenant_id,
                authorized_merchant_ids=merchant_ids,
                effective_at=self._parse_effective_at(ctx),
            )
            result = await self._execute_business_query(compiled, ctx)
        except (BusinessQueryCompileError, ValidationError):
            return self._safe_result(
                "invalid_request",
                resource_name="business_query",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_QUERY_INVALID_REQUEST",
                safe_message="Business query request is invalid",
                error_source="caller",
            )

        return self._business_query_result_to_fact_result(result, ctx)

    def _authorized_business_query_merchant_ids(
        self,
        spec: BusinessQuerySpec,
        ctx: ToolCallContext,
    ) -> list[str] | None:
        try:
            scope = (
                MerchantScopeV1(merchant_ids=ctx.merchant_scope)
                if isinstance(ctx.merchant_scope, list)
                else MerchantScopeV1.model_validate(ctx.merchant_scope)
            )
        except (TypeError, ValueError, ValidationError):
            return None
        if not scope.merchant_ids:
            return None
        if spec.merchant_id is not None:
            if not scope.allows(merchant_id=spec.merchant_id):
                return None
            return [spec.merchant_id]
        return list(scope.merchant_ids)

    @staticmethod
    def _denied_business_query_result(spec: BusinessQuerySpec) -> BusinessQueryResultV1:
        scope = BusinessQueryScopeSummary(
            scope_label="authorized_merchants",
            merchant_id=None,
            no_leak_status="scope_denied_no_existence_leak",
        )
        safe_spec = spec.model_copy(update={"merchant_id": None, "resource_id": None})
        return BusinessQueryResultV1(
            operation=spec.operation,
            resource=spec.resource,
            status="permission_denied",
            rows=[],
            answer_context=BusinessQueryAnswerContext(
                query_spec=safe_spec,
                result_refs=[],
                allowed_drilldowns=[],
                fields_shown=list(safe_spec.fields),
                scope=scope,
                time_summary=safe_spec.time_preset,
                filter_summary=",".join(safe_spec.filters.status_filter)
                if safe_spec.filters.status_filter
                else None,
            ),
            scope=scope,
        )

    async def _execute_business_query(
        self,
        compiled: CompiledBusinessQuery,
        ctx: ToolCallContext,
    ) -> BusinessQueryResultV1:
        operation = compiled.spec.operation
        if operation == "aggregate":
            row = await self._execute_business_query_aggregate(compiled, ctx)
            return self._business_query_result(compiled, status="ok", rows=[row])
        if operation == "list":
            return await self._execute_business_query_order_list(compiled)
        if operation == "detail":
            return await self._execute_business_query_order_detail(compiled)
        if operation == "breakdown":
            return await self._execute_business_query_order_breakdown(compiled)
        if operation == "compare":
            return await self._execute_business_query_order_compare(compiled)
        raise BusinessQueryCompileError("unsupported business query operation")

    async def _execute_business_query_aggregate(
        self,
        compiled: CompiledBusinessQuery,
        ctx: ToolCallContext,
    ) -> dict[str, Any]:
        spec = compiled.spec
        if spec.metric_id == "merchant_refund_rate":
            numerator = int(await self.session.scalar(compiled.statements["numerator"]) or 0)
            denominator = int(await self.session.scalar(compiled.statements["denominator"]) or 0)
            if denominator == 0:
                metric = self._business_query_metric_result(
                    compiled,
                    ctx,
                    status="non_computable",
                    value=None,
                    rate=None,
                    numerator=numerator,
                    denominator=denominator,
                    unit="ratio",
                    display_value="暂无可计算退款率",
                    formula="distinct refunded orders / total scoped orders",
                    caveats=["当前范围内没有订单，无法计算退款率。"],
                )
            else:
                rate = numerator / denominator
                metric = self._business_query_metric_result(
                    compiled,
                    ctx,
                    value=rate,
                    rate=rate,
                    numerator=numerator,
                    denominator=denominator,
                    unit="ratio",
                    display_value=f"{rate * 100:.2f}%",
                    formula="distinct refunded orders / total scoped orders",
                )
            return metric.model_dump(mode="json")

        value = int(await self.session.scalar(compiled.statements["value"]) or 0)
        metric_descriptor = self.query_compiler.registry.metric_descriptor(str(spec.metric_id))
        formula_map = {
            "order_count": "count orders by created_at in authorized merchant scope",
            "refund_case_count": "count refund cases by created_at joined through scoped orders",
            "pending_ticket_count": "count open or in-progress tickets joined through scoped orders",
            "coupon_record_count": "count MOCA issue_coupon ActionDraft records by created_at",
        }
        caveats = (
            [
                "MOCA demo only: coupon_record_count counts issue_coupon ActionDraft records/drafts, "
                "not external coupon delivery success."
            ]
            if spec.metric_id == "coupon_record_count"
            else []
        )
        return self._business_query_metric_result(
            compiled,
            ctx,
            value=value,
            unit=metric_descriptor.unit,
            display_value=str(value),
            formula=formula_map[str(spec.metric_id)],
            caveats=caveats,
        ).model_dump(mode="json")

    async def _execute_business_query_order_list(
        self,
        compiled: CompiledBusinessQuery,
    ) -> BusinessQueryResultV1:
        result = await self.session.execute(compiled.statements["rows"])
        records = [dict(row) for row in result.mappings().all()]
        has_more = len(records) > compiled.limit
        visible_records = records[: compiled.limit]
        rows = [self._safe_business_query_row(row) for row in visible_records]
        cursor = None
        if has_more and visible_records:
            last_row = visible_records[-1]
            cursor = BusinessQueryResultCursor(
                cursor_id=BusinessQueryCompiler.encode_order_cursor(
                    created_at=last_row["created_at"],
                    order_no=str(last_row["order_no"]),
                ),
                has_more=True,
                limit=compiled.limit,
                next_cursor=BusinessQueryCursor(
                    cursor_id=BusinessQueryCompiler.encode_order_cursor(
                        created_at=last_row["created_at"],
                        order_no=str(last_row["order_no"]),
                    ),
                    direction="next",
                ),
            )
        status = "ok" if rows else "empty"
        return self._business_query_result(compiled, status=status, rows=rows, cursor=cursor)

    async def _execute_business_query_order_detail(
        self,
        compiled: CompiledBusinessQuery,
    ) -> BusinessQueryResultV1:
        result = await self.session.execute(compiled.statements["row"])
        row = result.mappings().first()
        if row is None:
            return self._business_query_result(compiled, status="empty", rows=[])
        return self._business_query_result(compiled, status="ok", rows=[self._safe_business_query_row(dict(row))])

    async def _execute_business_query_order_breakdown(
        self,
        compiled: CompiledBusinessQuery,
    ) -> BusinessQueryResultV1:
        result = await self.session.execute(compiled.statements["rows"])
        rows = [
            {"status": row["status"], "value": int(row["value"] or 0), "display_value": str(int(row["value"] or 0))}
            for row in result.mappings().all()
        ]
        return self._business_query_result(compiled, status="ok" if rows else "empty", rows=rows)

    async def _execute_business_query_order_compare(
        self,
        compiled: CompiledBusinessQuery,
    ) -> BusinessQueryResultV1:
        current = int(await self.session.scalar(compiled.statements["current"]) or 0)
        previous = int(await self.session.scalar(compiled.statements["previous"]) or 0)
        row = {
            "metric_id": compiled.spec.metric_id,
            "current_value": current,
            "previous_value": previous,
            "delta": current - previous,
            "display_value": str(current),
            "current_period": self._time_window_payload(compiled.time_window),
            "previous_period": self._time_window_payload(compiled.previous_time_window),
        }
        return self._business_query_result(compiled, status="ok", rows=[row])

    def _business_query_metric_result(
        self,
        compiled: CompiledBusinessQuery,
        ctx: ToolCallContext,
        *,
        status: Literal["ok", "invalid_request", "non_computable"] = "ok",
        value: float | int | None,
        rate: float | None = None,
        numerator: int | None = None,
        denominator: int | None = None,
        unit: str,
        display_value: str,
        formula: str,
        caveats: list[str] | None = None,
    ) -> BusinessMetricResultV1:
        computed_at = datetime.now(UTC)
        return BusinessMetricResultV1(
            metric_id=compiled.spec.metric_id,
            status=status,
            value=float(value) if value is not None else None,
            rate=rate,
            numerator=numerator,
            denominator=denominator,
            unit=unit,
            display_value=display_value,
            scope=BusinessMetricScopeV1(
                tenant_id=ctx.tenant_id,
                merchant_ids=list(compiled.merchant_ids),
                scope_label="all_authorized_merchants" if "*" in compiled.merchant_ids else "authorized_merchants",
            ),
            time_range=BusinessMetricTimeRangeV1(
                start_at=compiled.time_window.start_at,
                end_at=compiled.time_window.end_at,
                preset=compiled.time_window.preset,
                timezone=compiled.time_window.timezone,
            ),
            filters=BusinessMetricFiltersV1(
                merchant_id=compiled.spec.merchant_id,
                status_filter=list(compiled.status_filter),
            ),
            freshness=BusinessMetricFreshnessV1(
                data_freshness_at=computed_at,
                computed_at=computed_at,
                source_system="business_fact_service",
            ),
            formula=formula,
            caveats=caveats or [],
            no_leak_status="not_applicable",
        )

    def _business_query_result(
        self,
        compiled: CompiledBusinessQuery,
        *,
        status: Literal["ok", "partial", "empty", "permission_denied", "invalid_request", "unavailable"],
        rows: list[dict[str, Any]],
        cursor: BusinessQueryResultCursor | None = None,
    ) -> BusinessQueryResultV1:
        scope = BusinessQueryScopeSummary(
            scope_label="all_authorized_merchants" if "*" in compiled.merchant_ids else "authorized_merchants",
            merchant_id=compiled.spec.merchant_id,
        )
        fields_shown = list(compiled.fields)
        query_spec = compiled.spec
        if compiled.spec.operation == "detail" and status == "empty":
            query_spec = compiled.spec.model_copy(update={"resource_id": None})
        answer_context = BusinessQueryAnswerContext(
            query_spec=query_spec,
            result_refs=self._business_query_result_refs(compiled, rows),
            allowed_drilldowns=self._allowed_business_query_drilldowns(compiled),
            fields_shown=fields_shown,
            cursor=cursor,
            scope=scope,
            time_summary=compiled.time_window.preset,
            filter_summary=",".join(compiled.status_filter) if compiled.status_filter else None,
        )
        return BusinessQueryResultV1(
            operation=compiled.spec.operation,
            resource=compiled.spec.resource,
            status=status,
            rows=rows,
            answer_context=answer_context,
            cursor=cursor,
            scope=scope,
        )

    @staticmethod
    def _business_query_result_refs(compiled: CompiledBusinessQuery, rows: list[dict[str, Any]]) -> list[str]:
        if compiled.spec.operation == "aggregate" and compiled.spec.metric_id:
            return [compiled.spec.metric_id]
        refs = []
        for row in rows:
            order_no = row.get("order_no")
            if isinstance(order_no, str):
                refs.append(order_no)
        return refs

    @staticmethod
    def _allowed_business_query_drilldowns(compiled: CompiledBusinessQuery) -> list[str]:
        if compiled.spec.operation == "aggregate" and compiled.spec.resource == "order":
            return ["list"]
        if compiled.spec.operation == "list" and compiled.spec.resource == "order":
            return ["detail"]
        return []

    @staticmethod
    def _safe_business_query_row(row: dict[str, Any]) -> dict[str, Any]:
        return {key: BusinessFactService._json_safe_value(value) for key, value in row.items() if key != "created_at"}

    @staticmethod
    def _json_safe_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if hasattr(value, "quantize"):
            return str(value)
        return value

    @staticmethod
    def _time_window_payload(time_window: BusinessQueryTimeWindow | None) -> dict[str, Any] | None:
        if time_window is None:
            return None
        return {
            "start_at": BusinessFactService._json_safe_value(time_window.start_at) if time_window.start_at else None,
            "end_at": BusinessFactService._json_safe_value(time_window.end_at) if time_window.end_at else None,
            "preset": time_window.preset,
            "timezone": time_window.timezone,
        }

    @staticmethod
    def _business_query_result_to_fact_result(
        result: BusinessQueryResultV1,
        ctx: ToolCallContext,
    ) -> BusinessFactResultV1:
        retrieved_at = datetime.now(UTC)
        fact_ref = BusinessFactRefV1(
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            resource_type="business_query",
            resource_id=f"{result.operation}:{result.resource}",
            resource_version=result.schema_version,
            data_freshness_at=retrieved_at,
            retrieved_at=retrieved_at,
        )
        return BusinessFactResultV1(
            tenant_id=ctx.tenant_id,
            status="ok",
            fact={"business_query": result.model_dump(mode="json")},
            business_fact_refs=[fact_ref],
            resource_version=result.schema_version,
            data_freshness_at=retrieved_at,
            source_system="business_fact_service",
            scope_check_result="allowed",
            missing_required_facts=[],
            safe_errors=[],
        )

    async def fetch_context(self, slots: dict[str, Any], intent: str, ctx: ToolCallContext) -> BusinessContextV1:
        """Aggregate approved domain facts into a prompt-safe business context."""

        del intent
        facts: dict[str, Any] = {}
        fact_refs: list[BusinessFactRefV1] = []
        fact_ref_keys: set[str] = set()
        missing_required_facts: list[str] = []
        errors: list[ToolError] = []
        freshness_values = []

        try:
            for tool_name, definition in self.tools.items():
                slot_name = definition.slot_name
                resource_name = definition.resource_name
                argument_name = definition.argument_name
                if slot_name is None or resource_name is None or argument_name is None:
                    continue
                identifier = slots.get(slot_name)
                if not identifier:
                    continue

                tool_ctx = ctx.model_copy(update={"tool_call_id": str(uuid4()), "attempt": 1})
                result = await self._read_tool(tool_name, {argument_name: identifier}, tool_ctx)
                if result.status in {"ok", "partial"} and result.fact is not None and result.business_fact_refs:
                    facts[resource_name] = result.fact
                    for fact_ref in result.business_fact_refs:
                        key = fact_ref.model_dump_json()
                        if key not in fact_ref_keys:
                            fact_ref_keys.add(key)
                            fact_refs.append(fact_ref)
                    if result.data_freshness_at is not None:
                        freshness_values.append(result.data_freshness_at)
                else:
                    for missing in result.missing_required_facts or [resource_name]:
                        if missing not in missing_required_facts:
                            missing_required_facts.append(missing)
                    errors.extend(result.safe_errors)
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
                definition.resource_name
                for definition in self.tools.values()
                if definition.slot_name is not None
                and definition.resource_name is not None
                and slots.get(definition.slot_name)
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
            tool_results=[],
            missing_required_facts=missing_required_facts,
            errors=errors,
            data_freshness_at=max(freshness_values) if freshness_values else None,
        )

    def _authorized_metric_merchant_ids(
        self,
        query: BusinessMetricQueryInput,
        ctx: ToolCallContext,
    ) -> list[str] | None:
        try:
            scope = (
                MerchantScopeV1(merchant_ids=ctx.merchant_scope)
                if isinstance(ctx.merchant_scope, list)
                else MerchantScopeV1.model_validate(ctx.merchant_scope)
            )
        except (TypeError, ValueError, ValidationError):
            return None
        if not scope.merchant_ids:
            return None
        if query.merchant_id is not None:
            if not scope.allows(merchant_id=query.merchant_id):
                return None
            return [query.merchant_id]
        return list(scope.merchant_ids)

    async def _calculate_business_metric(
        self,
        query: BusinessMetricQueryInput,
        ctx: ToolCallContext,
        merchant_ids: list[str],
    ) -> BusinessMetricResultV1:
        time_range = self._resolve_metric_time_range(query, ctx)
        if time_range is None:
            return self._invalid_metric_result(query, ctx, merchant_ids)

        status_filter = self._resolve_metric_status_filter(query)
        if status_filter is None:
            return self._invalid_metric_result(query, ctx, merchant_ids, time_range=time_range)

        tenant_id = self._safe_uuid(ctx.tenant_id)
        if tenant_id is None:
            return self._invalid_metric_result(query, ctx, merchant_ids, time_range=time_range)

        merchant_uuid_ids = self._safe_merchant_uuid_ids(merchant_ids)
        if merchant_uuid_ids == []:
            return self._invalid_metric_result(query, ctx, merchant_ids, time_range=time_range)

        if query.metric_id == "order_count":
            value = await self._count_orders(
                tenant_id=tenant_id,
                merchant_uuid_ids=merchant_uuid_ids,
                time_range=time_range,
                status_filter=status_filter,
            )
            return self._metric_result(
                query,
                ctx,
                merchant_ids,
                time_range=time_range,
                status_filter=status_filter,
                value=value,
                unit="count",
                display_value=str(value),
                formula="count orders by created_at in authorized merchant scope",
            )

        if query.metric_id == "refund_case_count":
            value = await self._count_refund_cases(
                tenant_id=tenant_id,
                merchant_uuid_ids=merchant_uuid_ids,
                time_range=time_range,
                status_filter=status_filter,
            )
            return self._metric_result(
                query,
                ctx,
                merchant_ids,
                time_range=time_range,
                status_filter=status_filter,
                value=value,
                unit="count",
                display_value=str(value),
                formula="count refund cases by created_at joined through scoped orders",
            )

        if query.metric_id == "pending_ticket_count":
            value = await self._count_pending_tickets(
                tenant_id=tenant_id,
                merchant_uuid_ids=merchant_uuid_ids,
                time_range=time_range,
                status_filter=status_filter,
            )
            return self._metric_result(
                query,
                ctx,
                merchant_ids,
                time_range=time_range,
                status_filter=status_filter,
                value=value,
                unit="count",
                display_value=str(value),
                formula="count open or in-progress tickets joined through scoped orders",
            )

        if query.metric_id == "coupon_record_count":
            value = await self._count_coupon_records(
                tenant_id=tenant_id,
                merchant_ids=merchant_ids,
                time_range=time_range,
            )
            return self._metric_result(
                query,
                ctx,
                merchant_ids,
                time_range=time_range,
                status_filter=status_filter,
                value=value,
                unit="count",
                display_value=str(value),
                formula="count MOCA issue_coupon ActionDraft records by created_at",
                caveats=[
                    "MOCA demo only: coupon_record_count counts issue_coupon ActionDraft records/drafts, "
                    "not external coupon delivery success."
                ],
            )

        numerator, denominator = await self._merchant_refund_rate_counts(
            tenant_id=tenant_id,
            merchant_uuid_ids=merchant_uuid_ids,
            time_range=time_range,
        )
        if denominator == 0:
            return self._metric_result(
                query,
                ctx,
                merchant_ids,
                time_range=time_range,
                status_filter=status_filter,
                status="non_computable",
                value=None,
                rate=None,
                numerator=numerator,
                denominator=denominator,
                unit="ratio",
                display_value="暂无可计算退款率",
                formula="distinct refunded orders / total scoped orders",
                caveats=["当前范围内没有订单，无法计算退款率。"],
            )

        rate = numerator / denominator
        return self._metric_result(
            query,
            ctx,
            merchant_ids,
            time_range=time_range,
            status_filter=status_filter,
            value=rate,
            rate=rate,
            numerator=numerator,
            denominator=denominator,
            unit="ratio",
            display_value=f"{rate * 100:.2f}%",
            formula="distinct refunded orders / total scoped orders",
        )

    @staticmethod
    def _safe_uuid(value: str) -> UUID | None:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _safe_merchant_uuid_ids(self, merchant_ids: list[str]) -> list[UUID] | None:
        if "*" in merchant_ids:
            return None
        parsed = [self._safe_uuid(merchant_id) for merchant_id in merchant_ids]
        if any(merchant_id is None for merchant_id in parsed):
            return []
        return [merchant_id for merchant_id in parsed if merchant_id is not None]

    @staticmethod
    def _parse_effective_at(ctx: ToolCallContext) -> datetime:
        if ctx.effective_at is None:
            return datetime.now(BUSINESS_METRIC_TIMEZONE)
        try:
            parsed = datetime.fromisoformat(ctx.effective_at.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(BUSINESS_METRIC_TIMEZONE)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(BUSINESS_METRIC_TIMEZONE)

    def _resolve_metric_time_range(
        self,
        query: BusinessMetricQueryInput,
        ctx: ToolCallContext,
    ) -> BusinessMetricTimeRangeV1 | None:
        if query.start_at is not None or query.end_at is not None:
            if query.start_at is None or query.end_at is None:
                return None
            return BusinessMetricTimeRangeV1(
                start_at=self._to_utc(query.start_at),
                end_at=self._to_utc(query.end_at),
                preset=query.time_preset,
                timezone=BUSINESS_METRIC_TIMEZONE_NAME,
            )

        if query.time_preset in {None, "current_snapshot"}:
            if query.metric_id != "pending_ticket_count" and query.time_preset is None:
                return None
            return BusinessMetricTimeRangeV1(
                start_at=None,
                end_at=None,
                preset=query.time_preset,
                timezone=BUSINESS_METRIC_TIMEZONE_NAME,
            )

        effective_at = self._parse_effective_at(ctx)
        start_local = self._preset_start_at(query.time_preset, effective_at)
        if start_local is None:
            return None
        return BusinessMetricTimeRangeV1(
            start_at=start_local.astimezone(UTC),
            end_at=effective_at.astimezone(UTC),
            preset=query.time_preset,
            timezone=BUSINESS_METRIC_TIMEZONE_NAME,
        )

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _preset_start_at(preset: str | None, effective_at: datetime) -> datetime | None:
        local = effective_at.astimezone(BUSINESS_METRIC_TIMEZONE)
        if preset == "today":
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
        if preset == "this_week":
            start = local - timedelta(days=local.weekday())
            return start.replace(hour=0, minute=0, second=0, microsecond=0)
        if preset == "this_month":
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if preset == "this_quarter":
            quarter_month = ((local.month - 1) // 3) * 3 + 1
            return local.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        if preset == "this_year":
            return local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return None

    @staticmethod
    def _resolve_metric_status_filter(query: BusinessMetricQueryInput) -> list[str] | None:
        if query.metric_id in NO_STATUS_FILTER_METRICS:
            return [] if not query.status_filter else None
        allowed = COUNT_METRIC_STATUS_ALLOWLISTS[query.metric_id]
        if query.status_filter:
            if not set(query.status_filter).issubset(allowed):
                return None
            return list(query.status_filter)
        if query.metric_id == "pending_ticket_count":
            return list(PENDING_TICKET_DEFAULT_STATUSES)
        return []

    @staticmethod
    def _time_conditions(column: Any, time_range: BusinessMetricTimeRangeV1) -> list[Any]:
        conditions = []
        if time_range.start_at is not None:
            conditions.append(column >= time_range.start_at)
        if time_range.end_at is not None:
            conditions.append(column < time_range.end_at)
        return conditions

    @staticmethod
    def _order_scope_conditions(
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
    ) -> list[Any]:
        conditions = [Order.tenant_id == tenant_id]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        return conditions

    async def _count_orders(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_range: BusinessMetricTimeRangeV1,
        status_filter: list[str],
    ) -> int:
        conditions = self._order_scope_conditions(tenant_id=tenant_id, merchant_uuid_ids=merchant_uuid_ids)
        conditions.extend(self._time_conditions(Order.created_at, time_range))
        if status_filter:
            conditions.append(Order.status.in_(status_filter))
        value = await self.session.scalar(select(func.count(Order.id)).where(*conditions))
        return int(value or 0)

    async def _count_refund_cases(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_range: BusinessMetricTimeRangeV1,
        status_filter: list[str],
    ) -> int:
        conditions = [
            RefundCase.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            RefundCase.order_id == Order.id,
        ]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        conditions.extend(self._time_conditions(RefundCase.created_at, time_range))
        if status_filter:
            conditions.append(RefundCase.status.in_(status_filter))
        value = await self.session.scalar(select(func.count(RefundCase.id)).select_from(RefundCase, Order).where(*conditions))
        return int(value or 0)

    async def _count_pending_tickets(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_range: BusinessMetricTimeRangeV1,
        status_filter: list[str],
    ) -> int:
        conditions = [
            Ticket.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            Ticket.order_id == Order.id,
            Ticket.status.in_(status_filter),
        ]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        conditions.extend(self._time_conditions(Ticket.created_at, time_range))
        value = await self.session.scalar(select(func.count(Ticket.id)).select_from(Ticket, Order).where(*conditions))
        return int(value or 0)

    async def _count_coupon_records(
        self,
        *,
        tenant_id: UUID,
        merchant_ids: list[str],
        time_range: BusinessMetricTimeRangeV1,
    ) -> int:
        conditions = [
            ActionDraft.tenant_id == tenant_id,
            ActionDraft.action_type == "issue_coupon",
        ]
        if "*" not in merchant_ids:
            conditions.append(ActionDraft.target_merchant_id.in_(merchant_ids))
        conditions.extend(self._time_conditions(ActionDraft.created_at, time_range))
        value = await self.session.scalar(select(func.count(ActionDraft.id)).where(*conditions))
        return int(value or 0)

    async def _merchant_refund_rate_counts(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_range: BusinessMetricTimeRangeV1,
    ) -> tuple[int, int]:
        order_conditions = self._order_scope_conditions(tenant_id=tenant_id, merchant_uuid_ids=merchant_uuid_ids)
        order_conditions.extend(self._time_conditions(Order.created_at, time_range))

        denominator = await self.session.scalar(select(func.count(distinct(Order.id))).where(*order_conditions))

        refund_conditions = [
            RefundCase.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            RefundCase.order_id == Order.id,
            *order_conditions,
        ]
        numerator = await self.session.scalar(
            select(func.count(distinct(RefundCase.order_id))).select_from(RefundCase, Order).where(*refund_conditions)
        )
        return int(numerator or 0), int(denominator or 0)

    def _invalid_metric_result(
        self,
        query: BusinessMetricQueryInput,
        ctx: ToolCallContext,
        merchant_ids: list[str],
        *,
        time_range: BusinessMetricTimeRangeV1 | None = None,
    ) -> BusinessMetricResultV1:
        return self._metric_result(
            query,
            ctx,
            merchant_ids,
            time_range=time_range
            or BusinessMetricTimeRangeV1(
                start_at=None,
                end_at=None,
                preset=query.time_preset,
                timezone=BUSINESS_METRIC_TIMEZONE_NAME,
            ),
            status_filter=[],
            status="invalid_request",
            value=None,
            unit="unknown",
            display_value="invalid_request",
            formula="invalid business metric request",
        )

    def _metric_result(
        self,
        query: BusinessMetricQueryInput,
        ctx: ToolCallContext,
        merchant_ids: list[str],
        *,
        time_range: BusinessMetricTimeRangeV1,
        status_filter: list[str],
        status: Literal["ok", "invalid_request", "non_computable"] = "ok",
        value: float | int | None,
        rate: float | None = None,
        numerator: int | None = None,
        denominator: int | None = None,
        unit: str,
        display_value: str,
        formula: str,
        caveats: list[str] | None = None,
    ) -> BusinessMetricResultV1:
        computed_at = datetime.now(UTC)
        return BusinessMetricResultV1(
            metric_id=query.metric_id,
            status=status,
            value=float(value) if value is not None else None,
            rate=rate,
            numerator=numerator,
            denominator=denominator,
            unit=unit,
            display_value=display_value,
            scope=BusinessMetricScopeV1(
                tenant_id=ctx.tenant_id,
                merchant_ids=list(merchant_ids),
                scope_label="all_authorized_merchants" if "*" in merchant_ids else "authorized_merchants",
            ),
            time_range=time_range,
            filters=BusinessMetricFiltersV1(merchant_id=query.merchant_id, status_filter=status_filter),
            freshness=BusinessMetricFreshnessV1(
                data_freshness_at=computed_at,
                computed_at=computed_at,
                source_system="business_fact_service",
            ),
            formula=formula,
            caveats=caveats or [],
            no_leak_status="not_applicable",
        )

    def _metric_to_business_fact_result(
        self,
        metric: BusinessMetricResultV1,
        ctx: ToolCallContext,
    ) -> BusinessFactResultV1:
        if metric.status == "permission_denied":
            return self._permission_denied_result("business_metric", ctx.tenant_id)
        if metric.status == "invalid_request":
            return self._safe_result(
                "invalid_request",
                resource_name="business_metric",
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_METRIC_INVALID_REQUEST",
                safe_message="Business metric request is invalid",
                error_source="caller",
            )

        fact = metric.model_dump(mode="json")
        fact_ref = BusinessFactRefV1(
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            resource_type="business_metric",
            resource_id=metric.metric_id,
            resource_version=None,
            data_freshness_at=metric.freshness.data_freshness_at,
            retrieved_at=datetime.now(UTC),
        )
        return BusinessFactResultV1(
            tenant_id=ctx.tenant_id,
            status="ok",
            fact=fact,
            business_fact_refs=[fact_ref],
            resource_version=None,
            data_freshness_at=metric.freshness.data_freshness_at,
            source_system="business_fact_service",
            scope_check_result="allowed",
            missing_required_facts=[],
            safe_errors=[],
        )

    async def _read_tool(
        self,
        name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
    ) -> BusinessFactResultV1:
        definition = self.tools.get(name)
        resource_name = definition.resource_name if definition is not None and definition.resource_name else name

        if not _merchant_scope_allows(ctx.merchant_scope):
            return self._permission_denied_result(resource_name, ctx.tenant_id)

        if ctx.attempt > ctx.max_attempts:
            return self._safe_result(
                "unavailable",
                resource_name=resource_name,
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_FACT_UNAVAILABLE",
                safe_message="Business fact is unavailable",
                error_source="adapter",
            )

        last_result: BusinessFactResultV1 | None = None
        for attempt in range(ctx.attempt, ctx.max_attempts + 1):
            attempt_ctx = ctx.model_copy(update={"attempt": attempt})
            raw_result = await self._invoke_adapter(name, args, attempt_ctx)
            fact_result = self._to_business_fact_result(raw_result, resource_name, ctx.tenant_id)
            last_result = fact_result
            if isinstance(raw_result, ToolResultV2) and raw_result.retryable is True and raw_result.status != "success":
                continue
            return fact_result
        return last_result or self._safe_result(
            "unavailable",
            resource_name=resource_name,
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            scope_check_result="unknown",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="adapter",
        )

    async def _invoke_adapter(
        self,
        name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
    ) -> BusinessFactAdapterResult:
        definition = self.tools.get(name)
        if definition is None:
            return self._safe_result(
                "unavailable",
                resource_name=name,
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="not_applicable",
                code="BUSINESS_FACT_UNAVAILABLE",
                safe_message="Business fact is unavailable",
                error_source="tool",
            )

        try:
            input_model = definition.input_model.model_validate(args)
        except ValidationError:
            resource_name = definition.resource_name or name
            return self._safe_result(
                "invalid_request",
                resource_name=resource_name,
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_FACT_INVALID_REQUEST",
                safe_message="Business fact request is invalid",
                error_source="caller",
            )

        try:
            result = await definition.adapter(input_model, ctx, self.session)
        except Exception:
            resource_name = definition.resource_name or name
            return self._safe_result(
                "unavailable",
                resource_name=resource_name,
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_FACT_UNAVAILABLE",
                safe_message="Business fact is unavailable",
                error_source="adapter",
            )
        if not isinstance(result, ToolResultV2 | BusinessFactResultV1):
            resource_name = definition.resource_name or name
            return self._safe_result(
                "unavailable",
                resource_name=resource_name,
                tenant_id=ctx.tenant_id,
                source_system="business_fact_service",
                scope_check_result="unknown",
                code="BUSINESS_FACT_UNAVAILABLE",
                safe_message="Business fact is unavailable",
                error_source="adapter",
            )
        return result

    def _to_business_fact_result(
        self,
        result: BusinessFactAdapterResult,
        resource_name: str,
        tenant_id: str,
    ) -> BusinessFactResultV1:
        if isinstance(result, BusinessFactResultV1):
            return self._sanitize_domain_result(result, resource_name, tenant_id)

        if result.status in {"success", "partial_success"} and result.data is not None:
            has_service_approved_refs = bool(result.business_fact_refs) and all(
                fact_ref.tenant_id == tenant_id for fact_ref in result.business_fact_refs
            )
            if not has_service_approved_refs:
                return self._safe_result(
                    "unavailable",
                    resource_name=resource_name,
                    tenant_id=tenant_id,
                    source_system=result.source_system,
                    scope_check_result="unknown",
                    code="BUSINESS_FACT_UNAVAILABLE",
                    safe_message="Business fact is unavailable",
                    error_source="adapter",
                )
            return BusinessFactResultV1(
                tenant_id=tenant_id,
                status="ok" if result.status == "success" else "partial",
                fact=result.data,
                business_fact_refs=result.business_fact_refs,
                resource_version=result.business_fact_refs[0].resource_version,
                data_freshness_at=result.data_freshness_at,
                source_system=result.source_system,
                scope_check_result="allowed",
                missing_required_facts=[],
                safe_errors=[],
            )

        if result.status == "permission_denied":
            return self._permission_denied_result(resource_name, tenant_id, source_system=result.source_system)
        if result.status == "not_found":
            not_found = self._safe_result(
                "not_found",
                resource_name=resource_name,
                tenant_id=tenant_id,
                source_system=result.source_system,
                scope_check_result="unknown",
            )
            if result.error is not None:
                not_found = not_found.model_copy(update={"safe_errors": [result.error]})
            return not_found
        if result.status == "invalid_request":
            return self._safe_result(
                "invalid_request",
                resource_name=resource_name,
                tenant_id=tenant_id,
                source_system=result.source_system,
                scope_check_result="unknown",
                code="BUSINESS_FACT_INVALID_REQUEST",
                safe_message="Business fact request is invalid",
                error_source="caller",
            )
        return self._safe_result(
            "unavailable",
            resource_name=resource_name,
            tenant_id=tenant_id,
            source_system=result.source_system,
            scope_check_result="unknown",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="adapter",
        )

    def _sanitize_domain_result(
        self,
        result: BusinessFactResultV1,
        resource_name: str,
        tenant_id: str,
    ) -> BusinessFactResultV1:
        if result.status in {"ok", "partial"}:
            has_service_approved_refs = (
                result.fact is not None
                and bool(result.business_fact_refs)
                and all(fact_ref.tenant_id == tenant_id for fact_ref in result.business_fact_refs)
            )
            if not has_service_approved_refs:
                return self._safe_result(
                    "unavailable",
                    resource_name=resource_name,
                    tenant_id=tenant_id,
                    source_system=result.source_system,
                    scope_check_result="unknown",
                    code="BUSINESS_FACT_UNAVAILABLE",
                    safe_message="Business fact is unavailable",
                    error_source="adapter",
                )
            return result.model_copy(update={"tenant_id": tenant_id, "scope_check_result": "allowed"})
        if result.status == "permission_denied":
            return self._permission_denied_result(resource_name, tenant_id, source_system=result.source_system)
        if result.status == "stale":
            safe_errors = result.safe_errors or [
                ToolError(
                    code="BUSINESS_FACT_STALE",
                    safe_message="Business fact is stale",
                    retryable=False,
                    source="adapter",
                )
            ]
            return result.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "fact": None,
                    "business_fact_refs": [],
                    "missing_required_facts": result.missing_required_facts or [resource_name],
                    "safe_errors": safe_errors,
                }
            )
        if result.status == "not_found":
            return self._safe_result(
                "not_found",
                resource_name=resource_name,
                tenant_id=tenant_id,
                source_system=result.source_system,
                scope_check_result="unknown",
            )
        if result.status == "invalid_request":
            return self._safe_result(
                "invalid_request",
                resource_name=resource_name,
                tenant_id=tenant_id,
                source_system=result.source_system,
                scope_check_result="unknown",
                code="BUSINESS_FACT_INVALID_REQUEST",
                safe_message="Business fact request is invalid",
                error_source="caller",
            )
        return self._safe_result(
            "unavailable",
            resource_name=resource_name,
            tenant_id=tenant_id,
            source_system=result.source_system,
            scope_check_result="unknown",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="adapter",
        )

    def _permission_denied_result(
        self,
        resource_name: str,
        tenant_id: str,
        *,
        source_system: str = "business_fact_service",
    ) -> BusinessFactResultV1:
        return self._safe_result(
            "permission_denied",
            resource_name=resource_name,
            tenant_id=tenant_id,
            source_system=source_system,
            scope_check_result="denied",
            code="BUSINESS_FACT_PERMISSION_DENIED",
            safe_message=NO_LEAK_BUSINESS_RESOURCE_MESSAGE,
            error_source="caller",
        )

    @staticmethod
    def _safe_result(
        status: Literal["not_found", "permission_denied", "stale", "unavailable", "invalid_request"],
        *,
        resource_name: str,
        tenant_id: str,
        source_system: str,
        scope_check_result: Literal["allowed", "denied", "not_applicable", "unknown"],
        code: str | None = None,
        safe_message: str | None = None,
        error_source: Literal["caller", "tool", "adapter", "upstream", "policy"] = "adapter",
    ) -> BusinessFactResultV1:
        safe_errors = []
        if code is not None and safe_message is not None:
            safe_errors.append(
                ToolError(code=code, safe_message=safe_message, retryable=False, source=error_source)
            )
        return BusinessFactResultV1(
            tenant_id=tenant_id,
            status=status,
            fact=None,
            business_fact_refs=[],
            resource_version=None,
            data_freshness_at=None,
            source_system=source_system,
            scope_check_result=scope_check_result,
            missing_required_facts=[resource_name],
            safe_errors=safe_errors,
        )


class BusinessToolService:
    def __init__(
        self,
        session: AsyncSession,
        adapters: Mapping[str, BusinessFactAdapter] | None = None,
        tools: Mapping[str, BusinessReadToolDefinition] | None = None,
        fact_service: BusinessFactService | None = None,
    ) -> None:
        self.session = session
        self.fact_service = fact_service or BusinessFactService(session, adapters=adapters, tools=tools)
        self.tools = self.fact_service.tools

    @classmethod
    def with_default_registry(cls, session: AsyncSession) -> BusinessToolService:
        """Compatibility constructor for the default business read adapters."""

        return cls(session)

    @classmethod
    def with_default_adapters(cls, session: AsyncSession) -> BusinessToolService:
        return cls(session)

    def has_tool(self, name: str) -> bool:
        return self.fact_service.has_tool(name)

    async def invoke_tool(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        """Invoke a logical business read through the domain fact boundary."""

        if name == "business_query":
            result = await self.fact_service.query_business(args, ctx)
        elif name == "query_business_metric":
            result = await self.fact_service.query_business_metric(args, ctx)
        else:
            result = await self.fact_service._read_tool(name, args, ctx)
        return self._wrap_business_fact_result(result)

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
            for tool_name, definition in self.tools.items():
                slot_name = definition.slot_name
                resource_name = definition.resource_name
                argument_name = definition.argument_name
                if slot_name is None or resource_name is None or argument_name is None:
                    continue
                identifier = slots.get(slot_name)
                if not identifier:
                    continue

                tool_ctx = ctx.model_copy(update={"tool_call_id": str(uuid4()), "attempt": 1})
                result = await self.invoke_tool(tool_name, {argument_name: identifier}, tool_ctx)
                tool_results.append(result)

                if (
                    result.status in FACT_BEARING_TOOL_STATUSES
                    and result.data is not None
                    and result.business_fact_refs
                ):
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
                definition.resource_name
                for definition in self.tools.values()
                if definition.slot_name is not None
                and definition.resource_name is not None
                and slots.get(definition.slot_name)
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
    def _wrap_business_fact_result(result: BusinessFactResultV1) -> ToolResultV2:
        status_map: dict[str, Literal[
            "success",
            "partial_success",
            "not_found",
            "permission_denied",
            "unavailable",
            "invalid_request",
        ]] = {
            "ok": "success",
            "partial": "partial_success",
            "not_found": "not_found",
            "permission_denied": "permission_denied",
            "stale": "unavailable",
            "unavailable": "unavailable",
            "invalid_request": "invalid_request",
        }
        code_map = {
            "not_found": "BUSINESS_FACT_NOT_FOUND",
            "permission_denied": "BUSINESS_FACT_PERMISSION_DENIED",
            "stale": "BUSINESS_FACT_STALE",
            "unavailable": "BUSINESS_FACT_UNAVAILABLE",
            "invalid_request": "BUSINESS_FACT_INVALID_REQUEST",
        }
        source_map: dict[str, Literal["caller", "tool", "adapter", "upstream", "policy"]] = {
            "not_found": "upstream",
            "permission_denied": "caller",
            "stale": "adapter",
            "unavailable": "adapter",
            "invalid_request": "caller",
        }

        tool_status = status_map[result.status]
        success = result.status in {"ok", "partial"} and result.fact is not None and result.business_fact_refs
        if success:
            return ToolResultV2(
                status=tool_status,
                data=result.fact,
                summary="Business fact read succeeded",
                source_system=result.source_system,
                data_freshness_at=result.data_freshness_at,
                policy_evidence_refs=[],
                business_fact_refs=result.business_fact_refs,
                error=None,
                retryable=False,
                retry_after_ms=None,
                latency_ms=0,
                audit_ref=None,
            )

        status = result.status if result.status not in {"ok", "partial"} else "unavailable"
        safe_message = (
            "Business fact request is invalid"
            if status == "invalid_request"
            else NO_LEAK_BUSINESS_RESOURCE_MESSAGE
        )
        safe_code = code_map[status]
        if status == "not_found" and result.safe_errors:
            safe_code = result.safe_errors[0].code
        return ToolResultV2(
            status=status_map[status],
            data=None,
            summary=safe_message,
            source_system=result.source_system,
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(
                code=safe_code,
                safe_message=safe_message,
                retryable=False,
                source=source_map[status],
            ),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
