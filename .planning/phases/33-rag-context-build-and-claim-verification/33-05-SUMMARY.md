---
phase: 33-rag-context-build-and-claim-verification
plan: 33-05
subsystem: agent
tags: [rag, claim-verification, langgraph, routing]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: rules-first ClaimVerificationBundleV1 aggregation from PolicyKnowledgeService.verify_claims
provides:
  - runnable claim_verify graph node that is the only writer for claim verification bundle fields
  - deterministic route_after_claim_verify mapping from semantic bundle routes to registered graph keys
  - graph and vocabulary promotion for claim_verify runtime execution
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - claim_verify delegates verification to PolicyKnowledgeService and writes only claim bundle outputs
    - route_after_claim_verify returns only assess_risk_and_approval or final_response
    - legacy verification_route is allow only for verified/not_required continue bundles

key-files:
  created:
    - src/agent/nodes/claim_verify.py
    - tests/agent/test_nodes/test_claim_verify.py
    - .planning/phases/33-rag-context-build-and-claim-verification/33-05-SUMMARY.md
  modified:
    - src/agent/routing.py
    - src/agent/graph.py
    - src/agent/graph_vocabulary.py
    - tests/agent/rag_context/test_routing.py
    - tests/agent/test_graph.py
    - tests/agent/test_graph_vocabulary.py
    - tests/knowledge/test_claim_verification_bundle.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "claim_verify is a narrow graph writer: it calls PolicyKnowledgeService.verify_claims and serializes only claim verification outputs plus compatibility verifier fields."
  - "route_after_recommendation routes material claims, proposed actions, and user-visible claim payloads to claim_verify instead of directly to risk."
  - "route_after_claim_verify sends verified continue bundles to risk only when a proposed action or risk signal exists; answer-only verified bundles go to final_response."

patterns-established:
  - "Claim verification node trace metrics expose status, route, claim count, blocked count, safe ref count, and reason-code count without raw verifier payloads."
  - "Graph vocabulary promotion from deferred_non_runnable to runtime is paired with compiled graph node and edge tests."

requirements-completed: [APF-14]

duration: 11min
completed: 2026-06-29
---

# Phase 33 Plan 05: ClaimVerify Node And RouteAfterClaimVerify Summary

**claim_verify now runs as a registered post-generation graph node and routes verified claim bundles safely to risk or final response.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-28T19:49:12Z
- **Completed:** 2026-06-28T20:00:32Z
- **Tasks:** 2 TDD tasks
- **Files modified:** 10 including validation log and summary

## Accomplishments

- Added `src/agent/nodes/claim_verify.py`, delegating claim verification to `PolicyKnowledgeService.verify_claims(...)` and writing only `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, compatibility verifier fields, and `trace_steps`.
- Added fail-closed node behavior for verifier exceptions/malformed bundles with `overall_status="error"`, `route="final_response"`, and `claim_verify_error`.
- Updated routing so `route_after_recommendation` sends claims/actions to `claim_verify`, while `route_after_claim_verify` never returns semantic bundle route values such as `continue`.
- Registered `claim_verify` in LangGraph and promoted it from `deferred_non_runnable` to runtime/runnable vocabulary.

## Task Commits

Each TDD task was committed atomically:

1. **Task 33-05-01 RED: claim_verify writer node tests** - `e42faae` (test)
2. **Task 33-05-01 GREEN: claim_verify writer node** - `3745ac3` (feat)
3. **Task 33-05-02 RED: claim_verify routing and graph tests** - `adbaebe` (test)
4. **Task 33-05-02 GREEN: graph routing and vocabulary wiring** - `98c62d1` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/nodes/claim_verify.py` - New runnable claim verification graph node with fail-closed error bundle and legacy route/status compatibility fields.
- `src/agent/routing.py` - Added `route_after_claim_verify`, changed recommendation routing to `claim_verify`/`final_response`, and kept route outputs to registered graph keys.
- `src/agent/graph.py` - Registered `claim_verify` and conditional edges from recommendation and claim verification.
- `src/agent/graph_vocabulary.py` - Promoted `claim_verify` to runtime/runnable.
- `tests/agent/test_nodes/test_claim_verify.py` - Node writer, fail-closed, no-write, and authority-boundary tests.
- `tests/agent/rag_context/test_routing.py` - Router tests for recommendation-to-claim verification and claim bundle route mapping.
- `tests/agent/test_graph.py` - Compiled graph and router edge tests for `claim_verify`.
- `tests/agent/test_graph_vocabulary.py` - Runtime/runnable vocabulary tests.
- `tests/knowledge/test_claim_verification_bundle.py` - Added action-recommendation authority negative coverage.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese records for handled TDD RED and GREEN debugging failures.

