---
phase: 62-business-query-and-drilldown-foundation
plan: 06
subsystem: business-query-projection-eval
tags: [business-query, projection, final-response, sse, api, eval, tdd]

requires:
  - phase: 62-05
    provides: "BusinessQueryResultV1 runtime and backend query service contract"
provides:
  - "Prompt-safe and UI-safe business_query projection helpers"
  - "business_query_answer final response and API/SSE payload allowlist"
  - "Deterministic Phase 62 business-query golden/eval coverage"
affects: [62-07, agent-console, frontend-business-query-ui, phase63]

tech-stack:
  added: []
  patterns:
    - "BusinessQueryResultV1 normalized payload is the single projection source of truth"
    - "API/SSE business_query payloads are allowlisted separately from prompt-safe metadata"
    - "Phase eval checks deterministic JSONL fixtures without live LLM calls"

key-files:
  created:
    - src/business/query/projection.py
    - tests/tools/test_projection.py
    - scripts/eval_phase62_business_query.py
    - evaluation/golden/phase62_business_query_cases.jsonl
    - tests/eval/test_phase62_business_query_golden.py
    - .planning/phases/62-business-query-and-drilldown-foundation/62-06-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - src/business/query/__init__.py
    - src/tools/projection.py
    - src/agent/nodes/final_response.py
    - src/api/routers/agent_runs.py
    - src/api/schemas/agent_runs.py
    - tests/agent/test_nodes/test_final_response.py
    - tests/test_agent_runs_api.py

key-decisions:
  - "Use BusinessQueryResultV1 normalized payloads as the projection source of truth and reject unwrapped raw tool-result dictionaries."
  - "Keep metric_answer compatibility for query_business_metric while emitting business_query_answer for native business_query facts."
  - "Validate Phase 62 business-query behavior with deterministic JSONL fixtures rather than live LLM evaluation."

patterns-established:
  - "Projection helpers must strip raw rows, raw filters, hidden scope internals, raw cursor tokens, SQL markers, and routing/tool arguments before prompt or API exposure."
  - "Denied list/detail business-query responses use no-existence-leak copy and still return a bounded safe payload."
  - "Business-query eval fixtures must cover drilldown, permission boundaries, breakdown, compare, projection bounds, clarification, and unsupported cases."

requirements-completed: [BQ-62-06, BQ-62-08, BQ-62-04]

duration: 27m16s
completed: 2026-07-09
---

# Phase 62 Plan 06: Business Query Projection, Final Response, API, and Eval Summary

**Safe business-query answers now project from normalized backend facts into final response text, API/SSE payloads, and deterministic Phase 62 golden fixtures.**

## Performance

- **Duration:** 27m16s
- **Started:** 2026-07-09T14:51:43Z
- **Completed:** 2026-07-09T15:18:59Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments

- Added `src/business/query/projection.py` with prompt-safe metadata, UI-safe API payloads, bounded row projection, and operation-specific Chinese response text for aggregate, list, detail, breakdown, compare, and denied no-leak cases.
- Wired business-query projections through tool summaries, final response generation, and `agent_runs` API/SSE schemas while preserving existing metric answer compatibility.
- Added deterministic Phase 62 golden/eval coverage for drilldown sequence, permission boundaries, list/detail no-existence-leak behavior, breakdown, compare, projection bounds, clarification, and unsupported boundaries.
- Recorded the verified projection/final/API safety fix in the architecture debt ledger and the Task 2 validation failure in the local validation issue log.

## Task Commits

Each task was committed atomically. TDD tasks have RED and GREEN commits.

1. **Task 1 RED: business_query projection tests** - `89e38d9` (`test`)
2. **Task 1 GREEN: final/API/SSE projection implementation** - `413f74c` (`feat`)
3. **Task 2 RED: Phase 62 eval and API backstop tests** - `84e1838` (`test`)
4. **Task 2 GREEN: eval script, golden fixtures, and validation fix** - `fdd4b2d` (`feat`)

## Files Created/Modified

- `src/business/query/projection.py` - Normalized business-query projection helpers for prompt text, metadata, UI rows, and API payloads.
- `src/business/query/__init__.py` - Exports the projection helpers.
- `src/tools/projection.py` - Adds `business_query_summary` to prompt-safe tool projections.
- `src/agent/nodes/final_response.py` - Emits `business_query_answer` text and metadata for native business-query facts.
- `src/api/routers/agent_runs.py` - Adds allowlisted `business_query` final payload support.
- `src/api/schemas/agent_runs.py` - Adds `business_query` to SSE final event payload schema.
- `tests/tools/test_projection.py` - Covers prompt/API projection bounds and raw-payload rejection.
- `tests/agent/test_nodes/test_final_response.py` - Covers final response text and metadata for all business-query operations.
- `tests/test_agent_runs_api.py` - Covers API/SSE payload allowlist, no-leak denied payloads, breakdown, and compare.
- `scripts/eval_phase62_business_query.py` - Validates Phase 62 JSONL golden fixtures.
- `evaluation/golden/phase62_business_query_cases.jsonl` - Adds 9 deterministic business-query regression cases.
- `tests/eval/test_phase62_business_query_golden.py` - Tests eval fixture contract and required coverage.
- `.planning/ARCHITECTURE-DEBT.md` - Records the verified projection/final/API safety fix.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records the Task 2 validation failure and fix.

