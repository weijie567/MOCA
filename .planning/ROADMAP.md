# Roadmap: MOCA v2.1 Core Subsystem Hardening

## Current Milestone: v2.1 Core Subsystem Hardening

## Overview

v2.1 is a long-lived umbrella for cleaning up architecture debt across MOCA's four core subsystems tracked in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory). It began as a bounded cleanup of the tool-call platform (Phase 37-41) and is rescoped to hold subsequent subsystem-hardening phases as they arrive; defect-fix / debt-clearing work is appended as the next integer phase rather than opening a new milestone.

**Tool platform (Phase 37-41)** ran in dependency-ordered, blast-radius-aware waves: first consolidate the tool declaration source and converge the runtime/policy internals with no external contract change (Phase 37), then layer real `output_schema` declaration and `ToolRuntime` output-validation enforcement on top of the consolidated registry and shared failure helper (Phase 38), reconcile `docs/contract-spec.md` §12.5/§12.6 with the implemented contract fields (Phase 39), close source-confirmed validation/backstop gaps (Phase 40), and finally decide/remove the `UnifiedToolManager` legacy compatibility adapter so `ToolPlatform` is the sole graph-facing tool entrypoint (Phase 41). Throughout, `ToolCallContext` §8.0 identity fields stay locked and HIGH-blast-radius `ToolResultV2`/`ToolCallContext` envelope shapes are not changed.

**Intent recognition (Phase 42+)** clears the intent-subsystem debt tracked as ID-01..04 in `.planning/ARCHITECTURE-DEBT.md`. Phase 42 decoupled intent recognition into three explicit layers (semantic / risk-authorization / confidence-clarification), fixing ID-01 (keyword override of LLM) and ID-03 (three-dimension coupling); it is registered retroactively because the code was implemented and verified before formal phase registration. Phase 43 implemented multi-intent tier A for ID-04 / IDR-02.

**Memory (Phase 44+)** clears the memory-subsystem redesign debt tracked in `.planning/MEMORY-REDESIGN-DECISIONS.md`. Phase 44 delivered Case Working Context and thread-case M:N storage, Phase 45 wired it into the agent lifecycle, and Phases 46-48 carry the remaining deferred memory layering items: session context repositioning, reviewed case precedent generation, and narrow explicit long-term preference memory. Phase 48.1 is an inserted compatibility-debt cleanup discovered after Phase 48 source review; it narrows active reader debt without destructive table/API renames.

Code implementation is delegated to Codex per the project workflow; Claude is plan designer and adjudicator.

## Phases

**Phase Numbering:**
- Integer phases continue from the prior milestone (v2.0 ended at Phase 36); v2.1 starts at Phase 37.
- Decimal phases (37.1, 37.2): urgent insertions (marked INSERTED).

