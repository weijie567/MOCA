# Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation - Pattern Map

**Mapped:** 2026-07-01  
**Files analyzed:** 8  
**Analogs found:** 8 / 8  
**Project skill indexes:** none found under `.claude/skills/` or `.agents/skills/`

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/tools/catalog.py` | config / model registry | transform | `src/tools/catalog.py` | exact |
| `src/tools/manager.py` | compatibility adapter | request-response / transform | `src/tools/manager.py` + `src/tools/platform.py` | exact |
| `src/tools/runtime.py` | service | request-response / event-driven | `src/tools/runtime.py` + `src/tools/manager_results.py` | exact |
| `src/tools/policy.py` | service / policy | request-response / transform | `src/tools/policy.py` + `src/approvals/policy.py` | exact / role-match |
| `tests/tools/test_catalog.py` | test | structural / transform | `tests/tools/test_catalog.py` | exact |
| `tests/tools/test_tool_platform.py` | test | request-response / event-driven | `tests/tools/test_tool_platform.py` | exact |
| `tests/agent/test_tools/test_unified_tool_manager.py` | test | compatibility / request-response | `tests/agent/test_tools/test_unified_tool_manager.py` | exact |
| `tests/replay/test_tool_policy_events.py` | test | event-driven | `tests/replay/test_tool_policy_events.py` | exact |

## Pattern Assignments

### `src/tools/catalog.py` (config / model registry, transform)

**Analog:** `src/tools/catalog.py`

**Imports and model contract pattern** (lines 5-15):
```python
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.tools.contracts import ToolError, ToolResultV2


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

**Descriptor field surface to preserve** (lines 17-32):
```python
name: str
description: str = ""
kind: Literal["read", "retrieval", "write"]
input_schema: dict[str, Any]
output_schema: dict[str, Any]
risk_level: Literal["read", "retrieval", "write"]
side_effect: Literal["none", "read_only", "retrieval", "write"]
required_permission: str
caller_allowlist: list[str]
event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
resource_type: str | None
executor: Literal["business", "knowledge", "memory", "action"] | None = None
exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
requires_approval: bool = False
requires_safety_snapshot: bool = False
requires_idempotency_key: bool = False
```

**Current drift point to eliminate or derive/check** (lines 41-43, 89-109):
```python
_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
_IDENTIFIER_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_order": {
        ...
    "create_coupon_grant_draft": {
        "type": "object",
        "properties": {
            "approval_request_id": {"type": "string", "minLength": 1},
            ...
        },
        "required": ["action_type", "payload", "action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"],
    },
}
```

**Descriptor derivation pattern to keep stable** (lines 113-145):
```python
def _descriptor(
    name: str,
    *,
    description: str = "",
    kind: Literal["read", "retrieval", "write"],
    side_effect: Literal["read_only", "retrieval", "write"],
    caller_allowlist: list[str],
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None,
    resource_type: str | None,
    executor: Literal["business", "knowledge", "memory", "action"] | None = None,
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible",
    requires_approval: bool = False,
    requires_safety_snapshot: bool = False,
    requires_idempotency_key: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        kind=kind,
        input_schema=_IDENTIFIER_SCHEMAS[name],
        output_schema=_GENERIC_OBJECT_SCHEMA,
        risk_level=kind,
        side_effect=side_effect,
        required_permission=f"tool:{name}",
        caller_allowlist=caller_allowlist,
        event_family=event_family,
        resource_type=resource_type,
        executor=executor,
        exposure=exposure,
        requires_approval=requires_approval,
        requires_safety_snapshot=requires_safety_snapshot,
        requires_idempotency_key=requires_idempotency_key,
    )
```

**Registry list pattern to replace with single-source rows** (lines 148-238):
```python
def _default_descriptors() -> list[ToolDescriptor]:
    return [
        _descriptor(
            "get_order",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="order",
            executor="business",
        ),
        ...
        _descriptor(
            "create_coupon_grant_draft",
            kind="write",
            side_effect="write",
            caller_allowlist=["action_draft"],
            event_family="action",
            resource_type=None,
            executor="action",
            exposure="node_only",
            requires_safety_snapshot=True,
            requires_idempotency_key=True,
        ),
    ]
```

