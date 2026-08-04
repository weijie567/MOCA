---
phase: 56
review_loop: 1
review_source: claude
adjudicated_at: "2026-07-07T16:48:11+08:00"
status: repaired
---

# Phase 56 Plan Review Decisions

## Scope

This artifact adjudicates the Claude plan review in `56-REVIEWS.md`. Claude is treated as an external reviewer, not an authority; each actionable finding was checked against Phase 56 context, plans, and current source before repair.

## Source Evidence Checked

- `56-CONTEXT.md`: D-56-01 through D-56-16, especially D-56-06, D-56-10, D-56-11, and D-56-13.
- `src/agent/routing.py`: `_route_after_claim_verify` currently routes to `assess_risk_and_approval` when `_has_proposed_action(state)` is true, even if no action recommendation claim result allows it.
- `src/agent/routing.py`: `route_after_recommendation` already includes material, proposed-action, and user-visible claim gates.
- `src/agent/nodes/final_response.py`: `_verification_route_payload` currently falls back to `rag_verification`, `verification_route`, `verifier_status`, and `verifier_reason_codes` after canonical bundle/package checks.
- `tests/architecture/test_canonical_graph_baseline.py`: current baseline still contains active `generate_recommendation` as pre-Phase-56 evidence; Phase 56 plans own that cutover.
- Phase 50 Documentation Sync Checklist in `50-SPEC.md`: graph node names, route boundaries, and authority semantics must update relevant docs/debt artifacts consistently.

## Decisions

| Finding | Outcome | Evidence / Rationale | Repair |
|---|---|---|---|
| 56-01 refactor may become too broad and change recommendation behavior. | accepted | Plan already intended identity-only refactor, but did not explicitly forbid draft schema, evidence validation, material claim, LLM call-shape, fallback wording, or prompt assembly changes. | `56-01-PLAN.md` now says the refactor is identity-only and forbids those behavior changes. |
| 56-01 legacy wrapper identity needs clearer no-dual-write behavior. | accepted | D-56-04 permits narrow legacy import/test/historical compatibility; active runtime must use canonical identity. | `56-01-PLAN.md` now says canonical callable must not dual-write canonical and legacy `llm_outputs` keys, and legacy identity is direct import/test/historical compatibility only. |
| 56-01 compatibility metadata may duplicate vocabulary metadata. | disagree | Duplication is intentional because the wrapper records local import compatibility while `graph_vocabulary.py` records trace/API projection compatibility. Tests can check exact strings without adding a shared import dependency. | No plan change beyond existing metadata tests. |
| 56-02 route-map tests may only check router return values, not graph path-map destinations. | accepted | Current routing functions can already return `recommendation_generation`; the Phase 56 risk is graph path-map destination still pointing at active legacy `generate_recommendation`. | `56-02-PLAN.md` now requires inspecting active graph path maps / architecture baseline, not only router return values. |
| 56-02 baseline must prove active absence of `generate_recommendation` while preserving Phase 57 row. | accepted | `MIGRATION_MODE_LEGACY_NODE_MAP` currently includes both `generate_recommendation` and `assess_risk_and_approval`; Phase 56 must remove only the former. | `56-02-PLAN.md` now adds acceptance that tests fail on any active conditional edge source `generate_recommendation`. Existing plan already preserves Phase 57 row. |
| 56-03 action route condition is ambiguous. | accepted | Current `_route_after_claim_verify` enters risk when `proposed_action` is present, even without an allowed action claim. D-56-10 requires explicit action-recommendation claim allowance. | `56-03-PLAN.md` now includes a four-row decision table for proposed action, risk signal, and verified action claim combinations. |
| 56-03 `_has_verified_action_recommendation` without proposed action needs a defined boundary. | accepted | Without a proposed action, an allowed action claim alone should not create a risk route unless a separate non-action risk signal exists. | `56-03-PLAN.md` now requires tests for this boundary. |
| 56-03 user-visible non-action claims should stay covered. | accepted | `route_after_recommendation` currently gates `_has_material_claims`, `_has_proposed_action`, and `_has_user_visible_claims`; Phase 56 should not accidentally narrow this to action-only tests. | `56-03-PLAN.md` now requires tests that non-action material/user-visible policy/business claims still route to `claim_verify`. |
| 56-03 RAG route gate overclaims full downstream authority proof. | accepted | Route tests can prove unsafe statuses fail closed before generation/risk paths, but cannot alone prove stale candidate refs never become approval snapshots or risk lowering later. | `56-03-PLAN.md` now scopes this to route-gate proof and leaves broader downstream proof to final closeout/risk-action tests. |
| 56-03 `partial` predicate should use concrete existing fields. | accepted | Current routing has existing fields such as intent, requested operation, risk tier/level, risk signals, proposed action, evidence policy, and verified evidence package. New authority fields would be scope creep. | `56-03-PLAN.md` now lists allowed existing state fields and forbids inventing new routing authority fields. |
| 56-03 schema import direction should stay light. | accepted_as_execution_note | Importing schema vocabulary is acceptable; importing knowledge services or constructing Pydantic models inside router would be too heavy. | Existing plan already limits this to `RAG_CONTEXT_STATUSES`; no extra repair needed. |
| 56-04 `final_response` legacy verifier fallback may become current-run authority. | accepted | `final_response.py` currently falls back to `rag_verification` and `verification_route` fields after canonical checks. D-56-13 says final response should consume safe projections from `verified_evidence_package` and `claim_verification_bundle`; D-56-11 says legacy fields cannot override/bypass canonical bundle. | `56-04-PLAN.md` now requires canonical source priority, forbids legacy fields from creating current-run authority when canonical projections are absent, and adds final-response tests. |
| 56-04 file surface/frontmatter omits Phase 50 checklist docs that Task 3 may update. | accepted | Task 3 already read/inspected those files, but frontmatter only listed a subset. This could mislead execution. | `56-04-PLAN.md` frontmatter now includes the full checklist docs, `.planning/DEFERRED-DECISIONS.md`, `56-04-SUMMARY.md`, and final-response tests. |
| 56-04 safe final wording tests may be brittle. | accepted | Tests should verify route payload/source/reason semantics and sentinel absence, not exact Chinese copy. | `56-04-PLAN.md` now says to assert semantic payload/source/reason fields rather than brittle exact copy. |
| 56-04 current vs historical trace/API projection must preserve implementation node truth. | accepted | Historical `generate_recommendation` traces should target-project to `recommendation_generation` without rewriting original implementation node. | Existing Task 1 already required this; Task 2 wording now repeats it for API/trace tests. |
| 56-04 frontend label may need additional type/snapshot checks. | accepted_as_execution_note | The plan already tells executor to inspect via `rg`; no specific current type file was confirmed beyond `TimelineStep.tsx`. | No extra file added beyond the broader inspect/update requirement. |
| 56-04 `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` is unusual. | disagree | MOCA local rules prefer approved project entrypoints for dev tools; the command is intentionally consistent with Phase 56 validation style. | No change. |

