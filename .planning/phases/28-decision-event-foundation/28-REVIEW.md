---
phase: 28
phase_name: decision-event-foundation
status: clean
depth: deep
files_reviewed: 10
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
reviewed_at: 2026-06-23T02:15:32Z
---

# Phase 28 Code Review

## Scope

Reviewed source and focused test changes from Phase 28:

- `src/replay/decision_events.py`
- `src/replay/validators.py`
- `src/replay/service.py`
- `src/replay/__init__.py`
- `src/agent/events.py`
- `src/agent/nodes/memory_write.py`
- `tests/replay/test_decision_events.py`
- `tests/agent/test_events.py`
- `tests/agent/test_memory_write_node.py`
- `tests/replay/test_sequence_allocator.py`

## Findings

No critical, warning, or info findings.

## Checks Performed

- Verified `DecisionEventEnvelopeV1` stays locked to the existing `minimal_event_envelope.v1` fields.
- Verified `emit_decision_event(...)` persists via `ReplayService.append_event(...)` and does not create a second event format.
- Verified reason codes normalize under `redacted_payload.reason_codes` and versions stay under `redacted_payload.versions`.
- Verified `guard_resource_refs(...)` mirrors the existing unsafe-key guard and is invoked before event persistence.
- Verified the legacy `src.agent.events.emit_event(...)` wrapper delegates to the replay-owned emitter.
- Verified `memory_write` only adds operation-id propagation and does not change memory policy or storage behavior.

## Verification Reviewed

- `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py -q` - 73 passed.
- `uv run pytest tests/replay/test_sequence_allocator.py tests/platform/test_context_projections.py -q` - 11 passed.
- `uv run pytest tests/replay tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/platform/test_context_projections.py -q` - 132 passed.
- `uv run pytest tests/approvals/test_events.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q` - 42 passed.
- `git diff --name-only -- src/db/models.py src/db/migrations` - no output.

## Residual Risk

Phase 28 intentionally keeps broad Tool/Memory/RAG/Approval/Action payload migration out of scope. Later domain phases still need to move their service-specific reason/version payloads onto the new facade where required.
