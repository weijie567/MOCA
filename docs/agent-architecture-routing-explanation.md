# MOCA 目标 LangGraph 路由图讲解

> 用途：解释 `docs/agent-architecture-spec.md` 中 V2 细粒度流程路由图和 V2 严格 LangGraph 节点图。
>
> 重点：这不是当前 MOCA 已实现流程的复述，而是目标分层架构下的 LangGraph 设计说明。当前 MOCA 仍是较线性的 10 节点主链；本文讲的是未来目标版如何从线性 demo 升级为 intent-driven、evidence-gated、risk-controlled 的状态机。

---

## 1. 这张路由图到底是什么？

目标版 MOCA 的图可以分成两种：

### 1.1 流程路由图

流程路由图回答：

> 一个用户请求进来后，根据 intent、slots、证据、风险、审批结果，可能走哪些路线？

它会混合展示：

- LangGraph 节点；
- router 判断；
- intent path；
- service 调用说明；
- gate 分支。

所以它更像“业务流程地图”。

### 1.2 严格 LangGraph 节点图

严格节点图回答：

> 目标版 MOCA 到底建议注册哪些 `StateGraph.add_node(...)` 节点？节点之间怎么通过 conditional edge 路由？

它只包含真正的 LangGraph 节点。

旧图曾拆成 18 个节点；现行目标版严格收敛为 **16 个 canonical LangGraph nodes**：

```text
1. receive_request
2. normalize_input
3. intent_classification
4. clarification_gate
5. slot_extraction
6. session_memory_load
7. long_term_memory_retrieve
8. investigate
9. recommendation_generation
10. risk_gate
11. approval_gate
12. action_draft
13. action_execution
14. final_response
15. memory_write
16. trace_close
```

这些才是未来可以写成：

```python
builder.add_node("receive_request", receive_request)
builder.add_node("normalize_input", normalize_input)
builder.add_node("intent_classification", intent_classification)
# ...
```

的节点。

---

## 2. 图里的三类元素

读图时先区分三类东西。

### 2.1 方框：LangGraph 节点

例如：

```text
receive_request
normalize_input
intent_classification
slot_extraction
investigate
recommendation_generation
risk_gate
approval_gate
final_response
```

这些是实际干活的节点。

它们会：

- 读写 `AgentState`；
- 调 LLM；
- 调 service；
- 生成结构化输出；
- 创建审批；
- 创建动作草稿；
- 记录 trace。

### 2.2 菱形：router，不是节点

例如：

```text
route_after_intent
route_after_slots
route_after_investigate
route_after_recommendation
route_after_risk
route_after_approval
route_after_action_draft
```

这 **7 个 canonical routers** 不算 LangGraph 节点。

它们只是 conditional edge 里的函数，比如：

```python
def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent")
    confidence = state.get("intent_confidence")

    if confidence < 0.65:
        return "clarification_gate"

    if intent == "policy_qa":
        return "investigate"

    if intent == "order_status_inquiry":
        return "session_memory_load"

    if intent in {"small_talk", "unsupported"}:
        return "final_response"

    return "session_memory_load"
```

router 只负责：

> 看 state，决定下一个 node key。

router 不应该：

- 调 LLM；
- 查数据库；
- 调工具；
- 写复杂业务逻辑；
- 执行动作。

### 2.3 Service：也不是 LangGraph 节点

例如：

```text
KnowledgeService
BusinessToolService
MemoryService
RiskPolicy
ApprovalPolicy
ActionExecutor
ObservabilityService
```

这些是分层架构里的 service。

它们不是 graph 节点，而是被节点调用。

例如：

```text
investigate 节点
  -> 在 read-only allowlist 内按需调用 BusinessToolService read
  -> 按需调用 KnowledgeService RAG
  -> 按需调用 MemoryService case search
```

这样做的目的：

> LangGraph 节点负责“什么时候调用”，service 负责“怎么实现”。

---

## 3. 整体执行结构

目标版 MOCA 不是线性流水线，而是：

```text
公共入口
  -> intent 分类
  -> 按 intent 分流
  -> 按是否需要 slots / business facts / policy evidence / risk / approval / action 继续分支
  -> final_response
  -> memory_write
  -> trace_close
```

也就是：

```text
common entry
-> intent router
-> intent-specific path
-> optional risk / approval / action
-> final / memory / trace
```

