# Phase 7: tool-registry-contracts - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 delivers a schema-first tool registry, typed tool/investigation contracts, safe registry invocation boundary, and dormant investigation state fields for the future v1.1 investigator. Requirements are locked by SPEC.md. This phase prepares contracts and boundaries only; it must not change existing graph edges, routing, `generate_recommendation`, investigator execution, public API responses, or v1.0 runtime behavior.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**9 requirements are locked.** See `07-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `07-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- Schema-first registry metadata contract for tool definitions.
- Investigator allowlist metadata for `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`.
- Explicit exclusion of write/action/approval mutation tools from investigator access.
- Registry validation that fails fast for missing, inconsistent, or unsafe metadata.
- Typed adapters around existing agent tool functions.
- Safe invocation boundary that validates tool name and input schema before execution.
- Structured unsafe-tool rejection results that do not execute disallowed tools.
- Investigator-facing `ToolExecutionResult` sanitization based on registry-declared `result_summary_fields` plus `status`, `error`, and `evidence_refs`.
- Typed `InvestigationResult` contract and optional dormant `AgentState` fields.
- Unit/regression tests covering registry validation, unsafe tool exclusion, schema validation failures, allowed read-only invocation, result sanitization, and v1.0 behavior preservation.

**Out of scope (from SPEC.md):**
- Changing graph edges or adding an investigator node — Phase 7 only prepares contracts and boundaries for later routing/execution phases.
- Changing `generate_recommendation` behavior or making it consume `InvestigationResult` — recommendation integration belongs to a later workflow preservation phase.
- Implementing deterministic investigation routing — Phase 8 owns routing trigger decisions.
- Implementing the bounded investigator execution loop — Phase 9 owns iteration, tool selection, stop conditions, and advisory output generation.
- Replacing existing tool function signatures wholesale — adapters should wrap existing functions unless a minimal compatibility-preserving change is strictly necessary.
- Full field-level PII redaction system — Phase 7 prevents raw payloads from entering investigator-facing prompt results, but complete PII redaction policy is not part of this phase.
- Changing public API request/response contracts — v1.0 clients must remain backward compatible.
- Changing approval semantics, action draft creation, or action execution — approval and execution remain downstream and authoritative.

</spec_lock>

<decisions>
## Implementation Decisions

### Module layout
- **D-01:** Split registry implementation into three files under the existing agent tools package:
  - `src/agent/tools/registry.py` — registry construction, validation, lookup, and `ToolRegistry.invoke(...)` orchestration.
  - `src/agent/tools/contracts.py` — tool registry metadata models, `ToolExecutionResult`, invocation context, risk/side-effect/status/error literals, and related tool contract types.
  - `src/agent/tools/adapters.py` — typed adapters around existing `src/agent/tools/*` functions.
- **D-02:** Put `InvestigationResult` in `src/agent/schemas.py`, alongside existing structured agent outputs such as `RecommendationDraft` and `RiskAssessment`.
- **D-03:** Existing graph nodes must keep their current direct tool calls during Phase 7. `load_business_context` and `retrieve_policy_evidence` must not be rewired to registry runtime in this phase.

### Schema strictness
- **D-04:** Use strict `Literal[...]` or enum-like literal fields for registry and investigation contract values such as `risk_level`, `side_effect`, `stop_reason`, result status, and error codes.
- **D-05:** Use Pydantic `BaseModel` for registry metadata, invocation context, input/output contract wrappers, `ToolExecutionResult`, and `InvestigationResult` where typed validation is required.
- **D-06:** Prompt-facing Pydantic contracts should use `extra="forbid"` so unknown fields cannot silently enter investigator-facing outputs.
- **D-07:** `InvestigationResult` should express versioning as `schema_version: Literal["v1"] = "v1"`.

### Invocation API
- **D-08:** The long-term unified tool runtime entrypoint is `ToolRegistry.invoke(name, input, context)`.
- **D-09:** Invocation `context` must include a `caller` field. Registry policy is caller-aware:
  - `investigator` can call only read/retrieval tools.
  - `load_business_context` can call only deterministic read tools.
  - `retrieve_policy_evidence` can call only retrieval tools.
  - `execute_action` may later call action tools only after approval preconditions are satisfied.
- **D-10:** Phase 7 must not rewire existing graph nodes, but the invocation API should be shaped so later migration of deterministic nodes to registry runtime is possible without redesign.
- **D-11:** `ToolRegistry.invoke(...)` returns prompt-facing `ToolExecutionResult` only. It must not return raw tool payloads to the future investigator prompt boundary.
- **D-12:** Runtime invalid tool requests return structured `ToolExecutionResult` values rather than graph-level exceptions. Error codes should distinguish at least `not_found`, `unsafe_tool_request`, `validation_error`, and `tool_error`.

### Test strategy
- **D-13:** Add focused tests split by layer:
  - `tests/agent/test_tools/test_registry.py` for registry construction, validation, lookup, caller policy, allowlist/exclusion, and unsafe request behavior.
  - `tests/agent/test_tools/test_tool_contracts.py` for Pydantic contracts, strict literal validation, `extra="forbid"`, `ToolExecutionResult`, and `InvestigationResult` shape/versioning.
  - `tests/agent/test_tools/test_tool_adapters.py` for adapter invocation around existing read/retrieval tools.
