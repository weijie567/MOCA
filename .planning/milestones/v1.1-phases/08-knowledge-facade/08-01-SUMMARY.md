---
phase: 08-knowledge-facade
plan: 08-01
subsystem: knowledge
tags: [pydantic, evidence-ref, sha256, sqlalchemy, ingestion]

# Dependency graph
requires:
  - phase: 07-contract-baseline
    provides: normative knowledge and evidence contract baseline
provides:
  - Canonical EvidenceRefV1 and v2 knowledge request/result schemas
  - evidence_text_hash.v1 normalization and hashing
  - Deterministic score-stripped canonical evidence projection
  - Content-stable PolicyDocument version pins during ingestion
affects: [08-02, 08-03, 08-04, 13-approval-state-machine, 15-replay-event-contract]

# Tech tracking
tech-stack:
  added: []
  patterns: [producer-owned canonical evidence schema, row-locked content-version bump, golden-byte contract tests]

key-files:
  created:
    - src/knowledge/__init__.py
    - src/knowledge/text_hash.py
    - src/knowledge/schemas.py
    - tests/knowledge/conftest.py
    - tests/knowledge/test_text_hash.py
    - tests/knowledge/test_evidence_projection.py
  modified:
    - src/rag/ingestion.py
    - src/repositories/policy_document_repo.py
    - tests/test_ingestion.py

key-decisions:
  - "Policy evidence identity uses policy_version = v{PolicyDocument.version}; effective_date is filtering metadata, not identity."
  - "Existing policy rows are fetched with SELECT FOR UPDATE so concurrent changed-content imports serialize version bumps."

patterns-established:
  - "Evidence hash material uses full normalized text and never case-folds."
  - "Canonical evidence projection removes score and uses rank-aware deterministic sorting."

requirements-completed: [KNOW-02]

# Metrics
duration: 5 min
completed: 2026-06-07
---

# Phase 8 Plan 1: Knowledge Contracts Foundation Summary

**Canonical EvidenceRefV1 contracts, golden evidence hash/projection bytes, and row-locked content-version ingestion pins**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-07T02:11:27Z
- **Completed:** 2026-06-07T02:17:03Z
- **Tasks:** 4
- **Files modified:** 10

## Accomplishments

- Added the producer-owned knowledge schema layer with stable evidence identity and v2 search contracts.
- Implemented and froze `evidence_text_hash.v1` plus deterministic score-stripped canonical projection bytes.
- Made `PolicyDocument.version` a true content-version pin using a locked read and single-transaction version bump.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create knowledge package and evidence_text_hash.v1** - `b9050db` (feat)
2. **Task 2: Define canonical knowledge schemas and projection** - `b9f97ef` (feat)
3. **Task 3: Add knowledge contract golden tests** - `c298b5f` (test)
4. **Task 4: Make PolicyDocument.version a content-version pin** - `a937d64` (fix)

## Files Created/Modified

- `src/knowledge/text_hash.py` - Implements NFC/newline/outer-whitespace normalization and SHA-256 evidence hashes.
- `src/knowledge/schemas.py` - Defines EvidenceRefV1, knowledge request/result contracts, citation result schemas, and canonical projection.
- `src/rag/ingestion.py` - Bumps a locked policy document version only when content changes.
- `src/repositories/policy_document_repo.py` - Adds a narrow `SELECT FOR UPDATE` fetch for ingestion.
- `tests/knowledge/` - Freezes evidence hash, identity, and canonical projection behavior.
- `tests/test_ingestion.py` - Covers first, unchanged, changed, and failed content imports.

## Decisions Made

- Pinned `policy_version` to `v{PolicyDocument.version}` to reconcile the spec's date-like example with stable `@v3` evidence identity.
- Used a row lock rather than optimistic version checks because ingestion already owns a single short write transaction after embeddings are generated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired planning metadata handler edge cases**
- **Found during:** Plan completion metadata update
- **Issue:** Phase-start placeholders made `STATE.md` unparsable; subsequent SDK handlers left session placeholders, line-broke `KNOW-02`, and could not update ROADMAP's `TBD` plan count.
- **Fix:** Restored concrete Phase 08 state, repaired requirement formatting, recorded metrics/decisions/session continuity, and updated Phase 8 roadmap progress to 1/6.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Planning files parse as readable Markdown and show Plan 2 of 6, KNOW-02 complete, and Phase 8 at 1/6.

---

**Total deviations:** 1 auto-fixed (1 blocking issue).
**Impact on plan:** Metadata repair only; implementation scope and behavior are unchanged.

## Issues Encountered

None.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge tests/test_ingestion.py -q` - 15 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/knowledge src/rag/ingestion.py src/repositories/policy_document_repo.py tests/knowledge tests/test_ingestion.py` - passed.
- Changed-file boundary confirmed no edits under `src/agent/`, `src/db/models.py`, or migrations; `src/rag/ingestion.py` is the only changed `src/rag/` file.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Canonical evidence contracts and golden bytes are ready for the KnowledgeService facade and legacy RAG adapter in 08-02.
- No blockers identified.

## Self-Check: PASSED

- All created files exist.
- All four task commits exist.
- Targeted tests, lint, and changed-file boundary checks pass.

---
*Phase: 08-knowledge-facade*
*Completed: 2026-06-07*
