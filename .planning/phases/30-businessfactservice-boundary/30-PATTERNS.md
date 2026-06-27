# Phase 30: BusinessFactService Boundary - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 12 planned new/modified files + 2 reference-only source analogs
**Analogs found:** 14 / 14

## File Classification

| File | Plan Classification | Role | Data Flow | Closest Analog | Match Quality |
|------|---------------------|------|-----------|----------------|---------------|
| `src/business/schemas.py` | Plan 30-01 source edit | model | transform | `src/tools/contracts.py` | role-match |
| `src/business/service.py` | Plan 30-01 and 30-02 source edit | service | request-response / CRUD read | `src/business/service.py` | exact |
| `src/business/adapters.py` | Reference-only source analog | utility / adapter | transform | `src/business/adapters.py` | exact |
| `src/business/__init__.py` | Plan 30-01 source edit | provider / public export | transform | `src/business/__init__.py` | exact |
| `src/tools/executors/business.py` | Plan 30-02 source edit | service / executor | request-response | `src/tools/executors/business.py` | exact |
| `src/tools/projection.py` | Plan 30-03 source edit | utility | transform | `src/tools/projection.py` | exact |
| `src/agent/nodes/investigate.py` | Reference-only source analog | controller / graph node | event-driven / request-response | `src/agent/nodes/investigate.py` | exact |
| `tests/business/test_schemas.py` | Plan 30-01 test edit | test | contract validation | `tests/business/test_schemas.py` | exact |
| `tests/business/test_service.py` | Plan 30-01 and 30-02 test edit | test | service / integration | `tests/business/test_service.py` | exact |
| `tests/business/test_adapters.py` | Plan 30-02 test edit | test | transform / adapter | `tests/business/test_adapters.py` | exact |
| `tests/tools/test_tool_platform.py` | Plan 30-02 test edit | test | platform / integration | `tests/tools/test_tool_platform.py` | exact |
| `tests/agent/test_nodes/test_investigate.py` | Plan 30-03 test edit | test | graph / event-driven | `tests/agent/test_nodes/test_investigate.py` | exact |
| `tests/agent/rag_context/test_authority_boundaries.py` | Plan 30-03 test edit | test | authority-boundary transform | `tests/agent/rag_context/test_authority_boundaries.py` | exact |
| `tests/agent/test_policy_retrieval_ownership.py` | Plan 30-03 test edit | test | authority-boundary integration | `tests/agent/test_policy_retrieval_ownership.py` | exact |

## Pattern Assignments

### `src/business/schemas.py` (model, transform)

**Analog:** `src/tools/contracts.py`; keep public schemas strict and Pydantic-based.

**Imports / strict schema pattern** (`src/tools/contracts.py` lines 5-14):
```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.knowledge.schemas import EvidenceRefV1


class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

**Business ref contract to reuse** (`src/tools/contracts.py` lines 58-68):
```python
class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
    resource_version: str | None
    data_freshness_at: datetime | None
    retrieved_at: datetime
```

**Existing context schema to extend** (`src/business/schemas.py` lines 20-31):
```python
class BusinessContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_context.v1"] = "business_context.v1"
    tenant_id: str
    status: Literal["complete", "partial", "insufficient", "error"]
    facts: dict[str, Any]
    business_fact_refs: list[BusinessFactRefV1]
    tool_results: list[ToolResultV2]
    missing_required_facts: list[str]
    errors: list[ToolError]
    data_freshness_at: datetime | None
