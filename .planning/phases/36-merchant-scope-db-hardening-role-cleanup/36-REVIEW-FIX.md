---
phase: 36-merchant-scope-db-hardening-role-cleanup
fixed_at: 2026-06-30T15:09:50Z
review_path: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 36: Code Review Fix Report

**Fixed at:** 2026-06-30T15:09:50Z
**Source review:** .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: Runtime business fact scope is not bound to the referenced resource id

**Files modified:** `src/agent/run_scope.py`, `tests/agent/test_phase36_run_scope.py`
**Commit:** `c376097`
**Commit status:** fixed: requires human verification
**Applied fix:** Runtime `business_context.facts` now resolve the fact resource id and only produce a `business_merchant` scope candidate when a trusted `BusinessFactRefV1` matches both `resource_type` and `resource_id`. Added regression coverage for same-type/different-id facts and refs, while preserving the valid matching-ref path and the non-authoritative `last_business_context_refs` behavior.

**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('src/agent/run_scope.py', 'tests/agent/test_phase36_run_scope.py')]"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/run_scope.py tests/agent/test_phase36_run_scope.py` - passed (`All checks passed!`).
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py::test_runtime_business_context_fact_and_ref_classifies_business_merchant tests/agent/test_phase36_run_scope.py::test_business_context_fact_requires_matching_business_fact_ref_resource_id tests/agent/test_phase36_run_scope.py::test_last_business_context_refs_without_current_fact_body_is_not_authoritative -q --tb=short` - passed (`3 passed, 1 warning`).

---

_Fixed: 2026-06-30T15:09:50Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
