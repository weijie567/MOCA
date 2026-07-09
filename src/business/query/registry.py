from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class BusinessQueryOperationDescriptor:
    id: str
    compatible_resource_ids: frozenset[str]
    metric_ids: frozenset[str] = frozenset()
    group_by_field_ids: frozenset[str] = frozenset()
    comparison_metric_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class BusinessQueryResourceDescriptor:
    id: str
    field_ids: frozenset[str]
    list_field_ids: frozenset[str]
    detail_field_ids: frozenset[str]
    prompt_field_ids: frozenset[str]
    ui_field_ids: frozenset[str]
    status_descriptor_id: str | None = None
    default_sort_id: str | None = None
    default_limit: int = 20
    max_limit: int = 100


@dataclass(frozen=True, slots=True)
class BusinessMetricDescriptor:
    id: str
    resource_id: str
    operation_id: str
    accepted_time_presets: frozenset[str]
    status_allowlist: frozenset[str]
    compatibility_resource_type: str
    default_time_preset: str | None = None
    default_status_filter: frozenset[str] = frozenset()
    requires_merchant_filter: bool = False
    parser_aliases: frozenset[str] = frozenset()
    unit: str = "count"


@dataclass(frozen=True, slots=True)
class BusinessQueryTimePresetDescriptor:
    id: str
    windowed: bool
    snapshot: bool
    parser_aliases: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class BusinessQueryFieldDescriptor:
    id: str
    resource_id: str
    safe_for_list: bool
    safe_for_detail: bool
    safe_for_prompt: bool
    safe_for_ui: bool
    contains_pii: bool = False


@dataclass(frozen=True, slots=True)
class BusinessQuerySortDescriptor:
    id: str
    resource_id: str
    field_id: str
    direction: str


@dataclass(frozen=True, slots=True)
class BusinessQueryStatusDescriptor:
    id: str
    resource_id: str
    values: frozenset[str]
    default_values: frozenset[str] = frozenset()


def _read_only_mapping[T](values: Mapping[str, T]) -> Mapping[str, T]:
    return MappingProxyType(dict(values))


