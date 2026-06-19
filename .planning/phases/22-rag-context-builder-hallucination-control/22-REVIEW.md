---
phase: 22-rag-context-builder-hallucination-control
reviewed: 2026-06-19T12:50:54Z
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
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-06-19T12:50:54Z
**Depth:** deep
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Deep review covered the listed implementation, repository/service validation paths, graph routing, deterministic eval scaffold, and Phase 22 tests. The context builder and most non-allow routing paths are fail-closed, but two recommendation-verification paths can still synthesize an `allow` route without the required authority checks. One additional edge case can let an invalid duplicate evidence ref suppress a valid tenant ref before validation.

## Critical Issues

### CR-01: Failed action dependencies can be aggregated as `supported` and routed `allow`

**File:** `src/agent/nodes/generate_recommendation.py:424`

**Issue:** `_verify_recommendation_with_shared_kernel()` sets the aggregate outcome to `verification_results[0].outcome.value` whenever not all claims pass. If the first policy claim is supported but the later action recommendation claim fails, for example because `claim-business-1` is missing, the aggregate outcome remains `supported`. The route map then allows it because `dependency_result_missing` is not a blocking reason in `src/agent/rag_context/routing.py:116`. I reproduced this with a supported policy claim plus an `issue_coupon` action claim with no business refs; the result was `overall_outcome: supported`, `allows_recommendation: True`, and `route: allow` with `reason_codes: ["lexical_span_supported", "dependency_result_missing"]`.

This violates the Phase 22 action boundary: an actionable recommendation can proceed without current Tool System business support.

**Fix:**
```python
# src/agent/nodes/generate_recommendation.py
blocking_results = [result for result in verification_results if not result.allows_claim]
overall = "supported" if not blocking_results else _highest_priority_blocking_outcome(blocking_results)

# At minimum, do not let the first supported claim mask later failures:
# overall = "supported" if all(result.allows_claim for result in verification_results) else next(
#     result.outcome.value for result in verification_results if not result.allows_claim
# )
```

Also add dependency failure reason codes to the route map's blocking/insufficient sets, including `dependency_result_missing`, `unsupported_dependency`, `unsupported_policy_dependency`, `unsupported_business_dependency`, `policy_dependency_not_evidence_supported`, and `business_dependency_not_tool_supported`. Add a regression test where a supported policy claim plus missing business dependency must route non-allow.

### CR-02: Missing-session compatibility path returns `supported/allow` without verification

**File:** `src/agent/nodes/generate_recommendation.py:382`

**Issue:** When `ContextBuilder` runs without a session, `_context_builder_mode()` marks the bundle as `missing_session_compat`. `_verify_recommendation_with_shared_kernel()` then returns `overall_outcome: supported` and an `allow` route for any non-empty claim list as long as citation membership passed, without canonical re-fetch, Level 1 bundle membership, Level 2 support, or business-fact authority checks. I confirmed the branch returns `supported/allow` for an unsupported policy claim with only `citation_validation={"is_valid": True}`.

This is a fail-open safety path if a caller invokes the node without `configurable.session`, and it bypasses the shared verifier kernel that Phase 22 is meant to enforce.

**Fix:**
```python
if claims and citation_validation.get("is_valid") is True and _missing_session_compat(context_bundle):
    route = determine_verification_route(
        {
            "overall_outcome": "insufficient",
            "reason_codes": ["policy_evidence_required", "context_builder_session_missing"],
        }
    )
    return _normalize_recommendation_verification(
        {
            "overall_outcome": "insufficient",
            "allows_recommendation": False,
            "route": route,
            "material_claims": _safe_material_claims(claims),
            "reason_codes": ["policy_evidence_required", "context_builder_session_missing"],
            "safe_citation_refs": [],
            "metrics": route.metrics,
        }
    )
```

Prefer removing the compatibility allowance entirely; if no canonical evidence service is available, the recommendation path should be insufficient evidence or manual review, not allow.

## Warnings

### WR-01: Dedupe can discard a valid tenant evidence ref before validation

**File:** `src/agent/rag_context/builder.py:340`

**Issue:** `_dedupe_candidates()` groups by `(doc_key, chunk_id)` before tenant validation. Since `EvidenceRefV1.evidence_id` does not include tenant, a wrong-tenant ref and a valid-tenant ref with the same doc/chunk/version/text are treated as duplicates. If the wrong-tenant ref appears first, the valid ref is excluded as `duplicate_evidence_key`, then the retained wrong-tenant ref is excluded as `tenant_mismatch`, leaving no citation even though valid evidence was present.

**Fix:** Include tenant in the dedupe key or validate/sort tenant-matching refs before duplicate collapse.

```python
def _dedupe_candidates(refs: list[EvidenceRefV1]) -> tuple[list[EvidenceRefV1], list[EvidenceTraceEntry]]:
    grouped: dict[tuple[str, str, str], list[EvidenceRefV1]] = defaultdict(list)
    for ref in refs:
        grouped[(ref.tenant_id, ref.doc_key, ref.chunk_id)].append(ref)
```

Add a regression test with wrong-tenant and valid-tenant refs sharing the same doc/chunk/version/text; the valid tenant ref should survive and the wrong tenant ref should be excluded.

---

_Reviewed: 2026-06-19T12:50:54Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