- [x] **Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation** - Single-source tool registry plus runtime `_fail` helper and declarative policy gate pipeline, with no external contract change (TPH-03, TPH-04).
- [x] **Phase 38: output_schema Declaration + Runtime Output-Validation Enforcement** - Real `output_schema` for all eight tools, enforced in the `ToolRuntime` output-validation gate as `invalid_response` mapping (TPH-01). Plan progress: 3/3 complete; DB-backed pytest passed.
- [x] **Phase 39: contract-spec §12.5/§12.6 Reconciliation** - Spec catches up to implemented contract fields via dual-AI review, without touching §8.0-locked identity fields (TPH-02). Plan progress: 1/1 complete.
- [x] **Phase 40: Tool Contract Validation Hardening** - Close source-confirmed validation/backstop gaps left after TPH-01 without changing `ToolResultV2`, `ToolCallContext` §8.0 identity fields, BusinessFactService ownership runtime semantics, or the `UnifiedToolManager` compatibility API (TPH-05).
- [x] **Phase 41: Tool Platform Legacy Manager Cleanup** - Make the API/spec decision to remove the `UnifiedToolManager` legacy compatibility adapter and converge production/tests to `ToolPlatform` as the single graph-facing entrypoint (TPH-06). Plan progress: 4/4 complete.
- [x] **Phase 43: Intent Recognition Multi-Intent Tier A** - Preserve multi-intent utterances as a bounded `TaskPlan`, process only s1 in the current turn, and surface all later steps as deferred confirmations without changing the single-intent route contract (IDR-02). Plan progress: 3/3 complete.
- [x] **Phase 44: Memory Layering — Case Working Context + thread-case Many-to-Many** - Add durable CWC storage and explicit thread-case M:N association without renaming existing memory tables (MEM-01, MEM-02). Plan progress: 4/4 complete.
- [x] **Phase 45: Memory Lifecycle Wiring for Case Working Context** - Wire CWC active read/link/writeback into real agent lifecycle while preserving contextual-only authority (MEM-01, MEM-02). Plan progress: 4/4 complete.
- [x] **Phase 46: Session Context Repositioning** - Re-scope thread-level session memory after CWC so it remains short-lived conversational context, not cross-case state (MEM-03). Plan progress: 3/3 complete.
- [x] **Phase 47: Case Precedent Repositioning and Closed-Case Candidate Generation** - Re-scope `case_memories` as reviewed precedent and add closed-case candidate generation from CWC into governed review flow (MEM-04). Plan progress: 4/4 complete.
- [x] **Phase 48: Narrow Long-Term Explicit Preference Memory** - Re-scope `long_term_memories` to explicit tenant preference memory only, without generic automatic run summarization (MEM-05). Plan progress: 4/4 complete.
- [x] **Phase 48.1: Memory Context Compatibility Debt Cleanup (INSERTED)** - Migrate active memory-context readers and case-link reads to canonical surfaces while recording remaining legacy names as explicit deferred compatibility debt. Plan progress: 4/4 complete.

## Phase Details

### Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation
**Goal**: Tool declarations resolve from one single-source registry, and the runtime failure paths plus policy authorization checks are consolidated into shared/declarative structures — all with existing tests green and no external contract shape change.
**Depends on**: Nothing within v2.1 (first phase; prior milestone Phase 36 is complete)
**Requirements**: TPH-03, TPH-04
**Success Criteria** (what must be TRUE):
  1. Adding or changing a tool requires editing only the single-source registry; `catalog._IDENTIFIER_SCHEMAS` and `manager.INVESTIGATE_TOOL_NAMES` are either derived from that registry or consistency-checked against it, and a drift check fails if the lists diverge.
  2. `ToolRuntime` failure paths produce their `(error result, projection, decision event, outcome tuple)` through one shared `_fail` helper instead of ten duplicated branches.
  3. `ToolPolicyEngine.runtime_auth` expresses its authorization checks as a declarative gate sequence rather than a hardcoded if-chain.
  4. Existing tool-platform, policy, and runtime tests remain green, and no external contract shape (`ToolResultV2`, `ToolCallContext`, `ToolPolicyDecision`, `ToolViewV1`, `ToolInvocationOutcome`) is added to, removed from, or renamed.
**Plans**: 3 plans
Plans:
- [x] 37-01-PLAN.md — registry single-source declaration rows and drift guards for catalog/manager tool lists.
- [x] 37-02-PLAN.md — `ToolRuntime._fail(...)` failure helper consolidation with safe projection/event regressions.
- [x] 37-03-PLAN.md — declarative `runtime_auth` gate sequence plus final Phase 37 contract/regression sweep.
**UI hint**: no

