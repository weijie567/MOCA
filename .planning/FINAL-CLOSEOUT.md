# MOCA Final Closeout

Date: 2026-06-20
Status: closed; no active milestone; no current pending GSD work

## Scope

- Milestones v1.0 through v1.6 are shipped and archived.
- Current active phase: none.
- Phase 17 External Action Execution is not active.
- The 17-prep AgentState cleanup record is preserved only as deferred future context if Phase 17 is reintroduced.
- Phase 18 and Phase 19 have no current active scope in the roadmap.

## GSD State Check

- `gsd-sdk query init.todos`: `todo_count` was 0.
- `gsd-sdk query init.progress`: `phase_count` was 0, `current_phase` was null, and `next_phase` was null.

## Final Verification

- `uv run pytest -q`: 1282 passed, 1 skipped, 6 warnings in 550.99s.
- `uv run pytest tests/memory/test_phase16_requirement_coverage.py -q`: 2 passed, 1 warning.
- `uv run ruff check src tests scripts`: passed.
- `uv run ruff format --check src tests scripts`: passed; 359 files already formatted.
- `npm run lint` in `frontend/`: passed.
- `npm run build` in `frontend/`: passed.

Warnings were limited to existing dependency/config deprecations from LangChain checkpoint serde and Alembic path-separator configuration.

## Closeout Fixes

- Updated `tests/memory/test_phase16_requirement_coverage.py` so Phase 16 coverage checks accept the archived v1.2 milestone path after milestone archival.
- Applied Ruff formatting to touched retrieval/rerank/eval files and the related reranker test.
- Recorded final closeout state in `.planning/STATE.md`, `.planning/ROADMAP.md`, and this file.

## Not Done

- No remote push was performed.
- `study_plan/deep-research-report (1).md` was intentionally left untouched and uncommitted.
- No `v1.6` tag movement was performed during this final closeout.
