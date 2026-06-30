---
phase: 33-rag-context-build-and-claim-verification
plan: 33-02
subsystem: agent-graph
tags: [rag, claim-verification, langgraph, routing, prompt-safety]

requires:
  - phase: 33-rag-context-build-and-claim-verification
    provides: KnowledgeService-owned VerifiedEvidencePackageV1 contracts and build_verified_context boundary
  - phase: 32-intent-graph-migration
    provides: target graph vocabulary and graph projection conventions
provides:
  - runnable rag_context_build node that writes rag_context_status, verified_evidence_package, citation_map, and evidence_map
  - deterministic route_after_rag_context router over all ten RAG context statuses
  - graph and vocabulary promotion for rag_context_build as a runtime node
  - working-state projection that rejects candidate-only policy evidence refs
affects: [phase-33, phase-34-approval-action, phase-35-replay-eval]

tech-stack:
  added: []
  patterns:
    - TDD RED/GREEN commits for graph node, router, and projection boundary changes
    - fail-closed deterministic routing before recommendation generation
    - prompt-safe working-state refs sourced only from verified evidence packages

key-files:
  created:
    - src/agent/nodes/rag_context_build.py
    - tests/agent/test_nodes/test_rag_context_build.py
    - tests/agent/test_rag_context_routing.py
  modified:
    - src/agent/routing.py
    - src/agent/graph.py
    - src/agent/graph_vocabulary.py
    - src/agent/working_state.py
    - src/agent/state.py
    - tests/agent/test_graph.py
    - tests/agent/test_graph_vocabulary.py
    - tests/agent/rag_context/test_leakage.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "rag_context_build is the sole graph node writer for RAG package/status/map fields and delegates canonical validation to PolicyKnowledgeService.build_verified_context."
  - "route_after_rag_context is total, side-effect-free, and fail-closed for malformed state and hard package statuses."
  - "WorkingState retrieved evidence refs are projected only from verified_evidence_package evidence_map for verified or allowed partial packages."
  - "Phase 33 AgentState DTO imports must exist at runtime because LangGraph resolves TypedDict annotations with get_type_hints."

patterns-established:
  - "Candidate policy refs are inputs only until the verified package boundary promotes them."
  - "Routers expose finite graph edge keys and avoid service, repository, retrieval, tool, or LLM calls."
  - "Graph vocabulary runtime status must match actual graph node registration."

requirements-completed: [APF-13]

duration: 19min
completed: 2026-06-28
---

# Phase 33 Plan 02: RAG Context Build and Routing Summary

**Runnable RAG context build node with verified-package routing and no-leak working-state evidence projection.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-06-28T18:42:20Z
- **Completed:** 2026-06-28T19:00:45Z
- **Tasks:** 3
- **Files modified:** 12 including validation log, excluding this summary

## Accomplishments

- Added `rag_context_build` as a package/status/map writer node that validates candidate `EvidenceRefV1` values and calls `PolicyKnowledgeService.build_verified_context(...)`.
- Added deterministic `route_after_rag_context` routing over exact RAG context statuses, with fail-closed behavior for malformed and unsafe package states.
- Wired `rag_context_build` into the LangGraph runtime, promoted its graph vocabulary entry to runtime/runnable, and kept `claim_verify` deferred.
- Hardened `WorkingState` so candidate-only `policy_evidence`, `retrieved_evidence.evidence_refs`, and `evidence_refs` do not become prompt-safe retrieved evidence refs.

## Task Commits

Each TDD task produced RED and GREEN commits:

1. **Task 33-02-01: Implement rag_context_build writer node**
   - `6451a3d` test: add failing tests for rag context build node
   - `d493452` feat: implement rag context build node
2. **Task 33-02-02: Add deterministic route_after_rag_context**
   - `45cef0c` test: add failing tests for rag context routing
   - `532d98e` feat: add deterministic rag context routing