所以不是所有请求都必须：

```text
slot_extraction
-> investigate
-> route_after_investigate
-> recommendation_generation
-> risk_gate
```

有些请求很短，有些请求才走完整链路。

---

## 4. 公共入口部分

所有请求通常都会先走这几个节点：

```text
START
-> receive_request
-> normalize_input
-> intent_classification
```

### 4.1 `receive_request`

这个节点负责初始化当前 run。

它做的事类似：

```text
- 接收用户 query
- 初始化 run_id / thread_id / trace_id
- 注入 tenant_id / user_id / role
- 清理上一轮临时状态
- 初始化 trace_steps
```

当前 MOCA 已经有类似节点：

```text
src/agent/nodes/receive_request.py
```

当前它会 reset 一些 ephemeral state，比如：

```text
current_intent
extracted_slots
business_context
retrieved_evidence
recommendation_draft
risk_assessment
approval_result
action_result
final_response
trace_steps
```

目标版继续保留这个入口节点。

### 4.2 `normalize_input`

这是目标新增节点。

它不是做智能判断，而是做输入标准化。

例如用户输入：

```text
帮我看一下  ord-1001 退款咋回事
```

normalize 后可能得到：

```json
{
  "normalized_query": "帮我看一下 ORD-1001 退款咋回事",
  "locale": "zh-CN",
  "channel": "chat"
}
```

它可以做：

- 去掉多余空格；
- 标准化订单号大小写；
- 标准化金额格式；
- 识别中文/英文；
- 识别渠道；
- 做轻量 keyword hints。

但它不应该：

- 决定审批；
- 查订单；
- 查政策；
- 生成最终答案。

### 4.3 `intent_classification`

这是第一个关键智能节点。

它负责判断用户的主要意图。

目标输出类似：

```json
{
  "intent": "refund_troubleshooting",
  "confidence": 0.88,
  "secondary_intents": ["compensation_suggestion"],
  "required_slots": ["order_id"],
  "extracted_slots": {
    "order_id": "ORD-1001",
    "refund_case_id": null,
    "ticket_id": null,
    "amount": null
  },
  "risk_signals": ["refund_related"],
  "needs_business_context": true,
  "needs_policy_retrieval": true,
  "approval_hint": "unknown"
}
```

intent node 可以做：

- 分类；
- 给 confidence；
- 提取粗 slots；
- 给 routing hints；
- 判断是否可能需要 business context；
- 判断是否可能需要 policy retrieval。

intent node 不应该做：

- 不生成最终答案；
- 不决定审批；
- 不执行工具；
- 不直接生成 action draft；
- 不说“可以退款”或者“应该补偿”。

审批必须交给后面的：

```text
risk_gate
approval_gate
```

---

## 5. 第一个 router：`route_after_intent`

`intent_classification` 后面，不是固定进入 `slot_extraction`。

而是先进入一个 router：

```text
route_after_intent
```

它看：

```text
intent 是什么？
confidence 是否足够？
required slots 是否明显缺失？
这个请求是不是可以直接回复？
这个请求是否需要查业务事实？
这个请求是否需要查政策？
```

然后决定下一步。

---

## 6. intent 分支一：低置信度 / 信息不足

用户可能问：

```text
这个能处理吗？
```

这句话没有说明：

- 哪个订单；
- 哪个退款；
- 哪个工单；
- 要查规则还是要执行动作。

此时 intent 可能是：

```json
{
  "intent": "unknown",
  "confidence": 0.42,
  "required_slots": []
}
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> clarification_gate
-> final_response
-> memory_write
-> trace_close
```

`clarification_gate` 会生成澄清问题：

```text
请补充你要处理的具体事项：是查询退款规则、排查某个订单/退款单，还是发起补偿/退款动作？如果是具体订单，请提供订单号或退款单号。
```

这个路径不会进入：

```text
slot_extraction
investigate
risk_gate
approval_gate
action_draft
action_execution
```

因为信息不足，不能继续查或执行。

---

## 7. intent 分支二：small_talk

用户问：

```text
你好
```

或者：

```text
你是谁？
```

intent：

```text
small_talk
```

路线很短：

```text
receive_request
-> normalize_input
-> intent_classification
-> final_response
-> memory_write
-> trace_close
```

