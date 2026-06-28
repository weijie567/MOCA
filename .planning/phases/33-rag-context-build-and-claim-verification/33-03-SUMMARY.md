---
phase: 33-rag-context-build-and-claim-verification
plan: 33-03
subsystem: agent-graph
tags: [rag, material-claims, recommendation-generation, prompt-safety]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: runnable rag_context_build node and VerifiedEvidencePackageV1 prompt/evidence maps
  - phase: 33-rag-context-build-and-claim-verification
    provides: KnowledgeService-owned MaterialClaimV1 and ClaimVerificationBundleV1 contracts
provides:
  - recommendation_generation consumes verified package prompt_projection, citation_map, and evidence_map
  - canonical MaterialClaimV1 dictionaries emitted from generation with generated_from_step=recommendation_generation
  - generation no longer builds RAG context or verifies claim support
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN commits for generation boundary migration
    - verified-package-only prompt context for recommendation generation
    - canonical MaterialClaimV1 emission before downstream claim verification

key-files:
  created:
    - .planning/phases/33-rag-context-build-and-claim-verification/33-03-SUMMARY.md
  modified:
    - src/agent/nodes/generate_recommendation.py
    - src/agent/rag_context/claims.py
    - tests/agent/test_nodes/test_generate_recommendation.py
    - tests/agent/rag_context/test_material_claims.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "recommendation_generation consumes only verified package prompt/evidence projections for policy context."
  - "recommendation_generation emits canonical MaterialClaimV1 dictionaries but does not verify support or write package/bundle fields."
  - "Legacy generate_recommendation source-node claims normalize to generated_from_step=recommendation_generation."

patterns-established:
  - "Generation is a pure prompt/material-claim boundary; support decisions belong to later claim verification."
  - "Policy snippets entering generation prompts are bounded from verified_evidence_package.prompt_projection."

requirements-completed: [APF-14]

duration: 15min
completed: 2026-06-28
---

# Phase 33 Plan 03: MaterialClaimV1 Emission Summary

**Recommendation generation now consumes verified evidence-package prompt context and emits canonical MaterialClaimV1 records without owning claim verification.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-28T19:06:01Z
- **Completed:** 2026-06-28T19:20:44Z
- **Tasks:** 1 TDD task
- **Files modified:** 5 including validation log, excluding this summary

## Accomplishments

- Removed generation-local RAG context building and material-claim verification calls from `generate_recommendation`.
- Added verified-package prompt/evidence adapters that read `prompt_projection`, `citation_map`, and `evidence_map`.
- Emitted top-level and draft-embedded canonical `material_claims` using `claim_type`, `risk_hints`, and `generated_from_step="recommendation_generation"`.
- Preserved citation membership validation against verified package evidence refs while leaving support decisions to downstream claim verification.

## Task Commits

TDD RED/GREEN commits:

1. **Task 33-03-01 RED: Emit canonical material claims only** - `21f8a9b` (test)
2. **Task 33-03-01 GREEN: Emit canonical material claims only** - `28a73e6` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/nodes/generate_recommendation.py` - Reads verified package projections, bounds package snippets, emits canonical material claims, and stops writing RAG/verifier package or bundle fields.
- `src/agent/rag_context/claims.py` - Normalizes legacy generation source names to `recommendation_generation` and accepts canonical claim payloads for dependency-map projection.
- `tests/agent/test_nodes/test_generate_recommendation.py` - Adds boundary tests for verified-package prompt use, canonical claim output, fail-closed unusable packages, and removed generation-owned verification.
- `tests/agent/rag_context/test_material_claims.py` - Pins canonical generated-from step compatibility.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records handled local validation failures, the invalid bare Python entrypoint rerun, and GSD metadata SDK drift corrected during wrap-up.

## Decisions Made

- Kept citation membership validation in generation because it validates copied citation objects against verified package evidence identity; it does not infer semantic support.
- Did not add `claim_verify` graph wiring or bundle hard gates in this plan; those remain owned by later Phase 33 plans.
- Treated `verified_evidence_package` mentions in generation as read-only package consumption, not writer ownership.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Validation Record] Recorded handled validation failures**
- **Found during:** Task 33-03-01 GREEN
- **Issue:** MOCA project rules require local validation failures and environment-entry mistakes to be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`; the plan did not list that file.
- **Fix:** Added a Chinese validation record covering expected RED failures, legacy-test GREEN failures, and the invalid bare `python -m py_compile` command, then reran through `UV_CACHE_DIR=/tmp/uv-cache uv run python -m py_compile ...`.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Final focused pytest, ruff, and `git diff --check` passed.
- **Committed in:** `28a73e6`

---

**Total deviations:** 1 auto-fixed (1 missing critical project validation record).  
**Impact on plan:** Required by project rules; no product scope was added.

## Issues Encountered

- RED failed as expected: old generation still imported/called RAG context builder and claim verifier ownership.
- GREEN first pass exposed old tests monkeypatching the removed knowledge-service path and expecting `verifier_status` / `verification_route`; tests were migrated to verified-package fixtures.
- A bare `python -m py_compile` command was accidentally run and discarded as invalid MOCA validation; the valid `uv run python -m py_compile ...` rerun passed.
- GSD metadata handlers did not fully match MOCA's current planning file format and flag syntax; ROADMAP/STATE were manually synchronized and the drift was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub scan found only typed empty collection defaults and test fixture empty values; no unresolved placeholder behavior was introduced.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, DB schema change, or unplanned trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/rag_context/test_material_claims.py -q --tb=short` -> 29 passed, 1 warning
- `uv run ruff check src/agent/nodes/generate_recommendation.py src/agent/rag_context/claims.py src/knowledge/schemas.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/rag_context/test_material_claims.py` -> passed
- `git diff --check` -> passed
- Static grep guard for `ContextBuilder|MaterialClaimVerifier|verify_claims|determine_verification_route|_verify_recommendation_with_shared_kernel` in `generate_recommendation.py` -> no matches

## TDD Gate Compliance

- RED commit present: `21f8a9b`
- GREEN commit present after RED: `28a73e6`
- Refactor commit not needed.

## Next Phase Readiness

Ready for the next Phase 33 plan: generation produces canonical claims from verified package prompt context; downstream claim verification can now consume `material_claims` without parsing final prose or trusting generation-owned support state.

## Self-Check: PASSED

- Verified summary and key modified files exist on disk.
- Verified task commits are reachable: `21f8a9b`, `28a73e6`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-28*
