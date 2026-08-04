---
phase: 53
slug: session-context-before-intent-and-contextual-intent-resolve
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-06
verified: 2026-07-06
---

# Phase 53 - Security

Phase 53 threat mitigation audit for session context before intent and contextual intent resolve.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user text -> safety_pre_route | Untrusted ordinary chat is classified before session context, intent, approval, action, tools, or memory authority. | user text, pre-route disposition |
| safety_pre_route -> session_context_load | Safe / safety_sensitive requests may load same-thread context before intent; unsafe approval-like chat fails closed. | routing_hints, pre_route_decision |
| session_context_load -> contextual_intent_resolve | Same-thread contextual memory becomes LLM input context before canonical intent. | tenant/user/thread-scoped session_context |
| contextual_intent_resolve -> route_after_contextual_intent | Candidate intent fields cross into deterministic route logic. | primary_intent, requested_operation, required_slots, candidate_slots, routing_hints |
| runtime traces -> graph vocabulary/API labels | Runtime and historical names are projected for API, replay, and audit display. | trace_steps, node/router vocabulary |
| retained compatibility aliases -> future migration work | Legacy names remain readable without becoming active graph authority. | classify_intent, session_memory_load, route_after_intent, intent_classification |

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-53-01-01 | Tampering / Elevation | contextual_intent_resolve adapter | mitigate | closed | `src/agent/nodes/contextual_intent_resolve.py:76` allowlists forbidden authority fields and filters updates at `:444`; tests assert forbidden fields absent in `tests/agent/test_nodes/test_contextual_intent_resolve.py:70` and `tests/agent/test_intent_adapter.py:39`. |
| T-53-01-02 | Spoofing / Elevation | route_after_contextual_intent | mitigate | closed | `src/agent/routing.py:77` fail-closed wrapper allowlists route values; `_route_after_contextual_intent` rejects `approval_decision` at `src/agent/routing.py:279`; tests cover approval-decision to `clarification_gate` in `tests/test_graph_routing.py:360`. |
| T-53-01-03 | Reliability / Route Drift | 53-01 staging boundary | mitigate | closed | `53-01-SUMMARY.md:34` and `:84` document non-active `route_after_contextual_intent` and preserved active values until 53-02; 53-02 performs atomic cutover per `53-02-SUMMARY.md:51` and source graph path at `src/agent/graph.py:282`. |
| T-53-01-04 | Repudiation | classification_trace | mitigate | closed | Canonical traces contain `route_decision` but no `pre_route_decision` in `src/agent/nodes/contextual_intent_resolve.py:407`; tests assert absence at `tests/agent/test_nodes/test_contextual_intent_resolve.py:63`, `:116`, and `:145`; scan for `pre_route_decision` in canonical node returned no output. |
| T-53-01-05 | Information Disclosure | pending-slot short replies | mitigate | closed | Pending-slot path uses `active_flow_state` at `src/agent/nodes/contextual_intent_resolve.py:592` and returns deterministic output without LLM call; tests assert no downstream memory/RAG/approval/action/tool fields in `tests/agent/test_nodes/test_contextual_intent_resolve.py:82` and `:120`. |
| T-53-01-06 | Scope Creep | slot_resolution_gate / memory_context_load | mitigate | closed | Slot-required intents route to `extract_slots` in `src/agent/routing.py:303`; active graph maps contextual intent `extract_slots` to existing node at `src/agent/graph.py:310`; scan found no `add_node("slot_resolution_gate")` or `add_node("memory_context_load")`. |
| T-53-02-01 | Reliability / Route Drift | routing / policy / graph | mitigate | closed | Atomic active route values in `src/agent/routing.py:37`, `src/agent/intent_policy.py:15`, and graph path maps at `src/agent/graph.py:300`; architecture tests reject active `classify_intent` / `session_memory_load` at `tests/architecture/test_canonical_graph_baseline.py:19` and `:126`; active legacy scan returned no output. |
| T-53-02-02 | Information Disclosure | session_context_load before intent | mitigate | closed | `session_context_load` calls context service with tenant/user/thread/current_intent at `src/agent/nodes/session_context_load.py:88`; merchant/current-turn filtering is at `:166`; `current_intent=None` remains compatible in `src/memory/service.py:434`; tests cover pre-intent None at `tests/agent/test_session_memory_load.py:280` and wrong scope at `tests/agent/test_session_memory_integration.py:182`. |
| T-53-02-03 | Spoofing / Elevation | approval-like ordinary chat | mitigate | closed | `detect_pre_route` marks approval-like chat untrusted at `src/agent/intent_policy.py:621`; `route_after_safety` sends it to `clarification_gate` at `src/agent/routing.py:208`; graph smoke tests prove it stops before classifier/memory/tools/action in `tests/agent/test_graph.py:1097` and `:1108`. |
| T-53-02-04 | Tampering | current-turn vs inherited slots | mitigate | closed | Explicit current-turn slots override inherited session slots in `src/agent/nodes/session_context_load.py:202` and metadata marks explicit override at `:247`; integration test asserts current slot wins in `tests/agent/test_session_memory_integration.py:156`. |
| T-53-02-05 | Scope Creep | extract_slots compatibility | mitigate | closed | Active graph keeps `extract_slots` at `src/agent/graph.py:286`; architecture baseline maps `extract_slots` to `slot_resolution_gate` with delete phase Phase 54 at `tests/architecture/graph_baseline.py:51`; docs ledger Phase 54 ownership at `docs/current-langgraph-architecture.md:98`. |
| T-53-02-06 | Denial / Fail-Closed | graph edge totality | mitigate | closed | Router wrappers fail closed at `src/agent/routing.py:77` and `:85`; route-map coverage is asserted at `tests/architecture/test_canonical_graph_baseline.py:105` and `tests/agent/test_graph.py:1013`; exception/unregistered route tests pass in `tests/test_graph_routing.py:314` and `:385`. |
| T-53-03-01 | Repudiation | graph vocabulary / trace projection | mitigate | closed | Runtime entries for `contextual_intent_resolve` and `route_after_contextual_intent` are in `src/agent/graph_vocabulary.py:65` and `:134`; legacy aliases are compatibility-only at `:49` and `:75`; tests assert runtime/compat status in `tests/agent/test_graph_vocabulary.py:66` and `:105`. |
| T-53-03-02 | Information Disclosure / Audit Confusion | docs and architecture debt | mitigate | closed | Current-source docs distinguish implementation facts from target contract in `docs/current-langgraph-architecture.md:1` and ledger retained aliases at `:86`; debt ledger records Phase 53 compatibility closeout and retained aliases at `.planning/ARCHITECTURE-DEBT.md:983`. |
| T-53-03-03 | Reliability / Route Drift | artifact scans | mitigate | closed | Active graph/baseline scan for `classify_intent` / `session_memory_load` registration or route destination returned no output; validation records same at `53-VALIDATION.md:52`, `:97`, and `:105`; compatibility hits are ledgered at `53-VALIDATION.md:99`. |
| T-53-03-04 | Repudiation | duplicate pre-route trace ownership | mitigate | closed | Canonical node scan for `classification_trace.*pre_route_decision` returned no output; validation records this at `53-VALIDATION.md:98` and `:106`; contextual intent tests assert absence at `tests/agent/test_nodes/test_contextual_intent_resolve.py:63`. |
| T-53-03-05 | Scope Creep | Phase 54/55/56/57/58 aliases | mitigate | closed | Migration baseline keeps later-phase aliases owner-scoped at `tests/architecture/graph_baseline.py:51`; docs list Phase 54/55/56/57 delete phases at `docs/current-langgraph-architecture.md:98`; debt ledger records Phase 58 compatibility cleanup at `.planning/ARCHITECTURE-DEBT.md:1025`. |
| T-53-03-06 | Validation Integrity | Phase 53 artifacts | mitigate | closed | `53-VALIDATION.md:22` through `:24` use approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` commands; `53-VALIDATION.md:34` forbids bare commands; bare command scan returned no output and is recorded at `53-VALIDATION.md:100`. |

## Accepted Risks Log

No accepted risks.

## Unregistered Flags

None. No `## Threat Flags` sections were present in the Phase 53 summary files, and no additional summary threat flag required registration.

