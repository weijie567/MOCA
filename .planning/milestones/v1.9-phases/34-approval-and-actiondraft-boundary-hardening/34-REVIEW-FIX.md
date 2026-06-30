---
phase: 34-approval-and-actiondraft-boundary-hardening
fixed_at: 2026-06-29T08:14:01Z
review_path: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 34: Code Review Fix Report

**Fixed at:** 2026-06-29T08:14:01Z
**Source review:** .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-04: Failed edit resume cannot be retried after the approval is superseded

**Status:** fixed; focused verification passed
**Files modified:** `src/api/routers/approvals.py`, `tests/test_approval_api.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
**Commit:** 115550e
**Applied fix:** Extended recoverable resume retries to include saved `edit` decisions on `superseded` approvals. Retry reconstruction now rebuilds trusted edit resume payloads from the persisted decision and `approval_decided` event metadata/resource refs, including `edited_action`, `new_action_payload_hash`, and `resume_route`, and rejects mismatched retry bodies. Added an API regression that simulates a failed edit rerisk resume before rebound approval persistence, then retries the same decision and verifies the graph is called again with the same trusted edit fields and a bound replacement approval is created. Logged and fixed a local test fixture issue in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/api/routers/approvals.py','tests/test_approval_api.py']]"
```

Result: passed.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision -q --tb=short
```

Initial result: failed with `sqlalchemy.exc.MissingGreenlet` from accessing expired `seeded_session["merchant"].id` after async commit/rollback. Fixed by capturing `merchant_id` before the retry flow and recorded the issue in `.planning/LOCAL-VALIDATION-ISSUES.md`.

Final result: `1 passed, 1 warning in 3.64s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision -q --tb=short
```

Result: `4 passed, 1 warning in 13.19s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py tests/test_approval_api.py
```

Result: `All checks passed!`

```bash
git diff --check -- src/api/routers/approvals.py tests/test_approval_api.py .planning/LOCAL-VALIDATION-ISSUES.md
```

Result: passed.

Warning observed: `LangChainPendingDeprecationWarning` from LangGraph checkpoint serde; not introduced by this fix.

## Orchestrator Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision -q --tb=short
```

Result: 4 passed, 1 warning in 13.07s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action -q --tb=short
```

Result: 10 passed, 1 warning in 30.00s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py tests/test_approval_api.py
```

Result: all checks passed.

```bash
git diff --check
```

Result: passed.

## Skipped Issues

None.

---

_Fixed: 2026-06-29T08:14:01Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
