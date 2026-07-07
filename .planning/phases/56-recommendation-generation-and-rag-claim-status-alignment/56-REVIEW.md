---
phase: 56
reviewed: "2026-07-07T10:02:49Z"
status: findings
depth: deep
files_reviewed: 27
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
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/recommendation_generation.py
  - src/agent/routing.py
  - src/api/routers/agent_runs.py
  - tests/agent/rag_context/test_routing.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_nodes/test_generate_recommendation.py
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
---

# Phase 56: Code Review Report

## Critical Issues

### CR-01: Downstream action paths can proceed without a positively verified action recommendation

**File:** `src/agent/graph.py:103`

**Issue:** Phase 56 correctly hardens `route_after_claim_verify` so a `proposed_action` requires a verified `action_recommendation` claim with `allows_action_recommendation is True` before routing to `assess_risk_and_approval` (`src/agent/routing.py:581`, `src/agent/routing.py:644`). However, the downstream graph action gate still only blocks explicit negative action claims. In `src/agent/graph.py:103-118`, `_claim_bundle_blocks_action_path` returns `False` when the bundle is `route=continue`, `overall_status=verified`, has no blocked claims, and has either an empty `claim_results` list or only non-action results. `route_after_risk` then permits `approval_gate` or `action_draft` if the risk/snapshot checks pass (`src/agent/graph.py:69-87`).

This is reachable outside the normal `claim_verify -> assess_risk_and_approval` route. A trusted approval edit can resume directly to `assess_risk_and_approval` (`src/agent/graph.py:143-156`), bypassing the newly hardened `route_after_claim_verify` predicate. The risk node uses the same negative-only action-claim check (`src/agent/nodes/assess_risk_and_approval.py:206-229`), so a verified/continue bundle with no positive action allowance can still be treated as action-safe.

**Evidence:** These probes both returned allow-like results:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.graph import _verification_allows_action_path; state={"proposed_action":{"action_type":"issue_coupon"},"claim_verification_bundle":{"overall_status":"verified","route":"continue","claim_results":[],"blocked_claims":[]}}; print(_verification_allows_action_path(state))'
# True

UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from src.agent.nodes.assess_risk_and_approval import _action_gate_block_reason; state={"proposed_action":{"action_type":"issue_coupon"},"claim_verification_bundle":{"schema_version":"claim_verification_bundle.v1","overall_status":"verified","route":"continue","claim_results":[],"blocked_claims":[],"safe_support_refs":[],"reason_codes":[],"verifier_policy_version":"claim-verifier.v1"}}; draft={"recommended_action":"issue_coupon"}; print(_action_gate_block_reason(state, draft))'
# None
```

**Fix:** Centralize the positive action allowance predicate and use it everywhere an action path is allowed, not only in `route_after_claim_verify`.

```python
def _has_allowed_action_recommendation(bundle: dict[str, Any]) -> bool:
    for raw_result in bundle.get("claim_results") or []:
        result = raw_result.model_dump(mode="python") if hasattr(raw_result, "model_dump") else raw_result
        if not isinstance(result, dict):
            continue
        claim_type = result.get("claim_type") or result.get("authority_class")
        if claim_type == "action_recommendation" and result.get("allows_action_recommendation") is True:
            return True
    return False
```

Use that helper in `route_after_claim_verify`, `src/agent/graph.py` action routing, and `assess_risk_and_approval`. For states with `proposed_action`, treat absence of a positive action recommendation as blocking. Add regression tests for `route_after_risk` and approval-edit/risk re-entry with `proposed_action` plus a verified/continue bundle that lacks an allowed action claim; those tests should route to `final_response` or produce `claim_verification_not_allow`.

## Warnings

### WR-01: CI graph-contract eval still patches legacy nodes and fails before validating the active Phase 56 graph

**File:** `scripts/eval_agent.py:416`

**Issue:** The CI eval graph-contract harness imports and patches legacy modules `classify_intent`, `extract_slots`, and `generate_recommendation` (`scripts/eval_agent.py:416-439`), but the active graph registers `contextual_intent_resolve`, `slot_resolution_gate`, and `recommendation_generation` (`src/agent/graph.py:282-290`). The expected-node list is also stale: it still expects `classify_intent`, `session_memory_load`, `extract_slots`, and always `assess_risk_and_approval` (`scripts/eval_agent.py:504-511`).

As a result, the graph-contract eval no longer reliably exercises the active graph with fake LLMs. It can fail before reaching the Phase 56 route checks, or it can pass/fail on legacy node names rather than canonical runtime behavior.

**Evidence:** Running the project-approved eval command failed all graph-contract cases before validating the Phase 56 runtime path:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_agent.py --mode ci --output /tmp/moca-agent-eval-review.json
# GRAPH-CONTRACT GS-01/GS-04/GS-07 failed:
# ImportError: Using SOCKS proxy, but the 'socksio' package is not installed.
```

The failure happens because active canonical nodes are not patched to fake LLMs in CI mode, so they instantiate real HTTP clients.

**Fix:** Update the eval harness to patch the current active modules (`contextual_intent_resolve`, `slot_resolution_gate`, canonical recommendation generation, and risk assessment) and update `_expected_nodes_for_case` to the Phase 56 active graph or the canonical `target_nodes_executed` projection. Add a small self-check that fails if graph-contract patch targets do not match the registered nodes in `build_graph`.

## Info

### IN-01: Architecture overview current graph still describes legacy entrance nodes as active

**File:** `docs/architecture-overview.md:226`

**Issue:** Section 7.2 says the current runtime entrance still uses `classify_intent`, `extract_slots`, and `long_term_memory_retrieve`, and the Mermaid diagram shows those nodes as active (`docs/architecture-overview.md:226-244`). That contradicts the actual registered graph, which uses `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, and `memory_context_load` before investigation (`src/agent/graph.py:282-290`). `docs/current-langgraph-architecture.md` already reflects the newer active graph, so this is documentation drift rather than a runtime bug.

**Fix:** Update `docs/architecture-overview.md` section 7.2 to match the registered graph and keep the old names only in compatibility or migration notes.

## Summary

Reviewed the Phase 56 source, API/SSE projection, frontend timeline projection, eval harness, architecture docs, phase artifacts, and the scoped tests at deep depth. The main Phase 56 canonicalization work is present: active routing now uses `recommendation_generation`, final response authority prioritizes canonical claim/RAG state before the gated legacy fallback, RAG partial/fail-closed routing is covered, and API/SSE/frontend/trace projections preserve the current and historical recommendation node names.

The remaining blocking safety issue is that the positive action-claim requirement is not enforced consistently after `claim_verify`. Existing tests can pass while unsupported proposed actions still pass through downstream risk/action gates via re-entry paths. The eval harness also needs repair because it still patches legacy graph nodes and currently fails before it can validate the active canonical graph.

## Verification Performed

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_agent.py --mode ci --output /tmp/moca-agent-eval-review.json` failed in `GRAPH-CONTRACT` with the stale patch-target issue described above.
- Targeted predicate probes confirmed that verified/continue bundles without positive action allowance currently pass downstream action gates.
- No source files were modified during this review.

---

_Reviewed: 2026-07-07T10:02:49Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
