---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
review_path: .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-REVIEW.md
status: fixed
fixed:
  critical: 0
  warning: 3
  info: 0
remaining:
  critical: 0
  warning: 0
  info: 0
completed: 2026-07-08
---

# Phase 58 Review Fix Summary

Deep code review found three warnings. All three were accepted and fixed.

## Fixes

### WR-01: Strict classifier blind spot

Accepted. The Phase 58 legacy-hit classifier now scans `intent_classification` in addition to the other deleted/current-incompatible graph names. A regression test was added to prove an active runtime `builder.add_node("intent_classification", ...)` fixture fails strict mode with `active_runtime_legacy > 0`.

Files changed:

- `scripts/classify_phase58_legacy_hits.py`
- `tests/architecture/test_canonical_graph_baseline.py`

Verification:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q --tb=short` passed: `20 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check scripts/classify_phase58_legacy_hits.py tests/architecture/test_canonical_graph_baseline.py` passed

### WR-02: Current LangGraph docs named removed public route helper

Accepted. `docs/current-langgraph-architecture.md` now states that the public slot-route delegate is deleted, and that the remaining private helper is an implementation detail rather than current public route authority.

File changed:

- `docs/current-langgraph-architecture.md`

Verification:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` passed with `current_docs_legacy_authority=0`
- Current-doc canonical concept assertion passed

### WR-03: README runtime graph and memory wording drift

Accepted. The README Mermaid graph now matches the compiled graph routing shape: policy/fact paths go from contextual intent to `investigate`, ordinary completed slots go to `investigate`, and `memory_context_load` is used only when reviewed or long-term memory context is needed. The memory scope wording now reflects PostgreSQL-backed same-thread session memory and bounded contextual long-term/reviewed memory.

File changed:

- `README.md`

Verification:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` passed after fixes

## Final Status

All accepted code-review warnings are fixed. A clean re-review is required before Phase 58 is closed.
