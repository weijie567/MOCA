---
phase: 22-rag-context-builder-hallucination-control
plan: "02"
subsystem: testing
tags: [pytest, eval, rag-context, hallucination-control, red-tests]

# Dependency graph
requires:
  - phase: 22-01-wave-0-unit-scaffold
    provides: "RED unit scaffold for ContextBuilder, MaterialClaim, verifier tiers, authority boundaries, and deterministic routes."
provides:
  - "Wave 0 RED pytest scaffold for evidence validation, latest/current version gates, scope gates, and leakage boundaries."
  - "Wave 0 RED integration scaffold for recommendation, graph/action boundary, and final response routing behavior."
  - "Deterministic local hallucination-control JSONL dataset and eval CLI with blocking metrics."
affects: [phase-22, context-builder, verifier-routing, action-boundary, hallucination-eval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Future Phase 22 imports stay inside pytest helpers so RED tests collect cleanly."
    - "Eval CLI validates JSONL locally and fails thresholds without live model, DB, Redis, or network dependencies."

key-files:
  created:
    - tests/knowledge/test_phase22_evidence_validation.py
    - tests/agent/rag_context/test_leakage.py
    - tests/agent/test_phase22_recommendation_integration.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/agent/test_phase22_final_response.py
    - evaluation/golden/phase22_hallucination_cases.jsonl
    - scripts/eval_phase22_hallucination.py
  modified:
    - tests/knowledge/test_phase21_boundaries.py

key-decisions:
  - "Plan 22-02 remains RED-only; production rag_context APIs and graph behavior are reserved for later implementation plans."
  - "Latest/current version validation is pinned separately from text hash and effective-date freshness validation."
  - "Phase 21 boundary guards now allow Phase 22-owned claim/verifier names only in owned files while preserving Phase 23/RAG-5/Phase 17 scope bans."

patterns-established:
  - "Evidence validation tests use canonical row fakes to isolate tenant, scope, duplicate-key, hash, freshness, and latest-version exclusions."
  - "Graph/action/final RED tests assert backend-selected verifier routes and model-selected safety route rejection."
  - "Phase 22 eval cases carry expected verifier status, route, metrics bucket, and must-not-contain sentinels."

requirements-completed:
  - CTX-02
  - CTX-06
  - VER-06
  - RTE-03
  - RTE-04
  - RTE-05
  - BND-01
  - BND-02
  - BND-03
  - BND-04
  - BND-05
  - EVAL-01
  - EVAL-02
  - EVAL-03
  - EVAL-04
  - EVAL-05

# Metrics
duration: 13 min
completed: 2026-06-19
---

# Phase 22 Plan 02: Wave 0 Integration and Eval Scaffold Summary

**RED safety scaffold for canonical evidence validation, leakage boundaries, graph/action/final routing, and hallucination-control eval metrics**

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-19T08:58:57Z
- **Completed:** 2026-06-19T09:12:28Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added evidence validation RED tests for malformed tenant IDs, wrong tenant refs, wrong scope tied to `merchant_scope`/`doc_type`/`risk_level`, duplicate keys, text hash mismatch, freshness, and latest/current policy version mismatch.
- Added leakage RED tests covering prompt, final response, memory, replay, business fact, and action snapshot surfaces.
- Added graph/action/final integration RED tests proving backend verifier routes must drive recommendation, risk, approval, action draft, snapshot, and safe final-response behavior.
- Added 15 deterministic hallucination-control golden cases and a local eval CLI that reports the required Phase 22 metrics.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create evidence validation and leakage RED tests** - `5c62b24` (test)
2. **Task 2: Create graph/action/final-response integration RED tests** - `8b46774` (test)
3. **Task 3: Create hallucination-control golden eval scaffold** - `2d98edf` (test)

**Plan metadata:** final docs commit.

## Files Created/Modified

- `tests/knowledge/test_phase22_evidence_validation.py` - RED tests for canonical re-fetch, tenant/scope/hash/freshness/latest-version exclusions.
- `tests/agent/rag_context/test_leakage.py` - RED leakage tests for prompt, final, memory, replay, business fact, and action snapshot surfaces.
- `tests/knowledge/test_phase21_boundaries.py` - Boundary guard narrowed for Phase 22-owned claim/verifier files while preserving EvidenceRefV1 identity and scope bans.
- `tests/agent/test_phase22_recommendation_integration.py` - RED tests for shared ContextBuilder/verifier use and backend-owned safety route selection.
- `tests/agent/test_phase22_action_boundary.py` - RED tests for non-allow verifier outcomes blocking proposed actions, approval routing, action drafts, and snapshots.
- `tests/agent/test_phase22_final_response.py` - RED tests for safe non-allow final response wording and debug/provenance leakage prevention.
- `evaluation/golden/phase22_hallucination_cases.jsonl` - Golden cases for supported/unsupported/missing/stale/conflict/unauthorized/hash/OCR/business/action/fail-closed categories.
- `scripts/eval_phase22_hallucination.py` - Deterministic local eval CLI with JSONL schema validation, metrics report, and threshold failure mode.

## Verification

- `bash -lc 'set +e; uv run pytest tests/knowledge/test_phase22_evidence_validation.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_phase21_boundaries.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 22 tests and failed only on missing `src.agent.rag_context` for Phase 22 RED tests.
- `bash -lc 'set +e; uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 23 tests and failed on missing Phase 22 recommendation/routing/action/final behavior.
- `bash -lc 'set +e; uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds; status=$?; test "$status" -eq 1'` - passed wrapper; script loaded 15 cases and failed thresholds because the Phase 22 metrics adapter is intentionally missing in Wave 0.
- `bash -lc 'set +e; uv run pytest tests/knowledge/test_phase22_evidence_validation.py tests/agent/rag_context/test_leakage.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/knowledge/test_phase21_boundaries.py -q; status=$?; test "$status" -eq 1'` - passed wrapper; pytest collected 45 tests, 14 boundary tests passed, and 31 RED tests failed for missing Phase 22 implementation behavior.
- `uv run ruff check tests/knowledge/test_phase22_evidence_validation.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_phase21_boundaries.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py scripts/eval_phase22_hallucination.py` - passed.

## Decisions Made

- Kept this plan RED-only. The expected test failure remains missing `src.agent.rag_context` or missing graph/action/final integration behavior.
- Made the eval CLI stdout-first by default, with optional `--output`, so standard verification does not leave generated report artifacts in the working tree.
- Used Chinese user-facing expected phrases in final-response RED tests to match the existing MOCA response style.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

**1. Intentional Wave 0 eval fallback**
- **File:** `scripts/eval_phase22_hallucination.py`
- **Lines:** 88-101
- **Reason:** The CLI returns `implementation_missing` when `src.agent.rag_context.metrics.evaluate_hallucination_case` is absent. This is the planned RED eval failure path and should be replaced by later Phase 22 implementation work.

## Authentication Gates

None.

## Threat Flags

None. This plan added tests, local JSONL fixtures, and a local eval CLI only; it introduced no new network endpoint, auth path, schema boundary, or runtime external I/O.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 22-03. The next implementation plan can start making `src.agent.rag_context` and canonical evidence validation pass against the Wave 0 tests from Plans 22-01 and 22-02.

## Self-Check: PASSED

- Summary file exists.
- All seven planned created files exist, and the planned Phase 21 boundary test update exists.
- Task commits found: `5c62b24`, `8b46774`, `2d98edf`.

---
*Phase: 22-rag-context-builder-hallucination-control*
*Completed: 2026-06-19*
