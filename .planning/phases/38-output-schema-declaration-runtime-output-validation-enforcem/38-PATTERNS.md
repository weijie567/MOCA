# Phase 38: output-schema-declaration-runtime-output-validation-enforcem - Pattern Map

**Mapped:** 2026-07-02  
**Files analyzed:** 11 scoped implementation/test/verification targets  
**Analogs found:** 11 / 11  

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/tools/catalog.py` | config / catalog | declaration-transform | `src/tools/catalog.py`; producer shapes in `src/business/adapters.py`, `src/tools/executors/knowledge.py`, `src/tools/executors/memory.py` | exact |
| `src/tools/validation.py` | utility | transform | `src/tools/validation.py`; tests in `tests/tools/test_catalog.py` | exact |
| `src/tools/runtime.py` | service / runtime | request-response | `src/tools/runtime.py`; facade in `src/tools/platform.py` | exact |
| `tests/tools/test_catalog.py` | test | structural / transform | `tests/tools/test_catalog.py` | exact |
| `tests/tools/test_tool_platform.py` | test | request-response runtime | `tests/tools/test_tool_platform.py`; manager analog in `tests/agent/test_tools/test_unified_tool_manager.py` | exact |
| `tests/agent/test_tools/test_unified_tool_manager.py` | regression test | request-response compatibility | `tests/agent/test_tools/test_unified_tool_manager.py` | exact |
| `tests/agent/test_nodes/test_investigate.py` | regression test | graph request-response / projection | `tests/agent/test_nodes/test_investigate.py` | exact |
| `tests/agent/rag_context/test_verifier.py` | regression test | transform / authority validation | `tests/agent/rag_context/test_verifier.py` | exact |
| `tests/conversation/test_service.py` | regression test | persistence / projection storage | `tests/conversation/test_service.py` | exact |
| `tests/test_execute_action.py` | regression test | request-response / action safety | `tests/test_execute_action.py` | exact |
| `tests/architecture/test_trusted_context_boundaries.py` | architecture test | structural boundary | `tests/architecture/test_trusted_context_boundaries.py` | exact |

Protected no-edit files for Phase 38: `docs/contract-spec.md` and `src/tools/contracts.py`. Only edit them if a plan explicitly records a hard blocker; otherwise Phase 39 owns spec reconciliation.

## Pattern Assignments

### `src/tools/catalog.py` (config/catalog, declaration-transform)

**Analog:** `src/tools/catalog.py`

**Imports pattern** (lines 5-11):
```python
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.tools.contracts import ToolError, ToolResultV2
```

**Declaration row pattern** (lines 41-57):
```python
_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
@dataclass(frozen=True)
class _ToolDeclaration:
    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    side_effect: Literal["read_only", "retrieval", "write"]
    caller_allowlist: tuple[str, ...]
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    description: str = ""
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False
```

Copy this dataclass style and add `output_schema: dict[str, Any]` beside `input_schema`. Keep the declaration immutable and keep rows as the single descriptor source.

**Descriptor pass-through pattern** (lines 225-243):
```python
def _descriptor(declaration: _ToolDeclaration) -> ToolDescriptor:
    return ToolDescriptor(
        name=declaration.name,
        description=declaration.description,
        kind=declaration.kind,
        input_schema=declaration.input_schema,
        output_schema=_GENERIC_OBJECT_SCHEMA,
        risk_level=declaration.kind,
        side_effect=declaration.side_effect,
        required_permission=f"tool:{declaration.name}",
        caller_allowlist=list(declaration.caller_allowlist),
        event_family=declaration.event_family,
        resource_type=declaration.resource_type,
        executor=declaration.executor,
        exposure=declaration.exposure,
        requires_approval=declaration.requires_approval,
        requires_safety_snapshot=declaration.requires_safety_snapshot,
        requires_idempotency_key=declaration.requires_idempotency_key,
    )
```

Phase 38 should replace the generic assignment with `output_schema=declaration.output_schema`. Do not change public `ToolDescriptor` fields.

**Investigate visibility helper pattern** (lines 250-258):
```python
def investigate_tool_names(descriptors: Iterable[ToolDescriptor] | None = None) -> frozenset[str]:
    source = descriptors if descriptors is not None else _default_descriptors()
    return frozenset(
        descriptor.name
        for descriptor in source
        if "investigate" in descriptor.caller_allowlist
        and descriptor.kind != "write"
        and descriptor.exposure == "planner_visible"
    )
```

Do not reintroduce hand-maintained manager tool lists. Phase 37 established catalog-derived investigate visibility.

**Implemented business output shapes source** (source: `src/business/adapters.py`, lines 20-72):
```python
class _StrictProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class _OrderRelationHints(_StrictProjection):
    has_active_refund: bool
    latest_refund_case_id: str | None
    has_open_ticket: bool
    latest_ticket_id: str | None

class _OrderData(_StrictProjection):
    order_no: str
    merchant_id: str
    status: str
    amount: str
    currency: str
    buyer_name: str
    item_name: str
    paid_at: str | None
    delivered_at: str | None
    relation_hints: _OrderRelationHints

