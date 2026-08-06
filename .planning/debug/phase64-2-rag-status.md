---
status: diagnosed
trigger: "Phase 64.2 UAT gap: combined invalid-scope, stale-policy-version, invalid-hash RAG input expected invalid_hash but full suite observed no_evidence"
created: 2026-08-06T11:46:34+08:00
updated: 2026-08-06T12:26:22+08:00
---

## Current Focus

hypothesis: CONFIRMED — the failing node is a stale/reduced fixture omitted from the exact-current-validator migration, not a production status-precedence regression
test: completed isolated reproduction, canonical hard-gate comparison, history/blame analysis, direct failing-output inspection, and canonical combined counterfactual
expecting: satisfied — canonical combined input returns invalid_hash with bounded evidence_unavailable plus stale/hash diagnostic reasons
next_action: none — diagnosis artifact validated and ready for parent handoff; no fix in find_root_cause_only mode

## Symptoms

expected: combined invalid-scope, stale-policy-version, invalid-hash input is rejected with the contractually correct bounded status/reason using a canonical fixture; reported expected status is invalid_hash
actual: full-suite execution reported status no_evidence for the exact test node
errors: "tests/agent/test_nodes/test_rag_context_build.py::test_rag_context_build_combined_invalid_scope_stale_policy_version_and_invalid_hash_fail_closed expected invalid_hash, got no_evidence"
reproduction: "UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_rag_context_build.py::test_rag_context_build_combined_invalid_scope_stale_policy_version_and_invalid_hash_fail_closed"
started: observed in Phase 64.2 UAT/full-suite validation; exact introduction time not yet confirmed

## Eliminated

- hypothesis: full-suite state pollution or PostgreSQL ordering changes the result
  evidence: the exact node fails alone with the same no_evidence result in 0.08s and its fake has no database dependency
  timestamp: 2026-08-06T11:52:03+08:00

- hypothesis: production _verified_package_status precedence regressed from invalid_hash to no_evidence
  evidence: source still checks text_hash_mismatch first, all three canonical hard-gate cases pass, and the canonical combined counterfactual returns invalid_hash
  timestamp: 2026-08-06T12:18:57+08:00

- hypothesis: rag_context_build or ContextBuilder overwrites a service-produced invalid_hash status
  evidence: complete call-path reading shows the node passes package.status through; direct execution shows the service itself receives only evidence_unavailable because exact validation stops before the fake row API
  timestamp: 2026-08-06T12:13:42+08:00

## Evidence

- timestamp: 2026-08-06T11:46:34+08:00
  checked: repository worktree state before investigation
  found: existing uncommitted planning artifacts are present; the requested debug file did not exist
  implication: investigation must preserve shared edits and restrict writes to this debug session artifact

- timestamp: 2026-08-06T11:50:45+08:00
  checked: Phase 64.2 UAT and STATE planning context
  found: UAT explicitly classifies the gap as expected invalid_hash versus actual no_evidence after exact current-evidence validation and requires a canonical fixture; STATE.md is stale and still describes Phase 64.2 as unplanned
  implication: the UAT wording itself points to validator/fixture alignment, while STATE.md cannot establish current implementation truth

- timestamp: 2026-08-06T11:50:45+08:00
  checked: debug knowledge base and project skill discovery
  found: no .planning/debug/knowledge-base.md and no project .claude/skills or .agents/skills SKILL.md files exist in this worktree
  implication: there is no known-pattern candidate or additional project skill rule to test first

- timestamp: 2026-08-06T11:50:45+08:00
  checked: complete tests/agent/test_nodes/test_rag_context_build.py
  found: the failing test uses a local _row() fake containing legacy/current policy fields but no explicit exact scope or immutable identity fields; it mixes wrong-tenant, stale-version, mutated-content, and malformed-ref candidates and expects invalid_hash precedence
  implication: a reduced fake row rejected wholesale by a stricter validator is a concrete candidate for why the status collapses to no_evidence

