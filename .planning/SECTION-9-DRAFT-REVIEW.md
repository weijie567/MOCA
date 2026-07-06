> HISTORICAL REVIEW NOTE（2026-07-06）：本文是对早期 §9 agentic 草案的评审记录，不是当前目标 graph 或契约依据。当前应以 `docs/contract-spec.md` §9、`docs/target-agent-platform-architecture-plan.md` §6.1 和 Phase 49 summary 为主要参考；本文中的 blocker/warning 只在追溯当时草案演进时使用。

## BLOCKERS

1. **`investigate` 不应直接写 `evidence_refs`，否则会绕过 canonical citation-consumption 边界。** 草案把 `evidence_refs` 列为 `investigate` 的 state writes（draft:252），但现行 canonical registry 明确规定 `evidence_refs` 的 writer 是 `recommendation_generation / citation validator`，并将其定义为 recommendation/response/action 实际消费且通过 citation validation 的引用子集（contract-spec.md:585,605）。这是安全相关 contract 冲突：`risk_gate` 和 action snapshot 会消费已验证 evidence，草案必须区分 `investigate` 写入的 `retrieved_evidence` 与 citation validator 后才可写入的 `evidence_refs`（contract-spec.md:584-585；draft:253-254）。

2. **Phase 10 loop replay 无法按草案所述完整表达 parent/attempt，必须先裁决 minimal-envelope ownership。** 草案要求每个 tool operation 的 `parent_operation_id` 指向 `investigate` node operation，并用 `attempt` 表达重试（draft:353），但现行 spec 明确把 `parent_operation_id`、`attempt`、`error` 定义为 Phase 15 enrichment，Phase 10 minimal envelope 只有 conditional `operation_id`（contract-spec.md:1600,1628）。如果 Phase 10 实现 bounded loop 并首次 emit 事件（draft:265；contract-spec.md:1618），在 Phase 15 前无法按草案保证 node/tool parent hierarchy 和 retry semantics；这不是单纯措辞问题。

3. **retry 的 `parent_operation_id` 规则与草案的“必须指向 node operation”发生直接冲突。** 草案要求每个 tool operation 的 `parent_operation_id` 必须指向所属 node operation（draft:353），但现行 V3 字段规则要求 retry 创建新 operation 时，`parent_operation_id` 指向前一 attempt 或共同父 operation（contract-spec.md:1681-1682,1703）。两者会导致 Phase 15 validator 对 retry tool call 无法同时满足规则；必须定义首 attempt 与 retry attempt 的明确 parent 模型。

4. **`investigate` 的 Required inputs 自我依赖，无法覆盖 policy-only 入口。** 草案将 `business context` 列为 `investigate` required input，同时又要求该节点写入 `business_context`（draft:252）；但 `policy_qa` 从 intent router 直接进入 `investigate`，明确可跳过 business context（draft:127,194）。若表中 Required inputs 按字面执行，policy-only 路径在进入节点前就缺 required input；必须把它改为 optional/current accumulated context，或按调查计划声明条件输入。

## WARNINGS

1. **permission-denied 语义在同一草案内冲突。** §9.3 规定“任一只读 tool 返回 permission denied”即进入 final response，§9.5 precedence 也是 `permission denied -> final`（draft:209,292）；追加裁决倾向则主张只阻断依赖被拒资源的回答（draft:382）。这会直接影响 deterministic router 的输入聚合与 precedence，进入 discuss 前应把冲突标为待替换文本。

2. **`iteration` 当前只约束 “tool lifecycle event”，没有覆盖 RAG lifecycle event。** 草案的 normative 文本只要求 bounded loop 内每个 “tool lifecycle event” 带 `iteration`（draft:354），但现行 event enum 和覆盖要求把 tool 与 RAG 分成不同事件族（contract-spec.md:1612,1698,1702），追加倾向也主张 RAG 只发 `rag_retrieval_*`（draft:386）。若不把要求扩展到 loop 内所有 tool/RAG lifecycle events，policy/SOP 检索轮次无法完整回放。

3. **`max_iterations` 终止状态没有进入 canonical state/status contract。** 草案要求达到上限后以可路由的 retrieval/tool status 表达（draft:264），但现有 Knowledge result status 只有 `strong_evidence | partial_evidence | no_evidence | error`（contract-spec.md:90），`route_after_investigate` 的 Reads 也没有 `termination_reason` 或 `max_iterations_reached`（draft:292）。在不污染 evidence status 的前提下，需要明确独立终止原因字段或固定 payload 规则。

4. **安全红线总体保留，但“human review mandatory”不能被表述为所有 action 一律人工审批。** 草案明确 loop 不得触发写动作或绕过 risk/approval/action gates（draft:266），且 action intent 不能跳过 `risk_gate`（draft:201）；但现有路由仍允许 policy 判定后的 `auto allowed -> action_draft`（draft:294；contract-spec.md:329）。确认事实是“需要 approval 时不可绕过 human review”，不是“所有 write action 必须人工审批”。

5. **§17.2 示例保留旧 `node_name` 会削弱新 contract 的可读性。** 草案明确“现有 JSON 示例不修改”（draft:351），但现行示例仍写 `node_name: policy_evidence_retrieve`（contract-spec.md:1655）。字段 schema 无需变更，但示例值应在正式 spec 提升时同步为 `investigate`，否则读者会误以为旧 node 仍是 canonical。

## 对 Claude 7 条裁决倾向的意见

