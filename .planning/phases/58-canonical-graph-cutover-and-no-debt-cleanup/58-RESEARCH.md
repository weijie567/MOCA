# Phase 58: Canonical Graph Cutover and No-Debt Cleanup - Research

**Researched:** 2026-07-08
**Domain:** MOCA canonical LangGraph runtime cutover, migration-debt deletion, trace/API/frontend/eval projection, approval resume safety
**Confidence:** HIGH for local code and validation inventory; MEDIUM for production runtime-state inventory not directly connected during research

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for all copied constraints in this section: [VERIFIED: `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-CONTEXT.md`]

### Locked Decisions

## Implementation Decisions

### Final No-Debt Scope

- **D-58-01:** Treat `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` Final No-Debt Gate as the controlling checklist. The plan must close every checklist item or record a reviewed spec/implementation exception; silent partial cleanup is not acceptable.
- **D-58-02:** Active runtime graph behavior is already source-verified as canonical: `graph_add_node_names()` currently returns 15 nodes and equals `TARGET_CANONICAL_GRAPH_NODES`; route map scan found no legacy route destinations. Planning should preserve this state and focus on final debt removal, not risky runtime rewiring.
- **D-58-03:** Do not bulk-rewrite historical production data. Historical trace/API/replay rows may remain readable, but current-run projection and active runtime contracts must no longer depend on compatibility aliases labeled as active graph vocabulary.

### Compatibility Alias Cleanup

- **D-58-04:** Close all `DELETE_BY_PHASE_58` compatibility rows intentionally. Primary source candidates include `src/agent/graph_vocabulary.py`, legacy wrapper modules/tests for `generate_recommendation` and `assess_risk_and_approval`, frontend/API trace labels, approval retry normalization, eval replay manifest rows, and stale architecture tests.
- **D-58-05:** Prefer deleting import/test-only wrappers when no current runtime code imports them. If a helper must remain for historical projection or internal implementation, reclassify it as internal/historical and prove it is not a main graph compatibility alias.
- **D-58-06:** Persisted historical approval retry metadata must not authorize a legacy resume route. If `src/api/routers/approvals.py` still needs a server-side canonicalization path for old rows, the plan must name it as bounded data-read compatibility, not graph vocabulary compatibility, and tests must prove graph resume emits `risk_gate`.

### Trace, API, Eval, And Docs

- **D-58-07:** Current-run trace/API/SSE/frontend/eval surfaces should present canonical names. Tests that preserve old node names should be narrowed to historical-row readability only, or removed if they merely preserve migration-era compatibility.
- **D-58-08:** Documentation and planning ledgers must distinguish target contract, implemented current state, and historical references. Current architecture docs should no longer describe legacy names as active runtime nodes, current route values, or current resume routes.
- **D-58-09:** The final skipped gate in `tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope` should become a real assertion as part of closeout.

### Validation Strategy

- **D-58-10:** Verification must use MOCA-approved entrypoints only: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.
- **D-58-11:** Include a static legacy-hit classifier in the plan and final validation. It should report total hits, file/path categories, zero active-runtime legacy hits, and zero unclassified rows. It should avoid recursive self-counting of the generated validation artifact.
- **D-58-12:** Keep verification scoped enough for fast feedback during tasks, then run a broad closeout suite covering graph baseline, routing, graph vocabulary, trace/API projections, approval resume, recommendation/risk wrapper deletions, eval/diagnostic surfaces, docs guards, ruff, and `git diff --check`.

### the agent's Discretion

The agent may choose exact plan decomposition, but it should be split by ownership boundary rather than one large plan. A reasonable split is: source/graph vocabulary cleanup, projection/API/eval/frontend cleanup, docs/debt/validation closeout, and final broad verification. Each plan must have concrete file scope and tests.

### Deferred Ideas (OUT OF SCOPE)

## Deferred Ideas

None — discussion stayed within Phase 58 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-09 | The active runtime graph is cut over to the final 15 canonical registered nodes, with active legacy node names, dual routes, and runtime compatibility aliases removed or internalized so no migration debt remains. [VERIFIED: `.planning/REQUIREMENTS.md`] | Active graph AST helpers already report the final 15 nodes and no legacy route values; Phase 58 should enforce that as a non-skipped gate, then remove or internalize `DELETE_BY_PHASE_58` aliases, wrappers, projection rows, docs, and eval manifest debt. [VERIFIED: `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `src/agent/graph.py`, `src/agent/routing.py`, static scans run 2026-07-08] |
</phase_requirements>

## Summary

Phase 58 should be planned as a final no-debt cleanup and verification phase, not as a runtime graph rewrite. The active main graph already registers the Phase 50 canonical 15-node set and current router return values do not point to the legacy graph node names. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python ... graph_add_node_names()/graph_router_route_values()` run during research; `tests/architecture/graph_baseline.py`; `src/agent/graph.py`; `src/agent/routing.py`] The highest-risk work is therefore removing migration scaffolding without breaking historical trace/readability, approval retry safety, or eval/frontend/API current-run projections. [VERIFIED: `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-CONTEXT.md`; `src/agent/graph_vocabulary.py`; `src/api/routers/approvals.py`; `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`; `eval/replay/dev-contract-manifest.v1.json`]

The major planning boundary is active runtime vocabulary versus historical data-read projection. `src/agent/graph_vocabulary.py` currently mixes canonical runtime entries with `compatibility_alias` rows for legacy graph names and route helper names, several explicitly marked `DELETE_BY_PHASE_58`. [VERIFIED: `src/agent/graph_vocabulary.py`] Phase 58 should split or reclassify those surfaces so the main graph vocabulary exposes only canonical runtime concepts, while any remaining support for old stored rows is named as historical projection/data-read compatibility. [VERIFIED: `58-CONTEXT.md` decisions D-58-03 through D-58-07]

**Primary recommendation:** Create multiple ownership-boundary plans: active graph/vocabulary final gate, legacy wrapper/import-test deletion, API/frontend/eval/historical projection cleanup, approval retry data-read compatibility hardening, and docs/debt/final validation closeout. Do not produce a single oversized `58-01-PLAN.md`. [VERIFIED: `AGENTS.md` PLAN 粒度硬约束; `58-CONTEXT.md` agent discretion]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Active 15-node graph registration and conditional routing | API / Backend | Test / Validation | `src/agent/graph.py` owns `StateGraph.add_node(...)` and conditional edges; `tests/architecture/graph_baseline.py` parses source to enforce the contract. [VERIFIED: `src/agent/graph.py`; `tests/architecture/graph_baseline.py`] |
| Canonical graph vocabulary for current runtime | API / Backend | Test / Validation | `src/agent/graph_vocabulary.py` maps implementation names to target names and is the active alias cleanup target. [VERIFIED: `src/agent/graph_vocabulary.py`; `58-CONTEXT.md` D-58-04] |
| Historical trace/replay readability | Database / Storage | API / Backend, Frontend | `agent_steps.node_name`, `replay_events.node_name`, and trace APIs can contain historical names; the current decision forbids bulk rewrite and requires bounded readability. [VERIFIED: `src/db/models.py`; `src/repositories/trace_repo.py`; `src/api/routers/traces.py`; `58-CONTEXT.md` D-58-03] |
| Approval edit retry resume authority | API / Backend | Database / Storage | Approval retry reconstruction reads persisted metadata but must emit only canonical `risk_gate` into graph resume. [VERIFIED: `src/api/routers/approvals.py`; `src/approvals/service.py`; `tests/test_approval_api.py`; `tests/test_graph_routing.py`] |
| SSE/API timeline current-run projection | API / Backend | Frontend | `src/api/routers/agent_runs.py` emits timeline/SSE payloads and current-run branch logic; frontend renders node labels from API payloads. [VERIFIED: `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`] |
| Frontend timeline display | Browser / Client | API / Backend | `TimelineStep.tsx` owns browser labels, but should not decide active runtime graph vocabulary. [VERIFIED: `frontend/src/components/timeline/TimelineStep.tsx`] |
| Eval/replay manifest and diagnostic patch points | Test / Validation | API / Backend | `scripts/eval_agent.py` and `eval/replay/dev-contract-manifest.v1.json` still reference legacy wrappers/test paths and must track canonical current-run surfaces. [VERIFIED: `scripts/eval_agent.py`; `eval/replay/dev-contract-manifest.v1.json`] |
| Docs and architecture debt closeout | Documentation / Planning | Test / Validation | Current-source docs and `.planning/ARCHITECTURE-DEBT.md` must stop describing legacy names as active current runtime nodes, while preserving historical context. [VERIFIED: `58-CONTEXT.md` D-58-08; `AGENTS.md`; `CLAUDE.md`] |

