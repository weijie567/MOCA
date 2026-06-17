---
phase: 16
slug: long-term-case-memory
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-17
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for long-term profile memory and reviewed case memory.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` / existing pytest setup |
| **Quick run command** | `pytest tests/memory tests/agent/context -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | Quick subset should stay suitable for per-task feedback; full suite before verification |

## Sampling Rate

- **After every task commit:** Run the task-specific pytest command from the PLAN task.
- **After every plan wave:** Run `pytest tests/memory tests/agent/context -q` plus affected agent/tool tests.
- **Before `$gsd-verify-work`:** Run `pytest -q`.
- **Max feedback latency:** No three consecutive implementation tasks may rely only on final full-suite verification.

## Per-Requirement Verification Map

| Requirement | Required Automated Coverage | Command |
|-------------|-----------------------------|---------|
| MEMID-01 | `memory_identity.v1` golden normalization/hash tests, `content_hash`, `candidate_hash`, allowed source refs, unknown source refs rejected | `pytest tests/memory/test_memory_identity.py -q` |
| MEMSCHEMA-01 | Migration/model tests for `long_term_memories`, `case_memories`, `memory_tombstones`, `memory_write_events`, constraints, indexes, downgrade | `uv run pytest tests/memory/test_memory_schema.py tests/conversation/test_models.py -q` |
| LONGMEM-01 | Long-term write source policy tests: deterministic/explicit sources allowed, LLM inference `needs_review`, prohibited PII skipped | `pytest tests/memory/test_long_term_memory_service.py -q` |
| LONGMEM-02 | Retrieval predicate tests for tenant/scope, approved/current status, freshness/expiry, deleted/tombstoned/prohibited exclusion | `pytest tests/memory/test_long_term_memory_repository.py -q` |
| LONGMEM-03 | Correction/supersede transactional tests proving exactly one current memory per identity | `pytest tests/memory/test_long_term_memory_service.py -q` |
| CASEMEM-01 | Reviewed precedent storage with source identity, outcome metadata, review status, safe authoritative refs | `pytest tests/memory/test_case_memory_retrieval.py -q` |
| CASEMEM-02 | Case memory retrieval remains separate from session memory, long-term memory, policy evidence, and current business facts | `pytest tests/memory/test_case_memory_retrieval.py tests/agent/test_memory_evidence_boundary.py -q` |
| CASEMEM-03 | Transitional `search_case_memory` renamed/quarantined or backed by reviewed case memory; catalog text cannot imply reviewed memory unless true | `pytest tests/tools tests/agent/test_policy_retrieval_ownership.py -q` |
| TOMBSTONE-01 | Forget/delete creates tombstone; retrieval excludes matching long-term/case memory immediately | `pytest tests/memory/test_memory_tombstones.py -q` |
| TOMBSTONE-02 | Delayed/asynchronous candidate writes check tombstones in the same transaction and emit `memory_write_event(reason_code='tombstone_match')` | `pytest tests/memory/test_memory_tombstones.py -q` |
| MEMCTX-01 | `ContextAssembler` bounded memory snippets, profile/case count caps, total memory char cap, no raw payload/hash/authority leakage | `pytest tests/agent/context/test_assembler.py -q` |
| MEMCTX-02 | Memory cannot produce evidence, approval evidence, action authorization, current business truth, or replay/audit truth | `pytest tests/agent/test_memory_evidence_boundary.py -q` |
| MEMREVIEW-01 | Candidate/review/write/skip/delete/supersede/tombstone decisions create observable `memory_write_events` for long-term and case memory | `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q` |
| MEMEVAL-01 | Contract/eval gates cover identity, retrieval predicates, supersede, tombstones, boundaries, legacy search behavior, and Phase 16 requirement coverage manifest | `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/memory/test_phase16_requirement_coverage.py -q` |

## Wave 0 Requirements

- [x] `tests/memory/test_memory_identity.py` — golden identity fixtures for MEMID-01.
- [x] `tests/memory/test_memory_schema.py` — migration/model contract checks for MEMSCHEMA-01, including `case_memories.content_hash`.
- [x] `tests/memory/test_memory_tombstones.py` — tombstone no-rewrite and transaction fixtures.
- [x] `tests/memory/test_case_memory_retrieval.py` — reviewed case retrieval separation fixtures.
- [x] `tests/memory/test_phase16_requirement_coverage.py` — verifies `.planning/phases/16-long-term-case-memory/16-COVERAGE.md` lists all Phase 16 requirement IDs before `$gsd-verify-work`.

Existing infrastructure covers pytest itself; no framework install task is expected.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DB-backed pgvector recall sanity, if CI lacks PostgreSQL/pgvector | CASEMEM-02 / CASEMEM-03 | Local DB integration may not run in pure CI | Seed reviewed case memories locally, run the implementation's DB-backed retrieval command, and record top-k filtered output summary in `.planning/phases/16-long-term-case-memory/16-SUMMARY.md` |

All authority-boundary, tombstone, prompt-safety, identity, and legacy-search gates must have automated tests.

## Validation Sign-Off

- [x] All requirements have an automated verification target or explicit DB-backed fallback.
- [x] Sampling continuity: no three consecutive tasks may omit automated verify.
- [x] Wave 0 requirements list all new missing test scaffolds; execution is closed (`wave_0_complete: true`) after implementation created them.
- [x] No watch-mode flags.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** executed; Phase 16 closure gates passed on 2026-06-18. Post-review fixes passed focused regression, expanded memory/tool, lint, schema-drift, and full-suite verification; latest full suite: `uv run pytest -q` - 980 passed, 6 warnings, 506.49s.
