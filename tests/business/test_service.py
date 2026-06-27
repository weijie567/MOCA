from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import _project_tool_result
from src.business.schemas import BusinessFactResultV1
from src.business.service import (
    BUSINESS_READ_TOOLS,
    BusinessFactService,
    BusinessReadToolDefinition,
    BusinessToolService,
    _merchant_scope_allows,
)
from src.integrations.demo_business.authz import merchant_can_access
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
        (order_result, "order", "ORD-TEST-001", "order_no"),
        (refund_result, "refund_case", "RF-TEST-001", "refund_case_no"),
        (ticket_result, "ticket", "TK-TEST-001", "ticket_no"),
        (admin_cross_merchant, "order", "ORD-TEST-002", "order_no"),
    ]
    for result, resource_type, resource_id, fact_key in expected:
        assert isinstance(result, BusinessFactResultV1)
        assert result.status == "ok"
        assert result.scope_check_result == "allowed"
        assert result.fact is not None
        assert result.fact[fact_key] == resource_id
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