class _RefundCaseData(_StrictProjection):
    refund_case_no: str
    merchant_id: str
    status: str
    reason_code: str
    reason_text: str
    requested_amount: str
    approved_amount: str | None

class _TicketData(_StrictProjection):
    ticket_no: str
    merchant_id: str
    status: str
    channel: str
    summary: str
```

Use these as the exact `output_schema` source for `get_order`, `get_refund_case`, and `get_ticket`. Mirror `extra="forbid"` with `additionalProperties: False`.

**Business success wrapping pattern** (source: `src/business/adapters.py`, lines 211-240):
```python
try:
    projected = projection.model_validate(raw.get("data"))
except ValidationError:
    return _invalid_response(source_system, latency_ms)

retrieved_at = _fixed_millisecond_now()
return ToolResultV2(
    status="success",
    data=projected.model_dump(mode="json"),
    summary=success_summary,
    source_system=source_system,
    data_freshness_at=None,
    policy_evidence_refs=[],
    business_fact_refs=[
        BusinessFactRefV1(
            tenant_id=ctx.tenant_id,
            source_system=source_system,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=None,
            data_freshness_at=None,
            retrieved_at=retrieved_at,
        )
    ],
    error=None,
    retryable=False,
    retry_after_ms=None,
    latency_ms=latency_ms,
    audit_ref=None,
)
```

Schemas validate only `ToolResultV2.data`; refs stay in the envelope.

**Unavailable business no-data pattern** (source: `src/business/service.py`, lines 123-147):
```python
async def get_logistics(self, tracking_no: str, ctx: ToolCallContext) -> BusinessFactResultV1:
    del tracking_no
    return self._safe_result(
        "unavailable",
        resource_name="logistics",
        tenant_id=ctx.tenant_id,
        source_system="business_fact_service",
        scope_check_result="not_applicable",
        code="BUSINESS_FACT_UNAVAILABLE",
        safe_message="Business fact is unavailable",
        error_source="tool",
    )

async def get_merchant_risk(self, merchant_id: str, ctx: ToolCallContext) -> BusinessFactResultV1:
    del merchant_id
    return self._safe_result(
        "unavailable",
        resource_name="merchant_risk",
        tenant_id=ctx.tenant_id,
        source_system="business_fact_service",
        scope_check_result="not_applicable",
        code="BUSINESS_FACT_UNAVAILABLE",
        safe_message="Business fact is unavailable",
        error_source="tool",
    )
```

Use strict empty-object no-data schemas for `get_logistics` and `get_merchant_risk` unless the plan records a product decision to implement real success payloads.

**Knowledge output shape source** (source: `src/tools/executors/knowledge.py`, lines 73-90; `src/knowledge/schemas.py`, lines 244-255):
```python
return ToolResultV2(
    status=status_map[search_result.status],
    data={
        "retrieval_status": search_result.status,
        "best_score": search_result.best_score,
        "threshold": search_result.threshold,
        "summary": search_result.summary,
    },
    summary=search_result.summary or f"Policy search returned {search_result.status}",
    source_system="policy_knowledge_service",
    data_freshness_at=None,
    policy_evidence_refs=search_result.evidence_refs,
    business_fact_refs=[],
    error=error,
    retryable=bool(error.retryable) if error else False,
    retry_after_ms=None,
    latency_ms=0,
    audit_ref=None,
)
```

```python
class KnowledgeSearchResult(BaseModel):
    schema_version: Literal["knowledge_search_result.v2"] = "knowledge_search_result.v2"
    status: Literal["strong_evidence", "partial_evidence", "no_evidence", "error"]
    query_rewrite: str | None = None
    retrieval_config_version: str
    rerank_config_version: str
    best_score: float
    threshold: float
    evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    citation_validation: CitationValidationResult = Field(default_factory=CitationValidationResult)
    summary: str | None = None
    error: dict | None = None
```

`search_policy` schema should include `retrieval_status`, `best_score`, `threshold`, and nullable `summary`. Policy evidence refs are envelope fields, not `data`.

**Knowledge unavailable pattern for `search_sop`** (source: `src/tools/executors/knowledge.py`, lines 27-38):
```python
def has_tool(self, name: str) -> bool:
    return name == "search_policy"

async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    if name != "search_policy":
        return result(
            "unavailable",
            "Tool is declared but unavailable",
            code="TOOL_UNAVAILABLE",
            source="tool",
            source_system="knowledge_tool_executor",
        )
```

`search_sop` has no current success payload. Use the same strict no-data schema stance as other declared-but-unavailable tools.

**Case-memory output shape source** (source: `src/tools/executors/memory.py`, lines 97-112; `src/memory/schemas.py`, lines 391-408):
```python
def _case_memory_result(search_result: CaseMemorySearchResult) -> ToolResultV2:
    if search_result.status == "success":
        return ToolResultV2(
            status="success",
            data={"items": [item.model_dump(mode="json") for item in search_result.items]},
            summary=f"Found {len(search_result.items)} reviewed case memory precedent item(s)",
            source_system="case_memory_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
```

```python
class CaseMemorySearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_memory_id: str
    excerpt: str
    applicability: str | None = None
    outcome: str | None = None
    caveats: str | None = None
    score: float
    policy_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)

class CaseMemorySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "empty"]
    items: list[CaseMemorySearchItem] = Field(default_factory=list)
```

`search_case_memory` schema should require `items`, strict item objects, nullable optional text fields, numeric `score`, and bounded object arrays for refs.

---

### `src/tools/validation.py` (utility, transform)

**Analog:** `src/tools/validation.py`

**Core validation pattern** (lines 8-47):
```python
def validate_json_value(value: Any, schema: dict[str, Any]) -> None:
    """Validate the JSON Schema subset used by tool descriptors."""

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        for required_name in schema.get("required", []):
            if required_name not in value:
                raise ValueError("Missing required property")
        properties = schema.get("properties", {})
        for property_name, property_schema in properties.items():
            if property_name in value:
                validate_json_value(value[property_name], property_schema)
        if schema.get("additionalProperties") is False and any(name not in properties for name in value):
            raise ValueError("Unexpected property")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise TypeError("Expected array")
        item_schema = schema.get("items", {})
        for item in value:
            validate_json_value(item, item_schema)
    elif expected_type == "string":
        if not isinstance(value, str):
            raise TypeError("Expected string")
        if len(value) < schema.get("minLength", 0):
            raise ValueError("String is too short")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Expected integer")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Expected number")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValueError("Number is below exclusive minimum")
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise TypeError("Expected boolean")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Value is not in enum")
```

Extend this helper before strict nullable schemas are used. Add list-type union support before the scalar/object branches, then support `"null"` as `value is None`.

**Existing helper tests to extend** (source: `tests/tools/test_catalog.py`, lines 86-100):
```python
def test_json_schema_helper_accepts_valid_input() -> None:
    _validate_json_value({"order_no": "ORD-1"}, _descriptor("get_order").input_schema)

@pytest.mark.parametrize(
    ("value", "schema"),
    [
        ({}, _descriptor("get_order").input_schema),
        ({"order_no": ""}, _descriptor("get_order").input_schema),
        ({"order_no": 123}, _descriptor("get_order").input_schema),
    ],
)
def test_json_schema_helper_rejects_invalid_input(value: object, schema: dict) -> None:
    with pytest.raises((TypeError, ValueError)):
        _validate_json_value(value, schema)
```

Add null/type-union cases here rather than adding a new validator test file.

---

### `src/tools/runtime.py` (service/runtime, request-response)

**Analog:** `src/tools/runtime.py`

**Imports pattern** (lines 9-19):
```python
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

**Input validation before auth** (lines 94-112):
```python
# Step 2: Input schema validation (BEFORE runtime_auth so unvalidated
# args never enter resource_scope_binding or decision event resource_refs)
try:
    validate_json_value(args, descriptor.input_schema)
except (TypeError, ValueError):
    decision = self._denied_decision(
        tool_name=tool_name, ctx=ctx,
        reason_codes=["schema_invalid"],
        required_scopes=[descriptor.required_permission],
    )
    return await self._fail(
        tool_name=tool_name,
        ctx=ctx,
        decision=decision,
        session=session,
        status="invalid_request",
        summary="Tool input failed validation",
        code="INVALID_TOOL_INPUT", source="caller",
    )
```

**Output validation gate** (lines 176-190):
```python
# Step 7: Output schema validation
try:
    if tool_result.data is not None:
        validate_json_value(tool_result.data, descriptor.output_schema)
except (TypeError, ValueError):
    return await self._fail(
        tool_name=tool_name,
        ctx=ctx,
        decision=decision,
        session=session,
        status="invalid_response",
        summary="Tool executor returned an invalid response",
        code="INVALID_EXECUTOR_RESPONSE", source="adapter",
    )
```

Keep this gate. If Phase 38 changes `runtime.py`, it should be a narrowly scoped guard or test-facing cleanup only; schema failures already map to `invalid_response`.

**Shared failure helper** (lines 265-295):
```python
async def _fail(
    self,
    *,
    tool_name: str,
    ctx: ToolCallContext,
    decision: ToolPolicyDecision,
    session: AsyncSession | None,
    result: ToolResultV2 | None = None,
    status: _FailStatus | None = None,
    summary: str | None = None,
    code: str | None = None,
    source: _FailSource = "caller",
) -> tuple[ToolResultV2, ToolPolicyDecision, str | None, ToolResultProjectionV1]:
    if result is None:
        if status is None or summary is None or code is None:
            raise ValueError("_fail requires either result or status, summary, and code")
        error_result = safe_result(status, summary, code=code, source=source)
    else:
        error_result = result

    projection = self._projector.project(
        tool_name=tool_name,
        result=error_result,
        tool_call_id=ctx.tool_call_id,
    )
    event_id = await self._emit_decision_event(
        decision=decision,
        ctx=ctx,
        session=session,
    )
    return error_result, decision, event_id, projection
```

