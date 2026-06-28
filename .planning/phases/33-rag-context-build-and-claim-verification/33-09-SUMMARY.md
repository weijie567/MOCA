---
phase: 33-rag-context-build-and-claim-verification
plan: 33-09
subsystem: testing
tags: [rag, claim-verification, static-guards, validation, phase-gate]

# Dependency graph
requires:
  - phase: 33-08
    provides: safe rag_claim_summary projections for trace, SSE, trace API, and replay
  - phase: 32-intent-graph-migration
    provides: historical target graph vocabulary and deferred/non-runnable mapping
provides:
  - Phase 32 stale non-runnable guard migration for `rag_context_build` and `claim_verify`
  - Phase 33 static boundary guards for runtime nodes, deterministic routers, writer ownership, no raw leakage, and approved validation commands
  - Chinese RAG/claim target mapping with explicit deferrals and Phase 32-to-33 compatibility closure
  - Final focused Phase 33 validation gate result
affects: [phase-32-compatibility, phase-33-final-gate, phase-34-approval-action-binding, phase-35-replay-eval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - static architecture guards for graph/runtime boundary closure
    - Chinese target-mapping docs with English identifiers preserved
    - final focused suite as phase-gate-only validation

key-files:
  created:
    - tests/architecture/test_phase33_rag_claim_boundaries.py
    - .planning/phases/33-rag-context-build-and-claim-verification/33-RAG-CLAIM-TARGET-MAPPING.md
    - .planning/phases/33-rag-context-build-and-claim-verification/33-09-SUMMARY.md
  modified:
    - tests/architecture/test_phase32_static_contract.py
    - tests/agent/test_phase22_recommendation_integration.py
    - tests/agent/test_graph.py
    - .planning/phases/32-intent-graph-migration/32-MVP-TARGET-MAPPING.md
    - .planning/phases/33-rag-context-build-and-claim-verification/33-VALIDATION.md
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Phase 32 static guards no longer assert that rag_context_build and claim_verify are deferred_non_runnable or absent from the graph."
  - "Phase 33 static guards now own runtime/runnable RAG and claim boundary checks."
  - "generate_recommendation remains a verified-package consumer and MaterialClaimV1 producer; claim_verify owns verifier route/blocking assertions."
  - "Semantic verifier coverage remains deterministic/mocked with no live provider requirement."

patterns-established:
  - "Use Phase 33 static guards to close compatibility windows instead of preserving stale Phase 32 non-runnable assertions."
  - "Record final phase gates in validation docs with exact approved MOCA commands and results."

requirements-completed: [APF-13, APF-14]

# Metrics
duration: 24min
completed: 2026-06-29
---

# Phase 33 Plan 09: Final Static, Focused, And Eval Closure Summary

**Runtime RAG/claim boundary guards and target mapping closure with the full Phase 33 focused suite green.**

## Performance

- **Duration:** 24min
- **Started:** 2026-06-28T21:11:05Z
- **Completed:** 2026-06-28T21:34:38Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Migrated Phase 32 static compatibility guards so `rag_context_build` and `claim_verify` are no longer required to be deferred/non-runnable or absent from graph registration.
- Added Phase 33 static architecture coverage for runtime/runnable vocabulary, graph registration, deterministic routers, writer ownership, no repository bypass, no raw projection exposure, and MOCA-approved validation commands.
- Recorded the Phase 32-to-33 target mapping transition and explicit deferrals for Phase 34, Phase 35, Policy Scope, Phase RAG-5, and future real execution boundaries.
- Ran the final focused Phase 33 gate after stale-test migration: `473 passed, 22 warnings in 160.87s (0:02:40)`.

## Task Commits

Each task was committed atomically:

1. **Task 33-09-01 RED: Add failing Phase 33 static guard coverage** - `54685a2` (test)
2. **Task 33-09-01 GREEN: Migrate Phase 32 static guard compatibility** - `fb175d1` (test)
3. **Task 33-09-02: Record mapping, deferrals, and validation closure** - `42d0d42` (docs)
4. **Task 33-09-03: Run final focused Phase 33 gate and migrate stale gate expectations** - `0eb7463` (fix)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/architecture/test_phase33_rag_claim_boundaries.py` - New static guards for Phase 33 runtime graph/RAG/claim boundaries.
- `tests/architecture/test_phase32_static_contract.py` - Removed stale Phase 33 non-runnable/absent graph assertions from Phase 32 compatibility coverage.
- `tests/agent/test_phase22_recommendation_integration.py` - Migrated stale integration expectations to Phase 33 split ownership: generation consumes verified package, claim verification owns route/blocking.
- `tests/agent/test_graph.py` - Updated trace summary shape expectation for safe `rag_claim_summary.v1`.
- `.planning/phases/33-rag-context-build-and-claim-verification/33-RAG-CLAIM-TARGET-MAPPING.md` - Chinese target mapping, writer ownership, route summary, projection/no-leak summary, and explicit deferrals.
- `.planning/phases/32-intent-graph-migration/32-MVP-TARGET-MAPPING.md` - Clarified historical Phase 32 deferral versus Phase 33 runtime behavior.
- `.planning/phases/33-rag-context-build-and-claim-verification/33-VALIDATION.md` - Recorded final closure commands and final gate results.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Recorded handled RED/focused-suite validation failures in Chinese per MOCA rules.

## Decisions Made

- Phase 32 remains historical documentation for `rag_context_build` / `claim_verify` deferral; Phase 33 is the runtime source of truth for runnable graph behavior.
- Stale Phase 22 recommendation integration tests were migrated forward instead of reintroducing `ContextBuilder` / `MaterialClaimVerifier` ownership into `generate_recommendation`.
- The trace summary test now treats `rag_claim_summary.v1` as an intended safe projection from Plan 33-08.
- The final focused suite remains documented as phase-gate-only latency; fast static smoke remains the normal short feedback loop.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Validation Record] Recorded handled TDD RED failure**
- **Found during:** Task 33-09-01
- **Issue:** The required RED run failed as expected because Phase 32 static guards still treated `rag_context_build` and `claim_verify` as non-runnable/absent.
- **Fix:** Appended a Chinese validation issue record after the GREEN fix, per MOCA local validation rules.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` -> `13 passed, 1 warning`
- **Committed in:** `fb175d1`

**2. [Rule 3 - Blocking] Migrated stale final focused-suite expectations**
- **Found during:** Task 33-09-03
- **Issue:** The full focused suite failed on stale Phase 22 integration tests expecting `generate_recommendation` to own RAG build/verifier route and on a graph summary shape that predated `rag_claim_summary`.
- **Fix:** Migrated the tests to Phase 33 ownership boundaries and recorded the handled validation failure in Chinese.
- **Files modified:** `tests/agent/test_phase22_recommendation_integration.py`, `tests/agent/test_graph.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`, `.planning/phases/33-rag-context-build-and-claim-verification/33-VALIDATION.md`
- **Verification:** Targeted rerun -> `6 passed, 2 warnings`; final focused suite -> `473 passed, 22 warnings in 160.87s (0:02:40)`
- **Committed in:** `0eb7463`

---

**Total deviations:** 2 auto-fixed (1 project validation record, 1 blocking stale-test migration).
**Impact on plan:** Both were required to complete the final gate and close the compatibility window. No new runtime surface, endpoint, auth path, schema migration, or service boundary was introduced.

## Issues Encountered

- The first full focused gate failed after 2:43 on stale tests; the issue was fixed in the same task and documented in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Existing LangGraph warnings remain during focused tests: checkpointer serializer deprecation and `extract_slots` config typing. They are pre-existing and non-blocking.

## Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short
```

Result: `13 passed, 1 warning in 0.07s`

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/agent/test_graph.py::test_trace_summary_shape_uses_merged_investigate_tool_name -q --tb=short
```

Result: `6 passed, 2 warnings in 0.13s`

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/agent/test_working_state.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short
```

Result: `473 passed, 22 warnings in 160.87s (0:02:40)`

```bash
uv run ruff check src/knowledge/schemas.py src/knowledge/service.py src/agent/rag_context/schemas.py src/agent/rag_context/claims.py src/agent/rag_context/domain_rules.py src/agent/rag_context/verifier.py src/agent/rag_context/routing.py src/agent/nodes/rag_context_build.py src/agent/nodes/claim_verify.py src/agent/nodes/generate_recommendation.py src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py src/agent/nodes/final_response.py src/agent/routing.py src/agent/graph.py src/agent/graph_vocabulary.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/working_state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/api/schemas/agent_runs.py src/repositories/trace_repo.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_graph.py
```

Result: `All checks passed!`

```bash
git diff --check
```

Result: passed

## TDD Gate Compliance

- RED commit present for Task 33-09-01: `54685a2`
- GREEN commit present after RED for Task 33-09-01: `fb175d1`
- Refactor commit not needed.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 33 is ready for final metadata closure: APF-13/APF-14 are complete, static guards are migrated, and the final focused suite is green.
- Phase 34 owns approval/action binding, Phase 35 owns broad replay/eval hardening, Policy Scope owns tenant-over-global/global fallback, Phase RAG-5 owns external search backend, and a future execution-boundary phase owns real external execution.

## Self-Check: PASSED

- Created files found: `tests/architecture/test_phase33_rag_claim_boundaries.py`, `.planning/phases/33-rag-context-build-and-claim-verification/33-RAG-CLAIM-TARGET-MAPPING.md`, `.planning/phases/33-rag-context-build-and-claim-verification/33-09-SUMMARY.md`.
- Task commits found: `54685a2`, `fb175d1`, `42d0d42`, `0eb7463`.
- Final command records found in `33-VALIDATION.md` and `33-09-SUMMARY.md`.
- `git diff --check` passed after summary creation.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-29*