## Project Constraints (from CLAUDE.md and AGENTS.md)

- Local validation, API testing, UI testing, RAG/agent/memory/tool-call debugging failures must be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` after handling, in Chinese, with symptom, reproduction, evidence, root-cause judgment, treatment, remaining issue, and next entry point. [VERIFIED: `CLAUDE.md`; `AGENTS.md`]
- Changes to tool calling, RAG, memory, or intent-recognition core subsystems must append verified subsystem-level bug/fix/debt entries to `.planning/ARCHITECTURE-DEBT.md`, in Chinese. Phase 58 touches agent graph/memory/intent-adjacent migration surfaces, so final closeout should update the ledger when debt is removed. [VERIFIED: `CLAUDE.md`; `AGENTS.md`]
- MOCA validation commands must use `uv run`, `UV_CACHE_DIR=/tmp/uv-cache uv run`, or `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid evidence. [VERIFIED: `AGENTS.md`]
- Phase-level planning must split work when a phase spans multiple service boundaries, ownership domains, waves, or verification gates; one oversized plan that covers contract, migration, compatibility, callers, security boundary, and final verification is a planning blocker. [VERIFIED: `AGENTS.md`]
- `docs/contract-spec.md` is the accepted contract reference for semantics, but not automatic proof of implementation; any divergence between phase implementation and spec must be recorded rather than silently accepted. [VERIFIED: `AGENTS.md`; `CLAUDE.md`]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | 1.1.10 | Builds the MOCA agent runtime graph through `StateGraph`. [VERIFIED: local `importlib.metadata.version("langgraph")`] | Existing active graph uses LangGraph; no new graph framework should be introduced for a cutover cleanup. [VERIFIED: `src/agent/graph.py`; `pyproject.toml`] |
| Python | >=3.12 project requirement | Runtime and test language for backend, graph, API, and architecture guards. [VERIFIED: `pyproject.toml`] | Current code uses Python 3.12+ assumptions and MOCA test rules warn against old local Python. [VERIFIED: `AGENTS.md`] |
| `pytest` / `pytest-asyncio` | pytest 9.0.3 / pytest-asyncio 1.3.0 | Unit, integration, architecture, and API validation. [VERIFIED: local `importlib.metadata.version(...)`; `pyproject.toml`] | Existing Phase 57 validation and current architecture tests use pytest. [VERIFIED: `57-VALIDATION.md`; `tests/architecture/test_canonical_graph_baseline.py`] |
| FastAPI / Pydantic | FastAPI 0.136.1 / Pydantic 2.13.4 | API routers and response models for approvals, traces, and agent runs. [VERIFIED: local `importlib.metadata.version(...)`; `src/api/routers/approvals.py`; `src/api/routers/agent_runs.py`] | Phase 58 changes API projection and approval resume behavior in existing routers; no API framework migration is in scope. [VERIFIED: `58-CONTEXT.md`] |
| React / Vite / Vitest / TypeScript | React 19.2.6, Vite 8.0.12, Vitest 4.1.7, TypeScript 6.0.2 | Frontend timeline rendering and build verification. [VERIFIED: `frontend/package.json`] | Timeline label cleanup must fit the existing frontend stack and be build-verified with `npm --prefix frontend run build`. [VERIFIED: `frontend/package.json`; `57-VALIDATION.md`] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `ruff` | 0.15.12 | Python lint/format gate. [VERIFIED: local `importlib.metadata.version("ruff")`; `pyproject.toml`] | Run after source/test cleanup that deletes wrappers or moves implementation helpers. [VERIFIED: `57-VALIDATION.md`] |
| `uv` | 0.11.2 | Approved MOCA Python command entrypoint. [VERIFIED: `uv --version`] | Use for every pytest, ruff, and inline Python static classifier command. [VERIFIED: `AGENTS.md`] |
| `git grep` / `rg` | system tools | Static scan and candidate inventory. [VERIFIED: commands run during research] | Use for `DELETE_BY_PHASE_58`, legacy-node, and docs/current-source drift classification. [VERIFIED: `58-CONTEXT.md` D-58-11] |
| Docker | 29.4.2 server available locally | Optional service/container support. [VERIFIED: `docker info`] | Not required for source-only tests unless a planner adds DB/container validation. [VERIFIED: environment audit] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `tests/architecture/graph_baseline.py` AST helpers | Ad hoc text grep of `graph.py` and `routing.py` | Do not use ad hoc grep for final graph correctness; existing AST helpers already expose registered node names, router values, conditional edge maps, and baselines. [VERIFIED: `tests/architecture/graph_baseline.py`] |
| Existing `graph_vocabulary.py` projection APIs plus a separated historical map | Keep active `compatibility_alias` rows in the main vocabulary | Keeping active compatibility aliases conflicts with CAGM-09 and Phase 50 final no-debt gate. [VERIFIED: `50-SPEC.md`; `58-CONTEXT.md` D-58-04] |
| Source-level cleanup and historical projection | Bulk SQL/data migration rewriting old node names | Bulk rewrite is explicitly out of scope and risks audit/replay integrity. [VERIFIED: `58-CONTEXT.md` D-58-03] |

**Installation:**

No new packages are recommended. [VERIFIED: `pyproject.toml`; `frontend/package.json`; current local package versions]

**Version verification:** Package versions above were verified locally with approved project entrypoints and package metadata during research. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import importlib.metadata as m; ..."`; `uv --version`; `node --version`; `npm --version`; `frontend/package.json`]

## Current Evidence Inventory

### Active Runtime State

