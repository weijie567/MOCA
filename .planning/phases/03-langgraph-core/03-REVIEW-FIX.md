---
phase: 03-langgraph-core
source_review: 03-REVIEW.md
status: fixed
fixed_at: 2026-05-11T08:47:00Z
findings_fixed:
  critical: 1
  warning: 5
  total: 6
fix_commit: 1f9aa9b
---

# Phase 3 Code Review Fixes

## Fixed Findings

- CR-01: Agent business-data tools now enforce merchant ownership checks for orders, refund cases, and tickets, closing the same-tenant merchant data leakage path through `/agent/chat`.
- WR-01: `build_trace_summary()` now reads node `tools_called` lists and nested retrieval evidence data, so API trace summaries report tool calls and evidence counts correctly.
- WR-02: `get_ticket()` now accepts both internal UUIDs and public `ticket_no` identifiers, matching the REST ticket API contract.
- WR-03: Policy retrieval infrastructure errors now produce a retrieval-error draft, `node_errors`, and error trace status instead of being mislabeled as insufficient evidence.
- WR-04: The deterministic full-refund high-risk rule now matches Chinese full-refund wording such as `全额退款` for delivered orders.
- WR-05: `scripts/smoke_agent_live.py` now uses a real async DB session and fails non-zero on expected intent or final-status mismatches.

## Regression Coverage

- Added DB-backed same-tenant merchant denial tests for `get_order`, `get_refund_case`, and `get_ticket`.
- Added `get_ticket` tests for both public `ticket_no` and UUID lookup paths.
- Added retrieval error handling coverage for `DB_TIMEOUT`.
- Added deterministic Chinese full-refund high-risk override coverage.
- Strengthened graph trace summary assertions for `tools_called` and `evidence_count`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` - passed, 31 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent scripts/smoke_agent_live.py tests/agent` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 81 tests.
