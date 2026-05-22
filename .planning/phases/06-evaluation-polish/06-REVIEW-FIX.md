---
phase: 06-evaluation-polish
source_review: 06-REVIEW.md
status: fixed
fixed_at: 2026-05-22T00:00:00Z
findings_fixed:
  critical: 0
  warning: 2
  info: 1
---

# Phase 6 Code Review Fixes

## Summary

Fixed all findings from `06-REVIEW.md`.

## Fixes

### WR-01: Default Agent Eval Does Not Exercise The Graph

**Status:** Fixed

`scripts/eval_agent.py` now runs a compiled LangGraph CI contract gate with patched deterministic LLM/tool dependencies for representative categories:

- `normal_policy_qa`
- `refund_troubleshooting`
- `approval_required`
- `approval_approved`
- `approval_rejected`

The JSON report includes a `graph_contract` section and the overall eval status fails if compiled-graph contract checks fail.

### WR-02: Demo Script Continues After Failed Core Chat Flow

**Status:** Fixed

`scripts/demo_phase6.sh` now:

- Fails preflight unless `/api/v1/agent/chat` returns HTTP 200 with `success: true`.
- Fails each chat scenario if the response has `success: false` or lacks a run ID.
- Requires scenario 4 to return `approval_id`.
- Uses the real approval ID for the permission-denied scenario.
- Fails scenario 6 and trace lookup on unexpected API response shapes.

### IN-01: Architecture Doc Lists The Old Embedding Model

**Status:** Fixed

`docs/architecture.md` now documents DashScope `text-embedding-v4` and the 1024-dimensional pgvector retrieval shape.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_agent.py --output /tmp/moca-agent-eval-review-fix.json` - PASS.
- `graph_contract.status == "pass"` and `graph_contract.failures == []` in `/tmp/moca-agent-eval-review-fix.json`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check scripts/eval_agent.py` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check scripts/eval_agent.py` - PASS.
- `bash -n scripts/demo_phase6.sh` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/validate_golden_seeds.py` - PASS.

## Residual Risk

Full DB-backed RAG evaluation and full pytest still require the local Postgres/pgvector stack. The deterministic agent eval path and compiled graph CI contract are covered without provider keys.
