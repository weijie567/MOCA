---
phase: 15-replay-event-contract
verified: 2026-06-16T16:51:01Z
status: passed
score: "26/26 must-haves verified"
overrides_applied: 0
deferred:
  - truth: "External execution/outbox/reconciliation/compensation and action_execution_* event families remain outside Phase 15."
    addressed_in: "Phase 17"
    evidence: "ROADMAP.md Phase 17 goal: external action execution with transactional claim/outbox, reconciliation, and compensation; 15-COVERAGE.md records these as DEFERRED_WITH_OWNER: Phase 17."
---

# Phase 15: Replay Event Contract Verification Report

**Phase Goal:** Implement ReplayEventV3, run lifecycle finalizer, shared sequence allocator, redaction/retention, and replay read-switch.
**Verified:** 2026-06-16T16:51:01Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines are complete. | VERIFIED | `RunLifecycleService` exposes all status appenders in `src/replay/lifecycle.py`; `tests/replay/test_lifecycle_finalizer.py` covers normal, interrupted, resumed, responded-without-completed, rejected, expired, error, and cancelled paths. |
| 2 | Sequence and operation pairing contracts pass under concurrent writers and retries. | VERIFIED | `ReplayService.append_event()` takes `pg_advisory_xact_lock`, reads prior ordered events, validates pairing, then allocates `MAX(sequence)+1`; tests cover concurrent sequence allocation, concurrent duplicate terminal rejection, retries, and operation pairing. |
| 3 | `/replay` reads V3 while `/trace` remains the rollback fallback. | VERIFIED | `/replay` delegates to `ReplayService.get_replay()`; `/trace` still calls `TraceRepository.build_timeline()`. API tests cover event-store-first replay and trace fallback. |
| 4 | `agent_trace_events` stores both minimal rows and new `replay_event.v3` rows without rewriting old rows. | VERIFIED | ORM and Alembic check allow both schema versions; tests assert minimal rows project with provenance and remain `minimal_event_envelope.v1`. |
| 5 | ReplayEventV3 and ReplayResponseV3 schemas expose only V3 replay entries with provenance for legacy/minimal rows. | VERIFIED | Strict Pydantic schemas in `src/replay/schemas.py`; `ReplayService.project_event()` always emits `replay_event.v3` and provenance includes source schema and pairing status. |
| 6 | Live schema expansion includes V3 columns, checks, and indexes. | VERIFIED | `src/db/models.py` and migration `010_replay_event_v3.py` add `parent_operation_id`, `attempt`, retention columns, schema/event checks, positive sequence/attempt checks, and replay indexes. |
| 7 | ReplayService owns append, projection, redaction guard, retention defaults, and shared per-run sequence allocation. | VERIFIED | `src/replay/service.py` contains append/projection/read/allocation; `src/replay/validators.py` owns redaction and retention classification. |
| 8 | `src.agent.events.emit_event()` remains a compatibility wrapper and delegates replay logic. | VERIFIED | `src/agent/events.py` delegates `allocate_sequence()` and `emit_event()` to `ReplayService`. |
| 9 | Concurrent writers for one run cannot duplicate `(run_id, sequence)` and resume continues after existing rows. | VERIFIED | Unique ORM constraint plus advisory-lock allocator; sequence tests cover resume after existing sequence 8 and five concurrent appends. |
| 10 | Raw prompt/tool/action/secret/PII keys are rejected before persistence and projection. | VERIFIED | `guard_redacted_payload()` recursively rejects forbidden keys and is called before append and projection; redaction tests cover unsafe keys and replay omission. |
| 11 | Started and terminal events for the same operation share `operation_id`. | VERIFIED | `validate_operation_pairing()` requires terminal events to find a prior started event with the same `operation_id`; service and pairing tests cover started-to-terminal pairs. |
| 12 | Every operation has at most one terminal event; duplicate terminal events are rejected. | VERIFIED | Pairing validator rejects duplicate terminal events; service tests and concurrent terminal tests prove one commit and one rejection. |
| 13 | Retries use a new `operation_id`, valid `parent_operation_id`, and positive incremented `attempt`. | VERIFIED | `src/replay/pairing.py` enforces retry parent existence, new operation id, and greater attempt; tests cover valid and invalid retry shapes. |
| 14 | Historical/minimal rows with unprovable pairing project as `pairing_status="unresolved"` and do not fabricate pairs. | VERIFIED | `_projected_pairing_status()` returns unresolved for minimal rows; tests assert no backwrite to source schema. |
| 15 | RunLifecycleService is the unified owner for lifecycle replay events and final status append behavior. | VERIFIED | Trace helpers route status changes through `RunLifecycleService`; lifecycle service appends via `ReplayService`. |
| 16 | Normal, interrupted, resumed, responded, rejected, expired, error, and cancelled timelines are represented without fabricated completion. | VERIFIED | Lifecycle matrix tests include responded needs-info remaining interrupted with no completed lifecycle event. |
| 17 | Approval `respond` remains interrupted and does not emit completed lifecycle. | VERIFIED | `src/approvals/service.py` calls `update_agent_run_status(... final_status="interrupted", reason_code="needs_info_response", emit_if_unchanged=True)`; tests assert `needs_info_response`. |
| 18 | ApprovalSlaScanner remains disabled by default unless a later enablement phase opens the gate. | VERIFIED | Coverage records active SLA scanner as owner-named deferral; `tests/approvals/test_sla_scanner.py` remains part of final gates. |
| 19 | `GET /api/v1/agent-runs/{run_id}/replay` returns `schema_version="replay_response.v3"` and a sequence-ordered V3 timeline. | VERIFIED | `ReplayService.get_replay()` orders by `AgentTraceEvent.sequence`; API and service tests assert schema version and ordered sequences. |
| 20 | `/replay` reads `agent_trace_events` rows first and does not depend on legacy `TraceRepository.build_timeline()` for V3 rows. | VERIFIED | Router uses `TraceRepository` only for tenant-scoped run lookup and then calls `ReplayService.get_replay()`; event-store-first tests create replay rows without legacy step dependence. |
| 21 | `/trace` remains the legacy rollback fallback and existing trace tests stay green. | VERIFIED | `/trace` route still calls `repo.build_timeline(...)`; final coverage records `tests/test_trace_api.py` in passing gates. |
| 22 | Replay access control preserves cross-tenant 404 and same-tenant non-owner non-supervisor 403 behavior. | VERIFIED | `/replay` route reuses tenant-scoped lookup and owner/supervisor role check; API tests cover 404 and 403 cases. |
| 23 | Replay-facing demo draft wording cannot be mistaken for external execution. | VERIFIED | `action_draft_created` payload contains `execution_mode="demo"`, `external_side_effect=False`, and `draft_outcome.status="not_executed_demo"`. |
| 24 | Replay responses omit raw prompt/tool/action payloads, full final responses, secrets, credentials, and PII-heavy keys. | VERIFIED | Redaction guard blocks unsafe keys; replay API tests assert absence of `raw_payload`, secrets, `proposed_action`, and `action_execution_*` markers. |
| 25 | Phase 15 coverage records every requirement, deferred owner, command result, and rollback fallback. | VERIFIED | `15-COVERAGE.md` maps REPLAY-01..03, deferred owners, `/trace` fallback, final gate commands, post-review fix `c091515`, clean review `9779b7f`, and coverage refresh `8451516`. |
| 26 | Focused replay suite, trace/event/approval/action regressions, Alembic upgrade, ruff, and full pytest gate are recorded. | VERIFIED | `15-COVERAGE.md` records Alembic PASS, focused PASS, full pytest `875 passed, 1 warning`, and ruff PASS after `c091515`. |

