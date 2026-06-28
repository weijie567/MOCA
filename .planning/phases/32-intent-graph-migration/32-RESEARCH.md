# Phase 32: Intent Graph Migration - Research

**Researched:** 2026-06-28  
**Domain:** Agent graph canonical vocabulary, intent/slot policy boundaries, trace/eval/API projection, merchant-context evidence  
**Confidence:** HIGH  

<user_constraints>
## User Constraints (from CONTEXT.md)

**Source for this entire section:** copied from `.planning/phases/32-intent-graph-migration/32-CONTEXT.md`. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

### Locked Decisions

#### Graph Vocabulary And Compatibility

- **D-01:** Use a compatibility-first canonical migration: add target canonical mapping/projection and explicit wrappers where needed, while preserving current runtime behavior until tests prove each route.
  - Current `src/agent/graph.py` still registers `classify_intent`, `session_memory_load`, `long_term_memory_retrieve`, `generate_recommendation`, and `assess_risk_and_approval`.
  - Phase 31 already made `session_memory_load` a wrapper over `session_context_load` and `long_term_memory_retrieve` a wrapper over `reviewed_memory_context_retrieve`; Phase 32 should extend that pattern rather than doing a mechanical rename of every call site.
- **D-02:** Target graph names must be real contract/eval names, not only comments.
  - Trace/eval/API projections should be able to map `classify_intent` / `intent_classification` to `contextual_intent_resolve`, `session_memory_load` to `session_context_load`, `long_term_memory_retrieve` to `memory_context_load`, `route_after_intent` to `route_after_contextual_intent`, and `route_after_slots` to `route_after_slot_resolution`.
  - Legacy implementation names may remain visible for debugging, but target canonical names must be available for contract/eval assertions.
- **D-03:** Do not claim Phase 33 nodes are fully implemented in Phase 32.
  - `rag_context_build` and `claim_verify` can appear as target canonical aliases/projection placeholders or route-map entries only where clearly marked as deferred target nodes.
  - Any placeholder must fail closed or be explicitly non-runnable until Phase 33 implements the actual verified evidence and claim verification contracts.
- **D-04:** Plan granularity must split this phase. A single broad `32-01-PLAN.md` covering aliases, registries, routing, trace/eval, merchant context, and validation would be too large.
  - Recommended plan units: graph vocabulary/projection; intent policy registry integration; slot policy gate/router migration; trace/eval/AgentRun merchant-context evidence; final focused verification.

#### Intent Policy Ownership

- **D-05:** `IntentPolicyRegistry` owns effective intent/route policy. LLM structured output remains candidate-only.
  - Existing code already has `IntentPolicyRegistry`, `IntentDefinition`, `INTENT_ROUTE_POLICY`, precedence, evidence-required, direct-response, high-risk, and risk-tier helpers in `src/agent/intent_policy.py`.
  - Phase 32 should move effective decision consumers toward the registry interface instead of directly spreading constants across `classify_intent`, `routing`, and tests.
- **D-06:** `contextual_intent_resolve` semantics should include deterministic pre-route, same-thread context handling, precedence normalization, confidence gates, risk tier resolution, and effective route decision.
  - Existing `classify_intent` already performs `detect_pre_route`, deterministic active-flow handling, short-reply guards, precedence overrides, risk tier resolution, and `classification_trace`.
  - Phase 32 should make that trace read as candidate -> policy override -> effective classification, not as LLM-owned routing.
- **D-07:** Approval-like chat and safety-sensitive ordinary-chat inputs remain fail-closed before any action/approval authority is accepted from chat text.
  - `approval_chat_not_trusted`, `safety_sensitive`, `multi_target_request`, low confidence, and ambiguous short replies must remain routed to clarification/refusal paths.
  - Do not let a target rename weaken Phase 25 safety behavior.

#### Slot Policy Resolution

- **D-08:** `SlotPolicyRegistry` owns required-slot policy and slot inheritance decisions. Current-turn explicit slots override inherited session slots; inherited slots are accepted only when freshness, scope, and intent compatibility pass.
  - Existing `route_after_slots`, `missing_required_slots`, and `resolve_slots_with_metadata` already implement much of this, but they read `REQUIRED_SLOT_POLICY` directly.
  - Phase 32 should expose a target `slot_resolution_gate` semantic boundary and make tests assert registry-owned required slot policy.
- **D-09:** Uncertain slot inheritance must clarify, not guess.
  - Missing, stale, wrong-thread, incompatible, invalidated, or scope-unsafe slots route to `clarification_gate`.
  - `policy_qa` and other no-slot direct investigation paths must not accidentally consume stale active business identifiers.
- **D-10:** `route_after_slot_resolution` should be deterministic and total. Tests must include safety pre-route, low confidence, direct response, slot required, missing slot, stale/incompatible inherited slot, trusted memory context path, and direct investigate path.

#### Trace, Eval, And Merchant Context Evidence

- **D-11:** Trace/eval projections should preserve debugging compatibility while making target canonical graph vocabulary assertable.
  - `trace_steps[].node` may keep implementation node names where existing APIs depend on them, but there should be a safe target-name projection, alias map, or summary field that contract/eval tests can consume.
  - `AgentStep.node_name`, `build_trace_summary`, SSE node messages, and eval/golden projection surfaces should be reviewed for this alias requirement.
- **D-12:** Router totality tests must cover target names and legacy edge keys together.
  - Existing `tests/agent/test_graph.py` pins legacy router edge keys. Phase 32 should add target router mapping assertions without breaking current graph compilation.
- **D-13:** AgentRun and graph routing must record target merchant context as one of: resolved, deferred, unavailable, or not_applicable.
  - This evidence can live in graph state, trace metrics, route decision metadata, or AgentRun/run-detail projection according to planning, but it must be deterministic and safe.
  - Manager/supervisor-style access must not remain implicitly tenant-wide. Until same-merchant proof is available, business run details stay owner/admin-only.
- **D-14:** Phase 32 should not broaden authorization semantics.
  - Merchant-bound `support`, `manager`, and legacy `merchant` roles stay merchant-scoped. `admin` remains the only platform-wide business-data role. Tenant public policy remains separate.

#### Verification Strategy

- **D-15:** Start from RED tests that pin canonical alias/projection semantics before implementation.
  - Tests should prove legacy graph names map to target canonical names in trace/eval projections, and that aliasing does not create different semantics.
- **D-16:** Add registry-focused tests proving `IntentPolicyRegistry` and `SlotPolicyRegistry` are the consumed policy surface for effective route and slot decisions.
- **D-17:** Add route totality and graph compilation tests for both legacy runtime edge keys and target canonical route names.
- **D-18:** Add AgentRun/trace tests proving target merchant context evidence is recorded safely and manager/supervisor-style visibility is not tenant-wide without target merchant/business fact proof.
- **D-19:** Use MOCA's required test entrypoint: `uv run pytest ...` or `.venv/bin/pytest ...`; never use bare `pytest`.

### Claude's Discretion

