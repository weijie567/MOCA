from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import _project_tool_result
from src.business.schemas import BusinessFactResultV1, BusinessMetricResultV1, BusinessQueryResultV1
from src.business.service import (
    BUSINESS_READ_TOOLS,
    BusinessFactService,
    BusinessReadToolDefinition,
    BusinessToolService,
    _merchant_scope_allows,
)
from src.integrations.demo_business.authz import merchant_can_access
from src.db.models import ActionDraft, AgentRun, Order
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2
from src.tools.executors.business import BusinessToolExecutor


NO_LEAK_MESSAGE = "Business resource unavailable for this request"


def _context(**updates: object) -> ToolCallContext:
    values: dict[str, object] = {
        "tenant_id": "tenant-09",
        "user_id": "user-09",
        "role": "support",
        "permissions": ["tool:get_order", "tool:get_refund_case", "tool:get_ticket"],
        "merchant_scope": {"merchant_ids": ["*"]},
        "thread_id": "thread-09",
        "run_id": "run-09",
        "trace_id": "trace-09",
        "request_id": "request-09",
        "tool_call_id": "tool-call-09",
        "caller_node": "investigate",
    }
    values.update(updates)
    return ToolCallContext.model_validate(values)


def _result(
    status: str = "success",
    *,
    data: dict | None = None,
    retryable: bool = False,
    code: str | None = None,
    business_fact_refs: list[BusinessFactRefV1] | None = None,
) -> ToolResultV2:
    error = None
    if code is not None:
        error = ToolError(code=code, safe_message=f"Safe {code}", retryable=retryable, source="adapter")
    resolved_data = {"id": "resource-09"} if status == "success" and data is None else data
    return ToolResultV2(
        status=status,
        data=resolved_data,
        summary=f"{status} result",
        source_system="test_business_db",
        data_freshness_at=None,
        business_fact_refs=(
            [_fact_ref()]
            if business_fact_refs is None and status in {"success", "partial_success"} and resolved_data is not None
            else business_fact_refs or []
        ),
        error=error,
        retryable=retryable,
        latency_ms=1,
        audit_ref=None,
    )


def _fact_ref(
    tenant_id: str = "tenant-09",
    resource_type: str = "order",
    resource_id: str = "ORD-09",
) -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=tenant_id,
        source_system="test_business_db",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=None,
        retrieved_at=datetime.now(UTC),
    )


def _business_fact_result(
    *,
    status: str = "ok",
    resource_name: str = "order",
    resource_type: str = "order",
    resource_id: str = "ORD-09",
    tenant_id: str = "tenant-09",
) -> BusinessFactResultV1:
    allowed = status in {"ok", "partial"}
    error = None
    if status == "stale":
        error = ToolError(
            code="BUSINESS_FACT_STALE",
            safe_message="Business fact is stale",
            retryable=False,
            source="adapter",
        )
    return BusinessFactResultV1(
        tenant_id=tenant_id,
        status=status,
        fact={f"{resource_name}_id": resource_id} if allowed else None,
        business_fact_refs=[_fact_ref(tenant_id, resource_type, resource_id)] if allowed else [],
        resource_version=None,
        data_freshness_at=None,
        source_system="test_business_db",
        scope_check_result="allowed" if allowed else "unknown",
        missing_required_facts=[] if allowed else [resource_name],
        safe_errors=[] if error is None else [error],
    )


def _metric_result(**overrides: object) -> BusinessMetricResultV1:
    payload: dict[str, object] = {
        "metric_id": "pending_ticket_count",
        "status": "ok",
        "value": 3,
        "rate": None,
        "numerator": None,
        "denominator": None,
        "unit": "count",
        "display_value": "3",
        "scope": {
            "tenant_id": "tenant-09",
            "merchant_ids": ["merchant-09"],
            "scope_label": "当前权限范围",
        },
        "time_range": {
            "start_at": None,
            "end_at": None,
            "preset": "current_snapshot",
            "timezone": "Asia/Shanghai",
        },
        "filters": {"merchant_id": "merchant-09", "status_filter": ["open", "in_progress"]},
        "freshness": {
            "data_freshness_at": None,
            "computed_at": datetime.now(UTC),
            "source_system": "demo_business_db",
        },
        "formula": "count tickets where status in open/in_progress",
        "caveats": [],
        "no_leak_status": "not_applicable",
    }
    payload.update(overrides)
    return BusinessMetricResultV1.model_validate(payload)


class _StubMetricService(BusinessFactService):
    def __init__(self, result: BusinessMetricResultV1) -> None:
        super().__init__(AsyncMock())
        self.result = result
        self.calls: list[tuple[object, ToolCallContext, list[str]]] = []

    async def query_business(self, args, ctx: ToolCallContext):
        from src.business.query.schemas import BusinessQuerySpec

        spec = BusinessQuerySpec.model_validate(args)
        merchant_ids = self._authorized_business_query_merchant_ids(spec, ctx)
        if merchant_ids is None:
            return self._permission_denied_result("business_query", ctx.tenant_id)
        self.calls.append((spec, ctx, merchant_ids))
        query_result = BusinessQueryResultV1(
            operation=spec.operation,
            resource=spec.resource,
            status="ok",
            rows=[self.result.model_dump(mode="json")],
            scope={"scope_label": "authorized_merchants", "merchant_id": spec.merchant_id},
        )
        return self._business_query_result_to_fact_result(query_result, ctx)