不需要：

- slots；
- 订单；
- 退款；
- 工单；
- RAG；
- risk；
- approval；
- action。

回复可能是：

```text
你好，我是 MOCA，主要帮助处理商家售后、订单、退款、工单和补偿相关问题。
```

---

## 8. intent 分支三：unsupported

用户问：

```text
帮我写一首诗
```

或者：

```text
帮我分析股票
```

这不是 MOCA 的业务范围。

intent：

```text
unsupported
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> final_response
-> memory_write
-> trace_close
```

回复：

```text
当前 MOCA 主要支持商家售后、订单、退款、工单和补偿相关问题。这个请求不在当前支持范围内。
```

也不需要 RAG 或 risk。

---

## 9. intent 分支四：policy_qa

用户问：

```text
超过 7 天还能退款吗？
```

这是政策问答，不是具体订单处理。

intent：

```text
policy_qa
```

路线通常是：

```text
receive_request
-> normalize_input
-> intent_classification
-> investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
-> memory_write
-> trace_close
```

这里为什么可以跳过 `slot_extraction`？

因为用户问的是规则，不是具体订单。

为什么可以不查业务事实？

因为不需要查某个订单状态。`policy_qa` 仍进入 `investigate`，但其内部 bounded tool loop 可以只调用 KnowledgeService RAG，不要求先调用 BusinessToolService。

为什么可以跳过 `risk_gate`？

如果只是回答政策，不产生 proposed action，就不需要 risk gate。

但有一个例外。

如果用户问：

```text
超过 7 天还能退款吗？如果可以就帮我退。
```

这就不再是纯 policy QA，而是带 action request。

那后续会进入：

```text
risk_gate
approval_gate / action_draft
```

---

## 10. policy_qa 路径里的 evidence gate

`investigate` 完成后统一交给 `route_after_investigate`，由它判断有没有足够证据以及下一步目标。

### 10.1 有证据

例如检索到：

```json
{
  "retrieval_status": "strong_evidence",
  "best_score": 0.82,
  "evidence": [
    {
      "doc_key": "refund_policy_v1",
      "chunk_id": "refund_policy_v1_003",
      "title": "七天无理由退款规则",
      "section": "适用范围"
    }
  ]
}
```

路线：

```text
investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
```

回复需要引用证据：

```text
根据 refund_policy_v1 / refund_policy_v1_003，七天无理由退款适用于...
```

### 10.2 没有证据

如果：

```json
{
  "retrieval_status": "no_evidence",
  "best_score": 0.21,
  "evidence": []
}
```

路线：

```text
investigate
-> route_after_investigate
-> final_response
```

回复：

```text
当前知识库中没有找到足够证据支持这个判断，建议转人工处理或补充相关规则文档。
```

这很重要。

MOCA 不应该在无政策依据时编造规则。

---

## 11. intent 分支五：order_status_inquiry

用户问：

```text
ORD-1001 现在是什么状态？
```

这是业务事实查询。

intent：

```text
order_status_inquiry
```

路线通常是：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> final_response
-> memory_write
-> trace_close
```

### 11.1 为什么需要 `slot_extraction`？

因为要知道查哪个订单、退款单或工单。

例如：

```json
{
  "order_id": "ORD-1001",
  "refund_case_id": null,
  "ticket_id": null
}
```

### 11.2 为什么需要 `investigate`？

因为订单状态来自业务系统，不应该由 LLM 猜。

`investigate` 会调用 BusinessToolService，再由它调用 read tools：

```text
get_order
get_refund_case
get_ticket
```

返回类似：

```json
{
  "order": {
    "order_no": "ORD-1001",
    "status": "delivered",
    "amount": "199.00",
    "currency": "CNY"
  }
}
```

### 11.3 为什么可以跳过 RAG？

因为用户只是问状态。

不需要查政策规则。

但是如果用户问：

```text
ORD-1001 已签收还能退款吗？
```

那就不是纯订单状态查询了，需要：

```text
investigate（内部按需读取订单事实和政策证据）
-> route_after_investigate
-> recommendation_generation
```

### 11.4 为什么可以跳过 risk？

因为只是读事实，没有 proposed action。

只要没有退款、补偿、关闭工单等动作，就不需要 risk gate。

---

## 12. intent 分支六：refund / compensation / ticket 进入完整分析路径

这一类是 MOCA 最核心的业务路径。

包含：

```text
refund_troubleshooting
compensation_suggestion
ticket_reply_draft
```

典型用户问题：

```text
ORD-1001 退款为什么没到账？
```

```text
这个客户投诉很严重，可以补偿多少？
```

```text
帮我草拟一个工单回复。
```

这类请求通常需要综合：

- 用户问题；
- 订单/退款/工单事实；
- 当前平台政策；
- 历史类似 case；
- 风险规则；
- 是否需要人工审批。

典型路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> risk_gate 或 final_response
-> final_response
-> memory_write
-> trace_close
```

