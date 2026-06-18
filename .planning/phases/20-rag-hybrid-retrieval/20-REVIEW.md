---
phase: 20-rag-hybrid-retrieval
status: clean
reviewer: codex-local-fallback
gsd_subagent: not_run_tool_policy
depth: standard
files_reviewed: 13
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
reviewed_at: 2026-06-18T10:20:00Z
---

# Phase 20 Code Review

## Scope

Reviewed implementation files from `20-01-postgres-hybrid-retrieval-SUMMARY.md`:

- `src/rag/search_text.py`
- `src/db/models.py`
- `src/db/migrations/versions/014_rag_hybrid_retrieval.py`
- `src/rag/ingestion.py`
- `src/repositories/policy_chunk_repo.py`
- `src/knowledge/retrieval.py`
- `src/api/schemas/search.py`
- `scripts/eval_rag_hit_at_5.py`
- `tests/rag/test_search_text.py`
- `tests/knowledge/test_hybrid_schema.py`
- `tests/knowledge/test_hybrid_retrieval.py`
- `tests/test_ingestion.py`
- `tests/test_rag_eval.py`

## GSD Subagent Note

`gsd-code-review` normally delegates to `gsd-code-reviewer`. The current tool rules disallow spawning subagents unless the user explicitly requests delegation/subagents, so this review was completed locally by Codex as a fallback.

## Findings

No critical, warning, or info findings.

## Checks Performed

- Confirmed `EvidenceRefV1` is not extended and continues to build from raw `PolicyRetrievalHit.text`.
- Confirmed `PolicyChunk.content` remains raw citation text while `search_text` is retrieval-only.
- Confirmed dense, sparse, and fuzzy retrieval calls pass the same tenant/doc/risk/effective filters.
- Confirmed RRF score is ordering metadata and does not replace normalized confidence score.
- Confirmed eval diagnostic fields on `EvidenceItem` use `exclude=True` and do not change API serialization.
- Confirmed Phase 20 excludes OCR, `DocumentBlock`, `MaterialClaim`, Vespa/OpenSearch, and external `SearchBackend`.

## Verification Evidence

- `uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q` -> 82 passed.
- `uv run ruff check src/rag/search_text.py src/knowledge/retrieval.py src/repositories/policy_chunk_repo.py tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py` -> passed.
- `uv run pytest -q` -> 1002 passed.
