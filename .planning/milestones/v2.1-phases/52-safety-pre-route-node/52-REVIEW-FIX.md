---
phase: 52-safety-pre-route-node
fixed_at: 2026-07-06T09:35:38Z
review_path: .planning/phases/52-safety-pre-route-node/52-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 52: Code Review Fix Report

**Fixed at:** 2026-07-06T09:35:38Z
**Source review:** `.planning/phases/52-safety-pre-route-node/52-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: Approval IDs Without Hyphen Bypass Safety Pre-Route

**Files modified:** `src/agent/intent_policy.py`, `tests/agent/test_nodes/test_safety_pre_route.py`, `tests/agent/test_graph.py`

**Applied fix:** Broadened `detect_pre_route()` so approval-like verbs combined with explicit approval context are treated as `approval_chat_not_trusted`. This covers separatorless and underscore approval IDs such as `APR1` and `APR_1` while still requiring approval context for non-exact longer replies.

**Regression tests:** Added node coverage for `approve APR1`, `approve APR_1`, `approved APR1`, and `同意 APR1`. Added graph smoke coverage proving `approve APR1` stops at `safety_pre_route -> clarification_gate` and does not reach `classify_intent`, memory, tools, approval, or action paths.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_graph.py -q --tb=short` -> 50 passed, 28 warnings
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short` -> 239 passed, 2 skipped, 28 warnings
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py src/agent/graph_vocabulary.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py` -> passed

---

_Fixed: 2026-07-06T09:35:38Z_
_Fixer: Codex_
_Iteration: 1_
