---
phase: 53
slug: session-context-before-intent-and-contextual-intent-resolve
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-06
---

# Phase 53 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Pytest 9.0.3 with pytest-asyncio 1.3.0 in the project `uv` environment |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_adapter.py -q --tb=short` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture` |
| **Estimated runtime** | Unknown until Phase 53 test files are finalized |

---

## Sampling Rate

- **After every task commit:** Run the narrow command for the touched area, always through `UV_CACHE_DIR=/tmp/uv-cache uv run ...`.
- **After every plan wave:** Run the quick command above.
- **Before `$gsd-verify-work`:** Full focused suite, Ruff, and artifact scans must be green.
- **Max feedback latency:** Keep task-level checks focused; do not substitute bare `pytest` or bare `python -m pytest` results.

---

## Per-Task Verification Map

Task IDs will be filled by the Phase 53 plans. The planner must map every task that touches graph, routing, contextual intent, session context, vocabulary, docs, or architecture debt to at least one automated command below.

| Behavior | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Active graph order is `safety_pre_route -> session_context_load -> contextual_intent_resolve` | CAGM-04 | T-53-route-drift | Removed legacy graph nodes cannot remain active route destinations | architecture/static + graph integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | ✅ existing files updated | ✅ green |
| Active router/policy values and graph path maps cut over atomically: `route_after_safety` routes safe/safety-sensitive continuation to `session_context_load`, contextual intent routing omits active `session_memory_load`, and slot-required policy routes to `extract_slots` | CAGM-04 | T-53-route-drift | Unknown, exception, approval-chat, and low-confidence cases fail closed; no intermediate graph/path-map mismatch | router/policy/unit + graph baseline | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | ✅ existing files updated | ✅ green |
| `contextual_intent_resolve` owns canonical trace and `llm_outputs` while LLM output stays candidate-only | CAGM-04 | T-53-llm-authority | Intent LLM cannot choose graph routes, satisfy slots, load memory, verify evidence, lower risk, draft actions, or call tools | node/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` | ✅ created in Wave 0 | ✅ green |
| `classify_intent` legacy tests no longer enforce active `session_memory_load` routing or classifier-owned `pre_route_decision` | CAGM-04 | T-53-compat-regression | Retained classifier surface is compatibility-only and cannot reintroduce active route or trace ownership | compatibility/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | ✅ existing file updated | ✅ green |
| Same-thread pending-slot short replies resolve from session context without reviewed memory, RAG, approval, action, or tools | CAGM-04 | T-53-memory-authority | Bare identifiers after prior clarification use same-thread context only | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_session_memory_integration.py tests/agent/test_session_memory_load.py -q --tb=short` | ✅ existing files updated | ✅ green |
| Pre-intent `current_intent=None` does not discard trusted same-thread slots solely due to intent filtering | CAGM-04 | T-53-memory-authority | Unknown intent means pre-intent unresolved, not incompatible intent | memory/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_service.py -q --tb=short` | ✅ existing file updated | ✅ green |
| Graph vocabulary marks canonical active surfaces as runtime and retained legacy names as explicit compatibility aliases | CAGM-04 | T-53-trace-repudiation | Runtime/compat trace projection is unambiguous | vocabulary/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` | ✅ existing file updated | ✅ green |
| Retained `classify_intent` compatibility adapter preserves non-authoritative `llm_outputs["intent_classification"]` mirror while canonical active owner stays `contextual_intent_resolve` | CAGM-04 | T-53-compat-regression | Legacy output readers remain readable without reintroducing active graph authority | compatibility/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` | ✅ existing files updated | ✅ green |
| Artifact scans prove no active `classify_intent` / `session_memory_load` graph registration or route destination remains | CAGM-04 | T-53-route-drift | Compatibility hits are ledgered and not active graph authority | artifact scan | `rg -n 'add_node\\(\"classify_intent\"|add_node\\(\"session_memory_load\"|\"classify_intent\": \"classify_intent\"|\"session_memory_load\": \"session_memory_load\"' src/agent/graph.py tests/architecture/graph_baseline.py` | ✅ scan-only | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/agent/test_nodes/test_contextual_intent_resolve.py` - covers canonical active intent node name, trace owner, `llm_outputs` owner, candidate-only state writes, deterministic short-reply path, and no `classification_trace.pre_route_decision`.
- [x] `tests/agent/test_nodes/test_classify_intent.py` - update or retire legacy classifier assertions so they no longer require `session_memory_load` routing or classifier-owned `pre_route_decision`.
- [x] `tests/architecture/graph_baseline.py` - update active baseline node set and conditional edge maps from Phase 52 to Phase 53.
- [x] `tests/test_graph_routing.py` - update safety and contextual intent router expectations.
- [x] `tests/agent/test_intent_routing.py` - update policy route expectations so slot-required intents route to `extract_slots` during the atomic graph/router/policy cutover.
- [x] `tests/memory/test_session_memory_service.py` - prove `current_intent=None` pre-intent load keeps trusted same-thread slots instead of treating them as intent-incompatible.
- [x] `tests/agent/test_graph_vocabulary.py` - update runtime/compat status for `contextual_intent_resolve` and `route_after_contextual_intent`.
- [x] `tests/agent/test_intent_adapter.py` - prove retained `classify_intent` adapter still mirrors `llm_outputs["intent_classification"]` for compatibility callers.

