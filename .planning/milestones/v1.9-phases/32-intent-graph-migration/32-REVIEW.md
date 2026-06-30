---
status: clean
phase: 32
phase_name: intent-graph-migration
reviewed: 2026-06-28T16:25:21Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - src/agent/graph_vocabulary.py
  - src/agent/intent_policy.py
  - src/agent/merchant_context.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/receive_request.py
  - src/agent/routing.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/api/routers/agent_runs.py
  - src/api/routers/traces.py
  - src/repositories/trace_repo.py
  - tests/agent/test_graph.py
  - tests/agent/test_graph_vocabulary.py
  - tests/agent/test_intent_policy_registry.py
  - tests/agent/test_intent_routing.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_required_slots.py
  - tests/agent/test_session_memory_integration.py
  - tests/agent/test_trace.py
  - tests/architecture/test_phase32_static_contract.py
  - tests/replay/test_replay_api.py
  - tests/test_agent_runs_api.py
  - tests/test_trace_api.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
---

# Phase 32: Code Review Report

**Reviewed:** 2026-06-28T16:25:21Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** clean

## Summary

本次 clean deep re-review 覆盖配置中列出的 25 个源码与测试文件，并结合 `32-CONTEXT.md`、`32-UAT.md`、`32-REVIEWS.md`、`32-REVIEW-FIX.md`、五个 plan/summary 核对 Phase 32 的 intent graph migration 目标。

复核重点包括：target graph vocabulary 与 runtime legacy graph 的兼容投影、intent/slot registry 跨 `classify_intent` / `receive_request` / `routing` 的调用链、slot inheritance 与 required-slot gate、trace/replay/API contract projection、`target_merchant_context.v1` 安全投影、AgentRun/trace/replay 授权边界，以及 phase artifact validation command scanner。

未发现新的 Critical、Warning 或 Info finding。所有已审文件满足本阶段质量要求。

## Fixed Warning Verification

WR-001 已关闭。`src/repositories/trace_repo.py:67` 现在通过 `project_trace_step_for_contract({"node": step.node_name})` 生成 timeline detail，并在 `src/repositories/trace_repo.py:76` 输出统一的 `target_node`。`tests/test_trace_api.py:260` 覆盖 `route_after_slots`，断言 timeline projection 为 `route_after_slot_resolution`；`tests/agent/test_trace.py:138` 也覆盖 trace summary 的 router target projection。

WR-002 已关闭。`src/agent/merchant_context.py:51` 对显式状态的 `source` 使用 allowlist sanitizer，`src/agent/merchant_context.py:52` / `src/agent/merchant_context.py:175` 对 `reason_codes` 只保留安全 code 形态。`tests/agent/test_trace.py:248` 覆盖 explicit `deferred`、`unavailable`、`not_applicable` metadata sanitizer，确认 raw merchant/order/refund/ticket/user query 不会进入投影。

WR-003 已关闭。`tests/architecture/test_phase32_static_contract.py:34` 定义 bullet inline-code 命令提取正则，`tests/architecture/test_phase32_static_contract.py:159` 在 `_validation_commands(...)` 中解析 `- \`command\` - result` 格式。`tests/architecture/test_phase32_static_contract.py:109` 覆盖 bare `pytest` 与 bare `python -m pytest` 的 bullet inline command 检测。

## Cross-File Checks

Trace/replay compatibility：runtime 继续保留 legacy node/router names；contract 输出通过 `graph_vocabulary` 投影 target names。`AgentStep.node_name` 未被重写，summary、trace step response 与 timeline 均使用 target projection 字段补充目标 vocabulary，兼容 replay 与历史 trace。

Merchant context 安全边界：`target_merchant_context` 只作为 final payload / trace summary 的安全状态投影使用，没有进入 AgentRun、trace 或 replay 的可见性判断。业务角色、supervisor、approval manager 等非 owner/non-admin 角色仍不能因为 merchant context metadata 获得 run visibility。

Registry 调用链：intent/slot policy 仍由 `IntentPolicyRegistry` 与 `SlotPolicyRegistry` 统一消费；直接 policy 常量回退由静态测试覆盖。slot resolution 的当前轮优先、跨 scope 拒绝、stale/invalidated/incompatible 拒绝和 idempotence 均有行为测试。

Phase 33 scope：`rag_context_build` 与 `claim_verify` 仅作为 deferred non-runnable vocabulary entry 存在；runtime graph 未新增 runnable Phase 33 节点，相关静态测试覆盖该边界。

## Validation

执行命令：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short
```

结果：`225 passed, 28 warnings in 176.23s`。warnings 来自依赖 deprecation 与既有 LangGraph config typing warning，本次未发现 Phase 32 回归。

执行命令：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/agent/intent_policy.py src/agent/merchant_context.py src/agent/nodes/classify_intent.py src/agent/nodes/extract_slots.py src/agent/nodes/receive_request.py src/agent/routing.py src/agent/state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/repositories/trace_repo.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py
```

结果：`All checks passed!`

---

_Reviewed: 2026-06-28T16:25:21Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
