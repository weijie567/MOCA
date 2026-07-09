# Phase 62: Business Query And Drilldown Foundation - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 48 probable new/modified files from `62-CONTEXT.md`, `62-RESEARCH.md`, `62-UI-SPEC.md`, and `62-VALIDATION.md`
**Analogs found:** 48 / 48

## File Classification

Exact module names for the query package are planner discretion. The files below are the concrete likely targets implied by the phase inputs.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docs/contract-spec.md` | config | request-response | existing `docs/contract-spec.md` ToolPlatform/BusinessFactService sections | role-match |
| `src/business/query/__init__.py` | config | transform | `src/business/__init__.py` | role-match |
| `src/business/query/registry.py` | config | transform | `src/agent/intent_policy.py`, `src/rag/parsers/registry.py` | role-match |
| `src/business/query/schemas.py` | model | request-response | `src/business/schemas.py` | exact |
| `src/business/query/compiler.py` | service | CRUD | `src/business/service.py` | role-match |
| `src/business/query/projection.py` | utility | transform | `src/tools/projection.py`, `src/business/adapters.py` | role-match |
| `src/business/schemas.py` | model | request-response | `src/business/schemas.py` | exact |
| `src/business/service.py` | service | CRUD | `src/business/service.py` | exact |
| `src/business/adapters.py` | service | request-response | `src/business/adapters.py` | exact |
| `src/tools/contracts.py` | model | request-response | `src/tools/contracts.py` | exact |
| `src/tools/catalog.py` | config | request-response | `src/tools/catalog.py` | exact |
| `src/tools/policy.py` | middleware | request-response | `src/tools/policy.py` | exact |
| `src/tools/executors/business.py` | service | request-response | `src/tools/executors/business.py` | exact |
| `src/tools/projection.py` | utility | transform | `src/tools/projection.py` | exact |
| `src/agent/schemas.py` | model | request-response | `src/agent/schemas.py` | exact |
| `src/agent/intent_policy.py` | config | request-response | `src/agent/intent_policy.py` | exact |
| `src/agent/routing.py` | middleware | request-response | `src/agent/routing.py` | exact |
| `src/agent/state.py` | store | event-driven | `src/agent/state.py` | exact |
| `src/agent/nodes/receive_request.py` | controller | event-driven | `src/agent/state.py` durable/ephemeral split | role-match |
| `src/agent/nodes/contextual_intent_resolve.py` | controller | request-response | `src/agent/nodes/contextual_intent_resolve.py` | exact |
| `src/agent/nodes/slot_resolution_gate.py` | controller | request-response | `src/agent/nodes/slot_resolution_gate.py` | exact |
| `src/agent/nodes/investigate.py` | controller | event-driven | `src/agent/nodes/investigate.py` | exact |
| `src/agent/nodes/investigate_planner.py` | utility | request-response | `src/agent/nodes/investigate_planner.py` | exact |
| `src/agent/nodes/final_response.py` | controller | transform | `src/agent/nodes/final_response.py` | exact |
| `src/api/routers/agent_runs.py` | controller | streaming | `src/api/routers/agent_runs.py` | exact |
| `src/api/schemas/agent_runs.py` | model | streaming | `src/api/routers/agent_runs.py` payload helpers | role-match |
| `frontend/src/types/events.ts` | model | streaming | `frontend/src/types/events.ts` | exact |
| `frontend/src/hooks/useAgentRun.ts` | hook | streaming | `frontend/src/hooks/useAgentRun.ts` | exact |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | streaming | `frontend/src/components/timeline/TimelineStep.tsx` | exact |
| `frontend/src/components/details/DetailsPanel.tsx` | component | request-response | `frontend/src/components/details/DetailsPanel.tsx` | exact |
| `frontend/src/components/details/BusinessQueryResultTab.tsx` | component | request-response | `frontend/src/components/details/EvidenceTab.tsx` | role-match |
| `frontend/src/hooks/useAgentRun.test.ts` | test | streaming | `frontend/src/hooks/useAgentRun.test.ts` | exact |
| `frontend/e2e/agent-console.spec.ts` | test | streaming | `frontend/e2e/agent-console.spec.ts` | exact |
| `tests/business/test_business_query_registry.py` | test | transform | `tests/agent/test_required_slots.py` | role-match |
| `tests/business/test_business_query_schemas.py` | test | request-response | `tests/business/test_schemas.py` | exact |
| `tests/business/test_business_query_service.py` | test | CRUD | `tests/business/test_service.py` | exact |
| `tests/tools/test_catalog.py` | test | request-response | `tests/tools/test_catalog.py` | exact |
| `tests/tools/test_tool_platform.py` | test | request-response | `tests/tools/test_tool_platform.py` | exact |
| `tests/agent/test_required_slots.py` | test | request-response | `tests/agent/test_required_slots.py` | exact |
| `tests/agent/test_nodes/test_contextual_intent_resolve.py` | test | request-response | same file | exact |
| `tests/agent/test_nodes/test_slot_resolution_gate.py` | test | request-response | same file | exact |
| `tests/agent/test_nodes/test_investigate.py` | test | event-driven | same file | exact |
| `tests/agent/test_nodes/test_final_response.py` | test | transform | same file | exact |
| `tests/agent/test_graph.py` | test | event-driven | `tests/agent/test_graph.py` | exact |
| `tests/test_agent_runs_api.py` | test | streaming | `tests/test_agent_runs_api.py` | exact |
| `tests/eval/test_phase62_business_query_golden.py` | test | batch | `tests/eval/test_phase61_ux_golden.py` | role-match |
| `scripts/eval_phase62_business_query.py` | utility | batch | `scripts/eval_phase61_ux.py` | role-match |
| `evaluation/golden/phase62_business_query_cases.jsonl` | config | batch | `evaluation/golden/phase61_ux_cases.jsonl` | role-match |

## Pattern Assignments

### Query Registry And Schemas

**Apply to:** `src/business/query/registry.py`, `src/business/query/schemas.py`, `src/business/schemas.py`, `src/agent/schemas.py`, `src/agent/intent_policy.py`, `src/agent/routing.py`, `tests/business/test_business_query_registry.py`, `tests/business/test_business_query_schemas.py`, `tests/agent/test_required_slots.py`

**Analog:** `src/business/schemas.py`, `src/agent/intent_policy.py`, `src/rag/parsers/registry.py`

**Strict Pydantic boundary pattern** (`src/business/schemas.py` lines 55-83):
```python
class BusinessMetricQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: BusinessMetricId
    time_preset: BusinessMetricTimePreset | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    merchant_id: str | None = None
    status_filter: list[str] = Field(default_factory=list)

    @field_validator("merchant_id")
    @classmethod
    def _reject_wildcard_merchant_filter(cls, value: str | None) -> str | None:
        if value == "*":
            raise ValueError("merchant_id wildcard is not allowed in metric tool args")
        return value