### Phase 38: output_schema Declaration + Runtime Output-Validation Enforcement
**Goal**: Each of the eight registered tools declares a real `output_schema` for `ToolResultV2.data`, and the `ToolRuntime` output-validation gate enforces it — schema-failing executor results become `invalid_response` instead of passing through — replacing the current no-op `{"type":"object"}`, without changing the `ToolResultV2` envelope shape.
**Depends on**: Phase 37 (output_schema is declared in the consolidated single-source registry; the enforcement gate routes failures through the shared `_fail`/`invalid_response` path)
**Requirements**: TPH-01
**Success Criteria** (what must be TRUE):
  1. Each of the eight tools (`get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, `get_merchant_risk`, `search_policy`, `search_sop`, `search_case_memory`) declares a real `output_schema`, no longer the no-op `{"type":"object"}`.
  2. An executor result whose `data` violates the declared `output_schema` is mapped to an `invalid_response` `ToolResultV2` instead of passing through the gate.
  3. A conforming executor result passes through unchanged, and the `ToolResultV2` envelope shape gains, loses, and renames no field (data-shape enforcement only).
  4. Enforcement failures flow through the shared failure path from Phase 37, and none of the 7 HIGH-blast-radius envelope consumers (`business/adapters`, `business/service`, `conversation/service`, `agent/rag_context/verifier`, `agent/nodes/action_draft`, `platform/context_projections`, `memory/search`) observe a contract change.
**Plans**: 3 plans
Plans:
- [x] 38-01-PLAN.md — validator nullable/type-union support plus TPH-01 scoped tool-set contract.
- [x] 38-02-PLAN.md — catalog real output_schema declarations and current payload acceptance/rejection tests.
- [x] 38-03-PLAN.md — runtime invalid_response enforcement tests plus high-blast consumer/contract sweep.
**UI hint**: no

### Phase 39: contract-spec §12.5/§12.6 Reconciliation
**Goal**: `docs/contract-spec.md` §12.5/§12.6 normative type definitions match the implemented contract fields — spec catches up to code — without redefining, widening, or renaming any §8.0-locked `TrustedContext`-projected identity field, via the project's dual-AI review workflow.
**Depends on**: Phase 38 (spec reflects the final implemented state, including the consolidated declarations and enforced output_schema semantics)
**Requirements**: TPH-02
**Success Criteria** (what must be TRUE):
  1. §12.5/§12.6 include the implemented-but-previously-unspecified fields: `ToolDescriptor.executor` / `exposure` / `requires_approval` / `requires_safety_snapshot` / `requires_idempotency_key`, `event_family` value `action`, `ToolPolicyDecision.runtime_available` / `availability_summary`, and `ToolCallContext.effective_at` / `approval_ref` / `safety_snapshot_ref`.
  2. No §8.0-locked `TrustedContext`-projected identity field (`tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, `trace_id`) is redefined, widened, or renamed.
  3. Planning re-checked whether commit `4dcb673` (prior memory-alignment work) incidentally modified §12.5/§12.6 before editing, and the edit is reconciled against the current on-disk file state.
  4. The spec change passed the dual-AI review workflow (`gsd-plan-checker` + Codex cross-review + Claude adjudication) before it is treated as final.
**Plans**: 1 plan
Plans:
- [x] 39-01-PLAN.md — docs-only §12.5/§12.6 contract-spec reconciliation with pre-edit commit evidence and dual-AI review gate.
**UI hint**: no

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 37. Tool Declaration + Runtime/Policy Internal Consolidation | 3/3 | Complete; DB pytest pending | 2026-07-02 |
| 38. output_schema Declaration + Runtime Output-Validation Enforcement | 3/3 | Complete | 2026-07-02 |
| 39. contract-spec §12.5/§12.6 Reconciliation | 1/1 | Complete | 2026-07-02 |
| 40. Tool Contract Validation Hardening | 3/3 | Complete | 2026-07-02 |
| 41. Tool Platform Legacy Manager Cleanup | 4/4 | Complete | 2026-07-02 |
| 42. Intent Recognition Three-Layer Decoupling | 1/1 | Complete (retroactively registered) | 2026-07-02 |
| 43. Intent Recognition Multi-Intent Tier A | 3/3 complete | Complete | 2026-07-02 |
| 44. Memory Layering — Case Working Context + thread-case Many-to-Many | 4/4 | Complete | 2026-07-03 |
| 45. Memory Lifecycle Wiring for Case Working Context | 4/4 | Complete | 2026-07-03 |
| 46. Session Context Repositioning | 3/3 | Complete | 2026-07-03 |
| 47. Case Precedent Repositioning and Closed-Case Candidate Generation | 4/4 | Complete    | 2026-07-03 |
| 48. Narrow Long-Term Explicit Preference Memory | 4/4 | Complete    | 2026-07-04 |
| 48.1. Memory Context Compatibility Debt Cleanup | 4/4 | Complete | 2026-07-04 |

### Phase 40: Tool Contract Validation Hardening

