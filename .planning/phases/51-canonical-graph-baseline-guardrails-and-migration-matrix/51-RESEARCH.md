# Phase 51: Canonical Graph Baseline Guardrails and Migration Matrix - Research

**Researched:** 2026-07-06 [VERIFIED: system date and phase context]
**Domain:** MOCA LangGraph architecture guardrails, static source inspection, migration matrix tests [VERIFIED: .planning/ROADMAP.md:356-367]
**Confidence:** HIGH for current source facts and test architecture; MEDIUM for whether planner should keep all migration constants test-local because that is a boundary recommendation, not a user-locked implementation detail. [VERIFIED: src/agent/graph.py:280-377; VERIFIED: tests/architecture/test_phase32_static_contract.py:17-172; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-80]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied verbatim from `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md` `## Implementation Decisions`. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:22-82]

#### Scope

- Phase 51 is guardrail/test/docs only.
- Phase 51 must not rewire `src/agent/graph.py` runtime edges or change graph behavior.
- Phase 51 may add static/architecture tests, test helpers, constants/fixtures, documentation, planning ledgers, and source-verified migration matrix artifacts.
- Phase 51 must not create `safety_pre_route`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, or `risk_gate` runtime nodes. Those belong to later phases.

#### Target graph constant / fixture

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

#### Migration-mode guard

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

#### Forbidden graph-node drift

- `slot_extraction` is not a final registered graph node.
- `normalize_input`, `memory_write`, `trace_close`, and `action_execution` are also not current main-chain registered graph nodes.
- If a future phase wants to promote any of these to a graph node, it must first update `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and Phase 50 SPEC with an explicit reviewed decision.

#### Testing approach

- Prefer static tests under existing architecture-test conventions where possible.
- Tests must use source inspection or graph construction in a way that does not require live LLM/provider calls, external services, or DB setup.
- Verification commands in plans must use MOCA-approved entrypoints such as `uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

#### Documentation / ledger

- Phase 51 should update `.planning/ARCHITECTURE-DEBT.md` if it adds, narrows, or closes architecture debt records.
- Phase 51 should not claim runtime migration complete. It should explicitly say runtime graph remains legacy/canonical mixed until later phases.

### Claude's Discretion

No `## Claude's Discretion` section exists in the Phase 51 context file. [VERIFIED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:1-145]

### Deferred Ideas (OUT OF SCOPE)

Copied verbatim from `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md` `## Deferred Ideas`. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:132-140]

- Runtime rewiring starts in Phase 52, not Phase 51.
- Final no-debt enforcement belongs to Phase 58.
- ReAct investigate hardening beyond baseline preservation belongs to a later phase only if Phase 50/51 validation identifies a concrete gap.
- External action execution after `action_draft` remains future scope and is not part of this migration.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-02 | Baseline graph guardrails and migration matrix checks exist before runtime rewiring starts, proving the current active graph node set, router route values, legacy-to-target mapping, and no-`slot_extraction` graph-node rule are source-verified and testable. [CITED: .planning/REQUIREMENTS.md:54] | Add AST/source-based architecture tests under `tests/architecture/`, with explicit constants for current active nodes, the final 15-node target set, migration-mode legacy mappings, router mappings, and forbidden registered-node names. [VERIFIED: src/agent/graph.py:280-377; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:120-128] |
</phase_requirements>

## Summary

Phase 51 should add static architecture guardrails around the graph as it exists today, not change the graph. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] The current `build_graph()` registers 14 active nodes, including six legacy nodes that must be allowed during migration mode but mapped to final canonical owners. [VERIFIED: src/agent/graph.py:280-293; VERIFIED: uv run python AST extraction of src/agent/graph.py] The final target remains exactly the 15 registered-node set in Phase 50 and contract §9. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:17-35; CITED: docs/contract-spec.md:434-436]

The planner should split this into a focused test-helper/matrix plan, a focused architecture-test plan, and a docs/ledger validation plan. [VERIFIED: AGENTS.md:55-60; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:128] The guardrail tests should parse `src/agent/graph.py` with `ast` to enumerate `builder.add_node(...)` and `builder.add_conditional_edges(...)`, because this avoids compiling the graph or requiring a checkpointer/provider. [VERIFIED: src/agent/graph.py:276-377; VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54]

Primary recommendation: create a test-local canonical graph baseline helper under `tests/architecture/` and assert the current mixed graph, target graph, migration-mode matrix, router route map, and forbidden registered-node drift from source inspection. [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-56; VERIFIED: src/agent/graph.py:280-377; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:120-128]

## Project Constraints (from CLAUDE.md and AGENTS.md)

