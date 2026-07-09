---
phase: 61-product-experience-fixes
plan: 01
subsystem: agent-response-ux
tags: [agent-graph, intent-recognition, final-response, clarification, ux-regression]

requires:
  - phase: 60
    provides: "v2.1 canonical Agent Graph, intent, RAG, ToolPlatform, memory, and approval boundaries"
provides:
  - "Deterministic direct-response baseline for standalone greetings and temporary aggregate-order unsupported requests"
  - "Safe clarification wording for missing business identifiers"
  - "No-false-evidence final-response guards for direct, clarification, business-fact-only, and no-ref recommendation paths"
affects: [61-02-metric-contract, agent-console, contextual-intent-resolve, final-response]

tech-stack:
  added: []
  patterns:
    - "Direct-response intents render through explicit deterministic final-response templates"
    - "Final response defaults claim policy evidence only when evidence citations exist"
    - "Clarification questions project missing-slot internals into user-safe accepted-input wording"

key-files:
  created:
    - ".planning/phases/61-product-experience-fixes/61-01-SUMMARY.md"
  modified:
    - "src/agent/nodes/contextual_intent_resolve.py"
    - "src/agent/nodes/clarification_gate.py"
    - "src/agent/nodes/final_response.py"
    - "tests/agent/test_nodes/test_contextual_intent_resolve.py"
    - "tests/agent/test_clarification_gate.py"
    - "tests/agent/test_nodes/test_final_response.py"

key-decisions:
  - "Preserved the temporary aggregate-order unsupported guard; Plan 61-02 owns metric reclassification."
  - "Generic unsupported responses name supported alternatives without asking for an irrelevant order identifier."
  - "Completed-response fallback wording now depends on actual evidence citations before using evidence-backed phrasing."

patterns-established:
  - "No-evidence response branches assert absence of false policy/RAG evidence phrases."
  - "TDD RED commits precede GREEN commits for each UX baseline task."

requirements-completed: []

duration: 8 min
completed: 2026-07-09
---

# Phase 61 Plan 01: Agent Response UX Baseline Summary

**Deterministic response UX baseline for small talk, unsupported requests, clarification prompts, and no-false-evidence final wording**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-09T03:24:14Z
- **Completed:** 2026-07-09T03:32:28Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Locked standalone greetings (`你好`, `您好`, `hi`, `谢谢`) to deterministic `small_talk` routing without LLM calls.
- Kept the temporary aggregate-order unsupported behavior in place for `当前有多少订单`, with Plan 61-02 still owning metric support.
- Improved missing-ID clarification copy so it explains the accepted order/refund/ticket identifiers without leaking routing internals.
- Added final-response guards preventing direct, clarification, business-fact-only, and no-ref recommendation branches from claiming RAG/policy evidence.

## Task Commits

1. **Task 1 RED:** `a3b357d` test(61-01): add direct response UX regression tests
2. **Task 1 GREEN:** `b1ffbe6` feat(61-01): implement direct response UX baseline
3. **Task 2 RED:** `e537a32` test(61-01): add clarification wording regression tests
4. **Task 2 GREEN:** `9286959` feat(61-01): improve clarification identifier wording
5. **Task 3 RED:** `02364c4` test(61-01): add no false evidence response guards
6. **Task 3 GREEN:** `16d3305` feat(61-01): guard final responses against false evidence claims

## Files Created/Modified

- `src/agent/nodes/contextual_intent_resolve.py` - Adds deterministic standalone small-talk and temporary aggregate-order unsupported guards.
- `src/agent/nodes/clarification_gate.py` - Adds user-safe missing-identifier wording with accepted input labels.
- `src/agent/nodes/final_response.py` - Adds direct-response templates and citation-aware completed-response defaults.
- `tests/agent/test_nodes/test_contextual_intent_resolve.py` - Covers greeting variants, no-LLM routing, business-keyword guard, and aggregate unsupported routing.
- `tests/agent/test_clarification_gate.py` - Covers missing-ID wording and no internal leakage.
- `tests/agent/test_nodes/test_final_response.py` - Covers direct/unsupported/clarification/business-fact/no-ref response wording and citation-backed branches.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_final_response.py -q --tb=short` -> `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_clarification_gate.py tests/agent/test_nodes/test_final_response.py -q --tb=short` -> `30 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_final_response.py -q --tb=short` -> `27 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_clarification_gate.py tests/agent/test_nodes/test_final_response.py -q --tb=short` -> `56 passed, 1 warning`

The warning is the existing `LangChainPendingDeprecationWarning` from `langgraph.checkpoint.serde.encrypted`; it is unrelated to this plan.

## Decisions Made

- None beyond the plan constraints. The aggregate-order unsupported response remains a temporary baseline for Plan 61-02 to replace.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Planned TDD RED gates failed for the intended reasons before each GREEN fix.
- `.planning/ARCHITECTURE-DEBT.md` and `.planning/LOCAL-VALIDATION-ISSUES.md` were already dirty before this executor, including a pre-existing Phase 61 direct-response ledger entry. They were not staged or modified by this plan executor to avoid committing unrelated dirty ledger content.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were intentionally not modified because this autopilot run assigns those shared artifacts to the orchestrator.

## Known Stubs

None. Stub scan only found ordinary empty-list/dict initializers and test assertions, not UI-visible placeholder data.

## Threat Flags

None. This plan added no new network endpoints, auth paths, file access patterns, schemas, or trust-boundary expansions.

## TDD Gate Compliance

Passed. Each task has a `test(61-01)` RED commit followed by a `feat(61-01)` GREEN commit; no refactor commits were needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 61-02. The temporary aggregate-order unsupported guard is preserved and test-locked so the next plan can intentionally replace it with the scoped metric intent/slot behavior.

---
*Phase: 61-product-experience-fixes*
*Completed: 2026-07-09*