注意：这条路径虽然更完整，但仍然不是“所有节点都无条件执行”。

例如：

- 如果 slots 缺失，提前去 `clarification_gate`。
- 如果 `investigate` 后业务上下文仍不足，`route_after_investigate` 去澄清或安全回复。
- 如果政策证据不足，`route_after_investigate` 提前进入 insufficient evidence response。
- 如果 recommendation 没有 proposed action，可以不进 `risk_gate`。
- 如果有 proposed action，必须进 `risk_gate`。

### 12.1 `refund_troubleshooting` 示例

用户：

```text
ORD-1001 退款为什么没到账？
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
-> memory_write
-> trace_close
```

如果查到：

```json
{
  "order": {
    "order_no": "ORD-1001",
    "status": "delivered"
  },
  "refund_case": {
    "refund_case_no": "RF-9001",
    "status": "pending_payment_channel",
    "requested_amount": "199.00"
  }
}
```

再查到政策：

```json
{
  "doc_key": "refund_timeout_policy",
  "chunk_id": "refund_timeout_policy_002",
  "title": "退款超时处理规则"
}
```

最后回复：

```text
已查询到订单 ORD-1001 和退款单 RF-9001。当前退款状态为 pending_payment_channel。
根据 refund_timeout_policy / refund_timeout_policy_002，退款超时需要先核实支付通道状态。建议先检查退款通道回执；如果超过规则时限仍未完成，转人工复核。
```

这里没有 proposed action，所以可以不进入 approval/action。

### 12.2 `compensation_suggestion` 示例

用户：

```text
这个客户投诉很严重，可以给多少补偿券？
```

如果上一轮 session memory 里有：

```json
{
  "active_slots": {
    "order_id": "ORD-1001"
  }
}
```

路线：

```text
intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> risk_gate
```

recommendation 可能生成：

```json
{
  "recommended_action": "建议发放 50 元体验补偿券",
  "proposed_action": {
    "action_type": "issue_coupon",
    "amount": "50",
    "currency": "CNY",
    "target_id": "ORD-1001"
  }
}
```

因为有 proposed action，所以必须进：

```text
risk_gate
```

risk gate 判断：

```json
{
  "risk_level": "low",
  "approval_required": false,
  "rule_ref": "coupon_low_value_v1"
}
```

后续路线：

```text
risk_gate
-> action_draft
-> action_execution
-> final_response
```

如果金额是 600 元：

```json
{
  "risk_level": "high",
  "approval_required": true,
  "rule_ref": "refund_high_value_v1"
}
```

后续路线：

```text
risk_gate
-> approval_gate
```

### 12.3 `ticket_reply_draft` 示例

用户：

```text
帮我根据规则草拟一个给客户的工单回复。
```

路线：

```text
intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
```

这里通常不需要 action execution。

因为“草拟回复”不是“关闭工单”或“实际发送消息”。

如果用户说：

```text
帮我关闭这个工单并回复客户。
```

这就产生动作了，需要进入：

```text
risk_gate
approval_gate 或 action_draft
```

---

## 13. slots 部分：`slot_extraction` 和 `route_after_slots`

进入需要业务上下文的路径后，先要有关键 identifier。

常见 slots：

- `order_id`
- `refund_case_id`
- `ticket_id`
- `merchant_id`
- `customer_id`
- `amount`
- `issue_type`

### 13.1 `slot_extraction`

用户输入：

```text
帮我看下 ORD-1001 退款为什么没到账
```

输出：

```json
{
  "order_id": "ORD-1001",
  "refund_case_id": null,
  "ticket_id": null,
  "merchant_id": null,
  "customer_id": null,
  "issue_type": "退款未到账"
}
```

