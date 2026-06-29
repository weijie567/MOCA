---
phase: 34-approval-and-actiondraft-boundary-hardening
reviewed: 2026-06-29T08:04:02Z
depth: deep
files_reviewed: 39
files_reviewed_list:
  - src/actions/drafts.py
  - src/actions/schemas.py
  - src/actions/service.py
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/state.py
  - src/agent/working_state.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/schemas/agent_runs.py
  - src/api/schemas/approvals.py
  - src/approvals/policy.py
  - src/approvals/repository.py
  - src/approvals/schemas.py
  - src/approvals/service.py
  - src/db/migrations/versions/018_phase34_approval_action_bindings.py
  - src/db/models.py
  - src/repositories/action_draft_repo.py
  - src/tools/catalog.py
  - src/tools/executors/action.py
  - tests/actions/test_action_draft_v2.py
  - tests/actions/test_phase34_action_draft_bindings.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_working_state.py
  - tests/approvals/test_migration_contract.py
  - tests/approvals/test_phase34_boundary_bindings.py
  - tests/approvals/test_service_transitions.py
  - tests/architecture/test_action_draft_boundaries.py
  - tests/architecture/test_phase34_approval_action_boundaries.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
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

# Phase 34: Code Review Report

**Reviewed:** 2026-06-29T08:04:02Z
**Depth:** deep
**Files Reviewed:** 39
**Status:** issues_found

## Warnings

### WR-04: Failed edit resume cannot be retried after the approval is superseded

**File:** `src/api/routers/approvals.py:443`

**Issue:** The WR-02 fix makes trusted edit decisions resume the graph when `resume_route == "assess_risk_and_approval"` (`src/api/routers/approvals.py:734`), but the recoverable retry gate still only recognizes terminal approved/rejected/cancelled rows and excludes `edit` decisions (`src/api/routers/approvals.py:49`, `src/api/routers/approvals.py:452`, `src/api/routers/approvals.py:454`). If `_run_resume_lifecycle` fails after `ApprovalService._edit` has saved the decision and marked the request `superseded` (`src/approvals/service.py:503`), the API returns `APPROVAL_RESUME_FAILED` and says to retry (`src/api/routers/approvals.py:262-278`), but retry falls through to the normal decision path and conflicts because the row is no longer pending. The retry reconstruction helper also omits edit-specific fields (`edited_action`, `new_action_payload_hash`, `resume_route`) from the rebuilt trusted payload (`src/api/routers/approvals.py:572-589`), so simply admitting `edit` to the set would still not resume.

**Impact:** A transient graph/DB failure during edit rerisk can leave the original approval permanently `superseded` with no rebound approval row. The user receives an instruction to retry, but the retry cannot reconcile the saved edit decision, so the Phase 34 edit-rebind path can dead-end.

**Fix:** Treat `edit`/`superseded` as a recoverable resume state and reconstruct the trusted edit payload from the saved decision plus the `approval_decided` event metadata/resource refs before calling `_run_resume_lifecycle`.

```python
RESUMABLE_DECISIONS = {"accept", "approve", "reject", "ignore", "edit"}
RESUME_RETRY_STATUSES = {"approved", "rejected", "cancelled", "superseded"}

metadata = event.metadata_json or {}
resource_refs = event.resource_refs_json or {}
trusted = TrustedApprovalResultV1(
    ...,
    decision_type=decision.decision_type,
    status=approval.status,
    edited_action=decision.edited_action if decision.decision_type == "edit" else None,
    new_action_payload_hash=resource_refs.get("new_action_payload_hash"),
    resume_route=metadata.get("resume_route"),
).model_dump(mode="json")
```

Add an API regression test mirroring `test_approval_resume_failure_can_retry_without_new_decision`, but with `decision_type="edit"` and a resume graph failure before the rebound interrupt is persisted. The retry should return 200, call the graph again with the same trusted edit payload, and create the bound replacement approval after the interrupt.

## Summary

Deep re-review traced the Phase 34 approval/action flow across risk gating, approval interrupts, edit rerisk resume, rebound approval creation, action draft validation, safe projections, and static no-real-execution boundaries. The prior findings WR-01, WR-02, and WR-03 are resolved in the current code and covered by focused tests.

One new warning remains: the edit resume retry path was not updated with the WR-02/WR-03 behavior, so a failed edit rerisk resume is not recoverable even though the API tells the caller to retry.

## Verification

- WR-01 resolved: `_approval_create_command_from_interrupt` now accepts `claim_verification_ref` or `claim_verification_summary` and preserves a nullable claim ref (`src/api/routers/agent_runs.py:852`, `src/api/routers/agent_runs.py:892`).
- WR-02 resolved: `_should_resume_graph` now resumes trusted edit results with `resume_route="assess_risk_and_approval"` (`src/api/routers/approvals.py:734`), and risk gate validates/re-hashes the trusted edited action (`src/agent/nodes/assess_risk_and_approval.py:336`, `src/agent/nodes/assess_risk_and_approval.py:373`).
- WR-03 resolved: `_edit` and `_supersede_from_info` no longer create unbound replacement approval rows inside `ApprovalService`; edit rebound rows are created through the approval interrupt bridge after rerisk (`src/approvals/service.py:458`, `src/approvals/service.py:618`, `src/api/routers/approvals.py:349`).
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action -q --tb=short` -> `9 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` -> `20 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent_runs.py src/api/routers/approvals.py src/agent/nodes/assess_risk_and_approval.py src/approvals/service.py tests/test_agent_runs_api.py tests/test_approval_gate.py tests/test_approval_api.py tests/test_graph_routing.py tests/approvals/test_service_transitions.py` -> passed.
- Static scans over the 39-file scope found no dangerous function/secret/debug patterns; production source scans found no real execution/outbox/reconciliation/compensation surfaces.

---

_Reviewed: 2026-06-29T08:04:02Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
