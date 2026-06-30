---
phase: 28
slug: decision-event-foundation
phase_name: decision-event-foundation
status: verified
asvs_level: 1
block_on: open
threats_total: 5
threats_closed: 5
threats_open: 0
unregistered_flags: 0
created: 2026-06-23
---

# Phase 28 Security Verification

Verified declared Phase 28 threat mitigations from `28-01-PLAN.md` against the implemented code and focused tests. All registered threats are disposition `mitigate`; there are no accepted or transferred risks for this phase.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| TrustedContextFactory -> ReplayContext -> emit_decision_event | Trusted API/auth/run identity enters replay audit truth. User or LLM payload fields must not override `run_id`, `tenant_id`, `thread_id`, or `trace_id`. | Trusted run identity, tenant scope, thread id, trace id |
| Service writer -> redacted_payload/resource_refs -> AgentTraceEvent | Service-provided event metadata crosses into durable audit storage. Raw prompts, raw tool args/output, raw business payloads, PII, and secrets must be rejected. | Redacted decision payloads, typed refs, resource hashes/ids |
| Wrapper compatibility -> replay-owned emitter | Legacy callers enter the new decision-event contract through `src.agent.events.emit_event`. Compatibility must not create a second envelope or widen top-level fields. | Minimal decision event envelope |
| Concurrent writers -> ReplayService allocator -> agent_trace_events | Multiple services append events for one run. Shared allocation and DB uniqueness preserve monotonic sequence ordering. | Event sequence, event id, operation id |

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-28-01 | Spoofing | mitigate | CLOSED | `src/replay/decision_events.py:80` resolves identity before append, `src/replay/decision_events.py:151` prefers `ReplayContext`, `src/replay/decision_events.py:166` requires `run_id`, `tenant_id`, and `thread_id`, `src/replay/decision_events.py:172` raises `ValueError`; `tests/replay/test_decision_events.py:177` and `tests/replay/test_decision_events.py:217` cover trusted identity and no-row fail closed behavior. |
| T-28-02 | Information Disclosure | mitigate | CLOSED | `src/replay/validators.py:56` defines forbidden unsafe keys including `raw_prompt`, `raw_args`, `raw_payload`, `raw_tool_output`, `secret`, `credentials`, and `pii`; `src/replay/validators.py:88` and `src/replay/validators.py:105` recursively guard payloads and resource refs; `src/replay/service.py:81` and `src/replay/service.py:82` guard before persistence; `src/replay/service.py:183`, `src/replay/service.py:184`, `src/replay/service.py:217`, and `src/replay/service.py:218` guard replay projection read paths; tests at `tests/replay/test_decision_events.py:417` and `tests/replay/test_decision_events.py:426` cover the declared unsafe keys, with stored unsafe resource-ref read regressions at `tests/replay/test_replay_service.py:324` and `tests/replay/test_replay_service.py:349`. |
| T-28-03 | Tampering | mitigate | CLOSED | `src/replay/decision_events.py:29` uses `ConfigDict(extra="forbid")`; `src/replay/decision_events.py:46` validates event type via `validate_event_type`; registry enforcement is in `src/replay/validators.py:83`; `tests/replay/test_decision_events.py:95` rejects extra top-level keys and `tests/replay/test_decision_events.py:132` rejects unregistered event types. |
| T-28-04 | Tampering / Repudiation | mitigate | CLOSED | `src/replay/service.py:30` preserves the per-run `pg_advisory_xact_lock`; `src/replay/service.py:107` allocates the next sequence and `src/replay/service.py:108` derives UUIDv5 event ids from `run_id:sequence`; `tests/replay/test_sequence_allocator.py:76` covers concurrent appends without duplicate sequences, and `tests/replay/test_sequence_allocator.py:167` includes `emit_decision_event` in shared allocator regression coverage. |
| T-28-05 | Repudiation | mitigate | CLOSED | `src/replay/service.py:179` projects minimal events, `src/replay/service.py:202` validates through `DecisionEventEnvelopeV1`, and `src/replay/service.py:204` returns the strict envelope dump; `tests/replay/test_decision_events.py:95` forbids top-level `policy_version`, `model_version`, `tool_version`, `reason_code`, `reason_codes`, and service metadata, while `tests/replay/test_decision_events.py:488` verifies minimal projection matches `DecisionEventEnvelopeV1`. |

## Threat Flags

`28-01-SUMMARY.md` has no `## Threat Flags` section. No unregistered flags were recorded.

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-23 | 5 | 5 | 0 | gsd-security-auditor |

## Verification Notes

- Implementation files were read-only during this audit.
- Only this `28-SECURITY.md` report was created.

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-06-23
