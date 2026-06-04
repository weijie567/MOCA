# Phase 7: tool-registry-contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 07-tool-registry-contracts
**Areas discussed:** Module layout, Schema strictness, Invocation API, Test strategy

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Module layout | Decide whether registry/contracts live in a single module, split files, or a new package. | ✓ |
| Schema strictness | Decide strictness for risk/side-effect/stop_reason/error fields and Pydantic unknown fields. | ✓ |
| Invocation API | Decide the runtime invocation boundary, context shape, return semantics, and unsafe request errors. | ✓ |
| Test strategy | Decide test organization and regression coverage for Phase 7. | ✓ |

**User's choice:** Discuss all four areas.
**Notes:** Requirements were already locked by `07-SPEC.md`; discussion focused only on implementation decisions.

---

## Module layout

### Tool registry file split

| Option | Description | Selected |
|--------|-------------|----------|
| Split files | `registry.py` for registry construction/lookup, `contracts.py` for models/enums, `adapters.py` for wrappers. | ✓ |
| Single module | Put registry, contracts, and adapters in one `registry.py`. | |
| New package | Create `src/agent/tool_registry/` with submodules. | |

**User's choice:** Split files.
**Notes:** This keeps Phase 7 code near existing tools while keeping contracts/adapters/test layers clear.

### `InvestigationResult` location

| Option | Description | Selected |
|--------|-------------|----------|
| Agent schemas | Put `InvestigationResult` in `src/agent/schemas.py`. | ✓ |
| Registry contracts | Put `InvestigationResult` together with tool registry contracts. | |
| State module | Put investigation schema near `AgentState` in `src/agent/state.py`. | |

**User's choice:** Agent schemas.
**Notes:** Matches existing `RecommendationDraft`, `RiskAssessment`, and other structured agent outputs.

### Existing graph node usage

| Option | Description | Selected |
|--------|-------------|----------|
| Keep old calls | Existing nodes keep direct calls to old tool functions; registry is prepared for later phases. | ✓ |
| Dual path helper | Add optional helper but default old calls. | |
| Registry internal | Rewire existing nodes to registry in Phase 7. | |

**User's choice:** Keep old calls.
**Notes:** User added deferred follow-up: after Phase 9/10 investigator path is stable, migrate deterministic read/retrieval nodes to registry runtime while preserving current outputs, trace semantics, fallback behavior, tests, API compatibility, deterministic tool-selection logic, and non-LLM-driven behavior.

---

## Schema strictness

### Enum/literal strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict Literals | Use `Literal[...]` or enum-like fields for registry and investigation contract values. | ✓ |
| String fields | Use `str` plus runtime validator. | |
| Safety only | Only safety metadata is strict. | |

**User's choice:** Strict Literals.
**Notes:** Applies to `risk_level`, `side_effect`, `stop_reason`, result status, and error codes.

### Unknown field handling

| Option | Description | Selected |
|--------|-------------|----------|
| Forbid extra | Pydantic prompt-facing contracts use `extra="forbid"`. | ✓ |
| Filter output | Allow extra but filter at output. | |
| Result only | Forbid extra only for `ToolExecutionResult`. | |

**User's choice:** Forbid extra.
**Notes:** This supports the locked requirement that raw payloads not accidentally enter investigator-facing prompt results.

### `InvestigationResult` versioning

| Option | Description | Selected |
|--------|-------------|----------|
| Literal v1 | Use `schema_version: Literal["v1"] = "v1"`. | ✓ |
| Integer version | Use `version: int = 1`. | |
| No version | Defer version field. | |

**User's choice:** Literal v1.
**Notes:** Makes STATE-02 evolvability explicit and easy to test.

---

## Invocation API

### Main invocation interface

| Option | Description | Selected |
|--------|-------------|----------|
| Function + context | `execute_tool_for_investigator(name, input, context)`. | |
| Registry method | `ToolRegistry.invoke(name, input, context)`. | ✓ |
| Lookup only | `get_tool(name)` returns adapter; caller executes. | |

**User's choice:** Registry method.
**Notes:** User specified `context` must include `caller`. Registry applies policy by caller: `investigator` read/retrieval only; `load_business_context` deterministic read tools only; `retrieve_policy_evidence` retrieval only; future `execute_action` action tools only after approval preconditions. Phase 7 does not rewire graph, but API should support later deterministic node migration.

### Return value and raw payload handling

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt result only | Return prompt-facing `ToolExecutionResult`; no raw payload. | ✓ |
| Split raw/result | Return both internal raw result and prompt result. | |
| Dict + helper | Return existing dict plus sanitizer helper. | |

**User's choice:** Prompt result only.
**Notes:** Raw payloads may remain internal to adapter execution but must not be part of investigator-facing results.

### Invalid request semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Structured result | Invalid requests return structured `ToolExecutionResult`. | ✓ |
| Mixed errors | ValidationError for schema-invalid, result for unsafe/unknown. | |
| Exceptions | Raise for all invalid requests. | |

**User's choice:** Structured result.
**Notes:** User refined this: use structured `ToolExecutionResult` for all runtime invalid tool requests; do not raise graph-level exceptions for model/caller-requested invalid tools; distinguish `not_found`, `unsafe_tool_request`, `validation_error`, and `tool_error`.

---

## Test strategy

### New test organization

| Option | Description | Selected |
|--------|-------------|----------|
| Split tests | Add `test_registry.py`, `test_tool_contracts.py`, and `test_tool_adapters.py`. | ✓ |
| Single test file | Put all registry-related tests in one file. | |
| Colocated | Put adapter tests next to existing per-tool tests. | |

**User's choice:** Split tests.
**Notes:** Mirrors the selected implementation file split.

### Minimum regression coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted + graph/API | New registry/schema tests plus existing graph/API regression tests. | ✓ |
| New tests only | Only new registry/schema tests. | |
| Full suite | Run complete pytest suite. | |

**User's choice:** Targeted + graph/API.
**Notes:** Minimum verification should include new registry/schema/adapter tests plus `tests/agent/test_graph.py`, existing `tests/agent/test_tools/`, and relevant agent API regression such as `tests/test_agent_runs_api.py`.

### Unsafe tool non-execution proof

| Option | Description | Selected |
|--------|-------------|----------|
| Mock execution | Use mock/AsyncMock to prove underlying unsafe function is not called. | ✓ |
| Seeded DB | Use real seeded DB for allowed tool adapter tests. | |
| Metadata only | Only test metadata. | |

**User's choice:** Mock execution.
**Notes:** Disallowed tool requests must return structured rejection results and the underlying unsafe tool function must not be called. Allowed tools can reuse existing fake repo/session patterns.

---

## Claude's Discretion

- Exact class/helper names inside the locked file/module boundaries.
- Whether literal fields are implemented as type aliases or small enum-like literals, as long as Pydantic validation rejects invalid values.
- Exact summary dictionary shape inside `ToolExecutionResult`, as long as prompt-facing fields obey the locked sanitization contract.

## Deferred Ideas

- After Phase 9/10 investigator path is stable, migrate deterministic read/retrieval nodes (`load_business_context`, `retrieve_policy_evidence`) to registry runtime to unify tool invocation boundaries. This future work must preserve existing `AgentState` outputs, trace semantics, fallback behavior, tests, and API response compatibility. It must not change deterministic tool-selection logic or make these nodes LLM-driven.
