# Phase 24 Code Review Fix

## 来源

Claude code review: `.planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW.md`

## 裁决

- CR-01 成立。`_claim_pending_run_for_stream` 复用了 view 权限，supervisor/admin 可以查看同租户其他用户 run，但 stream 执行会用当前调用者身份和 scopes 启动 graph，存在执行越权和 memory identity 污染风险。
- CR-02 成立。completed-run finalizer 在同一个 `AsyncSession` 中先写 assistant message / rolling summary，再调用 memory write；memory write fallback/timeout 路径可能 rollback 外层事务，导致终端 conversation rows 被误回滚。

## 修复

- `src/api/routers/agent_runs.py`
  - 新增 `_ensure_can_execute_run(...)`。
  - SSE claim 只允许 run owner 执行；supervisor/admin 保留 read/view 能力，但不能代替 owner 启动 pending run。
  - 拒绝同租户非 owner 执行前 rollback，释放 `FOR UPDATE` 事务。

- `src/api/services/agent_run_memory.py`
  - terminal memory write 改为通过当前 session bind 创建独立 `AsyncSession`。
  - memory write 自身失败、fallback 或 rollback 不再污染 finalizer 的 assistant message / rolling summary 外层事务。

## 回归

- `tests/test_agent_runs_api.py::test_events_rejects_same_tenant_supervisor_execution_before_claim`
- `tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_memory_write_rollback_does_not_remove_terminal_rows`