**Catalog uniqueness and descriptor API pattern** (lines 241-260):
```python
class ToolCatalog:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        if tools is None:
            registered_tools = [RegisteredTool(descriptor=descriptor) for descriptor in _default_descriptors()]
        else:
            registered_tools = list(tools)

        self._tools: dict[str, RegisteredTool] = {}
        for tool in registered_tools:
            name = tool.descriptor.name
            if name in self._tools:
                raise ValueError(f"Duplicate tool registry entry: {name}")
            self._tools[name] = tool

    def descriptors(self) -> list[ToolDescriptor]:
        return [tool.descriptor for tool in self._tools.values()]

    def descriptor(self, name: str) -> ToolDescriptor | None:
        tool = self._tools.get(name)
        return tool.descriptor if tool else None
```

**Planner action:** introduce a single internal row/table that includes all descriptor fields plus `input_schema`. Derive `ToolDescriptor` from rows. Keep `_GENERIC_OBJECT_SCHEMA` unchanged for Phase 37; real output schemas belong to Phase 38.

---

### `src/tools/manager.py` (compatibility adapter, request-response / transform)

**Analog:** `src/tools/manager.py`; delegation boundary in `src/tools/platform.py`.

**Current duplicated investigate set** (lines 17-26):
```python
INVESTIGATE_TOOL_NAMES = {
    "get_order",
    "get_refund_case",
    "get_ticket",
    "get_logistics",
    "get_merchant_risk",
    "search_policy",
    "search_sop",
    "search_case_memory",
}
```

**Adapter construction pattern** (lines 42-57):
```python
catalog = descriptors if descriptors is not None else ToolCatalog().descriptors()
self._descriptors = {descriptor.name: descriptor for descriptor in catalog}
self._executors = self._executor_registry(executors or {})
if descriptors is not None:
    platform_catalog = ToolCatalog(
        tools=[RegisteredTool(descriptor=d) for d in descriptors]
    )
else:
    platform_catalog = ToolCatalog()
self._platform = ToolPlatform(
    catalog=platform_catalog,
    executors=self._executors,
)
```

**Descriptor compatibility filter to preserve while removing second hand-maintained list** (lines 70-80):
```python
def descriptors(self, caller_node: str = "investigate") -> list[ToolDescriptor]:
    if caller_node == "investigate":
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist
            and descriptor.name in INVESTIGATE_TOOL_NAMES
            and descriptor.kind != "write"
            and descriptor.exposure == "planner_visible"
        ]
    return [descriptor for descriptor in self._descriptors.values() if caller_node in descriptor.caller_allowlist]
```

**Platform delegation compatibility pattern** (lines 82-98):
```python
async def visible_tools(
    self,
    *,
    caller: str,
    ctx: ToolCallContext,
    session: Any = None,
) -> list[ToolViewV1]:
    """Delegate to ToolPlatform for prompt-safe planner visibility."""
    return await self._platform.visible_tools(caller=caller, ctx=ctx, session=session)

async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    """Delegate to ToolPlatform.invoke and return the ToolResultV2 for backward compat."""
    outcome = await self._platform.invoke(name, args, ctx, session=None)
    return outcome.tool_result
```

**Side-effect helper pattern already present** (lines 136-141):
```python
def _side_effect_allowed(caller_node: str, descriptor: ToolDescriptor) -> bool:
    if caller_node == "investigate":
        return descriptor.kind != "write" and descriptor.side_effect in {"read_only", "retrieval"}
    if caller_node == "action_draft":
        return descriptor.kind == "write" and descriptor.side_effect == "write"
    return descriptor.side_effect in {"none", "read_only", "retrieval"}
```

**Facade analog:** `src/tools/platform.py` (lines 112-133):
```python
async def invoke(
    self,
    tool_name: str,
    args: dict[str, Any],
    ctx: ToolCallContext,
    *,
    session: AsyncSession | None = None,
) -> ToolInvocationOutcome:
    tool_result, policy_decision, policy_event_id, projection = await self._runtime.invoke(
        tool_name, args, ctx, session=session,
    )
    return ToolInvocationOutcome(
        tool_result=tool_result,
        projection=projection,
        policy_decision=policy_decision,
        policy_event_id=policy_event_id,
    )
```

**Planner action:** keep `UnifiedToolManager` as a compatibility adapter. Derive any retained `INVESTIGATE_TOOL_NAMES` from catalog descriptors matching `caller_allowlist`, non-write `kind`, and `planner_visible` exposure; do not move runtime or policy ownership into this file.

