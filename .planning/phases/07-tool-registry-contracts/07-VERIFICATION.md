---
phase: "07-tool-registry-contracts"
verified: "2026-06-04T10:15:18Z"
status: gaps_found
score: "14/18 must-haves verified"
overrides_applied: 0
gaps:
  - truth: "Invalid literal values and malformed tool outputs are rejected before runtime or returned as structured safe errors."
    status: failed
    reason: "ToolOutput.status is typed as str, and ToolRegistry._to_execution_result treats any non-error status as success. A runtime probe with status='pending' returned a success ToolExecutionResult."
    artifacts:
      - path: "src/agent/tools/registry.py"
        issue: "ToolOutput.status is plain str at line 35; _to_execution_result promotes non-error statuses to success at lines 214-229."
    missing:
      - "Type ToolOutput.status with ToolResultStatus or otherwise reject malformed statuses."
      - "Add a regression test proving status='pending' does not become success."
  - truth: "ToolRegistry.invoke returns structured rejection results rather than leaking validation/conversion exceptions."
    status: failed
    reason: "Input validation and adapter exceptions are caught, but output_schema validation and result conversion happen after the guarded adapter call. A malformed output schema raised a Pydantic ValidationError out of invoke."
    artifacts:
      - path: "src/agent/tools/registry.py"
        issue: "invoke returns _to_execution_result directly at line 172; output validation at line 213 is not caught."
    missing:
      - "Catch output conversion failures in invoke and return a validation_error or tool_error ToolExecutionResult."
      - "Constrain registry output_schema to the wrapper shape expected by _to_execution_result."
  - truth: "Caller-aware registry policy rejects unsafe metadata before execution for all registry callers."
    status: failed
    reason: "The non-investigator caller gates check name and risk_level but ignore side_effect. A model_constructed get_order entry with side_effect='write' executed through load_business_context."
    artifacts:
      - path: "src/agent/tools/registry.py"
        issue: "_caller_can_invoke checks side_effect only for investigator at lines 197-203; load_business_context and retrieve_policy_evidence branches omit side-effect checks at lines 204-207."
    missing:
      - "Require read context tools to have side_effect in {'none', 'read_only'}."
      - "Require retrieval context tools to have side_effect == 'retrieval'."
      - "Add negative registry tests for non-investigator side-effect mismatches."
  - truth: "Dormant investigation state remains ephemeral and cannot persist into later normal graph turns."
    status: failed
    reason: "AgentState marks investigation fields under the ephemeral context section, but receive_request does not reset them. In LangGraph's merged state model, omitted keys can remain from checkpointed state."
    artifacts:
      - path: "src/agent/state.py"
        issue: "investigation_result, investigation_steps, investigation_trigger_reason, and investigation_path are listed as Phase 7 dormant investigation fields at lines 70-74."
      - path: "src/agent/nodes/receive_request.py"
        issue: "receive_request resets older ephemeral fields at lines 28-47 but omits all four investigation fields."
    missing:
      - "Reset investigation_result, investigation_steps, investigation_trigger_reason, and investigation_path in receive_request."
      - "Add a graph regression test that seeds stale investigation fields in a checkpointed thread and verifies the next normal turn clears them."
---

# Phase 7: Tool Registry & Investigation Contracts Verification Report

**Phase Goal:** The workflow has a schema-first registry and typed investigation contracts that safely expose only approved read/retrieval tools to the future investigator while preserving existing tool and API compatibility.
**Verified:** 2026-06-04T10:15:18Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

Phase 7 has the main contract, registry, adapter, state, and test artifacts in place. The default registry path and compatibility tests pass, including the unrestricted target suite: `64 passed, 1 warning`.