```

Copy this for `BusinessQuerySpec`, filters, sort, cursor, answer context, and UI/prompt projection models: `ConfigDict(extra="forbid")`, bounded fields, validators for authority-bearing fields, and model validators for time/cursor consistency.

**Registry ownership pattern** (`src/agent/intent_policy.py` lines 19-29, 293-347):
```python
@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
    high_risk: bool = False
    critical_route_class: bool = False

class IntentPolicyRegistry:
    """Read-only view over current intent policy constants."""

    def definitions(self) -> Mapping[str, IntentDefinition]:
        return MappingProxyType(INTENT_DEFINITIONS)

    def get_definition(self, name: str) -> IntentDefinition | None:
        return INTENT_DEFINITIONS.get(name)
```

Use a frozen descriptor dataclass plus read-only registry accessors. The business-query registry should own operation/resource/metric/time/status/field/sort/cursor descriptors and expose read-only helpers used by agent, service, tool catalog, projection, eval, and frontend payload tests.

**Route/resolve registry pattern** (`src/rag/parsers/registry.py` lines 28-62):
```python
_ROUTES: dict[str, ParserRoute] = {
    "policy_markdown": ParserRoute("policy_markdown", frozenset({".md", ".markdown"})),
}

class ParserRegistry:
    def __init__(self, *, register_default_adapters: bool = True) -> None:
        self._adapters: dict[str, ParserAdapter] = {}

    def resolve(self, source_type: str, extension: str) -> ParserRoute | None:
        route = _ROUTES.get(source_type)
        if route is None:
            return None
        normalized_extension = extension.lower()
        if normalized_extension not in route.extensions:
            return None
        return route
```

Use this shape for compatibility lookups such as metric-id to query spec and resource/operation compatibility, returning `None` or a safe validation error instead of falling through to generic query behavior.

**Testing pattern** (`tests/business/test_schemas.py` lines 217-250):
```python
def test_metric_query_input_is_strict_and_rejects_authority_fields():
    query = BusinessMetricQueryInput.model_validate(
        {"metric_id": "order_count", "time_preset": "today", "merchant_id": "merchant-001"}
    )

    for payload in (
        {"metric_id": "order_count", "tenant_id": "tenant-attacker"},
        {"metric_id": "order_count", "merchant_scope": ["*"]},
        {"metric_id": "order_count", "merchant_id": "*"},
    ):
        with pytest.raises(ValidationError):
            BusinessMetricQueryInput.model_validate(payload)
```

New query schema tests should reject `tenant_id`, trusted scope, raw SQL, raw cursor tokens, unallowlisted fields, arbitrary filters, and wildcard merchant filters.

### BusinessFactService Runtime And Compiler

**Apply to:** `src/business/query/compiler.py`, `src/business/service.py`, `src/business/adapters.py`, `tests/business/test_business_query_service.py`

**Analog:** `src/business/service.py`, `src/business/adapters.py`

**Imports and constants pattern** (`src/business/service.py` lines 12-47):
```python
from pydantic import BaseModel, ValidationError
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ActionDraft, Order, RefundCase, Ticket
from src.platform.trusted_context import MerchantScopeV1
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2

NO_LEAK_BUSINESS_RESOURCE_MESSAGE = "Business resource unavailable for this request"
```

The compiler should use SQLAlchemy expressions from descriptors and DB models. Do not introduce raw SQL strings, generic list-all helpers, or tool/agent-side query conditions.

**Validate, authorize, then execute pattern** (`src/business/service.py` lines 171-191):
```python
async def query_business_metric(self, args: dict[str, Any], ctx: ToolCallContext) -> BusinessFactResultV1:
    try:
        query = BusinessMetricQueryInput.model_validate(args)
    except ValidationError:
        return self._safe_result(
            "invalid_request",
            resource_name="business_metric",
            tenant_id=ctx.tenant_id,
            source_system="business_fact_service",
            scope_check_result="unknown",
            code="BUSINESS_METRIC_INVALID_REQUEST",
            safe_message="Business metric request is invalid",
            error_source="caller",
        )

    merchant_ids = self._authorized_metric_merchant_ids(query, ctx)
    if merchant_ids is None:
        return self._permission_denied_result("business_metric", ctx.tenant_id)
