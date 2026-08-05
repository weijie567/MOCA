---
phase: 54
slug: slot-resolution-gate-cutover
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-07
verified: 2026-07-07
---

# Phase 54 - Security

Phase 54 threat mitigation audit for the `slot_resolution_gate` cutover. Scope is limited to the declared Phase 54 plan threat models and summary Threat Flags.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LLM structured output -> deterministic slot resolver | LLM output is candidate/extracted input only; deterministic policy decides satisfaction and routing. | `candidate_slots`, `extracted_slots`, `slot_resolution_trace` |
| session context -> active slot inheritance | Same-thread session slots enter current-turn state only after scope, freshness, and intent checks. | tenant/user/thread scoped slot metadata |
| current user query -> invalidation/conflict detector | Current user text can invalidate or replace inherited slots and must be recorded. | invalidation phrases, current-turn slot values |
| slot gate -> fail-closed routing | Missing, stale, incompatible, conflicting, malformed, or LLM-error states must stop at clarification. | `missing_required_slots`, route decision, reason codes |
| contextual_intent_resolve -> slot_resolution_gate | Slot-required intent routes cross from intent policy into the active graph node. | intent route values, graph path map keys |
| slot_resolution_gate -> long_term_memory_retrieve | Phase 55 memory compatibility route remains reachable only after slot requirements pass and explicit memory hints exist. | reviewed/long-term memory routing hints |
| source graph -> current architecture docs | Docs and debt ledger must describe current source facts, not target-contract aspiration. | graph node set, router names, compatibility ledger |
| runtime trace/API -> historical projection | New runtime traces use canonical names; historical names remain readable without becoming authority. | trace steps, SSE node names, target projections |
| validation artifacts -> downstream verification | Phase artifacts must use approved project entrypoints and avoid scope-creep claims. | command evidence, graph scans, artifact scans |

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-54-01-01 | Elevation of Privilege | `slot_resolution_gate` LLM extraction | mitigate | closed | `slot_resolution_gate` passes LLM output into `resolve_slots_with_provenance` before writing active slots at `src/agent/nodes/slot_resolution_gate.py:61` and `:78`; resolver emits deterministic resolved/missing/route data at `src/agent/routing.py:124` and `:243`; candidate-only tests fail closed at `tests/agent/test_nodes/test_slot_resolution_gate.py:113` and `tests/agent/test_required_slots.py:497`. |
| T-54-01-02 | Information Disclosure | inherited session slots | mitigate | closed | Inherited slots call `SLOT_POLICY_REGISTRY.accepts_inherited_slot` at `src/agent/routing.py:192`; policy enforces trusted source, tenant/user/thread, invalidation, freshness, and intent compatibility at `src/agent/intent_policy.py:423`; tests cover wrong scope/stale/incompatible at `tests/agent/test_required_slots.py:89` and `:220`. |
| T-54-01-03 | Tampering | current-turn slot replacement | mitigate | closed | Current-turn slots override inherited values and record conflict provenance at `src/agent/routing.py:147` and `:167`; unresolved trusted-session conflicts are normalized and skipped at `src/agent/routing.py:183`; invalidated slots are recorded at `src/agent/routing.py:211`; tests cover replacement, unresolved conflict, and invalidation at `tests/agent/test_required_slots.py:442`, `:457`, and `:304`. |
| T-54-01-04 | Repudiation | trace/eval/replay boundary | mitigate | closed | Canonical trace node and target router are written at `src/agent/nodes/slot_resolution_gate.py:42` and `:55`; `slot_resolution_trace` includes reason-code buckets at `src/agent/routing.py:285`; tests assert canonical trace/output at `tests/agent/test_nodes/test_slot_resolution_gate.py:81`; legacy names are compatibility aliases at `src/agent/graph_vocabulary.py:94` and `:140`. |
| T-54-01-05 | Denial of Service | malformed required-slot state or router exception | mitigate | closed | `route_after_slot_resolution` catches exceptions and allowlists route values at `src/agent/routing.py:95`; required-slot mismatch/malformed state fails closed at `src/agent/routing.py:486`; tests cover mismatch and fail-closed paths at `tests/agent/test_required_slots.py:357`. |
| T-54-01-06 | Scope Creep | Phase 55/56/57/58 graph names | mitigate | closed | 54-01 deferred active graph wiring to 54-02 by plan; final Phase 54 scan confirms `slot_resolution_gate` is active while `extract_slots`, `slot_extraction`, `memory_context_load`, `recommendation_generation`, and `risk_gate` are not active nodes in `54-VALIDATION.md:116`; Phase 55/56/57/58 ownership is documented at `docs/current-langgraph-architecture.md:103` and `.planning/ARCHITECTURE-DEBT.md:1057`. |
| T-54-02-01 | Tampering / Route Drift | `routing.py`, `intent_policy.py`, `graph.py` | mitigate | closed | Route constants include `slot_resolution_gate` and slot routes at `src/agent/routing.py:38`; slot-required policy initial routes use `slot_resolution_gate` at `src/agent/intent_policy.py:141`; graph path maps align at `src/agent/graph.py:310` and `:320`; router edge tests assert totality at `tests/agent/test_graph.py:1028`. |
| T-54-02-02 | Repudiation | active graph node name | mitigate | closed | Active graph imports/registers `slot_resolution_gate` at `src/agent/graph.py:37` and `:286`, and has no active `extract_slots` node; docs record `extract_slots` as non-active compatibility only at `docs/current-langgraph-architecture.md:73` and `:99`. |
| T-54-02-03 | Elevation of Privilege | `slot_extraction` accidental graph node | mitigate | closed | Architecture test explicitly rejects `slot_extraction` registration at `tests/architecture/test_canonical_graph_baseline.py:158`; final validation scan confirms absence at `.planning/phases/54-slot-resolution-gate-cutover/54-VALIDATION.md:118`. |
| T-54-02-04 | Information Disclosure | reviewed-memory compatibility route | mitigate | closed | Slot route only reaches `long_term_memory_retrieve` after missing slots are empty and reviewed/long-term memory hints exist at `src/agent/routing.py:493` and `:501`; graph maps that route explicitly at `src/agent/graph.py:320`; integration test verifies reviewed-memory output without raw replay leakage at `tests/agent/test_graph.py:1268`. |
| T-54-02-05 | Denial of Service | router exception / unregistered route | mitigate | closed | Contextual and slot routers catch exceptions and fail closed to `clarification_gate` at `src/agent/routing.py:79` and `:95`; `_route_after_slot_resolution` also honors existing `llm_slot_extraction_error` before recomputing state at `src/agent/routing.py:462`; LLM-error regression merges state and confirms clarification at `tests/agent/test_nodes/test_slot_resolution_gate.py:245`. |
| T-54-02-06 | Scope Creep | Phase 55/56/57/58 active names | mitigate | closed | Active graph node set at `src/agent/graph.py:282` contains current Phase 54 nodes and not `memory_context_load`, `recommendation_generation`, or `risk_gate`; Phase 54 validation records the no-scope-creep scan at `54-VALIDATION.md:118`; later-phase ownership remains explicit at `.planning/ARCHITECTURE-DEBT.md:1057`. |
| T-54-03-01 | Repudiation | `graph_vocabulary.py`, trace/API projection | mitigate | closed | Runtime entries for `slot_resolution_gate` and `route_after_slot_resolution` exist at `src/agent/graph_vocabulary.py:102` and `:148`; retained legacy aliases have Phase 54 reason codes at `src/agent/graph_vocabulary.py:41`, `:94`, and `:140`; tests assert runtime/compat status at `tests/agent/test_graph_vocabulary.py:114`. |
| T-54-03-02 | Information Disclosure | SSE / trace payload labels | mitigate | closed | `NODE_MESSAGES` adds a concise canonical runtime label at `src/api/routers/agent_runs.py:56`; `_sse_event` only adds `target_node_name` projection when `node_name` is present at `src/api/routers/agent_runs.py:1138`; tests preserve legacy payload/name and assert canonical target at `tests/test_agent_runs_api.py:971` and runtime identity at `:989`. |
| T-54-03-03 | Tampering | architecture docs / debt ledger | mitigate | closed | Current architecture doc states it is a source snapshot and distinguishes target contract from current facts at `docs/current-langgraph-architecture.md:3`; Phase 54 active path and compatibility ledger are documented at `:73` and `:91`; architecture debt closeout records source/test evidence at `.planning/ARCHITECTURE-DEBT.md:1038`. |
| T-54-03-04 | Denial of Service | invalid validation commands | mitigate | closed | Final validation records approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` commands and artifact command-entrypoint scan at `54-VALIDATION.md:94` and `:116`; auditor reran the artifact entrypoint scan successfully on 2026-07-07. |
| T-54-03-05 | Scope Creep | Phase 55/56/57/58 active nodes | mitigate | closed | Final validation confirms active graph excludes `memory_context_load`, `recommendation_generation`, and `risk_gate` at `54-VALIDATION.md:118`; architecture tests keep later legacy rows scoped without enforcing Phase 58 no-debt cleanup at `tests/architecture/test_canonical_graph_baseline.py:141` and `:166`. |
| T-54-03-06 | Integrity | retained compatibility aliases | mitigate | closed | Compatibility aliases include owner, reason, trace/API projection, validation, and delete phase in docs at `docs/current-langgraph-architecture.md:99` through `:102`; debt ledger repeats retained surfaces and delete phase at `.planning/ARCHITECTURE-DEBT.md:1044`; vocabulary tests require delete-phase reason codes at `tests/agent/test_graph_vocabulary.py:136`. |

## Accepted Risks Log

No accepted risks.

Named deferrals are not open Phase 54 runtime threats:

- Phase 55 owns `long_term_memory_retrieve -> memory_context_load`; Phase 54 gates the current compatibility route behind resolved required slots and explicit memory hints.
- Phase 56 owns `generate_recommendation -> recommendation_generation`.
- Phase 57 owns `assess_risk_and_approval -> risk_gate`.
- Phase 58 owns removal or reclassification of retained `extract_slots` / `route_after_slots` compatibility surfaces.

## Unregistered Flags

None.

| Summary | Threat Flags |
|---------|--------------|
| `54-01-SUMMARY.md` | No `## Threat Flags` section found; no additional threat flag registered. |
| `54-02-SUMMARY.md` | `None. This plan did not introduce new network endpoints, auth paths, file-access patterns, or schema changes at trust boundaries.` |
| `54-03-SUMMARY.md` | `None - this plan changed vocabulary/projection labels, tests, and documentation. It introduced no new network endpoint, auth path, file access pattern, schema change, or new trust boundary beyond the threats already listed in the plan.` |

