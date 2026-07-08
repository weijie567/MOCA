---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
reviewed: 2026-07-08T04:33:03Z
depth: deep
files_reviewed: 49
files_reviewed_list:
  - README.md
  - docs/architecture-overview.md
  - docs/current-langgraph-architecture.md
  - docs/target-agent-platform-architecture-plan.md
  - eval/replay/dev-contract-manifest.v1.json
  - frontend/src/components/timeline/TimelineStep.tsx
  - scripts/classify_phase58_legacy_hits.py
  - scripts/eval_agent.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/recommendation_generation.py
  - src/agent/nodes/risk_gate.py
  - src/agent/nodes/slot_resolution_gate.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - tests/agent/test_empty_session_adapter.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_adapter.py
  - tests/agent/test_intent_golden_contract.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_memory_context_load.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_nodes/test_recommendation_generation.py
  - tests/agent/test_nodes/test_risk_gate.py
  - tests/agent/test_nodes/test_session_context_load.py
  - tests/agent/test_nodes/test_slot_resolution_gate.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_trace.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/architecture/test_phase33_rag_claim_boundaries.py
  - tests/architecture/test_phase34_approval_action_boundaries.py
  - tests/conftest.py
  - tests/eval/test_phase35_replay_eval_gates.py
  - tests/knowledge/test_facade_integration.py
  - tests/knowledge/test_phase21_boundaries.py
  - tests/memory/test_phase48_1_memory_compat_alignment.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_graph_routing.py
  - tests/test_interception_rate.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-07-08T04:33:03Z
**Depth:** deep
**Files Reviewed:** 49
**Status:** issues_found

## Summary

Reviewed the Phase 58 graph cutover changes across runtime graph vocabulary, routing, canonical node implementations, API trace/approval projection boundaries, replay eval wiring, guard scripts, tests, and current docs. The active runtime code is consistently using canonical graph names, and the remaining old-name handling is bounded to historical projection/retry paths.

The issues below are no-debt guardrail and current-documentation drift problems. I treated `58-VALIDATION.md` as evidence that broad verification passed, and independently ran the strict legacy classifier plus a temporary fixture check for the classifier blind spot.

## Warnings

### WR-01: Strict legacy classifier misses an active legacy node alias

**File:** `scripts/classify_phase58_legacy_hits.py:13`

**Issue:** `LEGACY_TERMS` omits `intent_classification`, even though `src/agent/graph_vocabulary.py` treats it as a historical stored graph name projected to `contextual_intent_resolve`. A future active runtime regression such as `builder.add_node("intent_classification", ...)` would produce `total_hits=0` and pass strict mode because the classifier never searches for that alias. This weakens the Phase 58 no-debt gate.

**Fix:**

```python
LEGACY_TERMS = (
    "classify_intent",
    "intent_classification",
    "session_memory_load",
    "extract_slots",
    "long_term_memory_retrieve",
    "generate_recommendation",
    "assess_risk_and_approval",
    "route_after_intent",
    "route_after_slots",
)
```

Also add a regression test that writes an active runtime fixture containing `builder.add_node("intent_classification", ...)` and asserts strict classification reports `active_runtime_legacy > 0`. Longer term, derive this term set from the canonical graph vocabulary/historical projection definitions so the scanner cannot drift from the contract vocabulary.

### WR-02: Current LangGraph architecture doc still names removed public compatibility router

**File:** `docs/current-langgraph-architecture.md:101`

**Issue:** The current architecture doc says `route_after_slots()` is "only a compatibility delegate." Phase 58 removed the public `def route_after_slots(` surface; the only remaining symbol is the private internal `_route_after_slots()`, and `tests/architecture/test_canonical_graph_baseline.py` explicitly asserts the public function is absent. Because this section is under "关键依据" and says it describes current source facts, the line is current-doc contract drift rather than harmless historical text.

**Fix:** Replace the sentence with the current public router list only. If the internal helper must be mentioned, call it `_route_after_slots()` and state that it is private implementation detail, not a public compatibility delegate or accepted current route authority.

### WR-03: README current runtime snapshot is inconsistent with the compiled graph and memory state

**File:** `README.md:52`

**Issue:** The README says the Mermaid graph is the current runtime snapshot, but it shows `contextual_intent_resolve` routing directly to `memory_context_load` and `slot_resolution_gate` routing `slots ok` to `memory_context_load`. The compiled graph routes `contextual_intent_resolve` only to `clarification_gate`, `final_response`, `investigate`, or `slot_resolution_gate`; `memory_context_load` is only reachable from `slot_resolution_gate` when slot resolution decides reviewed memory is required. The same README section later says session memory adapters are empty (`README.md:174`), which is stale now that session memory loads from PostgreSQL via `MemoryService`.

**Fix:** Update the Mermaid diagram to match `src/agent/graph.py`: route `contextual_intent_resolve` fact/policy paths to `investigate`, route `slot_resolution_gate` `slots ok` to `investigate`, and reserve `slot_resolution_gate -> memory_context_load -> investigate` for reviewed-memory-needed cases. Update the scope bullet to say same-thread session memory is PostgreSQL-backed/current, while cross-session long-term and case memory remain limited or out of scope.

---

_Reviewed: 2026-07-08T04:33:03Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