```

Copy this ordering for `query_business`: strict spec validation first, then trusted scope resolution, then controlled execution. Out-of-scope detail/list requests must return denied/empty-safe without fetching by ID first.

**Scope helper pattern** (`src/business/service.py` lines 272-291):
```python
def _authorized_metric_merchant_ids(self, query: BusinessMetricQueryInput, ctx: ToolCallContext) -> list[str] | None:
    try:
        scope = (
            MerchantScopeV1(merchant_ids=ctx.merchant_scope)
            if isinstance(ctx.merchant_scope, list)
            else MerchantScopeV1.model_validate(ctx.merchant_scope)
        )
    except (TypeError, ValueError, ValidationError):
        return None
    if not scope.merchant_ids:
        return None
    if query.merchant_id is not None:
        if not scope.allows(merchant_id=query.merchant_id):
            return None
        return [query.merchant_id]
    return list(scope.merchant_ids)
```

Generalize this for authorized business-query scope. Keep action target merchant separate from query scope.

**Controlled SQLAlchemy aggregate/list pattern** (`src/business/service.py` lines 552-646):
```python
conditions = self._order_scope_conditions(tenant_id=tenant_id, merchant_uuid_ids=merchant_uuid_ids)
conditions.extend(self._time_conditions(Order.created_at, time_range))
if status_filter:
    conditions.append(Order.status.in_(status_filter))
value = await self.session.scalar(select(func.count(Order.id)).where(*conditions))
```

For list/detail/breakdown/compare, use fixed `select()` statements, descriptor-owned field allowlists, deterministic ordering, and `limit + 1` cursor detection. Apply tenant/scope/time filters before resource existence is observable.

**No-existence-leak error pattern** (`src/business/service.py` lines 1014-1029):
```python
def _permission_denied_result(self, resource_name: str, tenant_id: str, *, source_system: str = "business_fact_service"):
    return self._safe_result(
        "permission_denied",
        resource_name=resource_name,
        tenant_id=tenant_id,
        source_system=source_system,
        scope_check_result="denied",
        code="BUSINESS_FACT_PERMISSION_DENIED",
        safe_message=NO_LEAK_BUSINESS_RESOURCE_MESSAGE,
        error_source="caller",
    )
```

For unauthorized detail/list/id queries, copy this fail-closed shape: no facts, no business refs, no raw ID confirmation, no "not found" distinction for unauthorized objects.

**Strict projection adapter pattern** (`src/business/adapters.py` lines 20-33, 171-240):
```python
class _StrictProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class GetOrderInput(BaseModel):
    order_no: str = Field(min_length=1)

async def _adapt_read(...):
    try:
        projected = projection.model_validate(raw.get("data"))
    except ValidationError:
        return _invalid_response(source_system, latency_ms)

    return ToolResultV2(
        status="success",
        data=projected.model_dump(mode="json"),
        business_fact_refs=[BusinessFactRefV1(...)]
    )
```

Use strict resource projection models for UI-safe rows and detail payloads. Do not dump ORM rows or upstream raw payloads into `ToolResultV2.data`.

**Runtime tests to copy** (`tests/business/test_service.py` lines 299-313, 519-556):
```python
result = await service.query_business_metric(
    {"metric_id": "order_count", "merchant_id": "merchant-secret"},
    _context(permissions=["tool:query_business_metric"], merchant_scope={"merchant_ids": ["merchant-allowed"]}),
)

