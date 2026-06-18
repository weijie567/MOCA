---
phase: 20
slug: rag-hybrid-retrieval
status: execution_passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
---

# Phase 20 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` / existing pytest configuration |
| **Quick run command** | `uv run pytest tests/rag/test_search_text.py tests/knowledge/test_hybrid_retrieval.py tests/test_ingestion.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | repo-dependent; quick retrieval subset should be the per-task feedback loop |

## Sampling Rate

- **After every task commit:** Run the task-specific verify command from `20-01-postgres-hybrid-retrieval-PLAN.md`.
- **After every plan wave:** Run `uv run pytest tests/rag tests/knowledge tests/test_ingestion.py tests/test_rag_eval.py -q`.
- **Before `$gsd-verify-work`:** `uv run pytest -q` should be green, or a concrete environment blocker must be recorded in the summary.
- **Max feedback latency:** keep task-level commands scoped to retrieval/ingestion tests.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | RAGTOK-01, RAGTOK-02 | T-20-01-02 | Search text does not mutate citation text | unit | `uv run pytest tests/rag/test_search_text.py -q` | yes | passed |
| 20-01-02 | 01 | 1 | RAGHYB-01, RAGHYB-02 | T-20-01-04 | Search indexes exist without changing evidence identity | schema/unit | `uv run pytest tests/knowledge/test_hybrid_schema.py -q` | yes | passed |
| 20-01-03 | 01 | 1 | RAGTOK-02, RAGHYB-01 | T-20-01-02 | Raw chunk content remains citation source | unit | `uv run pytest tests/test_ingestion.py tests/rag/test_search_text.py -q` | yes | passed |
| 20-01-04 | 01 | 1 | RAGRET-01, RAGSCOPE-01 | T-20-01-01 | Each channel applies trusted filters before returning candidates | unit/db | `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_effective_time.py -q` | yes | passed |
| 20-01-05 | 01 | 1 | RAGRET-02, RAGRET-03, RAGSCOPE-02, RAGTRACE-01 | T-20-01-03 | RRF ordering is separate from normalized confidence | unit | `uv run pytest tests/knowledge/test_hybrid_retrieval.py tests/knowledge/test_retrieval.py tests/knowledge/test_service.py -q` | yes | passed |
| 20-01-06 | 01 | 1 | RAGEVAL-01 | T-20-01-05 | Eval diagnostics do not encode business facts as policy evidence | unit/eval | `uv run pytest tests/test_rag_eval.py tests/knowledge/test_hybrid_retrieval.py -q` | yes | passed |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. New test files are created inside the plan tasks.

## Manual-Only Verifications

All phase behaviors should have automated verification. DB-backed Hit@5 eval may require a seeded PostgreSQL environment; if unavailable, record the environment blocker and run the pure pytest subset.

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** execution passed; ready for GSD verify-work
**Execution result:** passed focused retrieval suite, ruff gate, and full pytest (`1002 passed`).
