---
phase: 13-approval-state-machine
reviewed: 2026-06-15T14:37:06Z
depth: deep
files_reviewed: 49
files_reviewed_list:
  - .env.example
  - src/agent/events.py
  - src/agent/graph.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/final_response.py
  - src/agent/state.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/schemas/approvals.py
  - src/approvals/__init__.py
  - src/approvals/events.py
  - src/approvals/policy.py
  - src/approvals/repository.py
  - src/approvals/schemas.py
  - src/approvals/service.py
  - src/approvals/sla_scanner.py
  - src/approvals/snapshot_service.py
  - src/approvals/snapshots.py
  - src/common/__init__.py
  - src/common/canonical_hash.py
  - src/config.py
  - src/db/migrations/versions/008_approval_state_machine.py
  - src/db/models.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/approvals/phase13_eval_manifest.json
  - tests/approvals/test_canonical_hash.py
  - tests/approvals/test_events.py
  - tests/approvals/test_hash_binding.py
  - tests/approvals/test_migration_contract.py
  - tests/approvals/test_multi_level_contract.py
  - tests/approvals/test_needs_info_resume.py
  - tests/approvals/test_service_transitions.py
  - tests/approvals/test_single_level_runtime.py
  - tests/approvals/test_sla_scanner.py
  - tests/approvals/test_snapshots.py
  - tests/architecture/test_approval_boundaries.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_approval_integration.py
  - tests/test_approval_models.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-15T14:37:06Z
**Depth:** deep
**Files Reviewed:** 49
**Status:** issues_found

## Summary

Deep re-review covered the full scoped Phase 13 approval state machine after commits `f8680d3` and `f39a07f`, with extra focus on the prior `f67485e` warnings.

The latest fixes resolve three of the four prior warnings:

- WR-02 is resolved: result projection `ValidationError` from `TrustedApprovalResultV1` / `ApprovalInfoResult` now maps to `approval_invalid_result`, while malformed executable material still maps to `approval_not_executable`.
- WR-03 is resolved: reviewer `reason` is persisted on `ApprovalRequest.reason` and round-trips through the API response.
- WR-04 is resolved: SLA scanning filters executable v2 rows, and direct expiry asserts executable request state.

No Critical issues were found. One Warning remains: WR-01 is narrowed but not fully resolved because LangGraph checkpoint advancement is still not recoverable if post-resume DB side effects fail to commit.

Verification run:

- `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` - 215 passed, 1 upstream LangGraph warning.
- `uv run ruff check src/api/routers/approvals.py src/approvals/service.py src/approvals/sla_scanner.py tests/test_approval_api.py tests/approvals/test_service_transitions.py tests/approvals/test_sla_scanner.py` - passed.

## Warnings

### WR-01: Graph resume can still advance checkpoint before action/run side effects commit

**File:** `src/api/routers/approvals.py:75`, `src/api/routers/approvals.py:165`, `src/agent/nodes/execute_action.py:137`

**Issue:** `decide_approval()` now commits the approval decision before `graph.ainvoke(...)`, so the original "checkpoint advanced but approval decision rolled back" case is fixed. However, the resume still uses LangGraph's separate checkpointer while `execute_action()` and `_resume_graph_after_decision()` persist action drafts, run status, and trace steps through the request `session`. Those side effects are only committed by the final `await session.commit()` after `graph.ainvoke(...)`.

If that final commit fails after LangGraph has checkpointed past `approval_gate` / `execute_action`, the approval remains terminal because of the first commit, but the action draft, agent run completion, and appended trace steps can roll back. A second `decide` attempt then returns `approval_conflict`, and the scoped code has no persisted resume attempt marker or retry/reconciliation endpoint to re-run the service-produced resume payload. The action draft path is idempotent once committed, but it does not help if the transaction containing the draft is the one that fails.

**Fix:** Treat graph resume as its own recoverable lifecycle. Persist a resume attempt/completion marker keyed by `approval_id` + `revision` before invoking the graph, commit graph side effects in an idempotent transaction, and expose a retry/reconcile path that can resume a terminal approval when the run/action side effects are missing or marked failed. Add a regression test where the fake graph returns successfully but the final `session.commit()` fails, then assert the system either retries to completion or records a recoverable resume failure instead of leaving a terminal approval with an interrupted run.

---

_Reviewed: 2026-06-15T14:37:06Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
