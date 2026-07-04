# Memory Delta / Contract 清单

本文是 `docs/target-agent-platform-architecture-plan.md` 第 9 节目标记忆设计与当前仓库真实实现之间的执行级差异清单。它只描述当前可依赖的代码事实、兼容命名和目标语义，不把目标架构当成已落地事实。

## 术语锁定

| 术语 | 当前结论 |
| --- | --- |
| `SessionMemory` / `session_memories` | 当前实现名。代码和数据库表继续使用该命名。 |
| `SessionContinuityStore` | 目标语义名，用来描述同 thread 短期连续性存储层；暂不强制重命名当前模型或表。 |
| `SessionContextMemory` | agent-facing projection，当前已实现，权限语义为 `contextual_only`。 |
| `long_term_memory_retrieve` | 当前 graph 兼容节点名，承担 reviewed memory context 加载入口。 |
| `memory_context_load` | target canonical vocabulary，用于文档和 trace projection；不是要求立刻重命名 runtime node。 |
| `memory_write` | 当前 post-response 写入节点 / 调度入口。 |
| `memory_write_pipeline` | 目标语义，表示候选提取、policy、review、写入、event 的完整流水线；当前不是 graph 主链节点。 |
| `MemoryWriteService` | 当前已落地 facade，负责 `propose_candidates` / `evaluate_policy` / `apply_policy_and_write`；session 写入由 `memory_write` post-response 调用，新增 long-term/case 写入路径应从 facade 进入。 |
| `MemoryPolicyDecision` | 当前已落地的可审计 policy 输出对象，包含 `decision`、`review_status`、`reason_code`、`policy_version`、`blocked_by`、`authority_class`。 |
| `MemoryPolicyEngine` | 目标组件名；当前先以 `src/memory/policy.py` 规则模块和 `MemoryPolicyDecision` 契约落地，不是独立大组件。 |

## A. 当前代码已实现

