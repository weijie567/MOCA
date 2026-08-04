# Phase 47: Case Precedent Repositioning and Closed-Case Candidate Generation - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning
**Source:** `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-2, MEM-04, Phase 44-46 memory decisions, codebase scout, and user-authorized execution-style discussion.

<domain>
## Phase Boundary

Phase 47 repositions the existing `case_memories` layer after Case Working Context (CWC) and session-context boundaries have landed.

This phase has two responsibilities:

1. Lock `case_memories` as reviewed historical precedent, not active case working state and not a replacement for CWC.
2. Introduce a governed closed-case candidate path: when a refund case reaches a trusted closed/resolved terminal business state, finalized CWC content may be projected into a `CaseMemoryWriteCandidate`, submitted through the existing `CaseMemoryService.submit_case_memory_candidate(...)` review workflow, audited in `memory_write_events`, and kept invisible to planner-facing retrieval until approved.

This is not a schema-redesign phase. The existing `case_memories` table already has review status, source refs, content/source identity hashes, prompt-safe retrieval filters, metadata indexes, optional vector embedding, and review API surfaces. Phase 47 should reuse those surfaces unless planning proves a concrete additive gap.

In scope:
- Contract/docs/tests that make `case_memories = reviewed precedent, NOT active case state` executable.
- Closed-case candidate projection from CWC into case-memory candidate shape.
- Governance guarantees: default `needs_review`, audit event, PII block, tenant/source-ref binding, duplicate/tombstone behavior, and review-before-retrieval.
- Metadata-first retrieval tests and any small narrowing needed so exact scoped retrieval works without embeddings.
- A trusted close-trigger seam if the current product has no real close endpoint.

Out of scope:
- Renaming, dropping, or retyping `case_memories`, `long_term_memories`, `case_working_contexts`, `conversation_threads.case_id`, or `thread_case_links`.
- Treating a normal completed agent run as a case-close event.
- Building a reviewer UI or new public refund-case close endpoint.
- ReAct / graph-node architecture refactor.
- Graph-global `active_slots` writer semantics.
- Phase 48 long-term explicit-preference memory.
- Automatic publishing of generated candidates as reviewed precedents.
</domain>

<decisions>
## Implementation Decisions

### D-47-01 - Preserve table identity
- Phase 47 must not rename or replace `case_memories`; semantics are locked by docs/tests and small additive code only.
- `case_working_contexts` remains the current-case working-state table. `case_memories` remains reviewed precedent.

### D-47-02 - Candidate generation is automatic, publication is not
- Closed-case generation may be automatic only up to candidate creation.
- Generated candidates default to `needs_review` and must be excluded from `retrieve_reviewed(...)`, `reviewed_memory_context`, and `search_case_memory` until a reviewer approves them.
- `human_reviewed` / `explicit_admin_preference` may stay auto-approved under the existing policy; closed-case CWC candidates must not use those source types.

### D-47-03 - Use the existing case memory review pipeline
- Reuse `CaseMemoryWriteCandidate`, `CaseMemoryService.submit_case_memory_candidate(...)`, `CaseMemoryRepository.emit_write_event(...)`, `list_pending_review`, and approve/reject/delete/forget actions.
- Do not create a second review queue, second audit table, or parallel case-precedent store.
- Prefer an explicit additive source type such as `closed_case_cwc_candidate` and classify it as review-required. If planning chooses not to add a source type, it must explain why `summary_candidate` is sufficient and still preserve closed-case provenance in `source_ref_json`.

### D-47-04 - Close trigger must be trusted
- Current code has `RefundCase.status` but no dedicated close-transition service or public close endpoint. Phase 47 must not infer "closed case" from `AgentRun.final_status == "completed"`.
- The first implementation should expose a trusted internal trigger/service seam, for example `generate_closed_case_precedent_candidate(...)`, taking explicit tenant, case, run, close source, and closed-at inputs.
- If a real refund-case status transition hook exists by planning time, wire to that hook only. If it does not exist, deliver the seam and tests without inventing a public close API.
- The closure predicate/status allowlist must be explicit and test-covered; ambiguous or non-terminal states such as `open` / `reviewing` skip with a reason.

### D-47-05 - Source CWC is the finalized snapshot, not authority
- Source content comes from the active CWC row/revision at close time and any trusted close/outcome metadata passed to the trigger.
- CWC remains `contextual_only`; the generated case-memory candidate is a reviewed-precedent candidate, not policy evidence, current business fact authority, approval authorization, action authorization, action outcome truth, audit truth, or replay truth.
- If no active CWC exists, tenant/case identity is missing, CWC is PII-blocked, or content is not projectable, generation skips with an explicit reason and no `case_memories` row.

### D-47-06 - Projection is deterministic and allowlisted
- Projection may use CWC fields such as customer request, issue type, verified facts summaries, policy refs, actions taken summaries, recommendations, staff decisions, commitments, and final outcome metadata.
- Projection must keep claims and verified facts distinct in source processing; it must not silently promote claims to verified facts.
- Case-memory output may summarize historical outcome and applicability, but must store prompt-safe text and refs only.
- Forbidden payloads: policy body text, raw tool payloads, raw conversation/debug/replay blobs, approval authority bodies, action authority bodies, sensitive raw PII, and current-business-state truth presented as authoritative.

### D-47-07 - Retrieval scope is not source identity
- `CaseMemory.scope_type/scope_id` is the retrieval scope. `source_ref_json.business_object_type/business_object_id` is the source case identity.
- Closed-case precedents should be reusable where the product can safely retrieve them. Prefer merchant-scope storage when the closed refund case can resolve through `RefundCase -> Order.merchant_id`; fall back conservatively when the merchant cannot be resolved.
- Exact case-scoped retrieval must remain supported for audit/debug and tests, but planner-facing merchant retrieval must not miss all generated precedents merely because their source case id lives in `source_ref_json`.
- Do not widen `ToolCallContext` identity fields to carry case id; those fields are locked by the tool-platform contract.

### D-47-08 - Metadata-first retrieval remains the MVP path
- Retrieval must work without embeddings by using tenant + scope + case type + policy family/version + text filters/rerank.
- Optional vector similarity may remain as an additional ranking mode, but embeddings must not become mandatory for exact scoped retrieval.
- Needs-review, rejected, deleted, expired, tombstoned, cross-tenant, and non-prompt-safe PII rows must stay excluded.

### D-47-09 - Idempotency and audit
- Candidate writes must be idempotent for the same tenant/source case/CWC version/close event or equivalent source identity.
- Existing content/source identity hashes and duplicate/tombstone handling should be reused before adding new columns.
- Every write/skip/needs_review outcome must produce or preserve an observable `memory_write_events` record where the existing service already does so.

### D-47-10 - Verification entrypoint
- Every automated test command in Phase 47 plans must use the MOCA-approved test entrypoint: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- Bare `pytest` or bare `python -m pytest` is invalid verification.

### Planner's Discretion
- Exact service/module names for closed-case projection.
- Whether the first plan adds `closed_case_cwc_candidate` as a source type or reuses an existing review-required source type with stronger source refs.
- Exact projection wording and truncation limits, provided it is deterministic and prompt-safe.
- Whether implementation needs a tiny repository helper for `RefundCase -> Order.merchant_id` resolution or keeps it inside the candidate service.
- Exact plan split, as long as docs/static tests, candidate service, retrieval/gate behavior, and final validation remain separate enough for bounded execution.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 47 Inputs
- `.planning/MEMORY-REDESIGN-DECISIONS.md` - DEFER-2, D3 metadata-first retrieval, D4 closed-case candidate rule, and D5 naming red line.
- `.planning/REQUIREMENTS.md` - MEM-04.
- `.planning/ROADMAP.md` - Phase 47 scope and success criteria.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-CONTEXT.md` - CWC table/revision/authority foundation.
- `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-CONTEXT.md` - CWC read/link/write lifecycle and case identity rules.
- `.planning/phases/46-session-context-repositioning/46-CONTEXT.md` - session context boundary and Phase 47 defer trace.
- `.planning/phases/46-session-context-repositioning/46-VALIDATION.md` - confirms Phase 46 kept DEFER-2 out of scope.

