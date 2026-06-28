---
phase: 32
fixed_at: 2026-06-28T16:15:43Z
review_path: .planning/phases/32-intent-graph-migration/32-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 32: Code Review Fix Report

**Fixed at:** 2026-06-28T16:15:43Z
**Source review:** `.planning/phases/32-intent-graph-migration/32-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-001: Trace timeline router target projection 不一致

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Commit:** 3a4994f
**Applied fix:** timeline detail 改用 `project_trace_step_for_contract(...)`，与 trace summary 和 step response 共用同一 projection contract；新增 `route_after_slots` 回归测试，确认 timeline `target_node` 投影为 `route_after_slot_resolution`。

### WR-002: 显式 target_merchant_context metadata 泄漏 raw 文本

**Files modified:** `src/agent/merchant_context.py`, `tests/agent/test_trace.py`
**Commit:** 08fa32f
**Applied fix:** 显式 `deferred` / `unavailable` / `not_applicable` 状态的 `source` 改为安全 allowlist，非法值 fallback 到 `explicit_state`；`reason_codes` 只保留大写 code 形态。新增测试覆盖 merchant/order/refund/ticket/user raw 文本不会进入投影结果。

### WR-003: Phase 32 validation command scanner 漏扫 bullet inline-code 命令

**Files modified:** `tests/architecture/test_phase32_static_contract.py`
**Commit:** e79f4dc
**Applied fix:** `_validation_commands(...)` 改为用正则提取 bullet 行第一个 inline code span，支持 ``- `cmd` - passed`` 格式；新增 focused 测试，确认该格式下的裸 `pytest` 和 `python -m pytest` 会被识别为违规命令。

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/repositories/trace_repo.py', 'tests/test_trace_api.py', 'src/agent/merchant_context.py', 'tests/agent/test_trace.py', 'tests/architecture/test_phase32_static_contract.py']]"`
  - Result: passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_trace_api.py::test_build_timeline_projects_router_step_target_node tests/agent/test_trace.py::test_target_merchant_context_sanitizes_explicit_status_metadata tests/architecture/test_phase32_static_contract.py -q --tb=short`
  - Result: `11 passed, 1 warning in 0.03s`
  - Note: warning 为既有 LangGraph `LangChainPendingDeprecationWarning`。

---

_Fixed: 2026-06-28T16:15:43Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 1_