## Verification Commands

| Date | Command | Result |
|------|---------|--------|
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_session_memory_integration.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | Recorded in `54-VALIDATION.md`: 1452 passed, 1 skipped, 35 warnings. |
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q --tb=short` | Recorded in `54-VALIDATION.md`: 1 passed, 1 warning. |
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/api/routers/agent_runs.py tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py` | Recorded in `54-VALIDATION.md`: all checks passed. |
| 2026-07-07 | `rg -n "Threat ID\|T-54-" .planning/phases/54-slot-resolution-gate-cutover/54-0*-PLAN.md` | Auditor parsed 18 declared Phase 54 threats. |
| 2026-07-07 | `rg -n "slot_resolution_gate\|route_after_slot_resolution\|resolve_slots_with_provenance\|llm_slot_extraction_error\|conflicting_slots\|SLOT_POLICY_REGISTRY" src/agent/routing.py src/agent/graph.py src/agent/nodes/slot_resolution_gate.py src/agent/intent_policy.py src/agent/graph_vocabulary.py` | Auditor located mitigation anchors in implementation. |
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "...graph scope scan..."` | `54 security graph scope scan OK`. |
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "...vocabulary alias scan..."` | `54 security vocabulary alias scan OK`. |
| 2026-07-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "...artifact entrypoint scan..."` | `54 security artifact entrypoint scan OK`. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | ASVS Level | Run By | Notes |
|------------|---------------|--------|------|------------|--------|-------|
| 2026-07-07 | 18 | 18 | 0 | 1 | Codex security auditor | Created Phase 54 security artifact from three plan threat models, summaries, validation, UAT, verification, review/fix reports, source, docs, and focused static scans. |

## Sign-Off

- [x] All Phase 54 plan threats have disposition `mitigate`.
- [x] All 18 mitigations verified against source, tests, validation, review/fix, docs, or debt-ledger evidence.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] Summary Threat Flags incorporated; no unregistered flags found.
- [x] Named later-phase work is documented and does not leave current Phase 54 runtime risk open.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-07-07
