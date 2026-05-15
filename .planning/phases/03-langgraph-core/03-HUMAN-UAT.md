---
status: resolved
phase: 03-langgraph-core
source:
  - 03-VERIFICATION.md
started: 2026-05-15T07:31:23Z
updated: 2026-05-15T07:31:23Z
---

# Phase 3 Human UAT

## Current Test

Live DashScope-backed agent smoke verification completed against the local database and seeded demo tenant data.

## Tests

### 1. Live policy QA

expected: A policy question returns `final_status=completed`, uses retrieved evidence, and records the full 8-node trace.
command: `set -a; source .env; set +a; LIVE_SMOKE_CASE_TIMEOUT_SECONDS=420 UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/smoke_agent_live.py`
result: passed
evidence: Query `退款超时规则是什么？` returned `intent=policy_qa`, `final_status=completed`, `evidence_count=5`, and `trace_steps=8`.

### 2. Live refund troubleshooting

expected: A seeded order refund troubleshooting question returns `final_status=completed`, uses retrieved evidence, and records the full 8-node trace.
command: `set -a; source .env; set +a; LIVE_SMOKE_CASE_TIMEOUT_SECONDS=420 UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/smoke_agent_live.py`
result: passed
evidence: Query `订单ORD-2024-001为什么还没退款？` returned `intent=refund_troubleshooting`, `final_status=completed`, `evidence_count=5`, and `trace_steps=8`.

### 3. Live no-evidence fallback

expected: An unrelated query returns `final_status=insufficient_evidence` with no evidence.
command: `set -a; source .env; set +a; LIVE_SMOKE_CASE_TIMEOUT_SECONDS=420 UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/smoke_agent_live.py`
result: passed
evidence: Query `这个问题没有任何相关规则` returned `intent=unknown`, `final_status=insufficient_evidence`, `evidence_count=0`, and `trace_steps=8`.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

Resolved. The previous Phase 3 human verification item is closed by the live smoke run.
