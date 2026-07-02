"""Phase 29 Wave 0 RED tests for the tool platform boundary (APF-06 / APF-07).

These tests lock the approved ``ToolViewV1`` prompt-safety, ``ToolPolicyDecision``
runtime authorization, ``ToolPlatform`` facade, ``ToolRuntime`` hard boundary, and
``ToolResultProjector`` projection behavior *before* the production contracts exist.

Top-level imports are limited to the Plan 29-02 contracts/policy engine so the file
collects as soon as 29-02 lands, letting the four contract tests run in 29-02's verify.
The ``ToolPlatform`` / ``ToolRuntime`` / ``ToolResultProjector`` imports (Plan 29-03)
are deferred into the tests that exercise them, so those tests stay RED until 29-03.

Failures must be missing-artifact failures (ImportError / AttributeError on the planned
symbols), never syntax errors or unrelated environment failures.
"""

from __future__ import annotations

import inspect
from typing import Any
from uuid import uuid4

import pytest

from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    ToolViewV1,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolInvocationOutcome,
    ToolResultV2,
    ToolCallContext,
)
from src.tools.policy import (
    TOOL_POLICY_CORE_REASON_CODES,
    ToolPolicyEngine,
    project_prompt_safe_input_schema,
    validate_tool_policy_reason_codes,
)
from src.platform.trusted_context import MerchantScopeV1


_FORBIDDEN_VIEW_FIELDS = {
    "schema_version",
    "risk_level",
    "side_effect",
    "required_permission",
    "caller_allowlist",
    "event_family",
    "resource_type",
    "executor",
    "exposure",
    "requires_approval",
    "requires_safety_snapshot",
    "requires_idempotency_key",
    "kind",
}

_PROMPT_SAFE_SCHEMA_KEYS = {
    "type",
    "properties",
    "required",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "enum",
    "description",
}

_FORBIDDEN_SCHEMA_KEYS = {
    "default",
    "examples",
    "x-internal",
    "x-permission",
    "x-resource-policy",
    "x-adapter",
    "required_permission",
    "caller_allowlist",
    "side_effect",
    "executor",
}

_RUNTIME_DENIAL_REASONS = {
    "caller_not_allowed",
    "missing_permission",
    "scope_denied",
    "side_effect_blocked",
    "schema_invalid",
    "approval_required",
    "safety_snapshot_required",
    "idempotency_required",
    "tool_unavailable",
}

_RAW_SENTINEL_KEYS = {
    "raw",
    "raw_payload",
    "raw_tool_payload",
    "raw_tool_output",
    "raw_args",
    "private_reasoning",
    "approval_authority_body",
    "debug_trace",
    "secret",
    "pii",
}

_RAW_SENTINEL_VALUES = {
    "internal ledger blob",
    "<upstream error text>",
    "raw tool payload blob",
    "model chain-of-thought",
    "authority body",
    "stack",
    "sk-xxx",
    "4111111111111111",
}


def _descriptor(name: str):
    return next(item for item in ToolCatalog().descriptors() if item.name == name)


def _ctx(
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    role: str = "support",
    caller_node: str = "investigate",
    permissions: list[str] | None = None,
    merchant_scope: Any | None = None,
    idempotency_key: str | None = None,
    safety_snapshot_ref: str | None = None,
    approval_ref: str | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=tenant_id or str(uuid4()),
        user_id=user_id or str(uuid4()),
        role=role,
        permissions=[f"tool:{name}" for name in ("get_order", "get_refund_case")] if permissions is None else permissions,
        merchant_scope=(
            merchant_scope.model_dump()
            if hasattr(merchant_scope, "model_dump")
            else merchant_scope if merchant_scope is not None
            else {"merchant_ids": ["*"]}
        ),
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        request_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node=caller_node,
        attempt=1,
        max_attempts=1,
        idempotency_key=idempotency_key,
        safety_snapshot_ref=safety_snapshot_ref,
        approval_ref=approval_ref,
        policy_snapshot_ref=None,
    )