def _seeded_context(
    seeded_session: dict,
    user_key: str = "cs_zhang",
    *,
    merchant_scope: dict | None = None,
    role: str | None = None,
) -> ToolCallContext:
    user = seeded_session["users"][user_key]
    tenant = seeded_session["tenant"]
    if merchant_scope is None:
        if user.role == "admin":
            merchant_scope = {"merchant_ids": ["*"]}
        elif user.merchant_id is None:
            merchant_scope = {"merchant_ids": []}
        else:
            merchant_scope = {"merchant_ids": [str(user.merchant_id)]}
    return _context(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        role=user.role if role is None else role,
        merchant_scope=merchant_scope,
    )


def _assert_fail_closed(result: BusinessFactResultV1, status: str) -> None:
    assert result.status == status
    assert result.fact is None
    assert result.business_fact_refs == []


def _assert_wrapped_tool_result_has_no_facts(
    result: ToolResultV2,
    *,
    status: str,
    code: str,
    safe_message: str = NO_LEAK_MESSAGE,
) -> None:
    assert result.status == status
    assert result.data is None
    assert result.business_fact_refs == []
    assert result.policy_evidence_refs == []
    assert result.error is not None
    assert result.error.code == code
    assert result.error.safe_message == safe_message


def _metric_value(result: BusinessFactResultV1) -> dict:
    assert result.status == "ok"
    assert result.fact is not None
    assert result.business_fact_refs
    assert result.business_fact_refs[0].resource_type == "business_metric"
    return result.fact


async def _add_coupon_draft(
    session: AsyncSession,
    *,
    tenant_id,
    user_id,
    merchant_id,
    created_at: datetime,
    action_type: str = "issue_coupon",
) -> None:
    run_id = uuid4()
    session.add(
        AgentRun(
            id=run_id,
            thread_id=f"metric-coupon-{run_id}",
            tenant_id=tenant_id,
            user_id=user_id,
            input_query="metric coupon fixture",
            final_status="completed",
            target_merchant_id=str(merchant_id),
            target_merchant_ref={"merchant_id": str(merchant_id)},
            scope_classification="business_merchant",
            started_at=created_at,
            completed_at=created_at,
        )
    )
    await session.flush()
    session.add(
        ActionDraft(
            id=uuid4(),
            run_id=run_id,
            tenant_id=tenant_id,
            idempotency_key=f"{run_id}:{action_type}",
            action_type=action_type,
            status="draft_created",
            payload={"target_id": "RF-METRIC"},
            target_merchant_id=str(merchant_id),
            draft_outcome={"status": "not_executed_demo"},
            execution_mode="demo",
            created_by_agent_run=run_id,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_business_fact_ref_accepts_metric_query_result_with_metric_provenance() -> None:
    service = _StubMetricService(_metric_result())

    result = await service.query_business_metric(
        {"metric_id": "pending_ticket_count", "time_preset": "current_snapshot", "merchant_id": "merchant-09"},
        _context(permissions=["tool:query_business_metric"], merchant_scope={"merchant_ids": ["merchant-09"]}),
    )

    assert result.status == "ok"
    assert result.fact is not None
    assert result.fact["metric_id"] == "pending_ticket_count"
    assert result.fact["value"] == 3
    assert result.fact["scope"]["merchant_ids"] == ["merchant-09"]
    assert result.business_fact_refs == [
        BusinessFactRefV1(
            tenant_id="tenant-09",
            source_system="business_fact_service",
            resource_type="business_metric",
            resource_id="pending_ticket_count",
            resource_version=None,
            data_freshness_at=result.data_freshness_at,
            retrieved_at=result.business_fact_refs[0].retrieved_at,
        )
    ]
    assert service.calls[0][2] == ["merchant-09"]


@pytest.mark.asyncio
async def test_business_metric_permission_denial_has_no_metric_data_or_merchant_leak() -> None:
    service = _StubMetricService(_metric_result())

    result = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "today", "merchant_id": "merchant-secret"},
        _context(permissions=["tool:query_business_metric"], merchant_scope={"merchant_ids": ["merchant-allowed"]}),
    )

    _assert_fail_closed(result, "permission_denied")
    assert result.scope_check_result == "denied"
    assert result.missing_required_facts == ["business_metric"]
    serialized = result.model_dump_json()
    assert "merchant-secret" not in serialized
    assert "merchant-allowed" not in serialized
    assert service.calls == []


@pytest.mark.asyncio
async def test_business_metric_zero_denominator_refund_rate_is_successful_non_computable_fact() -> None:
    service = _StubMetricService(
        _metric_result(
            metric_id="merchant_refund_rate",
            status="non_computable",
            value=None,
            rate=None,
            numerator=0,
            denominator=0,
            unit="ratio",
            display_value="暂无可计算退款率",
            formula="distinct refunded orders / total orders",
            caveats=["当前范围内没有订单，无法计算退款率。"],
        )
    )

    result = await service.query_business_metric(
        {"metric_id": "merchant_refund_rate", "time_preset": "today"},
        _context(permissions=["tool:query_business_metric"], merchant_scope={"merchant_ids": ["merchant-09"]}),
    )

    assert result.status == "ok"
    assert result.fact is not None
    assert result.fact["status"] == "non_computable"
    assert result.fact["denominator"] == 0
    assert result.fact["rate"] is None
    assert result.fact["display_value"] == "暂无可计算退款率"
    assert result.business_fact_refs[0].resource_type == "business_metric"


