# Phase 32: Intent Graph Migration - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning
**Source:** `$gsd-phase-autopilot 32` -> `$gsd-discuss-phase 32 --auto` semantics; conservative defaults selected by Codex after reading roadmap, requirements, prior context, and current graph code.

<domain>
## Phase Boundary

Phase 32 migrates the current intent/routing graph toward the target canonical vocabulary in `docs/contract-spec.md` while preserving legacy compatibility. It owns target-name mapping for legacy nodes/routers such as `intent_classification`, `session_memory_load`, `route_after_intent`, and `route_after_slots`; it also owns the point where `IntentPolicyRegistry` and `SlotPolicyRegistry` become the authoritative source for effective route and slot inheritance decisions.

This phase must satisfy APF-11 and APF-12. It should prove the graph can project or register target names for `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `rag_context_build`, and `claim_verify`, without silently claiming Phase 33 RAG/claim behavior is complete. It must also record how target merchant context is resolved or deferred for graph routing and AgentRun visibility, without keeping manager/supervisor-like access implicitly tenant-wide.

This phase should not implement full RAG context build, full claim verification, approval/action binding, external execution, broad replay/eval hardening, physical microservice extraction, or a wholesale graph rewrite that breaks current Agent Console behavior.

</domain>

<decisions>
## Implementation Decisions

### Graph Vocabulary And Compatibility

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

### Intent Policy Ownership

- **D-05:** `IntentPolicyRegistry` owns effective intent/route policy. LLM structured output remains candidate-only.
  - Existing code already has `IntentPolicyRegistry`, `IntentDefinition`, `INTENT_ROUTE_POLICY`, precedence, evidence-required, direct-response, high-risk, and risk-tier helpers in `src/agent/intent_policy.py`.
  - Phase 32 should move effective decision consumers toward the registry interface instead of directly spreading constants across `classify_intent`, `routing`, and tests.
- **D-06:** `contextual_intent_resolve` semantics should include deterministic pre-route, same-thread context handling, precedence normalization, confidence gates, risk tier resolution, and effective route decision.
  - Existing `classify_intent` already performs `detect_pre_route`, deterministic active-flow handling, short-reply guards, precedence overrides, risk tier resolution, and `classification_trace`.
  - Phase 32 should make that trace read as candidate -> policy override -> effective classification, not as LLM-owned routing.
- **D-07:** Approval-like chat and safety-sensitive ordinary-chat inputs remain fail-closed before any action/approval authority is accepted from chat text.
  - `approval_chat_not_trusted`, `safety_sensitive`, `multi_target_request`, low confidence, and ambiguous short replies must remain routed to clarification/refusal paths.
  - Do not let a target rename weaken Phase 25 safety behavior.

### Slot Policy Resolution

- **D-08:** `SlotPolicyRegistry` owns required-slot policy and slot inheritance decisions. Current-turn explicit slots override inherited session slots; inherited slots are accepted only when freshness, scope, and intent compatibility pass.
  - Existing `route_after_slots`, `missing_required_slots`, and `resolve_slots_with_metadata` already implement much of this, but they read `REQUIRED_SLOT_POLICY` directly.
  - Phase 32 should expose a target `slot_resolution_gate` semantic boundary and make tests assert registry-owned required slot policy.
- **D-09:** Uncertain slot inheritance must clarify, not guess.
  - Missing, stale, wrong-thread, incompatible, invalidated, or scope-unsafe slots route to `clarification_gate`.
  - `policy_qa` and other no-slot direct investigation paths must not accidentally consume stale active business identifiers.
- **D-10:** `route_after_slot_resolution` should be deterministic and total. Tests must include safety pre-route, low confidence, direct response, slot required, missing slot, stale/incompatible inherited slot, trusted memory context path, and direct investigate path.

### Trace, Eval, And Merchant Context Evidence

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

### Verification Strategy

- **D-15:** Start from RED tests that pin canonical alias/projection semantics before implementation.
  - Tests should prove legacy graph names map to target canonical names in trace/eval projections, and that aliasing does not create different semantics.
- **D-16:** Add registry-focused tests proving `IntentPolicyRegistry` and `SlotPolicyRegistry` are the consumed policy surface for effective route and slot decisions.
- **D-17:** Add route totality and graph compilation tests for both legacy runtime edge keys and target canonical route names.
- **D-18:** Add AgentRun/trace tests proving target merchant context evidence is recorded safely and manager/supervisor-style visibility is not tenant-wide without target merchant/business fact proof.
- **D-19:** Use MOCA's required test entrypoint: `uv run pytest ...` or `.venv/bin/pytest ...`; never use bare `pytest`.

### Agent Discretion

- Exact file names are left to planning. Likely targets include `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/intent_policy.py`, `src/agent/nodes/classify_intent.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, and targeted tests under `tests/agent/`, `tests/api/`, and `tests/architecture/`.
- Exact representation of the alias map is left to planning. Prefer a small typed registry/helper over ad hoc per-test string maps.
- Exact merchant-context evidence schema is left to planning, but it must not expose forbidden business identifiers or imply access to out-of-scope runs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 32 goal, APF-11/APF-12 success criteria, Phase 31 dependency, and Phase 33-35 deferrals.
- `.planning/REQUIREMENTS.md` - APF-11, APF-12, MER-01, APF-13/APF-18 traceability and out-of-scope constraints.
- `.planning/STATE.md` - Current milestone state, Phase 31 completion context, and required Phase 32 next step.

