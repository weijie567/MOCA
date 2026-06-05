# Phase 7: Tool Registry & Investigation Contracts - Research

**Researched:** 2026-06-04
**Status:** Ready for planning
**Mode:** Main-session research per project preference; no researcher subagent spawned.

## Research Question

What does the planner need to know to plan Phase 7 well?

Phase 7 should add schema-first tool registry contracts, safe invocation boundaries, typed adapters, dormant investigation state fields, and tests while preserving the existing v1.0 graph, API, approval, and direct tool-call behavior.

## Source Artifacts Read

- `.planning/phases/07-tool-registry-contracts/07-SPEC.md` - locked Phase 7 requirements and boundaries.
- `.planning/phases/07-tool-registry-contracts/07-CONTEXT.md` - implementation decisions D-01 through D-15.
- `.planning/ROADMAP.md` - Phase 7 goal, dependency, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` - REG-01 through REG-09, STATE-01 through STATE-04, TEST-01.
- `.planning/STATE.md` - current milestone constraints and status.
- `src/agent/tools/get_order.py`, `get_refund_case.py`, `get_ticket.py`, `search_policy.py`, `create_coupon_grant_draft.py` - existing allowed and unsafe tools.
- `src/agent/state.py`, `src/agent/schemas.py`, `src/agent/graph.py` - state/schema/graph contracts.
- `src/agent/nodes/load_business_context.py`, `src/agent/nodes/retrieve_policy_evidence.py` - existing direct tool call path to preserve.
- `tests/agent/test_tools/`, `tests/agent/test_graph.py`, `tests/test_agent_runs_api.py` - existing unit and regression patterns.
- `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml` - dependency and verification commands.

## Current Code Facts

### Existing allowed tools

The four Phase 7 investigator-visible tools already exist as async functions with direct signatures and dict outputs:

- `get_order(order_no, tenant_id, user_id, role, session)` in `src/agent/tools/get_order.py`
- `get_refund_case(refund_case_no, tenant_id, user_id, role, session)` in `src/agent/tools/get_refund_case.py`
- `get_ticket(ticket_id, tenant_id, user_id, role, session)` in `src/agent/tools/get_ticket.py`
- `search_policy(query, tenant_id, user_id, role, session, top_k=5, doc_type=None, risk_level=None)` in `src/agent/tools/search_policy.py`

Each returns a dict shaped like:

```python
{"status": "success", "data": {...}, "error": {}}
{"status": "error", "data": {}, "error": {"error_code": str, "message": str, "retryable": bool, ...}}
```

Adapter plans must wrap these functions and keep existing signatures intact. Existing graph nodes and tests directly import/call these functions.

### Existing unsafe/write tool

`src/agent/tools/create_coupon_grant_draft.py` creates or reuses action drafts inside `execute_action`. It takes write-side fields such as `run_id`, `approval_request_id`, `idempotency_key`, `action_type`, and `payload`, and must not become investigator-allowed.

The planner should require explicit registry metadata or validation tests proving `create_coupon_grant_draft`, `execute_action`, and approval mutations cannot appear in the investigator-allowed set.

### Current graph path to preserve

`src/agent/graph.py` builds the current path:

`receive_request -> classify_intent -> extract_slots -> load_business_context -> retrieve_policy_evidence -> generate_recommendation -> assess_risk_and_approval -> approval_gate/execute_action/final_response`

Phase 7 must not add an investigator node, alter graph edges, change routing, or make deterministic nodes call the registry at runtime.

`load_business_context` currently calls `get_order`, `get_refund_case`, and `get_ticket` directly. `retrieve_policy_evidence` calls `search_policy` directly and stores raw retrieval output under `retrieved_evidence`.

### State and schema pattern

`src/agent/state.py` uses `TypedDict(total=False)` for optional state fields. New fields should follow that style:

- `investigation_result`
- `investigation_steps`
- `investigation_trigger_reason`
- `investigation_path`

`src/agent/schemas.py` uses Pydantic `BaseModel`, `Field`, and `Literal[...]` for structured LLM/output schemas. New prompt-facing contracts should use Pydantic v2 `model_config = ConfigDict(extra="forbid")` where unknown fields must be rejected.

### Tool output sanitization risk

`search_policy` currently returns raw evidence entries with `text`. Phase 7 must ensure `ToolExecutionResult` exposes only:

- `status`
- `error`
- `evidence_refs`
- fields declared by registry `result_summary_fields`

Raw `data` and policy evidence `text` must not be included in investigator-facing results unless explicitly declared as summary fields. The safer default is to never declare `text` as a summary field in Phase 7.

## Recommended Implementation Shape

### 1. Contracts first

Create `src/agent/tools/contracts.py` with typed Pydantic contracts and literal aliases. Suggested literal values:

- `ToolRiskLevel = Literal["read", "retrieval", "write", "action", "approval"]`
- `ToolSideEffect = Literal["none", "read_only", "retrieval_only", "writes_draft", "mutates_approval", "executes_action"]`
- `ToolResultStatus = Literal["success", "error", "rejected"]`
- `ToolErrorCode = Literal["not_found", "unsafe_tool_request", "validation_error", "tool_error"]`
- `ToolCaller = Literal["investigator", "load_business_context", "retrieve_policy_evidence", "execute_action"]`

Suggested models:

- `ToolInputContext` or `ToolInvocationContext` with `tenant_id`, `user_id`, `role`, `session`, and `caller`.
- `ToolDefinition` or `ToolRegistryEntry` with required registry fields from REG-01 and REG-09.
- `ToolExecutionResult` with prompt-facing sanitized fields only.

Keep SQLAlchemy `AsyncSession` out of prompt-facing serialization. It can live in invocation context with arbitrary types allowed or remain a plain dataclass if easier.

### 2. Add adapters around existing functions

Create `src/agent/tools/adapters.py` with Pydantic input models for each allowed tool:

- `GetOrderInput(order_no: str)`
- `GetRefundCaseInput(refund_case_no: str)`
- `GetTicketInput(ticket_id: str)`
- `SearchPolicyInput(query: str, top_k: int = Field(default=5, ge=1, le=10), doc_type: str | None = None, risk_level: str | None = None)`

Adapters should validate input, call existing functions with context tenant/user/role/session, and return raw dicts only to registry internals. Existing direct-call tests should keep passing unchanged.

### 3. Build registry and validation

Create `src/agent/tools/registry.py` with a `ToolRegistry` class that:

- validates entries at construction time;
- indexes by tool `name`;
- exposes `investigator_tools()` or equivalent selection metadata for prompting;
- validates caller and requested tool name before execution;
- validates input shape before calling an adapter;
- returns structured `ToolExecutionResult` for unknown tools, disallowed tools, invalid input, and adapter/tool errors;
- sanitizes success payloads using registry `result_summary_fields` and evidence ref extraction.

The registry should fail fast for invalid definitions: missing schema, missing safety metadata, `allowed_in_investigator=True` with non-read/retrieval risk, and side-effecting tools marked investigator-allowed.

### 4. Add investigation schema and dormant state

Add `InvestigationResult` in `src/agent/schemas.py`, not in tools. Suggested fields:

- `schema_version: Literal["v1"] = "v1"`
- `facts: list[str]`
- `evidence_refs: list[EvidenceRefSchema]`
- `missing_info: list[str]`
- `candidate_action: dict[str, Any] | None` or a small typed model if easy
- `confidence: float = Field(ge=0.0, le=1.0)`
- `stop_reason: Literal["sufficient_evidence", "insufficient_evidence", "unsafe_tool_request", "tool_error", "iteration_budget_exhausted"]`
- `safety_notes: list[str]`

Use `extra="forbid"` for prompt-facing/evolvable contracts.

Add optional dormant fields to `AgentState` only. Do not read them in graph nodes during Phase 7.

## Planning Recommendations

Split implementation into small plans that preserve compatibility gates:

1. Contract models and schema tests first.
2. Registry validation and safe rejection tests second.
3. Adapters and allowed invocation tests third.
4. Dormant state fields plus graph/API regression preservation last.

A single large plan would mix schema design, runtime boundary, adapter behavior, and graph regression proof. Separate plans reduce risk and make failures easier to localize.

## Test Strategy

Add focused new tests under existing test style:

- `tests/agent/test_tools/test_tool_contracts.py`
  - required metadata fields validate;
  - literals reject invalid risk/side-effect/status/stop reason values;
  - `extra="forbid"` rejects unknown prompt-facing fields;
  - `ToolExecutionResult` excludes raw payload by contract;
  - `InvestigationResult` validates `schema_version="v1"`, confidence bounds, and stop reason literals.

- `tests/agent/test_tools/test_registry.py`
  - investigator-allowed tool names equal exactly `{get_order, get_refund_case, get_ticket, search_policy}`;
  - `create_coupon_grant_draft`, `execute_action`, and approval mutations are not investigator-allowed;
  - missing schema/safety metadata fails before execution;
  - unsafe risk/side-effect combinations fail registry validation;
  - unknown or disallowed requested tool returns structured rejection and does not call underlying function;
  - invalid input returns structured validation error and does not call adapter.

- `tests/agent/test_tools/test_tool_adapters.py`
  - each allowed adapter calls the existing tool function with `tenant_id`, `user_id`, `role`, `session` from context;
  - allowed success results are summarized through registry result fields;
  - `search_policy` success result does not expose raw evidence `text` in `ToolExecutionResult`.

Regression checks should include:

```bash
uv run pytest tests/agent/test_tools tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q
uv run ruff check src/ tests/
```

CI-style broader check available:

```bash
uv run pytest tests/ -x --ignore=tests/integration -q --tb=short
uv run ruff format --check .
```

## Validation Architecture

Phase 7 has no database schema changes, so no ORM/schema push task is required. Validation should be code/test based:

- Contract validation: Pydantic model validation rejects invalid registry metadata, invalid invocation inputs, invalid result status/error codes, invalid investigation stop reasons, and unknown prompt-facing fields.
- Safety validation: registry construction fails fast before runtime execution for unsafe or incomplete metadata.
- Boundary validation: runtime invocation returns structured rejection results for unknown, disallowed, and schema-invalid requests without awaiting/calling the underlying unsafe function.
- Sanitization validation: `ToolExecutionResult` contains only `status`, `error`, `evidence_refs`, and registry-declared summary fields; no raw `data` payload or policy evidence `text` leaks to prompt-facing output.
- Regression validation: graph edges, direct tool calls, API behavior, approval/action path, and v1.0 tests remain unchanged.

## Risks and Pitfalls

- Rewiring `load_business_context` or `retrieve_policy_evidence` to the registry in Phase 7 would violate the phase boundary and add unnecessary regression risk.
- Returning raw adapter payloads from `ToolRegistry.invoke` would fail REG-08 and defeat the safe investigator prompt boundary.
- Making `create_coupon_grant_draft` absent without any explicit exclusion test could leave the unsafe boundary under-specified. Tests should prove both exact allowlist and unsafe exclusion.
- Putting `InvestigationResult` inside `src/agent/tools/contracts.py` would hide it from downstream graph/schema consumers; context requires `src/agent/schemas.py`.
- Overly generic registry abstractions could obscure the four concrete v1.1 tools. Keep the initial registry explicit and small.

## Files Planner Should Touch

Expected implementation files:

- `src/agent/tools/contracts.py` - new tool metadata, invocation, and result contracts.
- `src/agent/tools/registry.py` - new registry construction, validation, lookup, invocation, sanitization.
- `src/agent/tools/adapters.py` - new typed wrappers around allowed existing tools.
- `src/agent/schemas.py` - add `InvestigationResult` and supporting typed schemas if needed.
- `src/agent/state.py` - add dormant optional investigation fields.
- `tests/agent/test_tools/test_tool_contracts.py` - new contract tests.
- `tests/agent/test_tools/test_registry.py` - new registry/safety tests.
- `tests/agent/test_tools/test_tool_adapters.py` - new adapter/sanitization tests.

Files to read and preserve:

- `src/agent/tools/get_order.py`
- `src/agent/tools/get_refund_case.py`
- `src/agent/tools/get_ticket.py`
- `src/agent/tools/search_policy.py`
- `src/agent/tools/create_coupon_grant_draft.py`
- `src/agent/nodes/load_business_context.py`
- `src/agent/nodes/retrieve_policy_evidence.py`
- `src/agent/graph.py`
- `tests/agent/test_tools/`
- `tests/agent/test_graph.py`
- `tests/test_agent_runs_api.py`

## Research Conclusion

Plan Phase 7 as a compatibility-preserving contract and boundary phase. The core work is not graph orchestration; it is creating typed contracts, explicit registry metadata, caller-aware validation, safe invocation rejection, result sanitization, dormant state fields, and focused tests that prove unsafe tools cannot cross the future investigator boundary.

## RESEARCH COMPLETE
