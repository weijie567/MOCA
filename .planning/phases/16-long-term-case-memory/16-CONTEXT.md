# Phase 16: Long-term / Case Memory - Context

**Gathered:** 2026-06-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 16 implements reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 conversation/context foundation.

This phase owns `memory_identity.v1`, safe long-term/case memory schema, tombstones, memory write events, review lifecycle, retrieval predicates, reviewed case precedent retrieval, and bounded `ContextAssembler` integration.

Memory remains contextual assistance only. It must not become policy evidence, approval/action authority, current business truth, replay/audit truth, or a replacement for `session_memories`.

</domain>

<decisions>
## Implementation Decisions

### Memory Family And Schema Boundary

- **D-01:** Use a memory-family contract with separate tables. Share `memory_identity.v1`, tombstone, review, and write-event semantics across memory types, but keep `long_term_memories` and `case_memories` as separate tables.
- **D-02:** Do not use a single generic memory table for long-term profile facts, case precedents, preferences, and strategy patterns. It would blur the boundary between preferences, precedents, and future strategy memory.
- **D-03:** Do not expand `session_memories` into long-term memory. `session_memories` stays scoped to same-thread slot continuity, intent continuity, unresolved questions, and lightweight session state.

### Semantic Episode Layer

- **D-04:** Introduce a Semantic Episode Layer as short-term memory V2's semantic enhancement layer. It is separate from `session_memories`, working memory, and raw conversation log.
- **D-05:** Semantic episode data is derived from `conversation_messages`, `tool_results`, `summaries`, and future case outcomes. It may contain candidate cross-case patterns, similar-case hints, strategy hints, and preference candidates.
- **D-06:** Semantic episode output is a candidate/interpretation layer only. It does not become business truth, policy evidence, approval/action authority, or reviewed case memory.
- **D-07:** For Phase 16 planning, prefer a minimal semantic extension through `summaries.summary_type` / `summary_json` conventions or an independent extractor projection. Do not build a heavy new authoritative semantic-episode fact store unless planning proves it necessary.

### Write Sources And Review Lifecycle

- **D-08:** Use a three-channel write model.
- **D-09:** Deterministic facts may auto-approve when they come from structured successful tool results, confirmed business outcomes, explicit policy-version-compatible decisions, or final human-approved approval state.
- **D-10:** Explicit user preferences may auto-approve when the user clearly asks the system to remember a stable preference, but they must remain deletable through tombstones.
- **D-11:** LLM candidates, semantic episode candidates, summaries, cross-case pattern mining, similarity inference, and behavior inference must enter `needs_review`. They cannot directly become retrievable memory.
- **D-12:** `review_status` is the only DB lifecycle status. The allowed status set is `auto_approved`, `needs_review`, `approved`, `rejected`, `superseded`, `tombstoned`, and `deleted`.
- **D-13:** "Published" is not a DB status. It is a retrieval predicate: `review_status in ('auto_approved', 'approved')`, not tombstoned, not deleted, not expired or prohibited, scope allowed, and version compatible.
- **D-14:** `draft` may exist as a candidate/write-event concept before a durable reviewed row, but downstream retrieval must not treat draft candidates as usable memory.

### Retrieval Strategy

- **D-15:** Use different retrieval strategies for profile memory and case memory.
- **D-16:** Long-term profile memory is predicate-only. Retrieve by tenant, scope, memory kind, review status, freshness/expiry, tombstone state, and allowed visibility. Do not use pgvector for profile memory in Phase 16.
- **D-17:** Case memory uses metadata-first + pgvector. First apply hard filters for tenant, approved status, tombstone/deletion, case type, policy family/version compatibility, and expiry; then run pgvector semantic top-k.
- **D-18:** Case memory MVP uses light reranking, not full hybrid/RRF. Initial scoring may combine semantic similarity, policy match, and recency, for example `0.6 * semantic_similarity + 0.2 * policy_match + 0.2 * recency`.
- **D-19:** Do not implement full dense + lexical + RRF hybrid retrieval in Phase 16 MVP. Leave it as a future retrieval-quality expansion after baseline predicates and pgvector case retrieval are safe.

### ContextAssembler Integration

- **D-20:** Memory is an interpretation layer, not a truth layer. It must be injected after policy/business/tool facts and before recent messages.
- **D-21:** Use the prompt order: system prompt, safety constraints, business IDs/state, policy refs, working state, thread rolling summary, profile constraints, case precedents, recent messages, tool summaries, current user query.
- **D-22:** Recent messages and the current user query must be able to override memory. Memory must not override current user instructions, current business state, policy evidence, or tool results.
- **D-23:** Profile memory enters prompt only as bounded constraints/preferences. Case memory enters only as reviewed precedent excerpts.
- **D-24:** Memory injection uses strict small blocks. Profile memory max 3 items, each 150-200 chars. Case memory max 3 items, each with fixed fields: `excerpt`, `applicability`, `outcome`, and `caveats`.
- **D-25:** Total memory block hard limit is 1600 chars. Tests must assert profile count, case count, total memory chars, and no raw payload/authority-object leakage.

