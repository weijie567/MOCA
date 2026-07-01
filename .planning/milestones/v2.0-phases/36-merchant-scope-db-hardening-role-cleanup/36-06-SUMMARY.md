---
phase: 36-merchant-scope-db-hardening-role-cleanup
plan: 36-06
subsystem: replay
tags: [readiness, replay, merchant-scope, no-widening, pytest, ruff]

requires:
  - phase: 36-03
    provides: AgentRun target merchant binding and scope classification
  - phase: 36-04
    provides: approval/action/snapshot target merchant consistency
  - phase: 36-05
    provides: migration preflight and DB hardening facts
provides:
  - Strict Phase 36 readiness artifact contract and validated readiness conclusion
  - Final no-widening evidence for owner/admin-only run, trace, replay, status, and evidence surfaces
  - Full-suite and Ruff evidence for Phase 36 completion
affects: [phase-36, phase-37-readiness, trace-replay, approval-readiness, merchant-scope]

tech-stack:
  added: []
  patterns:
    - Readiness artifacts separate trusted AgentRun/business facts from weak projection-only facts.
    - Route legacy identity fields continue to flow through trusted-context projection helpers.
    - Final validation records concrete command results instead of carrying draft pending rows.

key-files:
  created:
    - src/replay/phase36_readiness.py
    - eval/replay/phase36-readiness.v1.json
    - tests/replay/test_phase36_readiness.py
    - .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-06-SUMMARY.md
  modified:
    - .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-VALIDATION.md
    - tests/replay/test_phase35_trace_replay_permissions.py
    - src/api/routers/agent.py
    - src/api/routers/agent_runs.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/action_draft.py
    - src/actions/service.py
    - src/db/migrations/env.py
    - tests/test_agent_runs_api.py
    - tests/test_approval_api.py
    - tests/conftest.py
    - src/business/adapters.py
    - src/integrations/demo_business/orders.py
    - src/integrations/demo_business/refunds.py
    - src/integrations/demo_business/tickets.py
    - tests/business/test_adapters.py
    - tests/business/test_service.py

key-decisions:
  - "Phase 36 readiness is ready_with_agent_run_binding because AgentRun binding, consistency, migration, and no-widening evidence all passed."
  - "Phase 37 may consume persisted AgentRun target merchant binding as the primary future authorization fact, but Phase 36 does not implement same-merchant manager visibility."
  - "Weak facts such as owner identity, requested_by, thread id, prompt text, memory, RAG, LLM output, raw tool payload, target_merchant_context, and replay_authorization_proof remain non-authorizing."

patterns-established:
  - "Readiness validators enforce approved MOCA pytest entrypoints and reject bare pytest command evidence."
  - "Legacy /agent/chat interrupt persistence uses trusted-context identity projection instead of writing current_run_id directly in route code."
  - "Final validation docs include failed-command remediation evidence before marking full suite green."

requirements-completed: [MSH-07, MSH-08]

duration: 4h 20min
completed: 2026-06-30
---

# Phase 36 Plan 36-06: Readiness and No-Widening Validation Summary

**Strict Phase 36 readiness evidence now records `ready_with_agent_run_binding` while preserving owner/admin-only runtime visibility.**

## Performance

- **Duration:** 4h 20min
- **Started:** 2026-06-30T08:30:00Z
- **Completed:** 2026-06-30T12:50:00Z
- **Tasks:** 2
- **Files modified:** 39

## Accomplishments

- Added a strict readiness artifact validator and `eval/replay/phase36-readiness.v1.json` with exactly one readiness result: `ready_with_agent_run_binding`.
- Extended Phase 36 no-widening static/API coverage so new target merchant binding and readiness projection facts do not become authorization guard inputs.
- Repaired final validation regressions found during full-suite execution, including legacy chat interrupt scope persistence, canonical action/snapshot JSON binding stability, migration test DB setup, and stale fixture assumptions.
- Updated `36-VALIDATION.md` with final focused, full-suite, Ruff, source-audit, no-RLS, and Phase 37/RLS deferral evidence.

