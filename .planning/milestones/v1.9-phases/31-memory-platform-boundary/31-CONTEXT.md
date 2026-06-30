# Phase 31: Memory Platform Boundary - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 31` (plain-text interactive; all gray areas discussed)

<domain>
## Phase Boundary

Phase 31 turns MOCA memory from a set of useful but ambiguous graph/storage concepts into explicit platform boundaries. The phase owns the graph-facing distinction between same-thread session context, reviewed long-term memory, reviewed case memory, conversation log context, workflow checkpoint, working state, and memory write policy.

This phase must make `SessionContextMemory` the agent-facing same-thread projection while keeping the durable session store an internal `SessionContinuityStore` concern. It must also separate early session context loading from late reviewed memory context retrieval, add contextual-only memory refs/statuses, and prove memory cannot satisfy policy evidence, current business fact, approval/action authority, or replay truth.

This phase consumes Phase 29.5 merchant-scope semantics and Phase 30 business fact authority. Memory retrieval scope must come from trusted identity/scope and trusted business context; memory must never create or widen merchant scope.

This phase should not implement the full Phase 32 graph migration, Phase 33 RAG claim verification, Phase 34 approval/action binding, Phase 35 replay/eval coverage, a review queue UI, a complete memory operations backend, physical microservices, full DB/RLS redesign, or broad storage/table renames.

</domain>

<decisions>
## Implementation Decisions

### Graph-Facing Boundary Vocabulary

- **D-01:** Phase 31 adopts graph-facing target-boundary vocabulary, not adapter-only and not whole-repo mechanical rename.
  - Same-thread continuity and prompt context should move from `session_memory` wording toward `session_context` / `SessionContextMemory`.
  - Reviewed long-term and case memory prompt inputs should be grouped under non-authoritative `reviewed_memory_context` / `memory_context` vocabulary.
  - A service/facade may be introduced where useful, but the public graph-facing boundary should not remain a thick adapter over old names.
- **D-02:** Target graph-facing renames should be real where they clarify architecture.
  - `session_memory_load` should become or be wrapped by `session_context_load`.
  - `long_term_memory_retrieve` should become or be wrapped by `reviewed_memory_context_retrieve` or `memory_context_retrieve`.
  - `session_memory_bundle` should become or be wrapped by `session_context_bundle`.
  - `long_term_memory` / `case_memory` state projections should converge under `memory_context.long_term_items` / `memory_context.case_items` or an equivalent structured bundle.
- **D-03:** Preserve persistence-layer and historical contract names unless a specific compatibility or spec requirement demands a change.
  - Do not rename DB tables, migrations, repository classes, or existing storage schema versions solely for wording.
  - `SessionMemory`, `LongTermMemory`, `CaseMemory`, `MemoryWriteEvent`, and `session_memory.v2` may remain as storage/history names.

### Two-Stage Context Loading

- **D-04:** Use two-stage context loading: early session context for same-thread continuity; late reviewed memory context after scope/business context is explicit or trusted.
- **D-05:** `session_context_load` runs after initial safety/basic intent classification and before slot completeness checks.
  - It may provide same-thread rolling summary, recent messages, prompt-safe tool summaries, and trusted/compatible session slot continuity.
  - It must not override explicit current-turn input.
  - It must not provide business, evidence, action, approval, or replay authority.
- **D-06:** `reviewed_memory_context_retrieve` runs only after explicit slots, merchant/resource identifiers, or trusted business context are available.
  - It may provide reviewed long-term and case memory as contextual assistance only.
  - It must not create merchant scope, business facts, evidence claims, action payload fields, approval snapshot inputs, or replay truth.
- **D-07:** Target order for planning is:
  1. `receive_request`
  2. `classify_intent`
  3. `session_context_load`
  4. `extract_slots`
  5. slot completeness / clarification routing
  6. investigate / trusted business lookup
  7. `reviewed_memory_context_retrieve`
  8. `generate_recommendation`
  9. `assess_risk_and_approval`
- **D-08:** If the current graph cannot place reviewed memory retrieval after trusted investigation yet, the plan must explicitly guard the MVP path: late retrieval can only use explicit slots and trusted context to form scopes; memory cannot infer or supply merchant scope.

### Authority And Reference Boundaries

