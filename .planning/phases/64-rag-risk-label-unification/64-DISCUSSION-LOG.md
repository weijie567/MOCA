---
phase: 64
slug: rag-risk-label-unification
mode: auto
created: 2026-07-10
---

# Phase 64 Discussion Log

Autopilot ran Phase 64 discussion in auto mode because the user requested Phase 63 and Phase 64 to run sequentially without another manual pause.

## Gray Areas And Auto Decisions

### Canonical Owner

Auto decision: create a RAG-specific registry under `src/agent/rag_context/`, not a general action-safety taxonomy extension.

Reason: Phase 63 already owns action/risk vocabulary for write safety. RAG labels describe evidence and verifier routing semantics.

### Compatibility Or Rename

Auto decision: preserve existing label strings and add registry ownership/parity tests. Do not rename labels in Phase 64 unless planning finds an unavoidable collision.

Reason: current bug is label-set drift, especially `manual_review_sensitive` being filtered by builder, not bad label naming.

### Reason Code Scope

Auto decision: allow planner to centralize route-trigger reason-code groups only where needed to keep RAG label/routing semantics consistent. Do not rewrite deterministic negation/conflict domain rules.

Reason: hardcoded negation/conflict rules are security gates; Phase 64 should make their downstream semantics explicit, not replace the algorithms.

### Test Strategy

Auto decision: require RED tests first for `manual_review_sensitive` builder propagation and registry parity, then migrate callers.

Reason: the known production risk is current drift, and a RED builder test should fail before implementation.

## Deferred

- Trace/console/frontend display labels: Phase 65.
- Config/demo hygiene: Phase 66.
- State-machine registry/DB CHECK hardening: suggested Phase 67.
