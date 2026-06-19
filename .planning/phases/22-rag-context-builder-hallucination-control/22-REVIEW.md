---
phase: 22-rag-context-builder-hallucination-control
reviewed: 2026-06-19T11:57:07Z
depth: deep
files_reviewed: 35
files_reviewed_list:
  - evaluation/golden/phase22_hallucination_cases.jsonl
  - scripts/eval_phase22_hallucination.py
  - src/agent/graph.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/rag_context/__init__.py
  - src/agent/rag_context/builder.py
  - src/agent/rag_context/claims.py
  - src/agent/rag_context/metrics.py
  - src/agent/rag_context/routing.py
  - src/agent/rag_context/schemas.py
  - src/agent/rag_context/verifier.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/knowledge/retrieval.py
  - src/knowledge/service.py
  - src/repositories/policy_chunk_repo.py
  - tests/agent/rag_context/test_authority_boundaries.py
  - tests/agent/rag_context/test_budgeting.py
  - tests/agent/rag_context/test_context_builder.py
  - tests/agent/rag_context/test_leakage.py
  - tests/agent/rag_context/test_material_claims.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/rag_context/test_semantic_verifier.py
  - tests/agent/rag_context/test_verifier.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_final_response.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/conftest.py
  - tests/knowledge/test_phase21_boundaries.py
  - tests/knowledge/test_phase22_evidence_validation.py
  - tests/knowledge/test_service.py
  - tests/test_graph_routing.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-06-19T11:57:07Z
**Depth:** deep
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Deep review covered the Phase 22 RAG context builder, verifier, route mapping, recommendation/risk/action/final-response integration, golden eval scaffold, and related tests. The deterministic verifier kernel has useful low-level checks, but the recommendation integration currently bypasses the material-claim safety contract: it verifies evidence text against itself and never models action/business dependencies. Existing Phase 22 tests and eval pass despite this bypass.

Validation performed:

- `uv run pytest tests/agent/rag_context tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_service.py tests/test_graph_routing.py` passed: 145 tests.
- `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds` passed.
- A focused runtime probe showed an unsupported `issue_coupon` draft with valid citation membership routes as `allow` because the generated claim text is replaced with the cited snippet.

## Critical Issues

### CR-01: Recommendation Verification Self-Verifies Evidence Instead Of The Draft Claim

**File:** `src/agent/nodes/generate_recommendation.py:618`

**Issue:** `_material_claims_from_draft()` sets `claim_text` from `_supportable_claim_text()`, and `_supportable_claim_text()` returns the cited verifier snippet when available (`src/agent/nodes/generate_recommendation.py:627`). That means the verifier checks whether evidence text supports itself, not whether the LLM-generated `reasoning_summary` or actionable recommendation is supported. The same function only creates a `POLICY_CLAIM`, so an actionable `issue_coupon`/refund recommendation can route `allow` without a business fact claim or an action recommendation dependency check.

I confirmed this with a runtime probe: a draft saying "The merchant needs no logistics evidence and should be compensated automatically" cited evidence saying the opposite, but the claim text became "Delivered orders require verified logistics evidence before compensation" and `_verify_recommendation_with_shared_kernel()` returned `overall_outcome: supported`, `route: allow`.

**Fix:** Build material claims from the model draft, not from the evidence snippet, and include action/business dependency claims for actionable recommendations. Add a regression test in `tests/agent/test_phase22_recommendation_integration.py` that uses the real verifier path and asserts a cited-but-unsupported `reasoning_summary` plus `issue_coupon` does not route `allow`.

