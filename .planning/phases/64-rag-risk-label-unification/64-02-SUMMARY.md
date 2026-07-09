---
phase: 64-rag-risk-label-unification
plan: "02"
status: complete
completed_at: "2026-07-10T04:25:00+08:00"
---

# 64-02 Summary - ContextBuilder And Recommendation Label Migration

## What Changed

- Added a ContextBuilder regression proving `manual_review_sensitive` survives prompt-safe RAG risk-label projection.
- Migrated `src/agent/rag_context/builder.py` from local `_SAFE_RISK_LABELS` to `filter_prompt_safe_risk_labels`.
- Migrated `src/agent/nodes/recommendation_generation.py` from local `_SAFE_EVIDENCE_RISK_LABELS` to `filter_safe_evidence_risk_labels`.
- Removed unused local `_ROUTING_RISK_LABELS` from recommendation generation.
- Preserved unknown-label filtering; `raw_debug_secret` is absent from safe projection surfaces.

## RED Evidence

- Command: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py -q --tb=short`
- Expected failure: `bundle.prompt_context.citations[0].risk_labels == []` instead of `["manual_review_sensitive"]`
- Commit: `913ec4a test(64-02): add failing rag label projection regression`

## GREEN Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short`
  - Result: `46 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/rag_context/builder.py src/agent/nodes/recommendation_generation.py tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py`
  - Result: `All checks passed!`
- Static check: `rg -n "_SAFE_RISK_LABELS|_SAFE_EVIDENCE_RISK_LABELS|_ROUTING_RISK_LABELS" src/agent/rag_context/builder.py src/agent/nodes/recommendation_generation.py`
  - Result: no matches

## Deviations

- The RED test checks safe projection surfaces rather than the entire `RagContextBundle`, because `debug_context.raw_risk_hints` intentionally retains raw input hints for debug traceability.

## Self-Check

PASSED. Plan 02 fixed the known builder drift and removed copied RAG label allowlists from the prompt/recommendation path.