@pytest.mark.asyncio
async def test_business_tool_service_dispatches_query_business_metric() -> None:
    service = _StubMetricService(_metric_result())

    tool_result = await BusinessToolService(AsyncMock(), fact_service=service).invoke_tool(
        "query_business_metric",
        {"metric_id": "pending_ticket_count", "time_preset": "current_snapshot"},
        _context(permissions=["tool:query_business_metric"], merchant_scope={"merchant_ids": ["merchant-09"]}),
    )

    assert tool_result.status == "success"
    assert tool_result.data is not None
    assert tool_result.data["metric_id"] == "pending_ticket_count"
    assert tool_result.business_fact_refs[0].resource_type == "business_metric"


@pytest.mark.asyncio
async def test_metric_order_count_respects_support_manager_and_admin_scope(
    session: AsyncSession,
    seeded_session,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    now = datetime.now(UTC)
    args = {
        "metric_id": "order_count",
        "start_at": (now - timedelta(days=10)).isoformat(),
        "end_at": (now + timedelta(days=1)).isoformat(),
    }

    support_fact = _metric_value(await service.query_business_metric(args, _seeded_context(seeded_session, "cs_zhang")))
    manager_fact = _metric_value(
        await service.query_business_metric(args, _seeded_context(seeded_session, "approval_manager"))
    )
    admin_fact = _metric_value(await service.query_business_metric(args, _seeded_context(seeded_session, "admin_user")))
    narrowed_admin_fact = _metric_value(
        await service.query_business_metric(
            args,
            _seeded_context(
                seeded_session,
                "admin_user",
                merchant_scope={"merchant_ids": [str(seeded_session["second_merchant"].id)]},
            ),
        )
    )

    assert support_fact["value"] == 1
    assert support_fact["scope"]["merchant_ids"] == [str(seeded_session["merchant"].id)]
    assert manager_fact["value"] == 1
    assert manager_fact["scope"]["merchant_ids"] == [str(seeded_session["merchant"].id)]
    assert admin_fact["value"] == 2
    assert admin_fact["scope"]["merchant_ids"] == ["*"]
    assert narrowed_admin_fact["value"] == 1
    assert narrowed_admin_fact["scope"]["merchant_ids"] == [str(seeded_session["second_merchant"].id)]


@pytest.mark.asyncio
async def test_metric_runtime_computes_refunds_tickets_coupons_and_refund_rate(
    session: AsyncSession,
    seeded_session,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    now = datetime.now(UTC)
    support_ctx = _seeded_context(seeded_session, "cs_zhang")
    time_args = {
        "start_at": (now - timedelta(days=10)).isoformat(),
        "end_at": (now + timedelta(days=1)).isoformat(),
    }
    await _add_coupon_draft(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        merchant_id=seeded_session["merchant"].id,
        created_at=now - timedelta(days=1),
    )
    await _add_coupon_draft(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        merchant_id=seeded_session["second_merchant"].id,
        created_at=now - timedelta(days=1),
    )
    await _add_coupon_draft(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        merchant_id=seeded_session["merchant"].id,
        created_at=now - timedelta(days=1),
        action_type="not_coupon",
    )

    refund_fact = _metric_value(
        await service.query_business_metric({"metric_id": "refund_case_count", **time_args}, support_ctx)
    )
    ticket_fact = _metric_value(
        await service.query_business_metric({"metric_id": "pending_ticket_count"}, support_ctx)
    )
    coupon_fact = _metric_value(
        await service.query_business_metric({"metric_id": "coupon_record_count", **time_args}, support_ctx)
    )
    refund_rate_fact = _metric_value(
        await service.query_business_metric({"metric_id": "merchant_refund_rate", **time_args}, support_ctx)
    )

    assert refund_fact["value"] == 1
    assert ticket_fact["value"] == 1
    assert ticket_fact["filters"]["status_filter"] == ["open", "in_progress"]
    assert coupon_fact["value"] == 1
    assert any("MOCA demo" in caveat for caveat in coupon_fact["caveats"])
    assert refund_rate_fact["numerator"] == 1
    assert refund_rate_fact["denominator"] == 1
    assert refund_rate_fact["rate"] == 1.0
    assert refund_rate_fact["display_value"] == "100.00%"


@pytest.mark.asyncio
async def test_metric_time_preset_uses_local_business_timezone_boundaries(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant = seeded_session["tenant"]
    merchant = seeded_session["merchant"]
    before_today_utc = datetime(2026, 7, 8, 15, 59, 59, tzinfo=UTC)
    start_today_utc = datetime(2026, 7, 8, 16, 0, 0, tzinfo=UTC)
    session.add_all(
        [
            Order(
                id=uuid4(),
                tenant_id=tenant.id,
                merchant_id=merchant.id,
                order_no="ORD-METRIC-BEFORE-TODAY",
                buyer_name="Boundary",
                item_name="Boundary",
                amount=1,
                currency="CNY",
                status="paid",
                created_at=before_today_utc,
                updated_at=before_today_utc,
            ),
            Order(
                id=uuid4(),
                tenant_id=tenant.id,
                merchant_id=merchant.id,
                order_no="ORD-METRIC-START-TODAY",
                buyer_name="Boundary",
                item_name="Boundary",
                amount=1,
                currency="CNY",
                status="paid",
                created_at=start_today_utc,
                updated_at=start_today_utc,
            ),
        ]
    )
    await session.flush()

    fact = _metric_value(
        await BusinessFactService.with_default_registry(session).query_business_metric(
            {"metric_id": "order_count", "time_preset": "today"},
            _seeded_context(
                seeded_session,
                "cs_zhang",
                merchant_scope={"merchant_ids": [str(merchant.id)]},
            ).model_copy(update={"effective_at": "2026-07-09T12:00:00+08:00"}),
        )
    )

    assert fact["value"] == 1
    assert fact["time_range"]["start_at"] == "2026-07-08T16:00:00Z"
    assert fact["time_range"]["end_at"] == "2026-07-09T04:00:00Z"


@pytest.mark.asyncio
async def test_metric_invalid_ranges_empty_scope_and_malicious_args_fail_closed(
    session: AsyncSession,
    seeded_session,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    ctx = _seeded_context(seeded_session, "cs_zhang")

    invalid_range = await service.query_business_metric(
        {
            "metric_id": "order_count",
            "start_at": "2026-07-09T00:00:00Z",
            "end_at": "2026-07-08T00:00:00Z",
        },
        ctx,
    )
    unsupported_status = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "today", "status_filter": ["cancelled"]},
        ctx.model_copy(update={"effective_at": "2026-07-09T12:00:00+08:00"}),
    )
    empty_scope = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "today"},
        ctx.model_copy(update={"merchant_scope": {"merchant_ids": []}, "effective_at": "2026-07-09T12:00:00+08:00"}),
    )
    malicious_tenant = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "today", "tenant_id": str(seeded_session["other_tenant"].id)},
        ctx.model_copy(update={"effective_at": "2026-07-09T12:00:00+08:00"}),
    )
    malicious_scope = await service.query_business_metric(
        {"metric_id": "order_count", "time_preset": "today", "merchant_scope": ["*"]},
        ctx.model_copy(update={"effective_at": "2026-07-09T12:00:00+08:00"}),
    )

    assert invalid_range.status == "invalid_request"
    assert unsupported_status.status == "invalid_request"
    _assert_fail_closed(empty_scope, "permission_denied")
    assert malicious_tenant.status == "invalid_request"
    assert malicious_scope.status == "invalid_request"
    assert str(seeded_session["other_tenant"].id) not in malicious_tenant.model_dump_json()


