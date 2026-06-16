---
phase: 15
slug: replay-event-contract
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 15 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` |
| **Estimated runtime** | ~120 seconds focused; full suite runtime depends on DB availability |

---

## Sampling Rate

- **After every task commit:** Run focused replay/event tests touched by the task.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short`.
- **Before `$gsd-verify-work`:** Full suite and ruff must be green.
- **Max feedback latency:** 180 seconds for focused replay suite.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-00-01 | TBD | 0 | REPLAY-01 | T-15-01 | Lifecycle finalizer never fabricates completed status for interrupted/responded/error paths | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py -q --tb=short` | no W0 | pending |
| 15-00-02 | TBD | 0 | REPLAY-02 | T-15-02 | Shared allocator prevents duplicate or reordered per-run sequence across writers | transaction | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_sequence_allocator.py -q --tb=short` | no W0 | pending |
| 15-00-03 | TBD | 0 | REPLAY-02 | T-15-03 | Operation pairing rejects missing/duplicate terminal events and validates retry parent/attempt | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py -q --tb=short` | no W0 | pending |
| 15-00-04 | TBD | 0 | REPLAY-03 | T-15-04 | Replay payloads expose safe refs only and reject raw prompt/tool/action/secret/PII keys | security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/agent/test_events.py -q --tb=short` | no W0 | pending |
| 15-00-05 | TBD | 0 | REPLAY-03 | T-15-05 | `/replay` enforces tenant/owner/supervisor access and `/trace` remains rollback fallback | api | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/test_trace_api.py -q --tb=short` | no W0 | pending |
| 15-00-06 | TBD | 0 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-06 | Migration preserves minimal rows, adds V3 columns/indexes/checks, and supports event-store-first reads | migration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py -q --tb=short` | no W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/replay/test_lifecycle_finalizer.py` - normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines.
- [ ] `tests/replay/test_sequence_allocator.py` - shared allocator concurrency and resume continuation.
- [ ] `tests/replay/test_operation_pairing.py` - started/terminal pairing, retry parent/attempt, unresolved backfill markers.
- [ ] `tests/replay/test_replay_redaction_retention.py` - V3 redaction/retention contract.
- [ ] `tests/replay/test_replay_api.py` - `/replay` response shape, ordering, access control, event-store-first read.
- [ ] `tests/replay/test_replay_migration_contract.py` - Alembic/ORM target schema compatibility.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local Alembic upgrade against developer DB | REPLAY-01, REPLAY-02, REPLAY-03 | Requires a live local PostgreSQL connection; sandbox may block socket access | Run `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head`; if sandbox blocks DB socket, rerun with approved local DB access and record output in phase summary. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing replay references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 180s for focused tests.
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 tests exist and map to plans.

**Approval:** pending
