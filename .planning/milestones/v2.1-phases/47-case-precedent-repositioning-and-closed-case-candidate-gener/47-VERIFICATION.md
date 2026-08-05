---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
verified: 2026-07-03T15:38:26Z
status: passed
score: "6/6 must-haves verified"
overrides_applied: 0
---

# Phase 47: Case Precedent Repositioning and Closed-Case Candidate Generation Verification Report

**Phase Goal:** Reposition `case_memories` as reviewed closed-case precedent, not active case state, and introduce a governed candidate-generation path from finalized Case Working Context into the existing reviewed memory workflow when a case closes.
**Verified:** 2026-07-03T15:38:26Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

Phase 47 achieved its goal. The current codebase keeps `case_memories` as the existing reviewed precedent store, adds a trusted closed-case CWC projection seam, submits generated candidates through the existing case-memory review/audit/dedupe/PII path, keeps pending candidates hidden from reviewed retrieval until approval, and preserves DEFER-3 as Phase 48 scope.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `case_memories` semantics are documented and test-locked as reviewed case precedent, not active working state and not a replacement for `case_working_contexts`. | VERIFIED | `docs/contract-spec.md:1521-1527`, `docs/current-implementation-map.md:38-39`, and `docs/architecture-overview.md:486-497` state the split. `tests/memory/test_phase47_case_precedent_alignment.py:38-62` locks the contract and storage identity. |
| 2 | A closed-case candidate generation boundary is designed from finalized CWC content into the governed memory candidate/review flow, preserving `needs_review`, audit event, PII, tenant, source-ref, and reviewer semantics. | VERIFIED | `src/memory/case_precedent.py:72-129` reads terminal trusted close inputs, tenant-bound refund case, active CWC, and calls `CaseMemoryService.submit_case_memory_candidate(...)`; `src/memory/case_memory.py:490-620` handles review-required write events, duplicate checks, and PII skip events. Tests cover needs-review rows, source refs, policy refs, duplicate handling, PII skip, pending list, approval, and review API behavior. |
| 3 | Retrieval is metadata-first where applicable; vector search remains optional and does not become the only route for exact tenant/case/merchant scoped precedent retrieval. | VERIFIED | `src/memory/case_memory.py:409-438` uses text/metadata filtering when `query_embedding is None`; vector path is only selected when an embedding is supplied. `tests/memory/test_case_memory_retrieval.py:516-689` proves merchant and exact case retrieval with `query_embedding=None`. |
| 4 | Candidate generation keeps claims/facts/policy refs separated and never stores policy body text, raw tool payloads, approval/action authority bodies, replay/debug blobs, or sensitive raw PII. | VERIFIED | `src/memory/case_precedent.py:239-253` labels request, claims, verified facts, actions, recommendations, and commitments separately; policy refs are mapped to `doc_key/chunk_id/policy_version` at lines 221-236; forbidden markers are stripped at lines 302-311; sensitive/prohibited CWC PII creates a fixed non-sensitive blocked candidate at lines 168-187. Tests cover separation, refs-only policy mapping, forbidden marker removal, and blocked PII. |
| 5 | No destructive rename/drop of `case_memories`, `long_term_memories`, `case_working_contexts`, or `conversation_threads.case_id` occurs. | VERIFIED | ORM still declares `long_term_memories`, `case_memories`, `case_working_contexts`, and `ConversationThread.case_id` at `src/db/models.py:438`, `508`, `583`, and `1225`. There is no Phase 47 migration; migration list still ends at `022_case_working_context.py`. Static guard `tests/memory/test_phase47_case_precedent_alignment.py:52-107` checks protected tables and destructive operation patterns. |
| 6 | DEFER-3 remains out of scope and is carried forward by name. | VERIFIED | `.planning/MEMORY-REDESIGN-DECISIONS.md:107`, `.planning/ROADMAP.md:253-265`, and `.planning/REQUIREMENTS.md:40,72` keep narrow long-term explicit preference memory as MEM-05 / Phase 48. Phase 47 docs also state Phase 48 only at `docs/architecture-overview.md:488,495,497`. `MemoryWriteService.propose_candidates(...)` still defaults to `{"session"}` at `src/memory/write_service.py:56-67`; no Phase 47 explicit-preference generation path was added. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/memory/test_phase47_case_precedent_alignment.py` | Static semantic, red-line, command, source-ref, tool-context guards | VERIFIED | Exists, substantive, and passed in the focused suite. |
| `src/memory/schemas.py` | `CaseMemorySourceType` includes `closed_case_cwc_candidate` | VERIFIED | Source type is present at lines 263-275; write candidate schema remains case-memory scoped. |
| `src/memory/policy.py` | `closed_case_cwc_candidate` is review-required only | VERIFIED | It is in `REVIEW_REQUIRED_CASE_SOURCE_TYPES` at lines 77-88 and absent from `AUTO_APPROVED_CASE_SOURCE_TYPES` at lines 71-76. |
| `src/memory/case_precedent.py` | Trusted closed-case CWC-to-case-memory candidate service | VERIFIED | Implements terminal status allowlist, tenant/CWC reads, scope resolution, projection, PII block, and existing service submission. |
| `src/repositories/refund_repo.py` | Tenant-bound `RefundCase` lookup with order merchant | VERIFIED | `get_by_id_with_order(...)` uses `selectinload(RefundCase.order)` and tenant/case filters. |
| `tests/memory/test_case_precedent_generation.py` | Projection, skip, dedupe, PII, review lifecycle tests | VERIFIED | Covers non-terminal skips, missing case/CWC, merchant scope, source refs, dedupe, PII skip, pending hidden until approval, and projection safety. |
| `tests/memory/test_case_memory_retrieval.py` | Metadata/text retrieval without embeddings | VERIFIED | Generated merchant and exact case retrieval tests use `query_embedding=None` and filter wrong tenant/scope/status/PII/tombstone. |
| `tests/memory/test_reviewed_memory_context_boundary.py` | Reviewed context boundary for approved generated precedents | VERIFIED | Approved `closed_case_cwc_candidate` is returned through reviewed memory context after approval. |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | Reviewed-memory node issue_type behavior | VERIFIED | Regression proves `issue_type` drives `case_type`, not `primary_intent`. |
| `tests/tools/test_catalog.py` / `src/tools/contracts.py` | Tool context stays case-id-free | VERIFIED | `ToolCallContext` has no `case_id`; static guard checks executor uses tenant/user/thread/merchant scope only. |
| `docs/*` and `.planning/MEMORY-REDESIGN-DECISIONS.md` | Contract/current map/architecture/DEFER alignment | VERIFIED | Phase 47 delivery text is present; DEFER-3 remains Phase 48. |

`gsd-sdk query verify.artifacts` passed all declared artifacts across 47-01 through 47-04: 11/11.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/memory/policy.py` | `src/memory/case_memory.py` | `case_memory_policy_decision` used by `submit_case_memory_candidate` | WIRED | GSD helper verified; service applies policy before insert/event. |
| `src/memory/case_precedent.py` | `src/memory/case_working_context.py` | `read_active` and `hydrate_content` | WIRED | CWC active row is read and hydrated before projection. |
| `src/memory/case_precedent.py` | `src/repositories/refund_repo.py` | `get_by_id_with_order` | WIRED | Tenant-bound case lookup resolves merchant scope. |
| `src/memory/case_precedent.py` | `src/memory/case_memory.py` | `CaseMemoryService.submit_case_memory_candidate` | WIRED | Successful and PII-blocked generated candidates flow through existing service. |
| `src/memory/case_precedent.py` | `src/memory/schemas.py` | `MemorySourceRefV1` event/outcome identity | WIRED | Source identity uses allowed `event_id`, `outcome_id`, business object, and run fields. |
| `src/tools/executors/memory.py` | `src/memory/case_memory.py` | `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed` | WIRED | Planner-facing `search_case_memory` calls reviewed retrieval and returns `ToolResultV2` items. |
| `tests/tools/test_catalog.py` | `src/tools/contracts.py` | `ToolCallContext` remains without `case_id` | WIRED | Static and catalog tests cover the contract. |

`gsd-sdk query verify.key-links` passed all declared key links across 47-01 through 47-04: 8/8.

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ClosedCasePrecedentService.generate_closed_case_precedent_candidate` | `CaseMemoryWriteCandidate` | `RefundRepository.get_by_id_with_order` + `CaseWorkingContextRepository.read_active` + `hydrate_content(row)` | Yes - tenant/case scoped DB reads produce projection inputs; missing/non-terminal paths skip without inserts. | FLOWING |
| `CaseMemoryService.submit_case_memory_candidate` | `review_status`, `event_id`, identity hashes | Policy, tombstone, duplicate, PII, insert, and `MemoryWriteEvent` paths in `src/memory/case_memory.py` | Yes - rows and events are persisted through existing repository methods. | FLOWING |
| `CaseMemoryRepository.search_reviewed` | reviewed search items | `CaseMemorySearchRequest` metadata/scope/query filters | Yes - DB query returns only approved/auto-approved, prompt-safe, non-tombstoned rows; text path works without embeddings. | FLOWING |
| `reviewed_memory_context_retrieve` | `case_memory` prompt items | `MemoryContextService.load_reviewed_memory_context(...) -> CaseMemoryService.retrieve_reviewed(...)` | Yes - node passes trusted scope, query, and `case_type` from `issue_type`; tests use real service/repository. | FLOWING |
| `MemoryToolExecutor` | `ToolResultV2.data["items"]` | `CaseMemoryService.retrieve_reviewed(...)` | Yes - tool builds tenant/user/thread/merchant scopes from `ToolCallContext` and returns reviewed items. | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 47 post-review implementation surface | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py -q` | `122 passed, 1 warning in 123.40s` | PASS |
| CWC lifecycle and Phase 45/46 memory boundary regressions | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_phase45_contract_alignment.py tests/memory/test_phase46_session_context_alignment.py -q` | `51 passed, 1 warning in 7.95s` | PASS |
| Ruff over Phase 47 implementation/test surface | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py src/memory/case_memory.py src/agent/nodes/reviewed_memory_context_retrieve.py src/tools/executors/memory.py src/tools/contracts.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py` | `All checks passed!` | PASS |
| Recorded final validation gate | `47-VALIDATION.md` final command | Records `151 passed, 1 warning` for the full Phase 47 suite and `20 passed, 1 warning` for Phase 45/46 contract alignment. | PASS |

Warnings are the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MEM-04 | 47-01, 47-02, 47-03, 47-04 | `case_memories` locked as reviewed case precedent; closed-case CWC precedent generation introduced only as governed candidate path into case-memory review flow; metadata-first retrieval; `needs_review`/audit behavior; no destructive table rename. | SATISFIED | `.planning/REQUIREMENTS.md:39,71`; all four plans declare MEM-04; roadmap Phase 47 has 4/4 plans complete; code/docs/tests verify the six roadmap success criteria. |

No orphaned Phase 47 requirements were found. `.planning/REQUIREMENTS.md` maps MEM-04 to Phase 47 and MEM-05 to Phase 48.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docs/contract-spec.md` | 2456 | IN-01 from clean review: storage-model appendix still lists stale legacy case-memory fields/indexes. | Info | Non-blocking documentation drift. Normative Phase 47 text and implementation use `CaseMemory.scope_type/scope_id`; `47-REVIEW.md` classifies this as info-only. |
| `docs/current-implementation-map.md` | 40 | Existing `long_term_memory_retrieve` placeholder wording. | Info | Intentional Phase 48/MEM-05 scope, not a Phase 47 stub. |
| Source/tests scan | multiple | Empty lists/dicts, `None` defaults, and empty result assertions. | Info | Benign accumulators, schema defaults, skip-path assertions, or fixture values; not product stubs and not connected to a hollow Phase 47 path. |

No blocker anti-patterns, placeholder implementations, direct `CaseMemory` writes from `case_precedent.py`, second review queue, public close endpoint, or destructive schema changes were found.

### Human Verification Required

None. This phase is backend memory service wiring, docs, and tests. There is no UI, external service, or visual/manual workflow required to establish the Phase 47 goal.

### Gaps Summary

No gaps found. Phase 47 satisfies all six roadmap success criteria and MEM-04. DEFER-3 remains Phase 48/MEM-05 scope, and the remaining IN-01 documentation drift is info-only, not a Phase 47 goal blocker.

---

_Verified: 2026-07-03T15:38:26Z_
_Verifier: Codex (gsd-verifier)_
