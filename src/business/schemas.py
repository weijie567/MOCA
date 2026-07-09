"""Compatibility exports for unified tool contracts and business context."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from src.tools.contracts import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolError,
    ToolRequest,
    ToolResult,
    ToolResultV2,
)

from src.business.query.schemas import (
    BusinessQueryAnswerContext,
    BusinessQueryCursor,
    BusinessQueryFilterSet,
    BusinessQueryResultCursor,
    BusinessQueryResultV1,
    BusinessQueryScopeSummary,
    BusinessQuerySort,
    BusinessQuerySpec,
    metric_input_to_business_query,
)


class BusinessFactResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_result.v1"] = "business_fact_result.v1"
    tenant_id: str
    status: Literal[
        "ok",
        "partial",
        "not_found",
        "permission_denied",
        "stale",
        "unavailable",
        "invalid_request",
    ]
    fact: dict[str, Any] | None
    business_fact_refs: list[BusinessFactRefV1]
    resource_version: str | None = None
    data_freshness_at: datetime | None = None
    source_system: str
    scope_check_result: Literal["allowed", "denied", "not_applicable", "unknown"]
    missing_required_facts: list[str]
    safe_errors: list[ToolError]


BusinessMetricId = Literal[
    "order_count",
    "refund_case_count",
    "pending_ticket_count",
    "coupon_record_count",
    "merchant_refund_rate",
]
BusinessMetricStatus = Literal["ok", "permission_denied", "invalid_request", "non_computable"]
BusinessMetricTimePreset = Literal["today", "this_week", "this_month", "this_quarter", "this_year", "current_snapshot"]


class BusinessMetricQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: BusinessMetricId
    time_preset: BusinessMetricTimePreset | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    merchant_id: str | None = None
    status_filter: list[str] = Field(default_factory=list)

    @field_validator("merchant_id")
    @classmethod
    def _reject_wildcard_merchant_filter(cls, value: str | None) -> str | None:
        if value == "*":
            raise ValueError("merchant_id wildcard is not allowed in metric tool args")
        return value

    @field_validator("status_filter")
    @classmethod
    def _validate_status_filter(cls, value: list[str]) -> list[str]:
        if not all(isinstance(item, str) and item for item in value):
            raise ValueError("status_filter values must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _validate_time_range_order(self) -> "BusinessMetricQueryInput":
        if self.start_at is not None and self.end_at is not None and self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")
        return self


class BusinessMetricScopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    merchant_ids: list[str]
    scope_label: str


class BusinessMetricTimeRangeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None
    end_at: datetime | None
    preset: str | None
    timezone: str


class BusinessMetricFiltersV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str | None
    status_filter: list[str] = Field(default_factory=list)


class BusinessMetricFreshnessV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_freshness_at: datetime | None
    computed_at: datetime
    source_system: str

    @field_serializer("computed_at", "data_freshness_at", when_used="json")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None


class BusinessMetricResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: BusinessMetricId
    status: BusinessMetricStatus
    value: float | None
    rate: float | None
    numerator: int | None
    denominator: int | None
    unit: str
    display_value: str
    scope: BusinessMetricScopeV1
    time_range: BusinessMetricTimeRangeV1
    filters: BusinessMetricFiltersV1
    freshness: BusinessMetricFreshnessV1
    formula: str
    caveats: list[str] = Field(default_factory=list)
    no_leak_status: Literal["not_applicable", "scope_denied_no_existence_leak"]

    @model_validator(mode="after")
    def _validate_non_computable_shape(self) -> "BusinessMetricResultV1":
        if self.status == "non_computable" and (self.value is not None or self.rate is not None):
            raise ValueError("non-computable metric must not carry value or rate")
        return self


class BusinessContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_context.v1"] = "business_context.v1"
    tenant_id: str
    status: Literal["complete", "partial", "insufficient", "error"]
    facts: dict[str, Any]
    business_fact_refs: list[BusinessFactRefV1]
    tool_results: list[ToolResultV2]
    missing_required_facts: list[str]
    errors: list[ToolError]
    data_freshness_at: datetime | None


__all__ = [
    "BusinessContextV1",
    "BusinessFactRefV1",
    "BusinessFactResultV1",
    "BusinessMetricFiltersV1",
    "BusinessMetricFreshnessV1",
    "BusinessMetricQueryInput",
    "BusinessMetricResultV1",
    "BusinessMetricScopeV1",
    "BusinessMetricTimeRangeV1",
    "BusinessQueryAnswerContext",
    "BusinessQueryCursor",
    "BusinessQueryFilterSet",
    "BusinessQueryResultCursor",
    "BusinessQueryResultV1",
    "BusinessQueryScopeSummary",
    "BusinessQuerySort",
    "BusinessQuerySpec",
    "ToolCallContext",
    "ToolError",
    "ToolRequest",
    "ToolResult",
    "ToolResultV2",
    "metric_input_to_business_query",
]
