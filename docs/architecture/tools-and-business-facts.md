<!-- generated-by: gsd-doc-writer -->
# 工具平台与业务事实边界

> 文档类型：CURRENT
> 描述范围：当前工具平台、业务事实服务和跨边界调用契约
> 最后核验：2026-08-04（当前工作区）
> 权威来源：当前 ToolPlatform、业务服务、可信上下文、契约 schema 与边界测试
> 更新触发：工具 catalog/policy/runtime、业务事实或查询契约、scope 与投影边界变化

本文描述 MOCA 当前代码已经实现的边界，不把目标规范或旧重构方案当作运行时事实。核心原则是：`ToolPlatform` 负责统一暴露、授权、校验、分发和结果投影；各领域 service 负责本领域真实性；业务事实、政策证据、记忆上下文、工具结果与动作草稿是五种不同对象，不能互相冒充。

## 总览

```text
FastAPI/auth boundary
  -> TrustedContextFactory -> TrustedContext -> ToolCallContext
  -> investigate（只读、有限循环）
       -> ToolPlatform.visible_tools() -> ToolViewV1（给 planner）
       -> ToolPlatform.invoke()
            -> ToolCatalog / ToolDescriptor
            -> input validation
            -> ToolPolicyEngine.runtime_auth()
            -> business | knowledge | memory executor
            -> domain service
            -> output validation
            -> ToolResultProjector
       -> business facts / policy candidate refs / contextual case memory
  -> evidence build + claim verification + risk/approval
  -> action_draft（独立写路径）
       -> ToolPlatform.invoke("create_coupon_grant_draft", ...)
       -> ActionToolExecutor -> ActionService -> durable ActionDraft
```

在工具发现和工具调用路径中，`investigate` 与 `action_draft` 通过 `ToolPlatform` 选择 descriptor/executor，不直接选择业务 adapter；默认 executor 由 `ToolPlatform.with_defaults(session)` 组装。无数据库 session 时使用 stub executor，调用安全返回 `unavailable`。这并不代表所有图节点都只依赖该门面：会话结果持久化、知识核验以及记忆生命周期节点仍会直接组合各自的 service/repository。`ToolCatalog.invoke()` 本身也是 declaration-only compatibility shim，不执行工具。源码锚点：`src/tools/platform.py::ToolPlatform`、`src/tools/catalog.py::ToolCatalog`、`src/tools/runtime.py::ToolRuntime`、`src/agent/nodes/investigate.py`、`src/agent/nodes/claim_verify.py`、`src/agent/nodes/memory_write.py`。

## Catalog、descriptor 与 planner view

`src/tools/catalog.py` 中的 `_TOOL_DECLARATIONS` 是当前声明源。每个 `ToolDescriptor` 同时声明：名称、read/retrieval/write 类型、输入/输出 schema、side effect、必需权限、caller allowlist、事件族、资源类型、executor、暴露级别，以及 approval/safety snapshot/idempotency 要求。

Catalog 是全量能力表，不等于模型可见能力表。`ToolPolicyEngine` 只把同时满足以下条件的 descriptor 投影成 `ToolViewV1`：executor 可用、`exposure="planner_visible"`、caller 在 allowlist、`ctx.permissions` 含 `tool:<name>`。`ToolViewV1` 只暴露 `name`、`description`、prompt-safe `input_schema`、`safe_usage_notes`、`result_contract_version`；executor、权限规则和内部元数据不进入 prompt。

