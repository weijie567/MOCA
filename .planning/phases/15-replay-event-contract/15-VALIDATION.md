---
phase: 15
slug: replay-event-contract
status: ready_for_execution
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-16
updated: 2026-06-16
---

# Phase 15 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

Wave 0 in this file means the validation design is complete before execution. The actual implementation plans are `15-01` through `15-06`.

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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Test Owner | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------------|--------|
| 15-01-01 | 15-01 | 1 | REPLAY-01, REPLAY-03 | T-15-01 | Strict V3 schemas expose V3 timeline shape and legacy provenance without raw fields | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py -q --tb=short` | `tests/replay/test_replay_service.py` | planned |
| 15-01-02 | 15-01 | 1 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-02 | Migration preserves minimal rows and adds V3 columns, event_type/schema checks, sequence/attempt checks, and indexes | migration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py -q --tb=short` | `tests/replay/test_replay_migration_contract.py` | planned |
| 15-01-03 | 15-01 | 1 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-03 | Live schema is upgraded before service/API verification | schema | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | Alembic local DB | blocking |
| 15-02-01 | 15-02 | 2 | REPLAY-01, REPLAY-03 | T-15-04 | Replay append rejects unsafe payload keys and requires retention classification | security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_redaction_retention.py -q --tb=short` | `tests/replay/test_replay_redaction_retention.py` | planned |
| 15-02-02 | 15-02 | 2 | REPLAY-02 | T-15-05 | Shared allocator prevents duplicate/reordered sequence across graph, memory_write, approval, action draft, and replay/backfill writer surfaces; lifecycle writer is explicitly deferred to 15-04 | transaction | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_sequence_allocator.py -q --tb=short` | `tests/replay/test_sequence_allocator.py` | planned |
| 15-03-01 | 15-03 | 3 | REPLAY-02 | T-15-06 | Operation pairing rejects missing/duplicate terminal events and validates retry parent/attempt | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py -q --tb=short` | `tests/replay/test_operation_pairing.py` | planned |
| 15-03-02 | 15-03 | 3 | REPLAY-01, REPLAY-02 | T-15-07 | Historical/minimal rows project as unresolved instead of fabricated pairs | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_operation_pairing.py -q --tb=short` | `tests/replay/test_replay_service.py` | planned |
| 15-04-01 | 15-04 | 4 | REPLAY-01 | T-15-08 | Lifecycle finalizer never fabricates completed status for interrupted/responded/error paths | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py -q --tb=short` | `tests/replay/test_lifecycle_finalizer.py` | planned |
| 15-04-02 | 15-04 | 4 | REPLAY-01, REPLAY-02 | T-15-09 | Run-status persistence helpers and API callers use service-owned lifecycle/allocator boundaries and complete the lifecycle writer coverage deferred by 15-02 | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py tests/replay/test_sequence_allocator.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py -q --tb=short` | replay/API/approval tests | planned |
| 15-04-03 | 15-04 | 4 | REPLAY-01 | T-15-10 | SLA scanner remains disabled by default until post-Phase 15 SLA Scanner Enablement phase | config | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_sla_scanner.py -q --tb=short` | `tests/approvals/test_sla_scanner.py` | planned |
| 15-05-01 | 15-05 | 5 | REPLAY-01, REPLAY-03 | T-15-11 | `/replay` reads event-store rows first and returns sequence-ordered V3 response | api | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_api.py -q --tb=short` | `tests/replay/test_replay_api.py` | planned |
| 15-05-02 | 15-05 | 5 | REPLAY-03 | T-15-12 | `/replay` enforces tenant/owner/supervisor access and `/trace` remains rollback fallback | api | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/test_trace_api.py -q --tb=short` | replay API + trace API tests | planned |
| 15-06-01 | 15-06 | 6 | REPLAY-03 | T-15-13 | Demo draft replay cannot imply external execution and exposes safe refs/outcome only | security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_replay_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | replay/action tests | planned |
| 15-06-02 | 15-06 | 6 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-14 | Coverage records every requirement, deferred owner, `/trace` fallback, and final gate | documentation | `rg -n "REPLAY-01|REPLAY-02|REPLAY-03|DEFERRED_WITH_OWNER|Phase 16|Phase 17|post-Phase 15 SLA Scanner Enablement|/trace|TraceRepository.build_timeline|PASS|FAIL|NOT_RUN" .planning/phases/15-replay-event-contract/15-COVERAGE.md` | `15-COVERAGE.md` | planned |
| 15-06-03 | 15-06 | 6 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-15 | Final commands are recorded with blocking follow-ups for failures | final gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short` | `15-COVERAGE.md` | blocking |

*Status values: planned / blocking / green / red / flaky.*

---

## Wave 0 Requirements

- [x] `tests/replay/test_lifecycle_finalizer.py` planned in `15-04` for normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines.
- [x] `tests/replay/test_sequence_allocator.py` planned in `15-02` for pre-lifecycle writer surfaces and completed in `15-04` for lifecycle/finalizer writer coverage.
- [x] `tests/replay/test_operation_pairing.py` planned in `15-03` for started/terminal pairing, retry parent/attempt, and unresolved backfill markers.
- [x] `tests/replay/test_replay_redaction_retention.py` planned in `15-02` and `15-06` for V3 redaction/retention and demo draft safety.
- [x] `tests/replay/test_replay_api.py` planned in `15-05` for `/replay` response shape, ordering, access control, and event-store-first read.
- [x] `tests/replay/test_replay_migration_contract.py` planned in `15-01` for Alembic/ORM target schema compatibility.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local Alembic upgrade against developer DB | REPLAY-01, REPLAY-02, REPLAY-03 | Requires a live local PostgreSQL connection; sandbox may block socket access | Run `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head`; if DB socket is unavailable, start local services with `docker compose up -d postgres redis` and record output in `15-COVERAGE.md`. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or a blocking manual schema gate.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing replay references.
- [x] No watch-mode flags.
- [x] Feedback latency target is < 180s for focused replay suite.
- [x] `nyquist_compliant: true` set in frontmatter because actual plans now own every validation surface.

**Approval:** ready for execution
