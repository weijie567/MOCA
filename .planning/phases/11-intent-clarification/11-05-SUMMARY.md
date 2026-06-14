---
phase: 11-intent-clarification
plan: 05
subsystem: eval
tags: [intent, manifest, golden, wilson]
requires:
  - phase: 11-intent-clarification
    provides: Deterministic intent, slot, graph, and clarification helpers
provides:
  - Intent golden dataset and coverage manifest
  - Intent consistency manifest
  - M6 Wilson statistical gate helper
affects: [phase-12-session-memory, phase-13-approval, m6-release]
tech-stack:
  added: []
  patterns: [hash-owned-eval-fixture, release-gate-separation]
key-files:
  created:
    - src/agent/intent_manifest.py
    - tests/agent/test_intent_manifest.py
    - tests/agent/test_intent_golden_contract.py
    - eval/intent/intent-golden.v1.json
    - eval/intent/coverage-manifest.v1.json
    - eval/intent/m6-statistical-gate.v1.json
    - eval/intent/intent-consistency.v1.json
  modified:
    - tests/agent/test_nodes/test_receive_request.py
key-decisions:
  - "intent-golden.v1 is blocking for Phase 11 verification; m6-statistical-gate.v1 is release-blocking only."
  - "Manifest tooling is not imported by runtime routers, graph, classifier, or nodes."
patterns-established:
  - "Coverage metadata is checked against runtime source tables and committed golden cases."
requirements-completed: [INTENT-01, INTENT-02, CLARIFY-01]
duration: 0h 0m
completed: 2026-06-14
---

# Phase 11 Plan 05: Intent Manifest and Golden Gate Summary

**Hash-owned intent golden artifacts and Wilson gate tooling with Phase 11 versus M6 blocking semantics separated**

## Performance

- **Duration:** Inline with Phase 11 execution batch
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added `eval/intent/intent-golden.v1.json`, `coverage-manifest.v1.json`, `m6-statistical-gate.v1.json`, and `intent-consistency.v1.json`.
- Added `src/agent/intent_manifest.py` with strict Pydantic models, canonical hash checking, manifest validation, and one-sided 95% Wilson gate evaluation.
- Added executable golden tests against deterministic pre-router, precedence, route, and required-slot helpers.
- Final validation included `test_receive_request` reset coverage for `intent_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, and `clarification_request`.

## Verification

- `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_clarification_gate.py tests/agent/test_intent_manifest.py tests/agent/test_intent_golden_contract.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py -q` — 131 passed, 3 skipped.
- `uv run pytest tests/knowledge tests/agent/test_tools tests/agent/test_policy_retrieval_ownership.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py tests/test_approval_integration.py tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_clarification_gate.py tests/agent/test_intent_manifest.py tests/agent/test_intent_golden_contract.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py -q --tb=short` — 279 passed, 3 skipped.
- `uv run ruff check src/agent tests/agent` — passed.
- `gsd-sdk query phase-assumptions 11` — unavailable in this SDK (`Unknown command`); deferred-boundary checks were verified with scoped greps and manifest tests instead.

## Planning Hygiene

- **schema/migration owner:** N/A with reason: Phase 11 introduces no database schema, backfill, migration, or persisted read-switch.
- **service/API owner:** N/A with reason: Phase 11 changes backend graph nodes, prompts, schemas, routers, and eval artifacts only; no public API contract changes were introduced.
- **read-switch/fallback/rollback owner:** Phase 11 classifier/router owner. Rollback is by reverting Phase 11 prompt/schema/adapter/router/graph changes as a unit; no runtime read-switch is introduced.
- **eval gate blocking status:** `intent-golden.v1` and `coverage-manifest.v1` are blocking for Phase 11 exit with failure impact `block_phase_11_verification`. `m6-statistical-gate.v1` is release-blocking only with failure impact `block_m6_release_not_phase_11_exit`; insufficient samples remain `statistical_gate_not_demonstrated`.

## Task Commits

Inline execution was used in this runtime, so task-level changes are included in the final Phase 11 scoped commit rather than separate per-task commits.

## Deviations from Plan

Generated the repetitive golden dataset mechanically, then locked hashes with the manifest checker. This does not change runtime scope.

## Issues Encountered

The generated fixture initially used a different hash format than the checker. Hashes were re-locked to the checker-owned canonical JSON format. The broader regression gate also exposed that the approval integration fixture still returned the old intent schema and lacked explicit `action_type`; the fixture and slot schema were updated so legacy approval flows continue to reach the approval gate under the Phase 11 slot policy.

## User Setup Required

None.

## Next Phase Readiness

Phase 11 is ready for code review and verification. Phase 12 can build session CAS/continuity on the fail-closed slot inheritance hook; Phase 13 remains owner of trusted approval lifecycle and needs_info resume.

---
*Phase: 11-intent-clarification*
*Completed: 2026-06-14*
