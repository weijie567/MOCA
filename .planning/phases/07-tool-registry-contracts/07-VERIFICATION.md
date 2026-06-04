---
phase: 07-tool-registry-contracts
verified: 2026-06-04T10:51:18Z
status: passed
score: 18/18 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 14/18
  gaps_closed:
    - "Malformed ToolOutput status values such as pending cannot become success."
    - "ToolRegistry.invoke returns structured safe errors for output conversion/validation failures."
    - "Caller-aware registry policy rejects non-investigator side-effect mismatches before execution."
    - "Dormant investigation fields reset per turn in receive_request and cannot persist from checkpointed state into normal graph turns."
  gaps_remaining: []
  regressions: []
---

# Phase 7: Tool Registry & Investigation Contracts Verification Report

**Phase Goal:** The workflow has a schema-first registry and typed investigation contracts that safely expose only approved read/retrieval tools to the future investigator while preserving existing tool and API compatibility.
**Verified:** 2026-06-04T10:51:18Z
**Status:** passed
**Re-verification:** Yes - after gap closure plan 07-05.

## Goal Achievement

Phase 7 now meets the roadmap goal. The registry contracts are schema-first, the default investigator allowlist is exactly the approved read/retrieval tools, runtime invocation returns structured safe results for unsafe or malformed requests, prompt-facing results are sanitized, and dormant investigation state is reset per graph turn while current graph/API behavior remains compatible.

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Investigator-visible tools are defined through one validated registry format with schemas, safety metadata, and prompt-facing guidance. | VERIFIED | `ToolRegistryEntry` requires schema, risk, side-effect, allowlist, `when_to_use`, identifiers, and summary fields in `src/agent/tools/contracts.py`; default entries populate them in `src/agent/tools/registry.py`. |
| 2 | Existing approved tools are exposed through adapters without changing direct tool signatures. | VERIFIED | `src/agent/tools/adapters.py` delegates to existing `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`; adapter tests assert exact forwarding. |
| 3 | Missing-schema, unsafe, or write-capable investigator exposure fails before runtime execution. | VERIFIED | Registry construction validates Pydantic schemas, allowlist names, safe risk levels, safe side effects, and `ToolOutput` wrapper shape before indexing tools. |
| 4 | Tool calls through the registry validate name and input shape before execution and return safe structured rejections. | VERIFIED | `ToolRegistry.invoke` returns `not_found`, `unsafe_tool_request`, or `validation_error` without awaiting adapters; tests assert `assert_not_awaited()`. |
| 5 | Tool invocation returns sanitized `ToolExecutionResult` values while raw tool payloads stay internal. | VERIFIED | `_to_execution_result` builds only `summary` from declared `result_summary_fields` plus `evidence_refs`; raw policy `text` is absent from model dumps in tests. |
| 6 | Downstream nodes can read typed investigation contracts and new state fields without breaking existing memory/API behavior. | VERIFIED | `InvestigationResult` exists in `src/agent/schemas.py`; optional dormant fields exist in `AgentState`; graph and API regression tests pass. |
| 7 | Malformed adapter output status values such as `pending` never become prompt-facing success results. | VERIFIED | `ToolOutput.status: ToolResultStatus` rejects invalid statuses; regression test expects `validation_error` and no summary leakage. |
| 8 | `ToolRegistry.invoke` contains output validation/result conversion failures and returns structured errors. | VERIFIED | `_to_execution_result(...)` is guarded for `ValidationError`, `AttributeError`, and `TypeError`; malformed output regression returns `ToolExecutionResult(status="error")`. |
| 9 | Caller-aware registry policy rejects non-investigator side-effect mismatches before execution. | VERIFIED | `load_business_context` requires read risk plus `none/read_only`; `retrieve_policy_evidence` requires retrieval risk plus `retrieval`; negative tests assert adapters are not awaited. |
| 10 | Dormant investigation fields reset at the start of each graph turn. | VERIFIED | `receive_request` resets `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, and `investigation_path` to `None`; checkpoint regression proves stale values are cleared. |
| 11 | Prompt-facing contracts reject undeclared fields and invalid literals. | VERIFIED | Contract tests cover invalid status/error/caller/safety literals and extra prompt-facing fields. |
| 12 | The investigator allowlist is exact. | VERIFIED | `ToolRegistry().investigator_tool_names()` is asserted to equal `{get_order, get_refund_case, get_ticket, search_policy}`. |
| 13 | Unsafe tools and approval/action operations are excluded. | VERIFIED | Tests assert `create_coupon_grant_draft`, `execute_action`, and approval mutation names are disjoint from investigator-visible tools. |
| 14 | `InvestigationResult` is strict and versioned. | VERIFIED | Tests validate `schema_version="v1"`, typed evidence refs, confidence bounds, stop reasons, and `extra="forbid"`. |
| 15 | `AgentState` investigation fields are optional and dormant. | VERIFIED | Minimal `AgentState` works without those keys; no graph routing consumes them in Phase 7. |
| 16 | Existing graph routing remains contract-only with no investigator node. | VERIFIED | `src/agent/graph.py` contains the existing v1.0 nodes and edges only; graph tests assert no investigation node appears. |
| 17 | Public API/event payloads remain backward-compatible. | VERIFIED | `tests/test_agent_runs_api.py` asserts dormant investigation fields are absent from final response and approval event payloads. |
| 18 | TEST-01 coverage exists for registry validation, unsafe exclusion, schema failures, allowed invocation, and regressions. | VERIFIED | Focused Phase 7 suite passed: 69 passed, 1 LangGraph deprecation warning. |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agent/tools/contracts.py` | Typed registry metadata, invocation context, and prompt-facing result contracts | VERIFIED | Strict Pydantic models, literal aliases, and `extra="forbid"` prompt-facing models exist. |
| `src/agent/tools/registry.py` | Registry validation, allowlist lookup, caller-aware invocation, structured rejections, sanitization | VERIFIED | `ToolRegistry`, `RegisteredTool`, `ToolOutput`, exact allowlist, side-effect gates, and output conversion containment exist. |
| `src/agent/tools/adapters.py` | Typed wrappers for the four approved tools | VERIFIED | Pydantic input models and async adapter callables delegate to existing tools. |
| `src/agent/schemas.py` | Strict `InvestigationResult` validation | VERIFIED | Versioned schema with facts, evidence refs, missing info, candidate action, confidence, stop reason, and safety notes. |
| `src/agent/state.py` | Optional dormant investigation state keys | VERIFIED | Four optional keys exist under Phase 7 dormant investigation contracts. |
| `src/agent/nodes/receive_request.py` | Per-turn reset for ephemeral and dormant fields | VERIFIED | All four investigation fields reset to `None` with other per-turn fields. |
| `tests/agent/test_tools/test_tool_contracts.py` | Contract and state validation tests | VERIFIED | Covers metadata completeness, strict literals, prompt-field rejection, `InvestigationResult`, and optional state keys. |
| `tests/agent/test_tools/test_registry.py` | Allowlist, unsafe exclusion, fail-fast, non-execution, sanitization, 07-05 gap regressions | VERIFIED | Includes malformed status, conversion containment, non-investigator side-effect mismatch, and raw policy text leakage tests. |
| `tests/agent/test_tools/test_tool_adapters.py` | Adapter forwarding tests | VERIFIED | Mocks assert exact context and identifier forwarding for all four adapters. |
| `tests/agent/test_graph.py` | Graph compatibility and checkpoint stale-state reset | VERIFIED | Current graph path remains unchanged; stale investigation fields are cleared on next same-thread turn. |
| `tests/agent/test_nodes/test_retrieve_policy_evidence.py` | Existing retrieval node compatibility | VERIFIED | Included in passing Phase 7 suite. |
| `tests/test_agent_runs_api.py` | API/event compatibility | VERIFIED | Included in passing Phase 7 suite; dormant fields remain absent from public payloads. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/agent/tools/registry.py` | `src/agent/tools/contracts.py` | Imports `ToolRegistryEntry`, `ToolInvocationContext`, `ToolExecutionResult`, `ToolResultStatus` | WIRED | Registry enforces the shared contracts at construction and invocation. |
| `src/agent/tools/registry.py` | `src/agent/tools/adapters.py` | Default registry entries use adapter input schemas and callables | WIRED | The default four tools route through public adapter functions. |
| `tests/agent/test_tools/test_registry.py` | `src/agent/tools/registry.py` | `ToolRegistry.invoke` probes and `AsyncMock` assertions | WIRED | Tests prove rejection before execution and safe conversion after execution. |
| `tests/agent/test_tools/test_tool_adapters.py` | Existing tool functions | Monkeypatched adapter imports and `assert_awaited_once_with(...)` | WIRED | Existing direct tool signatures are preserved. |
| `tests/agent/test_tools/test_tool_contracts.py` | `src/agent/tools/contracts.py`, `src/agent/schemas.py`, `src/agent/state.py` | Pydantic validation and TypedDict optional-key checks | WIRED | Contract and state shapes are validated directly. |
| `tests/agent/test_graph.py` | `src/agent/nodes/receive_request.py` | Same-thread `MemorySaver` checkpoint regression | WIRED | Stale dormant fields reset to `None` on the next normal turn. |
| `tests/test_agent_runs_api.py` | Public run event payloads | Negative assertions for investigation fields | WIRED | Public response contracts remain unchanged. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `ToolRegistry.invoke` | `validated_input` | `entry.input_schema.model_validate(input_data)` | Yes | FLOWING |
| `ToolRegistry.invoke` | `raw_result` | Awaited registered adapter | Yes | FLOWING |
| `ToolRegistry.invoke` | structured errors | `_rejection(...)` for name, policy, input, adapter, and output failures | Yes | FLOWING |
| `ToolRegistry._to_execution_result` | `summary` | `entry.result_summary_fields` filtering over validated `ToolOutput.data` | Yes | FLOWING |
| `ToolRegistry._to_execution_result` | `evidence_refs` | `_evidence_refs_from_data(data)` | Yes | FLOWING |
| `receive_request` | dormant investigation fields | Per-turn reset dict | Yes | FLOWING |
| Public API events | response payload fields | `agent_runs.py` emits only existing final/approval payload fields | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 7 focused contract/registry/adapter/graph/API suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q --tb=short` | 69 passed, 1 LangGraph deprecation warning | PASS |
| Source and test lint | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/ tests/` | All checks passed | PASS |
| Later-phase deferral scan | `gsd-sdk query roadmap.analyze --raw` | Later phases cover routing, investigator execution, integration, and evals; no Phase 7 gaps deferred | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REG-01 | 07-01, 07-05 | Schema-first registry metadata | SATISFIED | `ToolRegistryEntry` requires all core schema, safety, and prompt-selection metadata; tests cover missing required fields. |
| REG-02 | 07-02, 07-05 | Investigator can only select allowed read/retrieval tools | SATISFIED | Investigator caller gate checks allowlist, risk, and side-effect metadata. |
| REG-03 | 07-02, 07-05 | Initial investigator registry includes only four approved tools | SATISFIED | Exact allowlist test passes. |
| REG-04 | 07-02, 07-05 | Write/action/approval mutation tools excluded | SATISFIED | Unsafe names are excluded; disallowed write/action registry probes reject without execution. |
| REG-05 | 07-02, 07-05 | Validation fails fast on missing/inconsistent/unsafe metadata | SATISFIED | Registry rejects missing schemas, unsafe investigator metadata, and non-`ToolOutput` output schemas. |
| REG-06 | 07-03, 07-05 | Typed adapters wrap existing tool functions | SATISFIED | Adapter models and forwarding tests exist for all four tools. |
| REG-07 | 07-02, 07-05 | Invocation validates name/input and records structured unsafe result | SATISFIED | Unknown, invalid input, disallowed, adapter error, and output validation paths return structured `ToolExecutionResult` errors. |
| REG-08 | 07-03, 07-05 | Results summarized/sanitized to avoid raw leakage | SATISFIED | `ToolExecutionResult` exposes `summary` and evidence refs only; raw policy `text` is absent in tests. |
| REG-09 | 07-03, 07-05 | Tool-selection prompting metadata exists | SATISFIED | Default entries include descriptions, `when_to_use`, `required_identifiers`, and `result_summary_fields`. |
| STATE-01 | 07-04, 07-05 | Optional investigation fields without API contract changes | SATISFIED | `AgentState` includes optional fields; API payload tests assert those fields remain absent. |
| STATE-02 | 07-04, 07-05 | Versioned/typed `InvestigationResult` | SATISFIED | `schema_version: Literal["v1"]` and strict tests exist. |
| STATE-03 | 07-04, 07-05 | Structured investigation result fields | SATISFIED | Facts, evidence refs, missing info, candidate action, confidence, stop reason, and safety notes are distinct fields. |
| STATE-04 | 07-04, 07-05 | Existing persistent thread memory fields continue unchanged | SATISFIED | Cross-turn context and evidence memory tests pass; dormant investigation fields reset per turn. |
| TEST-01 | 07-03, 07-04, 07-05 | Unit tests cover registry validation, unsafe exclusion, schema failures, allowed invocation | SATISFIED | Focused suite passed with 69 tests; 07-05 added regressions for the four prior gaps. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None | - | - | - | Anti-pattern scan found only benign empty test fixtures and initialized containers; no stubs or placeholders blocking the goal. |

### Human Verification Required

None. Phase 7 is contract/state/test focused, and the relevant behaviors are covered programmatically.

### Gaps Summary

No remaining gaps. The four previous verification failures are closed by plan 07-05, and the original Phase 7 roadmap success criteria and requirement IDs are satisfied. Later phases still own routing, bounded investigator execution, recommendation/trace integration, and milestone evaluation, but those are explicit future-phase goals rather than Phase 7 gaps.

---

_Verified: 2026-06-04T10:51:18Z_
_Verifier: Claude (gsd-verifier)_
