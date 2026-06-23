---
phase: 29-tool-platform-boundary
plan: 02
type: summary
wave: 2
depends_on: [29-01]
completed: 2026-06-23
---

# 29-02 Summary: Tool Policy Contracts and Event Registration

## 改动文件

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `src/tools/contracts.py` | 修改 | 新增 `ToolViewV1`、`ToolPolicyDecision`、`ToolResultProjectionV1`、`ToolInvocationOutcome` 四个严格 Pydantic contract |
| `src/tools/policy.py` | 新建 | `TOOL_POLICY_CORE_REASON_CODES`、`TOOL_POLICY_RUNTIME_ONLY_REASON_CODES`、`TOOL_POLICY_EXTENSION_REASON_PATTERN`、`validate_tool_policy_reason_codes()`、`project_prompt_safe_input_schema()`、`ToolPolicyEngine` |
| `src/replay/decision_events.py` | 修改 | `REASON_CODE_PATTERN` 从 `^[a-z][a-z0-9_]*$` 扩展为 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$`，支持 namespaced extension codes |
| `src/replay/validators.py` | 修改 | `REPLAY_EVENT_TYPES` 和 `EVENT_RETENTION_CLASSIFICATION` 新增 `tool_policy_visibility_recorded` / `tool_policy_runtime_auth_recorded`；`FORBIDDEN_REDACTED_PAYLOAD_KEYS` 新增 `input_schema`、`required_permission`、`caller_allowlist` |
| `src/db/models.py` | 修改 | `ck_agent_trace_events_event_type` ORM check constraint 新增两个 tool policy event type |
| `src/db/migrations/versions/017_tool_policy_events.py` | 新建 | Alembic migration：drop + recreate `ck_agent_trace_events_event_type` 包含全部 22 个 event type |
| `tests/replay/test_replay_migration_contract.py` | 修改 | `MIGRATION_PATH` 指向 017；新增 `test_migration_010_event_type_check_matches_original_registry` 验证 010 的 check 与当时 registry 一致；保留 010 column/index 断言；017 的 event type check 与 `REPLAY_EVENT_TYPES` 一致 |

## 验证命令与结果

```
uv run pytest tests/tools/test_tool_platform.py::test_tool_view_exposes_only_prompt_safe_fields \
  tests/tools/test_tool_platform.py::test_prompt_safe_schema_projection_strips_descriptor_policy_and_adapter_metadata \
  tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope \
  tests/tools/test_tool_platform.py::test_visibility_stage_forbids_runtime_only_reason_codes \
  tests/replay/test_decision_events.py -q
```
结果：**57 passed**

```
uv run pytest tests/replay/test_tool_policy_events.py tests/replay/test_replay_migration_contract.py -q
```
结果：**16 passed**

```
git diff --check
```
结果：无 whitespace errors

## 与 Plan 偏差

| 项目 | Plan 描述 | 实际 | 原因 |
| --- | --- | --- | --- |
| `FORBIDDEN_REDACTED_PAYLOAD_KEYS` | Plan 未显式要求新增 `input_schema`/`required_permission`/`caller_allowlist` | 已新增 | `test_tool_policy_events.py` RED 测试要求这些 descriptor/policy 字段不得出现在 redacted payload 中；Phase 28 的 redaction guard 原有 key 列表不含它们，需扩展 |
| `test_replay_migration_contract.py` | Plan 说"MIGRATION_PATH 或 helper 逻辑指向 017" | 重构为 `V3_MIGRATION_PATH` + `TOOL_POLICY_MIGRATION_PATH` 分离读取 | 原 `MIGRATION_PATH` 指向 010 且 `test_migration_010_*` 依赖它读 010 源码；改为两个独立 path 更清晰 |
| `test_migration_event_type_check_matches_replay_event_registry` | Plan 说"指向 017" | 改为 `test_migration_010_event_type_check_matches_original_registry` 验证 010 的 check 与当时 registry 一致 | 原测试用 010 源码对比当前 `REPLAY_EVENT_TYPES` 会因新增 event type 失败；拆分后各自验证正确性 |

## 未完成项

无。29-02 scope 的两个 task 全部完成。`tests/tools/test_tool_platform.py` 中 4 个 RED 测试（ToolPlatform / ToolResultProjector 相关）仍为 RED，属于 29-03 scope，不在本次范围内。

## Post-Review 修复

- 修复 `ToolPolicyDecision` reason-code 验证：非法 freeform code 会被拒绝，visibility 阶段也禁止 runtime-only reason code。
- 修复 `project_prompt_safe_input_schema(...)` 对 `additionalProperties` 的递归投影，避免内部策略字段透传到 prompt-safe schema。
- 修复 `src.tools.policy` 的 public surface：`TOOL_POLICY_CORE_REASON_CODES`、`TOOL_POLICY_RUNTIME_ONLY_REASON_CODES`、`TOOL_POLICY_EXTENSION_REASON_PATTERN` 均由 `policy.py` 导出，`contracts.py` 不再出现 plan forbidden grep 命中的 descriptor/policy 字段文本。
