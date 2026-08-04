# Phase 48: Narrow Long-Term Explicit Preference Memory - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 48` interactive discussion, Phase 44-47 memory contexts, codebase scout, and user-confirmed decisions.

<domain>
## Phase Boundary

Phase 48 narrows `long_term_memories` to explicit tenant/merchant preference memory only.

This phase delivers the MEM-05 boundary:

1. Published long-term memory stores only explicit soft preferences and human-confirmed preferences.
2. Ordinary completed runs must not create published long-term memory or generic run summaries.
3. Automatic observation may produce at most needs-review preference candidates; it must not publish prompt-usable long-term memory directly.
4. `long_term_memories` table identity is preserved. The phase narrows semantics through contract/docs/tests and small additive/narrowing code.
5. Session context, Case Working Context, and reviewed case precedent remain separate memory layers and must not compete for the same content.

Out of scope:

- User-specific preference as a main path.
- Generic profile facts, stable merchant patterns, strategy hints, similar-case hints, operational rules, policy rules, current order/refund/ticket state, approval/action authorization, or ordinary run summaries as long-term memory.
- Renaming, dropping, or retyping `long_term_memories`, `case_memories`, `session_memories`, `case_working_contexts`, `conversation_threads.case_id`, or `thread_case_links`.
- New broad LLM-based preference inference from normal chat.
- ReAct / graph-node architecture refactor.

</domain>

<decisions>
## Implementation Decisions

### Write Entry And Source Policy
- **D-48-01:** Supported write entry points are chat explicit-memory intent, admin save, and reviewed candidates.
- **D-48-02:** Chat entry requires an explicit memory phrase such as "remember this preference", "use this going forward", or "save this preference". Ordinary statements must not be auto-treated as preference writes.
- **D-48-03:** Add a minimal admin-only save API/service that directly creates `explicit_admin_preference`. Permissions, scope, and audit must be explicit. Do not disguise admin-created preferences as pending review.
- **D-48-04:** Explicit user preferences may auto-publish only when they are non-PII, non-tombstoned, scope-valid, and semantically soft preferences.
- **D-48-05:** Admin and human-reviewed preferences may publish directly when policy gates pass.
- **D-48-06:** Published long-term memory source types are narrowed to `explicit_user_preference`, `explicit_admin_preference`, and `human_reviewed`.
- **D-48-07:** `semantic_episode_candidate`, run summary, pattern, and strategy outputs must not become published long-term memory directly.
- **D-48-08:** Exception: semantic episodes may generate needs-review `preference_candidate` rows. If approved/published, the source type must become `human_reviewed`; `semantic_episode_candidate` must not remain a published long-term source type.

### Preference Semantic Boundary
- **D-48-09:** Allow soft operational preferences, not only communication/display preferences, but represent them as preference/hint rather than policy/rule.
- **D-48-10:** Acceptable example: "In low-amount refund scenarios, prefer calming explanatory wording first."
- **D-48-11:** Forbidden example: "Below X yuan must refund / must reject." Hard rules belong to policy/config/rule systems, not memory.
- **D-48-12:** `semantic_episode` may project only `preference_candidate` into long-term needs-review candidates. `cross_case_pattern`, `similar_case_hint`, and `strategy_hint` must not enter long-term memory.

### Retrieval And Scope Behavior
- **D-48-13:** Keep the existing `needs_long_term_memory` / `memory_context_load` seam to reduce Phase 48 blast radius.
- **D-48-14:** Long-term retrieval must return only published preference rows after Phase 48.
- **D-48-15:** Do not query preferences on every turn; avoid prompt noise and cost growth.
- **D-48-16:** Do not rely only on explicit preference intents for retrieval; generation scenarios may need preference hints even when the user is not asking about memory.
- **D-48-17:** Default scope is merchant/team preference. Tenant-level preference requires explicit admin save because its blast radius is wider.
- **D-48-18:** User-specific preference is deferred to post-Phase 48 due to scope precedence, privacy, and conflict-governance complexity.