---

### `src/tools/runtime.py` (service, request-response / event-driven)

**Analog:** `src/tools/runtime.py`; safe envelope helper in `src/tools/manager_results.py`.

**Imports pattern** (lines 7-19):
```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    ToolCallContext,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolResultV2,
)
from src.tools.manager_results import result as safe_result
from src.tools.policy import ToolPolicyEngine
from src.tools.projection import ToolResultProjector
from src.tools.validation import validate_json_value
```

**Gate-order invariant** (lines 22-37):
```python
class ToolRuntime:
    """Centralizes the runtime invocation chain.

    Gate order:
    1. Descriptor lookup
    2. Input schema validation (BEFORE runtime_auth — unvalidated args must
       never enter resource_scope_binding or decision event resource_refs)
    3. Runtime auth decision (ToolPolicyEngine.runtime_auth)
    4. Side-effect gate (already in runtime_auth)
    5. Approval/safety/idempotency gates (already in runtime_auth)
    6. Executor dispatch
    7. Output schema validation
    8. Result projection (ToolResultProjector)
    9. Safe error mapping
    10. Decision event emission
    """
```

**Failure branch shape to consolidate into `_fail(...)`** (lines 80-90):
```python
error_result = safe_result(
    "not_found", "Requested tool is not registered",
    code="TOOL_NOT_FOUND", source="caller",
)
projection = self._projector.project(
    tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
)
event_id = await self._emit_decision_event(
    decision=decision, ctx=ctx, session=session,
)
return error_result, decision, event_id, projection
```

**Additional repeated failure branches to route through `_fail(...)`**:

| Branch | Lines | Preserve status/code/source |
|--------|-------|-----------------------------|
| invalid input | 94-112 | `invalid_request` / `INVALID_TOOL_INPUT` / `caller` |
| runtime policy denial | 123-131 | `_safe_denial_result(decision)` |
| executor unavailable | 135-153 | `unavailable` / `TOOL_UNAVAILABLE` / `tool` |
| executor exception | 155-168 | `error` / `EXECUTOR_ERROR` / `adapter` |
| malformed executor return | 170-181 | `invalid_response` / `INVALID_EXECUTOR_RESPONSE` / `adapter` |
| output schema failure | 183-198 | `invalid_response` / `INVALID_EXECUTOR_RESPONSE` / `adapter` |

**Success path tuple pattern must remain unchanged** (lines 200-210):
```python
projection = self._projector.project(
    tool_name=tool_name, result=tool_result, tool_call_id=ctx.tool_call_id,
)
event_id = await self._emit_decision_event(
    decision=decision, ctx=ctx, session=session,
)

return tool_result, decision, event_id, projection
```

**Policy denial mapping pattern** (lines 250-272):
```python
def _safe_denial_result(self, decision: ToolPolicyDecision) -> ToolResultV2:
    code_map = {
        "caller_not_allowed": "CALLER_NOT_ALLOWED",
        "missing_permission": "PERMISSION_REQUIRED",
        "scope_denied": "SCOPE_DENIED",
        "side_effect_blocked": "SIDE_EFFECT_BLOCKED",
        "schema_invalid": "INVALID_TOOL_INPUT",
        "approval_required": "APPROVAL_REQUIRED",
        "safety_snapshot_required": "SAFETY_SNAPSHOT_REQUIRED",
        "idempotency_required": "IDEMPOTENCY_KEY_REQUIRED",
        "tool_unavailable": "TOOL_UNAVAILABLE",
    }
    status_map = {
        "tool_unavailable": "unavailable",
        "schema_invalid": "invalid_request",
        "idempotency_required": "invalid_request",
    }
    primary_reason = decision.reason_codes[0] if decision.reason_codes else "tool_unavailable"
    code = code_map.get(primary_reason, "POLICY_DENIED")
    message = f"Tool invocation denied: {primary_reason}"
    status = status_map.get(primary_reason, "permission_denied")
    return safe_result(status, message, code=code, source="policy")
```