| Evidence | Finding | Planning Impact |
|----------|---------|-----------------|
| Active graph nodes | Sorted active `StateGraph.add_node(...)` names equal the Phase 50 target 15-node set: `receive_request`, `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `investigate`, `rag_context_build`, `recommendation_generation`, `claim_verify`, `risk_gate`, `approval_gate`, `action_draft`, `clarification_gate`, `final_response`. [VERIFIED: `tests/architecture/graph_baseline.py`; research command output; `50-SPEC.md`] | First plan should turn the skipped final no-debt gate into a real assertion and preserve this state. |
| Legacy route values | Router return values found during research are canonical, including `risk_gate`, `recommendation_generation`, `memory_context_load`, and `slot_resolution_gate`; no route value points to `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, or `assess_risk_and_approval`. [VERIFIED: research command output from `graph_router_route_values()`; `src/agent/routing.py`] | Plans should not introduce runtime rewiring; they should delete stale delegates/tests around old route helper names. |
| Skipped final gate | `test_final_no_debt_gate_is_marked_phase58_scope` currently skips before asserting `graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES`. [VERIFIED: `tests/architecture/test_canonical_graph_baseline.py`] | Phase 58 must replace this skip with live assertions for exact graph, no active legacy aliases, and no unclassified legacy hits. |
| Focused current tests | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` produced `13 passed, 1 skipped`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` produced `58 passed`. [VERIFIED: commands run during research] | Existing tests are a useful baseline but still preserve migration-era expectations; planner must update them rather than only rerun them. |

### `DELETE_BY_PHASE_58` Candidate Classification

Research command scope: tracked source, tests, docs, frontend, scripts, eval, rules, and planning ledgers excluding generated validation self-counting where applicable. [VERIFIED: `git grep -n "DELETE_BY_PHASE_58" -- README.md docs src tests frontend scripts eval rules .planning/ARCHITECTURE-DEBT.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md`]

| Ownership Boundary | Count | Files / Rows | Required Plan Treatment |
|--------------------|------:|--------------|-------------------------|
| Graph vocabulary runtime alias debt | 9 | `src/agent/graph_vocabulary.py` rows for legacy aliases and route helper aliases. [VERIFIED: `src/agent/graph_vocabulary.py`] | Remove from active runtime vocabulary or move to explicitly historical projection map. |
| Architecture projection tests | 9 | `tests/agent/test_graph_vocabulary.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/architecture/test_memory_contract_delta.py`, `tests/architecture/test_phase34_approval_action_boundaries.py`, `tests/memory/test_phase48_1_memory_compat_alignment.py`. [VERIFIED: static scan] | Replace alias-preservation assertions with canonical-current assertions plus historical-only tests where needed. |
| Planning architecture debt ledger | 6 | `.planning/ARCHITECTURE-DEBT.md`. [VERIFIED: static scan] | Update Chinese ledger entries to closed/resolved, or record reviewed exception. |
| Current docs compatibility table | 4 | `docs/current-langgraph-architecture.md`. [VERIFIED: static scan] | Remove legacy aliases from current-active table or re-label as historical-only. |
| API/frontend historical projection debt | 2 | `src/api/routers/agent_runs.py`, `frontend/src/components/timeline/TimelineStep.tsx`. [VERIFIED: static scan] | Current-run payloads and labels should be canonical; historical handling must be bounded. |
| Risk legacy wrapper debt | 2 | `src/agent/nodes/assess_risk_and_approval.py`. [VERIFIED: static scan] | Move shared implementation to canonical/private module, then delete or internalize wrapper. |
| Recommendation legacy wrapper debt | 2 | `src/agent/nodes/generate_recommendation.py`. [VERIFIED: static scan] | Move shared implementation to canonical/private module, then delete or internalize wrapper. |
| Approval retry historical read compatibility | 2 | `src/api/routers/approvals.py`. [VERIFIED: static scan] | If retained, name as data-read compatibility and prove output route is canonical `risk_gate`. |
| Risk wrapper tests | 2 | `tests/agent/test_nodes/test_assess_risk_and_approval.py`. [VERIFIED: static scan] | Delete or rewrite as canonical `risk_gate` tests. |
| Recommendation wrapper tests | 2 | `tests/agent/test_nodes/test_generate_recommendation.py`. [VERIFIED: static scan] | Delete or rewrite as canonical `recommendation_generation` tests. |

### Legacy Wrapper and Import Surface

| Legacy Surface | Current Owner / Dependency | Recommended Planning Decision |
|----------------|----------------------------|-------------------------------|
| `generate_recommendation` | Shared implementation currently lives in `src/agent/nodes/generate_recommendation.py`; `src/agent/nodes/recommendation_generation.py` imports `_generate_recommendation_with_identity` from it. [VERIFIED: `src/agent/nodes/generate_recommendation.py`; `src/agent/nodes/recommendation_generation.py`] | Move implementation into `recommendation_generation.py` or a private canonical helper, update test fakes and eval patch points, then delete legacy wrapper if no import remains. |
| `assess_risk_and_approval` | Shared implementation currently lives in `src/agent/nodes/assess_risk_and_approval.py`; `src/agent/nodes/risk_gate.py` imports it as implementation. [VERIFIED: `src/agent/nodes/assess_risk_and_approval.py`; `src/agent/nodes/risk_gate.py`] | Move implementation into `risk_gate.py` or a private canonical helper, update tests/rules references, then delete legacy wrapper if no import remains. |
| `extract_slots` | `slot_resolution_gate.py` imports helper functions from `extract_slots.py`. [VERIFIED: `src/agent/nodes/extract_slots.py`; `src/agent/nodes/slot_resolution_gate.py`] | Move shared prompt helpers to canonical/private helper before deleting wrapper. |
| `classify_intent` | Compatibility wrapper around `contextual_intent_resolve`; tests still import wrapper/helper. [VERIFIED: `src/agent/nodes/classify_intent.py`; test import scan] | Migrate tests to `contextual_intent_resolve` or canonical helper, then delete wrapper if unused. |
| `session_memory_load` | Compatibility wrapper around `session_context_load` with legacy node name support. [VERIFIED: `src/agent/nodes/session_memory_load.py`] | Delete after tests move to canonical session context surface, unless a bounded historical helper is explicitly needed. |
| `long_term_memory_retrieve` | Compatibility wrapper around `memory_context_load`; canonical implementation still strips legacy metrics. [VERIFIED: `src/agent/nodes/long_term_memory_retrieve.py`; `src/agent/nodes/memory_context_load.py`] | Delete wrapper if no current runtime/test import remains; preserve only historical projection/read behavior if still required. |
| `route_after_intent` / `route_after_slots` | Delegates remain in `src/agent/routing.py`; tests still import old function names. [VERIFIED: `src/agent/routing.py`; test import scan] | Remove delegates after tests move to `route_after_contextual_intent` and `route_after_slot_resolution`. |

## Architecture Patterns

### System Architecture Diagram

```text
Current request / graph resume
        |
        v
API / approval service boundary
        |
        | trusted approval edit resume? -- yes --> validate approval id / tenant / run / hash / snapshot / version
        |                                          |
        |                                          v
        |                                  canonical resume_route = risk_gate
        |                                          |
        no                                         v
        |                                  active StateGraph routers
        v                                          |
active LangGraph StateGraph ----------------------+
        |
        v
canonical node execution only
        |
        v
trace / replay writes with implementation node_name
        |
        +--> current-run API/SSE/frontend projection -> canonical node labels
        |
        +--> historical row read path -> bounded historical projection map
        |
        v
eval/replay manifests and docs validate canonical current contract
```

This flow keeps runtime authority in backend graph/router code, preserves old stored row readability through a bounded projection path, and prevents frontend/eval/docs from becoming sources of graph truth. [VERIFIED: `src/agent/graph.py`; `src/agent/routing.py`; `src/agent/trace.py`; `src/repositories/trace_repo.py`; `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`; `58-CONTEXT.md`]

### Recommended Project Structure

Do not introduce a new top-level package. Use the existing structure and move shared implementation only where deletion requires it. [VERIFIED: repository layout and existing modules]

