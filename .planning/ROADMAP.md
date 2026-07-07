# Roadmap: MOCA v2.1 Core Subsystem Hardening

## Current Milestone: v2.1 Core Subsystem Hardening

## Overview

v2.1 is a long-lived umbrella for cleaning up architecture debt across MOCA's four core subsystems tracked in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory). It began as a bounded cleanup of the tool-call platform (Phase 37-41) and is rescoped to hold subsequent subsystem-hardening phases as they arrive; defect-fix / debt-clearing work is appended as the next integer phase rather than opening a new milestone.

**Tool platform (Phase 37-41)** ran in dependency-ordered, blast-radius-aware waves: first consolidate the tool declaration source and converge the runtime/policy internals with no external contract change (Phase 37), then layer real `output_schema` declaration and `ToolRuntime` output-validation enforcement on top of the consolidated registry and shared failure helper (Phase 38), reconcile `docs/contract-spec.md` §12.5/§12.6 with the implemented contract fields (Phase 39), close source-confirmed validation/backstop gaps (Phase 40), and finally decide/remove the `UnifiedToolManager` legacy compatibility adapter so `ToolPlatform` is the sole graph-facing tool entrypoint (Phase 41). Throughout, `ToolCallContext` §8.0 identity fields stay locked and HIGH-blast-radius `ToolResultV2`/`ToolCallContext` envelope shapes are not changed.

**Intent recognition (Phase 42+)** clears the intent-subsystem debt tracked as ID-01..04 in `.planning/ARCHITECTURE-DEBT.md`. Phase 42 decoupled intent recognition into three explicit layers (semantic / risk-authorization / confidence-clarification), fixing ID-01 (keyword override of LLM) and ID-03 (three-dimension coupling); it is registered retroactively because the code was implemented and verified before formal phase registration. Phase 43 implemented multi-intent tier A for ID-04 / IDR-02.

**Memory (Phase 44+)** clears the memory-subsystem redesign debt tracked in `.planning/MEMORY-REDESIGN-DECISIONS.md`. Phase 44 delivered Case Working Context and thread-case M:N storage, Phase 45 wired it into the agent lifecycle, and Phases 46-48 carry the remaining deferred memory layering items: session context repositioning, reviewed case precedent generation, and narrow explicit long-term preference memory. Phase 48.1 is an inserted compatibility-debt cleanup discovered after Phase 48 source review; it narrows active reader debt without destructive table/API renames.

