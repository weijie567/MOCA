# Phase 45: Memory Lifecycle Wiring for Case Working Context - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Source:** GAD-01 qualification, Phase 44 defer, codebase scout, and user-confirmed default decisions.

<domain>
## Phase Boundary

Phase 45 wires the Phase 44 Case Working Context (CWC) foundation into the real agent-run lifecycle.

This phase delivers the caller-side lifecycle that Phase 44 intentionally deferred:

1. Resolve the canonical case identity for a run, using `refund_cases.id` as the only durable CWC scope key.
2. Link the current thread to the resolved case through `thread_case_links`.
3. Load active CWC as contextual-only run input before investigation/recommendation can use it.
4. Write back a deterministic CWC update after a successful terminal run, through the Phase 44 audited CWC service.

This phase is an integration/wiring phase, not a schema-redesign phase. The Phase 44 tables, repository semantics, revision model, audit type, and red lines stay fixed.

Out of scope:
- ReAct implementation or graph-node architecture refactor.
- New `active_slots` writer semantics.
- `case_memories` precedent repositioning or closed-case precedent extraction.
- Narrow long-term explicit-preference write path.
- Session memory redesign.
- Table renames for `case_memories` or `long_term_memories`.
- Destructive changes to `conversation_threads.case_id`.

</domain>

<decisions>
## Implementation Decisions

### GAD-01 Precondition
- **D-45-01:** GAD-01 is qualified as acceptable input for Phase 45. The observation-to-slot feedback decision is locked to **A / loop-local**: `investigate` may keep discovered identifiers in its own planner working memory in a future ReAct phase, but it must not write graph-global `active_slots` and must not become a canonical slot writer.
- **D-45-02:** Phase 45 planning must treat ReAct as decoupled from memory lifecycle. CWC lifecycle rules must not depend on the current graph node names, current graph edge order, or future ReAct loop internals.

### Lifecycle Integration Shape
- **D-45-03:** Introduce a stable memory lifecycle adapter/service boundary for CWC read/link/write orchestration. The adapter maps trusted run state to Phase 44 services; the core CWC repository/service must remain graph-agnostic.
- **D-45-04:** Prefer the existing terminal finalizer path (`src/api/services/agent_run_memory.py`) as the first production write hook because it already runs after completed `/agent-runs` responses, persists assistant messages/thread summaries, invokes `memory_write`, isolates memory side effects, and reports memory-write status without blocking the user response.
- **D-45-05:** Planner may still choose to register/wire the canonical `memory_write` graph node if that is needed for spec alignment, but it must keep the business rule in the lifecycle adapter. Do not hide CWC writeback inside `final_response`.

### Active CWC Read
- **D-45-06:** Active CWC read happens after slot resolution/case identity resolution and before `investigate` or recommendation logic consumes memory context. In the current implementation, the natural seam is the `memory_context_load` compatibility path (`long_term_memory_retrieve` / `reviewed_memory_context_retrieve`), extended with a CWC active-read projection.
- **D-45-07:** If no trusted case identity can be resolved, active CWC read must skip with an explicit status/ref reason. It must not backfill from `case_memories` precedent and must not guess a case.
- **D-45-08:** Loaded CWC must be exposed as contextual-only run state, preferably through additive `AgentState` fields and/or `memory_context_bundle` extension. Exact field names are planner discretion, but they must be registered in `AgentState` and contract-alignment tests if added.

### Thread-to-Case Link
- **D-45-09:** When a canonical `case_id` is resolved for a run, call the explicit Phase 44 linkage point (`ConversationRepository.link_case`) with `link_source="run_auto"` and `linked_by_run_id=current_run_id`.
- **D-45-10:** `append_message` must remain non-linking. Link creation belongs to the lifecycle adapter once the run has a trusted case identity, not to generic message persistence.
- **D-45-11:** Duplicate links must continue to dedupe through the Phase 44 repository/unique active index. Link failure must be surfaced in lifecycle status/trace and must not silently create a CWC row.