- timestamp: 2026-08-06T11:52:03+08:00
  checked: isolated named test node via UV_CACHE_DIR=/tmp/uv-cache uv run pytest
  found: the node fails deterministically in 0.08s with actual no_evidence versus expected invalid_hash, without PostgreSQL or full-suite state
  implication: cross-test pollution and shared-database ordering are eliminated; the failure is intrinsic to the node's current fixture/code contract

- timestamp: 2026-08-06T11:57:18+08:00
  checked: PolicyKnowledgeService.validate_current_evidence and build_verified_context status mapping
  found: validate_current_evidence returns evidence_unavailable for every ref when the retriever lacks get_current_canonical_evidence_rows_by_keys; it also rejects refs without complete canonical identity and rows without eleven exact identity fields. _verified_package_status maps text_hash_mismatch to invalid_hash before scope/stale, but unknown-only evidence_unavailable falls through to no_evidence.
  implication: the observed no_evidence is the intended fail-closed result for a non-canonical fixture, not evidence that invalid_hash precedence regressed

- timestamp: 2026-08-06T11:57:18+08:00
  checked: failing test's fake/ref construction against canonical service fixtures found by rg
  found: failing FakeCanonicalRetriever exposes only get_canonical_evidence_rows_by_keys and _ref uses EvidenceRefV1.build (legacy ref with all immutable binding fields None); known canonical fixtures use EvidenceRefV1.from_canonical_identity and expose get_current_canonical_evidence_rows_by_keys
  implication: both producer ref shape and retriever capability in the failing node predate the exact current-evidence contract

- timestamp: 2026-08-06T12:01:36+08:00
  checked: complete tests/knowledge/test_verified_evidence_package.py canonical fixture
  found: its _evidence_ref mints PersistedEvidenceIdentityMaterialV1 then projects with EvidenceRefV1.from_canonical_identity; _canonical_row spreads the full identity; its fake implements both legacy canonical and current canonical row methods
  implication: the authoritative unit-test pattern directly supplies all three pieces absent from the failing node fixture

- timestamp: 2026-08-06T12:01:36+08:00
  checked: code diff and recent history for service/node test
  found: worktree product/tests are clean; commit 941a9f7 is named 'fix(64.2): WR-02 validate exact context evidence' and is the latest relevant service change
  implication: this is likely a fixture migration omission introduced by the exact-validator review fix rather than an uncommitted regression

- timestamp: 2026-08-06T12:07:11+08:00
  checked: canonical hard-gate package tests using the required uv entry point
  found: invalid-hash, stale-version, and invalid-scope parametrized cases all pass (3 passed), proving canonical inputs still map text_hash_mismatch to invalid_hash and retain the expected hard-gate behavior
  implication: production diagnostic mapping is not generally regressed; fixture shape differentiates passing versus failing behavior

- timestamp: 2026-08-06T12:07:11+08:00
  checked: git show/blame for commit 941a9f7 and the failing node fixture
  found: commit 941a9f7 changed build_verified_context from get_verified_evidence_details to validate_current_evidence and explicitly migrated test_verified_evidence_package.py to canonical refs/rows/current-row fake. The failing _ref, _row, fake, and combined test remain unchanged from June commits 6451a3d/d493452.
  implication: history directly confirms a missed sibling-fixture migration at the exact production-boundary change

- timestamp: 2026-08-06T12:13:42+08:00
  checked: direct execution of the failing setup outside pytest
  found: status=no_evidence, reason_codes=[evidence_unavailable,candidate_ref_invalid], rejected_count=3, stale_count=0, build_calls=1, and legacy FakeCanonicalRetriever.calls=[]
  implication: validation exits before row retrieval and before the stale/hash classifiers; the no_evidence value is fully explained by fixture incapability

