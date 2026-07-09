---
phase: 62
slug: business-query-and-drilldown-foundation
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-09
updated: 2026-07-10
---

# Phase 62 — Validation Strategy

> Per-phase validation contract for safe business-query contracts, backend execution, drilldown, projection, console UI, and regression coverage.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Frontend framework** | Vitest 4.1.7 and Playwright 1.61.1 through the frontend npm package tree |
| **Config files** | `pyproject.toml`, `frontend/package.json`, frontend Vite/Vitest/Playwright config |
| **Quick backend command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business tests/tools tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short` |
| **Focused graph/API command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` |
| **Frontend unit command** | `npm --prefix frontend test` |
| **Frontend E2E command** | `npm --prefix frontend run e2e` or `npm --prefix frontend exec playwright -- test`, depending on existing package scripts |
| **Full backend suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -q --tb=short` |
| **Estimated runtime** | Focused backend suites should stay under a few minutes; full backend + frontend + E2E may take several minutes depending on local services |

---

## Sampling Rate

- **After every task commit:** Run the smallest targeted backend/frontend command for the touched boundary, always through MOCA-approved entrypoints.
- **After every plan wave:** Run focused graph/API/backend service tests plus relevant frontend tests when payload/UI changes.
- **Before `$gsd-verify-work`:** Run full backend suite, frontend unit/E2E, and Phase 62 eval/golden command.
- **Max feedback latency:** Keep task-local feedback under 180 seconds where practical; allow longer only for phase-final frontend/E2E and broad backend gates.

---

## Per-Task Verification Map

Phase 62 uses canonical phase-local requirement IDs `BQ-62-01` through `BQ-62-08`.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 62-TASK-01 | 01 | 1 | BQ-62-01 | T-62-01 | Registry is the single source for operation/resource/metric/time/status/field/sort definitions. | unit/parity | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/tools/test_catalog.py -q --tb=short` | ✅ `tests/business/test_business_query_registry.py` plus parser/catalog parity tests | ✅ green |
| 62-TASK-02 | 01/02 | 1/2 | BQ-62-02 | T-62-02 | `business_metric_query` maps into `BusinessQuerySpec` and remains compatibility-only. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_schemas.py tests/agent/test_graph.py -q --tb=short` | ✅ `tests/business/test_business_query_schemas.py` and graph compatibility coverage | ✅ green |
| 62-TASK-03 | 04 | 4 | BQ-62-03 | T-62-03 | BusinessFactService executes aggregate/list/detail/breakdown/compare through controlled scope-safe queries. | service/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py -q --tb=short` | ✅ `tests/business/test_business_query_service.py` | ✅ green |
| 62-TASK-04 | 03/04/06 | 3/4/6 | BQ-62-04 | T-62-04 | Out-of-scope list/detail/resource inputs do not reveal existence. | service/graph/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` | ✅ service/tool/API no-existence-leak and denial payload coverage | ✅ green |
| 62-TASK-05 | 05 | 5 | BQ-62-05 | T-62-05 | Drilldown flow `本周多少订单？` -> `订单号是多少？` re-executes backend query from safe context. | graph/eval | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` plus Phase 62 eval command | ✅ `tests/agent/test_graph.py` and Phase 62 golden drilldown case | ✅ green |
| 62-TASK-06 | 06 | 6 | BQ-62-06 | T-62-06 | Projection/final response emits bounded prompt-safe and UI-safe `business_query_answer` payload. | unit/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py -q --tb=short` | ✅ projection/final/API business-query coverage | ✅ green |
| 62-TASK-07 | 07 | 7 | BQ-62-07 | T-62-07 | Frontend Timeline/Details render aggregate/list/detail/breakdown/compare without raw rows or overlap. | frontend unit/build + phase-gate e2e | `npm --prefix frontend test`; `npm --prefix frontend run build`; `npm --prefix frontend run e2e` | ✅ frontend unit/build/e2e business-query coverage | ✅ green |
| 62-TASK-08 | 06 | 6 | BQ-62-08 | T-62-08 | Golden/eval coverage includes drilldown, permission boundary, list/detail no-existence-leak, breakdown, and compare. | eval | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_phase62_business_query.py --golden-set evaluation/golden/phase62_business_query_cases.jsonl --output /tmp/phase62_business_query_eval.json` | ✅ `scripts/eval_phase62_business_query.py`, JSONL golden cases, and eval tests | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/business/test_business_query_registry.py` or equivalent parity tests for descriptor source of truth.
- [x] `tests/business/test_business_query_schemas.py` for strict `BusinessQuerySpec`, filters, limits, cursors, and compatibility shim.
- [x] `tests/business/test_business_query_service.py` for aggregate/list/detail/breakdown/compare and no-existence-leak.
- [x] Agent graph tests for `本周多少订单？` followed by `订单号是多少？`.
- [x] API payload tests for `business_query_answer` and safe payload filtering.
- [x] Frontend Timeline/Details tests for result kinds and no raw payload rendering.
- [x] Phase 62 golden/eval cases and runner updates or a new script.

---

## Manual-Only Verifications

All core Phase 62 behaviors should have automated verification. Manual validation is limited to optional local Agent Console smoke checks after automated frontend/E2E tests pass.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local Agent Console inspection for typed query result readability | BQ-62-07 | Visual density, scroll behavior, and text fit are easier to judge in a running browser, but must not replace automated tests. | Start local API/frontend if needed, run aggregate/list/detail/drilldown examples, and record any local validation issue in `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese after handling. |