```

**Target contract source** (`docs/contract-spec.md` lines 368-390): add `BusinessFactResultV1` with `schema_version`, `tenant_id`, status enum, nullable `resource_version` / `data_freshness_at`, `source_system`, `scope_check_result`, `missing_required_facts`, and `safe_errors`.

### `src/business/service.py` (service, request-response / CRUD read)

**Analog:** current `BusinessToolService`; copy registry, retry, validation, aggregation, and local safe error patterns, but make `BusinessFactService` the public authority and return `BusinessFactResultV1` from per-resource reads.

**Tool registry pattern** (`src/business/service.py` lines 37-59):
```python
BUSINESS_READ_TOOLS: dict[str, BusinessReadToolDefinition] = {
    "get_order": BusinessReadToolDefinition(
        input_model=GetOrderInput,
        adapter=get_order_adapter,
        slot_name="order_id",
        resource_name="order",
        argument_name="order_no",
    ),
    "get_refund_case": BusinessReadToolDefinition(
        input_model=GetRefundCaseInput,
        adapter=get_refund_case_adapter,
        slot_name="refund_case_id",
        resource_name="refund_case",
        argument_name="refund_case_no",
    ),
    "get_ticket": BusinessReadToolDefinition(
        input_model=GetTicketInput,
        adapter=get_ticket_adapter,
        slot_name="ticket_id",
        resource_name="ticket",
        argument_name="ticket_id",
    ),
}
```

**Retry and dispatch pattern** (`src/business/service.py` lines 121-157):
```python
async def invoke_tool(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    """Invoke one logical tool call, retrying only explicitly retryable results."""

    if not _merchant_scope_allows(ctx.merchant_scope):
        return self._local_error(
            "permission_denied",
            "Merchant scope is required",
            code="EMPTY_MERCHANT_SCOPE",
        )

    if ctx.attempt > ctx.max_attempts:
        return self._local_error(
            "error",
            "Tool retry limit exhausted",
            code="MAX_ATTEMPTS_EXHAUSTED",
        )

    for attempt in range(ctx.attempt, ctx.max_attempts + 1):
        attempt_ctx = ctx.model_copy(update={"attempt": attempt})
        result = await self._invoke_adapter(name, args, attempt_ctx)
        if result.status == "success" or result.retryable is not True:
            return result
    return result
```

**Validation and safe adapter error pattern** (`src/business/service.py` lines 159-194):
```python
try:
    input_model = definition.input_model.model_validate(args)
except ValidationError:
    return self._local_error(
        "invalid_request",
        "Business read request is invalid",
        code="INVALID_BUSINESS_REQUEST",
    )

try:
    result = await definition.adapter(input_model, ctx, self.session)
except Exception:
    return self._local_error(
        "error",
        "Business read failed",
        code="ADAPTER_ERROR",
        source="adapter",
    )
if not isinstance(result, ToolResultV2):
    return self._local_error(
        "invalid_response",
        "Business read returned an invalid response",
        code="INVALID_ADAPTER_RESPONSE",
        source="adapter",
    )
```

**Context aggregation pattern** (`src/business/service.py` lines 196-275): copy the `fetch_context` loop shape: derive reads from slots, use distinct `tool_call_id`, aggregate facts/refs only from successful results, collect missing facts/errors otherwise, and compute `complete` / `partial` / `insufficient` / `error`.

**No-leak local error pattern** (`src/business/service.py` lines 277-298): denied/unavailable/error results must set `data=None`, `policy_evidence_refs=[]`, `business_fact_refs=[]`, `data_freshness_at=None`, and a safe `ToolError`.

**Scope proof source to hide behind service** (`src/integrations/demo_business/authz.py` lines 11-43):
```python
MERCHANT_BOUND_ROLES = {"support", "manager", "merchant"}
PLATFORM_ADMIN_ROLES = {"admin"}

async def merchant_can_access(..., role: str, merchant_id: UUID) -> bool:
    ...
    if user is None or user.role != role:
        return False
    if user.role in PLATFORM_ADMIN_ROLES:
        return True
    if user.role not in MERCHANT_BOUND_ROLES:
        return False
    return user.merchant_id is not None and user.merchant_id == merchant_id
```

### `src/business/adapters.py` (utility / adapter, transform)

**Analog:** existing safe adapters. Keep raw integration responses private; project only strict data, safe errors, and service-approved refs.

**Strict projection models** (`src/business/adapters.py` lines 20-33):
```python
class _StrictProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class GetOrderInput(BaseModel):
    order_no: str = Field(min_length=1)


class GetRefundCaseInput(BaseModel):
    refund_case_no: str = Field(min_length=1)


class GetTicketInput(BaseModel):
    ticket_id: str = Field(min_length=1)
```

**Raw error mapping pattern** (`src/business/adapters.py` lines 75-111):
```python
_ERROR_MAPPING: dict[str, tuple[str, _ErrorSource, bool, str]] = {
    "FORBIDDEN": ("permission_denied", "caller", False, "Business resource access denied"),
    "DB_TIMEOUT": ("timeout", "adapter", True, "Business data source timed out"),
    "VALIDATION_ERROR": ("invalid_request", "caller", False, "Business read request is invalid"),
    "DB_ERROR": ("error", "adapter", False, "Business data source failed"),
}

def _error_result(...) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=summary,
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(code=code, safe_message=summary, retryable=retryable, source=source),
        retryable=retryable,
        retry_after_ms=None,
        latency_ms=latency_ms,
        audit_ref=None,
    )
