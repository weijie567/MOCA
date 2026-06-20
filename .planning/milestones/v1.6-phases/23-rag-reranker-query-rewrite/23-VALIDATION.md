---
phase: 23
slug: rag-reranker-query-rewrite
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-20
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest under `uv run`, with pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py -q --tb=short` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~120 seconds for targeted knowledge suite; full suite depends on local DB/service state |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/knowledge/test_query_rewrite.py tests/knowledge/test_reranker.py tests/knowledge/test_hybrid_retrieval.py -q --tb=short` after Wave 0 files exist.
- **After every plan wave:** Run `uv run pytest tests/knowledge tests/agent/rag_context tests/test_rag_eval.py tests/test_rag_ablation_eval.py -q --tb=short` after Phase 23 eval tests exist.
- **Before `$gsd-verify-work`:** Run `uv run pytest` and the Phase 23 ablation eval command once implemented.
- **Max feedback latency:** 120 seconds for targeted loops.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | QRW-01 | T-23-01 | Rewrite plan preserves original query and bounded expansions. | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_plan_preserves_original_query -q` | No - W0 | pending |
| 23-01-02 | 01 | 1 | QRW-02 | T-23-02 | Specific, out-of-domain, unsafe, or missing-context queries skip rewrite deterministically. | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_skips_specific_out_of_domain_unsafe_or_missing_context -q` | No - W0 | pending |
| 23-01-03 | 01 | 1 | QRW-03 | T-23-01 | Rewrite output cannot widen tenant, merchant, role, doc, risk, or effective-date filters. | unit | `uv run pytest tests/knowledge/test_query_rewrite.py::test_rewrite_plan_cannot_widen_trusted_filters -q` | No - W0 | pending |
| 23-02-01 | 02 | 1 | QRW-04, BND-01 | T-23-01 | Original and rewritten channels all receive trusted filters and merge before rerank. | unit | `uv run pytest tests/knowledge/test_hybrid_retrieval.py::test_original_and_rewrite_channels_merge_before_rerank -q` | Existing file, new test needed | pending |
| 23-02-02 | 02 | 1 | QRW-05 | T-23-03 | Safe rewrite summary excludes raw prompts, raw payloads, and private reasoning. | unit | `uv run pytest tests/knowledge/test_retrieval_diagnostics.py::test_query_rewrite_summary_excludes_raw_payloads -q` | No - W0 | pending |
| 23-03-01 | 03 | 2 | RRK-01, RRK-06 | T-23-05 | Reranker preserves candidate identity and runs before `EvidenceRefV1` construction. | unit | `uv run pytest tests/knowledge/test_reranker.py::test_rerank_occurs_before_evidence_ref_construction -q` | No - W0 | pending |
| 23-03-02 | 03 | 2 | RRK-02 | T-23-04 | Default reranker is deterministic, local, and credential-free. | unit | `uv run pytest tests/knowledge/test_reranker.py::test_default_reranker_is_deterministic_and_local -q` | No - W0 | pending |
| 23-03-03 | 03 | 2 | RRK-04 | T-23-03 | Reranker inputs exclude raw internals and enforce bounded candidate text. | unit | `uv run pytest tests/knowledge/test_reranker.py::test_reranker_inputs_exclude_raw_internals_and_unbounded_text -q` | No - W0 | pending |
| 23-04-01 | 04 | 3 | RRK-03, EVAL-05 | T-23-04 | Disabled, timeout, provider error, malformed output, and budget overflow all fallback safely. | unit | `uv run pytest tests/knowledge/test_reranker.py::test_provider_adapter_disabled_timeout_error_malformed_and_budget_fallbacks -q` | No - W0 | pending |
| 23-04-02 | 04 | 3 | RRK-05, EXP-01, EXP-02 | T-23-03 | Diagnostics expose safe score components without extending evidence refs or public surfaces. | unit | `uv run pytest tests/knowledge/test_retrieval_diagnostics.py::test_rerank_diagnostics_do_not_extend_evidence_ref -q` | No - W0 | pending |
| 23-05-01 | 05 | 4 | EVAL-01, EVAL-02, EVAL-03 | T-23-04 | Ablation golden cases and metrics cover required modes, rank quality, safety, fallback, and latency. | unit/eval | `uv run pytest tests/test_rag_ablation_eval.py -q --tb=short` | No - W0 | pending |
| 23-05-02 | 05 | 4 | EVAL-04, EVAL-05 | T-23-04 | Rewrite/rerank budgets are explicit and stage failures fallback safely. | unit | `uv run pytest tests/knowledge/test_retrieval_budgets.py -q --tb=short` | No - W0 | pending |
| 23-06-01 | 06 | 5 | BND-02, BND-03, BND-04, BND-05, BND-06 | T-23-01/T-23-03/T-23-05 | Phase 21/22 boundaries remain intact and deferred Phase 17/RAG-5/UI scope remains blocked. | regression/static | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/rag_context/test_leakage.py tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_verifier.py -q --tb=short` | Yes, extend guard tests | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/knowledge/test_query_rewrite.py` — stubs for QRW-01..QRW-05.
- [ ] `tests/knowledge/test_reranker.py` — stubs for RRK-01..RRK-06.
- [ ] `tests/knowledge/test_retrieval_diagnostics.py` — stubs for EXP-01..EXP-04 and RRK-05.
- [ ] `tests/knowledge/test_retrieval_budgets.py` — stubs for EVAL-04/EVAL-05.
- [ ] `tests/test_rag_ablation_eval.py` — stubs for EVAL-01..EVAL-03.
- [ ] `tests/knowledge/test_phase21_boundaries.py` — static guard updates that allow Phase 23-owned symbols only in owned files while keeping Phase 17, RAG-5, and Policy Source Operations blocked.
- [ ] No framework install needed; pytest infrastructure already exists.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provider adapter with a real external cross-encoder/rerank service | RRK-03 | Live provider use is Phase 23 stretch only and default tests must be credential-free. | If later enabled, run provider-specific smoke with credentials outside default CI and compare fallback report. |

---

## Validation Sign-Off

- [x] All planned task groups have automated verification targets or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test files.
- [x] No watch-mode flags.
- [x] Feedback latency target under 120 seconds for targeted loops.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-20
