# Phase 46: Session Context Repositioning - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Source:** `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-1, Phase 44/45 memory decisions, codebase scout, and conservative defaults from MEM-03.

<domain>
## Phase Boundary

Phase 46 repositions the existing `session_memories` layer after Case Working Context (CWC) has landed.

This phase is a boundary-locking and compatibility phase. Its job is to make `session_memories` explicitly mean same-thread, short-lived conversational continuity, not current-case durable state, reviewed precedent, tenant preference memory, policy evidence, business-fact authority, approval/action authority, or replay truth.

In scope:
1. Document and test-lock the role of `session_memories` as thread-scoped temporary context.
2. Audit existing session-memory read/write behavior and either leave it unchanged with explicit contract tests or make small migration-safe narrowing edits if the current behavior violates the new boundary.
3. Lock the separation between `session_context`, CWC, reviewed `case_memory`, and narrow long-term preference memory.
4. Add static/contract tests preventing session memory from becoming an authority surface or a cross-case durable state store.
5. Carry Phase 47 / Phase 48 defers forward by name.

Out of scope:
- New schema migrations unless planning proves a concrete existing table-shape defect.
- Destructive rename/drop/retype of `session_memories`, `case_memories`, `long_term_memories`, `case_working_contexts`, or `conversation_threads.case_id`.
- Rewriting CWC lifecycle behavior from Phase 45.
- Closed-case precedent generation or metadata-first precedent retrieval changes; those belong to Phase 47.
- Explicit tenant preference memory write path; that belongs to Phase 48.
- ReAct / graph-node architecture refactor.
- Adding a graph-global `active_slots` writer from `investigate`.

## Current Code Shape

The codebase already mostly matches the intended Phase 46 boundary:

- `SessionMemoryRepository.get_active(...)` and `session_memories` are keyed by `tenant_id`, `user_id`, and `thread_id`; there is no `case_id` column on `session_memories`.
- `MemoryService.load_session_memory(...)` loads same-thread continuity, filters expired slots, filters intent-incompatible slots, and marks inherited slots as `trusted_session_memory` metadata rather than current-turn explicit input.
- `MemoryWriteService.propose_candidates(...)` defaults to a session candidate only; long-term/case candidates require explicit `state.memory_write_candidates` input.
- `SessionMemoryBundleService` combines same-thread prompt context, rolling summary, recent messages, tool summaries, slot continuity, policy topic hints, and prior policy mention refs into a prompt-safe session bundle.
- `session_context_load` projects the target `session_context_bundle` while preserving legacy `session_memory` / `session_memory_bundle` outputs. It also has current-turn explicit slot override and merchant-scope filtering behavior.
- CWC is already a separate field in `MemoryContextBundle` / `AgentState` (`case_working_context`, `case_working_context_lifecycle_status`) and is loaded/written through Phase 45 CWC lifecycle code.
- `MemoryToolExecutor` for `search_case_memory` already uses `CaseMemoryService` / reviewed case memory. The old `LegacySessionPrecedentSearchService` is explicitly debug/legacy and must not become planner-facing case precedent.

The main Phase 46 risk is not table structure; it is semantic drift. Several prompt-context surfaces contain refs or hints (`last_business_context_refs`, `tool_summaries.business_fact_refs`, `policy_topic_hints`, `prior_policy_mention_refs`). These may remain useful as contextual pointers, but Phase 46 must test-lock that they are not policy evidence, business-system truth, approval/action authority, replay truth, long-term preference memory, reviewed case precedent, or CWC fallback.
</domain>

<decisions>
## Implementation Decisions

### D-46-01 - Preserve `session_memories` table identity
- Phase 46 starts with no migration. Preserve the existing `session_memories` table and its tenant/user/thread identity.
- Planner may propose a migration only if research proves an existing implementation defect that cannot be fixed with docs/tests or migration-safe code narrowing.

