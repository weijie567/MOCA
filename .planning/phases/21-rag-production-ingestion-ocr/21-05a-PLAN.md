---
phase: "21-rag-production-ingestion-ocr"
plan: "05a"
title: "Final Phase 21 Acceptance Gate"
type: "execute"
wave: 9
depends_on: ["21-05"]
files_modified:
  - ".planning/phases/21-rag-production-ingestion-ocr/21-ACCEPTANCE.md"
autonomous: true
requirements: [SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, PROV-01, PROV-02, PROV-03, PROV-04, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-01, INGEST-02, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]
requirements_addressed: [SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, PROV-01, PROV-02, PROV-03, PROV-04, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, OCR-01, OCR-02, SAFE-01, SAFE-02, SAFE-03, INGEST-01, INGEST-02, INGEST-03, INGEST-04, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]
must_haves:
  truths:
    - "All Phase 21 requirements and security threats are verified with automated commands and documented acceptance evidence."
    - "Focused Phase 21 suite, full pytest gate, and Ruff gate results are recorded in the acceptance artifact."
    - "Phase 22/23/RAG-5 deliverables remain absent at phase close."
  artifacts:
    - path: ".planning/phases/21-rag-production-ingestion-ocr/21-ACCEPTANCE.md"
      provides: "Final requirement, threat, rollback, OCR runtime, full-suite, and command evidence"
  key_links:
    - from: "21-VALIDATION.md"
      to: "21-ACCEPTANCE.md"
      via: "requirement and threat coverage matrix"
    - from: "uv run pytest -q --tb=short"
      to: "21-ACCEPTANCE.md"
      via: "recorded full-suite result"
---

<objective>
Close Phase 21 with the final acceptance record and full verification gate.

Purpose: the phase must not claim completion until every requirement, threat, rollback path, and out-of-scope guard is accounted for with command evidence.
Output: `.planning/phases/21-rag-production-ingestion-ocr/21-ACCEPTANCE.md`.
</objective>

<scope>
In scope: focused Phase 21 suite, full pytest gate, Ruff gate, threat/requirement coverage evidence, OCR runtime preflight status, migration downgrade/reupgrade status, and final scope-guard confirmation.

Out of scope: new implementation beyond acceptance-record fixes, Phase 22 context builder/hallucination control, Phase 23 reranker/query rewrite, Phase RAG-5 external backend, source document UI, async workers, business data ingestion, and external action execution.
</scope>

<context>
@/Users/ming/.codex/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/21-rag-production-ingestion-ocr/21-VALIDATION.md
@.planning/phases/21-rag-production-ingestion-ocr/21-RESEARCH.md
@.planning/phases/21-rag-production-ingestion-ocr/21-PATTERNS.md
@.planning/phases/20-rag-hybrid-retrieval/20-01-postgres-hybrid-retrieval-SUMMARY.md
@tests/rag/test_parser_contract.py
@tests/rag/test_document_block_schema.py
@tests/rag/test_block_chunker.py
@tests/rag/test_pdf_parser.py
@tests/rag/test_docx_parser.py
@tests/rag/test_ocr_parser.py
@tests/rag/test_ingestion_safety.py
@tests/rag/test_ingestion_jobs.py
@tests/knowledge/test_provenance_lookup.py
@tests/knowledge/test_phase21_boundaries.py
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| final acceptance -> release readiness | A passing narrow slice must not hide unverified Phase 21 requirements or threats. |
| OCR runtime -> acceptance evidence | Missing native language data must be recorded as dependency status, not misreported as implementation success. |
| scope guard -> later RAG phases | Final acceptance must prove Phase 22/23/RAG-5 deliverables remain deferred. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan | Tests | Residual Risk |
|---|---|---|---|---|---|---|
| T21-01 | T | acceptance record | mitigate | Record source-type/signature gate results. | `uv run pytest tests/rag/test_ingestion_safety.py -q` | Additional real corpus signatures can be added after source operations begins. |
| T21-02 | D | acceptance record | mitigate | Record file/page/image/zip hazard and migration round-trip results. | `uv run pytest tests/rag/test_ingestion_safety.py tests/test_rag_production_migration.py -q` | Optional live DB gate depends on disposable DB availability. |
| T21-03 | D | acceptance record | mitigate | Record parser/OCR timeout and native runtime preflight status. | `uv run pytest tests/rag/test_ocr_parser.py tests/test_ingestion.py -q` | Native OCR runtime absence must be explicit dependency status. |
| T21-04 | S/E | acceptance record | mitigate | Record hidden prompt injection and raw payload exclusion results. | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/context/test_assembler.py -q` | Later UI/viewer surfaces need their own gate. |
| T21-05 | I | acceptance record | mitigate | Record cross-tenant and hash mismatch provenance results. | `uv run pytest tests/knowledge/test_provenance_lookup.py -q` | Maintainer authorization UI remains future scope. |
| T21-06 | T/E | acceptance record | mitigate | Record business artifact and Tool System output rejection results. | `uv run pytest tests/rag/test_ingestion_safety.py tests/agent/test_policy_retrieval_ownership.py -q` | Future source upload workflows must reuse the same guard. |
| T21-07 | E | acceptance record | mitigate | Record block authority boundary results. | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_memory_evidence_boundary.py -q` | Internal provenance remains debug/maintainer only. |
| T21-08 | I | acceptance record | mitigate | Record sanitized trace/report results. | `uv run pytest tests/rag/test_ingestion_jobs.py -q` | Operational logs outside persisted rows are not broadened in Phase 21. |
</threat_model>