@pytest.mark.asyncio
async def test_metric_future_empty_range_and_zero_denominator_are_deterministic(
    session: AsyncSession,
    seeded_session,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    ctx = _seeded_context(seeded_session, "cs_zhang")
    future_args = {
        "start_at": "2099-01-01T00:00:00Z",
        "end_at": "2099-01-02T00:00:00Z",
    }

    empty_count = _metric_value(await service.query_business_metric({"metric_id": "order_count", **future_args}, ctx))
    refund_rate = _metric_value(
        await service.query_business_metric({"metric_id": "merchant_refund_rate", **future_args}, ctx)
    )

    assert empty_count["value"] == 0
    assert empty_count["display_value"] == "0"
    assert refund_rate["status"] == "non_computable"
    assert refund_rate["denominator"] == 0
    assert refund_rate["rate"] is None
    assert refund_rate["display_value"] == "暂无可计算退款率"


@pytest.mark.asyncio
async def test_retry_cap_reuses_stable_tool_call_id_and_session() -> None:
    adapter = AsyncMock(
        side_effect=[
            _result("timeout", data=None, retryable=True, code="DB_TIMEOUT"),
            _result(),
        ]
    )
    session = AsyncMock(spec=AsyncSession)
    ctx = _context(max_attempts=2)

    result = await BusinessToolService(session, adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        ctx,
    )

    assert result.status == "success"
    assert adapter.call_count == 2
    attempts = [call.args[1].attempt for call in adapter.await_args_list]
    tool_call_ids = [call.args[1].tool_call_id for call in adapter.await_args_list]
    assert attempts == [1, 2]
    assert tool_call_ids == [ctx.tool_call_id, ctx.tool_call_id]
    assert all(call.args[2] is session for call in adapter.await_args_list)


@pytest.mark.asyncio
async def test_attempt_exhausted_does_not_invoke_adapter() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(attempt=3, max_attempts=2),
    )

    assert result.error is not None
    assert result.error.code == "BUSINESS_FACT_UNAVAILABLE"
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_merchant_scope_denied_before_adapter() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(merchant_scope={}),
    )

    assert result.status == "permission_denied"
    assert result.error is not None
    assert result.error.code == "BUSINESS_FACT_PERMISSION_DENIED"
    assert result.error.safe_message == NO_LEAK_MESSAGE
    adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_does_not_repeat_permission_check() -> None:
    adapter = AsyncMock(return_value=_result())

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(permissions=[]),
    )

    assert result.status == "success"
    adapter.assert_awaited_once()


def test_unknown_category_scope_denied() -> None:
    assert not _merchant_scope_allows(
        {"merchant_ids": ["*"], "categories": ["food"]},
        category="electronics",
    )


def test_merchant_scope_no_widening_denied() -> None:
    assert not _merchant_scope_allows({"merchant_ids": ["merchant-1"]}, merchant_id="merchant-2")


def test_merchant_scope_legacy_list_supports_canonical_matching() -> None:
    assert _merchant_scope_allows(["*"], merchant_id="merchant-2")
    assert not _merchant_scope_allows(["merchant-1"], merchant_id="merchant-2")


