# Phase 54: Slot Resolution Gate Cutover - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-06T23:29:53Z
**Phase:** 54-slot-resolution-gate-cutover
**Mode:** autopilot auto discussion
**Areas discussed:** graph boundary, slot extraction vs slot resolution, provenance contract, fail-closed routing, compatibility ledger, planning granularity

---

## Graph Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical active node | Register `slot_resolution_gate` as the active graph node and move active path maps to it. | ✓ |
| Cosmetic alias only | Leave `extract_slots` active and only project traces to `slot_resolution_gate`. | |
| Broader graph cutover | Also introduce `memory_context_load` in the same phase. | |

**Auto choice:** Canonical active node.
**Notes:** Phase 54 owns `extract_slots -> slot_resolution_gate`; Phase 55 owns `memory_context_load`, so broader graph cutover is out of scope.

---

## Slot Extraction Versus Slot Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Internal extraction, deterministic gate | Keep candidate extraction internal and make deterministic slot satisfaction/provenance the registered node boundary. | ✓ |
| LLM authority at gate | Let LLM output satisfy slots directly. | |
| Separate `slot_extraction` graph node | Add a graph node for extraction before gate. | |

**Auto choice:** Internal extraction, deterministic gate.
**Notes:** Phase 50 and contract §9 forbid final `slot_extraction` as a registered graph node. LLM output can propose candidates only.

---

## Provenance Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit provenance payload | Add trace-visible resolved/missing/stale/incompatible/invalidated provenance while preserving existing state fields. | ✓ |
| Minimal rename | Rename the node without changing provenance visibility. | |
| Downstream-only provenance | Defer provenance until later memory/replay phases. | |

**Auto choice:** Explicit provenance payload.
**Notes:** CAGM-05 success criteria require explicit slot provenance, not just a graph rename.

---

## Fail-Closed Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative slot router | Unknown/mismatch/missing/stale/incompatible/invalid states route to `clarification_gate`; satisfied slots route to `investigate`; memory-needed paths keep `long_term_memory_retrieve` until Phase 55. | ✓ |
| Aggressive progression | Route more cases to `investigate` and let investigation recover. | |
| Phase 55 early route | Route memory-needed paths to new `memory_context_load` now. | |

**Auto choice:** Conservative slot router.
**Notes:** This preserves fail-closed behavior and Phase 55 boundary.

---

## Compatibility Ledger

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit retained compatibility | Retain `extract_slots` / `route_after_slots` only as compatibility surfaces with owner, reason, trace projection, validation, and delete phase. | ✓ |
| Delete every import immediately | Remove all compatibility surfaces in Phase 54. | |
| Leave implicit compatibility | Keep legacy names without ledger updates. | |

**Auto choice:** Explicit retained compatibility.
**Notes:** Phase 50 temporary compatibility policy requires explicit metadata for retained aliases.

---

## Planning Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Three small plans | Split into node contract, graph/router cutover, and vocabulary/docs/validation closeout. | ✓ |
| One large plan | Handle contract, implementation, graph wiring, docs, and validation in one plan. | |
| Many micro-plans | Split every file family into separate plans. | |

**Auto choice:** Three small plans.
**Notes:** Project planning rules require splitting service-boundary/graph migration work into executable units.

---

## the agent's Discretion

- Exact provenance schema name.
- Whether deterministic helper extraction from `src/agent/routing.py` is necessary.
- Exact test file distribution across the three plans, as long as Phase 54 success criteria are covered.

## Deferred Ideas

- Phase 55: `memory_context_load`.
- Phase 56: `recommendation_generation`.
- Phase 57: `risk_gate` / approval canonicalization.
- Phase 58: final no-debt cleanup.