**Graph/ReAct and Canonical Agent Graph Migration (Phase 49+)** clears the accepted GAD-01 implementation debt and then migrates the outer LangGraph runtime to the canonical 15-node target architecture. Phase 49 completed the `investigate` bounded read-only ReAct main path with deterministic fallback while preserving outer graph routers and downstream gates. Phase 50 locks the no-debt migration charter for the remaining canonical graph work. Phases 51-58 are registered as macro implementation phases for baseline guardrails, `safety_pre_route`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, `risk_gate`/`approval_gate`, and final no-debt cleanup.

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
- [x] **Phase 49: Investigate Bounded ReAct Loop Migration** - Migrate `investigate` from legacy deterministic main planning to the bounded read-only ReAct loop defined in `contract-spec.md` §9.4, with ToolPlatform-only dispatch, 8-tool allowlist coverage, loop-local discovered slots, deterministic fallback, projection boundary, trace/replay iteration semantics, and no changes to intent/memory/risk/approval/action contracts (GAD-01-IMPL). Plan progress: 4/4 complete; closed as IMPLEMENTED_WITH_LIMITATIONS for replay parent-operation identity.
- [x] **Phase 50: Canonical Agent Graph Migration Spec and Guardrails** - Lock the migration charter for the remaining canonical graph migration, including the exact 15-node final graph, no `slot_extraction` graph node, Phase 49 baseline treatment, temporary compatibility policy, validation matrix, and final no-debt gates (CAGM-01). SPEC-only phase complete; downstream implementation phases pending.
- [x] **Phase 51: Canonical Graph Baseline Guardrails and Migration Matrix** - Add source-verified graph guardrails and migration matrix checks before runtime rewiring starts (CAGM-02). Plan progress: 3/3 complete; verified 2026-07-06.
- [x] **Phase 52: Safety Pre-route Node** - Extract request-risk pre-route into explicit `safety_pre_route` node before memory/context enrichment (CAGM-03). Plan progress: 3/3 complete; verified 2026-07-06.
- [x] **Phase 53: Session Context Before Intent and Contextual Intent Resolve** - Move session context before intent resolution and replace active `classify_intent` with `contextual_intent_resolve` (CAGM-04). Plan progress: 3/3 complete; verified 2026-07-06.
- [x] **Phase 54: Slot Resolution Gate Cutover** - Replace active `extract_slots` / `route_after_slots` graph boundary with canonical `slot_resolution_gate` and slot provenance (CAGM-05). Plan progress: 3/3 complete; verified 2026-07-07.
- [ ] **Phase 55: Memory Context Load Cutover** - Replace active `long_term_memory_retrieve` graph naming with canonical `memory_context_load` and contextual-only memory authority labels (CAGM-06). Not planned yet.
- [ ] **Phase 56: Recommendation Generation and RAG Claim Status Alignment** - Canonicalize `recommendation_generation` and align RAG/claim fail-closed status semantics (CAGM-07). Not planned yet.
- [ ] **Phase 57: Risk Gate and Approval Gate Canonicalization** - Replace active `assess_risk_and_approval` with canonical `risk_gate` while preserving approval pending/trusted resume semantics (CAGM-08). Not planned yet.
- [ ] **Phase 58: Canonical Graph Cutover and No-Debt Cleanup** - Cut over the active graph to the final 15-node set and remove legacy node names, dual routes, and active compatibility aliases (CAGM-09). Not planned yet.

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
| 49. Investigate Bounded ReAct Loop Migration | 4/4 | Complete with replay parent-operation limitation | 2026-07-04 |
| 50. Canonical Agent Graph Migration Spec and Guardrails | 0/0 | Complete (spec-only); implementation phases pending | 2026-07-06 |
| 51. Canonical Graph Baseline Guardrails and Migration Matrix | 3/3 | Complete    | 2026-07-06 |
| 52. Safety Pre-route Node | 3/3 | Complete | 2026-07-06 |
| 53. Session Context Before Intent and Contextual Intent Resolve | 3/3 | Complete    | 2026-07-06 |
| 54. Slot Resolution Gate Cutover | 3/3 | Complete | 2026-07-07 |
| 55. Memory Context Load Cutover | 0/TBD | Not planned | - |
| 56. Recommendation Generation and RAG Claim Status Alignment | 0/TBD | Not planned | - |
| 57. Risk Gate and Approval Gate Canonicalization | 0/TBD | Not planned | - |
| 58. Canonical Graph Cutover and No-Debt Cleanup | 0/TBD | Not planned | - |

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

### Phase 49: Investigate Bounded ReAct Loop Migration