All output-schema failures must continue through `_fail(...)` so projection and decision-event behavior stays uniform.

**Facade outcome pattern** (source: `src/tools/platform.py`, lines 121-133):
```python
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

Tests for runtime behavior should usually call `ToolPlatform.invoke(...)` and assert on `ToolInvocationOutcome`.

---

### `tests/tools/test_catalog.py` (test, structural/transform)

**Analog:** `tests/tools/test_catalog.py`

**Imports and helpers pattern** (lines 7-29):
```python
from src.tools.catalog import _IDENTIFIER_SCHEMAS, RegisteredTool, ToolCatalog, ToolDescriptor, investigate_tool_names
from src.tools.contracts import ToolCallContext
from src.tools.validation import _validate_json_value

def _descriptor(name: str) -> ToolDescriptor:
    return next(descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == name)
```

Use `_descriptor(...)` for schema assertions. Do not duplicate catalog lookup logic.

**Outdated generic-schema assertion to replace** (lines 32-36):
```python
def test_catalog_registry_derives_identifier_schemas_without_drift() -> None:
    descriptors = ToolCatalog().descriptors()

    assert _IDENTIFIER_SCHEMAS == {descriptor.name: descriptor.input_schema for descriptor in descriptors}
    assert all(descriptor.output_schema == {"type": "object"} for descriptor in descriptors)
```

Replace the line 36 assertion with real-schema assertions for the eight scoped read/retrieval tools. Keep the `_IDENTIFIER_SCHEMAS` drift assertion.

**Descriptor source-of-truth pattern** (lines 39-53):
```python
def test_descriptor_table_is_single_source_for_investigate_names_and_resource_types() -> None:
    descriptors = ToolCatalog().descriptors()
    investigate_names = investigate_tool_names(descriptors)

    assert investigate_names
    assert "create_coupon_grant_draft" not in investigate_names
    assert investigate_names == investigate_tool_names()
    assert {descriptor.resource_type for descriptor in descriptors} <= {
        "order",
        "refund_case",
        "ticket",
        "logistics",
        "merchant_risk",
        None,
    }
```

Keep action tool `create_coupon_grant_draft` out of Phase 38 real-output-schema scope unless a plan explicitly broadens action output hardening.

---

### `tests/tools/test_tool_platform.py` (test, request-response runtime)

**Analog:** `tests/tools/test_tool_platform.py`

**Imports and context helper pattern** (lines 24-39, 124-160):
```python
from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    ToolViewV1,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolInvocationOutcome,
    ToolResultV2,
    ToolCallContext,
)
from src.platform.trusted_context import MerchantScopeV1
```

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
```

Use this helper pattern for fake-executor tests. Expand default permissions only where needed for read/retrieval tools.

**Fake executor pattern** (lines 190-203):
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

Copy this for valid/invalid output tests. It avoids PostgreSQL and isolates the runtime output-validation gate.

**Platform invocation pattern** (lines 422-452):
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
```

New output-validation tests should assert on `outcome.tool_result`, `outcome.projection`, and `outcome.model_dump_json()`.

**Shared `_fail(...)` guard** (lines 456-464):
```python
def test_tool_runtime_failure_paths_use_shared_fail_helper() -> None:
    from src.tools.runtime import ToolRuntime

    runtime_source = inspect.getsource(ToolRuntime)
    invoke_source = inspect.getsource(ToolRuntime.invoke)

    assert "async def _fail(" in runtime_source
    assert invoke_source.count("await self._fail(") >= 7
```

Retain this as a regression guard if runtime failure branches change.

**Runtime failure redaction pattern** (lines 466-491):
```python
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
```

Copy this redaction style for invalid-output data: assert the raw invalid sentinel is absent from the full outcome JSON and projection JSON.

**Existing manager-level output-schema analog** (source: `tests/agent/test_tools/test_unified_tool_manager.py`, lines 502-525):
```python
@pytest.mark.asyncio
async def test_output_schema_failure_returns_invalid_response_without_raw_data():
    raw_sentinel = "RAW-MANAGER-SENTINEL"
    descriptor = next(item for item in ToolCatalog().descriptors() if item.name == "get_order").model_copy(
        update={
            "output_schema": {
                "type": "object",
                "properties": {"order_no": {"type": "string"}},
                "required": ["order_no"],
                "additionalProperties": False,
            }
        }
    )
    executor = _FakeExecutor("get_order", _success_result())
    executor._tools = {"get_order": descriptor}
    executor.result = _success_result()
    executor.result.data = {"unexpected": raw_sentinel}
    manager = UnifiedToolManager(descriptors=[descriptor], executors=[executor])

    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))

    assert result.status == "invalid_response"
    assert result.data is None
    assert raw_sentinel not in str(result.model_dump())
