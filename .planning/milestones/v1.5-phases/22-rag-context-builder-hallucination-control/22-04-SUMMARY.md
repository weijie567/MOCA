---
phase: 22-rag-context-builder-hallucination-control
plan: "04"
subsystem: rag-context
tags: [rag-context, material-claim, verifier, hallucination-control, pytest]

# Dependency graph
requires:
  - phase: 22-03-context-builder-evidence-validation
    provides: "Strict RagContextBundle DTOs, active citation map, verifier context, business fact refs, and canonical evidence validation."
provides:
  - "Strict MaterialClaim DTOs for policy, business fact, and action recommendation authority classes."
  - "Deterministic Level 1 bundle/authority gates and Level 2 lexical/span support outcomes."
  - "Budgeted fake-provider-testable Level 3 semantic verifier with timeout/error/malformed/budget fail-closed behavior."
affects: [phase-22, material-claim, verifier, authority-boundaries, semantic-verifier]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Material claims are separate DTOs and do not mutate EvidenceRefV1 or business fact identity contracts."
    - "Verifier results expose typed outcomes, reason codes, metrics, and safe refs only."
    - "Level 3 semantic verification is provider-injected, budgeted, deterministic-testable, and fail-closed by default."

key-files:
  created:
    - src/agent/rag_context/claims.py
    - src/agent/rag_context/verifier.py
    - .planning/phases/22-rag-context-builder-hallucination-control/deferred-items.md
  modified:
    - src/agent/rag_context/schemas.py
    - src/agent/rag_context/__init__.py

key-decisions:
  - "Kept MaterialClaim and verifier metadata outside EvidenceRefV1 and BusinessFactRefV1 identity DTOs."
  - "Accepted successful or partial-success ToolResultV2 business_fact_refs as trusted business authority while failed tool results remain non-authority."
  - "Kept Level 3 tests provider-injected with no live model, network, or credential requirement."

patterns-established:
  - "Level 1 membership and authority checks run before any support result can become supported."
  - "Level 2 lexical support returns typed outcomes and keeps citation membership distinct from support."
  - "Semantic verifier outputs are redacted and never include raw prompts, private reasoning, or source internals."

requirements-completed:
  - CLM-01
  - CLM-02
  - CLM-03
  - CLM-04
  - CLM-05
  - VER-01
  - VER-02
  - VER-03
  - VER-04
  - VER-05
  - VER-06
  - BND-03
  - BND-04

# Metrics
duration: 10 min
completed: 2026-06-19
---

# Phase 22 Plan 04: Material Claims and Verifier Tiers Summary

**Typed MaterialClaim authority contracts with deterministic Level 1/2 support checks and budgeted fail-closed semantic verification**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-19T09:36:40Z
- **Completed:** 2026-06-19T09:46:46Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added strict `MaterialClaim` contracts and dependency-map helpers for policy, business fact, and action recommendation claims.
- Added `MaterialClaimVerifier` with Level 1 bundle/authority checks, Level 2 lexical/span support outcomes, and authority-boundary fail-closed behavior.
- Added `SemanticSupportVerifier` with explicit D-16 budgets, provider injection for deterministic fakes, timeout/error/malformed/budget fail-closed outcomes, and redacted result surfaces.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement MaterialClaim DTOs and dependency helpers** - `d41c662` (feat)
2. **Task 2: Implement deterministic Level 1 and Level 2 verification** - `88f2b75` (feat)
3. **Task 3: Implement risk-triggered Level 3 semantic verification** - `69e25b8` (feat)

**Plan metadata:** final docs commit.

## Files Created/Modified

- `src/agent/rag_context/claims.py` - MaterialClaim normalization and claim dependency-map projection helpers.
- `src/agent/rag_context/verifier.py` - Level 1/2 claim verifier plus Level 3 semantic verifier config, trigger policy, budget enforcement, and fail-closed result DTOs.
- `src/agent/rag_context/schemas.py` - Strict MaterialClaim, authority-class, and verifier-status DTOs.
- `src/agent/rag_context/__init__.py` - Public exports for claim and verifier APIs.
- `.planning/phases/22-rag-context-builder-hallucination-control/deferred-items.md` - Logs the existing 22-05-owned routing RED tests discovered by a broader verification command.

## Decisions Made

- Kept claim/verifier metadata in `src.agent.rag_context` DTOs only; `EvidenceRefV1`, `BusinessFactRefV1`, and `ToolResultV2` identity fields were not changed.
- Treated `BusinessFactRefV1` from active bundle context and safe successful/partial-success `ToolResultV2` values as business authority; policy evidence, memory, provenance, and model knowledge remain non-authority.
- Left deterministic route mapping to Plan 22-05; Plan 22-04 emits typed verifier outcomes and reason codes only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired GSD metadata handler output**
- **Found during:** Metadata update after Task 3
- **Issue:** `roadmap.update-plan-progress` did not match the current roadmap table format, and `state.record-session` reset stale milestone labels in `STATE.md`.
- **Fix:** Manually repaired the Phase 22 plan count, Plan 22-04 roadmap checkbox, current/next step text, milestone labels, and requirement traceability statuses.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Reviewed the metadata diff and confirmed it is scoped to Plan 22-04 progress; unrelated dirty `study_plan/deep-research-report (1).md` remains unstaged.
- **Committed in:** final docs commit.

---

**Total deviations:** 1 auto-fixed (1 blocking metadata issue).
**Impact on plan:** Runtime implementation scope is unchanged; metadata now reflects Plan 22-04 completion.

## Issues Encountered

- The local GSD roadmap handler returned `updated: false` for the current roadmap format. The affected status lines were repaired before final commit.
- Broader `uv run pytest tests/agent/rag_context -q` still fails on `tests/agent/rag_context/test_routing.py` because `src.agent.rag_context.routing` is not implemented. This is out of scope for 22-04 and explicitly deferred to Plan 22-05 in `deferred-items.md`.

## Verification

- `uv run pytest tests/agent/rag_context/test_material_claims.py -q` - passed, 3 tests.
- `uv run pytest tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/knowledge/test_citation_membership.py -q` - passed, 19 tests.
- `uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_leakage.py -q` - passed, 17 tests.
- `uv run pytest tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_leakage.py tests/knowledge/test_citation_membership.py -q` - passed, 39 tests.
- `uv run ruff check src/agent/rag_context tests/agent/rag_context` - passed.
- `uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_phase21_boundaries.py tests/agent/context/test_budget.py -q` - passed, 27 tests.

## Known Stubs

None. Stub scan found typed optional defaults and local list initializers only; no TODO/FIXME markers, placeholder text, UI-flowing empty data, or unwired production stubs were introduced.

## Authentication Gates

None.

## Threat Flags

None. This plan added verifier DTOs/services inside the threat model already documented in 22-04; no new network endpoint, auth path, file access pattern, database schema, or external provider requirement was introduced.

## User Setup Required

None - no external service configuration required.

## Deferred Issues

- `tests/agent/rag_context/test_routing.py` remains RED until Plan 22-05 implements `src.agent.rag_context.routing`.

## Next Phase Readiness

Ready for Plan 22-05. The verifier now emits typed outcomes, reason codes, safe refs, and redacted metrics that deterministic routing can consume without relying on model-selected routes.

## Self-Check: PASSED

- Summary file exists.
- Key created/modified files exist.
- Task commits found: `d41c662`, `88f2b75`, `69e25b8`.

---
*Phase: 22-rag-context-builder-hallucination-control*
*Completed: 2026-06-19*