**Goal:** Migrate `src/agent/nodes/investigate.py` from legacy deterministic `plan_next_step` as the main controller to a bounded read-only ReAct loop matching `docs/contract-spec.md` §9.4. The loop uses LLM structured planning, one planner-selected read/retrieval tool per iteration, `ToolPlatform.invoke(...)` as the only graph-facing dispatch path, projected observations only, loop-local discovered slots, deterministic fallback for invalid/unavailable planner paths, and §9.4 / §17.2 termination and trace semantics without changing intent, memory, risk, approval, action, or `contract-spec.md` contracts.
**Requirements**: GAD-01-IMPL
**Depends on:** Phase 48.1
**Plans:** 4 plans
**Success Criteria** (what must be TRUE):
  1. The main investigate control path calls an LLM structured planner that validates exactly `{next_tool, args, reason}` or `{stop, stop_reason}`; invalid JSON/schema, invalid tool, write tool, invalid args, timeout, or unavailable planner falls back to the deterministic `plan_next_step` safety net or fails closed without dispatching unsafe tools.
  2. The investigate planner allowlist covers all eight §12.4 read/retrieval tools: `get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, `get_merchant_risk`, `search_policy`, `search_sop`, and `search_case_memory`. Write tools are never visible to or executable from `investigate`.
  3. Tool dispatch remains exclusively through `ToolPlatform.invoke(...)`; no direct calls to business, knowledge, memory, repository, risk, approval, or action executor APIs are introduced in `investigate`.
  4. observation→slot回流 is loop-local scratchpad only: discovered identifiers may inform later iterations in the same investigate loop but are never written to `state["active_slots"]`, `extracted_slots`, `candidate_slots`, memory state, field registry, or `contract-spec.md`.
  5. `max_iterations`, `deadline_at`, and `max_attempts` are enforced; `termination_reason` is one of `enough_evidence`, `no_more_useful_tools`, `max_iterations_reached`, or `unrecoverable_error`; max-iteration truncation keeps lifecycle completed and does not force `retrieval_status` to insufficient.
  6. Planner-visible observations use `ToolResultProjector` / equivalent projected summaries only. Raw tool payloads, prompt-injection text, secrets, debug blobs, PII, policy bodies, and raw adapter data do not enter planner context.
  7. Each loop tool/RAG call emits a distinct trace event with `iteration`; replay can distinguish multiple tool operations under one investigate node operation without changing event schema.
  8. The phase proves no regression to Phase 43 intent behavior, Phase 44-48 memory/CWC/reviewed/long-term lifecycle behavior, `active_slots` ownership, risk/approval/action fail-closed behavior, and `evidence_refs` writer ownership.

Plans:
- [x] 49-01-PLAN.md — planner schema, validation, allowlist guard, and deterministic fallback shell.
- [x] 49-02-PLAN.md — bounded loop runtime and loop-local discovered slot scratchpad.
- [x] 49-03-PLAN.md — 8-tool coverage, projection boundary, and trace/replay metadata.
- [x] 49-04-PLAN.md — graph-level safety regression, docs/debt closeout, and final validation.

### Phase 50: Canonical Agent Graph Migration Spec and Guardrails

**Goal:** Create the binding migration charter for moving the outer Agent Graph from the current legacy/canonical mixed runtime to the accepted 15-node canonical graph without leaving final migration debt, duplicate active paths, or conflicting document authorities.
**Requirements**: CAGM-01
**Depends on:** Phase 49
**Plans:** 0 implementation plans (spec-only phase)
**Spec:** `50-SPEC.md`
**Success Criteria** (what must be TRUE):
  1. The final runtime graph is locked to exactly 15 registered canonical nodes: `receive_request`, `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `investigate`, `rag_context_build`, `recommendation_generation`, `claim_verify`, `risk_gate`, `approval_gate`, `action_draft`, `clarification_gate`, and `final_response`.
  2. `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, and `action_execution` are explicitly excluded from the current main-chain registered node set, with their internal/lifecycle/future-extension ownership stated.
  3. Phase 49 `investigate` ReAct is treated as implemented-with-limitations, not pending; future graph phases preserve its bounded read-only planner constraints.
  4. The SPEC includes source hierarchy, current-to-target matrix, temporary compatibility policy, LLM authority matrix, validation matrix, required downstream phase order, and final no-debt gates.
  5. The phase registers the migration charter in ROADMAP/STATE/REQUIREMENTS/ARCHITECTURE-DEBT so later implementation phases do not rely on competing architecture stories.

Plans:
- [x] 50-SPEC.md — canonical graph migration charter and guardrails.
- [x] 50-SUMMARY.md — spec-only closeout and downstream implementation pointer.

### Phase 51: Canonical Graph Baseline Guardrails and Migration Matrix

**Goal:** Add baseline graph guardrails and source-verified current-to-target migration matrix checks before any runtime rewiring starts, so later phases cannot drift from Phase 50's canonical graph charter.
**Requirements**: CAGM-02
**Depends on:** Phase 50
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 3/3 plans complete
**Success Criteria** (what must be TRUE):
  1. Static tests or equivalent architecture checks can identify the current active graph node set, router route values, and legacy-to-target vocabulary mappings.
  2. The migration matrix from Phase 50 is represented in a machine-checkable or test-asserted form, including all target nodes and legacy active nodes.
  3. Guardrails explicitly fail on accidental introduction of `slot_extraction` as a registered main-chain graph node.
  4. No runtime graph behavior is changed unless the phase plan explicitly scopes a harmless test-only seam.

Plans:
- [x] 51-01-PLAN.md — Static graph baseline helper and migration matrix constants.
- [x] 51-02-PLAN.md — Architecture tests for graph baseline, migration mapping, router maps, forbidden drift, and Phase 58 no-debt marker.
- [x] 51-03-PLAN.md — Architecture debt and validation closeout.

### Phase 52: Safety Pre-route Node

**Goal:** Extract current request-risk / pre-route logic from the thick intent entry into an explicit `safety_pre_route` registered node that runs immediately after `receive_request`.
**Requirements**: CAGM-03
**Depends on:** Phase 51
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 3/3 plans complete
**Success Criteria** (what must be TRUE):
  1. `receive_request -> safety_pre_route` is the active graph entry path for ordinary runs.
  2. Unsafe, unsupported, untrusted approval chat, or approval-bypass attempts do not enter memory, investigate, approval, or action paths.
  3. `safety_pre_route` does not load long-term/case memory, query business facts, verify evidence, evaluate proposed-action risk, or execute tools.
  4. Any temporary compatibility left inside `classify_intent` is recorded with owner, deletion phase, trace projection, and validation coverage per Phase 50 policy.

Plans:
- [x] 52-01-PLAN.md — Deterministic `safety_pre_route` node and unit/Nyquist coverage.
- [x] 52-02-PLAN.md — Graph/router wiring plus architecture guardrails.
- [x] 52-03-PLAN.md — Trace compatibility, docs/architecture-debt ledger, and final validation closeout.

### Phase 53: Session Context Before Intent and Contextual Intent Resolve

**Goal:** Move same-thread `session_context_load` before intent resolution and cut over the active graph intent node from thick `classify_intent` to canonical `contextual_intent_resolve`.
**Requirements**: CAGM-04
**Depends on:** Phase 52
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 3/3 plans complete
**Success Criteria** (what must be TRUE):
  1. Active graph order is `safety_pre_route -> session_context_load -> contextual_intent_resolve`.
  2. `contextual_intent_resolve` may use LLM structured output for candidate intent/operation/slots but cannot choose graph routes, satisfy slots, load long-term memory, or evaluate action risk.
  3. Same-thread pending-slot short replies such as an order/refund identifier are resolved through session context without relying on long-term/case memory.
  4. Active runtime no longer depends on `classify_intent` as the registered graph node after cutover, except for explicitly recorded temporary implementation reuse slated for deletion.

Plans:
- [x] 53-01-PLAN.md — canonical `contextual_intent_resolve` node contract and deterministic `route_after_contextual_intent` routing.
- [x] 53-02-PLAN.md — active graph cutover to `safety_pre_route -> session_context_load -> contextual_intent_resolve`.
- [x] 53-03-PLAN.md — graph vocabulary, current architecture docs, architecture debt ledger, and final validation closeout.

### Phase 54: Slot Resolution Gate Cutover

**Goal:** Replace the active `extract_slots` / `route_after_slots` graph boundary with canonical `slot_resolution_gate`, including explicit slot provenance, inheritance, invalidation, stale, conflict, and missing-slot outputs.
**Requirements**: CAGM-05
**Depends on:** Phase 53
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 3/3 plans complete
**Success Criteria** (what must be TRUE):
  1. `slot_resolution_gate` is the active registered graph node for required-slot satisfaction and clarification routing.
  2. Slot candidate extraction remains internal to `contextual_intent_resolve` / `slot_resolution_gate`; no final `slot_extraction` graph node is introduced.
  3. Slot resolution trace distinguishes explicit current-turn slots, inherited session slots, invalidated slots, conflicting slots, stale slots, resolved slots, missing required slots, and reason codes.
  4. Active runtime no longer uses `extract_slots` as the registered graph node after cutover, except for explicitly recorded temporary implementation reuse slated for deletion.

Plans:
- [x] 54-01-PLAN.md — deterministic slot provenance, non-active `route_after_slot_resolution` contract, and canonical `slot_resolution_gate` node unit coverage.
- [x] 54-02-PLAN.md — atomic active graph/router/policy/baseline cutover to `slot_resolution_gate` / `route_after_slot_resolution`.
- [x] 54-03-PLAN.md — vocabulary/API projection, current architecture docs, architecture debt ledger, and final validation closeout.

### Phase 55: Memory Context Load Cutover

**Goal:** Replace active `long_term_memory_retrieve` graph naming with canonical `memory_context_load`, positioned after slot resolution and constrained to contextual-only memory authority.
**Requirements**: CAGM-06
**Depends on:** Phase 54
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 0 plans (not planned yet)
**Success Criteria** (what must be TRUE):
  1. Active graph order routes resolved slot state into `memory_context_load` before `investigate`.
  2. Memory outputs carry usage/authority labels and cannot satisfy policy evidence, current business facts, approval/action authority, or replay truth.
  3. Long-term preference memory, reviewed case memory, and session/context surfaces remain distinct according to Phases 46-48.1.
  4. Active runtime no longer uses `long_term_memory_retrieve` as the registered graph node after cutover, except for explicitly recorded temporary implementation reuse slated for deletion.

Plans:
- [ ] TBD (run /gsd-plan-phase 55 to break down)

### Phase 56: Recommendation Generation and RAG Claim Status Alignment

**Goal:** Canonicalize `recommendation_generation` as the active generation node and align `rag_context_build` / `claim_verify` fail-closed statuses so unsafe evidence or unsupported claims cannot pass into action paths.
**Requirements**: CAGM-07
**Depends on:** Phase 55
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 0 plans (not planned yet)
**Success Criteria** (what must be TRUE):
  1. Active graph uses `recommendation_generation` as the registered node name, not `generate_recommendation`.
  2. Material claims and candidate proposed actions cannot bypass `claim_verify`.
  3. RAG status and claim verification status semantics are explicit enough for deterministic routers to fail closed on missing, stale, conflicting, unauthorized, or unsupported evidence.
  4. Active runtime no longer uses `generate_recommendation` as the registered graph node after cutover, except for explicitly recorded temporary implementation reuse slated for deletion.

Plans:
- [ ] TBD (run /gsd-plan-phase 56 to break down)

### Phase 57: Risk Gate and Approval Gate Canonicalization

**Goal:** Replace active `assess_risk_and_approval` with canonical `risk_gate` while preserving the separation between action-risk policy and `approval_gate` pending/trusted-resume state machine.
**Requirements**: CAGM-08
**Depends on:** Phase 56
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 0 plans (not planned yet)
**Success Criteria** (what must be TRUE):
  1. `risk_gate` is the active registered graph node for blocked/manual-review/approval-required/auto-draft decisions.
  2. `approval_gate` only handles approval request creation/resume, pending self-loop, edit/superseded reroute, approved draft path, and rejected/expired/invalid finalization.
  3. Ordinary chat approval text cannot become trusted approval.
  4. Active runtime no longer uses `assess_risk_and_approval` as the registered graph node after cutover, except for explicitly recorded temporary implementation reuse slated for deletion.

Plans:
- [ ] TBD (run /gsd-plan-phase 57 to break down)

### Phase 58: Canonical Graph Cutover and No-Debt Cleanup

**Goal:** Cut over the active main graph to the final 15-node canonical runtime set and remove all active legacy node names, dual runtime routes, and migration compatibility aliases.
**Requirements**: CAGM-09
**Depends on:** Phase 57
**Must read:** `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`
**Plans:** 0 plans (not planned yet)
**Success Criteria** (what must be TRUE):
  1. Active `StateGraph.add_node(...)` registrations equal the 15 canonical node names from Phase 50 exactly.
  2. Active route values no longer point to `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, or `assess_risk_and_approval`.
  3. `graph_vocabulary.py` no longer needs active runtime compatibility aliases for the main graph.
  4. Docs, tests, trace/replay/eval projection, and architecture debt are synchronized so no final migration debt remains.

Plans:
- [ ] TBD (run /gsd-plan-phase 58 to break down)
