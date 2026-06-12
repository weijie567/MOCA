---
phase: 09-business-tool-facade
reviewed: 2026-06-12T20:58:17Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - src/business_tools/__init__.py
  - src/business_tools/schemas.py
  - tests/business_tools/__init__.py
  - tests/business_tools/test_schemas.py
  - src/business_tools/registry.py
  - tests/business_tools/test_registry.py
  - src/business_tools/adapters.py
  - tests/business_tools/test_adapters.py
  - src/business_tools/service.py
  - tests/business_tools/test_service.py
  - src/agent/nodes/load_business_context.py
  - src/api/routers/agent_runs.py
  - src/agent/tools/registry.py
  - src/agent/tools/contracts.py
  - tests/agent/test_nodes/test_load_business_context.py
  - tests/agent/test_tools/test_registry.py
  - tests/agent/test_tools/test_tool_contracts.py
  - tests/agent/test_graph.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-06-12T20:58:17Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The typed business-tool facade, registry gates, adapters, and aggregation path are generally well covered, and the scoped test suite passes. Two authorization-context issues remain in the router integration: verified JWT scope restrictions are discarded when deriving tool permissions, and the newly injected structured merchant scope is incompatible with the existing policy-retrieval consumer.

## Critical Issues

### CR-01: Restricted JWT scopes are widened back to all role permissions

**File:** `src/api/routers/agent_runs.py:57-63`
**Issue:** `_trusted_tool_config` derives tool permissions exclusively from `ROLE_SCOPES[user.role]`. `get_current_user` verifies that the token includes `agent:chat`, but it does not expose the token's remaining verified scopes to this function. Consequently, a support or merchant JWT intentionally issued with only `agent:chat` can stream a run and receives `tool:get_order`, `tool:get_refund_case`, `tool:get_ticket`, and `tool:search_policy` anyway. This bypasses token-level least-privilege restrictions.
**Fix:** Preserve the verified token scopes in the authenticated principal/request context and derive tool permissions from the intersection of those scopes and the current database role's allowed scopes.

```python
trusted_scopes = set(principal.token_scopes) & set(ROLE_SCOPES.get(user.role, []))
permissions = [
    permission
    for scope, permission in SCOPE_TO_TOOL_PERMISSION.items()
    if scope in trusted_scopes
]
```

Add an integration test using a support-role principal whose verified JWT scopes contain only `agent:chat`, and assert that the injected tool-permission list is empty.

## Warnings

### WR-01: Structured merchant scope is silently discarded by policy retrieval

**File:** `src/api/routers/agent_runs.py:64-69`
**Issue:** The router now injects merchant scope as `{"merchant_ids": [...]}`, but `retrieve_policy_evidence` still accepts only `list[str]` and converts every non-list value to `None` (`src/agent/nodes/retrieve_policy_evidence.py:96-98`). Every run created through this router therefore loses its trusted merchant scope before `PolicyKnowledgeService.search`, disabling that service's merchant-filter authorization check. The current adapter does not send merchant filters to the database, so this is not presently a data leak, but the authorization contract is already broken and will become exploitable when merchant-filtered policy retrieval is enabled.
**Fix:** Keep separate compatible projections in trusted config, or update the policy node to extract the list from the structured scope.

```python
scope = configurable.get("merchant_scope")
merchant_scope = scope.get("merchant_ids") if isinstance(scope, dict) else scope
if not isinstance(merchant_scope, list):
    merchant_scope = []
```

Add a graph/router integration test asserting that a merchant user's ID reaches `KnowledgeContext.merchant_scope`.

---

_Reviewed: 2026-06-12T20:58:17Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