def _business_permissions() -> list[str]:
    return [
        "tool:get_order",
        "tool:get_refund_case",
        "tool:get_ticket",
        "tool:get_logistics",
        "tool:get_merchant_risk",
    ]


def _seeded_ctx(seeded_session: dict, user_key: str = "cs_zhang") -> ToolCallContext:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"][user_key]
    merchant_scope = (
        {"merchant_ids": ["*"]}
        if user.role == "admin"
        else {"merchant_ids": [] if user.merchant_id is None else [str(user.merchant_id)]}
    )
    return _ctx(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        role=user.role,
        permissions=_business_permissions(),
        merchant_scope=merchant_scope,
    )


class _RecordingExecutor:
    """Thin executor adapter that records whether dispatch was reached."""

    def __init__(self, name: str | set[str], result: ToolResultV2) -> None:
        self._names = {name} if isinstance(name, str) else name
        self.result = result
        self.dispatched = False

    def has_tool(self, name: str) -> bool:
        return name in self._names

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        self.dispatched = True
        return self.result


def _success_result() -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={
            "order_no": "ORD-1",
            "merchant_id": "merchant-1",
            "status": "shipped",
            "amount": "100.00",
            "currency": "CNY",
            "buyer_name": "Buyer A",
            "item_name": "Item A",
            "paid_at": "2026-07-02T00:00:00Z",
            "delivered_at": None,
            "relation_hints": {
                "has_active_refund": False,
                "latest_refund_case_id": None,
                "has_open_ticket": False,
                "latest_ticket_id": None,
            },
        },
        summary="order shipped",
        source_system="business_tool_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref="audit-1",
    )


def _no_data_success_result() -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={},
        summary="no data payload",
        source_system="fake_tool_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


@pytest.mark.asyncio
async def test_output_schema_success_passes_tool_result_unchanged() -> None:
    from src.tools.platform import ToolPlatform

    result = _success_result()
    executor = _RecordingExecutor({"get_order"}, result)
    platform = ToolPlatform(executors={"business": executor})

    outcome = await platform.invoke(
        "get_order",
        {"order_no": "ORD-1"},
        _ctx(permissions=["tool:get_order"]),
        session=None,
    )

    assert executor.dispatched is True
    assert outcome.tool_result.status == "success"
    assert outcome.tool_result.data == result.data
    assert outcome.tool_result.summary == result.summary
    assert outcome.projection.normalized_result["order_no"] == "ORD-1"


@pytest.mark.asyncio
async def test_output_schema_failure_returns_invalid_response_without_raw_data() -> None:
    from src.tools.platform import ToolPlatform

    raw_sentinel = "RAW-OUTPUT-SCHEMA-SENTINEL"
    invalid = _success_result()
    assert invalid.data is not None
    invalid.data["raw_payload"] = raw_sentinel
    executor = _RecordingExecutor({"get_order"}, invalid)
    platform = ToolPlatform(executors={"business": executor})

    outcome = await platform.invoke(
        "get_order",
        {"order_no": "ORD-1"},
        _ctx(permissions=["tool:get_order"]),
        session=None,
    )

    assert executor.dispatched is True
    assert outcome.tool_result.status == "invalid_response"
    assert outcome.tool_result.data is None
    assert outcome.tool_result.error is not None
    assert outcome.tool_result.error.code == "INVALID_EXECUTOR_RESPONSE"
    assert raw_sentinel not in outcome.model_dump_json()
    assert raw_sentinel not in outcome.projection.model_dump_json()


@pytest.mark.asyncio
async def test_no_data_output_schema_rejects_accidental_unavailable_tool_payload() -> None:
    from src.tools.platform import ToolPlatform

    invalid = ToolResultV2(
        status="success",
        data={"raw_payload": "unexpected SOP payload"},
        summary="sop data should not exist yet",
        source_system="fake_knowledge_executor",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )
    executor = _RecordingExecutor({"search_sop"}, invalid)
    platform = ToolPlatform(executors={"knowledge": executor})

    outcome = await platform.invoke(
        "search_sop",
        {"query": "refund SOP"},
        _ctx(permissions=["tool:search_sop"]),
        session=None,
    )

    assert executor.has_tool("search_sop") is True
    assert executor.dispatched is True
    assert outcome.policy_decision.runtime_available is True
    assert outcome.tool_result.status == "invalid_response"
    assert outcome.tool_result.data is None
    assert outcome.tool_result.error is not None
    assert outcome.tool_result.error.code == "INVALID_EXECUTOR_RESPONSE"
    assert "unexpected SOP payload" not in outcome.model_dump_json()