<tasks>

<task type="auto" id="21-05a-01">
  <name>Run full Phase 21 acceptance gate and write acceptance record</name>
  <files>.planning/phases/21-rag-production-ingestion-ocr/21-ACCEPTANCE.md</files>
  <read_first>
    .planning/REQUIREMENTS.md
    .planning/ROADMAP.md
    .planning/phases/21-rag-production-ingestion-ocr/21-VALIDATION.md
    .planning/phases/21-rag-production-ingestion-ocr/21-RESEARCH.md
    .planning/phases/21-rag-production-ingestion-ocr/21-PATTERNS.md
    tests/rag/test_parser_contract.py
    tests/rag/test_document_block_schema.py
    tests/rag/test_block_chunker.py
    tests/rag/test_pdf_parser.py
    tests/rag/test_docx_parser.py
    tests/rag/test_ocr_parser.py
    tests/rag/test_ingestion_safety.py
    tests/rag/test_ingestion_jobs.py
    tests/knowledge/test_provenance_lookup.py
    tests/knowledge/test_phase21_boundaries.py
  </read_first>
  <action>
    Run the focused Phase 21 suite:
    `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q`.
    Run the full gate:
    `uv run pytest -q --tb=short` and `uv run ruff check src tests`.
    Create `.planning/phases/21-rag-production-ingestion-ocr/21-ACCEPTANCE.md` with: requirement coverage for all 26 IDs, threat coverage for T21-01 through T21-08, exact command results, migration downgrade/reupgrade status, OCR runtime preflight status, and explicit confirmation that Phase 22/23/RAG-5 deliverables remain absent.
    The acceptance record must list any native OCR dependency skip separately from implementation gaps. If any requirement is not covered by a passing test or explicit dependency skip, mark the phase blocked instead of claiming acceptance.
  </action>
  <verify>
    <automated>uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q</automated>
    <automated>uv run pytest -q --tb=short</automated>
    <automated>uv run ruff check src tests</automated>
  </verify>
  <acceptance_criteria>
    `21-ACCEPTANCE.md` contains all 26 requirement IDs and all eight threat refs.
    Focused Phase 21 suite passes.
    Full suite command result is recorded in `21-ACCEPTANCE.md`; if it fails for unrelated pre-existing reasons, record exact failing tests and keep Phase 21 focused suite plus Ruff results separate.
    Ruff passes.
    Static scope guard confirms no Phase 22/23/RAG-5 deliverables were implemented.
  </acceptance_criteria>
  <done>Focused suite, full-suite result, Ruff, requirement coverage, threat coverage, and scope guard status are captured in `21-ACCEPTANCE.md`.</done>
</task>

</tasks>

<verification>
Focused gate: `uv run pytest tests/test_ingestion.py tests/test_chunker.py tests/rag tests/knowledge -q`

Full gate: `uv run pytest -q --tb=short`

Lint gate: `uv run ruff check src tests`
</verification>

<must_haves>
- Acceptance artifact proves every requirement and threat ref is covered.
- Full suite and Ruff results are recorded explicitly.
- Native OCR dependency skips are recorded separately from implementation gaps.
</must_haves>

<out_of_scope>
No `MaterialClaim`, semantic verifier, runtime hallucination control, conflict/freshness routing, refusal/manual-review answer policy, query rewrite, reranker interface/API, cross-encoder, Vespa, OpenSearch, full external `SearchBackend`, source document UI/CMS, real external action execution, or business data ingestion into RAG.
</out_of_scope>

<output>
After completion, create `.planning/phases/21-rag-production-ingestion-ocr/21-05a-SUMMARY.md`.
</output>