## Repair Summary

- Repaired `56-01-PLAN.md` identity-only refactor and no-dual-write legacy behavior.
- Repaired `56-02-PLAN.md` path-map/source test specificity.
- Repaired `56-03-PLAN.md` action claim decision table, partial predicate field source, user-visible claim coverage, and route-gate proof scope.
- Repaired `56-04-PLAN.md` final-response authority source priority, final-response test coverage, semantic assertions, and full documentation file surface.

## Codex Independent Plan Review Result

Initial independent review after repair found no remaining blocker in plan structure or phase scope:

- CAGM-07 is covered across canonical callable, active graph cutover, RAG/claim fail-closed routing, projection/docs/debt, and final validation.
- Phase 57 `risk_gate` activation and Phase 58 compatibility deletion remain explicitly out of scope.
- The repaired plans use approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` commands and include no bare `pytest` / bare `python -m pytest` validation commands.
- Accepted Claude findings are reflected in plan text or recorded above as execution notes with rationale.

Because the repair changes safety-critical plan semantics for `route_after_claim_verify` and `final_response`, autopilot must rerun Claude plan review before execution.

## Loop 2 Decisions

Claude review loop 2 found no HIGH blocker and assessed the revised phase plan risk as MEDIUM-LOW. One remaining MEDIUM warning was accepted:

| Finding | Outcome | Evidence / Rationale | Repair |
|---|---|---|---|
| 56-04 still did not define how executor distinguishes historical compatibility fallback from current-run authority when canonical projections are absent. | accepted | The existing `src/agent/nodes/final_response.py` fallback reads `rag_verification`, `verification_route`, `verifier_status`, and `verifier_reason_codes`; without a concrete historical marker rule, a current run missing canonical projections could still get a verifier-derived route payload. | `56-04-PLAN.md` now says historical fallback may be used only with an existing persisted-trace or compatibility-projection signal, such as graph vocabulary projection metadata or a historical implementation node. If no reliable historical marker exists, final response must stop constructing authoritative route payloads from legacy verifier fields and leave legacy display compatibility to API/trace projection tests. |

Loop 2 LOW suggestions about exhaustive 56-01 return-path identity tests, mixed `partial` test states, checklist summary table format, and graph grep evidence are accepted as execution notes because the repaired plan already contains the relevant test/summary requirements. No additional plan structure change is needed for those LOW items.

Because the accepted Loop 2 repair is a narrow clarification of the already-added `final_response` authority rule, autopilot should rerun Claude review once more to confirm no remaining actionable warning before execution.

## Loop 3 Result

Claude review loop 3 reported no remaining actionable blocker or warning. It specifically confirmed that the 56-04 historical fallback gating concern is resolved at the plan level:

- current-run authority source priority is explicit;
- legacy verifier fields cannot create current-run authority when canonical projections are absent;
- any retained historical fallback must be gated by an existing historical/compatibility marker and labelled non-authoritative;
- Phase 57 and Phase 58 boundaries remain preserved.

Codex independent review agrees that the repaired plans are ready for execution. Remaining risk is implementation risk, not plan risk.
