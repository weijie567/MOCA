---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-05-10T14:37:00.000Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 10
  completed_plans: 10
  percent: 17
---

# Project State: MOCA

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-09)

**Core value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution.
**Current focus:** Phase 02 — RAG live verification

## Current Status

- **Active phase:** 2
- **Phase status:** Phase 2 implementation and automated verification complete; live external embedding verification pending
- **Blockers:** Live DashScope ingestion, RAG Hit@5 eval, and authenticated search endpoint verification

## Phase History

- **Phase 1: Foundation** — Complete on 2026-05-10
  - Plans completed: 5/5
  - Verification: `01-VERIFICATION.md`
  - Validation: `01-VALIDATION.md`
  - Human UAT: `01-HUMAN-UAT.md`
  - Security: `01-SECURITY.md` (`threats_open: 0`)
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 12 passed
- **Phase 2: RAG Pipeline** — Plans complete on 2026-05-10
  - Plans completed: 5/5
  - Verification: `02-VERIFICATION.md` (`status: human_needed`, score 35/36)
  - Human UAT: `02-HUMAN-UAT.md` (3 live checks pending)
  - Code review: `02-REVIEW.md`; fixes recorded in `02-REVIEW-FIX.md`
  - Latest plan summary: `.planning/phases/02-rag-pipeline/05-SUMMARY.md`
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 39 passed
  - Live checks pending: real `DASHSCOPE_API_KEY` ingestion, DB-backed Hit@5 eval, authenticated `/api/v1/search/`

## Session Notes

- 2026-05-10: Completed Phase 2 Plan 03. Added policy document/chunk repositories, ingestion service, dry-run ingestion CLI, and 15 Chinese policy documents. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 22 passed.
- 2026-05-10: Completed Phase 2 Plan 04. Added tenant-scoped retriever confidence scoring, citation validator, authenticated search endpoint, and mocked retrieval tests. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - 31 passed; ruff passed for Plan 04 files.
- 2026-05-10: Completed Phase 2 Plan 05. Added calibrated RAG golden set, Hit@5 eval script, deterministic search integration tests, and DashScope env docs. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 35 passed.
- 2026-05-10: Completed Phase 2 code review fixes. Fixed migration doc_key backfill, demo seed doc_key, tenant-safe vector joins, settings-backed embedding config, and sanitized generic 500 responses. Verification: ruff passed, targeted tests 8 passed, full pytest 39 passed, `alembic upgrade head` passed, `seed_demo.py --reset` passed.
- 2026-05-10: Phase 2 verifier returned `human_needed`: implementation verified, but live external embedding ingestion, RAG Hit@5, and live search endpoint relevance require human/API-key validation.

## Decisions

- Plan 04: Retriever emits structured evidence and fallback state only; answer generation remains downstream.
- Plan 04: Citation validation is deterministic field matching against retrieved chunk IDs, with no LLM judge.
- Plan 04: `knowledge:read` is granted to existing role scopes so the protected search endpoint is usable after login.
- Plan 05: Golden expected_chunk_ids were calibrated against the current zero-based heading chunker output instead of leaving placeholder IDs.
- Plan 05: The RAG eval script uses SessionLocal and the production Retriever/PolicyChunkRepository path for realistic DB-backed scoring.

**Planned Phase:** 2 (rag-pipeline) — 5 plans — 2026-05-10T09:41:47.870Z
