---
status: complete
phase: 63-safety-taxonomy-and-risk-vocabulary
source:
  - .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-01-SUMMARY.md
  - .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-02-SUMMARY.md
  - .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-03-SUMMARY.md
  - .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-04-SUMMARY.md
  - .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-05-SUMMARY.md
started: 2026-07-10T05:40:00+08:00
updated: 2026-07-10T05:40:00+08:00
---

## Current Test

[testing complete]

## Tests

### 1. Safety taxonomy registry is the single owner for executable actions and dispositions

expected: The system exposes executable action ids, non-executable dispositions, action aliases, and risk vocabulary from `src.agent.safety.taxonomy`; migrated callers do not recreate local action taxonomy sources.

result: pass

evidence:
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short`
- Covered again in the post-review focused gate: `1428 passed, 1 warning`

### 2. Risk gate separates severity from disposition and blocks non-executable actions before snapshot binding

expected: `risk_level` remains a severity value, `risk_disposition` carries `manual_review` / `blocked` / approval disposition, and `manual_review`-shaped recommendations do not create `proposed_action` or approval/action binding state.

result: pass

evidence:
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/approvals/test_hash_binding.py -q --tb=short`
- Covered again in the post-review focused gate: `1428 passed, 1 warning`

### 3. Action draft invokes ToolPlatform only for executable action types

expected: `action_draft` rejects explicit non-executable dispositions such as `manual_review` / `blocked`, canonicalizes supported executable aliases such as compensation to `issue_coupon`, and preserves approval / auto-allowed binding checks before invoking `create_coupon_grant_draft`.

result: pass

evidence:
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short`
- Covered again in the post-review focused gate: `1428 passed, 1 warning`

### 4. Intent and routing safety policy derive from registries and fail closed

expected: action-bound and evidence-required routing decisions are derived from `IntentPolicyRegistry`; registry exceptions fail closed instead of allowing unsafe partial RAG or action routes.

result: pass

evidence:
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py -q --tb=short`
- Covered again in the post-review focused gate: `1428 passed, 1 warning`

### 5. Recommendation generation no longer owns a copied evidence-required intent set

expected: recommendation generation uses `INTENT_POLICY_REGISTRY.requires_evidence(...)` for evidence policy and fails closed if the registry is unavailable, so it cannot silently drift from intent routing.

result: pass

evidence:
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py -q --tb=short` -> `1263 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/recommendation_generation.py tests/agent/test_nodes/test_recommendation_generation.py` -> `All checks passed!`

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[]
