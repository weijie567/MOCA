# Phase 55: Memory Context Load Cutover - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `55-CONTEXT.md` - this log preserves the alternatives considered.

**Date:** 2026-07-07T05:00:00+08:00
**Phase:** 55-memory-context-load-cutover
**Mode:** Auto-selected recommended defaults via `$gsd-phase-autopilot 55`
**Areas discussed:** Active graph naming cutover, Memory authority and usage labels, Memory layer separation, Compatibility and validation scope

---

## Active graph naming cutover

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical active node with compatibility wrapper | Register `memory_context_load` as the active graph node and keep `long_term_memory_retrieve` only as non-active compatibility/import surface if required. | ✓ |
| Blind rename everywhere | Replace strings broadly across code/docs/tests. Risky because storage/API/historical trace compatibility names must remain. | |
| Leave active node unchanged | Keep `long_term_memory_retrieve` registered and rely on vocabulary projection. Fails CAGM-06. | |

**Auto choice:** Canonical active node with compatibility wrapper.
**Notes:** Current source shows `long_term_memory_retrieve` is already a wrapper over `reviewed_memory_context_retrieve`; Phase 55 should move active graph identity, not rewrite memory storage semantics.

---

## Memory authority and usage labels

| Option | Description | Selected |
|--------|-------------|----------|
| Contextual-only labels and guard tests | Preserve `authority_class = "contextual_only"` and add finite usage/source labels plus tests that memory cannot satisfy policy/business/approval/action/replay authority. | ✓ |
| Documentation-only note | State the boundary in docs without executable tests. Too weak for this migration. | |
| Treat reviewed memory as evidence-capable | Allow reviewed memory to satisfy evidence/business/action requirements. Violates Phase 50 and memory-layer contracts. | |

**Auto choice:** Contextual-only labels and guard tests.
**Notes:** Existing `context_refs.py` models already carry contextual-only authority; Phase 55 should make usage labels and graph-facing canonical metrics explicit.

---

## Memory layer separation

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve distinct layers and migrate active readers only | Keep session context, reviewed case precedent, CWC, and preference memory separate while changing active graph names. | ✓ |
| Collapse memory layers into one bundle | Simpler shape but blurs authority, source, and lifecycle semantics. | |
| Delete legacy storage/API names now | Exceeds Phase 55 and conflicts with Phase 48.1 compatibility constraints. | |

**Auto choice:** Preserve distinct layers and migrate active readers only.
**Notes:** Phase 46-48.1 already locked the memory boundaries. Phase 55 should not reopen table identity, API paths, or storage cleanup.

---

## Compatibility and validation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata-backed compatibility until Phase 58 | Close active runtime debt now; record retained wrapper/historical trace aliases with owner, reason, validation, and delete phase. | ✓ |
| No compatibility after Phase 55 | Cleaner, but likely breaks historical trace/import/test surfaces before Phase 58. | |
| Permanent compatibility aliases | Conflicts with Phase 50 final no-debt gate. | |

**Auto choice:** Metadata-backed compatibility until Phase 58.
**Notes:** Active `long_term_memory_retrieve` runtime debt belongs to Phase 55. Historical/import compatibility can remain temporarily only if recorded and test-covered.

---

## the agent's Discretion

- Exact implementation shape for `memory_context_load`.
- Exact finite usage label field names and enum values.
- Exact test split across unit, graph, architecture, trace/API, and memory-boundary suites.

## Deferred Ideas

- Phase 56 `recommendation_generation` and RAG/claim status alignment.
- Phase 57 `risk_gate` / `approval_gate` canonicalization.
- Phase 58 final no-debt cleanup.
