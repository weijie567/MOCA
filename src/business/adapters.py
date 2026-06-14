"""Safe adapters from legacy business reads to the typed facade contract."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.demo_business.orders import get_order
from src.integrations.demo_business.refunds import get_refund_case
from src.integrations.demo_business.tickets import get_ticket
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2


class _StrictProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class GetOrderInput(BaseModel):
    order_no: str = Field(min_length=1)


class GetRefundCaseInput(BaseModel):
    refund_case_no: str = Field(min_length=1)


class GetTicketInput(BaseModel):
    ticket_id: str = Field(min_length=1)


class _OrderRelationHints(_StrictProjection):
    has_active_refund: bool
    latest_refund_case_id: str | None
    has_open_ticket: bool
    latest_ticket_id: str | None


class _OrderData(_StrictProjection):
    order_no: str
    status: str
    amount: str
    currency: str
    buyer_name: str
    item_name: str
    paid_at: str | None
    delivered_at: str | None
    relation_hints: _OrderRelationHints


class _RefundCaseData(_StrictProjection):
    refund_case_no: str
    status: str
    reason_code: str
    reason_text: str
    requested_amount: str
    approved_amount: str | None


class _TicketData(_StrictProjection):
    ticket_no: str
    status: str
    channel: str
    summary: str


_RawTool = Callable[[str, str, str, str, AsyncSession], Awaitable[dict[str, Any]]]
_ResourceType = Literal["order", "refund_case", "ticket"]
_ErrorSource = Literal["caller", "tool", "adapter", "upstream", "policy"]

_NOT_FOUND_CODES = {"ORDER_NOT_FOUND", "REFUND_CASE_NOT_FOUND", "TICKET_NOT_FOUND"}
_ERROR_MAPPING: dict[str, tuple[str, _ErrorSource, bool, str]] = {
    "FORBIDDEN": ("permission_denied", "caller", False, "Business resource access denied"),
    "DB_TIMEOUT": ("timeout", "adapter", True, "Business data source timed out"),
    "VALIDATION_ERROR": ("invalid_request", "caller", False, "Business read request is invalid"),
    "DB_ERROR": ("error", "adapter", False, "Business data source failed"),
}


def _latency_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _error_result(
    *,
    status: Literal["not_found", "permission_denied", "timeout", "invalid_request", "invalid_response", "error"],
    summary: str,
    source_system: str,
    code: str,
    source: _ErrorSource,
    retryable: bool,
    latency_ms: int,
) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=summary,
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(code=code, safe_message=summary, retryable=retryable, source=source),
        retryable=retryable,
        retry_after_ms=None,
        latency_ms=latency_ms,
        audit_ref=None,
    )


def _invalid_response(source_system: str, latency_ms: int) -> ToolResultV2:
    return _error_result(
        status="invalid_response",
        summary="Business read returned an invalid response",
        source_system=source_system,
        code="INVALID_BUSINESS_RESPONSE",
        source="adapter",
        retryable=False,
        latency_ms=latency_ms,
    )


def _map_raw_error(raw: dict[str, Any], source_system: str, latency_ms: int) -> ToolResultV2:
    error = raw.get("error")
    if raw.get("status") != "error" or not isinstance(error, dict):
        return _invalid_response(source_system, latency_ms)

    code = error.get("error_code")
    raw_retryable = error.get("retryable")
    if not isinstance(code, str) or not isinstance(raw_retryable, bool):
        return _invalid_response(source_system, latency_ms)

    if code in _NOT_FOUND_CODES:
        status, source, default_retryable, summary = (
            "not_found",
            "upstream",
            False,
            "Business resource was not found",
        )
    else:
        status, source, default_retryable, summary = _ERROR_MAPPING.get(
            code,
            ("error", "upstream", raw_retryable, "Business read failed"),
        )
    retryable = raw_retryable if code not in {"FORBIDDEN", "DB_TIMEOUT", "VALIDATION_ERROR"} else default_retryable
    if code == "DB_ERROR":
        retryable = raw_retryable

    return _error_result(
        status=status,  # type: ignore[arg-type]
        summary=summary,
        source_system=source_system,
        code=code,
        source=source,
        retryable=retryable,
        latency_ms=latency_ms,
    )


async def _adapt_read(
    *,
    raw_call: Awaitable[dict[str, Any]],
    projection: type[_StrictProjection],
    resource_type: _ResourceType,
    resource_id: str,
    source_system: str,
    success_summary: str,
    ctx: ToolCallContext,
    started_at: float,
) -> ToolResultV2:
    try:
        raw = await raw_call
    except asyncio.TimeoutError:
        return _error_result(
            status="timeout",
            summary="Business data source timed out",
            source_system=source_system,
            code="DB_TIMEOUT",
            source="adapter",
            retryable=True,
            latency_ms=_latency_ms(started_at),
        )
    except Exception:
        return _error_result(
            status="error",
            summary="Business read failed",
            source_system=source_system,
            code="ADAPTER_ERROR",
            source="adapter",
            retryable=False,
            latency_ms=_latency_ms(started_at),
        )

    latency_ms = _latency_ms(started_at)
    if not isinstance(raw, dict):
        return _invalid_response(source_system, latency_ms)
    if raw.get("status") != "success":
        return _map_raw_error(raw, source_system, latency_ms)

    try:
        projected = projection.model_validate(raw.get("data"))
    except ValidationError:
        return _invalid_response(source_system, latency_ms)

    retrieved_at = datetime.now(UTC)
    return ToolResultV2(
        status="success",
        data=projected.model_dump(mode="json"),
        summary=success_summary,
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[
            BusinessFactRefV1(
                tenant_id=ctx.tenant_id,
                source_system=source_system,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_version=None,
                data_freshness_at=None,
                retrieved_at=retrieved_at,
            )
        ],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=latency_ms,
        audit_ref=None,
    )


async def get_order_adapter(input_model: GetOrderInput, ctx: ToolCallContext, session: AsyncSession) -> ToolResultV2:
    started_at = perf_counter()
    return await _adapt_read(
        raw_call=get_order(input_model.order_no, ctx.tenant_id, ctx.user_id, ctx.role, session),
        projection=_OrderData,
        resource_type="order",
        resource_id=input_model.order_no,
        source_system="demo_orders_db",
        success_summary="Order read succeeded",
        ctx=ctx,
        started_at=started_at,
    )


async def get_refund_case_adapter(
    input_model: GetRefundCaseInput,
    ctx: ToolCallContext,
    session: AsyncSession,
) -> ToolResultV2:
    started_at = perf_counter()
    return await _adapt_read(
        raw_call=get_refund_case(input_model.refund_case_no, ctx.tenant_id, ctx.user_id, ctx.role, session),
        projection=_RefundCaseData,
        resource_type="refund_case",
        resource_id=input_model.refund_case_no,
        source_system="demo_refund_cases_db",
        success_summary="Refund case read succeeded",
        ctx=ctx,
        started_at=started_at,
    )


async def get_ticket_adapter(input_model: GetTicketInput, ctx: ToolCallContext, session: AsyncSession) -> ToolResultV2:
    started_at = perf_counter()
    return await _adapt_read(
        raw_call=get_ticket(input_model.ticket_id, ctx.tenant_id, ctx.user_id, ctx.role, session),
        projection=_TicketData,
        resource_type="ticket",
        resource_id=input_model.ticket_id,
        source_system="demo_tickets_db",
        success_summary="Ticket read succeeded",
        ctx=ctx,
        started_at=started_at,
    )