- Exact file names are left to planning. Likely targets include `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/intent_policy.py`, `src/agent/nodes/classify_intent.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, and targeted tests under `tests/agent/`, `tests/api/`, and `tests/architecture/`.
- Exact representation of the alias map is left to planning. Prefer a small typed registry/helper over ad hoc per-test string maps.
- Exact merchant-context evidence schema is left to planning, but it must not expose forbidden business identifiers or imply access to out-of-scope runs.

### Deferred Ideas (OUT OF SCOPE)

- Full `rag_context_build`, `VerifiedEvidencePackageV1`, `route_after_rag_context`, and claim verifier implementation belong to Phase 33.
- Approval/action payload binding to business fact refs, verified evidence refs, claim verification refs, risk decisions, and safety snapshots belongs to Phase 34.
- Full replay/eval hardening for platform decisions, including broad run visibility gates, belongs to Phase 35.
- DB constraints, RLS hardening, broad role enum cleanup, and merchant-specific policy schema belong to Phase 36+ / future hardening.
- Physical microservice extraction remains future scope after modular monolith boundaries are stable.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-11 | The graph can map legacy nodes/routers to target canonical vocabulary for `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `rag_context_build`, and `claim_verify`. [VERIFIED: .planning/REQUIREMENTS.md] | Use a typed graph vocabulary helper and projection tests that map legacy runtime names to target canonical names while preserving `trace_steps[].node` and existing edge keys. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; src/agent/graph.py; src/agent/trace.py] |
| APF-12 | Intent and slot policy registries drive contextual intent resolution and slot inheritance decisions, with LLM output limited to candidates and deterministic policy owning effective route/slot decisions. [VERIFIED: .planning/REQUIREMENTS.md] | Move routing/classification/slot-resolution consumers to `IntentPolicyRegistry` and `SlotPolicyRegistry`, then add tests that prove LLM-required slots and LLM route hints cannot override deterministic policy. [VERIFIED: src/agent/intent_policy.py; src/agent/routing.py; src/agent/nodes/classify_intent.py; tests/agent/test_required_slots.py] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Local debug/startup/API/UI/RAG/agent/memory/tool-call failures discovered during validation must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese after handling. [VERIFIED: CLAUDE.md; AGENTS.md]
- Phase-level plans and larger changes require GSD-native review followed by independent cross-check against real repo code/docs/tests. [VERIFIED: CLAUDE.md; AGENTS.md]
- Phase-level planning must split broad service-boundary or platform-foundation work into multiple small plans when it crosses service boundaries, ownership domains, waves, or verification gates. [VERIFIED: AGENTS.md]
- Phase 32 must not be planned as a single large `32-01-PLAN.md` that covers aliases, registries, routing, trace/eval, merchant context, and validation together. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; AGENTS.md]
- MOCA validation commands must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or the repo `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` results are invalid. [VERIFIED: AGENTS.md]
- `docs/contract-spec.md` is the normative contract source for contract semantics, but target-state text is not proof of current implementation and MVP deviations must be recorded rather than silent. [VERIFIED: CLAUDE.md; AGENTS.md]

## Summary

Phase 32 should be planned as a compatibility-first migration that adds canonical target graph vocabulary and policy-boundary enforcement without renaming existing runtime graph nodes wholesale. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; src/agent/graph.py] The current graph still registers legacy node keys such as `classify_intent`, `session_memory_load`, and `long_term_memory_retrieve`, while the target contract expects names such as `contextual_intent_resolve`, `session_context_load`, and `memory_context_load`. [VERIFIED: src/agent/graph.py; docs/contract-spec.md §9; docs/target-agent-platform-architecture-plan.md §6]

