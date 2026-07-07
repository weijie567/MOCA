---
phase: 56-recommendation-generation-and-rag-claim-status-alignment
reviewed: "2026-07-07T10:22:41Z"
depth: deep
files_reviewed: 30
files_reviewed_list:
  - README.md
  - docs/architecture-overview.md
  - docs/current-langgraph-architecture.md
  - docs/rag-architecture-spec.md
  - docs/target-agent-platform-architecture-plan.md
  - frontend/src/components/timeline/TimelineStep.tsx
  - scripts/eval_agent.py
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/recommendation_generation.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_phase22_final_response.py
  - tests/agent/test_phase22_recommendation_integration.py
  - tests/agent/test_rag_context_routing.py
  - tests/agent/test_trace.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
  - tests/test_agent_runs_api.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 56: Code Review Report

**Reviewed:** 2026-07-07T10:22:41Z
**Depth:** deep
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Reviewed the Phase 56 re-review scope at deep depth, including the listed files plus `src/agent/nodes/action_draft.py` as the downstream action-creation boundary needed to verify the previous CR-01 end to end.

The first fix pass did repair the previous WR-01: `scripts/eval_agent.py` now patches active Phase 56 graph nodes, self-checks patch targets against registered graph nodes, and `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_agent.py --mode ci --output /tmp/moca-agent-eval-rereview.json` passed.

The previous CR-01 is only partially fixed. `route_after_risk` and `assess_risk_and_approval` now require a positive `allows_action_recommendation is True`, but the final `action_draft` node still allows a verified/continue claim bundle with no positive action claim. The fix also introduced a routing regression for low-risk verified action recommendations.

## Critical Issues

### CR-01: Final action draft boundary still does not require a positive action recommendation claim

**File:** `src/agent/nodes/action_draft.py:146`

**Issue:** `action_draft` remains the final boundary before creating a durable action draft, but `_claim_bundle_blocks_action()` only blocks explicit negative action-claim results. After route/status/blocked-claim checks, line 158 returns `_action_claim_result_disallows_action(bundle)`, and `_action_claim_result_disallows_action()` only returns `True` when an `action_recommendation` claim has `allows_action_recommendation is False`. A verified/continue bundle with no action claim, or only non-action claims, therefore passes this boundary.

The graph/risk portions of the first CR-01 fix are working:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.graph import _verification_allows_action_path; state={"proposed_action":{"action_type":"issue_coupon"},"claim_verification_bundle":{"overall_status":"verified","route":"continue","claim_results":[],"blocked_claims":[]}}; print(_verification_allows_action_path(state))'
# False

UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.nodes.assess_risk_and_approval import _action_gate_block_reason; state={"proposed_action":{"action_type":"issue_coupon"},"claim_verification_bundle":{"schema_version":"claim_verification_bundle.v1","overall_status":"verified","route":"continue","claim_results":[],"blocked_claims":[],"safe_support_refs":[],"reason_codes":[],"verifier_policy_version":"claim-verifier.v1"}}; draft={"recommended_action":"issue_coupon"}; print(_action_gate_block_reason(state, draft))'
# claim_verification_not_allow
```

But the same claim state still passes the action-draft-local gate:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.nodes.action_draft import _verification_blocks_action; state={"proposed_action":{"action_type":"issue_coupon"},"claim_verification_bundle":{"schema_version":"claim_verification_bundle.v1","overall_status":"verified","route":"continue","claim_results":[],"blocked_claims":[],"safe_support_refs":[],"reason_codes":[],"verifier_policy_version":"claim-verifier.v1"}}; print(_verification_blocks_action(state))'
# False
```

This leaves stale approvals, direct node calls, or any future graph path into `action_draft` able to rely on approval/auto-allowed binding checks without re-validating the positive action-claim authority at the final write boundary.

**Fix:**