**Score:** 26/26 truths verified

### Deferred Items

Items not implemented in Phase 15 but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | External execution tables/rows, outbox, dispatcher, external worker allocator tests, reconciliation, compensation, and `action_execution_*` event families. | Phase 17 | ROADMAP Phase 17 goal and success criteria own external action execution; `15-COVERAGE.md` records these as `DEFERRED_WITH_OWNER`. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/replay/schemas.py` | ReplayEventV3, ReplayResponseV3, provenance, retention, error schemas | VERIFIED | Exists, substantive, strict schemas with `extra="forbid"` and V3 literals. |
| `src/replay/validators.py` | Event registry, redaction guard, retention classification | VERIFIED | Registry excludes Phase 17 event families; recursive unsafe-key guard and explicit retention map exist. |
| `src/db/models.py` | `AgentTraceEvent` V3 ORM expansion | VERIFIED | Contains V3 nullable columns, checks, unique `(run_id, sequence)`, and indexes. |
| `src/db/migrations/versions/010_replay_event_v3.py` | Alembic expand migration | VERIFIED | Adds V3 columns/checks/indexes while allowing both minimal and V3 schema versions. |
| `src/replay/service.py` | Replay append/projection/read service and allocator | VERIFIED | Owns advisory-lock allocator, append validation, projection, and event-store-first read path. |
| `src/replay/pairing.py` | Operation pairing and retry validation | VERIFIED | Enforces operation identity, terminal pairing, retry parent/attempt, and statuses. |
| `src/replay/lifecycle.py` | Run lifecycle finalizer | VERIFIED | Appends lifecycle facts through ReplayService for all required statuses. |
| `src/agent/events.py` | Minimal-envelope compatibility wrapper | VERIFIED | Delegates sequence allocation and emit to ReplayService with minimal schema version. |
| `src/api/routers/traces.py` | `/replay` route and preserved `/trace` route | VERIFIED | `/replay` calls ReplayService; `/trace` calls TraceRepository timeline composition. |
| `src/actions/service.py` | Demo draft replay payload safety | VERIFIED | Emits safe draft outcome only; no external execution event or raw action payload in replay event. |
| `tests/replay/*`, `tests/agent/test_events.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, `tests/approvals/test_needs_info_resume.py` | Contract/regression coverage | VERIFIED | Tests cover schemas, migration, service, sequence allocator, pairing, lifecycle, replay API, redaction, and draft safety. |
| `.planning/phases/15-replay-event-contract/15-COVERAGE.md` | Final coverage and gate record | VERIFIED | Records REPLAY-01..03, deferred owners, rollback fallback, command results, and post-review evidence. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Migration | ORM | Matching V3 column/check/index names | VERIFIED | `verify.key-links` passed for Plan 15-01; manual inspection confirms shared columns and schema/event checks. |
| Replay schemas | Service/tests | Strict V3 response validation | VERIFIED | Service builds `ReplayResponseV3`; tests validate `replay_response.v3` and strict timeline items. |
| Validators | Migration/tests | Consolidated event enum/check parity | VERIFIED | `REPLAY_EVENT_TYPES` and migration check contain the same Phase 15 event family set. |
| Agent event wrapper | ReplayService | Delegated append/allocation | VERIFIED | `src/agent/events.py` imports and calls `ReplayService`. |
| Pairing validator | ReplayService | Append-time and read-time validation | VERIFIED | `append_event()` validates after lock before allocation; `get_replay()` revalidates persisted rows against `prior_events`. |
| Lifecycle service | ReplayService | Lifecycle append | VERIFIED | `RunLifecycleService._append_status_event()` calls `ReplayService.append_event()`. |
| Trace helpers/API routers | Lifecycle service | Status writes route through lifecycle-aware helpers | VERIFIED | `write_agent_run()` and `update_agent_run_status()` append lifecycle events; agent and approvals routers call these helpers. |
| `/replay` route | ReplayService | Event-store-first read | VERIFIED | Router delegates to `ReplayService.get_replay()` after access check. |
| `/trace` route | TraceRepository | Rollback fallback | VERIFIED | Router still calls `TraceRepository.build_timeline()`. |
| Action draft service | Replay payload safety | Safe draft outcome | VERIFIED | Action draft event emits only demo mode, no external side effect, and validated `DraftOutcomeV1`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `ReplayService.append_event()` | `AgentTraceEvent` row | Callers pass event payload; service validates, locks run, assigns sequence, inserts and flushes DB row | Yes | FLOWING |
| `ReplayService.get_replay()` | `timeline` | `sa.select(AgentTraceEvent).where(run_id).order_by(sequence)` | Yes | FLOWING |
| `/api/v1/agent-runs/{run_id}/replay` | `replay_response` | `ReplayService(session).get_replay(run_uuid)` after tenant/owner access check | Yes | FLOWING |
| `/api/v1/agent-runs/{run_id}/trace` | `timeline` | `TraceRepository.get_steps/get_approvals/get_action_drafts` then `build_timeline()` | Yes | FLOWING |
| `RunLifecycleService` | lifecycle `redacted_payload` | Trace helpers and approval service pass real run status transitions | Yes | FLOWING |
| `ActionDraftService._emit_action_draft_created()` | replay `redacted_payload` | Persisted draft data plus validated `DraftOutcomeV1` | Yes, safe subset only | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Pairing/retry validator behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py -q --tb=short` | `8 passed, 1 warning in 0.01s` | PASS |
| Replay schema/service import and retention classification | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.replay.schemas import ReplayResponseV3; from src.replay.validators import retention_for_event_type; from src.replay.service import ReplayService; ..."` | Printed `replay_response.v3`, `action_audit_event`, `True` | PASS |
| Phase 17 event families remain unregistered | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.replay.validators import REPLAY_EVENT_TYPES; ..."` | Printed `phase17-events-deferred` | PASS |
| ORM V3 columns/check exist | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.db.models import AgentTraceEvent; ..."` | Printed `True True True` and schema-version check name | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| REPLAY-01 | 15-01, 15-03, 15-04, 15-05, 15-06 | ReplayEventV3 and lifecycle finalizer cover all required completed/interrupted/terminal paths. | SATISFIED | Strict schemas, lifecycle service, lifecycle matrix tests, event-store replay, and draft safety are present. |
| REPLAY-02 | 15-01, 15-02, 15-03, 15-04, 15-06 | Shared per-run sequence allocator and operation pairing/retry contracts are enforced. | SATISFIED | Advisory-lock allocator, unique `(run_id, sequence)`, operation pairing/retry validator, wrapper delegation, lifecycle writer coverage, and concurrent writer tests. |
| REPLAY-03 | 15-01, 15-02, 15-05, 15-06 | Replay redaction, retention, access control, read-switch, fallback, and rollback are defined. | SATISFIED | Redaction guard, retention map, `/replay` route with access parity, `/trace` fallback, and coverage/final gate evidence. |

No orphaned Phase 15 requirements were found. `REPLAY-01..03` are the only Phase 15 requirements in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | - | - | - | Stub/placeholder scan found no TODO/FIXME/placeholder, console-only implementation, or hardcoded empty runtime data in Phase 15 runtime files. Empty list initializations are normal local accumulators. |

### Human Verification Required

None. Phase 15 is backend/API/event-store behavior with automated/static evidence; no visual, real-time UI, or live external-service behavior is required for this phase. External execution integration is explicitly deferred to Phase 17.

### Gaps Summary

No gaps found. The Phase 15 goal is achieved: ReplayEventV3 storage/projection, lifecycle finalization, sequence allocation, redaction/retention, operation pairing, replay read-switch, trace fallback, demo draft safety, and owner-named Phase 17 deferrals are present and wired in the actual codebase.

---

_Verified: 2026-06-16T16:51:01Z_
_Verifier: Codex (gsd-verifier)_
