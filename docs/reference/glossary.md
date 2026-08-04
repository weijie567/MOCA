<!-- generated-by: gsd-doc-writer -->
# MOCA Canonical Glossary

| 元数据 | 值 |
| --- | --- |
| 文档类型 | NORMATIVE |
| 描述范围 | MOCA canonical 术语、权威边界与禁止混用的近义表达 |
| 最后核验 | 2026-08-04（当前工作区） |
| 权威来源 | canonical schema owners、当前架构文档与跨边界契约 |
| 更新触发 | canonical 名称、schema owner、authority 或文档状态词变化 |

## 使用规则

本文规定 MOCA 文档、代码评审、接口说明和测试名称应采用的术语。定义以 canonical schema owner 为准；“当前是否已实现”仍必须由源码、测试和 `CURRENT` 架构文档证明。[跨边界契约](contracts.md)定义边界，本 glossary 固定写法，两者都不能把 `TARGET` 自动升级为现状。

三个总原则：**ref 不是对象本体，projection 不是权威源，context 不是 authorization**。任何 LLM、memory、trace 或 UI 文本都不能因为“看起来正确”而越过所属领域的 service/schema owner。

表中的“不要混称”是禁止的语义替换，不只是写作偏好。兼容字段或历史投影可以保留旧字符串，但新代码、路由和文档标题必须使用推荐写法。

## 执行身份、连续性与观察面

