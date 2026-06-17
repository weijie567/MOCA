# 每日面试追问规则

> 用途：每天生成技术面/产品面追问时，防止回答变成通用八股。所有问题都必须回到 MOCA 的真实设计、真实产物和真实边界。
> 同步来源与完整解释见：`study_plan/portfolio/interview/大厂技术追问模拟器同步.md`。

## 1. 核心规则

每一道面试题都必须按这个闭环回答：

```text
问题本身
→ 面试官想考什么
→ 通用原理的 60 秒回答
→ MOCA 里具体怎么做 / 没做但为什么没做
→ 证据文件或产物路径
→ 当前诚实边界
→ 如果继续追问，我怎么答
```

禁止只回答通用概念。凡是答不出“MOCA 里怎么做”的题，都不能标记为已掌握，只能标记为 `NEEDS_MOCA_BINDING`。

## 2. 每题必填字段

```markdown
### Q{n}: {问题}

- 类型：MOCA深挖 / Agent工程 / RAG / 工程底层 / 架构升级 / 模型训练 / 产品判断
- 难度：必会 / 会被追问 / 只需识别
- 面试官想考：
- 60秒回答：
- MOCA绑定：
- 证据路径：
- 当前边界：
- 被继续追问时的回答：
- 状态：READY / PARTIAL / NEEDS_MOCA_BINDING / NOT_STARTED
```

## 3. MOCA 绑定要求

回答至少命中下面一种绑定方式：

- **已实现绑定**：指向 MOCA 已有模块、文档、测试、trace、eval 或 demo。
- **MVP 边界绑定**：说明 MOCA 当前为什么没有实现，以及它被 defer 到哪个 phase 或增强计划。
- **升级路径绑定**：说明如果业务复杂、工具变多、知识库变大、外部执行上线，架构如何升级。
- **风险控制绑定**：说明 trace / eval / risk / HITL / approval / rollback 中至少一项如何处理。

如果四种都绑定不上，这道题当天不主攻，只放入“待补题库”。

## 4. 状态定义

- `READY`：能用 MOCA 例子回答，能扛至少 1 轮 why/if 追问。
- `PARTIAL`：懂通用原理，但 MOCA 绑定还不够具体。
- `NEEDS_MOCA_BINDING`：答案像八股，缺少项目证据。
- `NOT_STARTED`：只是收集到题目，还没准备答案。

## 5. 每日最低要求

每天只练熟 Top 5，不贪多：

1. 至少 3 题必须是 MOCA 项目深挖。
2. 至少 1 题必须包含 failure / risk / fallback。
3. 至少 1 题必须包含 trace / eval / evidence。
4. Top 5 里所有题都必须达到 `READY` 或 `PARTIAL`。
5. `NEEDS_MOCA_BINDING` 题必须写明明天补什么产物。

## 6. 自动审计规则

晚间审计时，Codex 只能基于证据判断：

- 有无 `dayXX_interview_questions.md`。
- Top 5 是否存在。
- 每题是否包含 `MOCA绑定` 和 `证据路径`。
- 是否存在 `READY / PARTIAL / NEEDS_MOCA_BINDING / NOT_STARTED` 状态。
- 是否存在“当前边界”，防止把未实现能力说成已实现。

Codex 不能判断口头表达是否真的过关；所有“能否 3 分钟讲清”“能否扛追问”必须由人工确认。

## 7. 大厂技术追问模拟器结构

每天先生成候选题，再挑 Top 5。候选题不要只围绕当天主题，要覆盖“当天主题 + MOCA 项目深挖 + 相关底层工程 + 架构升级边界”。

候选题按下面 6 类生成：

- **A. 今日主题直连题**：5 题，直接围绕当天主题。
- **B. MOCA 项目深挖题**：5 题，必须追问“项目里具体怎么做、为什么这么做、线上出问题怎么办、怎么验证”。
- **C. 底层工程追问题**：5 题，从 Redis / MySQL / MQ / Elasticsearch / RAG / context window / tool calling / trace / eval / risk / idempotency / fallback 中选当天最相关的。
- **D. 架构升级题**：3 题，考察从 demo 到生产的升级路径。
- **E. 模型与框架题**：3 题，考察 LangGraph / function calling / MCP / A2A / skills / ReAct / workflow / agent / context engineering 等边界。
- **F. 高级识别题**：2 题，只要求能识别和 60 秒简答，不作为主攻。

每个候选题必须包含：面试问题、面试官想考什么、60 秒回答要点、如何绑定 MOCA、当前最可能卡住的点、今天应该补的产物或证据。

最后从候选题里选出“今日必须练熟的 Top 5 追问”，每题给出标准回答骨架、MOCA 项目例子、一句面试金句、被继续追问时的 fallback 回答。

## 8. few-shot 风格

参考题型：

- ReAct 框架用过吗？消息格式是如何设计的？
- `tool_response` 应该用什么 role 传回？为什么？
- Redis 在 AI Agent 系统里有什么运用场景？如何设计缓存策略？
- MySQL 索引在什么情况下会失效？`LIKE` 查询什么时候走不了索引？
- 消息队列在 AI Agent 系统中有什么作用？为什么不直接通过数据库通信？
- RAG 为什么要引入父子索引？BM25 和向量检索如何融合？
- Agent 的短期记忆和长期记忆如何设计？上下文超限怎么处理？
- 滑动窗口和动态摘要有什么区别？
- Agent 有没有遇到过死循环？如何处理？
- 工具库有上百个工具时，如何让模型快速准确选择？
- 工具调用失败怎么处理？
- 长上下文中如何不忘记关键信息，除了向量检索还有什么方法？
- Tree of Thought 在线上系统能用吗？如何平衡成本和效果？
- Agent 决策出错导致误删数据，系统设计上如何防？
- 用户需求模糊，例如“按老样子处理一下”，Agent 如何处理？
- Kafka 在 AI Agent 系统里能用于什么场景？如何保证消息顺序？
- Elasticsearch 在 RAG 中起什么作用？如何优化检索性能？
- tools / workflow / agent 的本质区别是什么？
- function calling / A2A / MCP / skills 的区别是什么？
- prompt engineering / context engineering / harness engineering 有什么区别？
- multi-agent 架构如何设计？Agent 之间如何通信？
- 做 Agent 项目时，如何决定用什么模型和什么框架？
- 业务复杂后架构如何升级？现在架构顶得住吗？
- 多模态大模型结构是什么？视觉编码器和语言模型如何衔接？
- Agentic CPT / SFT / RL 三个阶段训练流程分别是什么？为什么 SFT 时需要 Observation token？

## 9. 回答原则

- 会的题：先讲业务场景，再讲技术实现，最后讲设计取舍。
- 没做过的题：明确说“MOCA 当前 MVP 没实现”，再讲合理升级路径。
- 高级题：只做识别和 60 秒简答，不伪装算法岗深度。
- 工程底层题：讲生产作用和边界，不装资深后端。
- 所有答案最终都要能落到 MOCA 的文件、图、测试、trace、eval、risk 或 defer 决策。
