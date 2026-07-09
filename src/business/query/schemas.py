from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.business.query.registry import BUSINESS_QUERY_REGISTRY

if TYPE_CHECKING:
    from src.business.schemas import BusinessMetricQueryInput


BusinessQueryStatus = Literal["ok", "partial", "empty", "permission_denied", "invalid_request", "unavailable"]
BusinessQueryCompareTo = Literal["previous_period"]


class BusinessQueryFilterSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_filter: list[str] = Field(default_factory=list)

    @field_validator("status_filter")
    @classmethod
    def _validate_status_filter(cls, value: list[str]) -> list[str]:
        if not all(isinstance(item, str) and item for item in value):
            raise ValueError("status_filter values must be non-empty strings")
        return value


class BusinessQuerySort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    direction: Literal["asc", "desc"]


class BusinessQueryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor_id: str = Field(min_length=1, max_length=128)
    direction: Literal["next", "previous"] = "next"


class BusinessQueryScopeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_label: str
    merchant_id: str | None = None
    no_leak_status: Literal["not_applicable", "scope_denied_no_existence_leak"] = "not_applicable"

    @field_validator("merchant_id")
    @classmethod
    def _reject_wildcard_merchant_filter(cls, value: str | None) -> str | None:
        if value == "*":
            raise ValueError("merchant_id wildcard is not allowed in business query scope summaries")
        return value


class BusinessQuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    resource: str
    metric_id: str | None = None
    time_preset: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    merchant_id: str | None = None
    resource_id: str | None = None
    filters: BusinessQueryFilterSet = Field(default_factory=BusinessQueryFilterSet)
    fields: list[str] = Field(default_factory=list)
    group_by: str | None = None
    compare_to: BusinessQueryCompareTo | None = None
    sort: BusinessQuerySort | None = None
    limit: int = Field(default=20, ge=1)
    cursor: BusinessQueryCursor | None = None

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, value: str) -> str:
        if value not in BUSINESS_QUERY_REGISTRY.operation_ids():
            raise ValueError("unsupported business query operation")
        return value

    @field_validator("resource")
    @classmethod
    def _validate_resource(cls, value: str) -> str:
        if value not in BUSINESS_QUERY_REGISTRY.resource_ids():
            raise ValueError("unsupported business query resource")
        return value

    @field_validator("metric_id")
    @classmethod
    def _validate_metric_id(cls, value: str | None) -> str | None:
        if value is not None and value not in BUSINESS_QUERY_REGISTRY.metric_ids():
            raise ValueError("unsupported business query metric")
        return value

    @field_validator("time_preset")
    @classmethod
    def _validate_time_preset(cls, value: str | None) -> str | None:
        if value is not None and value not in BUSINESS_QUERY_REGISTRY.time_preset_ids():
            raise ValueError("unsupported business query time preset")
        return value

    @field_validator("merchant_id")
    @classmethod
    def _reject_wildcard_merchant_filter(cls, value: str | None) -> str | None:
        if value == "*":
            raise ValueError("merchant_id wildcard is not allowed in business query tool args")
        return value

    @field_validator("fields")
    @classmethod
    def _validate_fields_shape(cls, value: list[str]) -> list[str]:
        if not all(isinstance(item, str) and item for item in value):
            raise ValueError("fields must be non-empty strings")
        if len(value) != len(set(value)):
            raise ValueError("fields must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _validate_against_registry(self) -> BusinessQuerySpec:
        registry = BUSINESS_QUERY_REGISTRY
        operation = registry.operations()[self.operation]
        resource = registry.resource_descriptor(self.resource)

        if self.resource not in operation.compatible_resource_ids:
            raise ValueError("resource is not compatible with operation")

        if operation.metric_ids:
            if self.metric_id is None:
                raise ValueError("metric_id is required for this business query operation")
            if self.metric_id not in operation.metric_ids:
                raise ValueError("metric_id is not compatible with operation")
            metric = registry.metric_descriptor(self.metric_id)
            if metric.resource_id != self.resource:
                raise ValueError("metric_id is not compatible with resource")
        elif self.metric_id is not None:
            raise ValueError("metric_id is not allowed for this business query operation")

        if self.operation != "detail" and self.resource_id is not None:
            raise ValueError("resource_id is only allowed for detail business queries")

        self._validate_time_compatibility()
        self._validate_status_filters(resource.status_descriptor_id)
        self._validate_fields()
        self._validate_group_by(operation.group_by_field_ids)
        self._validate_compare_to()
        self._validate_sort()
        self._validate_limit(resource.max_limit)
        return self

    def _validate_time_compatibility(self) -> None:
        if (self.start_at is None) != (self.end_at is None):
            raise ValueError("start_at and end_at must be provided together")
        if self.start_at is not None and self.end_at is not None and self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")
        if self.time_preset is not None and (self.start_at is not None or self.end_at is not None):
            raise ValueError("time_preset cannot be combined with explicit start_at/end_at")

        if self.metric_id is None:
            return

        metric = BUSINESS_QUERY_REGISTRY.metric_descriptor(self.metric_id)
        if self.time_preset is None and self.start_at is None and metric.default_time_preset is None:
            raise ValueError("metric business queries require time_preset or explicit start_at/end_at")
        if self.time_preset is not None and self.time_preset not in metric.accepted_time_presets:
            raise ValueError("time_preset is not compatible with metric descriptor")

    def _validate_status_filters(self, status_descriptor_id: str | None) -> None:
        values = self.filters.status_filter
        if not values:
            return

        if self.metric_id is not None:
            allowed = BUSINESS_QUERY_REGISTRY.metric_descriptor(self.metric_id).status_allowlist
        elif status_descriptor_id is not None:
            allowed = BUSINESS_QUERY_REGISTRY.status_descriptor(status_descriptor_id).values
        else:
            allowed = frozenset()

        if not allowed or any(value not in allowed for value in values):
            raise ValueError("status_filter contains values not allowed by descriptor")

    def _validate_fields(self) -> None:
        if not self.fields:
            return

        purpose = "detail" if self.operation == "detail" else "list" if self.operation == "list" else "prompt"
        allowed = BUSINESS_QUERY_REGISTRY.field_ids_for_resource(self.resource, purpose=purpose)
        if any(field_id not in allowed for field_id in self.fields):
            raise ValueError("fields contain values not allowed by descriptor")

    def _validate_group_by(self, group_by_field_ids: frozenset[str]) -> None:
        if group_by_field_ids:
            if self.group_by is None:
                raise ValueError("group_by is required for this business query operation")
            if f"{self.resource}.{self.group_by}" not in group_by_field_ids:
                raise ValueError("group_by is not allowed by operation descriptor")
            return
        if self.group_by is not None:
            raise ValueError("group_by is not allowed for this business query operation")

    def _validate_compare_to(self) -> None:
        if self.operation == "compare":
            if self.compare_to != "previous_period":
                raise ValueError("compare_to must be previous_period for Phase 62 compare")
            return
        if self.compare_to is not None:
            raise ValueError("compare_to is only allowed for compare business queries")

    def _validate_sort(self) -> None:
        if self.sort is None:
            return
        sort_matches = any(
            sort.resource_id == self.resource
            and sort.field_id == self.sort.field
            and sort.direction == self.sort.direction
            for sort in BUSINESS_QUERY_REGISTRY.sorts().values()
        )
        if not sort_matches:
            raise ValueError("sort is not allowed by descriptor")

    def _validate_limit(self, max_limit: int) -> None:
        if self.limit > max_limit:
            raise ValueError("limit exceeds descriptor maximum")


class BusinessQueryResultCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_query_result_cursor.v1"] = "business_query_result_cursor.v1"
    cursor_id: str = Field(min_length=1, max_length=128)
    has_more: bool
    limit: int = Field(ge=1)
    next_cursor: BusinessQueryCursor | None = None


class BusinessQueryAnswerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_query_answer_context.v1"] = "business_query_answer_context.v1"
    query_spec: BusinessQuerySpec
    result_refs: list[str] = Field(default_factory=list)
    allowed_drilldowns: list[str] = Field(default_factory=list)
    fields_shown: list[str] = Field(default_factory=list)
    cursor: BusinessQueryResultCursor | None = None
    scope: BusinessQueryScopeSummary | None = None
    time_summary: str | None = None
    filter_summary: str | None = None


class BusinessQueryResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_query_result.v1"] = "business_query_result.v1"
    operation: str
    resource: str
    status: BusinessQueryStatus
    rows: list[dict[str, Any]] = Field(default_factory=list)
    answer_context: BusinessQueryAnswerContext | None = None
    cursor: BusinessQueryResultCursor | None = None
    scope: BusinessQueryScopeSummary | None = None

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, value: str) -> str:
        if value not in BUSINESS_QUERY_REGISTRY.operation_ids():
            raise ValueError("unsupported business query result operation")
        return value

    @field_validator("resource")
    @classmethod
    def _validate_resource(cls, value: str) -> str:
        if value not in BUSINESS_QUERY_REGISTRY.resource_ids():
            raise ValueError("unsupported business query result resource")
        return value


def metric_input_to_business_query(metric_input: BusinessMetricQueryInput) -> BusinessQuerySpec:
    metric_id = str(metric_input.metric_id)
    metric = BUSINESS_QUERY_REGISTRY.metric_descriptor(metric_id)
    time_preset = metric_input.time_preset or metric.default_time_preset
    status_filter = list(metric_input.status_filter or metric.default_status_filter)
    payload: dict[str, Any] = {
        "operation": "aggregate",
        "resource": metric.resource_id,
        "metric_id": metric_id,
        "time_preset": time_preset,
        "start_at": metric_input.start_at,
        "end_at": metric_input.end_at,
        "merchant_id": metric_input.merchant_id,
        "filters": {"status_filter": status_filter},
    }
    return BusinessQuerySpec.model_validate(payload)


__all__ = [
    "BusinessQueryAnswerContext",
    "BusinessQueryCursor",
    "BusinessQueryFilterSet",
    "BusinessQueryResultCursor",
    "BusinessQueryResultV1",
    "BusinessQueryScopeSummary",
    "BusinessQuerySort",
    "BusinessQuerySpec",
    "metric_input_to_business_query",
]
