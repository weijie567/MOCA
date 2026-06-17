---
status: complete
phase: 14-demo-action-executor-boundary
source:
  - 14-01-SUMMARY.md
  - 14-02-SUMMARY.md
  - 14-03-SUMMARY.md
  - 14-04-SUMMARY.md
  - 14-05-SUMMARY.md
  - 14-06-SUMMARY.md
started: 2026-06-16T08:19:12Z
updated: 2026-06-16T09:10:50Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: From a fresh process and current database schema, Phase 14 starts cleanly: migrations are at head, the app's primary test/API surfaces can initialize, and the focused Phase 14 validation suite passes without setup beyond the existing local PostgreSQL service.
result: pass

### 2. Durable Demo Draft, Not External Execution
expected: When a compensation action is approved for demo mode, the system creates a durable `action_drafts` row with `draft_outcome.status == "not_executed_demo"` and `external_side_effect == false`; no execution row, outbox, reconciliation job, compensation record, adapter dispatch, or `action_execution_*` event is created.
result: pass

### 3. Fail-Closed Binding Guardrails
expected: Missing `target_id`, payload/hash mismatch, mismatched safety snapshot binding, or omitted approval evidence fails closed before draft persistence and leaves no draft row for that run.
result: pass

### 4. Approval Resume And Final Wording
expected: An approved resume path can create a draft through the trusted approval boundary, and API/final-response wording says a draft was created in demo mode without claiming coupon issuance, refund completion, ticket closure, or external success.
result: pass

### 5. Canonical Graph And Permission Boundary
expected: The canonical graph node is `action_draft`; `execute_action` is only a delegating compatibility shim, and the write tool is blocked with `PERMISSION_REQUIRED` unless permission is supplied by the trusted approved-resume boundary.
result: pass

### 6. Safe Trace And Event Projection
expected: Trace/timeline output exposes `draft_outcome` and safe refs such as draft id, target id, payload hash, and safety snapshot hash, while excluding raw action payload/tool args and all `action_execution_*` demo events.
result: pass

### 7. Exact Idempotency And Reuse
expected: Repeating the same tenant/run/action/target/payload/snapshot binding reuses the existing draft, while any binding mismatch raises a conflict; draft identity is service-owned, tenant-scoped, and bounded to the database key length.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
