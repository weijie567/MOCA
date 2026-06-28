---
phase: 33-rag-context-build-and-claim-verification
reviewed: 2026-06-28T21:51:31Z
depth: standard
files_reviewed: 55
files_reviewed_list:
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/claim_verify.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/rag_context_build.py
  - src/agent/nodes/receive_request.py
  - src/agent/rag_claim_summary.py
  - src/agent/rag_context/claims.py
  - src/agent/rag_context/domain_rules.py
  - src/agent/rag_context/schemas.py
  - src/agent/rag_context/verifier.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/agent/working_state.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/traces.py
  - src/api/schemas/agent.py
  - src/api/schemas/agent_runs.py
  - src/api/schemas/approvals.py
  - src/knowledge/schemas.py
  - src/knowledge/service.py
  - src/replay/schemas.py
  - src/replay/service.py
  - src/repositories/trace_repo.py
  - tests/agent/rag_context/test_leakage.py
  - tests/agent/rag_context/test_material_claims.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/rag_context/test_semantic_verifier.py
  - tests/agent/rag_context/test_verifier.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_claim_verify.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_nodes/test_rag_context_build.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_final_response.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_rag_context_routing.py
  - tests/agent/test_trace.py
  - tests/agent/test_working_state.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/architecture/test_phase33_rag_claim_boundaries.py
  - tests/knowledge/test_claim_verification_bundle.py
  - tests/knowledge/test_tenant_scope.py
  - tests/knowledge/test_verified_evidence_package.py
  - tests/replay/test_replay_api.py
  - tests/test_agent_runs_api.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-06-28T21:51:31Z
**Depth:** standard
**Files Reviewed:** 55
**Status:** issues_found

## Summary

Reviewed the Phase 33 source and test scope for APF-13/APF-14 contract boundaries, tenant isolation, routing, fail-closed behavior, trace/API/replay projections, and focused test coverage. The RAG package build, claim verifier service, safe summary projection, replay sanitization, and tenant-scoped API guards are generally well covered. I found two correctness gaps that can allow action-capable outputs or evidence projections to bypass the intended Phase 33 boundaries.

Tests were not executed as part of this read-only review.

## Warnings

### WR-01: Verified action recommendation claims can skip the risk and snapshot gate

**File:** `/Users/ming/projects/MOCA/src/agent/routing.py:355`
**Issue:** `_route_after_claim_verify` only routes a verified `continue` bundle into `assess_risk_and_approval` when `proposed_action` already exists or a high/critical risk signal is present. Phase 33 generation no longer owns `proposed_action`; it emits `action_recommendation` material claims from actionable drafts in `generate_recommendation.py:652-675`, and `assess_risk_and_approval` is the node that turns an actionable `recommendation_draft` into a `proposed_action`. A low or medium risk verified draft such as `issue_coupon` therefore routes directly to `final_response`, bypassing the risk node and safety snapshot creation even though APF-14 treats action recommendations as claim-gated action-capable output. Current tests cover `proposed_action` and high-risk paths, but not a verified action material claim with no existing `proposed_action`.
**Fix:**
```python
def _has_verified_action_recommendation(state: AgentState) -> bool:
    bundle = _claim_verification_bundle(state)
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result if isinstance(raw_result, dict) else {}
        if (
            result.get("claim_type") == "action_recommendation"
            and result.get("allows_action_recommendation") is True
        ):
            return True
    return _recommendation_draft_is_actionable(state)


def _route_after_claim_verify(state: AgentState) -> str:
    ...
    if _has_proposed_action(state) or _has_risk_signal(state) or _has_verified_action_recommendation(state):
        return "assess_risk_and_approval"
    return "final_response"
```
Add a regression test where `recommendation_draft.recommended_action == "issue_coupon"` and the verified bundle contains an allowed `action_recommendation` result but no `proposed_action`; the expected route should be `assess_risk_and_approval`.

### WR-02: Final response trace evidence can still be resolved from stale or candidate refs

**File:** `/Users/ming/projects/MOCA/src/agent/nodes/final_response.py:137`
**Issue:** `_final_response_evidence_refs` resolves displayed/persisted trace evidence from `state["evidence_refs"]`, `policy_evidence`, and `retrieved_evidence.evidence_refs` by `(doc_key, chunk_id)` before writing the final response trace step. `receive_request` does not reset durable `evidence_refs`, and `generate_recommendation.py:259` prepends existing state refs before the current verified refs. A stale prior-turn ref or candidate ref with the same `doc_key/chunk_id` can therefore win the `setdefault` lookup and be persisted in the final response `trace_steps`; `/agent-runs/{run_id}/evidence` later returns persisted step evidence refs. This is outside the prompt/action snapshot protections already added, but it still exposes ordinary trace/API evidence from unverified or stale state instead of the Phase 33 verified package/safe-support boundary.
**Fix:**
```python
def _state_evidence_ref_candidates(state: AgentState) -> list[dict[str, Any]]:
    safe_refs = _safe_support_refs_from_claim_bundle(state)
    if safe_refs:
        return safe_refs

    package = _verified_package_from_state(state)
    if package and package.get("status") in {"verified", "partial"}:
        evidence_map = package.get("evidence_map") or {}
        return [ref for ref in evidence_map.values() if isinstance(ref, dict)]

    return []
```
Also stop carrying old refs into the current generation result, for example by replacing `merged_refs = _merge_evidence_refs(state.get("evidence_refs"), validated_refs)` with current verified refs only, or by resetting `evidence_refs` at `receive_request` if no longer needed as durable state. Add regression coverage where stale `state["evidence_refs"]` and candidate `retrieved_evidence.evidence_refs` share the current draft citation key but must not appear in final response trace evidence or the run evidence endpoint.

---

_Reviewed: 2026-06-28T21:51:31Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
