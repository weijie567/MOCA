---
phase: 38-output-schema-declaration-runtime-output-validation-enforcem
verified: 2026-07-02T02:08:26Z
status: human_needed
score: "12/12 must-haves verified"
overrides_applied: 0
human_verification:
  - test: "Start local PostgreSQL at moca:moca_dev@localhost:5432 and rerun the Phase 38 full relevant pytest suite."
    expected: "DB-backed consumer suite completes without fixture setup connection errors."
    why_human: "Current local environment has no PostgreSQL listener on localhost:5432; non-DB TPH-01 gates pass and this is environment debt, not a product-code failure."
---

# Phase 38: output_schema Declaration + Runtime Output-Validation Enforcement Verification Report

**Phase Goal:** Each of the eight registered tools declares a real `output_schema` for `ToolResultV2.data`, and `ToolRuntime` enforces it so schema-failing executor results become `invalid_response`, without changing the `ToolResultV2` envelope shape.
**Verified:** 2026-07-02T02:08:26Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Validator supports nullable/type-union schema forms needed by Phase 38 output schemas. | VERIFIED | `src/tools/validation.py:12` handles list-valued `type`, `src/tools/validation.py:25` handles `"null"`; direct `uv run python` check accepted null/string union and rejected `123`. |
| 2 | TPH-01 scope is exactly the eight read/retrieval tools, with the write action excluded. | VERIFIED | `tests/tools/test_catalog.py:187` asserts planner-visible read/retrieval names equal the TPH-01 set and excludes `create_coupon_grant_draft`; `uv run pytest tests/tools/test_catalog.py -q` passed. |
| 3 | Each of the eight TPH-01 tools declares a real non-generic `output_schema`. | VERIFIED | Catalog constants and declarations at `src/tools/catalog.py:43`, `src/tools/catalog.py:65`, `src/tools/catalog.py:93`, `src/tools/catalog.py:115`, `src/tools/catalog.py:127`, `src/tools/catalog.py:166`, and rows at `src/tools/catalog.py:203`, `218`, `233`, `248`, `263`, `284`, `299`, `318`; direct schema inventory showed all eight differ from `{"type":"object"}` and have `additionalProperties: False`. |
| 4 | `create_coupon_grant_draft` remains outside TPH-01 output hardening. | VERIFIED | Action row keeps `output_schema=_GENERIC_OBJECT_SCHEMA`, `kind="write"`, `exposure="node_only"` at `src/tools/catalog.py:325`; test at `tests/tools/test_catalog.py:162`. |
| 5 | Current producer success payloads conform to the declared schemas. | VERIFIED | Business adapters project strict Pydantic shapes at `src/business/adapters.py:43`, `56`, `66` and emit `projected.model_dump(mode="json")` at `src/business/adapters.py:217`; knowledge emits retrieval fields at `src/tools/executors/knowledge.py:73`; memory emits `items` from `CaseMemorySearchItem` at `src/tools/executors/memory.py:97` and `src/memory/schemas.py:391`. Catalog payload tests at `tests/tools/test_catalog.py:266` passed. |
| 6 | Strict no-data schemas reject accidental non-empty payloads for unavailable scoped tools. | VERIFIED | `_NO_DATA_OUTPUT_SCHEMA` is strict at `src/tools/catalog.py:43`; assigned to `get_logistics`, `get_merchant_risk`, `search_sop` at `src/tools/catalog.py:248`, `263`, `299`; rejection tests at `tests/tools/test_catalog.py:337` and runtime `search_sop` test at `tests/tools/test_tool_platform.py:327` passed. |
| 7 | Runtime validates executor output against `descriptor.output_schema`. | VERIFIED | `ToolRuntime.invoke` computes `should_validate_output` for `success`, `partial_success`, or any non-empty data and calls `validate_json_value(tool_result.data, descriptor.output_schema)` at `src/tools/runtime.py:176`. |
| 8 | Schema-invalid executor output maps to `invalid_response` instead of passing through. | VERIFIED | Runtime catches schema errors and calls `_fail(... status="invalid_response", code="INVALID_EXECUTOR_RESPONSE", source="adapter")` at `src/tools/runtime.py:181`; platform and manager tests passed. |
| 9 | The prior `success + data=None` bypass is closed. | VERIFIED | `should_validate_output` includes `tool_result.status in {"success", "partial_success"}` at `src/tools/runtime.py:178`; regression test `test_output_schema_success_with_missing_data_returns_invalid_response` at `tests/tools/test_tool_platform.py:278` passed; fix commit `16a5d8f` exists. |
| 10 | Conforming executor output passes through unchanged. | VERIFIED | `test_output_schema_success_passes_tool_result_unchanged` asserts status, data, summary, and projection at `tests/tools/test_tool_platform.py:256`; focused runtime suite passed. |
| 11 | Invalid raw payload does not leak into outcome/projection JSON. | VERIFIED | `tests/tools/test_tool_platform.py:300` asserts sentinel absence from outcome and projection JSON; `tests/agent/test_tools/test_unified_tool_manager.py:519` covers manager-level redaction; both focused tests passed. |
| 12 | `ToolResultV2` envelope shape and high-blast consumers remain stable. | VERIFIED | Exact field-set guard at `tests/tools/test_tool_platform.py:365`; `git diff -- docs/contract-spec.md src/tools/contracts.py` returned no diff; non-DB high-blast subset passed `33 passed, 1 warning`. DB-backed full suite remains environment-gated by local PostgreSQL unavailability already recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`. |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/tools/validation.py` | Nullable/type-union validator support | VERIFIED | Exists, substantive, imported by runtime, tested by catalog helper tests. |
| `src/tools/catalog.py` | Per-tool declaration-owned output schemas | VERIFIED | `_ToolDeclaration.output_schema` and descriptor pass-through at `src/tools/catalog.py:176` and `369`; all eight scoped rows use real schemas. |
| `src/tools/runtime.py` | Runtime output-validation gate and shared failure routing | VERIFIED | Validates output at `src/tools/runtime.py:176`; failure branch calls `_fail` at `src/tools/runtime.py:181`; `_fail` constructs safe result/projection/event at `src/tools/runtime.py:266`. |
| `src/tools/contracts.py` | Protected envelope contract unchanged | VERIFIED | No diff; `ToolResultV2` field-set guard passed. |
| `tests/tools/test_catalog.py` | Schema declaration, scope, acceptance, rejection tests | VERIFIED | `uv run pytest tests/tools/test_catalog.py -q` -> `32 passed, 1 warning`. |
| `tests/tools/test_tool_platform.py` | Runtime output-validation, redaction, envelope tests | VERIFIED | Focused runtime output-schema nodes -> `5 passed, 1 warning`. |
| `tests/agent/test_tools/test_unified_tool_manager.py` | Manager-level invalid-response regression | VERIFIED | Focused manager output-schema nodes -> `2 passed, 1 warning`; high-blast subset -> `33 passed, 1 warning`. |
| `.planning/LOCAL-VALIDATION-ISSUES.md` | PostgreSQL environment blocker record | VERIFIED | Phase 38 PostgreSQL blocker entries found; current file has pre-existing unstaged local logs, not a product-code gap. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/tools/catalog.py::_TOOL_DECLARATIONS` | `ToolDescriptor.output_schema` | `_descriptor(declaration)` | WIRED | `output_schema=declaration.output_schema` at `src/tools/catalog.py:375`. |
| `src/tools/runtime.py` | `src/tools/validation.py` | `validate_json_value(tool_result.data, descriptor.output_schema)` | WIRED | Import at `src/tools/runtime.py:19`; output call at `src/tools/runtime.py:180`. |
| `src/tools/runtime.py` | `ToolRuntime._fail` | invalid output branch | WIRED | `invalid_response` branch at `src/tools/runtime.py:181` routes through `_fail`; `_fail` starts at `src/tools/runtime.py:266`. |
| `tests/tools/test_catalog.py` | `ToolCatalog().descriptors()` | descriptor helper and schema assertions | WIRED | Helper uses `ToolCatalog().descriptors()` at `tests/tools/test_catalog.py:72`; scoped schema tests start at `tests/tools/test_catalog.py:115`. |
| `tests/tools/test_tool_platform.py` | `ToolResultV2` | field-set guard | WIRED | Exact `ToolResultV2.model_fields` assertion at `tests/tools/test_tool_platform.py:365`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ToolDescriptor.output_schema` | `descriptor.output_schema` | `_ToolDeclaration.output_schema` constants | Yes | FLOWING - catalog rows pass schemas through to descriptors. |
| `ToolRuntime.invoke` | `tool_result.data` | Executor result returned from business/knowledge/memory/action executors | Yes | FLOWING - valid output passes projection; invalid output fails before projection. |
| Business read tools | `projected.model_dump(mode="json")` | Strict Pydantic projections from raw business data | Yes | FLOWING - adapter shapes match catalog schema fields. |
| `search_policy` | retrieval status/score/threshold/summary | `PolicyKnowledgeService.search(...)` result | Yes | FLOWING - executor emits declared fields. |
| `search_case_memory` | `items` array | `CaseMemoryService.retrieve_reviewed(...)` result | Yes | FLOWING - `CaseMemorySearchItem` fields match schema. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Catalog schemas and validator behavior | `uv run pytest tests/tools/test_catalog.py -q` | `32 passed, 1 warning` | PASS |
| Runtime output schema pass/fail/redaction/envelope nodes | `uv run pytest tests/tools/test_tool_platform.py::test_output_schema_success_passes_tool_result_unchanged tests/tools/test_tool_platform.py::test_output_schema_success_with_missing_data_returns_invalid_response tests/tools/test_tool_platform.py::test_output_schema_failure_returns_invalid_response_without_raw_data tests/tools/test_tool_platform.py::test_no_data_output_schema_rejects_accidental_unavailable_tool_payload tests/tools/test_tool_platform.py::test_tool_result_v2_envelope_fields_are_unchanged -q` | `5 passed, 1 warning` | PASS |
| Manager invalid-response regressions | `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py::test_output_schema_failure_returns_invalid_response_without_raw_data tests/agent/test_tools/test_unified_tool_manager.py::test_malformed_executor_return_becomes_invalid_response -q` | `2 passed, 1 warning` | PASS |
| Non-DB high-blast consumer subset | `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/agent/rag_context/test_verifier.py::test_business_fact_claim_requires_current_tool_system_refs tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q` | `33 passed, 1 warning` | PASS |
| Ruff on Phase 38 touched Python files | `uv run ruff check src/tools/catalog.py src/tools/runtime.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py` | `All checks passed!` | PASS |
| Protected files unchanged | `git diff -- docs/contract-spec.md src/tools/contracts.py` | no output | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TPH-01 | 38-01, 38-02, 38-03 | Eight registered tools declare real `output_schema`; runtime maps schema-failing `data` to `invalid_response` instead of passing through no-op object schema. | SATISFIED | Roadmap SC 1-4 verified above. All three plans declare TPH-01. Non-DB TPH-01 gates pass; DB-backed suite pending local PostgreSQL is environment debt already logged. |

No additional Phase 38 requirement IDs were found in `.planning/REQUIREMENTS.md`; TPH-02 is explicitly Phase 39.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| n/a | n/a | No TODO/FIXME/placeholder/console-only implementation found in Phase 38 code files. Empty lists and `{}` matches are test fixtures or deliberate strict no-data schemas. | INFO | No blocker. |

### Human Verification Required

### 1. DB-Backed Full Relevant Suite

**Test:** Start PostgreSQL locally so `moca:moca_dev@localhost:5432/moca_test` is reachable, then rerun the Phase 38 full relevant pytest suite from `38-VALIDATION.md`.
**Expected:** DB-backed consumer tests complete without `tests/conftest.py::test_engine` connection setup errors.
**Why human:** The current local machine has no PostgreSQL service listening on `localhost:5432`; prior failures are environment setup errors, not evidence of TPH-01 product-code failure.

### Gaps Summary

No product-code gaps found. All Phase 38 TPH-01 must-haves are verified against the actual codebase. Overall status is `human_needed` only because the DB-backed full relevant suite still needs a local PostgreSQL service to close the environment gate.

---

_Verified: 2026-07-02T02:08:26Z_
_Verifier: Codex (gsd-verifier)_