- `CLAUDE.md` exists and requires architecture-debt entries to be based on real code, tests, or planning artifacts, with target docs separated from implemented facts. [VERIFIED: CLAUDE.md:9-15]
- `CLAUDE.md` requires phase implementation/spec divergence to be recorded instead of silently diverging from `docs/contract-spec.md`. [VERIFIED: CLAUDE.md:73-80]
- `AGENTS.md` forbids bare `pytest` and bare `python -m pytest`; valid commands are `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or the current repo `.venv/bin/pytest ...`. [VERIFIED: AGENTS.md:24-29]
- `AGENTS.md` requires phase-level plans with multiple ownership domains, waves, or verification gates to be split into multiple numbered plans. [VERIFIED: AGENTS.md:55-60]
- `AGENTS.md` requires graph/RAG/memory/intent architecture debt discoveries or fixes to be appended to `.planning/ARCHITECTURE-DEBT.md` with Chinese records by default. [VERIFIED: AGENTS.md:16-22]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Current active graph node discovery | Test / Architecture guardrail | API / Backend source inspection | Phase 51 needs to identify registered nodes from `src/agent/graph.py` without changing backend runtime behavior. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |
| Target canonical node-set fixture | Test / Architecture guardrail | Planning docs | The target set is a Phase 50/contract decision and should be represented as a stable test constant for later phases. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:32-50; CITED: docs/contract-spec.md:434-436] |
| Migration-mode legacy mapping | Test / Architecture guardrail | Planning docs and graph vocabulary | Current legacy nodes must pass only when mapped to canonical owners and deletion phases. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192] |
| Router route-value baseline | Test / Architecture guardrail | API / Backend source inspection | `add_conditional_edges(...)` route maps and routing constants are current source facts; Phase 51 should assert them rather than alter them. [VERIFIED: src/agent/graph.py:297-372; VERIFIED: src/agent/routing.py:21-38] |
| Forbidden registered-node drift | Test / Architecture guardrail | Contract docs | `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, and `action_execution` are excluded from current main-chain registered nodes. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:65-69; CITED: docs/contract-spec.md:436] |
| Final no-debt gate | Test / Architecture guardrail | Phase 58 | Phase 51 should define or mark the final gate but must not fail the current mixed graph before Phase 58. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:63; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250] |

## Current Source Facts

### Active registered graph nodes

`src/agent/graph.py` currently registers this active main graph node set in `build_graph()`: [VERIFIED: src/agent/graph.py:280-293; VERIFIED: uv run python AST extraction of src/agent/graph.py]

```python
CURRENT_ACTIVE_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "classify_intent",
        "session_memory_load",
        "extract_slots",
        "long_term_memory_retrieve",
        "investigate",
        "rag_context_build",
        "generate_recommendation",
        "claim_verify",
        "assess_risk_and_approval",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
    }
)
```

Current active legacy registered nodes are `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, and `assess_risk_and_approval`. [VERIFIED: src/agent/graph.py:281-289; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:160]

Current active canonical registered nodes are `receive_request`, `investigate`, `rag_context_build`, `claim_verify`, `clarification_gate`, `approval_gate`, `action_draft`, and `final_response`. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:144-158]

`safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, and `risk_gate` are target names but are not currently registered active graph nodes in `src/agent/graph.py`. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:144-158]

### Active edge and router baseline

`src/agent/graph.py` currently wires direct edges `START -> receive_request`, `receive_request -> classify_intent`, `session_memory_load -> extract_slots`, `long_term_memory_retrieve -> investigate`, `clarification_gate -> final_response`, `action_draft -> final_response`, and `final_response -> END`. [VERIFIED: src/agent/graph.py:295-317; VERIFIED: src/agent/graph.py:337-375]

`src/agent/graph.py` currently uses these conditional router mappings: [VERIFIED: src/agent/graph.py:297-372; VERIFIED: uv run python AST extraction of src/agent/graph.py]

| Source node | Router | Route keys and destinations |
|-------------|--------|-----------------------------|
| `classify_intent` | `route_after_intent` | `clarification_gate -> clarification_gate`, `final_response -> final_response`, `investigate -> investigate`, `session_memory_load -> session_memory_load` [VERIFIED: src/agent/graph.py:297-305] |
| `extract_slots` | `route_after_slots` | `clarification_gate -> clarification_gate`, `investigate -> investigate`, `long_term_memory_retrieve -> long_term_memory_retrieve` [VERIFIED: src/agent/graph.py:308-315] |
| `investigate` | `route_after_investigate` | `final_response -> final_response`, `clarification_gate -> clarification_gate`, `rag_context_build -> rag_context_build`, `recommendation_generation -> generate_recommendation` [VERIFIED: src/agent/graph.py:318-326] |
| `rag_context_build` | `route_after_rag_context` | `recommendation_generation -> generate_recommendation`, `clarification_gate -> clarification_gate`, `final_response -> final_response` [VERIFIED: src/agent/graph.py:328-335] |
| `generate_recommendation` | `route_after_recommendation` | `claim_verify -> claim_verify`, `final_response -> final_response` [VERIFIED: src/agent/graph.py:338-344] |
| `claim_verify` | `route_after_claim_verify` | `assess_risk_and_approval -> assess_risk_and_approval`, `final_response -> final_response` [VERIFIED: src/agent/graph.py:346-352] |
| `assess_risk_and_approval` | `route_after_risk` | `assess_risk_and_approval -> assess_risk_and_approval`, `approval_gate -> approval_gate`, `action_draft -> action_draft`, `final_response -> final_response` [VERIFIED: src/agent/graph.py:354-362] |
| `approval_gate` | `route_after_approval` | `approval_gate -> approval_gate`, `assess_risk_and_approval -> assess_risk_and_approval`, `action_draft -> action_draft`, `final_response -> final_response` [VERIFIED: src/agent/graph.py:364-372] |