### 13.2 `route_after_slots`

它判断：

```text
required slots 是否齐全？
```

如果不齐：

```text
slot_extraction
-> clarification_gate
-> final_response
```

例如用户说：

```text
帮我查一下退款怎么回事
```

没有订单号，也没有退款单号。

回复：

```text
请提供订单号或退款单号，我才能查询具体退款状态。
```

如果 slots 齐了：

```text
session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate

或：

session_memory_load
-> slot_extraction
-> route_after_slots
-> long_term_memory_retrieve
-> investigate
```

---

## 14. memory 部分

这里有两个节点：

```text
session_memory_load
long_term_memory_retrieve
```

### 14.1 `session_memory_load`

这是比较必要的。

作用：

- 读取当前 thread 里的 active slots；
- 读取上一轮 case summary；
- 补齐用户省略的信息。

例子：

第一轮：

```text
用户：帮我看 ORD-1001 退款为什么没到账
```

系统保存：

```json
{
  "active_slots": {
    "order_id": "ORD-1001"
  },
  "last_intent": "refund_troubleshooting"
}
```

第二轮用户说：

```text
那能补偿多少？
```

这里没有订单号，但 session memory 里有 `ORD-1001`，所以可以补齐。

### 14.2 `long_term_memory_retrieve`

这个不是每次都必须。

它适合：

- 商家长期偏好；
- 历史稳定运营约束；
- 用户长期偏好；
- 某商家经常出现的售后模式。

例子：

```text
这个商家之前多次因为延迟发货投诉升级。
```

但它不能替代 policy evidence。

如果只是简单订单状态查询，可以跳过 long-term memory。

是否需要 long-term memory 由 `route_after_slots` 根据 intent 和已解析 slots 决定；canonical router 中没有额外的 session-memory router。

---

## 15. investigate 部分

现行目标图对外只有一个 registered `investigate` node。它合并 business context、policy evidence、case memory 三类概念子能力；这些能力是 node-internal 的只读 service calls，不是额外 LangGraph nodes，也不各自拥有 canonical router。

### 15.1 输入与只读调查能力

`investigate` 接收已解析 slots、query、intent 和 tenant / trusted tool context。LLM 只能在只读 allowlist 内决定下一次调用：

- BusinessToolService read：`get_order`、`get_refund_case`、`get_ticket`、`get_logistics`、`get_merchant_risk`；
- KnowledgeService RAG：搜索当前 policy / SOP evidence；
- MemoryService case search：搜索历史类似案例。

三类来源按 intent 和已累积结果条件性调用。例如，纯 `policy_qa` 可以只查政策证据；订单状态查询可以只查业务事实；退款诊断则可能综合三类来源。case memory 只能作为 precedent，不能替代 current policy evidence。

### 15.2 bounded tool loop

`investigate` 内部允许 bounded tool loop：

1. LLM 根据当前累积 state，在 read-only allowlist 内选择下一次调查调用或决定停止。
2. 每次 BusinessToolService read、KnowledgeService RAG 或 MemoryService case search 都必须写独立 trace。
3. loop 受硬性 `max_iterations` 约束；达到上限时停止，并写 `termination_reason=max_iterations_reached`。
4. loop 不允许 write/action，不产生对外路由决策，也不能绕过 `risk_gate`、`approval_gate` 或 action 路径。
5. loop 退出后，`investigate` 只把累积 state 统一交给 `route_after_investigate`。

`retrieval_status` 只表达政策证据强度，例如 `strong_evidence`、`partial_evidence`、`no_evidence`、`error`；`termination_reason` 单独表达 bounded loop 为什么终止，两者不能混写。

### 15.3 `route_after_investigate`

`route_after_investigate` 是 deterministic、side-effect-free 的 canonical router。它联合判断业务事实、missing required facts、tool errors、`retrieval_status`、`termination_reason`、`best_score` 和 intent，优先级如下：

1. permission denied 只阻断依赖被拒资源的回答；如无法安全回答则进入 `final_response`，但不得丢弃 loop 中已合法取得的其他事实。
2. 调查后仍缺 required facts 时，进入 `clarification_gate`。
3. fact-only intent 且所需事实已取得时，进入 `final_response`。
4. retrieval error、`no_evidence` 或证据不足时，进入 `final_response` 的 insufficient-evidence 路径。
5. 其余已有足够调查上下文的请求，进入 `recommendation_generation`。

