---
phase: 09-business-tool-facade
plan: 09
subsystem: authorization
tags: [policy-retrieval, permissions, merchant-scope, sse, fail-closed]

requires:
  - phase: 09-06
    provides: Verified JWT scope projection into trusted run config
  - phase: 09-07
    provides: Structured merchant scope projection into KnowledgeContext
provides:
  - Execution-time tool:search_policy authorization gate before PolicyKnowledgeService construction
  - Pre-adapter deny-all enforcement for empty and unauthorized merchant scope
  - Live API/SSE regression for restricted agent:chat-only JWT configuration
affects: [policy-retrieval, agent-run-streaming, phase-10-routing]

tech-stack:
  added: []
  patterns:
    - Fail-closed execution authorization before service construction
    - Typed no_evidence return before policy adapter execution

key-files:
  created:
    - tests/knowledge/test_service.py
  modified:
    - src/agent/nodes/retrieve_policy_evidence.py
    - src/knowledge/service.py
    - src/api/routers/agent_runs.py
    - tests/agent/test_nodes/test_retrieve_policy_evidence.py
    - tests/agent/test_graph.py
    - tests/test_agent_runs_api.py
    - tests/knowledge/test_tenant_scope.py
    - tests/agent/test_policy_retrieval_ownership.py

key-decisions:
  - "Missing, empty, or malformed retrieval permissions deny before session lookup or PolicyKnowledgeService construction."
  - "KnowledgeContext.merchant_scope=[] and unauthorized explicit merchant filters return typed no_evidence without adapter invocation."
  - "KnowledgeContext.merchant_scope=None remains legacy unrestricted compatibility and ['*'] remains explicit tenant-wide scope."

patterns-established:
  - "Denied retrieval traces contain PERMISSION_DENIED and an empty tools_called list."
  - "Merchant-role users without merchant_id receive {'merchant_ids': []}, never the string 'None'."

requirements-completed: [TOOL-01, TOOL-02]

duration: 11m
completed: 2026-06-13
---

# Phase 09 Plan 09: Policy Retrieval Execution-Boundary Gap Closure Summary

**Live policy retrieval now fails closed on denied permissions and empty or unauthorized merchant scope before service or adapter invocation**

## Performance

- **Duration:** 11m
- **Started:** 2026-06-13T01:40:52Z
- **Completed:** 2026-06-13T01:52:09Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added a `tool:search_policy` execution gate before session lookup and `PolicyKnowledgeService` construction, returning a safe typed `PERMISSION_DENIED` error with no evidence.
- Added service-level deny-all handling for empty merchant scope and unauthorized explicit merchant filters before `LegacyRagKnowledgeAdapter.retrieve`.
- Added a live `/api/v1/agent-runs/{run_id}/events` regression proving an `agent:chat`-only JWT reaches the graph with no tool permissions.
- Fixed merchant users with `merchant_id=None` to project `{"merchant_ids": []}`.
- Passed the exact full Phase 9 regression: `132 passed`.

## Task Commits

TDD tasks were committed as RED then GREEN:

1. **Task 1 RED: Policy permission and live SSE regressions** - `5519a35` (test)
2. **Task 1 GREEN: Policy retrieval permission gate** - `8e28247` (feat)
3. **Task 2 RED: Merchant scope and missing identity regressions** - `08a0007` (test)
4. **Task 2 GREEN: Pre-adapter merchant scope denial** - `7bdfdc4` (feat)
5. **Full-regression fixture correction** - `7f826fd` (test)

## Files Created/Modified

- `src/agent/nodes/retrieve_policy_evidence.py` - Enforces `tool:search_policy` before constructing or invoking the policy service.
- `src/knowledge/service.py` - Returns typed `no_evidence` before adapter execution for deny-all or unauthorized merchant scope.
- `src/api/routers/agent_runs.py` - Projects missing merchant identity to explicit deny-all scope.
- `tests/knowledge/test_service.py` - Covers deny-all, unauthorized, wildcard, matching, and legacy merchant scope behavior.
- `tests/test_agent_runs_api.py` - Covers live SSE restricted-token config and missing merchant identity.
- `tests/agent/test_nodes/test_retrieve_policy_evidence.py` - Covers permission denial and service non-invocation.
- `tests/agent/test_graph.py` - Grants explicit retrieval permission on successful graph paths.
- `tests/knowledge/test_tenant_scope.py` - Replaces the obsolete unauthorized-filter widening expectation.
- `tests/agent/test_policy_retrieval_ownership.py` - Grants explicit permission on its successful ownership path.