### Normative Contract
- `docs/contract-spec.md` Section 13.4 - case memory semantic lock and authority boundary.
- `docs/contract-spec.md` Section 13.4a - CWC distinction, source/ref rules, and contextual-only authority.
- `docs/contract-spec.md` Section 13.5 / 13.6 - memory write/storage constraints.
- `docs/current-implementation-map.md` - planner-facing `search_case_memory` maps to reviewed case memory.
- `docs/architecture-overview.md` - high-level memory layer split after Phase 46.

### Existing Implementation Surfaces
- `src/db/models.py` - `CaseMemory`, `CaseWorkingContext`, `MemoryWriteEvent`, `RefundCase`, `Order`.
- `src/memory/case_memory.py` - case-memory repository/service, review workflow, search filters, duplicate/tombstone/audit behavior.
- `src/memory/schemas.py` - `CaseMemoryWriteCandidate`, `CaseMemorySearchRequest`, `MemorySourceRefV1`, source/review literals.
- `src/memory/policy.py` - case-memory write policy and source-type review rules.
- `src/memory/case_working_context.py` - active CWC read/write and revision model.
- `src/memory/case_working_context_schemas.py` - CWC content shape and prompt-safe fields.
- `src/memory/case_working_context_lifecycle.py` - deterministic terminal CWC projection and source-ref patterns.
- `src/memory/context_service.py` - reviewed memory bundle and `CaseMemorySearchRequest` construction.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` - separate reviewed-memory and CWC read paths.
- `src/tools/executors/memory.py` - planner-facing `search_case_memory` executor.
- `src/api/routers/memory.py` and `src/api/schemas/memory.py` - existing pending review and review-action API surfaces.
- `src/repositories/refund_repo.py` and `src/api/routers/refund_cases.py` - current refund-case read surface; no close-transition service exists now.

### Tests And Verification Anchors
- `tests/memory/test_case_memory_retrieval.py`
- `tests/memory/test_memory_policy.py`
- `tests/memory/test_reviewed_memory_context_boundary.py`
- `tests/memory/test_phase45_contract_alignment.py`
- `tests/memory/test_phase46_session_context_alignment.py`
- `tests/agent/test_case_working_context_lifecycle.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/tools/test_catalog.py`
- `tests/test_memory_review_api.py`
- `tests/test_agent_runs_api.py`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CaseMemoryService.submit_case_memory_candidate(...)` already writes `needs_review` candidates, emits `memory_write_events`, blocks prohibited/sensitive PII, checks tombstones, and dedupes active content/source identities.
- `CaseMemoryService.retrieve_reviewed(...)` returns only published `auto_approved` / `approved` rows through metadata filters and prompt-safe PII guards.
- `CaseMemoryService.approve_case_memory(...)` and `reject_case_memory(...)` already emit observable review events.
- `MemoryToolExecutor` already uses reviewed `CaseMemoryService.retrieve_reviewed(...)` for `search_case_memory`.
- `CaseWorkingContextRepository.read_active(...)` can provide the close-time CWC snapshot by `(tenant_id, case_id)`.
- `RefundCase` links to `Order`, and `Order` carries `merchant_id`, which can support merchant-scope precedent storage.