```

**Success projection / provenance pattern** (`src/business/adapters.py` lines 203-232):
```python
projected = projection.model_validate(raw.get("data"))
retrieved_at = datetime.now(UTC)
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

**Phase 30 adjustment:** for denied reads, adapters may still map raw failures, but `BusinessFactService` must own final no-leak `BusinessFactResultV1` and must not emit refs/facts before scope proof.

### `src/business/__init__.py` (provider / public export, transform)

**Analog:** existing public export file.

**Export pattern** (`src/business/__init__.py` lines 1-5):
```python
from __future__ import annotations

from src.business.service import BusinessToolService

__all__ = ["BusinessToolService"]
```

Add `BusinessFactService` / `BusinessFactResultV1` exports only after the service and schema exist. Keep compatibility exports for `BusinessToolService` if retained.

### `src/tools/executors/business.py` (service / executor, request-response)

**Analog:** existing thin executor. Keep it thin and delegate to `BusinessFactService`; adapt `BusinessFactResultV1` to `ToolResultV2` at this boundary only.

**Current executor pattern** (`src/tools/executors/business.py` lines 11-21):
```python
class BusinessToolExecutor:
    executor_name = "business"

    def __init__(self, session: AsyncSession, service: BusinessToolService | None = None) -> None:
        self.service = service or BusinessToolService.with_default_registry(session)

    def has_tool(self, name: str) -> bool:
        return self.service.has_tool(name)

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        return await self.service.invoke_tool(name, args, ctx)
```

**Platform default wiring pattern** (`src/tools/platform.py` lines 61-83):
```python
@classmethod
def with_defaults(cls, session: AsyncSession | None) -> ToolPlatform:
    catalog = ToolCatalog()
    if session is None:
        return cls(catalog=catalog, executors=_StubExecutor.registry(catalog))
    from src.tools.executors.business import BusinessToolExecutor
    ...
    executors = {
        "business": BusinessToolExecutor(session),
        "knowledge": KnowledgeToolExecutor(session),
        "memory": MemoryToolExecutor(session),
        "action": ActionToolExecutor(session),
    }
    return cls(catalog=catalog, executors=executors)
```

**Runtime envelope to preserve** (`src/tools/runtime.py` lines 136-213): executor dispatch happens only after descriptor lookup, schema validation, runtime auth, and availability checks. Do not move ToolPlatform auth into `BusinessFactService`.

### `src/tools/projection.py` (utility, transform)

**Analog:** existing `ToolResultProjector`; projection consumes service-approved `ToolResultV2` envelope and strips raw data.

**Raw sentinel denylist** (`src/tools/projection.py` lines 9-21):
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

