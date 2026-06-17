# Phase 15: Replay Event Contract - Research

**Researched:** 2026-06-16
**Status:** Ready for planning
**Phase:** 15 - Replay Event Contract
**Requirements:** REPLAY-01, REPLAY-02, REPLAY-03

## Executive Summary

Phase 15 should turn the Phase 10 minimal event foundation into the first-class V3 replay service. The current code already has `agent_trace_events`, a minimal `AgentTraceEvent` ORM model, event registration, redaction guard, and per-run sequence allocation helpers. It also has Phase 12 memory events, Phase 13 approval events, and Phase 14 `action_draft_created` events using the same minimal envelope.

The current implementation is still not ReplayEventV3. Missing pieces include V3 columns and indexes, `replay_event.v3` schema handling, `parent_operation_id`, `attempt`, `node_name`, error payloads, retention lifecycle columns, operation pairing validation, consolidated event registry validation, a `ReplayService`, a `/replay` route, lifecycle finalizer coverage for non-happy paths, event-store-first reads, and a rollback-safe `/trace` fallback.

Planning should prefer a small number of cohesive service/schema slices over scattering replay logic through routers. Phase 15 should not create Phase 17 external execution/outbox/reconciliation behavior, and it must not let replay become business truth. Replay records what happened, with safe refs and redacted summaries only.

## Current Implementation Inventory

### Minimal Event Foundation Exists

- `src/db/models.py` defines `AgentTraceEvent` as a Phase 10 minimal envelope with `event_id`, `run_id`, `sequence`, `operation_id`, `tenant_id`, `thread_id`, `trace_id`, `event_type`, `schema_version`, `occurred_at`, `actor`, `resource_refs`, `redaction_policy_version`, and `redacted_payload`.
- `src/db/migrations/versions/006_agent_trace_events.py` creates the base table and `uq_agent_trace_events_run_seq`.
- `src/agent/events.py` provides:
  - `MINIMAL_EVENT_TYPES` including node, tool, RAG, LLM, memory, approval, and `action_draft_created` minimal events.
  - `classify_event_family()` for tool vs RAG event families.
  - `allocate_sequence()` using a PostgreSQL advisory transaction lock plus `max(sequence)+1`.
  - `emit_event()` with deterministic `uuid5(run_id:sequence)` event ids.
  - `_guard_redacted_payload()` rejecting raw/prompt/secret/PII-like keys.
- `tests/agent/test_events.py` covers monotonic sequence, resume continuation, duplicate `(run_id, sequence)` DB backstop, event family classification, iteration in `redacted_payload`, event registration, and redaction guard.

### Domain Event Emitters Exist

- `src/agent/nodes/investigate.py` emits `tool_call_*` and `rag_retrieval_*` events with independent `operation_id` and `redacted_payload.iteration`.
- `src/agent/nodes/memory_write.py` emits `memory_write_started/completed/failed` events where a run/session is present.
- `src/approvals/events.py` emits `approval_requested`, `approval_decided`, `approval_expired`, and `approval_resumed`, writes an `ApprovalEvent`, and links `approval_events.replay_event_id` to `agent_trace_events.event_id`.
- `src/actions/service.py` emits `action_draft_created` after durable demo draft creation.
- `tests/approvals/test_events.py`, `tests/approvals/test_needs_info_resume.py`, `tests/approvals/test_sla_scanner.py`, and `tests/agent/test_tools/test_create_coupon_grant_draft.py` prove key minimal event shapes and safety boundaries.

### Current Trace API Is Legacy Composition

- `src/repositories/trace_repo.py` builds a timeline from `AgentStep`, `ApprovalRequest`, `ApprovalStep`, and `ActionDraft`, sorting by time.
- `src/api/routers/traces.py` exposes `GET /api/v1/agent-runs/{run_id}/trace`, enforces same-tenant lookup and owner/supervisor access, and returns the legacy composed trace/debug view.
- `tests/test_trace_api.py` verifies `/trace` timeline composition, sorting, access control, cross-tenant 404, and redaction of raw action payload/final response/input query.