### Existing Gaps
- No current service represents a trusted refund-case close transition.
- `RefundCase.status` is a free string in current model/tests; seeds mostly use `reviewing` and `open`.
- `CaseMemorySourceType` has no dedicated closed-CWC source type.
- Planner-facing `search_case_memory` scopes tenant/user/thread/merchant from `ToolCallContext`; it does not carry case id and should not be widened for Phase 47.
- Current docs already state the case-memory semantic lock, but MEM-04 still needs Phase 47-specific closed-case candidate and metadata-first behavior locked by tests.

### Established Patterns To Preserve
- Memory remains contextual-only.
- Policy evidence, business facts, approval/action authority, and replay truth stay in their own services.
- Memory side effects should not roll back user-facing completed responses or authoritative business state.
- Static alignment tests are acceptable for semantic red lines and destructive-schema guards.
- GSD verification commands must use the approved uv pytest entrypoint.
</code_context>

<specifics>
## Specific Ideas

- Add `src/memory/case_precedent.py` or equivalent with a small service that reads active CWC, resolves retrieval scope, projects a case-memory candidate, and calls `CaseMemoryService.submit_case_memory_candidate(...)`.
- Projection output shape:
  - `scope_type`: preferably `merchant` when resolvable, otherwise conservative fallback.
  - `scope_id`: resolved merchant id or fallback scope id.
  - `case_type`: CWC issue type or normalized refund case reason/category.
  - `summary`: concise historical precedent statement.
  - `excerpt`: analyst-facing prompt-safe precedent snippet.
  - `applicability`: when this precedent is relevant.
  - `outcome`: final business/customer/merchant outcome summary if trusted close metadata exists.
  - `caveats`: fixed wording that precedent is not policy evidence or action authority.
  - `policy_refs`: CWC policy refs as refs only.
  - `source_ref`: source type, run id, case id, close event id, and CWC row/version/revision identity where possible.