**Goal:** Close the source-confirmed tool contract validation gaps left after TPH-01 by hardening `create_coupon_grant_draft` output validation, adding a backstop test for domain-scope ownership handoff markers, and aligning the local JSON Schema subset with the descriptor keywords it advertises, without changing the `ToolResultV2` envelope, `ToolCallContext` §8.0 identity fields, BusinessFactService ownership runtime semantics, `docs/contract-spec.md`, or the `UnifiedToolManager` compatibility API.
**Requirements**: TPH-05
**Depends on:** Phase 39
**Success Criteria** (what must be TRUE):
  1. `create_coupon_grant_draft` declares a strict `output_schema` for its real `ToolResultV2.data` payload, and conforming action-draft outputs pass runtime validation while missing required fields or unexpected raw fields fail closed as `invalid_response`.
  2. `get_logistics`, `get_merchant_risk`, and `search_sop` remain on strict no-data schemas until their executors produce real payloads; this phase does not invent future payload semantics.
  3. The `requires_domain_scope_check` resource binding marker is protected by an architecture/backstop test that fails if domain-lookup business read tools can drift away from BusinessFactService merchant-scope/no-leak ownership enforcement.
  4. `validate_json_value` supports the schema keywords retained by prompt-safe projection for current descriptor use (`maxLength`, `minimum`, `maximum`, `exclusiveMaximum` in addition to existing support), and descriptor schema meta tests fail if unsupported JSON Schema keywords enter `input_schema` or `output_schema`.
  5. `ToolResultV2` envelope fields, `ToolCallContext` §8.0 identity fields, BusinessFactService runtime ownership split, `docs/contract-spec.md`, and `UnifiedToolManager` compatibility behavior have no diff.
**Plans:** 3 plans

Plans:
- [x] 40-01-PLAN.md — strict `create_coupon_grant_draft` output schema and action fake payload alignment.
- [x] 40-02-PLAN.md — local JSON Schema subset keyword support plus descriptor schema meta guard.
- [x] 40-03-PLAN.md — domain-scope marker business-boundary backstop tests and final protected no-diff verification.

### Phase 41: Tool Platform Legacy Manager Cleanup

**Goal:** Decide and implement removal of the `UnifiedToolManager` legacy compatibility adapter so `ToolPlatform` becomes the single graph-facing tool registry/dispatch entrypoint, with `docs/contract-spec.md`, production injection seams, tests, and public exports updated consistently.
**Requirements**: TPH-06
**Depends on:** Phase 40
**Success Criteria** (what must be TRUE):
  1. `docs/contract-spec.md` no longer defines `UnifiedToolManager` as a retained legacy compatibility adapter; the spec states `ToolPlatform` is the canonical graph-facing entrypoint.
  2. Production code no longer imports, exports, constructs, or special-cases `UnifiedToolManager`; legacy `action_tool_manager` unwrapping is removed or explicitly migrated to `action_tool_platform`.
  3. Tests and fake platforms no longer depend on `UnifiedToolManager` private internals such as `_platform` or `_descriptors`; equivalent coverage is migrated to `ToolPlatform`/`ToolCatalog`.
  4. `src/tools/manager.py` and `src.tools.__all__/__getattr__` no longer expose `UnifiedToolManager`, unless planning discovers a hard external API blocker and records a stop decision.
  5. The phase receives an implementation code review before milestone archive because it changes public compatibility surface and crosses production, tests, and spec.
**Plans:** 4 plans

Plans:
- [x] 41-01-PLAN.md — spec/API decision cleanup plus `_side_effect_allowed` relocation.
- [x] 41-02-PLAN.md — production injection seam and manager-shaped test fake migration to `ToolPlatform`.
- [x] 41-03-PLAN.md — delete `UnifiedToolManager`, public export, and compatibility tests after coverage migration.
- [x] 41-04-PLAN.md — implementation code review, final verification, and Phase 41 completion record.

### Phase 42: Intent Recognition Three-Layer Decoupling (RETROACTIVE RECORD)

> **Retroactive registration.** The code for this phase was designed by Claude (spec: `.planning/intent-layering-codex-brief.md`), implemented by Codex, and verified green **before** it was formalized as a GSD phase. It did **not** run the `gsd-plan-phase` → `gsd-plan-checker` → `execute` flow. `42-01-PLAN.md` and `42-01-SUMMARY.md` are record-only compatibility artifacts for GSD plan/summary counting; there is intentionally no `42-PLAN-REVIEW.md`. The authority artifacts are `42-CONTEXT.md`, `42-01-SUMMARY.md`, and `42-VERIFICATION.md`, anchored to commit `a0a98e4`. This is a truthful record of a completed refactor, not a re-enacted plan.