`src/agent/routing.py` exposes route-allowlist constants for investigate, recommendation, RAG context, claim verify, intent, and slot routes. [VERIFIED: src/agent/routing.py:21-38] `route_after_rag_context()` returns canonical route labels like `recommendation_generation`, while `src/agent/graph.py` maps that label to the legacy active node `generate_recommendation`. [VERIFIED: src/agent/routing.py:339-352; VERIFIED: src/agent/graph.py:328-335]

### Target canonical graph facts

The final target canonical graph contains exactly 15 registered nodes: `receive_request`, `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `investigate`, `rag_context_build`, `recommendation_generation`, `claim_verify`, `risk_gate`, `approval_gate`, `action_draft`, `clarification_gate`, and `final_response`. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:17-35; CITED: docs/contract-spec.md:434-460; CITED: docs/target-agent-platform-architecture-plan.md:228-232]

`START`, `END`, `route_after_*` routers, `investigate` internal loop steps, service calls, and lifecycle concerns do not count as registered runtime graph nodes. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:46-54; CITED: docs/contract-spec.md:434-442; CITED: docs/target-agent-platform-architecture-plan.md:232-241]

`slot_extraction` is intentionally not a final registered graph node; slot candidate extraction is internal to `contextual_intent_resolve` / `slot_resolution_gate`. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:35; CITED: docs/target-agent-platform-architecture-plan.md:230]

### Current graph vocabulary facts

`src/agent/graph_vocabulary.py` defines immutable `GraphVocabularyEntry` records with `legacy_name`, `target_name`, `kind`, `status`, `runnable`, and optional `reason_codes`. [VERIFIED: src/agent/graph_vocabulary.py:13-39]

`graph_vocabulary.py` maps `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, and `assess_risk_and_approval` as compatibility aliases to target canonical graph concepts. [VERIFIED: src/agent/graph_vocabulary.py:49-66; VERIFIED: src/agent/graph_vocabulary.py:90-97]

`graph_vocabulary.py` does not currently include a `generate_recommendation -> recommendation_generation` entry even though `generate_recommendation` is an active registered graph node and Phase 50 maps it to `recommendation_generation`. [VERIFIED: src/agent/graph.py:287; VERIFIED: src/agent/graph_vocabulary.py:41-103; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:152]

`graph_vocabulary.py` currently marks `memory_write` as a runnable runtime vocabulary entry, but Phase 50/51 exclude `memory_write` from the current main-chain registered node set. [VERIFIED: src/agent/graph_vocabulary.py:48; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:65-69; CITED: docs/contract-spec.md:436]

## Existing Test Patterns

`tests/architecture/test_phase32_static_contract.py` already asserts required legacy-to-target vocabulary entries against `src.agent.graph_vocabulary`, including `classify_intent`, `session_memory_load`, `long_term_memory_retrieve`, `extract_slots`, `route_after_intent`, and `route_after_slots`. [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-56]

`tests/architecture/test_phase32_static_contract.py` already includes a helper that extracts validation commands from phase artifacts and rejects bare `pytest` / bare `python -m pytest` commands. [VERIFIED: tests/architecture/test_phase32_static_contract.py:84-150]

`tests/architecture/test_action_draft_boundaries.py` already uses AST parsing helpers for function-name and import-target checks, and it has direct source assertions against `src/agent/graph.py` for registered graph-node drift around `action_draft` / `execute_action`. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-54; VERIFIED: tests/architecture/test_action_draft_boundaries.py:112-121]

`tests/architecture/test_phase34_approval_action_boundaries.py` already verifies the `assess_risk_and_approval -> risk_gate` compatibility alias and `route_after_risk` router vocabulary entry. [VERIFIED: tests/architecture/test_phase34_approval_action_boundaries.py:37-55]

`tests/architecture/test_memory_contract_delta.py` already treats graph aliases as compatibility aliases and separates current implementation facts from target vocabulary. [VERIFIED: tests/architecture/test_memory_contract_delta.py:147-160]

Recommended Phase 51 test style: use `pathlib.Path`, `ast.parse`, plain constants, and small source-inspection helpers under `tests/architecture/`; avoid live graph compilation and avoid external services. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-54; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:71-75]

## Recommended Plan Split

### 51-01: Static Graph Baseline Helper and Migration Matrix

Goal: add a reusable architecture-test helper or constants module under `tests/architecture/`, for example `tests/architecture/graph_baseline.py`, that owns source-inspection helpers and explicit constants. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-54; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:120-128]