- **D-14:** Minimum verification should include new registry/schema/adapter tests plus targeted v1.0 behavior regression tests, especially `tests/agent/test_graph.py`, existing `tests/agent/test_tools/`, and relevant agent API regression such as `tests/test_agent_runs_api.py`.
- **D-15:** Unsafe tool non-execution should be proven with mocks or `AsyncMock`: disallowed tool requests must return structured rejection results and underlying unsafe functions must not be called. Allowed tool adapter tests can reuse existing fake repository/session patterns.

### Claude's Discretion
- Planner may decide exact class and helper names inside the locked file/module boundaries.
- Planner may decide whether literal fields are implemented as `typing.Literal` aliases or small enum-like type aliases, as long as Pydantic validation rejects invalid values.
- Planner may choose the exact shape of summary dictionaries inside `ToolExecutionResult`, as long as only declared `result_summary_fields` plus `status`, `error`, and `evidence_refs` are prompt-facing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked phase requirements
- `.planning/phases/07-tool-registry-contracts/07-SPEC.md` — Locked Phase 7 requirements, boundaries, acceptance criteria, and deferred follow-up.

### Milestone planning
- `.planning/ROADMAP.md` §Phase 7 — Phase goal, dependency, requirement IDs, and success criteria.
- `.planning/REQUIREMENTS.md` — v1.1 REG, STATE, TEST, FLOW, ROUTE, INV, TRACE, and EVAL requirement boundaries; Phase 7 maps to REG-01 through REG-09, STATE-01 through STATE-04, and TEST-01.
- `.planning/PROJECT.md` — v1.1 milestone principles: bounded investigator inside deterministic workflow, read-only/retrieval investigator, fast path/API/approval preservation.
- `.planning/STATE.md` — Current phase context and active constraints.

### Existing source contracts
- `src/agent/tools/get_order.py` — Existing read-only order tool function to wrap via adapter.
- `src/agent/tools/get_refund_case.py` — Existing read-only refund case tool function to wrap via adapter.
- `src/agent/tools/get_ticket.py` — Existing read-only ticket tool function to wrap via adapter.
- `src/agent/tools/search_policy.py` — Existing retrieval tool; current raw evidence includes `text`, which must not leak into prompt-facing `ToolExecutionResult` unless explicitly declared.
- `src/agent/tools/create_coupon_grant_draft.py` — Existing action/write tool; must be excluded from investigator allowlist.
- `src/agent/graph.py` — Existing graph topology; Phase 7 must not alter graph edges or runtime path.
- `src/agent/state.py` — Existing `AgentState` TypedDict; Phase 7 adds dormant optional fields only.
- `src/agent/schemas.py` — Existing structured agent output schemas; add `InvestigationResult` here.

### Existing tests to preserve and extend
- `tests/agent/test_tools/` — Existing tool tests and patterns for fake repos/sessions.
- `tests/agent/test_graph.py` — Existing graph behavior regression path; should remain passing.
- `tests/agent/test_nodes/test_retrieve_policy_evidence.py` — Existing policy retrieval node behavior and evidence refs.
- `tests/test_agent_runs_api.py` — Existing run/API behavior regression coverage.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/tools/get_order.py`, `get_refund_case.py`, `get_ticket.py`, `search_policy.py`: existing async functions returning `{status, data, error}` dicts; adapters should wrap these rather than rewrite signatures.
- `src/agent/tools/authz.py`: existing tenant/merchant authorization helper used by read tools; adapters should not bypass it.
- `src/agent/schemas.py`: existing Pydantic model home for structured agent outputs.
- `src/agent/state.py`: existing TypedDict state contract with optional fields style via `total=False`.
- Existing pytest patterns under `tests/agent/test_tools/` and `tests/agent/test_nodes/` use `AsyncMock`, fake repos, and session fixtures that Phase 7 tests can reuse.

### Established Patterns
- Agent tool functions are async, accept explicit `tenant_id`, `user_id`, `role`, and `session`, and return structured dict results rather than raising on normal tool errors.
- Graph nodes currently call tools directly and append trace steps manually. Phase 7 must preserve this path.
- Pydantic schemas in `src/agent/schemas.py` use explicit `Literal` values and field bounds for structured model outputs.
- Existing tests favor focused unit tests with monkeypatching and deterministic fake LLM/tool behavior.

### Integration Points
- New registry files should live under `src/agent/tools/` and wrap existing agent tool functions.
- New dormant state fields should be added to `AgentState` without changing `receive_request`, graph edges, API serialization, or current runtime outputs.
- New `InvestigationResult` schema in `src/agent/schemas.py` will be consumed by later phases but should not be read by `generate_recommendation` in Phase 7.
- Future phases can use `ToolRegistry.invoke(...)` as the runtime tool boundary without requiring Phase 7 to rewire deterministic nodes.

</code_context>

<specifics>
## Specific Ideas

- Caller-aware registry policy is intentional future-proofing. Phase 7 should model caller policy now even though only future investigator usage is expected immediately.
- Deterministic read/retrieval nodes should eventually migrate to registry runtime, but only after Phase 9/10 investigator path is stable and only if existing output, trace, fallback, tests, and API compatibility are preserved.

</specifics>

<deferred>
## Deferred Ideas

- After Phase 9/10 investigator path is stable, migrate deterministic read/retrieval nodes (`load_business_context`, `retrieve_policy_evidence`) to registry runtime to unify tool invocation boundaries. This future work must preserve existing `AgentState` outputs, trace semantics, fallback behavior, tests, and API response compatibility. It must not change deterministic tool-selection logic or make these nodes LLM-driven.

</deferred>

---

*Phase: 07-tool-registry-contracts*
*Context gathered: 2026-06-04*