```python
from src.agent.routing import _has_allowed_action_recommendation

def _claim_bundle_blocks_action(state: AgentState) -> bool:
    if not state.get("proposed_action"):
        return False
    bundle = _claim_verification_bundle(state)
    if bundle is None:
        return True
    if bundle.get("route") != "continue":
        return True
    if bundle.get("overall_status") not in {"verified", "not_required"}:
        return True
    if _non_empty_list(state.get("blocked_claims")) or _non_empty_list(bundle.get("blocked_claims")):
        return True
    return not _has_allowed_action_recommendation(bundle)
```

Add regression coverage in `tests/agent/test_phase22_action_boundary.py` proving `action_draft()` returns `VERIFIER_NOT_ALLOW` and does not invoke the action tool when `claim_results` is empty or contains only user-visible/non-action claims.

## Warnings

### WR-01: Positive low-risk action recommendations no longer route to risk assessment

**File:** `src/agent/routing.py:591`

**Issue:** The first CR-01 fix changed `_route_after_claim_verify()` so a positive `action_recommendation` claim only matters when `state.proposed_action` already exists. Current `recommendation_generation` does not create `proposed_action`; it creates `recommendation_draft` plus `material_claims`, and `claim_verify` returns the verified action-claim bundle. For low-risk actionable drafts, there is no existing `proposed_action` and `_has_risk_signal()` returns `False`, so the graph routes directly to `final_response` instead of `assess_risk_and_approval`.

This regresses the pre-fix behavior: the baseline routed `_has_verified_action_recommendation(state)` to `assess_risk_and_approval` even without `proposed_action`. The current behavior is reproducible:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.routing import route_after_claim_verify; state={"recommendation_draft":{"recommended_action":"issue_coupon","risk_level":"low"},"claim_verification_bundle":{"overall_status":"verified","route":"continue","claim_results":[{"claim_type":"action_recommendation","allows_action_recommendation":True}],"blocked_claims":[]}}; print(route_after_claim_verify(state))'
# final_response
```

This means the auto-allowed path tested directly in `tests/test_graph_routing.py` can still work when risk is invoked manually, but the full graph can fail to invoke risk for a verified low-risk action recommendation.

**Fix:** Keep the new safety rule for already-materialized `proposed_action`, but allow a verified action recommendation claim to enter risk so the risk node can construct the proposed action and binding.

```python
if _has_proposed_action(state):
    return "assess_risk_and_approval" if _has_verified_action_recommendation(state) else "final_response"
if _has_verified_action_recommendation(state) or _has_risk_signal(state):
    return "assess_risk_and_approval"
return "final_response"
```

Add a regression test for a low-risk `recommendation_draft` with a verified `action_recommendation` claim and no `proposed_action`; it should route to `assess_risk_and_approval`.

## Info

### IN-01: Architecture overview current graph section still describes legacy nodes as active

**File:** `docs/architecture-overview.md:226`

**Issue:** The skipped documentation drift remains materially actionable. Section 7.2 says it is describing the current `src/agent/graph.py` registered nodes and edges, but then states that the entrance still uses `classify_intent`, `extract_slots`, and `long_term_memory_retrieve`, and the Mermaid diagram shows those legacy nodes as active. That contradicts `src/agent/graph.py`, `README.md`, and `docs/current-langgraph-architecture.md`, which now show `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, and `recommendation_generation` as active runtime nodes.

**Fix:** Update `docs/architecture-overview.md` section 7.2 and the related current-implementation table rows to match `docs/current-langgraph-architecture.md`, keeping legacy names only as compatibility/migration notes.

## Verification Performed

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_phase22_action_boundary.py -q` - 94 passed, confirming the first fix pass tests still pass but do not cover the `action_draft` missing-positive-claim gap.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_agent.py --mode ci --output /tmp/moca-agent-eval-rereview.json` - PASS, confirming the previous WR-01 eval harness issue is fixed.
- Targeted probes confirmed graph/risk now block missing positive action claims, while `action_draft` still does not.
- Source scan found no hardcoded secrets, dangerous dynamic execution, debugger statements, or empty catch blocks in the reviewed source scope.
- No source files were modified during this review.

---

_Reviewed: 2026-07-07T10:22:41Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