The safest plan is to add one typed graph vocabulary/projection helper first, then move intent and slot decisions behind consumed registry methods, then expose merchant-context evidence in graph/trace/API projections without broadening AgentRun visibility. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; src/agent/intent_policy.py; src/agent/routing.py; src/api/routers/agent_runs.py] Phase 33 names `rag_context_build` and `claim_verify` may be projected or cataloged as deferred/non-runnable target nodes, but Phase 32 must not introduce a fake successful RAG or claim-verification path. [VERIFIED: .planning/REQUIREMENTS.md; .planning/ROADMAP.md; docs/contract-spec.md §9; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

**Primary recommendation:** split Phase 32 into five plans: graph vocabulary/projection, intent registry consumption, slot policy gate/router migration, trace/eval/API merchant-context evidence, and final focused verification. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; AGENTS.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Canonical graph vocabulary and legacy alias projection | API / Backend | Observability/replay projection | Graph nodes and trace helpers own runtime and trace naming; API surfaces should project target names without changing persisted legacy step names. [VERIFIED: src/agent/graph.py; src/agent/trace.py; src/api/routers/agent_runs.py; src/api/routers/traces.py] |
| Contextual intent resolution | API / Backend | LLM adapter | `classify_intent` currently combines LLM candidate output with deterministic pre-route, precedence, risk, required-slot, and route logic; Phase 32 should make policy registry the effective decision source. [VERIFIED: src/agent/nodes/classify_intent.py; src/agent/intent_policy.py] |
| Slot resolution gate | API / Backend | MemoryContextService | `extract_slots` and `routing.resolve_slots_with_metadata` currently merge current-turn slots with trusted session memory metadata, while session context loading remains graph/service-owned. [VERIFIED: src/agent/nodes/extract_slots.py; src/agent/routing.py; src/agent/nodes/session_context_load.py] |
| Session and memory context loading aliases | API / Backend | MemoryContextService | Legacy wrappers already delegate `session_memory_load` to `session_context_load` and `long_term_memory_retrieve` to reviewed memory context retrieval. [VERIFIED: src/agent/nodes/session_memory_load.py; src/agent/nodes/session_context_load.py; src/agent/nodes/long_term_memory_retrieve.py; src/agent/nodes/reviewed_memory_context_retrieve.py] |
| Target merchant context evidence | API / Backend | Database / trace storage | AgentRun creation/streaming and trace persistence are API/backend surfaces; existing authorization remains owner/admin-only until target merchant proof exists. [VERIFIED: src/api/routers/agent_runs.py; src/api/routers/traces.py; .planning/todos/deferred/2026-06-27-merchant-scope-agentrun-replay.md] |
| RAG context and claim verification target names | API / Backend | KnowledgeService, future verifier | The target contract names exist, but APF-13/APF-14 and Phase 33 own actual RAG context build and claim verification behavior. [VERIFIED: .planning/REQUIREMENTS.md; .planning/ROADMAP.md; docs/contract-spec.md §9] |

## Implementation Map

| File / Symbol | Current Behavior | Phase 32 Planning Implication |
|---------------|------------------|-------------------------------|
| `src/agent/graph.py::build_graph` | Registers legacy runtime node keys including `classify_intent`, `session_memory_load`, `long_term_memory_retrieve`, `generate_recommendation`, and `assess_risk_and_approval`; conditional edge maps use legacy route keys from `route_after_intent` and `route_after_slots`. [VERIFIED: src/agent/graph.py] | Do not mechanically rename graph nodes in the first plan; add canonical projection tests and only introduce explicit target wrappers where compatibility is proven. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `src/agent/routing.py::route_after_intent` | Wraps `_route_after_intent`, validates finite keys, and returns legacy keys such as `session_memory_load`, `investigate`, `final_response`, or `clarification_gate`. [VERIFIED: src/agent/routing.py] | Keep legacy edge keys for LangGraph compilation, but expose target router projection `route_after_contextual_intent`. [VERIFIED: docs/contract-spec.md §9; tests/agent/test_graph.py] |
| `src/agent/routing.py::_route_after_intent` | Uses direct-response, confidence, approval-chat, unknown-intent, required-slot, and operation checks to choose route. [VERIFIED: src/agent/routing.py] | Move effective route decisions behind `IntentPolicyRegistry` methods so tests prove registry ownership rather than constant spreading. [VERIFIED: src/agent/intent_policy.py; .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `src/agent/routing.py::route_after_slots` | Wraps `_route_after_slots`, validates finite keys, and returns legacy keys `clarification_gate`, `investigate`, or `long_term_memory_retrieve`. [VERIFIED: src/agent/routing.py] | Preserve legacy edge keys but map this router to target `route_after_slot_resolution`. [VERIFIED: docs/contract-spec.md §9; .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `src/agent/routing.py::resolve_slots_with_metadata` | Current-turn `extracted_slots` override inherited slots, and inherited slots require trusted-session source plus tenant/user/thread/freshness/intent compatibility checks. [VERIFIED: src/agent/routing.py] | Lift this behavior into a registry-consumed slot gate boundary instead of duplicating it in a new graph node. [VERIFIED: tests/agent/test_required_slots.py; tests/agent/test_session_memory_integration.py] |
| `src/agent/intent_policy.py::IntentPolicyRegistry` | Exposes read-only views of definitions, route policy, precedence order, and direct/evidence/high-risk/critical sets. [VERIFIED: src/agent/intent_policy.py] | Extend it into the consumed policy boundary for pre-route, precedence, confidence, risk tier, required slots, and initial route. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `src/agent/intent_policy.py::SlotPolicyRegistry` | Exposes read-only required-slot policy and required slots per intent. [VERIFIED: src/agent/intent_policy.py] | Add consumed methods for required slots and slot resolution outcomes, then make `routing` and `extract_slots` call registry APIs. [VERIFIED: src/agent/routing.py; src/agent/nodes/extract_slots.py] |
| `src/agent/nodes/classify_intent.py::intent_result_to_state` | Converts `IntentResultV3` candidate output into effective state by applying deterministic pre-route, precedence, risk tier, policy required slots, and `route_after_intent`. [VERIFIED: src/agent/nodes/classify_intent.py] | Treat this as the implementation surface for target `contextual_intent_resolve`; mirror target trace/projection fields while preserving legacy `classify_intent` behavior. [VERIFIED: docs/contract-spec.md §9; docs/contract-spec.md §10] |
| `src/agent/nodes/classify_intent.py::classify_intent` | Appends trace step node `classify_intent` and writes `llm_outputs.intent_classification`; fallback paths stay fail-closed. [VERIFIED: src/agent/nodes/classify_intent.py] | Do not change `trace_steps[].node` first; add target projection such as `target_node` or trace summary fields and preserve fallback safety tests. [VERIFIED: tests/agent/test_nodes/test_classify_intent.py] |
| `src/agent/nodes/extract_slots.py::extract_slots` | Extracts candidate slots, calls `resolve_slots_with_metadata`, and appends trace step node `extract_slots`. [VERIFIED: src/agent/nodes/extract_slots.py] | Expose target `slot_resolution_gate` semantics either as a deterministic helper/projection or a new explicit node only after RED tests prove no double-merge regression. [VERIFIED: src/agent/routing.py; docs/target-agent-platform-architecture-plan.md §6] |
| `src/agent/nodes/session_memory_load.py::session_memory_load` | Delegates to `session_context_load` with `node_name="session_memory_load"`. [VERIFIED: src/agent/nodes/session_memory_load.py] | Existing wrapper pattern is the model for compatibility-first graph migration. [VERIFIED: .planning/phases/31-memory-platform-boundary/31-RESEARCH.md; src/agent/nodes/session_memory_load.py] |
| `src/agent/nodes/session_context_load.py::session_context_load` | Calls `MemoryContextService.load_session_context_for_intent`, returns target `session_context`/`session_context_bundle` plus legacy `session_memory` aliases, and filters cross-merchant inherited context. [VERIFIED: src/agent/nodes/session_context_load.py] | Map legacy graph key `session_memory_load` to target `session_context_load` without changing current loading semantics. [VERIFIED: tests/agent/test_session_memory_load.py] |
| `src/agent/nodes/long_term_memory_retrieve.py::long_term_memory_retrieve` | Delegates to `reviewed_memory_context_retrieve` and adds legacy `llm_outputs.long_term_memory_retrieve` metrics. [VERIFIED: src/agent/nodes/long_term_memory_retrieve.py] | Map legacy graph key `long_term_memory_retrieve` to target `memory_context_load` while preserving reviewed memory fail-closed boundaries. [VERIFIED: src/agent/nodes/reviewed_memory_context_retrieve.py; tests/agent/test_reviewed_memory_context_retrieve.py] |
| `src/agent/nodes/reviewed_memory_context_retrieve.py::reviewed_memory_context_retrieve` | Loads reviewed memory context through `MemoryContextService`, fails closed without trusted context/merchant scope, and does not use session memory or candidate slots to create scope. [VERIFIED: src/agent/nodes/reviewed_memory_context_retrieve.py; tests/agent/test_reviewed_memory_context_retrieve.py] | Merchant-context evidence must not promote memory context into business authority or access proof. [VERIFIED: tests/agent/test_memory_evidence_boundary.py] |
| `src/agent/nodes/receive_request.py::receive_request` | Resets per-turn state including session/memory/RAG verifier fields. [VERIFIED: src/agent/nodes/receive_request.py; tests/agent/test_nodes/test_receive_request.py] | Add any Phase 32 target vocabulary or target merchant context fields to the reset inventory and test them. [VERIFIED: tests/agent/test_nodes/test_receive_request.py] |
| `src/agent/state.py::AgentState` | Declares optional typed state fields for identity, intent, slots, session/memory context, RAG verifier fields, approval/action, and trace steps. [VERIFIED: src/agent/state.py] | Add typed fields only if multiple nodes/API surfaces need to consume the same target projection; otherwise keep projection local to trace/API helpers. [VERIFIED: src/agent/state.py; src/agent/trace.py] |
| `src/agent/trace.py::write_agent_steps` | Persists `AgentStep.node_name` from `step["node"]` exactly. [VERIFIED: src/agent/trace.py; src/db/models.py] | Do not rewrite persisted implementation names for Phase 32; add canonical name into metrics/projection if persistence is needed. [VERIFIED: tests/agent/test_trace.py; tests/test_trace_api.py] |
| `src/agent/trace.py::build_trace_summary` | Builds `nodes_executed` from raw `trace_steps[].node` and currently has no canonical target projection field. [VERIFIED: src/agent/trace.py; tests/agent/test_graph.py] | Add `target_nodes_executed` or equivalent without removing `nodes_executed`; update exact-shape tests intentionally. [VERIFIED: tests/agent/test_graph.py] |
| `src/api/routers/agent_runs.py::NODE_MESSAGES` and streaming helpers | SSE lifecycle events use legacy node names and message lookup; `_extract_step_payload` contains node-specific legacy branches. [VERIFIED: src/api/routers/agent_runs.py; tests/test_agent_runs_api.py] | Add target projection to event payloads or run-detail projection without breaking existing `node_name` consumers. [VERIFIED: tests/test_agent_runs_api.py] |
| `src/api/routers/agent_runs.py::_ensure_can_view_run` | AgentRun detail/status/evidence access is owner/admin-only; manager/supervisor-style roles are denied by tests. [VERIFIED: src/api/routers/agent_runs.py; tests/test_agent_runs_api.py] | Preserve owner/admin-only visibility until target merchant proof is recorded and later phases reopen same-merchant access safely. [VERIFIED: .planning/todos/deferred/2026-06-27-merchant-scope-agentrun-replay.md; tests/test_agent_runs_api.py] |
| `src/api/routers/traces.py` | Trace API returns `node` from persisted `AgentStep.node_name`; owner/admin-only tests exist. [VERIFIED: src/api/routers/traces.py; tests/test_trace_api.py; tests/replay/test_replay_api.py] | Trace API can add canonical projection fields, but must not change persisted `node` semantics or broaden access. [VERIFIED: tests/test_trace_api.py; tests/replay/test_replay_api.py] |
| `src/platform/context_projections.py::project_to_intent_policy_context` | Provides an intent-policy context projection with tenant/user/session/thread/run/trace metadata. [VERIFIED: src/platform/context_projections.py] | Reuse this projection for registry consumption instead of reading trusted identity from arbitrary state fields. [VERIFIED: tests/architecture/test_trusted_context_boundaries.py] |
| `src/platform/trusted_context.py::TrustedContextFactory` | Derives merchant scope from trusted user/session/server context and rejects non-admin wildcard scope. [VERIFIED: src/platform/trusted_context.py; tests/platform/test_trusted_context_factory.py] | Target merchant context evidence must be derived from trusted context, explicit scoped business refs, or safe route metadata, not LLM text or memory. [VERIFIED: docs/contract-spec.md §8; tests/architecture/test_trusted_context_boundaries.py] |

## Recommended Plan Split

| Plan | Theme | Depends On | Primary Files | Must-Have Acceptance |
|------|-------|------------|---------------|----------------------|
| `32-01` | Graph vocabulary and projection helper | none | New `src/agent/graph_vocabulary.py` or equivalent; `src/agent/trace.py`; API projection tests | Legacy nodes/routers map to target names; `rag_context_build` and `claim_verify` are present only as deferred/non-runnable target entries; `trace_steps[].node` remains legacy-compatible. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; docs/contract-spec.md §9] |
| `32-02` | Intent policy registry consumption | `32-01` | `src/agent/intent_policy.py`; `src/agent/routing.py`; `src/agent/nodes/classify_intent.py`; intent tests | Effective intent, risk, required slots, and initial route come from `IntentPolicyRegistry`; LLM output is recorded as candidate only. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md; src/agent/nodes/classify_intent.py] |
| `32-03` | Slot policy gate and target router projection | `32-01`, `32-02` | `src/agent/intent_policy.py`; `src/agent/routing.py`; `src/agent/nodes/extract_slots.py`; slot tests | `SlotPolicyRegistry` owns required-slot and inherited-slot acceptance; `route_after_slot_resolution` target semantics are total while `route_after_slots` legacy edge keys still compile. [VERIFIED: src/agent/routing.py; tests/agent/test_required_slots.py] |
| `32-04` | Trace/eval/API and target merchant-context evidence | `32-01` through `32-03` | `src/agent/trace.py`; `src/agent/state.py` if shared state is needed; `src/agent/nodes/receive_request.py`; `src/api/routers/agent_runs.py`; `src/api/routers/traces.py` | Run/trace projections expose canonical target names and target merchant context status `resolved`, `deferred`, `unavailable`, or `not_applicable`; owner/admin-only visibility remains unchanged. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; src/api/routers/agent_runs.py] |
| `32-05` | Final focused verification and plan-granularity gate | `32-01` through `32-04` | Tests and validation docs only unless gaps appear | Focused suites cover APF-11/APF-12, legacy compatibility, router totality, merchant visibility, and no Phase 33 fake RAG/claim implementation. [VERIFIED: .planning/REQUIREMENTS.md; .planning/ROADMAP.md; AGENTS.md] |

