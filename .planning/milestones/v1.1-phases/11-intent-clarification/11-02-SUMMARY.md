---
phase: 11-intent-clarification
plan: 02
subsystem: agent
tags: [intent, routing, safety]
requires:
  - phase: 11-intent-clarification
    provides: IntentResultV3 adapter and REQUIRED_SLOT_POLICY
provides:
  - Deterministic pre-route detection
  - Intent precedence and confidence clarification helpers
affects: [phase-13-approval, eval-intent]
tech-stack:
  added: []
  patterns: [pure-policy-helper, fail-closed-routing]
key-files:
  created:
    - tests/agent/test_intent_routing.py
  modified:
    - src/agent/intent_policy.py
    - src/agent/nodes/classify_intent.py
    - tests/agent/test_nodes/test_classify_intent.py
key-decisions:
  - "Approval-looking ordinary chat maps to approval_chat_not_trusted clarification metadata, never approval_decision."
  - "Safety confidence checks combine requested operation and domain intent instead of relying only on a static high-risk set."
patterns-established:
  - "Pre-route decisions are deterministic Pydantic objects merged into routing_hints."
requirements-completed: [INTENT-01, CLARIFY-01]
duration: 0h 0m
completed: 2026-06-14
---

# Phase 11 Plan 02: Deterministic Intent Routing Summary

**Pure pre-router and precedence helpers for approval-looking text, write requests, and low-confidence safety routing**

## Performance

- **Duration:** Inline with Phase 11 execution batch
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added deterministic approval-chat, write/action, escalation, and multi-target pre-route detection.
- Added precedence and confidence helpers with safe clarification defaults.
- Wired pre-route metadata into classifier state before downstream graph routing.

## Task Commits

Inline execution was used in this runtime, so task-level changes are included in the final Phase 11 scoped commit rather than separate per-task commits.

## Deviations from Plan

None beyond inline execution/commit shape.

## Issues Encountered

Initial adapter tests showed secondary intents were over-promoting precedence. The helper was tightened so secondary intents do not override primary intent unless deterministic query evidence supports it.

## User Setup Required

None.

## Next Phase Readiness

Plan 11-03 can route classifier state using `routing_hints`, `intent_confidence`, and policy-owned required slots.

---
*Phase: 11-intent-clarification*
*Completed: 2026-06-14*
