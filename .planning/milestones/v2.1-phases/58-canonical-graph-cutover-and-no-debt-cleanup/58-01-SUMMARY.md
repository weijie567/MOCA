---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 01
subsystem: agent-graph-runtime
tags: [canonical-agent-graph, graph-vocabulary, routing, static-classifier, langgraph]

requires:
  - phase: 50-canonical-agent-graph-migration-spec-and-guardrails
    provides: Phase 50 canonical 15-node graph contract and CAGM-09 requirement
  - phase: 57-risk-gate-and-approval-gate-canonicalization
    provides: risk_gate and approval_gate canonical runtime cutover
provides:
  - Canonical-only current runtime graph vocabulary
  - Public routing surface without legacy route delegates
  - Phase 58 strict legacy-hit classifier foundation
affects: [phase-58-closeout, trace-projection, api-trace-readability, canonical-graph-validation]

tech-stack:
  added: []
  patterns:
    - Current runtime vocabulary is separated from historical stored-row projection.
    - Static no-debt scans fail active runtime/current authority/unclassified rows but allow classified historical references.

key-files:
  created:
    - scripts/classify_phase58_legacy_hits.py
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-01-SUMMARY.md
  modified:
    - src/agent/graph_vocabulary.py
    - src/agent/routing.py
    - tests/architecture/test_canonical_graph_baseline.py
    - tests/agent/test_graph_vocabulary.py
    - tests/architecture/test_phase32_static_contract.py
    - tests/architecture/test_memory_contract_delta.py
    - tests/architecture/test_phase34_approval_action_boundaries.py
    - tests/memory/test_phase48_1_memory_compat_alignment.py
    - tests/test_graph_routing.py
    - tests/agent/test_intent_routing.py
    - tests/agent/test_intent_golden_contract.py
    - tests/agent/test_required_slots.py
    - tests/agent/test_session_memory_integration.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "graph_vocabulary_entry() and target_graph_name() now describe current runtime vocabulary only."
  - "project_trace_step_for_contract() owns historical stored-row projection and preserves raw implementation_node."
  - "memory_write remains outside the current main-chain graph vocabulary for Phase 50 final-node assertions."
  - "Phase 58 strict classifier fails active runtime, current docs authority, and unclassified legacy rows, but does not require total_hits == 0."

patterns-established:
  - "Canonical-only runtime helpers: current graph/router names resolve as identity; old stored names do not become active vocabulary."
  - "Historical projection map: stored legacy trace names are mapped only through an explicitly named data-read projection path."
  - "Classifier categories: every allowed legacy-name hit must explain why it is historical, test-only, generated metadata, or classifier implementation."

requirements-completed: [CAGM-09]

duration: 22min
completed: 2026-07-08
---

# Phase 58 Plan 01: Canonical Graph Cutover Foundation Summary

**Canonical-only graph vocabulary, removed public legacy route delegates, and strict Phase 58 legacy-hit classifier**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-08T00:52:39Z
- **Completed:** 2026-07-08T01:14:06Z
- **Tasks:** 3
- **Files created/modified:** 16

## Accomplishments

- Converted the final graph no-debt gate into live assertions against the Phase 50 canonical 15-node set.
- Removed active runtime compatibility aliases from `src/agent/graph_vocabulary.py` while keeping historical stored-row projection explicit.
- Removed public `route_after_intent` and `route_after_slots` delegates from `src/agent/routing.py`; route tests now use canonical helpers.
- Added `scripts/classify_phase58_legacy_hits.py` with strict JSON output for active runtime, current-doc authority, and unclassified legacy-name rows.

## Task Commits

1. **Task 1 RED:** `62a131a` test(58-01): add failing graph vocabulary no-debt tests
2. **Task 1 GREEN:** `f7a4139` feat(58-01): activate canonical graph vocabulary
3. **Task 2 RED:** `5991ab2` test(58-01): add failing canonical route delegate tests
4. **Task 2 GREEN:** `be24838` feat(58-01): remove public legacy route delegates
5. **Task 3 RED:** `d5ef17f` test(58-01): add failing phase58 classifier contract tests
6. **Task 3 GREEN:** `019e84c` feat(58-01): add phase58 legacy-hit classifier

**Plan metadata:** committed separately after this summary was written.

## Files Created/Modified

