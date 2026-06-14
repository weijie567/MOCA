---
phase: 11-intent-clarification
fixed: 2026-06-14T03:46:28Z
source_review: .planning/phases/11-intent-clarification/11-REVIEW.md
status: fixed
findings_fixed:
  warning: 4
---

# Phase 11: Review Fix Report

## Summary

Manually fixed the four warnings from the deep Phase 11 code review.

## Fixes

### WR-01: Policy QA stale slot reuse

`investigate` no longer falls back to top-level `active_slots` when planning direct investigation steps. Zero-slot intents such as `policy_qa` now use only current-turn `extracted_slots`, preventing stale order/refund identifiers from being reused.

Added a graph regression test that verifies a policy question with stale `active_slots.order_id` only calls `search_policy`.

### WR-02: Safety-sensitive action slot policy

Safety-sensitive pre-route results with `requested_operation="execute_action"` now force the runtime intent boundary to `action_request` before required slots are computed. This enforces the `action_type` plus target identifier clarification policy even when the classifier labels the text as `policy_qa` or `refund_troubleshooting`.

Added routing tests for fake classifier outputs that try to classify direct execution requests as non-action intents.

### WR-03: Golden contract contradictions

Replaced contradictory hard-negative examples with semantically close but valid negatives and strengthened the executable golden contract test so it exercises runtime adapter semantics instead of only calling the precedence helper.

Golden cases now validate runtime `primary_intent`, `requested_operation`, required slots, forbidden trusted fields, and hard-negative `not_primary_intent` expectations.

### WR-04: M6 coverage hash staleness

`validate_intent_manifest` now validates `m6-statistical-gate.v1.json.coverage_manifest_hash` against the canonical hash of `coverage-manifest.v1.json`.

Added a stale M6 coverage hash regression test and refreshed the affected manifest hash chain.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/conftest.py`
  - Passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge tests/agent/test_tools tests/agent/test_policy_retrieval_ownership.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py tests/test_approval_integration.py tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_clarification_gate.py tests/agent/test_intent_manifest.py tests/agent/test_intent_golden_contract.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py -q --tb=short`
  - Passed: 286 passed, 1 warning