```text
src/
├── agent/
│   ├── graph.py                    # active canonical StateGraph registration
│   ├── routing.py                  # canonical route functions only
│   ├── graph_vocabulary.py         # canonical runtime vocabulary; historical map if retained
│   └── nodes/
│       ├── recommendation_generation.py
│       ├── risk_gate.py
│       ├── slot_resolution_gate.py
│       └── ... canonical nodes
├── api/routers/
│   ├── agent_runs.py               # current-run timeline/SSE projection
│   ├── approvals.py                # bounded historical retry read compatibility
│   └── traces.py                   # trace read projection
tests/
├── architecture/                   # final graph/static gates
├── agent/                          # canonical node tests
└── ... API/eval/frontend-adjacent tests
frontend/src/components/timeline/    # display-only labels
eval/replay/                         # dev contract manifest
```

### Pattern 1: Separate Active Runtime Vocabulary from Historical Projection

**What:** Keep active graph vocabulary canonical-only, and isolate old stored-name mapping behind a name such as `historical_trace_projection` or `legacy_stored_node_projection`. [VERIFIED: `58-CONTEXT.md` D-58-03 through D-58-07; `src/agent/graph_vocabulary.py`]

**When to use:** Use this when trace/API/replay rows may contain old implementation names but current runtime and graph vocabulary must not advertise active compatibility aliases. [VERIFIED: `src/db/models.py`; `src/repositories/trace_repo.py`; `src/api/routers/traces.py`]

**Example:**

```python
# Source: local pattern recommendation from Phase 58 research.
RUNTIME_GRAPH_NODES = frozenset(TARGET_CANONICAL_GRAPH_NODES)

HISTORICAL_NODE_PROJECTIONS = {
    "generate_recommendation": "recommendation_generation",
    "assess_risk_and_approval": "risk_gate",
}

def target_graph_name(name: str, *, historical: bool = False) -> str:
    if name in RUNTIME_GRAPH_NODES:
        return name
    if historical:
        return HISTORICAL_NODE_PROJECTIONS.get(name, name)
    return name
```

Planner note: this is a pattern sketch, not an implementation requirement; exact API should follow local `GraphVocabularyEntry` call sites. [VERIFIED: `src/agent/graph_vocabulary.py`]

### Pattern 2: Canonical Implementation Module Owns Shared Logic

**What:** If a legacy wrapper module currently hosts shared implementation, move the implementation into the canonical module or a private helper imported by the canonical module. [VERIFIED: `src/agent/nodes/generate_recommendation.py`; `src/agent/nodes/recommendation_generation.py`; `src/agent/nodes/assess_risk_and_approval.py`; `src/agent/nodes/risk_gate.py`]

**When to use:** Use before deleting `generate_recommendation.py` and `assess_risk_and_approval.py`, because canonical modules currently import implementation from those files. [VERIFIED: same files]

**Example:**

```python
# Source: local wrapper-deletion pattern recommendation.
# Before: canonical module imports implementation from legacy module.
# After: canonical module owns implementation and tests patch canonical path.
async def recommendation_generation(state: AgentState) -> AgentState:
    return await _generate_recommendation_with_identity(
        state,
        output_key="recommendation_generation",
        trace_node="recommendation_generation",
    )
```

### Pattern 3: Server-Side Historical Approval Read Compatibility Is Not Route Authority

**What:** If old `approval_events.metadata_json` rows are still supported, canonicalize them only after trusted approval/run/hash/snapshot checks, and emit only `risk_gate` into graph resume. [VERIFIED: `src/api/routers/approvals.py`; `src/approvals/service.py`; `tests/test_approval_api.py`; `tests/test_graph_routing.py`]

**When to use:** Use for persisted historical retry metadata only, not for accepting client-provided old route names. [VERIFIED: `58-CONTEXT.md` D-58-06]

**Example:**

```python
# Source: local approval safety pattern recommendation.
resume_route = _canonical_retry_resume_route(stored_metadata_route)
if resume_route != "risk_gate":
    return None

return TrustedApprovalResumePayload(resume_route="risk_gate", ...)
```

### Anti-Patterns to Avoid

- **One giant cleanup plan:** This phase spans backend graph vocabulary, source wrapper deletion, API/frontend/eval projection, approval security, docs, and final validation; one plan would violate MOCA plan granularity rules. [VERIFIED: `AGENTS.md`; `58-CONTEXT.md`]
- **Bulk rewriting historical rows:** The locked decision forbids bulk production-data rewrite; it also risks damaging audit/replay evidence. [VERIFIED: `58-CONTEXT.md` D-58-03]
- **Keeping active `compatibility_alias` rows and merely changing comments:** CAGM-09 requires active runtime compatibility aliases to be removed or internalized; comment-only cleanup would not close the final gate. [VERIFIED: `.planning/REQUIREMENTS.md`; `50-SPEC.md`; `58-CONTEXT.md`]
- **Letting frontend labels define graph truth:** Timeline labels should render API state; they should not preserve legacy names for current-run graph contracts. [VERIFIED: `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`]
- **Trusting old resume route metadata as route authority:** Legacy `assess_risk_and_approval` metadata must not authorize graph resume; only canonical `risk_gate` can be emitted after server-side validation. [VERIFIED: `src/api/routers/approvals.py`; `58-CONTEXT.md` D-58-06]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Active graph node/route static verification | New grep-only parser for `graph.py` / `routing.py` | Existing `tests/architecture/graph_baseline.py` AST helpers | They already parse `StateGraph.add_node`, direct edges, conditional edges, and router return values. [VERIFIED: `tests/architecture/graph_baseline.py`] |
| Historical projection mixed with runtime graph vocabulary | More `compatibility_alias` rows in active vocabulary | Separate historical projection/data-read mapping | CAGM-09 and Phase 50 final gate require no active main-graph compatibility aliases. [VERIFIED: `50-SPEC.md`; `58-CONTEXT.md`] |
| Approval retry route validation | Client-side or raw-metadata route allowlist | Existing approval API/service validation plus canonical `risk_gate` resume only | Approval resume authority depends on server-side tenant/run/hash/snapshot/version checks. [VERIFIED: `src/api/routers/approvals.py`; `src/approvals/service.py`; `57-VALIDATION.md`] |
| Legacy-hit closeout evidence | Manual ad hoc notes | Static classifier with total/category/unclassified rows and self-count exclusion | Phase 57 established this pattern and Phase 58 context requires it. [VERIFIED: `57-VALIDATION.md`; `58-CONTEXT.md` D-58-11] |
| Frontend display compatibility | Independent browser-only legacy mapping | Backend projection plus frontend canonical labels | Browser code should not own graph semantics. [VERIFIED: `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`] |

