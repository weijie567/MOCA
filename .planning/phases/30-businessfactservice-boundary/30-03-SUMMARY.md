---
phase: 30-businessfactservice-boundary
plan: 03
subsystem: agent
tags: [business-facts, projection, authority-boundary, no-leak, tdd]

requires:
  - phase: 30-02
    provides: BusinessToolService compatibility wrapping over BusinessFactService and ToolPlatform delegation
provides:
  - ToolResultProjector business refs sourced only from ToolResultV2.business_fact_refs
  - Investigate no-leak coverage for denied, stale, and unavailable business fact results
  - Authority-boundary tests for memory, RAG/policy evidence, model knowledge, prompt summaries, and raw repository rows
  - Static ownership tests for investigate and BusinessToolExecutor boundaries
affects: [Phase 31, Phase 33, Phase 34, Phase 35, APF-08, ToolPlatform, investigate]

tech-stack:
  added: []
  patterns:
    - Projection authority comes from service-approved ToolResultV2 envelope refs only
    - Denied/stale/unavailable business reads add safe errors but no facts, refs, or claim dependencies
    - MaterialClaimVerifier classifies prompt summaries and raw repository rows as non-authoritative for business facts

key-files:
  created:
    - .planning/phases/30-businessfactservice-boundary/30-03-SUMMARY.md
  modified:
    - src/tools/projection.py
    - src/agent/nodes/investigate.py
    - src/agent/rag_context/verifier.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/rag_context/test_authority_boundaries.py
    - tests/agent/test_policy_retrieval_ownership.py

key-decisions:
  - "ToolResultProjector no longer treats result.data business identifiers as authoritative business refs."
  - "Investigate records non-success business results as safe errors only; denied resources do not create claim dependency refs."
  - "Prompt summaries and raw repository-row-shaped context receive explicit non-authority reason codes while BusinessFactRefV1 remains required."

patterns-established:
  - "Envelope-only business ref projection: normalized_result, prompt_projection.resource_refs, and projection.resource_refs all derive from ToolResultV2.business_fact_refs."
  - "No-leak graph failure: denied, stale, and unavailable business result paths leave business_context facts/refs, last_business_context_refs, and claim_dependency_map empty."
  - "Authority-substitution tests: contextual sources can explain rejection reason codes but never satisfy business_fact_claim without BusinessFactRefV1."

requirements-completed: [APF-08]

duration: 10min
completed: 2026-06-28
---

# Phase 30 Plan 03: Projection and Authority Boundary Summary

**Business fact authority now reaches graph and prompt surfaces only through service-approved BusinessFactRefV1 envelopes.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-27T19:18:49Z
- **Completed:** 2026-06-27T19:29:03Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Hardened `ToolResultProjector` so data-shaped identifiers such as `order_no`, `refund_case_no`, `ticket_id`, `tracking_no`, and `merchant_id` no longer become business refs or resource refs.
- Added graph no-leak tests for denied, unavailable, and stale business results, including prompt summaries, `business_context`, `last_business_context_refs`, and `claim_dependency_map`.
- Removed synthetic denied claim dependency refs from `investigate`, leaving non-success business reads as safe errors only.
- Added authority-boundary tests proving memory, RAG/policy evidence, model knowledge, prompt summaries, and raw repository-row-shaped context cannot support business fact claims without `BusinessFactRefV1`.
- Added static ownership tests proving `investigate` stays on `ToolPlatform` without business service/repository imports, and `BusinessToolExecutor` imports the service boundary without raw integration/repository seams.

## Task Commits

Each TDD task was committed atomically:

