---
phase: 09-business-tool-facade
plan: 08
subsystem: verification
tags: [ownership-boundary, regression-guard, re-verification, policy-retrieval]
depends_on: [09-06, 09-07]
requires: []
provides: [ownership-boundary-artifact, executable-ownership-regression]
affects: [verification]
tech_stack:
  added: []
  patterns: [declaration-only-descriptors, ownership-regression-test]
key_files:
  created:
    - tests/agent/test_policy_retrieval_ownership.py
    - .planning/phases/09-business-tool-facade/09-OWNERSHIP-BOUNDARY.md
  modified: []
decisions:
  - "Disposition of verifier expanded claim (Truth #2) as scope conflict, not implementation requirement"
  - "Retrieval descriptors remain declaration-only (adapter=None) in Phase 9 registry"
  - "PolicyKnowledgeService remains the sole live owner of policy retrieval execution"
metrics:
  duration: "5 min"
  completed: "2026-06-13T00:21:04Z"
  tasks: 2
  files: 2
---

# Phase 09 Plan 08: Resolve Ownership Boundary for Re-verification Summary

Durable ownership-boundary artifact and executable regression guard resolving the verifier's expanded single-facade claim against the authoritative Phase 9 goal and locked CONTEXT boundary.

## Tasks Completed

### Task 1: Add executable policy-retrieval ownership regression
**Commit:** `46a847e`
**Files:** `tests/agent/test_policy_retrieval_ownership.py` (330 lines)

Created a focused ownership-contract test module with 18 tests covering:

- **Policy retrieval ownership** (`TestPolicyRetrievalOwnership`): Proves `retrieve_policy_evidence` calls `PolicyKnowledgeService.search` (not `BusinessToolService`), and the module imports `PolicyKnowledgeService` but not `BusinessToolService`.
- **Declaration-only retrieval descriptors** (`TestRetrievalDescriptorsDeclarationOnly`): Proves `search_policy`, `search_sop`, `search_case_memory` exist in the registry as `kind="retrieval"` with `event_family="rag_retrieval_*"` and `resource_type=None`. Invoking them through the registry returns `status="unavailable"` because their adapters are `None`.
- **Executable business-read descriptors** (`TestBusinessReadDescriptorsExecutable`): Proves `get_order`, `get_refund_case`, `get_ticket` retain non-`None` adapters in the default registry composition.
- **Write descriptor blocked** (`TestWriteDescriptorBlocked`): Proves `create_coupon_grant_draft` is hard-blocked before adapter execution.
- **Ownership contract encoding** (`TestOwnershipContractEncoding`): Meta-assertion that the ownership tests never assert policy execution through `BusinessToolService`.

### Task 2: Record authoritative ownership disposition for independent re-verification
**Commit:** `09ea2b5`
**Files:** `.planning/phases/09-business-tool-facade/09-OWNERSHIP-BOUNDARY.md` (134 lines)

Created the durable re-verification contract containing:

- Authoritative Phase 9 goal quoted from ROADMAP
- Locked ownership decision quoted from CONTEXT ("Do NOT own policy knowledge")
- Phase 8 `PolicyKnowledgeService` as the live owner of policy retrieval
- Executable contract table (business reads vs policy retrieval vs retrieval descriptors vs write tools)
- Disposition of the verifier's expanded Truth #2 as an **invalid scope conflict**, not an implementation gap
- References to the two real authorization defects closed by Plans 09-06 and 09-07
- Full Phase 9 regression command and per-plan regression commands for the independent verifier

## Verification Results

- 18/18 ownership regression tests pass
- 101/101 full Phase 9 regression suite passes (9 warnings from pre-existing graph test mocks)
- No changes to protected files (VERIFICATION.md, ROADMAP.md, REQUIREMENTS.md, CONTEXT.md, REVIEW.md)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All tests assert real behavior against existing production code.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:T-09-08-04 | tests/agent/test_policy_retrieval_ownership.py | Executable regression guard for policy retrieval ownership boundary (mitigation for tampering/elevation of privilege) |

---

*Plan: 09-08*
*Completed: 2026-06-13T00:21:04Z*
*Duration: 5 min*
*Tasks: 2/2*
*Files: 2*