| 工具 | 类型 / 暴露 | Executor | 当前能力边界 |
| --- | --- | --- | --- |
| `get_order`、`get_refund_case`、`get_ticket` | read / planner-visible | business | 已实现 tenant + merchant ownership 约束的详情读取，成功时产出 `BusinessFactRefV1` |
| `business_query` | read / planner-visible | business | 已实现受控 aggregate/list/detail/breakdown/compare 查询；只接受 `BusinessQuerySpec`，不接受 SQL 或自由 where |
| `query_business_metric` | read / planner-visible | business | compatibility 入口；转换成 aggregate `BusinessQuerySpec` 后走同一查询服务 |
| `get_logistics`、`get_merchant_risk` | read / planner-visible | business | 已声明并可分发，但当前 domain service 只返回 typed `unavailable`，不伪造数据 |
| `search_policy` | retrieval / planner-visible | knowledge | 已接 `PolicyKnowledgeService`，返回候选 `EvidenceRefV1` |
| `search_sop` | retrieval / planner-visible | knowledge | 已声明且 executor 可分发，但当前返回 typed `unavailable` |
| `search_case_memory` | retrieval / planner-visible | memory | 只检索已发布、未删除、未过期且 prompt-safe 的 reviewed case memory；结果仅作上下文 |
| `create_coupon_grant_draft` | write / node-only | action | 只允许 `action_draft` caller；创建 durable demo draft，不向 planner 暴露 |

标准 API 身份只会把 `orders:read`、`refunds:read`、`tickets:read`、`knowledge:read`、`metrics:read`、`business:query` 映射为对应工具权限。其他工具即使已注册，也必须获得显式 server-side `tool:*` permission 才可能可见；审批恢复路径会在已批准时注入 `tool:create_coupon_grant_draft`。因此“在 catalog 中”不表示“默认 chat 请求可调用”。源码锚点：`src/platform/trusted_context.py::SCOPE_TO_TOOL_PERMISSION`、`src/api/routers/approvals.py::_resume_graph_config`。测试锚点：`tests/tools/test_tool_platform.py::test_visible_tools_matches_catalog_investigate_allowlist`、`test_tool_view_exposes_only_prompt_safe_fields`。

## Runtime policy、dispatch 与 fail-closed 顺序

`ToolRuntime.invoke()` 的当前顺序是硬边界：

1. 查找 descriptor；未知名称返回 `not_found`。
2. 在 runtime authorization 之前校验输入 schema，避免未经校验的参数进入 resource binding 或 decision event。
3. `ToolPolicyEngine.runtime_auth()` 依序检查 caller allowlist、permission、side effect、resource scope、approval、safety snapshot、idempotency。
4. 按 `descriptor.executor` 找到一个领域 executor；不存在时返回 `unavailable`。
5. 捕获 executor exception，并映射为不含原始异常的安全 `ToolResultV2`。
6. 对成功/部分成功或携带 data 的结果执行 descriptor output-schema 校验。
7. 失败的输出被替换为 `invalid_response`，原始 data 不进入 outcome。
8. `ToolResultProjector` 生成 graph、prompt、resource/audit refs 和 debug 四类分离投影。

输入/输出 schema 使用 `src/tools/validation.py` 支持的受限 JSON Schema 子集。`business_query` 等严格 schema 设置 `additionalProperties: false`；investigate planner 还会再次拒绝 schema properties 之外的参数。runtime authorization 会在 visibility 之后重新执行，因此“曾经可见”不能替代调用时权限检查。测试锚点：`tests/tools/test_tool_platform.py::test_business_query_policy_denies_authority_and_freeform_db_args_before_dispatch`、`test_runtime_auth_gate_sequence_is_declarative_and_ordered`、`test_output_schema_failure_returns_invalid_response_without_raw_data`。

当前 decision-event 写入是 best-effort：`ToolPlatform` / `ToolRuntime` 捕获事件写入异常，不能据此宣称每次 visibility 或 runtime decision 都一定持久化。调用结果本身仍按上述 fail-closed 路径返回。

## 输入、结果与投影契约

跨工具入口的稳定对象定义在 `src/tools/contracts.py`：

- `ToolCallContext`：trusted identity/scope 的投影加本次调用字段，例如 `tool_call_id`、`caller_node`、deadline、attempt、idempotency、approval/snapshot refs。
- `ToolRequest`：工具名、arguments、argument hash 与 redaction policy version；identity 不在 request arguments 中。
- `ToolResultV2`：统一 status、data、safe summary、source/freshness、两类 typed refs、安全 error、retry 与 audit metadata。
- `ToolInvocationOutcome`：原始的已验证 `tool_result`、分层 `projection`、policy decision 及可选 decision-event id。