class BusinessQueryRegistry:
    def __init__(
        self,
        *,
        operations: Mapping[str, BusinessQueryOperationDescriptor],
        resources: Mapping[str, BusinessQueryResourceDescriptor],
        metrics: Mapping[str, BusinessMetricDescriptor],
        time_presets: Mapping[str, BusinessQueryTimePresetDescriptor],
        fields: Mapping[str, BusinessQueryFieldDescriptor],
        sorts: Mapping[str, BusinessQuerySortDescriptor],
        statuses: Mapping[str, BusinessQueryStatusDescriptor],
    ) -> None:
        self._operations = _read_only_mapping(operations)
        self._resources = _read_only_mapping(resources)
        self._metrics = _read_only_mapping(metrics)
        self._time_presets = _read_only_mapping(time_presets)
        self._fields = _read_only_mapping(fields)
        self._sorts = _read_only_mapping(sorts)
        self._statuses = _read_only_mapping(statuses)
        self._metric_aliases = _read_only_mapping(
            {
                alias: metric.id
                for metric in self._metrics.values()
                for alias in metric.parser_aliases
            }
        )
        self._time_preset_aliases = _read_only_mapping(
            {
                alias: preset.id
                for preset in self._time_presets.values()
                for alias in preset.parser_aliases
            }
        )

    def operations(self) -> Mapping[str, BusinessQueryOperationDescriptor]:
        return self._operations

    def resources(self) -> Mapping[str, BusinessQueryResourceDescriptor]:
        return self._resources

    def metrics(self) -> Mapping[str, BusinessMetricDescriptor]:
        return self._metrics

    def time_presets(self) -> Mapping[str, BusinessQueryTimePresetDescriptor]:
        return self._time_presets

    def fields(self) -> Mapping[str, BusinessQueryFieldDescriptor]:
        return self._fields

    def sorts(self) -> Mapping[str, BusinessQuerySortDescriptor]:
        return self._sorts

    def statuses(self) -> Mapping[str, BusinessQueryStatusDescriptor]:
        return self._statuses

    def operation_ids(self) -> frozenset[str]:
        return frozenset(self._operations)

    def resource_ids(self) -> frozenset[str]:
        return frozenset(self._resources)

    def metric_ids(self) -> frozenset[str]:
        return frozenset(self._metrics)

    def time_preset_ids(self) -> frozenset[str]:
        return frozenset(self._time_presets)

    def window_time_preset_ids(self) -> frozenset[str]:
        return frozenset(preset.id for preset in self._time_presets.values() if preset.windowed)

    def snapshot_time_preset_ids(self) -> frozenset[str]:
        return frozenset(preset.id for preset in self._time_presets.values() if preset.snapshot)

    def event_or_rate_metric_ids(self) -> frozenset[str]:
        return frozenset(
            metric.id
            for metric in self._metrics.values()
            if not metric.default_time_preset and "current_snapshot" not in metric.accepted_time_presets
        )

    def metric_descriptor(self, metric_id: str) -> BusinessMetricDescriptor:
        return self._metrics[metric_id]

    def resource_descriptor(self, resource_id: str) -> BusinessQueryResourceDescriptor:
        return self._resources[resource_id]

    def status_descriptor(self, status_descriptor_id: str) -> BusinessQueryStatusDescriptor:
        return self._statuses[status_descriptor_id]

    def field_descriptor(self, resource_id: str, field_id: str) -> BusinessQueryFieldDescriptor:
        return self._fields[f"{resource_id}.{field_id}"]

    def metric_accepts_time_preset(self, metric_id: str, preset_id: str) -> bool:
        return preset_id in self.metric_descriptor(metric_id).accepted_time_presets

    def default_time_preset_for_metric(self, metric_id: str) -> str | None:
        return self.metric_descriptor(metric_id).default_time_preset

    def compatibility_resource_type(self, metric_id: str) -> str:
        return self.metric_descriptor(metric_id).compatibility_resource_type

    def status_filter_values_for_metric(self, metric_id: str) -> frozenset[str]:
        return self.metric_descriptor(metric_id).status_allowlist

    def default_status_filter_for_metric(self, metric_id: str) -> frozenset[str]:
        return self.metric_descriptor(metric_id).default_status_filter

    def metric_requires_merchant_filter(self, metric_id: str) -> bool:
        return self.metric_descriptor(metric_id).requires_merchant_filter

    def field_ids_for_resource(self, resource_id: str, *, purpose: str) -> frozenset[str]:
        resource = self.resource_descriptor(resource_id)
        if purpose == "list":
            return resource.list_field_ids
        if purpose == "detail":
            return resource.detail_field_ids
        if purpose == "prompt":
            return resource.prompt_field_ids
        if purpose == "ui":
            return resource.ui_field_ids
        raise KeyError(f"unknown business query field purpose: {purpose}")

    def metric_id_for_alias(self, alias: str) -> str | None:
        return self._metric_aliases.get(alias.strip())

    def time_preset_id_for_alias(self, alias: str) -> str | None:
        return self._time_preset_aliases.get(alias.strip())

    def metric_parser_aliases(self) -> Mapping[str, str]:
        return self._metric_aliases

    def time_preset_parser_aliases(self) -> Mapping[str, str]:
        return self._time_preset_aliases

    def all_descriptors(self) -> tuple[object, ...]:
        return (
            *self._operations.values(),
            *self._resources.values(),
            *self._metrics.values(),
            *self._time_presets.values(),
            *self._fields.values(),
            *self._sorts.values(),
            *self._statuses.values(),
        )


WINDOW_TIME_PRESETS = frozenset({"today", "this_week", "this_month", "this_quarter", "this_year"})

