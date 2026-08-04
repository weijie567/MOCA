---
phase: 38
slug: output-schema-declaration-runtime-output-validation-enforcem
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
updated: 2026-07-08
---

# Phase 38 - Nyquist Validation Refresh

This artifact replaces the original draft validation strategy with archive-gate validation evidence for TPH-01.

Phase 38 is Nyquist-compliant because the focused schema/runtime gates, high-blast consumer subset, Ruff check, protected-file checks, and DB-backed full relevant suite all have recorded passing evidence in `38-VERIFICATION.md` and `38-HUMAN-UAT.md`.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` |
| **Full relevant suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools/catalog.py src/tools/runtime.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py` |
| **DB-backed evidence** | `38-VERIFICATION.md` and `38-HUMAN-UAT.md` record the DB-backed suite passing with `184 passed, 1 warning`. |

## Sampling Rate

- **After every task commit:** Run focused catalog/runtime schema tests for touched areas.
- **After every plan wave:** Run focused Phase 38 schema/runtime gates plus the high-blast consumer subset.
- **Before archive evidence closure:** Confirm `38-VERIFICATION.md` and `38-HUMAN-UAT.md` preserve the DB-backed result and do not depend on invalid bare test command evidence.

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | TPH-01 | T-38-01 | `validate_json_value` accepts nullable/type-union schema forms needed by existing tool outputs and rejects wrong scalar types. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | passed |
| 38-01-02 | 01 | 1 | TPH-01 | T-38-02 | The eight scoped read/retrieval tools expose non-generic `output_schema` declarations; `create_coupon_grant_draft` stays outside TPH-01. | unit / structural | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | passed |
| 38-02-01 | 02 | 2 | TPH-01 | T-38-03 | Conforming executor `ToolResultV2.data` payloads pass through unchanged and keep the `ToolResultV2` envelope field set unchanged. | runtime behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | passed |
| 38-02-02 | 02 | 2 | TPH-01 | T-38-04 | Schema-invalid executor `data` maps to `invalid_response` through the shared Phase 37 `_fail(...)` path and does not leak raw invalid data. | runtime behavior / security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | passed |
| 38-03-01 | 03 | 3 | TPH-01 | T-38-05 | High-blast consumers continue to observe unchanged envelope/projection surfaces after output-schema enforcement. | regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/agent/rag_context/test_verifier.py::test_business_fact_claim_requires_current_tool_system_refs tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q` | yes | passed |
| 38-03-02 | 03 | 3 | TPH-01 | T-38-06 | `docs/contract-spec.md` and `src/tools/contracts.py` remain unchanged by Phase 38; spec reconciliation stays Phase 39-owned. | structural / regression | `git diff -- docs/contract-spec.md src/tools/contracts.py` | yes | passed |
| 38-03-03 | 03 | 3 | TPH-01 | T-38-07 | DB-backed business/conversation/agent consumer paths pass under local PostgreSQL. | DB-backed regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q` | yes | passed: `184 passed, 1 warning` |

## Closeout Evidence

- `38-VERIFICATION.md` records `12/12 must-haves verified`.
- `38-VERIFICATION.md` records catalog schema tests passing with `32 passed, 1 warning`.
- `38-VERIFICATION.md` records runtime output-schema focused tests passing with `5 passed, 1 warning`.
- `38-VERIFICATION.md` records manager invalid-response regressions passing with `2 passed, 1 warning`.
- `38-VERIFICATION.md` records the non-DB high-blast consumer subset passing with `33 passed, 1 warning`.
- `38-VERIFICATION.md` records Ruff passing for Phase 38 touched Python files.
- `38-VERIFICATION.md` records protected files unchanged.
- `38-HUMAN-UAT.md` records DB-backed full relevant suite completion: `184 passed, 1 warning`.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | TPH-01 | Phase 38 behavior is backend tool/runtime validation behavior with automated and DB-backed evidence. | N/A |

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity is documented from Phase 38 verification evidence.
- [x] Wave 0 covers nullable schema support, eight scoped tool schemas, runtime invalid-response enforcement, high-blast consumers, and protected contract files.
- [x] No watch-mode flags.
- [x] DB-backed evidence is recorded as passed.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** complete.
