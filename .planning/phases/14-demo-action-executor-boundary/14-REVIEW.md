---
phase: 14-demo-action-executor-boundary
reviewed: 2026-06-16T04:27:09Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/actions/service.py
  - src/agent/nodes/action_draft.py
  - src/api/routers/approvals.py
  - tests/agent/test_tools/test_create_coupon_grant_draft.py
  - tests/test_execute_action.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-16T04:27:09Z
**Depth:** deep
**Files Reviewed:** 5
**Status:** clean

## Summary

Reviewed the Phase 14 gap-closure source changes after plan 14-07 against the prior review findings, the 14-07 plan and summary, Phase 14 verification gaps, `.planning/REQUIREMENTS.md`, the Phase 13-17 architecture alignment, and the relevant contract-spec sections for action drafts, snapshot binding, tool permissions, idempotency, and approval resume.

All reviewed files meet quality standards for the requested scope. No critical, warning, or info findings remain.

## Previous Findings Recheck

| Finding | Status | Evidence |
| --- | --- | --- |
| CR-01 payload/hash mismatch | Fixed | `src/actions/service.py:82` recomputes `compute_action_payload_hash(payload)` before any draft persistence. `src/actions/service.py:89` rejects payload hash or payload/action_type mismatch with `ACTION_BINDING_MISMATCH`. Regression coverage exists at `tests/agent/test_tools/test_create_coupon_grant_draft.py:446` and `tests/agent/test_tools/test_create_coupon_grant_draft.py:471`. |
| CR-02 no-approval bypass | Fixed | `src/actions/service.py:201` fails closed when `approval_request_id is None`, returning `AUTO_ALLOWED_BINDING_REQUIRED`. No `_ValidatedActionBinding(...auto_allowed...)` return remains in the service. Regression coverage exists at `tests/agent/test_tools/test_create_coupon_grant_draft.py:309`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:367`, and `tests/agent/test_tools/test_create_coupon_grant_draft.py:405`. |
| CR-03 permission self-grant | Fixed | `src/agent/nodes/action_draft.py:195` now uses only configured permissions. There is no `permissions.append(...)` self-grant in the node. Missing permission returns `PERMISSION_REQUIRED` without executor dispatch at `tests/test_execute_action.py:151`. |
| WR-01 incomplete `ActionDraftV2Data` projection | Fixed | `src/actions/service.py:321` builds the complete v2 projection with `proposed_action`, approval refs, binding fields, draft metadata, `draft_outcome`, and `created_at`; `src/actions/service.py:343` validates it through `ActionDraftV2Data.model_validate`. |
| WR-02 overlong idempotency keys | Fixed | `src/actions/service.py:287` preserves the raw D-12 key shape when it fits and hashes overlong raw material into deterministic `key_sha256:<digest>` bounded by the 256-character DB column. Regression coverage exists at `tests/agent/test_tools/test_create_coupon_grant_draft.py:523`. |

## Deep Review Notes

- `src/api/routers/approvals.py:537` grants `tool:create_coupon_grant_draft` only in `_resume_graph_config`, and only for approved `accept`/`approve` resume results at `src/api/routers/approvals.py:539`. This preserves the trusted API/approval boundary and avoids reintroducing graph-node self-escalation.
- `ActionToolExecutor` still routes tool calls through `ActionService`, while `UnifiedToolManager` enforces caller allowlist, required permission, safety snapshot ref, and idempotency key before executor dispatch.
- The richer service `action_draft` payload does not break manager output validation because the current catalog output schema for `create_coupon_grant_draft` remains a generic object.
- No Phase 15 replay/read-switch work or Phase 17 external execution/outbox/reconciliation/compensation behavior was introduced by the reviewed source changes.

## Verification

Passed:

```bash
uv run ruff check src/actions/service.py src/agent/nodes/action_draft.py src/api/routers/approvals.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py
# All checks passed

uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py -q --tb=short
# 38 passed, 1 warning
```

Static acceptance scans confirmed:

- `compute_action_payload_hash` is used in `src/actions/service.py`.
- `AUTO_ALLOWED_BINDING_REQUIRED` is present and no `auto_allowed` revision binding remains in `src/actions/service.py`.
- `src/agent/nodes/action_draft.py` has no permission append/self-grant.
- `ActionDraftV2Data.model_validate`, `key_sha256`, `ACTION_BINDING_MISMATCH`, and `PERMISSION_REQUIRED` regression coverage are present.

---

_Reviewed: 2026-06-16T04:27:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
