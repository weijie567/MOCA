---
phase: 34-approval-and-actiondraft-boundary-hardening
plan: 34-05
subsystem: action-draft-boundary
tags: [action-draft, approval-binding, auto-allowed, safe-projection, no-real-execution]

requires:
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-01
    provides: Phase 34 action/approval binding schemas and persistence columns
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-03
    provides: ApprovalService trusted resume results carrying persisted bindings
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-04
    provides: agent_runs approval interrupt bridge preserving binding fields
provides:
  - exact approval and auto-allowed binding validation before durable demo draft persistence
  - binding-aware action draft idempotency and repository reuse conflict detection
  - safe action_draft and working-state projections with draft-only/no-execution wording
affects: [action-service, action-draft-node, working-state, final-response, phase35-replay-eval]

tech-stack:
  added: []
  patterns: [TDD, canonical binding comparison, safe draft projection, demo-only action boundary]

key-files:
  created:
    - .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-05-SUMMARY.md
  modified:
    - src/actions/service.py
    - src/actions/drafts.py
    - src/repositories/action_draft_repo.py
    - src/tools/catalog.py
    - src/tools/executors/action.py
    - src/agent/nodes/action_draft.py
    - src/agent/working_state.py
    - src/db/models.py
    - src/db/migrations/versions/018_phase34_approval_action_bindings.py
    - tests/actions/test_phase34_action_draft_bindings.py
    - tests/actions/test_action_draft_v2.py
    - tests/test_execute_action.py
    - tests/architecture/test_action_draft_boundaries.py
    - tests/agent/test_nodes/test_final_response.py
    - tests/agent/test_working_state.py
    - tests/test_approval_models.py

key-decisions:
  - "ActionService ignores caller-supplied draft idempotency keys and rebuilds tenant/run/revision/action/target/hash keys from trusted binding material."
  - "Long auto-allowed revision markers are stored in approval_revision_ref/auto_allowed_binding_ref while idempotency_key uses a bounded sha256 fallback."
  - "action_draft validates approval_result and auto_allowed_binding against current state bindings before invoking the node-only write tool."
  - "WorkingState exposes draft refs/counts only; raw proposed action, payload, snapshot hash, and draft_outcome remain prompt-unsafe."

patterns-established:
  - "Compare Phase 34 bindings after Pydantic canonicalization rather than raw dict equality."
  - "For claim/risk authority, require either exact ref match or exact typed summary/payload match, and fail closed if both sides lack authority."
  - "Project action draft state as demo draft artifacts, never external execution success."

requirements-completed: [APF-15, APF-16]

duration: 28 min
completed: 2026-06-29
---

# Phase 34 Plan 05: Action Draft Boundary Summary

**Action draft creation now requires exact approval or auto-allowed bindings and only projects demo draft-safe refs/counts**

## Performance

- **Duration:** 28 min
- **Completed:** 2026-06-29T06:40:42Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- Extended `create_coupon_grant_draft` through catalog, executor, service, store, and repository layers to accept Phase 34 target merchant, business fact, evidence, claim, risk, and auto-allowed binding material.
- Added exact binding validation for approved approval rows and no-approval `AutoAllowedActionBindingV1` rows before any durable draft insert/reuse.
- Persisted Phase 34 binding projections on `ActionDraft` and made idempotent key reuse compare the same binding material.
- Hardened `action_draft` so approval resume and auto-allowed paths must match current state bindings before invoking the node-only action tool.
- Extended working-state draft artifacts with safe refs/counts while preserving no-real-execution final response wording guards.

## Task Commits

1. **Task 1 RED: Action draft binding tests** - `966400b` (test)
2. **Task 1 GREEN: Validate action draft bindings** - `dce573d` (feat)
3. **Task 2 RED: Action draft projection tests** - `b269a95` (test)
4. **Task 2 GREEN: Safe action draft binding projections** - `af98dbc` (feat)

## Files Created/Modified

- `src/actions/service.py` - Validates approval/auto binding material, rebuilds bounded idempotency keys, and returns typed safe draft data.
- `src/actions/drafts.py` - Passes Phase 34 binding fields into the repository adapter.
- `src/repositories/action_draft_repo.py` - Persists and compares Phase 34 binding fields on create/reuse.
- `src/tools/catalog.py` - Adds safe binding args to the node-only create draft tool schema.
- `src/tools/executors/action.py` - Forwards safe binding args from tool invocation to ActionService.
- `src/agent/nodes/action_draft.py` - Validates trusted approval/auto bindings against state and forwards only safe action draft args.
- `src/agent/working_state.py` - Projects safe draft artifact refs/counts without raw payload/snapshot/draft outcome bodies.
- `src/db/models.py`, `src/db/migrations/versions/018_phase34_approval_action_bindings.py` - Widen action draft revision/auto binding refs for full auto marker storage.
- Focused tests under `tests/actions/`, `tests/test_execute_action.py`, `tests/architecture/`, and `tests/agent/` cover the new contracts.

