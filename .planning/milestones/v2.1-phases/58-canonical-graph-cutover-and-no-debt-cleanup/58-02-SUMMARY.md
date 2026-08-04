---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 02
subsystem: agent-graph-recommendation-risk
tags: [canonical-agent-graph, recommendation_generation, risk_gate, rag, approval-safety]

requires:
  - phase: 58-01
    provides: Canonical-only current graph vocabulary and strict Phase 58 legacy-hit classifier foundation
  - phase: 56-recommendation-generation-and-rag-claim-status-alignment
    provides: recommendation_generation active graph cutover and RAG/claim fail-closed semantics
  - phase: 57-risk-gate-and-approval-gate-canonicalization
    provides: risk_gate active graph cutover and approval/risk boundary semantics
provides:
  - Canonical recommendation implementation ownership in `src/agent/nodes/recommendation_generation.py`
  - Canonical risk implementation ownership in `src/agent/nodes/risk_gate.py`
  - Canonical direct recommendation and risk node test filenames before wrapper deletion
affects: [phase-58-closeout, canonical-agent-graph, rag-recommendation, risk-gate, approval-safety]

tech-stack:
  added: []
  patterns:
    - Legacy graph-node modules remain import wrappers only; canonical modules own implementation and patch seams.
    - Direct node tests patch canonical modules and assert no current-run legacy identity.

key-files:
  created:
    - tests/agent/test_nodes/test_recommendation_generation.py
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-02-SUMMARY.md
  modified:
    - src/agent/nodes/recommendation_generation.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/risk_gate.py
    - src/agent/nodes/assess_risk_and_approval.py
    - tests/agent/test_nodes/test_risk_gate.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md
  deleted:
    - tests/agent/test_nodes/test_generate_recommendation.py
    - tests/agent/test_nodes/test_assess_risk_and_approval.py

key-decisions:
  - "Kept legacy recommendation/risk modules as non-owning import wrappers until dependency-ordered Plan 58-03 deletes wrapper surfaces."
  - "Did not do scattered cross-test import cleanup in this plan; focused direct tests now target canonical modules."
  - "Recorded the implementation ownership move in ARCHITECTURE-DEBT because the plan touches RAG recommendation and risk graph subsystems."

patterns-established:
  - "Canonical implementation ownership: tests patch `src.agent.nodes.recommendation_generation` and `src.agent.nodes.risk_gate` directly."
  - "Legacy wrapper behavior: legacy callable imports remain available but emit canonical current-run identity."

requirements-completed: [CAGM-09]

duration: 12min
completed: 2026-07-08
---

# Phase 58 Plan 02: Recommendation And Risk Ownership Summary

**Recommendation and risk implementation ownership now lives in canonical graph node modules while legacy modules are non-owning wrappers.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-08T01:18:13Z
- **Completed:** 2026-07-08T01:30:01Z
- **Tasks:** 2
- **Files created/modified/deleted:** 11

## Accomplishments

- Moved recommendation implementation, prompt assembly, validation helpers, `_get_llm`, `_trace_step`, and the public callable into `recommendation_generation.py`.
- Moved risk rules, snapshot persistence seam, binding/fail-closed logic, `_get_llm`, `_trace_step`, and the public callable into `risk_gate.py`.
- Renamed the direct recommendation test to `test_recommendation_generation.py` and deleted the legacy direct risk test after migrating its unique assertions into `test_risk_gate.py`.

## Task Commits

1. **Task 1 RED:** `faff3fd` test(58-02): add failing canonical recommendation tests
2. **Task 1 GREEN:** `211e36a` feat(58-02): move recommendation ownership to canonical module
3. **Task 2 RED:** `74045b6` test(58-02): add failing canonical risk gate tests
4. **Task 2 GREEN:** `b90a830` feat(58-02): move risk ownership to canonical module

**Plan metadata:** committed separately after this summary was written.

## Files Created/Modified