**Envelope refs override heuristic refs** (`src/tools/projection.py` lines 134-145):
```python
if result.business_fact_refs:
    normalized["business_fact_refs"] = [
        {"resource_type": ref.resource_type, "resource_id": ref.resource_id}
        for ref in result.business_fact_refs
    ]
if result.policy_evidence_refs:
    normalized["policy_evidence_refs"] = [
        {"evidence_id": ref.evidence_id, "doc_key": ref.doc_key}
        for ref in result.policy_evidence_refs
    ]
```

**Prompt projection pattern** (`src/tools/projection.py` lines 228-269): prompt output contains status, bounded summary, refs, safe error, and `text_for_prompt`; it must not include raw payloads or denied resource-specific details.

### `src/agent/nodes/investigate.py` (controller / graph node, event-driven)

**Analog:** existing investigate node. Keep graph code on `ToolPlatform` and projected outcomes, not repositories or business service internals.

**ToolPlatform setup pattern** (`src/agent/nodes/investigate.py` lines 63-76):
```python
tool_platform = configurable.get("tool_platform")
if tool_platform is None:
    tool_manager = configurable.get("tool_manager")
    if tool_manager is not None and hasattr(tool_manager, "_platform"):
        tool_platform = tool_manager._platform
    elif session is not None:
        tool_platform = ToolPlatform.with_defaults(session)
    else:
        tool_platform = ToolPlatform(executors={})
```

**Invoke and projection consumption pattern** (`src/agent/nodes/investigate.py` lines 144-193):
```python
descriptor = tool_platform.descriptor(tool_name)
...
outcome = await tool_platform.invoke(tool_name, args, tool_ctx, session=session)
result = outcome.tool_result
...
prompt_summary = await _append_tool_result_record(
    configurable,
    session,
    tool_name,
    tool_ctx,
    operation_id,
    result,
    tool_call_record,
    projection=outcome.projection,
)
_accumulate_tool_result(context, descriptor, tool_name, result, prompt_summary, outcome.projection)
```

**State output pattern** (`src/agent/nodes/investigate.py` lines 205-240): `business_context` carries facts, business refs, prompt-safe tool results, missing facts, errors, and status; `last_business_context_refs` carries only approved business refs.

**Accumulation pattern** (`src/agent/nodes/investigate.py` lines 539-597): only successful results with `result.business_fact_refs` populate `facts`, `business_fact_refs`, and claim dependencies; non-success appends safe errors. Phase 30 should add no-leak tests around permission denied/stale/unavailable service-approved results.

### `tests/business/test_schemas.py` (test, contract validation)

**Analog:** existing strict schema tests.

**Status enum test shape** (`tests/business/test_schemas.py` lines 16-27 and 64-74):
```python
TOOL_RESULT_STATUSES = [
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

@pytest.mark.parametrize("status", TOOL_RESULT_STATUSES)
def test_tool_result_accepts_all_contract_statuses(status: str):
    result = ToolResultV2.model_validate(_complete_result_payload(status=status))
    assert result.status == status
```

**Business ref is not evidence pattern** (`tests/business/test_schemas.py` lines 77-89):
```python
business_ref = BusinessFactRefV1(...)

with pytest.raises(ValidationError):
    EvidenceRefV1.model_validate(business_ref.model_dump())
```

Add analogous tests for `BusinessFactResultV1`: strict extra rejection, explicit nullable fields present, allowed statuses, `scope_check_result`, `missing_required_facts`, `safe_errors`, and business-ref/evidence separation.

### `tests/business/test_service.py` (test, service / integration)

**Analog:** existing business service tests.

**Permission denied before adapter pattern** (`tests/business/test_service.py` lines 103-116):
```python
result = await BusinessToolService(AsyncMock(), adapters={"get_order": adapter}).invoke_tool(
    "get_order",
    {"order_no": "ORD-09"},
    _context(merchant_scope={}),
)

assert result.status == "permission_denied"
assert result.error is not None
assert result.error.code == "EMPTY_MERCHANT_SCOPE"
adapter.assert_not_awaited()
```

**Context status / missing fact patterns** (`tests/business/test_service.py` lines 220-271): existing tests assert partial/complete/insufficient status and `missing_required_facts`; copy this shape for `BusinessFactService.fetch_context`.