`ToolResultProjector` 不把 `result.data` 原样送入 graph 或 prompt。它只提取 allowlisted scalar、关系提示、受控 metric/business-query shape、envelope 中的 typed refs，以及清洗后的 case-memory item；prompt 文本有长度上限，raw/debug/secret/PII sentinel 不进入 normalized/prompt/debug surface。`raw_artifact_ref/hash` 只是可选引用字段，projector 不创建 artifact storage。当前 investigate 持久化工具结果时显式传入 `raw_result_ref=None`、`raw_result_hash=None`，所以不能把现状描述成“已保存 raw tool payload”。源码锚点：`src/tools/projection.py::ToolResultProjector`、`src/agent/nodes/investigate.py::_append_tool_result_record`、`src/conversation/service.py::ConversationService.append_tool_result`。测试锚点：`tests/tools/test_tool_platform.py::test_tool_result_projector_blocks_raw_data_from_prompt_and_graph_surfaces`。

## TrustedContext 与 MerchantScope

`TrustedContextFactory.create_from_request()` 在 API/auth/run 边界构造 canonical `TrustedContext`。它从已验证 token scopes 与角色允许 scopes 的交集派生 tool permissions，并从服务端用户记录派生 merchant scope；用户文本、planner args 和 graph checkpoint 都不能扩大这些字段。`src/api/routers/agent.py::chat` 与 run API 把该对象注入 graph config，再通过 `project_to_tool_context()` 生成每次调用的 `ToolCallContext`。

`MerchantScopeV1` 采用 deny-first、all-provided-dimensions 语义：

- 空 `merchant_ids` 是 deny-all；只有显式 `"*"` 才表示 merchant-id wildcard。
- support、manager、兼容 merchant 角色从服务端 `user.merchant_id` 得到 own-bound scope；缺失绑定时得到空 scope。
- admin 得到 `merchant_ids=["*"]`。
- 非 admin 的 server override 当前只对 `merchant_ids` 强制收窄：不能加入新 merchant id，也不能设置 wildcard。`categories` / `risk_levels` 会参与后续 `allows()` 匹配，但当前 factory 没有校验它们相对基础 scope 的单调收窄，因此不能宣称整个 `MerchantScope` 已具备完整的 override 单调性保证。
- 如果同时提供 merchant/category/risk 维度，每个已提供维度都必须匹配。

权限检查分两层。Tool policy 对显式 `merchant_id` / `target_merchant_id` 立即检查 scope；对 `order_no`、`refund_case_no`、`ticket_id` 这类需要查库才能确定归属的标识，只记录 `requires_domain_scope_check`，随后由 business integration 以 tenant predicate 查询并核验当前用户的 merchant binding。只有通过领域校验的结果才能成为 business fact。源码锚点：`src/tools/policy.py::ToolPolicyEngine._build_resource_binding`、`src/business/service.py::BusinessFactService._read_tool`、`src/integrations/demo_business/authz.py::merchant_can_access`。测试锚点：`tests/tools/test_tool_platform.py::test_tool_platform_business_read_domain_scope_denial_is_no_leak`。

## BusinessFactService 与查询层

`BusinessToolExecutor` 是薄适配器，只调用 `BusinessFactService` / `BusinessToolService`；它不直接 import repository 或 demo integration。`BusinessFactService` 拥有 scope/ownership、bounded retry、adapter 结果清洗和业务事实聚合。

### 单资源事实

`BusinessFactResultV1` 包含 tenant、status、fact、`business_fact_refs`、resource version/freshness、source system、scope check、missing facts 与 safe errors。成功结果必须同时具备非 `null` fact、至少一个 service-approved `BusinessFactRefV1`，且每个 ref 的 tenant 必须与调用上下文一致；当前实现没有拒绝空字典 `{}`。缺 ref 或 tenant 不一致会降级为不含事实的 `unavailable`。拒绝、跨租户、not-found、stale 和 adapter exception 都不会回显查询标识、上游错误或资源是否存在。

