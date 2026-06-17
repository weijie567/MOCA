# Phase 12: Session Memory - Coverage Extraction and Verification

**Generated:** 2026-06-14
**Status:** Ready for plan execution after review fixes

## Coverage Extraction Inputs

- `.planning/REQUIREMENTS.md` — `SESSION-01`, `SESSION-02`, `SESSION-03` and mandatory phase-plan traceability fields.
- `.planning/ROADMAP.md` — Phase 12 goal, dependencies on Phases 10/11, and success criteria.
- `.planning/phases/12-session-memory/12-CONTEXT.md` — locked decisions D-01 through D-20.
- `.planning/phases/12-session-memory/12-RESEARCH.md` — local implementation research and recommended planning slices.
- `docs/contract-spec.md` Sections 9.3-9.5, 10.1-10.4, 13.1-13.2, 17.2, 18.1, 20.1, 21.3.
- `docs/agent-architecture-phase-decomposition.md` Phase 12 row, memory/schema ownership rows, Redis boundary, and follow-up register.
- `docs/migration-plan.md` Phase 12 row and phase planning traceability requirements.
- `docs/eval-test-plan.md` Session memory contract row and missing-slot cross-turn golden flow.
- `.planning/phases/10-state-lifecycle-routing-migration/10-05-SUMMARY.md` — existing empty session adapter and graph/API event foundation.
- `.planning/phases/11-intent-clarification/11-03-SUMMARY.md` — router/slot fail-closed metadata seam.

## Spec Consistency Findings

| ID | Source requirement | Conflicting evidence | Type | Recommended handling | Readiness impact | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SCF-12-01 | `docs/contract-spec.md` shows canonical `final_response -> memory_write -> trace_close` path. | Current MOCA API returns/streams final response from API handlers; no `trace_close` node exists yet, and Phase 15 owns full replay/finalizer. | Implementation topology deviation | Phase 12 implements memory write as a post-response finalizer/hook with strict timeout/best-effort semantics, using Phase 10 event emitter; Phase 15 owns `trace_close`/ReplayEventV3 finalizer. | Non-blocking if 12-03 tests prove final response is returned/yielded to the caller before memory write waits, and background writes use a fresh DB session/transaction. | Phase 12 for post-response hook; Phase 15 for trace_close | COVERED |
| SCF-12-02 | `docs/contract-spec.md` memory lifecycle shows `memory_write_decision.v2` with PII classification, decision, and reason code. | Phase 12 only owns session memory, not long-term/case review workflow, tombstones, or `memory_identity.v1`. | Scope split | Phase 12 uses a session-only subset: PII classification before write, `decision`/`reason_code` in write result, and prohibited/sensitive negative tests. Phase 16 owns full long-term/case decision lifecycle. | Non-blocking if 12-01/12-03/12-04 include PII/write-decision subset tests. | Phase 12 session subset; Phase 16 full memory lifecycle | COVERED |
| SCF-12-03 | Redis is mentioned as optional hot cache in Phase 12. | Phase 12 correctness gates are PostgreSQL CAS and safe inheritance; no measured latency need exists. | Deferral with owner | Default to `SKIP_FOR_PHASE_12`; Redis can only be implemented by explicit decision with fallback tests. | Non-blocking; Redis is not required for Phase 12 exit. | Phase 12 `12-05` decision gate | COVERED |

## Review Fixes Applied

- `12-02` now requires `slot_extraction` / slot resolution to write trusted inherited slots into resolved `AgentState.active_slots` for downstream `investigate` and business tool args, while preserving `active_slot_metadata` so inherited values cannot become current-turn explicit memory-write candidates.
- `12-03` now treats post-response memory write as truly non-blocking for `/chat`: the final response must be returned/yielded before slow memory write waits, and background writes must use a fresh DB session/transaction rather than a closed request-scoped `AsyncSession`.
- `12-01` and `12-04` now define and test field-level CAS merge/conflict rules for `active_slots_json`, `session_summary`, `unresolved_questions_json`, `last_intent`, and `last_business_context_refs_json`.
- `12-01` now separates persisted slot source from loaded router metadata: `trusted_session_memory` is loaded-view metadata only, not a persisted slot source.
- `12-01` now requires expired active rows to be reusable or transactionally replaced so TTL expiry cannot create a unique-index write failure.
- `12-03` now requires memory-write event retention classification in addition to event registration and redaction tests.
- `12-04` now covers the `docs/eval-test-plan.md` missing-slot cross-turn golden flow with unresolved question carryover.