**Key insight:** The remaining complexity is not creating canonical runtime behavior; it is deleting compatibility scaffolding while preserving bounded historical readability and security invariants. [VERIFIED: Phase 58 research scans; `58-CONTEXT.md`; `57-VALIDATION.md`]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agent_steps.node_name` stores trace step implementation names; `replay_events.node_name` stores replay node names; `approval_events.metadata_json` / `resource_refs_json` can preserve approval retry resume metadata. [VERIFIED: `src/db/models.py`; migrations `003_agent_tables.py`, `008_approval_state_machine.py`, `010_replay_event_v3.py`; `src/api/routers/approvals.py`] | No bulk rewrite. Preserve historical row readability through bounded projection/data-read compatibility. Ensure new/current writes emit canonical node names. Tests must prove historical approval metadata maps to canonical `risk_gate` and cannot authorize legacy graph resume. [VERIFIED: `58-CONTEXT.md` D-58-03/D-58-06] |
| Live service config | No repo-scoped live-service config with graph legacy node names was found during research. [VERIFIED: `rg`/`git grep` scans over tracked project roots] | No service-config migration planned. Production-only dashboards/workflows were not connected in this research session, so release checklist should state no external config was audited. [ASSUMED] |
| OS-registered state | No repo-scoped launchd/systemd/pm2/task registration embedding graph node names was found. [VERIFIED: repo scans; no OS registration files identified] | No OS re-registration task planned. If production has external process managers or dashboards, verify separately before release. [ASSUMED] |
| Secrets/env vars | `.env` and `.env.example` were scanned for legacy graph node names; no relevant hits were found. [VERIFIED: `rg -n "classify_intent|session_memory_load|extract_slots|long_term_memory_retrieve|generate_recommendation|assess_risk_and_approval|risk_gate|recommendation_generation" moca.egg-info .env .env.example`] | No secret/env rename needed. Do not print secret values in validation artifacts. [VERIFIED: `AGENTS.md` secrets posture implied by local rules] |
| Build artifacts / installed packages | `moca.egg-info/SOURCES.txt` contains legacy module filenames for `assess_risk_and_approval.py`, `classify_intent.py`, `extract_slots.py`, `generate_recommendation.py`, `long_term_memory_retrieve.py`, and `session_memory_load.py`. [VERIFIED: `rg ... moca.egg-info`] | After deleting/renaming source modules, run approved tests from `uv` and consider reinstalling editable metadata or regenerating egg-info if stale package metadata affects tooling. Do not treat egg-info rows as active runtime graph debt, but include them in final static scan classification if they remain. [VERIFIED: local scan] |

**Canonical question answer:** after tracked source files are updated, the runtime systems most likely to still hold old strings are historical DB rows and package/build metadata. Historical DB rows should remain readable; build metadata should be regenerated if stale. [VERIFIED: `src/db/models.py`; `moca.egg-info/SOURCES.txt`; `58-CONTEXT.md`]

## Common Pitfalls

### Pitfall 1: Treating Historical Readability as Active Runtime Compatibility

**What goes wrong:** The planner leaves old names in `graph_vocabulary.py` as `compatibility_alias` because old trace rows need display support. [VERIFIED: `src/agent/graph_vocabulary.py`]

**Why it happens:** Current vocabulary functions serve both runtime/current projection and historical projection. [VERIFIED: `src/agent/graph_vocabulary.py`; `src/repositories/trace_repo.py`; `src/api/routers/traces.py`]

**How to avoid:** Split or explicitly parameterize historical projection. Current runtime vocabulary should not advertise old node names as active aliases. [VERIFIED: `58-CONTEXT.md` D-58-03/D-58-07]

**Warning signs:** Tests still assert `target_graph_status == "compatibility_alias"` for current graph vocabulary, or new current-run events can emit old node names. [VERIFIED: `tests/agent/test_graph_vocabulary.py`; `src/api/routers/agent_runs.py`]

### Pitfall 2: Deleting Legacy Wrapper Files Before Moving Shared Implementation

**What goes wrong:** Removing `generate_recommendation.py` or `assess_risk_and_approval.py` breaks canonical modules that import implementation from those files. [VERIFIED: `src/agent/nodes/recommendation_generation.py`; `src/agent/nodes/risk_gate.py`]

**Why it happens:** The compatibility wrapper file is also the implementation host. [VERIFIED: `src/agent/nodes/generate_recommendation.py`; `src/agent/nodes/assess_risk_and_approval.py`]

**How to avoid:** First move shared logic to canonical module/private helper, then update tests/eval patch paths, then delete wrapper. [VERIFIED: import scan]

**Warning signs:** Tests or scripts patch `src.agent.nodes.generate_recommendation` for canonical behavior, or `risk_gate.py` imports legacy implementation module. [VERIFIED: `scripts/eval_agent.py`; `src/agent/nodes/risk_gate.py`]

### Pitfall 3: Approval Resume Route Spoofing Through Old Metadata

**What goes wrong:** Old `approval_events.metadata_json.resume_route = "assess_risk_and_approval"` becomes accepted route authority and drives graph resume to a legacy name. [VERIFIED: `src/api/routers/approvals.py`; `tests/test_approval_api.py`]

**Why it happens:** Historical data-read compatibility can be confused with client/runtime route authority. [VERIFIED: `58-CONTEXT.md` D-58-06]

**How to avoid:** Keep any old-row canonicalization server-side only, after trust checks, and assert the graph receives `risk_gate`. [VERIFIED: `src/api/routers/approvals.py`; `tests/test_graph_routing.py`]

**Warning signs:** `_should_resume_graph` or `route_after_approval` accepts legacy route strings; API response includes legacy resume route for retry. [VERIFIED: `src/api/routers/approvals.py`; `src/agent/graph.py`; `tests/test_graph_routing.py`]

### Pitfall 4: Static Scan Self-Counting and False Closure

**What goes wrong:** The final validation artifact counts its own legacy-name explanations and inflates totals, or unclassified rows are hidden. [VERIFIED: `57-VALIDATION.md` static scan notes]

**Why it happens:** Phase reports necessarily mention old node names while describing deletion. [VERIFIED: `57-05-SUMMARY.md`; `57-VALIDATION.md`]

**How to avoid:** Exclude generated Phase 58 validation/research artifacts from machine counts where appropriate, report scope, totals, category counts, and zero unclassified rows. [VERIFIED: `58-CONTEXT.md` D-58-11]

**Warning signs:** Static classifier has only a total count, lacks categories, or no explicit `unclassified_rows: 0`. [VERIFIED: `57-VALIDATION.md` accepted pattern]

### Pitfall 5: Silent Docs/Spec Divergence

**What goes wrong:** Current docs continue describing legacy nodes as active runtime nodes, or implementation diverges from `docs/contract-spec.md` without a recorded exception. [VERIFIED: `AGENTS.md`; `58-CONTEXT.md` D-58-08]

**Why it happens:** Historical planning docs and target-state docs are easy to confuse with implemented current state. [VERIFIED: `AGENTS.md`; `.planning/STATE.md`; `57-05-SUMMARY.md`]

**How to avoid:** Keep target contract, current implementation, and historical references separated; update `.planning/ARCHITECTURE-DEBT.md` when debt closes. [VERIFIED: `AGENTS.md`; `CLAUDE.md`]

**Warning signs:** Docs contain active-flow diagrams with `classify_intent`, `generate_recommendation`, or `assess_risk_and_approval` after Phase 58. [VERIFIED: docs scan patterns]

## Code Examples

Verified patterns and planning sketches:

### Final No-Debt Gate Shape

```python
# Source: local architecture-test pattern in tests/architecture/test_canonical_graph_baseline.py
def test_final_no_debt_gate_enforces_exact_canonical_graph() -> None:
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
    assert not legacy_route_hits()
    assert not active_runtime_vocabulary_alias_hits()
