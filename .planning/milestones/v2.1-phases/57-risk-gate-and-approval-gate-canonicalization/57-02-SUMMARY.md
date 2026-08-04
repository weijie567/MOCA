---
phase: 57-risk-gate-and-approval-gate-canonicalization
plan: 02
subsystem: agent-graph-risk-approval
tags: [langgraph, risk-gate, approval, rag-claim-routing, canonical-agent-graph]

requires:
  - phase: 57-01
    provides: canonical risk_gate callable and Phase 58-scoped legacy wrapper
  - phase: 56-03
    provides: claim verification fail-closed action-route decision table
provides:
  - active StateGraph registration and route maps targeting risk_gate
  - canonical claim_verify router return value for current risk routing
  - approval edit resume payloads that rerisk through risk_gate
  - preserved RAG/claim fail-closed routing tests under canonical route literals
affects: [phase-57, phase-57-03, phase-57-04, phase-58, canonical-agent-graph, approval-boundary]

tech-stack:
  added: []
  patterns:
    - active graph node cutover with AST baseline guard
    - approval edit rerisk via canonical resume_route
    - approval-service-owned action claim allowance for approved resume reconciliation

key-files:
  created:
    - .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-02-SUMMARY.md
  modified:
    - src/agent/graph.py
    - src/agent/routing.py
    - src/approvals/service.py
    - src/api/routers/approvals.py
    - tests/architecture/graph_baseline.py
    - tests/architecture/test_canonical_graph_baseline.py
    - tests/architecture/test_phase33_rag_claim_boundaries.py
    - tests/agent/test_graph.py
    - tests/test_graph_routing.py
    - tests/agent/rag_context/test_routing.py
    - tests/test_approval_api.py
    - tests/approvals/test_needs_info_resume.py
    - tests/approvals/test_service_transitions.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Cut active graph registration and current route values to risk_gate without adding a risk_gate self-loop."
  - "Kept historical assess_risk_and_approval direct-call compatibility tests outside current graph routing."
  - "Preserved action_draft's allowed action-claim gate by making approved resume reconciliation emit an explicit approval-service-owned action claim."

patterns-established:
  - "Current graph route values equal active node keys; legacy risk names are not active path-map destinations."
  - "Approved resume reconciliation represents prior approval as explicit action-claim allowance instead of bypassing action_draft guards."

requirements-completed: [CAGM-08]

duration: 22min
completed: 2026-07-07
---

# Phase 57 Plan 02: Active Risk Gate Route Cutover Summary

**Active graph, claim routing, and approval edit rerisk paths now use canonical `risk_gate` while preserving claim/action fail-closed behavior**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-07T13:33:38Z
- **Completed:** 2026-07-07T13:55:48Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments

- Replaced active `assess_risk_and_approval` graph registration and route-map destinations with `risk_gate`.
- Updated `route_after_claim_verify` and `_CLAIM_VERIFY_ROUTES` to current route values `{risk_gate, final_response}`.
- Changed new approval edit decisions and API resume validation to emit/accept `resume_route="risk_gate"`.
- Preserved Phase 56 claim/RAG fail-closed routing and action-draft final write guards under the canonical route literal.

## Task Commits

1. **Task 1 RED: Add failing risk_gate active route tests** - `d1a23a2` (test)
2. **Task 1 GREEN: Cut active risk routes to risk_gate** - `08a06e4` (feat)
3. **Task 2: Preserve claim fail-closed risk routing** - `68f7d17` (test)

## Files Created/Modified

- `src/agent/graph.py` - Active graph imports/registers `risk_gate`, maps `claim_verify` and approval edit rerisk to `risk_gate`, and keeps no risk self-loop.
- `src/agent/routing.py` - Claim verification allowlist and route returns use `risk_gate`.
- `src/approvals/service.py` - New edit decisions persist and return canonical `resume_route="risk_gate"`.
- `src/api/routers/approvals.py` - Edit retry/resume validation accepts canonical route; approved resume reconciliation emits explicit action-claim allowance.
- `tests/...` - Architecture, graph, approval, and RAG/claim tests updated to reject active legacy risk routes and preserve fail-closed cases.
- `.planning/LOCAL-VALIDATION-ISSUES.md` / `.planning/ARCHITECTURE-DEBT.md` - Records for handled validation failures and the approved-resume claim boundary fix.