### Current Gaps

- No `GET /api/v1/agent-runs/{run_id}/replay` route exists.
- `AgentTraceEvent` lacks V3 target fields/shape: `parent_operation_id`, `attempt`, `version`, `node_name`, typed FK columns such as `approval_id`/`draft_id`/`execution_id`, `tool_call_id`, `evidence_refs_json`, `error_json`, `archived_at`, `retention_until`, and `deleted_at`.
- The migration has only `ix_agent_trace_events_run_id` and `ix_agent_trace_events_tenant_id`, not the contract indexes `(tenant_id, run_id, sequence)`, `(tenant_id, run_id, operation_id)`, `(tenant_id, occurred_at)`, or `(event_type, occurred_at)`.
- `emit_event()` validates only minimal event registration, not full V3 enum, V3 field requirements, operation pairing, terminal uniqueness, or retry parent/attempt rules.
- There is no `RunLifecycleService`/finalizer. `trace_close` is a target node/contract concept, but current persistence is still API/router and graph-tail dependent.
- There is no event-store-first replay read model. `/trace` still composes legacy rows and does not read `agent_trace_events` first.
- Current sequence allocation is service-local to `src/agent/events.py`; Phase 15 should centralize it behind replay/trace-event service boundaries and add concurrent writer tests across graph, approval, demo action draft, replay/backfill, and SLA if enabled.

## Contract Targets

### REPLAY-01: ReplayEventV3 and Lifecycle Finalizer

Phase 15 must implement `replay_event.v3` on top of the Phase 10 minimal envelope. The replay timeline must cover normal, interrupted, resumed, responded, rejected, expired, error, and cancelled paths. The finalizer must cover non-happy paths that do not reach a normal graph tail. Approval `respond` remains an interrupted lifecycle exception and must not be represented as completed.

Required target behavior:

- Every replay response uses `schema_version: replay_response.v3`.
- Every event exposed through `/replay` uses V3 fields and safe JSON shape.
- Normal runs include running status, node/tool/RAG/LLM events, final response node, memory write where applicable, and completed terminal status.
- Interrupted approval runs include pre-interrupt events, `approval_requested`, and `run_status_changed: interrupted`.
- Resumed runs include `approval_decided` or `approval_resumed`, post-resume node/action events, and terminal status.
- Responded runs include `approval_decided`, clarification refs, and interrupted status, not a fabricated completed status.
- Rejected/expired/cancelled/error runs include corresponding lifecycle/terminal events and partial timeline.
- Demo draft runs include `action_draft_created` and never `action_execution_*`.

### REPLAY-02: Shared Allocator and Operation Pairing

The per-run sequence contract must be shared by all Phase 15-available writers: graph/tool/RAG/memory, approval/API, demo action draft, replay/backfill, and SLA finalizer only if enabled. Phase 17 external worker concurrency is deferred with owner Phase 17.

Operation contract:

- Operation events have positive `attempt`.
- Started and terminal events share `operation_id`.
- Each operation gets exactly one terminal event among completed/failed/unknown where applicable.
- Retry creates a new `operation_id`, uses `parent_operation_id` to link to the prior attempt or common parent, and increments `attempt`.
- Bounded investigate loop tool/RAG child operations include `iteration` in `redacted_payload`.
- Backfill must mark unresolved pairings with `pairing_status=unresolved`; it must not invent completed pairs.

### REPLAY-03: Redaction, Retention, Access, Read-Switch, Fallback, Rollback

The replay service must reject raw prompt/tool/action/secret/PII payloads, expose only safe refs and summaries, and define retention fields/rules for replay events. `/replay` must enforce `/trace`-equivalent or stricter access: cross-tenant 404, non-owner non-supervisor 403.

Read-switch and fallback:

