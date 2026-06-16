---
phase: 14-demo-action-executor-boundary
fixed_at: 2026-06-16T06:43:36Z
review_path: .planning/phases/14-demo-action-executor-boundary/14-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-06-16T06:43:36Z
**Source review:** `.planning/phases/14-demo-action-executor-boundary/14-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Trace Timeline Exposes Draft Idempotency Keys

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Commit:** 054ff21
**Applied fix:** Removed `idempotency_key` from action draft timeline detail and added a regression using a production-shaped key containing `RF-SECRET`.

### WR-02: `_safe_draft_outcome` Returns Arbitrary JSONB

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Commit:** 907091f
**Applied fix:** Projected draft outcomes through a `DraftOutcomeV1` allowlist/validation path with safe fallback defaults, plus a regression for unexpected JSONB keys.

### WR-03: Auto-Allowed Routing Depends On A Draft Path The Service Rejects

**Files modified:** `src/agent/graph.py`, `src/agent/nodes/action_draft.py`, `tests/test_graph_routing.py`, `tests/test_execute_action.py`, `tests/agent/test_graph.py`
**Commit:** 70727bf
**Applied fix:** Routed Phase 14 no-approval candidates to `final_response`, removed the risk-route edge to `action_draft`, and made direct `action_draft` calls fail closed without durable auto-allowed binding.

### WR-04: `create_or_get` Is Not Idempotent Under Concurrent Inserts

**Files modified:** `src/repositories/action_draft_repo.py`, `tests/actions/test_action_draft_v2.py`
**Commit:** 282ec94
**Applied fix:** Replaced select-then-insert with PostgreSQL `ON CONFLICT DO NOTHING` followed by a tenant/key re-select and binding check, plus a concurrent exact-key reuse regression.

---

_Fixed: 2026-06-16T06:43:36Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 1_