- `src/agent/nodes/recommendation_generation.py` - Canonical recommendation implementation host and patch seams.
- `src/agent/nodes/generate_recommendation.py` - Non-owning legacy wrapper delegating to canonical recommendation execution.
- `src/agent/nodes/risk_gate.py` - Canonical risk/action implementation host and patch seams.
- `src/agent/nodes/assess_risk_and_approval.py` - Non-owning legacy wrapper delegating to canonical risk execution.
- `tests/agent/test_nodes/test_recommendation_generation.py` - Renamed canonical recommendation direct tests.
- `tests/agent/test_nodes/test_risk_gate.py` - Canonical risk direct tests with migrated behavior coverage.
- `.planning/ARCHITECTURE-DEBT.md` - Chinese subsystem debt closure entry for Phase 58-02 ownership migration.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local validation note for the expected RED legacy real-LLM initialization path.

Deleted:

- `tests/agent/test_nodes/test_generate_recommendation.py`
- `tests/agent/test_nodes/test_assess_risk_and_approval.py`

## Decisions Made

- Legacy wrapper files remain until Plan 58-03 because this plan explicitly excludes scattered cross-test import cleanup.
- Current execution through legacy callables now emits canonical identity, rather than preserving legacy current-run identity.
- Canonical modules own patch seams so focused node tests no longer need to patch legacy implementation modules.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Tracking] Added required architecture debt ledger entry**
- **Found during:** Plan closeout.
- **Issue:** The plan touched RAG recommendation and risk graph subsystems; MOCA project rules require verified subsystem-level fixes/debt closures to be recorded in `.planning/ARCHITECTURE-DEBT.md`.
- **Fix:** Added a Chinese Phase 58-02 entry with symptoms, impact, status, evidence commits/files, verification, and remaining 58-03 cleanup risk.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Entry cites the actual task commits and focused verification commands.
- **Committed in:** final metadata commit.

**Total deviations:** 1 auto-fixed project-tracking item.
**Impact on plan:** No runtime scope expansion; the added ledger entry satisfies project documentation rules.

## Issues Encountered

- Expected TDD RED failures occurred before both GREEN implementation commits.
- The Task 2 RED run exposed a real-LLM initialization path in the old legacy risk implementation and hit local `socksio` absence. This was logged in `.planning/LOCAL-VALIDATION-ISSUES.md`; after the planned ownership move, the focused risk suite passed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short`
  - Result: `40 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py -q --tb=short`
  - Result: `17 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py -q --tb=short`
  - Result: `57 passed, 1 warning`.
- `test ! -e tests/agent/test_nodes/test_generate_recommendation.py && test ! -e tests/agent/test_nodes/test_assess_risk_and_approval.py`
  - Result: passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/recommendation_generation.py src/agent/nodes/generate_recommendation.py src/agent/nodes/risk_gate.py src/agent/nodes/assess_risk_and_approval.py tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py`
  - Result: All checks passed.

## Known Stubs

None. Stub-pattern scan hits were intentional test fixture values or optional function defaults, not unimplemented runtime stubs.

## Threat Flags

None. The plan changed existing recommendation/risk trust-boundary implementation hosts and tests; it did not add new network endpoints, auth paths, file access patterns, or schemas.

## TDD Gate Compliance

- RED commits exist for both TDD tasks: `faff3fd`, `74045b6`.
- GREEN commits follow each RED gate: `211e36a`, `b90a830`.
- No refactor commit was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 58-03 can now delete or migrate scattered legacy wrapper imports without implementation ownership being stranded in `generate_recommendation.py` or `assess_risk_and_approval.py`. The wrappers still exist intentionally and are documented as 58-03+ cleanup risk.

Per user instruction, this execution did not mutate `.planning/STATE.md`, `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`; shared tracking remains with the orchestrator.

## Self-Check: PASSED

- Found created files: `tests/agent/test_nodes/test_recommendation_generation.py`, `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-02-SUMMARY.md`.
- Confirmed deleted direct legacy tests are absent: `tests/agent/test_nodes/test_generate_recommendation.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`.
- Found task commits in git history: `faff3fd`, `211e36a`, `74045b6`, `b90a830`.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