详细当前行为见 [Agent 工作流](../architecture/agent-workflow.md)与 [Trace / Replay](../architecture/trace-and-replay.md)。

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **Agent run** / `run_id` | 一次持久化 run 请求/执行生命周期的聚合身份；它可以尚未被 claim，也可在同一 run 下包含初始 graph invocation 与后续可信 resume invocation。`AgentRun` 持有状态、时间和结果摘要 | thread、单次 HTTP request、单次 graph invocation、trace、replay event | [`AgentRun`](../../src/db/models.py#L350-L389) |
| **thread** / `thread_id` | 多个 turn/run 的会话连续性键；checkpoint 实际隔离键为 `tenant:user:thread` | run、case、tenant、checkpoint row | [`TrustedContext`](../../src/platform/trusted_context.py#L90-L105) · [checkpoint 边界](../architecture/agent-workflow.md#编译状态与入口边界) |
| **trace ID** / `trace_id` | 一次请求或调用链的可选关联标识；同一 run 的不同 HTTP 请求可以不同 | `run_id`、Replay `sequence`、Trace 视图 | [`ReplayEventV3`](../../src/replay/schemas.py#L37-L65) |
| **Trace** | 面向人和 UI 的调试投影，合并 `AgentStep`、审批与 draft，并按时间展示 | Replay、checkpoint、原始 transcript、执行日志真相全集 | [Trace 架构](../architecture/trace-and-replay.md#三类持久化对象) |
| **Replay** / `ReplayResponseV3` | 从持久化 `AgentTraceEvent` 按 run 内 `sequence` 生成的脱敏审计时间线 | resume、rerun、Trace、memory、SSE | [`ReplayEventV3`](../../src/replay/schemas.py#L37-L78) |
| **checkpoint** | LangGraph 的持久化执行状态，用于恢复图位置和受控 working state | session memory、Replay、Trace、业务数据库 | [Agent 工作流](../architecture/agent-workflow.md#编译状态与入口边界) |
| **interrupt** | `approval_gate` 暂停当前 checkpoint 的 LangGraph 控制流事件 | clarification、审批决定、run terminal、异常 | [Approval 边界](../architecture/security-approval-and-actions.md#interrupt决策与-resume) |
| **resume** | 服务端以可信 `TrustedApprovalResultV1` 和 `Command(resume=...)` 继续同一 run/checkpoint | Replay、deterministic rerun、新 run、用户下一轮澄清 | [`TrustedApprovalResultV1`](../../src/approvals/schemas.py#L234-L274) |
| **rerun** | 用固定输入/版本/依赖重新执行并比较结果的评测概念；当前 trace/replay API 不提供它 | Replay 或 checkpoint resume | [Trace / Replay 总览](../architecture/trace-and-replay.md#总览) |

## Graph vocabulary

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **node** | `StateGraph` 注册的可执行状态转换单元；当前 canonical node 的 `status=runtime`、`runnable=true` | router、route key、service、post-run side effect | [`graph_vocabulary.py`](../../src/agent/graph_vocabulary.py#L9-L76) |
| **router** | 条件边调用的决策函数，读取 state 并返回 route key；不是一个业务节点 traversal | node、policy service、LLM planner | [`graph_vocabulary.py`](../../src/agent/graph_vocabulary.py#L9-L76) |
| **route key** | router 返回并由 path map 解析的字符串；可与目标 node 同名，也可只是分支标签 | registered node；例如 `terminal_error` 不是节点 | [条件路由](../architecture/agent-workflow.md#条件路由) |

历史字符串只允许用于存量 trace 的 `historical_projection`：`classify_intent` / `intent_classification` → `contextual_intent_resolve`，`classify_intent:pre_route` → `safety_pre_route`，`session_memory_load` → `session_context_load`，`long_term_memory_retrieve` / `reviewed_memory_context_retrieve` → `memory_context_load`，`extract_slots` → `slot_resolution_gate`，`generate_recommendation` → `recommendation_generation`，`assess_risk_and_approval` → `risk_gate`，`route_after_intent` → `route_after_contextual_intent`，`route_after_slots` → `route_after_slot_resolution`。这些映射均 `runnable=false`，不可作为当前写入、路由或审批 authority（[`graph_vocabulary.py`](../../src/agent/graph_vocabulary.py#L74-L154)）。

## 可信上下文与工具契约

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **`TrustedContext`** | 仅由 API/auth/run 边界从已验证用户、token scopes 和服务端参数构造的身份/scope 根 | request body、prompt、AgentState、tool args、JWT payload 原文 | [`trusted_context.py`](../../src/platform/trusted_context.py#L90-L168) |
| **`MerchantScopeV1`** | deny-first、`all_provided_dimensions` 的 merchant/category/risk 允许域；非 admin override 当前只对 `merchant_ids` 强制子集收窄与禁止 wildcard，尚未校验 `categories` / `risk_levels` 相对基础 scope 的单调性 | merchant ID、角色、permission list、目标 merchant 事实证明 | [`MerchantScopeV1`](../../src/platform/trusted_context.py#L39-L78) |
| **`ToolDescriptor`** | catalog 中的完整能力声明：schema、side effect、permission、caller、executor、exposure 与安全要求 | planner 可见工具、runtime 可用性、一次调用授权 | [`ToolDescriptor`](../../src/tools/catalog.py#L16-L35) |
| **`ToolViewV1`** | 从 descriptor 和 visibility policy 派生的五字段 prompt-safe planner view | descriptor、permission grant、runtime authorization、tool implementation | [`ToolViewV1`](../../src/tools/contracts.py#L153-L166) |
| **`ToolResultV2`** | 一次工具调用的统一、已校验 transport envelope，可携带 typed business/policy refs | business fact、policy evidence、raw upstream result、动作成功 | [`ToolResultV2`](../../src/tools/contracts.py#L69-L95) |

“在 catalog 中”“对 planner 可见”“本次允许调用”“调用成功”是四个不同判断。完整边界见 [工具与业务事实](../architecture/tools-and-business-facts.md#catalogdescriptor-与-planner-view)。

## 业务事实、政策证据与 grounding

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **authority** | 某领域中可决定真实性或授权状态的 canonical service/schema；authority 必须按领域分开 | confidence、context、provenance、引用数量、LLM 判断 | [跨边界契约](contracts.md) |
| **business fact** | `BusinessFactResultV1` 中经 tenant/merchant scope 与 freshness 校验的当前领域事实；跨层用 `BusinessFactRefV1` 引用 | policy evidence、tool data、memory、用户陈述 | [`BusinessFactResultV1`](../../src/business/schemas.py#L31-L52) · [`BusinessFactRefV1`](../../src/tools/contracts.py#L44-L67) |
| **candidate evidence** / `EvidenceRefV1` | 被召回的 policy doc/chunk/version/hash 身份；仍需 canonical re-fetch 与时效/scope/hash 校验 | verified evidence、citation、business fact | [`EvidenceRefV1`](../../src/knowledge/schemas.py#L32-L67) |
| **verified evidence** / `VerifiedEvidencePackageV1` | 通过 canonical policy 校验的证据包及分离的 prompt/verifier/debug 投影 | 检索命中、业务事实、claim 已受支持、审批授权 | [`VerifiedEvidencePackageV1`](../../src/knowledge/schemas.py#L112-L132) |
| **citation** | 给用户或 verifier 的 `citation_id`、label、snippet 与到 evidence ref 的映射 | evidence 本体、语义支持证明、grounding 结果 | [`PromptCitation`](../../src/agent/rag_context/schemas.py#L70-L95) |
| **material claim** / `MaterialClaimV1` | 准备发布或用于动作判断的结构化声明，带 claim type、evidence/business refs 与来源步骤 | 最终回答、已验证事实、recommendation 文本、审批决定 | [`MaterialClaimV1`](../../src/knowledge/schemas.py#L135-L153) |
| **grounding** | 按 claim type 检查正确 authority、membership、scope/freshness、规则和 support，产出 `ClaimVerificationBundleV1` | RAG retrieval、citation membership、字符串相似、模型自评 | [`ClaimVerificationBundleV1`](../../src/knowledge/schemas.py#L178-L190) · [RAG / Grounding](../architecture/rag-and-grounding.md#citation-与-materialclaim-grounding) |

推荐写“claim 由 verified policy evidence / current business fact 支持”；不要写“有 citation 所以事实正确”或“tool success 所以政策允许”。

## 记忆与工作上下文

所有 prompt-facing memory 的 authority 都固定为 `contextual_only`；它们可帮助理解，不可成为 policy、business fact、approval、action 或 Replay truth。[记忆架构](../architecture/memory.md#阅读边界)

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **session context** / `SessionContextBundle` | exact `tenant + user + thread` 的短期槽位、摘要、消息与 tool-summary 连续性 | checkpoint、跨线程记忆、业务事实、案例先例 | [`SessionContextBundle`](../../src/memory/schemas.py#L147-L181) |
| **Case Working Context (CWC)** | exact `tenant + case` 的 versioned active working context，保存来源指针、待办与建议 | reviewed precedent、case 真相表、`EvidenceRefV1`、动作结果 | [`CaseWorkingContextContentV1`](../../src/memory/case_working_context_schemas.py#L74-L100) |
| **reviewed case precedent** | 已发布且 prompt-safe 的 `CaseMemory`，用于相似案例提示 | active CWC、当前 case 状态、政策证据、审批依据 | [`CaseMemorySearchItem`](../../src/memory/schemas.py#L392-L409) |
| **long-term preference** | 当前主路径允许的显式软偏好；只有允许来源、scope、review 和 PII 状态才可发布 | 通用 long-term fact、硬规则、behavior inference、tool outcome | [`LongTermMemoryView`](../../src/memory/schemas.py#L309-L325) · [`memory policy`](../../src/memory/policy.py#L24-L65) |

CWC 字段名 `verified_facts` 仅表示“带来源的 working-context 记录”，不是当前 `BusinessFactResultV1`；`policy_refs` 也不是 verified evidence package。

## 风险、审批与动作

| 推荐写法 | 是什么 / authority 边界 | 不要混称 | Canonical owner |
| --- | --- | --- | --- |
| **risk decision** / `RiskDecisionV1` | 对 exact action payload hash 的风险结论，带规则/配置版本与 `approval_required` | approval decision、permission、safety snapshot、动作授权本身 | [`RiskDecisionV1`](../../src/approvals/schemas.py#L54-L73) |
| **safety snapshot** / `ActionSafetySnapshot` | 对 action、target merchant、facts、evidence 和配置的 immutable hash-bound 安全材料 | risk decision、approval、checkpoint、完整原始 payload | [`ActionSafetySnapshot`](../../src/approvals/snapshots.py#L48-L78) |
| **approval** | 持久化 request/level/assignment/decision/event 的版本化状态机 | `approval_gate` 节点、聊天中的“同意”、risk allow、action execution | [`approvals/schemas.py`](../../src/approvals/schemas.py) |
| **decision context** / `ApprovalDecisionContextV1` | 服务端生成的 reviewer 安全视图，包含 immutable bindings 与允许决策集合；客户端只回传所需 version/hash 子集及其 decision，服务端重取 context 后构造 `ApprovalDecisionCommand` | approval decision、resume payload、authorization token、客户端原样回传的完整 DTO | [`ApprovalDecisionContextV1`](../../src/approvals/schemas.py#L32-L51) |
| **trusted approval result** / `TrustedApprovalResultV1` | `ApprovalService` 产出的、可供 graph resume 再校验的受信结果 | 客户端 dict、普通聊天、decision context、interrupt payload | [`TrustedApprovalResultV1`](../../src/approvals/schemas.py#L234-L274) |
| **capability** / `AutoActionCapabilityRefV1` | 服务端 mint、短期、opaque、一次性并绑定 run/actor/scope/action/snapshot/risk 的窄授权 | permission、JWT、approval、通用 bearer token、`auto_allowed=true` | [`actions/capabilities.py`](../../src/actions/capabilities.py#L23-L61) |
| **action draft** / `ActionDraftV2Data` | 通过 approval 或 capability 完整绑定后持久化的 demo 提案；`external_side_effect=false` | action execution、coupon issued、refund completed、外部系统成功 | [`ActionDraftV2Data`](../../src/actions/schemas.py#L21-L57) |

推荐写“审批通过后创建 action draft”；禁止写“审批通过后已执行动作”。完整链见 [安全、审批与动作](../architecture/security-approval-and-actions.md#概览)。

## 文档类型与能力状态

文档类型描述“这份文档在做什么”，能力状态描述“某项能力是否落地”；两组词不能互换。

| 文档类型 | 推荐定义 | 不要混称 |
| --- | --- | --- |
| **CURRENT** | 代码库当前事实快照；若与源码/测试漂移，应修文档 | NORMATIVE 目标、历史设计、未来承诺 |
| **NORMATIVE** | canonical 术语、边界或必须满足的契约；可同时标注 IMPLEMENTED/TARGET/DEFERRED | 已实现证明、操作教程、个人建议 |
| **GUIDE** | 面向执行者的步骤、示例与解释；应引用 CURRENT/NORMATIVE 依据 | canonical owner、架构事实源、契约本身 |

| 能力状态 | 推荐定义 | 不要混称 |
| --- | --- | --- |
| **IMPLEMENTED** | 当前主路径可达，并有源码或测试证据；范围必须写清 | 仅有 schema、manifest、mock、目标描述 |
| **TARGET** | 已接受的目标契约，但当前实现证据不足或尚未完整接线 | CURRENT、IMPLEMENTED、自动可用 |
| **DEFERRED** | 有意延后且应写明目标里程碑、触发条件或重新评估入口 | IMPLEMENTED、隐含 TODO、模糊“以后” |

状态词的跨边界用法以 [contracts](contracts.md) 为准。`NORMATIVE` 文档中的一句话仍可能是 `TARGET`；`CURRENT` 文档不得把 `TARGET` / `DEFERRED` 写成已落地事实。

## 强制消歧速查

- `run != thread != trace_id`；run 是执行，thread 是连续性，trace ID 是关联标识。
- `Trace != Replay != checkpoint`；三者分别是调试投影、审计时间线和执行恢复状态。
- `Replay != resume != rerun`；读取历史、继续中断和重新执行是三件事。
- `node != router != route key`；只有注册 node 是业务 traversal。
- `ToolDescriptor != ToolViewV1 != ToolResultV2`；声明、可见投影和调用结果不可互换。
- `BusinessFactRefV1 != EvidenceRefV1 != citation`；业务事实引用、政策候选引用和展示引用属于不同 authority。
- `session context != CWC != reviewed case precedent != long-term preference`；四者 scope、生命周期与用途不同。
- `risk allow != approval approved != action draft != external execution`；当前最后一项未由 draft 表示。
