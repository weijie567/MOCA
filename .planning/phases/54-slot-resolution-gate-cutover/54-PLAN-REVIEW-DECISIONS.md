---
phase: 54
review_source: claude
status: repaired
created: 2026-07-07
---

# Phase 54 Plan Review Decisions

Codex adjudication of `.planning/phases/54-slot-resolution-gate-cutover/54-REVIEWS.md`.

Rule used: Claude review is external input, not authority. Each finding below was checked against Phase 54 context, current plans, and relevant source files before repair.

## Decisions

| ID | Claude Finding | Decision | Evidence | Resolution |
|----|----------------|----------|----------|------------|
| C54-01 | 54-01 has inconsistent LLM failure semantics: must-haves say LLM failure fail-closed, Task 2 allowed accepted inherited slots to continue. | accepted | `54-01-PLAN.md` had strict fail-closed truth plus Task 2 fallback wording. Current `extract_slots` error path returns no active slots. | Repaired 54-01 to require strict `route_decision == "clarification_gate"`, empty `active_slots`, `llm_slot_extraction_error`, and no inherited-slot continuation on LLM validation/timeout/error. |
| C54-02 | Unresolved conflict input shape was not executable. | accepted | Current `active_slot_metadata` is free-form metadata, but no existing field named ambiguous/conflicting exists. | Repaired 54-01 to define exact additive input marker `slot_resolution_conflict={"values":[...],"source":"trusted_session_memory"}` and require normalization into `slot_resolution_trace.conflicting_slots`, not resolved metadata. |
| C54-03 | `receive_request` reset of new slot fields needs focused coverage and active-flow preservation. | accepted | `receive_request` already projects pending required slot flow before resetting ephemeral fields, and tests exist in `tests/agent/test_nodes/test_receive_request.py`. | Repaired 54-01 and validation map to require `test_receive_request` coverage for `slot_resolution_trace` / `missing_required_slots` reset and pending-required-slot `active_flow_state` preservation. |
| C54-04 | `routing.py` may grow into a large resolver/router/blob. | accepted as implementation guidance | Phase 54 context allows deterministic helper factoring at executor discretion. | Repaired 54-01 to prefer small private helpers such as `_collect_current_turn_slots`, `_evaluate_inherited_slots`, and `_build_slot_resolution_trace`. |
| C54-05 | 54-02 Task 1/Task 2 overlap could blur atomic cutover ownership. | accepted partially | 54-02 correctly keeps D-19 cutover in Task 1, but Task 2 touches overlapping test files. | Repaired Task 2 wording: it may only adjust focused smoke/regression assertions and must not modify route constants, graph path maps, intent policy values, or baseline files. |
| C54-06 | 54-02 says “one commit per D-19,” but D-19 requires atomicity, not a commit. | accepted | Plan text contained “one task and one commit.” | Repaired to “one atomic logical patch within this task” and removed “committed intermediate drift” wording. |
| C54-07 | `IntentRouteLiteral` might be widened incorrectly if confused with contextual router allowlist. | accepted as guardrail | `IntentRouteLiteral` is policy initial route surface; `CONTEXTUAL_INTENT_ROUTES` includes fail-closed destinations. | Repaired 54-02 with explicit instruction not to widen `IntentRouteLiteral` to `clarification_gate` solely because contextual route allowlist contains it. |
| C54-08 | 54-02 Task 1 verify should include canonical node tests once graph imports the node. | accepted | Task 1 changes `graph.py` to import/use `slot_resolution_gate`, but its verify omitted `test_slot_resolution_gate.py`. | Repaired 54-02 Task 1 pytest and Ruff commands to include `tests/agent/test_nodes/test_slot_resolution_gate.py`. |
| C54-09 | Legacy migration map “exactly” wording could trigger Phase 58 cleanup. | accepted | Phase 54 owns removal of `extract_slots`, not exact no-debt cleanup. | Repaired 54-02 wording to remove only the Phase 54-owned `extract_slots` row and preserve known later-phase active legacy rows. |
| C54-10 | 54-03 final validation suite misses tests explicitly modified or affected by 54-02. | accepted | `54-02-PLAN.md` includes `test_contextual_intent_resolve.py`; source also has `test_extract_slots.py`, golden contract, and session integration tests relevant to slot route/session behavior. | Repaired `54-03-PLAN.md` and `54-VALIDATION.md` final suite to include `test_receive_request.py`, `test_extract_slots.py`, `test_contextual_intent_resolve.py`, `test_intent_golden_contract.py`, and `test_session_memory_integration.py`. |
| C54-11 | Vocabulary promotion may create duplicate `(legacy_name, kind)` entries or lookup precedence errors. | accepted | Current `graph_vocabulary.py` already contains `slot_resolution_gate` / `route_after_slot_resolution` entries as compatibility aliases. | Repaired 54-03 to require modifying existing entries, uniqueness tests for Phase 54 slot node/router names, and no duplicate entries. |
| C54-12 | Reason-code requirements are too broad/free-text. | accepted partially | Existing plan required many details in reason codes; docs/debt is a better home for detail. | Repaired 54-03 to require minimum stable codes: `PHASE_54_COMPATIBILITY_ALIAS`, `HISTORICAL_TRACE_PROJECTION`, `IMPORT_TEST_COMPATIBILITY`, `DELETE_BY_PHASE_58`; owner/evidence detail can live in docs/debt. |
| C54-13 | API/SSE label change might need broader API tests. | disagree | 54-03 already includes trace/API projection tests plus the specific SSE projection test for node label behavior. No source evidence showed another affected API path requiring a broader DB/API suite in Phase 54 planning. | No plan change. Executor can add local focused API tests if implementation reveals a path gap. |
| C54-14 | Docs/debt verification is mostly text containment. | disagree / residual risk | This is a docs closeout task; exact semantic verification comes from source/test evidence plus final validation artifact. Text containment is a smoke guard, not the only acceptance criterion. | No plan change. Residual risk noted for executor summary. |
| C54-15 | `nyquist_compliant` field may not exist. | false_positive | `54-VALIDATION.md` already has `nyquist_compliant: false` in frontmatter. | No plan change. |
| C54-16 | Static AST scan may be brittle. | disagree / accepted as caution | The static scan is supplementary to graph baseline and focused tests, not the sole proof. | No plan change. Executor should treat baseline/tests as authority if AST scan shape changes. |
| C54-17 | Key link from `slot_resolution_gate.py` to graph vocabulary may be unnecessary before 54-03. | disagree | 54-01 may call `target_graph_name` even while vocabulary status is still compatibility; 54-03 owns runtime promotion. | No plan change. |

## Repair Summary

Files repaired after Claude review:

- `54-01-PLAN.md`: strict LLM error fail-closed semantics, exact unresolved-conflict marker, receive-request reset coverage, helper factoring guidance.
- `54-02-PLAN.md`: removed commit wording, narrowed Task 2 ownership, expanded Task 1 node-test coverage, clarified `IntentRouteLiteral`, removed exact legacy-map cleanup wording.
- `54-03-PLAN.md`: vocabulary uniqueness/minimum reason-code contract and expanded final validation suite.
- `54-VALIDATION.md`: full suite / wave suite / per-task commands aligned with repaired plans.

## Next Gate

Run Codex independent plan review on the repaired plans. Because repairs changed task semantics and verification scope, rerun Claude plan review before execution if Codex independent review finds no further issues.
