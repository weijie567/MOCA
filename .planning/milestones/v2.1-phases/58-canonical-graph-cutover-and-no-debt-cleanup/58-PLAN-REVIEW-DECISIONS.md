---
phase: 58
reviewed_at: 2026-07-08T08:25:00+08:00
review_source: .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-REVIEWS.md
reviewer: codex
status: clean_after_recheck
---

# Phase 58 Plan Review Decisions

## Checker Repair Addendum

Follow-up repair after GSD plan-checker blocker: the original oversized `58-03-PLAN.md` is split into dependency-ordered smaller plans. Current numbering is:

- `58-03`: recommendation/risk wrapper deletion and direct canonical test cleanup.
- `58-04`: intent/session wrapper/helper cleanup and direct legacy test migration.
- `58-05`: slot/memory wrapper/helper cleanup and direct legacy test migration.
- `58-06`: graph/routing/shared fixture patch seam cleanup.
- `58-07`: integration/architecture import coverage cleanup.
- `58-08`: former trace/API/SSE/frontend/eval cleanup plan.
- `58-09`: former approval retry plan.
- `58-10`: former closeout plan.

Accepted review repairs below remain binding. GSD plan-checker passed after the ten-plan split, Claude found one metadata-proof command blocker, and final Claude re-review passed after commit `ee6b90d`.

## Decision Summary

Claude's review is mostly upheld. The original six-plan split was directionally sound, but GSD plan-checker later found `58-03-PLAN.md` too large; the current repaired plan set uses ten plans. The approval-retry boundary remains directionally correct, and the repaired plans must still close the full CAGM-09 no-debt scope before execution.

## Adjudicated Findings

### F1: Remaining legacy wrapper/helper cleanup is incomplete

Decision: ACCEPTED

Evidence:
- `src/agent/nodes/classify_intent.py`, `src/agent/nodes/session_memory_load.py`, `src/agent/nodes/extract_slots.py`, and `src/agent/nodes/long_term_memory_retrieve.py` are tracked source files.
- `58-03-PLAN.md` only deletes `src/agent/nodes/generate_recommendation.py` and `src/agent/nodes/assess_risk_and_approval.py`.

Required repair:
- Add concrete tasks for `classify_intent`, `session_memory_load`, `extract_slots`, and `long_term_memory_retrieve`.
- For each surface, the plan must either delete it, move any still-needed implementation behind the canonical module/private helper, or explicitly retain it as historical/internal-only with static classifier proof that it is not active runtime compatibility.
- Update legacy-named tests for the same surfaces, including `tests/agent/test_nodes/test_classify_intent.py`, `tests/agent/test_session_memory_load.py`, and `tests/agent/test_nodes/test_extract_slots.py`.

### F2: Route delegate removal is not concrete

Decision: ACCEPTED

Evidence:
- `src/agent/routing.py` still defines `route_after_intent` and `route_after_slots`.
- `58-01-PLAN.md` removes these names from active graph vocabulary, but no execution task clearly modifies `src/agent/routing.py`.

Required repair:
- Add an execution task that removes public `route_after_intent` and `route_after_slots`, or renames/internalizes them with explicit historical/internal-only rationale.
- Add acceptance criteria and tests/static guards proving they are not public current route authority.

### F3: Legacy-named test strategy conflicts with no-debt closeout

Decision: ACCEPTED

Evidence:
- `58-02-PLAN.md`, `58-03-PLAN.md`, and `58-06-PLAN.md` retain `tests/agent/test_nodes/test_generate_recommendation.py` as canonical behavior coverage.
- Tracked legacy-named tests also exist for `test_classify_intent.py`, `test_session_memory_load.py`, and `test_extract_slots.py`.

Required repair:
- Rename legacy-named tests where the filename itself would require a permanent classifier exception, unless a plan gives a narrow classifier category and justification.
- Prefer `tests/agent/test_nodes/test_recommendation_generation.py` for canonical recommendation coverage.
- Delete or migrate `tests/agent/test_nodes/test_assess_risk_and_approval.py`.
- Apply the same rename/delete/migrate decision to intent/session/slot/memory legacy tests.

### F4: Historical projection API boundary needs more downstream detail

Decision: ACCEPTED

Evidence:
- `58-01-PLAN.md` correctly separates current runtime vocabulary from `project_trace_step_for_contract()`, but downstream trace/API call-site expectations are mostly deferred to the trace/API/SSE/frontend/eval plan. After checker repair, that downstream plan is `58-08`.

Required repair:
- Expand `58-01` to define the current-runtime API versus historical projection API contract.
- Name downstream readers that must be adapted or verified: `src/agent/trace.py`, `src/repositories/trace_repo.py`, `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, and the trace/API tests.

### F5: Static classifier strict semantics must be explicit

Decision: PARTIALLY ACCEPTED

Evidence:
- `58-01-PLAN.md` already says strict mode fails when `active_runtime_legacy > 0` or `unclassified_rows > 0`.
- The review concern is valid because later plan guards could still be interpreted as requiring every legacy string to disappear.

Required repair:
- Preserve the explicit rule that `--strict` does not require `total_hits == 0`.
- Add that rule to final verification and docs closeout language so executors do not delete legitimate historical/reference rows indiscriminately.

### F6: `moca.egg-info/SOURCES.txt` is not addressed

Decision: ACCEPTED

Evidence:
- `moca.egg-info/SOURCES.txt` exists and is tracked.
- Current plans do not say whether it should be regenerated, edited, or classified.

Required repair:
- Add `moca.egg-info/SOURCES.txt` to the wrapper/import cleanup or final metadata cleanup scope.
- Require stale deleted module/test paths to be removed or deliberately classified, with a command proving no deleted wrapper path remains in tracked package metadata.

### F7: Docs guard is too brittle

Decision: ACCEPTED

Evidence:
- `58-06-PLAN.md` uses an inline `bad_terms` list that only checks a few exact English phrases.
- `58-01-PLAN.md` already introduces a richer classifier, so final docs/current-wording guard should rely on classifier categories instead of exact phrase matching.

Required repair:
- Make `scripts/classify_phase58_legacy_hits.py --strict` the primary final current-wording/docs guard.
- Any additional docs check should assert required canonical concepts, not maintain a small hardcoded denylist as the authority.

### F8: Intermediate wrapper stubs need care

Decision: ACCEPTED AS WARNING

Evidence:
- `58-02-PLAN.md` keeps compatibility wrapper files temporarily while moving implementation ownership.

Required repair:
- Add an acceptance criterion to `58-02` that tests and patch seams are moved to canonical modules before `58-03`.
- `58-03` should be a deletion/static-guard diff, not a second implementation migration.

### F9: Frontend-specific tests are available but not mentioned

Decision: ACCEPTED

Evidence:
- `frontend/package.json` defines `test: vitest run --environment jsdom`.
- The original trace/API/SSE/frontend/eval plan only required `npm --prefix frontend run build`; after checker repair, this plan is `58-08`.

Required repair:
- Add `npm --prefix frontend run test -- --run` only if this command is valid for the configured Vitest version, or use the exact available script form `npm --prefix frontend run test`.
- If no relevant frontend test exists for timeline behavior, record build plus backend payload tests as the verification boundary in `58-08-SUMMARY.md`.

## Repair Gate

After repair:
- GSD plan checker: PASSED after ten-plan split.
- External Claude review: CLEAN after metadata-proof repair in commit `ee6b90d`.
- No outstanding plan-review blockers remain before execution.
