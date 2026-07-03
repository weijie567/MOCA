---
phase: 48
slug: narrow-long-term-explicit-preference-memory
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-04
---

# Phase 48 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py -x -q` |
| Full suite command | see Full Phase Gate below |
| Estimated runtime | ~120-240 seconds |

## Sampling Rate

- After every task commit: run the task-specific `<automated>` command from the active plan.
- After every plan wave: run that plan's `<verification>` command.
- Before `$gsd-verify-work`: run the Full Phase Gate.
- Max feedback latency: one focused pytest command per task.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 48-01-01 | 01 | 1 | MEM-05 | T-48-01 / T-48-02 | Contract says long-term is explicit preference only | static/docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py tests/architecture/test_memory_contract_delta.py -x -q` | existing docs/tests | pending |
| 48-01-02 | 01 | 1 | MEM-05 | T-48-02 | Storage identity and approved pytest entrypoints are locked | static/docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py -x -q` | new test file | pending |
| 48-02-01 | 02 | 2 | MEM-05 | T-48-03 / T-48-04 | Non-preference and disallowed long-term sources do not insert published memory | unit/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py -x -q` | existing tests | pending |
| 48-02-02 | 02 | 2 | MEM-05 | T-48-05 | Semantic episodes only project needs-review preference candidates | unit/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py -x -q` | existing/new tests | pending |
| 48-03-01 | 03 | 3 | MEM-05 | T-48-06 / T-48-07 | Chat writes require deterministic explicit preference phrases and trusted merchant scope | unit/node | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py -x -q` | existing tests | pending |
| 48-03-02 | 03 | 3 | MEM-05 | T-48-08 | Admin save requires admin role plus `memory:write` and emits audited explicit_admin_preference writes | API/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_memory_review_api.py tests/memory/test_long_term_memory_service.py -x -q` | existing tests | pending |
| 48-04-01 | 04 | 4 | MEM-05 | T-48-09 / T-48-10 | Retrieval returns only published preference rows from approved source types | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_repository.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py -x -q` | existing tests | pending |
| 48-04-02 | 04 | 4 | MEM-05 | T-48-11 / T-48-12 | Review approval publishes as human_reviewed and correction uses supersede/tombstone, not auto-merge | service/API | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_service.py tests/test_memory_review_api.py tests/agent/test_memory_evidence_boundary.py -x -q` | existing tests | pending |

## Wave 0 Requirements

Existing infrastructure covers all Phase 48 requirements. Do not add a new test runner or use bare `pytest`.

## Manual-Only Verifications

All Phase 48 behaviors have automated verification. Manual review is limited to plan/code review.

## Full Phase Gate

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/memory/test_phase48_long_term_preference_alignment.py \
  tests/architecture/test_memory_contract_delta.py \
  tests/memory/test_memory_policy.py \
  tests/memory/test_long_term_memory_service.py \
  tests/memory/test_long_term_memory_repository.py \
  tests/memory/test_memory_write_service.py \
  tests/memory/test_semantic_episode_projection.py \
  tests/memory/test_reviewed_memory_context_boundary.py \
  tests/agent/test_memory_write_node.py \
  tests/agent/test_reviewed_memory_context_retrieve.py \
  tests/agent/test_memory_evidence_boundary.py \
  tests/test_memory_review_api.py \
  -q
```

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity has no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] All commands use the MOCA-approved `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` entrypoint.

**Approval:** planned 2026-07-04
