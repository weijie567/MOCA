---
phase: 36-merchant-scope-db-hardening-role-cleanup
reviewed: 2026-06-30T14:22:56Z
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

**Reviewed:** 2026-06-30T14:22:56Z
**Depth:** deep
**Files Reviewed:** 43
**Status:** issues_found

## Summary

Deep review covered the listed contract, readiness artifact, source, migration, and tests. The tenant/role scope hardening, migration preflights, approval/action binding checks, and readiness command guards are generally consistent. One behavioral gap remains: normal business-read runs can miss persisted `AgentRun.target_merchant_id` even when the current turn has trusted business facts.

## Warnings

### WR-01: Runtime business facts are not consumed by AgentRun scope classification

**File:** `src/agent/run_scope.py:231`

**Issue:** `classify_agent_run_scope()` only derives merchant scope from explicit target bindings or `business_fact_results` payloads. The actual runtime `investigate` node emits business proof as `business_context.facts` plus `business_context.business_fact_refs` at `src/agent/nodes/investigate.py:206`, and its `tool_results` entries are prompt summaries rather than `BusinessFactResultV1` payloads. As a result, a completed order/refund/ticket read can have validated `merchant_id` facts and `BusinessFactRefV1` refs but still persist as `unknown_legacy` with `target_merchant_id = null`. That undermines the Phase 36 readiness claim that `AgentRun.target_merchant_id` is persisted from validated business-fact proof and leaves Phase 37 same-merchant visibility without its intended primary authorization fact for ordinary read-only business runs.

**Fix:** Teach the classifier to consume the runtime business-context shape, or have `investigate` emit sanitized `BusinessFactResultV1` payloads alongside the prompt-safe context. Keep `last_business_context_refs` alone non-authoritative because it lacks the current fact body; require a current fact containing `merchant_id` plus a service-approved `BusinessFactRefV1`.

```python
def classify_agent_run_scope(state: Mapping[str, Any]) -> AgentRunScopeFacts:
    ...
    fact_candidates, fact_errors = _candidates_from_business_fact_results(state)
    context_candidates, context_errors = _candidates_from_business_context(state)
    candidates.extend(fact_candidates)
    candidates.extend(context_candidates)
    reason_codes.extend(fact_errors)
    reason_codes.extend(context_errors)


def _candidates_from_business_context(state: Mapping[str, Any]) -> tuple[list[_ScopeCandidate], list[str]]:
    context = state.get("business_context")
    if not isinstance(context, Mapping):
        return [], []

    facts = context.get("facts") if isinstance(context.get("facts"), Mapping) else {}
    refs = []
    for raw_ref in _list_items(context.get("business_fact_refs")):
        try:
            ref = BusinessFactRefV1.model_validate(raw_ref)
        except ValidationError:
            return [], ["malformed_business_fact_ref"]
        if ref.source_system in _TRUSTED_FACT_SOURCES and ref.tenant_id == state.get("tenant_id"):
            refs.append(ref)

    candidates = []
    for resource_type, fact in facts.items():
        merchant_id = _non_empty_str(fact.get("merchant_id") if isinstance(fact, Mapping) else None)
        ref = next((item for item in refs if item.resource_type == resource_type), None)
        if merchant_id and ref is not None:
            candidates.append(
                _ScopeCandidate(
                    target_merchant_id=merchant_id,
                    target_merchant_ref=TargetMerchantBindingV1(
                        target_merchant_id=merchant_id,
                        source="business_fact_ref",
                        business_fact_ref=ref.model_dump(mode="json"),
                    ).model_dump(mode="json"),
                    scope_source="business_context_business_fact_ref_v1",
                )
            )
    return candidates, []
```

Add a regression test in `tests/agent/test_phase36_run_scope.py` that passes the realistic `investigate` output shape (`business_context.facts.order.merchant_id` plus `business_context.business_fact_refs`) and expects `BUSINESS_MERCHANT`. Run with:

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/test_agent_runs_api.py -q --tb=short`

---

_Reviewed: 2026-06-30T14:22:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
