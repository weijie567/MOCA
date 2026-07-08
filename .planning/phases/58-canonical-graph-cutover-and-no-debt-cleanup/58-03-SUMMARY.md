---
phase: 58
plan: 03
name: delete recommendation/risk legacy wrappers
subsystem: agent-graph-recommendation-risk
tags:
  - canonical-graph
  - rag
  - recommendation
  - risk-gate
  - no-debt-cleanup
dependency_graph:
  requires:
    - 58-02
  provides:
    - deleted recommendation/risk legacy wrapper modules
    - canonical-only direct recommendation/risk tests
    - static guard against wrapper recreation
  affects:
    - src/agent/nodes
    - tests/agent
    - tests/architecture
    - scripts/eval_agent.py
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN
    - canonical graph node ownership
key_files:
  created:
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-03-SUMMARY.md
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - scripts/eval_agent.py
    - tests/agent/test_graph.py
    - tests/agent/test_nodes/test_recommendation_generation.py
    - tests/agent/test_nodes/test_risk_gate.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/agent/test_phase22_recommendation_integration.py
    - tests/architecture/test_phase33_rag_claim_boundaries.py
    - tests/conftest.py
    - tests/knowledge/test_facade_integration.py
    - tests/test_graph_routing.py
    - tests/test_interception_rate.py
  deleted:
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/assess_risk_and_approval.py
key_decisions:
  - Delete recommendation/risk compatibility wrappers after 58-02 moved implementation ownership to canonical nodes.
  - Move remaining test and script imports to canonical modules so wrapper deletion does not leave broken collection paths.
  - Keep historical legacy node-name strings only where tests assert absence from runtime identity surfaces or replay historical payloads.
metrics:
  started_at: 2026-07-08T01:34:00Z
  completed_at: 2026-07-08T01:44:24Z
  duration: 10m25s
  tasks_completed: 1
  files_changed: 15
---

# Phase 58 Plan 03: Delete Recommendation/Risk Legacy Wrappers Summary

Recommendation/risk legacy wrapper modules were deleted, direct tests now target canonical modules only, and the Phase 58 static guard prevents wrapper recreation.

## Outcome

Plan 58-03 completed the canonical graph cutover for recommendation generation and risk gate ownership:

- Deleted `src/agent/nodes/generate_recommendation.py`.
- Deleted `src/agent/nodes/assess_risk_and_approval.py`.
- Updated direct recommendation/risk tests so they no longer import or patch deleted wrapper modules.
- Tightened `tests/architecture/test_phase33_rag_claim_boundaries.py` to assert the wrappers and legacy direct test files stay deleted and compatibility markers do not reappear under active node/test surfaces.
- Migrated remaining affected tests and `scripts/eval_agent.py` imports/calls to canonical `recommendation_generation` and `risk_gate` modules.
- Added the required Chinese architecture-debt ledger entry closing the recommendation/risk wrapper debt.

## Commits

| Commit | Type | Description |
| ------ | ---- | ----------- |
| `30ad924` | RED | `test(58-03): add failing wrapper deletion guards` |
| `56f6e26` | GREEN | `feat(58-03): delete recommendation and risk legacy wrappers` |

## TDD Gate Compliance

- RED gate passed: focused tests failed before implementation because the wrapper files still existed.
- GREEN gate passed: focused tests passed after deleting wrappers and moving imports to canonical modules.
- Refactor gate: not needed; no behavior-neutral cleanup commit was required.

## Verification

| Command | Result |
| ------- | ------ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` | RED before implementation: `1 failed, 60 passed, 1 warning`; GREEN after implementation: `61 passed, 1 warning in 0.35s` |
| `test ! -e src/agent/nodes/generate_recommendation.py && test ! -e src/agent/nodes/assess_risk_and_approval.py && test ! -e tests/agent/test_nodes/test_generate_recommendation.py && test ! -e tests/agent/test_nodes/test_assess_risk_and_approval.py` | Passed |
| `if rg -n "src\.agent\.nodes\.generate_recommendation" tests/agent/test_nodes/test_recommendation_generation.py; then exit 1; fi` | Passed |
| `if rg -n "src\.agent\.nodes\.assess_risk_and_approval" tests/agent/test_nodes/test_risk_gate.py; then exit 1; fi` | Passed |
| `if rg -n "DELETE_BY_PHASE_58|PHASE_56_COMPATIBILITY_ALIAS|PHASE_57_COMPATIBILITY_ALIAS" src/agent/nodes tests/agent/test_nodes; then exit 1; fi` | Passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` | Passed: `active_runtime_legacy: 0`, `current_docs_legacy_authority: 0`, `unclassified_rows: 0`, `total_hits: 935`, `files: 92` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --collect-only tests/agent/test_graph.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_recommendation_integration.py tests/conftest.py tests/knowledge/test_facade_integration.py tests/test_graph_routing.py tests/test_interception_rate.py -q` | Passed: `150 tests collected in 0.22s`, 1 warning |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -m py_compile scripts/eval_agent.py` | Passed |
| `git diff --check` | Passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Migrated broader imports after wrapper deletion**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** The plan listed direct node tests and static guards, but deleting the wrappers would leave broader tests and `scripts/eval_agent.py` importing removed modules.
- **Fix:** Moved affected imports/calls to canonical `recommendation_generation` and `risk_gate` modules.
- **Files modified:** `scripts/eval_agent.py`, `tests/conftest.py`, `tests/agent/test_graph.py`, `tests/agent/test_phase22_action_boundary.py`, `tests/agent/test_phase22_recommendation_integration.py`, `tests/knowledge/test_facade_integration.py`, `tests/test_graph_routing.py`, `tests/test_interception_rate.py`.
- **Commit:** `56f6e26`

**2. [Rule 2 - Project Rule] Recorded closed subsystem architecture debt**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** MOCA project rules require a Chinese `.planning/ARCHITECTURE-DEBT.md` entry when tool/RAG/memory/intent subsystem debt is fixed or closed.
- **Fix:** Added a Phase 58-03 entry documenting deletion of recommendation/risk compatibility wrappers, verification, evidence, and remaining risks.
- **Files modified:** `.planning/ARCHITECTURE-DEBT.md`
- **Commit:** `56f6e26`

## Known Stubs

None that affect the plan goal. Stub-pattern scan hits in modified files were existing test fixtures and optional/default model values such as empty lists, empty dicts, and `None` fields; no UI/runtime placeholder data source was introduced.

## Threat Flags

None. This plan deleted compatibility modules and updated tests/imports only; it did not add network endpoints, auth paths, file-access boundaries, schema changes, or new trust-boundary behavior.

## Local Validation Notes

No MOCA local validation/debug issue was encountered that required a `.planning/LOCAL-VALIDATION-ISSUES.md` entry. The only failing test was the intentional RED TDD gate.

## Shared State

Per orchestration instruction, this plan did not update `STATE.md`, `ROADMAP.md`, or `REQUIREMENTS.md`, and did not run GSD state mutation commands.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-03-SUMMARY.md`.
- RED commit `30ad924` exists in git history.
- GREEN commit `56f6e26` exists in git history.
- Intentional GREEN deletions were limited to `src/agent/nodes/generate_recommendation.py` and `src/agent/nodes/assess_risk_and_approval.py`.