```

For Phase 38, prefer adding the runtime/facade version in `tests/tools/test_tool_platform.py`, but keep this compatibility analog green.

**Projection redaction pattern** (lines 635-690):
```python
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
```

Use the same sentinel-search helper style from this test for raw invalid data leak checks.

**Case-memory projection redaction pattern** (lines 692-756):
```python
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
```

Use this shape for `search_case_memory` current-payload acceptance/rejection tests in catalog schema coverage.

---

### `tests/agent/test_tools/test_unified_tool_manager.py` (regression test, request-response compatibility)

**Analog:** `tests/agent/test_tools/test_unified_tool_manager.py`

**Catalog-derived descriptor discovery** (lines 97-128):
```python
def test_descriptor_discovery_returns_investigate_allowlist_only():
    manager = UnifiedToolManager()

    descriptors = manager.descriptors("investigate")

    assert {descriptor.name for descriptor in descriptors} == investigate_tool_names()
    assert all(descriptor.kind != "write" for descriptor in descriptors)
    assert "create_coupon_grant_draft" not in {descriptor.name for descriptor in descriptors}

def test_descriptor_discovery_uses_catalog_investigate_helper(monkeypatch):
    calls: dict[str, list[str]] = {}

    def fake_investigate_tool_names(descriptors):
        descriptor_list = list(descriptors)
        calls["names"] = [descriptor.name for descriptor in descriptor_list]
        return frozenset({"get_order"})

    monkeypatch.setattr("src.tools.manager.investigate_tool_names", fake_investigate_tool_names)

    descriptors = UnifiedToolManager().descriptors("investigate")

    assert calls["names"]
    assert {descriptor.name for descriptor in descriptors} == {"get_order"}

def test_descriptor_discovery_uses_business_registry_catalog():
    catalog = {descriptor.name: descriptor.model_dump() for descriptor in ToolCatalog().descriptors()}
    manager = UnifiedToolManager()

    for descriptor in manager.descriptors("investigate"):
        assert descriptor.model_dump() == catalog[descriptor.name]
```

High-blast regression: schema changes in catalog must flow through manager descriptors without drift.

**Case-memory manager dispatch** (lines 299-330):
```python
@pytest.mark.asyncio
async def test_search_case_memory_dispatches_to_reviewed_case_memory_service():
    class FakeMemorySearchService:
        def __init__(self) -> None:
            self.calls = []

        async def retrieve_reviewed(self, request):
            self.calls.append(request)
            return CaseMemorySearchResult(
                status="success",
                items=[
                    CaseMemorySearchItem(
                        case_memory_id="case-memory-1",
                        excerpt="Reviewed refund precedent.",
                        outcome="Context only.",
                        score=1.0,
                    )
                ],
            )

    service = FakeMemorySearchService()
    manager = UnifiedToolManager(executors=[MemoryToolExecutor(service=service)])

    result = await manager.invoke(
        "search_case_memory", {"query": "similar refund case"}, _ctx(tool="search_case_memory")
    )

    assert result.status == "success"
    assert result.source_system == "case_memory_service"
    assert result.data["items"][0]["case_memory_id"] == "case-memory-1"
    assert result.policy_evidence_refs == []
    assert service.calls[0].query == "similar refund case"
```

Keep this green when strict `search_case_memory` output schema is added.

**Manager delegates to platform** (lines 553-584):
```python
@pytest.mark.asyncio
async def test_unified_manager_invoke_returns_tool_result_v2_via_platform(monkeypatch):
    from src.tools.platform import ToolPlatform

    captured: dict[str, Any] = {}

    async def fake_invoke(self, name, args, ctx, session=None):
        captured["value"] = (name, args, ctx.caller_node)
        return SimpleNamespace(tool_result=_success_result("platform_delegate"))

    monkeypatch.setattr(ToolPlatform, "invoke", fake_invoke)
    manager = UnifiedToolManager()

    result = await manager.invoke("get_order", {"order_no": "ORD-DELEGATE"}, _ctx(tool="get_order"))

    assert isinstance(result, ToolResultV2)
    assert result.status == "success"
    assert result.source_system == "platform_delegate"
    assert captured["value"] == ("get_order", {"order_no": "ORD-DELEGATE"}, "investigate")
```

Output validation belongs behind the platform/runtime boundary, not directly in `UnifiedToolManager`.

---

### `tests/agent/test_nodes/test_investigate.py` (regression test, graph request-response/projection)

**Analog:** `tests/agent/test_nodes/test_investigate.py`

**Fake manager/platform pattern** (lines 74-165):
```python
class FakeManager:
    def __init__(self, results: dict[str, ToolResultV2]) -> None:
        self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}
        self.results = results
        self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []
        self._platform = _FakePlatform(self)

    def descriptors(self, caller_node: str = "investigate"):
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist and descriptor.kind != "write"
        ]

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        self.calls.append((name, args, ctx))
        return self.results[name]
```

Use this existing test harness for investigate regressions; do not make high-blast graph tests depend on new DB setup unless the target test already does.

**Case-memory success fixture** (lines 342-384):
```python
def _case_memory_success() -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={
            "items": [
                {
                    "case_memory_id": "case-memory-1",
                    "excerpt": "Reviewed refund timeout precedent.",
                    "applicability": "Similar delayed refund case.",
                    "outcome": "Context only.",
                    "score": 0.92,
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
                    "raw_tool_payload": {"secret": "must-not-leak"},
                }
            ]
        },
        summary="case memory found",
        source_system="case_memory_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=3,
        audit_ref=None,
    )