### Normative Contracts

- `docs/contract-spec.md` §0.2 - `IntentService`, `MemoryContextService`, `KnowledgeService`, `BusinessFactService`, and observability ownership boundaries.
- `docs/contract-spec.md` §8.0 / §8.0.1 - `TrustedContext`, `MerchantScopeV1`, and merchant-bound role semantics.
- `docs/contract-spec.md` §9 - Target canonical graph vocabulary, legacy graph alias rules, node/router contract, routing tables, and evidence sufficiency defaults.
- `docs/contract-spec.md` §10 - AgentState target fields, reset/merge rules, and compatibility state fields.
- `docs/contract-spec.md` §17 - Decision event ordering and future replay/trace expectations.
- `docs/target-agent-platform-architecture-plan.md` §3 / §5.2 - Modular monolith boundary principles and module ownership matrix.
- `docs/target-agent-platform-architecture-plan.md` §6 - Target runtime graph shape, registered node/router distinction, and legacy alias mapping.
- `docs/eval-test-plan.md` - Intent/routing, required-slot, evidence policy, and eval gate expectations.

### Prior Phase Context

- `.planning/phases/25-intent-routing-safety-hardening/25-CONTEXT.md` - Phase 25 safety and intent routing decisions.
- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - Trusted identity/scope projection rules.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - Decision event envelope and reason-code conventions.
- `.planning/phases/29-tool-platform-boundary/29-CONTEXT.md` - ToolPlatform visibility/runtime policy and trace handoff.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Merchant-bound role semantics and manager/admin scope decisions.
- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - Current business fact authority and no-leak boundary.
- `.planning/phases/31-memory-platform-boundary/31-CONTEXT.md` - Session context, reviewed memory context, and contextual-only authority boundary.

### Current Code Sites

- `src/agent/graph.py` - Current registered LangGraph node keys and conditional edge mappings.
- `src/agent/routing.py` - Legacy `route_after_intent`, `route_after_slots`, `route_after_investigate`, route totality guards, and slot inheritance helpers.
- `src/agent/intent_policy.py` - `IntentPolicyRegistry`, `SlotPolicyRegistry`, intent definitions, pre-route, precedence, confidence, and risk-tier policy.
- `src/agent/nodes/classify_intent.py` - Current candidate classification, deterministic overrides, policy trace, and route decision production.
- `src/agent/nodes/extract_slots.py` - Current slot candidate extraction and active-slot update behavior.
- `src/agent/nodes/session_memory_load.py` and `src/agent/nodes/session_context_load.py` - Legacy wrapper and target session context load node.
- `src/agent/nodes/long_term_memory_retrieve.py` and `src/agent/nodes/reviewed_memory_context_retrieve.py` - Legacy wrapper and reviewed memory context load behavior.
- `src/agent/nodes/receive_request.py` - Per-turn reset fields and initial graph state reset behavior.
- `src/agent/trace.py` - AgentStep persistence, trace summary projection, and node-name recording.
- `src/api/routers/agent_runs.py` - SSE node messages, trusted graph config, AgentRun visibility, stream trace persistence, and owner/admin visibility behavior.
- `src/platform/context_projections.py` - Trusted context projections including intent policy context.
- `src/platform/trusted_context.py` - `TrustedContextFactory` and `MerchantScopeV1`.

