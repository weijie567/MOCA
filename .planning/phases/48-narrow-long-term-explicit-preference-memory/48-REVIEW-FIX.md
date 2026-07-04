---
phase: 48-narrow-long-term-explicit-preference-memory
fixed_at: 2026-07-04T01:25:54Z
review_path: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md
iteration: 1
fix_scope: all
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 48: Code Review Fix Report

**Fixed at:** 2026-07-04T01:25:54Z
**Source review:** `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
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

### IN-01: Architecture overview still says Phase 48 explicit preference writes are not implemented

**Files modified:** `docs/architecture-overview.md`
**Commit:** d15e31a
**Applied fix:** Updated stale architecture overview statements so `long_term_memory_retrieve` is documented as the `reviewed_memory_context_retrieve` / `memory_context_load` compatibility wrapper, and Phase 48 narrow explicit preference write/retrieval is documented as implemented through deterministic explicit user preference capture, the admin save API, and human-review publication. Remaining limits now stay scoped to Redis hot cache and the broader profile/rule/run-summary memory-write pipeline.
**Verification:** Re-read the affected architecture overview sections and confirmed `rg 'empty adapter|long-term memory 仍是|long_term_memory_retrieve.*仍是|Phase 48 explicit preference memory 窄版写入尚未实现|Phase 48 前仍未落地|write path not implemented' docs/architecture-overview.md` returns no matches. Markdown syntax check not applicable.

---

_Fixed: 2026-07-04T01:25:54Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
