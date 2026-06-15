# Phase 13 Approval State Machine Coverage

**Status:** Blocked by full-suite verification failure  
**Eval manifest:** `tests/approvals/phase13_eval_manifest.json`  
**Eval dataset:** `approval-contract-phase13.v1`  
**Eval dataset hash:** `sha256:89251f64d1ffde20061b7406e684ee1c3bc56cedc882bc6c15a11799819600ae`  
**Eval blocking status:** `blocking_for_phase_exit`  
**Eval failure impact:** `phase_13_not_ready_for_execution`

No relevant MISSING rows remain in this Phase 13 coverage record. Any deferred capability below is recorded as `DEFERRED_WITH_OWNER` with owner, non-blocking rationale, dependency, and acceptance gate.

**Readiness verdict:** `phase_13_not_ready_for_execution` until the full-suite blocker in the Blocking Follow-Ups section is resolved.

## Requirement Coverage

| Requirement | Coverage status | Owning plan(s) | Evidence | Test command |
| --- | --- | --- | --- | --- |
| APPROVAL-01 | COVERED | 13-02, 13-03, 13-04, 13-06, 13-07 | Versioned request/level/assignment/decision schema, `ApprovalService` transition boundary, stale request/level/assignment/revision conflicts, wrong tenant/run/thread/binding failures, no-orphan rollback checks, API/graph cutover, approval events, and legacy v1 fail-closed deletion/quarantine. | `uv run pytest tests/approvals/test_migration_contract.py tests/approvals/test_service_transitions.py tests/approvals/test_single_level_runtime.py tests/approvals/test_hash_binding.py tests/approvals/test_events.py tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_graph_routing.py -q --tb=short` |
| APPROVAL-02 | COVERED | 13-05, 13-07 | `respond` enters `needs_info` without action resume, clarification identity/scope/version is bound, `attach_info` validates tenant/thread/versions, changed payload/evidence/config supersedes the old revision, `edit` reroutes through risk, and old revisions cannot execute. | `uv run pytest tests/approvals/test_needs_info_resume.py tests/test_approval_api.py tests/test_graph_routing.py tests/test_execute_action.py -q --tb=short` |
| APPROVAL-03 | COVERED | 13-02, 13-03, 13-06, 13-07 | Single-level runtime uses the target request/level/assignment/decision tables; multi-level-compatible `any_one` and `all` schema contracts are verified; the SLA scanner is implemented and feature-disabled with Phase 15 enablement ownership. | `uv run pytest tests/approvals/test_multi_level_contract.py tests/approvals/test_single_level_runtime.py tests/approvals/test_sla_scanner.py tests/architecture/test_approval_boundaries.py -q --tb=short` |
| SNAPSHOT-01 | COVERED | 13-01, 13-03, 13-04, 13-07 | `CanonicalHashProfile v1`, `proposed_action.v1` golden bytes, `action_safety_snapshot.v1` golden bytes, score stripping/rank retention, durable snapshot rows, exact action/snapshot hash binding in approval and action guards, and legacy rows fail closed. | `uv run pytest tests/approvals/test_canonical_hash.py tests/approvals/test_snapshots.py tests/approvals/test_hash_binding.py tests/test_execute_action.py tests/test_graph_routing.py -q --tb=short` |

## Follow-Up Register

