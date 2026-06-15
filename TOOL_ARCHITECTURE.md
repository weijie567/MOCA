# Tool Architecture

本文定义 MOCA 的目标工具架构。目标是简洁、统一、边界清楚：一个
agent-facing 调用入口，一个全量工具目录，一套上下文和结果契约，同时严格区分
只读、检索、记忆和动作写入。

## 设计目标

- 所有 graph-facing capability 只通过一个入口调用。
- 工具权限、输入输出 schema、caller allowlist、exposure、副作用、事件族和审计要求在一个目录中声明。
- Catalog 是全量声明源，但 manager 必须按 caller 派生 capability view；统一 catalog 不等于统一暴露给模型。
- Graph node 保持轻量：node 决定何时需要能力；工具层决定是否允许调用以及如何执行。
- 统一管理不等于放开写操作。写工具必须继续受 risk、approval、snapshot、idempotency 约束。
- 原始工具函数降级为内部 adapter，不再作为 graph-facing tool 暴露。

## 核心模型

目标调用链如下：

```text
Graph node
  -> UnifiedToolManager.invoke(tool_name, args, context)
    -> ToolCatalog 查 descriptor
    -> caller / permission / schema / side_effect / approval 校验
    -> domain executor
      -> domain service
        -> raw adapter / repository / external API
```

`UnifiedToolManager` 是 graph-facing 的唯一工具分发层。任何 graph node 可调用的能力都必须：

1. 在 `ToolCatalog` 中声明；
2. 通过 `UnifiedToolManager.invoke(...)` 执行；
3. 返回统一 `ToolResult` envelope。

Domain service 继续负责领域逻辑。manager 不应该知道如何查订单、如何做 RAG、如何写记忆、如何创建动作草稿；manager 只负责通用契约和安全边界，然后委托给对应 executor。

Manager 对 catalog 生成不同 view：

```text
planner-visible view   -> investigate 可选择：read / retrieval / memory read
node-only action view  -> execute_action 可调用：action draft / action execute
node-only memory view  -> memory_write 可调用：memory write
internal view          -> service / adapter 内部实现，不给 graph 或 planner
```

## 概念边界

### Tool

Tool 是 graph-facing capability，必须在 catalog 中声明。示例：

- `get_order`
- `get_refund_case`
- `get_ticket`
- `search_policy`
- `search_case_memory`
- `create_coupon_grant_draft`

### Raw Adapter

Raw adapter 是 domain service 后面的实现细节，可以访问 repo、本地 demo DB、RAG retriever 或外部 API。

Raw adapter 不应该被 graph node 直接 import，也不应该负责 agent 层的 caller allowlist、tool permission、approval 或事件族判断。它可以保留底层数据安全校验，例如 tenant / merchant ownership 防护。

### Domain Service

Domain service 负责领域语义：

- `BusinessReadService`：业务读、merchant scope、business fact projection。
- `PolicyKnowledgeService`：政策检索、证据质量、evidence contract。
- `MemoryService`：语义记忆 domain，当前实现 session memory；未来承载 long-term profile memory、reviewed case memory 和 memory-specific policy。
- `ActionExecutor`：动作草稿、外部动作执行、幂等和补偿语义。

### Domain Executor

Domain executor 是统一工具契约到 domain service 的薄适配层：

- `BusinessToolExecutor -> BusinessReadService`
- `KnowledgeToolExecutor -> PolicyKnowledgeService`
- `MemoryToolExecutor -> SessionPrecedentSearchService` for current `search_case_memory`; future reviewed case/long-term retrieval remains under the memory domain.
- `ActionToolExecutor -> ActionExecutor`

Executor 不应该承载复杂业务逻辑。它只做 context/args 映射、调用 domain service、把结果转成统一 `ToolResult`。

## Tool Catalog

Catalog 是 graph-facing capability 的唯一声明源。每个工具 descriptor 至少包含：

```python
class ToolDescriptor(BaseModel):
    name: str
    capability_type: Literal["business", "knowledge", "memory", "action"]
    operation: Literal["read", "search", "write", "draft", "execute"]
    side_effect: Literal[
        "none",
        "read_only",
        "retrieval",
        "internal_write",
        "external_write",
    ]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_permission: str
    caller_allowlist: list[str]
    exposure: Literal["planner_visible", "node_only", "internal"]
    executor: str
    event_family: Literal["tool_call", "rag_retrieval", "memory", "action"]
    requires_approval: bool = False
    resource_type: str | None = None
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False
```

