# Phase 9: Business Tool Facade - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 5 new/modified source files + 4 test files
**Analogs found:** 9 / 9 (every new/modified file has a strong in-repo analog)

> Scope note: this map gives the executor CODE PATTERNS and concrete excerpts to mirror. It does NOT re-derive contract field lists — those are normative in 09-RESEARCH.md §3 (copy field-for-field from there). Where RESEARCH says "import canonical EvidenceRefV1", this map shows the exact import target and class shape.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/business_tools/schemas.py` | model (pydantic contracts) | transform/request-response | `src/knowledge/schemas.py` | exact (same role: canonical pydantic-v2 contract module with `schema_version` Literal) |
| `src/business_tools/registry.py` | service (dispatch/validation entry) | request-response | `src/agent/tools/registry.py` | exact (same role; replace semantics) |
| `src/business_tools/adapters.py` | utility (raw→typed mapping) | transform | `src/agent/tools/adapters.py` + `src/agent/tools/get_order.py` | exact (reuse + remap) |
| `src/business_tools/service.py` | service (facade) | CRUD/aggregate | `src/knowledge/service.py` (`PolicyKnowledgeService`) | role-match (facade-over-adapter shape) |
| `src/agent/nodes/load_business_context.py` (migrate) | node (graph node) | event-driven (LangGraph) | itself (current direct-call) + `src/knowledge/service.py` caller pattern | exact (in-place migration) |
| `tests/business_tools/test_schemas.py` (new) | test | — | `tests/agent/test_tools/test_tool_contracts.py` | exact |
| `tests/business_tools/test_registry.py` (new) | test | — | `tests/agent/test_tools/test_registry.py` | exact |
| `tests/business_tools/test_adapters.py` (new) | test | — | `tests/agent/test_tools/test_tool_adapters.py` + `tests/knowledge/test_facade_status.py` | exact |
| `tests/business_tools/test_service.py` (new) | test | — | `tests/knowledge/test_facade_status.py` | exact |

Old tests to rewrite/retire (bound to v1 contracts): `tests/agent/test_tools/test_registry.py`, `tests/agent/test_tools/test_tool_contracts.py`, `tests/agent/test_tools/test_tool_adapters.py` (per RESEARCH §6 / Plan E).

---

## Pattern Assignments

### `src/business_tools/schemas.py` (model, pydantic v2 contracts)

**Analog:** `src/knowledge/schemas.py`

This is the canonical pattern for a pydantic-v2 contract module with a `schema_version` Literal tag. Mirror it exactly; do NOT redefine `EvidenceRefV1` — import it.

**Module-header + import pattern** (`src/knowledge/schemas.py:1-15`) — note module docstring records Spec Consistency Findings inline:
```python
"""Canonical knowledge contracts.

Spec Consistency Finding: ...
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
```

**schema_version Literal tag pattern** (`src/knowledge/schemas.py:31-42`) — copy this `schema_version: Literal[...] = ...` convention for every v2 contract (`ToolCallContext` → `"tool_context.v2"`, `ToolResultV2` → `"tool_result.v2"`, etc., per RESEARCH §3):
```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    ...
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)
```

**Canonical import target for `policy_evidence_refs`** — DO NOT redefine. `ToolResultV2.policy_evidence_refs: list[EvidenceRefV1]` must import from here:
```python
from src.knowledge.schemas import EvidenceRefV1
```
`EvidenceRefV1` is defined at `src/knowledge/schemas.py:31`. RESEARCH §3.4 requires `BusinessFactRefV1` be a SEPARATE class (not assignable to `EvidenceRefV1`) — they share no inheritance; keep them structurally distinct (different field sets: `EvidenceRefV1` has `doc_key/chunk_id/policy_version/text_hash`; `BusinessFactRefV1` has `resource_type/resource_id/source_system`).

**TrustedContext-projection inline pattern (SCF-1)** (`src/knowledge/schemas.py:18-28`) — Phase 8 already inlines the identity/scope projection fields rather than importing a canonical `TrustedContext` class (which does not exist in `src/`). `ToolCallContext` MUST follow the same precedent — inline the 9 identity/scope fields:
```python
class KnowledgeContext(BaseModel):
    """TrustedContext projection fields plus run-derived effective_at."""
    tenant_id: str
    user_id: str
    role: str
    merchant_scope: list[str] | None = None
    run_id: str
    trace_id: str
    locale: str | None = None
    effective_at: str
```
Note: Phase 8 uses `merchant_scope: list[str] | None = None`. `ToolCallContext` should match field names/types where they overlap (no widening/rename) per SCF-1.

**`extra="forbid"` config** — the old v1 contracts use `ConfigDict(extra="forbid")` (`src/agent/tools/contracts.py:16,26,51,62,70`) to keep raw payloads out of prompt-facing models. RESEARCH §3 / TOOL-02 "no raw payload exposure" depends on this. Apply `model_config = ConfigDict(extra="forbid")` to `ToolResultV2`, `ToolError`, `BusinessFactRefV1` (knowledge/schemas.py omits it; prefer the old-contract `extra="forbid"` rigor here for the no-leak guarantee).

---

### `src/business_tools/registry.py` (service, request-response dispatch)

**Analog:** `src/agent/tools/registry.py` (REPLACE semantics — keep skeleton, drop investigator whitelist)

**Reusable skeleton to KEEP** — the `RegisteredTool` dataclass, dict-keyed `_tools` registry, duplicate-name guard, and the `invoke` pipeline ordering:

**Registry init + duplicate guard** (`src/agent/tools/registry.py:139-147`):
```python
class ToolRegistry:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        registered_tools = list(_default_tools() if tools is None else tools)
        self._tools: dict[str, RegisteredTool] = {}
        for tool in registered_tools:
            self._validate_registered_tool(tool)
            if tool.entry.name in self._tools:
                raise ValueError(f"Duplicate tool registry entry: {tool.entry.name}")
            self._tools[tool.entry.name] = tool
```

**`invoke` pipeline ordering** (`src/agent/tools/registry.py:155-176`) — mirror this sequence but swap the result type to `ToolResultV2` and the gate to the new descriptor checks (RESEARCH §3.7: resolve → caller_allowlist → required_permission → input_schema → adapter → output_schema → ToolResultV2):
```python
async def invoke(self, name, input_data, context) -> ToolExecutionResult:  # → ToolResultV2
    tool = self._tools.get(name)
    if tool is None:
        return self._rejection("not_found", ...)          # → status="not_found"/"invalid_request"
    if not self._caller_can_invoke(tool.entry, context):
        return self._rejection("unsafe_tool_request", ...) # → status="permission_denied"
    try:
        validated_input = tool.entry.input_schema.model_validate(input_data)
    except ValidationError as exc:
        return self._rejection("validation_error", ...)    # → status="invalid_request"
    try:
        raw_result = await tool.adapter(validated_input, context)
    except Exception as exc:
        return self._rejection("tool_error", ..., retryable=True)  # → status="error"
    try:
        return self._to_execution_result(tool.entry, raw_result)
    except (ValidationError, AttributeError, TypeError) as exc:
        return self._rejection("validation_error", ...)    # → status="invalid_response"
```
Critical: the LAST except-block (output validation failure) is the **TOOL-02 "no raw invalid payload exposure"** seam — adapter output that fails `output_schema` must become `status="invalid_response"` with NO raw dict in the returned envelope.

**Declarative descriptor table pattern** (`src/agent/tools/registry.py:75-136`) — keep the `_default_tools()` list-of-entries shape. REPLACE per-entry fields with the §12.6 `ToolDescriptor` set (`kind`, `required_permission`, `caller_allowlist`, `event_family`, `resource_type`) per RESEARCH §3.7/§3.8. The 8 read/retrieval tool rows + 1 write declare-only row live here.

**DROP these (CONTEXT-locked, RESEARCH §2.1):**
- `INVESTIGATOR_TOOL_NAMES` / `allowed_in_investigator` / `_caller_can_invoke` investigator branch (`registry.py:28,149-153,194-209`).
- `_evidence_refs_from_data` (`registry.py:253-269`) — policy-chunk extraction is Phase 8 territory; business path must NOT emit it.
- The 4-way `caller` literal branching (`registry.py:202-224`). Replace with descriptor `caller_allowlist` membership check using canonical node name `investigate` (SCF-2 / D4).

**Write-tool block (TOOL-03 / D2):** declare `create_coupon_grant_draft` descriptor with `kind="write"`, but `invoke` must hard-reject it before adapter execution (return `permission_denied`/blocked, adapter never awaited). The old `_caller_can_invoke` `execute_action → return False` (`registry.py:222-223`) is the precedent for a hard-deny branch.

---

### `src/business_tools/adapters.py` (utility, raw→ToolResultV2 transform)

**Analog:** `src/agent/tools/adapters.py` (REUSE the 3 business adapters + input schemas) + `src/agent/tools/get_order.py` (raw shape source)

**Reusable input schemas + adapter signatures** (`src/agent/tools/adapters.py:14-51`) — keep `GetOrderInput`/`GetRefundCaseInput`/`GetTicketInput` and the `(input_data, context)` forwarding. Update the context type from `ToolInvocationContext` to `ToolCallContext` (now sources `tenant_id/user_id/role` from the 18-field context):
```python
class GetOrderInput(BaseModel):
    order_no: str = Field(min_length=1)

async def get_order_adapter(input_data: BaseModel, context: ToolInvocationContext) -> dict[str, Any]:
    data = GetOrderInput.model_validate(input_data)
    return await get_order(data.order_no, context.tenant_id, context.user_id, context.role, context.session)
```
DO NOT re-own `search_policy_adapter`/`SearchPolicyInput` (`adapters.py:26-31,54-65`) — Phase 8 KnowledgeService territory (RESEARCH §2.1).

**Raw `{status, data, error}` shape the new layer must remap** (`src/agent/tools/get_order.py:12-26`):
```python
def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}

def _tool_error(error_code, message, retryable, should_stop=False) -> dict:
    return {"status": "error", "data": {}, "error": {
        "error_code": error_code, "message": message,
        "retryable": retryable, "should_stop": should_stop}}
```

**Confirmed raw error codes to map** (the §3.9 status-mapping table source of truth):
- `get_order.py`: `VALIDATION_ERROR` (bad tenant_id, line 41), `ORDER_NOT_FOUND` (47), `FORBIDDEN` (61, `should_stop=True`), `DB_TIMEOUT` (90, `retryable=True`), `DB_ERROR` (92).
- `get_refund_case.py`: same set with `REFUND_CASE_NOT_FOUND` (line 51).
- `get_ticket.py`: same set with `TICKET_NOT_FOUND` (line 56).
- 10s timeout via `asyncio.wait_for(..., timeout=10.0)` + `except asyncio.TimeoutError` (`get_order.py:45,89`).

The new adapter layer wraps each raw call and maps `error.error_code` → `ToolResultV2.status` per RESEARCH §3.9, populating `business_fact_refs` (`BusinessFactRefV1`) on success and leaving `policy_evidence_refs=[]` (D7). For `get_logistics`/`get_merchant_risk` (no repo backing) → return `ToolResultV2(status="unavailable")` (RESEARCH §3.8).

**summary-projection (no-raw-leak) precedent** (`src/agent/tools/registry.py:239-244`) — old code projects only `result_summary_fields` into `summary`, dropping the raw dict. The new adapter's `ToolResultV2.summary`/`data` must follow the same "typed projection only" rule; raw upstream dict never travels in the envelope.

---

### `src/business_tools/service.py` (service, facade)

**Analog:** `src/knowledge/service.py` (`PolicyKnowledgeService`) — closest facade-over-adapter shape in the repo.

**Facade construction + typed-result error wrapping** (`src/knowledge/service.py:21-53,76-90`):
```python
class PolicyKnowledgeService:
    def __init__(self, adapter: LegacyRagKnowledgeAdapter):
        self.adapter = adapter

    async def search(self, request, context) -> KnowledgeSearchResult:
        try:
            status, evidence_refs, best_score = await self.adapter.retrieve(...)
        except asyncio.TimeoutError:
            return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
        except Exception:
            return self._error_result("SEARCH_ERROR", "...", retryable=False)
        ...
        return KnowledgeSearchResult(status=status, ...)

    @staticmethod
    def _error_result(error_code, message, *, retryable) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(status="error", ..., error={...})
```
Mirror this for `BusinessToolService`: constructor takes the `ToolRegistry` (and/or adapters); a static `_error_result`-style helper builds `ToolResultV2` error envelopes; never let a raw exception/dict escape.

**Scope-as-authorization-input precedent (deny-all / no-widening)** (`src/knowledge/service.py:30-36`) — the facade drops out-of-scope merchant IDs BEFORE hitting the DB:
```python
merchant_id = request.filters.merchant_id
merchant_scope = context.merchant_scope
if merchant_id is not None and merchant_scope is not None and merchant_id not in merchant_scope:
    merchant_id = None  # unauthorized id dropped; never sent to DB
```
This is the model for RESEARCH §6 "no-widening" / "deny-all" tests. Note: Phase 8 treats `merchant_scope=None` as "no restriction"; RESEARCH §6 requires `ToolCallContext` empty `merchant_scope` → **deny** (not unrestricted). The facade scope-check must differ from Phase 8 here — surface this as an intentional deviation in the plan (deny-on-empty, not Phase-8's permissive None). `merchant_can_access` (`src/agent/tools/authz.py:11-36`) is the per-resource scope-check to reuse inside the raw tools.

**`invoke_tool` retry loop (D5)** — no exact retry analog in repo. Build per RESEARCH §3.7/§3.8 + D5: `attempt` 1→`max_attempts`, same `tool_call_id` across attempts, stop (never re-call) when `attempt > max_attempts`. Loop control stays in Phase 10 — facade owns only the per-call retry.

**`fetch_context` aggregation (D6)** — mirrors the current node's conditional load logic (see node analog below): order/refund/ticket by slot presence, aggregate into `BusinessContextV1`. `partial_success` only when some sub-reads succeed and some fail (RESEARCH §6).

---

### `src/agent/nodes/load_business_context.py` (node migration — read-switch)

**Analog:** itself (current direct-call shape, the thing being migrated)

**Current direct-call shape to REPLACE** (`src/agent/nodes/load_business_context.py:31-79`):
```python
async def load_business_context(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    tenant_id = state["tenant_id"]; user_id = state["user_id"]; role = state["role"]
    intent = state.get("current_intent") or "unknown"
    extracted_slots = state.get("extracted_slots") or {}
    has_current_identifier = any(extracted_slots.get(k) for k in ("order_id","refund_case_id","ticket_id"))
    slots = extracted_slots if has_current_identifier else state.get("active_slots") or {}
    should_load_context = intent in {"refund_troubleshooting","compensation_suggestion"} or has_current_identifier
    if should_load_context:
        if slots.get("order_id"):
            result = await get_order(slots["order_id"], tenant_id, user_id, role, session)  # DIRECT CALL
            ...
    return {
        "business_context": ctx,
        "tool_results": results,
        "last_business_context_refs": refs,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at, tools_called)],
    }
```

**Migration must preserve (rollback seam / D6):**
- The conditional-load decision logic (intent set + `has_current_identifier`, `extracted_slots` vs `active_slots`) — move INTO `fetch_context` or pass slots/intent to it.
- The exact return-dict keys: `business_context`, `tool_results`, `last_business_context_refs`, `trace_steps` (state-write shape unchanged — regression guard, RESEARCH §6 "behavior parity").
- `session` sourced from `config["configurable"]["session"]`; identity from `state`.
- `_trace_step` shape (`load_business_context.py:18-28`) — keep the node id `"load_business_context"` in trace (physical node name unchanged until Phase 10).

**Migration must change:**
- Drop the 3 direct imports `from src.agent.tools.get_order import get_order` etc. (`load_business_context.py:9-11`). Node must call `BusinessToolService.fetch_context(slots, intent, ctx)` instead.
- Build a `ToolCallContext` from trusted `state`/`config`, injecting `caller_node="investigate"` (canonical, D4 / SCF-2) even though the physical node is still `load_business_context`.

**Graph-test seam to update (regression guard):** `tests/agent/test_graph.py:155-157` currently monkeypatches the node's module-level `get_order`/`get_refund_case`/`get_ticket`:
```python
monkeypatch.setattr(load_business_context_module, "get_order", get_order)
```
After migration those names no longer exist on the node module. The migration (Plan E) must update these graph tests to patch at the facade boundary instead, while asserting the same `final_state["business_context"]` shape (`test_graph.py:193-197,228-233`). Session injected as `{"configurable": {"thread_id": ..., "session": AsyncMock()}}` (`test_graph.py:58`).

---

## Shared Patterns

### Pydantic-v2 contract module convention
**Source:** `src/knowledge/schemas.py:9-42`
**Apply to:** `src/business_tools/schemas.py`
- `from __future__ import annotations`; `from typing import Literal`; `from pydantic import BaseModel, Field`.
- Every versioned contract carries `schema_version: Literal["<name>.vN"] = "<name>.vN"`.
- Module docstring records Spec Consistency Findings inline (precedent: schemas.py:1-7). Record SCF-1 (inline TrustedContext projection) here.

### No-raw-payload-exposure (TOOL-02 spine)
**Source:** `src/agent/tools/contracts.py:62,70` (`ConfigDict(extra="forbid")`) + `src/agent/tools/registry.py:239-244` (typed summary projection) + `registry.py:173-176` (output-validation → structured error, no raw dict)
**Apply to:** `ToolResultV2`, `ToolError`, `BusinessFactRefV1`, registry `invoke` output path, all adapters.
- `extra="forbid"` on prompt/graph-facing models.
- Adapter `output_schema` validation failure → `status="invalid_response"`, raw dict discarded.
- Only typed `data`/`summary`/refs/`status` reach graph nodes.

### Scope check (deny-all / no-widening)
**Source:** `src/knowledge/service.py:30-36` (drop-out-of-scope-before-DB) + `src/agent/tools/authz.py:11-36` (`merchant_can_access`)
**Apply to:** `BusinessToolService` scope gate + reused inside raw tools.
- Out-of-scope merchant id dropped before adapter/DB call.
- DEVIATION from Phase 8: empty `merchant_scope` → DENY (RESEARCH §6), not Phase-8's permissive `None`. Surface in plan.

### Facade error-envelope helper
**Source:** `src/knowledge/service.py:76-90` (`_error_result` static method)
**Apply to:** `BusinessToolService` — a `_error_result`/`_to_tool_result` helper that constructs `ToolResultV2` envelopes so no path returns a bare dict/exception.

---

## Test Patterns

### Contract/schema tests
**Source:** `tests/agent/test_tools/test_tool_contracts.py:43-203`
**Mirror for:** `tests/business_tools/test_schemas.py`
- `_complete_*_payload(**overrides)` factory + `payload.update(overrides)` (test_tool_contracts.py:26-40).
- Parametrized missing-field / invalid-literal rejection (`test_tool_contracts.py:68-107`).
- "Unknown prompt-facing field rejected" via `extra="forbid"` (`test_tool_contracts.py:174-184`) — directly covers no-raw-leak. Mirror for `BusinessFactRefV1` not coercible to `EvidenceRefV1` (RESEARCH §6).

### Registry tests
**Source:** `tests/agent/test_tools/test_registry.py:13-46` (helpers), `:117-211` (invoke-path assertions)
**Mirror for:** `tests/business_tools/test_registry.py`
- `_entry(...)` and `_context(...)` builders.
- `adapter = AsyncMock(...)` + `adapter.assert_not_awaited()` to prove rejection happens BEFORE execution (`test_registry.py:145,158,211`) — reuse for write-tool block (TOOL-03) and permission_denied.
- "raw text not in result" assertion: `assert "Raw evidence text" not in str(result.model_dump())` (`test_registry.py:288`) — reuse for invalid_response no-leak.
- single-entry consistency: `set(registry.<names>()) == {...}` (`test_registry.py:48-56`) — adapt to derive allowlist/resource_type from registry (RESEARCH §6).

### Adapter / status-mapping tests
**Source:** `tests/agent/test_tools/test_tool_adapters.py:30-39` (monkeypatch raw tool + assert forwarding) + `tests/knowledge/test_facade_status.py:62-119` (parametrized status mapping, timeout→error)
**Mirror for:** `tests/business_tools/test_adapters.py`
- `monkeypatch.setattr("src.business_tools.adapters.get_order", AsyncMock(...))` to inject raw `{status,data,error}` and assert mapped `ToolResultV2.status`.
- Parametrized `(raw_error_code, expected_status)` table mirroring RESEARCH §3.9.
- `asyncio.TimeoutError` side_effect → `status="timeout"`, `retryable=True` (`test_facade_status.py:106-119`).

### Service / facade tests
**Source:** `tests/knowledge/test_facade_status.py:54-59` (`_service(...)` builder with `SimpleNamespace` + `AsyncMock`), `:122-142` (partial/allow flags)
**Mirror for:** `tests/business_tools/test_service.py`
- Build service over mocked registry/adapters; assert `fetch_context` aggregation status (`complete`/`partial`/`insufficient`/`error`) and `partial_success` only-on-mixed-results.
- Retry test (D5): assert `attempt` increments, same `tool_call_id`, stops at `max_attempts`.

---

## No Analog Found

| File / concern | Role | Reason |
|------|------|--------|
| `invoke_tool` retry loop (attempt/max_attempts) | service | No retry mechanism exists in repo today; build from RESEARCH §3.7 + D5. Structure is novel but small. |
| `ToolDescriptor.event_family` / write `action_*` deferral | model | No `event_family` field exists in old `ToolRegistryEntry`; SCF-3 leaves write event_family unset/sentinel pending Phase 17. |
| `audit_ref` emission seam | service | No event/audit infra in repo (SCF-4); `audit_ref=None`, seam consumed by Phase 10c. |

These are correctly novel per the SCFs/decisions; planner should follow RESEARCH §3 normative shapes, not invent analogs.

---

## Metadata

**Analog search scope:** `src/agent/tools/`, `src/knowledge/`, `src/agent/nodes/`, `tests/agent/test_tools/`, `tests/knowledge/`, `src/agent/graph.py`
**Files scanned (read in full):** registry.py, contracts.py, adapters.py, authz.py, get_order.py, create_coupon_grant_draft.py (src); knowledge/schemas.py, knowledge/service.py (Phase 8 canon); load_business_context.py (migrate target); test_tool_contracts.py, test_registry.py, test_tool_adapters.py, test_facade_status.py (test analogs). Grep-confirmed: get_refund_case.py / get_ticket.py error codes; test_graph.py monkeypatch seam.
**Pattern extraction date:** 2026-06-12

## PATTERN MAPPING COMPLETE

**Phase:** 9 - business-tool-facade
**Files classified:** 9 (5 source + 4 test suites)
**Analogs found:** 9 / 9

### Coverage
- Files with exact analog: 8
- Files with role-match analog: 1 (`service.py` → `PolicyKnowledgeService`)
- Files with no analog: 0 source files (3 sub-concerns are intentionally novel per SCF-3/SCF-4/D5)

### Key Patterns Identified
- `src/knowledge/schemas.py` is the canonical pydantic-v2 contract module to mirror (schema_version Literal tags, inline TrustedContext projection per SCF-1, docstring-recorded SCFs); `EvidenceRefV1` imported from there, never redefined.
- `src/agent/tools/registry.py` `invoke` pipeline (resolve→gate→input_schema→adapter→output_schema) is the skeleton to keep; investigator-whitelist / `_evidence_refs_from_data` / 4-way caller branching are DROPPED; output-validation-failure branch is the TOOL-02 no-raw-leak seam.
- `PolicyKnowledgeService` (`src/knowledge/service.py`) is the facade + `_error_result` + scope-drop-before-DB pattern for `BusinessToolService`, with one deliberate deviation: empty `merchant_scope` denies (vs Phase-8 permissive None).
- Raw tools (`get_order/get_refund_case/get_ticket`) return `{status,data,error}` with confirmed codes (`*_NOT_FOUND/FORBIDDEN/DB_TIMEOUT/VALIDATION_ERROR/DB_ERROR`) — the deterministic source for the §3.9 status-mapping table.
- Test harness patterns (AsyncMock + `assert_not_awaited`, monkeypatch raw tool, parametrized status mapping, `str(result.model_dump())` no-leak assertion) all have direct analogs; graph-test monkeypatch seam at `test_graph.py:155-157` must be retargeted to the facade during migration.

### File Created
`/Users/ming/projects/MOCA/.planning/phases/09-business-tool-facade/09-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can reference these analogs and excerpts directly in the Wave 1-4 PLAN.md action sections (A=schemas, B=registry, C=adapters, D=service, E=node migration).