当前真正有数据的单资源读取是 order、refund case、ticket。Adapter 使用严格 Pydantic projection，只选择业务允许字段；例如 ticket 不返回 PII-heavy messages。`get_logistics` 与 `get_merchant_risk` 仍是 typed unavailable seam。源码锚点：`src/business/adapters.py`、`src/business/service.py::_to_business_fact_result`。测试锚点：`tests/business/test_service.py::test_business_fact_service_rejects_domain_success_without_service_refs`、`test_business_fact_service_denials_are_generic_no_leak`。

### `business_query`

`BusinessQueryRegistry` 是 operation/resource/metric/time/status/field/sort/limit 的 data-only allowlist；`BusinessQuerySpec` 使用 `extra="forbid"` 做组合兼容性校验；`BusinessQueryCompiler` 只生成 SQLAlchemy statements，不接受 raw SQL、自由 where、任意 cursor 或 authority 字段。

当前 runtime 范围是：

- aggregate：`order_count`、`refund_case_count`、`pending_ticket_count`、`coupon_record_count`、`merchant_refund_rate`。
- list/detail：仅 `order`。
- breakdown/compare：仅 `order_count` + `order`；compare 只支持 `previous_period`。
- `query_business_metric` 转换为 aggregate query 后进入相同 service path。

Registry 也声明 `refund_case`、`ticket`、`coupon_record`、`merchant_metric` 的字段 taxonomy，但这不等于这些资源已具备 list/detail runtime。未启用组合由 compiler 返回 `invalid_request`。

查询先从 trusted merchant scope 得到 authorized merchant ids，再编译 tenant/merchant predicates；scope 在排序、limit 和 existence 判断之前生效。显式越权或空 scope 返回 typed no-leak payload：rows 为空、无 `BusinessFactRefV1`，并从 answer context 移除原始 merchant/resource id。list/detail 仅返回 registry 允许字段，order list 不暴露 `buyer_name` 或 `merchant_id`。时间窗口以 `Asia/Shanghai` 解释，并由 `ctx.effective_at` 固定本次计算边界。`coupon_record_count` 统计 MOCA 的 `issue_coupon` draft 记录，不代表外部优惠券发放成功。

`BusinessQueryResultV1.answer_context` 只保留可重放 query spec、结果 refs、允许的 drilldown、显示字段、cursor 与 scope/time/filter 摘要。后续 drilldown 必须构造新 spec，再次经过 ToolPlatform、schema、permission 和 scope 校验；API 使用 `safe_business_query_api_payload()` 做二次 allowlist 投影。源码锚点：`src/business/query/{registry,schemas,compiler,projection}.py`、`src/business/service.py::query_business`。测试锚点：`tests/business/test_business_query_service.py::test_business_query_list_orders_applies_scope_before_limit_and_returns_cursor`、`test_business_query_invalid_inputs_fail_closed_without_querying`。

## 事实、证据、记忆、工具结果与动作草稿

| 对象 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| `BusinessFactResultV1` / `BusinessFactRefV1` | 当前 tenant/merchant scope 下读取到的订单、退款、工单、查询或指标事实及其来源引用 | 政策是否允许某动作 |
| `EvidenceRefV1` / `VerifiedEvidencePackageV1` | 特定 policy document/chunk/version/hash 在当前 tenant、有效期和检索配置下的政策证据 | 当前订单状态、退款状态、merchant metric 等业务事实 |
| `ToolResultV2` | 一次工具调用的统一传输 envelope；可分别携带 business refs 或 policy refs | 它本身不是新的权威来源，也不能把任意 data 自动升级成事实/证据 |
| reviewed case memory | 已审核案例的 contextual precedent；当前检索只发布 `auto_approved` / `approved` 且 prompt-safe 的记录 | 政策证据、当前业务事实、审批或动作权限 |
| `ActionDraft` | 在 exact payload/snapshot/merchant/fact/evidence/risk binding 下创建的 durable 提案记录 | 外部动作已经执行或成功 |

