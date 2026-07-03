# Roadmap: MOCA v2.1 Core Subsystem Hardening

## Current Milestone: v2.1 Core Subsystem Hardening

## Overview

v2.1 is a long-lived umbrella for cleaning up architecture debt across MOCA's four core subsystems tracked in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory). It began as a bounded cleanup of the tool-call platform (Phase 37-41) and is rescoped to hold subsequent subsystem-hardening phases as they arrive; defect-fix / debt-clearing work is appended as the next integer phase rather than opening a new milestone.

**Tool platform (Phase 37-41)** ran in dependency-ordered, blast-radius-aware waves: first consolidate the tool declaration source and converge the runtime/policy internals with no external contract change (Phase 37), then layer real `output_schema` declaration and `ToolRuntime` output-validation enforcement on top of the consolidated registry and shared failure helper (Phase 38), reconcile `docs/contract-spec.md` §12.5/§12.6 with the implemented contract fields (Phase 39), close source-confirmed validation/backstop gaps (Phase 40), and finally decide/remove the `UnifiedToolManager` legacy compatibility adapter so `ToolPlatform` is the sole graph-facing tool entrypoint (Phase 41). Throughout, `ToolCallContext` §8.0 identity fields stay locked and HIGH-blast-radius `ToolResultV2`/`ToolCallContext` envelope shapes are not changed.

**Intent recognition (Phase 42+)** clears the intent-subsystem debt tracked as ID-01..04 in `.planning/ARCHITECTURE-DEBT.md`. Phase 42 decoupled intent recognition into three explicit layers (semantic / risk-authorization / confidence-clarification), fixing ID-01 (keyword override of LLM) and ID-03 (three-dimension coupling); it is registered retroactively because the code was implemented and verified before formal phase registration. Phase 43 implemented multi-intent tier A for ID-04 / IDR-02.

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
| 38. output_schema Declaration + Runtime Output-Validation Enforcement | 3/3 | Complete    | 2026-07-02 |
| 39. contract-spec §12.5/§12.6 Reconciliation | 1/1 | Complete | 2026-07-02 |
| 40. Tool Contract Validation Hardening | 3/3 | Complete | 2026-07-02 |
| 41. Tool Platform Legacy Manager Cleanup | 4/4 | Complete | 2026-07-02 |
| 42. Intent Recognition Three-Layer Decoupling | 1/1 | Complete (retroactively registered) | 2026-07-02 |
| 43. Intent Recognition Multi-Intent Tier A | 3/3 complete | Complete | 2026-07-02 |
| 45. Memory Lifecycle Wiring for Case Working Context | 3/4 | In Progress |  |

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
**Plans:** 3/4 plans executed

Plans:
- [x] 45-01-PLAN.md — lifecycle contextual refs, status contracts, and graph/API-neutral adapter foundation.
- [x] 45-02-PLAN.md — active CWC read and `run_auto` thread-case link wiring at the memory-context seam.
- [x] 45-03-PLAN.md — terminal finalizer CWC writeback, deterministic projection, and failure/conflict semantics.
- [ ] 45-04-PLAN.md — contract/spec alignment, red-line sweeps, planning ledgers, and final targeted verification.