- `scripts/classify_phase58_legacy_hits.py` - strict Phase 58 legacy-hit classifier with JSON report fields and category counters.
- `src/agent/graph_vocabulary.py` - canonical current runtime entries only; historical projection moved to a private stored-name map.
- `src/agent/routing.py` - removed old public route delegate functions while preserving private shared routing logic.
- `tests/architecture/test_canonical_graph_baseline.py` - live final graph/vocabulary/routing gates plus classifier contract tests.
- `tests/agent/test_graph_vocabulary.py` - canonical identity assertions for current nodes and routers.
- `tests/architecture/test_phase32_static_contract.py` - static expectations updated away from active compatibility aliases.
- `tests/architecture/test_memory_contract_delta.py` - memory compatibility assertions aligned to historical projection semantics.
- `tests/architecture/test_phase34_approval_action_boundaries.py` - approval/risk graph-name expectations aligned to canonical current runtime.
- `tests/memory/test_phase48_1_memory_compat_alignment.py` - memory trace projection checks retargeted to the explicit historical helper.
- `tests/test_graph_routing.py` - canonical route helper imports and negative public-delegate assertions.
- `tests/agent/test_intent_routing.py` - canonical contextual intent route helper coverage.
- `tests/agent/test_intent_golden_contract.py` - canonical route helper expectations.
- `tests/agent/test_required_slots.py` - slot-resolution route helper imports and assertions.
- `tests/agent/test_session_memory_integration.py` - integration expectation updated to historical projection helper where stored legacy rows are read.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - recorded the Task 3 classifier false-positive validation incident in Chinese.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase34_approval_action_boundaries.py tests/memory/test_phase48_1_memory_compat_alignment.py -q --tb=short`
  - Result: 88 passed, 1 skipped, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py -q --tb=short`
  - Result: 1304 passed, 8 warnings.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict`
  - Result: passed; `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/agent/routing.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase34_approval_action_boundaries.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py scripts/classify_phase58_legacy_hits.py`
  - Result: All checks passed.

Acceptance greps were also clean for public legacy route delegates, `DELETE_BY_PHASE_58`, active `compatibility_alias` rows, and `pytest.skip` in the final gate.

## Decisions Made

- Kept `graph_vocabulary_entry()` and `target_graph_name()` as strict current-runtime helpers rather than dual-use compatibility helpers.
- Kept historical trace readability by using `project_trace_step_for_contract()` as the named data-read projection boundary.
- Treated `memory_write` as outside the current main-chain graph vocabulary, matching the Phase 50 final graph contract.
- Made classifier strict mode counter-based instead of total-hit-based, because Phase 58 intentionally permits classified historical/test/documentation references during cleanup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened classifier categories after strict false positives**
- **Found during:** Task 3 GREEN verification.
- **Issue:** The first classifier pass scanned `frontend/dist`, treated target-architecture migration prose as current-doc authority, and left RAG claim legacy-source projection unclassified.
- **Fix:** Skipped generated `dist`, classified `src/agent/rag_context/claims.py` as historical data-read projection, and refined current-doc authority markers for migration/anti-pattern prose.
- **Files modified:** `scripts/classify_phase58_legacy_hits.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** strict classifier and architecture classifier tests passed.
- **Committed in:** `019e84c` for code; summary metadata commit for validation issue log.

---

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** No scope expansion; the fix made the planned strict classifier reliable against generated artifacts and classified historical references.

## Issues Encountered

- Task 3 strict verification initially failed due classifier false positives. Details were recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` per project rule.
- Expected TDD RED failures occurred before each GREEN implementation and are represented by the RED commits.

## Known Stubs

None. Stub-pattern scan found only intentional empty test/runtime fixtures such as empty lists and dicts.

## TDD Gate Compliance

- RED commits exist for all three TDD tasks: `62a131a`, `5991ab2`, `d5ef17f`.
- GREEN commits follow each RED gate: `f7a4139`, `be24838`, `019e84c`.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 58-01 is ready for downstream Phase 58 plans. Current graph/vocabulary/routing surfaces are canonical-only, and later closeout work can use `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` as the reusable static classifier gate.

Per user instruction, this execution did not mutate `.planning/STATE.md`, `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`; shared tracking remains with the orchestrator.

## Self-Check: PASSED

- Found created files: `scripts/classify_phase58_legacy_hits.py`, `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-01-SUMMARY.md`.
- Found task commits in git history: `62a131a`, `f7a4139`, `5991ab2`, `be24838`, `d5ef17f`, `019e84c`.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
