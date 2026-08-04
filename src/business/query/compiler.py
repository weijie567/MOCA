from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, distinct, func, or_, select

from src.business.query.registry import BUSINESS_QUERY_REGISTRY, BusinessQueryRegistry
from src.business.query.schemas import BusinessQueryCursor, BusinessQuerySpec
from src.db.models import ActionDraft, Order, RefundCase, Ticket

BUSINESS_QUERY_TIMEZONE_NAME = "Asia/Shanghai"
ORDER_CURSOR_PREFIX = "order.created_at_desc"


class BusinessQueryCompileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BusinessQueryTimeWindow:
    start_at: datetime | None
    end_at: datetime | None
    preset: str | None
    timezone: str = BUSINESS_QUERY_TIMEZONE_NAME


@dataclass(frozen=True, slots=True)
class BusinessQueryCursorState:
    created_at: datetime
    order_no: str


@dataclass(frozen=True, slots=True)
class CompiledBusinessQuery:
    spec: BusinessQuerySpec
    tenant_id: UUID
    merchant_ids: tuple[str, ...]
    merchant_uuid_ids: tuple[UUID, ...] | None
    time_window: BusinessQueryTimeWindow
    previous_time_window: BusinessQueryTimeWindow | None
    status_filter: tuple[str, ...]
    fields: tuple[str, ...]
    limit: int
    cursor_state: BusinessQueryCursorState | None
    statements: dict[str, Select[Any]]


