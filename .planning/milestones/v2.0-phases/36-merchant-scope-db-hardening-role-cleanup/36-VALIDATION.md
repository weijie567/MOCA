---
phase: 36
slug: merchant-scope-db-hardening-role-cleanup
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-30
updated: 2026-06-30
---

# Phase 36 - Validation Strategy and Evidence

Per-phase validation contract and final execution evidence for merchant-scope DB hardening, role cleanup, migration gates, and trace/replay readiness.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio auto mode |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] asyncio_mode = "auto"`) |
| Final focused regression command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` |
| Lint command | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` |

## Wave 0 Requirements

All Wave 0 test files exist and were exercised by the final gates:

- [x] `tests/agent/test_phase36_run_scope.py`
- [x] `tests/approvals/test_phase36_scope_consistency.py`
- [x] `tests/db/test_phase36_migration_preflight.py`
- [x] `tests/replay/test_phase36_readiness.py`
- [x] `tests/integration/test_auth.py`

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Automated Command | Status | Evidence |
|---------|------|------|-------------|-------------------|--------|----------|
| 36-01-role-scope | 36-01 | 1 | MSH-01, MSH-02, MSH-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` | green | Covered by final focused gate. |
| 36-02-tenant-identity | 36-02 | 1 | MSH-02, MSH-03, MSH-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/approvals/test_migration_contract.py -q --tb=short` | green | Covered by final focused gate and full suite. |
| 36-03-run-scope | 36-03 | 2 | MSH-04, MSH-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py tests/test_agent_runs_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | green | AgentRun binding/API/replay focused regressions passed. |
| 36-04-consistency | 36-04 | 3 | MSH-05, MSH-07 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase36_scope_consistency.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` | green | Approval/action/snapshot consistency regressions passed. |
| 36-05-migration | 36-05 | 4 | MSH-02, MSH-03, MSH-04, MSH-05, MSH-06 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py -q --tb=short` | green | Migration contract/preflight tests passed in focused and full gates. |
| 36-06-readiness-regression | 36-06 | 5 | MSH-07, MSH-08 | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | green | Readiness and no-widening regression gates passed. |

## Final Command Evidence

| Gate | Command | Result |
|------|---------|--------|
| Phase 36 focused gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | 287 passed, 3 warnings |
| Code-review business/action focused fix gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` | 49 passed, 1 warning |
| Code-review adapter/tool/action regression gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_adapters.py tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` | 112 passed, 1 warning |
| Code-review graph/API/action regression gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/test_graph_routing.py tests/approvals/test_phase36_scope_consistency.py tests/test_approval_api.py -q --tb=short` | 175 passed, 1 warning |
| Approval/readiness/API regression subset | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_integration.py tests/test_approval_api.py tests/replay/test_phase35_trace_replay_permissions.py tests/replay/test_phase36_readiness.py tests/tools/test_tool_platform.py -q --tb=short` | 71 passed, 6 warnings |
| Split aggregate A | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py tests/conversation/test_models.py tests/conversation/test_repository.py tests/integration/test_refund_cases.py tests/integration/test_tickets.py tests/knowledge/test_facade_integration.py tests/knowledge/test_phase21_boundaries.py tests/replay/test_phase35_coverage_matrix.py -q --tb=short` | 86 passed, 2 skipped, 10 warnings |
| Split aggregate B | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/test_interception_rate.py tests/test_search_integration.py -q --tb=short` | 64 passed, 1 warning |
| Static trusted-context guard after fix | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_trusted_context_boundaries.py::test_route_current_run_id_fields_delegate_to_legacy_identity_projection -q --tb=short` | 1 passed, 1 warning |
| Interrupt/API focused regression after fix | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required tests/test_agent_runs_api.py::test_event_generator_rejects_spoofed_interrupt_proposed_action_identity tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_agent_runs_api.py::test_agent_chat_interrupt_rejects_proposed_action_identity_mismatch tests/test_agent_runs_api.py::test_sse_interrupted_path_skips_memory_write tests/test_agent_runs_api.py::test_agent_run_error_cancel_interrupted_do_not_write_completed_memory tests/test_approval_integration.py::test_high_risk_approve_flow_interrupts_resumes_executes_action -q --tb=short` | 10 passed, 2 warnings |
| Tool platform regression after unused-import cleanup | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/tools/test_tool_result_storage.py tests/agent/test_tools/test_unified_tool_manager.py -q --tb=short` | 63 passed, 1 warning |
| Full suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` | 2125 passed, 4 skipped, 44 warnings |
| Ruff | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` | All checks passed |

## Readiness Artifact

`eval/replay/phase36-readiness.v1.json` records:

