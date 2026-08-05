---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
fixed_at: 2026-07-03T15:22:50Z
review_path: .planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 47: Code Review Fix Report

**Fixed at:** 2026-07-03T15:22:50Z
**Source review:** `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Generic closed-case summaries collapse distinct merchant precedents

**Commit status:** fixed: requires human verification
**Files modified:** `src/memory/case_memory.py`, `tests/memory/test_case_precedent_generation.py`, `.planning/ARCHITECTURE-DEBT.md`
**Commit:** `8d874c4`
**Applied fix:** `closed_case_cwc_candidate` content identity now hashes the full projected precedent text (`summary`, `excerpt`, `applicability`, `outcome`, `caveats`) while preserving summary-only identity for other case-memory sources. Added same-merchant distinct closed-case regression coverage and kept identical projected content dedupe coverage.

### WR-02: Reviewed-memory node filters generated precedents with the wrong case type

**Commit status:** fixed: requires human verification
**Files modified:** `src/agent/nodes/reviewed_memory_context_retrieve.py`, `tests/agent/test_reviewed_memory_context_retrieve.py`, `.planning/ARCHITECTURE-DEBT.md`
**Commit:** `5b103cf`
**Applied fix:** `reviewed_memory_context_retrieve` now derives `case_type` from `active_slots/extracted_slots.issue_type` and no longer uses `primary_intent/current_intent` as the case-memory metadata filter. Added real node/service/repository integration coverage for an approved `closed_case_cwc_candidate` with `case_type="refund_dispute"` and `primary_intent="refund_troubleshooting"`, with no case id in state.

## Skipped Issues

None.

## Verification

**Per-fix syntax checks:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/case_memory.py','tests/memory/test_case_precedent_generation.py']]"` → passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/agent/nodes/reviewed_memory_context_retrieve.py','tests/agent/test_reviewed_memory_context_retrieve.py']]"` → passed

**Focused tests:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -q` → `20 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py -q` → `15 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/agent/test_reviewed_memory_context_retrieve.py -q` → `35 passed, 1 warning`

---

_Fixed: 2026-07-03T15:22:50Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