- `/replay` reads `agent_trace_events` V3/event-store data first.
- Legacy `TraceRepository.build_timeline()` remains a fallback/read model during migration and remains available through `/trace`.
- `/trace` should remain the rollback fallback and must not be broken by Phase 15.
- Any read-switch config/owner/rollback behavior must be explicit in the plan.

## Phase Boundaries and Non-Overlap

- Phase 10 owns the minimal event envelope, base table, initial event registry, and base allocator foundation. Phase 15 may harden/refactor these into the full replay service, but should not claim Phase 10 failed because V3 enrichment was intentionally deferred.
- Phase 12 owns session memory correctness and memory-write minimal events. Phase 15 consumes memory events and must not turn memory into replay truth, policy evidence, or action authority.
- Phase 13 owns approval state, snapshot/hash contracts, approval event additions, and feature-disabled SLA scanner. Phase 15 owns replay enrichment, lifecycle finalizer, scanner enablement gate, and allocator coverage if the scanner is enabled.
- Phase 14 owns durable demo action drafts and `action_draft_created`. Phase 15 consumes demo draft events and may remove/replace deprecated replay-facing compatibility surfaces such as `execute_action`/`action_result` wording if planning finds they block replay clarity.
- Phase 16 owns long-term/case memory, `memory_identity.v1`, tombstones, and review workflow. Phase 15 must not implement these.
- Phase 17 owns external action execution, outbox, reconciliation, compensation, `action_execution_*`, and external worker allocator tests. Phase 15 may keep V3 enum compatibility/deferred notes, but must not create external side effects or external execution tables.

## Schema and Migration Implications

Phase 15 is schema-relevant and must include a blocking Alembic migration/push verification task.

Expected migration work:

- Extend `agent_trace_events` with V3 columns: `parent_operation_id`, `attempt`, `version`, `node_name`, `approval_id`, `draft_id`, nullable future `execution_id` only if a referenced table already exists or explicitly deferred, `tool_call_id`, `evidence_refs_json`, `error_json`, `archived_at`, `retention_until`, and `deleted_at`.
- Decide whether to keep current `actor` and `resource_refs` JSON names or migrate/add contract names `actor_type`/`actor_id` and typed resource columns. If the plan chooses compatibility projection instead of physical rename, it must state exact service projection rules.
- Add/check `schema_version in ('minimal_event_envelope.v1','replay_event.v3')`.
- Add/check `sequence > 0` and `attempt is null or attempt > 0`.
- Add indexes: `(tenant_id, run_id, sequence)`, `(tenant_id, run_id, operation_id)`, `(tenant_id, occurred_at)`, and `(event_type, occurred_at)`.
- Preserve existing rows as `minimal_event_envelope.v1`; do not backwrite old rows to pretend full V3 facts exist.
- Add stable backfill/enrichment behavior for legacy rows with unresolved pairing metadata where pairing cannot be proven.
- Keep nullable FKs where early node/tool events do not have approval/action resources.

Schema push requirement:

- ORM/migration patterns are Alembic/SQLAlchemy under `src/db/models.py` and `src/db/migrations/versions/*.py`.
- The plan must include a `[BLOCKING]` schema task that runs Alembic upgrade verification before API/service verification.
- Existing project commands use `uv run alembic` and `uv run pytest`; the exact push/verification command should be `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` when a live DB is available, plus migration contract tests.

## Recommended Plan Slices

1. **V3 Schema and Replay Models**
   - Extend ORM/migration and add schema/contract tests for V3 columns, indexes, checks, and compatibility with existing minimal rows.
   - Add Pydantic schemas for `ReplayEventV3` and `ReplayResponseV3`.

2. **Replay/Trace Event Service and Registry Validation**
   - Introduce `ReplayService` or `TraceEventService` as owner of append/read, event registry validation, sequence allocation, operation pairing validation, redaction, retention metadata, and V3 projection.
   - Keep thin wrappers/compat imports for existing `emit_event()` only if needed, with new writes routed through the service.

