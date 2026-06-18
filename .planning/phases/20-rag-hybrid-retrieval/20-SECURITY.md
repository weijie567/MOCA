---
phase: 20
slug: rag-hybrid-retrieval
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-18
---

# Phase 20 - Security

Per-phase security verification for Plan 20-01 PostgreSQL Hybrid Retrieval.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Retrieval scope filters | Dense, sparse, and fuzzy retrieval must stay inside tenant, document type, risk level, and effective-date scope before fusion. | Policy chunk metadata and retrieval candidates |
| Citation identity | Retrieval-only search text must not replace raw policy chunk citation content or evidence text hashing. | Policy chunk content, search text, EvidenceRefV1 |
| Evidence boundary | Hybrid traces and eval diagnostics must not become policy evidence or business fact references. | Internal retrieval trace fields, EvidenceItem diagnostics, EvidenceRefV1 |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-20-01-01 | tenant_scope_leak | PolicyChunkRepository sparse/fuzzy channels and PolicyRetrievalEngine channel calls | mitigate | Repository sparse/fuzzy SQL includes tenant and policy filters; retrieval engine passes identical tenant/doc/risk/effective filters to dense, sparse, and fuzzy channels; tests assert both channel calls and repository SQL scope filters. | closed |
| T-20-01-02 | citation_identity_regression | ingestion, PolicyChunk.content, EvidenceRefV1 text_hash | mitigate | PolicyChunk.content remains raw citation text, search_text is separate retrieval text, retrieval hits use chunk.content, and EvidenceRefV1 hashes the provided raw hit text. | closed |
| T-20-01-03 | threshold_regression | PolicyRetrievalEngine RRF fusion and EvidenceRefV1 score projection | mitigate | RRF score is used for ordering while hit score and best_score use normalized 0-1 confidence; sparse scores are normalized; tests pin RRF ordering and threshold behavior. | closed |
| T-20-01-04 | stale_search_index | PolicyChunk search_text/search_vector schema and ingestion/reimport path | mitigate | search_vector is a generated stored column derived from search_text; migration backfills search_text and creates full-text/trgm indexes; ingestion writes search_text for new chunks; schema and ingestion tests cover this path. | closed |
| T-20-01-05 | business_fact_pollution | eval diagnostics, EvidenceItem, EvidenceRefV1, policy evidence boundary | mitigate | Hybrid trace fields are optional and excluded from API serialization; eval diagnostics stay retrieval-only; tests assert no business_fact_refs or EvidenceRefV1 contamination. | closed |

## Threat Verification

| Threat ID | Evidence |
|-----------|----------|
| T-20-01-01 | `src/repositories/policy_chunk_repo.py:119`-`145` applies sparse tenant/doc/risk/effective filters; `src/repositories/policy_chunk_repo.py:163`-`188` applies fuzzy tenant/doc/risk/effective filters; `src/knowledge/retrieval.py:293`-`322` passes matching scope to dense/sparse/fuzzy calls; `tests/knowledge/test_hybrid_retrieval.py:136`-`156` asserts all channel call kwargs; `tests/knowledge/test_hybrid_retrieval.py:174`-`205` asserts repository SQL contains scope filters. |
| T-20-01-02 | `src/db/models.py:191`-`195` keeps content and search_text/search_vector separate; `src/rag/ingestion.py:91`-`108` persists `content=chunk.content` and separately assigns `search_text`; `src/knowledge/retrieval.py:232`-`243` builds EvidenceRefV1 from hit text; `src/knowledge/retrieval.py:348`-`363` sets hit text from `candidate.chunk.content`; `src/knowledge/schemas.py:44`-`65` hashes the supplied text; `tests/test_ingestion.py:101`-`138` asserts raw content and search_text; `tests/knowledge/test_facade_status.py:94`-`103` asserts full-content text_hash. |
| T-20-01-03 | `src/knowledge/retrieval.py:28`-`29` defines RRF and sparse normalization constants; `src/knowledge/retrieval.py:147`-`159` computes normalized confidence; `src/knowledge/retrieval.py:186`-`196` uses RRF only for fusion ordering; `src/knowledge/retrieval.py:348`-`372` projects `score=candidate.confidence`, keeps `rrf_score` separate, and evaluates status thresholds from best normalized score; `tests/knowledge/test_hybrid_retrieval.py:66`-`117` pins RRF promotion and score separation; `tests/knowledge/test_retrieval.py:73`-`114` pins strong/partial/no-evidence behavior. |
| T-20-01-04 | `src/db/models.py:192`-`195` defines non-null search_text and generated stored search_vector from search_text; `src/db/migrations/versions/014_rag_hybrid_retrieval.py:22`-`50` creates pg_trgm, backfills search_text, adds generated search_vector, and creates GIN/trgm/scope indexes; `src/rag/ingestion.py:98`-`104` writes search_text for new chunks; `tests/knowledge/test_hybrid_schema.py:16`-`32` and `tests/knowledge/test_hybrid_schema.py:42`-`52` cover schema/index/downgrade expectations; `tests/test_ingestion.py:135`-`137` asserts search_text content. |
| T-20-01-05 | `src/api/schemas/search.py:13`-`17` marks hybrid trace fields `exclude=True`; `scripts/eval_rag_hit_at_5.py:79`-`98` builds retrieval-only diagnostic rows; `scripts/eval_rag_hit_at_5.py:152`-`165` maps retrieval hits to EvidenceItem diagnostics without business fact refs; `tests/test_rag_eval.py:128`-`147` asserts optional trace diagnostics do not contain business_fact_refs or EvidenceRefV1; `tests/knowledge/test_hybrid_retrieval.py:120`-`132` asserts trace fields stay out of EvidenceRefV1 serialization. |

## Accepted Risks Log

No accepted risks.

## Unregistered Flags

None. `20-01-postgres-hybrid-retrieval-SUMMARY.md` has no `## Threat Flags` section.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-18 | 5 | 5 | 0 | codex gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-18