Recommended constants: [VERIFIED: src/agent/graph.py:280-377; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162]

```python
TARGET_CANONICAL_GRAPH_NODES = frozenset({...15 canonical names...})
CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset({...14 current names...})
MIGRATION_MODE_LEGACY_NODE_MAP = {
    "classify_intent": {"target": "contextual_intent_resolve", "delete_phase": "Phase 53"},
    "session_memory_load": {"target": "session_context_load", "delete_phase": "Phase 53"},
    "extract_slots": {"target": "slot_resolution_gate", "delete_phase": "Phase 54"},
    "long_term_memory_retrieve": {"target": "memory_context_load", "delete_phase": "Phase 55"},
    "generate_recommendation": {"target": "recommendation_generation", "delete_phase": "Phase 56"},
    "assess_risk_and_approval": {"target": "risk_gate", "delete_phase": "Phase 57"},
}
FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES = frozenset(
    {"slot_extraction", "normalize_input", "memory_write", "trace_close", "action_execution"}
)
```

Recommendation: keep the Phase 51 matrix test-local unless the planner explicitly scopes a non-behavioral `graph_vocabulary.py` compatibility entry update. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30; VERIFIED: src/agent/graph_vocabulary.py:41-103] This avoids changing trace projection behavior while still making the missing `generate_recommendation` mapping visible to later plans. [VERIFIED: src/agent/graph_vocabulary.py:129-139; VERIFIED: src/agent/graph.py:287]

### 51-02: Architecture Tests for Current, Target, Migration Mode, and Forbidden Drift

Goal: add `tests/architecture/test_canonical_graph_baseline.py` with source-verified tests for CAGM-02. [CITED: .planning/REQUIREMENTS.md:54; VERIFIED: tests/architecture/test_phase32_static_contract.py:35-56]

Recommended tests: [VERIFIED: src/agent/graph.py:280-377; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:210-227]

- `test_current_active_graph_node_set_matches_phase51_baseline`: parse `builder.add_node(...)` string constants and assert the 14-node current baseline exactly. [VERIFIED: src/agent/graph.py:280-293]
- `test_target_canonical_graph_node_set_is_exact_phase50_contract`: assert the 15-node target fixture exactly matches Phase 50 / contract order or set. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:17-35; CITED: docs/contract-spec.md:434-460]
- `test_migration_mode_maps_every_active_legacy_node_to_target`: assert `CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES` equals the migration-map keys, and every map target is in the target set. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162]
- `test_current_router_mappings_match_source_baseline`: parse `builder.add_conditional_edges(...)` and assert router names plus route key/destination maps exactly. [VERIFIED: src/agent/graph.py:297-372]
- `test_forbidden_internal_or_lifecycle_names_are_not_registered_graph_nodes`: assert `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, and `action_execution` are absent from parsed `add_node(...)` names. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:65-69; VERIFIED: src/agent/graph.py:280-293]
- `test_slot_extraction_drift_is_explicitly_rejected`: assert `slot_extraction` is absent and include a failure message telling future phases to update `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and Phase 50 SPEC before promotion. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:67-69]
- `test_final_no_debt_gate_is_marked_future_until_phase58`: include a skipped or xfailed check that documents the final 15-node equality gate without failing the current mixed graph. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:63; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250]

### 51-03: Documentation and Ledger Closeout

Goal: update planning docs only if needed, especially `.planning/ARCHITECTURE-DEBT.md`, and explicitly state that runtime graph migration remains incomplete. [VERIFIED: AGENTS.md:16-22; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:77-80]

Recommended closeout content: record that Phase 51 added baseline guardrails and a migration-mode matrix, record that the active graph remains legacy/canonical mixed, and record that final no-debt enforcement remains Phase 58 scope. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:52-80; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:164-177]

Do not update `docs/contract-spec.md` or `docs/target-agent-platform-architecture-plan.md` in Phase 51 unless tests reveal a real target-contract mismatch; this phase is not changing graph semantics. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30; VERIFIED: AGENTS.md:94-102]

## Standard Stack

No new runtime library is needed for Phase 51. [VERIFIED: pyproject.toml:1-55; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:71-75]

| Tool / Library | Version / Constraint | Purpose | Why Standard |
|----------------|----------------------|---------|--------------|
| Python | `>=3.12` in project metadata; `uv run python --version` returned Python 3.12.13. [VERIFIED: pyproject.toml:5; VERIFIED: uv run python --version] | Static source inspection helper execution. | Existing project runtime and test environment. [VERIFIED: pyproject.toml:5] |
| pytest | `>=8.0` in dev dependency; `uv run pytest --version` returned pytest 9.0.3. [VERIFIED: pyproject.toml:34-39; VERIFIED: uv run pytest --version] | Architecture tests. | Existing test framework. [VERIFIED: pyproject.toml:54-55; VERIFIED: tests/architecture/test_phase32_static_contract.py:7] |
| Python `ast` | Standard library. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:3] | Parse `src/agent/graph.py` without compiling the graph. | Existing architecture tests already use AST for source guardrails. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54] |
| `pathlib.Path` | Standard library. [VERIFIED: tests/architecture/test_phase32_static_contract.py:5] | Locate repo files from architecture tests. | Existing architecture tests use repo-root path constants. [VERIFIED: tests/architecture/test_phase32_static_contract.py:13-15] |

