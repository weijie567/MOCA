# Day 1 理论笔记

- 日期：2026-06-18
- 主题：建仓 + MOCA 全景 + Phase 14/15 内化
- 资料：Anthropic《Building Effective Agents》(workflow vs agent)
- 目标：把 workflow / agent 的区别压缩成能解释 MOCA 架构选择的材料。

## 今日理论笔记

待填写。建议只读到能回答这三个问题：

1. 什么场景适合 workflow，而不是开放式 agent？
2. 什么场景需要 agent 自主选择工具、检索证据或继续追问？
3. MOCA 为什么是“结构化工作流 + 局部 agent 能力”，而不是泛聊天机器人？

## 关键概念

| 概念 | 一句话解释 | 和 MOCA 的关系 |
|---|---|---|
| workflow | 由系统明确编排步骤和边界 | MOCA 的审批、风险、最终响应更像 workflow |
| agent | 模型能根据上下文选择下一步动作 | MOCA 的调查、证据收集、工具选择局部需要 agent |
| HITL | 高风险步骤交给人确认 | MOCA 高风险动作必须进入 approval gate |
| evidence | 回答或建议必须有可追溯依据 | MOCA 的 RAG、trace、eval 都围绕证据闭环 |

## 对 MOCA 的设计启发

待填写。明天至少写 3 条：

- 哪些节点必须 deterministic，不能交给模型自由发挥？
- 哪些节点可以让模型做判断或工具选择？
- 如果面试官问“为什么不用一个大 agent 全包”，你怎么回答？

## 不懂的问题

- workflow / agent 的边界有没有一条可操作判断标准？
- LangGraph 的 durable execution、checkpoint 和 MOCA 的审批恢复如何对应？
- 如果未来工具更多，MOCA 应该先增强 planner，还是先增强 tool catalog / permission？