| ID | Item | Status | Owner | Non-blocking rationale | Dependency | Acceptance gate |
| --- | --- | --- | --- | --- | --- | --- |
| P13-FU-01 | Phase 13 internal slice 13a approval state machine/CAS/revision | COVERED | Phase 13 | N/A - implemented in Phase 13. | Plans 13-02, 13-03, 13-04, 13-07 | Focused approval service/API/architecture tests pass and final gate records PASS. |
| P13-FU-02 | Phase 13 internal slice 13b ActionSafetySnapshot + CanonicalHashProfile + hash binding | COVERED | Phase 13 | N/A - implemented in Phase 13. | Plans 13-01, 13-03, 13-04, 13-07 | Canonical hash, snapshot, hash-binding, action guard, and graph routing tests pass. |
| P13-FU-03 | Phase 13 internal slice 13c `needs_info` resume | COVERED | Phase 13 | N/A - implemented in Phase 13. | Plan 13-05 | `tests/approvals/test_needs_info_resume.py` and API/routing tests pass. |
| P13-FU-04 | SLA scanner implementation and event-shape tests | COVERED | Phase 13 | N/A - implemented in Phase 13 with scanner disabled by default. | Plan 13-06 | `APPROVAL_SLA_SCANNER_ENABLED=false` remains default and disabled scanner tests pass. |
| P13-FU-05 | SLA scanner active enablement | DEFERRED_WITH_OWNER | Phase 15 | Non-blocking because Phase 13 implemented the scanner and safe event shapes but active scanning requires replay coverage and allocator checks before scheduler enablement. | Phase 15 ReplayEventV3 enrichment, replay coverage for reminder/escalation/expire events, allocator concurrency with the SLA writer, rollback behavior. | Phase 15 acceptance gate enables the scanner only after replay consumption, allocator concurrency, and rollback tests pass; otherwise Phase 15 explicitly keeps it disabled. |
| P13-FU-06 | Cross-table enforcement row mapping for decision -> assignment -> level -> request | COVERED | Phase 13 | N/A - copied and verified in Phase 13. | Contract-spec Section 18.2 and Plans 13-02/13-03. | Tests cover wrong assignment-level, wrong level-request, wrong tenant, wrong run, wrong revision, stale request/level/assignment versions, and rollback/no orphan assertions. |
| P13-FU-07 | Phase 13 eval gate metadata | COVERED | Phase 13 | N/A - manifest is owned, versioned, hash-pinned, requirement-scoped, and blocking for phase exit. | Frozen Phase 13 approval contract test corpus. | `tests/approvals/phase13_eval_manifest.json` contains `approval-contract-phase13.v1`, real `sha256:` dataset hash, `blocking_for_phase_exit`, and `phase_13_not_ready_for_execution`. |
| P13-FU-08 | Phase 14 demo action executor boundary | DEFERRED_WITH_OWNER | Phase 14 | Non-blocking because Phase 13 only hands off exact approval/snapshot hashes and does not implement demo draft outcome semantics. | Phase 13 approval_result.v1, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`. | Phase 14 acceptance gate proves draft-only behavior, no execution row, no external side effect, exact hash/snapshot binding, and truthful demo wording. |
| P13-FU-09 | Phase 15 replay enrichment and replay read switch | DEFERRED_WITH_OWNER | Phase 15 | Non-blocking because Phase 13 emits minimal approval events and records `approval_events.replay_event_id` as nullable; full ReplayEventV3 lifecycle/read API belongs to Phase 15. | Phase 10 minimal event envelope, Phase 12 memory events, Phase 13 approval events, Phase 14 action draft events. | Phase 15 acceptance gate consumes approval event actor/resource/payload shape, enriches ReplayEventV3, validates retention/redaction, and switches `/replay` with rollback. |
| P13-FU-10 | Phase 16 long-term/case memory | DEFERRED_WITH_OWNER | Phase 16 | Non-blocking because Phase 13 approval/snapshot truth does not use memory as evidence or authorization. | Phase 12 session memory, Phase 15 replay foundations. | Phase 16 acceptance gate implements memory_identity.v1, tombstones, review workflow, and retrieval predicates without weakening Phase 12 fallback or Phase 13 approval authority. |
| P13-FU-11 | Phase 17 external action execution/outbox/reconciliation/compensation | DEFERRED_WITH_OWNER | Phase 17 | Non-blocking because Phase 13 authorizes only approval/snapshot handoff and does not create external execution side effects. | Phase 14 demo draft boundary and Phase 15 replay service. | Phase 17 acceptance gate proves claim-before-dispatch, committed outbox claim, unknown/reconciliation safety, compensation authorization, and duplicate execution/key guards. |

## Cross-Table Enforcement Row Mapping

| Relationship | Phase 13 disposition | Required mismatch tests | Evidence |
| --- | --- | --- | --- |
| decision -> assignment -> level -> request | COVERED | wrong assignment-level; wrong level-request; wrong tenant; wrong run; wrong revision; stale request version; stale level version; stale assignment version; any mismatch rolls back and writes no orphan decision/event rows. | `tests/approvals/test_service_transitions.py`, `tests/approvals/test_multi_level_contract.py`, `tests/approvals/test_migration_contract.py` |
| action_draft -> approval_request | DEFERRED_WITH_OWNER | pending/expired/superseded request; incomplete level; tenant/run/payload/snapshot mismatch. | Owner Phase 14; Phase 13 direct action guard tests cover the handoff until draft binding fields land. |
| action_execution -> draft | DEFERRED_WITH_OWNER | wrong tenant/run/hash; stale draft version; duplicate active execution/attempt/key; demo execution row. | Owner Phase 17; blocked behind Phase 14 draft-only boundary. |
| outbox/reconciliation/compensation -> execution/draft | DEFERRED_WITH_OWNER | wrong execution-draft; tenant/hash/key mismatch; unclaimed dispatch; duplicate active job/compensation; mismatch forbids dispatch/compensation. | Owner Phase 17; blocked until external execution tables and outbox exist. |

The deferred cross-table rows have owner phases, dependency chains, and acceptance gates in the follow-up register above. They are not Phase 13 readiness gaps.

## Spec Reconciliation Register

| ID | Source requirement | Conflicting evidence | Type | Recommended handling | Readiness impact | Owner | Status | Acceptance gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P13-SCF-01 | `docs/contract-spec.md` Section 15.3 `approval_decision_command.v1` lists `decision_type=accept|edit|respond|reject|ignore`. | Section 18.2 storage checks and Phase 13 API/service/event implementation use `accept|approve|edit|respond|reject|ignore`; API compatibility still accepts `approve`. | SPEC_CONFLICT | Update contract-spec Section 15.3 to include `approve` as a supported compatibility decision type or explicitly define `approve` as an API alias normalized by the trusted endpoint. | REQUIRES_BLUEPRINT_UPDATE | Blueprint/docs owner before Phase 15 replay contract freeze. | ACCEPTED_DEVIATION | Contract update lands before Phase 15 consolidates approval decision replay semantics; Phase 13 tests continue to prove all six decision types emit safe metadata. |
| P13-SCF-02 | `docs/contract-spec.md` Section 18.2 approval table definitions are incomplete for the implemented Phase 13 shape. | Phase 13 implementation requires `approval_decisions.thread_id` and Phase 13 `approval_events` shape: `actor_id`, `metadata_json`, `resource_refs_json`, `redacted_payload_json`, redundant tenant/run/thread/revision/version fields, and nullable `replay_event_id`. | REQUIRES_BLUEPRINT_UPDATE | Require a contract-spec Section 18.2 table update for `approval_decisions.thread_id` plus the Phase 13 `approval_events` shape: `actor_id`, `metadata_json`, `resource_refs_json`, `redacted_payload_json`, redundant tenant/run/thread/revision/version fields, and nullable `replay_event_id`. | REQUIRES_BLUEPRINT_UPDATE | Blueprint/docs owner with Phase 15 replay owner as consumer. | ACCEPTED_DEVIATION | Phase 15 replay consumption of `actor_id`, `metadata_json`, `resource_refs_json`, `redacted_payload_json`, redundant tenant/run/thread/revision/version fields, and nullable `replay_event_id` validates the shape before replay read-switch. |
| P13-SCF-03 | `docs/contract-spec.md` Section 15.3 names `action_safety_snapshot.v1` but does not provide an authoritative golden digest. | Phase 13 froze the authoritative local golden digest in `tests/approvals/test_snapshots.py`: `sha256:aafef5b8874e80241fce531bc6d3f73a7e713b6066586c50330ec9ee5e0ad144`. | SPEC_CONFLICT | Update contract-spec Section 15.3 with the canonical `action_safety_snapshot.v1` sample canonical JSON, hash input bytes, and digest, or explicitly reference the Phase 13 golden test as the authoritative fixture. | REQUIRES_BLUEPRINT_UPDATE | Blueprint/docs owner before Phase 14 action draft binding uses the snapshot contract. | ACCEPTED_DEVIATION | Phase 14 acceptance gate validates action draft snapshot binding against the same golden digest or the updated contract-spec sample. |

## Compatibility Disposition

| Path | Owner | Forbidden new references | Protection test | Final status | Deletion/Gate |
| --- | --- | --- | --- | --- | --- |
| `src/repositories/approval_repo.py` | Phase 13 compatibility path | Routers, agent routers, graph nodes, and tests cannot import legacy transition methods. | `tests/architecture/test_approval_boundaries.py` | Deleted in Plan 13-07. | Complete; deletion verified by Plan 13-07 self-check. |
| `ApprovalRepository.decide` and `mark_expired` | Obsolete v1 transition API | No new references anywhere outside optional shim-internal calls. | `tests/architecture/test_approval_boundaries.py` and `rg` checks from Plan 13-07. | Removed with `src/repositories/approval_repo.py`. | Complete. |
| `ApprovalStep` | Trace fallback only | No target transition/event writes. | Approval event tests and architecture boundary tests verify new `approval_events` path. | Compatibility read fallback remains for current `/trace` timeline only. | Phase 15 replay migration owns event-store-first read switch and fallback retirement. |
| v1 approval tests | Plan 13-07 | Cannot assert v1 idempotent approve/reject as target truth. | `tests/test_approval_models.py`, `tests/test_execute_action.py`, `tests/test_graph_routing.py`. | Rewritten around `ApprovalService`, v2 revision/version fields, exact hash/snapshot bindings, and legacy_v1 fail-closed behavior. | Complete. |

## Migration / Read-Switch / Rollback

| Field | Value |
| --- | --- |
| Alembic head before Phase 13 migration | `008_approval_state_machine` |
| Alembic current before Phase 13 migration | `005_approval_tables` |
| Alembic current after Phase 13 migration | `008_approval_state_machine` |
| Legacy v1 rows in local execution | `0` |
| Legacy non-executable rows in local execution | `0` |
| Legacy backfill disposition | Migration 008 uses deterministic `row_number()` per `(tenant_id, run_id)` and sets `legacy_non_executable=true` before revision uniqueness. |
| Read-switch owner | `src/approvals/repository.py` |
| Fallback behavior | Legacy v1 rows are display/reject/cancel/expire/supersede only and cannot authorize action until revalidated into v2. |
| Rollback command | `uv run alembic downgrade 007_session_memories` |
| Rollback note | Rollback is allowed only when no v2 approvals were authorized; otherwise v2 rows remain non-executable until resolved. |

## Verification Command Statuses

| Command | Status | Last observed | Notes |
| --- | --- | --- | --- |
| `uv run alembic upgrade head` | PASS | 2026-06-15 | Alembic reported PostgreSQL context and transactional DDL; no migration failure. |
| `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/test_approval_models.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_events.py -q --tb=short` | PASS | 2026-06-15 | 201 passed, 1 existing LangGraph pending-deprecation warning. |
| `uv run pytest -q --tb=short` | FAIL | 2026-06-15 | 13 failed, 731 passed, 1 existing LangGraph pending-deprecation warning. |
| `uv run ruff check src tests` | PASS | 2026-06-15 | All checks passed. |

## Blocking Follow-Ups

Blocking follow-up row present because the full-suite verification command failed.

| ID | Owner | Command | Impact | Status |
| --- | --- | --- | --- | --- |
| P13-BLOCK-FULL-PYTEST | Phase 13 | `uv run pytest -q --tb=short` | `phase_13_not_ready_for_execution`; Phase 13 cannot claim final readiness while full-suite failures remain. Failing tests: `tests/agent/test_nodes/test_assess_risk_and_approval.py::test_actionable_recommendation_still_proposes_action`, `tests/agent/test_nodes/test_assess_risk_and_approval.py::test_chinese_full_refund_delivered_order_matches_high_risk`, `tests/agent/test_nodes/test_assess_risk_and_approval.py::test_expected_error_retries_then_falls_back`, `tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required`, `tests/test_agent_runs_api.py::test_sse_interrupted_path_skips_memory_write`, `tests/test_interception_rate.py::test_hr01_compensation_over_500_requires_approval`, `tests/test_interception_rate.py::test_hr02_full_refund_on_delivered_order_requires_approval`, `tests/test_interception_rate.py::test_hr03_high_risk_merchant_requires_approval`, `tests/test_interception_rate.py::test_live_freeform_rejection_action_type_is_canonical`, `tests/test_interception_rate.py::test_route_after_risk_returns_approval_gate_for_all_high_risk_rules`, `tests/test_interception_rate.py::test_interception_rate_100_percent`, `tests/test_trace_api.py::test_get_run_trace_returns_full_timeline_with_agent_steps_approvals_and_action_drafts`, `tests/test_trace_api.py::test_get_run_trace_timeline_is_sorted_by_time`. | OPEN |
