# MOCA Product One Pager

> 作品集定位：AI 应用产品经理 / Agent 产品经理  
> 项目性质：open-source portfolio project / simulated merchant operations scenario  
> 项目边界：使用合成数据和模拟商家运营场景，不伪装成真实商用上线产品。

## 一句话定位

MOCA 是一个面向电商 / 本地生活商家售后运营的 AI Agent 工作流产品，帮助客服和运营人员在退款纠纷、规则咨询、补偿建议和高风险审批场景中，完成业务事实查询、政策证据引用、风险判断、动作草稿和处理 trace 复盘。

它不是普通聊天机器人，而是一个把“业务事实 + 政策证据 + 风险审批 + 审计追踪”串成可控流程的 Agent 产品原型。

## 用户与问题

| 目标用户 | 当前痛点 | MOCA 的产品价值 |
| --- | --- | --- |
| 一线客服 | 需要在订单、退款、工单、政策之间来回查找，回复慢且口径不一致 | 自动组织查询、证据和回复草稿，缩短 case 分析时间 |
| 客服主管 / 审核人员 | 高风险补偿和退款决策缺少统一依据，复盘成本高 | 提供风险原因、审批上下文和可回放 trace |
| 平台运营 | 难以观察规则执行是否一致、AI 判断是否可靠 | 用 evidence、risk、approval 和 trace 支持流程复盘 |
| 商家支持团队 | 商家侧退款、补偿、申诉问题容易跨系统沟通 | 用统一工作流降低沟通和处理成本 |

## 产品方案

MOCA 把一次售后咨询拆成可控的 Agent 工作流：

```text
用户请求
  -> 安全预判断
  -> 意图识别与槽位判断
  -> 业务事实查询 / 政策检索
  -> evidence 校验
  -> 建议或回复生成
  -> 风险判断
  -> 审批 / 动作草稿
  -> 最终回复 + trace 记录
```

核心设计原则：

- **业务事实不靠模型猜**：订单、退款、工单、物流、商家风险来自结构化业务工具。
- **规则回答必须有证据**：政策类回答尽量绑定 evidence 引用，没有证据时澄清、拒绝或降级。
- **高风险动作不自动执行**：退款、补偿、发券等动作只生成草稿，必须经过审批边界。
- **普通聊天不能伪造审批**：用户在对话里说“同意 / 执行吧”不能替代可信审批入口。
- **trace 是产品能力**：保留关键节点、工具调用、证据、风险和审批记录，用于复盘和问责。

## 核心演示场景

| 场景 | 用户问题示例 | 产品展示点 |
| --- | --- | --- |
| 查询退款进度 | “订单 ORD-2024-001 的退款进度如何？” | 意图识别、订单/退款事实查询、可解释回复 |
| 规则咨询 + evidence | “平台的退款超时处理规则是什么？” | 政策检索、证据引用、避免无依据回答 |
| 补偿建议 | “客户投诉延迟发货，能不能给补偿？” | 结合业务事实、政策和风险给建议 |
| 高风险动作审批 | “直接给这个订单退款并发券。” | 识别高风险动作，进入 approval gate，不直接执行 |
| Approval resume + trace | 主管审批后继续流程 | 人审恢复、动作草稿、完整 trace 回放 |

## 差异化亮点

1. **从聊天到工作流**：MOCA 不追求自由对话，而是把售后处理拆成有意图、有证据、有审批、有追踪的流程。
2. **AI Agent 安全边界清晰**：LLM 可以辅助理解、生成和建议，但不能拥有事实权威、政策权威、审批权限或真实执行权。
3. **证据与业务事实分离**：政策 evidence、当前业务事实、记忆上下文和审批/action authority 各自有边界，避免互相替代。
4. **人审是核心路径，不是补丁**：高风险动作通过 LangGraph interrupt/resume 进入审批流程，主管决策会写入审计轨迹。
5. **用评测定义可靠性**：不是只看回答是否像人，而是看 intent、tool selection、citation、safety interception 和 approval bypass prevention。

## 当前项目状态

- 已完成 v2.1 Core Subsystem Hardening：ToolPlatform、intent、memory、RAG/claim、approval、canonical Agent Graph 等核心子系统边界已收敛。
- 当前 active runtime graph 是 15-node canonical Agent workflow，围绕安全预判断、上下文意图、只读调查、证据校验、风险审批和最终回复组织。
- 当前 v2.2 方向聚焦 Product Experience Fixes：直接回复、澄清体验、业务指标查询、前端 timeline 和 UX regression suite。
- 所有写动作仍是模拟 action draft，不接真实支付、退款、发券或外部履约系统。

## 评测与成功指标

| 指标 | 目标意义 |
| --- | --- |
| Intent / route accuracy | 能否把用户请求分到正确业务路径 |
| Tool selection accuracy | 是否调用了必要业务工具再回答 |
| Citation / evidence rate | 规则类回答是否有政策依据 |
| RAG fallback accuracy | 无证据时是否避免编造 |
| Safety critical pass rate | 审批、拒绝、权限不足等安全路径必须稳定 |
| Trace completeness | 是否能复盘关键节点、证据、风险和审批状态 |

## 我想展示的 PM 能力

- **业务抽象**：把退款、规则、补偿、审批和复盘抽象成售后运营 Agent 产品。
- **需求取舍**：MVP 做可验证的 Agent 工作流，不急于接入真实外部执行。
- **Agent 行为设计**：定义何时查事实、何时查证据、何时生成建议、何时必须澄清或审批。
- **安全与合规意识**：明确 AI 不能绕过权限、审批、证据和审计。
- **评测设计**：用 golden set 和安全关键路径判断 AI 产品是否可靠。
- **技术理解转产品表达**：把 LangGraph、RAG、ToolPlatform、approval resume、trace 等技术能力翻译成用户价值。

## 作品集入口

- 详细案例页：[MOCA_PM_CASE_STUDY.md](MOCA_PM_CASE_STUDY.md)
- 项目 README：[`../../README.md`](../../README.md)
- Demo walkthrough：[`../../docs/demo-walkthrough.md`](../../docs/demo-walkthrough.md)
- Evaluation methodology：[`../../docs/evaluation.md`](../../docs/evaluation.md)
- Security model：[`../../docs/security-and-permission.md`](../../docs/security-and-permission.md)

## 一句话总结

MOCA 展示的是：我可以围绕真实业务场景，设计一个有证据、有权限、有审批、有评测、有复盘能力的 AI Agent 产品，而不是只做一个能聊天的模型 demo。