## Decisions Made

- Did not add `risk_gate -> risk_gate`; `route_after_risk` still returns only `approval_gate`, `action_draft`, or `final_response`.
- Did not delete legacy direct-call compatibility surfaces; Phase 58 still owns final cleanup.
- Fixed approved resume reconciliation by adding an explicit allowed action claim, not by weakening `action_draft`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened Phase 33 writer-ownership static guard**
- **Found during:** Task 1 GREEN verification.
- **Issue:** `test_phase33_rag_claim_boundaries.py` scanned every dict literal in `generate_recommendation.py`, so read-state dicts caused a false writer-ownership failure.
- **Fix:** Limited `_literal_dict_keys(...)` to returned dict literals while preserving repository/source-side-effect assertions.
- **Files modified:** `tests/architecture/test_phase33_rag_claim_boundaries.py`
- **Verification:** Task 1 full command passed with `231 passed, 1 skipped, 28 warnings`.
- **Committed in:** `08a06e4`

**2. [Rule 2 - Missing Critical] Added approved-resume action-claim allowance**
- **Found during:** Task 1 GREEN verification.
- **Issue:** `_approved_resume_claim_bundle()` produced an empty claim result set, so `action_draft()` correctly failed closed after approval resume.
- **Fix:** Added an approval-service-owned supported `action_recommendation` claim result with `allows_action_recommendation=True`.
- **Files modified:** `src/api/routers/approvals.py`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused approval tests passed with `2 passed`; full plan command passed with `243 passed, 1 skipped, 28 warnings`.
- **Committed in:** `08a06e4`

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical).
**Impact on plan:** Both fixes were required to keep the mandatory verification suite passing without weakening Phase 56 action/claim safety gates.

## Issues Encountered

- Expected Task 1 RED failure: active graph, router values, and approval edit resume still used `assess_risk_and_approval` before GREEN.
- Task 2 did not get a separate failing RED state because Task 1 GREEN had already implemented the canonical route literal; it was completed as a focused regression-hardening commit.

## TDD Gate Compliance

- Task 1 produced RED (`d1a23a2`) and GREEN (`08a06e4`) commits.
- Task 2 produced a test-only preservation commit (`68f7d17`); no additional GREEN source change was needed because Task 1 had already satisfied the route behavior.

## Known Stubs

None. Stub scan hits were existing test fixtures, explicit `None` values, empty fixture collections, or historical planning-ledger text; no runtime placeholder data source was introduced.

## Threat Flags

None. This plan changed the planned router return value -> StateGraph destination and approval resume -> rerisk trust boundaries; it introduced no new endpoint, auth path, file access path, schema boundary, or network surface beyond the threat model.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/rag_context/test_routing.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` - Task 1 RED failed as expected, then GREEN passed with `231 passed, 1 skipped, 28 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/test_graph_routing.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` - Task 2 passed with `133 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/rag_context/test_routing.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` - Plan-level passed with `243 passed, 1 skipped, 28 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY' ...` static scan confirmed active `risk_gate` registration, no active legacy node/path-map destination, and no `risk_gate` self-loop.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

57-03 can now harden trusted approval resume and risk/approval separation on top of canonical active `risk_gate` routing. Phase 58 still owns final deletion of remaining legacy compatibility aliases and historical projection cleanup.

## Self-Check: PASSED

- Found `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-02-SUMMARY.md`.
- Found `src/agent/graph.py`.
- Found `src/agent/routing.py`.
- Found `src/api/routers/approvals.py`.
- Found task commits `d1a23a2`, `08a06e4`, and `68f7d17`.

---
*Phase: 57-risk-gate-and-approval-gate-canonicalization*
*Completed: 2026-07-07*
