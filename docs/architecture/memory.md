<!-- generated-by: gsd-doc-writer -->
# MOCA 当前记忆架构

> 文档类型：CURRENT
> 描述范围：当前短期、工作上下文、案例先例和长期偏好记忆边界
> 最后核验：2026-08-04（当前工作区）
> 权威来源：当前源码、迁移、配置和测试
> 更新触发：`AgentState`/checkpoint、记忆 schema/lifecycle、review policy、检索或写入边界变化

## 阅读边界

本文只描述当前仓库已经实现的行为。旧的业务型和通用助手记忆设计文档仅用于定位概念；具体结论以源码、数据库模型与迁移、配置和测试为准。

MOCA 的所有 prompt-facing memory 都只有 **contextual authority**：`authority_class = contextual_only`。记忆可以帮助解析“刚才那笔订单”、恢复槽位、提供偏好或相似案例提示，但不能替代当前业务事实、政策证据、审批决定、动作授权、动作结果、审计事实或 replay truth。该约束同时存在于 schema、数据库约束、prompt 投影和 claim verifier 测试中（[memory policy](../../src/memory/policy.py#L9-L31) · [context refs](../../src/memory/context_refs.py#L12-L176) · [CWC schema](../../src/memory/case_working_context_schemas.py#L74-L100) · [权威边界测试](../../tests/agent/test_memory_evidence_boundary.py#L264-L487)）。

## 总览

```text
可信请求身份
  ├─> checkpoint -> AgentState（恢复；每轮先清临时权限/结果）
  ├─> session_context_load
  │     └─ conversation/summary/tool hints + session_memories
  │          -> SessionContextMemory(contextual_only)
  └─> memory_context_load（TrustedContext 收窄 scope）
        ├─ long_term_memories（已发布软偏好）
        ├─ case_memories（已发布先例）
        └─ case_working_contexts（当前 case 工作上下文）
             -> MemoryContextBundle -> prompt-safe projector

async run/SSE/approval 成功终态 -> message/summary + isolated memory/CWC writes
同步 /chat 成功终态 -> message/summary + memory_write side effects（当前不写 CWC 终态）
独立旁路 -> ReplayEventV3（per-run 脱敏事件线；不是 memory）
```

主图在意图解析前加载 session context，在槽位解析后按需加载 reviewed memory 与 CWC。async run/SSE 以及 approval resume 的成功终态由 API finalizer 持久化消息、滚动摘要、session/long-term/case memory side effects 和 CWC；同步 `/chat` 当前会写消息与滚动摘要并调度 memory write，但不会执行 CWC terminal write（[graph](../../src/agent/graph.py#L224-L341) · [session load](../../src/agent/nodes/session_context_load.py#L31-L133) · [reviewed/CWC load](../../src/agent/nodes/reviewed_memory_context_retrieve.py#L39-L105) · [finalizer](../../src/api/services/agent_run_memory.py#L105-L198) · [同步 chat](../../src/api/routers/agent.py#L184-L230)）。

## 七种状态与记忆表面

| 表面 | 身份键 / scope | 当前职责 | 明确不负责 |
|---|---|---|---|
| `AgentState` + checkpoint | checkpoint `thread_id = tenant:user:thread` | 图执行恢复、跨节点状态、interrupt/resume 和有限的同上下文连续性 | 长期语义记忆、业务数据库、审计时间线 |
| 原始会话与 thread summary | `tenant + user + thread` | 保留消息、safe tool summary，并生成确定性的滚动摘要 | 自动成为偏好或案例先例 |
| session memory / session context | `tenant + user + thread` | 短 TTL 槽位、未决问题、上次意图和安全摘要；为当前线程补全指代 | 跨用户/跨线程召回、政策或业务权威 |
| Case Working Context（CWC） | `tenant + case`；thread 通过 link 关联 | 当前 case 的可修订工作台、来源指针、建议与待办 | 已审案例库、最终业务状态、动作结果真相 |
| reviewed case precedent | `tenant + merchant/case` | 经发布的相似案例提示 | 当前 case 状态、政策证据、审批依据 |
| long-term preference | 存储 schema 支持多种 scope；当前主路径以 `merchant` 为主 | 显式软偏好和经审核的偏好候选 | 从普通聊天推断硬规则或长期事实 |
| replay | `tenant + run + sequence` | 脱敏、严格排序的运行事件投影 | 会话连续性、偏好召回、CWC 或 checkpoint 恢复 |

## AgentState 与 checkpoint

`AgentState` 是 LangGraph 的共享工作状态，图通过 `builder.compile(checkpointer=checkpointer)` 接入 PostgreSQL checkpointer。checkpoint 由服务端把租户、用户和业务 `thread_id` 拼成隔离键；它用于恢复同一图执行和保留受控的跨轮状态，不是独立 memory repository（[state contract](../../src/agent/state.py#L65-L198) · [graph compile](../../src/agent/graph.py#L224-L341) · [checkpoint key](../../src/api/routers/agent.py#L241-L243)）。

每个新回合先执行 `receive_request`。该节点会清空上一轮的意图、business context、RAG、memory bundle、风险、审批、动作和工具结果等临时字段；只有经过当前可信身份 fingerprint 校验的 drilldown 信息和待补槽位 flow 才可能保留。身份或 merchant/session/thread 绑定变化时，旧 drilldown 上下文失效（[turn reset](../../src/agent/nodes/receive_request.py#L112-L244) · [binding](../../src/agent/state.py#L201-L237) · [重置测试](../../tests/agent/test_nodes/test_receive_request.py#L12-L168)）。

因此两者分工是：checkpoint 恢复“图跑到哪里、这一轮有哪些状态”，session/CWC/long-term stores 提供“允许在以后重新加载的上下文”。不能因为字段曾在 checkpoint 中出现，就跳过本轮的 trusted scope、freshness 或 authority 校验。

## Session context、bundle 与 thread summary

`SessionMemoryBundleService` 将四类来源合成 `SessionMemoryBundle`：最新 `thread_rolling` summary、最近消息、prompt-safe tool summaries，以及 `SessionMemoryView` 槽位连续性；政策名称和历史引用只投影为 retrieval hints。各子来源读取失败时单独记录 `fallback_reasons`，不会把缺失数据伪装成成功连续性（[bundle service](../../src/memory/session_bundle.py#L30-L96) · [schemas](../../src/memory/schemas.py#L74-L181) · [bundle tests](../../tests/memory/test_session_memory_bundle.py#L53-L201)）。

`SessionContextMemory` 和外层 `SessionContextBundle` 都把 authority 固定为 `contextual_only`。`session_context_load` 按 `tenant_id + user_id + thread_id` 读取：当前回合显式槽位覆盖继承槽位；继承的 `merchant_id` 与本轮有效 merchant 或可信 scope 冲突时，旧 summary、消息、tool summaries 和槽位细节全部清空（[load node](../../src/agent/nodes/session_context_load.py#L166-L271) · [isolation tests](../../tests/memory/test_session_memory_isolation.py#L196-L448)）。

`session_memories` 对一个 `tenant + user + thread` 只允许一个未删除活动行。写入候选只从当前回合显式抽取的槽位、未决问题、意图、简短摘要和业务上下文 refs 构造；槽位带 `source_run_id`、更新时间、过期时间和兼容 intent。当前默认 TTL 为 1800 秒，summary 上限为 500 字符，写超时为 0.5 秒（[config](../../src/config.py#L30-L33) · [candidate builder](../../src/memory/write_service.py#L135-L174) · [model/index](../../src/db/models.py#L396-L436)）。

写入使用版本号和 CAS；并发的非冲突字段可以合并，显式槽位冲突、business-context ref 冲突或 retry 中的 intent 冲突会返回明确 reason code，而不是静默覆盖。过期行在新写入时 soft-delete 后重建（[service](../../src/memory/service.py#L108-L213) · [merge rules](../../src/memory/service.py#L352-L415) · [并发测试](../../tests/memory/test_session_memory_concurrency.py#L89-L359)）。

仓库仍保留 `LegacySessionPrecedentSearchService`，但当前 Agent executor 没有调用它；主路径不会跨线程搜索旧 session memory。当前会话连续性是 exact same-thread load（[legacy search](../../src/memory/search.py#L15-L63) · [repository exact load](../../src/memory/repository.py#L22-L54)）。

`ThreadRollingSummaryService` 从上一个 summary 之后的新消息和重要 tool summary 确定性地产生新摘要，记录 source message/tool-result IDs 和 hash，并对同一 source-end 幂等。它只使用清洗后的 prompt summary，去掉 raw result ref 和原始 authority/payload 标记；summary 是独立 conversation 派生物，不是 session row 或 case memory（[summary service](../../src/memory/thread_summary.py#L49-L207) · [sanitizer](../../src/memory/thread_summary.py#L210-L245) · [summary tests](../../tests/memory/test_thread_summary.py#L86-L342)）。

## Case Working Context（CWC）

CWC 是一个 case-scoped、可修订的工作上下文。每个 `tenant + case` 最多一个活动行，数据库同时强制 case 属于 tenant、`authority_class = contextual_only` 和正版本号；更新前保存上一版 revision，并用 case 级 advisory lock、row lock 和 `expected_version` 防止覆盖（[repository](../../src/memory/case_working_context.py#L44-L145) · [model](../../src/db/models.py#L583-L711) · [migration](../../src/db/migrations/versions/022_case_working_context.py#L42-L199)）。

当前内容 schema 区分 customer claims、带 source ref 的 verified facts、evidence pointers、actions taken、policy refs、agent recommendations、pending tasks、commitments 和 next action。这里的“verified fact”仍只是带来源的 CWC 工作记录；`CaseWorkingContextEvidencePointerV1` 也只是指向 tool result、conversation message 或 business-fact summary 的 contextual pointer，不是 `EvidenceRefV1`（[CWC schemas](../../src/memory/case_working_context_schemas.py#L10-L100) · [schema boundary tests](../../tests/memory/test_case_working_context_repo.py#L177-L272)）。

运行时生命周期如下：

1. `memory_context_load` 从当前可信槽位解析 refund case UUID 或 case number，建立/去重 thread-case link，然后读取该 `tenant + case` 的活动 CWC；没有可信 case 时跳过（[lifecycle load](../../src/memory/case_working_context_lifecycle.py#L75-L187)）。
2. 成功终态后，finalizer 只投影可证明的工具摘要、policy refs、recommendation 和 next action；纯 clarification 或无可投影内容时跳过（[terminal projection](../../src/memory/case_working_context_lifecycle.py#L407-L507)）。
3. CWC service 重新验证 run 与 case 均属于 tenant，规范化所有 source refs，阻断非 prompt-safe PII，并在隔离 child session 中提交写入与 `MemoryWriteEvent`（[write service](../../src/memory/case_working_context_service.py#L47-L151) · [隔离测试](../../tests/memory/test_case_working_context_service.py#L580-L612)）。

CWC 不等于案例先例。关闭 case 后生成 `closed_case_cwc_candidate` 的投影 service 已实现：它只接受 `closed/refunded/rejected`，从活动 CWC 生成固定 caveat 的 `CaseMemoryWriteCandidate`，并要求 review；但当前 `src/` 中没有该 service 的生产调用方，因此不能把“case 关闭后自动进入 precedent 库”视为已接通能力（[precedent service](../../src/memory/case_precedent.py#L18-L129) · [投影](../../src/memory/case_precedent.py#L148-L219) · [生成测试](../../tests/memory/test_case_precedent_generation.py#L518-L577)）。

## 长期偏好与已审案例先例

### 当前写入入口

| 候选来源 | 当前策略 | prompt 可见条件 | 主路径状态 |
|---|---|---|---|
| 普通聊天或 LLM 自行推断 | 不生成长期偏好；`llm_candidate`、summary、behavior inference 等直接拒绝 | 不可见 | 已实现的拒绝边界 |
| 显式用户短语，如“记住这个偏好” | projector/service 仅接受软偏好，且必须解析到可信 merchant scope；`explicit_user_preference` 可自动发布 | 活动、未过期、prompt-safe、无 tombstone | 边界与直接调用已实现；当前生产 terminal memory write 未传 `trusted_context`，尚未接通 |
| 管理员显式保存 | `POST /api/v1/memory/long-term/preferences`，仅 `tenant` 或 `merchant` scope；保存为 `explicit_admin_preference` | 同上 | 已接 API |
| `semantic_episode_candidate` | 只允许 preference candidate，状态 `needs_review` | 审核通过前不可见 | projector/service 有实现；当前无生产调用方 |
| 关闭 case 的 CWC 候选 | `closed_case_cwc_candidate`，状态 `needs_review` | 审核通过后才可作为 precedent | generator/service 有实现；当前无生产调用方 |
| Case memory 其他自动候选 | deterministic outcome、approval state、LLM/summary/pattern 等均要求 review | `auto_approved` 或 `approved` 才可见 | service boundary 已实现 |

策略集合见 [policy](../../src/memory/policy.py#L34-L151)，显式偏好解析见 [preference capture](../../src/memory/preference_capture.py#L67-L143)，API 限制见 [memory router](../../src/api/routers/memory.py#L68-L126)，未接主流程的 semantic projector 见 [semantic episode](../../src/memory/semantic_episode.py#L50-L139)。

长期表的 schema 虽然允许 `fact/preference/constraint/pattern`，当前 `LongTermMemoryService` 明确只持久化 `memory_kind = preference`，并拒绝把 hard rule 当偏好。工具结果、当前业务对象、审批状态或普通 LLM 总结不能借 long-term memory 绕过领域权威源（[long-term service](../../src/memory/long_term.py#L54-L139) · [策略测试](../../tests/memory/test_long_term_memory_service.py#L138-L233)）。

### 审核、发布与失效

| 状态 / 动作 | Long-term preference | Case precedent | 检索结果 |
|---|---|---|---|
| `auto_approved` | 显式用户、显式管理员或已标记 human-reviewed 的允许来源 | 仅显式管理员/human-reviewed 来源 | 可检索 |
| `needs_review` | semantic preference candidate | 关闭 CWC 和其他自动 case candidates | 不可检索 |
| `approve` | 仅活动 `needs_review` 软偏好；改为 `approved`/human-reviewed/current | 仅活动 `needs_review`；记录 reviewer 与 reason | 可检索 |
| `reject` | 改为 `rejected`、非 current | 改为 `rejected` | 不可检索 |
| `supersede` | 新版本通过策略后替换旧 current；需审核的新版本在批准前不撤下旧版 | 当前没有同等 supersede service | 只返回当前发布版本 |
| `delete` | 标记 `deleted`、设置 `deleted_at`，同时创建 tombstone | 同样创建 tombstone | 立即排除 |
| `forget` | 标记 `tombstoned`、设置 `deleted_at`，同时创建 tombstone | 同样创建 tombstone | 立即排除，并阻止同 identity 重写 |

long-term lifecycle 见 [service](../../src/memory/long_term.py#L237-L374)，case lifecycle 见 [service](../../src/memory/case_memory.py#L622-L762)，review API 当前要求 `admin` 角色、相应 OAuth scope，并验证操作所带 `run_id` 属于同一 tenant（[router](../../src/api/routers/memory.py#L130-L383)）。

### Tombstone 与 no-rewrite

`delete` 和 `forget` 在当前 long-term/case service 中都会创建 tombstone；两者保留不同 review/event 语义，但都执行 no-rewrite 防护。tombstone 以 `tenant + memory_type + scope_type + scope_id` 隔离，并按 canonical `content_hash` 或允许字段形成的 `source_identity_hash` **精确匹配**；不会使用语义相似度扩大删除范围。活动 tombstone 在写入前阻断候选，也在检索 SQL 中排除历史行；过期 tombstone 才允许相同 identity 再创建（[helper](../../src/memory/tombstones.py#L12-L63) · [repository](../../src/memory/repository.py#L330-L503) · [tombstone tests](../../tests/memory/test_memory_tombstones.py#L154-L378)）。

当前 tombstone 表只接受 `long_term_fact` 和 `case_memory`。session memory 依赖 TTL/soft-delete，CWC 只有活动行与 revision 模型；两者没有对应的公开 forget/tombstone API，不能把 long-term/case 的删除语义外推到它们（[model constraint](../../src/db/models.py#L713-L772) · [session soft-delete](../../src/memory/repository.py#L144-L151)）。

## 检索、scope 与隔离

存储 schema 允许 `tenant | merchant | user | thread | case`，但当前 Agent prompt 检索面更窄。应区分“表能表达的 scope”和“运行时实际开放的 scope”。

| 表面 | 当前检索边界 | 额外过滤 |
|---|---|---|
| Session context | exact `tenant + user + thread` | TTL、intent compatibility、本轮显式槽位、merchant scope |
| CWC | exact `tenant + resolved case` | case 必须属于 tenant；thread-case link 也带 tenant/user/thread |
| Long-term prompt memory | repository 必须给 tenant 和明确 scope；Agent runtime 只下发经验证的 `merchant`，以及可验证 merchant 归属的 `case` | preference only、允许 source、`auto_approved/approved`、current、未过期、PII `none/low`、无 tombstone |
| Case precedent | Agent runtime 同样只下发 verified `merchant/case` scopes | review status、未删除/过期、PII、tombstone、可选 case type/policy metadata；有 embedding 时向量检索，否则文本/metadata 检索 |

`MemoryContextService` 把 TrustedContext 的 tenant/user/thread 作为身份过滤输入，但不会把它们自动转成全局 memory query；显式请求 `tenant/global` memory 会返回 `tenant_global_memory_unsupported`。没有可验证 merchant/case、merchant 超权或 case 无法绑定到允许 merchant 时，返回空 bundle 和明确 fallback/filter reason（[scope decision](../../src/memory/context_service.py#L123-L245) · [scope rules](../../src/memory/context_service.py#L433-L499) · [boundary tests](../../tests/memory/test_reviewed_memory_context_boundary.py#L227-L285)）。

管理员保存偏好的 API 只暴露 `tenant` 和 `merchant`；用户显式偏好的自动路径只写可信 `merchant`。因此虽然底层 schema 仍接受 `user/thread/case` 等类型，不能据此宣称当前 API 或 Agent 已提供所有 scope 的通用长期记忆（[API schema](../../src/api/schemas/memory.py#L45-L53) · [user preference scope](../../src/memory/preference_capture.py#L142-L170)）。

## PII 与 prompt-safe 投影

记忆防护分为写入、检索和 prompt 投影三层：

1. **写入门控**：session、long-term、case 和 CWC 对 `sensitive/prohibited` 返回 skip/blocked，不会把候选内容写入 memory row。Long-term、case、CWC 以及直接调用底层 `MemoryService` 的路径会持久化带 policy version/reason 等字段的 `MemoryWriteEvent`；当前主 session facade 在候选阶段 short-circuit，只返回阻断结果，不会进入底层 event 写入（[shared policy](../../src/memory/policy.py#L34-L85) · [session facade](../../src/memory/write_service.py#L138-L183) · [CWC service](../../src/memory/case_working_context_service.py#L76-L101)）。
2. **检索门控**：long-term 和 case SQL 只返回 PII `none/low`，并同时过滤未审核、过期、删除、superseded 和 tombstoned 行（[long-term query](../../src/memory/repository.py#L632-L703) · [case query](../../src/memory/case_memory.py#L427-L480)）。
3. **prompt 投影**：bundle 和 projectors 只选择允许字段、限制 item/字符数，移除 raw payload、private reasoning、authority body、debug/trace、secret、hash、`EvidenceRefV1` 和 `ReplayEventV3` 等标记。政策 mention 只能作为 retrieval hint，不能作为 evidence（[session sanitizer](../../src/memory/session_bundle.py#L18-L48) · [memory projectors](../../src/agent/context/projectors.py#L83-L96) · [prompt projection](../../src/agent/context/projectors.py#L194-L276)）。

读取或写入失败采用 fail-soft context / fail-closed authority：上下文可以为空并继续回答或要求补充，但失败不会升级记忆权限。结构化投影的泄漏测试见 [memory evidence boundary](../../tests/agent/test_memory_evidence_boundary.py#L613-L678)。

## Memory 与 replay 的身份和职责分离

| 维度 | Memory | Replay |
|---|---|---|
| 主身份 | session：tenant/user/thread；CWC：tenant/case；reviewed memory：tenant/scope | tenant/run/严格递增 sequence |
| 目的 | 下一轮的上下文提示、偏好与 precedent | 解释一次 run 发生了哪些脱敏事件 |
| 数据形态 | 可过期、可审核、可 supersede/delete/forget；prompt-facing 子集 | `ReplayEventV3` 时间线、resource refs、redacted payload、provenance/retention |
| 写入关联 | `MemoryWriteEvent` 记录 policy decision；memory node 另发 started/completed/failed replay events | `ReplayService` 分配 per-run sequence 并验证 event type、redaction 和 pairing |
| 权威转换 | memory ref 不能转成 evidence/business/approval/action/replay DTO | replay event 也不自动变成长期偏好或业务事实 |

Replay 的 strict schema 和 per-run allocator 见 [schemas](../../src/replay/schemas.py#L37-L77) 与 [service](../../src/replay/service.py#L24-L185)。测试明确要求 contextual memory refs 无法通过 `ReplayEventV3`、`BusinessFactRefV1`、approval 或 action DTO 校验，也不能产生 claim verifier 的 safe support refs（[DTO boundary](../../tests/agent/test_memory_evidence_boundary.py#L490-L572) · [claim boundary](../../tests/agent/test_memory_evidence_boundary.py#L681-L758)）。

## 写入事务与可观测性

async run/SSE 与 approval resume 的成功 finalizer 先持久化 assistant message 和 thread summary 并提交，再执行 memory 与 CWC side effects。session/long-term/case 写入通过独立 child session 提交；CWC service 同样使用 child session。子事务失败只回滚 memory side effect，不污染父请求事务。同步 `/chat` 使用另一条终态路径，目前没有 CWC terminal write（[finalizer](../../src/api/services/agent_run_memory.py#L139-L198) · [同步 chat](../../src/api/routers/agent.py#L184-L230) · [isolation helper](../../src/memory/write_isolation.py#L1-L24) · [isolation test](../../tests/memory/test_write_isolation.py#L15-L68)）。

Agent `memory_write` 节点会把其选中的 session write result 投影为 `memory_write_decision.v2`，包含 memory type、scope、PII、review status、reason、policy version、blocked-by 和 identity hashes；同批 long-term/case 结果只进入 `memory_write_results`。持久化写入服务另行生成 `memory_write_events`；管理员 long-term/case API 与 CWC service 不生成该 graph V2 投影，而且 event 与 V2 decision 只有部分字段重合，并非相同审计面。两者仍是 contextual/audit metadata，不是审批或 replay 本体（[decision schema](../../src/memory/context_refs.py#L160-L177) · [节点投影](../../src/agent/nodes/memory_write.py#L266-L287) · [event model](../../src/db/models.py#L774-L812) · [audit migration](../../src/db/migrations/versions/020_memory_write_event_policy_audit.py#L21-L42)）。

当前管理 API 位于 `/api/v1/memory`：提供待审核列表、管理员 tenant/merchant 软偏好写入，以及 long-term/case 的 approve、reject、delete、forget；路由与权限边界见 [API prefix](../../src/api/main.py#L111) 和 [memory router](../../src/api/routers/memory.py#L30-L383)。

## 当前实现限制

- `semantic_episode.py` 能生成需审核的 preference candidate，但当前生产代码没有调用该 projector。显式用户短语的 projector/service boundary 也已实现，但 async finalizer 与同步 background writer 当前都没有向 `memory_write` 传入 `trusted_context`，因此无法解析可信 merchant scope；当前真正接通的长期偏好写入主路径只有管理员 API。
- `ClosedCasePrecedentService` 能从终态 case + active CWC 生成需审核候选，但当前没有接入 refund-case close 主路径。
- storage schema 的五种 scope 不等于运行时全开放；当前 reviewed prompt retrieval 只开放经过 merchant 权限验证的 merchant/case scope。
- session 和 CWC 没有 long-term/case 同款公开 forget/tombstone lifecycle；session 使用 TTL，CWC 使用活动行、version 和 revisions。
- case retrieval 支持 embedding 字段与向量分支，但当前 `memory_context_load` 只传文本 query，没有生成 `query_embedding`。

这些限制分别可从 [write candidate call sites](../../src/memory/write_service.py#L62-L87)、[closed precedent service](../../src/memory/case_precedent.py#L58-L129)、[runtime scopes](../../src/memory/context_service.py#L433-L499) 和 [case search](../../src/memory/case_memory.py#L402-L459) 核对。
