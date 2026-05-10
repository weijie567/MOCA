---
phase: 2
reviewers: [codex]
reviewed_at: "2026-05-10T12:00:00Z"
plans_reviewed: [02-PLAN-01.md, 02-PLAN-02.md, 02-PLAN-03.md, 02-PLAN-04.md, 02-PLAN-05.md]
---

# Cross-AI Plan Review — Phase 2

## Codex Review

**Summary**

The plans cover the right functional surface for Phase 2, but the current version has several integration blockers. The biggest issue is a schema mismatch: existing `PolicyChunk.doc_id` is a UUID foreign key to `PolicyDocument.id`, while the plans repeatedly treat `doc_id` as the semantic stable id like `refund_policy`. That affects ingestion, retrieval responses, citation expectations, and golden-set evaluation. There are also repo-specific path/API mismatches: migrations live under `src/db/migrations/versions`, existing routers use `get_session` and `Security(get_current_user, scopes=...)`, and API responses use `ApiResponse`, not a custom envelope. Overall: conceptually solid, but needs tightening before autonomous execution.

**Cross-Plan Concerns**

- **HIGH:** Add a semantic document id column before building ingestion/retrieval. Suggested: `PolicyDocument.doc_key: str`, unique on `(tenant_id, doc_key)`. Keep `PolicyChunk.doc_id` as the UUID FK.
- **HIGH:** Plan 04 depends on repositories created in Plan 03, but declares only `["01", "02"]`. This will break wave execution.
- **HIGH:** Migration path is wrong. The repo uses `src/db/migrations/versions/001_initial_schema.py`, not `alembic/versions`.
- **MEDIUM:** Acceptance criteria rely too heavily on grep/syntax checks. Add behavior tests for SQL filtering, similarity scoring, idempotent ingestion, and API response shape.
- **MEDIUM:** API design does not match existing conventions: current endpoints return `ApiResponse`, include trace ids, use `/api/v1/...`, and require scoped auth via `Security`.
- **MEDIUM:** Real embedding construction is too tightly coupled to request handling. Prefer settings-driven dependency injection so tests and local dry-runs do not require `DASHSCOPE_API_KEY`.

---

### Plan 01 Concerns

- **HIGH:** Migration location and revision are wrong. Use `src/db/migrations/versions/002_...py`, with `down_revision = "001_initial_schema"`.
- **HIGH:** Does not add a semantic document id field (`doc_key`), but later plans require one.
- **MEDIUM:** Migration should handle existing rows (currently null, but document assumption).
- **LOW:** Schemas use custom `SearchResponse` while existing API uses `ApiResponse`.

### Plan 02 Concerns

- **MEDIUM:** Chunk id stability — adding a heading changes all later ids.
- **MEDIUM:** `EmbeddingService.__init__` reads env var eagerly, fails in tests/dry-run.
- **LOW:** No embedding service tests planned.

### Plan 03 Concerns

- **HIGH:** `get_by_doc_id_str` cannot work without `doc_key` column.
- **HIGH:** Manifest acceptance says 5 entries but objective requires 15+.
- **HIGH:** `doc_type` filtering requires JOIN to PolicyDocument.
- **MEDIUM:** Embedding inside DB transaction holds it open during network calls.
- **MEDIUM:** No `--tenant-id` CLI argument specified.

### Plan 04 Concerns

- **HIGH:** `depends_on` should be `["01", "02", "03"]` not `["01", "02"]`.
- **HIGH:** Retriever uses `chunk.doc_id` as semantic id but it's a UUID FK.
- **HIGH:** Uses `get_db` / `Depends(get_current_user)` but project uses `get_session` / `Security(get_current_user)`.
- **MEDIUM:** Lazy-load issue accessing `chunk.document.title` in async context.
- **MEDIUM:** Should use `ApiResponse` not `SearchResponse`.

### Plan 05 Concerns

- **HIGH:** Expected chunk_ids guessed before actual chunking — will be flaky.
- **HIGH:** Eval script DB/tenant setup left as comments.
- **MEDIUM:** URL path should be `/api/v1/search/` not `/search/`.
- **MEDIUM:** Fake embeddings may not produce predictable nearest-neighbor behavior.

---

## Consensus Summary

### Agreed Strengths
- Correct functional coverage of all 9 phase requirements
- Three-tier confidence scoring well-designed
- Idempotent ingestion pattern is right
- CI boundary (fake embeddings) correctly enforced
- Golden set distribution appropriate

### Agreed Concerns (Verified Against Codebase)
1. **Schema: doc_id is UUID FK, not semantic ID** — Must add `PolicyDocument.doc_key` column
2. **Migration path: `src/db/migrations/versions/`** — Not `alembic/versions/`
3. **API conventions: `get_session`, `Security()`, `ApiResponse`, `settings.api_v1_prefix`** — Plans use wrong patterns
4. **Plan 04 dependency: needs Plan 03** — Wave ordering broken
5. **Embedding in transaction** — Should embed first, then short DB transaction

### Divergent Views
(Single reviewer — no divergence to report)