_assert_fail_closed(result, "permission_denied")
assert result.scope_check_result == "denied"
assert result.missing_required_facts == ["business_metric"]
assert "merchant-secret" not in result.model_dump_json()
assert service.calls == []
```

New service tests should prove invalid ranges, bad status/fields, empty scope, malicious authority fields, and unauthorized detail IDs all fail before query execution or existence disclosure.

### Tool Catalog, Policy, Platform, And Projection

**Apply to:** `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py`, `src/tools/executors/business.py`, `src/tools/projection.py`, `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`

**Analog:** `src/tools/catalog.py`, `src/tools/platform.py`, `src/tools/policy.py`, `src/tools/projection.py`, `src/tools/executors/business.py`

**Descriptor model pattern** (`src/tools/catalog.py` lines 14-33):
```python
class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_permission: str
    caller_allowlist: list[str]
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
```

`business_query` should be a read-only business executor tool with strict input/output schema and `caller_allowlist=("investigate",)`. Keep `query_business_metric` as a compatibility declaration that maps into the same service path.

**Current metric descriptor analog** (`src/tools/catalog.py` lines 504-527):
```python
_ToolDeclaration(
    name="query_business_metric",
    kind="read",
    input_schema={
        "type": "object",
        "properties": {
            "metric_id": _BUSINESS_METRIC_ID_SCHEMA,
            "time_preset": _BUSINESS_METRIC_TIME_PRESET_SCHEMA,
            "start_at": {"type": "string", "minLength": 1},
            "end_at": {"type": "string", "minLength": 1},
            "merchant_id": {"type": "string", "minLength": 1},
            "status_filter": _BUSINESS_METRIC_STATUS_FILTER_SCHEMA,
        },
        "required": ["metric_id"],
        "additionalProperties": False,
    },
    output_schema=_BUSINESS_METRIC_OUTPUT_SCHEMA,
    side_effect="read_only",
    caller_allowlist=("investigate",),
    event_family="tool_call_*",
    resource_type="business_metric",
    executor="business",
)
```

For `business_query`, generate or derive enum/schema values from the registry. The tool schema must not expose `tenant_id`, `merchant_scope`, raw SQL, raw cursor tokens, or arbitrary filter JSON.

**Platform boundary pattern** (`src/tools/platform.py` lines 28-54, 112-133):
```python
class ToolPlatform:
    def __init__(..., projector: ToolResultProjector | None = None) -> None:
        self._catalog = catalog or ToolCatalog()
        self._policy_engine = policy_engine or ToolPolicyEngine(catalog=self._catalog)
        self._projector = projector or ToolResultProjector()
        self._runtime = runtime or ToolRuntime(...)

    async def invoke(self, tool_name: str, args: dict[str, Any], ctx: ToolCallContext, *, session=None):
        tool_result, policy_decision, policy_event_id, projection = await self._runtime.invoke(...)
        return ToolInvocationOutcome(...)
```

Graph nodes should continue to call `ToolPlatform.visible_tools()` and `ToolPlatform.invoke()`, not `BusinessFactService` directly.

**Policy visibility pattern** (`src/tools/policy.py` lines 311-341, 365-382):
```python
if caller not in descriptor.caller_allowlist:
    visible = False
    reason_codes.append("caller_not_allowed")

if descriptor.required_permission not in ctx.permissions:
    visible = False
    reason_codes.append("missing_permission")

return ToolViewV1(
    name=descriptor.name,
    description=descriptor.description,
    input_schema=project_prompt_safe_input_schema(descriptor.input_schema),
    safe_usage_notes=safe_notes,
    result_contract_version="tool_result.v2",
)
```

Add `tool:business_query` permission mapping only through trusted auth/scope policy. If keeping `metrics:read` compatibility, test both `business_query` and `query_business_metric` visibility.

**Projection allowlist pattern** (`src/tools/projection.py` lines 9-73, 129-187, 299-350):
```python
_RAW_SENTINEL_KEYS = {"raw", "raw_payload", "raw_tool_payload", "raw_args", "private_reasoning", "debug_trace", "secret", "pii"}

def _build_normalized_result(self, data: dict[str, Any], result: ToolResultV2) -> dict[str, Any]:
    normalized["status"] = result.status
    normalized["source_system"] = result.source_system
    normalized["summary"] = result.summary[:500] if result.summary else ""
    metric_result = self._extract_metric_result(data)
    if metric_result:
        normalized.update(metric_result)
```

Add `_BUSINESS_QUERY_RESULT_KEYS` and `_extract_business_query_result` beside `_extract_metric_result`. Keep prompt text bounded, and expose only projected rows/metadata, not raw rows.

**Business executor pattern** (`src/tools/executors/business.py` lines 11-31):
```python
class BusinessToolExecutor:
    executor_name = "business"

    def __init__(self, session: AsyncSession, service: BusinessToolService | BusinessFactService | None = None) -> None:
        if service is None:
            fact_service = BusinessFactService.with_default_registry(session)
            self.service = BusinessToolService(session, fact_service=fact_service)

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        return await self.service.invoke_tool(name, args, ctx)
```

Keep the executor thin. Business query execution belongs in `BusinessFactService` / `BusinessToolService`.

**Catalog/policy tests to copy** (`tests/tools/test_catalog.py` lines 263-283; `tests/tools/test_tool_platform.py` lines 314-337):
```python
assert descriptor.kind == "read"
assert descriptor.side_effect == "read_only"
assert descriptor.required_permission == "tool:query_business_metric"
assert descriptor.caller_allowlist == ["investigate"]
assert descriptor.input_schema["additionalProperties"] is False
assert "tenant_id" not in descriptor.input_schema["properties"]
assert "merchant_scope" not in descriptor.input_schema["properties"]