```

Strict `search_case_memory` output schema must accept this valid shape except for raw sentinel keys when testing rejection.

**Contextual case-memory regression** (lines 854-875):
```python
@pytest.mark.asyncio
async def test_search_case_memory_tool_result_accumulates_contextual_case_memory():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_case_memory": _case_memory_success()})
    plan = [{"next_tool": "search_case_memory", "args": {"query": "refund timeout"}, "reason": "precedent"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert result["case_memory"][0]["case_memory_id"] == "case-memory-1"
    assert result["case_memory"][0]["excerpt"] == "Reviewed refund timeout precedent."
    assert result["case_memory"][0]["policy_refs"] == [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}]
    assert result["policy_evidence"] == []
    assert "raw_tool_payload" not in str(result["case_memory"])
    assert "must-not-leak" not in str(result["case_memory"])
    assert "raw_payload" not in str(result["case_memory"])
    assert "secret" not in str(result["case_memory"])
```

Run this as a high-blast regression after schema enforcement.

**Projection authority pattern** (lines 1065-1136):
```python
def test_tool_result_projector_rejects_data_only_business_identifiers_as_refs():
    result = ToolResultV2(
        status="success",
        data={
            "order_no": "ORD-DATA-30",
            "refund_case_no": "RF-DATA-30",
            "ticket_id": "TK-DATA-30",
            "tracking_no": "TRK-DATA-30",
            "merchant_id": "MER-DATA-30",
            "status": "loaded",
        },
        summary="business fact loaded",
        source_system="business_tool_service",
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
        tool_name="get_order",
        result=result,
        tool_call_id="tool-call-data-only-30",
    )

    assert "business_fact_refs" not in projection.normalized_result
    assert projection.prompt_projection["business_fact_refs"] == []
    assert projection.prompt_projection["resource_refs"] == []
    assert projection.resource_refs == []
```

Do not let output schemas turn data-only IDs into authority; refs remain envelope-owned.

---

### `tests/agent/rag_context/test_verifier.py` (regression test, transform/authority validation)

**Analog:** `tests/agent/rag_context/test_verifier.py`

**Verifier context bundle pattern** (lines 56-90):
```python
def _bundle(
    *,
    evidence: EvidenceRefV1,
    evidence_text: str,
    business_refs: list[BusinessFactRefV1] | None = None,
    evidence_snippet_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snippet = {
        "citation_id": "C1",
        "evidence_id": evidence.evidence_id,
        "text": evidence_text,
    }
    if evidence_snippet_overrides:
        snippet.update(evidence_snippet_overrides)
    return {
        "trusted_context": {
            "tenant_id": TENANT_ID,
            "scope": {"merchant_ids": ["merchant-001"]},
            "effective_at": "2026-06-19T00:00:00+00:00",
            "run_id": "run-phase22-verifier",
            "thread_id": "thread-phase22-verifier",
        },
        "citation_map": {
            "C1": {
                "citation_id": "C1",
                "evidence_ref": evidence.model_dump(mode="json"),
                "source_evidence_ids": [evidence.evidence_id],
                "snippet": evidence_text,
                "risk_labels": [],
            }
        },
        "verifier_context": {
            "evidence_snippets": [snippet],
            "business_fact_refs": [ref.model_dump(mode="json") for ref in business_refs or []],
        },
    }
```

**Business authority regression** (lines 292-315):
```python
async def test_business_fact_claim_requires_current_tool_system_refs() -> None:
    """CLM-03/CLM-05: policy evidence cannot satisfy business authority."""
    MaterialClaim, MaterialClaimVerifier, VerificationOutcome = _load_verifier_api()
    evidence = _evidence_ref()
    claim = MaterialClaim.model_validate(
        _claim_payload(
            "business_fact_claim",
            claim_text="Order ORD-1001 was delivered.",
            business_fact_refs=[],
        )
    )

    result = await MaterialClaimVerifier().verify_claim(
        claim,
        context_bundle=_bundle(
            evidence=evidence,
            evidence_text="Policy says delivered orders need logistics evidence.",
            business_refs=[],
        ),
    )

    assert _value(result.outcome) == VerificationOutcome.BUSINESS_FACT_MISSING.value
    assert "business_fact_ref_required" in result.reason_codes
    assert result.allows_claim is False
```

Run this after schema enforcement to confirm business fact authority still depends on current envelope refs.

---

### `tests/conversation/test_service.py` (regression test, persistence/projection storage)

**Analog:** `tests/conversation/test_service.py`

**Projected storage regression** (lines 680-778):
```python
@pytest.mark.asyncio
async def test_append_tool_result_stores_projector_normalized_data_without_raw_sentinels(
    session: AsyncSession, seeded_session: dict
) -> None:
    from sqlalchemy import select

    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService
    from src.tools.contracts import ToolResultV2

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-projector-normalized"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()
    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-projector-normalized",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-PROJ-001"},
        argument_summary_json={"order_no": "ORD-PROJ-001"},
        redaction_policy_version="conversation_redaction.v1",
    )
