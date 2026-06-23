---
phase: 28
slug: decision-event-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 28 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 under `uv run` |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py -q` |
| **Full suite command** | `uv run pytest tests/replay tests/agent/test_events.py tests/platform/test_context_projections.py -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py -q`
- **After every plan wave:** Run `uv run pytest tests/replay tests/agent/test_events.py tests/platform/test_context_projections.py -q`
- **Before `$gsd-verify-work`:** Full targeted suite must be green, plus any writer-specific tests touched by the implementation.
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | APF-05 | T-28-01 / T-28-03 | `DecisionEventEnvelopeV1` strictly accepts only `contract-spec.md` §17.2 minimal fields, rejects extras/missing required fields, validates registered event types, and requires `operation_id` for operation lifecycle events. | unit | `uv run pytest tests/replay/test_decision_events.py -q` | No - Wave 0 creates | pending |
| 28-01-02 | 01 | 1 | APF-05 | T-28-01 / T-28-05 | `emit_decision_event(...)` persists through `ReplayService.append_event(...)` with `schema_version="minimal_event_envelope.v1"` and returns a validated minimal envelope without top-level service metadata. | integration | `uv run pytest tests/replay/test_decision_events.py -q` | No - Wave 0 creates | pending |
| 28-01-03 | 01 | 1 | APF-05 | T-28-02 | `redacted_payload` and `resource_refs` reject unsafe keys including raw prompt, raw args, raw payload, raw tool output, PII, secrets, and credentials. | unit/integration | `uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_redaction_retention.py -q` | Partial - refs guard missing | pending |
| 28-01-04 | 01 | 1 | APF-05 | T-28-04 | `reason_code` compatibility converts to first-seen de-duplicated `reason_codes`; invalid reason-code strings are rejected; versions land under `redacted_payload.versions`. | unit | `uv run pytest tests/replay/test_decision_events.py -q` | No - Wave 0 creates | pending |
| 28-01-05 | 01 | 1 | APF-05 | T-28-05 | `src.agent.events.emit_event` remains compatible and delegates to the replay-owned facade without breaking existing event writer tests. | unit | `uv run pytest tests/agent/test_events.py -q` | Yes | pending |
| 28-01-06 | 01 | 1 | APF-05 | T-28-04 | Sequence allocator ordering remains shared across graph, memory, approval, action draft, replay backfill, and lifecycle writers. | integration | `uv run pytest tests/replay/test_sequence_allocator.py -q` | Yes | pending |
| 28-01-07 | 01 | 1 | APF-05 | T-28-05 | `ReplayContext` / trusted projection remains the preferred source for run/tenant/thread/trace identity and projection-local version metadata does not widen `TrustedContext`. | unit | `uv run pytest tests/platform/test_context_projections.py -q` | Yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/replay/test_decision_events.py` - strict envelope schema, emitter facade, missing identity, operation-id condition, reason/version normalization, and resource-ref guard tests.
- [ ] `tests/agent/test_events.py` - wrapper compatibility and legacy `reason_code` conversion coverage.
- [ ] `tests/replay/test_replay_service.py` or `tests/replay/test_decision_events.py` - prove `ReplayService.project_minimal_event(...)` validates through `DecisionEventEnvelopeV1` or returns exactly that schema shape.

---

## Manual-Only Verifications

All Phase 28 behaviors should have automated verification. Manual review is limited to checking that the plan does not introduce DB schema migrations or service-specific top-level envelope fields.

---

## Threat Model Requirements

| Threat ID | STRIDE | Behavior | Required Mitigation | Verification |
|-----------|--------|----------|---------------------|--------------|
| T-28-01 | Spoofing | User/LLM/caller forges event run, tenant, thread, or trace identity. | New emitter prefers `ReplayContext` from trusted context projection; missing required identity fails closed. | `tests/replay/test_decision_events.py` covers trusted context identity and missing identity rejection. |
| T-28-02 | Information Disclosure | Raw prompt, raw tool output, raw business payload, PII, or secrets leak into audit rows. | Recursive guard checks both `redacted_payload` and `resource_refs`; only typed refs, hashes, ids, and prompt-safe summaries are allowed. | Negative leakage tests in `tests/replay/test_decision_events.py` and existing redaction tests. |
| T-28-03 | Tampering | Unregistered event types or extra envelope fields bypass replay/retention rules. | `DecisionEventEnvelopeV1` uses registered event type validation and `extra="forbid"`. | Schema strictness tests. |
| T-28-04 | Tampering / Repudiation | Concurrent writers collide or reorder event sequence. | Preserve `ReplayService` advisory lock and unique `(run_id, sequence)` behavior. | `tests/replay/test_sequence_allocator.py`. |
| T-28-05 | Repudiation | Service-specific metadata widens top-level envelope and creates a parallel event format. | Keep §17.2 top-level fields fixed; put reason codes and versions under `redacted_payload`, `redacted_payload.versions`, or typed `resource_refs`. | Contract tests assert no top-level `policy_version`, `model_version`, `tool_version`, `reason_code`, or `reason_codes`. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 90 seconds.
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 tests exist and pass.

**Approval:** pending