## Verification Commands

| Date | Command | Result |
|------|---------|--------|
| 2026-07-06 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_safety_pre_route.py tests/test_graph_routing.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/agent/test_intent_adapter.py -q --tb=short` | 186 passed, 1 skipped, 1 warning |
| 2026-07-06 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py -q --tb=short` | 35 passed, 8 warnings |
| 2026-07-06 | `rg -n 'classification_trace.*pre_route_decision\|pre_route_decision": pre_route\|pre_route_decision": pre_route\\.model_dump\|pre_route_decision' src/agent/nodes/contextual_intent_resolve.py` | no output |
| 2026-07-06 | `rg -n 'add_node\\("classify_intent"\|add_node\\("session_memory_load"\|"classify_intent": "classify_intent"\|"session_memory_load": "session_memory_load"' src/agent/graph.py tests/architecture/graph_baseline.py` | no output |
| 2026-07-06 | `rg -n 'session_memory_load\|classify_intent' src/agent/graph.py src/agent/intent_policy.py` | no output |
| 2026-07-06 | `rg -n 'add_node\\("slot_resolution_gate"\|add_node\\("memory_context_load"\|add_node\\("recommendation_generation"\|add_node\\("risk_gate"' src/agent/graph.py` | no output |
| 2026-07-06 | `rg -n '(^\|<automated>\\s*)(pytest\|python -m pytest)(\\s\|$)' .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/*.md` | no output |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | ASVS Level | Run By |
|------------|---------------|--------|------|------------|--------|
| 2026-07-06 | 18 | 18 | 0 | 1 | Codex security auditor |

## Sign-Off

- [x] All threats have disposition `mitigate`.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-07-06
