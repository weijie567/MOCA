---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Agent Architecture Migration
status: ready_to_plan
stopped_at: Phase 13 verified complete; Phase 14 ready to plan
last_updated: "2026-06-15T12:24:32Z"
last_activity: 2026-06-15 -- Phase 13 verified complete
progress:
  total_phases: 11
  completed_phases: 7
  total_plans: 42
  completed_plans: 42
  percent: 64
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md`

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 14 — demo-action-executor-boundary

## Current Position

Phase: 14
Plan: Not started
Plans: Not planned
Status: Ready to plan
Last activity: 2026-06-15 -- Phase 13 verified complete

Progress: [██████░░░░] 64%

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

## Session Continuity

Last session: 2026-06-15T11:49:59Z
Stopped at: Phase 13 verified complete; Phase 14 ready to plan
Resume file: None

**Next:** Plan Phase 14 demo-action-executor-boundary

**Completed Phase:** Phase 13 (Approval State Machine) — 2026-06-15

**Planned Phase:** 14 (Demo Action Executor Boundary) — not planned