**Goal:** Decouple intent recognition's three tangled responsibilities — semantic understanding, risk authorization, and confidence/clarification — into three explicit, single-direction, independently testable layers that communicate only through frozen data contracts (`SemanticIntent` / `RiskDecision` / `ClarificationDecision`), turning implicit "who wins" arbitration into explicit, test-locked code. Behavior-equivalent refactor except one intended ID-01 fix.
**Requirements**: IDR-01
**Depends on:** Phase 25 (v1.8 intent routing safety hardening; the classification trace / risk-tier / clarification surfaces this phase refactors)
**Success Criteria** (what is TRUE, verified against commit `a0a98e4`):
  1. Three frozen-dataclass layer contracts exist in `src/agent/intent_policy.py`: `SemanticIntent` (semantic), `RiskDecision` (risk/authorization), `ClarificationDecision` (confidence/clarification).
  2. Keyword scanning (`derive_keyword_signals`) and winner selection (`arbitrate_intent`) are split into separate functions; keyword candidates may override the LLM primary only when the LLM itself listed the intent or raw confidence is below the ordinary threshold (ID-01 fix), locked by tests in `tests/agent/test_intent_routing.py`.
  3. Risk resolution is a declarative `RISK_POLICY_TABLE` + `resolve_risk_decision(...)`, behavior-equivalent to the old `resolve_risk_tier` if-elif (per-combination equivalence tests), with the old dead branch removed (ID-03).
  4. `classification_trace` records all three layer outputs (`semantic_intent` / `risk_decision` / `clarification_decision`) for replay.
  5. `IntentResultV3` wire schema, `docs/contract-spec.md`, and `src/agent/prompts.py` few-shot are unchanged; N=1 single-intent behavior is byte-equivalent except the one registered ID-01 exemption (`"这个不算投诉吧，我就是问下退款进度"`).
**Plans:** 1 record-only plan/summary pair (retroactive accounting artifact; no pre-execution plan review)

Plans:
- [x] 42-01-PLAN.md / 42-01-SUMMARY.md — record-only retroactive accounting artifacts for the three-layer decoupling refactor (design → Codex implementation → green verification), anchored to commit `a0a98e4`.

**Deferred to a later phase (not this one):** ID-02 confidence calibration (still 🔴; only a `calibrated_confidence` parameter placeholder landed). ID-04 multi-intent tier A was handled by Phase 43.

### Phase 43: Intent Recognition Multi-Intent Tier A

**Goal:** Extend intent recognition from a single winner into a bounded tier-A task plan: preserve multiple user requests in `TaskPlan`, normalize only explicit modifier cases, execute only the current turn's safe read-only prefix, and surface all non-executed steps as deferred confirmations in trace and final response.
**Requirements**: IDR-02
**Depends on:** Phase 42 (three-layer intent contracts; `SemanticIntent` / `RiskDecision` / `ClarificationDecision` are the foundation for plan construction and read-only prefix decisions)
**Success Criteria** (what must be TRUE):
  1. `TaskStep` and `TaskPlan` frozen data contracts exist alongside the Phase 42 intent-layer contracts, with stable step IDs, per-step intent/operation/entities/dependencies/relation, and a terminal step ID.
  2. N=1 plans are exact behavior-equivalent fallbacks to the existing single-intent route surface: `primary_intent`, `requested_operation`, `risk_tier`, `route_decision`, and current tests do not regress.
  3. N>1 plans are derived deterministically from the existing single LLM result plus keyword signals; no new LLM call, no `IntentResultV3` schema change, no prompt change, no new risk-tier enum.
  4. Modifier normalization is conservative: `small_talk` is dropped, secondary `complaint_escalation` is folded only as severity for the allowed main intents, and independent query/draft/action intents remain explicit steps.
  5. Tier A execution gating only permits s1 to be current-turn effective work: `executable_prefix` is `[s1]` only when s1 is `read_only`, otherwise `[]`; every s2+ step is recorded as `deferred_steps` and is not executed in the same turn.
  6. `classification_trace` records the task plan, executable prefix, deferred steps, and normalization/fallback decisions; final responses visibly mention deferred steps and the complaint-folding safety note when applicable.
  7. Invalid plans fail closed to the existing single-intent path and record `plan_invalid_fallback_single`, rather than throwing, silently dropping requests, or auto-running high-risk work.
