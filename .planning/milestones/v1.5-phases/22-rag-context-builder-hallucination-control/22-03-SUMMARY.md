---
phase: 22-rag-context-builder-hallucination-control
plan: "03"
subsystem: rag-context
tags: [rag-context, evidence-validation, pydantic, pytest]

# Dependency graph
requires:
  - phase: 22-01-wave-0-unit-scaffold
    provides: "RED unit scaffold for ContextBuilder, budgeting, and Phase 22 DTO contracts."
  - phase: 22-02-wave-0-integration-eval-scaffold
    provides: "RED evidence-validation, leakage, and latest/current policy-version tests."
provides:
  - "Strict src.agent.rag_context DTOs and ContextBuilder bundle basics."
  - "Canonical policy evidence detail lookup with current-row latest/current validation."
  - "Prompt-safe citation maps, risk labels, budget traces, and ordinary-surface leakage controls."
affects: [phase-22, context-builder, knowledge-service, policy-chunk-repo]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ContextBuilder consumes canonical details when available and falls back to already verified content lookup for older call sites."
    - "Latest/current policy validity uses current-row comparison: EvidenceRefV1.policy_version == v{PolicyDocument.version}."
    - "Raw provenance/OCR/debug material remains outside ordinary prompt/final/memory/replay/action projections."

key-files:
  created:
    - src/agent/rag_context/__init__.py
    - src/agent/rag_context/schemas.py
    - src/agent/rag_context/builder.py
  modified:
    - src/knowledge/service.py
    - src/repositories/policy_chunk_repo.py
    - tests/knowledge/test_phase22_evidence_validation.py

key-decisions:
  - "Kept EvidenceRefV1 unchanged; Phase 22 citation, trace, and budget metadata live in separate rag_context DTOs."
  - "Implemented the MVP latest/current rule as current PolicyDocument row version comparison."
  - "Allowed provenance/OCR inputs to produce only prompt-safe risk labels on ordinary surfaces."

patterns-established:
  - "Evidence exclusions carry stable reason_code/reason_codes for tenant, scope, duplicate, hash, freshness, and latest-version failures."
  - "Prompt-safe citation IDs map back to canonical EvidenceRefV1 refs without exposing text_hash or raw provenance fields."
  - "Budget traces preserve protected citation metadata while snippets and over-budget items are bounded deterministically."

requirements-completed:
  - CTX-01
  - CTX-02
  - CTX-03
  - CTX-04
  - CTX-05
  - CTX-06
  - VER-01
  - BND-01
  - BND-02
  - BND-05

# Metrics
duration: 10 min
completed: 2026-06-19
---

# Phase 22 Plan 03: Context Builder and Evidence Validation Summary

**Prompt-safe RAG context bundles backed by canonical current-row evidence validation**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-19T09:19:26Z
- **Completed:** 2026-06-19T09:29:26Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `src.agent.rag_context` DTOs and `ContextBuilder` for citation maps, prompt/verifier/debug/final projections, risk labels, dedupe/merge traces, and budget traces.
- Extended `PolicyKnowledgeService` and `PolicyChunkRepository` with tenant-scoped canonical evidence metadata lookup and typed latest/current, hash, freshness, scope, and duplicate exclusions.
- Made CTX/evidence/leakage tests pass without changing `EvidenceRefV1` identity or retrieval ranking behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Define strict RagContext DTOs and package exports** - `29469d5` (feat)
2. **Task 2: Add canonical evidence detail lookup with latest/current validation** - `26722dd` (feat)
3. **Task 3: Implement ContextBuilder bundle construction and safe projections** - `bc9a1e1` (fix)

**Plan metadata:** final docs commit.

## Files Created/Modified

- `src/agent/rag_context/__init__.py` - Public exports for ContextBuilder and strict bundle DTOs.
- `src/agent/rag_context/schemas.py` - Strict Pydantic DTOs for bundle inputs, citations, traces, projections, and budgets.
- `src/agent/rag_context/builder.py` - Evidence validation, dedupe/merge, citation map, budget trace, and safe projection construction.
- `src/knowledge/service.py` - Phase 22 verified evidence detail API with typed inclusion/exclusion results.
- `src/repositories/policy_chunk_repo.py` - Tenant-scoped policy document/chunk metadata join for current-row validation.
- `tests/knowledge/test_phase22_evidence_validation.py` - Direct service coverage for current-row version mismatch.

## Decisions Made

- Kept all Phase 22 fields outside `EvidenceRefV1`; the canonical evidence identity remains exactly the existing model.
- Used current-row `PolicyDocument.version` as the MVP latest/current source of truth.
- Preserved retrieval/ranking behavior by keeping ContextBuilder post-retrieval and avoiding query rewrite, reranking, or backend changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Wired ContextBuilder to canonical detail validation**
- **Found during:** Task 2 (canonical evidence detail lookup)
- **Issue:** The Task 2 plan listed service/repository files, but the CTX evidence-validation tests require ContextBuilder to consume canonical metadata and emit typed exclusions.
- **Fix:** Added builder support for `get_verified_evidence_details` and canonical-row fallback validation.
- **Files modified:** `src/agent/rag_context/builder.py`
- **Verification:** `uv run pytest tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_service.py -q`
- **Committed in:** `26722dd`

**2. [Rule 1 - Bug] Preserved primary evidence when exact duplicate refs share identity**
- **Found during:** Task 3 (safe projection verification)
- **Issue:** Exact duplicate refs share the same `evidence_id`, and duplicate trace bookkeeping initially hid the retained primary during adjacent merge.
- **Fix:** Scoped exclusion skipping to validation exclusions only, so exact duplicates remain trace-only while the retained primary keeps citation identity.
- **Files modified:** `src/agent/rag_context/builder.py`
- **Verification:** `uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_phase22_evidence_validation.py tests/agent/context/test_budget.py -q`
- **Committed in:** `bc9a1e1`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug).
**Impact on plan:** Both fixes were required for planned CTX/evidence correctness. No retrieval, ranking, EvidenceRefV1, or action execution scope was added.

## Issues Encountered

None.

## Verification

- `uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_citation_membership.py tests/agent/context/test_budget.py -q` - passed, 24 tests.
- `uv run pytest tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_service.py -q` - passed, 13 tests during Task 2 verification.
- `uv run pytest tests/knowledge/test_phase21_boundaries.py::test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape -q` - passed.
- `uv run ruff check src/agent/rag_context src/knowledge/service.py src/repositories/policy_chunk_repo.py src/knowledge/provenance.py tests/agent/rag_context tests/knowledge/test_phase22_evidence_validation.py` - passed.

## Known Stubs

None. Stub scan found only optional DTO defaults, fail-closed empty returns, and negative-test fixtures; no UI-flowing placeholder or unwired production stub was introduced.

## Authentication Gates

None.

## Threat Flags

None. The new service/repository trust boundary is explicitly covered by the plan threat model and is tenant-scoped, hash-checked, current-version checked, and fail-closed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 22-04. The bundle and canonical validation layer now provide the active context, citation map, evidence snippets, business refs, and exclusion reason codes that MaterialClaim and verifier work can consume.

## Self-Check: PASSED

- Summary file exists.
- Key created/modified files exist.
- Task commits found: `29469d5`, `26722dd`, `bc9a1e1`.

---
*Phase: 22-rag-context-builder-hallucination-control*
*Completed: 2026-06-19*
