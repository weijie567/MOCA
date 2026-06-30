---
phase: 29-tool-platform-boundary
fixed_at: 2026-06-23T13:08:29Z
review_path: .planning/phases/29-tool-platform-boundary/29-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 29: Code Review Fix Report

**Fixed at:** 2026-06-23T13:08:29Z
**Source review:** .planning/phases/29-tool-platform-boundary/29-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### CR-01: Nested Case-Memory `raw_tool_payload` Can Still Reach Graph State

**Files modified:** `src/tools/projection.py`, `tests/tools/test_tool_platform.py`, `tests/agent/test_nodes/test_investigate.py`
**Commit:** c52833c
**Applied fix:** Added `raw_tool_payload` to the projector raw sentinel set and extended projector/investigate regression coverage so nested `raw_tool_payload` values inside `policy_refs` and `source_refs` are stripped from normalized case memory and graph state.

---

_Fixed: 2026-06-23T13:08:29Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
