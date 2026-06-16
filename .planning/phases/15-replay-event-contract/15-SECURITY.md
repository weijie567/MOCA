---
phase: 15
slug: replay-event-contract
status: verified
threats_total: 24
threats_closed: 24
threats_open: 0
asvs_level: 1
created: 2026-06-17
verified: 2026-06-17
---

# Phase 15 - Security

Per-phase security contract for Phase 15 ReplayEventV3 storage, projection, lifecycle replay, operation pairing, replay API access control, redaction, retention, and deferred-owner evidence.

## Trust Boundaries

| Boundary | Description | Data Crossing |
| --- | --- | --- |
| Replay writer boundary | Domain event writers enter `ReplayService.append_event()` and share replay validation/allocation. | Tenant/run scoped replay event metadata and redacted payloads. |
| Replay read API boundary | `/api/v1/agent-runs/{run_id}/replay` exposes event-store replay data to authorized users. | `ReplayResponseV3` timelines, provenance, retention metadata, and redacted payloads. |
| Legacy trace fallback boundary | `/trace` remains a rollback/debug read model separate from `/replay`. | Legacy timeline data from steps, approvals, approval steps, and action drafts. |
| Lifecycle status boundary | run status changes are persisted in `AgentRun` and mirrored as replay lifecycle events. | `run_status_changed` events for running, interrupted, completed, error, and cancelled states. |
| Demo action draft boundary | demo draft replay evidence must not imply external execution. | Safe refs, action payload hash, `draft_outcome`, and `external_side_effect=false`. |
| Deferred external execution boundary | Phase 17 owns external execution, outbox, reconciliation, compensation, and `action_execution_*`. | No Phase 15 external side effects or action execution rows. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| T-15-01 | Tampering | Replay migration | mitigate | Expand-only nullable V3 columns preserve `minimal_event_envelope.v1`; migration tests prevent V3 backwrite. | closed | `src/db/models.py:652`, `src/db/migrations/versions/010_replay_event_v3.py:58`, `tests/replay/test_replay_migration_contract.py:107` |
| T-15-02 | Information disclosure | Replay schemas/service | mitigate | Strict Pydantic schemas and redaction-sensitive append/projection validation block raw payload fields. | closed | `src/replay/schemas.py:37`, `src/replay/service.py:79`, `tests/replay/test_replay_redaction_retention.py:60` |
| T-15-03 | Information disclosure | Retention lifecycle | mitigate | Replay retention fields are present in schema, ORM, migration, persistence, and projection. | closed | `src/replay/schemas.py:21`, `src/db/models.py:696`, `src/replay/service.py:232` |
| T-15-04 | Tampering | Schema rollout gate | mitigate | Alembic upgrade is a blocking gate and is recorded as PASS in phase artifacts. | closed | `15-01-SUMMARY.md:95`, `15-COVERAGE.md:55`, `15-COVERAGE.md:71` |
| T-15-05 | Tampering | Sequence allocator | mitigate | Per-run advisory transaction lock plus unique `(run_id, sequence)` backstop prevent duplicate sequence allocation. | closed | `src/replay/service.py:24`, `src/replay/service.py:30`, `src/db/models.py:650` |
| T-15-06 | Tampering | Legacy event wrapper | mitigate | Compatibility `emit_event()` delegates through `ReplayService.append_event()`. | closed | `src/agent/events.py:40`, `src/agent/events.py:59`, `tests/agent/test_events.py:111` |
| T-15-07 | Information disclosure | Replay payload guard | mitigate | Central unsafe-key denylist and recursive guard reject unsafe payload keys before persistence. | closed | `src/replay/validators.py:56`, `src/replay/validators.py:78`, `src/replay/service.py:81` |
| T-15-08 | Information disclosure | Event retention registry | mitigate | Every accepted replay event type requires explicit retention classification. | closed | `src/replay/validators.py:32`, `src/replay/validators.py:95`, `tests/replay/test_replay_redaction_retention.py:39` |
| T-15-09 | Tampering | Operation pairing | mitigate | Pairing validation rejects duplicate terminal events for the same operation. | closed | `src/replay/pairing.py:61`, `src/replay/pairing.py:65`, `tests/replay/test_operation_pairing.py:43` |
| T-15-10 | Tampering | Retry operation identity | mitigate | Retry validation requires a new `operation_id`, parent link, and increased attempt. | closed | `src/replay/pairing.py:100`, `src/replay/service.py:112`, `tests/replay/test_operation_pairing.py:61` |
| T-15-11 | Tampering | Legacy/minimal projection | mitigate | Minimal or unknown historical rows project as `pairing_status=unresolved` without storage backwrite. | closed | `src/replay/service.py:251`, `tests/replay/test_replay_service.py:423` |
| T-15-12 | Repudiation | Bounded tool/RAG iteration | mitigate | Replay service preserves iteration context in child operation payloads and pairing metadata. | closed | `src/replay/service.py:76`, `src/replay/service.py:84`, `src/replay/pairing.py:166` |
| T-15-13 | Tampering | Needs-info lifecycle | mitigate | Responded/needs-info flows append interrupted lifecycle events and do not append completed events. | closed | `src/replay/lifecycle.py:40`, `tests/replay/test_lifecycle_finalizer.py:141`, `tests/approvals/test_needs_info_resume.py:166` |
| T-15-14 | Repudiation | Error/cancel lifecycle | mitigate | Lifecycle service appends safe error/cancelled terminal events after partial replay history. | closed | `src/replay/lifecycle.py:142`, `src/replay/lifecycle.py:164`, `tests/test_agent_runs_api.py:385` |
| T-15-15 | Tampering | API/run status persistence | mitigate | `write_agent_run()` and `update_agent_run_status()` route status changes through lifecycle replay. | closed | `src/agent/trace.py:16`, `src/agent/trace.py:124`, `src/api/routers/approvals.py:278` |
| T-15-16 | Tampering | Approval SLA scanner | mitigate | Scanner remains default-disabled; active enablement is recorded as owner-named deferred work. | closed | `tests/approvals/test_sla_scanner.py:44`, `tests/approvals/test_sla_scanner.py:52`, `15-COVERAGE.md:33` |
| T-15-17 | Information disclosure | Replay API tenant scoping | mitigate | Replay route performs tenant-scoped run lookup and returns 404 cross-tenant. | closed | `src/api/routers/traces.py:89`, `src/api/routers/traces.py:92`, `tests/replay/test_replay_api.py:60` |
| T-15-18 | Information disclosure / elevation | Replay API authorization | mitigate | Same-tenant replay access requires owner or supervisor role; non-owner users receive 403. | closed | `src/api/routers/traces.py:95`, `tests/replay/test_replay_api.py:79` |
| T-15-19 | Tampering | Replay read switch | mitigate | `/replay` reads event-store rows through `ReplayService.get_replay()` ordered by sequence. | closed | `src/api/routers/traces.py:98`, `src/replay/service.py:171`, `tests/replay/test_replay_api.py:22` |
| T-15-20 | Availability | Legacy trace fallback | mitigate | `/trace` remains isolated on `TraceRepository.build_timeline()` with regression coverage. | closed | `src/api/routers/traces.py:39`, `src/repositories/trace_repo.py:56`, `tests/test_trace_api.py:24` |
| T-15-21 | Repudiation | Demo action draft replay | mitigate | `action_draft_created` replay payload uses demo-only labels and asserts no `action_execution_*` events. | closed | `src/actions/service.py:247`, `tests/replay/test_replay_redaction_retention.py:139`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:623` |
| T-15-22 | Information disclosure | Replay response projection | mitigate | Projection re-runs redaction guard; replay API tests assert raw payloads/secrets/execution markers stay absent. | closed | `src/replay/service.py:206`, `tests/replay/test_replay_api.py:148`, `tests/test_trace_api.py:59` |
| T-15-23 | Repudiation | Deferred owner evidence | mitigate | Phase 16/17 and SLA scanner deferrals are owner-named and not marked complete. | closed | `15-COVERAGE.md:31`, `15-COVERAGE.md:47` |
| T-15-24 | Repudiation | Phase command evidence | mitigate | Coverage records PASS/FAIL/NOT_RUN vocabulary and final gate command statuses. | closed | `15-COVERAGE.md:5`, `15-COVERAGE.md:67`, `15-COVERAGE.md:76` |

## Threat Flags Review

No unregistered flags.

| Source | Result |
| --- | --- |
| `15-02-SUMMARY.md` | `## Threat Flags`: None. |
| `15-04-SUMMARY.md` | `## Threat Flags`: None. |
| `15-05-SUMMARY.md` | `## Threat Flags`: None. |
| `15-06-SUMMARY.md` | `## Threat Flags`: None. |
| `15-01-SUMMARY.md` | No threat flags section; summary records no deviations, issues, known stubs, or setup blockers. |
| `15-03-SUMMARY.md` | No threat flags section; summary records no security-relevant runtime blocker or external setup. |

## Accepted Risks Log

No accepted risks.

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
| --- | --- | --- | --- | --- |

## Transferred Risks

No transferred risks.

## Security Audit 2026-06-17

| Metric | Count |
| --- | ---: |
| Threats found | 24 |
| Closed | 24 |
| Open | 0 |
| Unregistered flags | 0 |

## Verification Commands

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_redaction_retention.py tests/replay/test_operation_pairing.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py tests/agent/test_events.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | PASS: 131 passed, 1 warning |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
| --- | ---: | ---: | ---: | --- |
| 2026-06-17 | 24 | 24 | 0 | gsd-security-auditor + Codex |

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-06-17