### Terminal CWC Write
- **D-45-12:** CWC writeback is allowed only for successful completed terminal runs that have a final response and a resolved canonical case id. Approval-pending, interrupted, cancelled, error, and missing-final-response paths must skip CWC writeback. Clarification-only responses may link a resolved case but should skip CWC content write unless the planner proves a safe deterministic update.
- **D-45-13:** CWC writeback must call `CaseWorkingContextService.write_case_working_context(...)`, preserving its Phase 44 semantics: required tenant/case/run/source_ref, isolated session, audit event, PII block, version conflict skip, and tenant guards.
- **D-45-14:** Memory write failure or CWC write conflict must not roll back the final assistant message, thread summary, action/approval records, or user response. It is a memory side effect and must be reported in status/trace.

### Content Projection
- **D-45-15:** Phase 45 uses deterministic projection from final run state to `CaseWorkingContextContentV1`. No LLM summarizer is introduced in this phase.
- **D-45-16:** Projection may use safe summaries/refs from fields such as user query, active slots, `business_context`, `tool_results`, `rag_context_bundle`, `claim_verification_bundle`, recommendation/proposed action, approval/action draft state, and final response, but it must preserve Phase 44 boundaries: claims and verified facts stay separate; tool facts store references/summaries with `observed_at`; policy body text and sensitive raw PII are not stored.
- **D-45-17:** Existing session, long-term, and reviewed case memory behavior must remain compatible. Do not change `long_term_memories`, `case_memories`, or the existing session-memory write policy while wiring CWC.

### Verification Rules
- **D-45-18:** Every automated test command in plans must use the MOCA-approved entrypoint: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. Bare `pytest` or bare `python -m pytest` is invalid verification.
- **D-45-19:** Phase 45 plan verification must include targeted tests for active CWC read, thread-case link lifecycle, terminal writeback skip/write/conflict/PII behavior, finalizer integration, and red-line preservation.

### the agent's Discretion
- Exact adapter class/function names.
- Whether the first implementation extends `memory_write` directly or creates a CWC-specific helper invoked by the terminal finalizer.
- Exact additive `AgentState` field names for CWC status/content, as long as they are registered and tested.
- Exact plan split, but the first plan set should separate contract/state boundary, read/link wiring, terminal writeback, and final verification/spec alignment if those touch different ownership surfaces.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 45 Inputs
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - memory-layering decisions, Phase 44 delivery trace, and named Phase 45 defer.
- `.planning/DEFERRED-DECISIONS.md` - GAD-01 loop-local decision; confirms ReAct slot feedback is not a Phase 45 memory blocker.
- `.planning/AGENTIC-INVESTIGATION-DISCUSSION.md` - supporting GAD-01 discussion and future ReAct boundary.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-CONTEXT.md` - locked Phase 44 CWC/thread-case decisions and red lines.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md` - verifies Phase 44 delivered the CWC foundation and deferred lifecycle hooks to Phase 45.
- `.planning/REQUIREMENTS.md` - MEM-01/MEM-02 requirement mapping and Phase 44/45 defer note.
- `.planning/ROADMAP.md` - Phase 44/45 sequencing.

### Normative Contract
- `docs/contract-spec.md` Section 9.4 - target graph node contract, including `memory_context_load`, `final_response`, and `memory_write`.
- `docs/contract-spec.md` Section 9.5 - deterministic router contract; Phase 45 must not add router side effects.
- `docs/contract-spec.md` Section 13 - memory architecture, CWC authority boundary, thread-case M:N note, and memory write semantics.
- `docs/contract-spec.md` AgentState field registry - any new CWC state fields must be aligned here or explicitly deferred with traceable rationale.