3. **Lifecycle Finalizer**
   - Add `RunLifecycleService`/finalizer for running/interrupted/completed/error/cancelled/expired lifecycle events.
   - Wire API/graph/approval resume paths where current code updates `AgentRun` but lacks replay lifecycle closure.
   - Keep SLA scanner disabled unless the plan includes replay/allocator gates and explicit enablement tests.

4. **Operation Pairing, Retry, and Backfill**
   - Validate started/terminal pairs, terminal uniqueness, retry parent/attempt, iteration, and unresolved historical pairing markers.
   - Cover concurrent allocator cases across Phase 15-available writers.

5. **Replay API and Read-Switch**
   - Add `GET /api/v1/agent-runs/{run_id}/replay`.
   - Reuse `/trace` access-control behavior or make it stricter.
   - Implement event-store-first replay reads, stable sequence ordering, and legacy fallback.
   - Preserve `/trace` as rollback fallback.

6. **Redaction, Retention, and Boundary Cleanup**
   - Add redaction/retention tests for every newly accepted event type and V3 projection.
   - Verify no raw prompt/tool/action payload or PII appears in replay responses.
   - Close Phase 14 replay-facing compatibility gates only if necessary and explicitly scoped.

## Validation Architecture

Phase 15 validation should be treated as blocking contract validation, not only API snapshot tests.

### Lifecycle Timeline Matrix

Required tests:

- Normal completed run returns V3 replay with running -> node/tool/RAG/LLM/memory/action-draft where applicable -> completed.
- Interrupted approval run returns approval request and interrupted status.
- Resumed accepted/approved run returns approval decision/resume, action draft, and completed or error terminal status.
- Responded/needs_info run returns approval decision with clarification refs and interrupted status, no completed fabrication.
- Rejected run returns rejection decision and terminal safe final response/final status.
- Expired run returns approval_expired and terminal/interrupted status according to lifecycle rule.
- Error run returns partial timeline plus safe error payload.
- Cancelled run returns partial timeline plus cancelled terminal status.

### Sequence and Concurrency

Required tests:

- Graph/tool writer, approval event writer, action draft writer, replay/backfill writer, and optionally SLA writer allocate strictly increasing sequences for the same run.
- Concurrent allocation produces no duplicate `(run_id, sequence)` and no manual reorder/hole-filling behavior.
- Unique-conflict retry path is tested or a locked counter model makes conflict unreachable and is covered with transaction tests.
- Resume continues sequence after existing rows.

### Operation Pairing and Retry

Required tests:

- Tool/RAG/LLM/memory operation started -> terminal pairs share `operation_id`.
- Operation with no terminal event is flagged by validator.
- Operation with two terminal events is rejected.
- Retry uses new `operation_id`, positive incremented `attempt`, and valid `parent_operation_id`.
- Bounded investigate loop includes multiple child tool/RAG events with `redacted_payload.iteration`.
- Unresolved backfill rows are exposed with `pairing_status=unresolved` instead of invented pairs.

### Redaction and Retention

Required tests:

- V3 append/projection rejects raw prompt, raw args, raw payload, raw tool output, secret, credentials, and PII-heavy keys.
- Replay responses omit `input_query`, full `final_response`, raw `ActionDraft.payload`, full tool responses, and hidden prompt/internal reasoning.
- Retention fields/indexes exist and retention summary can preserve run_id, terminal status, event count, first/last occurred_at, and redaction policy version.

### Replay API and Fallback

Required tests:

- `/api/v1/agent-runs/{run_id}/replay` returns `schema_version=replay_response.v3` and `timeline` sorted by sequence.
- Cross-tenant run returns 404.
- Same-tenant non-owner non-supervisor returns 403.
- Owner/supervisor/admin can read according to `/trace` rules.
- `/trace` still passes existing tests and remains rollback fallback.
- Event-store-first read is observable in tests by creating V3 events and verifying `/replay` does not depend on legacy `AgentStep` composition.

