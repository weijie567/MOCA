---
phase: 16-long-term-case-memory
plan: 08
subsystem: agent-memory
tags: [long-term-memory, case-memory, context-assembler, graph, prompt-safety, tdd]

requires:
  - phase: 16-03-long-term-memory-service
    provides: reviewed LongTermMemoryView retrieval predicates and prompt-safe views
  - phase: 16-06-reviewed-case-memory
    provides: reviewed CaseMemorySearchItem precedent retrieval
  - phase: 16-07-context-assembler-memory
    provides: ContextAssembler profile_memory_snippets and case_memory_snippets parameters
provides:
  - Reviewed memory retrieval node with safe empty/unavailable fallbacks
  - Prompt-safe long-term and case memory state projections
  - Prompt call-site wiring for reviewed memory snippets through ContextAssembler
  - Authority-boundary tests proving reviewed memory stays contextual only
affects: [16-09-legacy-search-eval-closure, long_term_memory_retrieve, ContextAssembler, graph]

tech-stack:
  added: []
  patterns:
    - Service-backed reviewed memory retrieval from graph config dependencies
    - Prompt-safe allowlist projection before graph state exposure
    - Fail-closed unavailable memory fallback with continuity_claimed=false

key-files:
  created: []
  modified:
    - src/agent/nodes/long_term_memory_retrieve.py
    - src/agent/nodes/investigate.py
    - src/memory/long_term.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/extract_slots.py
    - src/agent/nodes/assess_risk_and_approval.py
    - tests/agent/test_graph.py
    - tests/agent/test_memory_evidence_boundary.py

key-decisions:
  - "Reviewed memory retrieval fails closed: unavailable services, missing dependencies, or empty reviewed rows never claim continuity."
  - "Graph state receives only prompt-safe allowlisted memory snippets, not raw ORM rows or authority-bearing payloads."
  - "Prompt nodes pass reviewed memory through ContextAssembler while preserving policy evidence, tool summaries, and business context as separate authority sources."

patterns-established:
  - "Memory retrieval node accepts optional service overrides from graph config and otherwise constructs services from the configured session."
  - "Long-term profile memory and case memory are projected with separate allowlists before entering AgentState."
  - "Retrieved case memory is preserved across investigate instead of being overwritten by the policy/business retrieval node."

requirements-completed:
  - MEMCTX-01
  - MEMCTX-02
  - LONGMEM-02
  - CASEMEM-02
  - MEMEVAL-01

duration: 10 min
completed: 2026-06-18
---

# Phase 16 Plan 08: Reviewed Memory Retrieval Integration Summary

**Reviewed long-term and case memory retrieval now feeds prompt-safe ContextAssembler snippets without becoming evidence or action authority**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-17T17:08:44Z
- **Completed:** 2026-06-17T17:19:05Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Replaced the `empty_adapter` memory seam with reviewed long-term and case memory retrieval through service dependencies resolved from graph config.
- Added safe empty and unavailable fallbacks that return empty memory lists with `continuity_claimed=False`.
- Projected retrieved memory through prompt-safe allowlists before storing it in graph state.
- Passed reviewed profile/case memory snippets into `ContextAssembler` from slot extraction, recommendation generation, and risk assessment nodes.
- Added graph and authority-boundary tests proving reviewed memory cannot create `EvidenceRefV1`, policy evidence, approval evidence, action authorization, current business truth, or replay/debug truth.

## Task Commits

1. **Task 16-08-01: Add reviewed memory retrieval graph tests** - `ae8c7aa` (test)
2. **Task 16-08-02: Replace empty memory adapter with reviewed retrieval** - `e0787cc` (feat)
3. **Task 16-08-03: Pass memory snippets into prompt call sites** - `336054a` (feat)

## Files Created/Modified

- `src/agent/nodes/long_term_memory_retrieve.py` - Loads reviewed long-term/case memory, handles unavailable/no-reviewed-memory fallbacks, and emits prompt-safe state plus trace metadata.
- `src/agent/nodes/investigate.py` - Preserves retrieved `case_memory` instead of resetting it during business/policy investigation.
- `src/memory/long_term.py` - Adds a thin service-level `retrieve_profile_memory(...)` wrapper around the existing repository retrieval method.
- `src/agent/nodes/generate_recommendation.py` - Passes reviewed memory snippets into `ContextAssembler`.
- `src/agent/nodes/extract_slots.py` - Passes reviewed memory snippets into `ContextAssembler`.
- `src/agent/nodes/assess_risk_and_approval.py` - Passes reviewed memory snippets into `ContextAssembler`.
- `tests/agent/test_graph.py` - Covers safe empty retrieval, unavailable fallback, reviewed snippets, continuity semantics, and prompt-safe state projection.
- `tests/agent/test_memory_evidence_boundary.py` - Covers reviewed memory authority boundaries with no policy/action escalation.