**Runtime auth decision event pattern** (lines 274-315):
```python
async def _emit_decision_event(
    self,
    *,
    decision: ToolPolicyDecision,
    ctx: ToolCallContext,
    session: AsyncSession | None,
) -> str | None:
    if session is None:
        return None

    from src.replay.decision_events import emit_decision_event

    try:
        event = await emit_decision_event(
            session,
            run_id=ctx.run_id,
            tenant_id=ctx.tenant_id,
            thread_id=ctx.thread_id,
            event_type="tool_policy_runtime_auth_recorded",
            actor={"type": "agent", "id": "moca"},
            resource_refs={
                "tool_name": decision.tool_name,
                "tool_call_id": ctx.tool_call_id,
                "resource_type": "tool",
            },
            redacted_payload={
                "decision_stage": decision.decision_stage,
                "tool_name": decision.tool_name,
                "decision": decision.decision,
                "reason_codes": decision.reason_codes,
                "policy_version": decision.policy_version,
                "data_classification": decision.data_classification,
                "runtime_available": decision.runtime_available,
            },
            reason_codes=decision.reason_codes,
            versions={"policy_version": decision.policy_version},
        )
        return str(event.get("event_id")) if event else None
    except Exception:
        return None
```

**Safe result helper to reuse**: `src/tools/manager_results.py` (lines 8-29):
```python
def result(
    status: Literal["not_found", "permission_denied", "unavailable", "invalid_request", "invalid_response", "error"],
    summary: str,
    *,
    code: str,
    source: Literal["caller", "tool", "adapter", "policy"] = "caller",
    source_system: str = "unified_tool_manager",
) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=summary,
        source_system=source_system,
        ...
        error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
        ...
    )
```

**Planner action:** add private async `_fail(...)` near `_safe_denial_result` / `_emit_decision_event`. It should accept `tool_name`, `ctx`, `decision`, `session`, and either a prebuilt `ToolResultV2` or safe-result parameters, then project, emit, and return `(ToolResultV2, ToolPolicyDecision, str | None, ToolResultProjectionV1)`.

---

### `src/tools/policy.py` (service / policy, request-response / transform)

**Analog:** `src/tools/policy.py`; immutable policy helper shape in `src/approvals/policy.py`.

**Imports and reason-code contract pattern** (lines 5-37):
```python
import re
from typing import Any

from src.platform.trusted_context import MerchantScopeV1
from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import (
    ToolCallContext,
    ToolPolicyDecision,
    ToolViewV1,
)

TOOL_POLICY_CORE_REASON_CODES: frozenset[str] = frozenset({
    "visible",
    "hidden_by_policy",
    "caller_not_allowed",
    "missing_permission",
    "scope_denied",
    "side_effect_blocked",
    "schema_invalid",
    "approval_required",
    "safety_snapshot_required",
    "idempotency_required",
    "tool_unavailable",
})
```

**Prompt-safe schema projection pattern must remain separate from runtime gates** (lines 108-142):
```python
def project_prompt_safe_input_schema(raw_schema: dict[str, Any]) -> dict[str, Any]:
    return _project_schema_node(raw_schema)

def _project_schema_node(node: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, value in node.items():
        if key in _INTERNAL_SCHEMA_KEYS:
            continue
        ...
        if key in _PROMPT_SAFE_SCHEMA_KEYS:
            projected[key] = value
    return projected
```

**Current runtime-auth if-chain to replace with an ordered declarative sequence** (lines 280-366):
```python
def runtime_auth(
    self,
    *,
    tool_name: str,
    args: dict[str, Any],
    ctx: ToolCallContext,
    availability_map: dict[str, bool] | None = None,
) -> ToolPolicyDecision:
    available = availability_map or {}
    descriptor = self._catalog.descriptor(tool_name)

    if descriptor is None:
        return self._denied_decision(...)

    is_available = available.get(tool_name, True)
    if not is_available:
        return self._denied_decision(...)

    reason_codes: list[str] = []

    if ctx.caller_node not in descriptor.caller_allowlist:
        reason_codes.append("caller_not_allowed")
    if descriptor.required_permission not in ctx.permissions:
        reason_codes.append("missing_permission")
    if descriptor.side_effect == "write":
        if not (ctx.caller_node == "action_draft" and descriptor.kind == "write"):
            reason_codes.append("side_effect_blocked")
    resource_scope_binding = self._build_resource_binding(args, ctx)
    if resource_scope_binding.get("_scope_denied"):
        reason_codes.append("scope_denied")
    if descriptor.requires_approval and not ctx.approval_ref:
        reason_codes.append("approval_required")
    if descriptor.requires_safety_snapshot and not ctx.safety_snapshot_ref:
        reason_codes.append("safety_snapshot_required")
    if descriptor.requires_idempotency_key and not ctx.idempotency_key:
        reason_codes.append("idempotency_required")
```