### Governance And Interfaces
- **D-48-19:** Chat explicit phrase hits still require PII, scope, tombstone, source-type, and soft-preference validation before write.
- **D-48-20:** Same-scope same-topic or similar-content correction uses the existing long-term supersede path.
- **D-48-21:** "Delete this preference" / "do not remember this anymore" uses tombstone/forget behavior.
- **D-48-22:** Do not auto-merge semantically similar preferences. Similar content may not be equivalent, and auto-merge risks turning preferences into incorrect rules.
- **D-48-23:** Phase 48 must update `docs/contract-spec.md` Section 13.3 from broad long-term memory to explicit preference-only target semantics and synchronize docs/tests.
- **D-48-24:** This is not an MVP-only annotation. If Phase 48 narrows the `long_term_memories` target contract, the normative spec must narrow too.

### the agent's Discretion
- Exact explicit-phrase list and normalization rules, as long as recognition remains deterministic and narrow.
- Exact API route/service names for admin save.
- Exact schema fields for preference topic/category if planning proves they are needed for supersede/conflict handling.
- Exact test split, but plans should separately cover contract/spec alignment, source-policy/schema narrowing, chat/admin/reviewed write paths, semantic-episode candidate narrowing, retrieval behavior, and final validation.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 48 Inputs
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - DEFER-3, D1 long-term narrow preference decision, D4 write-chain split, and D5 table naming red line.
- `.planning/REQUIREMENTS.md` - MEM-05 requirement: `long_term_memories` narrowed to explicit tenant preference memory.
- `.planning/ROADMAP.md` - Phase 48 scope, success criteria, dependency on Phase 47, and design input.
- `.planning/phases/46-session-context-repositioning/46-CONTEXT.md` - session memory boundary; Phase 48 preference memory stayed out of Phase 46.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-CONTEXT.md` - case precedent boundary and Phase 48 defer trace.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-VERIFICATION.md` - confirms Phase 47 preserved DEFER-3 and did not implement preference memory.

### Normative Contract And Docs
- `docs/contract-spec.md` Section 13.3 - currently broad long-term memory wording; Phase 48 must narrow this to explicit preference-only.
- `docs/contract-spec.md` Sections 13.5 and 13.6 - memory write policy, identity, tombstone, supersede, and storage constraints.
- `docs/architecture-overview.md` - current high-level memory split already states Phase 48 explicit preference memory only.
- `docs/memory-contract-delta.md` - historical/current broader long-term policy table; use as a drift source to reconcile or supersede, not as the final Phase 48 target.

### Existing Implementation Surfaces
- `src/db/models.py` - `LongTermMemory`, `MemoryWriteEvent`, source/review/status checks, and table identity to preserve.
- `src/memory/schemas.py` - `LongTermMemoryWriteCandidate`, `LongTermSourceType`, `LongTermMemoryKind`, `LongTermMemoryView`, and `MemorySourceRefV1`.
- `src/memory/policy.py` - current long-term source policy; must be narrowed for published long-term memory.
- `src/memory/long_term.py` - write/review/delete/forget/supersede service boundary.
- `src/memory/repository.py` - retrieval predicate, pending-review list, duplicate/tombstone identity, and source identity handling.
- `src/memory/write_service.py` - ordinary writes default to session-only; explicit candidates are the current long-term/case input seam.
- `src/memory/semantic_episode.py` - current semantic episode candidate projection; Phase 48 must narrow it to `preference_candidate` only or otherwise prevent non-preference long-term candidates.
- `src/memory/context_service.py` - reviewed memory load and long-term retrieval composition.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` and `src/agent/nodes/long_term_memory_retrieve.py` - current `memory_context_load` compatibility seam.
- `src/agent/routing.py` - `needs_long_term_memory` route behavior.
- `src/api/routers/memory.py` and `src/api/schemas/memory.py` - existing memory review API surfaces to reuse/extend for governance.

### Tests And Verification Anchors
- `tests/memory/test_long_term_memory_service.py`
- `tests/memory/test_long_term_memory_repository.py`
- `tests/memory/test_memory_policy.py`
- `tests/memory/test_memory_write_service.py`
- `tests/memory/test_memory_tombstones.py`
- `tests/memory/test_semantic_episode_projection.py`
- `tests/memory/test_reviewed_memory_context_boundary.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/agent/test_graph.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/test_memory_review_api.py`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LongTermMemoryService.write_memory(...)`: already handles tombstone checks, duplicate active identity, PII block, review status, audit events, and source identity.
- `LongTermMemoryService.approve_memory(...)`, `reject_memory(...)`, `delete_memory(...)`, `forget_memory(...)`, and `supersede_memory(...)`: existing governance primitives for review, deletion/tombstone, and correction.
- `LongTermMemoryRepository.retrieve_profile_memory(...)`: already filters to published, current, prompt-safe, non-expired, non-tombstoned rows.
- `MemoryWriteService.propose_candidates(...)`: ordinary run writes default to `{"session"}` and long-term/case candidates only flow from explicit `memory_write_candidates`.
- `MemoryContextService.load_reviewed_memory_context(...)`: existing read composition for long-term and case memory under trusted merchant scope.
- `semantic_episode.project_semantic_episode_candidates(...)`: current candidate-only projection can be narrowed instead of introducing a new extractor from scratch.
- `src/api/routers/memory.py`: review action API already exists for pending long-term and case memory.

