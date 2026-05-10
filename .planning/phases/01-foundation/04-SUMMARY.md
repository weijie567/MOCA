---
status: complete
phase: 01-foundation
plan_id: "04"
updated: 2026-05-09
key_files:
  created:
    - scripts/seed_demo.py
---

# Plan 04 Summary

## Delivered

- Created a deterministic seed script with UUID v5 IDs and `--reset` support.
- Seed data covers two tenants, 12 users, 6 merchants, 80+ orders, 30+ refund cases, 15 tickets, and 15 policy documents with chunks.
- Encoded the six fixed Chinese business scenarios called out in the phase context.

## Checks

- `PYTHONPYCACHEPREFIX=/tmp/moca-pycache python3 -m compileall src scripts tests` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src tests scripts` — passed

## Notes

- The script is ready to run with `uv run python scripts/seed_demo.py --reset` once Postgres is available locally.
