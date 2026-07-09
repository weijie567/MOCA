from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.query.compiler import BusinessQueryCompiler
from src.business.query.projection import safe_business_query_api_payload
from src.business.query.schemas import BusinessQuerySpec
from src.business.service import BusinessFactService, BusinessToolService
from src.db.models import Order
from src.tools.contracts import ToolCallContext


def _ctx(seeded_session: dict, user_key: str = "cs_zhang", **updates: object) -> ToolCallContext:
    user = seeded_session["users"][user_key]
    tenant = seeded_session["tenant"]
    if user.role == "admin":
        merchant_scope = {"merchant_ids": ["*"]}
    elif user.merchant_id is None:
        merchant_scope = {"merchant_ids": []}
    else:
        merchant_scope = {"merchant_ids": [str(user.merchant_id)]}
    values: dict[str, object] = {
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "role": user.role,
        "permissions": ["tool:business_query", "tool:query_business_metric"],
        "merchant_scope": merchant_scope,
        "thread_id": "thread-business-query",
        "run_id": "run-business-query",
        "trace_id": "trace-business-query",
        "request_id": "request-business-query",
        "tool_call_id": "tool-call-business-query",
        "caller_node": "investigate",
        "effective_at": "2026-07-09T12:00:00+08:00",
    }
    values.update(updates)
    return ToolCallContext.model_validate(values)


def _business_query_fact(result) -> dict:
    assert result.status == "ok"
    assert result.fact is not None
    assert set(result.fact) == {"business_query"}
    payload = result.fact["business_query"]
    assert payload["schema_version"] == "business_query_result.v1"
    assert result.business_fact_refs
    assert result.business_fact_refs[0].resource_type == "business_query"
    return payload


async def _add_order(
    session: AsyncSession,
    seeded_session: dict,
    *,
    merchant_key: str = "merchant",
    order_no: str,
    status: str = "paid",
    created_at: datetime,
    amount: Decimal = Decimal("88.00"),
) -> Order:
    order = Order(
        id=uuid4(),
        tenant_id=seeded_session["tenant"].id,
        merchant_id=seeded_session[merchant_key].id,
        order_no=order_no,
        buyer_name="Sensitive Buyer",
        item_name="Safe Item",
        amount=amount,
        currency="CNY",
        status=status,
        created_at=created_at,
        updated_at=created_at,
        paid_at=created_at,
    )
    session.add(order)
    await session.flush()
    return order


@pytest.mark.asyncio
async def test_business_query_aggregate_order_count_matches_metric_semantics(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)

    result = await service.query_business(
        {
            "operation": "aggregate",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
        },
        _ctx(seeded_session),
    )

    payload = _business_query_fact(result)
    assert payload["operation"] == "aggregate"
    assert payload["resource"] == "order"
    assert payload["status"] == "ok"
    row = payload["rows"][0]
    assert row["metric_id"] == "order_count"
    assert row["value"] == 1
    assert row["display_value"] == "1"
    assert row["time_range"]["start_at"] == "2026-07-05T16:00:00Z"
    assert row["time_range"]["end_at"] == "2026-07-09T04:00:00Z"
    assert payload["scope"]["scope_label"] == "authorized_merchants"