@pytest.mark.asyncio
async def test_legacy_list_merchant_scope_reaches_business_adapter() -> None:
    adapter = AsyncMock(return_value=_result(data={"order_no": "ORD-09"}))

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(merchant_scope=["*"]),
    )

    assert result.status == "success"
    adapter.assert_awaited_once()


@pytest.mark.asyncio
async def test_merchant_can_access_rejects_forged_admin_context(session: AsyncSession, seeded_session) -> None:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"]["cs_zhang"]
    merchant = seeded_session["second_merchant"]

    assert not await merchant_can_access(
        session,
        tenant_id=tenant.id,
        user_id="not-a-uuid",
        role="admin",
        merchant_id=merchant.id,
    )
    assert not await merchant_can_access(
        session,
        tenant_id=tenant.id,
        user_id=str(user.id),
        role="admin",
        merchant_id=merchant.id,
    )


def test_business_read_tool_definitions_drive_executor_support() -> None:
    service = BusinessToolService(AsyncMock())
    executor = BusinessToolExecutor(AsyncMock(), service=service)

    assert {name for name in BUSINESS_READ_TOOLS if executor.has_tool(name)} == set(BUSINESS_READ_TOOLS)


@pytest.mark.asyncio
async def test_custom_business_read_definition_drives_invoke_and_fetch_context() -> None:
    class DemoInput(BaseModel):
        demo_no: str

    adapter = AsyncMock(return_value=_result(data={"demo_no": "DEMO-09"}))
    service = BusinessToolService(
        AsyncMock(),
        tools={
            "get_demo": BusinessReadToolDefinition(
                input_model=DemoInput,
                adapter=adapter,
                slot_name="demo_id",
                resource_name="demo",
                argument_name="demo_no",
            )
        },
    )

    assert service.has_tool("get_demo")
    assert BusinessToolExecutor(AsyncMock(), service=service).has_tool("get_demo")

    result = await service.invoke_tool("get_demo", {"demo_no": "DEMO-09"}, _context())
    context = await service.fetch_context({"demo_id": "DEMO-09"}, "refund_troubleshooting", _context())

    assert result.status == "success"
    assert context.facts == {"demo": {"demo_no": "DEMO-09"}}
    assert adapter.await_count == 2


@pytest.mark.asyncio
async def test_real_read_input_does_not_fabricate_merchant_id_or_category() -> None:
    adapter = AsyncMock(return_value=_result())

    await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    dispatched_input = adapter.await_args.args[0]
    assert dispatched_input.model_dump() == {"order_no": "ORD-09"}
    assert not hasattr(dispatched_input, "merchant_id")
    assert not hasattr(dispatched_input, "category")
    # Resource ownership for these reads remains enforced by raw merchant_can_access.


@pytest.mark.asyncio
async def test_fetch_context_mixed_results_is_partial_and_lists_missing_fact() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result(data={"order_no": "ORD-09"})),
        "get_ticket": AsyncMock(return_value=_result("not_found", data=None, code="NOT_FOUND")),
    }

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "partial"
    assert context.facts == {"order": {"order_no": "ORD-09"}}
    assert context.missing_required_facts == ["ticket"]
    assert context.errors[0].code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_fetch_context_all_success_is_complete() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result(data={"order_no": "ORD-09"})),
        "get_refund_case": AsyncMock(return_value=_result(data={"refund_case_no": "RF-09"})),
        "get_ticket": AsyncMock(return_value=_result(data={"ticket_no": "T-09"})),
    }

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "complete"
    assert set(context.facts) == {"order", "refund_case", "ticket"}
    assert context.missing_required_facts == []
    assert all(adapter.await_count == 1 for adapter in adapters.values())


@pytest.mark.asyncio
async def test_fetch_context_partial_success_aggregates_fact_refs() -> None:
    fact_result = _business_fact_result(
        status="partial",
        resource_name="order",
        resource_type="order",
        resource_id="ORD-PARTIAL-09",
    )
    adapter = AsyncMock(return_value=fact_result)

    context = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).fetch_context(
        {"order_id": "ORD-PARTIAL-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "complete"
    assert context.facts == {"order": fact_result.fact}
    assert context.business_fact_refs == fact_result.business_fact_refs
    assert context.missing_required_facts == []
    assert context.errors == []
    assert context.tool_results[0].status == "partial_success"


@pytest.mark.asyncio
async def test_fetch_context_no_success_is_insufficient() -> None:
    adapters = {"get_refund_case": AsyncMock(return_value=_result("not_found", data=None, code="NOT_FOUND"))}

    context = await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"refund_case_id": "RF-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "insufficient"
    assert context.facts == {}
    assert context.missing_required_facts == ["refund_case"]


@pytest.mark.asyncio
async def test_fetch_context_uses_distinct_tool_call_id_per_logical_read() -> None:
    adapters = {
        "get_order": AsyncMock(return_value=_result()),
        "get_refund_case": AsyncMock(return_value=_result()),
        "get_ticket": AsyncMock(return_value=_result()),
    }

    await BusinessToolService(AsyncMock(), adapters=adapters).fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "T-09"},
        "refund_troubleshooting",
        _context(),
    )

    tool_call_ids = [call.args[1].tool_call_id for adapter in adapters.values() for call in adapter.await_args_list]
    assert len(set(tool_call_ids)) == 3


