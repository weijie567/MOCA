---
phase: 56
slug: recommendation-generation-and-rag-claim-status-alignment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 56 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_facade_integration.py -q --tb=short` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/knowledge src/api tests/architecture tests/agent tests/knowledge tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py` |
| **Estimated runtime** | ~60-180 seconds focused suite, depending on local DB/service state |

---

## Sampling Rate

- **After every task commit:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py -q --tb=short`
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py -q --tb=short`
- **Before `$gsd-verify-work`:** Full suite, Ruff, artifact command scan, and whitespace check must be green.
- **Max feedback latency:** 180 seconds for focused automated feedback.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 56-01-01 | 01 | 1 | CAGM-07 | T-56-01 / T-56-06 | Canonical recommendation node emits canonical trace/output identity while legacy import compatibility is explicit. | unit/node | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_phase22_recommendation_integration.py -q --tb=short` | ✅ | ⬜ pending |
| 56-02-01 | 02 | 2 | CAGM-07 | T-56-01 / T-56-05 | Active graph registers `recommendation_generation`, removes active `generate_recommendation`, and preserves Phase 57 legacy risk row. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | ✅ | ⬜ pending |
| 56-02-02 | 02 | 2 | CAGM-07 | T-56-01 | Route maps from `investigate` and `rag_context_build` target canonical `recommendation_generation` destination. | router/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py -q --tb=short` | ✅ | ⬜ pending |
| 56-03-01 | 03 | 3 | CAGM-07 | T-56-02 | Missing, unknown, malformed, stale, conflicting, unauthorized, invalid-hash, invalid-scope, no-evidence, and build-error RAG states fail closed. | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` | ✅ | ⬜ pending |
| 56-03-02 | 03 | 3 | CAGM-07 | T-56-03 / T-56-04 | Material claims, user-visible claims, and proposed actions cannot bypass `claim_verify`; proposed actions require explicit allowed action-claim support when action claims exist. | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` | ✅ | ⬜ pending |
| 56-04-01 | 04 | 4 | CAGM-07 | T-56-06 | Vocabulary/API/SSE projection exposes current-run `recommendation_generation` and historical `generate_recommendation -> recommendation_generation` compatibility. | trace/API/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` | ✅ | ⬜ pending |
| 56-04-02 | 04 | 4 | CAGM-07 | T-56-02 / T-56-04 | Final/API projection uses safe package/bundle fields and does not leak debug/verifier projections. | response/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` | ✅ | ⬜ pending |
| 56-04-03 | 04 | 4 | CAGM-07 | T-56-05 / T-56-06 | Docs/debt/phase artifacts record retained compatibility and approved command entrypoints. | docs/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from pathlib import Path; bad=[str(p) for p in Path(".planning/phases/56-recommendation-generation-and-rag-claim-status-alignment").glob("56-*.md") if any(line.strip().startswith(("pytest","python -m pytest")) for line in p.read_text().splitlines())]; assert not bad, bad'` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Add or adapt canonical node tests for `recommendation_generation` trace/output identity while keeping `generate_recommendation` import compatibility explicit.
- [ ] Update `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` to remove active legacy `generate_recommendation` while preserving `assess_risk_and_approval` as Phase 57-owned active legacy row.
- [ ] Add graph vocabulary tests for `generate_recommendation -> recommendation_generation` with Phase 56 reason codes and `DELETE_BY_PHASE_58`.
- [ ] Add claim-router negative test where `proposed_action` plus `verified/continue` bundle but no allowed action-recommendation result returns `final_response`.
- [ ] Add API/SSE/trace tests for current-run `recommendation_generation` display and legacy `generate_recommendation` historical projection.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | CAGM-07 | Phase 56 behaviors are backend graph, routing, trace/API projection, docs/debt, and validation behavior with automated source/test coverage. | N/A |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s for focused task checks
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
