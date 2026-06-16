---
phase: 14
slug: demo-action-executor-boundary
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-16
---

# Phase 14 - Validation Strategy

Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q` |
| **Focused run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_approval_api.py tests/test_trace_api.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` |
| **Estimated runtime** | quick <= 30s, focused <= 90s, full suite project-dependent |

## Sampling Rate

- **After every task commit:** Run the quick command, or a narrower pytest target named in the task.
- **After every plan wave:** Run the focused command for Phase 14 integration surfaces.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** no more than two task commits without an automated pytest run.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-W0-01 | 00 | 0 | DEMO-01 | T14-01 | Demo path writes `action_drafts` with `draft_outcome.status == "not_executed_demo"` and no execution/outbox side effect | contract/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py -q --tb=short` | existing | green |
| 14-W0-02 | 00 | 0 | DEMO-02 | T14-02 | Hash, revision, and safety snapshot mismatches fail closed before draft reuse or creation | service/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/actions/test_action_draft_v2.py -q --tb=short` | existing | green |
| 14-W0-03 | 00 | 0 | DEMO-02 | T14-03 | Backend/final/API wording says draft created and does not claim issued/refunded/executed external action | unit/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_final_response.py tests/test_approval_api.py tests/test_approval_integration.py -q --tb=short` | existing | green |
| 14-W0-04 | 00 | 0 | DEMO-01 | T14-04 | `action_draft_created` events contain safe refs only and no `action_execution_*` event is emitted in demo mode | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_trace_api.py tests/agent/test_events.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | existing | green |
| 14-W0-05 | 00 | 0 | DEMO-01, DEMO-02 | T14-05 | Canonical graph node is `action_draft`; retained `execute_action` compatibility is quarantined and forbidden for new references | architecture/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_graph_routing.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | existing | green |

## Wave 0 Requirements

- [x] Add failing tests before schema/service changes for `draft_outcome.v1`, exact idempotency binding, missing `target_id`, mismatched snapshot hash, and forbidden demo wording.
- [x] Add graph boundary tests proving new canonical route/node name `action_draft` and documenting any temporary `execute_action` shim owner/removal gate.
- [x] Add trace/event tests proving `action_draft_created` is safe-redacted and no `action_execution_*` events appear in demo mode.
- [x] Do not add `action_executions`, outbox, reconciliation, compensation, or external adapter side-effect assertions as positive behavior in Phase 14.

## Manual-Only Verifications

All Phase 14 behaviors have automated verification. Manual inspection is limited to reviewing generated plan coverage and checking that compatibility shims have a named owner and removal phase.

## Validation Audit 2026-06-16

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 5 stale pending validation rows updated to green |
| Escalated | 0 |

Focused validation command:

```bash
uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_approval_api.py tests/test_trace_api.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short
```

Result: `191 passed, 1 warning in 102.11s`.

Initial sandboxed execution failed with PostgreSQL socket `PermissionError: [Errno 1] Operation not permitted`; the same command passed with approved local database access.

## Validation Sign-Off

- [x] All plans include automated pytest verification for their modified surfaces.
- [x] Sampling continuity: no two consecutive implementation tasks omit automated verification.
- [x] Wave 0 covers all currently missing requirement assertions for DEMO-01 and DEMO-02.
- [x] No watch-mode flags are used in plan verification commands.
- [x] Full suite command is run before `$gsd-verify-work`.
- [x] `nyquist_compliant: true` remains set in frontmatter.

**Approval:** approved 2026-06-16
