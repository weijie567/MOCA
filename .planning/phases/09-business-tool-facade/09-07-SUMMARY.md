---
phase: 09-business-tool-facade
plan: 07
subsystem: agent-nodes
tags: [merchant-scope, knowledge-context, fail-closed, authorization, gap-closure]

requires:
  - phase: 09-05
    provides: Live read-switch with router-injected trusted merchant_scope config
provides:
  - Compatible structured merchant-scope projection for KnowledgeContext
  - Fail-closed behavior on malformed/missing merchant scope
  - Graph-path proof that structured scope reaches PolicyKnowledgeService
affects: [10-state-lifecycle-routing-migration, policy-retrieval, authorization]

tech-stack:
  added: []
  patterns:
    - Pure projection helper extracts merchant_ids from structured dict or validates legacy list
    - Fail-closed returns [] for any incompatible scope shape, never None

key-files:
  created: []
  modified:
    - src/agent/nodes/retrieve_policy_evidence.py
    - tests/agent/test_nodes/test_retrieve_policy_evidence.py
    - tests/agent/test_graph.py

key-decisions:
  - "_knowledge_merchant_scope() returns [] for invalid/missing scope rather than None, preventing unrestricted policy access"
  - "Spec Consistency Finding comment updated to reflect corrected projection instead of deferring to Phase 10"

patterns-established:
  - "Pure projection helper validates and copies structured merchant IDs before passing to KnowledgeContext"
  - "Graph tests inspect PolicyKnowledgeService.search call arguments to prove scope propagation"

requirements-completed: [TOOL-02]

duration: 5m
completed: 2026-06-12
---

# Phase 09 Plan 07: Structured Merchant Scope Projection Summary

**Structured merchant authorization scope now projects correctly into KnowledgeContext with fail-closed behavior**

## Performance

- **Duration:** ~5m
- **Started:** 2026-06-12T23:43:46Z
- **Completed:** 2026-06-12T23:48:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `_knowledge_merchant_scope()` pure helper that extracts `merchant_ids` from structured dict or validates legacy list inputs.
- All malformed, missing, non-string, or empty scope shapes now fail closed with `[]` instead of widening to unrestricted `None`.
- Updated the Spec Consistency Finding comment to reflect the corrected scope projection.
- Added 13 focused tests covering structured dict, legacy list, missing, and 9 malformed scope variants.
- Added graph-level test proving structured `merchant_ids` reaches `KnowledgeContext` unchanged through the full graph path.
- Confirmed `PolicyKnowledgeService` remains the retrieval service (Phase 8 ownership preserved).
- Full Phase 9 regression suite passes (99 tests).

## Task Commits

Each task was committed atomically:

1. **Task 1: Project structured merchant scope into KnowledgeContext** - `934e183` (feat) - RED: `5f2ad49` (test)
2. **Task 2: Prove structured scope reaches KnowledgeContext via graph** - `668b5fe` (test)

## Files Created/Modified

- `src/agent/nodes/retrieve_policy_evidence.py` - Added `_knowledge_merchant_scope()` helper; replaced broken `isinstance(merchant_scope, list) else None` with structured projection; updated Spec Consistency Finding comment.
- `tests/agent/test_nodes/test_retrieve_policy_evidence.py` - Added 13 tests: structured dict projection, legacy list passthrough, missing scope fail-closed, 9 malformed variants, multi-value IDs.
- `tests/agent/test_graph.py` - Added graph test asserting structured `merchant_ids` reaches `KnowledgeContext`; added test confirming `PolicyKnowledgeService` remains the retrieval seam.

## Decisions Made

- `_knowledge_merchant_scope()` returns `[]` for invalid/missing scope rather than `None`, preventing unrestricted policy access.
- The Spec Consistency Finding comment was updated to describe the corrected projection rather than deferring to Phase 10.
- Other structured dimensions (categories, risk_levels) are not misinterpreted as merchant IDs.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None. Empty merchant_scope lists are intentional fail-closed outcomes.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-09-07-01 (mitigated) | `src/agent/nodes/retrieve_policy_evidence.py` | Invalid/missing structured scope now maps to `[]` via `_knowledge_merchant_scope()`, never unrestricted `None`. |
| T-09-07-02 (mitigated) | `src/agent/nodes/retrieve_policy_evidence.py` | Only validated `merchant_ids` extracted; other dict dimensions ignored. |
| T-09-07-03 (mitigated) | `src/agent/nodes/retrieve_policy_evidence.py` | Scope read only from trusted configurable input, never derived from slots or user text. |

## Self-Check: PASSED

- Confirmed `_knowledge_merchant_scope` and `merchant_ids` present in `src/agent/nodes/retrieve_policy_evidence.py`.
- Confirmed `merchant_scope = None` returns zero matches (no unrestricted fallback).
- Confirmed fail-closed and structured scope assertions in test file.
- Confirmed task commits `5f2ad49`, `934e183`, `668b5fe` exist.
- Confirmed full Phase 9 regression suite passes (99 tests, 0 failures).
