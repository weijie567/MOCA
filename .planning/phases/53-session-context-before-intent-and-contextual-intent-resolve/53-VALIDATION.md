---
phase: 53
slug: session-context-before-intent-and-contextual-intent-resolve
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` |
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
| Active graph order is `safety_pre_route -> session_context_load -> contextual_intent_resolve` | CAGM-04 | T-53-route-drift | Removed legacy graph nodes cannot remain active route destinations | architecture/static + graph integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | ✅ existing files need updates | ⬜ pending |
| `route_after_safety` routes safe/safety-sensitive continuation to `session_context_load`; contextual intent routing omits active `session_memory_load` | CAGM-04 | T-53-route-drift | Unknown, exception, approval-chat, and low-confidence cases fail closed | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py -q --tb=short` | ✅ existing file needs updates | ⬜ pending |
| `contextual_intent_resolve` owns canonical trace and `llm_outputs` while LLM output stays candidate-only | CAGM-04 | T-53-llm-authority | Intent LLM cannot choose graph routes, satisfy slots, load memory, verify evidence, lower risk, draft actions, or call tools | node/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` | ❌ Wave 0 | ⬜ pending |
| `classify_intent` legacy tests no longer enforce active `session_memory_load` routing or classifier-owned `pre_route_decision` | CAGM-04 | T-53-compat-regression | Retained classifier surface is compatibility-only and cannot reintroduce active route or trace ownership | compatibility/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | ✅ existing file needs updates | ⬜ pending |
| Same-thread pending-slot short replies resolve from session context without reviewed memory, RAG, approval, action, or tools | CAGM-04 | T-53-memory-authority | Bare identifiers after prior clarification use same-thread context only | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_session_memory_integration.py tests/agent/test_session_memory_load.py -q --tb=short` | ✅ existing files need updates | ⬜ pending |
| Graph vocabulary marks canonical active surfaces as runtime and retained legacy names as explicit compatibility aliases | CAGM-04 | T-53-trace-repudiation | Runtime/compat trace projection is unambiguous | vocabulary/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py -q --tb=short` | ✅ existing file needs updates | ⬜ pending |
| Artifact scans prove no active `classify_intent` / `session_memory_load` graph registration or route destination remains | CAGM-04 | T-53-route-drift | Compatibility hits are ledgered and not active graph authority | artifact scan | `rg -n 'add_node\\(\"classify_intent\"|add_node\\(\"session_memory_load\"|\"classify_intent\": \"classify_intent\"|\"session_memory_load\": \"session_memory_load\"' src/agent/graph.py tests/architecture/graph_baseline.py` | ✅ scan-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_nodes/test_contextual_intent_resolve.py` - covers canonical active intent node name, trace owner, `llm_outputs` owner, candidate-only state writes, deterministic short-reply path, and no `classification_trace.pre_route_decision`.
- [ ] `tests/agent/test_nodes/test_classify_intent.py` - update or retire legacy classifier assertions so they no longer require `session_memory_load` routing or classifier-owned `pre_route_decision`.
- [ ] `tests/architecture/graph_baseline.py` - update active baseline node set and conditional edge maps from Phase 52 to Phase 53.
- [ ] `tests/test_graph_routing.py` - update safety and contextual intent router expectations.
- [ ] `tests/agent/test_graph_vocabulary.py` - update runtime/compat status for `contextual_intent_resolve` and `route_after_contextual_intent`.

---

## Manual-Only Verifications

All Phase 53 behaviors must have automated verification. Manual review is limited to inspecting `.planning/ARCHITECTURE-DEBT.md`, `docs/current-langgraph-architecture.md`, and plan/summary artifacts for accurate compatibility ledger wording.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency is bounded by focused task-level commands
- [ ] `nyquist_compliant: true` set in frontmatter after the Phase 53 plans bind task IDs to this map

**Approval:** pending