@pytest.mark.asyncio
async def test_fetch_context_cross_merchant_permission_denied_has_no_business_facts(
    session: AsyncSession, seeded_session
) -> None:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"]["cs_zhang"]
    merchant = seeded_session["merchant"]

    context = await BusinessToolService.with_default_registry(session).fetch_context(
        {"order_id": "ORD-TEST-002"},
        "refund_troubleshooting",
        _context(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            role=user.role,
            merchant_scope={"merchant_ids": [str(merchant.id)]},
        ),
    )

    assert context.status == "insufficient"
    assert context.facts == {}
    assert context.business_fact_refs == []
    assert context.missing_required_facts == ["order"]
    assert len(context.tool_results) == 1
    denied_result = context.tool_results[0]
    assert denied_result.status == "permission_denied"
    assert denied_result.business_fact_refs == []
    assert denied_result.data is None
    assert denied_result.error is not None
    assert denied_result.error.code == "BUSINESS_FACT_PERMISSION_DENIED"
    assert denied_result.error.safe_message == NO_LEAK_MESSAGE
    prompt_summary = _project_tool_result(
        tool_call_id="tool-call-denied",
        tool_result_id="tool-result-denied",
        tool_name="get_order",
        result=denied_result,
        raw_result_ref=None,
    )
    assert prompt_summary.business_fact_refs == []
    assert "ORD-TEST-002" not in prompt_summary.prompt_summary
    assert "Order read succeeded" not in prompt_summary.prompt_summary
    serialized_context = context.model_dump_json()
    assert "ORD-TEST-002" not in serialized_context
    assert "Order read succeeded" not in serialized_context


@pytest.mark.asyncio
async def test_adapter_exception_returns_safe_tool_result() -> None:
    adapter = AsyncMock(side_effect=RuntimeError("RAW-SERVICE-SECRET"))

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "unavailable"
    assert result.data is None
    assert result.error is not None
    assert result.error.code == "BUSINESS_FACT_UNAVAILABLE"
    assert "RAW-SERVICE-SECRET" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_with_default_registry_invokes_real_adapter_with_mocked_raw_get_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_get_order = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "order_no": "ORD-09",
                "merchant_id": "merchant-09",
                "status": "paid",
                "amount": "88.00",
                "currency": "CNY",
                "buyer_name": "Demo Buyer",
                "item_name": "Demo Item",
                "paid_at": None,
                "delivered_at": None,
                "relation_hints": {
                    "has_active_refund": False,
                    "latest_refund_case_id": None,
                    "has_open_ticket": False,
                    "latest_ticket_id": None,
                },
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.business.adapters.get_order", raw_get_order)
    session = AsyncMock(spec=AsyncSession)

    result = await BusinessToolService.with_default_registry(session).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "success"
    assert result.summary == "Business fact read succeeded"
    assert result.data is not None
    assert result.data["order_no"] == "ORD-09"
    assert result.data["merchant_id"] == "merchant-09"
    assert len(result.business_fact_refs) == 1
    assert result.business_fact_refs[0].resource_id == "ORD-09"
    assert result.policy_evidence_refs == []
    raw_get_order.assert_awaited_once_with("ORD-09", "tenant-09", "user-09", "support", session)


@pytest.mark.asyncio
async def test_business_tool_service_wraps_domain_ok_result_as_tool_result() -> None:
    fact_result = _business_fact_result(
        status="ok",
        resource_name="order",
        resource_type="order",
        resource_id="ORD-09",
    )
    adapter = AsyncMock(return_value=fact_result)

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "success"
    assert result.summary == "Business fact read succeeded"
    assert result.data == fact_result.fact
    assert result.business_fact_refs == fact_result.business_fact_refs
    assert result.policy_evidence_refs == []
    assert result.data_freshness_at == fact_result.data_freshness_at


@pytest.mark.asyncio
async def test_business_tool_service_wraps_domain_partial_result_as_partial_success() -> None:
    fact_result = _business_fact_result(
        status="partial",
        resource_name="order",
        resource_type="order",
        resource_id="ORD-09",
    )
    adapter = AsyncMock(return_value=fact_result)

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-09"},
        _context(),
    )

    assert result.status == "partial_success"
    assert result.data == fact_result.fact
    assert result.business_fact_refs == fact_result.business_fact_refs
    assert result.policy_evidence_refs == []


