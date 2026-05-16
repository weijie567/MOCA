---
phase: 04-approval-workflow-audit
plan: 03
subsystem: agent-approval-workflow
tags: [langgraph, approval, interrupt, write-tools, routing, audit]

requires:
  - phase: 04-approval-workflow-audit
    provides: approval tables, action draft repository, approval state fields, latency trace fields
provides:
  - LangGraph approval_gate node using interrupt/resume payloads
  - execute_action node with approval safety gate and idempotent action draft creation
  - create_coupon_grant_draft write tool backed by ActionDraftRepository
  - Conditional graph routing for approval-required, rejected, direct-action, and no-action paths
  - Final response text for approved, rejected, failed, and directly executed action outcomes
affects: [approval-workflow-audit, agent-graph, write-tools, final-response, tests]

tech-stack:
  added: []
  patterns:
    - LangGraph interrupt payloads carry proposed_action, risk metadata, and expiry; resume payload becomes approval_result
    - RunnableConfig provides AsyncSession to execution nodes via config["configurable"]["session"]
    - Idempotency keys combine run_id, approval_id, action_type, and target_id

key-files:
  created:
    - src/agent/nodes/approval_gate.py
    - src/agent/nodes/execute_action.py
    - src/agent/tools/create_coupon_grant_draft.py
    - tests/test_approval_gate.py
    - tests/test_execute_action.py
    - tests/test_graph_routing.py
  modified:
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/final_response.py
    - src/agent/graph.py
    - tests/agent/test_nodes/test_final_response.py

key-decisions:
  - "High-risk routing is enforced immediately after risk assessment: approval_required=True routes only to approval_gate."
  - "Rejected approvals resume the graph and route directly to final_response; execute_action is not called."
  - "The final_response node remains deterministic-template based, so approval outcomes are appended to template output instead of added to LLM messages."

requirements-completed: []
requirements-addressed: [AGNT-02a, SAFE-02, SAFE-04, SAFE-05, TOOL-04, TOOL-05, TOOL-09]

duration: 7min
completed: 2026-05-16
---

# Phase 4 Plan 3: Approval Gate and Execution Graph Summary

**Approval interrupt/resume routing now gates high-risk actions, creates idempotent action drafts after approval, and explains approval outcomes in final responses.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-16T07:49:17Z
- **Completed:** 2026-05-16T07:56:02Z
- **Tasks:** 7
- **Files modified:** 10

## Accomplishments

- Added proposed action derivation to `assess_risk_and_approval`, while keeping `policy_qa` and `insufficient_evidence` as no-action paths.
- Added `approval_gate`, which calls `langgraph.types.interrupt()` with run, tenant, user, proposed action, risk, and expiry metadata, then stores the resume payload as `approval_result`.
- Added `create_coupon_grant_draft` and `execute_action`; execution checks approval state before writing and creates action drafts through the 04-02 repository with deterministic idempotency keys.
- Rewired `src/agent/graph.py` from a linear risk-to-final edge to conditional routing across approval gate, execute action, and final response.
- Updated deterministic final responses to report approved draft creation, rejected approvals, post-approval execution failures, and direct low-risk execution.
- Added 19 focused tests for approval interrupt payloads, execution safety, idempotency/session passing, graph routing, and final response approval outcomes.

## Task Commits

Each task was committed atomically:

1. **Task 03-01: Modify assess_risk_and_approval to output proposed_action** - `55f7303` (feat)
2. **Task 03-02: Create approval_gate node with interrupt()** - `358bd85` (feat)
3. **Task 03-03: Create write tool create_coupon_grant_draft** - `0e58bf2` (feat)
4. **Task 03-04: Create execute_action node using RunnableConfig pattern** - `590fd50` (feat)
5. **Task 03-05: Update final_response to handle approval outcomes** - `41ea377` (feat)
6. **Task 03-06: Rewire graph.py with conditional edges** - `456e7cc` (feat)
7. **Task 03-07: Unit tests for approval workflow nodes and routing** - `c8d51d7` (test)

## Files Created/Modified

- `src/agent/nodes/assess_risk_and_approval.py` - Adds proposed action construction for approval-required and actionable recommendations.
- `src/agent/nodes/approval_gate.py` - Adds interrupt/resume approval node with a 24-hour expiry payload.
- `src/agent/tools/create_coupon_grant_draft.py` - Adds idempotent write tool for action draft creation.
- `src/agent/nodes/execute_action.py` - Adds approval-guarded execution node using `RunnableConfig`.
- `src/agent/nodes/final_response.py` - Adds deterministic approval/action outcome text.
- `src/agent/graph.py` - Adds approval and execution nodes plus conditional routing.
- `tests/test_approval_gate.py`, `tests/test_execute_action.py`, `tests/test_graph_routing.py` - Add focused approval workflow tests.
- `tests/agent/test_nodes/test_final_response.py` - Adds approval outcome response coverage.

## Decisions Made

- `approval_gate` does not write approval records; the API layer will create `approval_request` records when it detects the interrupt.
- `execute_action` treats any approval-required state whose resume decision is not `approve` as `NOT_APPROVED`, even if the graph routing is misused.
- Low-risk proposed actions can execute without approval and use `no_approval` in the idempotency key.
- Final-response approval handling follows the repository's deterministic template style instead of adding a new LLM call.

## Deviations from Plan

### Plan Adaptations

**1. Final response approval context implemented in deterministic templates**
- **Found during:** Task 03-05
- **Issue:** The plan sketch described appending approval context to LLM messages, but `final_response` is currently deterministic-template based.
- **Adjustment:** Added `_approval_outcome_text()` and appended its result to the deterministic response while preserving Phase 3 behavior when approval/action state is absent.
- **Files modified:** `src/agent/nodes/final_response.py`, `tests/agent/test_nodes/test_final_response.py`
- **Commit:** `41ea377`, `c8d51d7`

No Rule 1-3 auto-fixes were required.

## Issues Encountered

- The system `python` binary is broken on this machine. Graph compile verification used `UV_CACHE_DIR=/tmp/uv-cache uv run python`, matching the project workaround used in prior summaries.

## Verification

- `uv run pytest tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py -q` - 14 passed, 1 warning
- `uv run ruff check src/agent/nodes/ src/agent/graph.py src/agent/tools/` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY' ... build_graph(MemorySaver()) ... PY` - graph compiled
- `uv run pytest tests/agent -q` - 43 passed, 1 warning

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-04 can now connect API approval request creation and resume endpoints to the graph interrupt/resume path. The graph already handles both approved and rejected resume payloads.

## Self-Check: PASSED

- Verified summary and created approval workflow files exist.
- Verified task commits are reachable: `55f7303`, `358bd85`, `0e58bf2`, `590fd50`, `41ea377`, `456e7cc`, `c8d51d7`.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
