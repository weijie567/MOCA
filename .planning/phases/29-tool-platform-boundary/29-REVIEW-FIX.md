---
phase: 29-tool-platform-boundary
fixed_at: 2026-06-23T12:25:49Z
review_path: .planning/phases/29-tool-platform-boundary/29-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 29: Code Review Fix Report

**Fixed at:** 2026-06-23T12:25:49Z
**Source review:** .planning/phases/29-tool-platform-boundary/29-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-01: Nested Case-Memory Refs Can Leak Raw Payload Keys Into Normalized Graph State

**Files modified:** `src/tools/projection.py`, `tests/tools/test_tool_platform.py`, `tests/agent/test_nodes/test_investigate.py`
**Commit:** e8fc63a
**Applied fix:** Added nested case-memory ref sanitization for `policy_refs` and `source_refs`, stripping raw sentinel keys before normalized projection and investigate graph-state accumulation.

### WR-01: Runtime Auth Raises Instead Of Denying Legacy List Merchant Scope

**Files modified:** `src/tools/policy.py`, `tests/tools/test_tool_platform.py`
**Commit:** 2063214
**Applied fix:** Normalized legacy list-form merchant scopes before validation and denied closed on malformed scope validation errors, with runtime-auth coverage for allowed and denied list scopes.

---

_Fixed: 2026-06-23T12:25:49Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
