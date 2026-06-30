---
status: complete
phase: 34-approval-and-actiondraft-boundary-hardening
source:
  - 34-01-SUMMARY.md
  - 34-02-SUMMARY.md
  - 34-03-SUMMARY.md
  - 34-04-SUMMARY.md
  - 34-05-SUMMARY.md
  - 34-06-SUMMARY.md
started: 2026-06-29T08:14:00Z
updated: 2026-06-29T08:51:38Z
mode: automated_self_verification
---

# Phase 34 UAT

## Current Test

[testing complete]

## Tests

### 1. Approval/action binding contracts and persistence
expected: Approval requests and action drafts persist typed target merchant, business fact, evidence, claim, risk, payload hash, safety snapshot, and idempotency bindings without adding real-execution tables.
result: pass
evidence: Phase 34 focused suite final run passed; architecture and migration tests covered approval/action binding columns and no-real-execution storage guards.

### 2. Risk gate owns approval/action routing
expected: Risk routing uses `risk_gate` semantics; `approval_gate` does not re-decide blocked, approval-required, or auto-draft policy, and routes fail closed on missing or mismatched bindings.
result: pass
evidence: Final focused suite covered `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`, `tests/agent/test_graph.py`, and approval boundary architecture tests.

### 3. Approval service and API enforce trusted scope
expected: Approval creation, decision, needs-info resume, and manager review paths preserve Phase 34 bindings, reject stale/untrusted transitions, and enforce same-merchant access without wildcard merchant scope.
result: pass
evidence: Final focused suite covered `tests/approvals`, `tests/test_approval_api.py`, `tests/test_approval_gate.py`, `tests/platform/test_merchant_scope.py`, and static merchant-scope tests.

### 4. Agent runs approval bridge exposes only safe approval wait data
expected: Live `approval_required` responses create approval requests from trusted interrupt bindings, reject spoofed run/action identity, and project summaries/refs rather than raw proposed action or debug payloads.
result: pass
evidence: Final focused suite covered `tests/test_agent_runs_api.py`; post-review WR regression slice also passed.

### 5. Action draft boundary remains exact-bound and demo-only
expected: Approved and auto-allowed action draft paths validate exact Phase 34 binding material before durable draft insert/reuse, keep safe projections, and do not introduce real external execution/outbox behavior.
result: pass
evidence: Final focused suite covered `tests/actions/test_action_draft_v2.py`, `tests/actions/test_phase34_action_draft_bindings.py`, `tests/test_execute_action.py`, and action draft architecture guards.

### 6. Final boundary and static guard closure
expected: Phase 34 static guards cover ordinary chat spoofing, manager shortcuts, wildcard resume, approval/action boundary ownership, Phase 35 trace projection deferral, and execution-positive wording.
result: pass
evidence: Final focused suite covered `tests/architecture/test_phase34_approval_action_boundaries.py`, `tests/architecture/test_approval_boundaries.py`, `tests/architecture/test_action_draft_boundaries.py`, and Phase 33 RAG claim boundary regression tests.

### 7. Post-review WR-03/WR-04 rerisk and retry semantics
expected: Edit or changed-info supersede produces trusted rerisk/rebind signals without creating an unbound replacement approval; a replacement approval is created only after the resumed graph emits a new approval interrupt, and failed edit resume can be retried.
result: pass
evidence: Updated stale service tests and reran targeted WR slice: `tests/approvals/test_needs_info_resume.py` passed, and the WR-03/WR-04 API/graph slice passed.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]

## Automated Verification

Initial self-check found stale Phase 34 tests after WR-03:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short
```

Initial result: `6 failed, 397 passed, 23 warnings in 410.10s`. The failures were old `tests/approvals/test_needs_info_resume.py` assertions expecting service-layer creation of an immediate replacement approval. That contradicted WR-03's current contract, where service supersede emits rerisk/rebind material and replacement approval creation waits for the resumed graph interrupt. The issue and fix are recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

Targeted post-fix checks:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_needs_info_resume.py -q --tb=short
```

Result: `13 passed, 1 warning in 37.49s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_approval_gate.py::test_approval_gate_interrupt_payload_contains_display_refs_and_versions tests/test_approval_api.py::test_decide_edit_supersedes_and_resumes_risk_reroute tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_attach_info_changed_payload_supersedes_without_unbound_replacement tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision tests/approvals/test_service_transitions.py::test_edit_decision_reroutes_to_risk_without_approved_resume_authority tests/test_graph_routing.py::test_edit_resume_rerisk_uses_exact_trusted_edited_action -q --tb=short
```

Result: `10 passed, 1 warning in 25.99s`.

Final Phase 34 focused suite:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short
```

Result: `403 passed, 22 warnings in 389.10s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/approvals src/actions src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/approval_gate.py src/agent/nodes/action_draft.py src/agent/graph.py src/agent/graph_vocabulary.py src/api/routers/agent_runs.py src/api/routers/approvals.py src/api/schemas/agent_runs.py src/api/schemas/approvals.py tests/approvals tests/actions tests/architecture/test_phase34_approval_action_boundaries.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_execute_action.py tests/test_graph_routing.py
```

Result: `All checks passed!`

```bash
git diff --check
```

Result: passed.

## Artifact Scan

`node "$HOME/.codex/get-shit-done/bin/gsd-tools.cjs" audit-open --json` reported no Phase 34 UAT gaps, verification gaps, debug sessions, or context questions. It reported one unrelated global planning todo: `2026-06-22-archive-old-phase-directories.md`.

## Security Gate

`workflow.security_enforcement` is enabled and Phase 34 has no `*-SECURITY.md` artifact. Code/UAT verification is complete, but the next GSD gate before advancing should be:

```bash
$gsd-secure-phase 34
```