**Denied decision factory pattern** (lines 368-392):
```python
def _denied_decision(
    self,
    *,
    tool_name: str,
    caller: str,
    reason_codes: list[str],
    required_scopes: list[str],
    resource_scope_binding: dict[str, Any] | None = None,
    runtime_available: bool | None = None,
    availability_summary: str | None = None,
) -> ToolPolicyDecision:
    return ToolPolicyDecision(
        tool_name=tool_name,
        caller=caller,
        decision_stage="runtime_auth",
        decision="denied",
        reason_codes=reason_codes,
        required_scopes=required_scopes,
        matched_scope=None,
        policy_version=self._policy_version,
        data_classification="internal",
        resource_scope_binding=resource_scope_binding,
        runtime_available=runtime_available,
        availability_summary=availability_summary,
    )
```

**Resource-scope binding pattern to preserve** (lines 394-437):
```python
def _build_resource_binding(
    self,
    args: dict[str, Any],
    ctx: ToolCallContext,
) -> dict[str, Any]:
    binding: dict[str, Any] = {}
    scope_denied = False

    for key in _RESOURCE_BINDING_KEYS:
        value = args.get(key)
        if value is None:
            continue

        if key == "merchant_id":
            binding[key] = value
            merchant_scope = ctx.merchant_scope
            try:
                if isinstance(merchant_scope, MerchantScopeV1):
                    scope = merchant_scope
                elif isinstance(merchant_scope, list):
                    scope = MerchantScopeV1(merchant_ids=merchant_scope)
                else:
                    scope = MerchantScopeV1.model_validate(merchant_scope)
            except (TypeError, ValueError):
                scope_denied = True
            else:
                if not scope.allows(merchant_id=str(value)):
                    scope_denied = True

        if key in _DOMAIN_SCOPE_CHECK_IDENTIFIERS:
            binding["requires_domain_scope_check"] = True
            continue
        ...
    if scope_denied:
        binding["_scope_denied"] = True
    return binding
```

**Immutable helper analog for new gate entries:** `src/approvals/policy.py` (lines 20-26):
```python
@dataclass(frozen=True)
class ApprovalAssignmentPlan:
    required_role: str
    assigned_role: str
    mode: str
    sla_due_at: datetime
```

**Planner action:** define private ordered runtime auth gates, for example immutable `RuntimeAuthGate` entries with a `name`, `reason_code`, and predicate/callable. Keep descriptor missing and unavailable as preflight decisions unless a special descriptorless gate can preserve exact fields. Build `resource_scope_binding` once before the scope gate, and append reason codes in the existing order: caller, permission, side-effect, scope, approval, safety snapshot, idempotency.

---

### `tests/tools/test_catalog.py` (test, structural / transform)

**Analog:** `tests/tools/test_catalog.py`

**Imports and helper pattern** (lines 1-9, 28-29):
```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.tools.catalog import RegisteredTool, ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext
from src.tools.validation import _validate_json_value

def _descriptor(name: str) -> ToolDescriptor:
    return next(descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == name)
```

**Existing structural drift test pattern to extend** (lines 32-53):
```python
def test_descriptor_table_is_single_source_for_investigate_names_and_resource_types() -> None:
    descriptors = ToolCatalog().descriptors()
    investigate_names = {descriptor.name for descriptor in descriptors if "investigate" in descriptor.caller_allowlist}

    assert investigate_names == {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
        "search_policy",
        "search_sop",
        "search_case_memory",
    }
    assert {descriptor.resource_type for descriptor in descriptors} <= {
        "order",
        "refund_case",
        "ticket",
        "logistics",
        "merchant_risk",
        None,
    }
```

**Catalog fail-closed test pattern** (lines 103-122):
```python
@pytest.mark.asyncio
async def test_declaration_only_invoke_fails_closed_without_adapter_execution() -> None:
    adapter = AsyncMock()
    catalog = ToolCatalog([RegisteredTool(descriptor=_descriptor("get_order"), adapter=adapter)])

    result = await catalog.invoke("get_order", {"order_no": "ORD-1"}, _context(), AsyncMock())

    assert result.status == "unavailable"
    assert result.error is not None
    assert result.error.code == "TOOL_REGISTRY_DECLARATION_ONLY"
    adapter.assert_not_awaited()

@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found_with_integer_latency() -> None:
    result = await ToolCatalog([]).invoke("unknown", {}, _context(), AsyncMock())

    assert result.status == "not_found"
    assert result.data is None
    assert isinstance(result.latency_ms, int)
```

