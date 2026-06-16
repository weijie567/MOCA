# Phase 15 Replay Event Contract Coverage

**Phase:** 15-replay-event-contract  
**Plan status:** 15-06 Task 2 coverage baseline created; final gate statuses updated by 15-06 Task 3.  
**Status vocabulary:** `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `PASS`, `FAIL`, `NOT_RUN`.

## Requirement Coverage

| Requirement | Status | Owning plans | Implementation artifacts | Primary tests and commands | Notes |
| --- | --- | --- | --- | --- | --- |
| REPLAY-01: ReplayEventV3 and lifecycle finalizer cover required completed/interrupted/terminal paths | COVERED | 15-01, 15-03, 15-04, 15-05, 15-06 | `src/replay/schemas.py`, `src/replay/service.py`, `src/replay/lifecycle.py`, `src/api/routers/traces.py`, `src/actions/service.py` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py tests/replay/test_operation_pairing.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py -q --tb=short` | Native V3 rows, minimal-row provenance, lifecycle events, event-store-first `/replay`, and demo draft replay safety are covered. |
| REPLAY-02: Shared per-run sequence allocator and operation pairing/retry contracts are enforced | COVERED | 15-01, 15-02, 15-03, 15-04 | `src/replay/service.py`, `src/replay/pairing.py`, `src/agent/events.py`, `src/replay/lifecycle.py`, `src/db/models.py` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_sequence_allocator.py tests/replay/test_operation_pairing.py tests/agent/test_events.py -q --tb=short` | Advisory-lock plus `max(sequence)+1` remains the shared allocator. Phase 17 owns external worker allocator tests. |
| REPLAY-03: Replay redaction, retention, access control, read-switch, fallback, and rollback are defined | COVERED | 15-01, 15-02, 15-05, 15-06 | `src/replay/validators.py`, `src/replay/service.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/actions/service.py` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_replay_api.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | Redaction guard rejects unsafe keys; `/replay` omits raw action payloads; `/trace` remains rollback fallback. |

## Source Decision Coverage

| Source | Decision or requirement | Status | Evidence |
| --- | --- | --- | --- |
| 15-CONTEXT D-01 | Complete ReplayEventV3 MVP, not API-only stage | COVERED | Plans 15-01 through 15-06 cover schema, service, pairing, lifecycle, API, safety, and coverage. |
| 15-CONTEXT D-02/D-03 | Physical V3 column expansion with explicit schema/index/check work | COVERED | `src/db/models.py`, `src/db/migrations/versions/010_replay_event_v3.py`, `tests/replay/test_replay_migration_contract.py`. |
| 15-CONTEXT D-04 | Keep advisory-lock plus `max(sequence)+1` behind replay service | COVERED | `ReplayService.allocate_sequence()` and `tests/replay/test_sequence_allocator.py`. |
| 15-CONTEXT D-05 | `RunLifecycleService` owns lifecycle replay events | COVERED | `src/replay/lifecycle.py`, `src/agent/trace.py`, `tests/replay/test_lifecycle_finalizer.py`. |
| 15-CONTEXT D-06 | Active SLA scanner remains disabled in Phase 15 | DEFERRED_WITH_OWNER | `tests/approvals/test_sla_scanner.py`; owner is post-Phase 15 SLA Scanner Enablement phase. |
| 15-CONTEXT D-07/D-08 | Strict operation pairing and unresolved historical rows | COVERED | `src/replay/pairing.py`, `ReplayService.project_event()`, `tests/replay/test_operation_pairing.py`, `tests/replay/test_replay_service.py`. |
| 15-CONTEXT D-09/D-10 | Add V3 `/replay`, preserve `/trace`, and project V3-shaped entries only | COVERED | `src/api/routers/traces.py`, `ReplayService.get_replay()`, `tests/replay/test_replay_api.py`, `tests/test_trace_api.py`. |
| 15-CONTEXT D-11 | Phase 14 compatibility cleanup for replay-facing demo draft wording | COVERED | `src/actions/service.py`, `tests/replay/test_replay_redaction_retention.py`, `tests/replay/test_replay_api.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`. |
| 15-VALIDATION T-15-01..T-15-15 | Required Nyquist validation surfaces | COVERED | All planned test surfaces exist; final four command statuses are tracked below. |

## Deferred Owners

| Deferred item | Status | Owner | Acceptance gate |
| --- | --- | --- | --- |
| Active SLA scanner enablement and scheduling | DEFERRED_WITH_OWNER | post-Phase 15 SLA Scanner Enablement phase | Enablement plan must prove scanner lifecycle event emission, allocator sharing, default config safety, and no premature approval expiry side effects. |
| Long-term/case memory identity, tombstones, memory review workflow, and distinct retrieval predicates | DEFERRED_WITH_OWNER | Phase 16 | Phase 16 must implement `memory_identity.v1`, tombstone no-retrieval/no-rewrite behavior, and reviewed long-term/case memory flows without weakening Phase 12 session-memory fallback. |
| External execution tables and rows | DEFERRED_WITH_OWNER | Phase 17 | Phase 17 must create action execution storage only after transactional draft claim and committed outbox ownership are defined. |
| External execution outbox, dispatcher, external worker allocator tests, reconciliation, compensation, and `action_execution_*` event families | DEFERRED_WITH_OWNER | Phase 17 | Phase 17 must prove duplicate execution/key guards, unknown/reconciling retry safety, compensation authorization, and external worker sequence allocation. |

## Compatibility Disposition

| Surface | Status | Disposition |
| --- | --- | --- |
| `/api/v1/agent-runs/{run_id}/trace` | COVERED | `/trace` remains the legacy rollback fallback. It continues to use `TraceRepository.build_timeline()` and existing trace API tests remain part of final verification. |
| `TraceRepository.build_timeline()` | COVERED | Kept for rollback/debug composition only; `/replay` uses `ReplayService.get_replay()` and `agent_trace_events` ordered by `sequence`. |
| `src.agent.events.emit_event()` | COVERED | Kept as minimal envelope compatibility wrapper; delegates allocation and append to `ReplayService`. |
| `action_result` compatibility field | COVERED | Kept as a non-success draft compatibility payload with `status="draft_created"`; replay-facing evidence uses `draft_outcome.status="not_executed_demo"` and `external_side_effect=false`. |
| `execute_action` compatibility wording | COVERED | Not expanded by Phase 15; replay-facing demo draft events remain `action_draft_created` and do not imply external dispatch. |
| `action_execution_*`, external outbox, reconciliation, compensation | DEFERRED_WITH_OWNER | Not implemented in Phase 15; owner is Phase 17. |

## Verification Command Status

### Completed Plan Commands

| Command | Status | Source |
| --- | --- | --- |
| `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | PASS | 15-01 summary; live schema upgraded to head. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py -q --tb=short` | PASS | 15-01 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_redaction_retention.py -q --tb=short` | PASS | 15-02 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_sequence_allocator.py -q --tb=short` | PASS | 15-02 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q --tb=short` | PASS | 15-03 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py tests/replay/test_sequence_allocator.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py -q --tb=short` | PASS | 15-04 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/replay/test_replay_service.py tests/test_trace_api.py -q --tb=short` | PASS | 15-05 summary. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_replay_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | PASS | 15-06 Task 1. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/repositories/trace_repo.py tests/replay tests/agent/test_tools/test_create_coupon_grant_draft.py` | PASS | 15-06 Task 1. |

### Final Phase 15 Gate Commands

| Command | Status | Result detail |
| --- | --- | --- |
| `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | NOT_RUN | Pending 15-06 Task 3 final gate. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py tests/approvals/test_events.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | NOT_RUN | Pending 15-06 Task 3 final gate. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | NOT_RUN | Pending 15-06 Task 3 final gate. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` | NOT_RUN | Pending 15-06 Task 3 final gate. |

## Readiness Rule

Phase 15 is not ready until every final gate command above is updated to `PASS`, or any `FAIL`/`NOT_RUN` row is paired with a `Blocking follow-up` row naming the owner and exact command.
