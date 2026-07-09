---
phase: "62-business-query-and-drilldown-foundation"
reviewed: "2026-07-09T16:48:25Z"
depth: standard
files_reviewed: 54
files_reviewed_list:
  - docs/contract-spec.md
  - evaluation/golden/phase62_business_query_cases.jsonl
  - frontend/e2e/agent-console.spec.ts
  - frontend/package.json
  - frontend/src/components/details/BusinessQueryResultTab.tsx
  - frontend/src/components/details/DetailsPanel.tsx
  - frontend/src/components/timeline/TimelineStep.tsx
  - frontend/src/hooks/useAgentRun.test.ts
  - frontend/src/types/events.ts
  - scripts/eval_phase62_business_query.py
  - src/agent/nodes/contextual_intent_resolve.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/investigate_planner.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/slot_resolution_gate.py
  - src/agent/prompts.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/api/routers/agent_runs.py
  - src/api/schemas/agent_runs.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/business/query/__init__.py
  - src/business/query/compiler.py
  - src/business/query/projection.py
  - src/business/query/registry.py
  - src/business/query/schemas.py
  - src/business/schemas.py
  - src/business/service.py
  - src/platform/trusted_context.py
  - src/tools/catalog.py
  - src/tools/contracts.py
  - src/tools/executors/business.py
  - src/tools/projection.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_contextual_intent_resolve.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_nodes/test_slot_resolution_gate.py
  - tests/agent/test_required_slots.py
  - tests/architecture/test_business_query_boundaries.py
  - tests/business/test_business_query_registry.py
  - tests/business/test_business_query_schemas.py
  - tests/business/test_business_query_service.py
  - tests/business/test_schemas.py
  - tests/business/test_service.py
  - tests/eval/test_phase62_business_query_golden.py
  - tests/platform/test_trusted_context_factory.py
  - tests/test_agent_runs_api.py
  - tests/tools/test_catalog.py
  - tests/tools/test_projection.py
  - tests/tools/test_tool_platform.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 62: Code Review Report

**Reviewed:** 2026-07-09T16:48:25Z
**Depth:** standard
**Files Reviewed:** 54
**Status:** issues_found

## Summary

Re-reviewed the Phase 62 file scope at standard depth after fixes `07419cb` and `161a01a`, with focus on the prior WR-01/WR-02 findings and regressions from those fixes. WR-02 is resolved: backend projection/API tests now cover sensitive label values, and the Console component strips unsafe display labels. WR-01 is only partially resolved: the inner denied `business_query` payload now preserves the requested operation/resource shape, but the fix introduced a wrapper-status regression that marks denied queries as successful, allowed business facts.

Targeted verification:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/tools/test_projection.py tests/test_agent_runs_api.py tests/eval/test_phase62_business_query_golden.py` failed: 1 failed, 101 passed. The failure is the WR-01 wrapper-status regression below.
- `npm test -- --run frontend/src/components/details/BusinessQueryResultTab.test.tsx` passed: 3 files, 13 tests.

## Warnings

### WR-01: Denied business_query results are still wrapped as allowed successes

**File:** `src/business/service.py:650`

**Issue:** Fix `07419cb` correctly changed the denied branch to build a typed `BusinessQueryResultV1` at `src/business/service.py:282-284` and `src/business/service.py:329-354`, so the inner payload now preserves `operation == "list"` and `safe_reason == "scope_denied_no_existence_leak"`. However, that typed denied payload is passed through `_business_query_result_to_fact_result()`, which still hard-codes the outer `BusinessFactResultV1` as `status="ok"` and `scope_check_result="allowed"` at `src/business/service.py:650-658`.

This regresses the fail-closed control-plane contract. The targeted test `tests/business/test_business_query_service.py:300-336` now fails because an empty merchant scope returns outer status `ok` instead of `permission_denied`. The impact is broader than that assertion: `BusinessToolService._wrap_business_fact_result()` maps the outer `ok` to `ToolResultV2.status == "success"` at `src/business/service.py:1687-1698`, and `investigate._accumulate_tool_result()` treats successful tool results as fact-bearing at `src/agent/nodes/investigate.py:944-964`. That can add a denied business-query result and fact ref to authoritative context even though the inner payload says permission denied.

**Fix:**

Derive the outer business-fact status and scope result from the inner `BusinessQueryResultV1.status`, and preserve the safe denied payload without treating it as an allowed fact. One concrete shape:

```python
outer_status = "permission_denied" if result.status == "permission_denied" else "ok"
scope_check_result = "denied" if result.status == "permission_denied" else "allowed"
fact_refs = [] if result.status == "permission_denied" else [fact_ref]

return BusinessFactResultV1(
    tenant_id=ctx.tenant_id,
    status=outer_status,
    fact={"business_query": result.model_dump(mode="json")},
    business_fact_refs=fact_refs,
    resource_version=result.schema_version,
    data_freshness_at=retrieved_at,
    source_system="business_fact_service",
    scope_check_result=scope_check_result,
    missing_required_facts=[],
    safe_errors=[],
)
```

Then update the tool/investigate path so a `business_query` permission-denied result may carry the safe projected payload for final response rendering, but does not satisfy `FACT_STATUSES`, does not emit business fact refs, and is not counted as an authoritative allowed result. Add regression coverage for both direct service status and `BusinessToolService.invoke_tool("business_query", ...)` returning `permission_denied` while still preserving the safe denied `operation/resource` payload.

---

_Reviewed: 2026-07-09T16:48:25Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