## Standard Stack

### Core

| Library / Runtime | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| Python | Project requires `>=3.12`; repo `.venv/bin/python` is 3.12.13. [VERIFIED: pyproject.toml; command output `.venv/bin/python --version`] | Agent backend, graph nodes, API, tests | Existing code uses Python 3.12+ runtime assumptions and project rules warn that older Python can create false test failures. [VERIFIED: AGENTS.md] |
| LangGraph | `>=0.4` in project dependencies; runtime import succeeded but package did not expose `__version__`. [VERIFIED: pyproject.toml; command output `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...`] | Runtime graph assembly | Existing `build_graph` uses `StateGraph`, conditional edges, `START`, and `END`. [VERIFIED: src/agent/graph.py] |
| Pydantic | `pydantic-settings>=2.0` and existing structured schemas are project-standard. [VERIFIED: pyproject.toml; src/agent/nodes/classify_intent.py] | Typed model output, schema contracts, projections | `IntentResultV3`, context projections, and service schemas already use typed models. [VERIFIED: src/agent/nodes/classify_intent.py; src/platform/context_projections.py] |
| FastAPI / SSE | `fastapi>=0.115`; `sse-starlette>=1.6`. [VERIFIED: pyproject.toml] | AgentRun APIs and stream events | Current AgentRun streaming and route handlers are FastAPI code. [VERIFIED: src/api/routers/agent_runs.py] |
| Pytest | Project declares `pytest>=8.0`; installed `uv run` environment reports pytest 9.0.3. [VERIFIED: pyproject.toml; command output `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...`] | Validation | Existing Phase 32 analog tests are pytest modules. [VERIFIED: tests/agent/test_graph.py; tests/test_agent_runs_api.py] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `uv` | 0.11.2. [VERIFIED: command output `uv --version`] | Required test/package entrypoint | Use for every Phase 32 test command. [VERIFIED: AGENTS.md] |
| `rg` | 14.1.1. [VERIFIED: command output `rg --version`] | Source and architecture grep | Use for plan review and final static checks. [VERIFIED: AGENTS.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New external graph-name package | Internal typed helper | No package is needed because the mapping is project-specific and already defined by `contract-spec.md` and Phase 32 context. [VERIFIED: docs/contract-spec.md §9; .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| Physical graph node rename in first plan | Projection-first alias registry | Physical rename risks breaking LangGraph edge keys, persisted traces, SSE event consumers, and exact-shape tests. [VERIFIED: src/agent/graph.py; src/agent/trace.py; tests/test_agent_runs_api.py] |
| DB backfill for historical `AgentStep.node_name` | Read-time target projection | Existing tables persist node names, and prior migration research treated historical node names as audit history rather than requiring backfill. [VERIFIED: src/db/models.py; .planning/milestones/v1.1-phases/10-state-lifecycle-routing-migration/10-RESEARCH.md] |

**Installation:** no new packages are recommended for Phase 32. [VERIFIED: pyproject.toml; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

```bash
# No dependency installation required for the recommended plan.
```

## Architecture Patterns

### System Architecture Diagram

```text
User/API request
  -> TrustedContextFactory / graph config
  -> receive_request reset
  -> safety pre-route semantics inside contextual intent path
  -> classify_intent runtime node
       -> IntentPolicyRegistry resolves candidate -> effective intent/route/risk
       -> target projection: contextual_intent_resolve
  -> session_memory_load runtime node
       -> session_context_load implementation
       -> target projection: session_context_load
  -> extract_slots runtime node
       -> SlotPolicyRegistry resolves explicit + inherited slots
       -> target projection: slot_extraction + slot_resolution_gate
  -> route_after_slots legacy edge key
       -> target projection: route_after_slot_resolution
  -> long_term_memory_retrieve runtime node
       -> reviewed_memory_context_retrieve implementation
       -> target projection: memory_context_load
  -> investigate / recommendation / risk / final response
  -> trace/API/eval projections
       -> legacy node_name preserved
       -> target canonical node/router names exposed
       -> target merchant context status recorded
```

The diagram reflects current runtime node order and target alias direction from the code and contract. [VERIFIED: src/agent/graph.py; docs/contract-spec.md §9; docs/target-agent-platform-architecture-plan.md §6]

### Recommended Project Structure

```text
src/
├── agent/
│   ├── graph_vocabulary.py        # typed legacy -> target node/router projection helper
│   ├── intent_policy.py           # consumed IntentPolicyRegistry and SlotPolicyRegistry APIs
│   ├── routing.py                 # deterministic legacy edge keys plus target router projection metadata
│   ├── trace.py                   # trace summary projection for canonical target names
│   └── nodes/
│       ├── classify_intent.py     # target contextual_intent_resolve semantics
│       ├── extract_slots.py       # slot extraction + slot resolution gate boundary
│       └── receive_request.py     # reset any new per-turn target context fields
└── api/
    └── routers/
        ├── agent_runs.py          # SSE/run detail canonical projection and merchant-context status
        └── traces.py              # trace read projection without changing persisted node_name
```

This structure keeps Phase 32 inside existing agent/API modules and avoids new service extraction. [VERIFIED: .planning/REQUIREMENTS.md Out of Scope; docs/target-agent-platform-architecture-plan.md §3]

### Pattern 1: Typed Graph Vocabulary Helper

**What:** one internal registry maps implementation names and legacy contract names to target canonical names. [VERIFIED: docs/contract-spec.md §9; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
**When to use:** use in trace summaries, eval projections, API payload projections, and tests; do not use it to mutate LangGraph node keys by default. [VERIFIED: src/agent/graph.py; src/agent/trace.py; tests/test_agent_runs_api.py]

```python
# Proposed shape. Source contract: docs/contract-spec.md §9.
@dataclass(frozen=True)
class GraphVocabularyEntry:
    implementation_name: str
    target_name: str
    kind: Literal["node", "router"]
    status: Literal["implemented", "compatibility_wrapper", "deferred_non_runnable"]

def target_graph_name(name: str, *, kind: Literal["node", "router"]) -> str:
    entry = _BY_IMPLEMENTATION.get((kind, name)) or _BY_TARGET.get((kind, name))
    return entry.target_name if entry else name
```

### Pattern 2: Registry-Consumed Intent Resolution

**What:** `IntentPolicyRegistry` should expose consumed methods for pre-route, precedence, confidence gates, risk tier, required slots, and effective route. [VERIFIED: src/agent/intent_policy.py; src/agent/nodes/classify_intent.py]  
**When to use:** use when converting LLM candidate output into effective graph state and when `route_after_intent` validates final edge keys. [VERIFIED: src/agent/routing.py; tests/agent/test_intent_routing.py]

```python
# Proposed shape. Existing helpers live in src/agent/intent_policy.py.
effective = INTENT_POLICY_REGISTRY.resolve_contextual_intent(
    candidate=result,
    state=state,
    policy_context=project_to_intent_policy_context(trusted_context, run_ids),
)
return {
    "primary_intent": effective.primary_intent,
    "required_slots": effective.required_slots,
    "risk_tier": effective.risk_tier,
    "classification_trace": effective.trace,
}
```

### Pattern 3: Slot Resolution Gate as Deterministic Boundary

**What:** one deterministic slot policy method should accept current-turn extracted slots, active slots, session context metadata, invalidations, and current intent, then return resolved slots, metadata, missing slots, and route readiness. [VERIFIED: src/agent/routing.py; tests/agent/test_required_slots.py]  
**When to use:** use after slot extraction and before memory/investigate routing; keep legacy `route_after_slots` return keys until graph edge maps are intentionally changed. [VERIFIED: src/agent/graph.py; docs/contract-spec.md §9]

### Anti-Patterns to Avoid

- **Renaming `trace_steps[].node` directly:** existing persistence, SSE, trace, and replay consumers read legacy names. [VERIFIED: src/agent/trace.py; src/api/routers/agent_runs.py; tests/test_trace_api.py; tests/replay/test_replay_api.py]
- **Duplicating alias maps in tests and API:** a per-test map can pass APF-11 while production projections still drift. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]
- **Letting `IntentResultV3.required_slots` own effective slots:** the target contract says model output is candidate-only, and current code already records LLM-required slots separately from policy-required slots. [VERIFIED: docs/contract-spec.md §10; src/agent/nodes/classify_intent.py]
- **Treating session memory or LLM text as merchant authority:** memory is contextual-only and cannot satisfy business fact, approval, action, or replay truth. [VERIFIED: .planning/REQUIREMENTS.md; tests/agent/test_memory_evidence_boundary.py]
- **Adding runnable `rag_context_build` or `claim_verify` success paths:** Phase 33 owns APF-13/APF-14 behavior. [VERIFIED: .planning/REQUIREMENTS.md; .planning/ROADMAP.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canonical graph vocabulary | Scattered string replaces or test-local alias dictionaries | One typed helper used by trace/eval/API/tests | Contract/eval names must stay consistent across legacy traces, API payloads, and future replay. [VERIFIED: docs/contract-spec.md §9; src/agent/trace.py] |
| Intent route policy | Branches duplicated in `classify_intent`, `routing`, and tests | `IntentPolicyRegistry` consumed API | APF-12 requires deterministic policy ownership, and current direct constant imports are the gap. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md; src/agent/routing.py] |
| Slot inheritance | New ad hoc merge code in graph node | `SlotPolicyRegistry` plus existing `resolve_slots_with_metadata` semantics | Existing tests already cover freshness, tenant/user/thread, invalidation, current-turn override, and intent compatibility. [VERIFIED: tests/agent/test_required_slots.py] |
| Merchant-context proof | LLM-derived merchant ID or memory-derived scope | Trusted context, explicit current-turn scoped slot, or business fact refs | Existing boundaries forbid memory/LLM replacing current business facts or authority. [VERIFIED: .planning/REQUIREMENTS.md; tests/agent/test_reviewed_memory_context_retrieve.py] |
| RAG/claim placeholders | Dummy success nodes | Deferred/non-runnable target entries | APF-13/APF-14 belong to Phase 33. [VERIFIED: .planning/ROADMAP.md] |

**Key insight:** Phase 32 is a contract/projection and policy-consumption migration, not a wholesale graph rewrite. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; .planning/REQUIREMENTS.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agent_steps.node_name` stores raw step names, and `agent_trace_events.node_name` also persists node names. [VERIFIED: src/db/models.py] | Preserve stored legacy names and add read/projection fields; do not backfill historical audit rows in Phase 32 unless a later plan explicitly scopes a migration. [VERIFIED: src/agent/trace.py; tests/test_trace_api.py] |
| Live service config | No live external service configuration was identified in Phase 32 docs/code scan; graph behavior is repo code and database-backed traces. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; rg scan for `pm2|launchd|systemd|datadog|cloudflare|n8n`] | No API patch or external UI migration is planned; if implementation discovers external observability dashboards keyed by node names, record it as a separate scope item. [VERIFIED: rg scan] |
| OS-registered state | No OS-level graph node registrations, scheduled tasks, launchd/systemd units, or pm2 process names were identified in repo scan. [VERIFIED: rg scan for `pm2|launchd|systemd|Task Scheduler`] | None. [VERIFIED: rg scan] |
| Secrets/env vars | No secret or env-var rename is required by the Phase 32 graph vocabulary migration; `.env` files were not read. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; AGENTS.md] | None for research/planning; do not inspect secrets unless an implementation task introduces a concrete env-var change. [VERIFIED: AGENTS.md] |
| Build artifacts | Local `.pytest_cache`, `.ruff_cache`, `__pycache__`, and `moca.egg-info` exist. [VERIFIED: filesystem scan] | No package reinstall is required because Phase 32 does not rename the Python package; run tests from repo root through `uv run`. [VERIFIED: pyproject.toml; AGENTS.md] |

## Common Pitfalls

### Pitfall 1: Breaking Legacy Trace Consumers
**What goes wrong:** a plan renames `trace_steps[].node` or persisted `AgentStep.node_name` to target names. [VERIFIED: src/agent/trace.py; src/db/models.py]  
**Why it happens:** APF-11 target vocabulary can be mistaken for a physical storage migration. [VERIFIED: docs/contract-spec.md §9; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
**How to avoid:** keep implementation names in legacy fields and add canonical projection fields. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
**Warning signs:** tests in `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`, or `tests/replay/test_replay_api.py` fail on `node_name`. [VERIFIED: tests/test_agent_runs_api.py; tests/test_trace_api.py; tests/replay/test_replay_api.py]

### Pitfall 2: Registries Stay Thin Views
**What goes wrong:** tests assert registry contents, but `routing.py` and `classify_intent.py` still import constants directly. [VERIFIED: src/agent/routing.py; tests/agent/test_intent_policy_registry.py]  
**Why it happens:** current registry tests mirror constants rather than proving runtime consumption. [VERIFIED: tests/agent/test_intent_policy_registry.py]  
**How to avoid:** add spy/fake registry tests or monkeypatch registry methods and assert effective route/slots change only through registry APIs. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md]  
**Warning signs:** `rg -n "REQUIRED_SLOT_POLICY|INTENT_ROUTE_POLICY|DIRECT_RESPONSE_INTENTS" src/agent/routing.py src/agent/nodes/classify_intent.py` still shows direct policy consumption after Plan 32-02. [VERIFIED: src/agent/routing.py; src/agent/nodes/classify_intent.py]

### Pitfall 3: Slot Gate Double-Merges State
**What goes wrong:** a new `slot_resolution_gate` node reuses `resolve_slots_with_metadata` after `extract_slots` already merged active slots, causing stale or incompatible slots to reappear. [VERIFIED: src/agent/nodes/extract_slots.py; src/agent/routing.py]  
**Why it happens:** current code combines extraction and resolution in `extract_slots`. [VERIFIED: src/agent/nodes/extract_slots.py]  
**How to avoid:** first expose `slot_resolution_gate` as a deterministic helper/projection; split into a physical node only after idempotence tests exist. [VERIFIED: docs/target-agent-platform-architecture-plan.md §6; tests/agent/test_required_slots.py]  
**Warning signs:** stale, wrong-thread, invalidated, or incompatible inherited slots route to `investigate` instead of `clarification_gate`. [VERIFIED: tests/agent/test_required_slots.py; tests/agent/test_session_memory_integration.py]

### Pitfall 4: Merchant Context Evidence Becomes Authorization
**What goes wrong:** adding `target_merchant_context.status="resolved"` from LLM text or memory lets manager/supervisor-like roles see tenant-wide runs. [VERIFIED: .planning/todos/deferred/2026-06-27-merchant-scope-agentrun-replay.md; tests/test_agent_runs_api.py]  
**Why it happens:** merchant evidence and API authorization are easy to conflate. [VERIFIED: docs/contract-spec.md §8; docs/contract-spec.md §10]  
**How to avoid:** keep owner/admin-only visibility in Phase 32 and treat target merchant context as recorded evidence, not a new access grant. [VERIFIED: src/api/routers/agent_runs.py; src/api/routers/traces.py]  
**Warning signs:** tests for `supervisor` or `approval_manager` access start passing without explicit same-merchant proof requirements. [VERIFIED: tests/test_agent_runs_api.py; tests/test_trace_api.py; tests/replay/test_replay_api.py]

### Pitfall 5: Phase 33 Scope Creep
**What goes wrong:** `rag_context_build` and `claim_verify` are registered as runnable nodes that appear successful. [VERIFIED: .planning/REQUIREMENTS.md; .planning/ROADMAP.md]  
**Why it happens:** APF-11 asks for target vocabulary, while APF-13/APF-14 ask for actual RAG/claim behavior. [VERIFIED: .planning/REQUIREMENTS.md]  
**How to avoid:** mark those target names as deferred/non-runnable in the vocabulary helper and add tests that no Phase 33 success behavior is implied. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
**Warning signs:** `src/agent/graph.py` includes new successful `rag_context_build` or `claim_verify` nodes before Phase 33 contracts are implemented. [VERIFIED: src/agent/graph.py; .planning/ROADMAP.md]

## Code Examples

### Graph Trace Projection

```python
# Proposed Phase 32 pattern. It preserves legacy debug fields and adds target fields.
def project_trace_step_for_contract(step: dict[str, Any]) -> dict[str, Any]:
    node = str(step.get("node") or "unknown")
    return {
        **step,
        "target_node": target_graph_name(node, kind="node"),
        "implementation_node": node,
    }
```

The source requirement is APF-11 canonical mapping with legacy compatibility. [VERIFIED: .planning/REQUIREMENTS.md; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

### Registry-Owned Required Slots

```python
# Proposed Phase 32 pattern. Candidate slots remain observable, not authoritative.
policy_required = SLOT_POLICY_REGISTRY.required_slots_for(primary_intent)
llm_required = list(result.required_slots or [])
trace["llm_required_slots"] = llm_required
state["required_slots"] = policy_required
```

The source requirement is APF-12 and the existing adapter pattern in `intent_result_to_state`. [VERIFIED: .planning/REQUIREMENTS.md; src/agent/nodes/classify_intent.py]

### Target Merchant Context Evidence

```python
# Proposed Phase 32 shape. The status is evidence, not an authorization grant.
target_merchant_context = {
    "schema_version": "target_merchant_context.v1",
    "status": "deferred",
    "source": "insufficient_business_fact_ref",
    "reason_codes": ["TARGET_MERCHANT_NOT_PROVEN"],
}
```

The source requirement is D-13 target merchant context status with no widened manager/supervisor access. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; tests/test_agent_runs_api.py]

## State of the Art

| Old / Current Approach | Current Target Approach | When Changed / Source | Impact |
|------------------------|-------------------------|-----------------------|--------|
| Runtime graph exposes legacy names such as `classify_intent` and `route_after_intent`. [VERIFIED: src/agent/graph.py] | Contract/eval projections expose target names such as `contextual_intent_resolve` and `route_after_contextual_intent`. [VERIFIED: docs/contract-spec.md §9] | Target vocabulary established before Phase 32 in contract/architecture docs. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] | Planner must separate implementation node names from contract names. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `IntentPolicyRegistry` and `SlotPolicyRegistry` mirror constants. [VERIFIED: src/agent/intent_policy.py; tests/agent/test_intent_policy_registry.py] | Registries become consumed policy boundaries for effective routing and slot inheritance. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md] | Phase 32 owns this migration. [VERIFIED: .planning/ROADMAP.md] | Tests must prove consumers use registry APIs, not only constant equality. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |
| `session_memory_load` and `long_term_memory_retrieve` remain graph node keys. [VERIFIED: src/agent/graph.py] | Wrappers/projections map to `session_context_load` and `memory_context_load`. [VERIFIED: src/agent/nodes/session_memory_load.py; src/agent/nodes/long_term_memory_retrieve.py] | Phase 31 introduced wrapper-style memory migration; Phase 32 extends it. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] | Wrapper pattern is safer than broad renames. [VERIFIED: tests/agent/test_session_memory_load.py] |

**Deprecated/outdated:** treating legacy names as the only graph contract is outdated for APF-11, but legacy names remain valid implementation/debug names. [VERIFIED: .planning/REQUIREMENTS.md; src/agent/trace.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| None | All factual claims in this research are sourced from local project docs, source code, tests, or command output. [VERIFIED: local files and commands listed in Sources] | n/a | n/a |

## Open Questions

1. **Should target canonical names be persisted in `AgentStep.metrics_json` or only projected at read time?**  
   What we know: `AgentStep.node_name` persists implementation names, and `metrics_json` is available on the same table. [VERIFIED: src/db/models.py; src/agent/trace.py]  
   What's unclear: Phase 32 context allows graph state, trace metrics, route decision metadata, or AgentRun projection for merchant/context evidence. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
   Recommendation: prefer read-time projection first; persist only if eval/replay needs stable snapshot semantics in Phase 32. [VERIFIED: tests/test_trace_api.py; tests/replay/test_replay_api.py]

2. **Should `slot_resolution_gate` become a physical graph node in Phase 32?**  
   What we know: target architecture says it should become an explicit registered node, but current code resolves slots inside `extract_slots`. [VERIFIED: docs/target-agent-platform-architecture-plan.md §6; src/agent/nodes/extract_slots.py]  
   What's unclear: a physical node may require broader graph edge and trace fixture churn than APF-12 strictly needs. [VERIFIED: tests/agent/test_graph.py; tests/test_agent_runs_api.py]  
   Recommendation: plan a helper/projection first, then decide on a physical node only if tests and task scope remain small. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

3. **How much target merchant context should be exposed through AgentRun response schemas?**  
   What we know: D-13 requires status evidence, and current run visibility must remain owner/admin-only. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; src/api/routers/agent_runs.py]  
   What's unclear: whether the field belongs in graph state, trace metrics, run detail payload, or all three. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md]  
   Recommendation: start with graph state plus trace/run-detail projection; avoid DB schema migration unless the plan proves replay/eval cannot consume projection. [VERIFIED: src/agent/trace.py; src/api/routers/agent_runs.py]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | All validation commands | yes | 0.11.2 | None needed. [VERIFIED: command output `uv --version`] |
| repo `.venv` Python | Project test/runtime entrypoint | yes | 3.12.13 | Use `UV_CACHE_DIR=/tmp/uv-cache uv run ...`. [VERIFIED: command output `.venv/bin/python --version`; AGENTS.md] |
| system `python3` | Not recommended for MOCA tests | yes | 3.13.3 | Use repo `.venv`/`uv run` for tests. [VERIFIED: command output `python3 --version`; AGENTS.md] |
| `pytest` via `uv run` | Test execution | yes | 9.0.3 | None needed. [VERIFIED: command output `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...`] |
| `rg` | Source scan and plan review | yes | 14.1.1 | Use POSIX grep only if `rg` is unavailable. [VERIFIED: command output `rg --version`; AGENTS.md] |

**Missing dependencies with no fallback:** none identified for Phase 32 research/planning. [VERIFIED: environment commands]

**Missing dependencies with fallback:** none identified. [VERIFIED: environment commands]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Pytest 9.0.3 through `uv run`; project declares `pytest>=8.0`. [VERIFIED: command output; pyproject.toml] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"`. [VERIFIED: pyproject.toml] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` [VERIFIED: AGENTS.md; tests exist] |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py tests/platform/test_trusted_context_factory.py tests/platform/test_context_projections.py -q --tb=short` [VERIFIED: tests inspected; AGENTS.md] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APF-11 | Legacy node/router names project to target canonical names while preserving legacy `trace_steps[].node` and graph edge keys. [VERIFIED: .planning/REQUIREMENTS.md; src/agent/graph.py] | unit/contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_trace.py -q --tb=short` | yes; new assertions needed. [VERIFIED: tests/agent/test_graph.py; tests/agent/test_trace.py] |
| APF-11 | AgentRun/trace/replay API projections expose safe target names without breaking existing `node_name` consumers. [VERIFIED: src/api/routers/agent_runs.py; src/api/routers/traces.py] | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py -q --tb=short` | yes; new assertions needed. [VERIFIED: tests/test_agent_runs_api.py; tests/test_trace_api.py; tests/replay/test_replay_api.py] |
| APF-12 | `IntentPolicyRegistry` is consumed for effective intent/route/risk/required slots; LLM output remains candidate-only. [VERIFIED: .planning/REQUIREMENTS.md; src/agent/intent_policy.py] | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | yes; new consumption tests needed. [VERIFIED: test files inspected] |
| APF-12 | `SlotPolicyRegistry` owns required-slot and inherited-slot acceptance; stale/wrong-scope/incompatible slots clarify. [VERIFIED: src/agent/routing.py; tests/agent/test_required_slots.py] | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py -q --tb=short` | yes; new registry-consumption assertions needed. [VERIFIED: test files inspected] |
| D-13 | Target merchant context status is recorded safely and does not broaden manager/supervisor access. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] | API/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` | yes; new status assertions needed. [VERIFIED: test files inspected] |

### Sampling Rate

- **Per task commit:** run the focused test file touched by the task plus `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` for graph vocabulary tasks. [VERIFIED: AGENTS.md; tests/agent/test_graph.py]
- **Per wave merge:** run the quick command in the Test Framework table. [VERIFIED: AGENTS.md]
- **Phase gate:** run the full suite command in the Test Framework table and a static grep for forbidden bare pytest commands in Phase 32 artifacts. [VERIFIED: AGENTS.md]

### Wave 0 Gaps

- [ ] Add tests for a new graph vocabulary helper, likely in `tests/agent/test_graph_vocabulary.py`, covering node aliases, router aliases, deferred/non-runnable `rag_context_build` and `claim_verify`, and unknown-name passthrough. [VERIFIED: APF-11 in .planning/REQUIREMENTS.md]
- [ ] Add registry-consumption tests that fail if `routing.py` or `classify_intent.py` bypasses `IntentPolicyRegistry`/`SlotPolicyRegistry`. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md; src/agent/routing.py]
- [ ] Add target merchant context evidence tests in AgentRun/trace surfaces while preserving owner/admin-only access tests. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md; tests/test_agent_runs_api.py]

### Verification Matrix

| Area | Command | Purpose |
|------|---------|---------|
| Graph aliases and router totality | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_trace.py -q --tb=short` | Proves graph compiles, legacy edge keys remain finite, and target projection is testable. [VERIFIED: tests/agent/test_graph.py; tests/agent/test_trace.py] |
| Intent registry | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | Proves APF-12 candidate/effective ownership. [VERIFIED: test files inspected] |
| Slot policy and memory context | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py -q --tb=short` | Proves slot inheritance, session context, reviewed memory, and contextual-only authority boundaries. [VERIFIED: test files inspected] |
| API, trace, replay visibility | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` | Proves projection/visibility changes do not widen manager/supervisor access. [VERIFIED: test files inspected] |
| Static route/policy scan | `rg -n "REQUIRED_SLOT_POLICY|INTENT_ROUTE_POLICY|DIRECT_RESPONSE_INTENTS" src/agent/routing.py src/agent/nodes/classify_intent.py` | Detects direct policy constant consumption after registry migration. [VERIFIED: current direct imports in src/agent/routing.py and src/agent/nodes/classify_intent.py] |
| No fake Phase 33 nodes | `rg -n "rag_context_build|claim_verify" src/agent/graph.py src/agent tests/agent` | Detects runnable RAG/claim paths that should remain deferred unless explicitly planned. [VERIFIED: .planning/ROADMAP.md] |
| Test command docs review | `rg -n 'pytest|python -m pytest' .planning/phases/32-intent-graph-migration` | Review every match and verify runnable commands use `uv run pytest ...` or `.venv/bin/pytest ...`; explanatory mentions of bare pytest must describe forbidden usage only. [VERIFIED: AGENTS.md] |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct auth implementation | Preserve existing trusted API/auth/run context boundaries; do not accept LLM/user-payload identity overrides. [VERIFIED: src/platform/trusted_context.py; docs/contract-spec.md §8] |
| V3 Session Management | yes, through same-thread context | Session context may support continuity only within trusted tenant/user/thread/scope checks. [VERIFIED: docs/contract-spec.md §10; src/agent/routing.py] |
| V4 Access Control | yes | Keep AgentRun/trace owner/admin-only visibility until target merchant proof is available; do not widen manager/supervisor access in Phase 32. [VERIFIED: src/api/routers/agent_runs.py; src/api/routers/traces.py; tests/test_agent_runs_api.py] |
| V5 Input Validation | yes | Treat LLM structured output as candidate-only and validate effective decisions through registries and deterministic routers. [VERIFIED: APF-12 in .planning/REQUIREMENTS.md; src/agent/nodes/classify_intent.py] |
| V6 Cryptography | no new crypto | Phase 32 does not introduce cryptographic primitives or secret handling. [VERIFIED: .planning/phases/32-intent-graph-migration/32-CONTEXT.md] |

### Known Threat Patterns for MOCA Agent Graph

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM prompt text claims an approval/action decision | Elevation of privilege / spoofing | Pre-route approval chat remains untrusted and routes fail-closed to clarification/refusal. [VERIFIED: src/agent/intent_policy.py; tests/agent/test_nodes/test_classify_intent.py] |
| Stale or wrong-scope session slot satisfies required business identifier | Tampering / information disclosure | Slot policy accepts inherited slots only with trusted metadata, tenant/user/thread match, freshness, and intent compatibility. [VERIFIED: src/agent/routing.py; tests/agent/test_required_slots.py] |
| Manager/supervisor reads another merchant's run from tenant-wide AgentRun visibility | Information disclosure | Preserve owner/admin-only AgentRun/trace/replay visibility until same-merchant proof is implemented in later phases. [VERIFIED: tests/test_agent_runs_api.py; tests/test_trace_api.py; tests/replay/test_replay_api.py] |
| Memory or candidate slots used as business authority | Tampering / information disclosure | Reviewed memory remains contextual-only and cannot create trusted merchant scope or business fact authority. [VERIFIED: tests/agent/test_reviewed_memory_context_retrieve.py; tests/agent/test_memory_evidence_boundary.py] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/32-intent-graph-migration/32-CONTEXT.md` - Phase 32 locked decisions, current code sites, tests to inspect, deferrals. [VERIFIED: local file read]
- `.planning/REQUIREMENTS.md` - APF-11, APF-12, out-of-scope constraints, traceability. [VERIFIED: local file read]
- `.planning/ROADMAP.md` - Phase 32 goal and success criteria, Phase 33-35 ownership. [VERIFIED: `gsd-sdk query roadmap.get-phase 32`; local file read]
- `.planning/STATE.md` - Phase 31 completion and Phase 32 next-step status. [VERIFIED: local file read]
- `docs/contract-spec.md` §9/§10/§17 - target graph vocabulary, state fields, trace/replay expectations. [CITED: docs/contract-spec.md]
- `docs/target-agent-platform-architecture-plan.md` §3/§5/§6 - service boundaries and target graph shape. [CITED: docs/target-agent-platform-architecture-plan.md]
- `docs/eval-test-plan.md` - intent/routing/slot/eval expectations. [CITED: docs/eval-test-plan.md]
- `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/intent_policy.py`, `src/agent/nodes/*.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/platform/context_projections.py`, `src/platform/trusted_context.py` - current implementation behavior. [VERIFIED: local source read]
- Tests listed in Phase 32 CONTEXT, plus trace/replay/platform tests for API visibility. [VERIFIED: local test read]

### Secondary (MEDIUM confidence)

- `.planning/todos/deferred/2026-06-27-merchant-scope-agentrun-replay.md` - deferred AgentRun/merchant-scope context for Phase 32/35. [VERIFIED: local file read]
- Prior Phase 10 and Phase 31 research/plans - precedent for preserving historical node names and wrapper-style memory migration. [VERIFIED: local planning files]

### Tertiary (LOW confidence)

- None. [VERIFIED: no web-only findings used]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - based on `pyproject.toml` and local command output. [VERIFIED: pyproject.toml; environment commands]
- Architecture: HIGH - based on current graph/source/tests and normative project docs. [VERIFIED: source files; docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]
- Pitfalls: HIGH - based on current tests, persisted schema, locked Phase 32 decisions, and prior local migration precedent. [VERIFIED: tests; src/db/models.py; .planning/phases/32-intent-graph-migration/32-CONTEXT.md]

**Research date:** 2026-06-28  
**Valid until:** 2026-07-28 for codebase-local planning assumptions; re-run source/test scan before implementation if Phase 32 is delayed. [VERIFIED: current_date 2026-06-28]