def test_tool_result_v2_envelope_fields_are_unchanged() -> None:
    assert set(ToolResultV2.model_fields) == {
        "schema_version",
        "status",
        "data",
        "summary",
        "source_system",
        "data_freshness_at",
        "policy_evidence_refs",
        "business_fact_refs",
        "error",
        "retryable",
        "retry_after_ms",
        "latency_ms",
        "audit_ref",
    }


def test_tool_view_exposes_only_prompt_safe_fields() -> None:
    engine = ToolPolicyEngine()
    views = engine.tool_views_for_decisions(
        engine.visibility_decisions(caller="investigate", ctx=_ctx()),
    )
    assert views, "at least one ToolViewV1 must be visible for investigate"
    view = next(item for item in views if item.name == "get_order")

    dumped = view.model_dump()
    assert set(dumped.keys()) == {
        "name",
        "description",
        "input_schema",
        "safe_usage_notes",
        "result_contract_version",
    }
    assert view.result_contract_version == "tool_result.v2"
    for forbidden in _FORBIDDEN_VIEW_FIELDS:
        assert forbidden not in dumped
    assert "create_coupon_grant_draft" not in {item.name for item in views}


def test_prompt_safe_schema_projection_strips_descriptor_policy_and_adapter_metadata() -> None:
    raw_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "order_no": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "description": "Order identifier",
                "default": "ORD-?",
                "examples": ["ORD-1"],
                "x-internal": "ledger_ref",
                "x-permission": "orders:read",
                "x-resource-policy": "tenant_scoped",
                "x-adapter": "business_v1",
                "required_permission": "tool:get_order",
                "caller_allowlist": ["investigate"],
                "side_effect": "read_only",
                "executor": "business",
            }
        },
        "required": ["order_no"],
    }

    projected = project_prompt_safe_input_schema(raw_schema)

    assert projected["type"] == "object"
    assert projected["required"] == ["order_no"]
    field_schema = projected["properties"]["order_no"]
    assert set(field_schema.keys()) <= _PROMPT_SAFE_SCHEMA_KEYS
    for forbidden in _FORBIDDEN_SCHEMA_KEYS:
        assert forbidden not in field_schema
    assert field_schema["type"] == "string"
    assert field_schema["minLength"] == 1


def test_tool_policy_decision_is_not_an_event_envelope() -> None:
    decision = ToolPolicyDecision(
        tool_name="get_order",
        caller="investigate",
        decision_stage="runtime_auth",
        decision="denied",
        reason_codes=["missing_permission"],
        required_scopes=["tool:get_order"],
        matched_scope=None,
        policy_version="tool_policy.v1",
        data_classification="internal",
        resource_scope_binding=None,
        runtime_available=True,
        availability_summary=None,
    )
    dumped = decision.model_dump()
    for envelope_field in ("event_id", "sequence", "occurred_at", "run_id", "tenant_id"):
        assert envelope_field not in dumped
    assert dumped["schema_version"] == "tool_policy_decision.v1"
    assert dumped["decision_stage"] == "runtime_auth"

    with pytest.raises(Exception):
        ToolPolicyDecision(
            tool_name="get_order",
            caller="investigate",
            decision_stage="runtime_auth",
            decision="denied",
            reason_codes=["missing_permission"],
            required_scopes=["tool:get_order"],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            resource_scope_binding=None,
            runtime_available=True,
            availability_summary=None,
            event_id="must-be-rejected",
        )


