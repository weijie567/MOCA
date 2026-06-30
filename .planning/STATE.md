---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Merchant Scope Hardening
status: executing
stopped_at: Phase 36 planned; ready for execution
last_updated: "2026-06-30T06:33:57.117Z"
last_activity: 2026-06-30 -- Phase 36 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 6
  completed_plans: 3
  percent: 50
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-30)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 36 — merchant-scope-db-hardening-role-cleanup

## Current Position

Phase: 36 (merchant-scope-db-hardening-role-cleanup) — EXECUTING
Next roadmap item: execute Phase 36
Plan: 4 of 6
Status: Executing Phase 36
Last activity: 2026-06-30 -- Phase 36 execution started

Progress: [█████░░░░░] 50%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/MILESTONES.md`
- `.planning/milestones/v1.9-ROADMAP.md`
- `.planning/milestones/v1.9-REQUIREMENTS.md`
- `.planning/milestones/v1.9-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.6-ROADMAP.md`
- `.planning/milestones/v1.6-REQUIREMENTS.md`
- `.planning/milestones/v1.6-phases/23-rag-reranker-query-rewrite/`

## Current Milestone Context

- v2.0 focuses on merchant-scope database hardening and role cleanup, not new user-facing agent behavior.
- Phase 36 should convert v1.9 runtime merchant-bound role semantics into database/migration/readiness facts: deprecated legacy `merchant` compatibility, active business-user merchant binding, tenant-scoped username identity, run-level target merchant scope classification, and cross-table consistency gates.
- Same-merchant manager run/trace/replay visibility remains future Phase 37 scope until Phase 36 proves a trustworthy run-level merchant binding and emits a readiness conclusion.
- PostgreSQL RLS remains out of scope for v2.0 unless a later explicit phase adopts it; Phase 36 should prepare schema constraints, indexes, validation, and backfill gates only.

## Current Roadmap

| Phase | Plans | Status |
|-------|-------|--------|
| 36. Merchant-scope DB Hardening / Role Cleanup | 3/6 plans | In progress |

## Last Milestone Context

- v1.9 shipped the platform foundation for MOCA's agent architecture, not a new user-facing workflow and not full real external execution.
- The target is a microservice-ready modular monolith: service boundaries should be clear enough to split later, while deployment remains a single app for now.
- `docs/contract-spec.md` is the normative source. `docs/target-agent-platform-architecture-plan.md` records target architecture and Phase 26 spec-delta baseline decisions.
- The milestone should land foundations in dependency order: architecture contract baseline, TrustedContextFactory/projections, decision events, tool platform, business facts, memory platform, graph migration, RAG context build/claim verification, approval/action boundary hardening, replay/eval hardening, and audit-readiness closure.
- Memory remains contextual only; policy evidence, business facts, approval/action authority, and replay truth keep their own authoritative services and schemas.

## Performance Metrics

**v1.9 shipped scope:** 12 phases, 19 v1 requirements, 51/51 phase plans complete. Milestone audit status: ready to archive before archive, now archived.

| Phase | Plans | Status |
|-------|-------|--------|
| 26. Architecture Contract Baseline | 1/1 complete | Complete |
| 27. TrustedContextFactory and Projections | 3/3 complete | Complete |
| 28. Decision Event Foundation | 1/1 complete | Complete |
| 29. Tool Platform Boundary | 4/4 complete | Complete |
| 29.5. Merchant Scope / Role Model Alignment | 6/6 complete | Complete |
| 30. BusinessFactService Boundary | 3/3 complete | Complete |
| 31. Memory Platform Boundary | 6/6 | Complete |
| 32. Intent Graph Migration | 5/5 | Complete |
| 33. RAG Context Build and Claim Verification | 9/9 | Complete |
| 34. Approval and ActionDraft Boundary Hardening | 6/6 | Complete |
| 35. Replay and Eval Hardening | 6/6 | Complete |
| 35.1. v1.9 Milestone Readiness Closure | 1/1 | Complete |

Historical execution metrics are archived in milestone files and `.planning/MILESTONES.md`.
Latest planning metric: v1.9 archived on 2026-06-30 after Phase 35.1 completed formal verification artifacts, validation metadata refresh, requirements ledger reconciliation, and refreshed milestone audit.
| Phase 29.5 P01 | 35min | 2 tasks | 5 files |
| Phase 29.5 P02 | 5min | 2 tasks | 5 files |
| Phase 29.5 P03 | 34min | 2 tasks | 13 files |
| Phase 29.5 P04 | 6min | 2 tasks | 3 files |
| Phase 29.5 P05 | 55min | 2 tasks | 16 files |
| Phase 29.5 P06 | 2h 35min | 2 tasks | 14 files |
| Phase 30 P01 | 10min | 2 tasks | 5 files |
| Phase 30 P02 | 10min | 2 tasks | 5 files |
| Phase 30 P03 | 10min | 3 tasks | 6 files |
| Phase 32-intent-graph-migration P32-01 | 7min | 2 tasks | 3 files |
| Phase 32-intent-graph-migration P32-02 | 8min | 2 tasks | 6 files |
| Phase 32-intent-graph-migration P32-03 | 10min | 2 tasks | 6 files |
| Phase 32-intent-graph-migration P32-04 | 33min | 3 tasks | 13 files |
| Phase 32-intent-graph-migration P32-05 | 15min | 3 tasks | 3 files |
| Phase 33 P33-01 | 14min | 3 tasks | 11 files |
| Phase 33-rag-context-build-and-claim-verification P33-02 | 19min | 3 tasks | 12 files |
| Phase 33-rag-context-build-and-claim-verification P33-03 | 15min | 1 tasks | 5 files |
| Phase 33-rag-context-build-and-claim-verification P33-04 | 12min | 2 tasks | 7 files |
| Phase 33-rag-context-build-and-claim-verification P33-05 | 11min | 2 tasks | 10 files |
| Phase 33-rag-context-build-and-claim-verification P33-06 | 10min | 1 tasks | 6 files |
| Phase 33-rag-context-build-and-claim-verification P33-07 | 8min | 1 tasks | 5 files |
| Phase 33-rag-context-build-and-claim-verification P33-08 | 28min | 1 tasks | 16 files |
| Phase 33-rag-context-build-and-claim-verification P33-09 | 24min | 3 tasks | 9 files |
| Phase 34 P34-01 | 7 min | 2 tasks | 8 files |
| Phase 34 P34-02 | 18 min | 2 tasks | 7 files |
| Phase 34 P34-03 | 35 min | 2 tasks | 9 files |
| Phase 34 P34-04 | 17 min | 2 tasks | 3 files |
| Phase 34 P34-05 | 28 min | 2 tasks | 16 files |
| Phase 34 P34-06 | 24 min | 2 tasks | 3 files |
| Phase 35 P35-01 | 12 min | 2 tasks | 4 files |
| Phase 35 P35-02 | 23 min | 2 tasks | 4 files |
| Phase 35 P35-03 | 15 min | 2 tasks | 8 files |
| Phase 35 P35-05 | 8 min | 2 tasks | 6 files |
| Phase 35 P35-04 | 12 min | 2 tasks | 5 files |
| Phase 35 P35-06 | 13 min | 2 tasks | 3 files |

## Quick Tasks Completed

| Date | Quick ID | Task | Status |
|------|----------|------|--------|
| 2026-06-21 | 260621-lgq | MOCA memory long-term/case hardening | Complete |

## Accumulated Context

### Decisions

- v1.7 is scoped to Agent Console short-term memory unification, not a full memory product UI or long-term/case-memory redesign.
- Current `/agent-runs` is the user-facing Agent Console path and should be the implementation target.
- The legacy `/agent/chat` path is a compatibility/reference path; v1.7 should avoid introducing incompatible persistence semantics between the two paths.
- Memory context is contextual assistance only and must preserve established evidence, action, approval, and replay boundaries.
- v1.8 hardens the existing Phase 11 intent/clarification contract instead of replacing it with agent-selected routing.
- v1.9 starts a platform foundation milestone. Phase numbering continues from Phase 25 instead of restarting at Phase 1.
- v1.9 should implement a microservice-ready modular monolith, not physical microservice deployment.
- Full real external execution remains deferred; v1.9 only hardens action draft, approval, evidence, claim, and safety snapshot boundaries.
- 27-01 remains RED-only by design: planned production symbols are imported but no src/ files are edited.
- 27-01 seam integration tests use top-level src.platform imports so current failures are deterministic missing planned production modules, not local database setup.
- Preserved KnowledgeContext.merchant_scope as the existing list shape through project_merchant_scope_for_knowledge.
- Kept current search, agent route, graph node, and tool executor seam migration out of 27-02; 27-03 owns those call sites.
- Kept ToolCallContext safety_snapshot_ref and policy_snapshot_ref as compatibility fields only; target schema reconciliation remains Phase 29 scope.
- Graph config keeps legacy permissions, merchant_scope, trace_id, and session_id only as values derived from canonical trusted_context.
- Missing or invalid trusted_context in investigate/action_draft fails closed instead of falling back to AgentState authority.
- Approval resume grants action_draft permission through an explicit server_tool_permissions factory input, not through AgentState or request payload.
- Plan 30-01 introduced BusinessFactService beside BusinessToolService; BusinessToolService remains the compatibility facade for Plan 30-02 wrapping.
- Plan 30-01 returns typed unavailable BusinessFactResultV1 values for unsupported logistics and merchant-risk reads until real data support exists.
- Plan 30-01 BusinessFactService.fetch_context populates approved facts, refs, missing facts, and safe errors; ToolResultV2 compatibility wrapping remains deferred to Plan 30-02.
- BusinessToolService remains the source-compatible facade, but current business fact authority now flows through BusinessFactService.
- ToolPolicyEngine keeps requires_domain_scope_check for order/refund/ticket identifiers but redacts the identifier values from ToolInvocationOutcome serialization.
- BusinessToolExecutor constructs BusinessFactService explicitly and wraps it with BusinessToolService for ToolResultV2 compatibility.
- ToolResultProjector no longer treats result.data business identifiers as authoritative business refs.
- Investigate records non-success business results as safe errors only; denied resources do not create claim dependency refs.
- Prompt summaries and raw repository-row-shaped context receive explicit non-authority reason codes while BusinessFactRefV1 remains required.
- Phase 32 Plan 01 cataloged rag_context_build and claim_verify only as deferred_non_runnable Phase 33 target entries.
- Phase 32 Plan 01 kept legacy LangGraph node/router names as runtime/debug names and exposed target names through src.agent.graph_vocabulary.
- Phase 32 Plan 02 keeps LLM intent output candidate-only and records policy_owner=IntentPolicyRegistry on effective classifier traces.
- Phase 32 Plan 02 moved effective route, risk, precedence, direct-response, and required-slot decisions behind IntentPolicyRegistry and SlotPolicyRegistry APIs.
- Phase 32 Plan 03 moved required-slot completeness and inherited-slot acceptance behind SlotPolicyRegistry with explicit rejection reason codes.
- Phase 32 Plan 03 keeps slot_resolution_gate as additive extract_slots trace metadata rather than a physical graph node.
- Phase 32 Plan 04 treats target_merchant_context as sanitized evidence/status metadata only and not an AgentRun, trace, or replay authorization input.
- Phase 32 Plan 04 keeps target graph projection additive and leaves persisted AgentStep.node_name as the legacy implementation/debug value.
- Phase 32 Plan 05 keeps rag_context_build and claim_verify as deferred_non_runnable target names only; APF-13/APF-14 runnable behavior remains Phase 33-owned.
- Phase 33 Plan 01 keeps package/bundle payloads in Pydantic/state JSON surfaces; no DB schema, migration, endpoint, or event type was added.
- Phase 33 Plan 01 makes KnowledgeService the public owner of build_verified_context and verify_claims; graph nodes should call these service methods instead of assembling one-off ContextBuilder or MaterialClaimVerifier flows.
- Phase 33 Plan 01 keeps target DTOs in src/knowledge/schemas.py and uses rag_context compatibility adapters for legacy MaterialClaim authority_class payloads.
- Phase 32 Plan 05 machine-checks 32-MVP-TARGET-MAPPING.md against src.agent.graph_vocabulary to prevent target mapping drift.
- rag_context_build is the sole graph node writer for RAG package/status/map fields and delegates canonical validation to PolicyKnowledgeService.build_verified_context.
- route_after_rag_context is total, side-effect-free, and fail-closed for malformed state and hard package statuses.
- WorkingState retrieved evidence refs are projected only from verified_evidence_package evidence_map for verified or allowed partial packages.
- Phase 33 AgentState DTO imports must exist at runtime because LangGraph resolves TypedDict annotations with get_type_hints.
- recommendation_generation emits canonical MaterialClaimV1 dictionaries but does not verify support or write package/bundle fields.
- Legacy generate_recommendation source-node claims normalize to generated_from_step=recommendation_generation.
- recommendation_generation consumes only verified package prompt/evidence projections for policy context.
- Claim verification runs deterministic domain hard gates before Level 2 support decisions.
- ClaimVerificationBundleV1 claim_results preserve verifier rule_checks instead of collapsing them to a generic summary.
- Tenant public policy evidence cannot prove current business facts without merchant-scoped BusinessFactRefV1 / BusinessFactResultV1 authority.
- claim_verify is a narrow graph writer: it calls PolicyKnowledgeService.verify_claims and serializes only claim verification outputs plus compatibility verifier fields.
- route_after_recommendation routes material claims, proposed actions, and user-visible claim payloads to claim_verify instead of directly to risk.
- route_after_claim_verify sends verified continue bundles to risk only when a proposed action or risk signal exists; answer-only verified bundles go to final_response.
- Risk/action gates fail closed when proposed actions lack claim_verification_bundle authority.
- Safety snapshot evidence is sourced from safe_support_refs mapped through verified evidence maps, never candidate-only retrieved evidence.
- route_after_risk includes the same claim-bundle safety guard as defense-in-depth before approval routing.
- Blocked RAG package and claim bundle states render through sanitized insufficient-evidence/manual-review templates instead of recommendation draft text.
- Working-state evidence refs prefer claim bundle/state safe_support_refs, then package prompt_projection safe refs, and only fallback to verified evidence_map when no prompt-safe subset exists.
- Plan 33-08 centralized rag_claim_summary.v1 in src/agent/rag_claim_summary.py to avoid replay lifecycle import cycles and keep projection logic consistent.
- Plan 33-08 replay responses sanitize raw package/bundle/debug/verifier fields at projection time and return only the allowlisted summary.
- Plan 33-08 legacy/no Phase 33 responses use exclude_none so rag_claim_summary is omitted instead of fabricated with zero counts.
- Phase 32 static guards no longer assert that rag_context_build and claim_verify are deferred_non_runnable or absent from the graph.
- Phase 33 static guards now own runtime/runnable RAG and claim boundary checks.
- generate_recommendation remains a verified-package consumer and MaterialClaimV1 producer; claim_verify owns verifier route/blocking assertions.
- Semantic verifier coverage remains deterministic/mocked with no live provider requirement.
- Phase 34 binds action proposals, approval decisions, and action drafts to target merchant, business fact, evidence, claim, risk, payload hash, and safety snapshot material.
- risk_gate owns blocked/approval-required/auto-draft routing; approval_gate is now limited to approval-plan creation, trusted resume, interrupt, and revision state-machine behavior.
- ActionDraft remains demo-only in v1.9: no execution/outbox/reconciliation/compensation production surfaces were introduced, and final responses must not imply external side effects.
- Broad trace/run API projection hardening is explicitly Phase 35 scope; Phase 34 closed persistence and live approval-required projection safety.
- Phase 35 Plan 35-01 uses existing registered replay events plus payload/projection assertions for coverage matrix rows; no replay event type was added.
- Phase 35 Plan 35-01 enforces the six-plan Phase 35 shape by testing ROADMAP.md for exactly 35-01 through 35-06.
- Phase 35 Plan 35-01 treats MOCA pytest command discipline as a static contract for Phase 35 plan and matrix artifacts.
- Replay authorization proof is projection-only evidence and is not wired into trace, replay, or AgentRun authorization guards.
- Phase 35 keeps business-data run/trace/replay/status/evidence/stream access closed to owner/admin visibility, with stream execution still owner-only.
- Approval views, tool result records, memory, trace detail, run listing, and replay artifacts are tracked as unchanged non-widening regression surfaces.
- Phase 35 Plan 35-03 uses existing replay event types only; no replay registry, ORM constraint, or migration event-type expansion was introduced.
- Phase 35 Plan 35-03 approval expired timeline fixtures use the existing minimal-envelope approval event shape instead of treating approval lifecycle events as V3 operations.
- Phase 35 Plan 35-03 replay response projection preserves explicit null fields inside timeline events while omitting absent top-level rag_claim_summary.
- Monitoring metrics are schema/status artifacts only until production telemetry exists.
- The release smoke dataset is limited to three smoke references and is not release-scale statistical evidence.
- Release statistical readiness remains non-blocking for Phase 35 and is represented as statistical_gate_not_demonstrated.
- Phase 35 dev-contract eval gates are blocking phase-exit checks; release sample volume and production telemetry remain non-blocking references.
- Forbidden behavior cases are manifest-owned and point to concrete existing focused tests rather than broad statistical datasets.
- Replay-by-rerun checks are intentionally scoped to replay-owned code and the trace/replay API router to avoid false positives in legitimate runtime graph paths.
- Phase 35 closure records evidence only and introduces no new runtime code scope.
- Replay authorization proof remains projection-only; same-merchant trace/replay authorization expansion is reserved for a named post-Phase 35 phase.
- Arbitrary PII hidden inside otherwise safe free-text summaries remains a release/monitoring follow-up, not a Phase 35 dev-contract guarantee.

### Roadmap Evolution

- Phase 24.2 inserted after Phase 24: Unified Session Memory Bundle Read Path.
- Phase 24.3 inserted after Phase 24: Memory Write Isolation Policy and Observability MVP.
- Phase 24.4 inserted after Phase 24: Memory Eval MVP.
- Phase 25 added and completed: Intent routing safety hardening.
- Phase 26-35 added for v1.9 Agent Platform Foundation.
- Phase 35.1 added to close v1.9 milestone audit gates: missing formal verification artifacts, stale validation metadata, and MER-01 ledger reconciliation.

### Pending Todos

- No active pending todos remain in `.planning/todos/pending/` after `$gsd-cleanup`.
- Optional follow-up from v1.8 remains deferred: pin active slot `confidence` projection before confidence becomes a meaningful provenance field.

### Blockers / Concerns

- No active blockers.
- Resolved local GSD metadata drift: `init.new-milestone` now reads v1.9 as the current milestone and v1.8 as the latest completed milestone after ROADMAP/MILESTONES format repair. Old Phase 24/24.x/25 and completed v1.9 phase directories have now been archived into milestone-specific phase folders.

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-06-20:

| Category | Item | Status |
|----------|------|--------|
| deferred record | `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md` | future candidate only if Phase 17 is reintroduced |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |

Items acknowledged and deferred at milestone close on 2026-06-30:

| Category | Item | Status |
|----------|------|--------|
| planning todo | `2026-06-22-archive-old-phase-directories.md` | completed by `$gsd-cleanup` on 2026-06-30; archived Phase 24/24.x to `v1.7-phases`, Phase 25 to `v1.8-phases`, and Phase 26-35.1 to `v1.9-phases` |

## Last Archived Milestone Context

- v1.9 owned Phase 26 through Phase 35.1.
- All 19 v1.9 requirements are complete and archived in `.planning/milestones/v1.9-REQUIREMENTS.md`.
- Phase 35.1 closed readiness gaps without runtime source changes.
- MER-01 database hardening and same-merchant trace/replay authorization expansion remain future scope, not v1.9 blockers.

## Session Continuity

Last session: 2026-06-30T04:01:09.008Z
Stopped at: Phase 36 planned; ready for execution
Resume file: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-06-PLAN.md
Next: Run `$gsd-execute-phase 36`.

**Completed Phase:** 23 (RAG Reranker + Query Rewrite) — 6/6 plans complete; UAT 7/7 passed — 2026-06-20T10:33:42+08:00

**Completed Phase:** 24 (Agent Runs Short-term Memory Parity) — 9/9 plans complete; verification passed — 2026-06-20T23:32:39+08:00

**Completed Phase:** 24.2 (Unified Session Memory Bundle Read Path) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.3 (Memory Write Isolation Policy and Observability MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 24.4 (Memory Eval MVP) — 1/1 plans complete; verification passed — 2026-06-21

**Completed Phase:** 25 (Intent routing safety hardening) — 1/1 plans complete; review and verification passed — 2026-06-21T04:25:00Z

**Completed Phase:** 26 (Architecture Contract Baseline) — 1/1 plans complete; external review passed with warnings fixed — 2026-06-22T14:43:37Z

**Completed Phase:** 27 (TrustedContextFactory and Projections) — 3/3 plans complete; verification/security passed; UAT 6/6 passed — 2026-06-23T07:51:50+08:00

**Completed Phase:** 28 (Decision Event Foundation) — 1/1 plan complete; verification passed — 2026-06-23T10:15:32+08:00

**Completed Phase:** 29 (Tool Platform Boundary) — 4/4 plans complete; code review clean; UAT 6/6 passed; security `threats_open: 0`; Nyquist validation compliant — 2026-06-23T21:57:57+08:00

**Completed Phase:** 29.5 (Merchant Scope / Role Model Alignment) — 6/6 plans complete; focused suite `341 passed`; whole suite `1590 passed, 1 skipped`; static wildcard guard passed — 2026-06-27

**Completed Phase:** 30 (BusinessFactService Boundary) — 3/3 plans complete; verification passed; focused suite `190 passed`; code review warning fixed — 2026-06-27

**Completed Phase:** 31 (Memory Platform Boundary) — 6/6 plans complete; verification passed; focused suite `124 passed`; prior-phase regression `655 passed`; code review clean after fixes — 2026-06-28

**Completed Phase:** 32 (Intent Graph Migration) — 5/5 plans complete; verification passed; focused suite `267 passed`; static contract guards passed — 2026-06-28

**Completed Phase:** 33 (RAG Context Build and Claim Verification) — 9/9 plans complete; verification passed; code review warnings fixed; final focused suite `476 passed, 22 warnings`; static/focused/eval closure passed — 2026-06-29

**Completed Phase:** 34 (Approval and ActionDraft Boundary Hardening) — 6/6 plans complete; verification passed; final focused suite `400 passed, 22 warnings`; static/focused/ruff closure passed — 2026-06-29

**Completed Phase:** 35 (Replay and Eval Hardening) — 6/6 plans complete; code review clean after fixes; UAT 8/8 passed; security `threats_open: 0`; Nyquist validation compliant; aggregate Phase 35 suite `122 passed, 1 warning` — 2026-06-29

**Completed Phase:** 35.1 (v1.9 Milestone Readiness Closure) — 1/1 plan complete; v1.9 archived and phase artifacts archived — 2026-06-30

**Next Roadmap Item:** execute Phase 36

**Planned Phase:** 36 (Merchant-scope DB Hardening / Role Cleanup) — 6 plans — 2026-06-30T06:04:35.887Z