## Task Commits

1. **Task 1 RED: readiness artifact contract** - `3405c34` (test)
2. **Task 1/2 GREEN: readiness artifact validation** - `eee8836` (feat)
3. **Validation hardening and full-suite remediation** - `1662449` (fix)

**Plan metadata:** committed separately with this summary.

## Files Created/Modified

- `src/replay/phase36_readiness.py` - Strict Pydantic readiness loader/validator with approved command discipline.
- `eval/replay/phase36-readiness.v1.json` - Phase 37 readiness conclusion with trusted/untrusted facts and required commands.
- `tests/replay/test_phase36_readiness.py` - Readiness enum, schema, command, and no-widening artifact tests.
- `tests/replay/test_phase35_trace_replay_permissions.py` - Phase 36 static checks that forbid target/readiness proof from widening run/trace/replay guards.
- `src/api/routers/agent.py` - Persists interrupt final state with trusted-context legacy identity projection.
- `src/api/routers/agent_runs.py` - Synchronizes interrupted run scope from trusted interrupt payloads before approval wait projection.
- `src/agent/nodes/assess_risk_and_approval.py` - Carries target merchant and business fact refs into action safety snapshots.
- `src/agent/nodes/action_draft.py`, `src/actions/service.py` - Preserve canonical nullable binding fields during JSON-safe validation.
- `src/db/migrations/env.py` - Makes test Alembic database URL override explicit and widens `alembic_version.version_num` before long revision IDs.
- `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-VALIDATION.md` - Final validation evidence and source audit.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` -> 287 passed, 3 warnings.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` -> 2125 passed, 4 skipped, 44 warnings.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> passed.
- `rg -n "ROW LEVEL SECURITY|CREATE POLICY|ENABLE ROW LEVEL SECURITY|SET LOCAL|current_setting" src/db src/api src/auth src/platform src/agent src/replay` -> no matches.

## Post-Code-Review Fixes

The Phase 36 code-review gate found three true warnings after the initial 36-06 merge. All were fixed before final phase closure:

- Real order/refund/ticket business reads now carry authorized `merchant_id` through the strict adapter projections so target merchant binding can be derived from the default business fact path.
- Auto-allowed action draft creation now validates snapshot and auto-allowed binding material before promoting a newly created `unknown_legacy` run to `business_merchant`; mismatched existing run scope still fails closed.
- Auto-allowed drafts now validate the submitted `risk_decision` payload against tenant id, run id, action payload hash, and no-approval semantics before persisting it.