## Global Coverage Matrix

| Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Session memory CAS | 12-01, 12-04 | `tests/memory/test_session_memory_repository.py`, `tests/memory/test_session_memory_service.py`, `tests/memory/test_session_memory_concurrency.py`; includes field-level merge/conflict tests for slots, summary, unresolved questions, last intent, and business refs | 12-01 owns `session_memories`, version, indexes, downgrade | None | Disable session memory read/write; downgrade migration if required | Blocking contract tests; dataset owner: Phase 12; version/hash: test suite commit hash; failure blocks implementation completion | COVERED |
| Slot inheritance safety | 12-02, 12-04 | `tests/agent/test_required_slots.py`, `tests/agent/test_session_memory_integration.py`, graph tests; includes resolved `active_slots` handoff and explicit-vs-inherited metadata assertions | N/A: service/router behavior only | None | `session_memory_enabled=false` returns empty adapter view | Blocking route-safety eval; owner Phase 12; version/hash: focused test suite hash; failure blocks execution signoff | COVERED |
| Observable fallback/read-switch | 12-02, 12-03, 12-04 | disabled/missing/unavailable tests for read and write paths | N/A: config/read-switch only | None | Phase 12 owns `session_memory_enabled`, fallback telemetry, rollback behavior | Blocking fallback tests; no external dataset; failure blocks execution signoff | COVERED |
| Memory-is-not-evidence/action authority | 12-01, 12-03, 12-04 | grep/import guard, graph negative tests, citation/evidence boundary tests | N/A: no schema migration beyond session table | None | Disable memory; KnowledgeService remains sole evidence producer | Blocking negative tests; owner Phase 12; failure blocks implementation completion | COVERED |
| PII/prohibited content blocking | 12-01, 12-03, 12-04 | schema/service/node tests for `pii_classification`, `reason_code`, prohibited skip, no raw prompt/tool payload | N/A for Phase 12 schema beyond result fields; full memory identity deferred | Full `memory_identity.v1`, tombstones, review workflow deferred to Phase 16 with tombstone/review acceptance gate | Disable writes or skip prohibited candidates | Blocking contract tests; owner Phase 12 for session subset; failure blocks write-path completion | COVERED |
| Minimal memory write events | 12-03 | event type registration, retention classification, and redaction guard tests | Phase 10 owns base `agent_trace_events`; Phase 12 owns memory event additions | Full ReplayEventV3 enrichment and `trace_close` deferred to Phase 15 | Existing AgentRun/API terminal persistence remains rollback path | Non-blocking replay enrichment; Phase 15 owns V3 dataset/gate | PARTIAL |
| Redis hot cache boundary | 12-05 | default skip doc; optional fallback tests only if explicitly implemented | N/A: Redis owns no schema | Optional cache deferred until explicit approval and measured need; acceptance gate is cache miss/unavailable/stale/invalid fallback tests | Disable optional cache; PostgreSQL remains authoritative | Non-blocking; no Redis dataset in default path | DEFERRED_WITH_OWNER |
| Long-term/case memory + memory_identity/tombstones | Not implemented in Phase 12 | Negative boundary tests ensure not pulled into session memory | N/A in Phase 12 | Owner Phase 16; acceptance gate: identity/tombstone/review workflow tests | N/A for Phase 12 | Phase 16 memory write quality eval | DEFERRED_WITH_OWNER |
| Approval needs_info / action safety / external dispatch | Not implemented in Phase 12 | Negative tests ensure memory does not authorize approval/action; interrupted path skips normal memory write | N/A in Phase 12 | Owner Phases 13/14/17 with approval/action/external gates | N/A for Phase 12 | Phase 13/14/17 eval gates | DEFERRED_WITH_OWNER |

## Verification Outcome Required Before Execution

- No `MISSING` rows in this coverage matrix.
- Every `PARTIAL` row has an owner and non-blocking rationale.
- Review fixes above must remain represented in the individual plan acceptance criteria before execution.
- Redis remains skipped unless `12-05` is explicitly approved.
- Phase 12 implementation starts with `12-01`; `12-05` is not autonomous.