- **D-09:** Add typed contextual memory refs at the source, with downstream verifier deny-lists as defense-in-depth.
  - Session context and reviewed memory context may only produce contextual-only memory refs.
  - Target refs should carry memory-owned schema versions, source metadata, scope metadata, review metadata where applicable, and `authority_class="contextual_only"`.
- **D-10:** Target memory ref shapes are `SessionContextRef` for same-thread continuity references and `ReviewedMemoryRef` for reviewed long-term/case memory references.
  - Exact file names and model names are agent discretion, but the semantic split is not optional.
- **D-11:** Memory refs must intentionally remain incompatible with:
  - `EvidenceRefV1`
  - `BusinessFactRefV1`
  - approval evidence refs
  - action safety snapshot refs
  - authoritative action payload fields
  - replay truth refs
  - `MaterialClaim.business_fact_refs`
  - citation/evidence maps
- **D-12:** Prompt labels remain required for model hygiene, but prompt text is not the normative boundary.
  - Downstream evidence, business fact, approval, action, and replay verifiers must reject contextual-only memory refs as a second line of defense.

### Merchant Scope And Visibility

- **D-13:** Use deny-first trusted scope with explicit scoped sharing.
  - Memory retrieval scope must be derived only from `TrustedContext`, `MerchantScopeV1`, explicit current-turn input after trusted validation, or trusted business/resource context.
  - No trusted scope means no reviewed long-term or case memory retrieval.
  - Memory content, session summaries, long-term memory, and case memory must never create or widen merchant scope.
- **D-14:** Global memory is unsupported in Phase 31.
  - Tenant-wide memory remains disabled unless the plan adds a very explicit allowlist and proof; default is no tenant/global retrieval.
- **D-15:** Merchant-level memory sharing is allowed only when the memory record is explicitly merchant-scoped and passes actor trusted merchant scope, review, visibility, privacy, PII, deleted, and expiry gates.
- **D-16:** Session context remains thread/user scoped and does not cross thread or user by default.
  - User preference or user-specific constraint memory remains user-scoped and does not cross user by default.
  - Case memory may be case- or merchant-scoped only after case identity or merchant scope is confirmed by trusted business context.
- **D-17:** Retrieval must fail closed for missing `TrustedContext`, missing tenant, missing required actor merchant scope, merchant not allowed by `MerchantScopeV1`, unverified case merchant, deleted/expired memory, non-approved memory, non-prompt-safe PII, and unallowed tenant/global scope.

### Write Policy Boundary

- **D-18:** Implement write policy boundary and fail-closed lifecycle coverage; do not build the full memory operations product in Phase 31.
- **D-19:** Phase 31 should standardize the write decision boundary around `memory_write_decision.v2`-compatible metadata or an equivalent DTO.
  - Required metadata: decision, status, reason_code, memory_type, scope, source identity, candidate hash, PII classification, review status, and failure/fallback reason.
- **D-20:** Existing long-term/case lifecycle capabilities should be unified under the target boundary rather than reimplemented.
  - Current code already has tombstone, PII block, needs_review, supersede, write event, and retrieval exclusion behavior in long-term/case memory paths.
- **D-21:** Critical fail-closed cases must be test-pinned:
  - Sensitive/prohibited PII candidates are skipped or write-blocked and do not write session, long-term, or case memory.
  - Deleted or tombstoned memory is not revived by a later candidate with the same content or source identity.
  - Correction/supersede cannot create two current memories for the same identity/scope.
  - Deleted, rejected, superseded, tombstoned, expired, needs_review, or non-prompt-safe PII memory is excluded from reviewed memory context retrieval.
  - Memory write timeout/error records explicit error/skipped/fallback status and does not roll back final response, action, or approval main path.
  - Missing or untrusted tenant/user/thread/merchant/case scope fails closed.
  - Auto-approved source can be stored when eligible; unreviewed source can be persisted only as needs_review and must not surface in prompt-facing retrieval.
- **D-22:** Do not implement review queue UI, full redaction workflow, full operator workflow, every memory API, full RLS redesign, large DB/table renames, or a complete memory operations backend in Phase 31.

### Audit And Replay Handoff

- **D-23:** Add audit-ready memory status refs now; leave replay-authoritative event coverage to Phase 35.
  - Phase 31 should stabilize status/ref metadata for session context load, reviewed memory context retrieval, and memory write decisions.
  - These records are audit/replay-adjacent handoff points for Phase 35, not replay truth.
