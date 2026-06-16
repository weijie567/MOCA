---
phase: 14-demo-action-executor-boundary
reviewed: 2026-06-16T02:52:32Z
depth: deep
files_reviewed: 33
files_reviewed_list:
  - src/actions/drafts.py
  - src/actions/schemas.py
  - src/actions/service.py
  - src/agent/events.py
  - src/agent/graph.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/receive_request.py
  - src/agent/state.py
  - src/api/routers/approvals.py
  - src/api/routers/traces.py
  - src/db/migrations/versions/009_action_draft_v2.py
  - src/db/models.py
  - src/repositories/action_draft_repo.py
  - src/repositories/trace_repo.py
  - src/tools/catalog.py
  - src/tools/executors/action.py
  - src/tools/manager.py
  - tests/actions/test_action_draft_v2.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_tools/test_create_coupon_grant_draft.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_action_draft_boundaries.py
  - tests/test_approval_api.py
  - tests/test_approval_integration.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
  - tests/test_trace_api.py
  - tests/tools/test_catalog.py
findings:
  critical: 3
  warning: 2
  info: 0
  total: 5
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-16T02:52:32Z
**Depth:** deep
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the Phase 14 action draft boundary, approval resume path, tool manager boundary, trace projections, migrations, and the listed tests at deep depth. The main risks are in the write boundary: the service accepts trusted hash references without proving the payload being persisted is the payload those hashes describe, treats any valid snapshot as auto-allowed when no approval id is supplied, and the node self-grants the action tool permission before invoking the manager.

## Critical Issues

### CR-01: Action drafts can persist a payload that does not match the approved action hash

**File:** `src/actions/service.py:72`
**Issue:** `create_coupon_grant_draft` only checks that the supplied `action_payload_hash`, `safety_snapshot_ref`, and `safety_snapshot_hash` exist together on an `ActionSafetySnapshot` or approved request. It never recomputes `action_payload_hash` from `payload` before persisting `payload` at line 110. That lets a caller store an arbitrary or raw payload under a valid approved hash. The current tests exercise this bad path by approving a full `proposed_action` but passing small payloads like `{"target_id": "RF-1001"}` to the draft service.
**Fix:**
```python
from src.approvals.snapshot_service import compute_action_payload_hash
from src.common.canonical_hash import CanonicalHashError

try:
    computed_payload_hash = compute_action_payload_hash(payload)
except (CanonicalHashError, TypeError, ValueError):
    return _tool_error("INVALID_ACTION_PAYLOAD", "Action payload is invalid", retryable=False)

if computed_payload_hash != action_payload_hash:
    return _tool_error(
        "ACTION_BINDING_MISMATCH",
        "Action payload hash does not match action payload",
        retryable=False,
    )
if str(payload.get("action_type") or "") != action_type:
    return _tool_error("ACTION_BINDING_MISMATCH", "Action type does not match action payload", retryable=False)
```

### CR-02: Omitting `approval_request_id` bypasses approval for any valid snapshot

**File:** `src/actions/service.py:184`
**Issue:** When `approval_request_id` is `None`, `_validate_action_binding` returns an `"auto_allowed"` binding solely because the snapshot hash tuple exists. The snapshot schema does not persist an `auto_allowed` or `approval_required` decision, so a high-risk pending approval snapshot can be used to create a draft by omitting the approval id. The current `test_create_coupon_grant_draft_auto_allowed_key_is_service_owned` builds a normal approval request and then succeeds with `approval_request_id=None`, which demonstrates the bypass.
**Fix:** Persist the risk decision into durable binding material and require it for no-approval drafts, or require an approved `approval_request_id` until that binding exists.
```python
if approval_request_id is None:
    if snapshot.snapshot_json.get("auto_allowed") is not True:
        return _tool_error("APPROVAL_REQUIRED", "Action draft requires approved request", retryable=False)
    return _ValidatedActionBinding(
        revision_marker="auto_allowed",
        approval_revision_ref="auto_allowed",
    )
```

### CR-03: The action node self-grants the write-tool permission

**File:** `src/agent/nodes/action_draft.py:195`
**Issue:** `action_draft` copies `configurable["permissions"]` and appends `tool:create_coupon_grant_draft` if it is missing. That defeats `UnifiedToolManager.invoke`'s required-permission check at `src/tools/manager.py:85`; a graph run with no action-tool permission is upgraded by the node before dispatch. This makes the permission check ineffective exactly at the write boundary.
**Fix:** Do not synthesize permissions inside the node. Pass the permission from the authenticated/trusted orchestration boundary, and test that a config without it returns `PERMISSION_REQUIRED`.
```python
permissions = list(configurable.get("permissions") or [])

tool_ctx = ToolCallContext(
    ...
    permissions=permissions,
    ...
)
```

## Warnings

### WR-01: `action_draft` response does not satisfy `ActionDraftV2Data`

**File:** `src/actions/service.py:298`
**Issue:** `ActionDraftV2Data` requires `proposed_action` and `draft_outcome` (`src/actions/schemas.py:21`), but `_action_draft_data` returns neither. Callers receive a dict labeled `schema_version: action_draft.v2` that cannot be validated by the v2 schema.
**Fix:** Either rename this as a separate projection schema or return the full v2 shape.
```python
def _action_draft_data(draft, draft_outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": draft.schema_version,
        "tenant_id": str(draft.tenant_id),
        "run_id": str(draft.run_id),
        "draft_id": str(draft.id),
        "proposed_action": draft.payload,
        "action_payload_hash": draft.action_payload_hash,
        "approval_ref": str(draft.approval_request_id) if draft.approval_request_id else None,
        "approval_revision_ref": draft.approval_revision_ref,
        "safety_snapshot_ref": draft.safety_snapshot_ref,
        "safety_snapshot_hash": draft.safety_snapshot_hash,
        "target_id": draft.target_id,
        "idempotency_key": draft.idempotency_key,
        "status": draft.status,
        "execution_mode": draft.execution_mode,
        "draft_version": draft.draft_version,
        "lifecycle_status": draft.lifecycle_status,
        "retention_policy": draft.retention_policy,
        "draft_outcome": draft_outcome,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }
```

### WR-02: Service-built idempotency keys can exceed the database column length

**File:** `src/actions/service.py:276`
**Issue:** `_build_idempotency_key` concatenates tenant id, run id, revision marker, action type, target id, and a 71-character SHA-256 string into `ActionDraft.idempotency_key`, but the column is `String(256)` (`src/db/models.py:593`). A valid 128-character `target_id` can push the key above 300 characters, causing draft creation to fail with a generic retryable error.
**Fix:** Store a fixed-length digest for the composite idempotency material, or increase the column with a matching migration and explicit validation.
```python
import hashlib

def _build_idempotency_key(...):
    material = f"{tenant_id}:{run_id}:{revision_marker}:{action_type}:{target_id}:{action_payload_hash}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"action_draft.v2:{tenant_id}:{digest}"
```

---

_Reviewed: 2026-06-16T02:52:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