达到 `max_iterations` 只写独立 `termination_reason`，不会自动覆盖真实的 `retrieval_status`；router 仍基于累积事实和证据做上述确定性判断。

因此它的目标严格只能是：

```text
final_response
clarification_gate
recommendation_generation
```

例如订单号不存在时，可进入澄清或安全回复；纯订单状态查询拿到事实后直接回复；需要规则与建议的请求则进入 recommendation。无论哪一种，graph 上都不会把内部调查能力展开成额外 node 或 router。

---

## 16. recommendation 部分

### 16.1 `recommendation_generation`

这个节点综合：

- 用户问题；
- business context；
- policy evidence；
- session memory；
- long-term memory；
- case memory。

输出：

```json
{
  "recommended_action": "建议先核实物流签收凭证，再判断是否进入退款复核",
  "reasoning_summary": "订单已签收，但用户否认签收，政策要求核验证据",
  "evidence_refs": [
    {
      "doc_key": "refund_policy_v1",
      "chunk_id": "refund_policy_v1_003"
    }
  ],
  "confidence": 0.82,
  "risk_level": "medium",
  "missing_info": ["签收凭证"],
  "proposed_action": null
}
```

或者输出一个 proposed action：

```json
{
  "recommended_action": "建议发放 50 元补偿券",
  "proposed_action": {
    "action_type": "issue_coupon",
    "amount": "50",
    "currency": "CNY",
    "target_id": "refund_case_id",
    "reason": "符合低额体验补偿规则"
  }
}
```

### 16.2 `route_after_recommendation`

它判断：

```text
有没有 proposed action？
```

#### 没有 proposed action

```text
recommendation_generation
-> final_response
```

只是回答或建议。

#### 有 proposed action

```text
recommendation_generation
-> risk_gate
```

任何动作都要过 risk gate。

---

## 17. risk 部分

### 17.1 `risk_gate`

这是企业级售后 Agent 的关键节点。

它不应该只靠 LLM prompt。

它要调用：

- RiskPolicy；
- ApprovalPolicy。

判断：

- 风险等级：low / medium / high；
- 是否需要审批；
- 命中哪条规则；
- 是否允许自动创建草稿；
- 是否必须阻断；
- 需要几级审批；
- SLA 多久。

输出可能是：

```json
{
  "risk_level": "high",
  "risk_reason": "补偿金额超过 500 元",
  "approval_required": true,
  "rule_ref": "HR-01",
  "approval_plan": {
    "levels": [
      {"role": "manager", "sla_hours": 4},
      {"role": "finance", "sla_hours": 8}
    ]
  }
}
```

### 17.2 `route_after_risk`

它有三类路线。

#### 情况 A：无动作或动作被阻断

```text
risk_gate
-> final_response
```

例如：

```text
证据不足，不能建议发券，建议转人工复核。
```

#### 情况 B：低风险自动允许

```text
risk_gate
-> action_draft
```

例如：

```text
发放 10 元体验券，符合低风险规则，无需审批。
```

注意：目标设计里也建议先创建 draft，再执行 demo adapter，不是让 LLM 直接发券。

#### 情况 C：需要审批

```text
risk_gate
-> approval_gate
```

例如：

- 600 元补偿券；
- 全额退款；
- 关闭高风险工单；
- 账号解封。

---

## 18. approval 部分

### 18.1 `approval_gate`

这个节点负责 LangGraph interrupt。

它会创建类似：

```json
{
  "action_request": {
    "action": "review_proposed_action",
    "args": {
      "action_type": "issue_coupon",
      "amount": "600",
      "currency": "CNY"
    }
  },
  "config": {
    "allow_accept": true,
    "allow_edit": true,
    "allow_respond": true,
    "allow_ignore": true
  },
  "description": "风险原因、政策依据、业务事实..."
}
```

人审之后返回：

```json
{
  "type": "accept",
  "args": {}
}
```

或者：

```json
{
  "type": "edit",
  "args": {
    "action_type": "issue_coupon",
    "amount": "100"
  }
}
```

或者：

```json
{
  "type": "response",
  "args": "需要补充签收凭证"
}
```

