---
phase: "62-business-query-and-drilldown-foundation"
reviewed: "2026-07-09T16:28:02Z"
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
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 62: Code Review Report

**Reviewed:** 2026-07-09T16:28:02Z
**Depth:** standard
**Files Reviewed:** 54
**Status:** issues_found

## Summary

Reviewed the Phase 62 business query, projection, API, frontend, golden eval, and tests at standard depth. I found two warning-level issues: the denied business-query path loses the requested operation/resource before the final API payload is built, and the already-projected payload sanitizer still trusts display label fields that the Console renders directly. No critical issues were found.

No tests were run during this review.

## Warnings

### WR-01: Denied business_query errors are hard-coded as order detail payloads

**File:** `src/agent/nodes/final_response.py:346`

**Issue:** When `BusinessFactService.query_business()` rejects an out-of-scope merchant before compilation, it returns a generic permission-denied result for `business_query` at `src/business/service.py:282-284`. `investigate` records only the descriptor resource name in the error at `src/agent/nodes/investigate.py:981-989`, so `_business_query_fact()` synthesizes a fixed denied payload with `operation: "detail"` and `resource: "order"` at `src/agent/nodes/final_response.py:346-354`.

That preserves the no-existence-leak copy, but it breaks the actual Phase 62 payload contract for denied list/breakdown/compare requests. The golden case `P62-BQ-003` expects an unauthorized merchant list request to return `operation: "list"`, `resource_label: "order"`, `safe_reason: "scope_denied_no_existence_leak"`, and empty rows. Current code would emit a denied detail payload instead. The existing API test at `tests/test_agent_runs_api.py:640-725` only injects already-shaped final payloads, so it does not exercise the real service -> investigate -> final_response denial path.

**Fix:**

Preserve a sanitized typed `BusinessQueryResultV1` for denied business-query requests after `BusinessQuerySpec` validation, instead of falling back to an untyped generic error. Keep the requested operation/resource, but clear denied merchant/resource identifiers before serializing.

```python
merchant_ids = self._authorized_business_query_merchant_ids(spec, ctx)
if merchant_ids is None:
    denied = self._denied_business_query_result(spec)
    return self._business_query_result_to_fact_result(denied, ctx)

def _denied_business_query_result(self, spec: BusinessQuerySpec) -> BusinessQueryResultV1:
    scope = BusinessQueryScopeSummary(scope_label="authorized_merchants", merchant_id=None)
    safe_spec = spec.model_copy(update={"merchant_id": None, "resource_id": None})
    return BusinessQueryResultV1(
        operation=spec.operation,
        resource=spec.resource,
        status="permission_denied",
        rows=[],
        answer_context=BusinessQueryAnswerContext(
            query_spec=safe_spec,
            result_refs=[],
            allowed_drilldowns=[],
            fields_shown=[],
            scope=scope,
            time_summary=spec.time.preset if spec.time else None,
            filter_summary=None,
        ),
        scope=scope,
    )
```

Add an integration or graph/API test that sends an unauthorized list request such as `{"operation": "list", "resource": "order", "merchant_id": "MERCHANT-SECRET"}` through the real business-query tool path and asserts the final API payload keeps `operation == "list"`, has empty rows, uses `scope_denied_no_existence_leak`, and does not serialize the denied merchant id.

### WR-02: Projected label fields can still leak raw cursor/id strings into the API and Console

**File:** `src/business/query/projection.py:188`

**Issue:** `safe_business_query_metadata()` accepts already-projected payloads whenever `operation` is valid and a label field is present at `src/business/query/projection.py:138-140`. `_sanitize_projected_api_payload()` then allowlists label fields like `resource_label`, `result_label`, `filters_label`, `fields_label`, and `cursor_label` using `_safe_text()` at `src/business/query/projection.py:188-208`. `_safe_text()` only rejects SQL-like substrings at `src/business/query/projection.py:396-425`; it does not reject raw cursor tokens, denied ids, tenant/merchant markers in values, or resource ids embedded in labels.

The API exposes this result for `business_query_answer` at `src/api/routers/agent_runs.py:1230-1257`, and the Console renders these fields directly as title, metadata, and cursor button text at `frontend/src/components/details/BusinessQueryResultTab.tsx:98-145`. React escaping prevents XSS, but it does not prevent no-existence-leak or raw-payload leakage if a tool/test fixture/future executor supplies a projected payload containing values like `cursor-raw-should-not-leak`, `MERCHANT-SECRET`, or `ORD-SECRET-DENIED` in an allowed label field. Current tests cover forbidden keys such as `raw_rows`, `raw_args`, and `raw_cursor`, but not forbidden values placed inside allowed labels.

**Fix:**

Do not trust arbitrary labels on the already-projected payload path. Derive labels from typed operation/resource metadata where possible, and make `cursor_label` an enum-style display value instead of a free-form pass-through. At minimum, reject projected label values containing raw/tenant/merchant/cursor/id-denial markers before returning API/UI payloads.

```python
def _safe_display_label(value: Any) -> str:
    label = _safe_text(value)
    if not label:
        return ""
    lowered = label.lower()
    if any(marker in lowered for marker in ("raw", "cursor-", "tenant", "merchant-secret", "ord-secret")):
        return ""
    return label

safe: dict[str, Any] = {
    "operation": operation if operation in BUSINESS_QUERY_REGISTRY.operation_ids() else "",
    "resource_label": _safe_display_label(payload.get("resource_label")),
    "result_label": _safe_display_label(payload.get("result_label")),
    "filters_label": _safe_display_label(payload.get("filters_label")) or "无",
    "fields_label": _safe_display_label(payload.get("fields_label")),
    "cursor_label": "还有更多结果" if payload.get("cursor_label") == "还有更多结果" else "",
}
```

Add projection/API tests that place forbidden values inside allowed fields, for example `result_label="ORD-SECRET-DENIED"` and `cursor_label="cursor-raw-should-not-leak"`, and assert they are absent from serialized API payloads. Add a frontend regression test that verifies `BusinessQueryResultTab` only displays sanitized labels supplied by the backend.

---

_Reviewed: 2026-07-09T16:28:02Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