@pytest.mark.asyncio
async def test_business_fact_service_rejects_domain_success_without_service_refs() -> None:
    unsafe_fact = _business_fact_result(
        status="ok",
        resource_name="order",
        resource_type="order",
        resource_id="ORD-UNREF-09",
    ).model_copy(update={"business_fact_refs": []})
    fact_adapter = AsyncMock(return_value=unsafe_fact)
    service = BusinessFactService(AsyncMock(), adapters={"get_order": fact_adapter})

    fact_result = await service.get_order("ORD-UNREF-09", _context())

    _assert_fail_closed(fact_result, "unavailable")
    assert fact_result.scope_check_result == "unknown"
    assert fact_result.safe_errors[0].code == "BUSINESS_FACT_UNAVAILABLE"

    tool_adapter = AsyncMock(return_value=unsafe_fact)
    tool_result = await BusinessToolService(AsyncMock(), adapters={"get_order": tool_adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-UNREF-09"},
        _context(),
    )

    _assert_wrapped_tool_result_has_no_facts(
        tool_result,
        status="unavailable",
        code="BUSINESS_FACT_UNAVAILABLE",
    )
    assert "ORD-UNREF-09" not in tool_result.model_dump_json()


@pytest.mark.asyncio
async def test_business_fact_service_rejects_domain_success_with_wrong_tenant_ref() -> None:
    unsafe_fact = _business_fact_result(
        status="ok",
        resource_name="order",
        resource_type="order",
        resource_id="ORD-WRONG-TENANT-09",
    ).model_copy(update={"business_fact_refs": [_fact_ref("tenant-other", "order", "ORD-WRONG-TENANT-09")]})
    adapter = AsyncMock(return_value=unsafe_fact)
    service = BusinessFactService(AsyncMock(), adapters={"get_order": adapter})

    result = await service.get_order("ORD-WRONG-TENANT-09", _context())

    _assert_fail_closed(result, "unavailable")
    assert result.scope_check_result == "unknown"
    assert result.safe_errors[0].code == "BUSINESS_FACT_UNAVAILABLE"
    serialized = result.model_dump_json()
    assert "tenant-other" not in serialized
    assert "ORD-WRONG-TENANT-09" not in serialized


@pytest.mark.asyncio
async def test_business_fact_service_rejects_tool_success_with_wrong_tenant_ref() -> None:
    unsafe_tool_result = _result(
        data={"order_no": "ORD-WRONG-TENANT-09"},
        business_fact_refs=[_fact_ref("tenant-other", "order", "ORD-WRONG-TENANT-09")],
    )
    fact_adapter = AsyncMock(return_value=unsafe_tool_result)
    service = BusinessFactService(AsyncMock(), adapters={"get_order": fact_adapter})

    fact_result = await service.get_order("ORD-WRONG-TENANT-09", _context())

    _assert_fail_closed(fact_result, "unavailable")
    assert fact_result.scope_check_result == "unknown"
    assert fact_result.safe_errors[0].code == "BUSINESS_FACT_UNAVAILABLE"
    serialized_fact = fact_result.model_dump_json()
    assert "tenant-other" not in serialized_fact
    assert "ORD-WRONG-TENANT-09" not in serialized_fact

    tool_adapter = AsyncMock(return_value=unsafe_tool_result)
    tool_result = await BusinessToolService(AsyncMock(), adapters={"get_order": tool_adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-WRONG-TENANT-09"},
        _context(),
    )

    _assert_wrapped_tool_result_has_no_facts(
        tool_result,
        status="unavailable",
        code="BUSINESS_FACT_UNAVAILABLE",
    )
    serialized_tool = tool_result.model_dump_json()
    assert "tenant-other" not in serialized_tool
    assert "ORD-WRONG-TENANT-09" not in serialized_tool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain_status", "tool_status", "expected_code", "expected_message"),
    [
        ("permission_denied", "permission_denied", "BUSINESS_FACT_PERMISSION_DENIED", NO_LEAK_MESSAGE),
        ("stale", "unavailable", "BUSINESS_FACT_STALE", NO_LEAK_MESSAGE),
        ("unavailable", "unavailable", "BUSINESS_FACT_UNAVAILABLE", NO_LEAK_MESSAGE),
        ("invalid_request", "invalid_request", "BUSINESS_FACT_INVALID_REQUEST", "Business fact request is invalid"),
    ],
)
async def test_business_tool_service_wraps_domain_failures_without_facts_or_refs(
    domain_status: str,
    tool_status: str,
    expected_code: str,
    expected_message: str,
) -> None:
    adapter = AsyncMock(return_value=_business_fact_result(status=domain_status))

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-DENIED-09"},
        _context(),
    )

    _assert_wrapped_tool_result_has_no_facts(
        result,
        status=tool_status,
        code=expected_code,
        safe_message=expected_message,
    )
    serialized = result.model_dump_json()
    assert "ORD-DENIED-09" not in serialized
    assert "FORBIDDEN" not in serialized


@pytest.mark.asyncio
async def test_business_tool_service_wraps_not_found_without_facts_or_refs() -> None:
    adapter = AsyncMock(return_value=_business_fact_result(status="not_found"))

    result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
        "get_order",
        {"order_no": "ORD-MISSING-09"},
        _context(),
    )

    _assert_wrapped_tool_result_has_no_facts(
        result,
        status="not_found",
        code="BUSINESS_FACT_NOT_FOUND",
    )
    assert "ORD-MISSING-09" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("get_logistics", {"tracking_no": "TRACK-09"}),
        ("get_merchant_risk", {"merchant_id": "merchant-09"}),
    ],
)
async def test_business_tool_service_unsupported_catalog_reads_wrap_unavailable_domain_results(
    tool_name: str,
    args: dict[str, str],
) -> None:
    result = await BusinessToolService(AsyncMock()).invoke_tool(tool_name, args, _context())

    _assert_wrapped_tool_result_has_no_facts(
        result,
        status="unavailable",
        code="BUSINESS_FACT_UNAVAILABLE",
        safe_message=NO_LEAK_MESSAGE,
    )