### Legacy Case Search And Tombstone Semantics

- **D-26:** Quarantine the existing `search_case_memory` path as legacy/session-derived heuristic. It must not claim to be reviewed case memory.
- **D-27:** Add a new reviewed case retrieval service/path, such as `reviewed_case_memory.retrieve()` or `CaseMemoryService.retrieve_reviewed()`. Production prompt context must read the reviewed store, not the legacy session projection.
- **D-28:** During transition, legacy search may remain debug/fallback only. It should be renamed or clearly marked legacy in tool registry and documentation. Later v2 cleanup may delete it after validation.
- **D-29:** Tombstone no-rewrite uses two exact identity layers. First match canonical identity `(tenant_id, memory_type, scope_type, scope_id, content_hash)`. If content hash is missing or a candidate is reconstructed, match normalized source identity.
- **D-30:** Source identity fallback uses the authoritative `MemorySourceRefV1` typed key set: `source_type`, `run_id`, `event_id`, `conversation_message_id`, `tool_result_id`, `agent_run_id`, `business_object_type`, `business_object_id`, `policy_version`, and `outcome_id`. Unknown arbitrary JSON keys must be rejected before identity hashing and must not participate in identity matching.
- **D-31:** If canonical or source identity matches an active tombstone, the candidate write must be skipped or write-blocked in the same transaction and emit `memory_write_event(reason_code='tombstone_match')`.
- **D-32:** Tombstone matching must not use semantic similarity. Similarity-based deletion is too broad and is not auditable enough for no-rewrite semantics.

### the agent's Discretion

- Exact module/file naming may follow local code conventions during planning.
- Exact pgvector index parameters and score normalization constants may be refined by research, as long as the selected MVP remains metadata-first + pgvector + light rerank.
- Planner may choose whether the Semantic Episode Layer is represented by new `summary_type` values, new extractor code, or prompt-safe projection helpers, as long as it does not alter `session_memories` semantics.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Requirements

- `.planning/ROADMAP.md` — Phase 16 goal, success criteria, planning prerequisites, and deferred boundaries.
- `.planning/PROJECT.md` — v1.2 milestone scope and the rule that memory remains contextual assistance only.
- `.planning/REQUIREMENTS.md` — `MEMID-01`, `MEMSCHEMA-01`, `LONGMEM-*`, `CASEMEM-*`, `TOMBSTONE-*`, `MEMCTX-*`, `MEMREVIEW-01`, and `MEMEVAL-01`.
- `.planning/STATE.md` — current milestone state, prior v1.1 decisions, and Phase 16 planning blockers/concerns.

### Normative Contracts

- `docs/contract-spec.md` §13 — memory layer semantics, long-term memory, case memory, write policy, identity profile, correction/supersede, storage, and retrieval predicates.
- `docs/contract-spec.md` §14 — prompt priority and fact precedence.
- `docs/contract-spec.md` §18.1 — memory target schema, indexes, constraints, tombstone matching, and correction/supersede transaction rules.
- `docs/phase-13-17-architecture-plan.md` Phase 16 — required package shape, tables, identity-first implementation, deletion/quarantine rules, and gate tests.

### Migration And Test Gates

- `docs/migration-plan.md` Phase 16 and migration rollout protocol — schema ownership, rollback/read-switch rules, coverage matrix expectations, and migration hygiene.
- `docs/eval-test-plan.md` §20.1 — long-term/case memory lifecycle tests, forbidden behavior, tombstone no-rewrite, scope isolation, and supersede rollback coverage.

### Current-State And Design References