**No-leak denial pattern** (`tests/business/test_service.py` lines 292-334):
```python
assert context.status == "insufficient"
assert context.facts == {}
assert context.business_fact_refs == []
assert context.missing_required_facts == ["order"]
denied_result = context.tool_results[0]
assert denied_result.status == "permission_denied"
assert denied_result.business_fact_refs == []
assert denied_result.data is None
...
assert prompt_summary.business_fact_refs == []
assert "ORD-TEST-002" not in prompt_summary.prompt_summary
assert "Order read succeeded" not in prompt_summary.prompt_summary
assert "ORD-TEST-002" not in serialized_context
```

**Adapter exception no raw leak pattern** (`tests/business/test_service.py` lines 337-351): assert safe error code and raw exception text absent from serialized result.

### `tests/business/test_adapters.py` (test, transform / adapter)

**Analog:** existing adapter projection tests.

**Raw error deterministic mapping** (`tests/business/test_adapters.py` lines 55-89):
```python
@pytest.mark.parametrize(
    ("error_code", "expected_status", "expected_source", "retryable"),
    [
        ("FORBIDDEN", "permission_denied", "caller", False),
        ("ORDER_NOT_FOUND", "not_found", "upstream", False),
        ("DB_TIMEOUT", "timeout", "adapter", True),
        ("VALIDATION_ERROR", "invalid_request", "caller", False),
        ("DB_ERROR", "error", "adapter", False),
    ],
)
async def test_raw_error_code_maps_deterministically(...):
    ...
    assert "unsafe raw message" not in str(result.model_dump())
```

**Invalid response discard pattern** (`tests/business/test_adapters.py` lines 92-108): malformed success data with `RAW-UPSTREAM-SECRET-09` must produce `invalid_response`, `data is None`, and no raw secret in serialized result.

**Success provenance pattern** (`tests/business/test_adapters.py` lines 111-128): assert `policy_evidence_refs == []`, exactly one `BusinessFactRefV1`, correct `resource_type`, `resource_id`, tenant, latency, and raw call args.

### `tests/tools/test_tool_platform.py` (test, platform / integration)

**Analog:** existing ToolPlatform boundary tests.

**Recording executor pattern** (`tests/tools/test_tool_platform.py` lines 159-172):
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

**Runtime auth before dispatch pattern** (`tests/tools/test_tool_platform.py` lines 354-386): assert missing permission and explicit merchant scope denial return `permission_denied` before executor dispatch.

**Legacy merchant scope matrix pattern** (`tests/tools/test_tool_platform.py` lines 388-418): parameterize allowed/denied merchant scopes and assert status, decision, dispatch flag, and `scope_denied` reason.

**Raw projector test pattern** (`tests/tools/test_tool_platform.py` lines 421-473): build `ToolResultV2` with raw sentinel keys, project, and assert normalized/prompt/text/debug projections are raw-free.

### `tests/agent/test_nodes/test_investigate.py` (test, graph / event-driven)

**Analog:** existing graph tests.

**Fake platform wrapper pattern** (`tests/agent/test_nodes/test_investigate.py` lines 100-165): fake platform wraps a manager, projects result through `ToolResultProjector`, and returns `ToolInvocationOutcome`. Use this to inject service-approved success/denial/unavailable outputs.

**Business success helper pattern** (`tests/agent/test_nodes/test_investigate.py` lines 221-244): helper creates `ToolResultV2` with a `BusinessFactRefV1`, no policy refs, source system, freshness, and latency.

**Unavailable and permission-denied assertions** (`tests/agent/test_nodes/test_investigate.py` lines 627-690): unavailable tools record safe errors and tool result status; permission denied preserves existing successful facts but does not populate denied resource facts or leak the denied merchant id.

**Projection-only graph state pattern** (`tests/agent/test_nodes/test_investigate.py` lines 751-780): assert `tool_results` contain prompt-safe fields, not raw `data`; raw payload contents must not appear in tool result projection or `business_context`.

