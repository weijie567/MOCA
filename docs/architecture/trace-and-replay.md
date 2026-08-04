<!-- generated-by: gsd-doc-writer -->
# MOCA Trace 与 Replay 当前架构

> 文档类型：CURRENT
> 描述范围：run 记录、事件身份、审计时间线、replay 投影与数据最小化
> 最后核验：2026-08-04（当前工作区）
> 权威来源：当前源码、数据库迁移、Replay schema/registry 与测试
> 更新触发：run/step/event 模型、事件注册表、序列分配、配对规则、SSE、checkpoint resume、trace/replay API、权限、脱敏或保留策略变化

## 总览

MOCA 同时保留两种可观察事实：`AgentRun` / `AgentStep` 等业务表支持面向人的 trace 视图，`AgentTraceEvent` 支持按事件身份与顺序构建 `ReplayResponseV3` 审计时间线。两者描述同一次 run，但不是同一份投影，也不承担执行恢复。[数据模型](../../src/db/models.py#L350-L389) · [Replay schema](../../src/replay/schemas.py#L14-L78)

```text
POST agent-runs -> AgentRun(pending)
                    |
GET .../events -> claim pending -> graph + SSE presentation events
                    |                    |
                    |                    +-> run_started / step_* / approval_required / final_response / error
                    |
                    +-> AgentStep + approval/action rows -> /trace chronological projection
                    |
                    +-> AgentTraceEvent(sequence) -> ReplayEventV3 -> /replay audit timeline
                                              |
                                              +-> no graph/LLM/tool/RAG/action re-execution
```

四个容易混淆的概念边界如下：

| 概念 | 当前行为 | 是否执行 graph / 外部能力 |
| --- | --- | --- |
| Trace | 合并 step、审批、审批步骤和 action draft，按时间排序，供调试与 UI 展示 | 否 |
| Replay | 读取已持久化事件，按 run 内 `sequence` 投影为 V3 审计时间线 | 否 |
| Checkpoint resume | 审批结果满足条件时，以 `Command(resume=...)` 从 LangGraph checkpoint 继续同一 run | 是 |
| Deterministic rerun | 假定固定输入、版本和依赖后重新执行并比较结果；当前 trace/replay API 未实现该能力 | 当前无此 API |

Checkpoint resume 会更新原 `AgentRun`、追加中断后的 `AgentStep`，并继续写 lifecycle/replay 事件；它不是“读取 replay”。[审批恢复](../../src/api/routers/approvals.py#L301-L475) · [step 追加](../../src/agent/trace.py#L176-L217)

## 三类持久化对象

| 对象 | 粒度与主键 | 主要内容 | 主要消费者 |
| --- | --- | --- | --- |
| `AgentRun` | 一次 run 请求/执行生命周期；`id` 为 run UUID。创建时先持久化为 pending，被 stream claim 后才开始 graph invocation，也可能尚未执行 | tenant/user/thread、输入、最终状态/回复、时间与汇总指标 | status、trace、replay 的 run header |
| `AgentStep` | 一个持久化 trace step；通常对应节点 traversal，也包含 `agent_run_memory_finalize` 等 API 收尾 synthetic step。主键为 UUID，并带 `run_id + step_index` | 节点/步骤、状态、摘要、tool/model、token/latency、metrics 与 evidence refs | trace steps、trace timeline、evidence API |
| `AgentTraceEvent` | 一个审计事件；`event_id`，并唯一约束 `(run_id, sequence)` | 完整事件身份、类型、actor、refs、脱敏 payload、配对与保留相关字段 | ReplayService 与 `/replay` |

`AgentRun` 存储 `input_query` 和 `final_response`，但 `TraceResponse` 与 `ReplayResponseV3` 都没有这两个字段；读取 trace/replay 不等于返回 run 的原始输入或完整模型输出。[AgentRun](../../src/db/models.py#L368-L389) · [TraceResponse](../../src/api/schemas/approvals.py#L93-L104) · [ReplayResponseV3](../../src/replay/schemas.py#L68-L78)

`write_agent_steps()` 将运行期 `trace_steps` 规范化为 `AgentStep`；resume 使用 `start_index` 只追加中断后的步骤。TraceRepository 再把 step、approval request、approval decision 和 draft 合并为按 ISO 时间排序的兼容时间线。[写入](../../src/agent/trace.py#L91-L217) · [时间线](../../src/repositories/trace_repo.py#L28-L150)

## ReplayEventV3 身份

`ReplayEventV3` 是严格 schema（额外字段拒绝），其身份维度不能互相替代：

| 字段 | 当前语义 |
| --- | --- |
| `event_id` | 单个事件身份；`ReplayService` 以 UUID5(`run_id:sequence`) 生成 |
| `run_id` | 审计聚合边界，也是 sequence 分配范围 |
| `tenant_id` | 数据隔离维度；API 先以 tenant-scoped run 查询做授权收口 |
| `thread_id` | 会话关联；不单独构成读取权限，也不是事件唯一键 |
| `trace_id` | 可选请求/调用链关联；不同 HTTP 请求可产生不同 trace id |
| `sequence` | run 内正整数顺序；timeline 的权威排序键 |
| `operation_id` | 一次 node/tool/RAG/LLM/memory 操作的 started/terminal 配对身份 |
| `parent_operation_id` | 嵌套操作或 retry 的父操作引用 |
| `attempt` | 操作尝试次数；native V3 operation event 必须为正整数 |

其余审计上下文包括 `event_type`、`occurred_at`、`node_name`、`actor`、`resource_refs`、`redacted_payload`、`redaction_policy_version`、`provenance`、`retention` 与安全错误投影。[字段定义](../../src/replay/schemas.py#L37-L65) · [持久化列](../../src/db/models.py#L1624-L1693)

API 外层 `ApiResponse.trace_id` 标识本次读取请求；Replay timeline 内每个 event 的 `trace_id` 才是原写入调用链的可选关联值，二者不能混作同一身份。[API envelope](../../src/api/routers/traces.py#L69-L98)

## Run 内顺序与 operation 配对

`ReplayService` 在事务内对 `hashtext(run_id)` 获取 PostgreSQL advisory lock，再读取该 run 的 `MAX(sequence) + 1`。数据库同时以 `(run_id, sequence)` 唯一约束兜底；并发 writer 因此共享同一个 run 内单调分配器。该契约是有序且不重复，不应被解释为跨 run 的全局时钟。[分配器](../../src/replay/service.py#L30-L53) · [约束与索引](../../src/db/models.py#L1628-L1645)

Native `replay_event.v3` 写入在取号前校验 operation lifecycle：

1. `*_started` 必须带 `operation_id` 和正整数 `attempt`，输出 `pairing_status=unresolved`；
2. terminal 必须找到唯一 started，并保持相同 family、`operation_id`、`attempt` 与 `parent_operation_id`；
3. 同一 operation 的第二个 terminal 被拒绝；
4. retry 必须使用新的 `operation_id`，引用既有 `parent_operation_id`，且 attempt 大于父尝试；
5. 非 operation event 输出 `not_applicable`。

当前注册的 operation family 是 node、tool call、RAG retrieval、LLM call 与 memory write，常用 terminal 为 `completed` / `failed`。配对器还识别 `unknown`、`expired`、`cancelled` terminal 后缀，但事件仍必须先通过注册表。[配对规则](../../src/replay/pairing.py#L12-L119) · [事件注册表](../../src/replay/validators.py#L9-L57)

```json
{
  "event_type": "tool_call_completed",
  "operation_id": "同一 started 事件的 UUID",
  "parent_operation_id": null,
  "attempt": 1,
  "provenance": {"source_schema_version": "replay_event.v3", "pairing_status": "paired"}
}
```

## 事件注册表与 run lifecycle

当前事件类型分为四组：

- operation：`node_*`、`tool_call_*`、`rag_retrieval_*`、`llm_call_*`、`memory_write_*`；
- run：`run_status_changed`；
- approval/action：`approval_requested`、`approval_decided`、`approval_expired`、`approval_resumed`、`action_draft_created`；
- tool policy：`tool_policy_visibility_recorded`、`tool_policy_runtime_auth_recorded`。

注册表与数据库 check constraint 同步；未注册类型在 append 前失败。当前没有 action execution event，action producer 的 `action_draft_created` 只记录 draft 与 `external_side_effect=false` 的安全结果。[registry](../../src/replay/validators.py#L9-L57) · [最新约束迁移](../../src/db/migrations/versions/017_tool_policy_events.py#L22-L39)

`RunLifecycleService` 把状态变化统一写成 `run_status_changed`，payload 至少含 `status`、`previous_status`、`reason_code`，必要时增加 clarification ref、安全 error code 或 cancellation source。当前处理的状态包括 running、interrupted、resumed、completed、rejected、expired、error、manual_review、refused 与 cancelled。[lifecycle](../../src/replay/lifecycle.py#L12-L266) · [trace helper 路由](../../src/agent/trace.py#L365-L404)

正常路径通常是 `pending -> running -> completed`。`RunLifecycleService` 能表达 `interrupted -> resumed -> completed`，相关测试也可显式构造该链；但当前生产审批恢复路由会把原 run 从 `interrupted` 直接更新到 terminal status，并另写 `approval_resumed` attempted/completed/failed 审计事件，没有先写 `run_status_changed(status=resumed)`。Replay 仍保留中断前事件，并让恢复后的事件继续使用同一 run 的 sequence。[生命周期测试](../../tests/replay/test_lifecycle_finalizer.py#L66-L273) · [terminal timeline 测试](../../tests/replay/test_phase35_terminal_timelines.py#L234-L558) · [生产恢复](../../src/api/routers/approvals.py#L397-L440)

## SSE 是执行展示流，不是 replay 流

默认 API 前缀为 `/api/v1`。`POST /api/v1/agent-runs` 创建 pending run；`GET /api/v1/agent-runs/{run_id}/events` 以行锁原子 claim pending run，并执行 graph。已启动的 run 再次请求返回 `RUN_ALREADY_STARTED`。[配置](../../src/config.py#L7-L13) · [路由注册](../../src/api/main.py#L104-L113) · [创建与流入口](../../src/api/routers/agent_runs.py#L139-L271) · [claim](../../src/api/routers/agent_runs.py#L1099-L1131)

SSE data envelope 包含 `event_type`、`run_id`、`step_index`、`node_name`、`status`、`message`、`timestamp`、`payload`，节点事件另带 `target_node_name`；等待 graph 输出时每 15 秒发送 keepalive comment。典型展示事件是 `run_started`、`step_started`、`step_completed`、`approval_required`、`final_response` 和 `error`。[SSE envelope](../../src/api/routers/agent_runs.py#L1208-L1230) · [heartbeat](../../src/api/routers/agent_runs.py#L720-L772)

SSE 的 `step_index` 是客户端展示顺序，不是 `AgentTraceEvent.sequence`；SSE 事件名也不等于 Replay event registry。持久化 run/step/event 后，应通过 status、trace 或 replay API读取事实，而不是把断线后的 SSE 当作审计存储。

## Trace API 与 Replay API

| API | 数据源与排序 | 返回重点 | 适用场景 |
| --- | --- | --- | --- |
| `GET /api/v1/agent-runs/{run_id}` | `AgentRun` | 当前状态、时间、最终回复与 scope 摘要 | 轮询 run 状态 |
| `GET .../{run_id}/trace` | AgentStep + approval + draft；按时间 | steps、approvals、safe draft、兼容 timeline、可选 RAG/claim 摘要 | 人工调试、UI 展示 |
| `GET .../{run_id}/replay` | AgentTraceEvent；按 `sequence` | `replay_response.v3`、严格 V3 timeline、provenance、pairing、retention | 审计与契约级事件分析 |
| `GET .../{run_id}/events` | 实时 graph 输出 | SSE 展示事件 | 仅启动并观看 pending run |

Trace timeline 使用 `type/time/title/status/detail`，并把历史节点名投影到当前 target node，不改写存量 row；审批 proposed action 只保留 action type/amount/currency，draft outcome 走 allowlist。[TraceRepository](../../src/repositories/trace_repo.py#L58-L150)

Replay timeline 只从 `agent_trace_events` 读取并按 sequence 排序；response header 来自 AgentRun，event payload 经 schema、脱敏和可选 RAG/claim summary 投影。该代码路径没有 graph、LLM、tool、RAG retrieval 或 action 调用。[ReplayService.get_replay](../../src/replay/service.py#L153-L189)

两个读取 API 都要求 `agent:chat` scope：先用 `(run_id, tenant_id)` 查 run，跨 tenant 返回 404；同 tenant 下仅 run owner 或 `admin` 可读，其他角色返回 403。SSE 更严格，admin 也不能代替 owner 执行 run。[读取守卫](../../src/api/routers/traces.py#L23-L98) · [执行守卫](../../src/api/routers/agent_runs.py#L1428-L1438) · [权限回归](../../tests/replay/test_phase35_trace_replay_permissions.py#L53-L257)

`target_merchant_id`、scope classification 或 replay authorization proof 当前都不会扩大这些读取/执行权限；它们是数据投影或未来授权证据，不是现有 guard 的替代条件。

## Minimal envelope 兼容投影

`agent_trace_events` 允许 `minimal_event_envelope.v1` 与 `replay_event.v3` 共存。`emit_decision_event()` 是现有 producer 的 minimal facade；身份缺 run/tenant/thread 时 fail closed，并在落库前检查 payload 与 refs。[minimal schema](../../src/replay/decision_events.py#L24-L125)

读取 `/replay` 时，`ReplayService.project_event()` 把两种 source row 都输出为 `ReplayEventV3`：

- `provenance.source_schema_version` 保留真实来源；
- minimal row 的 `pairing_status` 固定为 `unresolved`，不伪造 native V3 pairing 证明；
- native V3 row 按 timeline 前序事件重新计算 pairing；
- 兼容投影不把 minimal row 回写成 V3。

因此，response 中的 `schema_version=replay_event.v3` 表示输出契约，不表示每一行原本都以 V3 写入；判断来源必须读取 `provenance`。[投影](../../src/replay/service.py#L191-L264) · [迁移兼容测试](../../tests/replay/test_replay_migration_contract.py#L110-L130)

## 数据最小化、resource refs 与保留字段

`guard_redacted_payload()` 与 `guard_resource_refs()` 在写入和读取投影时递归检查键名。当前禁止 `raw` / `data` / `arguments`、raw prompt/args/payload/tool output/action payload、secret/credential/API key、PII 别名，以及 parser/OCR/debug/权限描述等内部字段。[禁止键](../../src/replay/validators.py#L59-L134)

Replay 只应保存稳定、可授权回查的 ref/hash/version 与低敏摘要；例如 run、approval、draft、tool call、evidence 或 safety snapshot 引用。`resource_refs` 不是承载原始业务对象的旁路，和 `redacted_payload` 使用同一 forbidden-key guard。

这套守卫是**键名 denylist**，不是内容分类器；`actor` 目前也是通用 dict，而非字段级 allowlist。因此 producer 仍必须把 actor 限制为类型/标识，把 refs 限制为不含秘密或 PII 的稳定引用，不能把敏感值藏在看似安全的键下。

每个注册事件都有 retention class；V3 行还可携带 `archived_at`、`retention_until`、`deleted_at`，错误仅投影 `code`、最多 256 字符的 safe message 与 `retryable`。但当前 `ReplayService.get_replay()` 没有按这些时间戳过滤，也未在 `src/replay/` 中实现归档/删除 worker；这些字段是已建模 metadata，不应宣称自动保留执行已经落地。[分类](../../src/replay/validators.py#L35-L57) · [保留投影](../../src/replay/service.py#L250-L264) · [安全错误](../../src/replay/service.py#L273-L282)

## 使用示例

先查兼容 trace，再查严格 replay：

```bash
curl -H "Authorization: Bearer $TOKEN" "$MOCA_API/api/v1/agent-runs/$RUN_ID/trace"
curl -H "Authorization: Bearer $TOKEN" "$MOCA_API/api/v1/agent-runs/$RUN_ID/replay"
```

审计代码应按 `sequence` 消费 `data.timeline`，并同时检查 `event_type`、`provenance.source_schema_version` 与 `provenance.pairing_status`；不要只按 `occurred_at` 排序，也不要把缺 terminal 的 `unresolved` 操作当作成功。

## 当前实现边界

- Replay 是 audit projection，不恢复 raw prompt、raw args、raw tool output、secret、PII 或完整 action payload，也不重放模型输出。
- Replay 不会重新执行 LLM、tool、RAG、graph 或 action；checkpoint resume 是审批路由中的独立执行路径。
- Trace timeline 与 Replay timeline 的排序键、事件 taxonomy 和兼容语义不同，不能逐项一一对应。
- Minimal source row 只获得 V3 输出形状，不自动获得 native V3 operation pairing 证明。
- retention class 与时间戳已建模，但自动清理、归档执行和读取过滤当前未在 ReplayService 落地。
- `eval/replay/` 下的 manifest 是开发契约、release/readiness 或 sample-only/pending monitoring artifact；其中 monitoring gate 明确不证明生产 telemetry 已存在。[monitoring artifact](../../eval/replay/monitoring-gate.v1.json#L1-L63)

代表性验证入口：`tests/replay/test_sequence_allocator.py`、`tests/replay/test_operation_pairing.py`、`tests/replay/test_replay_service.py`、`tests/replay/test_replay_redaction_retention.py`、`tests/replay/test_replay_api.py`、`tests/agent/test_trace.py`、`tests/test_trace_api.py`。
