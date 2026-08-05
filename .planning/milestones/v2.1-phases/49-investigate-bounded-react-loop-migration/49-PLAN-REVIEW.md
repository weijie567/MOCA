# Phase 49 Plan Review

**Date:** 2026-07-04
**Reviewer:** GSD plan-checker subagent
**Mode:** read-only plan review
**Result after adjudication:** blockers accepted, plans revised, re-review passed with no blockers

## Review Findings

### BLOCKER 1: Production LLM planner main path was not explicit

**Finding:** The first draft allowed fake/test planner seams and fallback behavior but did not require the normal production path to call a default LLM structured planner. This could leave deterministic `plan_next_step` as the real controller.

**Adjudication:** Valid.

**Fix applied:**
- `49-01-PLAN.md` now requires the normal non-injected path to construct and call `_get_llm().with_structured_output(...)`, following existing node patterns in `classify_intent`, `extract_slots`, `assess_risk_and_approval`, and `generate_recommendation`.
- Fake planners are explicitly test seams only.
- Acceptance criteria now require a test proving the normal path uses structured planner output and does not enter fallback on success.

### BLOCKER 2: Final no-go `rg` commands had inverted semantics

**Finding:** Plain `rg` succeeds on matches, so absence checks would pass when forbidden matches exist and fail when clean. The write-tool grep also mixed production absence with test coverage presence.

**Adjudication:** Valid.

**Fix applied:**
- `49-CONTEXT.md` and `49-04-PLAN.md` now use inverted production checks such as `! rg -n ... src/agent/nodes/investigate.py`.
- Write-tool rejection test presence is checked separately with a positive grep limited to tests.
- Broad `Repository` grep was narrowed to direct business/knowledge/memory repository/service dispatch patterns to avoid false positives from allowed conversation trace persistence imports.

### BLOCKER 3: Eight-tool allowlist gap could be mislabeled as implemented-with-limitations

**Finding:** `49-04-PLAN.md` allowed GAD-01 to become `IMPLEMENTED_WITH_LIMITATIONS` if `search_sop`/tool availability remained limited, conflicting with the hard eight-tool §12.4 allowlist requirement.

**Adjudication:** Valid.

**Fix applied:**
- `49-04-PLAN.md` now states that any missing planner visibility or non-invocable ToolPlatform dispatch for one of the eight tools is a blocker.
- The only allowed limitation is a declared read-only tool dispatching through ToolPlatform and returning a safe unavailable/no-data result because the backend has no data.

### WARNING 1: Logistics discovered slot key did not match descriptor schema

**Finding:** The draft mentioned `logistics_id` / `logistics_ref`, while `get_logistics` requires `tracking_no`.

**Adjudication:** Valid.

**Fix applied:**
- `49-02-PLAN.md` now lists `tracking_no` as the supported loop-local slot.
- `logistics_ref` is allowed only if explicitly mapped to `tracking_no` before `get_logistics`.

### WARNING 2: Regression-test edits were too open-ended

**Finding:** The first draft allowed existing regression tests to be edited for imports/fixtures, which could mask forbidden intent/memory/risk/approval/action regressions.

**Adjudication:** Valid.

**Fix applied:**
- `49-04-PLAN.md` now restricts regression test edits to additive Phase 49 assertions/fixtures and explicitly forbids relaxing existing assertions.

## Residual Risk

- The plan still needs implementation-time verification that the default LLM planner can be tested without real network dependency by monkeypatching `_get_llm`/structured LLM, while production code uses the real configured LLM path.
- `search_sop` is currently catalog-declared but may need minimal executor visibility work in `src/tools/executors/knowledge.py`; the revised plan treats missing visibility as a blocker.
- Trace/replay parent-operation propagation may require a small event helper change; the plan forbids schema churn and permits only existing replay fields.

## Re-Review

Second read-only GSD plan-checker re-review found no blockers. It confirmed:

- production LLM structured planner main path is explicit;
- no-go `rg` checks are now correctly inverted and separated from positive test-coverage greps;
- missing eight-tool planner visibility / ToolPlatform dispatch is a blocker, not an implemented limitation;
- `tracking_no` is the logistics slot key;
- regression test edits are constrained to additive Phase 49 assertions/fixtures.

The re-review raised one non-blocking strengthening suggestion: require an explicit `ToolPlatform.invoke(...)` smoke test for all eight §12.4 tools, not only exact visibility and `search_sop`. This was accepted and added to `49-03-PLAN.md`.

## Follow-Up

Proceed to Phase 49 execution only after the implementation agent reads `49-CONTEXT.md`, all four plans, and this review file.

## Claude ReAct Sufficiency Review

**Reviewer verdict:** `PASS_WITH_WARNINGS`
**Adjudication:** Valid; warnings accepted and plans revised.

Claude's review specifically checked whether the four plans would produce a real bounded read-only ReAct loop rather than an LLM wrapper around deterministic fallback. It judged the core ReAct dimensions as covered:

- LLM main control path is covered by 49-01's normal `_get_llm().with_structured_output(...)` requirement.
- Action-observation-reasoning loop is covered by one tool-or-stop decision per iteration and planner input that includes projected observation summaries.
- Loop-local discovered slots are covered by 49-02's scratchpad-only slot merge and no graph-state writer rules.
- Boundedness, tool safety, projection boundary, and graph boundary isolation are covered.
- Trace/replay is partial-to-covered because parent node operation identity may require implementation-time confirmation.

### Accepted Warning: replay parent-operation limitation must affect closeout status

**Finding:** If parent node operation identity cannot be emitted without schema churn, distinct tool operation IDs plus iteration still preserve basic replay distinction, but do not fully satisfy the parent-operation semantics in `docs/contract-spec.md` §17.2.

**Fix applied:** `49-03-PLAN.md` now requires Phase 49 to close as `IMPLEMENTED_WITH_LIMITATIONS`, not `IMPLEMENTED`, if the parent-operation gap remains, and requires 49-04 to record the limitation in GAD-01 and `.planning/ARCHITECTURE-DEBT.md`.

### Accepted Warning: disabling planner main path means not implemented

**Finding:** 49-04 rollback correctly allowed disabling the planner main path if graph regressions expose instability, but this state must not be treated as successful Phase 49 delivery.

**Fix applied:** `49-04-PLAN.md` now states that if deterministic `plan_next_step` remains the active production path, Phase 49 verdict is `BLOCKED` / `NOT_IMPLEMENTED` for GAD-01 and cannot be marked `IMPLEMENTED` or `IMPLEMENTED_WITH_LIMITATIONS`.

### Note: numbering typo

Claude reported a duplicate test-number typo in 49-03. The current file has sequential behavior tests for Task 3, so no further edit was needed.
