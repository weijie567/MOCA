---
phase: 61
slug: product-experience-fixes
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for product UX, metric scope, console, and regression coverage.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest through `uv run pytest` |
| **Frontend framework** | Vitest/jsdom; Playwright to be added in Plan 61-05 |
| **Config files** | `pyproject.toml`, `frontend/package.json`, `frontend/vite.config.ts`; Playwright config created in Plan 61-05 |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_final_response.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent tests/business tests/tools tests/platform tests/test_agent_runs_api.py -q --tb=short` plus `cd frontend && npm run test -- --run && npm run build && npm run e2e && npm run e2e:live` after Plan 61-05 |
| **Estimated runtime** | ~2-8 minutes depending on full API and Playwright runs |

## Sampling Rate

- **After every task commit:** run that plan's focused backend/frontend command.
- **After every plan wave:** run all completed-plan focused commands plus frontend build when frontend files changed.
- **Before phase verification:** run backend focused suite, frontend Vitest/build, Playwright E2E, and live Agent Console API/SSE Playwright smoke.
- **Max feedback latency:** keep plan-local feedback under ~90 seconds where practical; Playwright is allowed to exceed this only in Plan 61-05 and phase-final validation.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 61-01-01 | 01 | 1 | UX-01, UX-04 | T-61-01-01 | Small talk stays deterministic and no evidence claim appears | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_final_response.py -q --tb=short` | ✅ | ⬜ pending |
| 61-01-02 | 01 | 1 | UX-02, UX-03 | T-61-01-02 | Unsupported/clarification text exposes safe reasons only | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_clarification_gate.py tests/agent/test_nodes/test_final_response.py -q --tb=short` | ✅ | ⬜ pending |
| 61-02-01 | 02 | 2 | MET-01, MET-02, MET-04 | T-61-02-01 | One metric intent with strict metric slots and conditional time clarification | unit/contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py -q --tb=short` | ✅ | ⬜ pending |
| 61-02-02 | 02 | 2 | SCOPE-01..SCOPE-04 | T-61-02-02 | Metric scope contract cannot be widened by user/LLM/frontend | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py -q --tb=short` | ✅ | ⬜ pending |
| 61-03-01 | 03 | 3 | MET-03, SCOPE-01..SCOPE-04 | T-61-03-01 | Metric values come only from scoped BusinessFactService queries | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q --tb=short` | ✅ | ⬜ pending |
| 61-04-01 | 04 | 4 | MET-01..MET-04, UX-04 | T-61-04-01 | Graph routes complete metric slots to read-only metric tool and final response | graph | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py -q --tb=short` | ✅ | ⬜ pending |
| 61-05-01 | 05 | 5 | CONSOLE-01..CONSOLE-03 | T-61-05-01 | Timeline renders safe result labels and does not leak debug/scope details | frontend | `cd frontend && npm run test -- --run && npm run build` | ✅ | ⬜ pending |
| 61-05-02 | 05 | 5 | EVAL-01..EVAL-03 | T-61-05-02 | Golden and live Playwright flows cover known UX regressions and role/scope cases | eval/e2e | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase61_ux_golden.py -q --tb=short && cd frontend && npm run e2e && npm run e2e:live` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Wave 0 Requirements

- [ ] `evaluation/golden/phase61_ux_cases.jsonl` — Phase 61 UX/metric golden cases.
- [ ] `tests/eval/test_phase61_ux_golden.py` — validates golden coverage and invariants.
- [ ] `frontend/playwright.config.ts` and `frontend/e2e/agent-console.spec.ts` — Playwright E2E infrastructure.
- [ ] `frontend/package.json` — add `e2e` plus `e2e:live` scripts and Playwright dev dependency.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Agent Console role switching with seeded demo data | EVAL-03 | Requires running backend/frontend and visual confirmation of timeline text | Start local services, run prompts as support/manager/admin, capture expected final response/timeline behavior in `.planning/LOCAL-VALIDATION-ISSUES.md` if any issue appears. |

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing Playwright/golden-set references.
- [ ] No watch-mode flags in validation commands.
- [ ] Feedback latency stays bounded for plan-local verification.
- [ ] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved for Phase 61 execution by local planning review; final status remains pending until execution artifacts prove the commands pass.
