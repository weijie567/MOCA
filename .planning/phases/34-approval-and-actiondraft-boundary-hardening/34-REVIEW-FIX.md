---
phase: 34-approval-and-actiondraft-boundary-hardening
fixed_at: 2026-06-29T07:51:47Z
review_path: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 34: Code Review Fix Report

**Fixed at:** 2026-06-29T07:51:47Z
**Source review:** .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Live approval interrupts reject the risk gate's claim-verification output

**Status:** fixed; focused verification passed
**Files modified:** `src/api/routers/agent_runs.py`, `tests/test_agent_runs_api.py`, `tests/test_approval_gate.py`
**Commit:** 4bdd307
**Applied fix:** Updated interrupt validation to require `claim_verification_ref` or `claim_verification_summary`, preserving nullable refs instead of converting `None` to `"None"`. Adjusted approval interrupt/API tests to use the current summary-only risk-gate payload shape.

### WR-02: Edit decisions emit a risk reroute payload, but the API never resumes the graph

**Status:** fixed; focused verification passed
**Files modified:** `src/api/routers/approvals.py`, `src/agent/nodes/assess_risk_and_approval.py`, `tests/test_approval_api.py`, `tests/test_graph_routing.py`
**Commit:** 7ab8a1a
**Applied fix:** Allowed trusted edit decisions with `resume_route="assess_risk_and_approval"` to resume the graph. Added guarded risk-node handling for trusted edit resumes so the exact edited action is re-risked and hash-checked against `new_action_payload_hash`.

### WR-03: Superseding edit/info approvals are persisted without Phase 34 binding fields

**Status:** fixed; focused verification passed
**Files modified:** `src/approvals/service.py`, `src/api/routers/approvals.py`, `tests/test_approval_api.py`, `tests/approvals/test_service_transitions.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
**Commit:** 6bd4f91
**Applied fix:** Stopped creating unbound replacement approval rows during edit/info supersede. Edit rerisk interrupts are now reconciled through the existing approval interrupt bridge, creating the replacement approval only after fresh Phase 34 bindings are available. Added manager visibility/binding coverage for the rebound row.

## Verification

```bash
uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/api/routers/agent_runs.py','tests/test_agent_runs_api.py','tests/test_approval_gate.py']]"
```
Result: passed.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action
```
Result: 2 passed, 1 warning in 7.51s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt
```
Initial result: failed with `APPROVAL_RESUME_FAILED`; root cause was a test fake using non-millisecond snapshot timestamp. Fixed and logged in `.planning/LOCAL-VALIDATION-ISSUES.md`.
Final result: 1 passed, 1 warning in 5.42s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority
```
Result: 4 passed, 1 warning in 14.67s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action
```
Result: 9 passed, 1 warning in 29.61s.

Warning observed: `LangChainPendingDeprecationWarning` from LangGraph checkpoint serde; not introduced by these changes.

## Orchestrator Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action -q --tb=short
```

Result: 9 passed, 1 warning in 27.26s.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent_runs.py src/api/routers/approvals.py src/agent/nodes/assess_risk_and_approval.py src/approvals/service.py tests/test_agent_runs_api.py tests/test_approval_gate.py tests/test_approval_api.py tests/test_graph_routing.py tests/approvals/test_service_transitions.py
```

Result: all checks passed.

```bash
git diff --check
```

Result: passed.

## Skipped Issues

None.

---

_Fixed: 2026-06-29T07:51:47Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