_OPERATIONS: Mapping[str, BusinessQueryOperationDescriptor] = {
    "aggregate": BusinessQueryOperationDescriptor(
        id="aggregate",
        compatible_resource_ids=frozenset({"order", "refund_case", "ticket", "coupon_record", "merchant_metric"}),
        metric_ids=frozenset(
            {
                "order_count",
                "refund_case_count",
                "pending_ticket_count",
                "coupon_record_count",
                "merchant_refund_rate",
            }
        ),
    ),
    "list": BusinessQueryOperationDescriptor(
        id="list",
        compatible_resource_ids=frozenset({"order", "refund_case", "ticket", "coupon_record"}),
    ),
    "detail": BusinessQueryOperationDescriptor(
        id="detail",
        compatible_resource_ids=frozenset({"order", "refund_case", "ticket", "coupon_record"}),
    ),
    "breakdown": BusinessQueryOperationDescriptor(
        id="breakdown",
        compatible_resource_ids=frozenset({"order"}),
        metric_ids=frozenset({"order_count"}),
        group_by_field_ids=frozenset({"order.status"}),
    ),
    "compare": BusinessQueryOperationDescriptor(
        id="compare",
        compatible_resource_ids=frozenset({"order"}),
        metric_ids=frozenset({"order_count"}),
        comparison_metric_ids=frozenset({"order_count"}),
    ),
}

_RESOURCES: Mapping[str, BusinessQueryResourceDescriptor] = {
    "order": BusinessQueryResourceDescriptor(
        id="order",
        field_ids=frozenset(
            {
                "order_no",
                "status",
                "amount",
                "currency",
                "item_name",
                "paid_at",
                "delivered_at",
                "created_at",
            }
        ),
        list_field_ids=frozenset({"order_no", "status", "amount", "currency", "paid_at"}),
        detail_field_ids=frozenset({"order_no", "status", "amount", "currency", "item_name", "paid_at", "delivered_at"}),
        prompt_field_ids=frozenset({"order_no", "status", "amount", "currency", "paid_at"}),
        ui_field_ids=frozenset({"order_no", "status", "amount", "currency", "paid_at", "delivered_at"}),
        status_descriptor_id="order_status",
        default_sort_id="order.created_at_desc",
    ),
    "refund_case": BusinessQueryResourceDescriptor(
        id="refund_case",
        field_ids=frozenset(
            {
                "refund_case_no",
                "status",
                "reason_code",
                "requested_amount",
                "approved_amount",
                "created_at",
            }
        ),
        list_field_ids=frozenset({"refund_case_no", "status", "reason_code", "requested_amount", "created_at"}),
        detail_field_ids=frozenset(
            {"refund_case_no", "status", "reason_code", "requested_amount", "approved_amount", "created_at"}
        ),
        prompt_field_ids=frozenset({"refund_case_no", "status", "reason_code", "requested_amount"}),
        ui_field_ids=frozenset({"refund_case_no", "status", "reason_code", "requested_amount", "approved_amount"}),
        status_descriptor_id="refund_case_status",
        default_sort_id="refund_case.created_at_desc",
    ),
    "ticket": BusinessQueryResourceDescriptor(
        id="ticket",
        field_ids=frozenset({"ticket_no", "status", "channel", "summary", "created_at"}),
        list_field_ids=frozenset({"ticket_no", "status", "channel", "summary", "created_at"}),
        detail_field_ids=frozenset({"ticket_no", "status", "channel", "summary", "created_at"}),
        prompt_field_ids=frozenset({"ticket_no", "status", "summary"}),
        ui_field_ids=frozenset({"ticket_no", "status", "channel", "summary", "created_at"}),
        status_descriptor_id="ticket_status",
        default_sort_id="ticket.created_at_desc",
    ),
    "coupon_record": BusinessQueryResourceDescriptor(
        id="coupon_record",
        field_ids=frozenset({"coupon_record_no", "status", "action_type", "created_at"}),
        list_field_ids=frozenset({"coupon_record_no", "status", "action_type", "created_at"}),
        detail_field_ids=frozenset({"coupon_record_no", "status", "action_type", "created_at"}),
        prompt_field_ids=frozenset({"coupon_record_no", "status", "action_type"}),
        ui_field_ids=frozenset({"coupon_record_no", "status", "action_type", "created_at"}),
        default_sort_id="coupon_record.created_at_desc",
    ),
    "merchant_metric": BusinessQueryResourceDescriptor(
        id="merchant_metric",
        field_ids=frozenset({"metric_id", "value", "rate", "display_value", "computed_at"}),
        list_field_ids=frozenset({"metric_id", "display_value", "computed_at"}),
        detail_field_ids=frozenset({"metric_id", "value", "rate", "display_value", "computed_at"}),
        prompt_field_ids=frozenset({"metric_id", "display_value", "computed_at"}),
        ui_field_ids=frozenset({"metric_id", "display_value", "computed_at"}),
        default_sort_id="merchant_metric.computed_at_desc",
    ),
}