**Plans:** 3 plans

Plans:
- [x] 43-01-PLAN.md — intent-policy `TaskStep` / `TaskPlan` contracts, deterministic normalization, s1-only prefix selection, fail-closed behavior, and policy tests.
- [x] 43-02-PLAN.md — `AgentState` / `receive_request` reset and `classify_intent` task-plan wiring while preserving current single-intent route fields and guards.
- [x] 43-03-PLAN.md — final-response deferred-step presentation, complaint-folding safety note, architecture-debt ledger update, and full regression/no-go verification.

### Phase 44: Memory Layering — Case Working Context + thread↔case Many-to-Many

**Goal:** Introduce a case-scoped durable working-context layer (new table `case_working_contexts`) plus a thread↔case association table, so a refund case's working state (customer request, claims, verified facts, missing info, actions taken, policy refs, agent recommendations + staff decisions, pending tasks, commitments, next action) survives across conversation threads and agent/staff handoffs through a durable read/write surface. Case Working Context is non-authoritative (`authority_class = contextual_only`), human-correctable, versioned, and bound to trusted `run_id` / `source_ref`; claims and verified facts are stored separately; tool-derived facts store only references/summaries with `observed_at` and never replace the business system; policy body and sensitive raw text are never stored. Phase 44 provides the callable audited write service; graph run-completion auto-update hook wiring is deferred to Phase 45 memory lifecycle wiring. This phase does NOT rename `case_memories` / `long_term_memories` and does NOT change the session-memory layer.
**Requirements**: MEM-01, MEM-02
**Depends on:** Phase 43
**Design input:** `.planning/MEMORY-REDESIGN-DECISIONS.md` (D1–D5; P1 = many-to-many, P2 = standalone table, P3 = long_term kept narrow). Red line D5: do not rename `case_memories` / `long_term_memories`.
**Success Criteria** (what must be TRUE):
  1. A new `case_working_contexts` table exists, scoped by `(tenant_id, case_id)`, holding the structured working-state fields above, with `version`, `updated_by_run_id`, and `source_ref` columns; it is distinct from `session_memories`, `case_memories`, and `long_term_memories`.
  2. Every persisted Case Working Context is marked `authority_class = contextual_only` and carries claim/fact separation (claims store `verified` flag + source; tool-derived facts store reference/summary + `observed_at`), never storing policy body or sensitive raw text.
  3. Case Working Context is human-correctable and versioned: manual edits are supported and each write bumps `version` and records `updated_by_run_id`, preserving prior version history.
  4. A thread↔case association table supports many-to-many (a thread may touch multiple cases; a case may span multiple threads/handoffs), providing an additive working-context join surface without dropping or rewriting existing single-case linkage behavior.
  5. `case_memories` and `long_term_memories` table names are unchanged; the session-memory layer (`session_memories`) behavior is unchanged.
  6. Reading a case's working context is possible across threads/handoffs (keyed by `case_id`, not `thread_id`), enabling continuity when a staff member reopens a ticket or a case is handed off.
  7. Deferred items (① session-memory changes, ③ case_memories repositioning / precedent extraction, long_term narrow explicit-preference extraction, and graph run-completion auto-update hook wiring) are NOT implemented in this phase and remain recorded in `.planning/MEMORY-REDESIGN-DECISIONS.md`.
**Plans:** 4 plans
**Completed:** 2026-07-03

Plans:
- [x] 44-01-PLAN.md — DDL layer: thread_case_links + case_working_contexts + case_working_context_revisions tables, memory_write_events enum extension (B4), ORM models (wave 1).
- [x] 44-02-PLAN.md — case-identity resolver refund_case_no→refund_cases.id (B2), CWC content schemas with claim/fact separation, versioned read/write repository with append-only revisions (B5) (wave 2).
- [x] 44-03-PLAN.md — thread↔case link write lifecycle + dedup at explicit linkage point (B3), CWC write service with audit event + isolated session (wave 3).
- [x] 44-04-PLAN.md — contract-spec §13 CWC + additive M:N normative note (B6), alignment test, DEFER trace, phase verification sweep + dual-AI review checkpoint (wave 4).