Installation: no new packages recommended. [VERIFIED: pyproject.toml:34-39]

## Architecture Patterns

### Pattern: AST-backed graph introspection

What: parse `src/agent/graph.py`, find calls where `node.func.attr` is `add_node`, `add_edge`, or `add_conditional_edges`, and extract only literal string node names and route maps. [VERIFIED: src/agent/graph.py:280-377; VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54]

When to use: use this for Phase 51 graph guardrails because importing and compiling the graph requires a checkpointer argument and is unnecessary for static contract checks. [VERIFIED: src/agent/graph.py:276-377; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:127]

Example:

```python
def graph_add_node_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_node"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value)
    return names
```

Source: adapted from existing architecture-test AST patterns. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54]

### Pattern: Migration-mode now, no-debt gate later

What: keep current mixed graph passing in migration mode while documenting the final no-debt equality check as skipped or xfailed until Phase 58. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:52-63; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250]

When to use: use it for Phase 51 because the current source graph intentionally still has six legacy registered nodes. [VERIFIED: src/agent/graph.py:281-289; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:160]

## Don't Hand-Roll

| Problem | Do not build | Use instead | Why |
|---------|--------------|-------------|-----|
| Source graph discovery | Regex-only parser for `builder.add_node(...)` / `add_conditional_edges(...)` | Python `ast` helper in tests | AST avoids false positives from comments and strings while matching existing test style. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54] |
| Live graph enumeration | Runtime graph compilation with checkpointer/provider setup | Static source inspection | Phase 51 must avoid live LLM/provider calls, external services, and DB setup. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:71-75] |
| Target graph source of truth | Re-derive target nodes from diagrams by parsing Mermaid | Explicit test constant copied from Phase 50/contract | Phase 50 and contract §9 are the authoritative target references. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:123-130; CITED: docs/contract-spec.md:430-436] |
| Final no-debt enforcement | A currently failing exact-15-node assertion | `pytest.mark.skip` or `pytest.mark.xfail(strict=True)` future gate | Phase 51 must allow current mixed graph until later phases migrate it. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:52-63] |

## Common Pitfalls

### Pitfall 1: Treating target docs as implemented source

What goes wrong: a planner may assert `safety_pre_route` or `risk_gate` already exists as an active graph node because it appears in contract docs. [CITED: docs/contract-spec.md:434-460]

Why it happens: Phase 50 distinguishes current source facts from target authority, and current `graph.py` still registers legacy names. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:123-130; VERIFIED: src/agent/graph.py:280-293]

How to avoid: Phase 51 tests should separately assert current active nodes and target canonical nodes. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:120-125]

### Pitfall 2: Using `graph_vocabulary.py` alone as the migration matrix

What goes wrong: `generate_recommendation` would be missed because the active graph registers it but `graph_vocabulary.py` currently lacks a `generate_recommendation -> recommendation_generation` entry. [VERIFIED: src/agent/graph.py:287; VERIFIED: src/agent/graph_vocabulary.py:41-103]

Why it happens: existing Phase 32 vocabulary tests predate the Phase 50 current-to-target matrix and cover only a subset of aliases. [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-28; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162]

How to avoid: build Phase 51's migration-mode matrix from the active node baseline plus Phase 50 matrix, then optionally compare available vocabulary entries without making vocabulary completeness the only source. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162]

### Pitfall 3: Confusing vocabulary entries with registered graph nodes

What goes wrong: `memory_write` is marked as a runnable runtime vocabulary entry but is excluded from the current main-chain registered node set. [VERIFIED: src/agent/graph_vocabulary.py:48; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:65-69]

Why it happens: `graph_vocabulary.py` projects traces/events and does not itself prove `StateGraph.add_node(...)` registration. [VERIFIED: src/agent/graph_vocabulary.py:129-139; VERIFIED: src/agent/graph.py:280-293]

How to avoid: the forbidden-node drift test must inspect actual `builder.add_node(...)` names, not just vocabulary entries. [VERIFIED: src/agent/graph.py:280-293]

### Pitfall 4: Failing the final no-debt gate too early

What goes wrong: an exact target-set test would fail immediately because Phase 51 intentionally precedes runtime rewiring. [CITED: .planning/ROADMAP.md:356-367; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:52-63]

Why it happens: Phase 50 defines a final gate, but Phase 51 only creates baseline guardrails before implementation phases. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:210-250]