## Decisions Made

- Permission denial uses the node's existing typed retrieval-error shape with stable `PERMISSION_DENIED`, while the trace accurately records no tool call.
- Unauthorized explicit merchant filters deny rather than being dropped and widened into an unfiltered tenant search.
- Legacy `merchant_scope=None` compatibility remains unchanged outside this gap closure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created the referenced focused service test module**
- **Found during:** Task 2 read-first gate
- **Issue:** The plan referenced `tests/knowledge/test_service.py`, but it did not exist.
- **Fix:** Created the focused module with the required service-boundary regressions.
- **Files modified:** `tests/knowledge/test_service.py`
- **Verification:** Focused Task 2 suite passed, `20 passed`.
- **Committed in:** `08a0007`

**2. [Rule 1 - Bug] Added missing KnowledgeSearchResult import**
- **Found during:** Task 1 GREEN verification
- **Issue:** The new typed permission-denial result initially referenced `KnowledgeSearchResult` without importing it.
- **Fix:** Added the canonical schema import.
- **Files modified:** `src/agent/nodes/retrieve_policy_evidence.py`
- **Verification:** Node and graph suite passed, `34 passed`.
- **Committed in:** `8e28247`

**3. [Rule 3 - Blocking] Updated obsolete unauthorized-filter regression**
- **Found during:** Task 2 GREEN verification
- **Issue:** An existing tenant-scope test expected unauthorized filters to be silently widened and sent to the adapter.
- **Fix:** Changed it to assert typed denial and adapter non-invocation while preserving authorized behavior.
- **Files modified:** `tests/knowledge/test_tenant_scope.py`
- **Verification:** Tenant-scope and focused service tests passed, `7 passed`.
- **Committed in:** `7bdfdc4`

**4. [Rule 3 - Blocking] Authorized the successful policy-ownership fixture**
- **Found during:** Full Phase 9 regression
- **Issue:** The ownership test expected successful live retrieval but omitted the newly required permission.
- **Fix:** Granted `tool:search_policy` only on that successful path.
- **Files modified:** `tests/agent/test_policy_retrieval_ownership.py`
- **Verification:** Ownership suite passed, `18 passed`; full Phase 9 regression passed, `132 passed`.
- **Committed in:** `7f826fd`

---

**Total deviations:** 4 auto-fixed (1 bug, 3 blocking issues).  
**Impact on plan:** All fixes were required to enforce and verify the planned fail-closed behavior; no architectural scope change.

## Issues Encountered

- Database-backed API tests could not open the local PostgreSQL socket inside the filesystem sandbox. They were rerun with approved unrestricted execution and passed.

## Known Stubs

None. Empty permission, evidence, and merchant-scope values are intentional deny-all/test outcomes.

## Verification

- Task 1 focused suite: `48 passed`
- Task 2 focused suite: `20 passed`
- Directly affected tenant-scope suite: `7 passed`
- Policy ownership suite: `18 passed`
- Exact full Phase 9 regression: `132 passed, 11 warnings`
- All task acceptance-criteria grep checks passed.

## Self-Check: PASSED

- Confirmed all nine created/modified implementation and test files exist.
- Confirmed commits `5519a35`, `8e28247`, `08a0007`, `7bdfdc4`, and `7f826fd` exist.
- Confirmed no plan-related generated files remain untracked.
- Confirmed unrelated modified `CLAUDE.md`, deleted `docs/*`, and six untracked planning drafts were not staged or changed.

## Next Phase Readiness

- Phase 9 execution-boundary authorization gaps are closed and regression-tested.
- Independent phase verification and shared phase-status updates remain for the orchestrator.

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-13*
