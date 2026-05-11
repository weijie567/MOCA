---
phase: 02-rag-pipeline
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-11
---

# Phase 02 - RAG Pipeline Security

Per-phase security verification for Phase 02 RAG pipeline threats. Scope is limited to declared threat register entries T-02-04-01, T-02-04-02, T-02-06-01 through T-02-06-04, and T-02-07-01 through T-02-07-04.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| API client to search endpoint | Authenticated POST `/api/v1/search/` accepts query text and metadata filters | User query, bearer token, tenant-scoped policy evidence |
| JWT scopes to protected route | `knowledge:read` scope controls knowledge search access | Token scopes and active user tenant identity |
| Retriever to pgvector repository | Query embeddings and reranked candidates flow through repository search | Embedding vectors, tenant_id, doc_type, risk_level |
| Local eval to golden set | Eval script reads developer-controlled JSONL and DB-backed retrieval results | Golden labels, retrieved chunk IDs, pass/fail diagnostics |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-02-04-01 | Information Disclosure | `src/api/routers/search.py` search endpoint | mitigate | Endpoint requires `knowledge:read` and passes `user.tenant_id` into retrieval. | closed | `src/api/routers/search.py:24`, `src/api/routers/search.py:33`, `src/api/main.py:91`, `tests/test_search_integration.py:118` |
| T-02-04-02 | Elevation of Privilege | `knowledge:read` scope | mitigate | Role-issued JWT scopes include `knowledge:read`; OAuth2 metadata advertises it; `get_current_user` still rejects missing scopes. | closed | `src/auth/jwt.py:14`, `src/auth/jwt.py:15`, `src/auth/jwt.py:16`, `src/auth/jwt.py:21`, `src/auth/permissions.py:23`, `src/auth/permissions.py:58` |
| T-02-06-01 | Tampering | `eval/golden_rag_queries.jsonl` | mitigate | Golden labels remain exact chunk-ID labels; Plan 06 stopped before unsafe calibration, and chunk-map validation confirmed expected chunks exist and map to expected doc_keys. | closed | `.planning/phases/02-rag-pipeline/06-SUMMARY.md:40`, `.planning/phases/02-rag-pipeline/06-SUMMARY.md:93`, `.planning/phases/02-rag-pipeline/06-SUMMARY.md:98`; auditor validation: `OK 14 rows, 90 chunks` |
| T-02-06-02 | Information Disclosure | `PolicyChunkRepository.search_similar` | mitigate | Repository joins `PolicyDocument` with matching tenant and filters `PolicyChunk.tenant_id`; tenant and mismatched document-tenant tests pass. | closed | `src/repositories/policy_chunk_repo.py:49`, `src/repositories/policy_chunk_repo.py:55`, `tests/test_search_integration.py:118`, `tests/test_search_integration.py:134` |
| T-02-06-03 | Denial of Service | `scripts/eval_rag_hit_at_5.py` | accept | Local/manual eval is bounded to the 14-case golden set and default official `top_k=5`; no public endpoint was added for eval. | closed | Accepted risk AR-02-01; `eval/golden_rag_queries.jsonl` has 14 rows; `scripts/eval_rag_hit_at_5.py:203` |
| T-02-06-04 | Repudiation | Eval threshold reporting | mitigate | Eval prints Hit@5, fallback accuracy, failed-case ranked evidence, and exits non-zero when either metric is below threshold. | closed | `scripts/eval_rag_hit_at_5.py:35`, `scripts/eval_rag_hit_at_5.py:77`, `scripts/eval_rag_hit_at_5.py:130`, `scripts/eval_rag_hit_at_5.py:131`, `scripts/eval_rag_hit_at_5.py:149`, `scripts/eval_rag_hit_at_5.py:238` |
| T-02-07-01 | Information Disclosure | Candidate retrieval | mitigate | Retriever uses only `PolicyChunkRepository.search_similar()` for DB retrieval and forwards tenant_id, doc_type, and risk_level filters. | closed | `src/rag/retriever.py:106`, `src/rag/retriever.py:111`, `src/rag/retriever.py:112`, `tests/test_retriever.py:175`, `tests/test_retriever.py:185`, `tests/test_retriever.py:187` |
| T-02-07-02 | Tampering | Hybrid reranking | mitigate | Deterministic tests prove lexical reranking can promote a lower vector-ranked match and still excludes below-threshold candidates. | closed | `src/rag/retriever.py:67`, `src/rag/retriever.py:117`, `tests/test_retriever.py:192`, `tests/test_retriever.py:213` |
| T-02-07-03 | Repudiation | Live eval result | mitigate | Before/after evidence, live commands, Hit@5, fallback accuracy, and residual misses are recorded in the retrieval audit and summary. | closed | `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md:14`, `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md:26`, `.planning/phases/02-rag-pipeline/07-RETRIEVAL-AUDIT.md:40`, `.planning/phases/02-rag-pipeline/07-SUMMARY.md:78`, `.planning/phases/02-rag-pipeline/07-SUMMARY.md:103` |
| T-02-07-04 | Denial of Service | Deeper candidate retrieval | accept | Candidate expansion is bounded by `top_k * CANDIDATE_MULTIPLIER` for local/manual RAG support retrieval; no unbounded retrieval path was added. | closed | Accepted risk AR-02-02; `src/rag/retriever.py:15`, `src/rag/retriever.py:109`, `tests/test_retriever.py:185` |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-06-03 | The eval runner is a local/manual CLI over a fixed 14-case golden set with official scoring at `top_k=5`; it is not exposed as a public endpoint. | gsd-security-auditor | 2026-05-11 |
| AR-02-02 | T-02-07-04 | Deeper candidate retrieval is bounded by `top_k * CANDIDATE_MULTIPLIER` and is used within the local/manual support corpus retrieval path. | gsd-security-auditor | 2026-05-11 |

## Threat Flags

| Flag | Source | Mapping | Status |
|------|--------|---------|--------|
| `threat_flag: network_endpoint` | `.planning/phases/02-rag-pipeline/04-SUMMARY.md:128` | Maps to T-02-04-01 | addressed |
| `threat_flag: auth_scope` | `.planning/phases/02-rag-pipeline/04-SUMMARY.md:129` | Maps to T-02-04-02 | addressed |

## Unregistered Flags

None. Plan 04 threat flags map to registered threats, Plan 07 reports no new threat flags, and no unmapped flags were found in the required summaries.

## Verification Commands

| Command | Result |
|---------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rag_eval.py tests/test_retriever.py tests/test_ingestion.py tests/test_search_integration.py -q` | PASS - 25 passed with local PostgreSQL access |
| Golden JSONL/chunk-map auditor validation | PASS - `OK 14 rows, 90 chunks` |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-11 | 10 | 10 | 0 | gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] Threat flags incorporated
- [x] Implementation files left unmodified
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
