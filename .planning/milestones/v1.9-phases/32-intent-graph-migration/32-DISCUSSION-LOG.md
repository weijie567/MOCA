# Phase 32: Intent Graph Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `32-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-28T12:02:12Z
**Phase:** 32-Intent Graph Migration
**Areas discussed:** Graph vocabulary and compatibility, Intent policy ownership, Slot policy resolution, Trace/eval and merchant context evidence
**Mode:** Auto mode; Codex selected conservative recommended options after reading roadmap, requirements, prior phase context, target specs, and current graph code.

---

## Graph Vocabulary And Compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical projection plus legacy aliases | Add target canonical mapping/projections and wrappers first, while preserving legacy runtime behavior where tests depend on it. | yes |
| Immediate full graph rename | Rename registered nodes and routers broadly in one implementation pass. | |
| Trace-only mapping | Leave runtime and tests unchanged and only document aliases in trace text. | |

**User's choice:** Auto-selected conservative default: canonical projection plus legacy aliases.
**Notes:** Current graph still registers legacy names. Phase 31 already introduced wrappers for `session_context_load` and reviewed memory context, so extending the wrapper/projection pattern fits the codebase.

---

## Intent Policy Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Registry-owned effective decisions | `IntentPolicyRegistry` owns effective route/intent decisions; LLM output remains candidate-only. | yes |
| LLM-owned route decision | Treat structured model output as the final route and slot authority. | |
| Keep current constants scattered | Preserve direct constant reads without a stronger policy boundary. | |

**User's choice:** Auto-selected conservative default: registry-owned effective decisions.
**Notes:** Existing `classification_trace` already distinguishes raw LLM output from policy overrides and effective classification. Phase 32 should make this boundary more explicit.

---

## Slot Policy Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic slot policy gate | `SlotPolicyRegistry` owns required-slot and inherited-slot policy; stale/scope-unsafe/incompatible slots clarify. | yes |
| Trust any same-thread slot | Accept inherited session slots broadly when same thread has a value. | |
| Disable inheritance entirely | Require users to repeat identifiers every turn. | |

**User's choice:** Auto-selected conservative default: deterministic slot policy gate.
**Notes:** Existing tests already cover stale/wrong-thread session slots and policy QA ignoring stale business identifiers; Phase 32 should add target `slot_resolution_gate` projection and registry ownership.

---

## Trace, Eval, And Merchant Context Evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Dual legacy/target projection with merchant-context evidence | Preserve implementation node names while adding target canonical names and deterministic merchant-context resolution/defer evidence. | yes |
| Legacy-only traces | Keep existing `trace_steps[].node` values with no target projection. | |
| Target-only breaking projection | Replace trace/API node names immediately with target names. | |

**User's choice:** Auto-selected conservative default: dual projection with safe merchant-context evidence.
**Notes:** AgentRun and trace APIs already persist legacy node names. Phase 32 should not break these surfaces, but APF-11/APF-12 need target names that evals can assert. Manager/supervisor-style business run visibility must not silently widen.

---

## Agent Discretion

- Exact alias-map module and schema names are left to planning.
- Exact plan split is left to planning, but context records that one giant plan would be a planning blocker for this phase.
- Exact merchant-context evidence shape is left to planning as long as it is deterministic, safe, and test-pinned.

## Deferred Ideas

- Full `rag_context_build` and `claim_verify` implementation: Phase 33.
- Approval/action binding: Phase 34.
- Full replay/eval hardening and broader run visibility proof: Phase 35.