```

```python
result = ToolResultV2(
    status="success",
    data={"order_no": "ORD-PROJ-001", "status": "shipped", **raw_sentinels},
    summary="order shipped",
    source_system="business_tool_service",
    data_freshness_at=datetime.now(UTC),
    policy_evidence_refs=[],
    business_fact_refs=[],
    error=None,
    retryable=False,
    retry_after_ms=None,
    latency_ms=5,
    audit_ref="audit/tool-result/ORD-PROJ-001",
)
prompt_summary = await service.append_tool_result(
    tenant_id=tenant_id,
    user_id=user_id,
    thread_id=thread_id,
    run_id=run_id,
    trace_id="trace-projector-normalized",
    operation_id=operation_id,
    tool_call_id=str(operation_id),
    tool_call_record_id=tool_call.id,
    tool_result_id="tool-result-projector-normalized",
    tool_name="get_order",
    result=result,
)
```

```python
assert not _has_raw_sentinel(stored.normalized_result_json)
assert not _has_raw_sentinel(stored.prompt_summary)
assert not _has_raw_sentinel(prompt_summary.prompt_summary)
assert stored.normalized_result_json.get("order_no") == "ORD-PROJ-001"
```

This is DB-backed. Run only when PostgreSQL is available; otherwise record the environment blocker in `.planning/LOCAL-VALIDATION-ISSUES.md`.

---

### `tests/test_execute_action.py` (regression test, request-response/action safety)

**Analog:** `tests/test_execute_action.py`

**Trusted config/action fake pattern** (lines 189-243):
```python
def _trusted_context_for_state(state: dict[str, Any], *, permissions: list[str] | None = None) -> dict[str, Any]:
    return TrustedContext(
        tenant_id=state["tenant_id"],
        user_id=state.get("user_id") or str(uuid4()),
        role=state.get("role") or "support",
        permissions=[ACTION_PERMISSION] if permissions is None else permissions,
        merchant_scope=MerchantScopeV1(merchant_ids=["*"]),
        session_id=None,
        thread_id=state.get("thread_id") or "thread-action-draft",
        run_id=state["current_run_id"],
        trace_id="trace-action-draft",
        locale=None,
    ).model_dump(mode="json")

class _RecordingActionExecutor:
    executor_name = "action"

    def __init__(self) -> None:
        self.calls = 0

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        del name, args, ctx
        self.calls += 1
        return ToolResultV2(
            status="success",
            data=_success_result()["data"],
            summary="created draft",
            source_system="fake_action_executor",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
```

**Action-fail-closed regression** (lines 282-301):
```python
@pytest.mark.asyncio
async def test_action_draft_tool_success_invalid_draft_outcome_fails_closed(monkeypatch):
    payload = _success_result()
    payload["data"]["draft_outcome"] = {
        "schema_version": "draft_outcome.v1",
        "draft_id": payload["data"]["draft_id"],
        "status": "executed",
        "external_side_effect": False,
    }
    create_draft = AsyncMock(return_value=payload)
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)

    state = _approved_state()
    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "INVALID_DRAFT_OUTCOME"
    assert "action_draft" not in result
    assert "draft_outcome" not in result
    assert result["trace_steps"][-1]["status"] == "error"
```

Run as high-blast regression to ensure read/retrieval output hardening does not alter action-tool semantics.

---

### `tests/architecture/test_trusted_context_boundaries.py` (architecture test, structural boundary)

**Analog:** `tests/architecture/test_trusted_context_boundaries.py`

**Boundary scan pattern** (lines 16-30):
```python
def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports

def _class_defs(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
```

**Context boundary assertions** (lines 33-90):
```python
def test_only_platform_module_defines_trusted_context_models() -> None:
    assert TRUSTED_CONTEXT_OWNER.exists()

    definitions: list[tuple[str, str]] = []
    for path in sorted((ROOT / "src").glob("**/*.py")):
        if path.name == "__init__.py":
            continue
        for name in _class_defs(path):
            if name in {"TrustedContext", "MerchantScopeV1", "TrustedContextFactory"}:
                definitions.append((str(path.relative_to(ROOT)), name))

    assert definitions == [
        ("src/platform/trusted_context.py", "MerchantScopeV1"),
        ("src/platform/trusted_context.py", "TrustedContext"),
        ("src/platform/trusted_context.py", "TrustedContextFactory"),
    ]

def test_route_current_run_id_fields_delegate_to_legacy_identity_projection() -> None:
    for path in ROUTE_SEAMS:
        source = path.read_text()

        assert "project_to_legacy_agent_state_identity" in source
        assert '"current_run_id":' not in source
```

Run this high-blast structural subset if Phase 38 touches context construction or test helpers. It should usually remain unchanged.

## Shared Patterns

### Protected Envelope and Identity Fields
**Source:** `src/tools/contracts.py`  
**Apply to:** all implementation and tests in Phase 38

`ToolCallContext` identity fields must stay stable (lines 13-36):
```python
class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: dict[str, Any] | list[str]
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
    effective_at: str | None = None
    attempt: int = 1
    max_attempts: int = 1
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None
```

`ToolResultV2` envelope fields must stay stable (lines 71-98):
```python
class ToolResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_result.v2"] = "tool_result.v2"
    status: Literal[
        "success",
        "partial_success",
        "not_found",
        "permission_denied",
        "timeout",
        "unavailable",
        "conflict",
        "invalid_request",
        "invalid_response",
        "error",
    ]
    data: dict[str, Any] | None
    summary: str
    source_system: str
    data_freshness_at: datetime | None
    policy_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    error: ToolError | None = None
    retryable: bool = False
    retry_after_ms: int | None = None
    latency_ms: int
    audit_ref: str | None = None
```

Add field-set regression tests in `tests/tools/test_tool_platform.py`; do not edit `src/tools/contracts.py` for Phase 38.

### Projection Uses Envelope Refs, Not Data-Only IDs
**Source:** `src/tools/projection.py`  
**Apply to:** runtime output-validation tests and high-blast consumers

Projection builds normalized surfaces from safe data fields and envelope refs (lines 98-148):
```python
def _build_normalized_result(
    self,
    data: dict[str, Any],
    result: ToolResultV2,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    normalized["status"] = result.status
    normalized["source_system"] = result.source_system
    normalized["summary"] = result.summary[:500] if result.summary else ""

    for key in _SAFE_SCALAR_KEYS:
        if key in data and isinstance(data[key], (str, int, float, bool)):
            normalized[key] = data[key]

    policy_refs = self._extract_policy_evidence_refs(data)
    if policy_refs:
        normalized["policy_evidence_refs"] = policy_refs

    if result.business_fact_refs:
        normalized["business_fact_refs"] = self._business_fact_refs_from_envelope(result)
    if result.policy_evidence_refs:
        normalized["policy_evidence_refs"] = [
            {"evidence_id": ref.evidence_id, "doc_key": ref.doc_key}
            for ref in result.policy_evidence_refs
        ]

    if result.audit_ref:
        normalized["audit_ref"] = result.audit_ref

    if result.error is not None:
        normalized["error"] = {
            "code": result.error.code,
            "safe_message": result.error.safe_message,
            "retryable": result.error.retryable,
            "source": result.error.source,
        }

    case_memory = data.get("_case_memory_items") or data.get("items")
    if isinstance(case_memory, list):
        normalized["_case_memory_items"] = self._sanitize_case_memory(case_memory)

    return normalized
```

Do not validate or project raw `data` into authority refs.

### Strict Schema Style
**Source:** current Pydantic projections and validation helper  
**Apply to:** all eight read/retrieval `output_schema` declarations

Use:
- `type: "object"` with `properties`, `required`, and `additionalProperties: False`.
- `type: ["string", "null"]` for fields currently emitted as `None` or string.
- `type: "null"` only in helper tests; production no-data tools should use strict empty object schemas so accidental non-empty data fails closed when `data is not None`.
- `enum` for `retrieval_status` values: `strong_evidence`, `partial_evidence`, `no_evidence`, `error`.
- `items` for arrays and strict object schemas for case-memory items.

Avoid:
- Adding `jsonschema` as a dependency.
- Changing `ToolResultV2.data` to a non-dict type.
- Moving output validation into individual executors.
- Inventing success payload fields for `get_logistics`, `get_merchant_risk`, or `search_sop`.

### Validation Commands
**Source:** `38-VALIDATION.md` and `AGENTS.md`  
**Apply to:** all plans and verification notes

Use only project-entry commands:
```bash
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q
uv run ruff check src/tools/catalog.py src/tools/validation.py src/tools/runtime.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/agent/rag_context/test_verifier.py::test_business_fact_claim_requires_current_tool_system_refs tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q
```

Full relevant suite from `38-VALIDATION.md`:
```bash
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q
```

Do not use bare `pytest` or bare `python -m pytest` in MOCA.

### No-Edit Guardrail
**Apply to:** Phase 38 structural verification

Required structural check:
```bash
git diff -- docs/contract-spec.md src/tools/contracts.py
```

Expected result: no diff. If either file must change, the plan must explicitly record the hard blocker and Phase 39 ownership tradeoff.

## No Analog Found

None. Every scoped source/test target has an in-repo exact analog. The only unresolved product assumption is the strict no-data schema stance for `get_logistics`, `get_merchant_risk`, and `search_sop`; if reviewers reject that stance, planning needs a product decision or a future executor/schema phase.

## Metadata

**Analog search scope:** `src/tools/`, `src/business/`, `src/knowledge/`, `src/memory/`, `tests/tools/`, `tests/agent/`, `tests/conversation/`, `tests/architecture/`, `tests/test_execute_action.py`  
**Files scanned:** 20 source/test files plus Phase 38 research/validation inputs and project instructions  
**Pattern extraction date:** 2026-07-02  
**Local constraints observed:** `.planning/LOCAL-VALIDATION-ISSUES.md` was dirty before this pattern map; it was not modified. No source files were edited.  