@pytest.mark.asyncio
async def test_business_fact_service_allowed_reads_emit_domain_results(
    session: AsyncSession,
    seeded_session,
) -> None:
    service = BusinessFactService.with_default_registry(session)
    support_ctx = _seeded_context(seeded_session, "cs_zhang")
    admin_ctx = _seeded_context(seeded_session, "admin_user")

    order_result = await service.get_order("ORD-TEST-001", support_ctx)
    refund_result = await service.get_refund_case("RF-TEST-001", support_ctx)
    ticket_result = await service.get_ticket("TK-TEST-001", support_ctx)
    admin_cross_merchant = await service.get_order("ORD-TEST-002", admin_ctx)

    expected = [
        (order_result, "order", "ORD-TEST-001", "order_no", str(seeded_session["merchant"].id)),
        (refund_result, "refund_case", "RF-TEST-001", "refund_case_no", str(seeded_session["merchant"].id)),
        (ticket_result, "ticket", "TK-TEST-001", "ticket_no", str(seeded_session["merchant"].id)),
        (admin_cross_merchant, "order", "ORD-TEST-002", "order_no", str(seeded_session["second_merchant"].id)),
    ]
    for result, resource_type, resource_id, fact_key, merchant_id in expected:
        assert isinstance(result, BusinessFactResultV1)
        assert result.status == "ok"
        assert result.scope_check_result == "allowed"
        assert result.fact is not None
        assert result.fact[fact_key] == resource_id
        assert result.fact["merchant_id"] == merchant_id
        assert result.resource_version is None
        assert result.data_freshness_at is None
        assert len(result.business_fact_refs) == 1
        assert result.business_fact_refs[0].resource_type == resource_type
        assert result.business_fact_refs[0].resource_id == resource_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identifier", "ctx_updates"),
    [
        ("ORD-TEST-002", {}),
        ("ORD-TEST-001", {"merchant_scope": {"merchant_ids": []}}),
        ("ORD-TEST-001", {"role": "auditor"}),
    ],
)
async def test_business_fact_service_denials_are_generic_no_leak(
    session: AsyncSession,
    seeded_session,
    identifier: str,
    ctx_updates: dict,
) -> None:
    ctx = _seeded_context(seeded_session, "cs_zhang", **ctx_updates)

    result = await BusinessFactService.with_default_registry(session).get_order(identifier, ctx)

    _assert_fail_closed(result, "permission_denied")
    assert result.scope_check_result == "denied"
    assert result.missing_required_facts == ["order"]
    assert len(result.safe_errors) == 1
    assert result.safe_errors[0].code == "BUSINESS_FACT_PERMISSION_DENIED"
    assert result.safe_errors[0].safe_message == NO_LEAK_MESSAGE
    serialized = result.model_dump_json()
    assert identifier not in serialized
    assert "ORD-TEST-002" not in serialized
    assert "FORBIDDEN" not in serialized


@pytest.mark.asyncio
async def test_business_fact_service_cross_tenant_read_fails_closed_without_raw_details(
    session: AsyncSession,
    seeded_session,
) -> None:
    result = await BusinessFactService.with_default_registry(session).get_order(
        "ORD-OTHER-001",
        _seeded_context(seeded_session, "cs_zhang"),
    )

    _assert_fail_closed(result, "not_found")
    assert result.scope_check_result == "unknown"
    assert result.missing_required_facts == ["order"]
    serialized = result.model_dump_json()
    assert "ORD-OTHER-001" not in serialized
    assert "Other Shop" not in serialized


@pytest.mark.asyncio
async def test_business_fact_service_unsupported_reads_are_typed_unavailable() -> None:
    service = BusinessFactService(AsyncMock())
    ctx = _context()

    logistics = await service.get_logistics("TRACK-09", ctx)
    merchant_risk = await service.get_merchant_risk("merchant-09", ctx)

    for result, missing in [(logistics, "logistics"), (merchant_risk, "merchant_risk")]:
        _assert_fail_closed(result, "unavailable")
        assert result.scope_check_result == "not_applicable"
        assert result.missing_required_facts == [missing]
        assert result.safe_errors[0].code == "BUSINESS_FACT_UNAVAILABLE"
        assert result.safe_errors[0].safe_message == "Business fact is unavailable"


@pytest.mark.asyncio
async def test_business_fact_service_stale_double_fails_closed() -> None:
    stale_result = _business_fact_result(status="stale")
    adapter = AsyncMock(return_value=stale_result)
    service = BusinessFactService(AsyncMock(), adapters={"get_order": adapter})

    result = await service.get_order("ORD-09", _context())

    _assert_fail_closed(result, "stale")
    assert result.safe_errors[0].code == "BUSINESS_FACT_STALE"


@pytest.mark.asyncio
async def test_business_fact_service_fetch_context_aggregates_only_service_approved_facts() -> None:
    order_ref = _fact_ref(resource_type="order", resource_id="ORD-09")
    adapters = {
        "get_order": AsyncMock(
            return_value=_result(
                data={"order_no": "ORD-09"},
            ).model_copy(update={"business_fact_refs": [order_ref]})
        ),
        "get_refund_case": AsyncMock(
            return_value=_result("permission_denied", data=None, code="FORBIDDEN"),
        ),
        "get_ticket": AsyncMock(return_value=_business_fact_result(status="stale", resource_name="ticket")),
    }
    service = BusinessFactService(AsyncMock(), adapters=adapters)

    context = await service.fetch_context(
        {"order_id": "ORD-09", "refund_case_id": "RF-09", "ticket_id": "TK-09"},
        "refund_troubleshooting",
        _context(),
    )

    assert context.status == "partial"
    assert context.facts == {"order": {"order_no": "ORD-09"}}
    assert context.business_fact_refs == [order_ref]
    assert context.missing_required_facts == ["refund_case", "ticket"]
    assert [error.code for error in context.errors] == [
        "BUSINESS_FACT_PERMISSION_DENIED",
        "BUSINESS_FACT_STALE",
    ]