| 目标能力 | 当前实现事实 | 代码锚点 |
| --- | --- | --- |
| 同 thread 短期连续性存储 | 已有 `SessionMemory` 模型和 `session_memories` 表，负责 active slots、summary、last intent、business refs、TTL/version。 | `src/db/models.py`, `src/memory/repository.py`, `src/memory/service.py` |
| agent-facing session projection | 已有 `SessionContextMemory`，并从 `SessionMemoryBundle` 转换为 prompt-safe projection。 | `src/memory/schemas.py`, `src/memory/context_service.py` |
| session memory 权限降级 | `SessionContextMemory` / `SessionContextBundle` 标记为 `authority_class="contextual_only"`，不能作为政策、业务事实、审批或 action 权威。 | `src/memory/schemas.py`, `tests/agent/test_memory_evidence_boundary.py` |
| reviewed long-term memory | 已有 `LongTermMemory` 表、repository、service、review status、prompt-safe retrieval。 | `src/db/models.py`, `src/memory/long_term.py`, `src/memory/repository.py` |
| reviewed case memory | 已有 `CaseMemory` 表、candidate、review status、metadata-first retrieval 和 prompt-safe projection。 | `src/db/models.py`, `src/memory/case_memory.py`, `tests/memory/test_case_memory_retrieval.py` |
| tombstone 防重写 | long-term 和 case memory 写入前检查 tombstone，命中后 skip，并写 `MemoryWriteEvent`。 | `src/memory/repository.py`, `src/memory/long_term.py`, `src/memory/case_memory.py`, `tests/memory/test_memory_tombstones.py` |
| 写入事件审计 | 已有 `MemoryWriteEvent`，记录 decision、reason_code、candidate/source identity，并持久化 `policy_version`、`blocked_by_json`、`authority_class`；session/long-term/case 写入都会写入事件。 | `src/db/models.py`, `src/db/migrations/versions/020_memory_write_event_policy_audit.py`, `src/memory/service.py`, `src/memory/long_term.py`, `src/memory/case_memory.py` |
| PII 写入阻断 | sensitive/prohibited PII candidate 不进入 memory store。 | `src/memory/policy.py`, `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_case_memory_retrieval.py` |
| LLM candidate review gate | `llm_candidate`、semantic/summary/cross-case/behavior inference 默认 `needs_review`，未发布前不进入 prompt retrieval。 | `src/memory/long_term.py`, `src/memory/case_memory.py`, `tests/memory/test_long_term_memory_service.py` |
| 写入 policy rules 模块 | `src/memory/policy.py` 集中 long-term/case source_type、PII、当前业务对象降级等规则。 | `src/memory/policy.py`, `tests/memory/test_memory_policy.py` |
| 可审计 policy decision | policy 规则输出 `MemoryPolicyDecision`，显式记录 decision、review status、reason、policy version、blocked_by 和 authority class。 | `src/memory/policy.py`, `tests/memory/test_memory_policy.py` |
| `MemoryWriteService` facade | 当前 `memory_write` node 通过 facade 提出 session memory candidate 并应用写入策略；facade 也能解析显式 long-term/case candidate 并统一路由到底层 service。 | `src/memory/write_service.py`, `src/agent/nodes/memory_write.py`, `tests/memory/test_memory_write_service.py` |
| 最小 review queue view | 已有 pending review API，复用 long-term/case memory 的 `review_status="needs_review"`，不新增独立队列表；查询规则下沉到对应 repository/service。 | `src/api/routers/memory.py`, `src/memory/repository.py`, `src/memory/case_memory.py`, `tests/test_memory_review_api.py` |
| agent-facing `MemoryContextBundle` projection | 已有轻量 projection，把 `SessionContextMemory`、long-term items、case items 和 status refs 分开放入一个 bundle；reviewed memory 节点在有 session context 时会同时产出统一 bundle。 | `src/memory/context_refs.py`, `src/memory/context_service.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`, `tests/memory/test_memory_context_bundle.py` |
| policy hints 填充 | session bundle 从 recent tool summaries 的 policy refs 派生 `policy_topic_hints` / `prior_policy_mention_refs`；这些字段只作为检索提示，不能进入 `EvidenceRefV1` 或满足 policy gate。 | `src/memory/session_bundle.py`, `tests/memory/test_session_memory_bundle.py`, `tests/agent/context/test_assembler.py`, `tests/agent/test_nodes/test_generate_recommendation.py` |
| long-term semantic alias | `LongTermMemoryView` 保留 legacy `semantic_kind` 兼容投影，但 Phase 48 target contract 收窄为 explicit preference memory only；published prompt retrieval 不再以 durable profile facts、patterns 或 operational constraints 为目标语义。 | `src/memory/schemas.py`, `src/memory/repository.py`, `src/agent/context/projectors.py` |
| graph vocabulary alias | legacy runtime node 与 target vocabulary 已有 alias 投影。 | `src/agent/graph_vocabulary.py`, `tests/agent/test_graph.py`, `tests/agent/test_graph_vocabulary.py` |
| post-response memory write | `memory_write` 当前通过 agent run API/runtime 在 response 后调度，不在 graph 主链 `final_response -> END` 中强行串联。 | `src/api/services/agent_run_memory.py`, `src/api/routers/agent_runs.py`, `src/api/routers/agent.py` |

## B. 当前代码部分实现 / legacy 命名