- `schema_version`: `phase36_trace_replay_readiness.v1`
- `readiness_result`: `ready_with_agent_run_binding`
- `blockers`: `[]`
- Trusted facts limited to persisted AgentRun target binding, approval/action/snapshot consistency, migration preflight evidence, and BusinessFactService/Phase 34 authority.
- Untrusted facts explicitly include `requested_by -> user.merchant_id`, owner identity, thread id, prompt text, memory, RAG evidence, LLM output, raw tool payload, `target_merchant_context`, and `replay_authorization_proof`.

## No-Widening Evidence

- Same-merchant manager run/status/evidence/trace/replay visibility is not implemented in Phase 36.
- Existing owner/admin-only trace and replay guards remain covered by `tests/replay/test_phase35_trace_replay_permissions.py` and `tests/test_trace_api.py`.
- Static no-widening checks confirm `target_merchant_id`, `scope_classification`, `phase36_readiness`, `project_replay_authorization_proof`, and `target_merchant_context` are not authorization guard inputs in Phase 36 route code.
- RLS/session tenant mechanisms remain unimplemented. This acceptance scan returned no matches:
  `rg -n "ROW LEVEL SECURITY|CREATE POLICY|ENABLE ROW LEVEL SECURITY|SET LOCAL|current_setting" src/db src/api src/auth src/platform src/agent src/replay`

## Source Audit

| Source | ID | Feature / Requirement | Status | Notes |
|--------|----|-----------------------|--------|-------|
| REQ | MSH-01 | Legacy merchant role deprecated compatibility-only | COVERED | Role/static focused tests and final suite passed. |
| REQ | MSH-02 | Active business users require merchant binding or fail closed | COVERED | Runtime deny-first checks plus migration preflight/final suite passed. |
| REQ | MSH-03 | Tenant-scoped username identity | COVERED | Auth and migration-contract tests passed. |
| REQ | MSH-04 | AgentRun target merchant binding and classification | COVERED | AgentRun runtime/API/migration tests passed. |
| REQ | MSH-05 | Approval/action/snapshot consistency | COVERED | Scope consistency, action draft, approval API, and snapshot tests passed. |
| REQ | MSH-06 | Authoritative migration/backfill only | COVERED | Migration source/preflight tests passed; weak proof remains rejected. |
| REQ | MSH-07 | Runtime no-regression boundaries | COVERED | Focused no-widening and full suite passed. |
| REQ | MSH-08 | Phase 37 readiness conclusion | COVERED | Strict readiness artifact validates and records `ready_with_agent_run_binding`. |
| DEFERRED | Phase 37 | Same-merchant manager run/status/evidence/trace/replay expansion | EXCLUDED | Not implemented in Phase 36; readiness only authorizes future planning. |
| DEFERRED | RLS | PostgreSQL RLS/session tenant variables | EXCLUDED | No production RLS/session tenant variable matches. |

## Issues Encountered During Validation

- A split aggregate rerun initially collided with a likely still-running full-suite process from a previous truncated command. PostgreSQL DDL on shared `moca_test/public` produced `pg_type` duplicate/deadlock errors. After confirming no pytest process remained and resetting the test schema, the same split aggregate passed.
- The first full-suite run found one static boundary failure: `tests/architecture/test_trusted_context_boundaries.py::test_route_current_run_id_fields_delegate_to_legacy_identity_projection`. The legacy `/api/v1/agent/chat` interrupt persistence path was writing `"current_run_id":` directly in route code. The fix now delegates legacy identity fields to `_legacy_agent_state_identity(trusted_context)`.
- Full ruff initially found unused imports in `src/tools/manager.py`, `src/tools/platform.py`, and `src/tools/runtime.py`. These were mechanical stale imports; removing them made full ruff pass and the focused tool-platform tests stayed green.
- Code review found three true warnings after the initial merge: real business reads omitted `merchant_id`, auto-allowed drafts could run before final `AgentRun` scope persistence, and auto-allowed draft creation did not validate the stored `risk_decision` payload. The final `36-REVIEW.md` records the adjudication, fixes, and green code-review gates.

## Validation Sign-Off

- [x] All planned requirement areas have automated verification targets.
- [x] Wave 0 coverage exists and was exercised.
- [x] No watch-mode flags.
- [x] All commands use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or the full-suite `uv run` entry; bare `pytest` is forbidden.
- [x] Focused Phase 36 gate passed.
- [x] Full suite passed.
- [x] Full ruff passed.
- [x] Code-review warnings adjudicated and resolved.
- [x] Phase 37/RLS deferred ideas remain unimplemented.

**Approval:** complete on 2026-06-30.
