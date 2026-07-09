---
phase: 63-safety-taxonomy-and-risk-vocabulary
reviewed: 2026-07-09T23:55:06Z
depth: deep
files_reviewed: 15
files_reviewed_list:
  - src/agent/intent_policy.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/risk_gate.py
  - src/agent/routing.py
  - src/agent/safety/__init__.py
  - src/agent/safety/taxonomy.py
  - tests/agent/test_intent_policy_registry.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_risk_gate.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_safety_taxonomy.py
  - tests/approvals/test_hash_binding.py
  - tests/architecture/test_action_draft_boundaries.py
  - tests/architecture/test_safety_taxonomy_boundaries.py
  - tests/test_execute_action.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 63: Code Review Report

**Reviewed:** 2026-07-09T23:55:06Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Deep review covered the Phase 63 safety taxonomy owner, migrated callers in `risk_gate`, `action_draft`, `intent_policy`, and `routing`, plus the listed regression and architecture tests. The shared action taxonomy is centralized and `action_draft` correctly rejects non-executable dispositions before the tool boundary. Approval/hash binding tests cover action payload and snapshot mutation paths.

Two warning-level gaps remain: claim-verification blockers are recorded as low/allow risk when no legacy verifier route is present, and executable operations can still be treated as evidence-not-required when no-evidence intents or explicit evidence-policy flags are present. Existing focused tests are green, which confirms these are uncovered regression gaps rather than currently failing tests.

## Warnings

### WR-01: Claim-verification blockers are normalized as `allow` / `low`

**File:** `src/agent/nodes/risk_gate.py:228`

**Issue:** `_blocked_verifier_risk()` derives `risk_disposition` and severity only from `_verification_route()`. For claim-bundle blockers, `_action_gate_block_reason()` passes `reason_code="claim_verification_not_allow"`, but there may be no legacy `verification_route` at all, or it may still be `"allow"`. In that case the blocked action path is recorded as `risk_disposition: "allow"` and `risk_level: "low"` even though `proposed_action`, approval, snapshot, and action state are cleared. Confirmed with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
from src.agent.nodes.risk_gate import _blocked_verifier_risk
print(_blocked_verifier_risk({"risk_assessment": {"risk_level": "high", "approval_required": True}}, "claim_verification_not_allow"))
PY
```

The current result includes `risk_disposition: "allow"` and `risk_severity: "low"`. This does not reopen `route_after_risk()` because `proposed_action` is cleared, but it corrupts the Phase 63 severity/disposition vocabulary and can mislead final-response/audit consumers.

**Fix:** Branch explicitly on `reason_code == "claim_verification_not_allow"` and derive a non-allow disposition from the claim bundle before falling back to legacy verifier routes. Add assertions to `tests/agent/test_phase22_action_boundary.py` and/or `tests/agent/test_nodes/test_risk_gate.py` for blocked claim bundles, missing positive action claims, and malformed bundles.

```python
if reason_code == "claim_verification_not_allow":
    bundle = _claim_verification_bundle(state) or {}
    hard_blocked = (
        _non_empty_list(state.get("blocked_claims"))
        or _non_empty_list(bundle.get("blocked_claims"))
        or bundle.get("overall_status") in {"blocked", "error"}
        or bundle.get("route") == "final_response"
    )
    disposition = "blocked" if hard_blocked else "manual_review"
    severity = "high" if hard_blocked else "medium"
else:
    route = _verification_route(state)
    disposition = "manual_review" if route == "manual_review" else "blocked" if route == "refuse" else "allow"
    severity = "high" if route == "refuse" else "low" if route not in {"manual_review", "refuse"} else None
```

### WR-02: Executable operations can be treated as evidence-not-required

**File:** `src/agent/intent_policy.py:1194`, `src/agent/routing.py:1115`

**Issue:** `_risk_decision_from_template()` lets intent-level `evidence_required=False` override operation-level risk templates, so `resolve_risk_decision("small_talk", "execute_action")` returns `approval_required=True` but `evidence_required=False`. `routing._policy_evidence_required()` has the same fail-open ordering: an explicit `evidence_policy={"evidence_required": False}` is trusted before checking `requested_operation in {"draft_action", "execute_action", "escalate"}`. Confirmed with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
from src.agent.intent_policy import resolve_risk_decision
from src.agent.routing import _policy_evidence_required, route_after_rag_context
print(resolve_risk_decision("small_talk", "execute_action", channel="ordinary_chat"))
state = {"primary_intent": "compensation_suggestion", "requested_operation": "execute_action", "evidence_policy": {"evidence_required": False}, "rag_context_status": "not_required"}
print(_policy_evidence_required(state), route_after_rag_context(state))
PY
```

The current result marks the executable operation as evidence-not-required and routes `rag_context_status="not_required"` to `recommendation_generation`. This violates the recommendation evidence policy for action-bound operations and is not covered by the listed intent/routing tests.

**Fix:** Make executable operations force evidence before applying intent exceptions or explicit false policy flags. Pass `requested_operation` into `_risk_decision_from_template()` and force `evidence_required=True` for `draft_action`, `execute_action`, and `escalate`; keep `approval_decision`/approval-chat as the explicit no-evidence forbidden case. In routing, check executable operations before honoring `evidence_policy` or `routing_hints` false values. Mirror the same ordering in the recommendation-generation helper that consumes the same state.

```python
ACTION_EVIDENCE_OPERATIONS = {"draft_action", "execute_action", "escalate"}

if requested_operation in ACTION_EVIDENCE_OPERATIONS:
    evidence_required = True
elif template.tier == "forbidden_in_chat":
    evidence_required = False
else:
    evidence_required = definition.evidence_required if definition is not None else template.evidence_required
```

Add regression coverage for:

- `resolve_risk_decision("small_talk", "execute_action").evidence_required is True`
- `_policy_evidence_required({"requested_operation": "execute_action", "evidence_policy": {"evidence_required": False}}) is True`
- `route_after_rag_context()` does not send executable-operation `not_required` evidence states to `recommendation_generation`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/agent/test_safety_taxonomy.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py tests/test_execute_action.py -q --tb=short` -> `1358 passed, 1 warning`
- Targeted review probes for WR-01 and WR-02 reproduced the reported behavior with `UV_CACHE_DIR=/tmp/uv-cache uv run python ...`.

---

_Reviewed: 2026-07-09T23:55:06Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
