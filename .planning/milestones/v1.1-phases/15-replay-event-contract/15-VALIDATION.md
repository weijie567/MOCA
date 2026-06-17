---
phase: 15
slug: replay-event-contract
status: verified
nyquist_compliant: true
wave_0_complete: true
gaps_found: 0
gaps_resolved: 0
manual_only: 0
created: 2026-06-16
updated: 2026-06-17
---

# Phase 15 - Validation Strategy

Per-phase validation contract and execution audit for Phase 15 ReplayEventV3 storage, projection, lifecycle replay, operation pairing, replay API access control, redaction, retention, and final coverage evidence.

Wave 0 in this file means the validation design was complete before execution. The implementation plans are `15-01` through `15-06`; this audit verifies their planned coverage now exists and runs green.

## Test Infrastructure

| Property | Value |
| --- | --- |
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short` |
| **Phase validation command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_redaction_retention.py tests/replay/test_operation_pairing.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py tests/agent/test_events.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` |
| **Schema gate command** | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` |
| **Estimated runtime** | ~135 seconds focused validation; full suite runtime depends on DB availability |

## Sampling Rate

- **After every task commit:** Run the focused replay/event tests touched by the task.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short`.
- **Before `$gsd-verify-work`:** Full suite and ruff must be green.
- **Max feedback latency:** 180 seconds for the focused replay suite.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15-01-01 | 15-01 | 1 | REPLAY-01, REPLAY-03 | T-15-01 | Strict V3 schemas expose V3 timeline shape and legacy provenance without raw fields. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py -q --tb=short` | yes | green |
| 15-01-02 | 15-01 | 1 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-02 | Migration preserves minimal rows and adds V3 columns, event_type/schema checks, sequence/attempt checks, and indexes. | migration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py -q --tb=short` | yes | green |
| 15-01-03 | 15-01 | 1 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-03 | Live schema is upgraded before service/API verification. | schema | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | command | green |
| 15-02-01 | 15-02 | 2 | REPLAY-01, REPLAY-03 | T-15-04 | Replay append rejects unsafe payload keys and requires retention classification. | security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_redaction_retention.py -q --tb=short` | yes | green |
| 15-02-02 | 15-02 | 2 | REPLAY-02 | T-15-05 | Shared allocator prevents duplicate/reordered sequence across graph, memory_write, approval, action draft, replay/backfill, and lifecycle/finalizer writers. | transaction | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_sequence_allocator.py -q --tb=short` | yes | green |
| 15-03-01 | 15-03 | 3 | REPLAY-02 | T-15-06 | Operation pairing rejects missing/duplicate terminal events and validates retry parent/attempt. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py -q --tb=short` | yes | green |
| 15-03-02 | 15-03 | 3 | REPLAY-01, REPLAY-02 | T-15-07 | Historical/minimal rows project as unresolved instead of fabricated pairs. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_operation_pairing.py -q --tb=short` | yes | green |
| 15-04-01 | 15-04 | 4 | REPLAY-01 | T-15-08 | Lifecycle finalizer never fabricates completed status for interrupted/responded/error paths. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py -q --tb=short` | yes | green |
| 15-04-02 | 15-04 | 4 | REPLAY-01, REPLAY-02 | T-15-09 | Run-status persistence helpers and API callers use service-owned lifecycle/allocator boundaries. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_lifecycle_finalizer.py tests/replay/test_sequence_allocator.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py -q --tb=short` | yes | green |
| 15-04-03 | 15-04 | 4 | REPLAY-01 | T-15-10 | SLA scanner remains disabled by default until the named post-Phase 15 SLA Scanner Enablement phase. | config | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_sla_scanner.py -q --tb=short` | yes | green |
| 15-05-01 | 15-05 | 5 | REPLAY-01, REPLAY-03 | T-15-11 | `/replay` reads event-store rows first and returns sequence-ordered V3 response. | api | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_service.py tests/replay/test_replay_api.py -q --tb=short` | yes | green |
| 15-05-02 | 15-05 | 5 | REPLAY-03 | T-15-12 | `/replay` enforces tenant/owner/supervisor access and `/trace` remains rollback fallback. | api | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_api.py tests/test_trace_api.py -q --tb=short` | yes | green |
| 15-06-01 | 15-06 | 6 | REPLAY-03 | T-15-13 | Demo draft replay cannot imply external execution and exposes safe refs/outcome only. | security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_replay_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | yes | green |
| 15-06-02 | 15-06 | 6 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-14 | Coverage records every requirement, deferred owner, `/trace` fallback, and final gate. | documentation | `rg -n "REPLAY-01|REPLAY-02|REPLAY-03|DEFERRED_WITH_OWNER|Phase 16|Phase 17|post-Phase 15 SLA Scanner Enablement|/trace|TraceRepository.build_timeline|PASS|FAIL|NOT_RUN" .planning/phases/15-replay-event-contract/15-COVERAGE.md` | yes | green |
| 15-06-03 | 15-06 | 6 | REPLAY-01, REPLAY-02, REPLAY-03 | T-15-15 | Final commands are recorded with blocking follow-ups for failures. | final gate | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay tests/agent/test_events.py tests/test_trace_api.py -q --tb=short` | yes | green |

