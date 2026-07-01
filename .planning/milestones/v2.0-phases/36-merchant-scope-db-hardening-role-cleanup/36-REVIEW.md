---
phase: 36-merchant-scope-db-hardening-role-cleanup
reviewed: 2026-06-30T14:50:49Z
depth: deep
files_reviewed: 43
files_reviewed_list:
  - docs/contract-spec.md
  - eval/replay/phase36-readiness.v1.json
  - scripts/seed_demo.py
  - src/actions/service.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/run_scope.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/auth.py
  - src/api/schemas/agent_runs.py
  - src/api/schemas/auth.py
  - src/approvals/repository.py
  - src/approvals/service.py
  - src/approvals/snapshot_service.py
  - src/approvals/snapshots.py
  - src/auth/permissions.py
  - src/business/adapters.py
  - src/db/migrations/env.py
  - src/db/migrations/versions/019_phase36_merchant_scope_hardening.py
  - src/db/models.py
  - src/integrations/demo_business/orders.py
  - src/integrations/demo_business/refunds.py
  - src/integrations/demo_business/tickets.py
  - src/platform/trusted_context.py
  - src/replay/phase36_readiness.py
  - tests/actions/test_phase34_action_draft_bindings.py
  - tests/agent/test_phase36_run_scope.py
  - tests/approvals/test_migration_contract.py
  - tests/approvals/test_phase36_scope_consistency.py
  - tests/business/test_adapters.py
  - tests/business/test_service.py
  - tests/conftest.py
  - tests/db/test_phase36_migration_preflight.py
  - tests/integration/test_auth.py
  - tests/platform/test_merchant_scope.py
  - tests/replay/test_phase35_trace_replay_permissions.py
  - tests/replay/test_phase36_readiness.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/tools/test_merchant_scope_static.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 36: Code Review Report

**Reviewed:** 2026-06-30T14:50:49Z
**Depth:** deep
**Files Reviewed:** 43
**Status:** issues_found

## Summary

Deep re-review covered the listed contract, readiness artifact, source, migration, and tests after the Phase 36 code-review-fix commit `5093ed8` and fix report `6b78feb`. The prior gap where current `business_context.facts` plus trusted refs were ignored is mostly fixed, and `last_business_context_refs` alone remains non-authoritative. One authorization-boundary warning remains: the new runtime business-context classifier accepts any trusted ref for the same resource type without proving that the fact body belongs to that specific referenced resource.

## Warnings

### WR-01: Runtime business fact scope is not bound to the referenced resource id

**File:** `src/agent/run_scope.py:263`

**Issue:** `_candidates_from_business_context()` stores trusted `BusinessFactRefV1` values by `resource_type` only, then classifies a current fact as `business_merchant` when the fact has a `merchant_id` and any trusted ref of the same type exists. It does not verify that the fact body's resource identifier matches `BusinessFactRefV1.resource_id`. A state with `business_context.facts.order.id = "order-spoofed"` and a trusted ref for `resource_id = "order-authorized"` is currently classified as `business_merchant` for the spoofed fact's merchant while persisting a target ref for the unrelated authorized order. This partially fixes the old WR-01 but widens weak authority: current facts plus trusted refs may classify business scope, but only when the fact is bound to the same resource proven by the trusted ref.

**Fix:** Bind facts to refs by both `resource_type` and resource id before creating a scope candidate. Add a regression test in `tests/agent/test_phase36_run_scope.py` where a current fact and trusted ref have the same type but different ids; it should remain `unknown_legacy` with no `target_merchant_id`.

```python
_RESOURCE_ID_KEYS = {
    "order": ("id", "order_id", "order_no"),
    "refund_case": ("id", "refund_case_id", "refund_case_no"),
    "ticket": ("id", "ticket_id", "ticket_no"),
}


def _fact_resource_id(resource_type: str, fact: Mapping[str, Any]) -> str | None:
    for key in _RESOURCE_ID_KEYS.get(resource_type, ("id",)):
        value = _non_empty_str(fact.get(key))
        if value is not None:
            return value
    return None


refs_by_key: dict[tuple[str, str], BusinessFactRefV1] = {}
for raw_ref in _list_items(context.get("business_fact_refs")):
    ref = BusinessFactRefV1.model_validate(raw_ref)
    if tenant_id is not None and ref.tenant_id == tenant_id and ref.source_system in _TRUSTED_FACT_SOURCES:
        refs_by_key.setdefault((ref.resource_type, ref.resource_id), ref)

for resource_type, fact in facts.items():
    if not isinstance(resource_type, str) or not isinstance(fact, Mapping):
        continue
    merchant_id = _non_empty_str(fact.get("merchant_id"))
    resource_id = _fact_resource_id(resource_type, fact)
    if merchant_id is None or resource_id is None:
        continue
    ref = refs_by_key.get((resource_type, resource_id))
    if ref is None:
        reason_codes.append("missing_business_fact_ref")
        continue
    ...
```

Suggested focused verification:

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py::test_business_context_fact_requires_matching_business_fact_ref_resource_id -q --tb=short`

---

_Reviewed: 2026-06-30T14:50:49Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
