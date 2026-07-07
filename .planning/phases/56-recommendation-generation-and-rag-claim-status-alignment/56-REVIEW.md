---
phase: 56-recommendation-generation-and-rag-claim-status-alignment
reviewed: 2026-07-07T10:55:07Z
depth: deep
files_reviewed: 31
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
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 56: Code Review Report

**Reviewed:** 2026-07-07T10:55:07Z
**Depth:** deep
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Reviewed the Phase 56 graph/node rename, RAG context routing, claim verification action boundary, API trace projection, frontend timeline rendering, eval harness, and the listed regression tests. The canonical graph rename to `recommendation_generation` is consistently wired through the graph, API step payloads, vocabulary aliasing, architecture baseline, and trace tests.

The review found one current user-visible safety regression: a draft with `missing_info` can bypass claim verification and still render as a completed actionable recommendation. It also found one guard-drift risk between the router and the recommendation node's direct compatibility surface, plus one CI/eval coverage gap around approved action drafting.

Static review was supplemented with this MOCA-approved minimal reproduction for the primary issue:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
import asyncio
from src.agent.routing import route_after_recommendation
from src.agent.nodes.final_response import final_response

state = {
    "recommendation_draft": {
        "recommended_action": "issue_coupon",
        "reasoning_summary": "Needs compensation but customer/order context is missing.",
        "evidence_refs": [],
        "missing_info": ["refund_case_id"],
        "risk_level": "low",
    },
    "current_intent": "compensation_suggestion",
    "requested_operation": "draft_action",
}
print("route=" + route_after_recommendation(state))
result = asyncio.run(final_response(state))
print("status=" + result["llm_outputs"]["final_response"]["final_status"])
print(result["final_response"].splitlines()[0])
PY
```

Observed result: `route=final_response`, `status=completed`, followed by an actionable recommendation.

## Warnings

### WR-01: Missing-info drafts can render as completed action recommendations without claim verification

**File:** `src/agent/routing.py:570`

**Issue:** `_route_after_recommendation` returns `final_response` immediately when `_recommendation_missing_info(state)` is true. That means a draft with an actionable `recommended_action` and non-empty `missing_info` skips `claim_verify` even if the recommendation contains a proposed business action. `final_response` then only treats `retrieval_error`, `insufficient_evidence`, and `citation_invalid` as safe incomplete states before falling through to `_completed_response` at `src/agent/nodes/final_response.py:903`. The reproduced state returns `final_status=completed` and displays the action recommendation despite missing required context.

This is a correctness and safety-boundary regression: missing context should block or downgrade an actionable recommendation, not mark it completed.

**Fix:** Normalize missing-info recommendation drafts to an insufficient/manual-review terminal state before final rendering, or make `final_response` fail closed for any displayable `missing_info` before `_completed_response`.

One small local guard would be:

```python
# src/agent/nodes/final_response.py, before the retrieval_error branch
if _displayable_missing_info(draft):
    safe_draft = {**draft, "recommended_action": "insufficient_evidence"}
    response_text = _insufficient_response_with_context(safe_draft, state.get("business_context") or {})
    response_text = _decorate_deferred_response(response_text, state)
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": {
                "response_text": response_text,
                "evidence_citations": [],
                "final_status": "insufficient_evidence",
                "mode": "deterministic-template",
                "approval_context": None,
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
```

Also add a regression test that constructs an actionable draft with `missing_info` and asserts the route/final response does not return `completed`.

### WR-02: Recommendation node partial-evidence guard is weaker than the router guard

**File:** `src/agent/nodes/generate_recommendation.py:413`

**Issue:** The graph router's partial RAG guard at `src/agent/routing.py:887` blocks partial evidence for proposed actions, action-bound intents, `approval_decision`, `draft_action`, `execute_action`, `escalate`, risk signals, high evidence-policy risk, and unsafe partial-evidence markers. The recommendation node's own `_partial_package_can_generate` only checks that evidence exists, `_action_bound_or_high_risk(state)` is false, and then allows `requested_operation == "advise"` or any `policy_qa` intent. Its `_action_bound_or_high_risk` at `src/agent/nodes/generate_recommendation.py:423` omits several router blockers, including `approval_decision`, action-bound intents, `risk_signals`, `evidence_policy` risk, and unsafe partial package indicators.

The compiled graph currently reaches this node through the stricter router, but `generate_recommendation` remains a compatibility surface and is called directly by the test suite and integration code. A direct call with a partial package and router-blocked state can therefore generate a recommendation under conditions the graph policy says must fail closed.

**Fix:** Share one partial-package eligibility helper between routing and generation, or mirror the router's full guard in `generate_recommendation.py`. The node-level helper should reject the same state classes as `routing._partial_rag_context_can_generate`.

```python
def _action_bound_or_high_risk(state: AgentState) -> bool:
    requested_operation = state.get("requested_operation")
    if requested_operation in {"approval_decision", "draft_action", "execute_action", "escalate"}:
        return True
    if (state.get("primary_intent") or state.get("current_intent")) in _ACTION_BOUND_INTENTS:
        return True
    if _non_empty_sequence(state.get("risk_signals")):
        return True
    ...
```

Add direct-node regression tests for partial packages with `approval_decision`, `risk_signals`, action-bound intents, evidence-policy high risk, and stale/conflict/rejected refs.

## Info

### IN-01: CI graph contract does not cover the approved action-draft path after the action result contract changed

**File:** `scripts/eval_agent.py:54`

**Issue:** `GRAPH_CONTRACT_CATEGORIES` only runs compiled graph contracts for `normal_policy_qa`, `refund_troubleshooting`, and `compensation_suggestion`, so CI does not exercise the approval-resume path that should reach `action_draft`. The helper for that hidden path is also stale: `_ci_action_tool_result` returns `_ci_action_result(case)["data"]` at `scripts/eval_agent.py:371`, but `_ci_action_result` only includes `draft_id` and `status` at `scripts/eval_agent.py:269`. Current `action_draft` requires a non-empty `draft_outcome` from successful tool results at `src/agent/nodes/action_draft.py:203`; without it, the node returns `invalid_response`.

Because `approval_approved` is omitted from the compiled graph contract category list, this drift would not be caught by the eval command even though `_assert_ci_routing` already has a check for approved cases at `scripts/eval_agent.py:923`.

**Fix:** Include a valid `draft_outcome.v1` payload in `_ci_action_result` or `_ci_action_tool_result`, then add `approval_approved` to `GRAPH_CONTRACT_CATEGORIES` or add a dedicated CI graph contract case that resumes an approval with `Command(resume={"decision": "approve", ...})` and asserts `action_draft` completes.

---

_Reviewed: 2026-07-07T10:55:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
