---
phase: 43-intent-recognition-multi-intent-tier-a
fixed_at: 2026-07-02T15:02:59Z
review_path: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 43: Code Review Fix Report

**Fixed at:** 2026-07-02T15:02:59Z
**Source review:** .planning/phases/43-intent-recognition-multi-intent-tier-a/43-REVIEW.md
**Iteration:** 1
**Fix scope:** critical_warning

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: Lossy Same-Intent Merge Clears Multi-Target Clarification

**Files modified:** `src/agent/nodes/classify_intent.py`, `tests/agent/test_nodes/test_classify_intent.py`
**Commit:** cbde8c6
**Applied fix:** Replaced the broad `bool(normalization)` multi-target neutralization check with an explicit lossless single-step normalization allowlist. Single-step `same_intent_entity_merge_limited` and fallback normalization records now keep the original `multi_target_request` clarification instead of routing forward with only `s1` represented.
**Regression test:** Added `test_lossy_same_intent_merge_keeps_multi_target_clarification`, which asserts `same_intent_entity_merge_limited` keeps `requires_clarification`, leaves no deferred hidden target, and routes to `clarification_gate`.
**Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py -q` passed with `16 passed, 1 warning`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q` passed with `67 passed, 1 warning`; `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` passed with `1237 passed, 1 skipped, 22 warnings`; `uv run ruff check src/agent tests/agent` passed; `git diff --exit-code -- docs/contract-spec.md src/agent/prompts.py src/agent/schemas.py` passed.

## Skipped Issues

None - all in-scope findings were fixed.

---

_Fixed: 2026-07-02T15:02:59Z_
_Fixer: Codex_
_Iteration: 1_
