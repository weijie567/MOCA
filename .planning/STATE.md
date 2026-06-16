---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Agent Architecture Migration
status: ready_to_plan
stopped_at: Phase 14 verified complete; Phase 15 ready to plan
last_updated: "2026-06-16T04:16:01.635Z"
last_activity: 2026-06-16 -- Phase 14 verified complete after gap closure; Phase 15 ready to plan
progress:
  total_phases: 11
  completed_phases: 8
  total_plans: 49
  completed_plans: 49
  percent: 73
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md`

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 15 — Replay Event Contract planning

## Current Position

Phase: 15
Plan: Not started
Plans: 7 planned
Status: Ready to plan
Last activity: 2026-06-16

Progress: [██████████] 98%

## Completed Baseline

Phase 7 Contract Baseline completed on 2026-06-06.

- Artifacts: `.planning/phases/07-contract-baseline/`
- Coverage result: `MISSING=0`
- Downstream readiness: Phase 8 and Phase 9 may proceed to planning.
- Phase 7 is docs-only and does not claim later target contracts are implemented.

## Decisions

- v1.0 remains archived as completed Phases 1-6.
- The previous v1.1 planning line was replaced at the planning level.
- v1.1 is now the Agent Architecture Migration roadmap spanning Phases 7-17.
- Phase 7-17 are standard SDK phase identities; no separate prefixed phase namespace remains.
- Source code, tests, and git history from the previous planning line were not rolled back.
- Phase 8 and Phase 9 may plan and execute in parallel after Phase 7.
- Phase 16 and Phase 17 remain named owner phases but do not block the MVP completion gate.
- Policy evidence identity uses `v{PolicyDocument.version}`; effective dates do not determine evidence identity.
- Policy re-import uses a row lock so concurrent changed-content imports serialize version bumps.
- Runtime policy retrieval uses `PolicyKnowledgeService`; the legacy `search_policy` path remains unchanged for rollback.
- Recommendation citations are validated by full `evidence_id`, and all no-action drafts are suppressed before proposed-action creation.
- Write descriptors remain declared but are hard-blocked before adapter access; action event families remain deferred to Phase 17.
- AsyncSession is passed explicitly to registry adapters and never added to ToolCallContext.
- BusinessToolService is the live registry-to-adapter composition root; callers inject only AsyncSession.
- Trusted tool permissions and merchant scope are derived in the agent-runs router and passed only through configurable run config.
- The prior-line registry remains only as an isolated policy-search compatibility path; live business reads use the Phase 9 facade.
- Phase 12 completed with PostgreSQL-authoritative session memory, same-thread slot continuity, CAS safety, no policy-evidence/action authority escalation, and Redis explicitly skipped for Phase 12.
- CanonicalHashProfile v1 lives in src/common/canonical_hash.py and is shared by approval, action, and replay consumers.
- The Phase 13-local action_safety_snapshot.v1 golden digest is frozen with exact canonical JSON and hash input bytes.
- ActionSafetySnapshot imports EvidenceRefV1 and canonical_evidence_projection instead of defining a reduced evidence schema.
- The active approval-request revision partial unique excludes legacy_non_executable rows so quarantined history cannot block a new executable v2 revision.
- Legacy v1 approval rows are backfilled with row_number() per (tenant_id, run_id) and marked legacy_non_executable before revision uniqueness is enforced.
- approval_decisions carries redundant level_mode so the winning-accept partial unique applies only to any_one levels and does not break all-mode assignments.
- ApprovalDecisionCommand carries run_id, thread_id, level_id, and assignment_id in addition to expected versions so the service can validate the full decision binding.
- ApprovalService calls src/approvals/snapshot_service.py for snapshot persistence and does not expose it as an auto-allow transition method.
- Approval decision rows record pre-transition authorization versions; ApprovalDecisionResult and approval_result.v1 return post-transition versions.
- Approval respond writes needs_info and clarification_request_id but intentionally returns resume_payload=None so the old interrupted run cannot enter action_draft.
- Approval attach_info updates the same revision only for non-material info with bumped versions; changed payload/evidence/config supersedes the old revision and creates a pending replacement.
- Approval edit persists edited_action_json and exposes a risk-reroute approval_result payload, while the API endpoint does not treat edit as an action-authorizing graph resume.
- route_after_approval lives in src/agent/graph.py in this codebase, so the Plan 13-05 routing change was applied there instead of src/agent/routing.py.
- Approval_requested, approval_decided, approval_expired, and approval_resumed are registered as minimal_event rows before Phase 15 replay enrichment.
- Edit and respond decisions now emit approval_decided with old_revision_ref and new_revision_ref; approval_resumed is registered as a helper but graph lifecycle wiring remains Phase 15-owned.
- ApprovalSlaScanner defaults to disabled via APPROVAL_SLA_SCANNER_ENABLED=false; Phase 15 owns enabling active scanning after replay and allocator gates pass.
- Deleted src/repositories/approval_repo.py instead of leaving a compatibility shim because source callers had already moved to src.approvals and the remaining legacy references were obsolete tests.
- Direct action-node execution now requires approval_result.v1 revision/version fields plus exact action_payload_hash, safety_snapshot_ref, and safety_snapshot_hash matches, mirroring graph routing.
- Legacy approval model tests now assert ApprovalService semantics, including terminal conflicts and legacy_v1 fail-closed behavior, rather than v1 repository idempotency.
- Phase 13 full pytest gate blocker was resolved; coverage records P13-BLOCK-FULL-PYTEST as RESOLVED, and phase verification passed 12/12 must-haves after `uv run pytest -q --tb=short` and `uv run ruff check src tests` passed.
- Phase 13 approval-contract eval manifest uses a real dataset hash computed from the frozen approval-focused test corpus instead of the placeholder hash.
- Phase 14 action drafts use tenant-scoped unique `(tenant_id, idempotency_key)` and persist v2 draft binding/outcome columns; contract `proposed_action` remains stored in the existing `ActionDraft.payload` JSONB column.
- Phase 14 ActionService owns final action draft idempotency key construction; caller-provided keys are ignored for persisted draft identity.
- Auto-allowed drafts use the exact `auto_allowed` key marker, while approval-backed drafts use `approval_revision_{revision}` and persist `approval_request/{id}@rev{revision}`.
- `AgentState.action_draft`, `AgentState.draft_outcome`, and `AgentState.execution_mode` are reset by `receive_request` at each turn so checkpointed draft state cannot leak.
- The canonical graph node and caller_node value is `action_draft`; `execute_action` remains only an intent-layer requested_operation value or compatibility shim name.
- Approval reconciliation imports `action_draft` directly so production source no longer depends on the `execute_action` shim; Phase 14 Plan 04 still owns draft_outcome-based reconciliation wording.
- Approval resume and final-response wording now use `draft_outcome.status == "not_executed_demo"` plus `external_side_effect is False` as the demo success signal instead of `action_result.status == "success"`.
- `action_draft_created` is a minimal trace event with safe refs only, and `/trace` projects `draft_outcome` without exposing raw `ActionDraft.payload`.
- Phase 14 Wave 4 post-merge validation passed `uv run pytest -q --tb=short` with 806 tests after stale approval model idempotency tests were updated to the v2 tenant-scoped draft contract.
- Phase 14 final coverage treats ReplayEventV3/lifecycle/read-switch work as Phase 15-owned and external execution/outbox/reconciliation/compensation as Phase 17-owned.
- execute_action and action_result compatibility remain temporary surfaces with Phase 15 Replay Event Contract removal/replacement gates targeting 2026-07-16 unless Phase 15 is replanned.

## Blockers / Concerns

- Every phase plan must preserve coverage-matrix and follow-up-register visibility.
- Relevant `MISSING` rows block execution.
- Phase 13 must keep the active SLA scanner as an explicit owned follow-up gate.
- Phase 16/17 deferral must not weaken Phase 12 session-memory fallback or Phase 14 demo action safety.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
| --- | --- | --- | --- | --- |
| 08 | 01 | 5 min | 4 | 10 |
| 08 | 04 | 2h 13m | 6 | 11 |
| 09 | 01 | 4 min | 2 | 4 |
| 09 | 02 | 7 min | 3 | 2 |
| 09 | 03 | 4 min | 2 | 2 |
| 09 | 04 | 5 min | 3 | 2 |
| 09 | 05 | 5h 9m | 3 | 8 |
| 09 | 06 | 8 min | 2 | 4 |
| 09 | 07 | 5 min | 2 | 4 |
| 09 | 08 | 5 min | 2 | 3 |
| 09 | 09 | 11 min | 2 | 9 |
| 10 | 05 | 36 min | 4 | 5 |
| 11 | 01 | inline | 3 | 9 |
| 11 | 02 | inline | 3 | 4 |
| 11 | 03 | inline | 3 | 7 |
| 11 | 04 | inline | 2 | 5 |
| 11 | 05 | inline | 3 | 8 |
| 12 | 01 | 14 min | 4 | 9 |
| 12 | 02 | 9 min | 4 | 11 |
| 12 | 03 | 26 min | 4 | 10 |
| 12 | 04 | 17 min | 5 | 6 |
| 12 | 05 | 3 min | 2 | 1 |
| 13 | 01 | 9 min | 4 | 7 |
| 13 | 02 | 1h 15m | 4 | 5 |
| 13 | 03 | 15 min | 4 | 8 |
| 13 | 04 | 34 min | 4 | 17 |
| 13 | 05 | 16 min | 3 | 10 |
| 13 | 06 | 15 min | 3 | 10 |
| 13 | 07 | 10 min | 3 | 7 |
| 13 | 08 | 15 min | 2 | 3 |
| 14 | 01 | 5 min | 3 | 5 |
| 14 | 02 | 29 min | 3 | 8 |
| 14 | 03 | 1h 2m | 2 | 12 |
| 14 | 04 | 31 min | 2 | 5 |
| 14 | 05 | 25 min | 2 | 8 |
| 14 | 06 | 16 min | 2 | 7 |
| Phase 14 P07 | 24 min | 3 tasks | 5 files |

## Session Continuity

Last session: 2026-06-16T04:16:01.361Z
Stopped at: Completed 14-07-PLAN.md
Resume file: None
Next: Verify Phase 14 gap closure

**Planned Phase:** 14 (Demo Action Executor Boundary) — 7 plans — 2026-06-16T03:43:31.270Z
