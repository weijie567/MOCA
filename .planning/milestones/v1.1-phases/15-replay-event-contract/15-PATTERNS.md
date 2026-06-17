# Phase 15: Replay Event Contract - Pattern Map

**Generated:** 2026-06-16
**Scope:** Planning-only map for Phase 15 implementation.

## Target File Map

| Target | Role | Closest Analog | Pattern to Reuse |
|--------|------|----------------|------------------|
| `src/db/models.py` | Extend `AgentTraceEvent` to V3-compatible ORM shape | Existing `AgentTraceEvent`, `ActionDraft`, approval lifecycle models | SQLAlchemy `Mapped[...] = mapped_column(...)`, nullable migration-safe columns, `TimestampMixin`, explicit indexes/unique constraints |
| `src/db/migrations/versions/010_replay_event_v3.py` | Alembic expand migration | `006_agent_trace_events.py`, `009_action_draft_v2.py`, `008_approval_state_machine.py` | `op.add_column`, `op.create_index`, server defaults only where needed, old rows remain compatible |
| `src/replay/schemas.py` | Pydantic schemas for `ReplayEventV3` and `ReplayResponseV3` | `src/actions/schemas.py`, `src/approvals/schemas.py` | Versioned schemas, typed literals where stable, `model_dump(mode=\"json\")` in API responses |
| `src/replay/service.py` or `src/replay/events.py` | Replay append/read/validate owner | `src/agent/events.py`, `src/approvals/events.py`, `src/actions/service.py` | Thin API boundaries call domain service; service owns validation, redaction, sequence allocation, and DB writes |
| `src/replay/lifecycle.py` | Run lifecycle finalizer | `src/agent/trace.py`, approval resume lifecycle in `src/api/routers/approvals.py` | Centralize `AgentRun` status update plus replay lifecycle event append; routers stay thin |
| `src/repositories/trace_repo.py` | Legacy `/trace` fallback and optional event-store read helper | Existing `TraceRepository.build_timeline` | Keep legacy composition isolated; do not make it V3 truth |
| `src/api/routers/traces.py` | Add `/replay`, preserve `/trace` | Existing `/trace` route | Same tenant lookup, owner/supervisor role gate, cross-tenant 404, `ApiResponse` envelope |
| `tests/replay/*.py` | Phase 15 contract tests | `tests/agent/test_events.py`, `tests/test_trace_api.py`, `tests/approvals/test_events.py` | DB-backed async tests, focused helper factories, assert exact JSON keys and status codes |

## Existing Code Patterns

### Event Append and Redaction

Source: `src/agent/events.py`

- Event types are registered in a single set before emit.
- `emit_event()` rejects unregistered event types before writing.
- Redaction guard recursively rejects unsafe keys such as raw payloads, prompt, secrets, credentials, and PII.
- Current sequence allocation uses a PostgreSQL advisory transaction lock on run id plus `max(sequence)+1`.
- Current event ids are deterministic `uuid5(namespace, f\"{run_uuid}:{sequence}\")`.

Phase 15 pattern:

- Move or wrap this behind `ReplayService`/`TraceEventService` without bypassing existing emitters.
- Add V3 validation before persistence or projection.
- Preserve safe redaction failure semantics with tests.
- Add operation pairing validator as service-owned logic, not router logic.

### Approval Event Linkage

Source: `src/approvals/events.py`

- Approval helpers build safe metadata/resource refs/redacted payload.
- Approval helper calls `emit_event()`, then writes/updates `ApprovalEvent.replay_event_id`.
- Revision refs are required for edit/respond or hash/config-changing decisions.

Phase 15 pattern:

- Consume existing `approval_events.replay_event_id` instead of re-inferring approval semantics.
- Do not fabricate actor/resource refs for older rows.
- Keep unresolved historical pairing/refs explicit in `redacted_payload`.

### Demo Action Event Surface

Source: `src/actions/service.py`, tests under `tests/agent/test_tools/test_create_coupon_grant_draft.py`

