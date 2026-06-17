---
phase: 16-long-term-case-memory
verified: 2026-06-17T18:37:27Z
status: passed
score: 14/14 requirements verified
overrides_applied: 0
review_fix_commit: 506c50d
human_verification: []
---

# Phase 16: Long-term / Case Memory Verification Report

**Phase Goal:** Implement reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 conversation/context foundation, while preserving the boundaries that memory is contextual assistance only.

**Verdict:** PASS. The current codebase implements reviewed long-term memory, reviewed case memory retrieval, tombstones, prompt-safe context assembly, and the memory authority boundary. No gaps or human verification needs were found.

## Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| MEMID-01 | VERIFIED | `src/memory/identity.py` defines `memory_identity.v1`, canonical content/source/candidate hashes, source-ref allowlist, and durable source discriminators. `tests/memory/test_memory_identity.py` covers stability and unknown-key rejection. |
| MEMSCHEMA-01 | VERIFIED | `src/db/models.py` and migration `013_long_term_case_memory.py` define `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events` with lifecycle constraints, rollback, tombstone indexes, and matching HNSW case-memory metadata. Schema drift check returned `valid: true`. |
| LONGMEM-01 | VERIFIED | `LongTermMemoryService.write_memory()` allows deterministic/explicit reviewed sources, sends model/semantic candidates to `needs_review`, and skips prohibited PII. Semantic episode candidates remain `needs_review`. |
| LONGMEM-02 | VERIFIED | `LongTermMemoryRepository.retrieve_profile_memory()` filters tenant/scope, published statuses, current rows, expiry, deletion, prohibited PII, and active tombstones. |
| LONGMEM-03 | VERIFIED | `supersede_memory()` checks tombstones and prohibited PII before mutation, then supersedes the previous row and inserts one current replacement. Regression tests cover prohibited PII and duplicate active identity behavior. |
| CASEMEM-01 | VERIFIED | `CaseMemoryService` stores reviewed precedent fields, outcome metadata, policy/source refs, review lifecycle, and write events. `tests/memory/test_case_memory_retrieval.py` covers reviewed storage and approval/rejection. |
| CASEMEM-02 | VERIFIED | `CaseMemoryRepository.search_reviewed()` uses separate case memory tables and filters reviewed rows only; boundary tests prove case memory is not session memory, policy evidence, or current business facts. |
| CASEMEM-03 | VERIFIED | Planner-visible `search_case_memory` dispatches through `CaseMemoryService.retrieve_reviewed`; legacy session search is `LegacySessionPrecedentSearchService` and debug/legacy-only. |
| TOMBSTONE-01 | VERIFIED | Long-term and case forget/delete paths create tombstones, mark rows deleted/tombstoned, and retrieval excludes matching content/source identities immediately. |
| TOMBSTONE-02 | VERIFIED | Long-term and case write paths call tombstone checks before insert and emit `memory_write_event` rows with `reason_code="tombstone_match"` instead of rewriting deleted content. |
| MEMCTX-01 | VERIFIED | `ContextAssembler` accepts bounded `profile_memory_snippets` and `case_memory_snippets`; projectors allowlist refs/summaries and reject raw payload, hash, authority, and debug markers. |
| MEMCTX-02 | VERIFIED | Memory boundary tests assert memory cannot create `EvidenceRefV1`, policy evidence, approval evidence, action authorization, business truth, or replay/audit truth. |
| MEMREVIEW-01 | VERIFIED | Long-term/case services emit `memory_write_events` for candidate, write, skip, approve/reject, delete, supersede, and tombstone decisions. |
| MEMEVAL-01 | VERIFIED | `16-COVERAGE.md` maps all 14 requirements to tests, and `tests/memory/test_phase16_requirement_coverage.py` guards the manifest. |

## Roadmap Criteria

All seven ROADMAP success criteria are satisfied: identity golden tests exist; reviewed long-term retrieval excludes rejected/deleted/tombstoned/prohibited/stale/out-of-scope rows; case memory is separate reviewed precedent context; tombstones block retrieval and rewrites; `ContextAssembler` includes bounded memory snippets; authority-boundary tests prevent memory from acting as evidence or authorization; and `search_case_memory` is backed by reviewed case memory rather than legacy session search.

## Code Review Fix Verification

Review findings in `16-REVIEW.md` were checked against current code and tests, not just `16-REVIEW-FIX.md`:

| Finding | Verification |
| --- | --- |
| CR-01 prohibited PII supersede | `supersede_memory()` now returns a `pii_blocked` skip before changing the previous row; regression test confirms no replacement is inserted. |
| WR-01 source-only tombstones | `canonical_source_identity_hash()` now returns `None` unless a durable discriminator such as event/message/tool/agent/business/outcome id is present. |
| WR-02 duplicate active writes | `write_memory()` checks `get_active_by_content_hash()` and returns `duplicate_active_identity` with a skip event. |
| WR-03 ORM vector index drift | `src/db/models.py` declares `ix_case_memories_embedding_hnsw` with `postgresql_using="hnsw"`, matching migration 013. |
| WR-04 dropped case snippets | `investigate()` accumulates `search_case_memory` result items into `state["case_memory"]` through prompt-safe projection only. |
| WR-05 ignored query | `MemoryToolExecutor` preserves non-empty query text in `CaseMemorySearchRequest`; repository applies text filtering when no embedding is provided. |

## Automated Verification

| Command | Result |
| --- | --- |
| `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_schema.py tests/memory/test_case_memory_retrieval.py tests/agent/test_tools/test_unified_tool_manager.py::test_search_case_memory_dispatches_to_reviewed_case_memory_service tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory -q` | Local verifier run: 33 passed, 1 warning, 28.40s. |
| `uv run pytest tests/memory tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_memory_evidence_boundary.py -q` | Local verifier run: 144 passed, 1 warning, 108.79s. |
| `uv run pytest tests/memory/test_phase16_requirement_coverage.py -q` | Local verifier run: 2 passed, 1 warning, 0.06s. |
| `uv run ruff check src/ tests/` | Local verifier run: passed. |
| `gsd-sdk query verify.schema-drift 16` | Local verifier run: `valid: true`, `issues: []`, `checked: 9`. |
| `uv run pytest -q` | Orchestrator post-fix run: 980 passed, 6 warnings, 506.49s. Not re-run in this verifier pass. |

## Anti-Patterns And Data Flow

Anti-pattern scan found only intentional empty-return guards in projector/fallback helpers, not placeholders or hollow stubs. Data-flow checks show reviewed memory flows from SQLAlchemy-backed repositories through services, graph/tool dispatch, prompt-safe projection, and `ContextAssembler`; memory does not flow into policy evidence, business facts, approval evidence, or action authorization.

## Residual Warnings/Risks

- Test warnings are the existing LangGraph `allowed_objects` pending deprecation warning.
- Normal duplicate active long-term writes are idempotent and evented. A high-concurrency duplicate writer race may still surface as a DB unique-constraint race rather than a controlled skip result; the unique index still preserves the one-current-memory invariant, so this is non-blocking for Phase 16.

## Human Verification Required

None. Phase 16 has no visual or external-service behavior requiring manual verification; the goal is covered by source, schema, data-flow, lint, and automated tests.

---

_Verified: 2026-06-17T18:37:27Z_
_Verifier: Claude (gsd-verifier)_
