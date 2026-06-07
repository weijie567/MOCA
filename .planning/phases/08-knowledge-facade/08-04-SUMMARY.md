---
phase: 08-knowledge-facade
plan: 08-04
subsystem: agent-runtime
tags: [knowledge-facade, evidence-ref, citation-membership, safety-routing]

# Dependency graph
requires:
  - phase: 08-knowledge-facade
    provides: PolicyKnowledgeService facade, EvidenceRefV1 contracts, and evidence_id membership validator from 08-01..03
provides:
  - Agent runtime policy retrieval through PolicyKnowledgeService
  - Canonical EvidenceRefV1 state projection and evidence_id merge semantics
  - Deterministic recommendation claim membership validation
  - No-action suppression for insufficient, invalid-citation, and retrieval-error drafts
affects: [08-05, 08-06, 10-state-lifecycle-routing, 13-approval-state-machine, 15-replay-event-contract]

# Tech tracking
tech-stack:
  added: []
  patterns: [run-start effective-time propagation, evidence_id state identity, no-action recommendation guard]

key-files:
  created: []
  modified:
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/retrieve_policy_evidence.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/final_response.py
    - tests/agent/test_graph.py
    - tests/agent/test_nodes/test_retrieve_policy_evidence.py
    - tests/agent/test_nodes/test_generate_recommendation.py
    - tests/agent/test_nodes/test_assess_risk_and_approval.py
    - tests/conftest.py

key-decisions:
  - "Use persisted run_started_at as the retrieval effective_at boundary, with node-entry time only as a compatibility fallback."
  - "Keep RecommendationDraft public schema stable and deterministically project its doc/chunk citations into one material claim for evidence_id membership."
  - "Treat insufficient_evidence, citation_invalid, and retrieval_error as a single no-action recommendation set at the risk boundary."

patterns-established:
  - "Runtime evidence state stores full EvidenceRefV1 dictionaries and merges only by evidence_id."
  - "No-action drafts short-circuit before risk LLM calls and are rechecked at every proposed-action builder."

requirements-completed: [KNOW-01, KNOW-02, KNOW-03]

# Metrics
duration: 2h 13m
completed: 2026-06-07
---

# Phase 8 Plan 4: State + Node + Consumer Migration Summary

**Agent runtime retrieval now uses PolicyKnowledgeService with run-start effective time, canonical EvidenceRefV1 state, evidence_id citation membership, and complete no-action safety suppression**

## Performance

- **Duration:** 2h 13m
- **Started:** 2026-06-07T02:30:08Z
- **Completed:** 2026-06-07T04:43:00Z
- **Tasks:** 6
- **Files modified:** 11

## Accomplishments

- Cut the active policy retrieval node over from direct `search_policy` calls to the knowledge facade while retaining the legacy path unchanged for rollback.
- Migrated persistent evidence state and recommendation validation to full canonical `evidence_id` identity with deterministic run-start effective time.
- Closed the B2 safety gap so insufficient evidence, invalid citations, and retrieval errors cannot produce proposed actions.
- Kept final-response citation rendering compatible with EvidenceRefV1 values that omit legacy title/section fields.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate AgentState EvidenceRef to EvidenceRefV1 fields** - `47c3773` (feat)
2. **Task 2: Switch retrieve_policy_evidence to the facade; merge by evidence_id** - `8f06b62` (feat)
3. **Task 3: generate_recommendation structured claims + evidence_id membership** - `c599859` (feat)
4. **Task 4: Suppress proposed actions for citation_invalid / retrieval_error** - `4fa8d52` (fix)
5. **Task 5: Keep final_response citation rendering compatible** - `d7cae13` (fix)
6. **Task 6: Update node tests for facade path + safety suppression** - `fe7ba9e` (test)

Additional migration-caused regression repairs:

- `ed5c31d` - migrate graph harness to the facade contract
- `8286f62` - migrate shared approval-integration graph fixture to the facade contract

## Files Created/Modified

