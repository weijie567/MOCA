---
phase: 57-risk-gate-and-approval-gate-canonicalization
review_loop: 1
reviewer: claude
adjudicator: codex
status: repairs_applied
created_at: "2026-07-07T20:51:49+08:00"
---

# Phase 57 Plan Review Decisions

## Scope

Codex adjudicated the Claude plan review against the Phase 57 plans and current repository evidence. Accepted findings were repaired in `57-01-PLAN.md` through `57-05-PLAN.md`; rejected/contained findings are recorded below so the next review loop can focus on remaining blockers.

## Decisions

| Finding | Decision | Repository Evidence | Repair |
|---|---|---|---|
| 57-01 identity hook may miss legacy writes outside `llm_outputs`/trace. | Accepted. | `src/agent/nodes/assess_risk_and_approval.py` currently has legacy literals in node metadata, `node_errors`, `llm_outputs`, resume checks, and fallback paths. | `57-01` now requires a literal audit and canonical identity coverage for normal, fail-closed, fallback, and error-output paths. |
| 57-01 `read_first` listed `src/agent/nodes/risk_gate.py` before creation. | Accepted. | `src/agent/nodes/risk_gate.py` does not exist yet. | Removed the pre-creation read requirement from Task 2. |
| 57-01 source-literal metadata assertions are brittle. | Accepted as test-design clarification. | Existing code has many legitimate legacy hits that need classification, not blanket deletion. | `57-01` now requires behavioral identity tests plus source-hit classification evidence. |
| `moca.egg-info/SOURCES.txt` may create noisy churn. | Contained. | File exists but is not currently tracked by `git ls-files`. | `57-01` now says to update it only if tracked and otherwise avoid generated egg-info churn. |
| 57-02/57-03 ordering could break approval edit rerisk after graph cutover. | Accepted. | Current `route_after_approval` returns `assess_risk_and_approval`; removing that graph destination before changing edit resume would break rerisk. | Moved minimal new edit `resume_route`, API current-route acceptance, and `route_after_approval` canonicalization into `57-02`. |
| 57-02 included an unnecessary `risk_gate -> risk_gate` self-loop. | Accepted. | Current `route_after_risk(...)` does not return a self-route. | Removed the self-loop from required interfaces and added a no-self-loop instruction unless a tested branch exists. |
| 57-02 Task 1 verification omitted `tests/agent/rag_context/test_routing.py`. | Accepted. | `src/agent/routing.py` current `_CLAIM_VERIFY_ROUTES` and claim route returns still use the legacy route. | Added RAG routing tests to Task 1 verification. |
| 57-03 legacy `resume_route` acceptance could become current authority. | Accepted. | Current graph/API uses the legacy route as the normal edit rerisk path. | `57-03` now restricts legacy route handling to persisted retry reconstruction or an internal server-labeled compatibility branch. |
| 57-03 should reject fresh/current legacy resume payloads and add mismatch negatives. | Accepted. | Current tests include trusted route checks but need canonical/legacy split after cutover. | Added acceptance criteria for fresh legacy rejection and hash/version/run/tenant mismatch negatives. |
| 57-03 static approval-gate checks could false-positive on comments/types. | Accepted. | Static grep-only checks would be too broad for docs/type references. | Scoped checks to production runtime coupling and excluded comments/docs/tests/type-only references. |
| 57-04 API risk payload extraction must preserve historical traces. | Accepted. | Existing `agent_runs.py` extracts risk payloads from `node_name == "assess_risk_and_approval"`; stored traces may still use that node. | `57-04` now requires historical extraction/projection tests instead of optional compatibility. |
| 57-04 frontend edit lacked frontend verification. | Accepted. | `frontend/package.json` has `build`, `test`, and `lint`; plan edits `TimelineStep.tsx`. | Added `npm --prefix frontend run build` to `57-04` verification and success criteria. |
| 57-04 eval/diagnostic scan must catch all current-run lists. | Accepted. | `scripts/eval_agent.py` has multiple places where current node lists/patches may appear. | Expanded static check wording to cover current-run lists, fake keys, patches, imports, and expected sequences. |
| 57-05 doc verification could pass while legacy remains active in diagrams/text. | Accepted. | README and current architecture docs currently show `assess_risk_and_approval` as active/current. | Strengthened doc verification to reject active legacy diagram/route/resume markers. |
| 57-05 static legacy classification lacked concrete scan evidence. | Accepted. | Existing validation file only describes a future classification section. | `57-05` now requires total hit count, per-category counts, path/category rows or summaries, command evidence, and zero `UNCLASSIFIED`. |
| 57-04/57-05 are broad. | No split required after repair. | GSD checker already accepted the five-plan split, and 57-04/57-05 are below the file-surface blocker after the earlier split. | Kept plan boundaries; added stronger verification instead of another split. |

## GSD Plan Checker Loop 1

| Finding | Decision | Repository Evidence | Repair |
|---|---|---|---|
| `57-02` changed approval edit rerisk route but omitted existing ApprovalService tests that still assert `resume_route == "assess_risk_and_approval"`. | Accepted. | `tests/approvals/test_needs_info_resume.py` and `tests/approvals/test_service_transitions.py` contain edit/needs-info service assertions for the legacy route. | Added both files to `57-02` file/read/verify scope and updated `57-VALIDATION.md` / `57-05` full-suite commands. |
| `57-02` changed claim routing but omitted the Phase 33 side-effect-free architecture guard. | Accepted. | `tests/architecture/test_phase33_rag_claim_boundaries.py` allows only `assess_risk_and_approval` or `final_response` for claim routes. | Added the file to `57-02` and required the allowlist to become `{"risk_gate", "final_response"}` while preserving forbidden-snippet assertions. |

## Follow-Up

GSD plan checker Loop 2 passed after the Loop 1 blocker repairs. Claude Review Loop 2 also returned PASS with only non-blocking execution reminders:

- `57-05` execution summary must include actual static scan command evidence, total hit count, and classification results.
- `57-03` should normalize persisted legacy retry to canonical `risk_gate` before graph resume and keep the legacy route only as metadata/historical marker.

Proceed to execution.