### Existing Implementation Surfaces
- `src/api/services/agent_run_memory.py` - current completed-run finalizer and terminal memory write execution path.
- `src/api/routers/agent_runs.py` - `/agent-runs` SSE path invoking the completed-run finalizer.
- `src/api/routers/agent.py` - legacy chat path background memory-write scheduling.
- `src/agent/nodes/memory_write.py` - current session/long-term/case memory write node callable used by finalizers.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` and `src/agent/nodes/long_term_memory_retrieve.py` - current memory-context read seam.
- `src/agent/graph.py` - current graph wiring; note `memory_write` is not registered in the graph even though it exists as a callable node.
- `src/agent/state.py` and `src/agent/nodes/receive_request.py` - state fields and per-turn reset surface.
- `src/agent/graph_vocabulary.py` - target graph vocabulary already lists `memory_write` and memory-context aliases.
- `src/memory/case_identity.py` - Phase 44 canonical case resolver.
- `src/conversation/repository.py` - `ConversationRepository.link_case` explicit thread-case linkage point.
- `src/memory/thread_case_links.py` - M:N link repository with dedupe and tenant guards.
- `src/memory/case_working_context.py` - CWC repository and revision/version behavior.
- `src/memory/case_working_context_service.py` - audited isolated CWC write service.
- `src/memory/case_working_context_schemas.py` - CWC content and write candidate schemas.

### Tests And Verification Anchors
- `tests/test_agent_runs_api.py` - current completed-run finalizer and idempotence coverage.
- `tests/agent/test_memory_write_node.py` - memory write node behavior.
- `tests/agent/test_graph.py` and `tests/agent/test_graph_vocabulary.py` - graph and target vocabulary coverage.
- `tests/memory/test_case_identity.py`
- `tests/memory/test_thread_case_links.py`
- `tests/memory/test_case_working_context_repo.py`
- `tests/memory/test_case_working_context_service.py`
- `tests/memory/test_phase44_contract_alignment.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CaseWorkingContextService.write_case_working_context(...)`: audited, isolated CWC write surface with PII block and conflict skip.
- `CaseWorkingContextRepository.read_active(...)`: active CWC read by `(tenant_id, case_id)`.
- `resolve_case_id(...)`: canonical resolver from refund case number or UUID to `refund_cases.id`.
- `ConversationRepository.link_case(...)`: explicit thread-case lifecycle linkage point.
- `finalize_completed_agent_run_memory(...)`: completed-run lifecycle finalizer that already persists assistant message, thread summary, and terminal memory write status.
- `reviewed_memory_context_retrieve(...)`: existing post-slot memory-context read seam for long-term/reviewed case memory.

### Established Patterns
- Memory side effects run isolated from caller transactions.
- Memory write failure does not block or roll back user-facing completed responses.
- Memory remains `contextual_only`; policy evidence, current business facts, approval/action authority, and replay truth are owned by other services.
- `receive_request` resets ephemeral memory fields each turn; new CWC fields must follow the same lifecycle discipline.
- Thread-case link creation is explicit and deduped; generic message append does not link cases.

### Integration Points
- Read side: extend the memory-context read seam after slots/case identity are resolved.
- Link side: call `ConversationRepository.link_case(...)` when a trusted case id is available.
- Write side: extend the terminal finalizer / memory-write path to project and write CWC after completed runs.
- State/spec side: add additive CWC state/status fields only if needed and align `AgentState`, tests, and `docs/contract-spec.md`.

</code_context>

<specifics>
## Specific Ideas

- Keep Phase 45 small enough that later ReAct work only reconnects lifecycle adapter call sites.
- Treat `run_auto` as the link source for agent-run-discovered case membership.
- Prefer a status shape that distinguishes `resolved/read/written`, `skipped_no_case`, `skipped_not_completed`, `blocked_pii`, `conflict`, and `error`.
- CWC writeback should include source refs tied to the run and case; do not invent run-less audit entries.

</specifics>

<deferred>
## Deferred Ideas

- Investigate ReAct implementation, including loop-local discovered slot memory, belongs in a later dedicated graph/agent phase.
- Option B from GAD-01 (`investigate` writes a discovered slot surface) is rejected for now and must not be smuggled into Phase 45.
- Case precedent generation from closed cases remains a future phase.
- Narrow long-term explicit-preference writes remain a future phase.
- Session memory repositioning after CWC remains a future phase.
- Full graph vocabulary/topology reconciliation can be a later graph architecture phase unless Phase 45 planning proves a minimal spec-alignment edit is necessary.

</deferred>

---

*Phase: 45-memory-lifecycle-wiring-for-case-working-context*
*Context gathered: 2026-07-03*