规则：

- 所有 graph-facing capability 都必须有 descriptor。
- graph node 只能调用 `caller_allowlist` 中包含自己的工具。
- planner 只能看到 `exposure="planner_visible"` 且 caller 为 `investigate` 的只读/检索/记忆读工具。
- `execute_action` 只能看到 `exposure="node_only"` 且 caller 为 `execute_action` 的 action 工具。
- `memory_write` 只能看到 `exposure="node_only"` 且 caller 为 `memory_write` 的 memory write 工具。
- action 工具可以在同一个 catalog 中声明，但不能从 `investigate` 执行。
- `external_write` 必须要求 approval、safety snapshot 和 idempotency context。
- 未实现但已规划的工具可以先声明；执行时返回安全的 `unavailable`。
- Domain service 不再拥有自己的 agent-facing registry。现有 `BusinessToolService` 内部 registry 应收敛为普通 adapter map 或被 manager catalog 取代。

## Unified Context

所有 manager 调用使用同一种可信上下文。上下文字段由系统注入，不由模型、planner 或用户提供。

```python
class ToolCallContext(BaseModel):
    trusted: TrustedContext
    call: ToolCallMetadata
    approval: ApprovalContext | None = None
    safety_snapshot_ref: str | None = None
    idempotency: IdempotencyContext | None = None
    policy_snapshot_ref: str | None = None
```

`ToolCallContext` 负责把身份、权限、scope、trace、deadline、retry、idempotency、approval/snapshot 信息传给工具层。工具层只信任 context，不信任模型生成的参数。

实现可以先沿用当前扁平字段，但目标形态应拆成 `trusted`、`call`、`approval`、`idempotency` 等子对象，避免每个 read tool 都携带大量 action-only 字段。

## Unified Result

所有工具返回统一结果 envelope：

```python
class ToolResult(BaseModel):
    status: Literal[
        "success",
        "partial_success",
        "not_found",
        "permission_denied",
        "timeout",
        "unavailable",
        "conflict",
        "invalid_request",
        "invalid_response",
        "error",
    ]
    data: dict[str, Any] | None
    summary: str
    source_system: str
    data_freshness_at: datetime | None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    action_refs: list[dict[str, Any]] = Field(default_factory=list)
    error: ToolError | None = None
    retryable: bool = False
    retry_after_ms: int | None = None
    latency_ms: int
    audit_ref: str | None = None
```

当前代码中的 `ToolResultV2` 可以演进成这个形态。关键原则是：graph node 不关心后端是业务数据库、RAG、记忆服务还是动作执行器，统一消费同一个结果 envelope。

## Manager 执行策略

`UnifiedToolManager.invoke(...)` 必须按以下顺序做校验：

1. descriptor 存在。
2. `ctx.caller_node` 在 `descriptor.caller_allowlist` 中。
3. `ctx.permissions` 包含 `descriptor.required_permission`。
4. 工具副作用允许由当前 caller 执行。
5. `args` 符合 `descriptor.input_schema`。
6. deadline 和 attempt 限制允许继续执行。
7. requires approval 的工具必须带 approval/safety snapshot。
8. write-capable 工具必须带 idempotency key。
9. executor 存在且支持该工具。
10. executor 输出符合统一结果契约。

任何失败都返回安全 `ToolResult`。不得把 raw exception、raw args、prompt、未脱敏 payload 泄露到用户可见状态或 trace event。

Manager 是唯一执行 agent-facing 校验的位置。Domain service 不重复校验 descriptor、caller allowlist 或 tool permission；它只保留领域安全校验，例如 merchant ownership、业务状态约束和数据投影。

## Caller 边界

### `investigate`

允许：

- `read`
- `retrieval`
- `memory_read`

禁止：

- `memory_write`
- `action_draft`
- `action_execute`
- 任何 `internal_write` 或 `external_write`

`investigate` 可以运行 bounded loop。每轮只能选择一个工具，通过 manager 调用一次，累积 fact/evidence/memory，记录 trace event，然后根据证据充分性、无可用工具、资源上限或不可恢复错误停止。

### `execute_action`

允许：

- `action_draft`
- `action_execute`

必须具备：