def test_visibility_stage_forbids_runtime_only_reason_codes() -> None:
    decisions = ToolPolicyEngine().visibility_decisions(caller="investigate", ctx=_ctx())
    runtime_only = {"schema_invalid", "approval_required", "safety_snapshot_required", "idempotency_required"}
    for decision in decisions:
        assert not (set(decision.reason_codes) & runtime_only), (
            "visibility decisions must not carry runtime-only reason codes"
        )
        assert decision.decision_stage == "visibility"


def test_tool_policy_reason_codes_enforce_core_or_namespaced_extension() -> None:
    assert "visible" in TOOL_POLICY_CORE_REASON_CODES
    assert _RUNTIME_DENIAL_REASONS <= TOOL_POLICY_CORE_REASON_CODES

    validate_tool_policy_reason_codes(["visible", "missing_permission", "business.permission_denied"])

    with pytest.raises(Exception):
        validate_tool_policy_reason_codes(["freeform_unknown_code"])
    with pytest.raises(Exception):
        validate_tool_policy_reason_codes(["business.UPPER"])
    with pytest.raises(Exception):
        validate_tool_policy_reason_codes(["business"])
    with pytest.raises(Exception):
        validate_tool_policy_reason_codes([".business.permission_denied"])


def test_runtime_denial_matrix_covers_all_required_reason_codes() -> None:
    # D-12: the core reason-code enum must cover every runtime denial path.
    assert _RUNTIME_DENIAL_REASONS <= TOOL_POLICY_CORE_REASON_CODES


def test_runtime_auth_gate_sequence_is_declarative_and_ordered() -> None:
    gates = ToolPolicyEngine()._runtime_auth_gates

    assert [gate.name for gate in gates] == [
        "caller_allowlist",
        "permission",
        "side_effect",
        "resource_scope",
        "approval",
        "safety_snapshot",
        "idempotency",
    ]


def test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order() -> None:
    decision = ToolPolicyEngine().runtime_auth(
        tool_name="create_coupon_grant_draft",
        args={"merchant_id": "M-DENIED"},
        ctx=_ctx(
            caller_node="investigate",
            permissions=[],
            merchant_scope=MerchantScopeV1(merchant_ids=["M-ALLOWED"]),
        ),
        availability_map={"create_coupon_grant_draft": True},
    )

    assert decision.decision == "denied"
    assert decision.reason_codes == [
        "caller_not_allowed",
        "missing_permission",
        "side_effect_blocked",
        "scope_denied",
        "safety_snapshot_required",
        "idempotency_required",
    ]


@pytest.mark.asyncio
async def test_visible_tools_records_hidden_and_unavailable_decisions_outside_prompt() -> None:
    from src.tools.platform import ToolPlatform

    catalog = ToolCatalog()
    # Make get_order unavailable by supplying an executor registry that lacks it.
    platform = ToolPlatform(catalog=catalog, executors={})
    views = await platform.visible_tools(caller="investigate", ctx=_ctx(), session=None)

    assert isinstance(views, list)
    assert all(isinstance(view, ToolViewV1) for view in views)
    visible_names = {view.name for view in views}
    assert "get_order" not in visible_names
    assert "create_coupon_grant_draft" not in visible_names
    write_descriptor = _descriptor("create_coupon_grant_draft")
    assert write_descriptor.exposure == "node_only"
    # Hidden / unavailable decisions are recorded outside the returned prompt views.
    visibility_events = getattr(platform, "last_visibility_decisions", None)
    assert visibility_events is not None, "ToolPlatform must retain/emit visibility decisions outside the prompt"
    decisions_by_name = {decision.tool_name: decision for decision in visibility_events}
    assert {"get_order", "create_coupon_grant_draft"} <= set(decisions_by_name)

    get_order_decision = decisions_by_name["get_order"]
    assert get_order_decision.decision_stage == "visibility"
    assert get_order_decision.decision == "hidden"
    assert get_order_decision.runtime_available is False
    assert "tool_unavailable" in get_order_decision.reason_codes

    draft_decision = decisions_by_name["create_coupon_grant_draft"]
    assert draft_decision.decision_stage == "visibility"
    assert draft_decision.decision == "hidden"
    assert "hidden_by_policy" in draft_decision.reason_codes


