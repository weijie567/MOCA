---
phase: 33-rag-context-build-and-claim-verification
plan: 33-07
subsystem: agent
tags: [rag, claim-verification, final-response, working-state, leakage]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: claim_verification_bundle and safe_support_refs action-gate authority from Plan 33-06
provides:
  - safe final-response wording for blocked RAG packages and blocked claim bundles
  - working-state evidence projection from claim safe refs or package prompt-safe refs
  - no-leak regression coverage for package debug, verifier prompt, private reasoning, source-block, OCR, and candidate-only refs
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - final_response converts package/bundle block states into sanitized backend-owned verification payloads
    - WorkingStateV1 resolves refs through safe_support_refs and package prompt_projection before package evidence_map fallback

key-files:
  created:
    - .planning/phases/33-rag-context-build-and-claim-verification/33-07-SUMMARY.md
  modified:
    - src/agent/nodes/final_response.py
    - src/agent/working_state.py
    - tests/agent/test_phase22_final_response.py
    - tests/agent/test_working_state.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Blocked RAG package and claim bundle states render through sanitized insufficient-evidence/manual-review templates instead of recommendation draft text."
  - "Working-state evidence refs prefer claim bundle/state safe_support_refs, then package prompt_projection safe refs, and only fallback to verified evidence_map when no prompt-safe subset exists."

patterns-established:
  - "New package/bundle final-response paths mark their safe projection source and suppress draft missing_info to avoid raw verifier/debug leakage."
  - "Prompt-facing working-state refs resolve string or dict safe refs through the verified evidence map and then apply the EvidenceRef allowlist."

requirements-completed: [APF-13, APF-14]

duration: 8min
completed: 2026-06-29
---

# Phase 33 Plan 07: Final Response And Working-State No-Leak Projections Summary

**Blocked RAG packages and claim bundles now collapse into safe final-response templates, while working-state evidence only exposes verified prompt-safe or claim-safe refs.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-28T20:23:27Z
- **Completed:** 2026-06-28T20:31:09Z
- **Tasks:** 1 TDD task
- **Files modified:** 5

## Accomplishments

- Added final-response handling for blocking `rag_context_status` values and non-continue / blocked `claim_verification_bundle` states.
- Prevented package/bundle block rendering from reading draft `missing_info`, so raw reason payloads, verifier prompts, debug projections, source-block IDs, OCR internals, and private reasoning stay out of user-facing responses.
- Updated `WorkingStateV1.retrieved_evidence_refs` to use claim `safe_support_refs` first, package `prompt_projection` safe refs second, and verified package maps only as compatibility fallback.
- Added focused RED/GREEN coverage for final-response package/bundle blocks, working-state safe-support precedence, and candidate-only no-leak behavior.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 33-07-01 RED: safe projection coverage** - `ed39684` (test)
2. **Task 33-07-01 GREEN: safe final and working projections** - `eeff715` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/nodes/final_response.py` - Added sanitized package/bundle verification payload projection and safe manual-review rendering for new block states.
- `src/agent/working_state.py` - Added safe-support and prompt-projection ref resolution before verified package-map fallback.
- `tests/agent/test_phase22_final_response.py` - Added blocked package and blocked claim bundle no-leak final-response regressions.
- `tests/agent/test_working_state.py` - Added verified package helpers, safe-support precedence coverage, and candidate-only no-leak assertions.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Recorded handled baseline/RED validation failures in Chinese per project rules.

## Decisions Made

- Blocked claim bundles are rendered as manual-review when blocked claims are present, even if raw bundle route shape is malformed or only state-level blocked claims exist.
- Blocking package statuses use safe final response text and never reuse model draft reasoning or missing-info payloads.
- Package `prompt_projection.safe_refs` is treated as the prompt-safe subset when present; older packages without prompt-safe refs continue to use verified `evidence_map` for compatibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Validation Record] Recorded handled focused-suite and RED failures**
- **Found during:** Task 33-07-01 RED/GREEN execution
- **Issue:** MOCA project rules require every local validation failure to be recorded. The initial focused suite had a stale working-state expectation, and the TDD RED suite failed on the intended missing package/bundle projection behavior.
- **Fix:** Appended a Chinese record to `.planning/LOCAL-VALIDATION-ISSUES.md` with symptoms, reproduction command, evidence, root cause, fixes, remaining issues, and next investigation entry points.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Focused pytest, Ruff, acceptance greps, and `git diff --check` passed.
- **Committed in:** `eeff715`

---

**Total deviations:** 1 auto-fixed (project-rule correctness).
**Impact on plan:** The validation record is required by project rules and does not widen implementation scope.

## Issues Encountered

- The initial focused suite failed because `tests/agent/test_working_state.py` still expected legacy `evidence_refs` to enter working-state evidence. The RED test update aligned that expectation with verified package refs.
- RED failed as expected: final responses rendered unsafe draft recommendation text for blocked package/bundle states, and working state emitted a package-map ref that was not claim-safe.
- Existing LangGraph checkpointer serializer deprecation warning still appears in focused tests; it is pre-existing and non-blocking.

## Known Stubs

None. Stub scan hits were optional Pydantic defaults, local accumulator initializations, and intentional empty lists in tests.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_final_response.py tests/agent/test_working_state.py tests/agent/rag_context/test_leakage.py -q --tb=short` -> 28 passed, 1 warning
- `uv run ruff check src/agent/nodes/final_response.py src/agent/working_state.py tests/agent/test_phase22_final_response.py tests/agent/test_working_state.py tests/agent/rag_context/test_leakage.py` -> passed
- `rg -n "claim_verification_bundle|rag_context_status|blocked_claims|safe_support_refs" src/agent/nodes/final_response.py src/agent/working_state.py tests/agent/test_phase22_final_response.py tests/agent/test_working_state.py tests/agent/rag_context/test_leakage.py` -> found final/working-state support
- `rg -n "SOURCE_BLOCK|OCR|debug_projection|verifier_prompt|private_reasoning|candidate-only|candidate_only" tests/agent/rag_context/test_leakage.py tests/agent/test_working_state.py tests/agent/test_phase22_final_response.py` -> found no-leak sentinel assertions
- `git diff --check` -> passed

## TDD Gate Compliance

- RED commit present for Task 33-07-01: `ed39684`
- GREEN commit present after RED: `eeff715`
- Refactor commit not needed.

## Next Phase Readiness

Ready for Plan 33-08. Final and working-state surfaces now consume package/bundle safe projections without leaking raw verifier/debug/candidate internals.

## Self-Check: PASSED

- Verified summary file exists on disk: `.planning/phases/33-rag-context-build-and-claim-verification/33-07-SUMMARY.md`.
- Verified task commits are reachable: `ed39684`, `eeff715`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-29*
