---
status: human_needed
phase: 01-foundation
updated: 2026-05-09
score: 2/5
---

# Phase 01 Verification

## Goal

Docker Compose starts the core stack, the database schema is present, FastAPI exposes authenticated tenant-scoped read APIs, deterministic Chinese seed data exists, and the test harness covers the Phase 1 success criteria.

## Automated Checks

| Check | Result | Notes |
|------|--------|-------|
| `PYTHONPYCACHEPREFIX=/tmp/moca-pycache python3 -m compileall src scripts tests` | PASS | All created Python files compile |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src tests scripts` | PASS | No lint findings remain |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` | BLOCKED | Local Postgres is unavailable; connect to `localhost:5432` failed |
| `docker --version` | BLOCKED | `docker` command not installed in current shell |
| `postgres --version` | BLOCKED | `postgres` command not installed in current shell |

## Verified Must-Haves

1. Project scaffold, config, migration setup, and service manifests exist.
2. JWT auth, unified response format, trace/run middleware, and tenant-scoped read endpoints are implemented.

## Human Verification

1. Start the stack with `docker compose up --build`.
expected: `postgres`, `redis`, and `api` all become healthy within 60 seconds.

2. Run `uv run alembic upgrade head`.
expected: all Phase 1 tables exist, including `audit_logs`, `policy_documents`, and `policy_chunks`.

3. Run `uv run python scripts/seed_demo.py --reset`.
expected: at least 80 orders, 30 refund cases, 15 tickets, and 15 policy documents are inserted with deterministic Chinese scenario data.

4. Run `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short`.
expected: health/auth/orders/refund/ticket/tenant-isolation/error-format tests pass.

5. Call `/api/v1/orders/{order_no}`, `/api/v1/refund-cases/{refund_case_no}`, and `/api/v1/tickets/{ticket_no}` with demo credentials.
expected: responses include `trace_id`, respect tenant scoping, and write audit log rows.

## Blocking Gap

Runtime verification is pending local infrastructure. The implementation is not marked passed until the stack can be started and the DB-backed tests are rerun successfully.
