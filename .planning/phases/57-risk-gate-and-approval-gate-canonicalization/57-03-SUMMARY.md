---
phase: 57-risk-gate-and-approval-gate-canonicalization
plan: 03
subsystem: agent-graph-risk-approval
tags: [langgraph, risk-gate, approval, canonical-agent-graph, security]

requires:
  - phase: 57-02
    provides: active graph and approval edit rerisk paths targeting risk_gate
provides:
  - canonical trusted approval edit retry resume route normalization
  - Phase 58-scoped persisted legacy resume_route compatibility boundary
  - approval_gate trusted result schema and binding validation
  - ordinary chat approval spoofing and stale authority regression coverage
affects: [phase-57, phase-57-04, phase-57-05, phase-58, approval-boundary, canonical-agent-graph]

tech-stack:
  added: []
  patterns:
    - persisted legacy retry normalization before graph resume
    - approval_gate full trusted-result validation before state mutation
    - receive_request turn-start reset of approval/risk/action authority fields

key-files:
  created:
    - .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-03-SUMMARY.md
  modified:
    - src/approvals/service.py
    - src/api/routers/approvals.py
    - src/agent/graph.py
    - src/agent/nodes/approval_gate.py
    - src/agent/nodes/receive_request.py
    - tests/test_approval_api.py
    - tests/test_graph_routing.py
    - tests/test_approval_gate.py
    - tests/agent/test_graph.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Normalized persisted legacy edit retry metadata to canonical risk_gate before graph resume instead of accepting legacy as current authority."
  - "Kept route_after_approval strict: trusted edit rerisk requires resume_route risk_gate and new_action_payload_hash; edit never routes directly to action_draft."
  - "Validated approval_gate interrupt resumes with TrustedApprovalResultV1 plus tenant/run/hash binding before setting approval_result."

patterns-established:
  - "Legacy resume_route compatibility is API retry reconstruction only, visibly DELETE_BY_PHASE_58, and normalized before graph resume."
  - "Approval-like chat turns clear stale approval/risk/action authority at receive_request before safety routing."

requirements-completed: [CAGM-08]

duration: 21min
completed: 2026-07-07
---

# Phase 57 Plan 03: Trusted Approval Resume Boundary Summary

**Trusted approval edit retries now resume through canonical `risk_gate`, while approval_gate and ordinary chat paths fail closed against malformed or spoofed approval authority**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-07T14:05:36Z
- **Completed:** 2026-07-07T14:27:00Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Canonicalized new and retried edit approval resume payloads to `resume_route="risk_gate"`.
- Added a narrow, Phase 58-marked compatibility path for persisted legacy retry metadata only.
- Rejected fresh/current legacy edit route authority in API resume checks and graph routing tests.
- Hardened `approval_gate` so only complete, bound `TrustedApprovalResultV1` payloads can set `approval_result`.
- Cleared stale approval/risk/action authority fields at new-turn intake for ordinary approval-like chat.

## Task Commits

1. **Task 1 RED: Add failing approval retry route tests** - `7c18af0` (test)
2. **Task 1 GREEN: Normalize legacy approval retry route** - `3c8e016` (fix)
3. **Task 2 RED: Add failing approval gate boundary tests** - `7635bbc` (test)
4. **Task 2 GREEN: Harden approval gate trust boundary** - `40be14c` (fix)

## Files Created/Modified

- `src/approvals/service.py` - Emits canonical `CANONICAL_RISK_ROUTE = "risk_gate"` for new edit decisions.
- `src/api/routers/approvals.py` - Normalizes persisted legacy retry metadata to `risk_gate` and rejects current legacy routes outside retry reconstruction.
- `src/agent/graph.py` - Keeps trusted edit rerisk on canonical `risk_gate`; no legacy current-route branch added.
- `src/agent/nodes/approval_gate.py` - Validates full trusted result schema and tenant/run/hash bindings before setting `approval_result`.
- `src/agent/nodes/receive_request.py` - Clears stale approval/risk/action authority fields at the start of each turn.
- `tests/test_approval_api.py` - Covers canonical edit resume, persisted legacy retry normalization, mismatch failures, and current-route rejection.
- `tests/test_graph_routing.py` - Covers canonical edit routing and fresh legacy edit route rejection.
- `tests/test_approval_gate.py` - Covers invalid/incomplete resume payload rejection and static runtime-coupling guard.
- `tests/agent/test_graph.py` - Covers approval-like chat avoiding approval/action paths and clearing contaminated authority state.
- `.planning/LOCAL-VALIDATION-ISSUES.md` / `.planning/ARCHITECTURE-DEBT.md` - Records for the RED failures and verified risk/approval boundary fixes.

## Decisions Made

