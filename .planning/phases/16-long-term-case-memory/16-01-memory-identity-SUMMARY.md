---
phase: 16-long-term-case-memory
plan: 01
subsystem: memory
tags: [memory-identity, canonical-hash, pydantic, tdd]

requires:
  - phase: 15.1-memory-foundation-v2
    provides: conversation/tool/summary foundation and prompt-safe memory boundaries
provides:
  - memory_identity.v1 canonical content, canonical identity, source identity, and candidate hashes
  - prompt-safe MemorySourceRefV1, MemoryIdentityV1, and MemoryCandidateIdentityV1 schemas
  - golden tests for memory identity stability and authority-boundary rejection
affects: [16-02-schema-migration, 16-03-long-term-memory-service, 16-05-tombstone-supersede, 16-09-legacy-search-eval-closure]

tech-stack:
  added: []
  patterns:
    - CanonicalHashProfile v1 reuse for memory-domain identities
    - Pydantic extra-forbid prompt-safe schemas for memory identity contracts

key-files:
  created:
    - src/memory/identity.py
    - tests/memory/test_memory_identity.py
  modified:
    - src/memory/schemas.py

key-decisions:
  - "Memory identity helpers stay in src/memory/identity.py instead of src/common because the normalization and source-ref allowlist are memory-domain rules."
  - "MemorySourceRefV1 was added now because downstream tombstone/source fallback code needs the same authoritative typed key set."
  - "Candidate hashes accept only the stable envelope fields and reuse content_hash/source_identity_hash rather than raw payloads or authority-bearing bodies."

patterns-established:
  - "memory_identity.v1 hashes use explicit schema_version namespaces for content, canonical identity, source identity, and candidate identity."
  - "Source identity normalizes optional allowed keys by filling absent optional fields with null while requiring source_type when a non-empty source ref is hashed."

requirements-completed: [MEMID-01, MEMEVAL-01]

duration: 6 min
completed: 2026-06-17
---

# Phase 16 Plan 01: memory_identity.v1 Summary

**Stable memory identity hashing with prompt-safe typed source refs and TDD golden coverage for long-term/case memory candidates**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-17T15:15:46Z
- **Completed:** 2026-06-17T15:22:31Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `memory_identity.v1` helpers for normalized content hashes, canonical memory identity hashes, typed source identity hashes, and write-event candidate hashes.
- Added prompt-safe Pydantic identity schemas with `extra="forbid"` and `sha256:` pattern validation.
- Added golden tests covering whitespace normalization, type-bound content hashing, tenant/scope/source-bound candidate hashing, unknown source-key rejection, and authority-boundary imports.

## Task Commits

Each task was committed atomically:

1. **Task 16-01-01: Add memory identity golden tests** - `dd4cbcb` (test, RED)
2. **Task 16-01-02: Implement memory identity helpers** - `b77f736` (feat, GREEN)
3. **Task 16-01-03: Add prompt-safe identity schemas** - `8437608` (feat)

## Files Created/Modified

- `src/memory/identity.py` - Defines `memory_identity.v1` constants, source-ref allowlist, normalization, and canonical hash helpers.
- `src/memory/schemas.py` - Adds prompt-safe `MemorySourceRefV1`, `MemoryIdentityV1`, and `MemoryCandidateIdentityV1`.
- `tests/memory/test_memory_identity.py` - Adds TDD golden and boundary tests for identity helpers and schemas.

## Decisions Made

- Kept identity helpers under `src/memory/` because the content normalization and source-ref fallback semantics are specific to reviewed memory.
- Required `source_type` for any non-empty source identity hash while allowing the remaining authoritative source keys to be optional/null.
- Added schemas in this plan because downstream service and tombstone plans need a typed key set for safe source fallback.

## TDD Gate Compliance

- **RED:** `uv run pytest tests/memory/test_memory_identity.py -q` failed before implementation with `ModuleNotFoundError: No module named 'src.memory.identity'`.
- **GREEN:** The same command passed after `src/memory/identity.py` was added.
- **REFACTOR:** No separate refactor commit was needed.

## Verification

- `uv run pytest tests/memory/test_memory_identity.py -q` - passed, 7 tests.
- `uv run ruff check src/memory/identity.py tests/memory/test_memory_identity.py` - passed.
- `uv run ruff check src/memory/schemas.py` - passed.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

None. The initial failing pytest run was the expected TDD RED gate.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-02-schema-migration-PLAN.md`. The identity helpers and typed source-ref schema are available for long-term/case memory tables, tombstones, and write-event candidate identity checks.

## Self-Check: PASSED

- Verified key files exist: `src/memory/identity.py`, `src/memory/schemas.py`, `tests/memory/test_memory_identity.py`, and this SUMMARY.
- Verified task commits exist in git history: `dd4cbcb`, `b77f736`, and `8437608`.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-17*
