# Roadmap: MOCA v2.1 Tool Platform Hardening

## Overview

v2.1 is a bounded, pre-scoped cleanup of the tool-call platform's contract debt and implementation gaps. The journey runs in three dependency-ordered, blast-radius-aware waves: first consolidate the tool declaration source and converge the runtime/policy internals with no external contract change (Phase 37), then layer real `output_schema` declaration and `ToolRuntime` output-validation enforcement on top of the consolidated registry and shared failure helper (Phase 38), and finally reconcile `docs/contract-spec.md` §12.5/§12.6 with the implemented contract fields so spec catches up to code, via the dual-AI review workflow (Phase 39). Throughout, `ToolCallContext` §8.0 identity fields stay locked and HIGH-blast-radius `ToolResultV2`/`ToolCallContext` envelope shapes are not changed — this milestone hardens data-shape enforcement and declaration hygiene only. Code implementation is delegated to Codex per the project workflow; Claude is plan designer and adjudicator, and these are planning/spec phases, not "Claude writes all the code" phases.

## Phases

**Phase Numbering:**
- Integer phases continue from the prior milestone (v2.0 ended at Phase 36); v2.1 starts at Phase 37.
- Decimal phases (37.1, 37.2): urgent insertions (marked INSERTED).

- [x] **Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation** - Single-source tool registry plus runtime `_fail` helper and declarative policy gate pipeline, with no external contract change (TPH-03, TPH-04).
- [ ] **Phase 38: output_schema Declaration + Runtime Output-Validation Enforcement** - Real `output_schema` for all eight tools, enforced in the `ToolRuntime` output-validation gate as `invalid_response` mapping (TPH-01).
- [ ] **Phase 39: contract-spec §12.5/§12.6 Reconciliation** - Spec catches up to implemented contract fields via dual-AI review, without touching §8.0-locked identity fields (TPH-02).

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
- [ ] 38-01-PLAN.md — validator nullable/type-union support plus TPH-01 scoped tool-set contract.
- [ ] 38-02-PLAN.md — catalog real output_schema declarations and current payload acceptance/rejection tests.
- [ ] 38-03-PLAN.md — runtime invalid_response enforcement tests plus high-blast consumer/contract sweep.
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
**Plans**: TBD
**UI hint**: no

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 37. Tool Declaration + Runtime/Policy Internal Consolidation | 3/3 | Complete; DB pytest pending | 2026-07-02 |
| 38. output_schema Declaration + Runtime Output-Validation Enforcement | 0/TBD | Not started | - |
| 39. contract-spec §12.5/§12.6 Reconciliation | 0/TBD | Not started | - |