- `src/agent/state.py` - Projects canonical EvidenceRefV1 fields and persists `run_started_at`.
- `src/agent/nodes/receive_request.py` - Captures the turn's run-start timestamp.
- `src/agent/nodes/retrieve_policy_evidence.py` - Builds trusted knowledge context/request, calls the facade, and merges by `evidence_id`.
- `src/agent/nodes/generate_recommendation.py` - Derives material claims and validates full evidence membership.
- `src/agent/nodes/assess_risk_and_approval.py` - Suppresses actions for every no-action draft state.
- `src/agent/nodes/final_response.py` - Renders canonical citations without requiring legacy display fields.
- `tests/agent/test_nodes/` - Covers facade statuses, version-distinct merge identity, membership, and action suppression.
- `tests/agent/test_graph.py`, `tests/conftest.py` - Update graph mocks to the facade result contract.

## Decisions Made

- Used the persisted `run_started_at` value for both context and request effective time; dedicated trace/merchant-scope convergence remains owned by Phase 10.
- Preserved `RecommendationDraft` and derived a deterministic single claim in node post-processing rather than adding a new required LLM field.
- Kept the 08-06 observability-consumer failure visible instead of changing `trace.py` outside this plan's ownership.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migrated graph test harness from removed active search_policy dependency**
- **Found during:** Plan-level full-suite verification
- **Issue:** `tests/agent/test_graph.py` still patched the node-local `search_policy` symbol removed by the facade cutover.
- **Fix:** Mocked `PolicyKnowledgeService.search` with canonical results and updated v2 payload/tool assertions.
- **Files modified:** `tests/agent/test_graph.py`
- **Verification:** 9/10 graph tests pass; the remaining assertion is the explicitly deferred 08-06 observability consumer.
- **Committed in:** `ed5c31d`

**2. [Rule 1 - Bug] Migrated shared approval integration graph fixture**
- **Found during:** Full-suite verification
- **Issue:** `tests/conftest.py` still patched `search_policy`, blocking five approval integration tests.
- **Fix:** Replaced the fixture with a correctly bound facade mock returning trusted-context-derived EvidenceRefV1 values.
- **Files modified:** `tests/conftest.py`
- **Verification:** `tests/test_approval_integration.py` passes 5/5.
- **Committed in:** `8286f62`

---

**Total deviations:** 2 auto-fixed bugs.
**Impact on plan:** Both repairs were required to keep existing graph and approval integration coverage valid after the planned runtime cutover. No production scope was added.

## Issues Encountered

- Running two PostgreSQL-backed verification suites concurrently caused test-database DDL deadlocks. Rerunning the full suite alone eliminated those infrastructure-only errors.
- Isolated full suite result: `259 passed, 1 failed`. The sole failure is `tests/agent/test_graph.py::test_trace_summary_shape`, because `src/agent/trace.py` still counts evidence from the legacy retrieval payload. This consumer migration is explicitly owned by 08-06.
- An untracked root `CLAUDE.md` appeared before Task 2. Its creator/origin is unknown from git state; it was read for project instructions, left untouched, and excluded from every commit.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q` - 16 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge tests/agent/test_nodes -q` - 53 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_integration.py -q` - 5 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q` - 259 passed, 1 expected deferred 08-06 failure.
- Ruff passed on every modified source and test file.
- `src/rag/*` and `src/agent/tools/search_policy.py` have no plan diff.

## Known Stubs

None.

## Threat Flags

None - the runtime facade cutover, trusted context, evidence identity, and no-action surfaces are covered by the plan threat model and tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Runtime knowledge facade migration is ready for 08-05 evaluation and documentation work.
- 08-06 must migrate `trace.py`/agent-run observability consumers to the v2 retrieved-evidence shape; the preserved failing graph assertion is its acceptance signal.

## Self-Check: PASSED

- All modified implementation and test files exist.
- All eight implementation/test commits exist.
- Focused suites pass, full-suite residual failure is explicitly owned by 08-06, and forbidden legacy files remain unchanged.
- Untracked `CLAUDE.md` remains untouched and uncommitted.

---
*Phase: 08-knowledge-facade*
*Completed: 2026-06-07*