- Action draft event uses safe refs only: `draft_id`, `target_id`, `action_payload_hash`, `safety_snapshot_hash`.
- Redacted payload carries `action_type`, `execution_mode=\"demo\"`, `external_side_effect=false`.
- No `action_execution_*` events are registered in Phase 14.

Phase 15 pattern:

- Replay API can expose demo draft events, but must not imply external execution.
- External execution event families remain Phase 17.

### Trace API Access Control

Source: `src/api/routers/traces.py`, `tests/test_trace_api.py`

- `repo.get_run(run_uuid, user.tenant_id)` gives cross-tenant 404 behavior.
- Same-tenant non-owner non-supervisor returns 403.
- Supervisor roles are `supervisor`, `admin`, `approval_manager`, `manager`.
- Response uses `ApiResponse(success=True, data=..., trace_id=...)`.

Phase 15 pattern:

- `/replay` should use the same or stricter access gate.
- Keep `/trace` behavior passing as rollback fallback.

### Legacy Timeline Composition

Source: `src/repositories/trace_repo.py`

- `build_timeline()` composes `AgentStep`, `ApprovalRequest`, `ApprovalStep`, and `ActionDraft`, then sorts by timestamp.
- It projects safe action draft outcome through `_safe_draft_outcome()`.
- It omits raw `ActionDraft.payload` and full response/input text.

Phase 15 pattern:

- Keep `build_timeline()` as legacy fallback only.
- Add event-store-first V3 projection in a separate replay service.
- Do not mix V3 operation pairing rules into the legacy timeline builder.

### Alembic and ORM

Sources: `006_agent_trace_events.py`, `008_approval_state_machine.py`, `009_action_draft_v2.py`, `src/db/models.py`

- Migrations use `op.create_table`, `op.add_column`, `op.create_index`, and PostgreSQL UUID/JSONB types.
- Existing action/approval migrations add nullable fields and preserve old rows.
- Current `agent_trace_events` has only basic run/tenant indexes and unique `(run_id, sequence)`.

Phase 15 pattern:

- Use an expand migration that preserves `minimal_event_envelope.v1` rows.
- Add V3 columns nullable where old rows cannot supply facts.
- Add contract indexes and checks.
- Include an explicit blocking Alembic upgrade verification task in the plan.

### Test Organization

Sources:

- `tests/agent/test_events.py`
- `tests/test_trace_api.py`
- `tests/approvals/test_events.py`
- `tests/approvals/test_sla_scanner.py`
- `tests/agent/test_tools/test_create_coupon_grant_draft.py`

Patterns:

- Use async DB fixtures with `AsyncSession`.
- Create `AgentRun` rows via `write_agent_run()` before event rows.
- Assert exact event payload/resource-ref keys.
- Assert route responses with status code plus response JSON code.
- Keep focused contract tests near the owning domain.

Recommended Phase 15 test paths:

- `tests/replay/test_replay_migration_contract.py`
- `tests/replay/test_replay_service.py`
- `tests/replay/test_lifecycle_finalizer.py`
- `tests/replay/test_sequence_allocator.py`
- `tests/replay/test_operation_pairing.py`
- `tests/replay/test_replay_redaction_retention.py`
- `tests/replay/test_replay_api.py`

## Data Flow Pattern

1. Writers call replay/event service append helpers.
2. Append helper validates event type, redaction, V3 field requirements, and sequence allocation.
3. DB stores append-only `agent_trace_events` rows.
4. Replay service reads event-store rows ordered by `(sequence asc)`.
5. Replay service projects `ReplayResponseV3`.
6. `/replay` enforces access and returns V3 response.
7. `/trace` remains legacy fallback and compatibility view.

## Anti-Patterns to Avoid

- Adding replay-specific logic directly in API routers.
- Reconstructing V3 timelines from `AgentStep.metrics_json` as the primary source.
- Backfilling old rows by inventing operation pairs or actor/resource refs.
- Adding Phase 17 `action_execution_*` events or tables.
- Returning raw prompt, raw tool args/output, raw `ActionDraft.payload`, full final response, secrets, credentials, or PII in replay responses.
- Letting `/trace` break while `/replay` is introduced.

## Verification Command Patterns

Focused:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short
```

Migration:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head
```

Lint:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests
```