```

The concrete helper names should use existing `graph_baseline.py` helpers or new local helpers in the same architecture-test style. [VERIFIED: `tests/architecture/graph_baseline.py`; `tests/architecture/test_canonical_graph_baseline.py`]

### Static Legacy-Hit Classifier Requirements

```python
# Source: Phase 57 validation pattern and Phase 58 context requirement.
roots = [
    "README.md",
    "docs",
    "src",
    "tests",
    "frontend",
    "scripts",
    "eval",
    "rules",
    ".planning/ARCHITECTURE-DEBT.md",
    ".planning/ROADMAP.md",
    ".planning/REQUIREMENTS.md",
    ".planning/STATE.md",
]
exclude = {
    ".planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-VALIDATION.md",
}

# Assert every hit has a category and no hit belongs to active-runtime graph debt.
```

The classifier should report total hits, file count, category counts, active-runtime legacy hits, and unclassified rows. [VERIFIED: `58-CONTEXT.md` D-58-11; `57-VALIDATION.md`]

### Historical Approval Retry Boundary

```python
# Source: local approval-router pattern in src/api/routers/approvals.py
route = _canonical_retry_resume_route(stored_metadata_resume_route)
if route != "risk_gate":
    return None

# Only canonical route leaves the API boundary.
resume_payload.resume_route = "risk_gate"
```

Phase 58 may keep this pattern only as bounded historical data-read compatibility, not active graph vocabulary compatibility. [VERIFIED: `src/api/routers/approvals.py`; `58-CONTEXT.md` D-58-06]

## Recommended Plan Decomposition

| Plan | Ownership Boundary | Goal | Key Files | Focused Verification |
|------|--------------------|------|-----------|----------------------|
| 58-01 | Active graph and vocabulary final gate | Turn skipped final gate into active assertions; remove/reclassify active `compatibility_alias` rows from main graph vocabulary; decide `memory_write` non-main/lifecycle classification. [VERIFIED: `tests/architecture/test_canonical_graph_baseline.py`; `src/agent/graph_vocabulary.py`; `50-SPEC.md`] | `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `src/agent/graph_vocabulary.py`, `tests/agent/test_graph_vocabulary.py` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short` |
| 58-02 | Legacy wrapper/import-test deletion | Move shared implementation out of legacy modules, update tests/eval patch paths, delete or internalize old wrappers and router delegates. [VERIFIED: import scan; `src/agent/nodes/*`; `src/agent/routing.py`] | `src/agent/nodes/recommendation_generation.py`, `src/agent/nodes/risk_gate.py`, `src/agent/nodes/slot_resolution_gate.py`, legacy node modules, `src/agent/routing.py`, impacted tests | Canonical node and routing suites; exact files may change after test renames. |
| 58-03 | Trace/API/frontend/eval projection cleanup | Current-run trace/API/SSE/frontend/eval surfaces present canonical names; historical projection remains bounded and explicit. [VERIFIED: `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`; `scripts/eval_agent.py`; `eval/replay/dev-contract-manifest.v1.json`] | `src/agent/trace.py`, `src/repositories/trace_repo.py`, `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, frontend timeline, eval manifest/scripts, trace/API tests | Trace/API/eval tests plus `npm --prefix frontend run build`. |
| 58-04 | Approval retry historical read compatibility and security | Ensure old persisted retry metadata cannot authorize legacy graph resume; if mapping remains, it is data-read only and emits `risk_gate`. [VERIFIED: `src/api/routers/approvals.py`; `src/approvals/service.py`; `tests/test_approval_api.py`; `tests/test_graph_routing.py`] | `src/api/routers/approvals.py`, approval service tests, graph routing tests | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` |
| 58-05 | Docs/debt/final validation closeout | Remove current-doc active legacy wording, update architecture debt in Chinese, run static classifier with zero active legacy/unclassified, broad pytest/ruff/frontend/diff gates. [VERIFIED: `AGENTS.md`; `57-VALIDATION.md`; `58-CONTEXT.md`] | `docs/current-langgraph-architecture.md`, `docs/architecture-overview.md`, `README.md`, `docs/target-agent-platform-architecture-plan.md`, `.planning/ARCHITECTURE-DEBT.md`, validation artifact | Broad closeout suite, static classifier, ruff, frontend build, `git diff --check`. |

This split is prescriptive because Phase 58 spans several ownership boundaries and MOCA explicitly treats one oversized plan as a planning blocker. [VERIFIED: `AGENTS.md`; `58-CONTEXT.md`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Active graph used or preserved legacy names such as `classify_intent`, `extract_slots`, `generate_recommendation`, and `assess_risk_and_approval` during migration. | Active graph now registers canonical runtime nodes and old names remain only as compatibility wrappers/projection/test/doc debt. [VERIFIED: Phase 51-57 summaries; `src/agent/graph.py`; `57-VALIDATION.md`] | Phases 51-57, completed by 2026-07-07. [VERIFIED: `.planning/STATE.md`; `57-05-SUMMARY.md`] | Phase 58 should delete scaffolding rather than re-cut runtime routes. |
| Graph vocabulary used `compatibility_alias` rows to bridge migration. | CAGM-09 requires active runtime aliases removed or internalized, with historical readability separated. [VERIFIED: `50-SPEC.md`; `.planning/REQUIREMENTS.md`; `58-CONTEXT.md`] | Phase 58. [VERIFIED: `.planning/ROADMAP.md`] | Planner must make `graph_vocabulary.py` no-debt final state explicit. |
| Approval retry compatibility accepted old persisted risk route names as migration support. | Current trusted edit resume emits `risk_gate`; any old-row compatibility must be bounded data-read only. [VERIFIED: `src/api/routers/approvals.py`; `src/approvals/service.py`; `57-VALIDATION.md`] | Phase 57 set current authority; Phase 58 closes residual debt. [VERIFIED: `57-05-SUMMARY.md`; `58-CONTEXT.md`] | Security tests must prove no legacy route leaves API/backend boundary. |

**Deprecated/outdated:**

- `compatibility_alias` as active main graph vocabulary for legacy node names is outdated for Phase 58 and should not survive as current runtime contract. [VERIFIED: `50-SPEC.md`; `58-CONTEXT.md`]
- Direct tests/fakes importing `generate_recommendation` or `assess_risk_and_approval` as current node surfaces are outdated after canonical cutover; they should be rewritten to canonical modules or removed. [VERIFIED: import scan; `src/agent/nodes/recommendation_generation.py`; `src/agent/nodes/risk_gate.py`]
- Current docs/timeline/eval rows that preserve old node names for current-run behavior are outdated; historical-only references may remain if labeled and tested as such. [VERIFIED: `58-CONTEXT.md`; static scan]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Production/live databases may contain historical legacy node names, but were not directly queried during research. | Runtime State Inventory | If production contains unexpected forms, historical projection tests may miss a read case; planner can add optional sampled DB audit if environment is available. |
| A2 | No production-only live service config or OS-registered state embeds graph node names. | Runtime State Inventory | If dashboards/workflows/process managers key off old node names, release docs may need an external config update task. |
| A3 | `memory_write` in graph vocabulary is a non-main/lifecycle concept rather than an active main-chain registered node. | Current Evidence Inventory / Plan 58-01 | If it is treated as active runtime vocabulary, final no-debt gate may conflict with Phase 50's excluded-node list; planner must inspect and decide explicitly. |

## Open Questions

1. **Should Phase 58 include a production/sample DB audit for historical node-name counts?**
   - What we know: schema fields can store old names, and the locked decision forbids bulk rewrite. [VERIFIED: `src/db/models.py`; `58-CONTEXT.md`]
   - What's unclear: this research did not connect to production/live DB rows. [VERIFIED: environment audit]
   - Recommendation: do not block code planning on this; add an optional manual verification note if release requires production inventory. [ASSUMED]

2. **How should `memory_write` be represented in `graph_vocabulary.py` after the final gate?**
   - What we know: Phase 50 excludes `memory_write` from current main-chain registered graph nodes, while `graph_vocabulary.py` currently includes it with runtime status. [VERIFIED: `50-SPEC.md`; `src/agent/graph_vocabulary.py`]
   - What's unclear: whether current vocabulary status means "main graph runtime" or broader lifecycle/internal vocabulary. [VERIFIED: local code review]
   - Recommendation: Plan 58-01 must explicitly classify it as non-main/internal if retained, or remove it from main graph vocabulary. [VERIFIED: `50-SPEC.md` final gate intent]

3. **What exact UI behavior is desired for old historical rows?**
   - What we know: current-run surfaces should show canonical names and old rows may remain readable. [VERIFIED: `58-CONTEXT.md` D-58-03/D-58-07]
   - What's unclear: whether the UI should display the old raw implementation name anywhere in expanded details, or only canonical target labels. [ASSUMED]
   - Recommendation: preserve raw `implementation_node` in backend payloads where already available, but render canonical current labels by default. [VERIFIED: `src/agent/graph_vocabulary.py`; `src/api/routers/agent_runs.py`; `frontend/src/components/timeline/TimelineStep.tsx`]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Approved Python test/lint/static classifier entrypoint | yes | 0.11.2 | None needed. [VERIFIED: `uv --version`] |
| Python project environment | Backend tests and static classifiers | yes via `uv run` | Project requires >=3.12 | Use `.venv/bin/...` only after confirming repo venv. [VERIFIED: `pyproject.toml`; `AGENTS.md`] |
| `pytest` | Test framework | yes | 9.0.3 | None. [VERIFIED: local package metadata] |
| `pytest-asyncio` | Async tests | yes | 1.3.0 | None. [VERIFIED: local package metadata] |
| `ruff` | Lint gate | yes | 0.15.12 | None. [VERIFIED: local package metadata] |
| Node.js | Frontend build/test | yes | v25.9.0 | None. [VERIFIED: `node --version`] |
| npm | Frontend scripts | yes | 11.12.1 | None. [VERIFIED: `npm --version`] |
| Docker | Optional service/container validation | yes | 29.4.2 server | Not required for source-only Phase 58 validation. [VERIFIED: `docker info`] |
| `pg_isready` | Optional direct Postgres health check | no | command not found | Use repository tests/mocks or Docker/SQLAlchemy config if DB validation is added. [VERIFIED: `command -v pg_isready`] |
| Graphify knowledge graph | Optional semantic codebase query | no | disabled | Continue with direct `rg`, source reads, and tests. [VERIFIED: `node /Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs graphify status`] |

**Missing dependencies with no fallback:**

- None for planned source/test/doc research. [VERIFIED: environment audit]

**Missing dependencies with fallback:**

- `pg_isready` is missing; it only matters if a plan adds direct Postgres service validation. [VERIFIED: environment audit]
- GSD graphify is disabled; direct code/source scans were used instead. [VERIFIED: graphify status]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0; frontend build through npm/Vite. [VERIFIED: local package metadata; `frontend/package.json`] |
| Config file | `pyproject.toml`; frontend scripts in `frontend/package.json`. [VERIFIED: files] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short` [VERIFIED: command run during research, currently `13 passed, 1 skipped` plus `58 passed` when split] |
| Full suite command | See Phase gate commands below; use approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` and `npm --prefix frontend run build`. [VERIFIED: `AGENTS.md`; `57-VALIDATION.md`] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-09 | Active graph registered nodes equal final 15 canonical names exactly. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | yes; skipped final gate must be activated. [VERIFIED: `tests/architecture/test_canonical_graph_baseline.py`] |
| CAGM-09 | Active route values do not target legacy graph nodes or old route helper destinations. | architecture/static/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py -q --tb=short` | yes. [VERIFIED: files] |
| CAGM-09 | Main graph vocabulary has no active runtime compatibility aliases for legacy node names. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | yes; expectations must be updated. [VERIFIED: `tests/agent/test_graph_vocabulary.py`] |
| CAGM-09 | Current-run trace/API/SSE/frontend/eval surfaces present canonical names while old stored rows remain readable only through bounded historical projection. | API/integration/static/frontend build | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py -q --tb=short` and `npm --prefix frontend run build` | yes for listed backend/eval tests; frontend build script exists. [VERIFIED: files; `frontend/package.json`] |
| CAGM-09 | Historical approval retry metadata cannot authorize legacy graph resume and emits canonical `risk_gate` only. | API/security/routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` | yes. [VERIFIED: files] |
| CAGM-09 | Legacy wrapper modules/import tests are deleted or rewritten to canonical modules. | unit/import/static | Run canonical node suites after renames; example: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_phase22_action_boundary.py -q --tb=short` until files are renamed, then update commands to canonical paths. | yes today, but some file names are deletion candidates. [VERIFIED: static scan] |
| CAGM-09 | Docs and architecture debt no longer describe legacy names as active current runtime nodes; static classifier has zero active-runtime legacy hits and zero unclassified rows. | docs/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python <phase58_static_classifier>` plus `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` | classifier to create in plan; docs exist. [VERIFIED: `57-VALIDATION.md`; `58-CONTEXT.md`] |

### Sampling Rate

- **Per task commit:** Run the focused command for the changed boundary, always through `UV_CACHE_DIR=/tmp/uv-cache uv run ...` or `npm --prefix frontend ...`. [VERIFIED: `AGENTS.md`]
- **Per wave merge:** Run graph baseline + graph vocabulary + impacted API/node suites. [VERIFIED: `57-VALIDATION.md` pattern]
- **Phase gate:** Run broad suite, ruff, frontend build, static classifier, and diff check before `/gsd-verify-work`. [VERIFIED: `58-CONTEXT.md` D-58-12]

### Recommended Focused Commands

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_memory_context_load.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_risk_gate.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short
npm --prefix frontend run build
```

Some test filenames are themselves deletion/rename candidates, so each plan must update validation commands after test migration. [VERIFIED: static scan]

### Recommended Phase Gate Commands

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/architecture/test_canonical_graph_baseline.py \
  tests/architecture/test_phase32_static_contract.py \
  tests/architecture/test_memory_contract_delta.py \
  tests/architecture/test_phase33_rag_claim_boundaries.py \
  tests/architecture/test_phase34_approval_action_boundaries.py \
  tests/architecture/test_approval_boundaries.py \
  tests/agent/test_graph.py \
  tests/test_graph_routing.py \
  tests/agent/test_graph_vocabulary.py \
  tests/agent/test_trace.py \
  tests/test_trace_api.py \
  tests/test_agent_runs_api.py \
  tests/test_approval_api.py \
  tests/test_approval_gate.py \
  tests/approvals/test_needs_info_resume.py \
  tests/approvals/test_service_transitions.py \
  tests/agent/test_nodes/test_contextual_intent_resolve.py \
  tests/agent/test_nodes/test_slot_resolution_gate.py \
  tests/agent/test_memory_context_load.py \
  tests/agent/test_nodes/test_risk_gate.py \
  tests/agent/test_phase22_action_boundary.py \
  tests/actions/test_phase34_action_draft_bindings.py \
  tests/eval/test_phase35_replay_eval_gates.py \
  tests/eval/test_phase35_release_monitoring_manifests.py \
  -q --tb=short

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check \
  src/agent src/api src/approvals src/repositories \
  tests/architecture tests/agent tests/test_graph_routing.py \
  tests/test_agent_runs_api.py tests/test_trace_api.py tests/test_approval_api.py tests/test_approval_gate.py

npm --prefix frontend run build
UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check
```

The final suite should be adjusted to include renamed canonical test files after wrapper deletion. [VERIFIED: current static scan and existing file names]

### Static Legacy-Hit Classifier Requirements

The final classifier should scan at least these old names: `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, `assess_risk_and_approval`, `route_after_intent`, and `route_after_slots`. [VERIFIED: `50-SPEC.md`; `src/agent/graph_vocabulary.py`; `src/agent/routing.py`]

Required outputs:

- total hits and files scanned. [VERIFIED: `58-CONTEXT.md` D-58-11]
- category counts by ownership boundary. [VERIFIED: `57-VALIDATION.md` pattern]
- zero active-runtime legacy hits. [VERIFIED: `50-SPEC.md` final no-debt gate]
- zero unclassified rows. [VERIFIED: `58-CONTEXT.md` D-58-11]
- explicit excluded generated artifacts to avoid recursive self-counting. [VERIFIED: `57-VALIDATION.md`]

### Wave 0 Gaps

- [ ] Convert `tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope` from skip to active final no-debt assertions. [VERIFIED: `tests/architecture/test_canonical_graph_baseline.py`]
- [ ] Add or update a Phase 58 static legacy-hit classifier so final validation can report categories and zero active/unclassified hits. [VERIFIED: `58-CONTEXT.md` D-58-11]
- [ ] Rename/rewrite test files whose filenames encode deleted legacy node names if wrappers are removed. [VERIFIED: static scan]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no new auth mechanism | Keep existing API authentication/tenant boundaries; Phase 58 should not add auth flows. [VERIFIED: phase scope; `58-CONTEXT.md`] |
| V3 Session Management | no new session mechanism | Do not change session management; graph session context cleanup stays inside existing backend tests. [VERIFIED: phase scope] |
| V4 Access Control | yes | Approval resume must be server-authorized and canonical `risk_gate` only. [VERIFIED: `src/api/routers/approvals.py`; `57-VALIDATION.md`] |
| V5 Input Validation | yes | Treat route/node names from stored metadata or API payloads as untrusted unless produced by server-side canonical routing/projection. [VERIFIED: `src/api/routers/approvals.py`; `src/agent/graph.py`] |
| V6 Cryptography | yes indirectly | Preserve existing approval payload hash/snapshot/hash validation; do not hand-roll new hashing. [VERIFIED: `src/api/routers/approvals.py`; `57-VALIDATION.md`] |
| V10 Malicious Code | yes for eval/test patch paths | Ensure eval/test monkeypatches move to canonical modules and do not keep deleted legacy import paths alive. [VERIFIED: `scripts/eval_agent.py`; static import scan] |

### Known Threat Patterns for Phase 58

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Route spoofing through legacy `assess_risk_and_approval` route value | Spoofing / Elevation of privilege | Canonical router allowlists only; `route_after_approval` and `_should_resume_graph` must reject legacy route values and emit `risk_gate` only. [VERIFIED: `src/agent/graph.py`; `src/api/routers/approvals.py`; `tests/test_graph_routing.py`] |
| Stale historical replay presented as current runtime behavior | Repudiation / Tampering | Preserve raw implementation node for audit where needed, but current-run projection and labels use canonical names; historical path is labeled separately. [VERIFIED: `src/agent/trace.py`; `src/repositories/trace_repo.py`; `src/api/routers/traces.py`; `58-CONTEXT.md`] |
| Approval resume authority from old persisted metadata | Elevation of privilege / Tampering | Only server-side historical read compatibility after approval/run/hash/snapshot/version validation; never accept legacy route as graph authority. [VERIFIED: `src/api/routers/approvals.py`; `57-VALIDATION.md`] |
| Silent docs/spec divergence | Repudiation | Update current docs/debt/spec exceptions; distinguish target contract, implemented current state, and historical references. [VERIFIED: `AGENTS.md`; `58-CONTEXT.md` D-58-08] |
| Import-path resurrection of deleted legacy wrappers | Tampering / Maintainability risk | Static scan for source/test/eval imports; tests patch canonical modules after migration. [VERIFIED: import scan; `scripts/eval_agent.py`] |
| Bulk historical data rewrite damaging audit trail | Tampering / Repudiation | No data migration; use bounded read projection. [VERIFIED: `58-CONTEXT.md` D-58-03] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-CONTEXT.md` - user decisions, scope, validation strategy, candidate count.
- `.planning/REQUIREMENTS.md` - CAGM-09 requirement text and pending status.
- `.planning/ROADMAP.md` - Phase 58 goal, dependency, success criteria, roadmap status.
- `.planning/STATE.md` - Phase 57 handoff and Phase 58 current focus.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - final 15-node set, excluded nodes, final no-debt gate.
- `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md` and `57-05-SUMMARY.md` - previous phase validation, legacy-hit pattern, Phase 58 readiness.
- `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` - active graph AST helpers and current skipped final gate.
- `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/graph_vocabulary.py` - active graph, routes, vocabulary/projection.
- `src/agent/nodes/*` canonical and legacy wrapper modules reviewed during research.
- `src/api/routers/approvals.py`, `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/db/models.py` - API, stored state, projection, approval resume surfaces.
- `frontend/src/components/timeline/TimelineStep.tsx`, `scripts/eval_agent.py`, `eval/replay/dev-contract-manifest.v1.json` - frontend/eval candidate surfaces.
- `AGENTS.md` and `CLAUDE.md` - MOCA-specific workflow, validation, plan granularity, debt ledger, and spec divergence rules.

### Primary Commands (HIGH confidence)

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` - current baseline `13 passed, 1 skipped`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` - current vocabulary suite `58 passed`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python ... graph_add_node_names()/graph_router_route_values()` - active graph matches target and has no legacy route hits.
- `git grep -n "DELETE_BY_PHASE_58" -- README.md docs src tests frontend scripts eval rules .planning/ARCHITECTURE-DEBT.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md` - 40 current deletion-marker hits classified by boundary.
- Environment probes: `uv --version`, `node --version`, `npm --version`, `docker info`, `command -v pg_isready`, graphify status.

### Secondary (MEDIUM confidence)

- None required. Phase 58 research is repository-specific; no external framework behavior change is planned. [VERIFIED: phase scope and no new dependencies]

### Tertiary (LOW confidence)

- Production/live DB and external service state were not connected during research; related statements are explicitly listed in the Assumptions Log. [ASSUMED]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - verified from local package metadata, project files, and existing validation artifacts.
- Architecture: HIGH - verified from source files, tests, Phase 50 spec, Phase 57 validation, and Phase 58 context.
- Cleanup inventory: HIGH for tracked repo candidates; MEDIUM for production runtime-state inventory because live DB/external services were not queried.
- Pitfalls/security: HIGH for approval route, historical projection, and docs divergence risks because they are grounded in local code and phase artifacts.

**Research date:** 2026-07-08
**Valid until:** 2026-08-07 for local architecture patterns; rerun candidate scans immediately before planning/execution because Phase 58 cleanup targets are fast-moving.
