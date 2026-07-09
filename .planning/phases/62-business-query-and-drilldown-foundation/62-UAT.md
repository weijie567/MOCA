---
status: complete
phase: 62-business-query-and-drilldown-foundation
source:
  - .planning/phases/62-business-query-and-drilldown-foundation/62-01-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-02-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-03-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-04-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-05-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-06-SUMMARY.md
  - .planning/phases/62-business-query-and-drilldown-foundation/62-07-SUMMARY.md
started: 2026-07-09T17:18:29Z
updated: 2026-07-09T17:18:29Z
---

## Current Test

[testing complete]

## Tests

### 1. Registry-backed business query vocabulary
expected: Metric ids, resources, time presets, status filters, fields, sorts, parser aliases, prompts, ToolCatalog enums, and routing surfaces are derived from `BUSINESS_QUERY_REGISTRY` instead of local duplicate literals.
result: pass

### 2. Strict BusinessQuerySpec contract
expected: `BusinessQuerySpec` accepts only registry-backed aggregate, list, detail, breakdown, and compare shapes; rejects authority-bearing fields, raw SQL/filter/cursor shapes, wildcard merchant filters, invalid limits, and incompatible `current_snapshot` usage.
result: pass

### 3. Trusted tool permission boundary
expected: `business:query` projects to `tool:business_query` only through trusted context; missing permissions, wrong callers, authority fields, raw SQL keys, arbitrary filters, and raw cursor strings are denied before executor dispatch.
result: pass

### 4. Controlled backend execution
expected: `BusinessFactService` owns business-query aggregate/list/detail/breakdown/compare execution through a registry-backed SQLAlchemy compiler; list queries use scoped pagination and detail queries preserve no-existence-leak behavior.
result: pass

### 5. Same-thread drilldown
expected: A first-turn aggregate answer safely stores `last_query_spec`, `last_answer_context`, and cursor metadata; a follow-up such as "订单号是多少？" derives a validated list/detail business-query spec only after context binding validation.
result: pass

### 6. Safe projection and final/API/SSE payloads
expected: Business-query facts render prompt-safe summaries, `business_query_answer` final responses, bounded API/SSE payloads, no-leak denied payloads, and deterministic eval coverage without exposing raw rows, hidden scope, raw cursors, SQL, routing hints, or tool args.
result: pass

### 7. Agent console rendering
expected: Timeline labels distinguish aggregate/list/detail/breakdown/compare business-query answers, and the Details Result tab renders typed safe fields, rows, denied/empty states, cursor labels, and drilldown affordances without relying on localized final-response text.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Verification Evidence

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/business/test_business_query_schemas.py tests/business/test_business_query_service.py tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/tools/test_projection.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py tests/test_agent_runs_api.py tests/eval/test_phase62_business_query_golden.py tests/architecture/test_business_query_boundaries.py -q --tb=short` -> `421 passed, 36 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_phase62_business_query.py --golden-set evaluation/golden/phase62_business_query_cases.jsonl --output /tmp/phase62_business_query_eval.json` -> `Phase 62 business-query golden validation passed: 9 cases`
- `npm --prefix frontend test` -> `3 files passed, 13 tests passed`
- `npm --prefix frontend run build` -> passed
- `npm --prefix frontend run e2e` -> `6 passed`
- `.planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md` -> `status: clean`

## Gaps

[none]
