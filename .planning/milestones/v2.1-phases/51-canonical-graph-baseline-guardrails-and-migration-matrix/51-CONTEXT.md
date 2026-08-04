# Phase 51: Canonical Graph Baseline Guardrails and Migration Matrix - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning
**Source:** Lightweight context pass requested by user; no extended discuss.

<domain>
## Phase Boundary

Phase 51 is the first implementation-prep phase after the Phase 50 canonical Agent Graph migration charter. It must create source-verified guardrails and a migration matrix before any runtime graph rewiring starts.

This phase should make later Phase 52-58 plans safer by turning the accepted target graph into testable/static checks:

- current active graph node set can be discovered from source;
- target 15-node canonical set is represented in a stable test/helper constant or fixture;
- current legacy graph nodes are allowed only in migration mode and only when each legacy node has an explicit canonical target mapping;
- `slot_extraction` must not become a registered main-chain graph node;
- final no-debt checks are defined but not enforced as failing runtime gates until Phase 58 cutover.

</domain>

<decisions>
## Implementation Decisions

### Scope

- Phase 51 is guardrail/test/docs only.
- Phase 51 must not rewire `src/agent/graph.py` runtime edges or change graph behavior.
- Phase 51 may add static/architecture tests, test helpers, constants/fixtures, documentation, planning ledgers, and source-verified migration matrix artifacts.
- Phase 51 must not create `safety_pre_route`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, or `risk_gate` runtime nodes. Those belong to later phases.

### Target graph constant / fixture

- The target canonical graph node set should be represented as an explicit stable test constant/fixture so later phases can import or compare against it.
- The target set is exactly:
  - `receive_request`
  - `safety_pre_route`
  - `session_context_load`
  - `contextual_intent_resolve`
  - `slot_resolution_gate`
  - `memory_context_load`
  - `investigate`
  - `rag_context_build`
  - `recommendation_generation`
  - `claim_verify`
  - `risk_gate`
  - `approval_gate`
  - `action_draft`
  - `clarification_gate`
  - `final_response`

### Migration-mode guard

- Phase 51 should allow the current legacy/canonical mixed source graph to pass in migration mode.
- Migration-mode pass condition: every active legacy graph node must have an explicit canonical target mapping and must be covered by Phase 50 / roadmap migration ownership.
- Current active legacy graph nodes expected from source:
  - `classify_intent -> contextual_intent_resolve`
  - `session_memory_load -> session_context_load`
  - `extract_slots -> slot_resolution_gate`
  - `long_term_memory_retrieve -> memory_context_load`
  - `generate_recommendation -> recommendation_generation`
  - `assess_risk_and_approval -> risk_gate`
- The final no-debt guard should exist as a future/final gate, skipped or migration-mode-marked until Phase 58. It must not fail the current build before implementation phases migrate the graph.

### Forbidden graph-node drift

- `slot_extraction` is not a final registered graph node.
- `normalize_input`, `memory_write`, `trace_close`, and `action_execution` are also not current main-chain registered graph nodes.
- If a future phase wants to promote any of these to a graph node, it must first update `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and Phase 50 SPEC with an explicit reviewed decision.

### Testing approach

- Prefer static tests under existing architecture-test conventions where possible.
- Tests must use source inspection or graph construction in a way that does not require live LLM/provider calls, external services, or DB setup.
- Verification commands in plans must use MOCA-approved entrypoints such as `uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### Documentation / ledger

- Phase 51 should update `.planning/ARCHITECTURE-DEBT.md` if it adds, narrows, or closes architecture debt records.
- Phase 51 should not claim runtime migration complete. It should explicitly say runtime graph remains legacy/canonical mixed until later phases.

</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

### Migration charter

- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — primary execution charter for Phase 51-58 canonical graph migration.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SUMMARY.md` — spec-only closeout and downstream pointer.

### Target architecture and contract

- `docs/contract-spec.md` — primary accepted contract reference, especially §9 graph/node/router contract.
- `docs/target-agent-platform-architecture-plan.md` — readable target graph, especially §6.1 Canonical Runtime Graph.
- `docs/current-langgraph-architecture.md` — current source graph snapshot; descriptive only, not target authority.

### Current source facts

- `src/agent/graph.py` — active LangGraph node registration and edge wiring.
- `src/agent/routing.py` — active deterministic routers and route values.
- `src/agent/graph_vocabulary.py` — current legacy-to-target vocabulary and compatibility aliases.
- `src/agent/state.py` — AgentState fields that target graph nodes read/write.

### Planning and project rules

- `.planning/ROADMAP.md` — Phase 51 goal, requirements, dependencies, and success criteria.
- `.planning/REQUIREMENTS.md` — `CAGM-02` requirement mapping.
- `.planning/STATE.md` — current phase state and next-step pointer.
- `.planning/ARCHITECTURE-DEBT.md` — cross-subsystem graph migration debt ledger.
- `AGENTS.md` — MOCA project rules, including approved test commands and architecture-debt ledger rules.

</canonical_refs>

<specifics>
## Specific Ideas

- Add a focused architecture test file if existing patterns support it, likely under `tests/architecture/`.
- The test/helper should distinguish:
  - current active node set;
  - target canonical node set;
  - active legacy nodes allowed during migration;
  - final legacy nodes forbidden after Phase 58.
- The guard should catch accidental registered graph nodes named `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, or `action_execution`.
- If importing `src/agent/graph.py` has side effects or provider dependencies, prefer AST/source inspection of `builder.add_node(...)` / route maps first.
- Keep Phase 51 plans small enough to satisfy the project PLAN granularity rule. If one plan would cover constants, source inspection, tests, docs, and validation in one broad file span, split into multiple plans.

</specifics>

<deferred>
## Deferred Ideas

- Runtime rewiring starts in Phase 52, not Phase 51.
- Final no-debt enforcement belongs to Phase 58.
- ReAct investigate hardening beyond baseline preservation belongs to a later phase only if Phase 50/51 validation identifies a concrete gap.
- External action execution after `action_draft` remains future scope and is not part of this migration.

</deferred>

---

*Phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix*
*Context gathered: 2026-07-06 via lightweight context pass*