**Planner action:** add/extend tests here for registry-row single source: descriptor names, per-row `input_schema`, any retained `_IDENTIFIER_SCHEMAS` compatibility surface, generic `output_schema`, and catalog-derived investigate names must not drift.

---

### `tests/tools/test_tool_platform.py` (test, request-response / event-driven)

**Analog:** `tests/tools/test_tool_platform.py`

**Imports and shared constants pattern** (lines 18-39, 83-93):
```python
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
```

**Context helper pattern** (lines 124-160):
```python
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
        ...
    )
```

**Executor spy pattern for dispatch-blocking tests** (lines 190-203):
```python
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
```

**Runtime auth behavior pattern to preserve** (lines 385-417):
```python
@pytest.mark.asyncio
async def test_runtime_auth_rechecks_visible_tool_before_dispatch() -> None:
    from src.tools.platform import ToolPlatform

    executor = _RecordingExecutor({"get_order", "get_merchant_risk"}, _success_result())
    platform = ToolPlatform(executors={"business": executor})

    denied_ctx = _ctx(permissions=[])
    outcome = await platform.invoke("get_order", {"order_no": "ORD-1"}, denied_ctx, session=None)

    assert isinstance(outcome, ToolInvocationOutcome)
    assert outcome.tool_result.status == "permission_denied"
    assert outcome.policy_decision.decision_stage == "runtime_auth"
    assert outcome.policy_decision.decision == "denied"
    assert "missing_permission" in outcome.policy_decision.reason_codes
    assert executor.dispatched is False

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
```

**Structural test style pattern** (lines 684-691):
```python
def test_tool_result_projector_does_not_emit_events() -> None:
    import inspect

    from src.tools.projection import ToolResultProjector

    source = inspect.getsource(ToolResultProjector)
    assert "emit_decision_event" not in source
```

**Planner action:** add structural tests here for `_fail(...)` and declarative runtime-auth gates. Prefer stable private seams (`hasattr(ToolRuntime, "_fail")`, `inspect.getsource(ToolRuntime.invoke)` count/absence of repeated projection-event-return blocks, gate sequence symbol existence/order) plus behavior tests for failure outcomes.

---

### `tests/agent/test_tools/test_unified_tool_manager.py` (test, compatibility / request-response)

**Analog:** `tests/agent/test_tools/test_unified_tool_manager.py`

**Imports and hardcoded expected set to replace/derive in tests** (lines 18-37):
```python
from src.tools.catalog import ToolCatalog
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager import UnifiedToolManager

INVESTIGATE_TOOLS = {
    "get_order",
    "get_refund_case",
    "get_ticket",
    "get_logistics",
    "get_merchant_risk",
    "search_policy",
    "search_sop",
    "search_case_memory",
}
```

**Fake executor pattern** (lines 72-87):
```python
class _FakeExecutor:
    def __init__(self, name: str, result: Any) -> None:
        descriptor = next(item for item in ToolCatalog().descriptors() if item.name == name)
        self._tools = {name: descriptor}
        self.result = result
        self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []

    def get_tools(self):
        return dict(self._tools)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext):
        self.calls.append((name, args, ctx))
        return self.result
```

**Descriptor discovery compatibility pattern** (lines 107-123):
```python
def test_descriptor_discovery_returns_investigate_allowlist_only():
    manager = UnifiedToolManager()

    descriptors = manager.descriptors("investigate")

    assert {descriptor.name for descriptor in descriptors} == INVESTIGATE_TOOLS
    assert all(descriptor.kind != "write" for descriptor in descriptors)
    assert "create_coupon_grant_draft" not in {descriptor.name for descriptor in descriptors}


def test_descriptor_discovery_uses_business_registry_catalog():
    catalog = {descriptor.name: descriptor.model_dump() for descriptor in ToolCatalog().descriptors()}
    manager = UnifiedToolManager()

    for descriptor in manager.descriptors("investigate"):
        assert descriptor.model_dump() == catalog[descriptor.name]
```