## Decisions Made

- Kept claim verification orchestration behind `PolicyKnowledgeService.verify_claims`; the node does not assemble verifier internals.
- Preserved current downstream compatibility by writing `verification_route="allow"` only for verified/not-required `continue` bundles, and non-allow routes for blocked/manual/error bundles.
- Treated verified answer-only bundles as final-response paths, not risk/action paths.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project Validation Record] Recorded handled validation failures**
- **Found during:** Task 33-05-01 and Task 33-05-02
- **Issue:** MOCA project rules require local validation failures to be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`; TDD RED failures and GREEN debugging failures occurred during focused verification.
- **Fix:** Added Chinese records for the missing `claim_verify` node RED failure, the test assertion correction, the missing `route_after_claim_verify` RED failure, and graph test compatibility fixes.
- **Files modified:** `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Final plan pytest, ruff, and `git diff --check` passed.
- **Committed in:** `3745ac3`, `98c62d1`

**2. [Rule 3 - Blocking] Updated stale graph test helper**
- **Found during:** Task 33-05-02 GREEN verification
- **Issue:** `tests/agent/test_graph.py` still monkeypatched `generate_recommendation.PolicyKnowledgeService`, but the current Phase 33 node no longer exposes that attribute. The stale helper blocked focused graph verification.
- **Fix:** Changed the monkeypatch to `raising=False` and aligned the policy-QA happy path assertion with the new `claim_verify -> final_response` answer-only route.
- **Files modified:** `tests/agent/test_graph.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_nodes/test_claim_verify.py -q --tb=short` passed.
- **Committed in:** `98c62d1`

---

**Total deviations:** 2 auto-fixed (1 project validation record, 1 blocking test helper).
**Impact on plan:** Both fixes were required to satisfy project workflow and current graph verification; no product scope was added.

## Issues Encountered

- Task 1 RED failed as expected because `src.agent.nodes.claim_verify` did not exist.
- Task 2 RED failed as expected because `route_after_claim_verify` did not exist.
- GREEN verification exposed stale graph test scaffolding and old policy-QA risk-path expectations; both were fixed in the Task 2 GREEN commit.
- Metadata update hit the known Phase 33 `roadmap.update-plan-progress` checkbox mismatch and a flag-style `state.record-metric` parsing issue; ROADMAP/STATE were manually corrected and the incident was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Known Stubs

None. Stub scan found only intentional empty collections/`None` values in test fixtures and fail-closed bundle construction; no UI-rendered or behavior-blocking stubs were introduced.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, DB schema change, or unplanned trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_claim_verify.py tests/agent/rag_context/test_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` -> 101 passed, 22 warnings
- `uv run ruff check src/agent/nodes/claim_verify.py src/agent/routing.py src/agent/graph.py src/agent/graph_vocabulary.py tests/agent/test_nodes/test_claim_verify.py tests/agent/rag_context/test_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py` -> passed
- `git diff --check` -> passed
- Task acceptance greps for node writer behavior, no-write assertions, business/action authority negatives, graph routing, vocabulary promotion, and semantic-route blocking passed.

## TDD Gate Compliance

- RED commit present for Task 33-05-01: `e42faae`
- GREEN commit present after RED for Task 33-05-01: `3745ac3`
- RED commit present for Task 33-05-02: `adbaebe`
- GREEN commit present after RED for Task 33-05-02: `98c62d1`
- Refactor commits not needed.

## Next Phase Readiness

Ready for the next Phase 33 plan: `claim_verify` is runnable, deterministic routing blocks manual/error/unsupported bundles from risk/action paths, and downstream Phase 34 can consume safe bundle refs.

## Self-Check: PASSED

- Verified created files exist on disk: `src/agent/nodes/claim_verify.py`, `tests/agent/test_nodes/test_claim_verify.py`, and this summary.
- Verified task commits are reachable: `e42faae`, `3745ac3`, `adbaebe`, `98c62d1`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-29*