- Persisted `resume_route="assess_risk_and_approval"` is treated as historical metadata only inside API retry reconstruction, then converted to `risk_gate` before graph resume.
- No graph-level legacy edit branch was introduced; current `route_after_approval(...)` accepts only canonical `risk_gate`.
- `approval_gate` now validates the trusted payload itself before mutating state, even though `route_after_approval(...)` also validates before routing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Cleared stale approval authority at request intake**
- **Found during:** Task 2 RED.
- **Issue:** `receive_request` reset `approval_result`, `proposed_action`, and hash fields, but left `approval_plan`, `risk_decision`, target refs, business/verified refs, `approval_idempotency_key`, and `auto_allowed_binding` attached to a new ordinary chat turn.
- **Fix:** Added those approval/risk/action authority fields to the per-turn reset and covered the contaminated-state case in `tests/agent/test_graph.py`.
- **Files modified:** `src/agent/nodes/receive_request.py`, `tests/agent/test_graph.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`, `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Task 2 focused command passed with `1172 passed, 29 warnings`; full plan command passed with `1283 passed, 29 warnings`.
- **Committed in:** `40be14c`

**Total deviations:** 1 auto-fixed missing-critical issue.
**Impact on plan:** The extra file was required to fully satisfy the ordinary-chat trust boundary; no architectural direction changed.

## Issues Encountered

- Task 1 RED initially surfaced two failures: the intended persisted legacy retry normalization gap, plus an overly weak version-mismatch test using `expected_request_version + 1`. The test was corrected to `+2`, leaving the intended RED failure.
- Task 2 RED surfaced the intended malformed resume gap and a stale `approval_plan` carryover gap. Both are recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- `gsd-sdk query roadmap.update-plan-progress "57"` repeated the known Phase 57 checkbox mismatch; ROADMAP/STATE plan progress was manually updated to 3/5 and the handler issue was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Compatibility Evidence

Remaining legacy `resume_route == "assess_risk_and_approval"` hits are classified as follows:

- `src/api/routers/approvals.py` - `LEGACY_RISK_ROUTE` and `_canonical_retry_resume_route(...)` are persisted historical retry compatibility only, adjacent to `DELETE_BY_PHASE_58`, and normalize to `risk_gate`.
- `tests/test_approval_api.py` - Historical persisted event metadata fixture plus `_should_resume_graph` rejection case for fresh/current legacy route.
- `tests/test_graph_routing.py` - Fresh/current legacy edit route rejection case for `route_after_approval(...)`.
- `tests/agent/test_phase22_action_boundary.py` and `src/agent/nodes/assess_risk_and_approval.py` - retained legacy wrapper/import-test compatibility from 57-01, a Phase 58 deletion candidate, not current graph authority.
- Phase planning/research/pattern docs - historical context and validation expectations only.

No current `ApprovalService` edit path, approval API current resume check, or graph route accepts the legacy route as current authority.

## TDD Gate Compliance

- Task 1 RED (`7c18af0`) failed as expected before GREEN (`3c8e016`).
- Task 2 RED (`7635bbc`) failed as expected before GREEN (`40be14c`).

## Known Stubs

None. Stub scan hits were test fixtures, explicit empty fixture collections, or historical planning-ledger text; no runtime placeholder data source was introduced.

## Threat Flags

None. The changes remain within the plan threat model: approval API retry reconstruction, ApprovalService-to-graph resume, and ordinary chat-to-routing trust boundaries. No new endpoint, auth path, file access path, schema boundary, or network surface was introduced.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_graph_routing.py -q --tb=short` - Task 1 RED failed as expected, then GREEN passed with `111 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py tests/agent/test_graph.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_intent_routing.py tests/agent/test_clarification_gate.py -q --tb=short` - Task 2 RED failed as expected with `3 failed, 1169 passed, 29 warnings`, then GREEN passed with `1172 passed, 29 warnings`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/agent/test_graph.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_intent_routing.py tests/agent/test_clarification_gate.py -q --tb=short` - Plan-level verification passed with `1283 passed, 29 warnings`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

57-04 can now update trace/API/frontend/eval projection surfaces assuming current approval edit resume authority is canonical `risk_gate`. CAGM-08 remains pending in `.planning/REQUIREMENTS.md` until the remaining Phase 57 plans complete. Phase 58 still owns final deletion of retained `assess_risk_and_approval` compatibility aliases.

## Self-Check: PASSED

- Found `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-03-SUMMARY.md`.
- Found task commits `7c18af0`, `3c8e016`, `7635bbc`, and `40be14c`.
- Confirmed no tracked file deletions in task commits.

---
*Phase: 57-risk-gate-and-approval-gate-canonicalization*
*Completed: 2026-07-07*