allowed_views = await platform.visible_tools(caller="investigate", ctx=_ctx(permissions=["tool:query_business_metric"]))
denied_views = await platform.visible_tools(caller="investigate", ctx=_ctx(permissions=[]))
wrong_caller_views = await platform.visible_tools(caller="final_response", ctx=_ctx(...))
```

### Agent Parser, Slot, Drilldown State, And Investigation

**Apply to:** `src/agent/state.py`, `src/agent/nodes/receive_request.py`, `src/agent/nodes/contextual_intent_resolve.py`, `src/agent/nodes/slot_resolution_gate.py`, `src/agent/nodes/investigate.py`, `src/agent/nodes/investigate_planner.py`, `tests/agent/test_nodes/test_contextual_intent_resolve.py`, `tests/agent/test_nodes/test_slot_resolution_gate.py`, `tests/agent/test_nodes/test_investigate.py`, `tests/agent/test_graph.py`

**Analog:** `src/agent/state.py`, `src/agent/routing.py`, `src/agent/nodes/contextual_intent_resolve.py`, `src/agent/nodes/slot_resolution_gate.py`, `src/agent/nodes/investigate.py`

**State durable/ephemeral split** (`src/agent/state.py` lines 61-75, 76-101):
```python
class AgentState(TypedDict, total=False):
    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    active_slot_metadata: dict[str, Any] | None
    last_intent: str | None
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
```

Add `last_query_spec`, `last_answer_context`, and `result_cursor` as durable same-thread query context. Do not store raw rows in state.

**Current metric duplication to replace** (`src/agent/routing.py` lines 38-63):
```python
SUPPORTED_METRIC_IDS = frozenset({"order_count", "refund_case_count", "pending_ticket_count", "coupon_record_count", "merchant_refund_rate"})
METRIC_RESOURCE_TYPES = {"order_count": "order", "refund_case_count": "refund_case", ...}
METRIC_STATUS_ALLOWLISTS = {"order_count": frozenset({"pending", "paid", "shipped", "delivered", "completed"}), ...}
```

Phase 62 should replace this with registry-derived descriptors. Avoid copying these literals into new query branches.

**Slot policy pattern** (`src/agent/routing.py` lines 490-554, 600-628):
```python
if intent == "business_metric_query":
    metric_missing, metric_reason_codes = _apply_metric_slot_policy(state, resolved_slots)
    if metric_missing:
        return metric_missing, "clarification_gate", metric_reason_codes
    return [], "investigate", metric_reason_codes

if preset == "current_snapshot":
    resolved_slots.pop("metric_time_preset", None)
    return True, "metric_time_range_required"
```

Generalize this into expected slot types: time, resource id, merchant filter, field/drilldown request, sort/limit/cursor. Service remains the final compatibility gate.

**Deterministic parser/follow-up pattern** (`src/agent/nodes/contextual_intent_resolve.py` lines 598-644, 743-850):
```python
metric_slots = _deterministic_metric_candidate_slots(user_text)
if metric_slots is not None:
    return _business_metric_query_update(state, pre_route, started_at, metric_slots)

flow = state.get("active_flow_state") if isinstance(state.get("active_flow_state"), dict) else None
if flow and flow.get("kind") == "pending_required_slot":
    pending_metric_slots = _pending_metric_time_answer_slots(primary_intent, flow, user_text)
    if pending_metric_slots:
        merged_candidate_slots = _merge_flow_metric_slots(flow, pending_metric_slots)
        return _deterministic_classification_update(..., routing_hints={"workflow_state_resolution": "answered_pending_metric_time_range"})
```

For drilldown, use the same same-thread flow guard but derive from `last_query_spec` and `last_answer_context`, not from final answer text or frontend payloads.

**Slot resolution node pattern** (`src/agent/nodes/slot_resolution_gate.py` lines 64-92, 137-153):
```python
result = await structured_llm.ainvoke(messages)
extracted = _merge_deterministic_metric_slots(result.model_dump(), state)
resolution_state = _state_with_metric_parser_hint(state, extracted)
resolution = resolve_slots_with_provenance(resolution_state)
return _node_update(...)
```

Move deterministic business-query slot extraction to shared registry/resolver helpers. Keep node output shape: `extracted_slots`, `active_slots`, `missing_required_slots`, `slot_resolution_trace`, and `routing_hints`.

**Investigation ToolPlatform pattern** (`src/agent/nodes/investigate.py` lines 207-330, 342-384):
```python
tool_views = await tool_platform.visible_tools(caller=visibility_caller, ctx=visibility_ctx, session=session)
...
outcome = await tool_platform.invoke(tool_name, args, tool_ctx, session=session)
result = outcome.tool_result
_accumulate_tool_result(context, descriptor, tool_name, result, prompt_summary, outcome.projection)
...
business_context = {
    "facts": context["facts"],
    "business_fact_refs": context["business_fact_refs"],
    "tool_results": context["tool_results"],
    "missing_required_facts": _missing_required_facts(state, context),
    "errors": context["errors"],
    "status": _business_status(context),
}
```

Business-query and drilldown calls must enter through this path. The deterministic fallback may build `business_query` args from `active_slots` / derived query spec, but must not compile SQL or call service methods in the node.

**Metric fallback compatibility pattern** (`src/agent/nodes/investigate.py` lines 105-157):
```python
def _metric_fallback_step(...):
    args = _metric_args_from_active_slots(state)
    if args is None:
        return None
    return {"next_tool": _METRIC_TOOL_NAME, "args": args, "reason": "deterministic business metric fallback"}
```

Keep `query_business_metric` compatibility by mapping to `BusinessQuerySpec` and then calling the same `business_query` tool/service path.

**Planner allowlist pattern** (`src/agent/nodes/investigate_planner.py` lines 9-21):
```python
INVESTIGATE_ALLOWED_TOOL_NAMES = frozenset(
    {"get_order", "get_refund_case", "get_ticket", "get_logistics", "get_merchant_risk", "query_business_metric", "search_policy", "search_sop", "search_case_memory"}
)
```

When adding `business_query`, update this or derive it from `ToolCatalog.investigate_tool_names()` and add a parity test. Phase 61 debt shows catalog/planner drift is a real risk.

**Graph tests to copy** (`tests/agent/test_graph.py` lines 909-987, 990-1009):
```python
final_state = await graph.ainvoke(_state("今天有多少退款单"), _config(tool_platform, events))
assert [call[0] for call in tool_platform.calls] == ["query_business_metric"]
assert final_state["llm_outputs"]["final_response"]["response_kind"] == "metric_answer"