| 目标说法 | 当前状态 | 当前处理 |
| --- | --- | --- |
| `SessionContinuityStore` | 语义已接近，但代码模型和表仍叫 `SessionMemory` / `session_memories`。 | 保留当前名，在文档里作为目标语义 alias。 |
| `session_context_load` | target vocabulary 已存在，但 runtime graph 仍使用 `session_memory_load`。 | 保留 legacy node，通过 `graph_vocabulary` 投影。 |
| `memory_context_load` | target vocabulary 已存在，但 runtime graph 仍使用 `long_term_memory_retrieve` / `reviewed_memory_context_retrieve`。 | 保留 legacy node，通过 `graph_vocabulary` 投影。 |
| `MemoryContextBundle` | projection 和部分消费面已落地，但不是底层 store 合并，也不是所有调用方唯一输入。 | 保持 session、long-term、case 三类语义分开，并保留 legacy fields 兼容。 |
| `MemoryPolicyEngine` | 可审计 decision object 和规则模块已落地，但没有独立大组件生命周期/API。 | 先用规则模块和 tests 锁定行为，再决定是否抽组件。 |
| `MemoryWriteService` / `memory_write_pipeline` | facade 已能处理 session candidate，并能解析显式 long-term/case candidate 后统一 policy/write 路由；pending review view 已落地，但完整 extractor、独立 review queue worker/assignment 编排还未全部落地。 | 维持 post-response 调度，不把 pipeline 当 graph 主链。 |
| session write event | session memory write 已补 `MemoryWriteEvent`，但仍保留 `memory_write` trace 和 `MemoryWriteDecisionV2` 作为 agent-facing 投影。 | 不要求 graph 主链消费底层 event row。 |
| CaseMemory 默认 review | 已收紧为只有 `human_reviewed` / `explicit_admin_preference` auto approve；deterministic/outcome/approval source 默认 `needs_review`。 | retrieval 结果仍只能作为 precedent/context，不能作为 policy citation 或当前业务事实权威。 |
| Long-term published target | Phase 48 target contract 是 explicit preference memory only，published long-term source types 仅为 `explicit_user_preference`、`explicit_admin_preference`、`human_reviewed`。 | `long_term_memories` / `memory_type='long_term_fact'` 只是 legacy storage/table identity，不代表 facts、patterns、constraints、tool results 或 run summaries 可发布。 |

## C. 目标设计还没落地，不能当事实

| 目标设计 | 为什么不能当当前事实 |
| --- | --- |
| 全量 graph node 重命名到 canonical vocabulary | runtime graph 仍保留 legacy node；当前只做 alias projection。 |
| `memory_write_pipeline` 作为 graph 主链阶段 | 当前 memory write 是 response 后调度逻辑，不在主链强制串联。 |
| 独立 `MemoryPolicyEngine` 大组件 | 当前 policy 是规则模块 + `MemoryPolicyDecision`，尚无独立组件生命周期、tenant config、retention config 和 review routing API。 |
| 完整多类型 `MemoryWriteService` pipeline | facade 已能解析显式 long-term/case candidate 并统一路由，pending review view 已复用 `needs_review` 行落地；复杂 extractor、独立 review queue worker/assignment、批量候选治理还未全部落地。 |
| `SessionContinuityStore` 表/模型重命名 | 当前数据库仍是 `session_memories`，不能在文档或测试里假设已重命名。 |
| `SessionContinuityStore` 完整 facade | 当前仍直接使用 `SessionMemory` / `SessionMemoryRepository` 实现连续性。 |
| 全量 prompt/graph 调用方只消费 `MemoryContextBundle` | 当前已有部分消费面，legacy fields 仍保留并被部分调用方直接使用。 |

## 权限边界

Memory 的默认权限是上下文辅助，不是证据或执行授权：

- memory 不能生成或伪装成 `EvidenceRefV1`。
- case memory 不能作为 policy citation。
- long-term memory 不能证明当前订单、退款、工单、审批、支付或物流状态。
- session slot 过期、scope 不匹配、intent 不兼容或被用户当前轮否定时不能继承。
- 高风险 action 不能只靠 inherited slot 执行，必须有当前业务事实引用、政策证据、claim verification、risk/approval/action binding。
- LLM candidate 不能直接 published。
- tombstone 命中后，异步或延迟 candidate 也不能写回同一内容或同一 source identity。

## Long-term Memory 语义收窄

Phase 48 target contract: long-term memory is explicit preference memory only. It is a contextual preference/hint layer, not durable fact/profile/pattern/rule storage and not an authority source.

Allowed published long-term semantics:

| Published semantic | 说明 |
| --- | --- |
| explicit soft preference / hint | 商家或 tenant 的明确软偏好，例如回复风格、升级倾向、低金额售后沟通倾向。 |
| `explicit_user_preference` | 用户通过确定性显式短语保存的非 PII、非 tombstone、scope 合法、软偏好。默认 merchant/team scope。 |
| `explicit_admin_preference` | 管理员通过 admin-only save 明确保存的非 PII、非 tombstone、scope 合法、软偏好；tenant scope 只允许该路径。 |
| `human_reviewed` | 人工审核通过的 preference candidate；自动观察来源审批后必须发布为 `human_reviewed`。 |