### Established Patterns
- Memory is `contextual_only`; it cannot produce `EvidenceRefV1`, current business facts, approval/action authority, or replay truth.
- Memory side effects must not roll back completed user responses or authoritative business records.
- Prompt-safe rows only enter the prompt/retrieval context.
- Tombstone and supersede behavior already exist for long-term memory and should be reused.
- Existing GSD validation commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` is invalid in MOCA.

### Integration Points
- Write side: explicit chat phrase gate and admin-save service should ultimately create validated `LongTermMemoryWriteCandidate` entries with source type `explicit_user_preference` or `explicit_admin_preference`.
- Reviewed candidate side: semantic episode may create needs-review preference candidates, but approval must publish as `human_reviewed` preference rather than `semantic_episode_candidate`.
- Read side: continue using `needs_long_term_memory` / `memory_context_load`, but narrow retrieval/projection to published preference rows.
- Contract side: update `docs/contract-spec.md` Section 13.3 and align static/behavioral tests.
</code_context>

<specifics>
## Specific Ideas

- Phrase gate examples: "remember this preference", "use this going forward", "save this preference", Chinese equivalents such as "记住这个偏好", "以后按这个", "保存这个偏好".
- Soft operational preference is allowed only as a hint. It must never be phrased or enforced as "must refund", "must reject", "must approve", "must execute", or a policy rule.
- Tenant-level preference is admin-only. Default preference scope should be merchant/team because that matches MOCA's business workflow.
- Published long-term memory should read like "Merchant/team prefers ..." rather than "System has determined ..." or "Policy requires ...".
</specifics>

<deferred>
## Deferred Ideas

- User-specific preference scope and precedence rules - post-Phase 48.
- Rich preference management UI - future product phase after storage/review/tombstone/retrieval foundations are safe.
- LLM-based broad preference inference from ordinary chat - out of scope until there is a separate review/eval design.
- Automatic semantic pattern/strategy/similar-case memory - belongs to case precedent or analytics, not long-term preference memory.
</deferred>

<suggested_plan_split>
## Suggested Plan Granularity

Phase 48 should not be planned as one large plan. A likely split:

1. **48-01:** Contract/docs/static semantic locks: narrow `docs/contract-spec.md` Section 13.3, preserve table identity, and lock source types/scope boundaries.
2. **48-02:** Source policy/schema narrowing and semantic episode candidate narrowing.
3. **48-03:** Explicit write paths: deterministic chat phrase gate and minimal admin-only save API/service, with PII/scope/tombstone/audit behavior.
4. **48-04:** Retrieval behavior, review approval publishing as `human_reviewed`, supersede/tombstone correction flow, and final validation.

Planning may adjust after source inspection, but it must keep spec alignment, source-policy narrowing, write-entry implementation, retrieval behavior, and final validation separable enough for bounded execution.
</suggested_plan_split>

---

*Phase: 48-narrow-long-term-explicit-preference-memory*
*Context gathered: 2026-07-04*
