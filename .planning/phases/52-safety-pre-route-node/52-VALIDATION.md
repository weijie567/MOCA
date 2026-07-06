---
phase: 52
slug: safety-pre-route-node
status: draft
nyquist_compliant: false
wave_0_complete: false
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
  `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/test_graph_routing.py`
- **Max feedback latency:** 120 seconds for focused validation.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 52-01-01 | 01 | 1 | CAGM-03 | T-52-01 / T-52-02 | `safety_pre_route` records deterministic request-risk decisions without LLM, memory, tool, approval, or action writes | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py -q --tb=short` | MISSING W0 | pending |
| 52-01-02 | 01 | 1 | CAGM-03 | T-52-01 / T-52-03 | Untrusted approval chat, approval-bypass, and approval-like short replies route fail-closed before memory/investigate/approval/action | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | MISSING W0 | pending |
| 52-02-01 | 02 | 2 | CAGM-03 | T-52-03 | Active graph entry path is `receive_request -> safety_pre_route`, and `route_after_safety` only maps to registered graph node keys | architecture + graph routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py tests/agent/test_graph.py -q --tb=short` | EXISTS / update | pending |
| 52-02-02 | 02 | 2 | CAGM-03 | T-52-03 / T-52-04 | Phase 51 baseline is updated for active `safety_pre_route` while remaining legacy nodes stay migration-mode only | architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | EXISTS / update | pending |
| 52-03-01 | 03 | 3 | CAGM-03 | T-52-04 / T-52-05 | Compatibility left in `classify_intent` has owner, Phase 53 deletion target, trace projection, and validation coverage | docs/static | `rg -n "classify_intent|Phase 53|safety_pre_route|compatibility" .planning/phases/52-safety-pre-route-node/*.md .planning/ARCHITECTURE-DEBT.md` | EXISTS / update | pending |
| 52-03-02 | 03 | 3 | CAGM-03 | T-52-01..T-52-05 | Final focused suite and ruff pass through MOCA-approved entrypoints | integration-ish focused suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` | EXISTS / update | pending |

*Status values: pending, green, red, flaky.*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_nodes/test_safety_pre_route.py` - new focused tests for `CAGM-03` safety dispositions, forbidden writes, trace visibility, and no LLM/tool/memory calls.
- [ ] `tests/architecture/graph_baseline.py` - update current active graph baseline, route maps, and migration-mode constants for active `safety_pre_route`.
- [ ] `tests/architecture/test_canonical_graph_baseline.py` - assert Phase 52 baseline while keeping Phase 58 exact final no-debt gate skipped.
- [ ] `tests/agent/test_graph.py` / `tests/test_graph_routing.py` - update active entry-path and router totality coverage.

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

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all MISSING references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 120s.
- [ ] `nyquist_compliant: true` set in frontmatter after execution validates every CAGM-03 row.

**Approval:** pending
