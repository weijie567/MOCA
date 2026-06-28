---
phase: 33-rag-context-build-and-claim-verification
plan: 33-06
subsystem: agent
tags: [rag, claim-verification, risk-gate, action-boundary]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: runnable claim_verify node writing claim_verification_bundle, blocked_claims, and safe_support_refs
provides:
  - bundle-aware risk/action guards for claim verification blockers
  - action snapshot evidence sourcing from safe support refs and verified evidence maps only
  - candidate-only evidence negative coverage for action snapshot binding
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - risk/action gates treat claim_verification_bundle, blocked_claims, and safe_support_refs as authoritative
    - action snapshot evidence resolves through verified safe support refs, not retrieval candidates

key-files:
  created:
    - .planning/phases/33-rag-context-build-and-claim-verification/33-06-SUMMARY.md
  modified:
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/action_draft.py
    - src/agent/graph.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/agent/test_nodes/test_assess_risk_and_approval.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Risk/action gates fail closed when proposed actions lack claim_verification_bundle authority."
  - "Safety snapshot evidence is sourced from safe_support_refs mapped through verified evidence maps, never candidate-only retrieved evidence."
  - "route_after_risk includes the same claim-bundle safety guard as defense-in-depth before approval routing."

patterns-established:
  - "Downstream action-capable nodes read ClaimVerificationBundleV1 semantics through local compatibility adapters."
  - "Candidate retrieval refs remain retrieval-only unless claim verification emits them as safe support refs."

requirements-completed: [APF-13, APF-14]

duration: 10min
completed: 2026-06-29
---

# Phase 33 Plan 06: Risk And Action Gate Enforcement Summary

**Risk and action draft paths now fail closed on unsupported claim bundles and bind action evidence only from verified safe support refs.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-28T20:07:18Z
- **Completed:** 2026-06-28T20:17:25Z
- **Tasks:** 1 TDD task
- **Files modified:** 6

## Accomplishments

- Added bundle-based blockers in `assess_risk_and_approval` for non-`continue` routes, blocked claims, malformed bundles, missing bundles for proposed actions, and action claim results with `allows_action_recommendation=False`.
- Changed action snapshot evidence collection to use `claim_verification_bundle.safe_support_refs`, `state["safe_support_refs"]`, and verified package/evidence-map lookups instead of retrieval candidates or unverified draft refs.
- Added the same claim bundle guard to `action_draft` and `route_after_risk`, so approval/action routing also fails closed if stale or malformed action-capable state appears.
- Added focused negative tests for bundle blockers, missing bundles, action-claim disallow flags, candidate-only retrieved evidence, and action draft claim-bundle denial.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 33-06-01 RED: action boundary guard tests** - `6386457` (test)
2. **Task 33-06-01 RED: missing bundle action guard** - `7c15ac2` (test)
3. **Task 33-06-01 GREEN: claim bundle action gates** - `9d05dc2` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/nodes/assess_risk_and_approval.py` - Added claim bundle fail-closed guards and safe-support-only evidence resolution for proposed action snapshots.
- `src/agent/nodes/action_draft.py` - Added claim bundle blockers before approval/tool draft checks.
- `src/agent/graph.py` - Added defense-in-depth claim bundle validation before routing from risk to approval.
- `tests/agent/test_phase22_action_boundary.py` - Added TDD RED coverage for blocked bundles, action disallow flags, candidate-only refs, and action draft denial.
- `tests/agent/test_nodes/test_assess_risk_and_approval.py` - Added missing-bundle negative coverage and updated allowed-action unit tests to provide verified claim bundles.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Recorded handled RED failures and GREEN verification in Chinese per project rules.

## Decisions Made

- Missing claim bundles now block action-capable state when a recommendation is actionable or a proposed action already exists.
- Candidate-only `retrieved_evidence.evidence_refs` no longer participates in risk prompt policy refs or action snapshot evidence binding.
- Graph routing was hardened in addition to node-level guards because approval routing is an action-capable boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Hardened graph risk routing**
- **Found during:** Task 33-06-01 GREEN implementation
- **Issue:** The plan named `assess_risk_and_approval.py` and `action_draft.py`, but `route_after_risk` in `src/agent/graph.py` could still route a pre-populated unsafe state toward approval if only legacy verifier state was checked.
- **Fix:** Added a claim-bundle guard to `route_after_risk` so non-continue bundles, blocked claims, missing bundles, or action claim disallow flags fail closed to `final_response`.
- **Files modified:** `src/agent/graph.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` passed.
- **Committed in:** `9d05dc2`

**2. [Rule 2 - Project Validation Record] Recorded handled RED failures**
- **Found during:** Task 33-06-01 RED/GREEN verification
- **Issue:** MOCA project rules require local validation failures to be recorded; TDD RED failures and the handled candidate-ref negative failure occurred during implementation.
- **Fix:** Appended a Chinese record to `.planning/LOCAL-VALIDATION-ISSUES.md` with symptoms, reproduction commands, evidence, root cause, fix, and next investigation entry points.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Final pytest, Ruff, acceptance greps, and `git diff --check` passed.
- **Committed in:** `9d05dc2`

---

**Total deviations:** 2 auto-fixed (2 missing critical / project-rule correctness).
**Impact on plan:** Both changes enforce the stated action-boundary safety contract. No user-facing scope or new architecture was added.

## Issues Encountered

- RED failed as expected because risk/action paths ignored claim bundle fields and still used candidate refs.
- Final grep for `retrieved_evidence|policy_evidence` still reports `policy_evidence_refs` in `action_draft.py`; this is a `ToolResultV2` error wrapper field and not an action snapshot evidence fallback.
- Existing LangGraph warnings about checkpointer serializer deprecation and `extract_slots` config typing appeared during focused tests; they are pre-existing and not blocking.
- Metadata update hit the known Phase 33 `roadmap.update-plan-progress` checkbox mismatch; ROADMAP/STATE were manually corrected and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub scan hits were intentional empty lists/`None` values in tests, helper defaults, and existing node locals; no UI-rendered or behavior-blocking stubs were introduced.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema boundary was introduced; the only additional trust-boundary logic is fail-closed routing.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` -> 37 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` -> 25 passed, 22 warnings
- `uv run ruff check src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py src/agent/graph.py tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_action_draft_boundaries.py` -> passed
- `rg -n "claim_verification_bundle|blocked_claims|safe_support_refs|allows_action_recommendation" src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py` -> found bundle guards and tests
- `rg -n "retrieved_evidence|policy_evidence" src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py` -> only `policy_evidence_refs` compatibility field in `action_draft.py`; no candidate-ref snapshot fallback remains
- `git diff --check` -> passed

## TDD Gate Compliance

- RED commit present for Task 33-06-01: `6386457`
- Additional RED commit present for missing-bundle must-have: `7c15ac2`
- GREEN commit present after RED commits: `9d05dc2`
- Refactor commit not needed.

## Next Phase Readiness

Ready for Plan 33-07. Downstream risk/approval/action paths now consume claim verification bundle authority and no longer treat retrieval candidates as action evidence.

## Self-Check: PASSED

- Verified summary file exists on disk: `.planning/phases/33-rag-context-build-and-claim-verification/33-06-SUMMARY.md`.
- Verified task commits are reachable: `6386457`, `7c15ac2`, `9d05dc2`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-29*