Status values: green / red / flaky / manual-only.

## Requirement Coverage Audit

| Requirement | Status | Evidence |
| --- | --- | --- |
| REPLAY-01 | COVERED | `tests/replay/test_replay_service.py`, `tests/replay/test_replay_migration_contract.py`, `tests/replay/test_operation_pairing.py`, `tests/replay/test_lifecycle_finalizer.py`, `tests/replay/test_replay_api.py`, and `15-COVERAGE.md`. |
| REPLAY-02 | COVERED | `tests/replay/test_sequence_allocator.py`, `tests/replay/test_operation_pairing.py`, `tests/agent/test_events.py`, lifecycle allocator coverage, migration checks, and `15-COVERAGE.md`. |
| REPLAY-03 | COVERED | `tests/replay/test_replay_redaction_retention.py`, `tests/replay/test_replay_api.py`, `tests/test_trace_api.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`, retention checks, and `15-COVERAGE.md`. |

## Wave 0 Requirements

- [x] `tests/replay/test_lifecycle_finalizer.py` covers normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines.
- [x] `tests/replay/test_sequence_allocator.py` covers pre-lifecycle writer surfaces and lifecycle/finalizer writer coverage.
- [x] `tests/replay/test_operation_pairing.py` covers started/terminal pairing, retry parent/attempt, duplicate terminal rejection, and unresolved markers.
- [x] `tests/replay/test_replay_redaction_retention.py` covers V3 redaction/retention and demo draft safety.
- [x] `tests/replay/test_replay_api.py` covers `/replay` response shape, ordering, access control, event-store-first read, and raw payload omission.
- [x] `tests/replay/test_replay_migration_contract.py` covers Alembic/ORM target schema compatibility and minimal-row preservation.

## Manual-Only Verifications

All Phase 15 behaviors have automated verification. No manual-only gaps were found.

| Behavior | Requirement | Why Manual | Test Instructions |
| --- | --- | --- | --- |

## Validation Audit 2026-06-17

| Metric | Count |
| --- | ---: |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only | 0 |

## Current Command Results

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_replay_migration_contract.py tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_redaction_retention.py tests/replay/test_operation_pairing.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py tests/agent/test_events.py tests/test_agent_runs_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/test_trace_api.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | PASS: 131 passed, 1 warning |
| `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | PASS: database at head |

## Prior Final Gate Evidence

| Source | Evidence |
| --- | --- |
| `15-COVERAGE.md` | Final focused replay/event/approval/action gate: PASS, 133 passed, 1 warning. |
| `15-COVERAGE.md` | Full pytest: PASS, 875 passed, 1 warning. |
| `15-COVERAGE.md` | `ruff check src tests`: PASS. |

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all Phase 15 replay validation surfaces.
- [x] No watch-mode flags.
- [x] Feedback latency target is less than 180 seconds for the focused replay suite.
- [x] `nyquist_compliant: true` set in frontmatter.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-06-17