或者：

```json
{
  "type": "reject",
  "reason": "证据不足"
}
```

### 18.2 `route_after_approval`

它处理人工结果。

#### accept / approve

```text
approval_gate
-> action_draft
```

审批通过，进入动作草稿。

#### edit

```text
approval_gate
-> risk_gate
```

这点很重要。

为什么 edit 后不能直接进入 action_draft？

因为审批人可能把金额从 50 改成 600，风险级别变了。

所以必须重新走：

```text
edit
-> risk_gate
-> approval/action route
```

#### respond / request info

```text
approval_gate
-> trace_close（lifecycle finalizer）
```

审批人说：

```text
请补充签收凭证
```

这不是普通澄清。ApprovalService 写入 `needs_info`、`clarification_request_id` 和可展示的 clarification message 后，原 run 由 lifecycle finalizer 保持 `interrupted`，**不进入** `clarification_gate -> final_response -> memory_write` 这条 completed 路径。后续用户补充信息时，必须创建或恢复一个可校验的新 revision，并重新跑 slot / business / evidence / risk 检查，不能直接执行旧审批。

#### reject / ignore / expired

```text
approval_gate
-> final_response
```

动作不执行，回复用户审批结果或超时结果。

---

## 19. action 部分

### 19.1 `action_draft`

这个节点创建 durable draft。

它不一定是真实执行。

当前 MOCA 已经有类似能力：

```text
ActionDraft
create_coupon_grant_draft
```

目标是把它抽象为：

```text
ActionExecutor.create_draft()
```

输出：

```json
{
  "draft_id": "...",
  "action_type": "issue_coupon",
  "status": "draft_created",
  "idempotency_key": "..."
}
```

### 19.2 `route_after_action_draft`

`route_after_action_draft` 根据 execution mode 和 draft 状态决定下一步。允许执行且需要实际执行时进入 `action_execution`；demo 或只创建草稿的路径进入 `final_response`。它只做确定性路由，不执行动作。

### 19.3 `action_execution`

这个节点执行动作。

但当前 MOCA 仍应该是 demo adapter：

```text
execution_mode = demo
```

也就是：

- 创建草稿；
- 写 execution result；
- 不真实发券；
- 不真实退款；
- 不调公司外部系统。

未来如果接真实系统，才变成：

```text
ActionExecutor.execute()
  -> CouponAdapter.issue_coupon()
  -> RefundAdapter.partial_refund()
```

---

## 20. final / memory / trace 收尾

所有路径最终都会汇合到：

```text
final_response
-> memory_write
-> trace_close
```

### 20.1 `final_response`

负责生成最终对用户可见的回复。

不同路径下回复不同。

政策 QA：

```text
根据 policy_refund_timeout / chunk_001，退款超时时需要...
```

订单查询：

```text
已查询到订单 ORD-1001，当前状态为 delivered。
```

审批通过：

```text
审批已通过，补偿草稿已创建。
```

审批拒绝：

```text
审批被拒绝，原因：证据不足。
```

证据不足：

```text
当前知识库没有找到足够证据支持该判断，建议转人工。
```

### 20.2 `memory_write`

它不是把所有聊天都写长期记忆。

它应该做：

- 更新 session memory；
- 生成 long-term memory candidates；
- 生成 case memory candidates；
- 根据 write policy 决定是否写入。

例如：

```json
{
  "session_summary": "用户正在处理 ORD-1001 退款未到账问题",
  "active_slots": {
    "order_id": "ORD-1001"
  }
}
```

长期记忆写入要谨慎。

### 20.3 `trace_close`

最后补全：

- AgentRun；
- AgentStep；
- tool calls；
- evidence refs；
- approval timeline；
- action draft；
- latency；
- metrics；
- replay timeline。

它是 observability/replay 的收尾节点。

---

## 21. 几个完整路线例子

### 21.1 简单政策问答

用户：

```text
超过 7 天还能退款吗？
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
-> memory_write
-> trace_close
```

不会走：

```text
slot_extraction
risk_gate
approval_gate
action_draft
action_execution
```

因为没有具体订单，也没有动作请求。

### 21.2 查订单状态

用户：

```text
ORD-1001 现在是什么状态？
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> final_response
-> memory_write
-> trace_close
```

不会走 RAG，因为只是业务事实查询。