3. **Task 33-02-03: Wire graph, vocabulary, and no-leak package projection**
   - `6bbfa2a` test: add failing tests for rag context projection
   - `7c0ec51` feat: wire rag context projection boundaries

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agent/nodes/rag_context_build.py` - Adds the RAG package build node, candidate validation, trusted context extraction, service dispatch, and fail-closed package creation.
- `src/agent/routing.py` - Adds RAG status literals, finite RAG route keys, `route_after_rag_context`, and investigate handoff to `rag_context_build`.
- `src/agent/graph.py` - Registers `rag_context_build` and its conditional edge mapping into generation, clarification, or final response paths.
- `src/agent/graph_vocabulary.py` - Promotes `rag_context_build` from deferred/non-runnable to runtime/runnable.
- `src/agent/working_state.py` - Projects retrieved evidence refs only from verified or partial verified evidence packages.
- `src/agent/state.py` - Makes Phase 33 DTO types available at runtime for LangGraph annotation resolution.
- `tests/agent/test_nodes/test_rag_context_build.py` - Covers node writer fields, candidate validation, service invocation, invalid scope/version/hash cases, and fail-closed service errors.
- `tests/agent/test_rag_context_routing.py` - Covers all ten RAG statuses and route containment.
- `tests/agent/test_graph.py` - Covers graph registration, edge mappings, and runtime graph behavior through the package build node.
- `tests/agent/test_graph_vocabulary.py` - Covers runtime vocabulary projection for `rag_context_build`.
- `tests/agent/rag_context/test_leakage.py` - Covers candidate-only evidence rejection and verified package evidence projection.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Records local validation issues found and resolved during execution.

## Decisions Made

- Used `PolicyKnowledgeService.build_verified_context(...)` as the only promotion boundary for candidate policy evidence instead of adding retrieval or repository orchestration inside the graph node.
- Kept `partial` package routing conservative: only low-risk answer paths with no proposed action can reach generation.
- Kept working-state candidate evidence fallbacks removed even when legacy `policy_evidence` or `retrieved_evidence.evidence_refs` are present, so ordinary prompt surfaces require the verified package boundary.
- Made Phase 33 AgentState DTO imports runtime-visible because LangGraph resolves `TypedDict` annotations while building the graph.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made Phase 33 AgentState DTO imports runtime-visible**
- **Found during:** Task 33-02-02 (Add deterministic route_after_rag_context)
- **Issue:** `tests/agent/test_graph.py` failed during `StateGraph(AgentState)` construction because LangGraph could not resolve `VerifiedEvidencePackageV1` from `TYPE_CHECKING`-only imports.
- **Fix:** Moved `ClaimVerificationBundleV1`, `EvidenceRefV1`, `MaterialClaimV1`, and `VerifiedEvidencePackageV1` imports in `src/agent/state.py` to runtime imports.
- **Files modified:** `src/agent/state.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/agent/test_graph.py -q --tb=short`
- **Committed in:** `532d98e`

**2. [Rule 3 - Blocking] Wired graph edge during Task 33-02-02 verification**
- **Found during:** Task 33-02-02 (Add deterministic route_after_rag_context)
- **Issue:** `route_after_investigate` correctly returned `rag_context_build`, but the graph mapping was originally scheduled for Task 33-02-03; the Task 33-02-02 graph test gate failed with `KeyError: 'rag_context_build'`.
- **Fix:** Added `rag_context_build` graph node registration, investigate edge mapping, RAG context conditional edges, and graph test service injection in the Task 33-02-02 GREEN commit.
- **Files modified:** `src/agent/graph.py`, `tests/agent/test_graph.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/agent/test_graph.py -q --tb=short`
- **Committed in:** `532d98e`

---

**Total deviations:** 2 auto-fixed (2 blocking).  
**Impact on plan:** Both fixes were required to satisfy the plan's own verification gates. No new feature scope was added.

## Issues Encountered

- A stray patch footer initially landed in `tests/agent/test_nodes/test_rag_context_build.py`; it was removed before the Task 33-02-01 GREEN commit and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Ruff caught unused `datetime` imports in the new Task 33-02-01 tests; the imports were removed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- TDD RED failures were expected missing-behavior failures and were resolved by the matching GREEN commits.

## Known Stubs

None. Stub scan found only intentional test fixture defaults, typed optional defaults, and empty fail-closed package/map fields; no unresolved placeholder text, mock-only data source, or UI-facing stub was introduced.

## Threat Flags

None. No unplanned network endpoint, auth path, file access pattern, DB schema change, or new trust boundary was introduced beyond the plan's modeled `investigate -> rag_context_build -> recommendation_generation` graph boundary.

## User Setup Required

None - no external service configuration required.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_rag_context_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` -> 103 passed, 22 warnings
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/rag_context_build.py src/agent/routing.py src/agent/graph.py src/agent/graph_vocabulary.py src/agent/working_state.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_rag_context_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/rag_context/test_leakage.py` -> passed
- `git diff --check` -> passed

## Next Phase Readiness

Ready for the next Phase 33 plan: RAG context packages are now built before recommendation generation, graph routing is finite and fail-closed, and ordinary working-state evidence projection requires verified package refs.

## Self-Check: PASSED

- Verified summary and key created/modified files exist on disk.
- Verified task commits are reachable: `6451a3d`, `d493452`, `45cef0c`, `532d98e`, `6bbfa2a`, `7c0ec51`.

---
*Phase: 33-rag-context-build-and-claim-verification*
*Completed: 2026-06-28*
