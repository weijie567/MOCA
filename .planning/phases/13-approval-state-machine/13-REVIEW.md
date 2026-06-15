---
phase: 13-approval-state-machine
reviewed: 2026-06-15T11:58:50Z
depth: deep
files_reviewed: 46
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
  warning: 5
  info: 0
  total: 5
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-15T11:58:50Z
**Depth:** deep
**Files Reviewed:** 46
**Status:** issues_found

## Summary

Deep review covered the Phase 13 approval state machine, graph/API resume paths, snapshot/hash binding, migrations, and approval tests. The core hash and service-transition contracts are well covered, but I found five warning-level issues around graph edge coverage, fail-closed user messaging, API decision exposure, SLA child-state consistency, and trace-event parity for needs-info supersedes.

## Warnings

### WR-01: Edit Resume Route Has No Compiled Graph Edge

**File:** `src/agent/graph.py:164`
**Issue:** `route_after_approval()` can return `"assess_risk_and_approval"` for trusted edit/supersede results, and `ApprovalService._edit()` builds such a resume payload. The compiled conditional edge map for `approval_gate` only includes `approval_gate`, `execute_action`, and `final_response`, so an edit resume routed through the graph can fail instead of re-assessing the edited action. Tests cover the route function but not the compiled edge map.
**Fix:**
```python
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "approval_gate": "approval_gate",
            "assess_risk_and_approval": "assess_risk_and_approval",
            "execute_action": "execute_action",
            "final_response": "final_response",
        },
    )
```

### WR-02: Snapshot Failure Response Is Overwritten

**File:** `src/agent/nodes/final_response.py:202`
**Issue:** `assess_risk_and_approval` returns a fail-closed `final_response` when action safety snapshot persistence or verification fails, but `final_response()` ignores existing `state["final_response"]` except for clarification flows. The user can receive a normal recommendation instead of the intended "manual review/no executable draft" message.
**Fix:**
```python
    blocked_response = state.get("final_response")
    if blocked_response and state.get("safety_snapshot_verified") is False:
        return {
            "final_response": blocked_response,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": {
                    "response_text": blocked_response,
                    "evidence_citations": [],
                    "final_status": "error",
                    "mode": "deterministic-template",
                    "approval_context": None,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
```

### WR-03: Wait Payload Hides Supported Edit/Respond Decisions

**File:** `src/api/routers/agent_runs.py:47`
**Issue:** `DecideRequest` and `ApprovalService` support `edit` and `respond`, and tests cover both, but the wait payload and `approval_gate` interrupt payload advertise only `accept`, `approve`, `reject`, and `ignore`. Clients following `allowed_decision_types` cannot discover Phase 13 edit/respond workflows even though the API accepts them.
**Fix:**
```python
APPROVAL_ALLOWED_DECISION_TYPES = ["accept", "approve", "edit", "respond", "reject", "ignore"]
```
Share this constant with `approval_gate` or deliberately remove `edit`/`respond` from the public request schema until they are meant to be client-visible.

### WR-04: Enabled SLA Expiry Leaves Level And Assignment Pending

**File:** `src/approvals/service.py:288`
**Issue:** `expire_due_request()` marks only the `ApprovalRequest` as `expired`. The current `ApprovalLevel` and `ApprovalAssignment` remain `pending`, which leaves the state machine internally inconsistent when `APPROVAL_SLA_SCANNER_ENABLED=true` and can pollute pending assignment views/history.
**Fix:**
```python
            if assignment is not None:
                await self.repository.increment_assignment_version(assignment, status="expired")
            if level is not None:
                await self.repository.increment_level_version(level, status="expired")
            await self.repository.increment_request_version(request, status="expired")
```
Add an enabled-scanner test that asserts request, level, and assignment all move to `expired`.

### WR-05: Needs-Info Supersede Creates An Unlinked New Approval Event

**File:** `src/approvals/service.py:653`
**Issue:** `_supersede_from_info()` creates a replacement approval request through `create_request_with_single_level()`, which inserts an `approval_requested` row, but unlike `_edit()` it never calls `emit_approval_requested(existing_event=_event)`. The new active approval therefore has an `ApprovalEvent` with no `replay_event_id` and no minimal `approval_requested` trace event, breaking trace/replay parity for changed-material `attach_info` paths.
**Fix:**
```python
        new_request, new_level, new_assignment, _event = await self.repository.create_request_with_single_level(...)
        await emit_approval_requested(
            self.session,
            request=new_request,
            level=new_level,
            assignment=new_assignment,
            actor_id=request.requested_by,
            existing_event=_event,
            metadata={"superseded_from_request_id": str(request.id)},
        )
```
Add a needs-info supersede test that reloads the replacement `approval_requested` event and asserts `replay_event_id` points to an `AgentTraceEvent`.

---

_Reviewed: 2026-06-15T11:58:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