_METRICS: Mapping[str, BusinessMetricDescriptor] = {
    "order_count": BusinessMetricDescriptor(
        id="order_count",
        resource_id="order",
        compatibility_resource_type="order",
        operation_id="aggregate",
        accepted_time_presets=WINDOW_TIME_PRESETS,
        status_allowlist=frozenset({"pending", "paid", "shipped", "delivered", "completed"}),
        parser_aliases=frozenset({"订单数", "多少订单", "订单量", "订单总数"}),
    ),
    "refund_case_count": BusinessMetricDescriptor(
        id="refund_case_count",
        resource_id="refund_case",
        compatibility_resource_type="refund_case",
        operation_id="aggregate",
        accepted_time_presets=WINDOW_TIME_PRESETS,
        status_allowlist=frozenset({"submitted", "reviewing", "approved", "rejected", "closed"}),
        parser_aliases=frozenset({"退款单", "退款单数", "多少退款", "退款数量"}),
    ),
    "pending_ticket_count": BusinessMetricDescriptor(
        id="pending_ticket_count",
        resource_id="ticket",
        compatibility_resource_type="ticket",
        operation_id="aggregate",
        accepted_time_presets=WINDOW_TIME_PRESETS | frozenset({"current_snapshot"}),
        status_allowlist=frozenset({"open", "in_progress"}),
        default_time_preset="current_snapshot",
        default_status_filter=frozenset({"open", "in_progress"}),
        parser_aliases=frozenset({"待处理工单", "当前待处理工单", "还有多少工单", "工单数"}),
    ),
    "coupon_record_count": BusinessMetricDescriptor(
        id="coupon_record_count",
        resource_id="coupon_record",
        compatibility_resource_type="action_draft",
        operation_id="aggregate",
        accepted_time_presets=WINDOW_TIME_PRESETS,
        status_allowlist=frozenset(),
        parser_aliases=frozenset({"补偿券", "优惠券", "券记录", "发了多少券"}),
    ),
    "merchant_refund_rate": BusinessMetricDescriptor(
        id="merchant_refund_rate",
        resource_id="merchant_metric",
        compatibility_resource_type="merchant_metric",
        operation_id="aggregate",
        accepted_time_presets=WINDOW_TIME_PRESETS,
        status_allowlist=frozenset(),
        requires_merchant_filter=True,
        parser_aliases=frozenset({"退款率", "商户退款率"}),
        unit="ratio",
    ),
}

_TIME_PRESETS: Mapping[str, BusinessQueryTimePresetDescriptor] = {
    "today": BusinessQueryTimePresetDescriptor(
        id="today",
        windowed=True,
        snapshot=False,
        parser_aliases=frozenset({"今天", "今日"}),
    ),
    "this_week": BusinessQueryTimePresetDescriptor(
        id="this_week",
        windowed=True,
        snapshot=False,
        parser_aliases=frozenset({"本周", "这周"}),
    ),
    "this_month": BusinessQueryTimePresetDescriptor(
        id="this_month",
        windowed=True,
        snapshot=False,
        parser_aliases=frozenset({"本月", "这个月"}),
    ),
    "this_quarter": BusinessQueryTimePresetDescriptor(
        id="this_quarter",
        windowed=True,
        snapshot=False,
        parser_aliases=frozenset({"本季度", "这个季度"}),
    ),
    "this_year": BusinessQueryTimePresetDescriptor(
        id="this_year",
        windowed=True,
        snapshot=False,
        parser_aliases=frozenset({"今年", "本年"}),
    ),
    "current_snapshot": BusinessQueryTimePresetDescriptor(
        id="current_snapshot",
        windowed=False,
        snapshot=True,
        parser_aliases=frozenset({"当前", "现在", "目前"}),
    ),
}


