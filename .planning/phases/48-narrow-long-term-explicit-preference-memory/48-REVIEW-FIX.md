---
phase: 48-narrow-long-term-explicit-preference-memory
fixed_at: 2026-07-04T01:17:43Z
review_path: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 48: Code Review Fix Report

**Fixed at:** 2026-07-04T01:17:43Z
**Source review:** `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-01: State-provided memory candidates can bypass tenant, run, and publish-source boundaries

**Files modified:** `src/memory/write_service.py`, `tests/memory/test_memory_write_service.py`, `.planning/ARCHITECTURE-DEBT.md`
**Commit:** b049b4e
**Applied fix:** Bound state-origin candidates to the current tenant/run identity, required state-origin long-term candidates to be review-required merchant-scope candidates covered by trusted merchant context, and added regression coverage for cross-tenant, wrong-run, tenant-scope, published-source, and untrusted merchant candidates.
**Verification:** `uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/write_service.py', 'tests/memory/test_memory_write_service.py']]"`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py -q` -> 25 passed, 1 warning.

### WR-01: Hard-rule text can be published after review as long-term preference memory

**Files modified:** `src/memory/long_term.py`, `tests/memory/test_long_term_memory_service.py`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`
**Commit:** 6b37e95
**Applied fix:** Reused soft preference validation at long-term write/supersede boundaries and before review approval, emitting `hard_rule_not_preference` skips for hard-rule content and preserving legacy pending rows as unapproved/unretrievable.
**Verification:** `uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/long_term.py', 'tests/memory/test_long_term_memory_service.py']]"`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_service.py -q` -> 29 passed, 1 warning.

---

_Fixed: 2026-07-04T01:17:43Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