## Decisions Made

- `BusinessQueryResultV1` normalized payloads are the projection boundary. The helper rejects unwrapped raw tool result dictionaries so raw backend payloads cannot accidentally become prompt/API data.
- Native `business_query` facts use `response_kind="business_query_answer"`, while `query_business_metric` keeps the existing `metric_answer` contract for compatibility.
- Phase 62 golden evaluation is deterministic and fixture-based; live LLM response quality remains outside this backend safety plan.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py -q --tb=short` - `124 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase62_business_query_golden.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` - `123 passed, 36 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py tests/test_agent_runs_api.py tests/eval/test_phase62_business_query_golden.py -q --tb=short` - `169 passed, 36 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_phase62_business_query.py --golden-set evaluation/golden/phase62_business_query_cases.jsonl --output /tmp/phase62_business_query_eval.json` - `Phase 62 business-query golden validation passed: 9 cases`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/projection.py src/business/query/__init__.py src/tools/projection.py src/agent/nodes/final_response.py src/api/routers/agent_runs.py src/api/schemas/agent_runs.py tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py` - `All checks passed!`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check scripts/eval_phase62_business_query.py tests/eval/test_phase62_business_query_golden.py tests/test_agent_runs_api.py src/agent/nodes/final_response.py .planning/LOCAL-VALIDATION-ISSUES.md` - `All checks passed!`
- `gsd-sdk query verify.key-links .planning/phases/62-business-query-and-drilldown-foundation/62-06-PLAN.md` - `all_verified: true`, 2/2 key links verified

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved metric permission-denied final response branch**
- **Found during:** Task 2 GREEN verification
- **Issue:** Task 1 fallback logic treated any `BUSINESS_FACT_PERMISSION_DENIED` error as a business-query fact. This caused an existing metric permission-denied graph test to return generic business-query no-leak copy instead of metric-specific copy.
- **Fix:** Limited the fallback branch to `error["resource"] == "business_query"` and updated the new API compare backstop to account for the intentionally safe `metric_label` field.
- **Files modified:** `src/agent/nodes/final_response.py`, `tests/test_agent_runs_api.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Task 2 focused suite passed with `123 passed, 36 warnings`; combined plan suite passed with `169 passed, 36 warnings`.
- **Committed in:** `fdd4b2d`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Required for correctness. No architecture change and no scope expansion beyond final/API/eval safety.

## Issues Encountered

- TDD RED failures were expected: Task 1 failed on missing `src.business.query.projection`; Task 2 failed on missing `scripts.eval_phase62_business_query`.
- Task 2 focused verification exposed the metric permission-denied branch priority bug documented above. It was fixed and logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- GSD metadata handlers again miscomputed Phase 62 progress as `5/5` and could not update the roadmap checkbox. The handlers were run as required, then `.planning/STATE.md` and `.planning/ROADMAP.md` were corrected to 6/7 completed with 62-07 next, and the issue was logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No authentication gates were encountered.

## Known Stubs

None. Stub scan over plan-created/modified source, test, fixture, and planning files found only ordinary empty collection initializers and test assertions, not UI-facing placeholders or unwired mock data.

## Threat Flags

None beyond the plan threat model. The new projection, final response, and API/SSE surfaces are the intended trust-boundary work for this plan and are covered by projection stripping, payload allowlists, denial copy, and regression tests.

## User Setup Required

None - no external service configuration required.

## TDD Gate Compliance

- RED gate commits present: `89e38d9`, `84e1838`
- GREEN gate commits present after RED: `413f74c`, `fdd4b2d`
- No refactor commit was needed.

## Next Phase Readiness

Plan 62-07 can render `response_kind="business_query_answer"` and the allowlisted `business_query` payload from API/SSE events. Backend projection now supplies safe operation labels, bounded UI rows, no-leak denied payloads, and deterministic fixture coverage for the frontend business-query UI.

## Self-Check: PASSED

- Created files verified present: `src/business/query/projection.py`, `tests/tools/test_projection.py`, `scripts/eval_phase62_business_query.py`, `evaluation/golden/phase62_business_query_cases.jsonl`, `tests/eval/test_phase62_business_query_golden.py`, `.planning/phases/62-business-query-and-drilldown-foundation/62-06-SUMMARY.md`
- Task commits verified present: `89e38d9`, `413f74c`, `84e1838`, `fdd4b2d`

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*
