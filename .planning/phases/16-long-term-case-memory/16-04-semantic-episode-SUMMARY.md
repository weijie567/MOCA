---
phase: 16-long-term-case-memory
plan: 04
subsystem: memory
tags: [semantic-episode, long-term-memory, review-gate, prompt-safety, tdd]

requires:
  - phase: 16-03-long-term-memory-service
    provides: LongTermMemoryService review policy where semantic_episode_candidate sources become needs_review
provides:
  - Candidate-only Semantic Episode projection layer
  - Prompt-safe semantic candidate model convertible to long-term memory write candidates
  - Contract tests proving semantic candidates are review-gated and separate from session_memories
affects:
  - 16-05-tombstone-supersede
  - 16-06-reviewed-case-memory
  - 16-07-context-assembler-memory
  - 16-08-memory-retrieval-integration

tech-stack:
  added: []
  patterns:
    - Pure projection module creates semantic candidates without persistence side effects
    - Semantic candidates use source_type=semantic_episode_candidate and review_status=needs_review
    - Candidate payloads carry bounded prompt-safe source summaries only

key-files:
  created:
    - src/memory/semantic_episode.py
    - tests/memory/test_semantic_episode_projection.py
  modified: []

key-decisions:
  - "Semantic Episode remains a candidate-only projection layer and does not create an authoritative semantic episode table."
  - "SemanticEpisodeCandidate converts to LongTermMemoryWriteCandidate with source_type=semantic_episode_candidate so existing long-term memory policy forces needs_review."
  - "Projection output keeps prompt-safe summaries and ignores raw payload, policy text, evidence refs, authority bodies, and replay/debug blobs."
  - "Semantic episode projection has no repository dependency and does not mutate session_memories."

patterns-established:
  - "Semantic episode extraction reads summary_json semantic_episode conventions and emits typed candidates by kind."
  - "Semantic candidates are reusable by later review/context plans through to_long_term_memory_candidate(), not direct retrieval."

requirements-completed: [LONGMEM-01, MEMREVIEW-01, MEMEVAL-01]

duration: 6 min
completed: 2026-06-17
---

# Phase 16 Plan 04: Semantic Episode Candidate Layer Summary

**Candidate-only Semantic Episode projection with review-gated long-term memory conversion and prompt-safety tests**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-17T16:02:58Z
- **Completed:** 2026-06-17T16:09:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `SemanticEpisodeCandidate` and `project_semantic_episode_candidates(...)` as a pure projection layer under `src/memory/semantic_episode.py`.
- Added TDD coverage proving semantic output is candidate-only, review-gated before retrieval, separate from `session_memories`, and prompt-safe.
- Verified existing `LongTermMemoryService` behavior correctly persists semantic episode candidates as `needs_review` and excludes them from retrieval.

## Task Commits

Each task was committed atomically:

1. **Task 16-04-01: Add semantic episode projection tests** - `8d00f5b` (test, RED)
2. **Task 16-04-02: Implement semantic episode candidate projection** - `d5517e0` (feat, GREEN)

## Files Created/Modified

- `src/memory/semantic_episode.py` - Semantic episode candidate schema, summary-based projection helper, prompt-safe source summary bounding, and long-term write candidate conversion.
- `tests/memory/test_semantic_episode_projection.py` - Contract tests for candidate-only projection, needs-review persistence, session memory isolation, and forbidden raw/authority payload exclusion.

## Decisions Made

- Kept Semantic Episode as a pure projection helper instead of adding a new table or repository.
- Reused the existing Phase 16 long-term memory write path for review gating rather than adding a parallel semantic review mechanism.
- Treated source summaries as prompt-safe context only; raw tool payloads, policy text, evidence refs, authority bodies, and replay/debug blobs are not projected.

## TDD Gate Compliance

- **RED:** `uv run pytest tests/memory/test_semantic_episode_projection.py -q` failed before implementation because `src.memory.semantic_episode` did not exist.
- **GREEN:** `uv run pytest tests/memory/test_semantic_episode_projection.py -q` passed after adding the projection module.
- **REFACTOR:** No separate refactor commit was needed.

## Verification

- `uv run pytest tests/memory/test_semantic_episode_projection.py -q` - passed, 4 tests.
- `uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_long_term_memory_service.py -q` - passed, 9 tests.
- `uv run ruff check src/memory/semantic_episode.py tests/memory/test_semantic_episode_projection.py` - passed.
- `grep -n "EvidenceRefV1\|ApprovalRequest\|ActionDraft" src/memory/semantic_episode.py || true` - no matches.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. Stub scan found only local empty list/dict initializers and test empty-result assertions, not runtime placeholder data or unwired UI/data flow.

## Issues Encountered

None beyond the expected TDD RED failure.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-05-tombstone-supersede-PLAN.md`. Semantic candidates now enter the same long-term memory candidate pipeline as other unreviewed inference sources, while remaining separate from session memory and direct retrieval.

## Self-Check: PASSED

- Verified key files exist: `src/memory/semantic_episode.py`, `tests/memory/test_semantic_episode_projection.py`, and this SUMMARY.
- Verified task commits exist in git history: `8d00f5b` and `d5517e0`.
- Verified final commands passed: focused semantic episode pytest, combined semantic/long-term service pytest, and Ruff check.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*