### D-46-02 - Session context contents stay narrow
- Allowed session context contents: slot continuity, last intent, lightweight same-thread summary, unresolved questions, same-thread recent-message / rolling-summary prompt context, prompt-safe tool summaries, and prompt-safe refs/hints.
- Disallowed session context contents: CWC durable working state, closed-case precedent, durable tenant/user/merchant preference memory, policy body text, policy evidence authority, business fact authority, risk decisions, approval decisions, action authorization, action outcome truth, replay truth, and sensitive raw PII.

### D-46-03 - Prompt hints are not authority
- `policy_topic_hints`, `prior_policy_mention_refs`, `last_business_context_refs`, and tool summary refs may remain as contextual hints only.
- These hints must not produce `EvidenceRefV1`, must not satisfy policy/approval evidence requirements, must not replace fresh business tool reads, and must not be cited as current business facts.

### D-46-04 - Session memory is not a CWC fallback
- CWC identity/read/write remains owned by Phase 45 lifecycle logic and canonical `refund_cases.id` resolution.
- Raw `session_memory`, raw `session_context`, reviewed `case_memory`, `case_memories`, and `memory_context` must not backfill or guess a CWC row.
- Existing slot inheritance may continue to feed graph `active_slots` through the current slot/session path, but CWC must still resolve through the trusted canonical case resolver rather than treating session memory as case authority.

### D-46-05 - Session memory is not reviewed precedent
- `search_case_memory` must stay backed by reviewed `case_memories` / `CaseMemoryService`, not by `session_memories`.
- `LegacySessionPrecedentSearchService` may remain as a legacy/debug-only projection only if tests lock that it is not the planner-facing `search_case_memory` implementation.

### D-46-06 - Session memory is not long-term automatic sedimentation
- Phase 46 must not introduce generic automatic long-term extraction from normal runs.
- Durable explicit preference memory remains Phase 48. Any "remember this preference" semantics must stay out of this phase.

### D-46-07 - Keep Phase 45 boundaries intact
- Do not alter CWC terminal writeback eligibility, CWC deterministic projection, thread-case `run_auto` link lifecycle, or CWC read seam behavior except to add boundary tests that protect Phase 46 semantics.
- Do not re-open GAD-01 option B. Observation-to-slot feedback remains future ReAct loop-local behavior, not a graph-global `active_slots` writer.

### D-46-08 - Verification entrypoint
- Every automated test command in Phase 46 plans must use the MOCA-approved test entrypoint: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- Bare `pytest` or bare `python -m pytest` is invalid verification.

