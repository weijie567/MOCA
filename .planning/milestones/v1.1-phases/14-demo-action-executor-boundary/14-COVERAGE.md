# Phase 14 Coverage and Boundary Audit

**Scope:** Phase 14 Demo Action Executor Boundary  
**Completed:** 2026-06-16  
**Requirements:** DEMO-01, DEMO-02

Phase 14 is verified as a durable draft-only demo boundary. The implementation creates `action_drafts` and `draft_outcome.v1`, emits only safe draft events, projects safe trace data, and keeps external execution, outbox, reconciliation, compensation, ReplayEventV3, lifecycle finalization, and frontend timeline label cleanup with their named downstream owners.

## Final Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| Focused Phase 14 pytest | PASS, 118 tests | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_trace_api.py tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` -> 118 passed, 1 warning |
| Full pytest | PASS, 813 tests | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` -> 813 passed, 1 warning |
| Ruff | PASS | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> All checks passed |

## Requirement Coverage

| Source | ID | Feature / Requirement | Status | Evidence |
| --- | --- | --- | --- | --- |
| GOAL | Phase 14 | Enforce durable draft-only demo boundary with exact approval/snapshot binding | COVERED | `src/actions/service.py`, `src/repositories/action_draft_repo.py`, `src/agent/nodes/action_draft.py`, `src/api/routers/approvals.py`; tests in `tests/actions/test_action_draft_v2.py`, `tests/test_execute_action.py`, `tests/test_approval_integration.py`; final focused pytest 118 passed |
| REQ | DEMO-01 | Demo mode creates durable draft and `draft_outcome` only, with no execution row or external side effect | COVERED | `src/db/models.py` `ActionDraft`; `src/db/migrations/versions/009_action_draft_v2.py`; `src/actions/service.py`; negative tests in `tests/actions/test_action_draft_v2.py` and `tests/agent/test_events.py`; full pytest 813 passed |
| REQ | DEMO-02 | Demo wording and hash/revision guards cannot claim or authorize real execution | COVERED | `src/actions/service.py` binding checks, `src/api/routers/approvals.py` draft outcome reconciliation, `src/agent/nodes/final_response.py` wording; tests in `tests/agent/test_nodes/test_final_response.py`, `tests/architecture/test_action_draft_boundaries.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`; ruff passed |

## Research Constraint Coverage

| Source | ID | Constraint | Status | Evidence |
| --- | --- | --- | --- | --- |
| RESEARCH | Schema | Full `action_draft.v2` and `draft_outcome.v1` persistence | COVERED | `src/actions/schemas.py`, `src/db/models.py`, `src/db/migrations/versions/009_action_draft_v2.py`, `tests/actions/test_action_draft_v2.py`; 14-01 summary and final focused pytest |
| RESEARCH | State/reset | `action_draft`, `draft_outcome`, and `execution_mode` are state-defined and reset each turn | COVERED | `src/agent/state.py`, `src/agent/nodes/receive_request.py`, `tests/agent/test_nodes/test_receive_request.py`; focused pytest 118 passed |
| RESEARCH | Idempotency | Service-owned key and exact safety snapshot conflict behavior | COVERED | `src/actions/service.py`, `src/actions/drafts.py`, `src/repositories/action_draft_repo.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`, `tests/actions/test_action_draft_v2.py`; full pytest 813 passed |
| RESEARCH | Graph | Canonical `action_draft` node and `execute_action` shim policy | COVERED | `src/agent/nodes/action_draft.py`, `src/agent/nodes/execute_action.py`, `src/agent/graph.py`, `tests/architecture/test_action_draft_boundaries.py`, `tests/agent/test_graph.py`; focused pytest 118 passed |
| RESEARCH | Compatibility | `action_result` compatibility retained only as draft-only deprecated output | COVERED | `src/agent/nodes/action_draft.py`, `src/api/routers/approvals.py`, `src/agent/nodes/final_response.py`, `tests/architecture/test_action_draft_boundaries.py`, `tests/agent/test_nodes/test_final_response.py`; ruff passed |
| RESEARCH | Trace | Safe `action_draft_created` and `/trace` `draft_outcome` projection | COVERED | `src/agent/events.py`, `src/actions/service.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `tests/agent/test_events.py`, `tests/test_trace_api.py`; final focused pytest |

## Source Audit