@pytest.mark.asyncio
async def test_runtime_auth_rechecks_visible_tool_before_dispatch() -> None:
    from src.tools.platform import ToolPlatform

    executor = _RecordingExecutor({"get_order", "get_merchant_risk"}, _success_result())
    platform = ToolPlatform(executors={"business": executor})

    # Visible tool, but caller lacks the required permission -> denied before dispatch.
    denied_ctx = _ctx(permissions=[])
    outcome = await platform.invoke("get_order", {"order_no": "ORD-1"}, denied_ctx, session=None)

    assert isinstance(outcome, ToolInvocationOutcome)
    assert outcome.tool_result.status == "permission_denied"
    assert outcome.policy_decision.decision_stage == "runtime_auth"
    assert outcome.policy_decision.decision == "denied"
    assert "missing_permission" in outcome.policy_decision.reason_codes
    assert executor.dispatched is False

    # Explicit out-of-scope merchant_id must also deny before dispatch.
    scoped_ctx = _ctx(
        permissions=["tool:get_merchant_risk"],
        merchant_scope=MerchantScopeV1(merchant_ids=["M-ALLOWED"]),
    )
    outcome = await platform.invoke(
        "get_merchant_risk",
        {"merchant_id": "M-DENIED"},
        scoped_ctx,
        session=None,
    )
    assert outcome.tool_result.status == "permission_denied"
    assert "scope_denied" in outcome.policy_decision.reason_codes
    assert outcome.policy_decision.decision == "denied"


def test_tool_runtime_failure_paths_use_shared_fail_helper() -> None:
    from src.tools.runtime import ToolRuntime

    runtime_source = inspect.getsource(ToolRuntime)
    invoke_source = inspect.getsource(ToolRuntime.invoke)

    assert "async def _fail(" in runtime_source
    assert invoke_source.count("await self._fail(") >= 7


@pytest.mark.asyncio
async def test_tool_runtime_failure_projection_redacts_raw_sentinel_inputs() -> None:
    from src.tools.platform import ToolPlatform

    raw_sentinel = "RAW-RUNTIME-SENTINEL"
    platform = ToolPlatform.with_defaults(None)

    invalid_input_outcome = await platform.invoke(
        "get_order",
        {"order_no": "", "raw_args": raw_sentinel},
        _ctx(permissions=["tool:get_order"]),
        session=None,
    )
    missing_tool_outcome = await platform.invoke(
        "missing_tool",
        {"raw_args": raw_sentinel},
        _ctx(),
        session=None,
    )

    assert invalid_input_outcome.tool_result.status == "invalid_request"
    assert missing_tool_outcome.tool_result.status == "not_found"
    assert isinstance(invalid_input_outcome.projection, ToolResultProjectionV1)
    assert isinstance(missing_tool_outcome.projection, ToolResultProjectionV1)
    assert raw_sentinel not in invalid_input_outcome.model_dump_json()
    assert raw_sentinel not in missing_tool_outcome.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("merchant_scope", "expected_status", "expected_decision", "expected_dispatched"),
    [
        (["M-ALLOWED"], "success", "allowed", True),
        (["M-OTHER"], "permission_denied", "denied", False),
    ],
)
async def test_runtime_auth_handles_legacy_list_merchant_scope(
    merchant_scope: list[str],
    expected_status: str,
    expected_decision: str,
    expected_dispatched: bool,
) -> None:
    from src.tools.platform import ToolPlatform

    executor = _RecordingExecutor({"get_merchant_risk"}, _no_data_success_result())
    platform = ToolPlatform(executors={"business": executor})

    outcome = await platform.invoke(
        "get_merchant_risk",
        {"merchant_id": "M-ALLOWED"},
        _ctx(permissions=["tool:get_merchant_risk"], merchant_scope=merchant_scope),
        session=None,
    )

    assert outcome.tool_result.status == expected_status
    assert outcome.policy_decision.decision == expected_decision
    assert executor.dispatched is expected_dispatched
    if expected_decision == "denied":
        assert "scope_denied" in outcome.policy_decision.reason_codes


