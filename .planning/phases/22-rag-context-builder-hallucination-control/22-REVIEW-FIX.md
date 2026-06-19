---
phase: 22-rag-context-builder-hallucination-control
phase_number: 22
phase_name: RAG Context Builder + Hallucination Control
review_fix_date: 2026-06-19
source_review: .planning/phases/22-rag-context-builder-hallucination-control/22-REVIEW.md
status: complete
---

# Phase 22 Code Review Fixes

## Findings Addressed

### CR-01: Recommendation verification self-verifies evidence instead of the draft claim

Verdict: true positive.

Fix:
- `generate_recommendation` now builds `MaterialClaim` records from the model draft text (`reasoning_summary` / `recommended_action`), not from the cited evidence snippet.
- Actionable recommendations now add action recommendation claims and include business fact dependencies when available.
- The shared verifier path now verifies claims sequentially and passes prior dependency results into action-claim verification.
- Added a regression test proving valid citation membership alone does not allow an unsupported `issue_coupon` recommendation.

### WR-01: RAG prompt total budget is recorded but not enforced

Verdict: true positive.

Fix:
- `ContextBuilder` now enforces cumulative citation snippet budget with `RagContextBudget.max_prompt_chars`.
- Evidence that cannot fit after prompt budget exhaustion is excluded with `budget_prompt_char_limit`.
- Snippet truncation now respects tiny remaining budgets without exceeding the requested character cap.
- Added a regression test for cumulative prompt-budget enforcement.

### WR-02: Golden hallucination eval does not exercise the production verifier path

Verdict: true positive, fixed without introducing live-model or external-provider dependency.

Fix:
- `evaluate_hallucination_case` now supports a marked local production-verifier path via `evaluation_path: production_verifier`.
- That path builds a `ContextBuilder` bundle, runs `MaterialClaimVerifier`, and routes through `determine_verification_route`.
- Added golden case `P22-HC-020`, which confirms a valid citation membership plus unsupported claim text is rejected as `unsupported -> regenerate_route`.

## Verification

- `uv run pytest tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_leakage.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short`
- `uv run pytest tests/agent/rag_context tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/test_graph_routing.py tests/test_approval_integration.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_service.py -q --tb=short`
- `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds`
- `uv run ruff check src/agent/rag_context/metrics.py src/agent/rag_context/builder.py src/agent/nodes/generate_recommendation.py tests/agent/rag_context/test_budgeting.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_nodes/test_generate_recommendation.py tests/conftest.py`
- `uv run ruff format --check src/agent/rag_context/metrics.py src/agent/rag_context/builder.py src/agent/nodes/generate_recommendation.py tests/agent/rag_context/test_budgeting.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_nodes/test_generate_recommendation.py tests/conftest.py`