### `tests/agent/rag_context/test_authority_boundaries.py` (test, authority-boundary transform)

**Analog:** existing material claim authority tests.

**Business fact claim cannot use policy evidence pattern** (`tests/agent/rag_context/test_authority_boundaries.py` lines 140-174):
```python
claim = MaterialClaim.model_validate(
    _claim(
        "business_fact_claim",
        claim_text="Order ORD-1001 was delivered.",
        cited_evidence_ids=[evidence.evidence_id],
        business_fact_refs=[],
    )
)

result = await MaterialClaimVerifier().verify_claim(claim, context_bundle=context)

assert _value(result.outcome) != "supported"
assert result.allows_claim is False
assert {
    "business_fact_ref_required",
    "policy_evidence_not_business_authority",
    "provenance_not_business_authority",
} <= set(result.reason_codes)
```

**Action dependency fail-closed pattern** (`tests/agent/rag_context/test_authority_boundaries.py` lines 177-209): action recommendation with memory/model-supported dependencies must not be supported and must block proposed action.

### `tests/agent/test_policy_retrieval_ownership.py` (test, authority-boundary integration)

**Analog:** existing cross-boundary ownership tests.

**Graph imports only platform/contracts pattern** (`tests/agent/test_policy_retrieval_ownership.py` lines 282-290):
```python
module_source = investigate_module
assert hasattr(module_source, "ToolPlatform")
assert not hasattr(module_source, "PolicyKnowledgeService")
assert not hasattr(module_source, "BusinessToolService")
```

**Business refs distinct from evidence refs pattern** (`tests/agent/test_policy_retrieval_ownership.py` lines 344-374):
```python
business_ref = _business_fact_ref(resource_type, resource_id)

with pytest.raises(ValidationError):
    EvidenceRefV1.model_validate(business_ref.model_dump(mode="json"))

result = ToolResultV2(
    status="success",
    data={"id": resource_id, "status": "loaded"},
    summary="business fact loaded",
    source_system="business_tool_service",
    data_freshness_at=None,
    policy_evidence_refs=[],
    business_fact_refs=[business_ref],
    ...
)

assert result.policy_evidence_refs == []
assert result.business_fact_refs == [business_ref]
```

## Shared Patterns

### Service Boundary Ownership

**Source:** `docs/contract-spec.md` lines 20-28 and `docs/target-agent-platform-architecture-plan.md` lines 197-209
**Apply to:** `src/business/service.py`, `src/tools/executors/business.py`, `src/agent/nodes/investigate.py`

`BusinessFactService` owns `BusinessFactResultV1`, `BusinessFactRefV1`, `BusinessContextV1`, freshness/scope checks, and owned business repositories/adapters. Graph/tool code must not directly access repositories or substitute memory/RAG/LLM facts.

### ToolPlatform Gate Order

**Source:** `src/tools/runtime.py` lines 76-213 and `docs/contract-spec.md` lines 1381-1391
**Apply to:** `src/tools/executors/business.py`, `tests/tools/test_tool_platform.py`, graph integration tests

Runtime must do descriptor lookup, input schema validation, runtime auth, availability check, executor dispatch, output validation, projection, and event emission. `BusinessFactService` must not duplicate descriptor permission, caller allowlist, side-effect, approval, idempotency, or ToolCatalog logic.

### Domain Scope Marker

**Source:** `src/tools/policy.py` lines 80-87 and 394-429
**Apply to:** `src/business/service.py`, `src/tools/executors/business.py`, `tests/tools/test_tool_platform.py`

```python
_DOMAIN_SCOPE_CHECK_IDENTIFIERS: set[str] = {
    "order_id",
    "order_no",
    "refund_id",
    "refund_case_no",
    "ticket_id",
}
...
if key in _DOMAIN_SCOPE_CHECK_IDENTIFIERS:
    binding["requires_domain_scope_check"] = True
```