Additional verification:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> 49 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_adapters.py tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> 112 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/test_graph_routing.py tests/approvals/test_phase36_scope_consistency.py tests/test_approval_api.py -q --tb=short` -> 175 passed, 1 warning.
- Final Phase 36 focused gate was rerun after the fixes and passed: 287 passed, 3 warnings.

## Decisions Made

- Marked readiness as `ready_with_agent_run_binding` only after AgentRun binding, approval/action/snapshot consistency, migration, no-widening regression, full-suite, and Ruff gates all passed.
- Kept Phase 37 same-merchant manager visibility as future work; Phase 36 emits evidence only.
- Treated `target_merchant_context` and `replay_authorization_proof` as projection-only facts, not authorization inputs.
- Kept route-owned `current_run_id` compatibility behind `project_to_legacy_agent_state_identity`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Synchronized interrupted run scope before approval wait projection**
- **Found during:** final focused approval/API regression.
- **Issue:** SSE interrupted runs could persist approval wait payloads before `AgentRun.scope_*` matched the trusted interrupt payload.
- **Fix:** Added `_apply_interrupt_run_scope(...)` in `src/api/routers/agent_runs.py` and flushed before creating the wait payload.
- **Files modified:** `src/api/routers/agent_runs.py`, `tests/test_agent_runs_api.py`
- **Verification:** Agent runs interrupt subset and full suite passed.
- **Committed in:** `1662449`

**2. [Rule 2 - Missing Critical] Preserved Phase 34 binding fields through JSON-safe canonicalization**
- **Found during:** approval/action/snapshot regression expansion.
- **Issue:** Canonical action and snapshot validation could drop nullable required binding fields, causing hash/binding drift in Phase 36 readiness paths.
- **Fix:** Added contract JSON-safe helpers in action draft/action service validators and updated snapshot hash nullable fields.
- **Files modified:** `src/agent/nodes/action_draft.py`, `src/actions/service.py`, `src/approvals/snapshots.py`, related tests.
- **Verification:** `tests/approvals` and full suite passed.
- **Committed in:** `1662449`

**3. [Rule 3 - Blocking] Routed legacy chat interrupt identity through trusted projection**
- **Found during:** full-suite static boundary gate.
- **Issue:** `tests/architecture/test_trusted_context_boundaries.py` forbids route code from writing `"current_run_id":` directly; the interrupt persistence fix initially violated that seam.
- **Fix:** Replaced the direct route literal with `_legacy_agent_state_identity(trusted_context)`.
- **Files modified:** `src/api/routers/agent.py`
- **Verification:** Static guard, interrupt/API focused regression, and full suite passed.
- **Committed in:** `1662449`

**4. [Rule 3 - Blocking] Hardened test DB/migration setup for full-suite execution**
- **Found during:** aggregate/full-suite validation.
- **Issue:** Metadata-created test DBs were missing `pg_trgm`, Alembic long revision IDs exceeded the old `alembic_version.version_num` size, and concurrent leftover pytest processes could collide on shared PostgreSQL DDL.
- **Fix:** Added `pg_trgm` setup to fixtures, allowed test Alembic URL overrides, widened `alembic_version.version_num` before migrations, reset the shared test schema before reruns, and recorded the concurrency pitfall in validation docs.
- **Files modified:** `tests/conftest.py`, `tests/conversation/test_models.py`, `tests/test_rag_production_migration.py`, `src/db/migrations/env.py`
- **Verification:** split aggregates and full suite passed.
- **Committed in:** `1662449`

---

**Total deviations:** 4 auto-fixed (2 missing critical, 2 blocking validation issues).
**Impact on plan:** All changes were required to make the readiness/no-widening evidence truthful and executable. No Phase 37 visibility behavior was implemented.

## Issues Encountered

- A split aggregate rerun initially failed with PostgreSQL `pg_type` duplicate/deadlock errors because a previous truncated full-suite command was likely still running against the same `moca_test/public` schema. After confirming no pytest process remained and resetting the schema, the same command passed.
- Full suite initially failed one trusted-context static guard; the fix kept the established projection seam intact.
- Full ruff initially found stale unused imports in untouched tool-platform files; removing those imports made full ruff pass and the tool-platform regression suite stayed green.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None open. T36-01 through T36-06 are covered by focused/full-suite evidence in `36-VALIDATION.md`.

## TDD Gate Compliance

- RED gate present: `3405c34` (`test(36-06): add failing readiness artifact contract`) failed before the readiness artifact/validator existed.
- GREEN gate present: `eee8836` (`feat(36-06): implement readiness artifact validation`) introduced the validator/artifact/tests.
- Remediation gate present: `1662449` (`fix(36-06): harden approval readiness validation`) made final focused/full-suite/Ruff gates green.

## Next Phase Readiness

Ready for Phase 37 planning. The next phase can consider read-only same-merchant manager visibility using persisted AgentRun target merchant binding as the primary authorization fact, while preserving fail-closed behavior for `policy_only`, `merchant_not_required`, and `unknown_legacy` runs unless Phase 37 records a narrower explicit decision.

## Self-Check: PASSED

- Key files exist on disk: readiness validator, readiness artifact, readiness tests, validation doc, and this summary.
- Task commits found: `3405c34`, `eee8836`, `1662449`.
- Full suite and full ruff passed with approved MOCA entrypoints.
- No `.planning/STATE.md` or `.planning/ROADMAP.md` changes were made in this worktree.

---
*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Completed: 2026-06-30*
