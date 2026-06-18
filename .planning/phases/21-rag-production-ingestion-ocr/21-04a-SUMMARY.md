---
phase: 21-rag-production-ingestion-ocr
plan: "04a"
subsystem: rag
tags: [rag, provenance, boundary-tests, replay, tool-system, pytest, ruff]

requires:
  - phase: 21-rag-production-ingestion-ocr
    provides: "21-04 verified provenance lookup and safe parser/OCR trace reporting"
provides:
  - "Boundary regression tests for API evidence serialization, prompts, memory, action snapshots, replay payloads, and Tool System ownership"
  - "Replay redacted payload guard against Phase 21 source-block/parser/OCR metadata keys"
  - "Phase 20 hybrid retrieval regression confirmation"
affects: [phase-21, rag-ingestion, policy-evidence, replay, context-assembler, tool-system]

tech-stack:
  added: []
  patterns:
    - "Internal provenance metadata is blocked at public/authority contract boundaries"
    - "Boundary tests assert allowed v1.3 query rewrite/rerank compatibility while guarding later RAG surfaces"

key-files:
  created:
    - .planning/phases/21-rag-production-ingestion-ocr/21-04a-SUMMARY.md
  modified:
    - src/replay/validators.py
    - tests/rag/phase21_xfail_inventory.py
    - tests/knowledge/test_phase21_boundaries.py
    - tests/agent/context/test_assembler.py
    - tests/agent/test_policy_retrieval_ownership.py

key-decisions:
  - "Parser/OCR/source-block metadata is explicitly forbidden in ReplayEventV3 redacted payload keys, including source_block_id, parser_metadata_json, ocr_metadata_json, raw_parser_payload, parser_dump, and hidden_text."
  - "21-04a removed only the completed boundary xfail owner entry; the reusable xfail helper remains for later Phase 21 cleanup/final acceptance work."
  - "No production retrieval or public search schema changes were needed; Phase 20 hybrid ranking and EvidenceRefV1 score semantics remain unchanged."

patterns-established:
  - "Boundary fixtures inject Phase 21 internal metadata into untrusted/raw fields and assert public/authority projections drop it."
  - "BusinessFactRefV1 remains non-assignable to EvidenceRefV1 and business tool outputs keep policy_evidence_refs empty."

requirements-completed: [PROV-04, SAFE-02, SAFE-03, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]

duration: 6m
completed: 2026-06-18T23:39:57Z
---

# Phase 21 Plan 04a: Boundary Regression Summary

**Parser/OCR/source-block provenance boundary tests across evidence, API, prompt, memory, action, replay, Tool System, and hybrid retrieval surfaces**

## Performance

- **Duration:** 6m
- **Started:** 2026-06-18T23:34:16Z
- **Completed:** 2026-06-18T23:39:57Z
- **Tasks:** 1
- **Files created/modified:** 6

## Accomplishments

- Expanded Phase 21 boundary tests for public `EvidenceRefV1`, API `EvidenceItem` serialization, approval/action snapshot projections, prompt assembly, replay redacted payloads, and Tool System ownership.
- Preserved Phase 20 hybrid retrieval behavior: filters still apply before channel contribution, RRF controls ordering, and normalized confidence remains the evidence score.
- Confirmed business facts and reviewed case-memory/tool outputs do not become policy chunks or `EvidenceRefV1`.
- Removed the completed 21-04a Wave 0 xfail owner entry from `PHASE21_XFAIL_OWNERS`.

## Task Commits

1. **Task 21-04a-01: Enforce evidence, prompt, memory, action, replay, business, and retrieval boundaries** - `b385068` (fix)

## Files Created/Modified

- `src/replay/validators.py` - Adds explicit replay redacted-payload forbidden keys for Phase 21 provenance/parser/OCR metadata.
- `tests/rag/phase21_xfail_inventory.py` - Clears the completed 21-04a xfail owner entry.
- `tests/knowledge/test_phase21_boundaries.py` - Adds API evidence serialization, action snapshot, replay payload, and compatibility guard coverage.
- `tests/agent/context/test_assembler.py` - Adds prompt assembly boundary coverage for source-block/parser/OCR metadata and hidden prompt-injection fixture text.
- `tests/agent/test_policy_retrieval_ownership.py` - Adds business-fact-vs-policy-evidence ownership assertions.
- `.planning/phases/21-rag-production-ingestion-ocr/21-04a-SUMMARY.md` - Records execution results.

## Verification

- `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_hybrid_retrieval.py tests/agent/test_memory_evidence_boundary.py tests/agent/context/test_assembler.py tests/agent/test_policy_retrieval_ownership.py -q` -> 56 passed, 1 warning
- `uv run pytest tests/rag/test_ingestion_safety.py tests/agent/test_events.py -q` -> 25 passed, 1 warning
- `uv run ruff check src/replay/validators.py tests/rag/phase21_xfail_inventory.py tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_hybrid_retrieval.py tests/agent/test_memory_evidence_boundary.py tests/agent/context/test_assembler.py tests/agent/test_policy_retrieval_ownership.py` -> passed
- `rg -n "target code absent|owner_task=21-|xfail|21-04a-01/prompt-api-memory-boundary" tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_production_migration.py` -> only the reusable helper remains; no 21-04a owner entry remains

## Decisions Made

- Replay redacted payload validation should explicitly reject Phase 21 provenance/parser/OCR metadata keys because replay payloads are authority-adjacent, not maintainer/debug provenance views.
- Public API/search schema tests should assert both field shape and serialized output so internal trace fields cannot become public evidence by accident.
- The Phase 20 hybrid retrieval tests were left behaviorally unchanged; 21-04a adds boundary coverage around them rather than altering ranking code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Blocked Phase 21 provenance metadata in replay redacted payloads**
- **Found during:** Task 21-04a-01 (boundary replay payload test)
- **Issue:** The existing replay redacted-payload guard rejected generic raw payload keys but did not explicitly reject direct Phase 21 provenance/parser/OCR keys such as `raw_parser_payload`, `source_block_id`, `parser_metadata_json`, and `ocr_metadata_json`.
- **Fix:** Added those keys to `FORBIDDEN_REDACTED_PAYLOAD_KEYS` and covered them in `tests/knowledge/test_phase21_boundaries.py`.
- **Files modified:** `src/replay/validators.py`, `tests/knowledge/test_phase21_boundaries.py`
- **Verification:** Required Phase 21 suite plus `tests/agent/test_events.py` passed.
- **Committed in:** `b385068`

**Total deviations:** 1 auto-fixed (Rule 2 missing critical boundary guard)
**Impact on plan:** Correctness/security-only replay boundary hardening. No retrieval ranking, public API schema, EvidenceRefV1, business, or prompt contract expansion.

## Issues Encountered

- The first local verification run found the replay guard gap above and a test helper timestamp issue; both were corrected before commit.

## Known Stubs

None. Stub scan found only normal Python list initializations and empty-list assertions in tests.

## Threat Flags

None. The only production change narrows an existing replay trust-boundary validator; it adds no endpoint, auth path, file access pattern, schema, or network surface.

## Authentication Gates

None.

## Next Phase Readiness

Plan 21-05 can proceed with cleanup/final acceptance. The completed 21-04a xfail owner entry is gone, while 21-05/21-05a final cleanup scope remains intact.

## Self-Check: PASSED

- Created files verified: `.planning/phases/21-rag-production-ingestion-ocr/21-04a-SUMMARY.md`
- Task commit verified in git log: `b385068`
- No accidental deletions found in the task commit.

---
*Phase: 21-rag-production-ingestion-ocr*
*Completed: 2026-06-18T23:39:57Z*