Phase 30 must make this marker enforced by `BusinessFactService` before emitting facts or refs for order/refund/ticket.

### Catalog Business Reads And Unsupported Tools

**Source:** `src/tools/catalog.py` lines 41-67 and 139-185; `src/business/service.py` lines 37-59
**Apply to:** `src/business/service.py`, `src/tools/executors/business.py`, `tests/business/test_service.py`, `tests/tools/test_tool_platform.py`, `tests/agent/test_nodes/test_investigate.py`

Catalog declares `get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, and `get_merchant_risk`; the current business registry backs only order/refund/ticket. Unsupported catalog business reads must return unavailable/no-fact/no-ref outputs or be hidden by availability.

### No-Leak Denial

**Source:** `docs/contract-spec.md` lines 105-140; `tests/business/test_service.py` lines 292-334
**Apply to:** all service/tool/graph denial paths

Denied business reads must not reveal existence through facts, refs, prompt summary, `business_context`, `last_business_context_refs`, safe error text, or final response content. Use generic messages such as `Business resource unavailable for this request`; do not copy API 403/404 existence semantics into service/tool responses.

### Raw Payload Stripping

**Source:** `src/tools/projection.py` lines 9-21 and `tests/tools/test_tool_platform.py` lines 421-473
**Apply to:** `src/business/adapters.py`, `src/tools/projection.py`, `src/agent/nodes/investigate.py`, tests

Raw sentinel keys and raw upstream messages must be discarded before normalized graph state, prompt projections, debug projection, and conversation tool summaries.

### Business Ref Is Not Policy Evidence

**Source:** `src/tools/contracts.py` lines 58-68; `docs/contract-spec.md` lines 1293-1307; `tests/business/test_schemas.py` lines 77-89
**Apply to:** `src/business/schemas.py`, `src/business/service.py`, all business result tests

`BusinessFactRefV1` is provenance for current business facts only. It must not validate as `EvidenceRefV1` or satisfy policy evidence, approval evidence, or action safety snapshot requirements.

## Reference-Only Files Mentioned In Scope

These files are important analog/reference sources but are not classified as planned edits unless the planner chooses a broader migration:

| File | Use |
|------|-----|
| `src/tools/contracts.py` | Schema style and existing `BusinessFactRefV1` / `ToolResultV2` contract source. |
| `src/tools/catalog.py` | Catalog-declared business read list, including unsupported logistics/risk tools. |
| `src/tools/policy.py` | `requires_domain_scope_check` marker source. |
| `src/tools/runtime.py` | ToolPlatform runtime gate order and safe denial envelope. |
| `src/tools/platform.py` | Default executor wiring and graph-facing facade. |
| `src/business/adapters.py` | Private adapter projection analog; source edits are not expected in split plans unless execution finds a direct adapter contract regression and records the reason. |
| `src/agent/nodes/investigate.py` | Graph accumulation analog; source edits are not expected in split plans unless projection-only changes cannot satisfy APF-08 no-leak tests. |
| `src/integrations/demo_business/authz.py` | Interim Phase 29.5 merchant role semantics; use behind `BusinessFactService`, not as public authority. |
| `src/integrations/demo_business/orders.py` / `refunds.py` / `tickets.py` | Current raw repository-backed reads; keep private behind service/adapters. |
| `tests/agent/test_tools/test_get_order.py` / `test_get_refund_case.py` / `test_get_ticket.py` | Regression-only raw tool suites from validation full command. |

## No Analog Found

None. All planned files have exact or role-match analogs in the current codebase.

## Metadata

**Analog search scope:** `src/business`, `src/tools`, `src/agent/nodes`, `src/integrations/demo_business`, `tests/business`, `tests/tools`, `tests/agent`
**Files scanned:** 32 source/test/doc files plus phase inputs
**Pattern extraction date:** 2026-06-28
**Non-blocking note:** Repository-local `.claude/skills/` and `.agents/skills/` directories were absent, so no project-local skill rules were loaded.
