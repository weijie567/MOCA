---
phase: 48-narrow-long-term-explicit-preference-memory
fixed_at: 2026-07-04T02:08:11Z
review_path: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 48: Code Review Fix Report

**Fixed at:** 2026-07-04T02:08:11Z
**Source review:** `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-01: Merchant-bound managers can review all tenant memory

**Status:** fixed: requires human verification
**Files modified:** `.planning/ARCHITECTURE-DEBT.md`, `src/api/routers/memory.py`, `tests/test_memory_review_api.py`
**Commit:** d339f70
**Applied fix:** Restricted memory review APIs to `admin` role only, moved review API happy-path tests to admin, and added denial coverage for support, same-merchant manager, and cross-merchant manager users carrying `approvals:review`.
**Verification:** Re-read modified sections; `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/api/routers/memory.py', 'tests/test_memory_review_api.py']]"` passed; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_memory_review_api.py -q` -> 8 passed, 1 warning.

### WR-01: State-origin case candidates can self-claim reviewed/admin provenance

**Status:** fixed: requires human verification
**Files modified:** `.planning/ARCHITECTURE-DEBT.md`, `src/memory/write_service.py`, `tests/memory/test_memory_write_service.py`, `tests/agent/test_memory_write_node.py`
**Commit:** 730e13e
**Applied fix:** Added a case-specific state-candidate gate that accepts only review-required case sources from graph state, rejects state-origin `human_reviewed` and `explicit_admin_preference` provenance, requires trusted merchant scope for merchant-scoped candidates, and requires matching refund-case source refs for case-scoped closed-case candidates.
**Verification:** Re-read modified sections; `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/write_service.py', 'tests/memory/test_memory_write_service.py', 'tests/agent/test_memory_write_node.py']]"` passed; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py -q` -> 48 passed, 1 warning; `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/write_service.py tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py` -> pass.

---

_Fixed: 2026-07-04T02:08:11Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