- **D-24:** Memory status refs can prove what contextual memory was loaded, retrieved, skipped, written, or rejected by the memory subsystem at runtime.
  - They must not be consumed as evidence, business facts, approval/action inputs, or deterministic replay inputs.
- **D-25:** Target status refs:
  - `session_context_load_status.v1`: status, source, `authority_class="contextual_only"`, tenant/user/thread/run identity, loaded `SessionContextRef` entries, fallback_reason, slot_count, recent_message_count, tool_summary_count.
  - `reviewed_memory_context_retrieve_status.v1`: status, `authority_class="contextual_only"`, trusted scope inputs, effective scopes, retrieved `ReviewedMemoryRef` entries, filter reasons, fallback_reason.
  - `memory_write_decision.v2`: status, decision, `authority_class="contextual_only"`, memory_type, memory_id, candidate_hash, source_identity_hash, scope, pii_classification, review_status, reason_code, fallback_reason.
- **D-26:** Full replay event coverage for memory load/retrieve/write/filter/scope/review/tombstone lifecycle decisions is deferred to Phase 35.

### Verification Strategy

- **D-27:** Start planning from RED tests that prove the graph-facing target boundary, authority boundaries, scope isolation, write-policy lifecycle, and audit-ready status refs.
- **D-28:** Tests should explicitly prove memory cannot satisfy policy evidence, current business fact, approval/action snapshot, or replay truth requirements.
- **D-29:** Merchant isolation tests must prove one merchant's conversation, case memory, or long-term memory cannot contaminate another merchant's prompt context.
- **D-30:** If implementation must diverge from `docs/contract-spec.md`, do not silently drift. Either correct the spec through the project review workflow or annotate MVP scope/target-state differences in spec and `.planning/`.

### Agent Discretion

- Exact module split is left to planning. Likely targets include `src/memory/schemas.py`, a new memory context/ref module, current memory services, graph nodes under `src/agent/nodes/`, and prompt projectors under `src/agent/context/`.
- Exact final node names may be `reviewed_memory_context_retrieve` or `memory_context_load`, but the plan must preserve the early session context / late reviewed memory context distinction.
- Exact compatibility shims are left to planning. Preserve legacy state fields long enough to keep existing tests/routes stable where needed.
- Exact reason code names are flexible, but they must be deterministic, stable, and test-pinned.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 31 goal, success criteria, dependency on Phase 30, and downstream Phase 32-35 sequence.
- `.planning/REQUIREMENTS.md` - APF-09, APF-10, MER-01, APF-17, and APF-18 traceability.
- `.planning/STATE.md` - Current milestone state and latest completed phase context.
- `.planning/todos/deferred/2026-06-27-merchant-scope-memory.md` - Memory-specific merchant scope deferred item from Phase 29.5.

### Normative Contracts

- `docs/contract-spec.md` §0.2 - `MemoryContextService` ownership row and forbidden memory access patterns.
- `docs/contract-spec.md` §8.0 / §8.0.1 - `TrustedContext`, `MerchantScopeV1`, and Phase 29.5 role-to-merchant-scope semantics.
- `docs/contract-spec.md` §9 - Target graph vocabulary including `session_context_load`, `memory_context_load`, `investigate`, and `memory_write`.
- `docs/contract-spec.md` §10 - AgentState memory fields and reset/merge rules.
- `docs/contract-spec.md` §13 - Memory design, authority boundary, layering, session/long-term/case semantics, write policy, lifecycle, PostgreSQL/Redis rules, and retrieval predicates.
- `docs/contract-spec.md` §14.6 - Memory write prompt constraints.
- `docs/contract-spec.md` §17 / §17.3 - Decision event ordering and `memory_write_*` behavior.
- `docs/contract-spec.md` §18.1 - Target memory schema, constraints, tombstones, and memory write events.
- `docs/target-agent-platform-architecture-plan.md` §3 / §5.2 - Modular monolith service boundary and ownership matrix.
- `docs/target-agent-platform-architecture-plan.md` §8-§9 - `SessionContextMemory`, `MemoryContextService`, `session_context_load`, and `memory_context_load` target vocabulary.
- `docs/eval-test-plan.md` - Platform boundary and memory eval/test expectations.

### Prior Phase Context