## Decisions Made

- Reviewed memory is retrieved from graph config dependencies only: explicit service overrides are honored for tests/injection, otherwise services are constructed from the configured session.
- `continuity_claimed` is true only when at least one prompt-safe reviewed profile or case snippet is returned.
- Memory projection is allowlist-based and separate for profile versus case memory. Extra service fields such as forged evidence, approval/action bodies, raw tool payloads, and replay/debug blobs are dropped before entering state.
- Prompt nodes treat memory as contextual assistance only; policy refs, tool summaries, and business context remain separate arguments to `ContextAssembler`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added service-level long-term retrieval wrapper**
- **Found during:** Task 16-08-02 (Replace empty memory adapter with reviewed retrieval)
- **Issue:** The plan required calling reviewed long-term profile retrieval through services, but `LongTermMemoryService` exposed write/review/delete methods while the reviewed retrieval method lived only on `LongTermMemoryRepository`.
- **Fix:** Added `LongTermMemoryService.retrieve_profile_memory(...)` as a thin wrapper over the existing repository method.
- **Files modified:** `src/memory/long_term.py`
- **Verification:** `uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q`
- **Committed in:** `e0787cc`

**2. [Rule 1 - Bug] Preserved retrieved case memory through investigate**
- **Found during:** Task 16-08-02 (Replace empty memory adapter with reviewed retrieval)
- **Issue:** `investigate` always returned `case_memory=[]`, which would erase case snippets loaded by the upstream `long_term_memory_retrieve` node before prompt generation.
- **Fix:** Changed `investigate` to carry forward `state.get("case_memory") or []`.
- **Files modified:** `src/agent/nodes/investigate.py`
- **Verification:** `uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q`
- **Committed in:** `e0787cc`

---

**Total deviations:** 2 auto-fixed (1 missing critical service seam, 1 state-preservation bug)
**Impact on plan:** Both fixes were required to satisfy the reviewed-memory retrieval contract. No new endpoint, table, auth path, or external infrastructure was introduced.

## Issues Encountered

None. All planned verification commands passed. Pytest emitted only the existing LangGraph serializer deprecation warning.

## Known Stubs

None. Stub scan found only intentional safe empty-list/string values in fallback paths and tests; no behavior-blocking stubs were introduced.

## TDD Gate Compliance

- **RED:** `ae8c7aa` added failing graph and authority-boundary tests. Initial RED run failed 4 tests because the node still returned `empty_adapter` and no reviewed snippets.
- **GREEN:** `e0787cc` implemented reviewed retrieval and made the focused retrieval/boundary suite pass.
- **Refinement:** `336054a` wired memory snippets into prompt call sites while keeping the focused assembler/boundary suite green.

## Verification

- `uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q` — RED failed before implementation, then passed with 26 tests after Task 16-08-02.
- `uv run pytest tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py -q` — passed, 11 tests.
- `uv run pytest tests/agent/context/test_assembler.py tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q` — passed, 32 tests.
- `uv run pytest tests/memory tests/agent/context -q` — passed, 76 tests.
- `uv run ruff check src/agent src/memory tests/agent` — passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-09-legacy-search-eval-closure-PLAN.md`. Reviewed memory now reaches prompt construction only as bounded contextual snippets, and tests guard against memory becoming evidence, approval/action authority, current business truth, or replay/audit truth.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-18*

## Self-Check: PASSED

- Found summary file: `.planning/phases/16-long-term-case-memory/16-08-memory-retrieval-integration-SUMMARY.md`.
- Found key files: `src/agent/nodes/long_term_memory_retrieve.py`, `src/agent/nodes/investigate.py`, `src/memory/long_term.py`, `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/extract_slots.py`, `src/agent/nodes/assess_risk_and_approval.py`, `tests/agent/test_graph.py`, `tests/agent/test_memory_evidence_boundary.py`.
- Found task commits: `ae8c7aa`, `e0787cc`, `336054a`.
