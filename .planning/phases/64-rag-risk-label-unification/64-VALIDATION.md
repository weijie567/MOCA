---
phase: 64
slug: rag-risk-label-unification
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
updated: 2026-07-10
---

# Phase 64 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Backend framework | pytest with pytest-asyncio |
| Quick registry command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_risk_labels.py -q --tb=short` |
| Builder/recommendation command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short` |
| Verifier/routing/metrics command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py -q --tb=short` |
| Drift guard command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short` |
| Lint command | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check <changed files>` |

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| 64-TASK-01 | 01 | 1 | RAG-LABEL-01, RAG-LABEL-02 | T-64-01, T-64-02, T-64-03 | Canonical RAG label groups exist and keep existing label strings compatible. | unit/parity | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_risk_labels.py -q --tb=short` | pending |
| 64-TASK-02 | 02 | 2 | RAG-LABEL-01, RAG-LABEL-02 | T-64-04, T-64-05, T-64-06 | `manual_review_sensitive` survives builder projection and recommendation generation uses registry-owned filtering. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short` | pending |
| 64-TASK-03 | 03 | 3 | RAG-LABEL-01, RAG-LABEL-02 | T-64-07, T-64-08, T-64-09 | Verifier/routing/metrics consume shared trigger groups without changing deterministic domain rules. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py -q --tb=short` | pending |
| 64-TASK-04 | 04 | 4 | RAG-LABEL-03 | T-64-10, T-64-11, T-64-12 | Architecture guard prevents local label set source-of-truth drift from returning. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short` | pending |

## Wave 0 Requirements

- [ ] RED registry tests exist before registry implementation.
- [ ] RED builder regression proves `manual_review_sensitive` is currently filtered.
- [ ] Drift guard exists before closeout and targets migrated caller-local set assignments only.

## Manual-Only Verifications

None. Phase 64 has no UI or external-service behavior.

## Security Validation Focus

| Threat Ref | Threat | Required Automated Evidence |
|------------|--------|-----------------------------|
| T-64-01 | Registry label groups are changed without compatibility evidence. | Registry parity tests assert the exact existing label strings and registry docstring separates labels from reason codes. |
| T-64-02 | Unknown labels leak into prompt/final response contexts. | Registry and builder tests prove unknown labels are filtered. |
| T-64-03 | Future label changes become untraceable. | Registry tests document the current contract and `ARCHITECTURE-DEBT.md` records closeout. |
| T-64-04 | Label drift causes prompt projection to drop a manual-review trigger. | Builder regression proves `manual_review_sensitive` propagates. |
| T-64-05 | Prompt/final contexts leak raw debug labels. | Serialized-bundle assertions prove unknown labels are absent. |
| T-64-06 | Recommendation generation treats labels differently from verifier/routing. | Recommendation tests and shared registry groups. |
| T-64-07 | Verifier semantic-review triggers drift from registry. | Verifier tests cover registry helper use and semantic trigger labels. |
| T-64-08 | Domain-rule algorithm changes under a label cleanup phase. | Existing verifier/domain-rule tests remain green; plan explicitly forbids algorithm rewrite. |
| T-64-09 | Route/eval semantics drift from registry. | Routing/metrics tests and registry-owned route/metric trigger groups. |
| T-64-10 | Future contributors reintroduce local source-of-truth sets. | Architecture/static drift guard. |
| T-64-11 | Architecture debt history omits residual Phase 65 display/trace label work. | `.planning/ARCHITECTURE-DEBT.md` records the fix and named deferral. |
| T-64-12 | Validation artifacts expose sensitive tenant/customer content. | Summaries include file paths and command results only. |

## Validation Sign-Off

- [ ] All Phase 64 plans have a focused test lane.
- [ ] Final focused command is green.
- [ ] `nyquist_compliant` updated to `true` only after final verification.