def test_business_tool_executor_source_uses_business_fact_service_boundary() -> None:
    import src.tools.executors.business as business_executor_module

    source = inspect.getsource(business_executor_module)

    assert "BusinessFactService" in source
    for forbidden in (
        "src.integrations.demo_business",
        "src.repositories",
        "OrderRepository",
        "RefundRepository",
        "TicketRepository",
    ):
        assert forbidden not in source


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "args", "resource_type", "resource_id"),
    [
        ("get_order", {"order_no": "ORD-TEST-001"}, "order", "ORD-TEST-001"),
        ("get_refund_case", {"refund_case_no": "RF-TEST-001"}, "refund_case", "RF-TEST-001"),
        ("get_ticket", {"ticket_id": "TK-TEST-001"}, "ticket", "TK-TEST-001"),
    ],
)
async def test_tool_platform_business_reads_use_service_approved_refs_and_domain_scope_marker(
    session,
    seeded_session: dict,
    tool_name: str,
    args: dict[str, str],
    resource_type: str,
    resource_id: str,
) -> None:
    from src.tools.platform import ToolPlatform

    platform = ToolPlatform.with_defaults(session)

    outcome = await platform.invoke(tool_name, args, _seeded_ctx(seeded_session), session=None)

    assert outcome.policy_decision.decision == "allowed"
    assert outcome.policy_decision.resource_scope_binding == {"requires_domain_scope_check": True}
    assert outcome.tool_result.status == "success"
    assert outcome.tool_result.data is not None
    assert outcome.tool_result.policy_evidence_refs == []
    assert len(outcome.tool_result.business_fact_refs) == 1
    ref = outcome.tool_result.business_fact_refs[0]
    assert ref.resource_type == resource_type
    assert ref.resource_id == resource_id


@pytest.mark.asyncio
async def test_tool_platform_business_read_domain_scope_denial_is_no_leak(
    session,
    seeded_session: dict,
) -> None:
    from src.tools.platform import ToolPlatform

    platform = ToolPlatform.with_defaults(session)

    outcome = await platform.invoke(
        "get_order",
        {"order_no": "ORD-TEST-002"},
        _seeded_ctx(seeded_session),
        session=None,
    )

    assert outcome.policy_decision.decision == "allowed"
    assert outcome.policy_decision.resource_scope_binding == {"requires_domain_scope_check": True}
    assert outcome.tool_result.status == "permission_denied"
    assert outcome.tool_result.data is None
    assert outcome.tool_result.business_fact_refs == []
    assert outcome.tool_result.policy_evidence_refs == []
    assert outcome.tool_result.error is not None
    assert outcome.tool_result.error.code == "BUSINESS_FACT_PERMISSION_DENIED"
    assert outcome.tool_result.error.safe_message == "Business resource unavailable for this request"
    assert "ORD-TEST-002" not in outcome.model_dump_json()
    assert "ORD-TEST-002" not in outcome.projection.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("get_logistics", {"tracking_no": "TRACK-09"}),
        ("get_merchant_risk", {"merchant_id": "*"}),
    ],
)
async def test_tool_platform_unsupported_business_reads_are_safe_unavailable(
    session,
    seeded_session: dict,
    tool_name: str,
    args: dict[str, str],
) -> None:
    from src.tools.platform import ToolPlatform

    platform = ToolPlatform.with_defaults(session)

    outcome = await platform.invoke(tool_name, args, _seeded_ctx(seeded_session, "admin_user"), session=None)

    assert outcome.policy_decision.decision == "allowed"
    assert outcome.tool_result.status == "unavailable"
    assert outcome.tool_result.data is None
    assert outcome.tool_result.business_fact_refs == []
    assert outcome.tool_result.policy_evidence_refs == []
    assert outcome.tool_result.error is not None
    assert outcome.tool_result.error.code == "BUSINESS_FACT_UNAVAILABLE"