**Declared-but-unavailable behavior to preserve** (lines 281-290):
```python
@pytest.mark.asyncio
async def test_declared_future_search_sop_returns_unavailable():
    tool_name = "search_sop"
    manager = UnifiedToolManager(
        executors=[KnowledgeToolExecutor(session=None, service=object()), MemoryToolExecutor()]
    )

    result = await manager.invoke(tool_name, {"query": "refund"}, _ctx(tool=tool_name))

    assert result.status == "unavailable"
```

**Existing failure behavior tests to keep green** (lines 364-529):
```python
@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found():
    result = await UnifiedToolManager().invoke("unknown_tool", {}, _ctx())
    assert result.status == "not_found"

@pytest.mark.asyncio
async def test_invalid_input_returns_invalid_request():
    executor = _FakeExecutor("get_order", _success_result())
    result = await UnifiedToolManager(executors=[executor]).invoke("get_order", {}, _ctx(tool="get_order"))
    assert result.status == "invalid_request"
    assert executor.calls == []

@pytest.mark.asyncio
async def test_malformed_executor_return_becomes_invalid_response():
    manager = UnifiedToolManager(executors=[_FakeExecutor("get_order", {"not": "a ToolResultV2"})])
    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))
    assert result.status == "invalid_response"
```

**Manager must remain adapter test pattern** (lines 539-578):
```python
def test_unified_manager_delegates_visibility_to_tool_platform():
    from src.tools.platform import ToolPlatform

    manager = UnifiedToolManager()
    assert isinstance(getattr(manager, "_platform", None), ToolPlatform)
    assert hasattr(manager, "visible_tools")

def test_unified_manager_does_not_own_new_policy_runtime_branches():
    import inspect

    from src.tools.manager import UnifiedToolManager as _Manager

    source = inspect.getsource(_Manager.invoke)
    assert "_platform" in source or "platform" in source
```

**Planner action:** update manager compatibility tests so expected investigate tools are derived from `ToolCatalog().descriptors()` using the production filter criteria, rather than maintaining a second expected name set.

---

### `tests/replay/test_tool_policy_events.py` (test, event-driven)

**Analog:** `tests/replay/test_tool_policy_events.py`

**Event constants and forbidden payload guard** (lines 26-40):
```python
TOOL_POLICY_VISIBILITY_EVENT = "tool_policy_visibility_recorded"
TOOL_POLICY_RUNTIME_AUTH_EVENT = "tool_policy_runtime_auth_recorded"

_FORBIDDEN_PAYLOAD_KEYS = {
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "input_schema",
    "required_permission",
    "caller_allowlist",
    "arguments",
    "data",
    "secret",
    "pii",
}
```

**Recursive forbidden-key helper** (lines 64-77):
```python
def _has_forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in _FORBIDDEN_PAYLOAD_KEYS:
                return str(key)
            nested = _has_forbidden_key(child)
            if nested is not None:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _has_forbidden_key(item)
            if nested is not None:
                return nested
    return None
```

**Runtime auth low-payload event pattern** (lines 130-159):
```python
@pytest.mark.asyncio
async def test_tool_policy_runtime_auth_recorded_emits_per_invocation_event(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="tool-policy-thread",
        event_type=TOOL_POLICY_RUNTIME_AUTH_EVENT,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool_name": "get_order", "tool_call_id": "tc-1", "resource_type": "order"},
        redacted_payload={
            "decision_stage": "runtime_auth",
            "tool_name": "get_order",
            "decision": "denied",
            "reason_codes": ["missing_permission"],
            "policy_version": "tool_policy.v1",
            "data_classification": "internal",
            "runtime_available": True,
        },
    )

    assert event["event_type"] == TOOL_POLICY_RUNTIME_AUTH_EVENT
    payload = event["redacted_payload"]
    assert payload["decision_stage"] == "runtime_auth"
    assert payload["decision"] == "denied"
    assert _has_forbidden_key(payload) is None
```

**Reject raw descriptor/argument payload pattern** (lines 162-197):
```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("raw_args", {"order_no": "ORD-1"}),
        ("raw_payload", {"secret": "sk-xxx"}),
        ("raw_tool_output", "<upstream error text>"),
        ("input_schema", {"type": "object"}),
        ("required_permission", "tool:get_order"),
        ("caller_allowlist", ["investigate"]),
    ],
)
async def test_tool_policy_event_rejects_raw_descriptor_and_arg_payload(...):
    ...
```