### Phase 45: Memory Lifecycle Wiring for Case Working Context

**Goal:** Wire the Phase 44 Case Working Context foundation into the real agent-run lifecycle through a stable lifecycle adapter: resolve canonical `refund_cases.id`, link the current thread with `link_source="run_auto"`, load active CWC as contextual-only memory input before investigation/recommendation, and write deterministic CWC updates after successful completed terminal runs without making memory authority for policy/risk/approval/action/replay.
**Requirements**: MEM-01, MEM-02 (deferred lifecycle hooks from Phase 44)
**Depends on:** Phase 44
**Plans:** 4/4 plans complete

Plans:
- [x] 45-01-PLAN.md — lifecycle contextual refs, status contracts, and graph/API-neutral adapter foundation.
- [x] 45-02-PLAN.md — active CWC read and `run_auto` thread-case link wiring at the memory-context seam.
- [x] 45-03-PLAN.md — terminal finalizer CWC writeback, deterministic projection, and failure/conflict semantics.
- [x] 45-04-PLAN.md — contract/spec alignment, red-line sweeps, planning ledgers, and final targeted verification.

### Phase 46: Session Context Repositioning

**Goal:** Reposition `session_memories` after Case Working Context has landed: keep session context as thread-scoped, short-lived conversational memory only, make its boundary explicit in contract/docs/tests, and prevent it from carrying cross-case durable working state, reviewed precedent, long-term preference memory, policy evidence, business facts, approval/action authority, or replay truth.
**Requirements**: MEM-03
**Depends on:** Phase 45
**Plans:** 3/3 plans complete
**Design input:** `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-1.
**Success Criteria** (what must be TRUE):
  1. The intended role of `session_memories` is documented as thread-scoped temporary conversational context, distinct from `case_working_contexts`, `case_memories`, and `long_term_memories`.
  2. Existing session-memory read/write behavior is audited and either left unchanged with explicit contract tests or narrowed with migration-safe compatibility notes.
  3. Static/contract tests prevent session memory from becoming cross-case durable state, reviewed precedent, tenant preference memory, policy evidence, business fact authority, approval/action authority, or replay truth.
  4. No destructive rename/drop of `session_memories`, `case_memories`, `long_term_memories`, `case_working_contexts`, or `conversation_threads.case_id` occurs unless a later plan explicitly proves and reviews a migration need.
  5. DEFER-2 and DEFER-3 remain out of scope and are carried forward by name.

Plans:
- [x] 46-01-PLAN.md — docs/contract/audit reconciliation for the post-CWC session context boundary.
- [x] 46-02-PLAN.md — static contract tests locking MEM-03 red lines and approved pytest entrypoints.
- [x] 46-03-PLAN.md — behavioral validation and migration-safe code narrowing only if tests expose real drift.

### Phase 47: Case Precedent Repositioning and Closed-Case Candidate Generation

**Goal:** Reposition `case_memories` as reviewed closed-case precedent, not active case state, and introduce a governed candidate-generation path from finalized Case Working Context into the existing reviewed memory workflow when a case closes.
**Requirements**: MEM-04
**Depends on:** Phase 46
**Plans:** 4/4 plans complete
**Design input:** `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-2.
**Success Criteria** (what must be TRUE):
  1. `case_memories` semantics are documented and test-locked as reviewed case precedent, not active working state and not a replacement for `case_working_contexts`.
  2. A closed-case candidate generation boundary is designed from finalized CWC content into the governed memory candidate/review flow, preserving `needs_review`, audit event, PII, tenant, source-ref, and reviewer semantics.
  3. Retrieval is metadata-first where applicable; vector search remains optional and does not become the only route for exact tenant/case/merchant scoped precedent retrieval.
  4. Candidate generation keeps claims/facts/policy refs separated and never stores policy body text, raw tool payloads, approval/action authority bodies, replay/debug blobs, or sensitive raw PII.
  5. No destructive rename/drop of `case_memories`, `long_term_memories`, `case_working_contexts`, or `conversation_threads.case_id` occurs.
  6. DEFER-3 remains out of scope and is carried forward by name.