---

## Manual-Only Verifications

All Phase 53 behaviors must have automated verification. Manual review is limited to inspecting `.planning/ARCHITECTURE-DEBT.md`, `docs/current-langgraph-architecture.md`, and plan/summary artifacts for accurate compatibility ledger wording.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency is bounded by focused task-level commands
- [x] `nyquist_compliant: true` set in frontmatter after the Phase 53 plans bind task IDs to this map

**Approval:** complete

---

## Phase 53 Closeout Evidence

- Task 1 vocabulary/API label check: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py -q --tb=short` -> `65 passed, 1 warning`.
- Task 1 Ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/api/routers/agent_runs.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py` -> pass.
- Code-review fix focused check: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` -> `21 passed, 1 warning`.
- Final focused suite after code-review fix: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_adapter.py -q --tb=short` -> `1400 passed, 2 skipped, 35 warnings`.
- Final Ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture` -> pass.
- Active graph/baseline legacy-node scan: `bash -lc "! rg -n 'add_node\\(\"classify_intent\"|add_node\\(\"session_memory_load\"|\"classify_intent\": \"classify_intent\"|\"session_memory_load\": \"session_memory_load\"' src/agent/graph.py tests/architecture/graph_baseline.py"` -> no output / pass.
- Duplicate pre-route ownership scan: `bash -lc "! rg -n 'classification_trace.*pre_route_decision|pre_route_decision\": pre_route|pre_route_decision\": pre_route\\.model_dump' src/agent/nodes/contextual_intent_resolve.py"` -> no output / pass.
- Compatibility review scan: `bash -lc "rg -n '\"session_memory_load\"|route_after_intent|classify_intent|intent_classification' src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/nodes src/api tests/architecture/graph_baseline.py tests/agent || true"` -> reviewed; hits are limited to non-active wrapper/import/test/historical label/output mirror surfaces listed in `docs/current-langgraph-architecture.md` and `.planning/ARCHITECTURE-DEBT.md`.
- Bare validation command scan: `bash -lc "! rg -n '(<''automated>[[:space:]]*(pytest|python -m pytest)([[:space:]]|$)|^[[:space:]]*(pytest|python -m pytest)([[:space:]]|$))' .planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/*.md"` -> no output / pass.

## Artifact Scan Conclusions

- Active graph order is verified in source as `receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve`.
- No active `classify_intent` or `session_memory_load` graph node / route destination remains in `src/agent/graph.py` or `tests/architecture/graph_baseline.py`.
- `contextual_intent_resolve` does not own duplicate `classification_trace.pre_route_decision`; runtime pre-route ownership remains `safety_pre_route`.
- Retained `classify_intent`, `intent_classification`, `session_memory_load`, and `route_after_intent` surfaces are compatibility-only and are ledgered for deletion no later than Phase 58.
- The retained `llm_outputs["intent_classification"]` mirror is restored only through the `classify_intent` compatibility wrapper; the canonical active output remains `llm_outputs["contextual_intent_resolve"]`.
- `extract_slots` remains intentionally Phase 54-owned compatibility and is not treated as a Phase 53 failure.
- `docs/contract-spec.md` was not edited because §9 already contains the Phase 53 target semantics; Phase 53 only updated current-source docs and ledger facts.
