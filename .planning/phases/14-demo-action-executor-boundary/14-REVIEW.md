---
phase: 14-demo-action-executor-boundary
reviewed: 2026-06-16T06:32:20Z
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
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-16T06:32:20Z
**Depth:** deep
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the full Phase 14 changed source and test scope, including the action draft service/store, graph routing, approval resume path, trace projection, tool catalog/manager, migration/model changes, and all listed tests. Phase 15 replay/read-switch work and Phase 17 external execution/outbox/reconciliation/compensation were treated as deferred.

The core approved-action draft boundary is mostly well covered: payload hashes are recomputed, approved bindings are checked, graph write tools are node-only, demo outcomes do not claim external execution, and no Phase 17 execution tables/events were introduced. The remaining issues are cross-file consistency and trace redaction gaps.

## Warnings

### WR-01: Trace Timeline Exposes Draft Idempotency Keys

**File:** `src/repositories/trace_repo.py:103-106`

**Issue:** The trace timeline includes `detail.idempotency_key` for action draft entries. Phase 14 service-built keys embed trusted binding material, including tenant/run/revision, action type, target id, and action payload hash (`src/actions/service.py:296`). That bypasses the narrower trace projection and can leak identifiers even though tests assert raw payload fields are hidden. The existing redaction test uses an opaque `idem-raw-payload` key, so it does not catch production-shaped keys that contain target ids.

**Fix:**
Remove `idempotency_key` from trace API/timeline output, or replace it with an opaque server-side diagnostic reference that cannot reveal target/action binding material. Add a regression where the draft idempotency key contains `RF-SECRET` and assert neither the key nor that target appears in the trace payload.

```python
# src/repositories/trace_repo.py
"detail": {
    "draft_id": str(draft.id),
    "draft_outcome": _safe_draft_outcome(draft),
},
```

### WR-02: `_safe_draft_outcome` Returns Arbitrary JSONB

**File:** `src/repositories/trace_repo.py:124-125`

**Issue:** `_safe_draft_outcome` is named as a safe projection, but it returns `dict(draft.draft_outcome or {})` verbatim. Service-created outcomes are validated, but the database column is JSONB and the repository/API layer should not rely on every historical or manually inserted row preserving that invariant. A malformed row with `raw_payload`, `secret`, or customer data in `draft_outcome` would be returned by `/trace`.

**Fix:**
Project only the `draft_outcome.v1` allowlisted fields, preferably by validating with `DraftOutcomeV1` and falling back to a minimal safe object for invalid legacy rows. Add a trace test with extra unexpected keys in `draft_outcome` and assert they are absent.

```python
_DRAFT_OUTCOME_KEYS = {
    "schema_version",
    "status",
    "external_side_effect",
    "tenant_id",
    "run_id",
    "draft_id",
    "created_at",
}

def _safe_draft_outcome(draft: ActionDraft) -> dict[str, Any]:
    outcome = draft.draft_outcome if isinstance(draft.draft_outcome, dict) else {}
    return {key: outcome[key] for key in _DRAFT_OUTCOME_KEYS if key in outcome}
```

### WR-03: Auto-Allowed Routing Depends On A Draft Path The Service Rejects

**File:** `src/agent/graph.py:63-65`

**Issue:** `route_after_risk` routes any proposed action with `approval_required == False` and verified snapshot binding to `action_draft`. Current Phase 14 service code intentionally rejects every no-approval draft with `AUTO_ALLOWED_BINDING_REQUIRED` (`src/actions/service.py:201-205`) because durable auto-allowed evidence is not implemented yet. That means the graph enters a write node for a path the service is designed to fail, and `final_response` does not surface the no-approval draft failure because it only renders no-approval success when `draft_outcome` is successful (`src/agent/nodes/final_response.py:177-180`). The tests currently encode the inconsistent route at `tests/test_graph_routing.py:100-103` and mock no-approval success at `tests/test_execute_action.py:314-327`.

**Fix:**
Until durable auto-allowed evidence exists, fail closed before entering `action_draft` for no-approval actions. Update the route tests to expect `final_response` for current Phase 14 auto-allowed candidates, or implement and validate the durable auto-allowed binding model before routing them to the draft node.

```python
def route_after_risk(state: AgentState) -> str:
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed or not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    # Phase 14 has no durable auto_allowed binding yet.
    return "final_response"
```

### WR-04: `create_or_get` Is Not Idempotent Under Concurrent Inserts

**File:** `src/repositories/action_draft_repo.py:36-77`

**Issue:** `ActionDraftRepository.create_or_get` first selects by `(tenant_id, idempotency_key)` and then inserts if no row is found. Two concurrent retries with the same trusted idempotency key can both miss the select; one insert wins and the other hits the unique constraint. That exception is swallowed by the service as `DRAFT_CREATION_FAILED` (`src/actions/service.py:173-174`) instead of returning the existing draft with `idempotent_reused=True`. This weakens the Phase 14 idempotency contract exactly where approval resume/retry behavior needs it most.

**Fix:**
Use a database-level upsert or catch the unique-conflict path and re-select the row before returning. The upsert is preferable because it keeps the transaction usable and makes the idempotent path deterministic.

```python
# Sketch: use PostgreSQL insert-on-conflict, then select the row.
from sqlalchemy.dialects.postgresql import insert

stmt = (
    insert(ActionDraft)
    .values(...)
    .on_conflict_do_nothing(
        constraint="uq_action_drafts_tenant_idempotency_key",
    )
    .returning(ActionDraft.id)
)
inserted_id = (await self.session.execute(stmt)).scalar_one_or_none()
draft = await self._get_by_tenant_key(tenant_id, idempotency_key)
if draft is None:
    raise ValueError("idempotency_key_conflict")
if not _same_binding(draft, ...):
    raise ValueError("idempotency_binding_conflict")
return draft, inserted_id is not None
```

## Deep Review Notes

- No new `action_execution_*` events, external execution tables, outbox/reconciliation/compensation paths, or ReplayEventV3/read-switch code were introduced in the reviewed scope.
- Approved action draft creation is guarded through `UnifiedToolManager`, `ActionToolExecutor`, and `ActionService`; missing write permission blocks executor dispatch.
- Approval resume grants `tool:create_coupon_grant_draft` only for approved `accept`/`approve` decisions.
- The `execute_action` source file is a compatibility shim only; the compiled graph registers `action_draft`.

## Verification

No automated tests were run during this review pass. Findings are from full-file reading and cross-file static analysis of the requested deep review scope.

---

_Reviewed: 2026-06-16T06:32:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
