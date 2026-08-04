<!-- generated-by: gsd-doc-writer -->
# MOCA Agent Runtime 与工作流

> 文档类型：CURRENT
> 描述范围：当前已实现的 LangGraph 运行时、节点与路由行为
> 最后核验：2026-08-04（当前工作区）
> 权威来源：`src/agent/graph.py`、路由与节点实现、canonical graph 测试
> 更新触发：注册节点、条件路由、checkpoint、retry、interrupt/resume 或终态语义变化

## 概览

MOCA Agent 当前是一个以 `AgentState` 为共享状态、由 LangGraph `StateGraph` 编排的单图运行时。`build_graph()` 精确注册 **15 个业务节点**；`START`、`END` 是 LangGraph 哨兵，不计入节点数，`terminal_error` 是条件路由键，也不是节点。主图以请求规范化和安全预路由开始，经会话上下文、意图与槽位解析、调查与证据验证，最后在风险、审批和动作草稿边界收口；所有图内终点都先进入 `final_response`，再到 `END`。[图构建源码](../../src/agent/graph.py#L224-L341)与[canonical baseline 测试](../../tests/architecture/test_canonical_graph_baseline.py#L44-L89)共同锁定该集合。

![MOCA Agent 运行时流程 V2（当前 15 个注册节点）](../moca-agent-runtime-flow-v2.png)

上图用于快速阅读；涉及分支条件、失败收口和恢复语义时，以本文下方表格及当前源码为准。

## 编译、状态与入口边界

- 应用启动时创建 `AsyncPostgresSaver`、执行 `setup()`，然后只编译一次图并挂到 `app.state.agent_graph`；`build_graph()` 最终调用 `builder.compile(checkpointer=checkpointer)`。[应用生命周期](../../src/api/main.py#L29-L35) · [编译点](../../src/agent/graph.py#L224-L341)
- 图状态类型是 `AgentState`。其中线程身份、上下文连续性等字段可随 checkpoint 保留；每轮临时意图、证据、风险、审批与动作字段由 `receive_request` 重新投影或清空，避免上一轮权限状态泄漏到本轮。[状态契约](../../src/agent/state.py#L65-L198) · [轮次重置](../../src/agent/nodes/receive_request.py#L112-L244)
- 普通同步入口 `/chat` 只把 `user_query` 和由可信请求上下文派生的身份投影放入 state；数据库 session、`trusted_context` 和 checkpoint `thread_id` 放入 `config.configurable`，随后调用 `graph.ainvoke()`。[普通调用入口](../../src/api/routers/agent.py#L41-L102)
- checkpoint 键是 `tenant_id:user_id:thread_id`，因此不同租户或用户即使提交相同业务 `thread_id` 也不会共用图状态。[checkpoint 命名](../../src/api/routers/agent.py#L241-L262)
- 异步 run/SSE 入口复用同一个已编译图和相同可信配置边界；创建 run 只持久化 `pending`，事件端点才领取并执行该 run。[run/SSE 入口](../../src/api/routers/agent_runs.py#L139-L183) · [执行配置](../../src/api/routers/agent_runs.py#L216-L271)
- 聊天文本不能直接完成审批。只有审批 API 生成的受信 `approval_result.v1` 才能通过 `Command(resume=...)` 恢复同一 checkpoint；恢复配置重新由服务端构造。[审批恢复调用](../../src/api/routers/approvals.py#L372-L405) · [恢复配置](../../src/api/routers/approvals.py#L1140-L1160)

## 15 个注册节点

### 1. 接入、会话与意图

| # | 节点 | 当前职责与边界 | 失败或跳过语义 | 事实锚点 |
|---|---|---|---|---|
| 1 | `receive_request` | 建立本轮 `current_run_id`/时间与 trace；保留经过绑定校验的 drilldown 上下文和待补槽位 flow，重置其余本轮临时状态。 | 不访问外部服务；始终进入 `safety_pre_route`。 | [源码](../../src/agent/nodes/receive_request.py#L112-L244) · [重置测试](../../tests/agent/test_nodes/test_receive_request.py#L12-L74) |
| 2 | `safety_pre_route` | 纯确定性执行 `detect_pre_route()`，写入 `pre_route_decision`、`safety_flags`、`routing_hints`；不调用 LLM、memory 或 tool。 | 审批式聊天、多目标或需澄清输入在路由层进入 `clarification_gate`。 | [源码](../../src/agent/nodes/safety_pre_route.py#L63-L72) · [边界测试](../../tests/agent/test_nodes/test_safety_pre_route.py#L64-L104) |
| 3 | `session_context_load` | 在意图解析前读取同线程 session context；显式本轮槽位覆盖会话槽位，跨商户或超出可信 merchant scope 的上下文会被过滤。其 authority 固定为 `contextual_only`。 | 功能关闭、缺 session 或读取异常时返回空的 `skipped`/`unavailable` 上下文并继续，不授予业务事实或动作权限。 | [源码](../../src/agent/nodes/session_context_load.py#L31-L133) · [过滤逻辑](../../src/agent/nodes/session_context_load.py#L166-L211) · [失败测试](../../tests/agent/test_nodes/test_session_context_load.py#L352-L389) |
| 4 | `contextual_intent_resolve` | 先处理 small talk、待补槽位回复、指标查询和 drilldown 等确定性路径；否则用结构化 LLM 产生候选意图，再由 intent/slot policy registry 决定有效意图、operation、task plan 与 required slots。不能写审批、动作、tool result 等 authority 字段。 | 结构化输出最多手动尝试 2 次；仍失败时写入 `unsupported`、置信度 0 和澄清提示，路由到 `clarification_gate`。 | [源码](../../src/agent/nodes/contextual_intent_resolve.py#L1089-L1246) · [禁止写字段](../../src/agent/nodes/contextual_intent_resolve.py#L78-L91) · [失败测试](../../tests/agent/test_nodes/test_contextual_intent_resolve.py#L320-L351) |
| 5 | `slot_resolution_gate` | 结构化抽取本轮槽位，合并确定性指标/业务查询槽位，并按 provenance、继承策略和 required-slot policy 生成 `active_slots`、缺失项与 route decision。 | 结构化输出最多手动尝试 2 次；若仍失败且无确定性槽位可用，记录 `llm_slot_extraction_error` 并进入 `clarification_gate`。 | [源码](../../src/agent/nodes/slot_resolution_gate.py#L66-L136) · [失败测试](../../tests/agent/test_nodes/test_slot_resolution_gate.py#L449-L476) |

### 2. 上下文、调查与证据

| # | 节点 | 当前职责与边界 | 失败或跳过语义 | 事实锚点 |
|---|---|---|---|---|
| 6 | `memory_context_load` | 通过 reviewed-memory helper 读取长期偏好、已审核案例与 case working context，并统一投影为 canonical `memory_context_load` trace/metrics；内容只作上下文。 | 缺可信上下文或服务异常时返回 `reviewed_memory_skipped`/`reviewed_memory_unavailable`，随后仍进入 `investigate`。 | [源码](../../src/agent/nodes/memory_context_load.py#L16-L52) · [语义测试](../../tests/agent/test_memory_context_load.py#L129-L168) · [失败测试](../../tests/agent/test_memory_context_load.py#L227-L258) |
| 7 | `investigate` | 在可信可见 tool 集合内执行有界 plan/act 循环，累积 prompt-safe tool projection、业务事实引用、政策候选引用和错误；默认最多 3 次迭代，硬上限 5。 | planner 输出无效时改用确定性 fallback；缺可信上下文、deadline、非法 tool 或 tool platform 异常会停止调查并保留安全错误投影，不直接取得审批或动作权限。 | [源码](../../src/agent/nodes/investigate.py#L222-L446) · [fallback](../../src/agent/nodes/investigate.py#L449-L506) · [失败测试](../../tests/agent/test_nodes/test_investigate.py#L903-L934) |
| 8 | `rag_context_build` | 把调查得到的候选 policy refs 与 business fact refs 交给 knowledge service，构造 `VerifiedEvidencePackageV1`、citation map 和 evidence map。 | 缺可信 knowledge context 或 service 异常产生 `build_error` package；不抛出可继续的未验证证据，路由到 `final_response`。 | [源码](../../src/agent/nodes/rag_context_build.py#L24-L55) · [失败测试](../../tests/agent/test_nodes/test_rag_context_build.py#L203-L284) |
| 9 | `recommendation_generation` | 只消费允许生成的 verified package，生成结构化 recommendation；重新校验 citation membership，解析 canonical action，并产出 material claims。 | 已有 retrieval-safety draft 时跳过 LLM；package 不可用或两次预期校验失败时降级为 `insufficient_evidence`，不保留 action authority。 | [源码](../../src/agent/nodes/recommendation_generation.py#L159-L318) · [跳过测试](../../tests/agent/test_nodes/test_recommendation_generation.py#L412-L427) · [失败测试](../../tests/agent/test_nodes/test_recommendation_generation.py#L1028-L1036) |
| 10 | `claim_verify` | 调用 policy knowledge service 验证 material claims、business facts 与 proposed action，输出统一 claim bundle、blocked claims 和 safe support refs。 | verifier 缺失或抛错时生成 `overall_status=error`、`route=final_response` 的空安全 bundle。 | [源码](../../src/agent/nodes/claim_verify.py#L19-L37) · [错误 bundle](../../src/agent/nodes/claim_verify.py#L103-L112) · [失败测试](../../tests/agent/test_nodes/test_claim_verify.py#L207-L232) |

### 3. 风险、审批与响应

| # | 节点 | 当前职责与边界 | 失败或跳过语义 | 事实锚点 |
|---|---|---|---|---|
| 11 | `risk_gate` | 合并确定性风险规则与结构化 LLM 结果；仅在 claim verification 允许时构造 canonical proposed action，并绑定 action hash、持久化 safety snapshot、merchant/business/evidence refs、risk decision、approval plan 或 server-minted auto-action capability。也负责可信 edit 后的重新评估。 | claim/binding/snapshot/capability 任一不可信就清空 proposed action 和审批/动作 authority，转为 blocked/manual review；预期 LLM 错误两次后使用确定性风险 fallback。 | [源码](../../src/agent/nodes/risk_gate.py#L1271-L1414) · [绑定失败收口](../../src/agent/nodes/risk_gate.py#L1058-L1219) · [测试](../../tests/agent/test_nodes/test_risk_gate.py#L499-L624) |
| 12 | `clarification_gate` | 生成用户可读问题和 `ClarificationRequest`，声明 `resume_policy=same_thread_only`，不触碰审批生命周期。 | 这不是 LangGraph interrupt；本轮经 `final_response` 结束，用户下一轮在同 thread 回复后由 `receive_request` 恢复待补 flow。 | [源码](../../src/agent/nodes/clarification_gate.py#L17-L46) · [测试](../../tests/agent/test_clarification_gate.py#L9-L74) |
| 13 | `approval_gate` | 校验 approval plan 幂等键后调用 LangGraph `interrupt()`；interrupt payload 只供展示，审批持久化由 ApprovalService 边界负责。恢复后再次校验 schema、tenant、run、action hash 与 snapshot 绑定。 | 缺幂等键或 resume payload 不可信时不创建动作，直接写安全响应；可信 `pending` 会再次进入本节点并重新 interrupt。 | [源码](../../src/agent/nodes/approval_gate.py#L48-L107) · [恢复校验测试](../../tests/test_approval_gate.py#L114-L232) |
| 14 | `action_draft` | 经唯一 tool 边界 `create_coupon_grant_draft` 创建持久化的 **demo action draft**；要求 verifier allow，且具备可信 approved result 或 server-minted capability、可信 context 与完整绑定。不会注册或执行 production side effect 节点。 | tool 调用 `attempt=1/max_attempts=1`；授权、持久化、outcome、draft identity 或关键审计失败都投影为稳定 `terminal_error`，不会伪装成功。 | [源码](../../src/agent/nodes/action_draft.py#L415-L556) · [单次调用](../../src/agent/nodes/action_draft.py#L507-L522) · [终态测试](../../tests/test_graph_routing.py#L648-L730) |
| 15 | `final_response` | 以确定性模板汇总澄清、直接回答、业务事实、验证结果、manual review、审批结果及 demo draft；写入最终文本和 final status 后进入 `END`。 | action draft 终态不完整时输出稳定 error；一般的证据不足/manual-review 路径不会标为 completed。当前有一个窄例外：`policy_qa` 已有强证据、无动作且仅 partial-overlap 需人工复核时，可保留 `verification_route=manual_review`，同时以 `final_status=completed` 输出安全政策说明。当前实现不调用 LLM，虽在 graph 层仍挂有 retry policy。 | [源码](../../src/agent/nodes/final_response.py#L954-L1005) · [终态测试](../../tests/agent/test_phase22_final_response.py#L552-L608) |

## 条件路由

`build_graph()` 当前有 10 个条件路由点；完整 path map 由 [graph.py](../../src/agent/graph.py#L246-L337) 定义，并由 [baseline 测试](../../tests/architecture/test_canonical_graph_baseline.py#L119-L175)核对。

| 来源 / router | 可能的 route key | 当前判定摘要 |
|---|---|---|
| `safety_pre_route` / `route_after_safety` | `session_context_load`、`clarification_gate`；path map 另注册 `final_response` | `none`/`safety_sensitive` 继续；审批式聊天、多目标、显式需澄清、异常或未知值进入澄清。当前 router 实现没有返回 `final_response` 的分支。[源码](../../src/agent/routing.py#L635-L656) |
| `contextual_intent_resolve` / `route_after_contextual_intent` | `final_response`、`clarification_gate`、`investigate`、`slot_resolution_gate` | direct-response intent 直接答；低置信度、审批式聊天或未知 intent 澄清；有 required-slot policy 先过槽位门；其余使用 intent registry route。[源码](../../src/agent/routing.py#L713-L744) |
| `slot_resolution_gate` / `route_after_slot_resolution` | `clarification_gate`、`investigate`、`memory_context_load` | LLM 槽位错误、未知 intent、policy mismatch、malformed/missing slot 进入澄清；需 reviewed/long-term memory 时先加载 memory；槽位完整则调查。[源码](../../src/agent/routing.py#L747-L793) |
| `investigate` / `route_after_investigate` | `clarification_gate`、`final_response`、`rag_context_build`、`recommendation_generation` | 缺业务事实则澄清；fact-only 已有事实、权限阻断、retrieval error/no evidence/低分时直接收口；需要政策证据或已有候选 refs 时建 RAG package，否则生成建议。[源码](../../src/agent/routing.py#L1279-L1321) |
| `rag_context_build` / `route_after_rag_context` | `recommendation_generation`、`clarification_gate`、`final_response` | 缺必要验证输入时澄清；`verified`、安全的 `not_required` 或允许的 `partial` 可生成；`no_evidence`、未授权、过期、冲突、hash/scope 无效、`build_error` 均收口。[源码](../../src/agent/routing.py#L1099-L1121) |
| `recommendation_generation` / `route_after_recommendation` | `claim_verify`、`final_response` | missing info 或非 allow verification 收口；存在 material/user-visible claim、proposed action，或 unresolved canonical action 时必须进入 claim verification。[源码](../../src/agent/routing.py#L1124-L1134) |
| `claim_verify` / `route_after_claim_verify` | `risk_gate`、`final_response` | blocked claim、缺 bundle、非 `continue`、非 `verified/not_required` 均收口；只有已验证 action recommendation 或 risk signal 才进入风险门。[源码](../../src/agent/routing.py#L1146-L1160) |
| `risk_gate` / `route_after_risk` | `approval_gate`、`action_draft`、`final_response` | 必须同时满足 verifier allow、正向 action claim、proposed action、完整且已验证 snapshot 绑定；blocked 收口；需审批且 approval plan 完整才进入审批；无需审批且 capability 有效才创建草稿。[源码](../../src/agent/graph.py#L70-L89) |
| `approval_gate` / `route_after_approval` | `approval_gate`、`risk_gate`、`action_draft`、`final_response` | 可信 approved accept/approve 进入草稿；可信 pending 自环；可信 edit + superseded + 新 hash + `resume_route=risk_gate` 返回风险重评；拒绝、需补充、取消或任何不可信绑定收口。[源码](../../src/agent/graph.py#L132-L150) |
| `action_draft` / `route_after_action_draft` | `final_response`、`terminal_error`（两者都映射到 `final_response` 节点） | 只有 durable、audited、identity-matched demo draft 为 completed；其余返回 `terminal_error`，再由 `final_response` 输出 error status。[源码](../../src/agent/routing.py#L226-L270) |

普通边只有：`START → receive_request → safety_pre_route`、`session_context_load → contextual_intent_resolve`、`memory_context_load → investigate`、`clarification_gate → final_response → END`。[源码](../../src/agent/graph.py#L244-L245) · [源码](../../src/agent/graph.py#L255-L255) · [源码](../../src/agent/graph.py#L275-L275) · [源码](../../src/agent/graph.py#L295-L295) · [源码](../../src/agent/graph.py#L339-L339)

## 典型运行路径

1. 安全预路由拦截：`START → receive_request → safety_pre_route → clarification_gate → final_response → END`。典型输入是普通聊天入口中的“同意/approve”式审批文本；不会加载 memory、调用 tool 或进入审批节点。[集成测试](../../tests/agent/test_graph.py#L1647-L1682)
2. 直接回答：`… → session_context_load → contextual_intent_resolve → final_response → END`。适用于 small talk 或 intent registry 定义的 direct-response intent。
3. 缺槽位：`… → contextual_intent_resolve → slot_resolution_gate → clarification_gate → final_response → END`。下一轮同 thread 回复后，pending flow 可在接入/意图节点确定性恢复。
4. 需要上下文的调查：`… → slot_resolution_gate → memory_context_load → investigate → …`；不需要 reviewed/long-term memory 时由槽位门直接进入 `investigate`。
5. 事实查询：`… → investigate → final_response → END`。fact-only intent 取得业务事实后不必经过 recommendation/RAG。
6. 政策建议：`… → investigate → rag_context_build → recommendation_generation → claim_verify → final_response → END`；若无需政策证据，`investigate` 可直接进入 recommendation。
7. 低风险草稿：`… → claim_verify → risk_gate → action_draft → final_response → END`，前提是 snapshot verified 且 server-minted auto-action capability 有效。
8. 高风险审批：`… → claim_verify → risk_gate → approval_gate → interrupt`；可信审批恢复后，approved 走 `action_draft`，reject/respond/ignore 走 `final_response`，edit 回 `risk_gate` 重评，pending 再次 interrupt。

## Retry、interrupt、resume 与 fail-closed

### Retry 分层

| 机制 | 当前范围 | 精确语义 |
|---|---|---|
| LangGraph node retry | `contextual_intent_resolve`、`slot_resolution_gate`、`recommendation_generation`、`risk_gate`、`final_response` | 共用 `RetryPolicy(max_attempts=2)`，即最多 2 次节点尝试；源码未覆盖其他 retry 参数。[注册点](../../src/agent/graph.py#L53-L54) · [节点绑定](../../src/agent/graph.py#L228-L242) |
| 节点内 structured-output retry | 前四个结构化 LLM 节点（不含 `final_response`） | 每次节点调用内部最多 2 次 provider/validation 尝试；trace 中的 `retry_count` 只表示这个内部循环，不代表 LangGraph node retry。[意图](../../src/agent/nodes/contextual_intent_resolve.py#L1100-L1140) · [槽位](../../src/agent/nodes/slot_resolution_gate.py#L70-L105) · [建议](../../src/agent/nodes/recommendation_generation.py#L189-L292) · [风险](../../src/agent/nodes/risk_gate.py#L1319-L1378) |
| 调查循环 | `investigate` | 不是图级 retry。默认 3 次、最大 5 次迭代；同一 tool+args 默认最多 1 次，`unavailable` tool 会标记为不可再用；planner 失败先尝试确定性 fallback。[源码](../../src/agent/nodes/investigate.py#L46-L49) · [循环](../../src/agent/nodes/investigate.py#L233-L395) |
| 动作 tool | `action_draft` | 明确 `attempt=1`、`max_attempts=1`，没有节点内自动重试；幂等和失败恢复由持久化/调用边界处理。[源码](../../src/agent/nodes/action_draft.py#L507-L522) |
| `approval_gate` pending 自环 | `approval_gate` | 这是新的 interrupt/恢复周期，不是失败重试，也不消费 LLM retry 次数。 |

### Interrupt 与 resume

`clarification_gate` 与 `approval_gate` 的“等待”语义不同：前者生成普通回复并结束本轮；后者调用 `interrupt()` 暂停当前 checkpoint。审批恢复 payload 必须来自服务端 `TrustedApprovalResultV1`，并同时匹配 tenant、run、action payload hash、snapshot ref/hash 及版本字段；普通聊天文本、缺字段、跨租户/跨 run 或 hash 不一致都不能恢复动作路径。[节点校验](../../src/agent/nodes/approval_gate.py#L28-L45) · [router 校验](../../src/agent/graph.py#L203-L221) · [路由矩阵测试](../../tests/test_graph_routing.py#L750-L853)

### Fail-closed 收口表

| 故障位置 | 收口行为 |
|---|---|
| safety / intent / slot router 抛错或返回未注册值 | 进入 `clarification_gate`；不猜测下一业务节点。[wrapper](../../src/agent/routing.py#L361-L382) |
| session/reviewed memory 不可用 | 使用空的 contextual-only 投影继续；不得作为业务事实、证据或动作授权。 |
| investigate planner 不可信 | 使用确定性 fallback；fallback 也不合法、缺 trusted context、deadline 或 tool platform 异常时停止调查，随后由 router 澄清或安全回答。 |
| RAG package 不可验证、claim verifier 报错 | 进入 `final_response`；未验证材料不会进入动作路径。 |
| recommendation 缺 package、citation 无效或预期校验失败 | 生成 insufficient-evidence draft 并收口；不会保留 canonical action。 |
| risk/action 绑定不完整 | 清空 proposed action、approval plan、snapshot/capability authority，输出 blocked 或 manual-review 安全结果。 |
| approval plan/result 不可信 | 不 interrupt 或不接受 resume，进入 `final_response`；不会创建 action draft。 |
| action draft 授权、持久化、identity/outcome/audit 失败 | `terminal_error → final_response → END`，最终 `final_status=error` 与稳定安全错误码；没有独立 error node，也没有外部副作用成功表述。 |
| 未被节点捕获的程序错误 | 仅带 retry policy 的节点可由 LangGraph 再尝试；耗尽或无 retry policy 时交由 API 错误边界处理，不能视为正常 completed。 |

## Graph vocabulary 与计数边界

`graph_vocabulary.py` 对 15 个当前节点做 `runtime/runnable` identity mapping，并对 9 个主要 router 做同样映射。[当前词表](../../src/agent/graph_vocabulary.py#L44-L70) · [词表测试](../../tests/agent/test_graph_vocabulary.py#L44-L75) 当前图实际上有 10 个条件路由点：post-draft 的 `route_after_action_draft` 由 `graph.py` 和 routing baseline 直接约束，但未列入该 vocabulary 的 router entries。历史 trace 名称只能在读取投影时映射，不能作为当前注册节点、route key 或 resume authority。[读取投影](../../src/agent/graph_vocabulary.py#L72-L192)

因此，判断“当前可运行图”应遵循以下顺序：

1. 以 `build_graph().add_node/add_edge/add_conditional_edges` 为执行事实；
2. 以 canonical graph baseline 测试校验节点集合和 path map；
3. 以 vocabulary 解释 trace/read projection，不用它替代 graph registration；
4. `START`、`END`、`terminal_error` 以及节点文件中的 helper 都不计入 15 个注册节点。