However, all four warnings in `07-REVIEW.md` are verification gaps, not advisory follow-up. They affect strict result validation, structured error containment, caller-aware safety checks, and ephemeral state isolation. Those are part of the Phase 7 goal and must-haves.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Investigator-visible tools are defined through one validated registry format with schemas, safety metadata, and prompt-facing guidance. | VERIFIED | `ToolRegistryEntry` requires schemas, risk, side_effect, allowlist flag, `when_to_use`, identifiers, and summary fields in `src/agent/tools/contracts.py:25`; default entries include those fields in `src/agent/tools/registry.py:49`. |
| 2 | Existing approved tools are exposed through adapters without changing direct tool signatures. | VERIFIED | `src/agent/tools/adapters.py:33` delegates to existing tool functions with tenant/user/role/session; adapter tests assert exact forwarding in `tests/agent/test_tools/test_tool_adapters.py:30`. |
| 3 | Missing-schema or investigator-unsafe tools fail before runtime execution. | VERIFIED | Registry construction validates input/output schemas and investigator allowlist/safety metadata in `src/agent/tools/registry.py:174`; tests cover missing schema and unsafe investigator metadata in `tests/agent/test_tools/test_registry.py:90`. |
| 4 | Tool name and input shape are validated before execution. | VERIFIED | `invoke` rejects unknown names and invalid input before awaiting adapters in `src/agent/tools/registry.py:154`; tests assert `adapter.assert_not_awaited()` in `tests/agent/test_tools/test_registry.py:127`. |
| 5 | Disallowed investigator requests return structured safe rejection results. | VERIFIED | Disallowed invocations return `unsafe_tool_request` without execution in `src/agent/tools/registry.py:159`; test coverage at `tests/agent/test_tools/test_registry.py:138`. |
| 6 | Prompt-facing results exclude raw payloads and expose declared summaries/evidence refs only. | PARTIAL | Happy path sanitization is tested at `tests/agent/test_tools/test_registry.py:171`, but malformed output status can become success and malformed output conversion can raise outside `invoke`. |
| 7 | Invalid literal values are rejected before runtime. | FAILED | Prompt-facing `ToolExecutionResult` rejects invalid status in tests, but registry wrapper `ToolOutput.status` is plain `str` at `src/agent/tools/registry.py:35`; runtime probe with `status='pending'` returned success. |
| 8 | Registry invocation returns structured errors rather than graph-level crashes. | FAILED | Output conversion exceptions from `entry.output_schema.model_validate(raw_result)` at `src/agent/tools/registry.py:213` are not caught; runtime probe raised `ValidationError`. |
| 9 | Caller-aware policy enforces safe metadata for all registry callers. | FAILED | `load_business_context` and `retrieve_policy_evidence` gates ignore `side_effect` at `src/agent/tools/registry.py:204`; runtime probe executed a `side_effect='write'` get_order entry. |
| 10 | Downstream phases have a typed InvestigationResult contract. | VERIFIED | `InvestigationResult` is strict/versioned in `src/agent/schemas.py:64`; tests cover valid and invalid versions/stop reasons in `tests/agent/test_tools/test_tool_contracts.py:204`. |
| 11 | AgentState has optional dormant investigation keys. | VERIFIED | Optional fields are present in `src/agent/state.py:70`; tests show they are optional in `tests/agent/test_tools/test_tool_contracts.py:214`. |
| 12 | Current graph/API outputs remain unchanged in default paths. | VERIFIED | Graph negative assertions are in `tests/agent/test_graph.py:173` and API payload negative assertions are in `tests/test_agent_runs_api.py:178`; target suite passed unrestricted. |
| 13 | Existing thread memory fields continue to work unchanged. | VERIFIED | Cross-turn evidence and context tests still pass in `tests/agent/test_graph.py:267` and `tests/agent/test_graph.py:283`. |
| 14 | Dormant investigation fields are ephemeral and reset per turn. | FAILED | `receive_request` resets older ephemeral fields but omits investigation fields in `src/agent/nodes/receive_request.py:28`; stale checkpointed fields can persist. |
| 15 | REG-08 raw payload leakage prevention is covered by tests. | VERIFIED | Registry sanitization test asserts raw policy `text` is absent from model dumps in `tests/agent/test_tools/test_registry.py:217`. |
| 16 | REG-09 selection metadata exists for prompt tool selection. | VERIFIED | Default entries include descriptions, `when_to_use`, `required_identifiers`, and `result_summary_fields` in `src/agent/tools/registry.py:77`. |
| 17 | TEST-01 unit coverage exists for registry validation, unsafe exclusion, schema failures, and allowed invocation. | VERIFIED | Contract, registry, adapter, graph, and API tests passed in the unrestricted target suite. |
| 18 | Phase 7 remains contract-only with no graph routing/API response expansion. | VERIFIED | `src/agent/graph.py` routing remains unchanged; tests assert no investigation nodes or response fields in `tests/agent/test_graph.py:174` and `tests/test_agent_runs_api.py:345`. |