- graph state 中确定性生成的 action payload；
- risk assessment；
- 需要时带 approval result；
- 需要时带 safety snapshot；
- idempotency key。

模型不能直接选择 action execution tool。是否进入 action path 由 graph 的 deterministic routing 决定。

### Memory Write Node

允许：

- `memory_write`

必须具备：

- final response 或 outcome state；
- deterministic memory write policy；
- 对模型生成内容做结构化校验后才能写入。

## 推荐目录结构

目标结构应该让“统一工具层”和“底层实现”一眼分开：

```text
src/tools/
  contracts.py
  catalog.py
  manager.py
  executors/
    business.py
    knowledge.py
    memory.py
    action.py

src/business/
  service.py
  adapters.py
  schemas.py

src/knowledge/
  service.py
  retrieval.py
  schemas.py
  citation.py

src/memory/
  service.py
  repository.py

src/actions/
  executor.py
  drafts.py

src/integrations/
  demo_business/
    orders.py
    refunds.py
    tickets.py
  rag/
    policy_search.py
```

依赖方向必须保持：

```text
graph nodes -> src/tools -> domain services -> integrations/repositories
```

Domain service 不 import graph node。Raw adapter 不 import manager。Domain service 不再定义第二套 agent-facing tool registry。

## 迁移计划

### Phase 1: 固化统一契约

- 将 `ToolCallContext`、`ToolResultV2`、`ToolDescriptor`、`UnifiedToolManager` 移到或镜像到中立的 `src/tools/`。
- 临时保留 compatibility import。
- 增加 descriptor 字段、exposure/caller/side-effect/action-safety 组合的测试。

### Phase 2: 接入 ActionExecutor

- 新增 `ActionExecutor` / `ActionToolExecutor`。
- 将 `create_coupon_grant_draft` 放到 action executor 后面。
- 修改 `execute_action`，改为调用 `UnifiedToolManager.invoke(...)`。
- write-capable 工具强制要求 caller、idempotency，以及需要时的 approval/snapshot context。

### Phase 3: 删除重复 registry

- 下线 `src/agent/tools/contracts.py` 和 `src/agent/tools/registry.py`。
- 移除 `BusinessToolService` 内部 agent-facing catalog/manager 职责。
- policy search 兼容测试迁移到 unified manager 路径。
- graph-facing 调用不再使用旧 `ToolInvocationContext` / `ToolExecutionResult`。

当前落地状态：

- `src/tools/catalog.py` 是唯一 agent-facing descriptor/catalog 来源。
- `src.business_tools` 兼容包已删除；新代码必须使用 `src.business`、`src.tools.catalog` 和 `src.tools.contracts`。
- `BusinessToolService` 使用 `BUSINESS_READ_TOOLS` 作为 business domain 内部 implementation map；它只维护 input model、adapter、slot/resource/argument 映射，不查 descriptor、不检查 caller allowlist、不检查 tool permission、不校验 catalog input/output schema。
- `UnifiedToolManager` 是 agent-facing descriptor lookup、caller allowlist、permission、input schema、output schema 和 side-effect 校验入口。

### Phase 4: 重命名 raw tools

- 将 `src/agent/tools/get_order.py` 等 raw function 移出 agent tools 目录。
- 改名为 integration 或 raw adapter。
- 加测试确保 graph node 不能直接 import raw adapter。

### Phase 5: 补齐 Memory tools

- 通过 `MemoryToolExecutor -> SessionPrecedentSearchService` 实现当前 `search_case_memory` 过渡检索。
- memory write 只允许 dedicated memory write node 调用。
- `investigate` 继续只允许 memory read。

### Phase 6: 禁止 graph 直连 raw adapter

- 增加测试或静态检查，禁止 graph node import raw adapter。
- graph node 只允许 import `UnifiedToolManager`、统一 contracts 和 typed state helpers。

## 最终目标

最终架构应该能用这几句话解释清楚：

```text
所有 graph-facing capability 只声明一次。
所有 graph-facing tool call 都经过 UnifiedToolManager。
planner-visible、node-only、internal 三类 view 从同一个 catalog 派生。
read / retrieval / memory / action 共享同一套 context 和 result contract。
副作用由 caller allowlist、approval context 和 idempotency 共同约束。
raw adapter 只是内部实现细节。
```

这样既能统一工具系统，又不会把 tool invocation 变成不受控的通用执行后门。