## Decisions Made

- Full `auto_allowed:{risk_decision_ref}` remains auditable in `approval_revision_ref` and `auto_allowed_binding_ref`; `idempotency_key` stays bounded to 256 chars via deterministic sha256 fallback when the raw contract key is too long.
- `action_draft` sends safe state fields to the tool without raw snapshot JSON or raw prompt bodies; ActionService remains the final durable validation authority.
- Working-state draft projection exposes counts for business/evidence refs instead of full ref arrays.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Auto-allowed marker exceeded existing action draft string lengths**

- **Found during:** Task 1 GREEN
- **Issue:** A valid `auto_allowed:{risk_decision_ref}` marker made the raw idempotency key exceed 256 chars, and the full marker also exceeded existing 128-char revision/binding ref columns.
- **Fix:** Made `_build_idempotency_key(...)` truly bounded, widened `ActionDraft.approval_revision_ref` and `auto_allowed_binding_ref` to 256, and updated migration 018 accordingly.
- **Files modified:** `src/actions/service.py`, `src/db/models.py`, `src/db/migrations/versions/018_phase34_approval_action_bindings.py`, `tests/actions/test_phase34_action_draft_bindings.py`
- **Verification:** Focused Task 1 tests passed; full 34-05 verification passed.
- **Committed in:** `dce573d`

---

**Total deviations:** 1 auto-fixed (blocking correctness issue)
**Impact on plan:** Required to satisfy the plan's auto-allowed revision marker and idempotency requirements. No real-execution scope was added.

## Issues Encountered

- The workflow example `gsd-sdk query state.begin-phase --phase 34 --name ... --plans 6` parsed flags as positional values in this local environment. Re-running as `gsd-sdk query state.begin-phase 34 approval-and-actiondraft-boundary-hardening 6` repaired `.planning/STATE.md`. The incident is recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 2 RED initially failed too broadly because the test fixture lacked a verified claim bundle and hit the existing fail-closed verifier guard before Phase 34 checks. The fixture was corrected before implementation.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py tests/test_execute_action.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_nodes/test_final_response.py tests/agent/test_working_state.py -q --tb=short` -> `87 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/actions/drafts.py src/repositories/action_draft_repo.py src/agent/nodes/action_draft.py src/agent/nodes/final_response.py src/agent/working_state.py src/tools/catalog.py src/tools/executors/action.py src/db/models.py src/db/migrations/versions/018_phase34_approval_action_bindings.py tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py tests/test_execute_action.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_nodes/test_final_response.py tests/agent/test_working_state.py tests/test_approval_models.py` -> passed
- `rg -n "target_merchant_id|business_fact_refs|verified_evidence_refs|AUTO_ALLOWED_BINDING_MISMATCH|auto_allowed:" src/actions/service.py src/repositories/action_draft_repo.py src/tools/executors/action.py` -> matches
- `rg -n "target_merchant_id|business_fact_refs|verified_evidence_refs|claim_verification_ref|risk_decision_ref" src/agent/nodes/action_draft.py src/agent/working_state.py` -> matches
- `rg -n "business_fact_refs: list\\[BusinessFactRefV1\\]|verified_evidence_refs: list\\[EvidenceRefV1\\]|risk_decision: RiskDecisionV1" src/actions/schemas.py` -> matches
- `rg -n "business_fact_refs: list\\[dict|verified_evidence_refs: list\\[dict" src/actions/schemas.py` -> no matches
- `rg -n "action_executions|action_outbox_events|action_reconciliation_jobs|action_compensation_records" src/actions src/tools src/repositories` -> no matches
- `rg -n "已发券|已退款|coupon issued|refund completed|ticket closed" src/agent/nodes/final_response.py tests/agent/test_nodes/test_final_response.py` -> test fixtures only

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 34-06. The approval/action draft boundary now has exact binding validation, durable demo-only draft persistence, safe projections, and static no-real-execution coverage for final closure validation.

## Self-Check: PASSED

- Focused pytest and ruff checks pass through the MOCA-approved `uv run` entrypoint.
- Approved and auto-allowed action draft paths fail closed on binding mismatch.
- Working state and final response paths project demo draft-safe fields only.
- No external execution/outbox/reconciliation/compensation production surfaces were introduced.

---
*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Completed: 2026-06-29*