- `docs/current-implementation-map.md` — current-state notes about session memory, legacy `search_case_memory`, empty long-term adapter, and prompt-context gaps. Treat this file as a static map that may lag Phase 15.1; verify against live code during planning.
- `docs/phase16设计参考.md` — user-provided Phase 16 design reference for reviewed case memory, Semantic Conversation Understanding, metadata-first retrieval, tombstone semantics, and migration from transitional `search_case_memory`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/common/canonical_hash.py` — existing canonical hashing precedent. Phase 16 should align `memory_identity.v1` with the project's canonical JSON/hash style while preserving memory-specific normalization rules.
- `src/db/models.py` — existing SQLAlchemy models include `SessionMemory`, `ConversationThread`, `ConversationMessage`, `ToolCallRecord`, `ToolResultRecord`, `ConversationSummary`, `PolicyChunk` with pgvector, `AgentTraceEvent`, approval/action tables, and replay-safe event storage.
- `src/db/migrations/versions/011_memory_foundation_v2.py` and `012_thread_user_scope.py` — Phase 15.1 conversation/tool/summary foundation and scoped thread uniqueness. Phase 16 migrations should build after this foundation.
- `src/memory/service.py`, `src/memory/repository.py`, and `src/memory/schemas.py` — current session-memory implementation and CAS/TTL patterns. Do not extend this into long-term/case memory semantics.
- `src/memory/thread_summary.py` — deterministic thread rolling summary service. Useful input for semantic episode candidates, but not a reviewed memory store.
- `src/memory/search.py` and `src/tools/executors/memory.py` — current legacy session-derived `search_case_memory` path. Must be quarantined or renamed.
- `src/agent/nodes/long_term_memory_retrieve.py` — empty adapter seam that Phase 16 can replace with real retrieval once reviewed memory predicates exist.
- `src/agent/context/assembler.py`, `src/agent/context/projectors.py`, and `src/agent/context/budget.py` — prompt assembly, projection, and budget enforcement entry points for memory injection.
- `src/agent/working_state.py` — strict prompt-safe `WorkingStateV1`. Phase 16 may add memory refs/snippets only through bounded prompt-safe fields or assembler inputs, not raw records.
- `src/conversation/service.py` and `src/conversation/repository.py` — prompt context loading over conversation messages, thread summaries, and tool prompt summaries.

### Established Patterns

- PostgreSQL is the authoritative persistence layer for memory, replay, approvals, actions, and business state. Redis must not become authoritative memory.
- Runtime state, business facts, policy evidence, approval/action state, replay truth, and memory are separate authority domains.
- Prompt-facing projections are explicit and bounded. Raw tool payloads, raw prompts, private reasoning, hashes, safety snapshots, approval/action authority bodies, and replay/debug blobs are excluded from prompt-safe views.
- Migrations follow expand -> backfill/verify -> read-switch -> enforce -> rollback/cleanup discipline.
- Tests favor contract boundaries, negative authority-boundary cases, migration rollback/preflight checks, and prompt-safety assertions.

### Integration Points

- Add Phase 16 schema in a new Alembic migration after `012_thread_user_scope`.
- Add memory identity helpers under `src/memory/` or `src/common/` only if they are truly shared; memory-specific identity rules should stay in the memory domain.
- Add long-term/profile and case-memory repository/service boundaries under `src/memory/`.
- Replace or extend `long_term_memory_retrieve` only after predicates, tombstone checks, and prompt-safe projections exist.
- Extend `ContextAssembler` with dedicated profile-memory and case-memory blocks, preserving protected policy/business/current-user blocks.
- Update tool catalog/executor behavior so legacy `search_case_memory` cannot be mistaken for reviewed case memory.
- Add tests under `tests/memory/`, `tests/agent/context/`, and relevant agent/tool tests for identity, retrieval predicates, tombstone no-rewrite, legacy quarantine, and prompt budget.

</code_context>

<specifics>
## Specific Ideas

- Short-term memory should become two layers: existing Session Slot Memory plus a separate Semantic Episode Layer.
- Semantic Episode Layer can include `cross_case_patterns`, `similar_cases`, `strategy_hints`, and `user_behavior_pattern`, but these are candidate/interpretation fields only.
- Case memory prompt shape should be compact and fixed:
  - `excerpt`
  - `applicability`
  - `outcome`
  - `caveats`
- Long-term profile memory is a structured constraint/preference system and should not use embedding retrieval in Phase 16.
- Case memory is the semantic precedent system and should use pgvector after hard filters.
- Prompt ordering principle: `FACT FIRST -> CONTEXT -> MEMORY -> HISTORY -> USER`.

</specifics>

<deferred>
## Deferred Ideas

- Full hybrid retrieval with dense + lexical + RRF — future retrieval-quality expansion after predicate and pgvector baseline is safe.
- Full user/admin memory management UI — future Memory UX milestone.
- Reviewed preference memory and reviewed strategy pattern sibling stores beyond the Phase 16 baseline — future v2 expansion unless Phase 16 planning proves a minimal table is required.
- Deleting the legacy `search_case_memory` tool entirely — defer until after reviewed retrieval is validated and compatibility impact is known.

</deferred>

---

*Phase: 16-long-term-case-memory*
*Context gathered: 2026-06-17*
