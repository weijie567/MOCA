---
phase: 62-business-query-and-drilldown-foundation
fixed_at: 2026-07-09T16:41:15Z
review_path: .planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 62: Code Review Fix Report

**Fixed at:** 2026-07-09T16:41:15Z
**Source review:** .planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Denied business_query errors are hard-coded as order detail payloads

**Status:** fixed: requires human verification
**Files modified:** `src/business/service.py`, `tests/business/test_business_query_service.py`
**Commit:** 07419cb
**Applied fix:** Added a typed denied `BusinessQueryResultV1` path in `BusinessFactService.query_business()` that preserves the requested operation/resource while clearing denied merchant/resource identifiers, plus a service regression asserting denied list requests project to the expected no-leak API payload.

### WR-02: Projected label fields can still leak raw cursor/id strings into the API and Console

**Status:** fixed
**Files modified:** `.planning/ARCHITECTURE-DEBT.md`, `src/business/query/projection.py`, `tests/tools/test_projection.py`, `tests/test_agent_runs_api.py`, `frontend/src/components/details/BusinessQueryResultTab.tsx`, `frontend/src/components/details/BusinessQueryResultTab.test.tsx`
**Commit:** 161a01a
**Applied fix:** Split display-label sanitization from row-value sanitization, rejected raw/cursor/tenant/merchant/denied-id markers in projected labels, made `cursor_label` enum-style, added API/projection regressions, added a Console display-label guard and component regression, and recorded the verified tool-call architecture debt entry required by MOCA rules.

---

_Fixed: 2026-07-09T16:41:15Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
