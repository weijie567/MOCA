---
phase: 16
slug: long-term-case-memory
status: complete
requirements_total: 14
requirements_covered: 14
created: 2026-06-17
---

# Phase 16 Requirement Coverage Manifest

This manifest maps every active v1.2 Phase 16 requirement to exact automated
coverage and verification commands. Memory remains contextual assistance only:
no row below authorizes memory as policy evidence, current business fact,
approval evidence, action authority, or replay/audit truth.

## Coverage Matrix

| Requirement | Test file(s) | Verification command | Coverage notes |
|-------------|--------------|----------------------|----------------|
| MEMID-01 | `tests/memory/test_memory_identity.py` | `uv run pytest tests/memory/test_memory_identity.py -q` | Golden normalization/hash tests cover `memory_identity.v1`, content hash, candidate hash, source identity hash, source-ref allowlist, unknown source-key rejection, and prompt-safe schemas. |
| MEMSCHEMA-01 | `tests/memory/test_memory_schema.py`, `tests/conversation/test_models.py` | `uv run pytest tests/memory/test_memory_schema.py tests/conversation/test_models.py -q` | Migration/model tests cover long-term memories, case memories, memory tombstones, memory write events, constraints, indexes, pgvector/HNSW declaration, and downgrade order. |
| LONGMEM-01 | `tests/memory/test_long_term_memory_service.py` | `uv run pytest tests/memory/test_long_term_memory_service.py -q` | Source policy tests cover explicit/deterministic auto-approval, LLM candidate review quarantine, prohibited PII skip, and observable write events. |
| LONGMEM-02 | `tests/memory/test_long_term_memory_repository.py` | `uv run pytest tests/memory/test_long_term_memory_repository.py -q` | Retrieval predicate tests cover tenant/scope filters, approved/current status, expiry/deletion, prohibited PII exclusion, content tombstones, and source-identity tombstones. |
| LONGMEM-03 | `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_memory_tombstones.py` | `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_memory_tombstones.py -q` | Supersede tests prove transactional replacement, previous row non-current status, successor links, and exactly one current memory per identity. |
| CASEMEM-01 | `tests/memory/test_case_memory_retrieval.py` | `uv run pytest tests/memory/test_case_memory_retrieval.py -q` | Reviewed precedent storage tests cover source identity, outcome metadata, review status, approved retrieval, rejection exclusion, and safe authoritative refs. |
| CASEMEM-02 | `tests/memory/test_case_memory_retrieval.py`, `tests/agent/test_memory_evidence_boundary.py` | `uv run pytest tests/memory/test_case_memory_retrieval.py tests/agent/test_memory_evidence_boundary.py -q` | Separation tests prove reviewed case memory is distinct from session memory, long-term profile memory, policy evidence, current business facts, and action authority. |
| CASEMEM-03 | `tests/tools/test_catalog.py`, `tests/agent/test_policy_retrieval_ownership.py`, `tests/agent/test_tools/test_unified_tool_manager.py`, `tests/memory/test_session_precedent_search.py` | `uv run pytest tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q` | Transitional search tests prove planner-visible `search_case_memory` is backed by reviewed case memory, descriptor wording names the reviewed case store, and old session-derived search is legacy/debug-only. |
| TOMBSTONE-01 | `tests/memory/test_memory_tombstones.py`, `tests/memory/test_case_memory_retrieval.py` | `uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_case_memory_retrieval.py -q` | Forget/delete tests prove tombstone creation and immediate retrieval exclusion for long-term and case memories. |
| TOMBSTONE-02 | `tests/memory/test_memory_tombstones.py`, `tests/memory/test_case_memory_retrieval.py` | `uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_case_memory_retrieval.py -q` | Delayed/same-transaction write tests prove tombstone checks before insert and `memory_write_event(reason_code='tombstone_match')` skip events. |
| MEMCTX-01 | `tests/agent/context/test_assembler.py`, `tests/agent/context/test_budget.py` | `uv run pytest tests/agent/context -q` | ContextAssembler tests cover bounded profile/case memory snippets, total memory cap, protected block precedence, and exclusion of raw payloads, hashes, policy full text, authority bodies, and debug blobs. |
| MEMCTX-02 | `tests/agent/test_memory_evidence_boundary.py`, `tests/agent/test_policy_retrieval_ownership.py` | `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/test_policy_retrieval_ownership.py -q` | Negative-boundary tests prove memory cannot produce `EvidenceRefV1`, policy evidence refs, approval/action authority, current business truth, or replay/audit truth. |
| MEMREVIEW-01 | `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_case_memory_retrieval.py`, `tests/memory/test_memory_tombstones.py` | `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q` | Review/observability tests cover candidate, approve, reject, write, skip, delete, supersede, tombstone decisions and audit-safe `memory_write_events`. |
| MEMEVAL-01 | `tests/memory/test_memory_identity.py`, `tests/memory/test_memory_schema.py`, `tests/memory/test_long_term_memory_repository.py`, `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_memory_tombstones.py`, `tests/memory/test_case_memory_retrieval.py`, `tests/agent/context/test_assembler.py`, `tests/agent/test_memory_evidence_boundary.py`, `tests/tools/test_catalog.py`, `tests/agent/test_policy_retrieval_ownership.py`, `tests/agent/test_tools/test_unified_tool_manager.py`, `tests/memory/test_session_precedent_search.py`, `tests/memory/test_phase16_requirement_coverage.py` | `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/memory/test_phase16_requirement_coverage.py -q` | Eval closure covers identity, schema, retrieval predicates, supersede, tombstones, prompt safety, authority negatives, legacy transition behavior, and this coverage manifest gate. |

## DB-Backed Fallback

The DB-backed pgvector recall fallback from `16-VALIDATION.md` is not required
for this closure when the automated SQLAlchemy/pgvector-backed retrieval tests
run successfully. If a future environment cannot run PostgreSQL/pgvector
integration tests, the allowed fallback is:

- **Requirements:** CASEMEM-02 / CASEMEM-03
- **DB-backed fallback:** Seed reviewed case memories locally, run reviewed
  case retrieval against pgvector, record top-k filtered output in
  `.planning/phases/16-long-term-case-memory/16-SUMMARY.md`.

## Closure Commands

- MEMSCHEMA exact command: `uv run pytest tests/memory/test_memory_schema.py tests/conversation/test_models.py -q`
- Focused Phase 16 suite: `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/memory/test_phase16_requirement_coverage.py -q`
- Full suite: `uv run pytest -q`