**Score:** 14/18 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agent/tools/contracts.py` | Typed registry metadata, invocation context, and prompt-facing result contracts | VERIFIED | Strict Pydantic models and literals exist; prompt-facing models use `extra="forbid"`. |
| `src/agent/tools/registry.py` | Registry validation, allowlist lookup, caller-aware invocation, structured rejections | PARTIAL | Default path exists, but WR-01, WR-02, and WR-03 show malformed output and some unsafe metadata paths are not safely rejected. |
| `src/agent/tools/adapters.py` | Typed wrappers for the four approved existing tools | VERIFIED | Adapters validate typed inputs and delegate to existing functions. |
| `src/agent/schemas.py` | Strict `InvestigationResult` validation | VERIFIED | Versioned schema with typed fields, confidence bounds, stop reasons, and `extra="forbid"`. |
| `src/agent/state.py` | Dormant optional investigation state keys | PARTIAL | Keys exist, but they are not reset despite being classified as ephemeral. |
| `tests/agent/test_tools/test_tool_contracts.py` | Contract and state validation tests | VERIFIED | Covers metadata, literals, prompt fields, InvestigationResult, optional AgentState keys. |
| `tests/agent/test_tools/test_registry.py` | Allowlist, unsafe exclusion, fail-fast, non-execution, sanitization | PARTIAL | Good happy-path and investigator checks, missing review-regression edge cases. |
| `tests/agent/test_tools/test_tool_adapters.py` | Adapter forwarding tests | VERIFIED | Exact async forwarding assertions exist for all four adapters. |
| `tests/agent/test_graph.py` | Backward-compatible graph behavior | VERIFIED | Default graph path and memory regressions pass. Missing stale investigation reset regression. |
| `tests/test_agent_runs_api.py` | Public API response compatibility | VERIFIED | API response payloads assert dormant investigation fields are absent; passed with DB access. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tests/agent/test_tools/test_tool_contracts.py` | `src/agent/tools/contracts.py` | Pydantic validation assertions | VERIFIED | Tests import and validate `ToolRegistryEntry`, `ToolInvocationContext`, and `ToolExecutionResult`. |
| `src/agent/tools/registry.py` | `src/agent/tools/contracts.py` | Contract model imports | VERIFIED | Registry imports `ToolExecutionResult`, `ToolInvocationContext`, and `ToolRegistryEntry`. |
| `tests/agent/test_tools/test_registry.py` | `src/agent/tools/registry.py` | Registry invocation and AsyncMock non-execution assertions | VERIFIED | Tests use `ToolRegistry`, `RegisteredTool`, and `adapter.assert_not_awaited()`. |
| `src/agent/tools/adapters.py` | Existing tool modules | Delegated async calls | VERIFIED | Adapters import `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`. |
| `src/agent/tools/registry.py` | `src/agent/tools/adapters.py` | Default registered adapter callables | VERIFIED | Default tools use public adapter models and callables. |
| `src/agent/state.py` | `src/agent/schemas.py` | Compatible investigation result strategy | PARTIAL | State stores `investigation_result` as `dict[str, Any]`, which is compatible but not type-linked to `InvestigationResult`. Plan allowed a compatible strategy, so not a blocking gap by itself. |
| `receive_request` | `AgentState` ephemeral investigation fields | Per-turn reset | FAILED | The four new ephemeral fields are not reset. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `ToolRegistry.invoke` | `validated_input` | `tool.entry.input_schema.model_validate(input_data)` | Yes | FLOWING |
| `ToolRegistry.invoke` | `raw_result` | Awaited adapter call | Yes | FLOWING |
| `ToolRegistry._to_execution_result` | `ToolExecutionResult.summary` | `entry.result_summary_fields` filtering over `output.data` | Partial | HOLLOW_EDGE - malformed statuses and output schema mismatches are not safely contained. |
| `ToolRegistry._to_execution_result` | `evidence_refs` | `_evidence_refs_from_data(data)` | Yes | FLOWING |
| `AgentState` investigation fields | dormant state keys | Future phases/manual state/checkpointer | Partial | HOLLOW_EDGE - fields exist but are not reset in `receive_request`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 7 target non-DB and API suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q --tb=short` | `64 passed, 1 warning` with local DB access | PASS |
| Non-API contract/registry/adapter/graph suite in sandbox | `uv run pytest ... -q` | `50 passed, 1 warning` | PASS |
| Malformed adapter status | Runtime probe invoking registry with adapter `status='pending'` | Returned `{'status': 'success', ...}` | FAIL |
| Malformed output schema conversion | Runtime probe with output_schema lacking `status/data/error` | Raised Pydantic `ValidationError` out of `invoke` | FAIL |
| Non-investigator side-effect mismatch | Runtime probe with `caller='load_business_context'`, `side_effect='write'` | Returned success and awaited adapter once | FAIL |
| API test under sandboxed DB access | Same target suite without elevated local DB access | 56 passed, 8 setup errors from `PermissionError` connecting to local DB | ENVIRONMENT BLOCKED, rerun unrestricted passed |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REG-01 | 07-01 | Schema-first tool registry metadata | SATISFIED | `ToolRegistryEntry` required fields and tests for missing metadata. |
| REG-02 | 07-02 | Investigator selects only allowed read/retrieval tools | SATISFIED | Investigator gate checks allowlist, risk, and side_effect; exact allowlist test passes. |
| REG-03 | 07-02 | Initial investigator registry includes only four approved tools | SATISFIED | `INVESTIGATOR_TOOL_NAMES` and exact set test. |
| REG-04 | 07-02 | Write/action/approval mutation tools excluded | SATISFIED | Unsafe names excluded and outside allowlist rejected for investigator. |
| REG-05 | 07-02 | Registry validation fails fast on missing/inconsistent/unsafe metadata | PARTIAL | Missing schemas and investigator-unsafe metadata fail; output wrapper mismatch and non-investigator side-effect mismatch remain gaps. |
| REG-06 | 07-03 | Typed input/output adapters around existing tools | SATISFIED | Adapter models and forwarding tests exist. |
| REG-07 | 07-02 | Invocation validates name/input before execution and records unsafe request | PARTIAL | Name/input/disallowed investigator paths work; output conversion can escape as exception. |
| REG-08 | 07-03 | Results summarized/sanitized to avoid prompt bloat/raw leakage | PARTIAL | Happy path sanitizes raw data; malformed status can be promoted to success, weakening strict result boundary. |
| REG-09 | 07-03 | Metadata includes tool-selection prompting information | SATISFIED | Default entries include `when_to_use`, `required_identifiers`, and `result_summary_fields`. |
| STATE-01 | 07-04 | AgentState extended backward-compatibly with optional investigation fields | PARTIAL | Optional fields exist and API surface remains unchanged, but fields are not reset despite being ephemeral. |
| STATE-02 | 07-04 | InvestigationResult versioned or explicitly typed | SATISFIED | `schema_version: Literal["v1"]` and strict tests. |
| STATE-03 | 07-04 | InvestigationResult distinguishes structured fields | SATISFIED | Facts, evidence refs, missing info, candidate action, confidence, stop reason, and safety notes exist. |
| STATE-04 | 07-04 | Existing persistent thread memory fields continue unchanged | PARTIAL | Existing memory tests pass; stale dormant investigation fields can persist because reset path omits them. |
| TEST-01 | 07-01, 07-03, 07-04 | Unit tests cover registry validation, unsafe exclusion, schema failures, allowed invocation | PARTIAL | Required positive tests exist and pass; missing edge-case regression tests for all four review warnings. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/agent/tools/registry.py` | 35 | Loose `status: str` on tool wrapper output | Blocker | Malformed statuses can be interpreted as success. |
| `src/agent/tools/registry.py` | 172 | Result conversion outside exception guard | Blocker | Malformed output can raise out of `invoke` instead of structured rejection. |
| `src/agent/tools/registry.py` | 204 | Non-investigator caller gates omit side-effect checks | Blocker | Unsafe metadata can execute for non-investigator registry callers. |
| `src/agent/nodes/receive_request.py` | 28 | Ephemeral investigation fields omitted from reset dict | Blocker | Stale checkpointed investigation state can persist into later turns. |

### Human Verification Required

None. The remaining gaps are code-level contract and state behavior issues that are programmatically reproducible.

### Gaps Summary

The phase achieved most of the intended surface area: contracts, registry, adapters, strict investigation schema, optional state keys, and compatibility tests are present and wired. The goal is not fully achieved because the review warnings expose paths where strict validation and safe structured rejection do not hold, plus a state reset omission that contradicts the dormant ephemeral-state boundary.

Fixing the four gaps should make this phase eligible for re-verification without requiring new product scope.

---

_Verified: 2026-06-04T10:15:18Z_
_Verifier: Claude (gsd-verifier)_