1. **有保留。** 按 intent 配置并设置全局硬上限与 GAD-02 的 `bounded_loop_allowed` / `max_iterations` 准入字段一致（draft:378；DEFERRED-DECISIONS.md:66-67），但现行 intent taxonomy/spec 尚未定义这些运行时配置字段，只有按 intent family 调阈值的先例（contract-spec.md:732）。默认 3、硬上限 5 可以作为讨论参数，不能声称已由 normative contract 定稿。

2. **有保留。** 复用 `partial_evidence` 与 `allow_partial_evidence` 有现行依据（contract-spec.md:81,90,145），且 `no_evidence` 不得授权 policy-required action（contract-spec.md:146）；但“因 max_iterations 截断”是调查完整性事实，不等同于 evidence strength。草案目前也要求上限命中后表达未完成状态（draft:264），因此仍需独立 termination reason，不能只靠 `retrieval_status`。

3. **同意。** 当前草案的一刀切 `permission denied -> final`（draft:209,292）会抹掉同一 loop 已合法获得的独立事实；现行 `BusinessContextV1` 本就能同时表达 facts、missing facts 和 errors（contract-spec.md:173-177）。但必须保留 TrustedContext scope 检查与禁止模型提供权限上下文的红线（contract-spec.md:935-937），且被拒资源不能通过推断泄露。

4. **同意。** 草案已把 `long_term_memory_retrieve` 保持为独立 canonical node并固定进入 `investigate`（draft:19,251），现行 memory contract也把 long-term/case memory 定义为 deferred、非 authority，不能替代当前事实或政策证据（contract-spec.md:952,958-960）。保持独立边界更符合现状。

5. **有保留。** 按调用性质区分 `rag_retrieval_*` 与 `tool_call_*` 符合现行独立事件族和 started/terminal pairing（contract-spec.md:1612,1702），不应为同一 operation 重复发两族事件；但 `search_case_memory` 的归类必须在 discuss 中固定，否则 draft 的 “每个 tool call”/“tool lifecycle”措辞（draft:265,354）仍可能让实现发错事件族。

6. **同意。** iteration 是运行时事实，Phase 10 已拥有 base node/tool/RAG/LLM lifecycle emitters（contract-spec.md:1618），而 replay 要求 partial timeline 和实际调用事件从执行时保留（contract-spec.md:1698,1701）。把 `iteration` 放在首次 emit 的 `redacted_payload` 与现有 minimal envelope 的开放 payload 字段一致（contract-spec.md:1610），不应留给 Phase 15 编造。

7. **有保留。** 不新增 event type 符合 event type 必须来自受控枚举的约束（contract-spec.md:1684），并可用现有 `node_completed` 表达正常受控终止（contract-spec.md:1697）；但 `status:max_iterations_reached` 会与 `completed` 状态语义混杂。应在 redacted payload 中固定 `termination_reason=max_iterations_reached`，同时保留 lifecycle `status=completed`，并与草案要求的可路由终止状态对齐（draft:264,390）。

## 草案 8 章之外的遗漏引用点

以下是对 `business_context_fetch|policy_evidence_retrieve|case_memory_retrieve|route_after_business_context|route_after_policy_evidence` 的 grep 命中中，排除草案已覆盖的 §9.0-§9.5、§12.4、§17.2 后的全部 10 个命中。

1. **contract-spec.md:181，§8.4 `BusinessContextV1`。** 周边语义规定 `BusinessContextV1.status` 驱动 `route_after_business_context`。这是需要更新的 normative spec block，应改为驱动 `route_after_investigate`，并说明 business status 如何与 retrieval/tool status 合并。

2. **contract-spec.md:548，§10.1 AgentState lifecycle matrix / Business context。** Writer 仍是 `business_context_fetch`。这是需要更新的 normative state-lifecycle block，writer 应同步为 `investigate`。

3. **contract-spec.md:549，§10.1 AgentState lifecycle matrix / Evidence context。** Writer 仍是 `policy_evidence_retrieve / recommendation_generation`。这是需要更新的 normative state-lifecycle block；应明确 `investigate` 写 retrieval payload，而 recommendation/citation validator 写实际消费的 `evidence_refs`。

4. **contract-spec.md:581，§10.1 canonical field registry / `business_context`。** Writer 和 reader/router 仍引用 `business_context_fetch`、`route_after_business_context`。这是需要更新的 normative registry block。

5. **contract-spec.md:582，§10.1 canonical field registry / `last_business_context_refs`。** Writer 仍引用 `business_context_fetch / MemoryService`。这是需要更新的 normative registry block。

6. **contract-spec.md:583，§10.1 canonical field registry / `policy_evidence`。** Writer 仍引用 `policy_evidence_retrieve / KnowledgeService`。这是需要更新的 normative registry block。

7. **contract-spec.md:586，§10.1 canonical field registry / `retrieval_status`。** Writer/router 仍是 `policy_evidence_retrieve` / `route_after_policy_evidence`。这是需要更新的 normative registry block，并应与 max-iteration termination semantics 分离。

8. **contract-spec.md:587，§10.1 canonical field registry / `best_score`。** Writer/router 仍是 `policy_evidence_retrieve` / `route_after_policy_evidence`。这是需要更新的 normative registry block。

9. **contract-spec.md:765，§11.5 clarification response 示例。** `blocked_nodes` 仍包含 `business_context_fetch`。这是需要更新的 contract/example block，应改为 `investigate`，否则 resume/blocked-node 语义引用非 canonical node。

10. **contract-spec.md:1724，§17.3 Trace spans。** 建议 span 仍为 `agent.node.business_context_fetch`。这是需要更新的 observability spec block，应同步为 `agent.node.investigate`，并保留 tool/RAG 子 span（contract-spec.md:1725-1727）。