@pytest.mark.asyncio
async def test_business_query_list_orders_applies_scope_before_limit_and_returns_cursor(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    in_scope = seeded_session["merchant"]
    out_of_scope = seeded_session["second_merchant"]
    newer = datetime(2026, 7, 9, 2, 0, tzinfo=UTC)
    await _add_order(
        session,
        seeded_session,
        merchant_key="second_merchant",
        order_no="ORD-BQ-OUT-OF-SCOPE-NEWER",
        created_at=newer,
    )
    await _add_order(session, seeded_session, order_no="ORD-BQ-IN-SCOPE-1", created_at=newer - timedelta(minutes=1))
    await _add_order(session, seeded_session, order_no="ORD-BQ-IN-SCOPE-2", created_at=newer - timedelta(minutes=2))

    result = await service.query_business(
        {
            "operation": "list",
            "resource": "order",
            "time_preset": "this_week",
            "fields": ["order_no", "status", "amount", "currency", "paid_at"],
            "limit": 1,
        },
        _ctx(seeded_session, merchant_scope={"merchant_ids": [str(in_scope.id)]}),
    )

    payload = _business_query_fact(result)
    assert payload["status"] == "ok"
    assert payload["rows"][0]["order_no"] == "ORD-BQ-IN-SCOPE-1"
    assert "ORD-BQ-OUT-OF-SCOPE-NEWER" not in payload["rows"][0].values()
    assert "merchant_id" not in payload["rows"][0]
    assert "buyer_name" not in payload["rows"][0]
    assert payload["cursor"]["has_more"] is True
    assert payload["cursor"]["next_cursor"]["cursor_id"]
    serialized = result.model_dump_json()
    assert str(out_of_scope.id) not in serialized
    assert "ORD-BQ-OUT-OF-SCOPE-NEWER" not in serialized


@pytest.mark.asyncio
async def test_business_query_denied_list_returns_typed_no_leak_payload(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)

    result = await service.query_business(
        {
            "operation": "list",
            "resource": "order",
            "merchant_id": "MERCHANT-SECRET",
            "time_preset": "this_week",
            "fields": ["order_no", "status"],
        },
        _ctx(seeded_session, merchant_scope={"merchant_ids": ["MERCHANT-ALLOWED"]}),
    )

    assert result.status == "permission_denied"
    assert result.scope_check_result == "denied"
    assert result.business_fact_refs == []
    assert result.fact is not None
    payload = result.fact["business_query"]
    assert payload["operation"] == "list"
    assert payload["resource"] == "order"
    assert payload["status"] == "permission_denied"
    assert payload["rows"] == []
    assert payload["answer_context"]["query_spec"]["operation"] == "list"
    assert payload["answer_context"]["query_spec"]["merchant_id"] is None
    assert payload["answer_context"]["query_spec"]["resource_id"] is None
    assert payload["scope"]["no_leak_status"] == "scope_denied_no_existence_leak"

    api_payload = safe_business_query_api_payload(payload)
    assert api_payload["operation"] == "list"
    assert api_payload["resource_label"] == "订单"
    assert api_payload["safe_reason"] == "scope_denied_no_existence_leak"
    assert api_payload["rows"] == []
    assert "MERCHANT-SECRET" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_business_query_tool_denial_preserves_safe_payload_without_fact_refs(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessToolService.with_default_registry(session)

    result = await service.invoke_tool(
        "business_query",
        {
            "operation": "list",
            "resource": "order",
            "merchant_id": "MERCHANT-SECRET",
            "time_preset": "this_week",
            "fields": ["order_no", "status"],
        },
        _ctx(seeded_session, merchant_scope={"merchant_ids": ["MERCHANT-ALLOWED"]}),
    )

    assert result.status == "permission_denied"
    assert result.business_fact_refs == []
    assert result.data is not None
    payload = result.data["business_query"]
    assert payload["operation"] == "list"
    assert payload["resource"] == "order"
    assert payload["status"] == "permission_denied"
    assert payload["rows"] == []
    assert payload["answer_context"]["query_spec"]["operation"] == "list"
    assert payload["answer_context"]["query_spec"]["merchant_id"] is None
    assert payload["answer_context"]["query_spec"]["resource_id"] is None
    assert payload["scope"]["no_leak_status"] == "scope_denied_no_existence_leak"
    assert result.error is not None
    assert result.error.code == "BUSINESS_FACT_PERMISSION_DENIED"

    api_payload = safe_business_query_api_payload(payload)
    assert api_payload["operation"] == "list"
    assert api_payload["safe_reason"] == "scope_denied_no_existence_leak"
    assert "MERCHANT-SECRET" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_business_query_detail_uses_scoped_lookup_without_existence_leak(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    statements: list[str] = []

    @event.listens_for(session.bind.sync_engine, "before_cursor_execute")
    def _capture_statement(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        del conn, cursor, parameters, context, executemany
        statements.append(statement)

    try:
        result = await service.query_business(
            {
                "operation": "detail",
                "resource": "order",
                "resource_id": "ORD-TEST-002",
                "fields": ["order_no", "status", "amount", "currency", "item_name", "paid_at", "delivered_at"],
            },
            _ctx(seeded_session),
        )
    finally:
        event.remove(session.bind.sync_engine, "before_cursor_execute", _capture_statement)

    payload = _business_query_fact(result)
    assert payload["status"] == "empty"
    assert payload["rows"] == []
    serialized = result.model_dump_json()
    assert "ORD-TEST-002" not in serialized
    order_statements = [statement for statement in statements if "FROM orders" in statement]
    assert len(order_statements) == 1
    assert "merchant_id" in order_statements[0]
    assert "order_no" in order_statements[0]


@pytest.mark.asyncio
async def test_business_query_breakdown_and_compare_execute_runtime_paths(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)

    breakdown = await service.query_business(
        {
            "operation": "breakdown",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "group_by": "status",
        },
        _ctx(seeded_session),
    )
    compare = await service.query_business(
        {
            "operation": "compare",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_month",
            "compare_to": "previous_period",
        },
        _ctx(seeded_session),
    )

    breakdown_payload = _business_query_fact(breakdown)
    assert breakdown_payload["status"] == "ok"
    assert breakdown_payload["rows"] == [{"status": "delivered", "value": 1, "display_value": "1"}]

    compare_payload = _business_query_fact(compare)
    assert compare_payload["status"] == "ok"
    row = compare_payload["rows"][0]
    assert row["metric_id"] == "order_count"
    assert row["current_value"] == 1
    assert row["previous_value"] == 0
    assert row["delta"] == 1
    assert row["previous_period"]["end_at"] == row["current_period"]["start_at"]


@pytest.mark.asyncio
async def test_business_query_compare_handles_week_boundary_and_empty_previous_period(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)

    result = await service.query_business(
        {
            "operation": "compare",
            "resource": "order",
            "metric_id": "order_count",
            "time_preset": "this_week",
            "compare_to": "previous_period",
        },
        _ctx(seeded_session, effective_at="2026-07-06T08:00:00+08:00"),
    )

    row = _business_query_fact(result)["rows"][0]
    assert row["current_period"]["start_at"] == "2026-07-05T16:00:00Z"
    assert row["current_period"]["end_at"] == "2026-07-06T00:00:00Z"
    assert row["previous_period"]["start_at"] == "2026-07-05T08:00:00Z"
    assert row["previous_value"] == 0


@pytest.mark.asyncio
async def test_business_query_invalid_inputs_fail_closed_without_querying(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    calls = 0

    @event.listens_for(session.bind.sync_engine, "before_cursor_execute")
    def _count_statement(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        nonlocal calls
        del conn, cursor, statement, parameters, context, executemany
        calls += 1

    try:
        invalid_field = await service.query_business(
            {"operation": "list", "resource": "order", "fields": ["buyer_name"]},
            _ctx(seeded_session),
        )
        invalid_cursor = await service.query_business(
            {
                "operation": "list",
                "resource": "order",
                "cursor": {"cursor_id": "not-a-business-query-cursor", "direction": "next"},
            },
            _ctx(seeded_session),
        )
        empty_scope = await service.query_business(
            {"operation": "list", "resource": "order"},
            _ctx(seeded_session, merchant_scope={"merchant_ids": []}),
        )
    finally:
        event.remove(session.bind.sync_engine, "before_cursor_execute", _count_statement)

    assert invalid_field.status == "invalid_request"
    assert invalid_cursor.status == "invalid_request"
    assert empty_scope.status == "permission_denied"
    assert calls == 0


@pytest.mark.asyncio
async def test_query_business_metric_delegates_to_business_query_and_preserves_metric_shape(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    calls: list[BusinessQuerySpec] = []
    original = service.query_business

    async def _recording_query_business(args, ctx):  # noqa: ANN001
        spec = BusinessQuerySpec.model_validate(args)
        calls.append(spec)
        return await original(spec, ctx)

    monkeypatch.setattr(service, "query_business", _recording_query_business)

    result = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "this_week"},
        _ctx(seeded_session),
    )

    assert calls == [
        BusinessQuerySpec(
            operation="aggregate",
            resource="order",
            metric_id="order_count",
            time_preset="this_week",
        )
    ]
    assert result.status == "ok"
    assert result.fact is not None
    assert result.fact["metric_id"] == "order_count"
    assert result.fact["value"] == 1
    assert result.business_fact_refs[0].resource_type == "business_metric"


def test_business_query_compiler_is_present_and_uses_sqlalchemy_statements() -> None:
    compiler = BusinessQueryCompiler()
    assert hasattr(compiler, "compile")
