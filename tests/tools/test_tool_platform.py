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
    caller_node: str = "investigate",
    permissions: list[str] | None = None,
    merchant_scope: Any | None = None,
    idempotency_key: str | None = None,
    safety_snapshot_ref: str | None = None,
    approval_ref: str | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
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
        data={"order_no": "ORD-1", "status": "shipped"},
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


def test_tool_result_projector_blocks_raw_data_from_prompt_and_graph_surfaces() -> None:
    from src.tools.projection import ToolResultProjector

    result = ToolResultV2(
        status="success",
        data={
            "order_no": "ORD-1",
            "status": "shipped",
            "raw": "internal ledger blob",
            "raw_payload": {"secret": "sk-xxx"},
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
                            "secret": "nested-policy-secret",
                        }
                    ],
                    "source_refs": [
                        {
                            "business_object_id": "refund-case-1",
                            "raw_payload": "nested-source-raw",
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
        "secret",
        "nested-policy-raw",
        "nested-policy-secret",
        "nested-source-raw",
        "nested-source-secret",
    ):
        assert forbidden not in dumped


def test_tool_result_projector_does_not_emit_events() -> None:
    # D-41: the projector must not own event emission.
    import inspect

    from src.tools.projection import ToolResultProjector

    source = inspect.getsource(ToolResultProjector)
    assert "emit_decision_event" not in source
