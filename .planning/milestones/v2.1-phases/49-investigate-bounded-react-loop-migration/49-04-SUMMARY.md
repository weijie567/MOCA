---
phase: 49-investigate-bounded-react-loop-migration
plan: "04"
subsystem: agent-graph
tags: [investigate, react, graph-regression, safety, closeout]
requires:
  - phase: 49-03
    provides: eight-tool surface, projection boundary, trace/replay metadata
provides:
  - graph-level ReAct scope regressions
  - intent/memory/risk/approval/action no-regression verification
  - GAD-01 IMPLEMENTED_WITH_LIMITATIONS closeout
  - architecture debt closure record
affects: [investigate, graph-react, planning-ledger]
tech-stack:
  added: []
  patterns:
    - "graph tests inject fake structured investigate planner rather than relying on legacy deterministic script path"
    - "Phase closeout records replay parent-operation limitation explicitly"
key-files:
  created:
    - .planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md
  modified:
    - src/agent/nodes/investigate.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/test_graph.py
    - .planning/DEFERRED-DECISIONS.md
    - .planning/ARCHITECTURE-DEBT.md
key-decisions:
  - "GAD-01 closes as IMPLEMENTED_WITH_LIMITATIONS because graph-level node operation emission was not added."
  - "Graph regression uses fake structured planner seam to test ReAct behavior without real LLM calls."
patterns-established:
  - "Policy-only graph path can use search_policy without forcing business context."
  - "Planner output cannot authorize routing, approval, or action behavior."
requirements-completed: [GAD-01-IMPL]
duration: 1 plan
completed: 2026-07-04
---

# Phase 49 Plan 04 Summary

**Graph-level regression proves ReAct is confined to investigate while downstream gates and memory/intent contracts stay unchanged.**

## Performance

- **Duration:** 1 closeout plan
- **Completed:** 2026-07-04
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added a graph-test fake structured planner seam so graph tests exercise planner-driven investigate without calling a real LLM.
- Added graph-level order→ticket→policy chain coverage using loop-local discovered slots.
- Added graph-level safety coverage showing planner attempts to select a write tool and inject route/approval/action fields cannot bypass downstream gates.
- Strengthened policy-only graph coverage to assert business context is not required.
- Ran intent, memory, approval/action, graph, and investigate regression commands using the approved `uv run pytest` entrypoint.
- Updated GAD-01 and architecture debt ledgers with an `IMPLEMENTED_WITH_LIMITATIONS` closeout.
- Post-closeout review fixed canonical preservation of planner `stop_reason="max_iterations_reached"`.

## Task Commits

1. **49-04 closeout changes** - `7827a3b` (`test: close phase 49 graph react migration`)
2. **Post-closeout review fix** - current review-fix commit (`fix: preserve investigate max-iteration stop reason`)

## Files Created/Modified

- `src/agent/nodes/investigate.py` - preserves the full validated stop reason enum, including `max_iterations_reached`.
- `tests/agent/test_nodes/test_investigate.py` - regression for planner stop reason preservation.
- `tests/agent/test_graph.py` - fake structured planner harness plus graph-level chain and safety regressions.
- `.planning/DEFERRED-DECISIONS.md` - GAD-01 status updated from pending implementation debt to implemented with replay parent limitation.
- `.planning/ARCHITECTURE-DEBT.md` - Phase 49 closeout entry for investigate deterministic planner debt.
- `.planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md` - closeout summary and verification record.

## Decisions Made

- Closed GAD-01 as `IMPLEMENTED_WITH_LIMITATIONS`, not fully `IMPLEMENTED`, because parent operation identity is emitted when supplied but graph-level node operation emission was not introduced.
- Kept `docs/contract-spec.md` unchanged; no spec/code blocker was found.

## Deviations from Plan

One post-closeout review fix was added: planner validation allowed `stop_reason="max_iterations_reached"`, but canonical termination mapping previously downgraded that explicit planner stop to `unrecoverable_error`. The fix stays inside investigate semantics and adds a focused regression test.

## Issues Encountered

No new local validation issue. A graph-test harness gap was fixed before it became a failing validation command: tests now inject a fake structured investigate planner instead of accidentally relying on real LLM planner calls.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/agent/test_graph.py` -> pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py -q` -> `81 passed, 25 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py -q` -> `47 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py -q` -> `41 passed, 4 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q` -> `31 passed, 1 warning`
- `rg -n 'active_slots\s*=|active_slots\]|active_slots\.' src/agent/nodes/investigate.py || true` -> no output
- `rg -n 'BusinessFactService|PolicyKnowledgeService|CaseMemoryService|RefundRepository|OrderRepository' src/agent/nodes/investigate.py || true` -> no output
- `rg -n 'create_coupon_grant_draft|issue_coupon|partial_refund|full_refund|close_ticket|escalate_ticket|manual_review' src/agent/nodes/investigate.py || true` -> no output
- `rg -n 'create_coupon_grant_draft|write tool|write-tool' tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py` -> rejection coverage present

## Next Phase Readiness

Phase 49 is ready for final review. Follow-up replay work can add graph-level node operation emission so every investigate tool operation always has a concrete parent operation without relying on configurable injection.

---
*Phase: 49-investigate-bounded-react-loop-migration*
*Completed: 2026-07-04*