def _resource_fields(resource: BusinessQueryResourceDescriptor) -> dict[str, BusinessQueryFieldDescriptor]:
    return {
        f"{resource.id}.{field_id}": BusinessQueryFieldDescriptor(
            id=field_id,
            resource_id=resource.id,
            safe_for_list=field_id in resource.list_field_ids,
            safe_for_detail=field_id in resource.detail_field_ids,
            safe_for_prompt=field_id in resource.prompt_field_ids,
            safe_for_ui=field_id in resource.ui_field_ids,
        )
        for field_id in resource.field_ids
    }


_FIELDS: Mapping[str, BusinessQueryFieldDescriptor] = {
    field_key: descriptor
    for resource in _RESOURCES.values()
    for field_key, descriptor in _resource_fields(resource).items()
}

_SORTS: Mapping[str, BusinessQuerySortDescriptor] = {
    "order.created_at_desc": BusinessQuerySortDescriptor(
        id="order.created_at_desc",
        resource_id="order",
        field_id="created_at",
        direction="desc",
    ),
    "refund_case.created_at_desc": BusinessQuerySortDescriptor(
        id="refund_case.created_at_desc",
        resource_id="refund_case",
        field_id="created_at",
        direction="desc",
    ),
    "ticket.created_at_desc": BusinessQuerySortDescriptor(
        id="ticket.created_at_desc",
        resource_id="ticket",
        field_id="created_at",
        direction="desc",
    ),
    "coupon_record.created_at_desc": BusinessQuerySortDescriptor(
        id="coupon_record.created_at_desc",
        resource_id="coupon_record",
        field_id="created_at",
        direction="desc",
    ),
    "merchant_metric.computed_at_desc": BusinessQuerySortDescriptor(
        id="merchant_metric.computed_at_desc",
        resource_id="merchant_metric",
        field_id="computed_at",
        direction="desc",
    ),
}

_STATUSES: Mapping[str, BusinessQueryStatusDescriptor] = {
    "order_status": BusinessQueryStatusDescriptor(
        id="order_status",
        resource_id="order",
        values=frozenset({"pending", "paid", "shipped", "delivered", "completed"}),
    ),
    "refund_case_status": BusinessQueryStatusDescriptor(
        id="refund_case_status",
        resource_id="refund_case",
        values=frozenset({"submitted", "reviewing", "approved", "rejected", "closed"}),
    ),
    "ticket_status": BusinessQueryStatusDescriptor(
        id="ticket_status",
        resource_id="ticket",
        values=frozenset({"open", "in_progress", "resolved", "closed"}),
        default_values=frozenset({"open", "in_progress"}),
    ),
}

BUSINESS_QUERY_REGISTRY = BusinessQueryRegistry(
    operations=_OPERATIONS,
    resources=_RESOURCES,
    metrics=_METRICS,
    time_presets=_TIME_PRESETS,
    fields=_FIELDS,
    sorts=_SORTS,
    statuses=_STATUSES,
)


__all__ = [
    "BUSINESS_QUERY_REGISTRY",
    "BusinessMetricDescriptor",
    "BusinessQueryFieldDescriptor",
    "BusinessQueryOperationDescriptor",
    "BusinessQueryRegistry",
    "BusinessQueryResourceDescriptor",
    "BusinessQuerySortDescriptor",
    "BusinessQueryStatusDescriptor",
    "BusinessQueryTimePresetDescriptor",
]