- timestamp: 2026-08-06T12:13:42+08:00
  checked: complete rag_context_build node and ContextBuilder paths plus commit 941a9f7 builder diff
  found: rag_context_build returns package.status unchanged and only appends candidate_ref_invalid; build_verified_context injects the same exact validation result into ContextBuilder, which explicitly does not fall back after evidence_unavailable
  implication: neither node nor builder overwrites invalid_hash; fail-closed exact-validator behavior is intentional and a compatibility fallback would violate the review fix

- timestamp: 2026-08-06T12:18:57+08:00
  checked: in-memory canonicalized counterfactual of the same combined wrong-tenant, stale-version, and mutated-content case
  found: production returned status=invalid_hash, reason_codes=[evidence_unavailable,latest_version_invalid,text_hash_mismatch], rejected=[policy_wrong_tenant,policy_bad_hash], stale=[policy_stale]
  implication: changing only the fixture from legacy/reduced to canonical exact identity restores the expected precedence and proves causation; the bounded invalid-scope reason under exact validation is evidence_unavailable rather than tenant_mismatch

## Fault Tree And Hypotheses

- production status precedence regression: eliminated by _verified_package_status ordering and three passing canonical hard-gate cases
- full-suite state pollution or PostgreSQL ordering: eliminated because the exact node fails alone in 0.08s without database access
- rag_context_build or ContextBuilder overwrites invalid_hash: eliminated by complete call-path reading; both preserve the service package status and ContextBuilder consumes the same validated result without fallback
- stale/reduced node fixture after exact-validator migration: confirmed by runtime call counts, canonical counterfactual, commit diff, and blame

## Files Involved

- tests/agent/test_nodes/test_rag_context_build.py: _ref still uses legacy EvidenceRefV1.build, _row omits immutable identity, FakeCanonicalRetriever lacks the current-row API, and the combined assertion still expects pre-exact tenant_mismatch diagnostics
- src/knowledge/service.py: validate_current_evidence intentionally requires complete canonical refs, the current-row retriever API, and exact row identity; build_verified_context now uses it and status precedence maps text_hash_mismatch to invalid_hash before scope/stale
- src/agent/rag_context/builder.py: exact validation results are consumed without compatibility fallback, preserving fail-closed semantics
- src/agent/nodes/rag_context_build.py: passes package.status through unchanged and only adds candidate_ref_invalid for malformed candidates
- tests/knowledge/test_verified_evidence_package.py: contains the canonical fixture pattern migrated in commit 941a9f7 and proves the production hard-gate mapping remains correct

## Suggested Fix Direction

Update only the stale node test fixture: mint canonical identities and create refs with EvidenceRefV1.from_canonical_identity; include the full identity projection in each fake row; add get_current_canonical_evidence_rows_by_keys to the fake; keep combined expected status invalid_hash; and assert the bounded invalid-scope reason evidence_unavailable instead of the pre-exact tenant_mismatch. Do not restore legacy fallback in production.

## Resolution

root_cause: "Commit 941a9f7 moved PolicyKnowledgeService.build_verified_context onto exact current-evidence validation and migrated canonical service tests, but omitted tests/agent/test_nodes/test_rag_context_build.py. That older fixture still creates legacy refs without immutable bindings, reduced rows, and a retriever without get_current_canonical_evidence_rows_by_keys. Exact validation therefore rejects every candidate as evidence_unavailable before stale/hash checks; _verified_package_status correctly falls through to no_evidence. With canonical inputs, production returns invalid_hash and preserves stale/hash precedence."
fix: "Not applied in diagnose-only mode. Suggested test-only migration is documented above; production behavior should remain unchanged."
verification: "Isolated failing node reproduced: 1 failed with no_evidence. Canonical hard-gate comparison: 3 passed. Direct stale-fixture execution: no_evidence, [evidence_unavailable,candidate_ref_invalid], zero fake row calls. Canonical combined counterfactual: invalid_hash with [evidence_unavailable,latest_version_invalid,text_hash_mismatch]."
files_changed: []