### Verification Commands

Planner should require focused tests before broad gates:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/test_trace_api.py tests/approvals/test_events.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests
```

Phase 15-specific tests should be added under focused paths such as:

- `tests/replay/test_replay_service.py`
- `tests/replay/test_replay_api.py`
- `tests/replay/test_lifecycle_finalizer.py`
- `tests/replay/test_operation_pairing.py`
- `tests/replay/test_replay_migration_contract.py`
- `tests/replay/test_replay_redaction_retention.py`

## Risks and Planner Constraints

- Do not let Phase 15 fabricate actor/resource refs or raw lifecycle semantics for Phase 10-14 events. If facts are missing, mark unresolved/deferred with owner and gate.
- Do not silently change `docs/contract-spec.md` semantics. If planning discovers the spec is wrong, route through spec revision and review; otherwise record MVP scope/deviations explicitly.
- Do not remove `/trace` compatibility while `/replay` is being introduced. `/trace` is the rollback fallback.
- Do not introduce `action_execution_*` events or external action tables before Phase 17.
- Do not enable active SLA scanning without replay/lifecycle/allocator gates. If not enabled, include a disabled-by-default verification.
- Do not store raw prompt, raw tool args/output, raw action payload, secrets, credentials, or unredacted PII in replay payloads.
- Do not turn Redis/memory into replay truth. PostgreSQL event rows are authoritative for replay.
- Plans must include concrete `<read_first>` and grep/test-verifiable acceptance criteria; avoid vague "align with spec" language.

## Source Anchors

- `.planning/ROADMAP.md` Phase 15 - goal, dependencies, mandatory architecture input, REPLAY-01..03, success criteria.
- `.planning/REQUIREMENTS.md` - REPLAY-01, REPLAY-02, REPLAY-03 and planning requirements.
- `.planning/STATE.md` - Phase 15 active focus and Phase 13/14 handoff notes.
- `docs/phase-13-17-architecture-plan.md` Phase 15 section - target service, required restructure, deletion/quarantine, gate tests.
- `docs/contract-spec.md` Section 17.2 - minimal envelope, full ReplayEventV3, bounded-loop pairing, event coverage, allocator, redaction.
- `docs/contract-spec.md` Section 17.6 - `/replay` API response, ordering/completeness, access control.
- `docs/contract-spec.md` Section 17.7 - redaction and retention.
- `docs/contract-spec.md` Section 18.4 `agent_trace_events` - target schema, constraints, indexes, transition strategy.
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` - Phase 10 event classification, iteration, and bounded loop guardrails.
- `.planning/phases/12-session-memory/12-CONTEXT.md` - memory ownership and replay deferral to Phase 15.
- `.planning/phases/13-approval-state-machine/13-CONTEXT.md` - approval events, replay FK, SLA scanner gate, and Phase 15 deferrals.
- `.planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md` and `14-07-SUMMARY.md` - demo draft event surface and Phase 15/17 non-overlap.
- `src/db/models.py` - current `AgentTraceEvent`, `ApprovalEvent.replay_event_id`, and action draft fields.
- `src/db/migrations/versions/006_agent_trace_events.py` - minimal table migration.
- `src/agent/events.py` - current event registry, sequence allocator, redaction guard, append helper.
- `src/repositories/trace_repo.py` and `src/api/routers/traces.py` - current `/trace` legacy composition and access control.
- `src/approvals/events.py` - approval event helper and replay_event_id linkage.
- `src/actions/service.py` - `action_draft_created` event writer.
- `src/agent/nodes/investigate.py` and `src/agent/nodes/memory_write.py` - tool/RAG and memory event emitters.
- `tests/agent/test_events.py`, `tests/test_trace_api.py`, `tests/approvals/test_events.py`, `tests/approvals/test_sla_scanner.py`, and `tests/agent/test_tools/test_create_coupon_grant_draft.py` - existing focused test patterns.