first_state = await graph.ainvoke(_state("现在有多少订单", thread_id), config)
assert first_state["missing_required_slots"] == [{"all_of": ["metric_time_range"]}]

second_state = await graph.ainvoke(_state("本周", thread_id), config)
assert [call[0] for call in tool_platform.calls] == ["query_business_metric"]
assert tool_platform.calls[0][1]["time_preset"] == "this_week"
```

Add Phase 62 graph tests for `本周多少订单？` then `订单号是多少？`: first turn aggregate, second turn list derived from safe query context and fresh ToolPlatform/BusinessFactService validation.

### Final Response, API/SSE Payload, And Frontend UI

**Apply to:** `src/agent/nodes/final_response.py`, `src/api/routers/agent_runs.py`, `src/api/schemas/agent_runs.py`, `frontend/src/types/events.ts`, `frontend/src/hooks/useAgentRun.ts`, `frontend/src/components/timeline/TimelineStep.tsx`, `frontend/src/components/details/DetailsPanel.tsx`, `frontend/src/components/details/BusinessQueryResultTab.tsx`, `frontend/src/hooks/useAgentRun.test.ts`, `frontend/e2e/agent-console.spec.ts`, `tests/test_agent_runs_api.py`

**Analog:** `src/agent/nodes/final_response.py`, `src/api/routers/agent_runs.py`, `frontend/src/types/events.ts`, `frontend/src/components/timeline/TimelineStep.tsx`, `frontend/src/components/details/DetailsPanel.tsx`, `frontend/src/components/details/EvidenceTab.tsx`

**Final response metric pattern** (`src/agent/nodes/final_response.py` lines 334-397, 457-484, 1063-1072):
```python
def _metric_response_text(metric: dict[str, Any]) -> str:
    if _metric_is_permission_denied(metric):
        return "当前权限范围内无法提供该商户指标。"
    first_line = f"{display_value}（{label}）。"
    second_line = f"范围：{_metric_scope_label(metric)}；时间：{_metric_time_label(metric)}；筛选：{_metric_filters_label(metric)}；新鲜度：{_metric_freshness_label(metric)}。"
    return "\n".join([first_line, second_line, *caveats])

def _metric_llm_output(response_text: str, metric: dict[str, Any]) -> dict[str, Any]:
    return {"response_text": response_text, "response_kind": "metric_answer", "metric": _safe_metric_metadata(metric)}
```

Add `_business_query_fact`, `_business_query_response_text`, and `_business_query_llm_output` beside this. `business_query_answer` must produce number/list/detail first, then safe scope/time/filter/freshness metadata. It must not claim RAG evidence for business facts.

**API safe payload pattern** (`src/api/routers/agent_runs.py` lines 58-66, 1216-1233):
```python
_SAFE_METRIC_PAYLOAD_FIELDS = ("metric_id", "metric_label", "scope_label", "time_label", "filters_label", "freshness_label", "safe_reason")

def _final_response_payload(final_response: str, final_state: dict[str, Any]) -> dict[str, Any]:
    payload = {"final_response": final_response, _TARGET_CONTEXT_KEY: _project_target_context(final_state)}
    response_projection = _as_mapping(_as_mapping(final_state.get("llm_outputs")).get("final_response"))
    response_kind = response_projection.get("response_kind") or _infer_response_kind(final_state, response_projection)
    if response_kind == "metric_answer":
        metric_payload = _safe_metric_payload(response_projection.get("metric"))
        if metric_payload:
            payload["metric"] = metric_payload
```

Add `_SAFE_BUSINESS_QUERY_PAYLOAD_FIELDS` and `_safe_business_query_payload`. Include only UI-safe projected fields from `62-UI-SPEC.md`: operation, labels, rows, allowed drilldowns, row count/limit, safe reason, and cursor label. No raw rows, raw filters, hidden scope internals, prompt payloads, tool args, or stack traces.

**Frontend event type pattern** (`frontend/src/types/events.ts` lines 22-57):
```ts
export interface SseEventPayload {
  final_response?: string
  response_kind?: 'small_talk' | 'direct_response' | 'clarification' | 'unsupported' | 'metric_answer' | 'rag_answer' | string
  safe_reason?: string
  metric?: {
    metric_id?: string
    metric_label?: string
    scope_label?: string
    time_label?: string
  }
}
```

Add `business_query?: BusinessQueryPayload` with typed `operation: 'aggregate' | 'list' | 'detail' | 'breakdown' | 'compare'`, safe labels, bounded rows, `allowed_drilldowns`, and cursor display capabilities.

**Timeline label pattern** (`frontend/src/components/timeline/TimelineStep.tsx` lines 36-61, 98-153):
```tsx
function metricSubtitle(step: SseEvent) {
  const metric = metricPayload(step)
  const metricLabel = metric.metric_label || metric.metric_id || 'business_metric'
  const scopeLabel = metric.scope_label || '当前权限范围'
  return `metric: ${metricLabel} · scope: ${scopeLabel}`
}