Plans:
- [x] 47-01-PLAN.md — contract/static alignment and `closed_case_cwc_candidate` review-required source-type foundation.
- [x] 47-02-PLAN.md — trusted closed-case CWC projection service seam with terminal status, scope, and prompt-safe projection tests.
- [x] 47-03-PLAN.md — governed write lifecycle through existing case-memory review/audit/dedupe path.
- [x] 47-04-PLAN.md — metadata/text retrieval, tool/reviewed-context stability, docs, DEFER-3, and final validation.

### Phase 48: Narrow Long-Term Explicit Preference Memory

**Goal:** Narrow `long_term_memories` to explicit tenant preference memory only, with writes coming from explicit user/admin/reviewed preference intent rather than ordinary automatic run summarization.
**Requirements**: MEM-05
**Depends on:** Phase 47
**Plans:** 4/4 plans complete
**Design input:** `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-3 and P3.
**Success Criteria** (what must be TRUE):
  1. `long_term_memories` is documented and test-locked as narrow explicit preference memory, not operational business state, policy authority, approval/action authority, or generic run summary storage.
  2. Ordinary completed runs do not automatically write long-term memory unless they contain an explicit remember/preference path accepted by the phase plan.
  3. Writes are tenant-scoped, audited, governed by PII/review policy, and carry source/run provenance.
  4. The phase preserves `long_term_memories` table identity and replay/eval contracts unless a reviewed plan proves a migration is necessary.
  5. Interaction with Phase 46 session memory and Phase 47 case precedent is documented so the three memory layers do not compete for the same content.

Plans:
- [x] 48-01-PLAN.md — contract/docs/static semantic locks for explicit preference-only long-term memory.
- [x] 48-02-PLAN.md — source policy/service guardrails and semantic episode preference-candidate narrowing.
- [x] 48-03-PLAN.md — deterministic chat preference capture and admin-only preference save API.
- [x] 48-04-PLAN.md — retrieval filtering, review publishing as `human_reviewed`, correction/tombstone lifecycle, and final validation.

### Phase 48.1: Memory Context Compatibility Debt Cleanup (INSERTED)

**Goal:** Clean up the source-confirmed memory compatibility debt that still affects active readers after Phase 48: migrate `conversation_threads.case_id` readers to `thread_case_links`, migrate session-context consumers away from direct `session_memory/session_memory_bundle` dependencies, and introduce a canonical reviewed-memory routing hint while retaining old names as compatibility aliases.
**Requirements**: MEM-COMPAT-01
**Depends on:** Phase 48
**Plans:** 4 plans
**Success Criteria** (what must be TRUE):
  1. Active code paths that need thread↔case relationships read from `thread_case_links` / `ThreadCaseLinkRepository`; `conversation_threads.case_id` remains only legacy storage/write compatibility or historical display, not the canonical reader source.
  2. Agent routing, working-state projection, and prompt/session context helpers read `session_context` / `session_context_bundle` as canonical; `session_memory` / `session_memory_bundle` remain only compatibility projection for old traces/tests.
  3. A canonical routing hint such as `needs_reviewed_memory_context` is introduced for reviewed memory context loading; `needs_long_term_memory` remains as a backward-compatible alias only.
  4. The phase does not rename/drop `session_memories`, `long_term_memories`, `case_memories`, `case_working_contexts`, `conversation_threads.case_id`, public memory API routes, or graph trace names unless a later plan separately proves and reviews a migration.
  5. Deferred compatibility names are recorded in `.planning/ARCHITECTURE-DEBT.md` with explicit status so future cleanup does not lose them.

Plans:
- [x] 48.1-01-PLAN.md — migrate active conversation thread-case readers to `ThreadCaseLinkRepository` / `thread_case_links` while preserving legacy `case_id` metadata.
- [x] 48.1-02-PLAN.md — make routing, working-state projection, and prompt/session helper reads canonical-first on `session_context` / `session_context_bundle`.
- [x] 48.1-03-PLAN.md — add canonical `needs_reviewed_memory_context` routing hint while keeping `needs_long_term_memory` as an alias and preserving graph node names.
- [x] 48.1-04-PLAN.md — add static guards, update architecture-debt status, and run the final Phase 48.1 validation gate.