明确禁止把以下内容作为 long-term memory 的 published authority：

- 当前订单状态。
- 当前退款状态。
- 当前工单状态。
- 审批结论。
- 政策规则。
- 单次客服判断。
- 单次工具调用的当前业务状态快照。
- durable profile facts。
- merchant patterns。
- operational constraints。
- deterministic tool results。
- run summaries、strategy hints、similar-case hints、cross-case pattern candidates。

## 写入策略表

| source / 条件 | 当前 contract |
| --- | --- |
| `explicit_user_preference` | 非 PII、非 tombstone、scope 合法、软偏好时可 auto publish long-term；普通 chat 不得语义推断成 long-term。 |
| `explicit_admin_preference` | 非 PII、非 tombstone、scope 合法、软偏好时可 auto publish；tenant scope 只能 admin 显式保存。 |
| `human_reviewed` | 非 PII、非 tombstone、scope 合法、软偏好时可 publish；仍不能替代政策或业务事实证据。 |
| `semantic_episode_candidate` | 只能产生 `needs_review` 的 `preference_candidate`；审批通过后 published row 的 `source_type` 必须变成 `human_reviewed`。 |
| `deterministic_tool_result` / `confirmed_business_outcome` / `approved_approval_state` | 不允许成为 published long-term memory source。当前业务事实、审批和动作结果必须留在权威业务/审批/动作系统。 |
| `llm_candidate` / `summary_candidate` / `cross_case_pattern_candidate` / `behavior_inference` | 不允许成为 published long-term memory source；自动观察最多进入待审核 preference candidate 队列。 |
| PII = `sensitive` / `prohibited` | skip/block，不写入 memory row。 |
| tombstone match | skip/write_blocked 语义，不允许重写。 |
| case memory | 默认 review；只有 `human_reviewed` / `explicit_admin_preference` 可 auto publish。retrieval 结果始终只能作为 precedent/context，不能作为 policy citation、当前业务事实或 action authority。 |
| policy decision object | 所有写入策略判断应输出 `MemoryPolicyDecision`，至少包含 `decision`、`review_status`、`reason_code`、`policy_version`、`blocked_by`、`authority_class`。 |

## Contract Test 覆盖清单

| Contract | 覆盖位置 |
| --- | --- |
| memory 不能生成 `EvidenceRefV1` | `tests/agent/test_memory_evidence_boundary.py`, `tests/memory/test_case_memory_retrieval.py` |
| case memory 不能作为 policy citation | `tests/agent/test_memory_evidence_boundary.py` |
| long-term memory 不能证明当前订单/退款/工单事实 | `tests/agent/test_memory_evidence_boundary.py`, `tests/memory/test_long_term_memory_service.py` |
| session slot 过期或 intent 不兼容时不能继承 | `tests/agent/test_required_slots.py` |
| 高风险 action 不能只靠 inherited slot 执行 | `tests/agent/test_nodes/test_assess_risk_and_approval.py` |
| LLM candidate 不能直接 published | `tests/memory/test_long_term_memory_service.py`, `tests/memory/test_case_memory_retrieval.py` |
| tombstone 命中后不能被异步候选写回 | `tests/memory/test_memory_tombstones.py`, `tests/memory/test_case_memory_retrieval.py` |
| session write 也持久化 `MemoryWriteEvent` | `tests/memory/test_session_memory_service.py` |
| 写入策略集中规则 | `tests/memory/test_memory_policy.py` |
| `MemoryWriteService` facade | `tests/memory/test_memory_write_service.py` |
| 最小 pending review view | `tests/test_memory_review_api.py`, `tests/memory/test_long_term_memory_repository.py`, `tests/memory/test_case_memory_retrieval.py` |
| `MemoryContextBundle` projection | `tests/memory/test_memory_context_bundle.py` |
| `MemoryContextBundle` prompt 消费和 policy hints 隔离 | `tests/agent/context/test_assembler.py`, `tests/agent/test_nodes/test_generate_recommendation.py` |
| legacy graph node 与 target vocabulary alias | `tests/agent/test_graph.py`, `tests/agent/test_graph_vocabulary.py` |
