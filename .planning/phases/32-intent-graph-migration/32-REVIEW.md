---
status: issues
phase: 32
phase_name: intent-graph-migration
reviewed: 2026-06-28T15:47:33Z
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
  warning: 1
  info: 0
  total: 1
---

# Phase 32: Code Review Report

**Reviewed:** 2026-06-28T15:47:33Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues

## 摘要

本次 deep review 覆盖配置中列出的 25 个源码与测试文件，并按 Phase 32 的目标交叉核对了 intent/slot registry 边界、target graph vocabulary 投影、trace/replay 兼容性、SSE/API 合同、权限可见性与 `target_merchant_context` 暴露范围。

未发现 Critical 级别的安全漏洞、授权放宽、trace/replay 破坏或崩溃型问题。发现 1 个 Warning：`receive_request` 在恢复 pending required-slot flow 时仍直接读取旧常量 `REQUIRED_SLOT_POLICY`，绕过 Phase 32 引入的 `SlotPolicyRegistry` 边界；当前静态 guard 也没有覆盖这个 consumer。

验证命令已按 MOCA 规则使用项目入口执行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short
```

结果：`219 passed, 28 warnings in 202.22s`。warnings 来自依赖 deprecation 与现有 LangGraph config typing 警告，本次 review 未将其作为 Phase 32 代码问题。

## Warnings

### WR-001 `receive_request` 恢复 active flow 时绕过 `SlotPolicyRegistry`

**Severity:** Warning

**File:** `src/agent/nodes/receive_request.py:21`

**Impact:** Phase 32 已把有效 intent/slot policy 的读取边界迁移到 registry，但 `receive_request` 的 `_project_active_flow_state` 仍用旧常量重建 `active_flow_state.required_slots`。如果后续 registry 变成配置化、测试 monkeypatch、租户化，或 registry 逻辑与常量产生差异，pending slot reply 的恢复路径会和 `classify_intent` / `routing` 的决策路径不一致，造成 required-slot clarification、trace/replay 复现与 APF-12 边界验证的隐性漂移。

**Evidence:**

- `src/agent/nodes/receive_request.py:7` 直接导入 `REQUIRED_SLOT_POLICY`。
- `src/agent/nodes/receive_request.py:21` 用 `intent not in REQUIRED_SLOT_POLICY` 判断是否可恢复 active flow。
- `src/agent/nodes/receive_request.py:26` 用 `REQUIRED_SLOT_POLICY[intent].model_dump()` 回填 required slots。
- 对比之下，`src/agent/routing.py:72` 的 required-slot 判断走 `SLOT_POLICY_REGISTRY.required_slots_for(...)`，`src/agent/nodes/classify_intent.py:134` / `src/agent/nodes/classify_intent.py:211` 也通过 registry 读取 precedence、risk 与 required slots。
- 当前静态 guard 只覆盖 `routing` 与 `classify_intent`：`tests/architecture/test_phase32_static_contract.py:73` 和 `tests/agent/test_intent_routing.py:341` 没有扫描 `src/agent/nodes/receive_request.py`，因此没有捕获这个 outlier。

**Suggested fix:**

将 `receive_request` 改为从 registry 读取 intent 与 slot policy，并给恢复路径补一个针对 registry 的测试：

```python
from src.agent.intent_policy import INTENT_POLICY_REGISTRY, SLOT_POLICY_REGISTRY

...

if not isinstance(intent, str) or not INTENT_POLICY_REGISTRY.is_known_intent(intent):
    return None

...

registry_required = SLOT_POLICY_REGISTRY.required_slots_for(intent).model_dump()
if not isinstance(required_slots, dict) or required_slots == {"all_of": [], "any_of": [], "optional": []}:
    required_slots = registry_required
```

同时建议：

- 在 `tests/agent/test_nodes/test_receive_request.py` 增加测试，monkeypatch `receive_request.SLOT_POLICY_REGISTRY.required_slots_for` 后确认 `active_flow_state.required_slots` 使用 registry 返回值。
- 扩展 `tests/architecture/test_phase32_static_contract.py` 或 `tests/agent/test_intent_routing.py` 的静态扫描范围，将 `src/agent/nodes/receive_request.py` 纳入禁止直接消费 policy 常量的检查。

---

_Reviewed: 2026-06-28T15:47:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