if (kind === 'metric_answer' || step.payload?.metric || step.payload?.metric_id) {
  return step.status === 'running' ? '正在查询业务指标' : '业务指标查询完成'
}
```

Add `businessQueryPayload`, `businessQuerySubtitle`, and operation-specific labels from `62-UI-SPEC.md`. Keep the stable `grid-cols-[20px_1fr_auto]` row and truncated subtitle; do not render row values in timeline except safe result labels/counts.

**Details tab pattern** (`frontend/src/components/details/DetailsPanel.tsx` lines 1-17, 59-113):
```tsx
type DetailsTab = 'evidence' | 'approval' | 'trace' | 'run'

<TabsList>
  <TabsTrigger value="evidence">Evidence</TabsTrigger>
  <TabsTrigger value="approval">Approval</TabsTrigger>
  <TabsTrigger value="trace">Trace</TabsTrigger>
  <TabsTrigger value="run">Run Info</TabsTrigger>
</TabsList>
```

Add `Result` first in tab order. The new `BusinessQueryResultTab` should follow `EvidenceTab` local-state/loading patterns but consume latest safe SSE payload from `steps`, not fetch raw data.

**EvidenceTab UI-state analog** (`frontend/src/components/details/EvidenceTab.tsx` lines 37-63, 65-86, 89-145):
```tsx
useEffect(() => {
  if (!runId) return
  let cancelled = false
  void getRunEvidence(runId).then((result) => {
    if (cancelled) return
    ...
  })
  return () => {
    cancelled = true
  }
}, [runId, refreshKey])

if (evidence.length === 0) {
  return <div className="rounded-md border border-dashed border-border p-4 text-body text-muted-foreground">暂无政策证据</div>
}
```

Use the same cancel/empty/error pattern, but render aggregate/list/detail/breakdown/compare from safe payloads. Avoid nested cards inside Details; use dense tables/lists and definition lists.

**SSE stale-run guard pattern** (`frontend/src/hooks/useAgentRun.ts` lines 187-193, 339-360):
```ts
const runGenerationRef = useRef(0)

