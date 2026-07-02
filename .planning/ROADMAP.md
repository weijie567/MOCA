# Roadmap: MOCA v2.1 Tool Platform Hardening

## Overview

v2.1 is a bounded cleanup of the tool-call platform's contract debt, implementation gaps, and legacy compatibility surface. The journey runs in dependency-ordered, blast-radius-aware waves: first consolidate the tool declaration source and converge the runtime/policy internals with no external contract change (Phase 37), then layer real `output_schema` declaration and `ToolRuntime` output-validation enforcement on top of the consolidated registry and shared failure helper (Phase 38), reconcile `docs/contract-spec.md` §12.5/§12.6 with the implemented contract fields (Phase 39), close source-confirmed validation/backstop gaps (Phase 40), and finally decide/remove the `UnifiedToolManager` legacy compatibility adapter so `ToolPlatform` is the sole graph-facing tool entrypoint (Phase 41). Throughout, `ToolCallContext` §8.0 identity fields stay locked and HIGH-blast-radius `ToolResultV2`/`ToolCallContext` envelope shapes are not changed. Code implementation is delegated to Codex per the project workflow; Claude is plan designer and adjudicator, and these are planning/spec phases, not "Claude writes all the code" phases.

## Phases

**Phase Numbering:**
- Integer phases continue from the prior milestone (v2.0 ended at Phase 36); v2.1 starts at Phase 37.
- Decimal phases (37.1, 37.2): urgent insertions (marked INSERTED).

- [x] **Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation** - Single-source tool registry plus runtime `_fail` helper and declarative policy gate pipeline, with no external contract change (TPH-03, TPH-04).
- [x] **Phase 38: output_schema Declaration + Runtime Output-Validation Enforcement** - Real `output_schema` for all eight tools, enforced in the `ToolRuntime` output-validation gate as `invalid_response` mapping (TPH-01). Plan progress: 3/3 complete; DB-backed pytest passed.
- [x] **Phase 39: contract-spec §12.5/§12.6 Reconciliation** - Spec catches up to implemented contract fields via dual-AI review, without touching §8.0-locked identity fields (TPH-02). Plan progress: 1/1 complete.
- [x] **Phase 40: Tool Contract Validation Hardening** - Close source-confirmed validation/backstop gaps left after TPH-01 without changing `ToolResultV2`, `ToolCallContext` §8.0 identity fields, BusinessFactService ownership runtime semantics, or the `UnifiedToolManager` compatibility API (TPH-05).
- [ ] **Phase 41: Tool Platform Legacy Manager Cleanup** - Make the API/spec decision to remove the `UnifiedToolManager` legacy compatibility adapter and converge production/tests to `ToolPlatform` as the single graph-facing entrypoint (TPH-06). Plan progress: 3/4 complete.

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
| 41. Tool Platform Legacy Manager Cleanup | 3/4 | In Progress | |

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
- [ ] 41-04-PLAN.md — implementation code review, final verification, and Phase 41 completion record.
