---
phase: "21-rag-production-ingestion-ocr"
plan: "04a"
title: "Phase 21 Boundary Regression"
type: "execute"
wave: 7
depends_on: ["21-04"]
files_modified:
  - "tests/rag/phase21_xfail_inventory.py"
  - "tests/knowledge/test_phase21_boundaries.py"
  - "tests/knowledge/test_hybrid_retrieval.py"
  - "tests/agent/test_memory_evidence_boundary.py"
  - "tests/agent/context/test_assembler.py"
  - "tests/agent/test_policy_retrieval_ownership.py"
autonomous: true
requirements: [PROV-04, SAFE-02, SAFE-03, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]
requirements_addressed: [PROV-04, SAFE-02, SAFE-03, BOUNDARY-01, BOUNDARY-02, BOUNDARY-03, BOUNDARY-04]
must_haves:
  truths:
    - "DocumentBlock and parser/OCR metadata stay internal/debug/maintainer data and never become authority surfaces."
    - "Existing hybrid retrieval behavior remains intact after provenance work."
    - "Business artifacts and Tool System outputs cannot become policy chunks or evidence refs."
  artifacts:
    - path: "tests/knowledge/test_phase21_boundaries.py"
      provides: "Parser/OCR metadata exclusion and Phase 22/23/RAG-5 scope guards"
    - path: "tests/knowledge/test_hybrid_retrieval.py"
      provides: "Phase 20 hybrid retrieval regression"
    - path: "tests/agent/test_policy_retrieval_ownership.py"
      provides: "Tool System vs policy retrieval ownership boundary"
  key_links:
    - from: "src/knowledge/retrieval.py"
      to: "tests/knowledge/test_hybrid_retrieval.py"
      via: "unchanged dense/sparse/fuzzy filters and RRF behavior"
    - from: "tests/knowledge/test_phase21_boundaries.py"
      to: "src/knowledge/schemas.py"
      via: "EvidenceRefV1 field exclusion assertions"
---

<objective>
Prove Phase 21 provenance and parser/OCR metadata remain outside evidence, prompt, memory, action, replay, business, and ranking authority.

Purpose: richer ingestion metadata is safe only if it stays subordinate to canonical evidence and verified maintainer/debug paths.
Output: boundary regression tests and xfail cleanup; production fixes are allowed only if these tests expose an actual Phase 21 metadata leak.
</objective>

<scope>
In scope: API/prompt/memory/action/replay boundary tests, Tool System ownership tests, precise Phase 22/23/RAG-5 implementation guards, and v1.3 hybrid retrieval regression.

Out of scope: provenance lookup implementation, report projection, user-facing source document viewer/highlight UI, public evidence schema changes, `MaterialClaim`, semantic verifier, query rewrite service, reranker service/interface, or external search backend.
</scope>

