# Day 1 · 大厂技术追问模拟器

- 日期：2026-06-18
- 今日主题：建仓 + MOCA 全景 + Phase 14/15 内化
- 规则来源：`study_plan/portfolio/daily/interview_question_rules.md`

## 大厂技术追问候选题

### A. 今日主题直连题

1. MOCA 为什么更像 structured workflow + 局部 agent，而不是一个完全开放的 chatbot？
2. workflow 和 agent 的边界怎么判断？MOCA 哪些节点必须 deterministic？
3. 如果用户问题信息不足，MOCA 是继续追问、查工具，还是直接回答？
4. 为什么 Day 1 要先画模块全景图，而不是直接读代码或改代码？
5. 如果面试官只给你 60 秒，你怎么讲清 MOCA 的主链路？

### B. MOCA 项目深挖题

1. MOCA 的核心业务对象是什么？退款、争议、补偿分别对应什么风险？
2. 高风险动作为什么不能让模型直接执行？MOCA 现在怎么处理？
3. RAG 证据在 MOCA 里是建议的装饰，还是系统契约的一部分？
4. trace / replay / eval 在 MOCA 里分别解决什么问题？
5. Phase 14/15 完成后，为什么还要插入 Phase 15.1 Memory Foundation V2？

### C. 底层工程追问题

1. Redis 在 MOCA 里适合做什么？为什么不能作为长期记忆或审计真相源？
2. PostgreSQL + pgvector 在 RAG 场景里承担什么角色？和普通全文检索有什么区别？
3. tool calling 失败时，系统应该怎么返回？能不能直接把异常抛给用户？
4. 幂等 key 为什么对 action draft / external action 很重要？
5. context window 超限时，为什么不能简单把历史全塞进 prompt？

### D. 架构升级题

1. 如果 MOCA 从 demo 变成生产系统，外部真实退款执行应该怎么接入？
2. 如果工具数量从 5 个涨到 100 个，tool catalog / planner-visible view 应该怎么升级？
3. 如果多租户、多角色、跨团队审批都上线，现有 approval / permission 边界够不够？

### E. 模型与框架题

1. LangGraph 相比裸写 while loop 的价值在哪里？MOCA 为什么适合 LangGraph？
2. function calling、MCP、A2A、skills 的边界分别是什么？MOCA 当前真正需要哪一类？
3. ReAct 思路在 MOCA 的 investigate 节点里能怎么体现？哪里不能放任 ReAct？

### F. 高级识别题

1. Agentic CPT / SFT / RL 和 MOCA 这种工程型 Agent 项目是什么关系？
2. Tree of Thought 在线上业务系统里为什么通常不能直接照搬？

## 今日 Top 5 追问

### Q1: MOCA 为什么不是 generic chatbot，而是 structured workflow + 局部 agent？

- 类型：MOCA深挖 / Agent工程
- 难度：必会
- 面试官想考：你是否理解 agent autonomy 和 production guardrail 的边界。
- 60秒回答：MOCA 面向退款、争议、补偿，这些场景有真实业务风险，所以不能让模型自由决定所有步骤。系统用 LangGraph 把意图识别、信息补全、调查、建议、风险评估、审批、最终响应拆成有边界的节点；局部需要模型判断和工具选择，但审批、权限、风险和动作边界必须 deterministic。
- MOCA绑定：`README.md` 的 Agent Workflow 展示了 classify / investigate / generate_recommendation / assess_risk_and_approval / approval_gate / execute_action 主链路；`TOOL_ARCHITECTURE.md` 规定 agent-facing tool 必须经过 UnifiedToolManager 和 caller allowlist。
- 证据路径：`README.md`、`TOOL_ARCHITECTURE.md`、`src/agent/graph.py`
- 当前边界：明天需要读代码确认 graph 节点名称和 README 是否完全一致；不要把目标架构文档里的未来 manager 全部说成当前已落地。
- 被继续追问时的回答：如果追问“为什么不用一个大 agent”，答：大 agent 可以提升灵活性，但在退款/补偿场景会放大越权、幻觉和不可审计风险；MOCA 的设计是把模型能力放在调查和建议层，把权限、审批和动作放在系统层。
- 状态：PARTIAL

### Q2: 高风险动作为什么只能 draft-only，不能直接执行？

- 类型：MOCA深挖 / 风险控制
- 难度：必会
- 面试官想考：你是否理解 HITL、approval、snapshot/hash、外部副作用边界。
- 60秒回答：退款和补偿是有真实财务影响的动作。MOCA 当前 Phase 14 的边界是 demo action executor，只生成 durable draft 和 draft_outcome，不执行真实外部动作；高风险路径需要 approval，审批绑定 action safety snapshot 和 hash，避免“审批的是 A，执行的是 B”。
- MOCA绑定：`.planning/ROADMAP.md` 明确 Phase 14 已完成 draft-only demo boundary，Phase 17 external action execution 被 defer。
- 证据路径：`.planning/ROADMAP.md`、`README.md`、`src/approvals/`、`rules/risk_rules.yaml`
- 当前边界：当前不声称真实退款执行已上线；Phase 17 才处理 external execution、outbox、reconciliation、compensation。
- 被继续追问时的回答：如果追问“那 demo 有什么价值”，答：demo 的价值是证明建议、证据、风险和审批链路正确，真实执行是另一个风险等级，需要 outbox、幂等、补偿和对账。
- 状态：PARTIAL