How to avoid: make the final equality test skipped or xfailed with a Phase 58 deletion/enforcement note. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:63; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:164-177]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest, project dev dependency `pytest>=8.0`; local command returned pytest 9.0.3. [VERIFIED: pyproject.toml:34-39; VERIFIED: uv run pytest --version] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"`. [VERIFIED: pyproject.toml:54-55] |
| Quick run command | `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` [VERIFIED: AGENTS.md:24-29] |
| Full architecture command | `uv run pytest tests/architecture -q` [VERIFIED: AGENTS.md:24-29; VERIFIED: rg --files tests/architecture] |
| Full suite command | `uv run pytest` [VERIFIED: AGENTS.md:24-29] |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-02 | Current active graph node set is source-verified. [CITED: .planning/REQUIREMENTS.md:54] | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_current_active_graph_node_set_matches_phase51_baseline -q` | No, Wave 0 create. [VERIFIED: rg --files tests/architecture] |
| CAGM-02 | Router route values and destinations are source-verified. [CITED: .planning/REQUIREMENTS.md:54] | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_current_router_mappings_match_source_baseline -q` | No, Wave 0 create. [VERIFIED: rg --files tests/architecture] |
| CAGM-02 | Legacy-to-target migration-mode matrix covers every active legacy registered node. [CITED: .planning/REQUIREMENTS.md:54] | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_migration_mode_maps_every_active_legacy_node_to_target -q` | No, Wave 0 create. [VERIFIED: rg --files tests/architecture] |
| CAGM-02 | `slot_extraction` cannot drift into registered graph nodes. [CITED: .planning/ROADMAP.md:363-367] | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_slot_extraction_drift_is_explicitly_rejected -q` | No, Wave 0 create. [VERIFIED: rg --files tests/architecture] |
| CAGM-02 | Final exact 15-node no-debt gate is documented but not enforced before Phase 58. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:63] | architecture/static skipped or xfail | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_future_until_phase58 -q` | No, Wave 0 create. [VERIFIED: rg --files tests/architecture] |

### Sampling Rate

- Per task commit: `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` [VERIFIED: AGENTS.md:24-29]
- Per plan completion: `uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase34_approval_action_boundaries.py -q` [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-56; VERIFIED: tests/architecture/test_phase34_approval_action_boundaries.py:37-55]
- Phase gate: `uv run pytest tests/architecture -q` plus `git diff --check`. [VERIFIED: AGENTS.md:24-29; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:269-280]

### Wave 0 Gaps

- [ ] `tests/architecture/graph_baseline.py` or equivalent helper/constants module. [VERIFIED: rg --files tests/architecture]
- [ ] `tests/architecture/test_canonical_graph_baseline.py`. [VERIFIED: rg --files tests/architecture]
- [ ] Optional `.planning/ARCHITECTURE-DEBT.md` update for baseline guardrail status. [VERIFIED: AGENTS.md:16-22; VERIFIED: .planning/ARCHITECTURE-DEBT.md:29-31]

## Runtime State Inventory

Phase 51 does not rename runtime graph nodes, registered services, stored data, environment variables, or OS registrations; it is guardrail/test/docs only. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30]

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None to migrate in Phase 51 because no runtime node name is changed by this phase. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | None for Phase 51; later runtime cutover phases must reassess if persisted traces/checkpoints depend on legacy node names. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250] |
| Live service config | None to change in Phase 51 because tests inspect source files only. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:71-75] | None. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:71-75] |
| OS-registered state | None to change in Phase 51 because no services or registrations are renamed. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | None. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |
| Secrets/env vars | None identified for Phase 51 because no env var names or secret keys are in scope. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | None. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |
| Build artifacts | None to refresh for Phase 51 beyond normal test execution because no package metadata or runtime code is changed. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | None. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Approved MOCA test commands | Yes [VERIFIED: uv --version] | 0.11.2 [VERIFIED: uv --version] | `.venv/bin/pytest ...` only if repo venv is confirmed. [VERIFIED: AGENTS.md:24-29] |
| Python | AST helpers and tests | Yes [VERIFIED: uv run python --version] | 3.12.13 [VERIFIED: uv run python --version] | None needed. [VERIFIED: pyproject.toml:5] |
| pytest | Architecture tests | Yes [VERIFIED: uv run pytest --version] | 9.0.3 [VERIFIED: uv run pytest --version] | None needed. [VERIFIED: pyproject.toml:34-39] |

Missing dependencies with no fallback: none found for Phase 51. [VERIFIED: uv --version; VERIFIED: uv run python --version; VERIFIED: uv run pytest --version]

Missing dependencies with fallback: none found for Phase 51. [VERIFIED: uv --version; VERIFIED: uv run python --version; VERIFIED: uv run pytest --version]

## Security Domain

Phase 51 does not add request handlers, authentication flows, authorization checks, persistence, or user-input processing. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] Security relevance is indirect: guardrails preserve deterministic route boundaries and prevent accidental promotion of helper/lifecycle names into registered graph nodes. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:81-84; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:194-208]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No for Phase 51. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | No runtime auth changes. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |
| V3 Session Management | No for Phase 51. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | No runtime session changes. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |
| V4 Access Control | Indirect only. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:194-208] | Preserve deterministic graph/risk/approval boundaries via static tests. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:194-208] |
| V5 Input Validation | Indirect only. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:194-208] | Keep LLM outputs candidate-only for future contextual intent and slot boundaries; Phase 51 documents/tests names only. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:198-200] |
| V6 Cryptography | No for Phase 51. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | No crypto changes. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] |

## Risks/Landmines

| Risk | Why it matters | Planning mitigation |
|------|----------------|---------------------|
| `generate_recommendation` is active but missing from `graph_vocabulary.py`. [VERIFIED: src/agent/graph.py:287; VERIFIED: src/agent/graph_vocabulary.py:41-103] | A vocabulary-only test would miss one active legacy node that Phase 50 explicitly maps to `recommendation_generation`. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:152] | Build the migration-mode matrix from parsed active nodes plus Phase 50 matrix; do not rely solely on vocabulary entries. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-162] |
| `memory_write` is vocabulary-runtime but forbidden as a main-chain registered node. [VERIFIED: src/agent/graph_vocabulary.py:48; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:65-69] | A naive test may fail on vocabulary status even though the actual registered graph does not include `memory_write`. [VERIFIED: src/agent/graph.py:280-293] | Test `StateGraph.add_node(...)` registrations for forbidden drift; keep vocabulary status as a documented landmine. [VERIFIED: src/agent/graph.py:280-293] |
| `recommendation_generation` appears as route key but maps to legacy destination `generate_recommendation`. [VERIFIED: src/agent/graph.py:318-335] | Route labels and registered node keys are not always identical during migration mode. [VERIFIED: src/agent/graph.py:318-335] | Test route key/destination maps exactly and document canonical-key-to-legacy-destination cases. [VERIFIED: src/agent/graph.py:318-335] |
| Final exact target-node test would fail today. [VERIFIED: src/agent/graph.py:280-293; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:17-35] | Phase 51 is before runtime rewiring. [CITED: .planning/ROADMAP.md:356-367] | Mark final no-debt equality as skipped/xfail until Phase 58. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:63] |
| Plan grain can become too broad. [VERIFIED: AGENTS.md:55-60] | One plan covering helper design, tests, docs, ledger, and validation would violate MOCA plan granularity guidance. [VERIFIED: AGENTS.md:55-60] | Split into helper/matrix, tests, and docs/ledger plans. [VERIFIED: AGENTS.md:55-60] |
| Bare pytest commands are invalid in MOCA. [VERIFIED: AGENTS.md:24-29] | Bad verification can produce false collection failures due to wrong Python. [VERIFIED: AGENTS.md:24-29] | Every plan acceptance command must use `uv run pytest ...` or the approved `.venv/bin/...` form. [VERIFIED: AGENTS.md:24-29] |

## Files Likely Modified

| File | Change Type | Rationale |
|------|-------------|-----------|
| `tests/architecture/graph_baseline.py` or equivalent | New test helper/constants | Keeps target/current/migration/forbidden constants reusable and test-local. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:32-50; VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-54] |
| `tests/architecture/test_canonical_graph_baseline.py` | New architecture test file | Implements CAGM-02 static guardrails. [CITED: .planning/REQUIREMENTS.md:54; VERIFIED: src/agent/graph.py:280-377] |
| `.planning/ARCHITECTURE-DEBT.md` | Planning ledger update, if implementation narrows the canonical graph migration debt | Project rules require core subsystem architecture debt updates when graph/intent/memory/RAG debt is narrowed or fixed. [VERIFIED: AGENTS.md:16-22] |
| `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-*-PLAN.md` | Plan artifacts | Phase 51 is not planned yet and needs numbered plans. [VERIFIED: .planning/STATE.md:32-37; VERIFIED: .planning/ROADMAP.md:356-369] |
| `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-SUMMARY.md` / `51-VALIDATION.md` | Later execution closeout artifacts | Phase execution should record that runtime migration remains incomplete and final no-debt gate is deferred to Phase 58. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:77-80] |

Files that should not be modified in Phase 51 unless the plan explicitly records a harmless test-only seam or a reviewed docs correction: `src/agent/graph.py`, `src/agent/routing.py`, runtime node implementations, `docs/contract-spec.md`, and `docs/target-agent-platform-architecture-plan.md`. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30; VERIFIED: src/agent/graph.py:280-377]

## Code Examples

### Parse registered graph nodes

```python
def graph_add_node_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_node"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value)
    return names
