---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: RAG Production Ingestion + OCR
current_phase: 21
status: executing
stopped_at: Completed 21-04-PLAN.md
last_updated: "2026-06-18T23:30:40.930Z"
last_activity: 2026-06-19 -- 21-04 verified provenance lookup and safe trace reporting complete
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 9
  completed_plans: 6
  percent: 67
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-18)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 21 RAG Production Ingestion + OCR — executing

## Current Position

Phase: 21 of 21 (RAG Production Ingestion + OCR) — EXECUTING
Plan: 7 of 9
Plans: 6/9 complete
Status: Ready to execute 21-04a-PLAN.md
Last activity: 2026-06-19 -- 21-04 verified provenance lookup and safe trace reporting complete

Progress: [███████░░░] 67%

Planning files:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`

## Completed Baseline

Phase 7 Contract Baseline completed on 2026-06-06.

- Artifacts: `.planning/milestones/v1.1-phases/07-contract-baseline/`
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
- Phase 16 and Phase 17 remain named owner phases but do not block the v1.1 MVP readiness gate.
- Phase 15.1 Memory Foundation V2 is inserted before Phase 16 to solve conversation log, working memory, short-term summaries, ContextAssembler, tool result layering, token budgeting, and trace/audit/conversation ID alignment without implementing long-term memory or case memory retrieval.
- Phase 15.2 v1.1 Readiness Closure is inserted after Phase 15.1 and before Phase 16 to close milestone audit evidence gaps without expanding runtime scope.
- Phase 15.2 adds formal Phase 7 and Phase 10 verification artifacts and records tenant-over-global global/default fallback as target-state `DEFERRED_WITH_OWNER` to post-Phase 17 `Policy Scope`.
- v1.2 is Long-term / Case Memory and is scoped to Phase 16 only.
- Phase 16 remains the single owner phase for memory_identity.v1, reviewed long-term memory, reviewed case memory, tombstones, memory write events, and prompt context integration.
- Phase 17 remains deferred for External Action Execution; v1.2 does not renumber or absorb external execution/outbox/reconciliation/compensation scope.
- v1.2 memory is contextual assistance only and cannot become policy evidence, approval/action authority, current business fact, or replay/audit truth.
- Phase 15.1 Plan 01 stores conversation facts in dedicated conversation/tool/summary tables while business tables, policy KB, approval/action tables, and replay remain authoritative for their own domains.
- ConversationService rejects raw prompt/tool payload, private reasoning, and approval/action authority keys before append.
- Phase 15.1 Plan 01 reserves nullable case_id only; long-term memory, case retrieval, tombstones, embeddings, and vector retrieval remain Phase 16-owned.
- Memory foundation schema rollback target is 010_replay_event_v3, with disposable DB downgrade/re-upgrade verification recorded in 15.1-MIGRATION-REPORT.md.
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
- Phase 15 Plan 01 keeps existing actor/resource_refs/redacted_payload storage names and projects ReplayEventV3 through the replay schema layer.
- Phase 15 Plan 01 deferred execution_id because Phase 17 action_executions storage does not exist yet.
- Phase 15 Plan 02 routes legacy minimal event emission through ReplayService while preserving minimal_event_envelope.v1 compatibility.
- Phase 15 Plan 02 keeps advisory-lock plus max(sequence)+1 as the shared allocator and explicitly defers lifecycle/finalizer coverage to 15-04 and external worker coverage to Phase 17.
- Minimal and context-less historical rows remain pairing_status=unresolved; no projection path rewrites stored rows.
- Non-operation V3 lifecycle/audit events project pairing_status=not_applicable instead of being mislabeled unresolved.
- V3 operation writes now fail closed when operation_id or positive attempt is missing.
- RunLifecycleService owns run_status_changed replay event appends; AgentRun remains the durable run-status source of truth.
- Approval respond/needs-info appends interrupted with reason_code=needs_info_response and never emits completed.
- ApprovalSlaScanner remains disabled by default; active enablement stays deferred to post-Phase 15 SLA Scanner Enablement.
- /replay uses ReplayService.get_replay and reads agent_trace_events ordered by sequence instead of legacy TraceRepository.build_timeline.
- /trace remains the legacy rollback/debug fallback and continues using TraceRepository.build_timeline.
- ReplayResponseV3 timeline entries are strict ReplayEventV3 items, so retention_class remains append/projection metadata outside the response contract.
- Phase 15 Plan 06: action_draft_created remains draft-only and projects DraftOutcomeV1 in redacted replay payloads.
- Phase 15 Plan 06: external execution/outbox/reconciliation/compensation and action_execution_* remain Phase 17-owned deferrals.
- Phase 15 Plan 06: /trace remains rollback fallback through TraceRepository.build_timeline while /replay stays event-store-first.
- Phase 15.1 Plan 02 wires tool call/result persistence in investigate because ToolManager.invoke() does not own database session access.
- Phase 15.1 Plan 02 stores tool argument summaries plus SHA-256 argument hashes, not raw argument bodies.
- Phase 15.1 Plan 02 keeps raw result storage as nullable ref/hash only and introduces no blob table or object-storage surface.
- Phase 15.1 Plan 03 keeps AgentState as runtime/checkpoint state and introduces WorkingStateV1 only as a prompt-safe projection.
- WorkingStateV1 may expose compact refs/summaries, but excludes raw business context, policy text, ToolResultV2 data, trace/debug blobs, LLM outputs, approval authority bodies, action payloads, safety snapshots, and hashes.
- `project_working_state()` is the current single projector from AgentState into WorkingStateV1; ContextAssembler wiring remains Plan 05-owned.
- Phase 15.1 Plan 04: ThreadRollingSummaryService owns source-range thread rolling summaries and writes only summaries rows.
- Phase 15.1 Plan 04: session_memories remains Phase 12 slot continuity; thread summaries do not mutate active_slots_json, session_summary, unresolved_questions_json, or last_intent.
- Phase 15.1 Plan 04: Phase 16 case memory, embeddings, tombstones, vector retrieval, and case precedent search remain unimplemented.
- Phase 15.1 Plan 04: load_prompt_context returns latest committed prior-turn thread_rolling summary plus bounded recent conversation messages and tool prompt summaries.
- Phase 15.1 Plan 05: token budgeting protects system prompt, current user message, safety constraints, business IDs, and policy refs before lower-priority context.
- Phase 15.1 Plan 05: ContextAssembler owns prompt block assembly and token budgeting without repository imports or raw prompt persistence.
- Phase 15.1 Plan 05: slot extraction uses PromptAssembly for current user text plus bounded candidate-slot hints, without synthetic thread/tool context injection.
- Phase 15.1 Plan 05: recommendation and risk nodes load prior-turn prompt context only when RunnableConfig provides session and run context.
- Phase 15.1 Plan 06 aligns conversation/tool/replay/audit refs using safe IDs and keeps ReplayService raw-key guards unchanged.
- Phase 15.1 final defers Phase 16 long-term memory write gate, memory tombstones, user-manageable memory, case memory vector search, and case precedent retrieval; Phase 17 owns external action execution storage, outbox/execution reconciliation, and compensation workflow.
- Phase 15.2 final readiness closure passed a focused suite with 181 tests and leaves Phase 16/17 runtime scope untouched.
- v1.1 archived on 2026-06-17. `.planning/REQUIREMENTS.md` was removed at archive time and then recreated with fresh v1.2 requirements.
- Phase 16 Plan 01 keeps `memory_identity.v1` helpers in `src/memory/identity.py` because normalization and source-ref allowlists are memory-domain rules.
- Phase 16 Plan 01 adds `MemorySourceRefV1` now so downstream tombstone/source fallback code uses the same authoritative typed key set.
- Phase 16 Plan 01 candidate hashes accept only stable envelope fields and reuse `content_hash` / `source_identity_hash`, excluding raw payloads and authority-bearing bodies.
- Phase 16 Plan 02 uses separate durable long-term/case/tombstone/write-event memory tables instead of overloading session_memories.
- Phase 16 Plan 02 uses PostgreSQL/pgvector Vector(1024) plus HNSW index for reviewed case memory embeddings.
- Approve/reject review paths use the existing memory_write_events decision enum: decision=write/reason_code=approved and decision=skip/reason_code=rejected.
- Explicit, admin, human-reviewed, deterministic tool, confirmed outcome, and approved approval-state sources may auto-approve when PII is not prohibited.
- Long-term retrieval returns bounded LongTermMemoryView values and excludes tombstoned rows by content hash or source identity.
- LLM, semantic, summary, cross-case pattern, and behavior inference candidates are persisted only as needs_review and are excluded from retrieval.
- Semantic Episode remains a candidate-only projection layer and does not create an authoritative semantic episode table.
- SemanticEpisodeCandidate converts to LongTermMemoryWriteCandidate with source_type=semantic_episode_candidate so existing long-term memory policy forces needs_review.
- Projection output keeps prompt-safe summaries and ignores raw payload, policy text, evidence refs, authority bodies, and replay/debug blobs.
- Semantic episode projection has no repository dependency and does not mutate session_memories.
- Forget/delete create active tombstone identities while keeping existing delete event semantics for delete_memory.
- Tombstone matching uses canonical content_hash first, then allowed source_identity_hash fallback, with no semantic similarity path.
- Supersede marks the previous row superseded/non-current, inserts a current replacement, links supersedes/superseded_by, and emits decision=supersede.
- Case review approve/reject events use the existing memory_write_events decision enum: decision=write/reason_code=approved and decision=skip/reason_code=rejected.
- Reviewed case memory returns fixed prompt-safe precedent fields only and does not import or emit policy evidence contracts from src/memory.
- Case retrieval applies tenant/scope/status/deletion/expiry/PII/case-type/policy/tombstone filters before pgvector scoring.
- Memory prompt blocks remain non-protected; profile_memory and case_memory are added to BlockName but not PROTECTED_BLOCK_NAMES.
- ContextAssembler caps combined profile/case memory prompt text at 1600 chars before adding prompt blocks.
- Case memory prompt refs prioritize compact source and policy identifiers, including business_object_id, while excluding EvidenceRefV1, hashes, raw payloads, and authority bodies.
- [Phase 16]: Reviewed memory retrieval fails closed: unavailable services, missing dependencies, or empty reviewed rows never claim continuity. — Plan 16-08 threat model requires safe empty behavior without false continuity.
- [Phase 16]: Graph state receives only prompt-safe allowlisted memory snippets, not raw ORM rows or authority-bearing payloads. — Reviewed memory must remain contextual assistance only and cannot become evidence or action authority.
- [Phase 16]: Prompt nodes pass reviewed memory through ContextAssembler while preserving policy evidence, tool summaries, and business context as separate authority sources. — This keeps memory context below the existing evidence/business/action safety boundaries.
- Phase 16 Plan 09 routes planner-visible `search_case_memory` to reviewed case memory and keeps session-derived precedent search legacy/debug-only.
- Phase 16 Plan 09 updated stale cross-phase guards after v1.1 archive and intentional Phase 16 schema creation; full suite passed with 974 tests.
- Phase 16 coverage manifest lists all 14 v1.2 requirement IDs and is guarded by `tests/memory/test_phase16_requirement_coverage.py`.
- Phase 20 keeps `PolicyChunk.content` as canonical citation text and stores retrieval-only `search_text` plus generated `search_vector` for PostgreSQL full-text search.
- Phase 20 fuses dense, sparse, and fuzzy retrieval candidates with RRF, while `EvidenceRefV1.score` and `KnowledgeSearchResult.best_score` remain normalized 0-1 confidence values.
- Phase 20 hybrid trace fields stay internal/eval-only and are excluded from API serialization; they do not enter `EvidenceRefV1` or prompts.
- Wave 0 records validation coverage for all Phase 21 requirements but does not mark the product requirements implemented.
- Implementation-pending Phase 21 behavior uses strict xfail markers with owner_task=21-* reasons and PHASE21_XFAIL_OWNERS entries.
- Native OCR behavior uses explicit pytest.importorskip/preflight instead of silent pass-through when pytesseract/Tesseract is unavailable.
- Phase 21 Plan 01: Markdown and plain-text adapters emit synthetic block IDs as doc_key:source_type:synthetic:0000-style identifiers.
- Phase 21 Plan 01: Hidden Markdown comments, control characters, local paths, raw parser dumps, and debug payload markers are excluded from ParsedBlock text and represented by safe warning codes.
- Phase 21 Plan 01: PDF, DOCX, and image source types are allowlisted for registry resolution, but parsing remains fail-closed until later native adapter plans register implementations.
- Phase 21 Plan 01a keeps PolicyDocument.policy_version_fingerprint as a dedicated nullable column, separate from parser_metadata_json.
- Phase 21 Plan 01a stores ordered source-block refs and OCR metadata on PolicyChunk while preserving EvidenceRefV1 and canonical evidence projection.
- Phase 21 Plan 01a source-block and ingestion-job repositories are tenant-scoped AsyncSession repositories with no independent commits.
- Phase 21 Plan 01a scope guards allow existing v1.3 query_rewrite/rerank compatibility names only at known sites and forbid new Phase 22/23/RAG-5 implementation surfaces.
- Phase 21 Plan 02 keeps chunk_markdown stable and adds BlockChunkResult/chunk_blocks as the parser-block path.
- Phase 21 Plan 02 stores policy version authority only in PolicyDocument.policy_version_fingerprint; parser_metadata_json remains trace/debug-only.
- Phase 21 Plan 02 keeps source/table/heading context retrieval-only in PolicyChunk.search_text; EvidenceRefV1.text_hash still hashes chunk.content.
- Phase 21 Plan 02 schema edge: first-import pre-document failures return safe job_id=None because RagIngestionJob.doc_id is non-null and no PolicyDocument id exists yet.
- Use exact parser/OCR pins as a Phase 21 local ingestion reproducibility exception.
- Mock native OCR availability in tests while preflight returns deterministic chi_sim/eng/executable failure states.
- Store OCR confidence only in block/chunk metadata; retrieval score contracts remain unchanged.
- ParserRegistry native-adapter wiring remains a scoped follow-up because registry.py was outside 21-03 write scope.
- Source provenance is internal maintainer/debug data and is returned only after tenant, unique-key, and canonical text-hash verification.
- Safe ingestion reports always project exactly the allowed fields and recursively drop raw payload, path, stack, parser dump, private reasoning, and authority-body keys.
- Wave 0 xfails were removed only for 21-04-owned provenance/report behavior; 21-04a-owned boundary xfail remains.

## Accumulated Context

### Roadmap Evolution

- Phase 15.1 inserted after Phase 15: Memory Foundation V2 (URGENT). It is a pre-Phase 16 foundation phase for conversation log, WorkingStateV1, short-term thread summaries, ContextAssembler, tool result storage, token budgeting, and trace/audit/conversation ID alignment. It explicitly does not implement Phase 16 long-term memory, tombstones, user-manageable memory, case memory vector search, or case precedent retrieval.
- Phase 15.2 inserted after Phase 15.1: v1.1 Readiness Closure (URGENT). It closes formal verification and owner-disposition gaps from the milestone audit before Phase 16 planning.
- v1.2 starts after v1.1 archive with fresh requirements in `.planning/REQUIREMENTS.md` and a one-phase roadmap for Phase 16 Long-term / Case Memory.
- v1.3 RAG Hybrid Retrieval shipped and archived on 2026-06-18 with Phase 20 completed.
- v1.4 RAG Production Ingestion + OCR is active as the single Phase 21 roadmap phase. Research work packages 21.1-21.5 are planning slices, not roadmap phases; Phase 22, Phase 23, and Phase RAG-5 remain deferred.

### Pending Todos

- [ ] Constrain AgentState memory expansion - `.planning/todos/pending/2026-06-17-constrain-agentstate-memory-expansion.md`

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-06-18:

| Category | Item | Status |
|----------|------|--------|
| todo | 2026-06-17-constrain-agentstate-memory-expansion.md | pending |

## Blockers / Concerns

- Every phase plan must preserve coverage-matrix and follow-up-register visibility.
- Relevant `MISSING` rows block execution.
- Phase 13 must keep the active SLA scanner as an explicit owned follow-up gate.
- Phase 15.1 must not weaken ReplayEventV3 redaction rules by turning trace events into raw conversation/tool payload storage.
- Phase 16/17 deferral must not weaken Phase 12 session-memory fallback or Phase 14 demo action safety.
- Phase 16 planning must read `docs/contract-spec.md`, `docs/phase-13-17-architecture-plan.md`, and `docs/current-implementation-map.md` before choosing implementation details.
- Any Phase 16 schema migration must include downgrade/rollback preflight strategy and tests for duplicate or tombstone-sensitive data where applicable.
- Long-term/case memory must stay separate from session memory, policy evidence, current business data, approval authority, action authority, and replay/audit truth.

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
| 15 | 01 | 12 min | 3 | 7 |
| 15 | 02 | 17 min | 2 | 8 |
| Phase 15 P03 | 17 min | 2 tasks | 6 files |
| Phase 15 P04 | 22 min | 3 tasks | 12 files |
| Phase 15 P05 | 11 min | 2 tasks | 4 files |
| Phase 15 P06 | 36 min | 3 tasks | 6 files |
| 15.1 | 01 | 17 min | 4 | 11 |
| Phase 15.1 P02 | 11 min | 3 tasks | 6 files |
| Phase 15.1 P03 | inline | 3 tasks | 4 files |
| Phase 15.1 P04 | 21 min | 4 tasks | 7 files |
| Phase 15.1 P05 | 12 min | 3 tasks | 12 files |
| Phase 15.1 P06 | 20 min | 3 tasks | 6 files |
| 16 | 01 | 6 min | 3 | 3 |
| 16 | 02 | 10 min | 4 | 3 |
| 16 | 03 | 10 min | 4 | 5 |
| Phase 16 P04 | 6 min | 2 tasks | 2 files |
| Phase 16 P05 | 14 min | 4 tasks | 5 files |
| 16 | 06 | 12 min | 4 | 4 |
| 16 | 07 | 6 min | 3 | 4 |
| 16 | 08 | 10 min | 3 | 8 |
| 16 | 09 | 24 min | 4 | 14 |
| 20 | 01 | 1h 10m | 6 | 13 |
| 21 | 00 | 8m 48s | 3 | 12 |
| Phase 21 P01 | 12m | 1 tasks | 10 files |
| Phase 21 P01a | 10 min | 2 tasks | 8 files |
| Phase 21 P02 | 19 min | 3 tasks | 10 files |
| Phase 21 P03 | 16 min | 3 tasks | 15 files |
| Phase 21 P04 | 9m 29s | 2 tasks | 10 files |

## Session Continuity

Last session: 2026-06-18T23:30:40.922Z
Stopped at: Completed 21-04-PLAN.md
Resume file: None
Next: Continue with `21-04a-PLAN.md`.

**Archived Milestone:** v1.1 Agent Architecture Migration — shipped 2026-06-17
**Completed Milestone:** v1.2 Long-term / Case Memory — shipped 2026-06-17
**Archived Milestone:** v1.3 RAG Hybrid Retrieval — shipped 2026-06-18

**Completed Phase:** 20 (RAG Hybrid Retrieval) — 1 plan — UAT/security verified 2026-06-18
**Current Phase:** 21 (RAG Production Ingestion + OCR) — executing

**Planned Phase:** 21 (RAG Production Ingestion + OCR) — 9 plans — 2026-06-18T15:36:45.369Z
