---
phase: 52
slug: safety-pre-route-node
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-06
---

# Phase 52 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` |
| **Estimated runtime** | ~60-120 seconds for focused suite; DB-backed suites should not be run in parallel processes |

---

## Sampling Rate

- **After every task commit:** Run the focused pytest command for the files touched by that task, always through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- **After every plan wave:** Run the full suite command above.
- **Before `$gsd-verify-work`:** Full suite plus ruff must be green:
  `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py src/agent/graph_vocabulary.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py`
- **Max feedback latency:** 120 seconds for focused validation.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 52-01-01 | 01 | 1 | CAGM-03 | T-52-01 / T-52-02 | `safety_pre_route` records deterministic request-risk decisions without LLM, memory, tool, approval, or action writes | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py -q --tb=short` | EXISTS | green |
| 52-01-02 | 01 | 1 | CAGM-03 | T-52-01 / T-52-03 | Untrusted approval chat, approval-bypass, and approval-like short replies route fail-closed before memory/investigate/approval/action | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | EXISTS | green |
| 52-02-01 | 02 | 2 | CAGM-03 | T-52-03 | Active graph entry path is `receive_request -> safety_pre_route`, and `route_after_safety` only maps to registered graph node keys | architecture + graph routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short` | EXISTS | green |
| 52-02-02 | 02 | 2 | CAGM-03 | T-52-03 / T-52-04 | Phase 51 baseline is updated for active `safety_pre_route` while remaining legacy nodes stay migration-mode only | architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | EXISTS | green |
| 52-03-01 | 03 | 3 | CAGM-03 | T-52-04 / T-52-05 | Compatibility left in `classify_intent` has owner, Phase 53 deletion target, trace projection, and validation coverage | docs/static | `rg -n '^\x7c Safe-route continuation .*safety_pre_route -> classify_intent.*classify_intent.*active graph node.*contextual_intent_resolve.*Phase 53 CAGM-04.*Architecture graph baseline.*graph tests.*Phase 53' docs/current-langgraph-architecture.md .planning/ARCHITECTURE-DEBT.md .planning/phases/52-safety-pre-route-node/52-VALIDATION.md` and `rg -n '^\x7c \x60classification_trace\.pre_route_decision.*classify_intent.*safety_pre_route.*classify_intent:pre_route.*test_graph_vocabulary\.py.*test_safety_pre_route\.py.*classifier parity tests.*Phase 53' docs/current-langgraph-architecture.md .planning/ARCHITECTURE-DEBT.md .planning/phases/52-safety-pre-route-node/52-VALIDATION.md` | EXISTS | green |
| 52-03-02 | 03 | 3 | CAGM-03 | T-52-01..T-52-05 | Final focused suite and ruff pass through MOCA-approved entrypoints | integration-ish focused suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` | EXISTS | green |

*Status values: pending, green, red, flaky.*

## Compatibility Ledger

| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
|----------------|-----------------|--------|------------------|------------|--------------|
| Safe-route continuation `safety_pre_route -> classify_intent` and `classify_intent` active graph node | `contextual_intent_resolve` / Phase 53 CAGM-04 | Phase 52 only extracts pre-route safety; session context before intent and contextual intent cutover are Phase 53 | `classify_intent` continues to project to `contextual_intent_resolve`; new `safety_pre_route` projects as runtime canonical | Architecture graph baseline + graph tests prove unsafe pre-route cases stop before `classify_intent` and safe cases use compatibility only | Phase 53 |
| `classification_trace.pre_route_decision` inside `classify_intent` | `safety_pre_route` for runtime pre-route ownership; Phase 53 removes classifier-owned duplicate | Safe-path compatibility may still need classifier trace parity until contextual intent cutover | `classify_intent:pre_route` remains a compatibility alias to `safety_pre_route`; `safety_pre_route` itself is runtime | `test_graph_vocabulary.py`, `test_safety_pre_route.py`, and classifier parity tests | Phase 53 |

---

## Wave 0 Requirements

- [x] `tests/agent/test_nodes/test_safety_pre_route.py` - new focused tests for `CAGM-03` safety dispositions, forbidden writes, trace visibility, and no LLM/tool/memory calls.
- [x] `tests/architecture/graph_baseline.py` - update current active graph baseline, route maps, and migration-mode constants for active `safety_pre_route`.
- [x] `tests/architecture/test_canonical_graph_baseline.py` - assert Phase 52 baseline while keeping Phase 58 exact final no-debt gate skipped.
- [x] `tests/agent/test_graph.py` / `tests/test_graph_routing.py` - update active entry-path and router totality coverage.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | CAGM-03 | All Phase 52 behaviors should have automated unit, graph, architecture, or static-doc coverage | N/A |

---

## Threat References

| Threat | STRIDE | Expected Mitigation |
|--------|--------|---------------------|
| T-52-01: ordinary-chat approval command such as `approve APR-1` | Elevation of Privilege / Spoofing | `safety_pre_route` detects untrusted approval chat and routes to `clarification_gate` or explicit deterministic refusal before `classify_intent`, memory, approval, or action |
| T-52-02: standalone approval/action short reply such as `同意`, `approve`, or `do it` | Elevation of Privilege | Reuse current approval-like short-reply guard and fail closed before downstream paths |
| T-52-03: router returns an unregistered or wrong legacy destination | Tampering / Denial of Service | `route_after_safety` allowlist and architecture tests prove route values are covered by graph path map and registered nodes |
| T-52-04: safety decision hidden only inside classifier trace | Repudiation | New canonical `safety_pre_route` trace-visible decision plus graph vocabulary/projection coverage |
| T-52-05: unsafe input reaches memory or investigation before fail-closed decision | Information Disclosure / Elevation of Privilege | Active graph path inserts `safety_pre_route` immediately after `receive_request`, with graph/no-tool tests |

---

## Nyquist Coverage Closeout

| Coverage | Evidence | Status |
|----------|----------|--------|
| Pre/post parity | Plan 52-01 and 52-02 summaries preserve safe-path behavior while moving pre-route ownership to `safety_pre_route`; final suite includes classifier parity tests and graph smoke tests. | green |
| Negative control tests | Ordinary supported requests and safety-sensitive supported requests continue through safe Phase 52 compatibility; unsafe approval-like inputs fail closed before classifier. | green |
| Static graph guardrails | `tests/architecture` verifies active `safety_pre_route`, direct entry edge, route maps, registered path maps, migration-mode legacy nodes, and Phase 58 final no-debt skip. | green |
| Fail-closed router behavior | `tests/test_graph_routing.py` covers `route_after_safety` safe continuation, unsafe dispositions, malformed state, exceptions, and unregistered route fallback. | green |
| No authority fields | `tests/agent/test_nodes/test_safety_pre_route.py` proves `safety_pre_route` writes only pre-route/routing/trace fields and never approval/action authority fields. | green |
| No memory/tool/approval/action side effects | `tests/agent/test_graph.py` proves untrusted approval chat and short approval replies stop before memory, investigate, approval, action, tool calls, or RAG events. | green |
| Trace vocabulary | `tests/agent/test_graph_vocabulary.py` proves real `safety_pre_route` projects as runtime while `classify_intent:pre_route` remains a temporary compatibility alias. | green |
| Compatibility documentation | `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`, and this validation artifact carry both Phase 53 compatibility rows. | green |

## Final Command Evidence

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` -> `234 passed, 2 skipped, 27 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py src/agent/graph_vocabulary.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py` -> `All checks passed!`
- `bash -lc "! rg -n '([<]automated[>][[:space:]]*(pytest([[:space:]]|$)|python -m pytest([[:space:]]|$))|^[[:space:]]*(pytest([[:space:]]|$)|python -m pytest([[:space:]]|$)))' .planning/phases/52-safety-pre-route-node/*.md"` -> no matches
- `git diff --check -- src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py src/agent/graph_vocabulary.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py docs/current-langgraph-architecture.md .planning/ARCHITECTURE-DEBT.md .planning/phases/52-safety-pre-route-node/52-VALIDATION.md` -> passed after validation closeout edit

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all MISSING references.
- [x] No watch-mode flags.
- [x] Feedback latency < 120s.
- [x] `nyquist_compliant: true` set in frontmatter after execution validates every CAGM-03 row.

**Approval:** complete
