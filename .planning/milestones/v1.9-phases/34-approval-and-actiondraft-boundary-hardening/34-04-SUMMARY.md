---
phase: 34-approval-and-actiondraft-boundary-hardening
plan: 34-04
subsystem: agent-runs-approval-interrupt-bridge
tags: [agent-runs, approval-interrupt, safe-projection, phase34-bindings]

requires:
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-01
    provides: Phase 34 approval binding contracts and persistence columns
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-02
    provides: risk_gate approval_plan and durable Phase 34 interrupt fields
  - phase: 34-approval-and-actiondraft-boundary-hardening
    plan: 34-03
    provides: ApprovalService persistence and trusted resume binding propagation
provides:
  - agent_runs interrupt-to-ApprovalService command bridge preserving Phase 34 binding fields
  - live approval_required SSE/chat payloads with safe refs/summaries instead of raw action authority bodies
  - regression coverage for spoofed run/action identity remaining fail-closed
affects: [agent-runs, approval-service, approval-required-sse, legacy-chat-interrupt]

tech-stack:
  added: []
  patterns: [TDD, safe projection, trusted interrupt command mapping, no trace API expansion]

key-files:
  created: []
  modified:
    - src/api/routers/agent_runs.py
    - src/api/schemas/agent_runs.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "agent_runs copies Phase 34 interrupt bindings into ApprovalRequestCreateCommand only after trusted run/action identity validation."
  - "approval_required payloads expose proposed_action_summary, binding refs, claim/risk summaries, and approval revision metadata, not raw proposed_action or graph debug bodies."
  - "Trace API projection hardening remains deferred to Phase 35; Plan 34-04 modifies only live approval-required surfaces."

patterns-established:
  - "Use ApprovalService create results as the source for approval_required safe binding projection."
  - "Keep action authority persistence and client display payloads separate: raw proposed_action is persisted but not emitted in live wait payloads."

requirements-completed: [APF-15, APF-16]

duration: 17 min
completed: 2026-06-29
---

# Phase 34 Plan 04: Agent Runs Approval Interrupt Bridge Summary

**Agent run approval interrupts now preserve Phase 34 bindings into ApprovalService and emit only safe live approval-required projections**

## Performance

- **Duration:** 17 min
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Extended `_approval_create_command_from_interrupt(...)` to require and copy target merchant, business fact refs, verified evidence refs, claim verification refs/summaries, risk decision refs/payloads, and approval idempotency keys into `ApprovalRequestCreateCommand`.
- Kept trusted run/action identity validation authoritative; spoofed proposed action tenant/run mismatches still create zero approval rows.
- Replaced live `approval_required` raw `proposed_action` echo with `proposed_action_summary` plus safe Phase 34 refs/summaries and approval revision metadata.
- Updated `SseEventPayload` to document the safe approval wait fields.
- Left `src/api/routers/traces.py` untouched; broad trace/replay projection hardening remains Phase 35 scope.

## Task Commits

1. **Task 1 RED: Agent run binding bridge tests** - `f0386ce` (test)
2. **Task 1 GREEN: Preserve approval interrupt bindings** - `363b6ca` (feat)
3. **Task 2 RED: Safe approval projection tests** - `3475abb` (test)
4. **Task 2 GREEN: Safe approval wait payloads** - `91f9cfb` (feat)

## Files Created/Modified

- `src/api/routers/agent_runs.py` - Maps Phase 34 interrupt bindings into ApprovalService commands and emits safe approval wait payloads.
- `src/api/schemas/agent_runs.py` - Adds typed optional safe approval-required payload fields.
- `tests/test_agent_runs_api.py` - Covers binding persistence, spoof fail-closed behavior, and raw/debug payload non-leakage.

## Decisions Made

- `approval_idempotency_key` is accepted from the structured interrupt payload, with `approval_plan.approval_idempotency_key` as the trusted fallback.
- `risk_decision` is persisted through ApprovalService but projected to clients only as `risk_decision_ref` plus `risk_decision_summary`.
- `action_payload_hash` and safety snapshot ref/hash remain in live payloads because they are decision/version metadata, not full raw snapshot bodies.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- No implementation blockers. The safe projection test initially needed key-level raw-field assertions to avoid false positives from safe names such as `proposed_action_summary` and `risk_decision_ref`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q --tb=short` -> `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent_runs.py src/api/schemas/agent_runs.py tests/test_agent_runs_api.py` -> passed
- `rg -n "target_merchant_id|business_fact_refs|verified_evidence_refs|claim_verification|risk_decision|approval_idempotency_key" src/api/routers/agent_runs.py tests/test_agent_runs_api.py` -> matches
- `rg -n "requested_by.*merchant|merchant_id.*requested_by" src/api/routers/agent_runs.py` -> no matches
- `git diff --name-only HEAD~4..HEAD` -> `src/api/routers/agent_runs.py`, `src/api/schemas/agent_runs.py`, `tests/test_agent_runs_api.py`
- `git diff --check` -> passed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 34-05. Action draft validation can now rely on approval requests and live approval interrupts carrying stable target merchant, business fact, evidence, claim, risk, snapshot, and payload-hash bindings.

## Self-Check: PASSED

- Focused pytest and ruff checks pass through the MOCA-approved `uv run` entrypoint.
- agent_runs preserves Phase 34 bindings into ApprovalService.
- approval_required payloads expose safe refs/summaries and omit raw proposed_action/debug/snapshot/action authority bodies.
- `src/api/routers/traces.py` remains unmodified for Phase 35 deferral.

---
*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Completed: 2026-06-29*