<context>
@/Users/ming/.codex/get-shit-done/workflows/execute-plan.md
@docs/contract-spec.md
@docs/rag-architecture-spec.md
@.planning/phases/21-rag-production-ingestion-ocr/21-RESEARCH.md
@.planning/phases/21-rag-production-ingestion-ocr/21-PATTERNS.md
@src/knowledge/schemas.py
@src/knowledge/retrieval.py
@src/api/schemas/search.py
@src/agent/context/projectors.py
@src/agent/context/assembler.py
@src/approvals/snapshots.py
@src/replay/schemas.py
@src/tools/contracts.py
@tests/knowledge/test_phase21_boundaries.py
@tests/knowledge/test_hybrid_retrieval.py
@tests/agent/test_memory_evidence_boundary.py
@tests/agent/context/test_assembler.py
@tests/agent/test_policy_retrieval_ownership.py
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| internal provenance -> agent/runtime surfaces | New metadata can leak into prompts, evidence refs, memory, actions, replay, or business facts. |
| parser text -> public evidence serialization | Hidden instructions or raw parser payloads can escape if public schemas include internal fields. |
| source guard -> Tool System boundary | Business artifacts can be incorrectly promoted into policy KB evidence. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan | Tests | Residual Risk |
|---|---|---|---|---|---|---|
| T21-04 | S/E | prompt/API boundary tests | mitigate | Keep raw parser/OCR text, hidden instructions, raw payloads, file bytes, comments, and parser dumps out of prompts/public evidence/memory/actions/replay. | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/context/test_assembler.py -q` | Later user-facing viewer must add separate redaction tests. |
| T21-06 | T/E | ingestion safety/boundary tests | mitigate | Reject business artifact sources and Tool System outputs before chunk persistence. | `uv run pytest tests/rag/test_ingestion_safety.py tests/agent/test_policy_retrieval_ownership.py -q` | Future upload UI taxonomy must preserve same source-type allowlist. |
| T21-07 | E | DocumentBlock metadata | mitigate | Prove block IDs cannot authorize policy evidence, approval evidence, memory, action, replay, or business facts. | `uv run pytest tests/knowledge/test_phase21_boundaries.py tests/agent/test_memory_evidence_boundary.py -q` | Internal maintainers can inspect locators after verification only. |
</threat_model>

<tasks>

<task type="auto" id="21-04a-01">
  <name>Enforce evidence, prompt, memory, action, replay, business, and retrieval boundaries</name>
  <files>tests/rag/phase21_xfail_inventory.py, tests/knowledge/test_phase21_boundaries.py, tests/knowledge/test_hybrid_retrieval.py, tests/agent/test_memory_evidence_boundary.py, tests/agent/context/test_assembler.py, tests/agent/test_policy_retrieval_ownership.py</files>
  <read_first>
    docs/contract-spec.md
    src/knowledge/schemas.py
    src/knowledge/retrieval.py
    src/api/schemas/search.py
    src/agent/context/projectors.py
    src/agent/context/assembler.py
    src/approvals/snapshots.py
    src/replay/schemas.py
    src/tools/contracts.py
    tests/rag/phase21_xfail_inventory.py
    tests/knowledge/test_phase21_boundaries.py
    tests/knowledge/test_hybrid_retrieval.py
    tests/agent/test_memory_evidence_boundary.py
    tests/agent/context/test_assembler.py
    tests/agent/test_policy_retrieval_ownership.py
  </read_first>
  <action>
    Complete boundary tests so parser/OCR provenance and source-block IDs are excluded from public `EvidenceRefV1`, API evidence serialization, prompt assembly, memory prompt blocks, approval snapshots, action draft authority, replay redacted payload authority, and Tool System business facts.
    Do not modify `src/knowledge/retrieval.py` or `src/api/schemas/search.py` unless a new boundary test exposes an actual Phase 21 metadata leak. If such a production fix is required, keep it narrowly scoped and record the deviation in `21-04a-SUMMARY.md`.
    Preserve existing Phase 20 hybrid behavior: dense/sparse/fuzzy filters run before candidate contribution, RRF controls ordering, and normalized confidence remains the evidence score.
    Ensure business artifact rejection tests prove orders/refunds/tickets/screenshots/tool results/business fact refs cannot be parsed into policy chunks or `EvidenceRefV1`.
    If any new internal provenance DTO is serialized for reports, mark it maintainer/debug/internal and keep it out of public API evidence response schemas unless the endpoint is tenant-scoped and verified.
    Scope guard assertions must allow current v1.3 `KnowledgeSearchResult.query_rewrite`, `RERANK_CONFIG_VERSION`, `rerank_config_version`, and `rerank_candidates(...)`, while forbidding new Phase 23-style query rewrite services, reranker services/interfaces, cross-encoders, Vespa/OpenSearch, or full external `SearchBackend`.
    Remove Wave 0 strict xfail markers for boundary tests this task satisfies and remove their entries from `tests/rag/phase21_xfail_inventory.py`.
  </action>
  <verify>
    <automated>uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_hybrid_retrieval.py tests/agent/test_memory_evidence_boundary.py tests/agent/context/test_assembler.py tests/agent/test_policy_retrieval_ownership.py -q</automated>
  </verify>
  <acceptance_criteria>
    Tests fail if `source_block_id`, `DocumentBlock`, parser metadata, OCR metadata, or provenance locator fields are added to `EvidenceRefV1`.
    Prompt/memory/action/replay tests prove hidden prompt injection fixture text and raw parser payloads do not appear in serialized prompt state or authority payloads.
    Scope guard tests allow current v1.3 query rewrite/rerank compatibility names and fail only on new Phase 23-style implementation deliverables.
    Hybrid retrieval tests from Phase 20 still pass unchanged.
  </acceptance_criteria>
  <done>Boundary regression tests prove provenance metadata stays internal and Phase 20 hybrid retrieval behavior remains unchanged.</done>
</task>

</tasks>

<verification>
`uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_hybrid_retrieval.py tests/agent/test_memory_evidence_boundary.py tests/agent/context/test_assembler.py tests/agent/test_policy_retrieval_ownership.py -q`
</verification>

<must_haves>
- Parser/OCR/source-block metadata remains subordinate internal/debug/maintainer metadata.
- Existing hybrid retrieval filters, RRF ordering, and normalized confidence behavior remain intact.
- Business artifacts and Tool System outputs cannot become policy chunks or evidence refs.
</must_haves>

<out_of_scope>
No public document viewer/highlight UI, no semantic verifier, no refusal/manual-review answer policy, no query rewrite service, no reranker service/interface, no cross-encoder, no external backend, and no business fact ingestion into RAG.
</out_of_scope>

<output>
After completion, create `.planning/phases/21-rag-production-ingestion-ocr/21-04a-SUMMARY.md`.
</output>