**Planner action:** after adding runtime `_fail(...)`, keep or extend this file as a regression that runtime auth events stay low-payload for failure paths. Do not add raw args, raw tool output, descriptor schemas, required permissions, or caller allowlists to event payloads.

---

## Shared Patterns

### External Contract Shapes

**Source:** `src/tools/contracts.py`  
**Apply to:** all source files in Phase 37

**Do not add/remove/rename fields on these models** (lines 13-37, 71-98, 145-158, 161-184, 208-231):
```python
class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

class ToolResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

class ToolViewV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

class ToolPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

class ToolInvocationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_result: ToolResultV2
    projection: ToolResultProjectionV1
    policy_decision: ToolPolicyDecision
    policy_event_id: str | None = None
```

### Runtime Tuple and Projection

**Source:** `src/tools/platform.py` and `src/tools/runtime.py`  
**Apply to:** `src/tools/runtime.py`, `src/tools/manager.py`, runtime tests

**Runtime invoke contract**: `ToolRuntime.invoke(...)` returns `(ToolResultV2, ToolPolicyDecision, str | None, ToolResultProjectionV1)` (runtime lines 60-71), and `ToolPlatform.invoke(...)` wraps it into `ToolInvocationOutcome` (platform lines 125-133).

### Input Validation Before Runtime Auth

**Source:** `src/tools/runtime.py` and `src/tools/validation.py`  
**Apply to:** `src/tools/runtime.py`, policy-event tests

**Order pattern** (runtime lines 92-120):
```python
try:
    validate_json_value(args, descriptor.input_schema)
except (TypeError, ValueError):
    decision = self._denied_decision(...)
    ...

decision = self._policy_engine.runtime_auth(
    tool_name=tool_name, args=args, ctx=ctx,
    availability_map=availability_map,
)
```

**Validator subset** (validation lines 8-23):
```python
def validate_json_value(value: Any, schema: dict[str, Any]) -> None:
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        for required_name in schema.get("required", []):
            if required_name not in value:
                raise ValueError("Missing required property")
```

### Prompt and Event Redaction

**Source:** `src/tools/projection.py`, `src/tools/runtime.py`, `tests/replay/test_tool_policy_events.py`  
**Apply to:** runtime helper and event regression tests

**Projection raw-sentinel denylist** (projection lines 9-21):
```python
_RAW_SENTINEL_KEYS: set[str] = {
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
```

**Runtime event payload allowed fields**: keep `decision_stage`, `tool_name`, `decision`, `reason_codes`, `policy_version`, `data_classification`, and `runtime_available` only unless a later phase explicitly changes replay contracts (runtime lines 300-308).

### Verification Command Entry Points

**Source:** `AGENTS.md`, `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-VALIDATION.md`, `src/replay/phase35_matrix.py`  
**Apply to:** all planner-generated verify sections

**Approved test command examples for this phase:**
```bash
uv run pytest tests/tools/test_catalog.py -q
uv run pytest tests/tools/test_tool_platform.py -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py -q
uv run pytest tests/replay/test_tool_policy_events.py -q
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q
uv run ruff check src/tools tests/tools tests/agent/test_tools tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py
```

**Existing whitelist validator analog**: `src/replay/phase35_matrix.py` (lines 53-58):
```python
APPROVED_PYTEST_ENTRYPOINTS = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest",
    "uv run pytest",
    ".venv/bin/pytest",
    ".venv/bin/python -m pytest",
)
```

## No Analog Found

None. All eight files are existing files with exact local analogs. Supporting shared analogs were found in `src/tools/platform.py`, `src/tools/manager_results.py`, `src/tools/projection.py`, `src/tools/contracts.py`, `src/tools/validation.py`, `src/approvals/policy.py`, and `src/replay/phase35_matrix.py`.

## Metadata

**Analog search scope:** `src/tools/`, `tests/tools/`, `tests/agent/test_tools/`, `tests/replay/`, plus supporting `src/approvals/` and `src/replay/phase35_matrix.py` for immutable helper / verification-entrypoint patterns.  
**Files scanned:** 30 from `rg --files src/tools tests/tools tests/agent/test_tools tests/replay`, plus 4 supporting analog files.  
**Pattern extraction date:** 2026-07-01  
**Phase constraints carried forward:** no external contract shape change; keep generic output schema until Phase 38; keep manager as adapter; keep runtime event payload low-payload; use project-scoped verification commands only.