- `.planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md` - Conversation persistence, prompt-safe memory parity, and memory non-authority decisions.
- `.planning/phases/24.2-unified-session-memory-bundle-read-path/24.2-CONTEXT.md` - `SessionMemoryBundle` read path and legacy `session_memory` compatibility.
- `.planning/phases/24.3-memory-write-isolation-policy-and-observability-mvp/24.3-CONTEXT.md` - Memory side-effect isolation and safe trace metrics.
- `.planning/phases/24.4-memory-eval-mvp/24.4-CONTEXT.md` - Memory eval fixtures for same-thread recall, stale slot non-leak, tombstone non-revival, and authority contamination negatives.
- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - Trusted identity/scope projection rules and `MemoryContext` projection inputs.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Merchant-bound role semantics and memory scope follow-up.
- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - Current business fact authority and memory/RAG/LLM non-substitution boundary.

### Current Code Sites

- `src/memory/schemas.py` - Existing `SessionMemoryBundle`, `SessionMemoryView`, write candidates/results, long-term/case write candidates/results, search request/results, and identity schemas.
- `src/memory/service.py` - Current session continuity load/write service with CAS, slot compatibility, expiry, and PII-blocked write behavior.
- `src/memory/session_bundle.py` - Current session bundle service combining conversation prompt context and slot continuity.
- `src/memory/long_term.py` - Long-term memory write/review/delete/tombstone/supersede and retrieval behavior.
- `src/memory/case_memory.py` - Case memory review, retrieval, tombstone, PII, and prompt-safe filtering behavior.
- `src/memory/repository.py` - Session and long-term repository helpers.
- `src/memory/identity.py` - Canonical memory content/source/candidate identity hashing.
- `src/memory/policy.py` - Prompt-safe and blocked PII classification sets.
- `src/memory/tombstones.py` - Tombstone matching helpers.
- `src/memory/write_isolation.py` - Isolated memory side-effect transaction helper.
- `src/db/models.py` - `SessionMemory`, `LongTermMemory`, `CaseMemory`, `MemoryTombstone`, and `MemoryWriteEvent` storage models and constraints.
- `src/db/migrations/versions/007_session_memories.py` - Session memory storage migration.
- `src/db/migrations/versions/013_long_term_case_memory.py` - Long-term/case memory, tombstone, and write-event migration.
- `src/agent/nodes/session_memory_load.py` - Current graph-facing same-thread memory load node.
- `src/agent/nodes/long_term_memory_retrieve.py` - Current graph-facing reviewed long-term/case retrieval node.
- `src/agent/nodes/memory_write.py` - Current terminal session memory write node and trace/status emission.
- `src/agent/context/session_memory_bundle.py` - Prompt projection helpers for session bundle context.
- `src/agent/context/projectors.py` - Prompt-safe projection patterns and existing authority projection conventions.
- `src/platform/trusted_context.py` - `TrustedContextFactory`, `MerchantScopeV1`, and deny-first merchant scope derivation.
- `src/agent/rag_context/schemas.py` - `MaterialClaimAuthorityClass` and separate memory/replay/business/action context buckets.
- `src/knowledge/schemas.py` - `EvidenceRefV1`.
- `src/tools/contracts.py` - `BusinessFactRefV1`, `ToolResultV2`, and tool prompt projection contracts.
- `src/approvals/schemas.py` - `ApprovalRequestCreateCommand.evidence_refs`.
- `src/replay/decision_events.py` - Minimal decision event envelope and `memory_write_` operation prefix.
- `src/replay/validators.py` - Replay event registry and memory write event classification.
- `src/replay/schemas.py` - Strict `ReplayEventV3` DTO.

### Tests To Inspect

