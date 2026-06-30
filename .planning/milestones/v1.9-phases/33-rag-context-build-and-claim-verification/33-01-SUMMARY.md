---
phase: 33-rag-context-build-and-claim-verification
plan: 33-01
subsystem: knowledge
tags: [rag, claim-verification, pydantic, agent-state, knowledge-service]

requires:
  - phase: 32-intent-graph-migration
    provides: target graph vocabulary and deferred Phase 33 rag_context_build / claim_verify placeholders
provides:
  - KnowledgeService-owned VerifiedEvidencePackageV1, MaterialClaimV1, and ClaimVerificationBundleV1 contracts
  - PolicyKnowledgeService.build_verified_context and verify_claims public boundaries
  - AgentState Phase 33 RAG/claim fields and receive_request per-turn reset lifecycle
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - strict Pydantic public DTOs with ConfigDict(extra="forbid")
    - service-owned RAG context build and claim verification aggregation
    - target MaterialClaimV1 compatibility normalization from legacy authority_class payloads

key-files:
  created:
    - tests/knowledge/test_verified_evidence_package.py
    - tests/knowledge/test_claim_verification_bundle.py
  modified:
    - src/knowledge/schemas.py
    - src/knowledge/service.py
    - src/agent/rag_context/schemas.py
    - src/agent/rag_context/claims.py
    - src/agent/state.py
    - src/agent/nodes/receive_request.py
    - tests/agent/rag_context/test_material_claims.py
    - tests/agent/test_nodes/test_receive_request.py
    - tests/knowledge/test_tenant_scope.py

key-decisions:
  - "KnowledgeService owns build_verified_context and verify_claims as public Phase 33 boundaries."
  - "Phase 33 target DTOs live in src/knowledge/schemas.py; rag_context keeps compatibility adapters for existing MaterialClaim payloads."
  - "No DB schema, migration, new endpoint, or new event type was added; package and bundle data remain Pydantic/state JSON payloads."

patterns-established:
  - "Verified evidence packages separate prompt, verifier, replay, and debug projections."
  - "Claim verification aggregates existing MaterialClaimVerifier results into ClaimVerificationBundleV1 without letting semantic review override hard gates."
  - "receive_request clears all Phase 33 package, claim, bundle, blocked-claim, and safe-ref fields per turn."

requirements-completed: [APF-13, APF-14]

duration: 14min
completed: 2026-06-28
---

# Phase 33 Plan 01: Contracts, State, and Service Boundary Summary

**KnowledgeService-owned verified evidence packages and claim verification bundles with AgentState lifecycle resets.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-28T18:22:28Z
- **Completed:** 2026-06-28T18:36:03Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Added strict public DTOs for `EvidenceItemV1`, `VerifiedEvidencePackageV1`, `MaterialClaimV1`, `ClaimVerificationResultV1`, and `ClaimVerificationBundleV1`.
- Added `PolicyKnowledgeService.build_verified_context(...)` and `PolicyKnowledgeService.verify_claims(...)` using existing `ContextBuilder` and `MaterialClaimVerifier` internals.
- Added Phase 33 `AgentState` fields and `receive_request` reset coverage for stale package, map, claim, bundle, blocked-claim, and support-ref data.
- Added focused tests for hard-gate status mapping, business-fact authority separation, target claim compatibility mapping, and tenant public policy versus merchant-scoped business facts.

## Task Commits

Each TDD task produced RED and GREEN commits:

1. **Task 33-01-01: Add strict KnowledgeService-owned DTOs**
   - `c02cc09` test: add failing tests for RAG claim contracts
   - `4728b40` feat: add strict RAG claim DTO contracts
2. **Task 33-01-02: Declare and reset Phase 33 AgentState fields**
   - `7542e79` test: add failing tests for Phase 33 state reset
   - `5a47c7b` feat: reset Phase 33 RAG claim state fields
3. **Task 33-01-03: Add KnowledgeService build and verify public methods**
   - `3b7ed58` test: add failing tests for KnowledgeService RAG boundary
   - `60d739f` feat: add KnowledgeService RAG verification boundary

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/knowledge/schemas.py` - Adds strict Phase 33 DTOs and exact status/type/route literals.
- `src/knowledge/service.py` - Adds `build_verified_context` and `verify_claims` public service boundaries.
- `src/agent/rag_context/schemas.py` - Re-exports target material-claim compatibility alias.
- `src/agent/rag_context/claims.py` - Adds legacy `authority_class` to target `claim_type` normalization.
- `src/agent/state.py` - Declares Phase 33 package, map, claim, bundle, blocked-claim, and safe-ref fields.
- `src/agent/nodes/receive_request.py` - Resets all new Phase 33 fields at the start of each turn.
- `tests/knowledge/test_verified_evidence_package.py` - Covers strict package DTOs and package hard-gate status mapping.
- `tests/knowledge/test_claim_verification_bundle.py` - Covers strict bundle DTOs and claim verification aggregation.
- `tests/knowledge/test_tenant_scope.py` - Adds tenant public policy versus merchant-scoped business fact authority regression.
- `tests/agent/rag_context/test_material_claims.py` - Covers canonical `MaterialClaimV1` field names and compatibility mapping.
- `tests/agent/test_nodes/test_receive_request.py` - Covers Phase 33 stale state reset and AgentState declarations.

## Decisions Made

- Kept package and bundle persistence out of schema migrations, matching the plan's JSONB/state boundary.
- Used existing `ContextBuilder` projection separation and canonical evidence validation instead of adding a new retrieval path.
- Used existing `MaterialClaimVerifier` for claim-level rules and added only bundle aggregation at the service boundary.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.  
**Impact on plan:** No scope changes.

## Issues Encountered

None. TDD RED failures were expected missing-symbol failures and were resolved by the matching GREEN commits.

## Known Stubs

None. Stub scan found only intentional empty defaults in strict DTO tests and fail-closed empty package/bundle returns; no placeholder UI/data-source stubs were introduced.

## Threat Flags

None. The plan added service methods at an already-modeled KnowledgeService trust boundary and did not add network endpoints, auth paths, file access, DB schema changes, or new event types.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_tenant_scope.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` -> 56 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/knowledge/schemas.py src/knowledge/service.py src/agent/rag_context/schemas.py src/agent/rag_context/claims.py src/agent/state.py src/agent/nodes/receive_request.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_tenant_scope.py tests/agent/rag_context/test_material_claims.py tests/agent/test_nodes/test_receive_request.py` -> passed
- `git diff --check` -> passed

## Next Phase Readiness

Ready for `33-02`: the graph/node plan can call `PolicyKnowledgeService.build_verified_context(...)`, write `rag_context_status`, `verified_evidence_package`, `citation_map`, and `evidence_map`, and route using exact package statuses.

## Self-Check: PASSED

- Verified summary and key created/modified files exist on disk.
- Verified task commits are reachable: `c02cc09`, `4728b40`, `7542e79`, `5a47c7b`, `3b7ed58`, `60d739f`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-28*
