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

### Deep review CR-01: Failed action dependencies can be aggregated as supported and routed allow

Verdict: true positive.

Fix:
- Recommendation verification now aggregates the first non-allow claim result instead of letting an earlier supported policy claim mask a later failed action dependency.
- Dependency failure reason codes now route as non-allow through the backend route map.
- Added a regression test where a supported policy claim plus missing business/action dependency must not route `allow`.

### Deep review CR-02: Missing-session compatibility path returns supported/allow without verification

Verdict: true positive.

Fix:
- Missing session now fails closed as `insufficient` with `context_builder_session_missing` and `policy_evidence_required`.
- The branch no longer exposes safe citation refs or `allows_recommendation=True`.
- Updated legacy no-session tests to assert fail-closed behavior.

### Deep review WR-01: Dedupe can discard a valid tenant evidence ref before validation

Verdict: true positive.

Fix:
- ContextBuilder duplicate collapse now groups by `(tenant_id, doc_key, chunk_id)`.
- Added a regression test proving a wrong-tenant duplicate cannot suppress the valid-tenant ref.

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

### Claude follow-up warning: Non-allow risk assessment can leave stale snapshot bindings on same-turn state merge

Verdict: true positive defensive gap, not previously confirmed as a live graph blocker.

Fix:
- `assess_risk_and_approval` now explicitly clears `action_payload_hash`, `safety_snapshot_ref`, and `safety_snapshot_hash` on non-allow verifier routes.
- Added a same-turn stale-binding regression proving old proposed action, approval, action draft, and snapshot fields are cleared after the node update is merged into state.

### Claude follow-up warning: Production eval did not cover hash/latest/freshness invalid evidence

Verdict: true positive evaluation-strength gap, and it exposed a production route-reason precision gap.

Fix:
- Recommendation verification now carries `ContextBuilder.debug_context.truncated_or_excluded_evidence.reason_codes` forward for evidence ids that the draft actually cited.
- Context-builder blocking reasons now promote generic verifier outcomes to explicit safety outcomes for hash mismatch, latest-version invalid, scope invalid, unauthorized tenant/scope, and freshness/stale evidence.
- Added a recommendation regression proving canonical `latest_version_invalid` routes `refuse` instead of generic `insufficient_evidence`.
- The production-verifier eval path now uses canonical rows, not just verified content strings, so hash/latest/freshness filtering is exercised locally.
- Added golden production-verifier cases `P22-HC-021`, `P22-HC-022`, and `P22-HC-023` for hash mismatch, latest-version invalid, and freshness/effective-at invalid evidence.

## Verification

- `uv run pytest tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_leakage.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short`
- `uv run pytest tests/agent/test_phase22_recommendation_integration.py::test_supported_policy_claim_does_not_mask_failed_action_dependency tests/agent/test_phase22_recommendation_integration.py::test_missing_session_context_builder_fails_closed_instead_of_allowing_membership_only tests/agent/rag_context/test_context_builder.py::test_wrong_tenant_duplicate_cannot_discard_valid_tenant_evidence -q --tb=short`
- `uv run pytest tests/agent/rag_context tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/test_graph_routing.py tests/test_approval_integration.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_service.py -q --tb=short`
- `uv run pytest tests/agent/test_graph.py tests/knowledge/test_facade_integration.py -q --tb=short`
- `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short`
- `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run ruff check src/agent/nodes/generate_recommendation.py src/agent/rag_context/builder.py src/agent/rag_context/routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_generate_recommendation.py`
- `uv run ruff format --check src/agent/nodes/generate_recommendation.py src/agent/rag_context/builder.py src/agent/rag_context/routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_generate_recommendation.py`
- `uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_generate_recommendation.py -q`
- `uv run pytest tests/agent/rag_context tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/knowledge/test_phase22_evidence_validation.py -q`
- `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds`
- `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short`
- `uv run ruff check .`
- `uv run ruff format --check .`

Latest results after Claude follow-up fixes:

- Focused action/recommendation regressions: `28 passed, 1 warning`.
- Phase 22 related suite: `125 passed, 1 warning`.
- Hallucination eval: `23` cases, `status: pass`, `failed_cases: []`, all blocking thresholds met.
- Full non-integration pytest: `1225 passed, 1 skipped, 6 warnings`.
- Full ruff check/format-check passed.