def test_tool_result_projector_blocks_raw_data_from_prompt_and_graph_surfaces() -> None:
    from src.tools.projection import ToolResultProjector

    result = ToolResultV2(
        status="success",
        data={
            "order_no": "ORD-1",
            "status": "shipped",
            "merchant_id": "merchant-1",
            "raw": "internal ledger blob",
            "raw_payload": {"secret": "sk-xxx"},
            "raw_tool_payload": "raw tool payload blob",
            "raw_tool_output": "<upstream error text>",
            "private_reasoning": "model chain-of-thought",
            "approval_authority_body": "authority body",
            "debug_trace": "stack",
            "secret": "sk-xxx",
            "pii": "4111111111111111",
        },
        summary="order shipped",
        source_system="business_tool_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref="audit-1",
    )

    projection = ToolResultProjector().project(
        tool_name="get_order",
        result=result,
        tool_call_id="tc-1",
        tool_result_id="tr-1",
    )

    assert isinstance(projection, ToolResultProjectionV1)

    def _has_sentinel(value: Any) -> bool:
        if isinstance(value, dict):
            return any(key in _RAW_SENTINEL_KEYS or _has_sentinel(child) for key, child in value.items())
        if isinstance(value, list):
            return any(_has_sentinel(item) for item in value)
        if isinstance(value, str):
            return any(sentinel in value for sentinel in _RAW_SENTINEL_VALUES)
        return False

    assert not _has_sentinel(projection.normalized_result), "normalized_result must strip raw sentinels"
    assert not _has_sentinel(projection.prompt_projection), "prompt_projection must strip raw sentinels"
    assert not _has_sentinel(projection.text_for_prompt), "text_for_prompt must strip raw sentinels"
    assert not _has_sentinel(projection.debug_projection), "debug_projection must strip raw sentinels"
    assert projection.normalized_result.get("order_no") == "ORD-1"
    assert projection.normalized_result.get("merchant_id") == "merchant-1"


def test_tool_result_projector_strips_raw_sentinels_from_case_memory_ref_lists() -> None:
    from src.tools.projection import ToolResultProjector

    result = ToolResultV2(
        status="success",
        data={
            "items": [
                {
                    "case_memory_id": "case-memory-1",
                    "excerpt": "Reviewed refund timeout precedent.",
                    "policy_refs": [
                        {
                            "doc_key": "refund_policy",
                            "chunk_id": "chunk-1",
                            "raw_payload": "nested-policy-raw",
                            "raw_tool_payload": "nested-policy-tool-raw",
                            "secret": "nested-policy-secret",
                        }
                    ],
                    "source_refs": [
                        {
                            "business_object_id": "refund-case-1",
                            "raw_payload": "nested-source-raw",
                            "raw_tool_payload": "nested-source-tool-raw",
                            "secret": "nested-source-secret",
                        }
                    ],
                }
            ],
        },
        summary="case memory found",
        source_system="case_memory_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )

    projection = ToolResultProjector().project(
        tool_name="search_case_memory",
        result=result,
        tool_call_id="tc-1",
        tool_result_id="tr-1",
    )

    case_memory = projection.normalized_result["_case_memory_items"]
    assert case_memory[0]["policy_refs"] == [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}]
    assert case_memory[0]["source_refs"] == [{"business_object_id": "refund-case-1"}]
    dumped = str(projection.normalized_result)
    for forbidden in (
        "raw_payload",
        "raw_tool_payload",
        "secret",
        "nested-policy-raw",
        "nested-policy-tool-raw",
        "nested-policy-secret",
        "nested-source-raw",
        "nested-source-tool-raw",
        "nested-source-secret",
    ):
        assert forbidden not in dumped


def test_tool_result_projector_does_not_emit_events() -> None:
    # D-41: the projector must not own event emission.
    import inspect

    from src.tools.projection import ToolResultProjector

    source = inspect.getsource(ToolResultProjector)
    assert "emit_decision_event" not in source