```

Source pattern: existing architecture tests parse source with `ast` for static boundary checks. [VERIFIED: tests/architecture/test_action_draft_boundaries.py:40-54]

### Parse conditional graph mappings

```python
def graph_conditional_edge_mappings(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_conditional_edges"
            and len(node.args) >= 3
        ):
            continue
        source = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
        router = node.args[1].id if isinstance(node.args[1], ast.Name) else None
        route_map = node.args[2]
        if not isinstance(source, str) or router is None or not isinstance(route_map, ast.Dict):
            continue
        mappings[(source, router)] = {
            key.value: value.value
            for key, value in zip(route_map.keys, route_map.values, strict=True)
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        }
    return mappings
```

Source target: `src/agent/graph.py` currently defines all conditional edge maps with literal strings. [VERIFIED: src/agent/graph.py:297-372]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No assumptions were needed for source facts; the only MEDIUM-confidence point is the recommendation to keep Phase 51 migration constants test-local rather than editing runtime vocabulary. [VERIFIED: src/agent/graph.py:280-377; VERIFIED: src/agent/graph_vocabulary.py:41-103; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30] | Summary / Recommended Plan Split | If the planner chooses to edit `src/agent/graph_vocabulary.py`, it must explicitly scope that as non-rewiring and verify trace projection impact. [VERIFIED: src/agent/graph_vocabulary.py:129-139] |

## Open Questions

1. Should Phase 51 add `generate_recommendation -> recommendation_generation` to `src/agent/graph_vocabulary.py`, or should it keep that mapping test-local until the Phase 56 runtime cutover? [VERIFIED: src/agent/graph.py:287; VERIFIED: src/agent/graph_vocabulary.py:41-103; CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:152]
   - What we know: Phase 50 requires the mapping, and current `graph_vocabulary.py` lacks it. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:152; VERIFIED: src/agent/graph_vocabulary.py:41-103]
   - What's unclear: whether the planner should treat `graph_vocabulary.py` as a runtime source file out of scope for Phase 51. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30]
   - Recommendation: keep the mapping in the Phase 51 test helper unless the plan explicitly scopes a no-behavior vocabulary projection update and validates trace projection. [VERIFIED: src/agent/graph_vocabulary.py:129-139; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30]

## Sources

### Primary (HIGH confidence)

- `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md` - phase boundary, locked decisions, target set, migration-mode policy, forbidden drift, test approach. [CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:7-140]
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - migration charter, target graph, current-to-target matrix, compatibility policy, validation matrix, final no-debt gate. [CITED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:1-267]
- `src/agent/graph.py` - active registered graph node set and edge/router wiring. [VERIFIED: src/agent/graph.py:276-377]
- `src/agent/routing.py` - current route constants and router return values. [VERIFIED: src/agent/routing.py:21-38; VERIFIED: src/agent/routing.py:295-378]
- `src/agent/graph_vocabulary.py` - current vocabulary entries and projection behavior. [VERIFIED: src/agent/graph_vocabulary.py:13-139]
- `docs/contract-spec.md` - accepted target graph vocabulary and exclusions. [CITED: docs/contract-spec.md:430-460]
- `docs/target-agent-platform-architecture-plan.md` - readable target graph and explanatory boundaries. [CITED: docs/target-agent-platform-architecture-plan.md:228-340]
- `tests/architecture/` existing tests - architecture-test style and helpers. [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-172; VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-121; VERIFIED: tests/architecture/test_phase34_approval_action_boundaries.py:37-55]

### Secondary (MEDIUM confidence)

- `uv run python` AST extraction command - confirmed current node and conditional-edge maps in this research session. [VERIFIED: uv run python AST extraction of src/agent/graph.py]
- `.planning/config.json` - Nyquist validation enabled and `commit_docs` true. [VERIFIED: .planning/config.json:1-43]
- `pyproject.toml` and local commands - project Python/test tool availability. [VERIFIED: pyproject.toml:1-55; VERIFIED: uv --version; VERIFIED: uv run python --version; VERIFIED: uv run pytest --version]

### Tertiary (LOW confidence)

- None. [VERIFIED: all research claims above cite source files, config, or inspected command output]

## Metadata

**Confidence breakdown:**
- Current source facts: HIGH, because active nodes and routes were verified from `src/agent/graph.py` and a session AST extraction. [VERIFIED: src/agent/graph.py:280-377; VERIFIED: uv run python AST extraction of src/agent/graph.py]
- Architecture/test approach: HIGH, because existing architecture tests already use source/AST and vocabulary checks. [VERIFIED: tests/architecture/test_phase32_static_contract.py:17-172; VERIFIED: tests/architecture/test_action_draft_boundaries.py:36-121]
- Recommended plan split: HIGH, because project rules require granular plans and Phase 51 context suggests static tests/helpers/docs only. [VERIFIED: AGENTS.md:55-60; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:120-128]
- Whether to update `graph_vocabulary.py`: MEDIUM, because the source gap is verified but the Phase 51 no-runtime-change boundary makes the exact location of the mapping a planning decision. [VERIFIED: src/agent/graph_vocabulary.py:41-103; CITED: .planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-CONTEXT.md:27-30]

**Research date:** 2026-07-06 [VERIFIED: system date]
**Valid until:** 2026-08-05, unless `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/graph_vocabulary.py`, or Phase 50/51 planning docs change first. [VERIFIED: src/agent/graph.py:280-377; VERIFIED: src/agent/routing.py:21-38; VERIFIED: src/agent/graph_vocabulary.py:41-103]
