---
phase: 55
slug: memory-context-load-cutover
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 55 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_memory_evidence_boundary.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase32_static_contract.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_phase46_session_context_alignment.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_phase48_1_memory_compat_alignment.py -q --tb=short` |
| **Estimated runtime** | ~60-180 seconds focused suite, depending on local DB/service state |

---

## Sampling Rate

- **After every task commit:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_memory_evidence_boundary.py -q --tb=short`
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py -q --tb=short`
- **Before `$gsd-verify-work`:** Full focused suite and Ruff must be green.
- **Max feedback latency:** 180 seconds for focused automated feedback.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 55-01-01 | 01 | 1 | CAGM-06 | T-55-01 / T-55-02 | `memory_context_load` writes canonical metrics/usage labels and preserves `contextual_only` authority. | unit/node | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_context_load.py tests/agent/test_reviewed_memory_context_retrieve.py -q --tb=short` | ❌ W0 for `tests/agent/test_memory_context_load.py`; ✅ existing reviewed-memory tests | ⬜ pending |
| 55-01-02 | 01 | 1 | CAGM-06 | T-55-02 / T-55-03 | Memory/CWC labels cannot become evidence, business fact, approval/action, or replay authority. | boundary/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py tests/memory/test_reviewed_memory_context_boundary.py -q --tb=short` | ✅ | ⬜ pending |
| 55-02-01 | 02 | 2 | CAGM-06 | T-55-04 | Active graph registers `memory_context_load`, not `long_term_memory_retrieve`; canonical node edges to `investigate`. | architecture/static + graph smoke | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | ✅ | ⬜ pending |
| 55-02-02 | 02 | 2 | CAGM-06 | T-55-04 / T-55-05 | `route_after_slot_resolution` returns only registered route keys and uses `memory_context_load` for reviewed-memory hints. | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_routing.py tests/test_graph_routing.py -q --tb=short` | ✅ | ⬜ pending |
| 55-02-03 | 02 | 2 | CAGM-06 | T-55-06 | Phase 56/57 active legacy rows remain untouched while Phase 55 row is closed. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/memory/test_phase48_1_memory_compat_alignment.py -q --tb=short` | ✅ | ⬜ pending |
| 55-03-01 | 03 | 3 | CAGM-06 | T-55-07 | Vocabulary projects `memory_context_load` as runtime and retained `long_term_memory_retrieve` as compatibility-only with delete metadata. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/architecture/test_phase32_static_contract.py -q --tb=short` | ✅ | ⬜ pending |
| 55-03-02 | 03 | 3 | CAGM-06 | T-55-07 / T-55-08 | Trace/SSE/API projection exposes canonical target names without rewriting historical implementation names. | trace/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` | ✅ | ⬜ pending |
| 55-03-03 | 03 | 3 | CAGM-06 | T-55-09 | Phase 46/47/48/48.1 memory-layer separation remains intact. | regression/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_phase48_1_memory_compat_alignment.py -q --tb=short` | ✅ | ⬜ pending |
| 55-03-04 | 03 | 3 | CAGM-06 | T-55-10 | Phase 55 artifacts use approved MOCA command entrypoints and document retained compatibility debt. | artifact/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from pathlib import Path; bad=[str(p) for p in Path(".planning/phases/55-memory-context-load-cutover").glob("55-*.md") if any(line.strip().startswith(("pytest","python -m pytest")) for line in p.read_text().splitlines())]; assert not bad, bad'` | ✅ command defined | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_memory_context_load.py` — canonical node tests for CAGM-06: `memory_context_load` metrics, finite usage/source labels, optional legacy metric dual-write, fail-closed unavailable status, and `contextual_only` authority.
- [ ] `tests/architecture/graph_baseline.py` — baseline update removing Phase 55 `long_term_memory_retrieve` active legacy row while preserving Phase 56 `generate_recommendation` and Phase 57 `assess_risk_and_approval`.
- [ ] `tests/memory/test_phase48_1_memory_compat_alignment.py` — update compatibility guard so it preserves storage/API/config/import compatibility but no longer requires active graph `long_term_memory_retrieve`.
- [ ] Phase 55 final plan must run the artifact scanner command above and also check that docs/ledger entries record retained compatibility debt.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | CAGM-06 | All Phase 55 behaviors are backend architecture, routing, trace/API, and memory-boundary behavior with automated source/test coverage. | N/A |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
