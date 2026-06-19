---
phase: 22
slug: rag-context-builder-hallucination-control
status: ready_for_planning
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-19
---

# Phase 22 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio; ruff for lint/format gates |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/agent/rag_context tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py -q` |
| **Full suite command** | `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short && uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~120 seconds for quick Phase 22 slice after Wave 0 exists; full suite may be longer |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/agent/rag_context tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py -q`
- **After every plan wave:** Run `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short && uv run ruff check .`
- **Before `$gsd-verify-work`:** Run the full suite plus `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds`
- **Max feedback latency:** 120 seconds for the focused task slice

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-W0-01 | Wave 0 | 0 | CTX-01, CTX-03, CTX-04, CTX-05 | T-22-01 / T-22-06 | Bundle creation, citation map, dedupe/merge, and protected metadata budgeting are tested before implementation proceeds. | unit | `uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py -q` | W0 required | pending |
| 22-W0-02 | Wave 0 | 0 | CLM-01 | T-22-03 | Claim DTOs reject unknown authority fields and pin required authority classes. | unit | `uv run pytest tests/agent/rag_context/test_material_claims.py -q` | W0 required | pending |
| 22-W0-03 | Wave 0 | 0 | CLM-02, CLM-03, CLM-04, CLM-05, VER-01, VER-02, VER-03 | T-22-02 / T-22-03 / T-22-04 | Claims cannot pass support without the correct current authority source. | unit | `uv run pytest tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py -q` | W0 required | pending |
| 22-W0-04 | Wave 0 | 0 | VER-04, VER-05 | T-22-05 | Semantic verifier trigger and provider failures fail closed with deterministic fake providers. | unit | `uv run pytest tests/agent/rag_context/test_semantic_verifier.py -q` | W0 required | pending |
| 22-W0-05 | Wave 0 | 0 | RTE-01, RTE-02 | T-22-04 / T-22-05 | Non-allow verifier outcomes map to safe backend routes without model choice. | unit | `uv run pytest tests/agent/rag_context/test_routing.py -q` | W0 required | pending |
| 22-W0-06 | Wave 0 | 0 | VER-06, BND-05, EVAL-04 | T-22-06 | Raw verifier/provenance/OCR/tool/debug payloads do not leak into prompt/final/memory/replay/action surfaces. | unit/static | `uv run pytest tests/agent/rag_context/test_leakage.py tests/knowledge/test_phase21_boundaries.py -q` | W0 required plus existing partial tests | pending |
| 22-W0-07 | Wave 0 | 0 | EVAL-01, EVAL-02, EVAL-03, EVAL-05 | T-22-07 | Hallucination-control golden dataset and eval script report blocking safety metrics. | eval | `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds` | W0 required | pending |
| 22-CTX | Implementation | 1 | CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06 | T-22-01 / T-22-02 / T-22-06 | Invalid evidence is excluded and only prompt-safe context is emitted. | unit/integration | `uv run pytest tests/agent/rag_context/test_context_builder.py tests/knowledge/test_phase22_evidence_validation.py -q` | after implementation | pending |
| 22-CLM-VER | Implementation | 2 | CLM-01, CLM-02, CLM-03, CLM-04, CLM-05, VER-01, VER-02, VER-03 | T-22-02 / T-22-03 / T-22-04 | Membership, support, and authority compatibility remain separate and fail closed. | unit | `uv run pytest tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py -q` | after implementation | pending |
| 22-SEM-ROUTE | Implementation | 3 | VER-04, VER-05, VER-06, RTE-01, RTE-02 | T-22-04 / T-22-05 / T-22-06 | Semantic verifier budgets, timeout, malformed output, and route decisions cannot allow unsafe claims. | unit | `uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py -q` | after implementation | pending |
| 22-GRAPH | Integration | 4 | RTE-03, RTE-04, RTE-05 | T-22-04 / T-22-05 / T-22-06 | Non-allow verification blocks recommendation-to-action and renders safe user-facing responses. | integration | `uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py -q` | after implementation | pending |
| 22-BND-EVAL | Acceptance | 5 | BND-01, BND-02, BND-03, BND-04, BND-05, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05 | T-22-01 through T-22-07 | Evidence identity, retrieval boundaries, authority separation, leakage, and metrics gates are all enforced. | static/eval | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/rag_context -q && uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds` | after implementation | pending |

---

## Wave 0 Requirements

- [ ] `tests/agent/rag_context/test_context_builder.py` - stubs and failing assertions for CTX-01 through CTX-05.
- [ ] `tests/agent/rag_context/test_budgeting.py` - protected citation metadata and budget-trace assertions for CTX-05.
- [ ] `tests/agent/rag_context/test_material_claims.py` - strict DTO and authority-class assertions for CLM-01.
- [ ] `tests/agent/rag_context/test_verifier.py` - Level 1/Level 2 and policy/business/action claim authority assertions for CLM-02 through CLM-05 and VER-01 through VER-03.
- [ ] `tests/agent/rag_context/test_authority_boundaries.py` - memory/provenance/model knowledge negative authority tests for CLM-05, BND-03, and BND-04.
- [ ] `tests/agent/rag_context/test_semantic_verifier.py` - Level 3 trigger, budget, timeout, provider-error, and malformed-output fake-provider tests for VER-04 and VER-05.
- [ ] `tests/agent/rag_context/test_routing.py` - route-matrix tests for RTE-01 and RTE-02.
- [ ] `tests/agent/rag_context/test_leakage.py` - prompt/final/memory/replay/action leakage assertions for VER-06, BND-05, and EVAL-04.
- [ ] `tests/agent/test_phase22_recommendation_integration.py` - shared kernel integration replacing node-local recommendation re-fetch logic for RTE-03.
- [ ] `tests/agent/test_phase22_action_boundary.py` - non-allow outcome blocks proposed actions, approvals, drafts, and snapshots for RTE-04.
- [ ] `tests/agent/test_phase22_final_response.py` - safe final response wording for RTE-05.
- [ ] `evaluation/golden/phase22_hallucination_cases.jsonl` - golden cases for EVAL-01 through EVAL-03 and EVAL-05.
- [ ] `scripts/eval_phase22_hallucination.py` - metrics report and threshold gate for EVAL-05.

---

## Manual-Only Verifications

All Phase 22 behaviors must have automated verification. Manual review may inspect generated eval reports, but it must not replace the blocking automated commands above.

---

## Validation Sign-Off

- [x] All planned behavior has an automated verify command or a Wave 0 dependency.
- [x] Sampling continuity: no implementation wave may have 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test/eval references before implementation tasks depend on them.
- [x] No watch-mode flags are used in validation commands.
- [x] Feedback latency target is less than 120 seconds for focused task checks.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** approved 2026-06-19 for planning