### Tests To Inspect

- `tests/agent/test_graph.py`
- `tests/agent/test_intent_routing.py`
- `tests/agent/test_intent_policy_registry.py`
- `tests/agent/test_required_slots.py`
- `tests/agent/test_session_memory_load.py`
- `tests/agent/test_session_memory_integration.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/agent/test_nodes/test_classify_intent.py`
- `tests/agent/test_nodes/test_receive_request.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/test_agent_runs_api.py`
- `tests/architecture/test_trusted_context_boundaries.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src.agent.intent_policy.IntentPolicyRegistry` and `SlotPolicyRegistry` already exist, but they are thin read-only views and not yet clearly the consumed policy boundary everywhere.
- `src.agent.nodes.session_memory_load.session_memory_load` is already a compatibility wrapper over `session_context_load`.
- `src.agent.nodes.long_term_memory_retrieve.long_term_memory_retrieve` is already a compatibility wrapper over `reviewed_memory_context_retrieve`.
- `src.agent.routing.resolve_slots_with_metadata` already applies current-turn override, freshness, thread/scope compatibility, intent compatibility, and invalidation metadata.
- `src.agent.nodes.classify_intent.intent_result_to_state` already records raw LLM classification, policy overrides, effective classification, risk tier, route decision, and reason codes.
- `src.agent.trace.write_agent_steps` and `build_trace_summary` are central places to add or consume safe target node projections.

### Established Patterns

- Public contracts use typed Pydantic schemas or explicit TypedDict state fields.
- Legacy compatibility aliases are acceptable when they are derived from target semantics and test-pinned.
- Routers are deterministic and side-effect-free; they return finite edge keys and fail closed to clarification/final response on invalid state.
- Trusted identity, merchant scope, and AgentRun visibility must come from `TrustedContextFactory`, business fact refs, or trusted route/run metadata; not from LLM text, memory, RAG, or prompt summaries.
- Negative tests are as important as happy paths for safety, scope, and authority boundaries.

### Current Gaps To Close

- `src/agent/graph.py` still exposes legacy registered node names only for intent/session/memory/recommendation/risk concepts.
- `route_after_intent` and `route_after_slots` still return legacy edge keys and consume constants directly rather than target registry-owned semantics.
- Trace/API/eval surfaces do not yet provide a first-class target canonical graph name projection.
- Existing router totality tests pin legacy edge keys but do not prove target canonical aliases.
- AgentRun target merchant context resolution/defer evidence is not yet a first-class graph/run artifact.

</code_context>

<specifics>
## Specific Ideas

- Keep the first implementation pass intentionally narrow: add a target graph vocabulary helper/registry and tests before modifying runtime graph edges.
- Make `contextual_intent_resolve` a target semantic projection of `classify_intent` before attempting any physical node rename.
- Make `slot_resolution_gate` a target semantic boundary around existing slot resolution helpers before adding new slot extraction complexity.
- Treat `rag_context_build` and `claim_verify` as named target deferrals in Phase 32 unless the plan explicitly adds fail-closed placeholder routes. Full behavior belongs to Phase 33.
- Prefer adding safe `canonical_node` / `target_node` projection metadata over changing `trace_steps[].node` in a breaking way.

</specifics>

<deferred>
## Deferred Ideas

- Full `rag_context_build`, `VerifiedEvidencePackageV1`, `route_after_rag_context`, and claim verifier implementation belong to Phase 33.
- Approval/action payload binding to business fact refs, verified evidence refs, claim verification refs, risk decisions, and safety snapshots belongs to Phase 34.
- Full replay/eval hardening for platform decisions, including broad run visibility gates, belongs to Phase 35.
- DB constraints, RLS hardening, broad role enum cleanup, and merchant-specific policy schema belong to Phase 36+ / future hardening.
- Physical microservice extraction remains future scope after modular monolith boundaries are stable.

</deferred>

---

*Phase: 32-intent-graph-migration*
*Context gathered: 2026-06-28*
