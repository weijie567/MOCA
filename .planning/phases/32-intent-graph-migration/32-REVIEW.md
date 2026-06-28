---
status: issues
phase: 32
phase_name: intent-graph-migration
reviewed: 2026-06-28T16:06:08Z
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
  warning: 3
  info: 0
  total: 3
---

# Phase 32: Code Review Report

**Reviewed:** 2026-06-28T16:06:08Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues

## Summary

本次 clean deep re-review 覆盖配置中列出的 25 个源码与测试文件，并结合 `32-CONTEXT.md`、`32-UAT.md`、`32-REVIEWS.md`、`32-REVIEW-FIX.md`、五个 plan/summary 核对 APF-11/APF-12、target graph projection、registry policy consumption、trace/replay compatibility、`target_merchant_context` 安全投影与 AgentRun/trace/replay 授权边界。

旧 review 的 WR-001 已确认关闭：`e5f9e7d` 已将 `src/agent/nodes/receive_request.py` 从直接读取 `REQUIRED_SLOT_POLICY` 改为通过 `INTENT_POLICY_REGISTRY.is_known_intent()` 与 `SLOT_POLICY_REGISTRY.required_slots_for()` 恢复 pending required-slot flow，并补充了行为级 monkeypatch regression test 与静态 guard。

未发现 Critical 级别的授权放宽、Phase 33 runnable scope creep、直接 policy 常量回退或崩溃型问题。发现 3 个 Warning，均为 trace/data-contract/test-gate 层面的可修问题。

## Validation

执行命令：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short
```

结果：`220 passed, 28 warnings in 190.19s`。warnings 来自依赖 deprecation 与既有 LangGraph config typing warning，本次未作为 Phase 32 finding。

## Warnings

### WR-001 Trace timeline 对 router step 的 target projection 不一致

**Severity:** Warning

**File:** `src/repositories/trace_repo.py:75`

**Impact:** `build_trace_summary(...)` 与 trace step response 都会把 `route_after_slots` 投影为 `route_after_slot_resolution`，但 timeline detail 只用 `target_graph_name(..., kind="node")`。如果持久化 `AgentStep.node_name` 出现 router 名称，trace timeline 会暴露 legacy router name，破坏 APF-11 要求的 trace/API target vocabulary projection 一致性。

**Evidence:**

- `src/agent/graph_vocabulary.py:122` 的 `project_trace_step_for_contract(...)` 会先查 node，再查 router。
- `src/agent/trace.py:244` 使用 `project_trace_step_for_contract(...)` 构造 summary projection。
- `src/api/routers/traces.py:107` 使用 `project_trace_step_for_contract(...)` 构造 step response。
- `src/repositories/trace_repo.py:75` 直接调用 `target_graph_name(step.node_name, kind="node")`，router 名称不会落到 router alias。
- 复现：`target_graph_name("route_after_slots", kind="node")` 返回 `route_after_slots`，而 `project_trace_step_for_contract({"node": "route_after_slots"})["target_node"]` 返回 `route_after_slot_resolution`。

**Suggested fix:** 在 timeline detail 中改用同一个 projection helper：

```python
projected = project_trace_step_for_contract({"node": step.node_name})
"target_node": projected["target_node"]
```

并在 `tests/test_trace_api.py` 或 repository-level test 中加入 `AgentStep(node_name="route_after_slots")`，断言 timeline detail 的 `target_node == "route_after_slot_resolution"`。

### WR-002 显式 `target_merchant_context` 的 `source` / `reason_codes` 未做 raw ID 过滤

**Severity:** Warning

**File:** `src/agent/merchant_context.py:40`

**Impact:** Phase 32 规定 `target_merchant_context.v1` 是安全 evidence/status metadata，不能包含 raw merchant/order/refund/ticket identifiers 或 prompt/user text。当前 `resolved` spoof 会降级，但显式 `deferred`、`unavailable`、`not_applicable` 状态会原样保留 `source` 和 `reason_codes` 字符串；如果上游 checkpoint 或节点写入 raw ID，这些值会进入 trace summary 与 SSE final payload。

**Evidence:**

- `src/agent/merchant_context.py:40-45` 对显式 `deferred/unavailable/not_applicable` 直接返回 `_safe_source(...)` 和 `_safe_reason_codes(...)`。
- `src/agent/merchant_context.py:162-170` 只检查非空字符串，不限制 source 枚举或 reason-code 形态。
- 复现命令输出显示 raw IDs 原样外泄：

```python
project_target_merchant_context({
    "target_merchant_context": {
        "status": "deferred",
        "source": "order_id=ORD-SECRET-123",
        "reason_codes": ["ticket TICKET-SECRET-456"],
    }
})
# {'schema_version': 'target_merchant_context.v1', 'status': 'deferred',
#  'source': 'order_id=ORD-SECRET-123', 'reason_codes': ['ticket TICKET-SECRET-456']}
```

**Suggested fix:** 将显式状态的 `source` 限制到小型 allowlist，例如 `explicit_state`, `business_fact_refs`, `intent_policy`, `business_context_status`；`reason_codes` 只接受枚举值或 `^[A-Z0-9_]+$` 形式的 code，非法值降级为 `TARGET_MERCHANT_CONTEXT_UNAVAILABLE` 或丢弃。补充 sanitizer tests，覆盖显式 `deferred/unavailable/not_applicable` 中的 `merchant_id`、`order_id`、`refund_case_id`、`ticket_id`、user query/prompt text。

### WR-003 Phase 32 command scanner 漏掉 summary 中常见的 inline-code 命令格式

**Severity:** Warning

**File:** `tests/architecture/test_phase32_static_contract.py:128`

**Impact:** MOCA 规则禁止把裸 `pytest` / 裸 `python -m pytest` 作为有效验证结论。当前 static guard 试图扫描 phase artifact 的 command-bearing lines，但只解析整行形如 `- \`command\`` 且以反引号结尾的 bullet。Phase summaries 实际常用 `- \`command\` - passed` 格式；如果其中写入 `- \`pytest tests/foo.py\` - passed`，当前 guard 会漏检，削弱 Phase 32 的最终验证门。

**Evidence:**

- `tests/architecture/test_phase32_static_contract.py:128-129` 只在 `stripped.startswith("- `") and stripped.endswith("`")` 时提取 bullet command。
- Phase summary 里的验证记录使用 `- \`UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...\` - passed` 这类格式。
- 临时复现 `_validation_commands(...)` 对 `- \`pytest tests/foo.py -q\` - 1 passed` 返回 `[]`，不会触发违规。

**Suggested fix:** 用正则提取 bullet 行第一个 inline code span，而不是要求整行以反引号结束：

```python
match = re.match(r"^-\s+`([^`]+)`", stripped)
if match:
    command = match.group(1).strip()
```

并为 `_validation_commands` 增加一个 focused unit test，断言 `- \`pytest tests/foo.py -q\` - 1 passed` 会被识别并由 `test_phase32_artifacts_use_project_test_entrypoints_for_validation_commands` 判为违规。

---

_Reviewed: 2026-06-28T16:06:08Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