1. **Task 1 RED: projector business-ref tests** - `054d018` (test)
2. **Task 1 GREEN: envelope-only projector refs** - `9f36144` (feat)
3. **Task 2 RED: investigate no-leak tests** - `e457de4` (test)
4. **Task 2 GREEN: remove denied dependency refs** - `2697b02` (fix)
5. **Task 3 RED: authority-boundary tests** - `782b1c7` (test)
6. **Task 3 GREEN: non-authority source reason codes** - `6f6799c` (fix)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/tools/projection.py` - Removes data-derived business ref/resource ref authority and counts envelope business refs.
- `src/agent/nodes/investigate.py` - Stops emitting synthetic denied claim dependencies.
- `src/agent/rag_context/verifier.py` - Adds prompt-summary and raw-repository-row non-authority reason codes for business fact claims.
- `tests/agent/test_nodes/test_investigate.py` - Adds projector envelope-vs-data tests and denied/stale/unavailable graph no-leak tests.
- `tests/agent/rag_context/test_authority_boundaries.py` - Adds APF-08 substitution negative tests for memory, model, prompt summary, and raw repository rows.
- `tests/agent/test_policy_retrieval_ownership.py` - Adds static source-boundary tests for investigate and BusinessToolExecutor.

## Decisions Made

- Kept `investigate` free of `BusinessFactService`, `BusinessToolService`, raw demo integrations, and business repositories.
- Kept `BusinessToolExecutor` allowed to import the business service boundary, while tests forbid raw demo integration and repository imports there.
- Added only narrow verifier reason-code classification for APF-08 non-authority sources; Phase 33 still owns full claim verification expansion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed denied business claim dependency refs**
- **Found during:** Task 2 (investigate no-leak RED tests)
- **Issue:** `investigate` added a synthetic `denied:{resource}` claim dependency for `permission_denied` business results. It did not leak the caller-supplied id, but it still placed a non-service-approved resource ref on the dependency surface.
- **Fix:** Removed the synthetic denied dependency append. Successful service-approved business refs still populate claim dependencies.
- **Files modified:** `src/agent/nodes/investigate.py`
- **Verification:** `uv run pytest tests/agent/test_nodes/test_investigate.py -q --tb=short`
- **Committed in:** `2697b02`

**2. [Rule 2 - Missing Critical] Added prompt/raw-row non-authority reason codes**
- **Found during:** Task 3 (authority-boundary RED tests)
- **Issue:** Business fact claims already failed closed without `BusinessFactRefV1`, but prompt summaries and raw repository-row-shaped sources were not explicitly classified as non-authoritative.
- **Fix:** `MaterialClaimVerifier` now reports `prompt_summary_not_business_authority` and `raw_repository_row_not_business_authority` when those contextual sources are present for business fact claims.
- **Files modified:** `src/agent/rag_context/verifier.py`
- **Verification:** `uv run pytest tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short`
- **Committed in:** `6f6799c`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes tighten APF-08 no-leak/authority boundaries without implementing Phase 31 memory isolation, Phase 33 full claim verification, Phase 34 approval/action binding, Phase 35 replay/eval broad hardening, Phase 36+ DB/RLS, physical microservices, or real external execution.

## Issues Encountered

- Task 1 RED failed as expected because `ToolResultProjector` still inferred business refs and `resource_refs` from `result.data`.
- Task 2 RED failed as expected because denied business results created a synthetic dependency ref.
- Task 3 RED failed as expected for missing prompt-summary and raw-repository-row non-authority reason codes.

## Known Stubs

None. Stub scan found only intentional empty test literals and initialized containers, not runtime placeholder data.

## Threat Flags

None. This plan added no new network endpoints, auth paths, file access patterns, schema changes, or trust-boundary surfaces beyond the threat mitigations already listed in the plan.

## Authentication Gates

None.

## Verification

- `uv run pytest tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` - passed (`32 passed`, 1 existing LangGraph deprecation warning).
- `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` - passed (`188 passed`, 1 existing LangGraph deprecation warning).
- `uv run ruff check src/tools/projection.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py` - passed.
- Additional changed-source lint: `uv run ruff check src/agent/nodes/investigate.py src/agent/rag_context/verifier.py` - passed.
- `git diff --check` - passed.

## TDD Gate Compliance

- Task 1 RED commit exists before GREEN: `054d018` -> `9f36144`.
- Task 2 RED commit exists before GREEN: `e457de4` -> `2697b02`.
- Task 3 RED commit exists before GREEN: `782b1c7` -> `6f6799c`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 30 is ready to close. Business facts now flow through service-approved refs into ToolPlatform projection and graph state, and APF-08 substitution bans are pinned for downstream Phase 31 memory, Phase 33 RAG/claim, Phase 34 approval/action, and Phase 35 replay/eval hardening.

---
*Phase: 30-businessfactservice-boundary*
*Completed: 2026-06-28*

## Self-Check: PASSED

- Found summary file at `.planning/phases/30-businessfactservice-boundary/30-03-SUMMARY.md`.
- Found task commits `054d018`, `9f36144`, `e457de4`, `2697b02`, `782b1c7`, and `6f6799c` in git history.
- Found all key created/modified files referenced by this summary.
- No unexpected tracked file deletions were detected in task commits.