### Planner's Discretion
- Exact plan split, as long as it follows the MOCA phase-level granularity rule.
- Whether Phase 46 is docs/static-tests only or includes small code narrowing, based on the audit evidence in the first plan.
- Exact names for any new static alignment tests.
- Whether to move legacy/debug session-precedent tests or keep them with stronger "not planner-facing" assertions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 46 Inputs
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - DEFER-1 and memory-layering decisions D1-D5.
- `.planning/REQUIREMENTS.md` - MEM-03.
- `.planning/ROADMAP.md` - Phase 46 scope and success criteria.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-CONTEXT.md` - CWC/session out-of-scope boundary.
- `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-CONTEXT.md` - CWC lifecycle decisions and Phase 46 defer.
- `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-VERIFICATION.md` - delivered CWC lifecycle state.

### Normative Contract
- `docs/contract-spec.md` Section 10.1 - AgentState lifecycle matrix and field registry.
- `docs/contract-spec.md` Section 13.2 - session memory contract.
- `docs/contract-spec.md` Section 13.4 - case memory semantic lock.
- `docs/contract-spec.md` Section 13.4a - Case Working Context contract.
- `docs/contract-spec.md` Section 13.5 / 13.6 - memory write/storage constraints.

### Existing Implementation Surfaces
- `src/db/models.py` - `SessionMemory`, `CaseMemory`, `LongTermMemory`, `CaseWorkingContext`, and `ConversationThread` table definitions.
- `src/db/migrations/versions/007_session_memories.py` - original session memory schema.
- `src/memory/schemas.py` - `SessionMemoryView`, `SessionContextMemory`, `SessionMemoryBundle`, write candidate/result DTOs.
- `src/memory/repository.py` - `SessionMemoryRepository`.
- `src/memory/service.py` - `MemoryService` session load/write semantics.
- `src/memory/session_bundle.py` - session bundle and session context projection.
- `src/memory/context_service.py` - `MemoryContextService` session/reviewed/bundle projection.
- `src/memory/search.py` - legacy session-derived precedent projection that must remain non-planner-facing.
- `src/tools/executors/memory.py` - production `search_case_memory` executor using reviewed case memory.
- `src/tools/catalog.py` - `search_case_memory` descriptor wording.
- `src/agent/nodes/session_context_load.py` and `src/agent/nodes/session_memory_load.py` - target node and compatibility wrapper.
- `src/agent/nodes/memory_write.py` and `src/memory/write_service.py` - session write candidate generation.
- `src/agent/state.py` and `src/agent/nodes/receive_request.py` - state fields and reset discipline.

### Tests And Verification Anchors
- `tests/memory/test_session_memory_schema.py`
- `tests/memory/test_session_memory_service.py`
- `tests/memory/test_session_memory_bundle.py`
- `tests/memory/test_session_memory_repository.py`
- `tests/memory/test_session_precedent_search.py`
- `tests/memory/test_phase45_contract_alignment.py`
- `tests/agent/test_session_memory_load.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/tools/test_catalog.py`
- `tests/architecture/test_memory_contract_delta.py`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SessionMemoryRepository.get_active(...)` and `insert_active(...)`: tenant/user/thread scoped session memory access.
- `MemoryService.load_session_memory(...)`: expiry, intent compatibility, and metadata filtering for inherited slots.
- `MemoryService.write_session_memory(...)`: CAS merge, PII skip, write-event emission, and fallback behavior.
- `SessionMemoryBundleService.load_session_memory_bundle(...)`: same-thread prompt context facade.
- `project_session_context_memory(...)`: target session context projection with `authority_class = contextual_only`.
- `MemoryContextService.load_memory_bundle_after_slot_resolution(...)`: unified memory bundle composition.
- `MemoryToolExecutor`: production reviewed case memory search surface.

### Established Patterns
- Memory remains `contextual_only`.
- Prompt-safe refs/hints may be carried, but source services remain authoritative.
- Session-memory write failures are side effects and do not block the user response.
- Session slot inheritance is deterministic and filtered; stale/incompatible slots are dropped.
- CWC and reviewed case memory are separate from session context and must not be fallback sources for each other.

### Integration Points For Planning
- Contract/docs: clarify Phase 46 semantics in `docs/contract-spec.md` without implying a migration.
- Static tests: assert no destructive table changes, no `session_memories` case-scope column, no planner-facing session-derived precedent, no authority DTO production from session memory, and no Phase 47/48 behavior.
- Behavioral tests: keep existing session read/write tests green while adding boundary assertions around prompt hints, CWC fallback, and reviewed-case executor separation.
</code_context>

<specifics>
## Specific Ideas

- Add a Phase 46 alignment test file analogous to `tests/memory/test_phase45_contract_alignment.py`.
- Extend contract-spec Section 13.2 to explicitly state that after CWC, session memory remains same-thread temporary context only.
- Lock `search_case_memory` as reviewed case memory in tests and keep `LegacySessionPrecedentSearchService` out of production executor wiring.
- Add tests proving session context refs/hints do not import or instantiate `EvidenceRefV1`, approval DTOs, action DTOs, or CWC DTOs.
- Add grep/static checks preventing Phase 46 plans from using bare `pytest` commands.
</specifics>

<deferred>
## Deferred Ideas

- Phase 47: `case_memories` reviewed-precedent repositioning, metadata-first retrieval semantics, and closed-case candidate generation.
- Phase 48: narrow explicit tenant preference memory for "remember this preference" / admin-save / reviewed candidate paths.
- Future graph/agent phase: investigate ReAct implementation with loop-local discovered slot memory.
- Optional future cleanup: remove legacy session-derived precedent code only after Phase 47 provides enough reviewed precedent coverage and product owners accept the deletion.
</deferred>

---

*Phase: 46-session-context-repositioning*
*Context gathered: 2026-07-03*
