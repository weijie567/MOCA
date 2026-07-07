---
phase: 56-recommendation-generation-and-rag-claim-status-alignment
plan: 03
subsystem: rag-claim-routing
tags: [rag, claim-verification, routing, langgraph, canonical-agent-graph]

requires:
  - phase: 56-01
    provides: canonical recommendation_generation callable and legacy compatibility wrapper
  - phase: 56-02
    provides: active graph registration and route maps targeting recommendation_generation
  - phase: 50-canonical-agent-graph-migration-spec-and-guardrails
    provides: canonical graph migration charter and authority matrix
provides:
  - schema-aligned deterministic RAG context status routing
  - fail-closed partial RAG routing for action, risk, and unsafe evidence states
  - claim_verify action route gate requiring explicit allowed action_recommendation claim support
  - regression tests for legacy verifier non-authority and Phase 57 risk-node boundary
affects: [phase-56, phase-56-04, phase-57, phase-58, canonical-agent-graph, rag, claim-verification]

tech-stack:
  added: []
  patterns:
    - router status vocabulary derived from strict knowledge schemas
    - canonical claim bundle as sole action-route authority
    - explicit proposed_action decision table before Phase 57 risk node

key-files:
  created:
    - .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-03-SUMMARY.md
  modified:
    - src/agent/routing.py
    - tests/agent/test_rag_context_routing.py
    - tests/agent/rag_context/test_routing.py
    - .planning/ARCHITECTURE-DEBT.md
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Derived router RAG_CONTEXT_STATUSES from src.knowledge.schemas.RAG_CONTEXT_STATUSES instead of maintaining a duplicate literal set."
  - "Made top-level rag_context_status mandatory for route authority; missing, unknown, malformed, and unsafe statuses fail closed to final_response."
  - "Required explicit allowed action_recommendation claim results before proposed_action can route to assess_risk_and_approval."
  - "Preserved assess_risk_and_approval as the current Phase 57 risk node and did not introduce risk_gate."

patterns-established:
  - "Fail-closed RAG route gate: unsafe evidence statuses and action-bound partial states terminate before generation."
  - "Action claim route gate: proposed actions require canonical bundle success plus allows_action_recommendation=True."
  - "Legacy verifier fields remain compatibility projections and cannot override missing or non-continuing claim_verification_bundle."

requirements-completed: [CAGM-07]

duration: 8min
completed: 2026-07-07
---

# Phase 56 Plan 03: RAG and Claim Route Hardening Summary

**Schema-aligned RAG routing and explicit action-claim gating before the Phase 57 risk node**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-07T09:17:51Z
- **Completed:** 2026-07-07T09:26:34Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `route_after_rag_context` now uses the schema-owned RAG status vocabulary and fails closed for missing, unknown, malformed, unsafe, stale, conflicting, invalid, and build-error states.
- `partial` RAG context can proceed only for deterministic low-risk policy-QA or answer-only flows, and is blocked by proposed actions, action intent/operation, high/approval risk, risk signals, or unsafe package indicators.
- `route_after_claim_verify` now requires explicit allowed `action_recommendation` claim support before a `proposed_action` can reach `assess_risk_and_approval`.
- Legacy verifier fields are tested as non-authoritative and cannot bypass a missing, blocked, or non-continuing canonical claim bundle.
- RAG/claim architecture debt entries were updated with the confirmed defects, fixes, evidence, and remaining Phase 56/57 boundaries.

## Task Commits

1. **Task 1 RED: Add RAG route hardening tests** - `6407bf2` (test)
2. **Task 1 GREEN: Harden RAG context routing** - `429ad98` (feat)
3. **Task 2 RED: Add claim route gate tests** - `b6bbd8f` (test)
4. **Task 2 GREEN: Require allowed action claims before risk routing** - `f24c108` (feat)

## Files Created/Modified

- `src/agent/routing.py` - schema-derived RAG status vocabulary, partial fail-closed predicate, and action-claim route decision table.
- `tests/agent/test_rag_context_routing.py` - exact status coverage, schema/router drift guard, missing/unknown/malformed status tests, and partial action/risk/unsafe evidence matrix.
- `tests/agent/rag_context/test_routing.py` - proposed-action claim gate, non-action risk routing, legacy verifier non-authority, and non-action claim-to-claim_verify tests.
- `.planning/ARCHITECTURE-DEBT.md` - Chinese RAG/claim subsystem entries for the two fixed route-gate defects.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese records for expected TDD RED failures and one GREEN validation bug.

## Decisions Made

- Missing top-level `rag_context_status` no longer inherits authority from `verified_evidence_package.status`; route authority is explicit and fail-closed.
- Allowed action recommendation results without a `proposed_action` do not create a risk route by themselves.
- Non-action risk signals still route to `assess_risk_and_approval`, preserving current Phase 57 behavior.
- `risk_gate` remains out of scope for Phase 56.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed risk_level masking in partial RAG routing**
- **Found during:** Task 1 GREEN verification.
- **Issue:** The first implementation checked `risk_tier` before `risk_level`, so a base `risk_tier="low"` masked `risk_level="approval_required"`.
- **Fix:** Checked `risk_tier` and `risk_level` independently in both partial RAG and risk-signal helpers.
- **Files modified:** `src/agent/routing.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` passed with `55 passed`.
- **Committed in:** `429ad98`

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** No scope change. The fix was required for the planned approval-required partial-routing guard.

## Issues Encountered

- Expected Task 1 RED failure: existing RAG router allowed package-status fallback and action/risk/unsafe partial cases.
- Expected Task 2 RED failure: existing claim router allowed unsupported proposed actions and allowed action claims without proposed actions to reach risk routing.
- During Task 1 GREEN, one validation failure exposed `risk_tier` masking `risk_level`; it was fixed before the task commit.
- One RED test case was corrected before GREEN from an invented `evidence_policy.unsafe_evidence` flag to existing `evidence_policy.risk_level`, preserving the plan rule against new routing authority fields.

## Known Stubs

None. Stub scan hits were ordinary in-memory test helpers, existing router local dict initializations, or historical validation-log text; no runtime placeholder data source was introduced.

## Threat Flags

None. The changed trust boundaries are exactly the planned RAG package -> route gate and claim bundle -> risk route gate surfaces from `T-56-02` through `T-56-05`; no new endpoint, auth path, file access path, or schema boundary was introduced.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` - Task 1 GREEN: `55 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` - Task 2 GREEN: `56 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` - plan-local: `111 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py -q --tb=short` - Wave 2: `273 passed, 1 skipped, 28 warnings`
- Acceptance scripts confirmed the repaired RAG and claim decision tables; `rg -n 'risk_gate' src/agent/routing.py tests/agent/rag_context/test_routing.py` returned no hits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

56-04 can now handle projection/docs/final-response closeout on top of deterministic route gates. Phase 57 still owns `assess_risk_and_approval -> risk_gate`, and Phase 58 still owns final compatibility deletion.

## Self-Check: PASSED

- Found `src/agent/routing.py`.
- Found `tests/agent/test_rag_context_routing.py`.
- Found `tests/agent/rag_context/test_routing.py`.
- Found `.planning/ARCHITECTURE-DEBT.md`.
- Found `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Found `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-03-SUMMARY.md`.
- Found task commits `6407bf2`, `429ad98`, `b6bbd8f`, and `f24c108`.
- Confirmed `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` were not modified.

---
*Phase: 56-recommendation-generation-and-rag-claim-status-alignment*
*Completed: 2026-07-07*