| Source | ID | Feature / Requirement | Plan | Status | Evidence / Notes |
| --- | --- | --- | --- | --- | --- |
| CONTEXT | D-01..D-05 | Draft schema, outcome persistence, nullable legacy columns, and no execution/outbox/reconciliation/compensation tables | 14-01, 14-02, 14-06 | COVERED | `ActionDraft` v2 fields in `src/db/models.py`; migration `009_action_draft_v2.py`; metadata and migration negative tests in `tests/actions/test_action_draft_v2.py`; no SQLAlchemy metadata table named `action_executions`, `action_outbox_events`, `action_reconciliation_jobs`, or `action_compensation_records` |
| CONTEXT | D-06..D-10 | `draft_outcome` success signal, deprecated `action_result` limits, and honest backend/API wording | 14-02, 14-04, 14-06 | COVERED | `src/api/routers/approvals.py`, `src/agent/nodes/final_response.py`, `tests/test_approval_integration.py`, `tests/agent/test_nodes/test_final_response.py`; final wording tests include forbidden external-success phrases |
| CONTEXT | D-11..D-17 | Trusted idempotency key, required `target_id`, `auto_allowed`, exact reuse, tenant-scoped uniqueness | 14-02 | COVERED | `src/actions/service.py` builds `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}`; `src/repositories/action_draft_repo.py` exact binding reuse checks; tests in `tests/agent/test_tools/test_create_coupon_grant_draft.py` and `tests/actions/test_action_draft_v2.py` |
| CONTEXT | D-18..D-23 | Canonical graph node `action_draft`, draft-explicit tool name, retained intent taxonomy, and named shim owner | 14-03, 14-06 | COVERED | `src/agent/graph.py` registers `action_draft`; `src/tools/catalog.py` caller allowlist is `action_draft`; `src/agent/nodes/execute_action.py` is delegating shim; static tests in `tests/architecture/test_action_draft_boundaries.py` |
| CONTEXT | D-24..D-27 | `action_draft_created`, safe refs, `/trace` `draft_outcome`, and negative tests | 14-05, 14-06 | COVERED | `src/agent/events.py`, `src/actions/service.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`; tests in `tests/agent/test_events.py` and `tests/test_trace_api.py`; focused pytest 118 passed |
| CONTEXT | D-28 | Spec/phase boundary for normative contract fields, implementation extensions, and `proposed_action` storage mapping | 14-01, 14-06 | COVERED | See "Contract Boundary Record" below; `tests/actions/test_action_draft_v2.py` asserts contract `proposed_action` storage maps to existing `ActionDraft.payload` JSONB |
| CONTEXT | Deferred | ReplayEventV3, lifecycle finalizer, richer replay API | Phase 15 Replay Event Contract | DEFERRED_WITH_OWNER | Owner phase: Phase 15. Acceptance gate: Phase 15 must introduce ReplayEventV3/lifecycle/read-switch tests before verification. Phase 14 uses only minimal `AgentTraceEvent` and `/trace` compatibility projection. |
| CONTEXT | Deferred | External execution, outbox, reconciliation, compensation | Phase 17 External Action Execution | DEFERRED_WITH_OWNER | Owner phase: Phase 17. Acceptance gate: Phase 17 must add external execution/outbox/reconciliation/compensation schema, transaction, worker, and adapter tests. Phase 14 negative tests prove these surfaces are absent. |
| CONTEXT | Deferred | Frontend timeline label cleanup | Phase 15 Replay Event Contract | DEFERRED_WITH_OWNER | Owner phase: Phase 15 replay/UI timeline cleanup. Acceptance gate: Phase 15 updates replay/timeline labels after event-store read semantics are owned. Phase 14 did not modify frontend. |

## Contract Boundary Record

`docs/contract-spec.md` remains the normative contract source. The normative contract fields for action drafts include the semantic `proposed_action` body, tenant/run/draft identity, action type, payload hash, safety snapshot refs and hashes, idempotency key, status, lifecycle timestamps, retention/archive/delete fields, and the external-only tables reserved for Phase 17.

Phase 14 implementation extensions are intentionally recorded here instead of being silently treated as normative spec changes: `target_id`, `approval_revision_ref`, `execution_mode`, `draft_version`, `lifecycle_status`, `retention_policy`, and persisted `draft_outcome`. The contract `proposed_action` storage maps to the existing SQLAlchemy column named `payload`; the `payload` column stores the proposed_action JSON body for current implementation compatibility. Tests in `tests/actions/test_action_draft_v2.py` explicitly assert this `proposed_action` to `payload` mapping and assert there is no separate `proposed_action` column.

## Compatibility Disposition

| Surface | Status | Owner / Gate |
| --- | --- | --- |
| `execute_action compatibility` | Quarantined shim only | `src/agent/nodes/execute_action.py` delegates to `action_draft`; new source imports are forbidden by `tests/architecture/test_action_draft_boundaries.py`. Removal gate: Phase 15 Replay Event Contract must remove or replace the shim before Phase 15 verification, target date `2026-07-16` unless Phase 15 is replanned. |
| `action_result compatibility` | Deprecated draft-only output | `src/agent/nodes/action_draft.py` may construct draft-only compatibility data, but `src/api/routers/approvals.py` and `src/agent/nodes/final_response.py` use `draft_outcome.status == "not_executed_demo"` plus `external_side_effect is False`. Static tests forbid new `action_result.status == "success"` dependencies. Replacement/removal gate: Phase 15 Replay Event Contract, target date `2026-07-16`. |

If Phase 15 is delayed, split, or replanned, the ROADMAP, REQUIREMENTS, and this coverage artifact must be updated before Phase 15 verification with a new owner phase, removal gate, and target date for both compatibility surfaces.

## Threat Register Coverage

| Threat ID | Disposition | Evidence |
| --- | --- | --- |
| T14-06-01 | COVERED | `tests/actions/test_action_draft_v2.py` asserts no external execution tables in metadata/migration; `tests/architecture/test_action_draft_boundaries.py` forbids external execution imports; final focused pytest passed |
| T14-06-02 | COVERED | `tests/architecture/test_action_draft_boundaries.py` scans source for `action_result.status == "success"` dependencies; final response tests prove demo success depends on `draft_outcome` |
| T14-06-03 | COVERED | `src/agent/nodes/execute_action.py` shim owner/removal text plus static import ban in `tests/architecture/test_action_draft_boundaries.py` |
| T14-06-04 | COVERED | `tests/agent/test_events.py` rejects `action_execution_*` events and raw payload-like keys; `tests/test_trace_api.py` excludes raw draft payload from trace projections |

## Open Phase 14 Gaps

None. Rows not owned by Phase 14 are explicitly marked `DEFERRED_WITH_OWNER` with owner phase and acceptance gate.