const attachStream = useCallback((runId: string, assistantMessageId: string, generation: number) => {
  controllerRef.current = connectToRunEvents(runId, {
    onEvent(event) {
      if (generation !== runGenerationRef.current) return
      setState((current) => {
        if (current.runId && current.runId !== runId) return current
```

Business-query Details must use the latest active run only. Keep this generation guard for late SSE callbacks.

**Frontend tests to copy** (`frontend/src/hooks/useAgentRun.test.ts` lines 323-416; `frontend/e2e/agent-console.spec.ts` lines 101-135):
```tsx
expected: ['业务指标查询完成', 'metric: 退款单数 · scope: 当前权限范围'],
forbidden: ['routing_hints', 'SHOULD_NOT_RENDER']

await expect(page.getByText('routing_hints')).toHaveCount(0)
await expect(page.getByText('raw_args')).toHaveCount(0)
await expectTimelineRowsDoNotOverlap(page)
```

Add cases for all five operations, raw payload rejection, no overlap, disabled/omitted drilldown controls, and cursor label safety.

### Eval And Golden Data

**Apply to:** `scripts/eval_phase62_business_query.py`, `evaluation/golden/phase62_business_query_cases.jsonl`, `tests/eval/test_phase62_business_query_golden.py`

**Analog:** `scripts/eval_phase61_ux.py`, `evaluation/golden/phase61_ux_cases.jsonl`, `tests/eval/test_phase61_ux_golden.py`

**Eval script pattern** (`scripts/eval_phase61_ux.py` lines 1-8, 19-43, 45-81, 84-131):
```python
"""Validate the Phase 61 UX and metric golden set.

Usage:
    uv run python scripts/eval_phase61_ux.py
"""

ALLOWED_RESPONSE_KINDS = frozenset({"small_talk", "clarification", "unsupported", "metric_answer"})
REQUIRED_CATEGORIES = frozenset({"metric_missing_time_range", "unauthorized_merchant_metric", "unsupported_metric"})

def load_cases(path: str | Path = DEFAULT_GOLDEN_SET) -> list[dict[str, Any]]:
    dataset = Path(path)
    return [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]

def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ...
```

Copy this deterministic validator style. Phase 62 required categories should include drilldown, permission boundary, list/detail no-existence-leak, breakdown runtime example, compare runtime example, projection bounds, clarification, unsupported.

**Golden case pattern** (`evaluation/golden/phase61_ux_cases.jsonl` lines 6, 13):
```json
{"category":"today_refund_count","prompt":"今天有多少退款单","expected_response_kind":"metric_answer","expected_tool":"query_business_metric","expected_metric_id":"refund_case_count","must_not_contain":["政策依据","检索到证据","跨商户"]}
{"category":"unauthorized_merchant_metric","prompt":"查询商户 MERCHANT-SECRET 本月退款率","expected_no_leak":true,"sensitive_terms":["MERCHANT-SECRET","商户是否存在"],"must_not_contain":["MERCHANT-SECRET 存在","MERCHANT-SECRET 不存在","已确认该商户"]}
```

Add multi-turn rows or grouped case objects for `本周多少订单？` -> `订单号是多少？`, including expected first operation `aggregate`, second operation `list`, expected tool `business_query`, expected safe identifiers, and no raw cursor/scope leakage.

**Golden test pattern** (`tests/eval/test_phase61_ux_golden.py` lines 11-40):
```python
cases = load_cases(DATASET)
errors = validate_cases(cases)
assert errors == []
categories = {case["category"] for case in cases}
assert REQUIRED_CATEGORIES <= categories
```

## Shared Patterns

### Trusted Scope And Permissions

**Source:** `src/platform/trusted_context.py` lines 24-30, 41-86, 122-163; `src/platform/context_projections.py` lines 86-120
**Apply to:** service, tool, agent, API, tests

```python
SCOPE_TO_TOOL_PERMISSION = {
    "orders:read": "tool:get_order",
    "refunds:read": "tool:get_refund_case",
    "tickets:read": "tool:get_ticket",
    "knowledge:read": "tool:search_policy",
    "metrics:read": "tool:query_business_metric",
}

class MerchantScopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def allows(self, merchant_id: str | None = None, category: str | None = None, risk_level: str | None = None) -> bool:
        if not self.merchant_ids:
            return False
        ...
```

Business query authority comes from `TrustedContext -> ToolCallContext`, never from user text, LLM output, tool args, or frontend payload.

### No Raw Data Projection

**Source:** `src/tools/projection.py` lines 9-21, 278-297, 428-451
**Apply to:** tool results, final response, API payload, frontend details

```python
redaction_applied = _has_raw_sentinels_in_dict(result.data or {})
metric_summary = self._metric_prompt_summary(normalized)
summary = metric_summary["text"] if metric_summary else normalized.get("summary", result.summary[:500])
```

Every business-query projection needs normalized, prompt, UI, audit/debug separation. Prompt/UI surfaces must be bounded and allowlisted.

### Tool Boundary Backstop

**Source:** `tests/architecture/test_tool_contract_backstops.py` lines 93-140
**Apply to:** `BusinessToolExecutor`, `BusinessFactService`, new query runtime

```python
result = await executor.execute("get_order", {"order_no": "ORD-1"}, _ctx())
assert result.status == "success"
source = inspect.getsource(BusinessToolExecutor)
for forbidden in ("src.repositories", "OrderRepository", "RefundRepository", "TicketRepository"):
    assert forbidden not in source

result = await service.get_order("ORD-SECRET-001", _ctx(merchant_scope={"merchant_ids": []}))
assert result.status == "permission_denied"
assert result.fact is None
assert result.business_fact_refs == []
```

Add a Phase 62 backstop that agent nodes/tools do not import DB repositories/models for business-query compilation and that invalid scope is denied before detail/list execution.

### MOCA Validation Entrypoints

**Source:** `62-VALIDATION.md` and project rules
**Apply to:** every plan verification command

Use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or repository `.venv/bin/...`. Bare `pytest` and bare `python -m pytest` are invalid evidence in MOCA.

Suggested targeted commands from the validation strategy:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business tests/tools tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short
npm --prefix frontend test
npm --prefix frontend run e2e
```

## No Analog Found

No file is completely without an analog, but these have no exact current implementation and should use role-match patterns:

| File | Role | Data Flow | Use Instead |
|---|---|---|---|
| `src/business/query/compiler.py` | service | CRUD | `src/business/service.py` controlled SQLAlchemy metric methods |
| `src/business/query/registry.py` | config | transform | `src/agent/intent_policy.py` frozen registry plus `src/rag/parsers/registry.py` resolver |
| `src/business/query/projection.py` | utility | transform | `src/tools/projection.py` allowlisted prompt projection plus `src/business/adapters.py` strict projection models |
| `frontend/src/components/details/BusinessQueryResultTab.tsx` | component | request-response | `frontend/src/components/details/EvidenceTab.tsx` state/loading/empty pattern and `TimelineStep.tsx` safe payload labels |
| `scripts/eval_phase62_business_query.py` | utility | batch | `scripts/eval_phase61_ux.py` deterministic JSONL validator |

## Metadata

**Analog search scope:** `src/business`, `src/tools`, `src/agent`, `src/api`, `frontend/src`, `frontend/e2e`, `tests`, `evaluation`, `scripts`, `docs`, `.planning`

**Strongest analogs read:**
- `src/business/schemas.py`
- `src/business/service.py`
- `src/business/adapters.py`
- `src/tools/catalog.py`
- `src/tools/contracts.py`
- `src/tools/platform.py`
- `src/tools/policy.py`
- `src/tools/projection.py`
- `src/tools/executors/business.py`
- `src/agent/schemas.py`
- `src/agent/state.py`
- `src/agent/intent_policy.py`
- `src/agent/routing.py`
- `src/agent/nodes/contextual_intent_resolve.py`
- `src/agent/nodes/slot_resolution_gate.py`
- `src/agent/nodes/investigate.py`
- `src/agent/nodes/investigate_planner.py`
- `src/agent/nodes/final_response.py`
- `src/api/routers/agent_runs.py`
- `frontend/src/types/events.ts`
- `frontend/src/hooks/useAgentRun.ts`
- `frontend/src/components/timeline/TimelineStep.tsx`
- `frontend/src/components/details/DetailsPanel.tsx`
- `frontend/src/components/details/EvidenceTab.tsx`
- matching backend/frontend/eval tests

**Pattern extraction date:** 2026-07-09
