---
phase: 27-trustedcontextfactory-and-projections
reviewed: "2026-06-22T17:50:10Z"
depth: deep
files_reviewed: 24
files_reviewed_list:
  - src/agent/intent_policy.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/investigate.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/routers/search.py
  - src/platform/__init__.py
  - src/platform/context_projections.py
  - src/platform/trusted_context.py
  - src/tools/executors/knowledge.py
  - tests/agent/test_intent_policy_registry.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_trusted_context_boundaries.py
  - tests/knowledge/test_tenant_scope.py
  - tests/platform/test_context_projections.py
  - tests/platform/test_merchant_scope.py
  - tests/platform/test_trusted_context.py
  - tests/platform/test_trusted_context_factory.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_execute_action.py
  - tests/test_search_integration.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-06-22T17:50:10Z
**Depth:** deep
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Reviewed Phase 27 TrustedContextFactory/projection implementation, route/node/tool seam migrations, approval resume/action draft safety paths, and the listed regression tests against APF-03/APF-04. The route and node migrations consistently derive permissions and merchant scope from canonical `trusted_context` rather than AgentState. Approval resume config is also factory-backed and action draft creation is still revalidated by the action service.

One scope-widening defect remains in the knowledge projection: canonical `MerchantScopeV1.categories` and `risk_levels` can be discarded before the knowledge service sees them. Tests cover merchant-id projection and malformed legacy values, but not restrictive category/risk dimensions.

Tests were not executed as part of this review; this report is based on source, test, and phase artifact inspection.

## Warnings

### WR-01: Knowledge Projection Drops Restrictive Merchant Scope Dimensions

**File:** `src/platform/context_projections.py:125-140`

**Issue:** `project_merchant_scope_for_knowledge()` projects a structured `MerchantScopeV1` or dict to only `merchant_ids`. If canonical trusted scope includes `categories` or `risk_levels`, `project_to_knowledge_context()` and `project_tool_context_to_knowledge_context()` discard those restrictions before calling `PolicyKnowledgeService`. Downstream knowledge retrieval only receives `KnowledgeContext.merchant_scope: list[str] | None`, so a scope like `merchant_ids=["*"], categories=["refund"], risk_levels=["high"]` becomes `["*"]`, which can authorize broader policy retrieval than the canonical scope allowed. This violates APF-04's no-widening requirement for service-safe projections.

**Fix:** Until `KnowledgeContext` can carry and enforce structured scope dimensions, fail closed when unsupported restrictive dimensions are present, and add regression tests for both API/factory projection and tool-context projection.

```python
def project_merchant_scope_for_knowledge(
    value: MerchantScopeV1 | dict[str, Any] | list[str] | None,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, MerchantScopeV1):
        if value.categories or value.risk_levels:
            return []
        return list(value.merchant_ids) if value.merchant_ids else []
    if isinstance(value, dict):
        try:
            parsed = MerchantScopeV1.model_validate(value)
        except ValueError:
            return []
        if parsed.categories or parsed.risk_levels:
            return []
        return list(parsed.merchant_ids) if parsed.merchant_ids else []
    raw_ids = value
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    if not all(isinstance(item, str) and item for item in raw_ids):
        return []
    return list(raw_ids)
```

Add a test such as `test_knowledge_projection_fails_closed_for_restrictive_scope_dimensions()` with `MerchantScopeV1(merchant_ids=["*"], categories=["refund"], risk_levels=["high"])`, and assert the projected knowledge context does not widen to `["*"]`.

---

_Reviewed: 2026-06-22T17:50:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
