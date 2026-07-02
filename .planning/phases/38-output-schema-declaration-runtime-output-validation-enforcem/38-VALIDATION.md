---
phase: 38
slug: output-schema-declaration-runtime-output-validation-enforcem
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 38 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` |
| **Full suite command** | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_verifier.py tests/conversation/test_service.py tests/test_execute_action.py tests/architecture/test_trusted_context_boundaries.py -q` |
| **Estimated runtime** | ~60 seconds for non-DB focused suite; DB-backed suite is environment-dependent and currently requires local PostgreSQL |

---

## Sampling Rate

- **After every task commit:** Run the narrow pytest command for the touched area plus `uv run ruff check` on changed Python files.
- **After every plan wave:** Run the quick command and the relevant high-blast consumer subset listed in the task map.
- **Before `$gsd-verify-work`:** Full relevant suite must be green when local PostgreSQL is available; if PostgreSQL remains unavailable, record the environment blocker in `.planning/LOCAL-VALIDATION-ISSUES.md` and report non-DB gates separately.
- **Max feedback latency:** 90 seconds for focused non-DB validation, excluding local PostgreSQL startup or DB fixture setup.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | TPH-01 | T-38-01 | `validate_json_value` accepts nullable/type-union schema forms needed by existing tool outputs and still rejects wrong scalar types. | unit | `uv run pytest tests/tools/test_catalog.py -q` | yes; update needed | pending |
| 38-01-02 | 01 | 1 | TPH-01 | T-38-02 | The eight scoped read/retrieval tools expose non-generic `output_schema` declarations; `create_coupon_grant_draft` remains out of scope unless a later phase expands action output hardening. | unit / structural | `uv run pytest tests/tools/test_catalog.py -q` | yes; update needed | pending |
| 38-02-01 | 02 | 2 | TPH-01 | T-38-03 | A conforming executor `ToolResultV2.data` payload passes through unchanged and keeps the `ToolResultV2` envelope field set unchanged. | runtime behavior | `uv run pytest tests/tools/test_tool_platform.py -q` | yes; update needed | pending |
| 38-02-02 | 02 | 2 | TPH-01 | T-38-04 | A schema-invalid executor `data` payload maps to `invalid_response` through the shared Phase 37 `_fail(...)` path and does not leak raw invalid data through the outcome/projection JSON. | runtime behavior / security | `uv run pytest tests/tools/test_tool_platform.py -q` | yes; update needed | pending |
| 38-03-01 | 03 | 3 | TPH-01 | T-38-05 | High-blast consumers continue to observe unchanged envelope/projection surfaces after output-schema enforcement. | regression | `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory tests/agent/rag_context/test_verifier.py::test_business_fact_claim_requires_current_tool_system_refs tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q` | yes | pending |
| 38-03-02 | 03 | 3 | TPH-01 | T-38-06 | `docs/contract-spec.md` and `src/tools/contracts.py` are not changed by Phase 38; spec reconciliation remains Phase 39. | structural / regression | `git diff -- docs/contract-spec.md src/tools/contracts.py` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/tools/test_catalog.py` - replace the Phase 37 generic output-schema assertion with real schema assertions for the eight scoped tools.
- [ ] `tests/tools/test_catalog.py` - add validation helper coverage for `"null"` and `["string", "null"]` / type-union schemas before strict output schemas rely on nullable fields.
- [ ] `tests/tools/test_catalog.py` - add current-payload acceptance/rejection fixtures for `get_order`, `get_refund_case`, `get_ticket`, `search_policy`, and `search_case_memory`, plus strict no-data schema coverage for `get_logistics`, `get_merchant_risk`, and `search_sop`.
- [ ] `tests/tools/test_tool_platform.py` - add fake-executor runtime tests for conforming output pass-through, invalid output mapping to `invalid_response`, raw invalid data redaction, and `ToolResultV2` envelope field-set preservation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local PostgreSQL availability for DB-backed consumer suite | TPH-01 | Current environment does not have `pg_isready` and `localhost:5432` is closed. | Start PostgreSQL with `moca:moca_dev@localhost:5432`, then rerun the full suite command above. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags.
- [ ] Feedback latency target documented.
- [ ] PostgreSQL blocker recorded separately if DB-backed suite cannot run locally.
- [ ] `nyquist_compliant: true` set in frontmatter after executor fills final task IDs and all available validation commands pass.

**Approval:** pending
