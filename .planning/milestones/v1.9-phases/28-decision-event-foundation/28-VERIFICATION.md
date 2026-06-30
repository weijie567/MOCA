---
phase: "28-decision-event-foundation"
phase_number: 28
phase_name: "Decision Event Foundation"
verified: "2026-06-23T02:15:32Z"
status: passed
requirements_verified:
  APF-05: verified
blockers: []
warnings:
  - id: W-01
    area: verifier_runtime
    issue: "Verifier subagent was not spawned because this Codex runtime requires explicit user authorization for subagents; verification was completed inline from committed code, tests, review, key links, schema drift, and regression gates."
  - id: W-02
    area: security_gate
    issue: "workflow.security_enforcement=true and no Phase 28 SECURITY.md exists yet; run `$gsd-secure-phase 28` before advancing if security gate enforcement is required for this milestone step."
tests_reviewed:
  - command: "uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py -q"
    result: "73 passed, 1 warning"
  - command: "uv run pytest tests/replay/test_sequence_allocator.py tests/platform/test_context_projections.py -q"
    result: "11 passed, 1 warning"
  - command: "uv run pytest tests/replay tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/platform/test_context_projections.py -q"
    result: "132 passed, 1 warning"
  - command: "uv run pytest tests/approvals/test_events.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q"
    result: "42 passed, 1 warning"
  - command: "uv run pytest tests/platform -q"
    result: "47 passed, 1 warning"
  - command: "uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py -q"
    result: "131 passed, 1 warning"
  - command: "uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q"
    result: "47 passed, 1 warning"
  - command: "uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q"
    result: "9 passed, 8 warnings"
  - command: "uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q"
    result: "97 passed, 9 warnings"
  - command: "uv run ruff check <focused Phase 28 source and test scope>"
    result: "passed"
  - command: "gsd-sdk query verify.key-links .planning/phases/28-decision-event-foundation/28-01-PLAN.md"
    result: "4/4 passed"
  - command: "gsd-sdk query verify.schema-drift 28"
    result: "valid true; issues []"
review:
  status: clean
  findings:
    critical: 0
    warning: 0
    info: 0
score: "1/1 requirements verified; 1/1 plan summary complete; 4/4 key links verified"
human_verification: []
---

# Phase 28 Verification Report

**Status:** passed

Phase 28 achieved APF-05 within the planned foundation scope. The implementation adds a replay-owned `DecisionEventEnvelopeV1` schema and `emit_decision_event(...)` facade for the existing `minimal_event_envelope.v1`, routes the legacy `src.agent.events.emit_event(...)` wrapper through that facade, guards `resource_refs` alongside `redacted_payload`, and preserves the shared `ReplayService` sequence allocator without DB schema changes.

## Requirement Coverage

| Requirement | Status | Evidence |
|---|---|---|
| APF-05 | VERIFIED | `src/replay/decision_events.py` defines `DecisionEventEnvelopeV1`, `emit_decision_event(...)`, reason-code normalization, and version placement under `redacted_payload.versions`. `ReplayService.append_event(...)` remains the persistence/sequence path and now guards `resource_refs`. `src.agent.events.emit_event(...)` delegates to the replay-owned facade. |

## Plan Must-Haves

| Must-have | Status | Evidence |
|---|---|---|
| Minimal envelope stays strict and does not create a second format. | VERIFIED | `DecisionEventEnvelopeV1` has `schema_version: Literal["minimal_event_envelope.v1"]` and `model_config = ConfigDict(extra="forbid")`; `ReplayService.project_minimal_event(...)` validates through `DecisionEventEnvelopeV1.model_validate(...)`. |
| Event writes persist through `ReplayService.append_event(...)`. | VERIFIED | `emit_decision_event(...)` calls `ReplayService(session).append_event(..., schema_version=SCHEMA_VERSION)` and returns a validated minimal envelope dict. |
| Reason codes normalize to `redacted_payload.reason_codes`. | VERIFIED | `normalize_reason_codes(...)` enforces non-empty snake_case and first-seen de-duplication. Contract tests cover legacy `reason_code` plus `reason_codes` normalization and invalid values. |
| Policy/model/tool versions stay under `redacted_payload.versions`. | VERIFIED | `_normalize_versions(...)` merges `ReplayContext` and explicit versions into allowed version keys only. Tests assert no top-level `policy_version`, `model_version`, or `tool_version`. |
| Redaction guards cover payload and refs. | VERIFIED | `guard_resource_refs(...)` recursively rejects the same unsafe keys as `guard_redacted_payload(...)`; `ReplayService.append_event(...)` invokes both before persistence. |
| Legacy wrapper remains usable. | VERIFIED | `src.agent.events.emit_event(...)` preserves the existing required arguments, adds optional `reason_code` / `reason_codes`, and delegates to `emit_decision_event(...)`. |
| Sequence allocator remains monotonic across current writer surfaces. | VERIFIED | `tests/replay/test_sequence_allocator.py` includes `emit_decision_event(...)` and verifies contiguous per-run sequences across graph, memory, decision facade, approval, action draft, replay backfill, and lifecycle writers. |

## Non-Goals Honored

| Non-goal | Status | Evidence |
|---|---|---|
| No DB schema migration. | VERIFIED | `git diff --name-only -- src/db/models.py src/db/migrations` produced no output. |
| No V3 parent/attempt pairing in minimal facade. | VERIFIED | `src/replay/decision_events.py` does not add `parent_operation_id` or `attempt`; V3 pairing remains in `src/replay/pairing.py` and `ReplayService` only for `schema_version="replay_event.v3"`. |
| No broad writer migration. | VERIFIED | Only `src.agent.events` and the `memory_write` operation-id key path changed; `src/agent/nodes/investigate.py`, `src/approvals/events.py`, and `src/actions/service.py` remained untouched in Task 3. |

## Review And Gates

Code review completed cleanly in `.planning/phases/28-decision-event-foundation/28-REVIEW.md` with no findings.

Key-link verification passed after normalizing PLAN key-link regex values:

- `src/replay/decision_events.py` -> `src/replay/service.py`: `ReplayService(session).append_event`
- `src/replay/service.py` -> `src/replay/decision_events.py`: `DecisionEventEnvelopeV1.model_validate`
- `src/agent/events.py` -> `src/replay/decision_events.py`: `emit_decision_event`
- `src/replay/service.py` -> `src/replay/validators.py`: `guard_resource_refs(resource_refs)`

Schema drift gate returned valid with no issues.

## Regression Gates

Phase 28 targeted gates passed, plus prior Phase 24/25/27 regression suites most likely affected by replay, memory, graph, and trusted-context boundaries. All passed. Remaining warnings are pre-existing LangChain pending deprecation and LangGraph config typing warnings.

## Warnings

1. `gsd-verifier` was not spawned because subagent use in this runtime requires explicit user authorization. This report was produced inline after checking committed artifacts and running the verification gates listed in frontmatter.
2. Security enforcement is enabled, but no Phase 28 `SECURITY.md` exists. Run `$gsd-secure-phase 28` before advancing if security-gate closure is required.

## Verdict

No blockers or verification gaps remain for APF-05 within Phase 28 scope. The phase is ready for Phase 29 planning, subject to the optional/security-gated `$gsd-secure-phase 28` follow-up.
