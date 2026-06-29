---
phase: 34-approval-and-actiondraft-boundary-hardening
reviewed: 2026-06-29T08:26:50Z
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
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 34: Code Review Report

**Reviewed:** 2026-06-29T08:26:50Z
**Depth:** deep
**Files Reviewed:** 39
**Status:** clean

## Summary

Deep re-review covered the same 39-file Phase 34 scope across approval interrupt creation, trusted decision resume, edit rerisk, rebound approval persistence, action draft binding validation, migration/model contracts, API schemas, safe working-state projections, and no-real-execution boundaries.

All reviewed files meet quality standards. No critical, warning, or info findings remain.

## Fixed Warning Recheck

- WR-01 resolved: approval interrupt persistence now accepts either `claim_verification_ref` or `claim_verification_summary`, and downstream approval/action binding validation accepts exact claim authority by ref or typed summary. Summary-only claim verification no longer blocks approval creation.
- WR-02 resolved: trusted edit decisions now resume through `assess_risk_and_approval`, and rerisk validates the edited action against the persisted trusted decision, tenant/run, prior snapshot/hash, and newly computed payload hash.
- WR-03 resolved: `ApprovalService` no longer creates unbound replacement approvals while superseding the old request. Replacement approvals are created only after the resumed graph emits a new approval interrupt, using the original requester/run/thread and the full Phase 34 binding payload.
- WR-04 resolved: failed resume attempts can now be retried for `edit` decisions after the original approval is `superseded`. The retry path reconstructs `edited_action`, `new_action_payload_hash`, and `resume_route` from the saved decision/event data before re-running the resume lifecycle.

## Regression Review

Commits `4bdd307`, `7ab8a1a`, `6bd4f91`, and `115550e` were checked against the current code and tests. No regressions were found in manager merchant scoping, summary-only claim binding, edit rerisk routing, rebound approval binding, retry idempotency, or the Phase 34 prohibition on real action execution/outbox behavior.

Cross-file boundary checks confirmed:

- `approval_gate` only packages a durable approval interrupt and does not make risk routing decisions.
- `assess_risk_and_approval` owns risk/approval routing, edit rerisk, safety snapshot creation, and auto-allowed binding construction.
- `approval_result` is treated as trusted resume data only after tenant/run/hash/snapshot/binding validation.
- `action_draft` creates `not_executed_demo` drafts only, with no external side effects.
- API live approval-required payloads project safe summaries and binding refs rather than raw executable action state.
- Static guards/tests continue to cover forbidden execution/outbox/compensation surfaces.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action -q --tb=short` -> `11 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_phase34_action_draft_bindings.py tests/approvals/test_phase34_boundary_bindings.py tests/approvals/test_migration_contract.py -q --tb=short` -> `42 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent_runs.py src/api/routers/approvals.py src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/approval_gate.py src/agent/nodes/action_draft.py src/approvals/service.py src/actions/service.py tests/test_agent_runs_api.py tests/test_approval_gate.py tests/test_approval_api.py tests/test_graph_routing.py tests/approvals/test_service_transitions.py tests/architecture/test_phase34_approval_action_boundaries.py tests/actions/test_phase34_action_draft_bindings.py` -> passed.
- Static pattern scans over the 39-file scope found no hardcoded secrets, dangerous function use, empty catch blocks, or production debug artifacts requiring a finding.
- Production source scans found no Phase 34 real execution, action outbox, reconciliation, compensation, refund-completed, coupon-issued, or wildcard merchant-scope shortcuts.
- `git check-ignore` confirmed the reviewed scope is not ignored by repository ignore rules.

---

_Reviewed: 2026-06-29T08:26:50Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