- Add static tests that forbid CWC-to-case projection from importing/constructing `EvidenceRefV1`, approval/action authority DTOs, replay DTOs, or raw tool payload fields.
- Add behavioral tests proving:
  - non-terminal refund case status skips;
  - terminal close with active CWC creates one `needs_review` case-memory candidate and event;
  - duplicate close event / same CWC version dedupes;
  - sensitive/prohibited PII blocks;
  - candidate is pending-review visible but not retrieve-reviewed visible until approved;
  - metadata/text retrieval works without embedding;
  - merchant-scoped generated precedent is visible to merchant-scoped reviewed search after approval.
</specifics>

<suggested_plan_split>
## Suggested Plan Granularity

The first Phase 47 plan set should avoid a single oversized plan. A likely split:

1. **47-01:** Docs/contract/static semantic locks for case precedent, closed-case candidate scope, destructive table red lines, and approved pytest entrypoints.
2. **47-02:** Closed-case CWC-to-case-memory candidate projection service, source type/policy rules, provenance, idempotency, and PII/skip tests.
3. **47-03:** Retrieval and review-flow alignment: pending exclusion, approval visibility, merchant/case metadata-first retrieval, and planner-facing executor guard tests.
4. **47-04:** Contract-spec delta cleanup, DEFER-3 carry-forward, final verification, security/UAT/validation prep artifacts.

Planning may merge or split differently if source inspection proves a smaller file surface, but do not combine docs/static locks, service implementation, retrieval wiring, and final validation into one plan.
</suggested_plan_split>

<deferred>
## Deferred Ideas

- Phase 48: narrow explicit tenant/user/merchant preference memory in `long_term_memories`.
- Future product/business phase: a real refund-case close/update workflow or public close endpoint, if product scope requires one.
- Future graph/agent phase: ReAct node architecture and loop-local discovered slot memory.
- Optional future cleanup: remove or further quarantine legacy session-derived precedent code only after reviewed case precedent coverage is sufficient.
- Optional future ranking work: embeddings or stronger semantic reranking for case precedents after metadata-first MVP has real data.
</deferred>

---

*Phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener*
*Context gathered: 2026-07-03*