Knowledge executor 返回的 `search_policy` 候选 ref 还要经过 canonical content、text hash、policy version、effective date、tenant/merchant scope 等校验，才能进入 `VerifiedEvidencePackageV1`。Claim verifier 对 claim type 分开判定：business-fact claim 必须有匹配的 `BusinessFactRefV1`；policy evidence 不能补缺失的 business authority；action recommendation 需要政策支持和 merchant-scoped business authority。反向也一样：`business_query` 不能满足 policy evidence requirement。源码锚点：`src/knowledge/service.py::{build_verified_context,verify_claims}`、`src/knowledge/schemas.py`。测试锚点：`tests/knowledge/test_claim_verification_bundle.py::test_verify_claims_blocks_business_fact_claim_without_business_fact_authority`、`test_tenant_public_policy_cannot_support_action_recommendation_without_action_authority`。

## 只读调查与动作草稿的硬边界

`investigate` 的 planner 每轮只能返回一个严格结构化决定：`{next_tool,args,reason}` 或 `{stop,stop_reason}`。它只能选择 planner-visible read/retrieval descriptor；write、node-only、wrong-caller 或不可用工具都会在 planner 校验或 runtime auth 被拒绝。循环默认最多 3 次，配置上限为 5，同时受总 deadline 与每个调用键的 `max_attempts` 约束；缺失或无效 `TrustedContext` 时不执行工具。源码锚点：`src/agent/nodes/investigate.py`、`src/agent/nodes/investigate_planner.py`。

动作不会从 investigate 直接发生。`create_coupon_grant_draft` 仅由 `action_draft` 节点调用，并至少要求 safety snapshot 与 idempotency context。`ActionService` 再验证：payload hash、snapshot ref/hash、target merchant 与 run scope、business fact refs，以及“已批准的 approval request”或“服务端 mint 且仍有效的一次性 auto-action capability”。任一 binding 不一致即返回安全错误，不创建 draft。

当前写入结果固定为 `execution_mode="demo"`；`action_draft_created` 事件明确记录 `external_side_effect=false`。所以 UI、回复和审计只能说“已创建动作草稿”，不能说“优惠券已发放”或“外部系统已执行”。源码锚点：`src/agent/nodes/action_draft.py`、`src/tools/executors/action.py`、`src/actions/service.py::ActionService.create_coupon_grant_draft`。

## 调用约束示例

业务统计只能提交受控 spec：

```json
{
  "operation": "aggregate",
  "resource": "order",
  "metric_id": "order_count",
  "time_preset": "this_week"
}
```

调用方不能在该对象中加入 `tenant_id`、`merchant_scope`、`raw_sql` 或自由 `where`；这些要么来自 trusted context，要么根本不属于允许契约。成功结果的 `business_fact_refs` 可支撑业务事实 claim，但如果回答还声称“政策允许补偿”，仍必须另外取得并验证 `EvidenceRefV1`。若后续需要写动作，必须经过 claim verification、risk/approval 或 auto-capability、safety snapshot，再进入独立的 action-draft 路径。

## 关键源码与测试入口

- 平台与契约：`src/tools/{platform,catalog,contracts,policy,runtime,validation,projection}.py`
- 领域 executors：`src/tools/executors/{business,knowledge,memory,action}.py`
- 业务事实与查询：`src/business/service.py`、`src/business/adapters.py`、`src/business/query/`
- Trusted context：`src/platform/trusted_context.py`、`src/platform/context_projections.py`
- 只读调查与动作草稿：`src/agent/nodes/investigate.py`、`src/agent/nodes/action_draft.py`、`src/actions/service.py`
- 主要回归测试：`tests/tools/`、`tests/business/`、`tests/knowledge/`
