---
phase: 33
slug: rag-context-build-and-claim-verification
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-29
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short` |
| **Estimated runtime** | ~120-240 seconds focused suite |

---

## Sampling Rate

- **After every task commit:** Run the plan-local quick command for the touched boundary.
- **After state/reset changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py -q --tb=short`.
- **After graph/routing changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py -q --tb=short`.
- **After risk/action/final-response changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/architecture/test_action_draft_boundaries.py -q --tb=short`.
- **After every plan wave:** Run the full focused suite above.
- **Before `$gsd-verify-work`:** Full focused suite plus `uv run ruff check` on touched Python files and `git diff --check` must pass.
- **Invalid command guard:** Bare `pytest` and bare `python -m pytest` are invalid validation in MOCA.
- **Max feedback latency:** 4 minutes for the focused phase suite.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 33-01 | 1 | APF-13/APF-14 | T-33-01 | New package/bundle/state schemas are strict, reset per turn, and writer ownership is testable. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 33-02-01 | 33-02 | 2 | APF-13 | T-33-02 | Candidate refs are re-fetched and rejected on invalid scope/hash/version/effective-date before prompt/action surfaces. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_rag_context_build.py tests/agent/rag_context/test_context_builder.py tests/knowledge/test_phase22_evidence_validation.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 33-02-02 | 33-02 | 2 | APF-13 | T-33-03 | `route_after_rag_context` is deterministic and total over all status values. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 33-03-01 | 33-03 | 3 | APF-14 | T-33-04 | `recommendation_generation` emits `MaterialClaimV1` and does not mark claims supported. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/rag_context/test_material_claims.py -q --tb=short` | ✅ / W0 updates | ⬜ pending |
| 33-03-02 | 33-03 | 3 | APF-14 | T-33-05 | `claim_verify` writes bundle, blocked claims, and safe support refs; business facts require `BusinessFactRefV1`. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_claim_verify.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 33-04-01 | 33-04 | 4 | APF-13/APF-14 | T-33-06 | Unsupported action claims and candidate-only refs cannot reach risk, approval, action draft, or safety snapshots. | negative/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | ✅ / W0 updates | ⬜ pending |
| 33-05-01 | 33-05 | 5 | APF-13/APF-14 | T-33-07 | Trace/API/final projections expose only safe statuses/counts/refs and no raw package/debug/verifier internals. | integration/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_leakage.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/knowledge/test_verified_evidence_package.py` — package schema, status, citation/evidence maps, rejected/stale/conflict refs, and projection separation.
- [ ] `tests/knowledge/test_claim_verification_bundle.py` — bundle schema, blocked claims, safe support refs, verifier policy/config version, and route semantics.
- [ ] `tests/agent/test_nodes/test_rag_context_build.py` — node writer ownership, candidate-to-package output, invalid scope/hash fail-closed, and build-error status.
- [ ] `tests/agent/test_nodes/test_claim_verify.py` — node writer ownership, malformed verifier output fail-closed, business fact authority, and unsupported action claim blocking.
- [ ] `tests/agent/test_rag_context_routing.py` — `route_after_rag_context` totality and route semantics.
- [ ] `tests/architecture/test_phase33_rag_claim_boundaries.py` — Phase 33 static ownership checks replacing Phase 32 non-runnable guards.
- [ ] Update `tests/agent/test_graph.py`, `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, and trace/API projection tests for runnable target nodes and safe RAG/claim projections.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | APF-13/APF-14 | Phase 33 must be covered by deterministic unit/integration/static tests. | All phase behaviors have automated verification. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all MISSING references.
- [x] No watch-mode flags.
- [x] Feedback latency < 4 minutes for focused suite.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending execution