---

## Security Validation Focus

| Threat Ref | Threat | Required Automated Evidence |
|------------|--------|-----------------------------|
| T-62-01 | Registry drift reintroduces duplicate operation/resource/time/status definitions. | Registry/catalog/parser parity tests. |
| T-62-02 | `business_metric_query` remains a permanent branch instead of compatibility shim. | Schema and graph tests proving mapping into `BusinessQuerySpec`. |
| T-62-03 | Business query compiler permits raw SQL or generic list exposure. | Service/compiler tests and static checks forbidding raw SQL/generic list helpers in agent/tool layers. |
| T-62-04 | Unauthorized list/detail confirms whether a merchant/resource/id exists. | Service, graph, and API no-existence-leak tests. |
| T-62-05 | Drilldown uses stale/raw prior answer data instead of revalidation. | Multi-turn graph/eval tests proving backend re-execution. |
| T-62-06 | Prompt or UI payload leaks raw rows, PII, debug data, or scope internals. | Projection/API/frontend safe-payload tests. |
| T-62-07 | Frontend parses localized final text or renders raw payload JSON. | Frontend unit/E2E tests against typed payloads and no raw payload rendering. |
| T-62-08 | Eval misses business-query regressions across drilldown and permission boundaries. | Phase 62 golden/eval suite with required cases. |

---

## Validation Sign-Off

- [x] All Phase 62 source decisions have an automated verification lane.
- [x] Sampling continuity defined; no plan should go three task commits without automated verification.
- [x] Wave 0 gaps are explicit and must be scheduled by the planner.
- [x] No watch-mode flags in required commands.
- [x] `nyquist_compliant: true` set in frontmatter for the strategy.
- [x] Wave 0 tests created during implementation.
- [x] All final focused and broad verification commands green.

**Approval:** verified 2026-07-10 after implementation.

---

## Validation Audit 2026-07-10

| Metric | Count |
|--------|-------|
| Requirements audited | 8 |
| Covered | 8 |
| Partial | 0 |
| Missing | 0 |
| Manual-only | 1 optional smoke check |

### Final Evidence

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/business/test_business_query_schemas.py tests/business/test_business_query_service.py tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/tools/test_projection.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py tests/test_agent_runs_api.py tests/eval/test_phase62_business_query_golden.py tests/architecture/test_business_query_boundaries.py -q --tb=short` -> `421 passed, 36 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_phase62_business_query.py --golden-set evaluation/golden/phase62_business_query_cases.jsonl --output /tmp/phase62_business_query_eval.json` -> `Phase 62 business-query golden validation passed: 9 cases`
- `npm --prefix frontend test` -> `3 files passed, 13 tests passed`
- `npm --prefix frontend run build` -> passed
- `npm --prefix frontend run e2e` -> `6 passed`
- `.planning/phases/62-business-query-and-drilldown-foundation/62-UAT.md` -> `7 passed, 0 issues`
- `.planning/phases/62-business-query-and-drilldown-foundation/62-SECURITY.md` -> `threats_open: 0`
