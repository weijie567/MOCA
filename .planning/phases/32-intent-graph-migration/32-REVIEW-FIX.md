---
phase: 32
fixed_at: 2026-06-28T15:00:17Z
review_path: .planning/phases/32-intent-graph-migration/32-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 32: Code Review Fix Report

**Fixed at:** 2026-06-28T15:00:17Z
**Source review:** .planning/phases/32-intent-graph-migration/32-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Target Merchant Context Rejects Real Adapter Business Fact Refs

**Files modified:** `src/agent/merchant_context.py`, `tests/agent/test_trace.py`
**Commit:** 76dfe83
**Applied fix:** Added the approved demo adapter source systems to the trusted business fact ref allowlist and added a regression covering order, refund case, and ticket adapter-shaped refs.

### WR-02: Canonical Runtime Nodes Are Projected As Unknown Passthrough

**Files modified:** `src/agent/graph_vocabulary.py`, `tests/agent/test_graph_vocabulary.py`
**Commit:** 895ea4d
**Applied fix:** Added runtime identity vocabulary entries for canonical runnable nodes and added tests asserting contract projection reports them as `runtime`; Phase 33 deferred nodes remain non-runnable.

---

_Fixed: 2026-06-28T15:00:17Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 1_
