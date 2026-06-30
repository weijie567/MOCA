---
phase: 36-merchant-scope-db-hardening-role-cleanup
fixed_at: "2026-06-30T14:41:40Z"
review_path: ".planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-REVIEW.md"
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 36: Code Review Fix Report

**Fixed at:** 2026-06-30T14:41:40Z
**Source review:** `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: Runtime business facts are not consumed by AgentRun scope classification

**Status:** fixed: requires human verification
**Files modified:** `src/agent/run_scope.py`, `tests/agent/test_phase36_run_scope.py`
**Commit:** 5093ed8
**Applied fix:** `classify_agent_run_scope()` now consumes the current runtime `business_context.facts` plus matching trusted `business_context.business_fact_refs` as merchant-scope proof. The classifier still does not treat `last_business_context_refs` refs alone as authoritative.

**Verification:**
- Tier 1 re-read: passed for modified sections in `src/agent/run_scope.py` and `tests/agent/test_phase36_run_scope.py`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(path).read_text()) for path in ('src/agent/run_scope.py', 'tests/agent/test_phase36_run_scope.py')]"`: passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/run_scope.py tests/agent/test_phase36_run_scope.py`: passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py::test_runtime_business_context_fact_and_ref_classifies_business_merchant tests/agent/test_phase36_run_scope.py::test_last_business_context_refs_without_current_fact_body_is_not_authoritative -q --tb=short`: passed, 2 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/test_agent_runs_api.py -q --tb=short`: failed because local PostgreSQL was unavailable on `127.0.0.1:5432` / `::1:5432`; current result was 30 passed, 44 setup errors, 1 warning, with errors originating from `tests/conftest.py::_ensure_test_database`.

---

_Fixed: 2026-06-30T14:41:40Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