### Q3: RAG 证据在 MOCA 里怎么防止“看起来有引用但其实不支持结论”？

- 类型：RAG / evidence
- 难度：会被追问
- 面试官想考：你是否能从“检索到了”讲到“证据支持结论”。
- 60秒回答：MOCA 不应该把 RAG 当成普通上下文拼接，而是把 evidence refs / citation validation 作为契约。检索结果需要返回 policy chunk 或 document key，建议生成时必须带证据引用；eval 里有 RAG Hit@5、citation rate、fallback accuracy，防止无证据场景胡编。
- MOCA绑定：`README.md` Key Capabilities 提到 RAG evidence retrieval with citation validation；`docs/evaluation.md` 说明 RAG golden set、Hit@5、fallback 和 citation metrics。
- 证据路径：`README.md`、`docs/evaluation.md`、`src/rag/`、`src/knowledge/`、`evaluation/golden/rag_cases.jsonl`
- 当前边界：明天需要实际跑或阅读 `make eval-rag` 相关脚本，不能只凭 README 讲实现细节。
- 被继续追问时的回答：如果追问“检索错了怎么办”，答：要区分 no-evidence、partial evidence 和 unsupported claim；系统应该安全降级或请求人工确认，而不是强行给建议。
- 状态：PARTIAL

### Q4: trace、replay、eval 三者有什么区别？为什么 MOCA 都需要？

- 类型：trace / eval / risk
- 难度：必会
- 面试官想考：你是否理解可观测、可复现、质量门槛不是一回事。
- 60秒回答：trace 是一次运行过程的记录，帮助定位节点、工具、证据、审批发生了什么；replay 是更严格的事件契约，让运行历史可以按事件序列重建和审计；eval 是离线质量门槛，用 golden cases 检查 RAG、routing、tool selection、approval safety 是否达标。MOCA 需要三者，因为 Agent 不是只看最终答案，生产问题常出在中间链路。
- MOCA绑定：`README.md` 提到 full execution trace / audit trail 和 evaluation scripts；`.planning/ROADMAP.md` 显示 Phase 15 Replay Event Contract 已完成。
- 证据路径：`README.md`、`docs/evaluation.md`、`.planning/ROADMAP.md`、`src/api/routers/traces.py`、`src/replay/`
- 当前边界：需要明天确认 `/trace` 和 `/replay` 当前 API 的具体返回形态；不要把 replay 说成完整调试 UI。
- 被继续追问时的回答：如果追问“为什么 eval 不够”，答：eval 证明一组场景的质量，trace/replay 解释单次运行为什么这样发生；一个是质量门槛，一个是事故定位和审计。
- 状态：PARTIAL

### Q5: Phase 15.1 Memory Foundation V2 为什么要插在 Phase 15 和 Phase 16 中间？

- 类型：架构升级 / memory
- 难度：会被追问
- 面试官想考：你是否能讲清 session memory、conversation log、long-term memory、case memory 的边界。
- 60秒回答：Phase 12 已有 session memory，Phase 15 有 replay event contract，但如果直接做 Phase 16 long-term/case memory，容易把原始对话、工具调用、工作状态、审计事件、长期画像混在一起。Phase 15.1 的作用是先补 conversation log、tool call/result storage、WorkingStateV1、thread summary、ContextAssembler 和 token budget，让 prompt-safe 当前上下文和审计/replay分层清楚，再进入长期记忆。
- MOCA绑定：`.planning/ROADMAP.md` 中 Phase 15.1 明确是 Memory Foundation V2，Phase 16 才是 long-term / case memory。
- 证据路径：`.planning/ROADMAP.md`、`docs/general_assistant_memory_design.md`、`docs/business_agent_memory_design.md`、`docs/current-implementation-map.md`
- 当前边界：Phase 15.1 尚未计划完成；明天只能准备 plan，不把它说成已实现。
- 被继续追问时的回答：如果追问“为什么不直接向量化所有历史”，答：因为对话历史、业务事实、政策证据、审批动作和长期偏好权威性不同，混成一个向量库会带来权限、过期、可解释和删除问题。
- 状态：NEEDS_MOCA_BINDING

## MOCA绑定

今日 Top 5 绑定到以下 MOCA 事实：

- MOCA 是商家运营 refund / dispute / compensation 场景，不是泛聊天。
- 主链路包含 LangGraph 编排、RAG 证据、risk assessment、approval gate、draft-only action、trace/eval/replay。
- Phase 14/15 已完成，Phase 15.1 是当前准备入口。
- Phase 16/17 仍是 defer，不能在面试里说成已经实现。

## 证据路径

- `README.md`
- `TOOL_ARCHITECTURE.md`
- `.planning/ROADMAP.md`
- `docs/evaluation.md`
- `docs/general_assistant_memory_design.md`
- `docs/business_agent_memory_design.md`
- `docs/current-implementation-map.md`
- `src/agent/graph.py`
- `src/approvals/`
- `src/rag/`
- `src/replay/`

## 当前边界

- 这些答案是 Day 1 训练材料，不代表已经口头练熟。
- `READY` 状态必须等明天你能脱稿讲，并能扛至少一轮追问后再改。
- Q5 需要补 Phase 15.1 的 plan 证据，目前只能标 `NEEDS_MOCA_BINDING`。