```python
def _material_claims_from_draft(
    draft: dict[str, Any],
    cited_evidence_ids: list[str],
    context_bundle: Any,
    business_fact_refs: list[BusinessFactRefV1],
) -> list[MaterialClaim]:
    cited = [evidence_id for evidence_id in cited_evidence_ids if not evidence_id.startswith("unresolved:")]
    claim_text = str(draft.get("reasoning_summary") or draft.get("recommended_action") or "").strip()
    if not cited or not claim_text:
        return []

    claims = [
        MaterialClaim(
            claim_id="claim-policy-1",
            claim_text=claim_text,
            authority_class=MaterialClaimAuthorityClass.POLICY_CLAIM,
            source_node="generate_recommendation",
            risk_level=draft.get("risk_level"),
            cited_evidence_ids=cited,
        )
    ]
    if _is_actionable_recommendation(draft.get("recommended_action")):
        claims.append(
            MaterialClaim(
                claim_id="claim-action-1",
                claim_text=f"{draft.get('recommended_action')}: {claim_text}",
                authority_class=MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
                source_node="generate_recommendation",
                risk_level=draft.get("risk_level"),
                cited_evidence_ids=cited,
                business_fact_refs=business_fact_refs,
                dependency_claim_ids=["claim-policy-1", "claim-business-1"],
            )
        )
    return claims
```

Also update `_verify_recommendation_with_shared_kernel()` to verify policy/business dependency results before verifying `claim-action-1`; otherwise the `MaterialClaimVerifier` action boundary remains unused by the graph integration.

## Warnings

### WR-01: RAG Prompt Total Budget Is Recorded But Not Enforced

**File:** `src/agent/rag_context/builder.py:115`

**Issue:** `RagContextBudget.max_prompt_chars` is copied into `budget_trace` but never used to limit included citations. The builder only applies `max_evidence_items` (`src/agent/rag_context/builder.py:115`) and per-snippet limits (`src/agent/rag_context/builder.py:132`). A probe with `max_prompt_chars=100`, three 80-character snippets, and `max_evidence_items=3` produced a prompt context JSON length of 946 characters while reporting `max_prompt_chars: 100`. This makes the budget trace misleading and can allow Phase 22 prompt/context surfaces to exceed the intended safety budget.

**Fix:** Apply a cumulative prompt budget before appending citations. If a citation cannot fit, either truncate it to the remaining budget or exclude it with a trace reason such as `budget_prompt_char_limit`.

```python
remaining_prompt_chars = self.budget.max_prompt_chars
for index, group in enumerate(citation_items, start=1):
    snippet, truncated = _bounded_snippet(content, min(self.budget.max_snippet_chars, remaining_prompt_chars))
    if not snippet:
        exclusions.extend(_trace(item.evidence_ref, "budget_prompt_char_limit") for item in group)
        continue
    remaining_prompt_chars -= len(snippet)
    # build PromptCitation/CitationMapEntry from the bounded snippet
```

### WR-02: Golden Hallucination Eval Does Not Exercise The Production Verifier Path

**File:** `src/agent/rag_context/metrics.py:57`

**Issue:** `evaluate_hallucination_case()` delegates to `_determine_verifier_status()`, which infers status from synthetic fields like `category`, `status`, risk hints, and claim ids rather than invoking `ContextBuilder`, `MaterialClaimVerifier`, or `generate_recommendation` integration. The Phase 22 eval passes all 19 cases even while CR-01 allows an unsupported actionable recommendation through the real shared-kernel integration. This makes the release gate a weak oracle for hallucination-control correctness.

**Fix:** Make the golden evaluator call the same implementation boundaries used by the graph. Add safe evidence text or fixture-backed canonical rows to the JSONL cases, build a `RagContextBundle`, normalize `MaterialClaim` payloads, run `MaterialClaimVerifier`, then route via `determine_verification_route()`. Include at least one integration case where valid citation membership plus unsupported `reasoning_summary` must produce `regenerate_route` or `insufficient_evidence`.

```python
async def evaluate_hallucination_case(case: Mapping[str, Any]) -> dict[str, Any]:
    claims = normalize_material_claims(case["input"]["claims"])
    bundle = await ContextBuilder(policy_service=GoldenCasePolicyService(case)).build(
        candidate_evidence_refs=golden_evidence_refs(case),
        business_fact_refs=golden_business_fact_refs(case),
        trusted_context=golden_trusted_context(case),
        risk_hints=golden_risk_hints(case),
    )
    results = [await MaterialClaimVerifier().verify_claim(claim, context_bundle=bundle) for claim in claims]
    route = determine_verification_route(combine_verifier_results(results, case))
    return hallucination_case_result_from_route(case, results, route)
```

---

_Reviewed: 2026-06-19T11:57:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
