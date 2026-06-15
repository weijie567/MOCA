---
phase: 13-approval-state-machine
reviewed: 2026-06-15T13:29:12Z
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
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-15T13:29:12Z
**Depth:** deep
**Files Reviewed:** 46
**Status:** issues_found

## Summary

Deep refresh review covered the approval state machine, graph/API resume paths, migration/model contracts, snapshot/hash binding, event emission, and regression tests. The five prior warnings were verified fixed: edit routing is registered in the compiled graph, snapshot failure messaging is preserved, edit/respond are advertised in wait payloads, enabled SLA expiry updates request/level/assignment together, and needs-info supersede now emits a replay-linked replacement `approval_requested` event.

Verification run: `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` passed with 208 tests and one upstream LangGraph deprecation warning.

## Warnings

### WR-01: Malformed Edit Or Info Payloads Can Escape As 500s

**File:** `src/approvals/service.py:213`
**Issue:** Public `edit` and changed-material `/info` payloads are accepted as generic dictionaries, then `_edit()` and `_supersede_from_info()` pass them into canonical hashing/snapshot persistence at `src/approvals/service.py:448` and `src/approvals/service.py:635`. `decide()` and `attach_info()` only translate `ApprovalRepositoryConflict` and `ApprovalPolicyError`, so `CanonicalHashError`, `ActionSafetySnapshotPersistenceError`, or Pydantic `ValidationError` from malformed edited actions/evidence can bypass `_approval_http_error()` and surface as a server error instead of a controlled conflict/validation response.
**Fix:**
```python
from pydantic import ValidationError
from src.common.canonical_hash import CanonicalHashError

# In decide() and attach_info(), after the existing domain-policy catches:
except (ActionSafetySnapshotPersistenceError, CanonicalHashError, ValidationError) as exc:
    raise ApprovalTransitionError("approval_not_executable", str(exc)) from exc
```
Add API/service tests for malformed `edited_action` and changed-material `info_payload` that assert a 409/422-style controlled response and no orphan decision/event rows.

### WR-02: Pending Queue Includes Legacy Non-Executable Rows

**File:** `src/approvals/service.py:135`
**Issue:** `list_pending_requests()` filters only by tenant, `status == "pending"`, and `expires_at`. Migration 008 explicitly preserves legacy rows as `legacy_non_executable=True` / `schema_version='approval_request.v1'`, and those rows can remain pending and unexpired. The pending review queue can therefore show approvals that the state machine will fail closed on decision, producing confusing and non-actionable approval items.
**Fix:**
```python
stmt = (
    select(ApprovalRequest)
    .where(
        ApprovalRequest.tenant_id == tenant_id,
        ApprovalRequest.schema_version == "approval_request.v2",
        ApprovalRequest.legacy_non_executable.is_(False),
        ApprovalRequest.status == "pending",
        ApprovalRequest.expires_at > datetime.now(UTC),
    )
    .order_by(ApprovalRequest.created_at.desc())
)
```
Add a regression test with a pending legacy row and assert `list_pending_requests()` and `GET /api/v1/approvals` exclude it.

### WR-03: Approval Read Endpoints Skip Current-Role Enforcement

**File:** `src/api/routers/approvals.py:145`
**Issue:** `decide_approval()` and `attach_approval_info()` enforce `APPROVAL_ROLES`, but `get_approval()` and `list_pending_approvals()` rely only on the token's `approvals:review` scope. Because `get_current_user()` validates scopes from the token and does not re-intersect them with the user's current DB role, a user whose role was downgraded while holding an unexpired approval-review token can still read approval details and the pending queue.
**Fix:**
```python
def _assert_approval_reviewer(user: User) -> None:
    if user.role not in APPROVAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for approval"},
        )

# Call this in get_approval() and list_pending_approvals() before reading rows.
```
Add API tests that authenticate a non-approval role with an over-scoped or stale `approvals:review` token and assert both read endpoints return 403.

---

_Reviewed: 2026-06-15T13:29:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
