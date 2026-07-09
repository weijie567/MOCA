---
phase: 63
status: fixed
fix_scope: critical_warning
iterations: 1
fixed:
  critical: 0
  warning: 1
  info: 0
  total: 1
review_path: .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-REVIEW.md
fixed_at: 2026-07-10
---

# Phase 63 Code Review Fix

## Fixed Findings

### WR-63-001: recommendation_generation still owned evidence-required intent policy

**Severity:** Warning

**Files:**
- `src/agent/nodes/recommendation_generation.py`
- `tests/agent/test_nodes/test_recommendation_generation.py`

**Issue:** Phase 63 migrated intent safety policy to `IntentPolicyRegistry`, but `recommendation_generation._policy_evidence_required_for_generation(...)` still had a hand-written evidence-required intent set. The set had already drifted from `EVIDENCE_REQUIRED_INTENTS`: `order_status_inquiry` was present in the registry and absent from the local set.

**Fix:** The helper now calls `INTENT_POLICY_REGISTRY.requires_evidence(...)` and fails closed on registry errors. Tests now prove recommendation generation consumes the registry and fails closed when the registry raises.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py -q --tb=short` -> `1263 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/recommendation_generation.py tests/agent/test_nodes/test_recommendation_generation.py` -> `All checks passed!`