- `tests/memory/test_session_memory_schema.py`
- `tests/memory/test_session_memory_repository.py`
- `tests/memory/test_session_memory_bundle.py`
- `tests/memory/test_session_memory_concurrency.py`
- `tests/memory/test_session_memory_isolation.py`
- `tests/memory/test_long_term_memory_repository.py`
- `tests/memory/test_long_term_memory_service.py`
- `tests/memory/test_case_memory_retrieval.py`
- `tests/memory/test_memory_tombstones.py`
- `tests/memory/test_memory_schema.py`
- `tests/memory/test_write_isolation.py`
- `tests/agent/test_session_memory_load.py`
- `tests/agent/test_memory_write_node.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/agent/rag_context/test_authority_boundaries.py`
- `tests/agent/rag_context/test_material_claims.py`
- `tests/business/test_schemas.py`
- `tests/knowledge/test_phase21_boundaries.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src.memory.schemas.SessionMemoryBundle` already combines rolling summary, recent messages, tool summaries, and slot continuity, but its public name still says "memory bundle" rather than agent-facing "session context".
- `src.memory.session_bundle.SessionMemoryBundleService` already composes `ConversationService.load_prompt_context(...)` with `MemoryService.load_session_memory(...)`.
- `src.agent.nodes.session_memory_load.session_memory_load` already loads PostgreSQL-backed same-thread continuity and emits trace metrics with fallback reasons.
- `src.agent.nodes.long_term_memory_retrieve.long_term_memory_retrieve` already loads reviewed long-term/case prompt snippets and emits trace metrics, but its current scope derivation includes tenant/user/thread plus slots without a trusted-scope boundary.
- `src.memory.long_term.LongTermMemoryService` and `src.memory.case_memory.CaseMemoryService` already implement substantial write lifecycle behavior: PII block, tombstone match, duplicate identity, review, delete, and supersede paths.
- `src.memory.write_isolation.run_memory_side_effect_in_isolated_session(...)` already isolates memory side-effect rollback from the caller transaction.
- `src.replay` already recognizes `memory_write_started`, `memory_write_completed`, and `memory_write_failed`; Phase 31 should not build full replay coverage but can shape stable status refs.

### Established Patterns

- Public schemas generally use Pydantic models with `extra="forbid"`.
- Authority refs are typed and owned by their source service: `EvidenceRefV1` by KnowledgeService, `BusinessFactRefV1` by tool/business fact contracts.
- Trusted identity and merchant scope must come from `TrustedContextFactory` / `MerchantScopeV1`, not AgentState guesses, memory, RAG, LLM output, or prompt summaries.
- Prompt-facing projections are bounded, sanitized, and ref-oriented; raw repository rows and raw payloads do not belong in prompts.
- Phase 29.5 and Phase 30 establish no-leak merchant/business boundaries that Phase 31 must preserve for memory.

### Current Gaps To Close

- Agent-facing code still uses old `session_memory_*`, `session_memory_bundle`, and `long_term_memory_retrieve` vocabulary at graph/state boundaries.
- Existing memory refs/statuses are not yet clearly modeled as contextual-only refs distinct from evidence, business fact, action, approval, and replay refs.
- Reviewed memory retrieval currently needs a stronger trusted-scope derivation boundary before merchant/case scoped memory enters prompts.
- Session context load/reviewed memory retrieve status metadata exists in traces, but target audit-ready status ref schemas are not fixed.
- Write policy behavior exists across services, but the graph-facing decision/status contract needs to be unified and tested as the Phase 31 boundary.

</code_context>

<specifics>
## Specific Ideas

- Prefer a staged compatibility migration: add target graph-facing names and structured outputs first, then keep legacy fields as aliases until affected tests and downstream graph code are migrated.
- Consider a small `src/memory/context_refs.py` or equivalent schema area for `SessionContextRef`, `ReviewedMemoryRef`, and memory status refs.
- Consider a `MemoryContextService` facade only if it clarifies the public service boundary; avoid a thick adapter that simply preserves old names as the main public API.
- The late reviewed memory retrieval node should return both a structured `memory_context` bundle and legacy `long_term_memory` / `case_memory` aliases where needed during the transition.
- Scope derivation should be explicit and observable: trusted inputs, effective scopes, filter reasons, and fallback reasons should all be traceable without exposing raw memory content or raw private payloads.

</specifics>

<deferred>
## Deferred Ideas

- Full canonical graph migration and router vocabulary belong to Phase 32.
- RAG claim verification for memory-contaminated or unsupported claims belongs to Phase 33.
- Approval/action binding to evidence, business fact refs, risk decisions, and safety snapshots belongs to Phase 34.
- Full replay/audit event coverage for memory lifecycle decisions belongs to Phase 35.
- Release/monitoring eval gates for broad memory scope leakage belong to Phase 35.
- Review queue UI, redaction workflow, operator memory management, full memory API productization, DB/RLS redesign, and microservice extraction belong to future hardening phases.
- Tenant-wide memory policy is not enabled by default in Phase 31; if needed, it requires a later explicit product/security decision.

</deferred>

---

*Phase: 31-memory-platform-boundary*
*Context gathered: 2026-06-28*