class BusinessQueryCompiler:
    def __init__(self, registry: BusinessQueryRegistry = BUSINESS_QUERY_REGISTRY) -> None:
        self.registry = registry

    def compile(
        self,
        spec: BusinessQuerySpec,
        *,
        tenant_id: str,
        authorized_merchant_ids: list[str],
        effective_at: datetime,
    ) -> CompiledBusinessQuery:
        tenant_uuid = self._uuid_or_raise(tenant_id)
        merchant_uuid_ids = self._merchant_uuid_ids(authorized_merchant_ids)
        time_window = self._time_window(spec, effective_at)
        previous_time_window = self._previous_time_window(spec, time_window)
        status_filter = self._status_filter(spec)
        fields = self._fields(spec)
        cursor_state = self._cursor_state(spec.cursor)

        statements = self._statements(
            spec=spec,
            tenant_id=tenant_uuid,
            merchant_uuid_ids=merchant_uuid_ids,
            merchant_ids=authorized_merchant_ids,
            time_window=time_window,
            previous_time_window=previous_time_window,
            status_filter=status_filter,
            fields=fields,
            cursor_state=cursor_state,
        )
        return CompiledBusinessQuery(
            spec=spec,
            tenant_id=tenant_uuid,
            merchant_ids=tuple(authorized_merchant_ids),
            merchant_uuid_ids=None if merchant_uuid_ids is None else tuple(merchant_uuid_ids),
            time_window=time_window,
            previous_time_window=previous_time_window,
            status_filter=tuple(status_filter),
            fields=tuple(fields),
            limit=spec.limit,
            cursor_state=cursor_state,
            statements=statements,
        )

    def _statements(
        self,
        *,
        spec: BusinessQuerySpec,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        merchant_ids: list[str],
        time_window: BusinessQueryTimeWindow,
        previous_time_window: BusinessQueryTimeWindow | None,
        status_filter: list[str],
        fields: tuple[str, ...],
        cursor_state: BusinessQueryCursorState | None,
    ) -> dict[str, Select[Any]]:
        if spec.operation == "aggregate":
            return self._aggregate_statements(
                spec, tenant_id, merchant_uuid_ids, merchant_ids, time_window, status_filter
            )
        if spec.operation == "list" and spec.resource == "order":
            return {
                "rows": self._order_list_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                    fields=fields,
                    limit=spec.limit,
                    cursor_state=cursor_state,
                )
            }
        if spec.operation == "detail" and spec.resource == "order":
            return {
                "row": self._order_detail_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    resource_id=spec.resource_id,
                    fields=fields,
                )
            }
        if spec.operation == "breakdown" and spec.resource == "order" and spec.metric_id == "order_count":
            return {
                "rows": self._order_breakdown_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                )
            }
        if spec.operation == "compare" and spec.resource == "order" and spec.metric_id == "order_count":
            if previous_time_window is None:
                raise BusinessQueryCompileError("compare requires a bounded time window")
            return {
                "current": self._order_count_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                ),
                "previous": self._order_count_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=previous_time_window,
                    status_filter=status_filter,
                ),
            }
        raise BusinessQueryCompileError("business query operation/resource is not runtime-enabled")

    def _aggregate_statements(
        self,
        spec: BusinessQuerySpec,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        merchant_ids: list[str],
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> dict[str, Select[Any]]:
        if spec.metric_id == "order_count":
            return {
                "value": self._order_count_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                )
            }
        if spec.metric_id == "refund_case_count":
            return {
                "value": self._refund_case_count_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                )
            }
        if spec.metric_id == "pending_ticket_count":
            return {
                "value": self._ticket_count_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                    status_filter=status_filter,
                )
            }
        if spec.metric_id == "coupon_record_count":
            return {
                "value": self._coupon_record_count_statement(
                    tenant_id=tenant_id,
                    merchant_ids=merchant_ids,
                    time_window=time_window,
                )
            }
        if spec.metric_id == "merchant_refund_rate":
            return {
                "numerator": self._refund_rate_numerator_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                ),
                "denominator": self._refund_rate_denominator_statement(
                    tenant_id=tenant_id,
                    merchant_uuid_ids=merchant_uuid_ids,
                    time_window=time_window,
                ),
            }
        raise BusinessQueryCompileError("unsupported aggregate metric")

    def _order_count_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> Select[Any]:
        conditions = self._order_conditions(tenant_id, merchant_uuid_ids, time_window, status_filter)
        return select(func.count(Order.id)).where(*conditions)

    def _refund_case_count_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> Select[Any]:
        conditions = [
            RefundCase.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            RefundCase.order_id == Order.id,
        ]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        conditions.extend(self._time_conditions(RefundCase.created_at, time_window))
        if status_filter:
            conditions.append(RefundCase.status.in_(status_filter))
        return select(func.count(RefundCase.id)).select_from(RefundCase, Order).where(*conditions)

    def _ticket_count_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> Select[Any]:
        conditions = [
            Ticket.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            Ticket.order_id == Order.id,
        ]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        conditions.extend(self._time_conditions(Ticket.created_at, time_window))
        if status_filter:
            conditions.append(Ticket.status.in_(status_filter))
        return select(func.count(Ticket.id)).select_from(Ticket, Order).where(*conditions)

    def _coupon_record_count_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_ids: list[str],
        time_window: BusinessQueryTimeWindow,
    ) -> Select[Any]:
        conditions = [ActionDraft.tenant_id == tenant_id, ActionDraft.action_type == "issue_coupon"]
        if "*" not in merchant_ids:
            conditions.append(ActionDraft.target_merchant_id.in_(merchant_ids))
        conditions.extend(self._time_conditions(ActionDraft.created_at, time_window))
        return select(func.count(ActionDraft.id)).where(*conditions)

    def _refund_rate_denominator_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
    ) -> Select[Any]:
        conditions = self._order_conditions(tenant_id, merchant_uuid_ids, time_window, [])
        return select(func.count(distinct(Order.id))).where(*conditions)

    def _refund_rate_numerator_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
    ) -> Select[Any]:
        conditions = [
            RefundCase.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            RefundCase.order_id == Order.id,
            *self._order_conditions(tenant_id, merchant_uuid_ids, time_window, []),
        ]
        return select(func.count(distinct(RefundCase.order_id))).select_from(RefundCase, Order).where(*conditions)

    def _order_list_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
        fields: tuple[str, ...],
        limit: int,
        cursor_state: BusinessQueryCursorState | None,
    ) -> Select[Any]:
        conditions = self._order_conditions(tenant_id, merchant_uuid_ids, time_window, status_filter)
        if cursor_state is not None:
            conditions.append(
                or_(
                    Order.created_at < cursor_state.created_at,
                    and_(Order.created_at == cursor_state.created_at, Order.order_no < cursor_state.order_no),
                )
            )
        selected_fields = fields if "created_at" in fields else (*fields, "created_at")
        return (
            select(*self._order_columns(selected_fields))
            .where(*conditions)
            .order_by(Order.created_at.desc(), Order.order_no.desc())
            .limit(limit + 1)
        )

    def _order_detail_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        resource_id: str | None,
        fields: tuple[str, ...],
    ) -> Select[Any]:
        if not resource_id:
            raise BusinessQueryCompileError("detail requires resource_id")
        conditions = self._order_conditions(tenant_id, merchant_uuid_ids, BusinessQueryTimeWindow(None, None, None), [])
        order_uuid = self._uuid_or_none(resource_id)
        if order_uuid is None:
            conditions.append(Order.order_no == resource_id)
        else:
            conditions.append(Order.id == order_uuid)
        return select(*self._order_columns(fields)).where(*conditions).limit(1)

    def _order_breakdown_statement(
        self,
        *,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> Select[Any]:
        conditions = self._order_conditions(tenant_id, merchant_uuid_ids, time_window, status_filter)
        return (
            select(Order.status.label("status"), func.count(Order.id).label("value"))
            .where(*conditions)
            .group_by(Order.status)
        )

    def _order_conditions(
        self,
        tenant_id: UUID,
        merchant_uuid_ids: list[UUID] | None,
        time_window: BusinessQueryTimeWindow,
        status_filter: list[str],
    ) -> list[Any]:
        conditions: list[Any] = [Order.tenant_id == tenant_id]
        if merchant_uuid_ids is not None:
            conditions.append(Order.merchant_id.in_(merchant_uuid_ids))
        conditions.extend(self._time_conditions(Order.created_at, time_window))
        if status_filter:
            conditions.append(Order.status.in_(status_filter))
        return conditions

    @staticmethod
    def _time_conditions(column: Any, time_window: BusinessQueryTimeWindow) -> list[Any]:
        conditions = []
        if time_window.start_at is not None:
            conditions.append(column >= time_window.start_at)
        if time_window.end_at is not None:
            conditions.append(column < time_window.end_at)
        return conditions

    def _fields(self, spec: BusinessQuerySpec) -> tuple[str, ...]:
        if spec.fields:
            return tuple(spec.fields)
        if spec.operation == "detail":
            return tuple(self.registry.field_ids_for_resource(spec.resource, purpose="detail"))
        if spec.operation == "list":
            return tuple(self.registry.field_ids_for_resource(spec.resource, purpose="list"))
        return ()

    @staticmethod
    def _order_columns(fields: tuple[str, ...]) -> list[Any]:
        column_map = {
            "order_no": Order.order_no,
            "status": Order.status,
            "amount": Order.amount,
            "currency": Order.currency,
            "item_name": Order.item_name,
            "paid_at": Order.paid_at,
            "delivered_at": Order.delivered_at,
            "created_at": Order.created_at,
        }
        columns = []
        for field_id in fields:
            column = column_map.get(field_id)
            if column is None:
                raise BusinessQueryCompileError("unsupported order field")
            columns.append(column.label(field_id))
        return columns

    def _status_filter(self, spec: BusinessQuerySpec) -> list[str]:
        if spec.filters.status_filter:
            return list(spec.filters.status_filter)
        if spec.metric_id is not None:
            return list(self.registry.default_status_filter_for_metric(spec.metric_id))
        resource = self.registry.resource_descriptor(spec.resource)
        if resource.status_descriptor_id is None:
            return []
        return list(self.registry.status_descriptor(resource.status_descriptor_id).default_values)

    def _time_window(self, spec: BusinessQuerySpec, effective_at: datetime) -> BusinessQueryTimeWindow:
        if spec.start_at is not None and spec.end_at is not None:
            return BusinessQueryTimeWindow(self._to_utc(spec.start_at), self._to_utc(spec.end_at), spec.time_preset)
        if spec.time_preset in {None, "current_snapshot"}:
            return BusinessQueryTimeWindow(None, None, spec.time_preset)
        start = self._preset_start_at(spec.time_preset, effective_at)
        if start is None:
            raise BusinessQueryCompileError("unsupported time preset")
        return BusinessQueryTimeWindow(start.astimezone(UTC), effective_at.astimezone(UTC), spec.time_preset)

    @staticmethod
    def _previous_time_window(
        spec: BusinessQuerySpec,
        time_window: BusinessQueryTimeWindow,
    ) -> BusinessQueryTimeWindow | None:
        if spec.operation != "compare":
            return None
        if time_window.start_at is None or time_window.end_at is None:
            raise BusinessQueryCompileError("compare requires a bounded time window")
        duration = time_window.end_at - time_window.start_at
        previous_end = time_window.start_at
        previous_start = previous_end - duration
        return BusinessQueryTimeWindow(previous_start, previous_end, time_window.preset)

    @staticmethod
    def _cursor_state(cursor: BusinessQueryCursor | None) -> BusinessQueryCursorState | None:
        if cursor is None:
            return None
        if cursor.direction != "next":
            raise BusinessQueryCompileError("only next cursors are supported")
        parts = cursor.cursor_id.split("|", 2)
        if len(parts) != 3 or parts[0] != ORDER_CURSOR_PREFIX:
            raise BusinessQueryCompileError("invalid cursor")
        try:
            created_at = datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
        except ValueError as exc:
            raise BusinessQueryCompileError("invalid cursor") from exc
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        order_no = parts[2]
        if not order_no:
            raise BusinessQueryCompileError("invalid cursor")
        return BusinessQueryCursorState(created_at=created_at.astimezone(UTC), order_no=order_no)

    @staticmethod
    def encode_order_cursor(*, created_at: datetime, order_no: str) -> str:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return f"{ORDER_CURSOR_PREFIX}|{created_at.astimezone(UTC).isoformat()}|{order_no}"

    @staticmethod
    def _uuid_or_raise(value: str) -> UUID:
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise BusinessQueryCompileError("invalid uuid") from exc

    @staticmethod
    def _uuid_or_none(value: str) -> UUID | None:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _merchant_uuid_ids(self, merchant_ids: list[str]) -> list[UUID] | None:
        if "*" in merchant_ids:
            return None
        return [self._uuid_or_raise(merchant_id) for merchant_id in merchant_ids]

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _preset_start_at(preset: str | None, effective_at: datetime) -> datetime | None:
        local = effective_at
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


__all__ = [
    "BusinessQueryCompileError",
    "BusinessQueryCompiler",
    "BusinessQueryCursorState",
    "BusinessQueryTimeWindow",
    "CompiledBusinessQuery",
]