### 21.3 退款诊断

用户：

```text
ORD-1001 退款为什么没到账？
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> final_response
-> memory_write
-> trace_close
```

如果 recommendation 没有 proposed action，就不进 risk gate。

如果 recommendation 里建议：

```text
转人工复核
```

可能也不需要 action。

### 21.4 低风险补偿

用户：

```text
给这个客户发 20 元体验券。
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> risk_gate
-> action_draft
-> action_execution
-> final_response
-> memory_write
-> trace_close
```

这里走 risk gate，因为有动作。

但如果规则判断 20 元低风险，可以不进 approval gate。

### 21.5 高风险补偿

用户：

```text
给这个客户发 600 元补偿券。
```

路线：

```text
receive_request
-> normalize_input
-> intent_classification
-> session_memory_load
-> slot_extraction
-> route_after_slots
-> investigate
-> route_after_investigate
-> recommendation_generation
-> risk_gate
-> approval_gate
```

然后 graph interrupt，等人工。

如果 manager accept：

```text
approval_gate
-> action_draft
-> action_execution
-> final_response
-> memory_write
-> trace_close
```

如果 manager edit，把 600 改成 100：

```text
approval_gate
-> risk_gate
-> action_draft 或 approval_gate
```

如果 manager reject：

```text
approval_gate
-> final_response
-> memory_write
-> trace_close
```

---

## 22. 为什么要设计成这样？

因为目标不是“线性 LangGraph demo”，而是企业级售后 Agent 原型。

### 22.1 避免所有请求都跑完整链路

简单问题不需要 RAG、risk、approval。

这样降低：

- latency；
- cost；
- 不必要的错误路径；
- 过度审批。

### 22.2 高风险动作必须被拦住

只要有 proposed action：

```text
recommendation_generation
-> risk_gate
```

只要高风险：

```text
risk_gate
-> approval_gate
```

这保证安全。

### 22.3 分层边界更清楚

LangGraph 节点只负责 orchestration：

```text
什么时候查订单？
什么时候查政策？
什么时候进审批？
什么时候执行动作？
```

真正实现放 service：

```text
BusinessToolService
KnowledgeService
MemoryService
ApprovalService
ActionExecutor
ObservabilityService
```

这符合目标分层架构。

### 22.4 更容易评估

每个节点都有明确输入输出。

可以测：

- intent 分类准不准；
- slots 是否提取对；
- RAG 有没有证据；
- recommendation 是否引用证据；
- risk gate 是否正确拦截；
- approval 是否正确 resume；
- action 是否幂等；
- trace 是否完整。

---

## 23. 最容易混淆的点

### 23.1 `route_after_xxx` 不是节点

它只是决定下一步。

比如：

```text
route_after_risk
```

不是一个 `risk_route_node`。

它只是：

```python
def route_after_risk(state):
    if approval_required:
        return "approval_gate"
    if auto_allowed:
        return "action_draft"
    return "final_response"
```

### 23.2 Service 不是 LangGraph 节点

比如 `KnowledgeService` 不应该是一个 graph node。

Graph node 是：

```text
investigate
```

它内部调用：

```python
knowledge_service.search(...)
```

### 23.3 `risk_gate` 不是所有请求都必须走

必须走 risk gate 的情况：

- 有 proposed action；
- 有退款/补偿/关闭工单/解封/升级等动作风险；
- 需要审批判断。

可以不走 risk gate 的情况：

- small talk；
- unsupported；
- 纯政策 QA 且无动作；
- 纯订单状态查询。

### 23.4 `case_memory` 不能替代 policy evidence

即使历史案例说“以前发了券”，也不能直接作为现在发券依据。

必须有：

```text
business facts + current policy evidence + risk policy
```

---

## 24. 一句话总结

这张 node-only 路由图想表达的是：

> MOCA 的目标 Graph 不是一条固定流水线，而是一个以 intent 为入口、以 evidence 和 risk 为安全门、以 approval 和 action executor 为动作边界的分层状态机。

更短一点：

```text
Intent 决定走哪条业务路径；
Evidence 决定能不能回答；
Risk 决定能不能动作；
Approval 决定高风险动作能不能继续；
ActionExecutor 决定动作如何安全落地；
Trace/Memory 负责收尾和可评估。
```
