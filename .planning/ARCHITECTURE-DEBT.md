# MOCA 架构债务 / 缺陷发现台账

> 本文件记录 MOCA 各子系统在代码走查、phase 实现、本地验证中**检测出的 bug、设计缺陷、遗留妥协**，以及**已完成的修复**。
> 与 `LOCAL-VALIDATION-ISSUES.md` 的分工：那个记「本地调试/启动/验证时踩到的具体事故」；本文件记「子系统级的架构缺陷与处理台账」，颗粒度更粗、生命周期更长。

## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
- 每条目尽量给：问题现象 / 根因、影响、处理状态、证据（phase / commit / 文件:行）、剩余风险。
- 只写「基于仓库真实代码、测试、planning artifact 核对过」的内容。未核实的写「未确认」，不编。
- 目标态 vs 已实现要分清：`docs/contract-spec.md` 是目标契约，不等于已实现事实。

## 状态图例

- ✅ 已修复并（在可验证范围内）验证
- ⚠️ 已修复但验证有缺口
- 🟡 已知遗留 / 有意妥协（defer，非 bug）
- 🔴 未修复的缺陷 / 待立项

---

# 0. 跨子系统目标架构收敛（Agent Graph / Intent / RAG / Memory / Risk）

## 2026-07-06 — 目标 Agent Graph 架构落 phase 前仍需收敛的 10 项边界 🟡

- **子系统**：意图识别 / 工具调用 / RAG / 记忆 / 审批风险主链
- **问题现象/根因**：`docs/target-agent-platform-architecture-plan.md` 的目标 graph 方向合理，但若直接落 phase，仍存在若干实现级 contract 未硬化：`contextual_intent_resolve` 输入输出、`safety_pre_route` vs `risk_gate` 分工、slot provenance、memory 可信度用途、RAG/claim fail-closed 状态、LLM authority、approval pending 状态机、memory write graph 化触发条件、current-to-target migration matrix 等。
- **影响**：后续 phase plan 可能把当前厚 `classify_intent` 改名但不瘦身，或把入口 risk/action risk、slot 抽取/slot 裁决、memory hint/evidence 混在一起，导致 eval/replay/trace 边界继续不清。
- **处理状态**：⚠️已完成文档/spec 收敛但 runtime 迁移未开始。已在 `docs/target-agent-platform-architecture-plan.md` 新增“后续 Phase 改进队列（按优先级）”，修正 Phase 49 后 `investigate` 已接入 bounded read-only ReAct 主路径的过时描述，并将当前目标 runtime graph 收敛为 15 个主链 registered nodes；`slot_extraction`、`normalize_input`、`memory_write`、`trace_close`、`action_execution` 不再属于当前主链 node set。2026-07-06 已追加同步 README、`docs/current-langgraph-architecture.md`、`docs/architecture-overview.md`、`docs/rag-architecture-spec.md`、`docs/agent-architecture-routing-explanation.md`、`docs/tool-system-unification-plan.md`、`docs/agent-architecture-spec-review.md`、`AGENTS.md`、`.planning/DEFERRED-DECISIONS.md` 和旧 §9 草稿/review 的读法边界，避免“当前源码图 / 目标 graph / 历史草稿”混用。同日新增 Phase 50 `Canonical Agent Graph Migration Spec and Guardrails`，把 15-node target、no `slot_extraction` graph node、临时兼容策略、LLM authority matrix、验证矩阵和最终 no-debt gate 固化为后续 implementation phase 的约束；随后注册 Phase 51-58 作为后续 macro implementation phases，分别覆盖 baseline guardrails、`safety_pre_route`、`contextual_intent_resolve`、`slot_resolution_gate`、`memory_context_load`、`recommendation_generation`、`risk_gate`/`approval_gate`、final no-debt cutover。
- **证据**：`docs/target-agent-platform-architecture-plan.md` §6.1 / §19；`docs/contract-spec.md` §9；`.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`；`.planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md`；`src/agent/nodes/investigate.py`；`src/agent/nodes/investigate_planner.py`。
- **剩余风险**：Phase 50 只是迁移总规约，runtime graph 仍未切到 canonical 15-node final state；后续仍需按 SPEC 逐步转成 implementation plans，并在最终 no-debt phase 删除 active legacy node names / dual routes / compatibility aliases。

## 2026-07-06 — Phase 51 canonical graph baseline guardrails 已落地 ⚠️

- **子系统**：Agent Graph / 意图识别 / RAG / 记忆 / 风险审批主链
- **问题现象/根因**：Phase 52-58 开始 rewiring 前，需要先把当前源码 graph、目标 15-node graph、迁移期 legacy alias、router route map 和 forbidden registered-node drift 变成机器可验证 guardrails。否则后续 phase 可能把目标态当已实现，或误把 `slot_extraction` / `memory_write` 等 helper/lifecycle concern 注册进主链 graph。
- **影响**：没有 baseline guardrails 时，后续 runtime migration 容易漏掉 active legacy node（尤其是 `generate_recommendation -> recommendation_generation` 这条当前不在 `graph_vocabulary.py` 的映射），也容易让最终 no-debt gate 提前失败或被静默跳过。
- **处理状态**：⚠️已完成 Phase 51 guardrail/matrix 覆盖，但 runtime 迁移未完成。新增 `tests/architecture/graph_baseline.py` 和 `tests/architecture/test_canonical_graph_baseline.py`，用 AST/source inspection 验证当前 14 个 active registered graph nodes、目标 15-node set、6 个 active legacy-to-target migration rows、当前 conditional edge route map、forbidden main-chain registered-node set，以及 Phase 58-scoped final exact no-debt marker。`src/agent/graph.py` 当前仍是 legacy/canonical mixed；Phase 51 没有创建 `safety_pre_route`、`contextual_intent_resolve`、`slot_resolution_gate`、`memory_context_load`、`recommendation_generation` 或 `risk_gate` runtime nodes。
- **证据**：`.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-01-SUMMARY.md`；`.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-02-SUMMARY.md`；`tests/architecture/graph_baseline.py`；`tests/architecture/test_canonical_graph_baseline.py`；`uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` = 8 passed / 1 skipped；`uv run pytest tests/architecture -q` = 78 passed / 2 skipped。
- **剩余风险**：Phase 51 只证明 baseline 和 migration matrix 可验证；Phase 52-58 仍需逐步切换 runtime graph，并在 Phase 58 删除 active legacy graph node names / dual route destinations / compatibility allowances。

## 2026-07-06 — Phase 52 safety_pre_route runtime pre-route 已落地，intent 兼容面留给 Phase 53 ⚠️

- **子系统**：Agent Graph / 意图识别
- **问题现象/根因**：Phase 51 之前的 runtime graph 把 request-risk / untrusted approval pre-route 行为藏在厚 `classify_intent` 节点与 `classification_trace.pre_route_decision` 中。这样 trace vocabulary 只能靠 `classify_intent:pre_route` synthetic alias 投影到 `safety_pre_route`，真实 graph entry path 没有显式 pre-route ownership。
- **影响**：安全前置判断在 replay/eval/API trace 中容易被误读成 classifier 内部实现细节；如果不记录剩余兼容面，`classify_intent` safe-path continuation 和 classifier-owned `pre_route_decision` 可能变成永久迁移债务。
- **处理状态**：⚠️Phase 52 已把 `safety_pre_route` 注册为 `receive_request` 之后的 runtime graph node，并通过 `route_after_safety` 在 untrusted approval chat、multi-target、requires-clarification、异常或未知 route 时 fail closed 到 `clarification_gate`；`src/agent/graph_vocabulary.py` 已把真实 `safety_pre_route` trace projection 标为 `runtime`。Phase 52 code review 发现 `approve APR1` / `approve APR_1` / `同意 APR1` 这类 approval-like + approval ID 变体会漏过 pre-route 并进入 `classify_intent`，已在同一 phase 修复：`detect_pre_route()` 现在要求“approval-like action + approval context” fail closed，并补了 node 与 graph smoke 回归。safe-path continuation 仍临时进入 `classify_intent`，`classification_trace.pre_route_decision` 也仍保留为 classifier parity artifact；两者删除目标均为 Phase 53 / CAGM-04，不在 Phase 52 删除。
- **兼容面台账**：

| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
|----------------|-----------------|--------|------------------|------------|--------------|
| Safe-route continuation `safety_pre_route -> classify_intent` and `classify_intent` active graph node | `contextual_intent_resolve` / Phase 53 CAGM-04 | Phase 52 only extracts pre-route safety; session context before intent and contextual intent cutover are Phase 53 | `classify_intent` continues to project to `contextual_intent_resolve`; new `safety_pre_route` projects as runtime canonical | Architecture graph baseline + graph tests prove unsafe pre-route cases stop before `classify_intent` and safe cases use compatibility only | Phase 53 |
| `classification_trace.pre_route_decision` inside `classify_intent` | `safety_pre_route` for runtime pre-route ownership; Phase 53 removes classifier-owned duplicate | Safe-path compatibility may still need classifier trace parity until contextual intent cutover | `classify_intent:pre_route` remains a compatibility alias to `safety_pre_route`; `safety_pre_route` itself is runtime | `test_graph_vocabulary.py`, `test_safety_pre_route.py`, and classifier parity tests | Phase 53 |

- **证据**：Phase 52 `52-01-SUMMARY.md`（node extraction）、`52-02-SUMMARY.md`（graph wiring）、`52-03-PLAN.md`（compatibility closeout）、`52-REVIEW-FIX.md`（approval ID 变体漏判修复）；`src/agent/graph.py` 中 `receive_request -> safety_pre_route` entry edge；`src/agent/routing.py` 中 `route_after_safety` allowlist/fail-closed；`src/agent/intent_policy.py` 中 `detect_pre_route()` approval action/context 判定；`src/agent/graph_vocabulary.py` 中 `safety_pre_route` runtime projection 与 `classify_intent:pre_route` compatibility alias；`tests/agent/test_nodes/test_safety_pre_route.py`、`tests/agent/test_graph.py`、`tests/architecture/test_canonical_graph_baseline.py`、`tests/agent/test_graph_vocabulary.py`。
- **剩余风险**：Phase 52 只完成 safety pre-route extraction；Phase 53 必须删除 active `classify_intent` graph-node compatibility，把 safe path 切到 `session_context_load -> contextual_intent_resolve`，并清理 classifier-owned duplicate `classification_trace.pre_route_decision`。

## 2026-07-06 — Phase 53-01 canonical contextual intent 合约已落地，active graph cutover 留给 53-02 ⚠️

- **子系统**：Agent Graph / 意图识别
- **问题现象/根因**：Phase 52 后 safe path 仍通过 active graph 的 `classify_intent` / `route_after_intent` / `session_memory_load` 兼容链路；同时 canonical `contextual_intent_resolve` 节点、`llm_outputs["contextual_intent_resolve"]` owner 和 `route_after_contextual_intent` 边界尚未作为独立可测合约存在。
- **影响**：如果直接在后续 plan 改 graph path map，容易把 intent LLM candidate 输出、slot-required route、trace owner 和 legacy classifier 兼容面混在一个提交里，导致中间状态不可验证或提前改动 active route/policy 值。
- **处理状态**：⚠️已在 53-01 建立 canonical intent node 与非 active router helper，并验证 canonical trace/LLM owner、candidate-only state write、pending-slot short reply、invalid structured output fail-closed，以及 `classification_trace.pre_route_decision` 不再出现在 canonical contextual intent trace 中。`classify_intent.py` 只保留为兼容 wrapper/import 面；但 **active graph route/policy cutover 尚未完成**，`route_after_safety`、`route_after_intent`、`SAFETY_ROUTES`、`INTENT_ROUTES`、`IntentRouteLiteral` 和 `IntentDefinition.initial_route` 仍保持 pre-53-02 兼容值。
- **证据**：Phase 53 Plan 53-01；`src/agent/nodes/contextual_intent_resolve.py`；`src/agent/nodes/classify_intent.py`；`src/agent/routing.py` 的 `route_after_contextual_intent`；`tests/agent/test_nodes/test_contextual_intent_resolve.py`；`tests/agent/test_nodes/test_classify_intent.py`；`tests/test_graph_routing.py`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py -q --tb=short` = 90 passed。
- **剩余风险**：53-02 必须原子切换 `safety_pre_route -> session_context_load -> contextual_intent_resolve` active graph wiring、active router/policy route values和 path maps；53-03 仍需完成 graph vocabulary、current architecture docs、最终兼容面 ledger 与更广 artifact scan。Phase 54 前 `extract_slots` 仍是有意保留的 slot-required compatibility destination。

---

# 1. 工具调用（Tool Platform）

**范围**：`src/tools/`（catalog / contracts / runtime / policy / platform / projection / validation / executors）。
**这一轮 = milestone v2.1「Tool Platform Hardening」，Phase 37–41，5 phase / 14 plan，全部标记 complete（`.planning/STATE.md`）。**
**主要契约参考**：`docs/contract-spec.md` §8.0 / §12.5 / §12.6；phase plan 若发现冲突，应先提出 spec delta。

## Phase 37 — 声明单源 + runtime/policy 内部收敛（TPH-03, TPH-04）✅⚠️

**问题**
- 工具声明分散重复：schema、investigate 工具名集合在 catalog、`manager.py`、测试里各写一份，存在 drift 风险（改一处漏一处）。
- `ToolRuntime` 各失败出口各自重复拼装 safe_result / projection / decision event / return tuple，容易不一致。
- `runtime_auth` 是一长串硬编码 if-chain，门的顺序靠人肉维护。

**修复**
- 引入单一声明表 `_TOOL_DECLARATIONS`（当前 9 个工具），descriptor / `_IDENTIFIER_SCHEMAS` / investigate 可见性全部从它派生；删除 manager 里未被引用的 `INVESTIGATE_TOOL_NAMES`；investigate 过滤统一走 `catalog.investigate_tool_names(...)`。
- 新增 `ToolRuntime._fail(...)` 共享 helper，7 条失败路径统一经它返回。
- 引入 `RuntimeAuthGate` + 有序 `_runtime_auth_gates`：`caller_allowlist → permission → side_effect → resource_scope → approval → safety_snapshot → idempotency`，保留原 reason-code 顺序；descriptor 缺失 / 工具不可用仍作 preflight `tool_unavailable`。

**证据**：37-01/02/03-SUMMARY；commit `0030380`/`ff72c2d`（单源）、`e9d09e0`（_fail）、`9f060e6`（gate 序列）。

**遗留 / 缺口**
- ⚠️ Phase 37 全程 DB-backed pytest 被本地 PostgreSQL 未启动 block（最好一次 `66 passed, 14 errors`，errors 全是 `localhost:5432` 连接被拒的 fixture setup，非产品代码失败）。见 `LOCAL-VALIDATION-ISSUES.md`。
- 本 phase 未改任何外部契约字段（ToolDescriptor / ToolResultV2 / ToolCallContext 等），仍全部用通用 output schema（留给 Phase 38）。

## Phase 38 — output_schema 声明 + 运行时输出校验强制（TPH-01）✅

**问题（核心）**
- 所有工具的 `output_schema` 都是通用 `{"type":"object"}`，执行器返回任意结构都能通过——**输出侧完全没有 schema 约束**，raw/debug 字段可能随 `ToolResultV2.data` 泄漏。

**修复**
- 本地 validator 支持 nullable 与 type-union（`{"type":["string","null"]}`、`{"type":"null"}`），首个候选校验成功即返回；未引入 `jsonschema` 依赖。
- 为 8 个读/检索工具（get_order / get_refund_case / get_ticket / search_policy / search_case_memory 等）声明严格 output schema（`additionalProperties:false`）；为 3 个当前不可用工具（get_logistics / get_merchant_risk / search_sop）声明严格 no-data 空对象 schema。
- runtime 在 `success` / `partial_success` 路径强制校验输出；非法输出映射为 `invalid_response` + 清空 `data` + 返回 `INVALID_EXECUTOR_RESPONSE` + 不序列化原始 sentinel。

**关键 bug（post-review 修复）**
- 🔴→✅ `status="success"` 且 `data=None` 时会**绕过**非空 object output schema（校验被短路）。修复为即使 `data` 为 None 也执行输出校验，非空 schema 无法被空成功结果绕过。commit `16a5d8f`。

**证据**：38-01/02/03-SUMMARY；commit `877ae04`（validator）、`f9af07c`（catalog schema）、`5f748c7`（runtime 校验测试）、`16a5d8f`（空成功绕过修复）。38-03 记录 compose 起 PostgreSQL 后 DB-backed 路径已验证通过。

## Phase 39 — contract-spec §12.5/§12.6 对齐（TPH-02）✅（部分未逐行核对）

**问题**：Phase 38 落地 output_schema 语义后，`docs/contract-spec.md` §12.5/§12.6 需与实现对齐，避免 spec 与代码不一致。

**处理**：走双 AI 复审流程（`gsd-plan-checker` + Codex + Claude 裁决）把实现态回写 spec。

> ⚠️ 说明：本条目依据 `.planning/STATE.md` roadmap 与 40-CONTEXT 的引用得出；**39-01-SUMMARY 本轮未逐行读取**，具体改了 spec 哪几段未在此逐条核实。需要时读 `.planning/phases/39-.../39-01-SUMMARY.md` 补全。

## Phase 40 — 工具契约校验加固（TPH-05）✅

**问题（Phase 38/39 后残留的 source-confirmed 缺口）**
- 写动作 `create_coupon_grant_draft` 仍是通用 output schema——**唯一的高风险写工具输出没被约束**。
- 本地 validator「广告了但没实现」的关键词：string `maxLength`、numeric `minimum`/`maximum`/`exclusiveMaximum` 实际被静默忽略——schema 里写了约束，运行时根本不生效（假安全）。
- domain-scope 归属检查是 advisory marker（policy 只记 `requires_domain_scope_check`，真正 merchant-scope/no-leak 在 BusinessFactService），缺回归 backstop，容易 drift。

**修复**
- 用 `ActionService.create_coupon_grant_draft` 真实成功 payload 派生严格 schema（draft_id / idempotency_key / status / created / idempotent_reused / action_draft / draft_outcome / execution_mode / action_result），`additionalProperties:false`，测试 fake 升级到真实契约而非弱化 schema 迁就 fake。
- 实现缺失的 validator 关键词（maxLength / minimum / maximum / exclusiveMaximum，数值约束同时作用 integer 与 number）。
- 加 descriptor schema meta guard：遍历所有 input/output schema，出现**不支持的关键词就 fail**，防止「看起来生效实则被忽略」的约束。`pattern`/`format`/`oneOf`/`anyOf` 明确 out-of-scope。
- 加架构 backstop 测试：domain-lookup 读工具（get_order/get_refund_case/get_ticket）若偏离 `ToolPlatform → BusinessToolExecutor → BusinessFactService` 边界与 merchant-scope/no-leak 即失败。**未改 runtime policy 去做归属查库**（保持架构分层）。

**证据**：40-CONTEXT（D-05~D-16）；commit `5ebd913`（action output schema）、`69b9dae`（schema 校验关键词）、`508562c`（domain scope marker backstop）；40-VERIFICATION。

**遗留**
- 🟡 get_logistics / get_merchant_risk / search_sop 保持 no-data schema，执行器不可用——**有意 defer**，不臆造未来 payload。

## Phase 41 — 删除 legacy manager 适配器（TPH-06）✅

**问题**：`UnifiedToolManager` 是过渡期兼容适配器，与目标态「`ToolPlatform` 单一入口」并存，造成 spec 与代码双轨、生产代码里 `tool_manager._platform` 解包这种脆缝。属破坏性 API 清理。

**修复**
- 删除 `UnifiedToolManager` 适配器、`src.tools.__getattr__` 懒导出与 `__all__` 条目；`ToolPlatform` 成为唯一 graph-facing 入口。
- 移除 `investigate.py` / `action_draft.py` 里对 `_platform` 的生产解包；改为注入 `tool_platform` / `ToolPlatform.with_defaults(session)` / 空 fallback。
- `_side_effect_allowed` 从将删的 `manager.py` 迁到 `policy.py`（active 架构测试代码）；`manager_results.py` 不动（是 runtime/executor 仍用的 safe-result helper，非适配器）。
- 迁移/删除 `test_unified_tool_manager.py`，fake 全部改成 platform-native（不再依赖 `_platform`/`_descriptors`/`_manager.invoke`）；架构测试禁止生产代码 import `src.tools.manager`，断言 `src/` 无 `UnifiedToolManager` 残留。
- 更新 `docs/contract-spec.md` §6/§10/§12.6 删除 legacy 适配器契约；保留 `ToolResultV2`/`ToolCallContext` §8.0 no-diff 保护。

**证据**：41-CONTEXT（D-01~D-16）；commit `4078ab9`（helper 迁移）、`27e4630`（node seam 移除）、`3e1c1da`（API 移除）、`e2eb62c`（残留引用清理）；41-REVIEW / 41-VERIFICATION / 41-CLOSURE-REVIEW。

---

# 2. 意图识别（Intent Recognition）✅🔴🟡

**范围**：`src/agent/nodes/classify_intent.py`、`src/agent/intent_policy.py`、`src/agent/prompts.py`、`src/agent/routing.py`、`src/agent/intent_manifest.py`、`src/agent/schemas.py`。
**已 ship 的相关 milestone**：v1.8 Intent Routing Safety Hardening（Phase 25，IRS-01~IRS-12）。

> 以下为 2026-07-02 代码走查中发现的**设计层面缺陷**与后续处理状态。ID-01/ID-03 已通过三层契约拆分落地；ID-04 的档位 A 已通过 Phase 43 落地；ID-02 仍未修复。

## ID-01 关键词候选覆盖 LLM 语义判断 ✅

**原问题/根因**：`resolve_intent_precedence` 旧实现（`intent_policy.py`）在 LLM 已给出主/次意图后，又用纯字符串包含（`"投诉"/"升级"/"申诉"/"reply"` 等）扫原始 query 往候选表里追加意图，再按优先级排序选赢家。关键词不理解否定/反问/引用。
**失败场景**：用户「这个不算投诉吧，我就是问下退款进度」——LLM 正确判 `refund_troubleshooting`，但 `"投诉" in text` 命中把 `complaint_escalation` 塞进候选，其优先级更高 → 被错误路由到投诉升级流程。
**深层问题**：LLM 分类与关键词分类在做同一件事（判意图），但「谁在什么条件下说了算」没有显式规则，是 if 叠优先级排序涌现出来的覆盖行为，无专门测试锁定，易长回归 bug。
**修复**：新增三层解耦中的语义层契约 `SemanticIntent`；把关键词扫描拆成 `derive_keyword_signals(...)`，只产候选、不选赢家；把赢家选择集中到 `arbitrate_intent(...)`，显式约束「关键词候选只有在 LLM primary/secondary 也列出该意图，或 raw confidence 低于普通阈值时，才可覆盖 LLM primary」。
**证据**：`src/agent/intent_policy.py`（`SemanticIntent` / `derive_keyword_signals` / `arbitrate_intent` / `resolve_semantic_intent`）；`src/agent/nodes/classify_intent.py`（`classification_trace.semantic_intent`）；`tests/agent/test_intent_routing.py` 覆盖关键词候选不选赢家、高置信”不算投诉”不被覆盖、低置信可抬升；执行规格见 `.planning/intent-layering-codex-brief.md`；回溯登记为 Phase 42（`.planning/phases/42-intent-recognition-three-layer-decoupling/`）。三层解耦代码基线 commit `a0a98e4`。
**验证**：`uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` → Phase 42 回溯登记时重跑 `1230 passed, 1 skipped`；`uv run ruff check src/agent tests/agent` → pass。
**状态**：✅ 已修复并验证。唯一登记行为变化：`"这个不算投诉吧，我就是问下退款进度"` 从旧的关键词误抬 `complaint_escalation` 修正为 `refund_troubleshooting`。

## ID-02 置信度阈值卡的是未校准的自报置信度 🔴

**现象/根因**：`decide_clarification` / `confidence_requires_clarification` 用双阈值（普通 <0.65、安全敏感 <0.85）决定是否澄清，但当前仍卡 LLM 自报的 `confidence`。prompt few-shot 里 `calibration_version` 恒为 `calibration.unverified`（`prompts.py`），即未做校准。
**影响**：用未校准的自报置信度守资损相关澄清闸门，安全性可能是名义上的。
**本次处理**：三层解耦已新增 `ClarificationDecision`，并在 `decide_clarification(..., calibrated_confidence=None)` 预留校准入参位；`classification_trace.clarification_decision.threshold_applied` 已可回放阈值。但函数当前按 brief 要求显式 `del calibrated_confidence`，未实现真实校准。
**状态**：🔴 未修复，待立项。当前只是 ID-02 的接口占位，不算修复。

## ID-03 意图/操作/风险三维耦合在多张表 + if-elif ✅

**原问题**：意图→路由、意图+操作→风险、意图→槽位散在多个 registry 和 `resolve_risk_tier` 的 if-elif 链里。`intent_policy.py` 旧实现有个两分支返回同值的坏味道（`approval_required if effective_channel in ORDINARY_CHAT_CHANNELS else "approval_required"`）。
**影响**：10 意图 × 6 操作组合扩展时需跨多表核对，契约一致性风险。
**修复**：新增风险层契约 `RiskDecision` 和声明式 `RISK_POLICY_TABLE`；`resolve_risk_decision(...)` 负责查表与确定性兜底，`resolve_risk_tier(...)` 保持向后兼容但委托风险层；旧的同值三元死分支已删除。风险查表顺序经逐组合等价测试锁定，保持旧行为不漂移。
**证据**：`src/agent/intent_policy.py`（`RiskDecision` / `RISK_POLICY_TABLE` / `resolve_risk_decision`）；`src/agent/nodes/classify_intent.py`（`classification_trace.risk_decision`）；`tests/agent/test_intent_routing.py` 遍历 intent × operation × channel × routing_hints 做旧逻辑等价测试，并覆盖策略表每行可达与死分支删除；回溯登记为 Phase 42。三层解耦代码基线 commit `a0a98e4`。
**验证**：同 ID-01 的 §6 pytest / ruff 命令均通过。
**状态**：✅ 已修复并验证。

## ID-04 意图识别是"分类"而非"任务规划"——多意图被单赢家坍缩、次诉求被静默丢弃 ✅（档位 A）

**现象/根因**：`resolve_intent_precedence`（`intent_policy.py:463-466`）把「LLM 主意图 + 次意图 + 关键词扫出的候选」揉成一个候选池，`for intent in PRECEDENCE_INTENTS: if intent in valid_candidates: return intent` —— 遍历到第一个命中即 return **单个** effective intent。`secondary_intents` 只是参与竞选单一赢家的陪跑候选，选完即丢，从不存在「主意图做完接着做次意图」。系统把"用户一句话里有两件事"建模成了"用户到底指哪一件"的**消歧问题**，而非"用户要两件事、按序做"的**组合/规划问题**——这是范畴错误：用分类器解规划问题。

**失败场景**：「查下 ORD-1001 退款卡在哪，然后帮我拟个回复给客户」= `refund_troubleshooting` → `ticket_reply_draft` 的**带数据依赖顺序**（回复内容依赖排查结论）。当前设计按优先级选一个、丢一个，用户另一半请求静默消失。

**多意图其实混三种关系，不能一律顺序执行**：
- **依赖型**（A 输出喂 B）："查完卡哪 → 拟回复"。这才是真正的顺序执行。
- **修饰型**（不是第二个任务，是给主任务加上下文/抬风险档）："投诉很严重，给多少补偿券"——"投诉"是抬高补偿风险档的**修饰语**，不是要单独执行的意图。few-shot 里 compensation 主 + complaint 次正是此类；对它做"顺序执行升级流程"是错的。此类与 ID-01 关键词误抬同源。
- **并列独立型**："查订单 A 和订单 B"——实为同意图多实体，不算多意图。

**资损硬约束**：顺序执行次意图 ≠ 在同一 turn 自动跑掉高风险第二步。若后续步是 draft_action/execute/approval，组合必须**停在每个风险闸前**，把高危步降级成"待确认的后续步骤"，不得自动执行——否则等于用多意图能力绕过资损安全模型。另注：被标"次意图"的往往才是用户真正终点（"拟回复"是目标，"查卡哪"是手段），"主/次"命名本身误导，真正该建模的是**带依赖的小计划 + 终点交付物**。

**当前单赢家收敛的合理面**：作为安全闸它几乎肯定是故意的——"一 turn 坍缩成一个意图 = 一个风险决策"是"一 turn 一风险"的廉价实现，避免一个 turn 里读→拟动作→升级把风险面和审批模型打穿。所以 ID-04 要改的是**意图理解模型**，不是废掉"一 turn 一风险"的安全性质。

**先决问题（未确认，需数据）**：实际流量里"带真依赖的多意图查询"占比多高，未知。若绝大多数是单意图，改成轻量 planner 可能不划算，中间方案（识别到次诉求 → 记为"待确认后续"、先不自动执行）即够；若高频，才值得把输出类型整体改成计划。此项应由 eval 集/流量数据定，不拍脑袋。

**Phase 43 修复（档位 A）**：新增 bounded `TaskPlan` / `TaskStep` 契约，N=1 退化为现状；`classify_intent` 记录 `task_plan`、`executable_prefix`、`deferred_steps`、`plan_normalization`，但本 turn 的 effective route fields 始终只来自 s1；`receive_request` 每 turn 重置 `task_plan` / `deferred_steps`；`final_response` 对所有可见回复分支追加 deferred confirmation，并对 `modifier_folded:complaint_as_severity` 追加含「投诉情绪」的安全网。档位 A 修复的是「次诉求静默丢弃」：s2+ 不执行、但以待确认后续呈现给用户。

**证据**：Phase 43（`.planning/phases/43-intent-recognition-multi-intent-tier-a/`）；`src/agent/intent_policy.py`（`TaskPlan` / `build_task_plan` / `select_executable_prefix`）；`src/agent/nodes/classify_intent.py`（state/trace wiring）；`src/agent/nodes/final_response.py`（deferred/complaint decorator）；`src/agent/nodes/receive_request.py`（per-turn reset）；测试覆盖 `tests/agent/test_intent_task_plan.py`、`tests/agent/test_nodes/test_classify_intent.py`、`tests/agent/test_nodes/test_final_response.py`、`tests/agent/test_nodes/test_receive_request.py`。

**验证**：`uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q` → `66 passed`；`uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` → `1236 passed, 1 skipped`；`uv run ruff check src/agent tests/agent` → pass；`git diff --exit-code -- docs/contract-spec.md src/agent/prompts.py src/agent/schemas.py` → no diff。

**状态**：✅ 档位 A 已修复并验证。与 ID-01 部分同源（修饰型误抬），但更根本：ID-01 是"关键词覆盖 LLM"，ID-04 是"输出类型本身只能承载单意图"。本次只实现识别计划 + deferred 呈现，不实现自动依赖执行链。

**分档决策（2026-07-02 定）**：多意图落地拆成三档递进，逐档一一对应「先识别→自动依赖链→完整门控」。**当前只做档位 A**，B/C 已设计、待数据触发，不现在做。

- **档位 A（已通过 Phase 43 落地，最小安全版）**：第一层输出从「单意图」扩成 bounded `TaskPlan`（N=1 退化为现状，不破坏既有行为）+ 规范化（modifier 折叠 / fail-closed / 同意图受控合并）+ 本 turn 只处理 s1，其余步一律记为 `deferred_steps` 并在最终回复呈现。收益：消除"次诉求被静默吞掉"（ID-04 核心痛点）；不碰资损自动执行模型；**同时采集"多意图占比"数据**。执行规格见 `.planning/intent-multi-a-codex-brief.md`。
- **档位 B（待触发）**：在 A 之上打通 `read→read` / `read→draft` 的自动依赖链（依赖型且每步都在确认边界以下者一个 turn 内自动跑完；触到 `suggest_action` 及以上即停）。**触发条件**：A 上线后采到的数据显示"带依赖的多意图查询"占比达到值得投入的水平（阈值由届时 eval/流量定），或业务侧明确"查完接着拟回复/建议补偿"为高频刚需。落地要求拆成独立 plan、A 验收后再做，中间过一次 Claude 复核。
- **档位 C（待触发，暂不做）**：完整门控执行器 + resume + 终点交付追踪，任意步可中断续跑。**触发条件**：B 已稳定且出现"多步、跨 turn、需断点续跑"的真实需求。现在不碰，因需动 LangGraph interrupt/resume 泛化，风险最大。

**步数上限**：多意图计划步数 ≤ 3，超出直接澄清"你想先做哪几件"。理由：客服场景一句话塞 >3 个真任务极少见，上限小让组合可穷举测试。

**为什么先 A 不直接 B**：B = A + 自动执行链，直接做 B 不省 A，只是把"计划识别"与"资损执行器"两类 bug 捆成一个大改一次交，违反判定线且风险集中；且 B 的价值取决于依赖型多意图的真实占比，该由 A 采到的数据决定，不拍脑袋。

## ID-DESIGN 从 0 的目标态设计草案（三层解耦）🟡

> 这是针对 ID-01/02/03/04 的**重设计方向草案**。截至 2026-07-02，已落地「单意图路径」的三层契约拆分（语义理解 / 风险授权 / 置信度澄清），并通过 Phase 43 落地多意图档位 A（bounded TaskPlan + deferred 呈现）；仍未落地档位 B/C 的自动依赖执行链、DAG/resume/parallel 计划执行器，也未实现置信度校准。
>
> **2026-07-02 修正（因 ID-04）**：本草案原把第一层输出定为"单个意图"，保留了"意图识别产物是一个标签"这一错误假设。经 ID-04 讨论修正为——第一层输出应是**一个 1~N 步的有序意图计划**，多数普通查询 N=1 退化为现状。下文第一层已按此更新。

**当前架构的病根**：现状是「规则和 LLM 在同一层互相打架、风险判断混在分类节点里」。关键词能往 LLM 候选里追加意图并靠优先级覆盖（ID-01），风险映射与分类耦合（ID-03），置信度闸门信的是未校准自报值（ID-02），且输出类型只能承载单意图、多诉求被坍缩丢弃（ID-04）。这些都是「谁说了算」没有显式契约、靠 if 叠优先级涌现出来的行为。

**第一层：语义理解层（只答"用户想干什么"——产出计划而非标签）**
- LLM 输出**一个有序意图计划**：`[{intent, operation, 依赖关系, 关系类型 ∈ {依赖/修饰/独立}}]` + 每步抽到的实体 + 一个（后续可校准的）置信度，并标出哪步是**终点交付物**。N=1 时退化为现状的单意图。**不在这层塞任何关键词覆盖、风险判断、路由**。
- **关系类型消解**：修饰型（如"投诉"抬补偿风险）折进主步骤的风险档、不单独成步——直接消解 ID-01/ID-04 同源的"投诉误抬升级"；依赖型按拓扑序进计划；独立同实体不算多意图。
- 关键词规则只保留一个用途——低延迟强信号短路（如明确的"执行退款 ORD-xxx"），且其输出是与 LLM **并列的独立证据**，不混进 LLM 候选、不在这层偷偷覆盖。谁赢由下一层显式仲裁。
- **修 ID-01**：仲裁规则写成显式一条（如"关键词信号仅在 LLM 低置信或 LLM 自身也列了该次意图时才可抬升，否则以 LLM 语义为准"），可对"这个不算投诉吧"写 case 锁定。注意：这修的是"规则打架/覆盖不透明/没法测"的结构病，不替 LLM 提升语义准确率——后者靠第三层暴露。
- **修 ID-04**：计划由执行引擎**逐步过风险闸**推进——读类步骤可连做，一旦某步到 draft_action/execute/approval 档即停下，降级成"下一步建议做 X，要我继续吗"，不在同一 turn 自动跑高危步。这样既支持多意图组合，又不破坏"一 turn 一风险"安全性质。**先决问题见 ID-04：是否值得做取决于多意图+依赖的真实流量占比，需 eval 集/数据定。**

**第二层：风险与授权层（只答"当前身份/渠道下允许做到哪一步"）**
- 把意图翻译成"允许的最高动作档位"，**只认一张声明式策略表**：`(意图, 操作, 渠道, 角色) → 允许档位 + 是否要证据 + 是否要审批`。
- 把现在散在多处的 if-elif（含 `resolve_risk_tier`）全收敛成一份可单独测试、可 diff、可被 golden case 覆盖的策略数据。这层是硬地板，语义层再自信也不能突破。资损安全集中在**这一层可审计**。**对应修 ID-03**。

**第三层：置信度与澄清层（只答"够不够确定、要不要反问"）**
- 保留双阈值机制，但补两件当前缺的事：
  - **校准**：拿 golden dataset 学一条 confidence → 真实准确率的映射，让 0.85 这类数字有统计含义，而非信 LLM 自我感觉。**对应修 ID-02**。
  - **风险加权的澄清成本**：越靠近资损（执行/审批/补偿）越倾向反问而非猜；对 MOCA，多问一句的成本远低于错执行一次。

**贯穿三层的两个原则**
- 每层判定都留证据链（现有 `classification_trace` 方向正确，保留强化）：最终意图是 LLM 定的、关键词抬的、还是策略表压的，必须能回放——客服场景事后追责刚需。
- 意图空间可扩展，但操作/风险空间收敛：意图会随业务涨，但"操作类型""风险档位"两个枚举要死死控小，因为它们是安全闸门的坐标轴，轴越少组合越可穷举测试。

**已落地部分（2026-07-02）**
- 单意图三层契约已落地：`SemanticIntent` / `RiskDecision` / `ClarificationDecision`。
- ID-01 的关键词覆盖规则已显式化并测试锁定。
- ID-03 的风险层已收敛到声明式 `RISK_POLICY_TABLE` 并保留旧行为等价。
- `classification_trace` 已记录三层输出，支持回放「语义仲裁 / 风险决策 / 澄清阈值」。
- 执行规格：`.planning/intent-layering-codex-brief.md`。

**已新增落地部分（2026-07-02，Phase 43）**
- ID-04 档位 A：`TaskPlan` / `TaskStep`、s1-only effective route、s2+ `deferred_steps`、`classification_trace.plan_normalization`、final_response deferred confirmation 与 complaint safety note。

**仍未落地部分**
- ID-02：`calibrated_confidence` 只有入参占位，未做真实 calibration。
- ID-04 后续档位：自动 `read→read` / `read→draft` 依赖链、DAG/resume/parallel 计划执行器仍未做，本次明确禁止越界。

**状态**：🟡 三层契约拆分与多意图档位 A 已落地；目标态中的校准与档位 B/C 计划执行能力仍待独立立项。

---

# 3. RAG（检索 / 证据 / 上下文构建）

**范围**：检索、rerank、query rewrite、ContextBuilder、claim 验证、evidence 契约。
**已 ship**：v1.3 混合检索、v1.4 生产 ingestion+OCR、v1.5 ContextBuilder+幻觉控制、v1.6 rerank+query rewrite。

## RAG-56-03-01：RAG context routing status drift 与 partial action/risk 漏挡 ✅已修复验证

- **问题现象/根因**：`route_after_rag_context` 原本在 router 内维护一份手写 `RAG_CONTEXT_STATUSES`，虽然当时与 schema 一致，但存在后续 drift 风险；同时顶层 `rag_context_status` 缺失时会回退读取 `verified_evidence_package.status`，`no_evidence` 携带 missing business facts 时会先进入 `clarification_gate`，`partial` 允许谓词也没有覆盖 action intent、`risk_signals`、`evidence_policy.risk_level`、package stale/conflict/rejected evidence 指示，导致 unsafe evidence 或 action/risk-bound partial 可能进入 generation。
- **影响**：RAG 证据包状态与路由状态不是单一词表来源，且 `partial` 的低风险边界不够可穷举；在 Phase 56 CAGM-07 目标下，这会让 unsafe evidence 或未充分验证的 partial context 进入 recommendation generation。
- **处理状态**：✅ 已修复验证。`src/agent/routing.py` 改为从 `src.knowledge.schemas.RAG_CONTEXT_STATUSES` 派生 router 词表；缺失/未知/malformed 顶层 `rag_context_status` 和 unsafe statuses fail closed 到 `final_response`；`partial` 只允许低风险 `policy_qa` 或 answer-only fact intent，且 action/risk/unsafe evidence 指示一律 fail closed。
- **证据**：Phase 56 Plan 56-03 Task 1；`src/agent/routing.py`（`RAG_CONTEXT_STATUSES` schema 派生、`_route_after_rag_context`、`_partial_rag_context_can_generate`、`_action_bound_or_high_risk`、`_partial_rag_has_unsafe_evidence_indicator`）；`tests/agent/test_rag_context_routing.py`（schema equality、exact status set、unsafe statuses、missing/unknown/malformed status、partial action/risk/unsafe evidence matrix）；验证命令 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` 通过，55 passed。
- **剩余风险**：本条只证明 deterministic route gate 阻断 unsafe RAG status 进入 generation；stale candidate refs 不会成为 approval snapshots、risk lowering 或 action authority 的下游端到端证明仍按 Phase 56 final closeout / risk-action 测试边界处理，不在 56-03 Task 1 过度声称。

## RAG-56-03-02：claim_verify 后 proposed_action 可绕过显式 action claim allowance ✅已修复验证

- **问题现象/根因**：`route_after_claim_verify` 原本在 canonical bundle 为 `verified/continue` 后，只要 state 中存在 `proposed_action`、任意 risk signal，或任意 allowed `action_recommendation` claim result，就路由到 `assess_risk_and_approval`。这让 proposed action 在没有显式 allowed action-recommendation claim result 时也能进入风险/审批路径；反过来，allowed action claim result 即使没有 proposed action，也会自己打开风险路由。
- **影响**：claim verification bundle 的 action authority 边界不够精确，legacy verifier projection 虽未直接被读取，但 action path 的进入条件仍过宽；unsupported action claims 可能在 Phase 56 CAGM-07 语义下过早进入 Phase 57 风险节点。
- **处理状态**：✅ 已修复验证。`src/agent/routing.py` 现在按 repaired decision table 执行：有 `proposed_action` 时必须存在 `_has_verified_action_recommendation(state)` 才能进入 `assess_risk_and_approval`；没有 `proposed_action` 时，allowed action claim result 本身不创建风险路由，只有独立 non-action risk signal 才进入当前 Phase 57 风险节点；legacy `verification_route` / `verifier_status` / `verifier_reason_codes` 不能绕过 canonical bundle。
- **证据**：Phase 56 Plan 56-03 Task 2；`src/agent/routing.py`（`_route_after_claim_verify` decision table）；`tests/agent/rag_context/test_routing.py`（unsupported proposed action negative、allowed action recommendation positive、allowed action without proposed action negative、non-action risk positive、legacy verifier non-authority cases、non-action material/user-visible policy/business claims route to `claim_verify`）；验证命令 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` 通过，56 passed；acceptance script 覆盖 repaired decision table；`rg -n 'risk_gate' src/agent/routing.py tests/agent/rag_context/test_routing.py` 无命中。
- **剩余风险**：本条保持 `assess_risk_and_approval` 为 Phase 57 当前节点，不处理 `risk_gate` rename；final_response 对 legacy verifier projection 的展示/历史兼容收敛仍属 56-04。

## RAG-56-04-01：recommendation_generation active cutover、trace/API 投影与 final_response authority 收敛 ✅已修复验证

- **问题现象/根因**：Phase 56 前后存在三类会混淆当前 authority 的残留面：active graph 已切向 `recommendation_generation`，但 graph vocabulary/API/frontend/eval/docs 仍可能把历史 `generate_recommendation` 读成当前 runtime owner；`final_response` 仍可能从 legacy `rag_verification` / `verification_route` / `verifier_status` / `verifier_reason_codes` 构造当前-run 权威 route payload；当前源码图和 validation artifact 仍可能保留旧节点名或旧测试入口。
- **影响**：历史 trace 可以读，但如果投影和最终回复 authority 不分层，当前-run 缺少 `claim_verification_bundle` / `verified_evidence_package` 时可能被 legacy verifier 字段误判为安全；后续 Phase 57/58 也容易误删或误保留 compatibility surface。
- **处理状态**：✅ 已修复验证。`src/agent/graph_vocabulary.py` 将 `recommendation_generation` 标为 runtime node，并将 `generate_recommendation -> recommendation_generation` 标为 Phase 56 `compatibility_alias`，reason codes 包含 `PHASE_56_COMPATIBILITY_ALIAS`、`HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。API/SSE/frontend/eval 当前投影识别 `recommendation_generation`，历史 `generate_recommendation` 保留可读且不重写原始 implementation node。`final_response` 的 route payload authority 顺序已收敛为 `claim_verification_bundle` 优先，其次 `verified_evidence_package`；legacy verifier fields 只有在已有历史/compatibility marker 时才作为非权威 historical fallback，否则 fail closed 为 non-authoritative manual review。当前 docs/validation artifact 已同步 active `recommendation_generation`，同时明确 `assess_risk_and_approval` 仍属 Phase 57、`generate_recommendation` alias/wrapper 删除仍属 Phase 58。
- **证据**：Phase 56 Plan 56-04；commits `54290f0`（vocabulary RED tests）、`920c265`（vocabulary implementation）、`4915a38`（API/final-response RED tests）、`2abf5c7`（projection/final-response implementation）；文件 `src/agent/graph_vocabulary.py`、`src/api/routers/agent_runs.py`、`frontend/src/components/timeline/TimelineStep.tsx`、`scripts/eval_agent.py`、`src/agent/nodes/final_response.py`、`tests/agent/test_graph_vocabulary.py`、`tests/agent/test_trace.py`、`tests/test_trace_api.py`、`tests/test_agent_runs_api.py`、`tests/agent/test_nodes/test_final_response.py`、`tests/agent/test_phase22_final_response.py`、`docs/current-langgraph-architecture.md`、`.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_final_response.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_facade_integration.py -q --tb=short` → `474 passed, 1 skipped, 32 warnings`；focused Ruff → pass；Phase 56 artifact command scan → pass；`UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` → pass。
- **剩余风险**：🟡 Phase 57 仍负责 `assess_risk_and_approval -> risk_gate` active rename 与 approval/risk boundary canonicalization；🟡 Phase 58 仍负责删除 retained `generate_recommendation` wrapper/import/test/historical display compatibility 和其他 Phase 53-56 alias surfaces。本条不启用 `risk_gate`，也不删除 recommendation compatibility alias/wrapper。

---

# 4. 记忆（Memory）

**范围**：短期/会话记忆、thread summary、ContextAssembler、记忆边界与 fail-closed。
**已 ship**：v1.1 Memory Foundation V2、v1.7 短期记忆统一。
**在册探索**：Phase 999.1「评估 mem0 作为 MemoryContextService 背后可选 backend」。

## Phase 48 Plan 02 — long-term 自动来源过宽与 semantic episode 投影过宽 ✅已修复验证

**问题 / 根因**
- `long_term_memory_policy_decision(...)` 曾允许 `deterministic_tool_result`、`confirmed_business_outcome`、`approved_approval_state` 在部分情况下作为 long-term auto-approved source；这与 Phase 48 目标「published long-term 只存显式 preference / human reviewed preference」冲突。
- `LongTermMemoryWriteCandidate.memory_kind` 默认值是 `fact`，且 `LongTermMemoryService.write_memory(...)` 在 tombstone/PII 后没有在 insert 前统一拒绝非 `preference` 或 policy skip source，导致服务边界仍可写入 broad long-term rows。
- `semantic_episode.py` 曾从 `cross_case_patterns`、`similar_cases`、`strategy_hints`、`preference_candidates` 四类 semantic summary 投影 long-term candidates，容易把案例模式/策略建议沉淀为长期记忆。

**影响**
- 自动观察、工具结果或业务状态可能进入 prompt 可用长期记忆，和 policy evidence / business fact / approval/action authority 的服务边界混淆。
- 后续实现者可能把 `long_term_memories` 继续理解为 durable facts/patterns，而不是 preference-only contextual hints。

**修复**
- 新增 `PUBLISHED_LONG_TERM_SOURCE_TYPES = {"explicit_user_preference", "explicit_admin_preference", "human_reviewed"}`，`semantic_episode_candidate` 仅 `needs_review`，其他 long-term source 统一 `skip/source_type_not_allowed`。
- `LongTermMemoryWriteCandidate.memory_kind` 默认改为 `preference`；`LongTermMemoryService.write_memory(...)` 与 `supersede_memory(...)` 在 insert 前对非 preference 返回 `skipped/not_preference_memory_kind`，对 policy skip source 返回 `skipped/source_type_not_allowed`，并写 `memory_write_events`。
- `semantic_episode.py` 只投影 `preference_candidate`，`to_long_term_memory_candidate()` 固定 `memory_kind="preference"`；pattern/similar/strategy keys 不再生成 long-term candidates。

**证据**
- Phase / plan：`48-02`
- 文件：`src/memory/policy.py`、`src/memory/schemas.py`、`src/memory/long_term.py`、`src/memory/semantic_episode.py`、`tests/memory/test_memory_policy.py`、`tests/memory/test_long_term_memory_service.py`、`tests/memory/test_semantic_episode_projection.py`、`tests/memory/test_phase48_long_term_preference_alignment.py`
- 计划依据：`.planning/phases/48-narrow-long-term-explicit-preference-memory/48-02-PLAN.md`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py -q` → `43 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/policy.py src/memory/schemas.py src/memory/long_term.py src/memory/semantic_episode.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py` → pass

**剩余风险**
- ⚠️ 48-02 只完成写入 policy/service guard 与 semantic episode candidate narrowing。retrieval 过滤、review approval 发布为 `human_reviewed`、supersede/tombstone 目标语义和 API 错误映射属于 `48-04`。

## Phase 48 Plan 03 — explicit preference 写入口治理 ✅已修复验证

**问题 / 根因**
- Phase 48 目标允许 chat 中明确「记住偏好」和 admin save 两类显式写入口，但原 `MemoryWriteService.propose_candidates(...)` 只处理 session candidate 与显式 state candidates，没有 deterministic phrase gate、trusted merchant scope 解析或 chat path 的 tenant-scope 防线。
- 记忆 review API 只有审批/拒绝/删除/forget 操作，没有 admin-only direct save path；tenant-scope long-term preference 若走普通 chat/state path，会扩大影响面且缺少 admin role/scope 边界。

**影响**
- 如果用 LLM/普通陈述推断偏好，ordinary chat 可能被误写成长期记忆。
- 如果 tenant-scope preference 不限制 admin-only，商家/客服普通对话可能影响全租户 prompt context。
- admin 运营调试缺少直接保存 explicit preference 的受控入口，会诱导绕过 service/audit path。

**修复**
- 新增 `src/memory/preference_capture.py`：只匹配 deterministic explicit phrases（含 `记住这个偏好` / `以后按这个` / `保存这个偏好`），拒绝 hard-rule markers，PII sensitive/prohibited 不创建 chat candidate。
- `MemoryWriteService.propose_candidates(...)` 接收 `trusted_context`，仅从 trusted merchant scope 解析 merchant preference；chat captured preference 永不返回 tenant/user/thread/case scope；state explicit candidates 不能偷渡 `explicit_admin_preference` 或非 merchant `explicit_user_preference`。
- `memory_write` node 把 `configurable["trusted_context"]` 传入 write service。
- 新增 `POST /api/v1/memory/long-term/preferences`，要求 admin role + `memory:write` scope；admin 可保存 merchant scope 与匹配自身 tenant 的 tenant scope，候选仍经 `LongTermMemoryService.write_memory(...)` 的 PII/tombstone/source/audit gates。

**证据**
- Phase / plan：`48-03`
- 文件：`src/memory/preference_capture.py`、`src/memory/write_service.py`、`src/agent/nodes/memory_write.py`、`src/api/routers/memory.py`、`src/api/schemas/memory.py`、`src/auth/jwt.py`、`src/auth/permissions.py`、`tests/memory/test_memory_write_service.py`、`tests/agent/test_memory_write_node.py`、`tests/test_memory_review_api.py`
- 计划依据：`.planning/phases/48-narrow-long-term-explicit-preference-memory/48-03-PLAN.md`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py tests/test_memory_review_api.py tests/memory/test_long_term_memory_service.py -q` → `65 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/preference_capture.py src/memory/write_service.py src/agent/nodes/memory_write.py src/api/routers/memory.py src/api/schemas/memory.py src/auth/jwt.py src/auth/permissions.py tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py tests/test_memory_review_api.py` → pass

**剩余风险**
- ⚠️ 48-03 不完成 retrieval filter、review approval source_type 转 `human_reviewed`、API 非 preference approval 受控错误映射、supersede/tombstone lifecycle 完整验证；这些仍属于 `48-04`。

## Phase 48 Plan 04 — published long-term memory narrowed to explicit preferences ✅已修复验证

**问题 / 根因**
- Phase 48 的目标契约是 published long-term memory narrowed to explicit preferences，但在 48-04 前，prompt-facing retrieval 仍主要依赖 `review_status` / current / PII / tombstone 等通用过滤，没有把 `memory_kind="preference"` 与允许发布 source types 作为最终 retrieval predicate。
- Review approval path 会把 `semantic_episode_candidate` 候选发布为 approved row，但没有把 published source 明确转换为 `human_reviewed`；如果保留自动抽取 source，会让 prompt context 看起来仍在消费自动长期记忆。
- 旧 architecture/static tests 还保留了 pre-Phase-48 假设：current business object / `llm_candidate` long-term rows 进入 `needs_review`，而新目标是 broad durable source auto-publish removed，普通 LLM/current business source 不插入 long-term 候选。

**影响**
- 非 preference 的 fact/pattern/constraint row 或 disallowed source row 即使处于 approved/current 状态，也可能被误取进 prompt context。
- `semantic_episode_candidate` 若作为 published source 暴露，会模糊「自动抽取最多 candidate-only，人工审批后才是 human_reviewed preference」的治理边界。
- 非 preference long-term approval 如果只靠 service 抛异常而 API 不控错，review endpoint 可能退化成 500 或半发布状态。

**修复**
- `LongTermMemoryRepository.retrieve_profile_memory(...)` 现在额外要求 `LongTermMemory.memory_kind == "preference"` 且 `LongTermMemory.source_type.in_(PUBLISHED_LONG_TERM_SOURCE_TYPES)`；context service 继续依赖 repository-filtered rows，不重复实现过滤。
- `LongTermMemoryService.approve_memory(...)` 在状态更新前拒绝 `memory_kind != "preference"`，审批成功时将 `source_type` / `source_ref_json["source_type"]` / `source_identity_hash` 同步转换为 `human_reviewed`。
- Review API 对非 preference approval 返回受控 409/422（当前为 409 conflict），row 保持 `needs_review`、不转 `human_reviewed`、不进入 retrieval。
- Supersede/tombstone/no-auto-merge 行为通过回归测试锁定：相似 same-scope preference 不自动合并，删除/forget tombstone 阻止同内容/同 source identity 重写。
- 静态 Phase 48 guard 和 architecture guard 已同步到新目标：semantic episode is candidate-only，retrieval is preference-source filtered，`llm_candidate` / current business object long-term source 被 skip。

**证据**
- Phase / plan：`48-04`
- 文件：`src/memory/repository.py`、`src/memory/long_term.py`、`tests/memory/test_long_term_memory_repository.py`、`tests/memory/test_reviewed_memory_context_boundary.py`、`tests/memory/test_long_term_memory_service.py`、`tests/test_memory_review_api.py`、`tests/memory/test_phase48_long_term_preference_alignment.py`、`tests/architecture/test_memory_contract_delta.py`
- 计划依据：`.planning/phases/48-narrow-long-term-explicit-preference-memory/48-04-PLAN.md`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_repository.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_long_term_preference_alignment.py -x -q` → `32 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_long_term_memory_service.py tests/test_memory_review_api.py tests/agent/test_memory_evidence_boundary.py -x -q` → `44 passed, 3 warnings`
- Full Phase 48 gate：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py tests/architecture/test_memory_contract_delta.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py tests/memory/test_memory_write_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_write_node.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/test_memory_review_api.py -q` → `135 passed, 3 warnings`
- Focused ruff：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` → pass

**剩余风险**
- 🟡 `memory_type='long_term_fact'` 仍是 legacy storage/table identity；它不表示 fact/pattern/constraint 可作为 published long-term memory 语义。该命名妥协已在 `docs/contract-spec.md` 与 Phase 48 static guards 中锁定。
- 🟡 User-specific preference scope 仍为 post-Phase 48 defer；当前实现主路径是 merchant/team default + admin tenant explicit。

## Phase 48.1 — Memory context compatibility debt cleanup ✅已修复验证

**问题 / 根因**
- Phase 44-48 已引入新的 memory 语义层：`session_context`、`reviewed_memory_context`、`case_working_context`、`thread_case_links`、`memory_context_bundle`。但源码中仍有旧字段/旧入口作为 active reader 使用，不只是纯 projection。
- `conversation_threads.case_id` 与 `thread_case_links` 并存；前者只能表达单 case 且是 legacy string 字段，后者才是 canonical many-to-many 关系。
- `session_memory` / `session_memory_bundle` 仍被 routing、working-state、prompt session helper 读取；如果后续只改 `session_context`，这些 reader 容易漏迁。
- reviewed memory context 的实际加载仍由 `needs_long_term_memory` / `long_term_memory_retrieve` 触发，命名和 Phase 48 后的实际语义不一致。

**影响**
- 多 case 线程场景下，继续读 `conversation_threads.case_id` 会看不到完整 thread↔case 关系。
- 新旧 state 字段并存会让后续 memory prompt 注入、slot inheritance、working-state 投影修改出现「改一边漏一边」。
- `needs_long_term_memory` 名称会继续误导实现者，以为只加载 long-term preference，而不是 reviewed memory context + case memory + active CWC。

**已修复验证**
- ✅ active thread↔case reader 已迁到 `thread_case_links` / `ThreadCaseLinkRepository`：`ConversationRepository.insert_thread_summary(...)` 只在 canonical links 恰好一个时写 legacy `ConversationSummary.case_id` metadata；无 link 或多 link 不再 fallback 到 `ConversationThread.case_id`。
- ✅ routing、working-state、prompt/session helper 已改为 canonical-first：`src/agent/routing.py` 先读 `session_context`；`src/agent/working_state.py` 先读 `session_context`；`src/agent/context/session_memory_bundle.py` 先读 `session_context_bundle`，再 fallback 到 `session_memory_bundle` / service。
- ✅ reviewed-memory canonical routing hint 已新增：`needs_reviewed_memory_context` 是 canonical hint，`needs_long_term_memory` 作为 backward-compatible alias 继续可用；route 返回的 runtime node key 仍是 `long_term_memory_retrieve`。
- ✅ Phase 48.1 static guard 已新增：`tests/memory/test_phase48_1_memory_compat_alignment.py` 锁定 active reader 迁移、graph compatibility names、deferred compatibility names、no destructive rename/drop、approved pytest entrypoint。

**保留 / defer 项（防遗忘）**
- 🟡 graph 节点旧名 wrapper：`session_memory_load`、`long_term_memory_retrieve` 仍作为 runtime/trace compatibility wrapper 保留；清理需单独评估 replay/trace/eval 影响。
- 🟡 `long_term_fact` 存储/审计 identity：`MemoryTombstone`、`MemoryWriteEvent`、repository 常量仍使用该名字；当前视为 legacy storage identity，不代表 published long-term fact 语义。
- 🟡 `session_memory_enabled` / TTL / timeout 等配置名仍保留；它们属于 env/config compatibility surface，改名会影响部署配置。
- 🟡 API 路由里的 `/long-term/...` 与 schema `memory_type="long_term"` 仍保留；它们是 public/admin API surface，不能跟内部语义清理一起破坏。
- 🟡 `LegacySessionPrecedentSearchService` 仍保留为 debug-only legacy session-derived precedent 搜索；源码已注明不得支撑 planner-facing `search_case_memory`，未来可单独删除。

**证据（源码 / 测试 / planning）**
- Plan summaries：`.planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-01-SUMMARY.md`、`48.1-02-SUMMARY.md`、`48.1-03-SUMMARY.md`。
- ThreadCaseLinkRepository active reader：`src/conversation/repository.py`、`tests/conversation/test_repository.py`、`tests/memory/test_thread_case_links.py`。
- Session context active readers：`src/agent/routing.py`、`src/agent/working_state.py`、`src/agent/context/session_memory_bundle.py`、`tests/agent/test_intent_routing.py`、`tests/agent/test_working_state.py`、`tests/agent/test_session_memory_load.py`。
- Reviewed memory hint alias：`src/agent/routing.py`、`src/agent/nodes/reviewed_memory_context_retrieve.py`、`tests/agent/test_graph.py`、`tests/agent/test_memory_evidence_boundary.py`、`tests/agent/test_reviewed_memory_context_retrieve.py`。
- Static guard：`tests/memory/test_phase48_1_memory_compat_alignment.py`。
- 保留 defer surfaces：`src/agent/graph.py` / `src/agent/graph_vocabulary.py`（graph compatibility names）、`src/memory/repository.py`（`long_term_fact` storage identity）、`src/config.py`（`session_memory_enabled`）、`src/api/routers/memory.py` / `src/api/schemas/memory.py`（public long-term route/schema naming）、`src/memory/search.py`（`LegacySessionPrecedentSearchService`）。

**状态**
- ✅ 已完成代码、静态 guard、final pytest 和 Ruff 验证。最终验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_thread_case_links.py tests/conversation/test_repository.py tests/agent/test_intent_routing.py tests/agent/test_working_state.py tests/agent/test_session_memory_load.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/context/test_assembler.py tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase46_session_context_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py -q` → `1249 passed, 26 warnings`；focused Ruff → pass。
- 🟡 defer 项已记录，除非后续 phase 明确评估 replay/trace/API/config 迁移影响，否则不作为 Phase 48.1 必须交付。

## Phase 55 Plan 01 — canonical `memory_context_load` node contract 已建立，active graph 切换留给 55-02 ⚠️

**问题 / 根因**
- Phase 48.1 后 reviewed memory context 的真实语义已经是 explicit preference long-term memory + reviewed case precedent + active CWC，但 active node/import compatibility 仍以 `long_term_memory_retrieve` 命名承载。
- 旧名容易让后续实现误以为该节点只加载 long-term preference，或误把 memory/CWC 用作 policy evidence、current business fact、approval/action authority、replay truth。

**影响**
- 在 active graph 切到 canonical name 前，trace/LLM output 指标若继续只看旧 key，Phase 55/56/57 后续 cutover 容易发生节点 ownership 与 authority label 漂移。
- memory usage labels 若不显式 finite + `contextual_only`，后续 recommendation/RAG/risk 阶段可能误读 memory 为证据或事实来源。

**已修复验证**
- ✅ 新增 `src/agent/nodes/memory_context_load.py`：canonical node 委托 `reviewed_memory_context_retrieve(...)`，保留既有 memory service / repository / CWC lifecycle 注入 seam，同时写 `llm_outputs["memory_context_load"]`。
- ✅ canonical metrics 只包含 finite `usage_labels` 与 `authority_class == "contextual_only"`，并把 direct canonical trace/node_error identity 从 `reviewed_memory_context_retrieve` 映射为 `memory_context_load`。
- ✅ `src/agent/nodes/long_term_memory_retrieve.py` 改为 compatibility wrapper：调用 canonical `memory_context_load(...)` 后只在 wrapper path 增补 legacy `llm_outputs["long_term_memory_retrieve"]` metrics。
- ✅ `tests/agent/test_memory_context_load.py` 覆盖 direct canonical metrics、finite labels、trace identity、missing trusted context skip、service error unavailable、wrapper compatibility。
- ✅ `tests/agent/test_memory_evidence_boundary.py` 新增 canonical `memory_context_load` metrics boundary，证明 metrics/labels 不能解析为 `EvidenceRefV1`、`BusinessFactRefV1`、approval/action DTO 或 `ReplayEventV3`。

**证据**
- Phase 55 Plan 01；commits `e7dd979`（RED tests）与 `87c6aa6`（canonical node implementation）。
- 文件：`src/agent/nodes/memory_context_load.py`、`src/agent/nodes/long_term_memory_retrieve.py`、`tests/agent/test_memory_context_load.py`、`tests/agent/test_memory_evidence_boundary.py`。
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_context_load.py tests/agent/test_reviewed_memory_context_retrieve.py -q --tb=short` → `22 passed`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py -q --tb=short` → `12 passed`；Task 2 full gate 以 `55-01-SUMMARY.md` 为准。

**剩余风险**
- ⚠️ active graph/router 仍由 Plan 55-02 切到 `memory_context_load`；本条只关闭 canonical node contract，不声称 active graph 已完成 cutover。
- 🟡 `long_term_memory_retrieve` wrapper 与 legacy metric key 暂保留为 Phase 58 删除项，避免破坏历史 import/test/trace compatibility。

## Phase 55 Plan 03 — `memory_context_load` runtime vocabulary/API/docs closeout ✅已修复验证

**问题 / 根因**
- Phase 55-02 已把 active graph/router 切到 `memory_context_load`，但 vocabulary、trace/API/SSE projection、当前源码架构图和债务台账如果继续把 `long_term_memory_retrieve` 或 `reviewed_memory_context_retrieve` 读成 runtime owner，会让历史 trace/import/test compatibility 与当前 runtime authority 混在一起。
- `reviewed_memory_context_retrieve` 是 helper/service test surface，不应在 Phase 55 后成为第二个 runtime graph owner。

**影响**
- Agent run timeline、SSE event 和 current-source docs 可能误导后续 Phase 56/57/58，把 `long_term_memory_retrieve` 当作仍 active 的 registered node。
- Phase 58 删除 compatibility alias 时若缺少 reason/delete metadata，容易漏删 wrapper/import/test/historical trace surface，或误删仍需保留的 memory storage/API/config 名称。

**已修复验证**
- ✅ `src/agent/graph_vocabulary.py` 将 `memory_context_load` 标为 runtime node；`long_term_memory_retrieve` 与 `reviewed_memory_context_retrieve` 标为 `compatibility_alias`，reason codes 包含 `PHASE_55_COMPATIBILITY_ALIAS`、`HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。
- ✅ `src/api/routers/agent_runs.py` 增加 `memory_context_load` SSE label；trace/API/SSE tests 覆盖当前 runtime `memory_context_load`、历史 `long_term_memory_retrieve -> memory_context_load`、helper `reviewed_memory_context_retrieve -> memory_context_load`，并保持 persisted implementation name 不被重写。
- ✅ `docs/current-langgraph-architecture.md` 已更新为当前源码事实：active path 为 `slot_resolution_gate -> route_after_slot_resolution -> memory_context_load -> investigate`；active node set 不再包含 `long_term_memory_retrieve`。
- ✅ Phase 56/57 scope 未提前实现：active graph 仍保留 `generate_recommendation` 与 `assess_risk_and_approval` legacy rows；Phase 58 final no-debt cleanup 未执行。
- ✅ 本次没有破坏性 rename/drop memory storage/API/config：`long_term_fact` storage identity、public memory API/schema/config compatibility 不在 Phase 55-03 范围内改名或删除。

**保留兼容面**
- 🟡 `src/agent/nodes/long_term_memory_retrieve.py` wrapper、legacy `llm_outputs["long_term_memory_retrieve"]` direct wrapper metrics、historical trace/API rows 暂保留到 Phase 58。
- 🟡 `reviewed_memory_context_retrieve` helper/direct test surface 暂保留为 implementation compatibility；Phase 58 可删除 alias 或重分类为 internal-only helper。

**证据**
- Phase 55 Plan 03；commits `92a760e`（vocabulary RED tests）、`2872047`（runtime vocabulary implementation）、`46d1400`（trace/API RED tests）、`5b57289`（SSE projection label）。
- 文件：`src/agent/graph_vocabulary.py`、`src/api/routers/agent_runs.py`、`tests/agent/test_graph_vocabulary.py`、`tests/architecture/test_phase32_static_contract.py`、`tests/architecture/test_memory_contract_delta.py`、`tests/agent/test_trace.py`、`tests/test_trace_api.py`、`tests/test_agent_runs_api.py`、`docs/current-langgraph-architecture.md`。
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase32_static_contract.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_memory_context_load.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_phase46_session_context_alignment.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_phase48_1_memory_compat_alignment.py -q --tb=short` → `1455 passed, 2 skipped, 31 warnings`。
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/memory tests/architecture tests/agent tests/memory` → pass。
- 验证：literal-aware active graph/vocabulary scan → `55-03 active graph/vocabulary scan OK`。计划内原始 scan 因 `START` / `END` AST endpoint 形状失败，已记录到 `.planning/LOCAL-VALIDATION-ISSUES.md`。

**剩余风险**
- 🟡 Phase 56 仍负责 `generate_recommendation -> recommendation_generation` active cutover 和 evidence/claim 状态收敛；本条不声称已完成。
- 🟡 Phase 57 仍负责 `assess_risk_and_approval -> risk_gate` / approval boundary canonicalization；本条不声称已完成。
- 🟡 Phase 58 仍负责删除 Phase 55 retained aliases/wrappers/historical display compatibility，并执行 final no-debt cleanup；本条只把 delete metadata 和验证入口固定下来。

## Phase 55 Code Review WR-01 — canonical `memory_context_load` helper metrics 泄漏修复 ✅已修复验证

**问题 / 根因**
- `memory_context_load()` 委托 `reviewed_memory_context_retrieve()` 后只剔除了 `llm_outputs["long_term_memory_retrieve"]`，没有剔除 helper 写入的 `llm_outputs["reviewed_memory_context_retrieve"]`。
- Phase 55 后 active canonical runtime owner 应只写 `llm_outputs["memory_context_load"]`；`reviewed_memory_context_retrieve` 只是 helper/compatibility surface，不应在 direct canonical run 的 active metrics 中继续出现。

**影响**
- active graph trace/API 可能同时暴露 canonical metrics key 与 helper metrics key，让后续 Phase 56/57/58 误判 runtime ownership。
- direct canonical tests 只检查旧 wrapper key 缺失，无法防住 helper key 回流。

**已修复验证**
- ✅ `_without_legacy_metrics()` 同时剔除 `long_term_memory_retrieve` 与 `reviewed_memory_context_retrieve`，并保留其他上游 `llm_outputs`。
- ✅ `tests/agent/test_memory_context_load.py` 覆盖 direct canonical call 会剔除 result-side 与 stale state-side helper/legacy metrics，同时保留 `memory_context_load` canonical metrics。
- ✅ `tests/agent/test_graph.py` active graph smoke tests 增补 helper metrics key 不出现在 final `llm_outputs` 的断言。

**证据**
- Phase 55 code review WR-01；文件：`src/agent/nodes/memory_context_load.py`、`tests/agent/test_memory_context_load.py`、`tests/agent/test_graph.py`。
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_context_load.py tests/agent/test_graph.py::test_memory_context_load_reviewed_retrieval_safe_empty_when_no_reviewed_rows tests/agent/test_graph.py::test_canonical_reviewed_memory_hint_reaches_memory_context_load tests/agent/test_graph.py::test_memory_context_load_reviewed_retrieval_safe_empty_when_unavailable tests/agent/test_graph.py::test_memory_context_load_reviewed_snippets_flow_into_graph_state -q --tb=short` → `9 passed, 5 warnings`。
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/memory_context_load.py tests/agent/test_memory_context_load.py tests/agent/test_graph.py` → pass。

**剩余风险**
- 🟡 `reviewed_memory_context_retrieve` helper 和 `long_term_memory_retrieve` wrapper 仍按 Phase 58 范围保留；本修复只限制 direct canonical / active graph metrics projection。

## Phase 48 Review CR-01 — state-origin 记忆候选身份与发布边界加固 ✅已修复验证

**问题 / 根因**
- `MemoryWriteService.propose_candidates(...)` 曾对 `state["memory_write_candidates"]` 只做 Pydantic 形状校验和有限 source-type 过滤，没有绑定回当前 state 的 `tenant_id` / `current_run_id`，也没有要求 state-origin long-term candidate 只能是 review-required merchant scope。

**影响**
- 上游 state writer 可能把跨租户、错 run、tenant-scope、`human_reviewed` / `explicit_admin_preference` / `explicit_user_preference` 等已发布来源候选偷渡到写入 side effect，绕过显式 preference / review 路径治理。

**修复**
- state-origin candidate 现在必须匹配当前 tenant/run；source_ref 若声明 run/source type 也必须与 candidate/current run 一致。
- state-origin long-term candidate fail-closed：只允许 `REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES` 中的 merchant-scope candidate，并要求 `trusted_context.merchant_scope` 覆盖该 merchant；显式 user/admin/human-reviewed 发布来源仍只能由 deterministic helper / admin API / review path 创建。

**证据**
- Phase / review：`48-REVIEW.md` CR-01
- 文件：`src/memory/write_service.py`、`tests/memory/test_memory_write_service.py`

**状态**：✅ 已修复并通过 focused verification；剩余风险是 case-memory state candidate 仍按既有 case policy 处理，本次 review finding 的 long-term explicit preference 边界已收紧。

## Phase 48 Review WR-01 — hard-rule 文本禁止发布为长期偏好 ✅已修复验证

**问题 / 根因**
- explicit user/admin 入口会调用 `validate_soft_preference_text(...)`，但 `LongTermMemoryService.write_memory(...)` 与 review approval 边界此前没有复用该校验。
- 结果是 `semantic_episode_candidate` 或 service-level direct write 可以携带「must refund below 10 yuan」这类硬规则文本进入 `needs_review` 或直接 `human_reviewed` 发布。

**影响**
- prompt-facing long-term preference memory 可能混入政策规则、阈值或必须执行行为，破坏「长期记忆只承载软偏好/contextual hints，不提供 authority」的 Phase 48 边界。

**修复**
- long-term write / supersede 在 insert 前对 preference content 调用 `validate_soft_preference_text(...)`；hard-rule text 统一 skip 并写 `reason_code="hard_rule_not_preference"` / `blocked_by=["preference_text"]`。
- review approval 在 source 转 `human_reviewed` 前拒绝 hard-rule pending row，旧数据保持 `needs_review` 且不可进入 retrieval。

**证据**
- Phase / review：`48-REVIEW.md` WR-01
- 文件：`src/memory/long_term.py`、`tests/memory/test_long_term_memory_service.py`

**状态**：✅ 已修复并通过 focused verification；剩余风险是 hard-rule marker 集合仍是 deterministic denylist，未来若扩展政策规则表达需要独立更新 preference capture 校验。

## Phase 48 Re-review CR-01 — memory review API fail-closed 到 admin-only ✅已修复验证

**问题 / 根因**
- `src/api/routers/memory.py` 的 memory review endpoints 原本允许 `manager` 角色；这些 endpoint 按 tenant 列出和审批 / 拒绝 / 删除 / forget pending long-term 与 case memory，没有 merchant-scope 授权检查。

**影响**
- merchant-bound manager 若持有 `approvals:review` scope，可能在同一 tenant 内操作其他 merchant 的 pending memory，破坏 reviewed memory 的可信发布边界。

**修复**
- Phase 48 先 fail-closed：memory review router 的 reviewer role allowlist 收窄为 `admin`。manager 的通用 approval scope 不改，避免影响非 memory 的 approvals API。
- API 回归测试改为 admin happy path，并显式覆盖同商家 manager、跨商家 manager、support 即使带 `approvals:review` 也被 memory review API 拒绝。

**证据**
- Phase / review：`48-REVIEW.md` CR-01（2026-07-04 re-review）
- 文件：`src/api/routers/memory.py`、`tests/test_memory_review_api.py`

**状态**：✅ 已修复并通过 focused verification；剩余风险是未来若要恢复 merchant-scoped manager review，需要独立实现逐 row merchant/case identity 授权。

## Phase 48 Re-review WR-01 — state-origin case memory provenance fail-closed ✅已修复验证

**问题 / 根因**
- `MemoryWriteService.propose_candidates(...)` 已对 state-origin long-term candidate 做 trusted source/scope gate，但 case-memory candidate 只校验 tenant/run/source_ref identity；因此 state payload 可自称 `human_reviewed` 或 `explicit_admin_preference`，触发 case policy auto-publish。

**影响**
- 普通 state-origin case candidate 可能绕过 review-required generator path，把未审核 case precedent 写成已审核 / admin provenance，污染 reviewed case-memory store。

**修复**
- 新增 case-specific state gate：state-origin case candidate 只能使用 `REVIEW_REQUIRED_CASE_SOURCE_TYPES`。`human_reviewed` / `explicit_admin_preference` 仍保留给 explicit review/admin service path，但不再接受来自 graph state。
- merchant scope candidate 必须落在 trusted merchant scope 内；case scope candidate 当前只接受带 matching refund_case source_ref 的 `closed_case_cwc_candidate`。
- 回归测试覆盖 human-reviewed/admin 自声明、缺失或不匹配 case source_ref、跨 merchant scope 均被过滤，同时保留 direct service path 对 reviewed/admin provenance 的支持。

**证据**
- Phase / review：`48-REVIEW.md` WR-01（2026-07-04 re-review）
- 文件：`src/memory/write_service.py`、`tests/memory/test_memory_write_service.py`、`tests/agent/test_memory_write_node.py`

**状态**：✅ 已修复并通过 focused verification；剩余风险是如果未来需要从 state 接受更多 case-scope generator sources，必须先补 resolved case identity 授权，而不是放宽到所有 case source。

## Phase 48 Re-review WR-01 follow-up — merchant-scope closed-case source provenance fail-closed ✅已修复验证

**问题 / 根因**
- 上一轮 `MemoryWriteService.propose_candidates(...)` state-origin case gate 已收紧 case-scope `closed_case_cwc_candidate`，但 merchant-scope 分支只要求 `trusted_context.merchant_scope` 覆盖目标 merchant。
- 因此 `scope_type="merchant"`、`source_type="closed_case_cwc_candidate"` 的 state candidate 即使缺失 `source_ref`，或缺少 `refund_case` source identity / close event，也会进入 pending review。

**影响**
- pending case-memory candidate 可能只留下 `source_type` 而没有 normalized closed-case provenance。虽然仍需 reviewer approval，但 review/audit boundary 失去源退款 case 与 close event 依据。

**修复**
- `closed_case_cwc_candidate` 现在无论 merchant scope 还是 case scope，都必须先通过完整 source identity 校验：`source_ref.business_object_type == "refund_case"`、`business_object_id` 非空、`event_id` 非空。
- merchant-scope 仍保留 trusted merchant-scope 授权，但它只是 source identity 校验之后的追加条件；case-scope 继续要求 `source_ref.business_object_id == scope_id`。
- 回归测试覆盖 merchant-scope 完整 source_ref 可接受，以及缺失 source_ref、缺 event_id、缺 business_object_id、错误 business_object_type 均被过滤。

**证据**
- Phase / review：`48-REVIEW.md` WR-01（2026-07-04 re-review follow-up）
- 文件：`src/memory/write_service.py`、`tests/memory/test_memory_write_service.py`
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/write_service.py', 'tests/memory/test_memory_write_service.py']]"` → pass
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/write_service.py tests/memory/test_memory_write_service.py` → pass
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py -q` → `35 passed, 1 warning`

**状态**：✅ 已修复并通过 focused verification；剩余风险是未来若要允许 state-origin 非 closed-case case-memory generator source，需要先定义独立 source identity / scope authorization 规则。

## Phase 44 Wave 2 — Case Working Context 身份解析与版本化仓库 ✅⚠️

**问题 / 根因**
- 现有记忆层缺少「当前退款 case 的工作上下文」服务边界；业务 / tool 层传入的是 `refund_case_no` 字符串，`conversation_threads.case_id` 又是无 FK 的自由字符串，如果直接作为 CWC scope key 会把上下文绑定到不稳定身份。
- Wave 1 已建 `case_working_contexts` / `case_working_context_revisions` 表；若没有 resolver + repository，版本化表仍只是空机器：无法稳定按 `(tenant_id, refund_cases.id)` 读取当前上下文，也无法在更新时保留旧版本快照。

**修复**
- 新增 `resolve_case_id(...)`：空输入不查库、UUID 字符串按 `refund_cases.id + tenant_id` 查、普通字符串复用 `RefundRepository.get_by_case_no(...)`，跨租户 case_no 返回 `not_found`，永不把原始字符串当 scope key。
- 新增 CWC Pydantic schema：`claims[]` 与 `verified_facts[]` 是不同类型，claim 必带 `verified + source_ref`，verified fact 必带 `source_ref + observed_at`；policy 只存 `doc_id/chunk_id/version` 引用。
- 新增 `CaseWorkingContextRepository`：按 `(tenant_id, case_id)` 读 active row；写入前拿 PostgreSQL advisory lock；`expected_version` 不匹配返回 `conflict`；更新前把当前内容写入 `case_working_context_revisions`，再 bump active row `version` 并固定 `authority_class='contextual_only'`。

**证据**
- Phase / plan：`44-02`
- Commits：`bfa4a5b`（resolver）、`31fccbc`（schema）、`52dd19e`（repository），TDD red commits `6d1954e` / `94c05f0` / `9c7bab0`
- 文件：`src/memory/case_identity.py`、`src/memory/case_working_context_schemas.py`、`src/memory/case_working_context.py`、`tests/memory/test_case_identity.py`、`tests/memory/test_case_working_context_repo.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py -x -q` → `6 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_repo.py -x -q -k schema` → `4 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_repo.py -x -q` → `10 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py -q` → `16 passed`

**剩余风险**
- ⚠️ Wave 2 只完成 resolver / schema / repository。thread↔case link 生命周期、CWC write service + audit event + isolated session 属于 Wave 3；contract-spec §13 对齐与最终 sweep 属于 Wave 4，当前不越界实现。

## Phase 44 Wave 3 — thread↔case 写生命周期与 CWC audited write service ✅⚠️

**问题 / 根因**
- Wave 1 已建 `thread_case_links`，但历史 `append_message()` 不携带已解析 case identity，若没有显式写入口，关联表会继续保持空机器。
- Wave 2 已有 `CaseWorkingContextRepository`，但还没有统一服务层负责 provenance、PII gate、`memory_write_events(memory_type='case_working_context')` 审计与 isolated child session；直接从业务事务写 CWC 会放大 caller transaction poisoning 风险。

**修复**
- 新增 `ThreadCaseLinkRepository`：写入前校验 `link_source in {'run_auto','staff_manual','import'}`；按 `(tenant_id, conversation_thread_id, case_id, deleted_at IS NULL)` 先查 active row 并幂等返回；提供 thread→cases 与 case→threads 双向 active 读取。
- 新增 `ConversationRepository.link_case(...)` 作为显式 B3 linkage point；`append_message()` 不自动写 link，避免未解析 case 时静默写 null / 错 identity。为避免 conversation ↔ memory package 初始化循环，`ThreadCaseLinkRepository` 在方法体内延迟 import。
- 新增 `CaseWorkingContextService.write_case_working_context(...)`：在打开 isolated child session 前校验 tenant/case/source_ref/run_id；PII `sensitive/prohibited` 写入只发 `write_blocked/pii_blocked` audit event、不写 CWC row；成功/版本冲突分别发 `write/eligible` 与 `skip/version_conflict` event；candidate_hash 绑定 tenant/case/content/source identity；服务通过 `run_memory_side_effect_in_isolated_session` 写入，child failure 不污染 caller transaction。

**证据**
- Phase / plan：`44-03`
- Commits：`83820ea`（thread-case repository）、`53efe92`（explicit link_case）、`db3bbcc`（CWC service），TDD red commits `5d93324` / `994cadd`
- 文件：`src/memory/thread_case_links.py`、`src/conversation/repository.py`、`src/memory/case_working_context_service.py`、`tests/memory/test_thread_case_links.py`、`tests/memory/test_case_working_context_service.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_thread_case_links.py -x -q` → `4 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/conversation/test_repository.py -q` → `5 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_service.py -x -q` → `9 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py -q` → `13 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/thread_case_links.py src/conversation/repository.py src/memory/case_working_context_service.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py` → pass

**剩余风险**
- ⚠️ 本 phase 只交付 callable write surfaces：真实 run/staff call site wiring 明确 defer 到 `Phase 45 memory lifecycle wiring`（`DEFER-LINK-CASE-CALLER`、`DEFER-CWC-READ-ACTIVE-CALLER`）。Wave 4 仍需做 contract-spec §13 对齐和最终 no-redline sweep；本轮未改 DDL、未迁移 26 个 legacy `case_id` readers。

## Phase 45 Plan 01 — CWC lifecycle contextual refs 与 adapter foundation ✅⚠️

**问题 / 根因**
- Phase 44 已提供 CWC resolver / repository / audited write service，但 graph/API/finalizer caller 若直接拼状态，容易把 CWC 与 reviewed `case_memory`、候选槽位、session memory 或业务事实 authority 混在一起。
- 现有 `MemoryContextBundle` 没有显式 CWC lifecycle status/ref 字段；后续 active read / link / terminal write 无法稳定表达 `skipped/error/resolve/link/read/write` 原因。

**修复**
- 新增 `CaseWorkingContextRef` 与 `CaseWorkingContextLifecycleStatusV1`，固定 `authority_class='contextual_only'`，并把 `case_working_context` / `case_working_context_status_ref` 作为 `MemoryContextBundle` 的 additive optional fields。
- 新增 `CaseWorkingContextLifecycleAdapter` foundation：trusted case ref 只从 `active_slots.refund_case_id`、`extracted_slots.refund_case_id`，以及显式启用时的 `business_context.refund_case` 三个字段序列提取；忽略 `candidate_slots`、`session_memory`、`case_memory`、`memory_context`。
- `build_active_cwc_payload(...)` 只从 persisted CWC row 字段构造 prompt-safe payload：内容经 `hydrate_content(row)`，ref 来自 `tenant_id/case_id/id/version/updated_by_run_id/source_ref_json`。

**证据**
- Phase / plan：`45-01`
- Commits：`b5794a8`（context refs）、`7e5c757`（adapter foundation），TDD red commits `9fa41d2` / `571b5f3`
- 文件：`src/memory/context_refs.py`、`src/memory/case_working_context_lifecycle.py`、`tests/memory/test_context_refs.py`、`tests/agent/test_case_working_context_lifecycle.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py -q` → `24 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/context_refs.py src/memory/case_working_context_lifecycle.py tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py` → pass

**剩余风险**
- ⚠️ 本 plan 只交付 graph/API-neutral adapter foundation；active CWC read + `run_auto` thread-case link wiring 属于 `45-02`，terminal finalizer writeback / conflict semantics 属于 `45-03`，contract/spec/red-line final sweep 属于 `45-04`。

## Phase 45 Plan 02 — memory_context_load active CWC 读取与 run_auto link wiring ✅⚠️

**问题 / 根因**
- Phase 45 Plan 01 只有 CWC lifecycle adapter foundation；真实 graph read seam 仍不会调用 CWC active read，也不会把当前 thread 与已解析 `refund_cases.id` 写入 `thread_case_links`。
- 如果 read seam 直接在共享 graph session 内调用 link writer 且失败后手动 `rollback()`，会污染 / 回滚同一个 graph session；如果从 `case_memories` 或 untrusted state 猜 case，则会把 reviewed precedent 误当 active case state。

**修复**
- 在 `AgentState` 和 `receive_request` 增加并 reset 两个 additive 字段：`case_working_context`、`case_working_context_lifecycle_status`，不改 `case_memory` / `long_term_memory`。
- 新增 `CaseWorkingContextLifecycleAdapter.link_and_load_active(...)`：只从 trusted case ref 解析 canonical case；无 case / unresolved case 显式 skip；resolved case 用 `ConversationRepository.link_case(..., link_source="run_auto", linked_by_run_id=run_id)` 写 link；link 调用包在 `async with session.begin_nested():` 中，失败返回 `link_failed` 且不对共享 session 调 `rollback()`；随后通过 keyword-only `read_active(tenant_id=..., case_id=...)` 读取 active CWC。
- 在 `reviewed_memory_context_retrieve` / `memory_context_load` seam 调用 CWC adapter：tenant/user/thread/run 只从 `configurable["trusted_context"]` 解析；缺失 trusted context 返回 `missing_trusted_context`；adapter error 追加 `CASE_WORKING_CONTEXT_LOAD_FAILED` node error，但保留 reviewed memory fallback / available result。

**证据**
- Phase / plan：`45-02`
- Commits：`82b623f`（state/reset fields）、`c442591`（link_and_load_active）、`a944a04`（memory seam wiring），TDD red commits `0c41b84` / `a19076d` / `4d26bb8`
- 文件：`src/agent/state.py`、`src/agent/nodes/receive_request.py`、`src/memory/case_working_context_lifecycle.py`、`src/agent/nodes/reviewed_memory_context_retrieve.py`、`tests/agent/test_nodes/test_receive_request.py`、`tests/agent/test_case_working_context_lifecycle.py`、`tests/agent/test_reviewed_memory_context_retrieve.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_case_working_context_lifecycle.py -q` → `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_case_links.py -x -q` → `20 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_working_context_lifecycle.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_case_working_context_lifecycle.py` → pass

**剩余风险**
- ⚠️ 本 plan 只完成 active read + link wiring。terminal finalizer CWC writeback、expected_version conflict / PII block / finalizer failure preservation 属于 `45-03`；contract-spec / red-line final sweep 属于 `45-04`。

## Phase 45 Plan 03 — terminal finalizer CWC writeback 与失败隔离 ✅⚠️

**问题 / 根因**
- Phase 45 Plan 02 已把 active CWC 读取和 `run_auto` thread-case link 接到 `memory_context_load` seam，但 completed terminal run 仍不会把新的 prompt-safe run state 写回 CWC，MEM-01 的「run-completion auto-update」defer 尚未关闭。
- 如果把 CWC 写入混进 assistant message / thread summary 事务，PII block、version conflict 或 CWC service failure 可能回滚用户可见的 final response artifact，破坏 Phase 24/44 的 memory side-effect isolation 边界。

**修复**
- 新增 deterministic terminal projection：`TerminalProjectionResult` + `project_terminal_write_candidate(...)`。projection 只使用 `user_query`、`active_slots.issue_type` / `primary_intent`、prompt-safe tool summaries、policy ref identifiers、recommendation/proposed action identifier字段；显式排除 raw tool data / raw payload / policy body text / replay/debug blob；source_ref 固定为 `source_type="run_auto_terminal"` 并绑定 `run_id/agent_run_id/refund_case`。
- `CaseWorkingContextLifecycleAdapter.write_after_terminal_success(...)` 在 terminal writeback 前重新用 trusted case ref 解析 canonical `refund_cases.id`，对 `skipped_no_case` / `skipped_unresolved_case` fail closed；对同一 thread/case/run 的 read-seam `run_auto` link 返回 `deduped`，读取 active row `version` 作为 `expected_version`，再通过 `CaseWorkingContextService.write_case_working_context(...)` 写入，保留 audited service 的 PII block / conflict / isolated session 语义。
- `finalize_completed_agent_run_memory(...)` 在 assistant message + thread summary commit 和原有 `memory_write` side effect 之后调用 CWC lifecycle adapter；`AgentRunMemoryFinalizeResult` 新增 `case_working_context_status/result`，trace metrics 新增 `case_working_context_status/reason_code/memory_id/version`，且 `finalizer.status` 仍只由原 `memory_write_status` 推导。

**证据**
- Phase / plan：`45-03`
- Commits：`afc6565`（terminal projection）、`274614b`（lifecycle write_after_terminal_success）、`9ec3415`（finalizer integration），TDD red commits `661a357` / `d4feed2` / `aeafdcf`
- 文件：`src/memory/case_working_context_lifecycle.py`、`src/api/services/agent_run_memory.py`、`tests/agent/test_case_working_context_lifecycle.py`、`tests/test_agent_runs_api.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_memory_write_rollback_does_not_remove_terminal_rows tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status -q` → `34 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_blocked_preserves_terminal_rows tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_conflict_preserves_terminal_rows -q` → `2 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_case_working_context_service.py -x -q` → `43 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_working_context_lifecycle.py src/api/services/agent_run_memory.py tests/agent/test_case_working_context_lifecycle.py tests/test_agent_runs_api.py` → pass

**剩余风险**
- ⚠️ 本 plan 完成 terminal writeback / skip / blocked / conflict / error preservation，但 `docs/contract-spec.md` 对 Phase 45 最终状态、红线 no-diff sweep、跨计划验收汇总仍属于 `45-04`。

## Phase 45 Plan 04 — CWC lifecycle contract / red-line / validation closure ✅已修复验证

**问题 / 根因**
- Phase 44 把 active CWC read、thread-case `run_auto` caller、terminal CWC writeback 明确 defer 到 Phase 45；45-01/02/03 已完成代码 wiring，但若 `docs/contract-spec.md`、验证计划和记忆重设计台账不对齐，后续 phase 可能继续把目标态 spec 当成未实现事实，或把 CWC 误提升为 reviewed case memory / long-term memory / policy evidence / approval/action authority。
- Phase 45 横跨 graph seam、finalizer、CWC service 与 planning artifacts，必须用静态红线锁住：不引入 ReAct loop，不让 `investigate` 写 graph-global `active_slots`，不从 `case_memories` 回填 active CWC，不使用 LLM summarizer，不改 `case_memories` / `long_term_memories` / `conversation_threads.case_id`。

**修复**
- `docs/contract-spec.md` 对齐 Phase 45 实现：`memory_context_load` 写入 `case_working_context` / `case_working_context_lifecycle_status`；AgentState registry 记录 writer 为 `memory_context_load / CaseWorkingContextLifecycleAdapter`；§13.4a 记录 active CWC read、`link_source="run_auto"`、terminal deterministic writeback、PII/ref-only projection、`expected_version` conflict skip 和 finalizer failure isolation；§13.5 记录 `case_working_context` `memory_write_events` 只是 audit records。
- 新增 `tests/memory/test_phase45_contract_alignment.py`，覆盖 contract text、CWC contextual-only authority、no LLM/summarizer projection、no `case_memories` fallback、AST 检查 `investigate` 不返回或赋值 `active_slots`、graph 不添加 ReAct / `memory_write` edge、legacy table/column retention、Phase 45 PLAN/VALIDATION 不含未批准 pytest 命令。
- `.planning/MEMORY-REDESIGN-DECISIONS.md` 增加 Phase 45 completion trace，明确 closed defers：active CWC read、thread-case `run_auto` link caller、terminal CWC writeback；DEFER-1/2/3 仍保持 future phase，不被标成已实现。
- `45-VALIDATION.md` 在最终 pytest / ruff / alembic 全部通过后才设置 `nyquist_compliant: true` 和 `wave_0_complete: true`。

**证据**
- Phase / plan：`45-04`
- Commits：`75d8367`（contract RED tests）、`dea1ec2`（contract-spec alignment）、`2eae073`（red-line static sweeps）
- 文件：`docs/contract-spec.md`、`tests/memory/test_phase45_contract_alignment.py`、`.planning/MEMORY-REDESIGN-DECISIONS.md`、`.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-VALIDATION.md`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` → `11 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_identity.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/test_agent_runs_api.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_phase45_contract_alignment.py -q` → `172 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/context_refs.py src/memory/case_working_context_lifecycle.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py src/api/services/agent_run_memory.py tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/test_agent_runs_api.py tests/memory/test_phase45_contract_alignment.py` → pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` → `022_case_working_context (head)`

**剩余风险**
- ✅ Phase 45 lifecycle wiring 已完成并验证。剩余 memory redesign ideas 不属于本 phase：DEFER-1 session context repositioning、DEFER-2 case precedent / closed-case candidate generation、DEFER-3 narrow long-term explicit-preference memory。它们继续作为 future phases，不构成 Phase 45 未完成项。

## Phase 45 Code Review Fix — terminal thread-case link 状态准确性 ✅已修复验证

**问题 / 根因**
- Phase 45 code review WR-01 确认：terminal CWC writeback 在写 `run_auto` link 前只用 `link_source="run_auto"` 和 `linked_by_run_id=run_id` 检测既有 link；但真实幂等边界是 active `(tenant_id, conversation_thread_id, case_id)`，staff/import 或同线程其他 run 已经建立 active link 时，状态可能误报为 `linked`。

**影响**
- 不会产生重复 row，但 lifecycle status / trace metrics 会把 repository dedupe 或既有 active link 误记为新建 link。

**修复**
- `CaseWorkingContextLifecycleAdapter._link_terminal_thread_case(...)` 改为先检测任意 active thread-case link；命中时直接返回 `deduped`，不再尝试 terminal `link_case`。
- 新增 focused regression：预置 `staff_manual` active link，并用会在 `link_case` 被调用时抛错的 repository subclass 验证 terminal writeback 在既有 active link 场景返回 `deduped` 且不会发起新 link attempt。

**证据**
- Phase / review：`45-REVIEW.md` WR-01
- 文件：`src/memory/case_working_context_lifecycle.py`、`tests/agent/test_case_working_context_lifecycle.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/memory/case_working_context_lifecycle.py', 'tests/agent/test_case_working_context_lifecycle.py']]"` → pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py::test_write_after_terminal_success_dedupes_read_seam_run_auto_link tests/agent/test_case_working_context_lifecycle.py::test_write_after_terminal_success_dedupes_any_existing_active_link_before_terminal_attempt -q` → `2 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_working_context_lifecycle.py tests/agent/test_case_working_context_lifecycle.py` → pass

**剩余风险**
- ✅ 已用 focused integration test 覆盖 active link pre-check 与 status 输出；未运行全量测试，留给后续 verifier。

## Phase 46 Plan 03 — SessionMemoryBundle policy/business ref 提示字段收窄 ✅已修复验证

**问题 / 根因**
- Phase 46 行为测试新增 `test_session_memory_bundle_serializes_policy_refs_as_hints_only` 后发现：`SessionMemoryBundleService._tool_summary_views(...)` 会把 conversation tool result 里保存的 `policy_evidence_refs_json` 原样放进 `SessionToolSummaryView.policy_evidence_refs`。
- 这导致 same-thread session bundle 序列化里出现 `evidence_id`、`tenant_id`、`text_hash`、`retrieved_at` 等权威 evidence ref 字段。它不是直接构造 `EvidenceRefV1`，但会让 session context 携带过完整的政策证据身份，和 MEM-03「session hints 只能是 contextual pointer」边界不一致。

**影响**
- Session memory prompt context 可能把完整 policy evidence ref 字段作为历史工具摘要的一部分继续传递。它仍不能通过现有 verifier 成为 policy/business/action authority，但语义上扩大了 session context 的数据面，增加后续误用风险。

**修复**
- 在 `src/memory/session_bundle.py` 增加 allowlist projection：policy refs 只保留 `doc_key` / `chunk_id` / `policy_version` / `policy_family` / `title` / `section`；business refs 只保留 `source_system` / `resource_type` / `resource_id` / `resource_version`。
- `SessionMemoryBundle` 继续生成 `policy_topic_hints` 和 `prior_policy_mention_refs`，但不再序列化 raw `evidence_id`、tenant、hash、retrieved timestamp、policy body 或 authority/debug 字段。
- 同步新增行为测试覆盖：session hint DTO 严格解析失败、默认 memory write 只产生 `SessionMemoryWriteCandidate`、raw session context 不作为 CWC identity。

**证据**
- Phase / plan：`46-03`
- Commits：`26cbb2b`（行为测试）、`5fd68c5`（session bundle ref 收窄）
- 文件：`src/memory/session_bundle.py`、`tests/memory/test_session_memory_bundle.py`、`tests/agent/test_memory_evidence_boundary.py`、`tests/memory/test_memory_write_service.py`、`tests/agent/test_reviewed_memory_context_retrieve.py`

**验证**
- 初始行为命令：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py tests/agent/test_memory_evidence_boundary.py tests/memory/test_memory_write_service.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py tests/memory/test_phase46_session_context_alignment.py -q` → `1 failed, 86 passed, 3 warnings`
- 修复后同命令 → `87 passed, 3 warnings`
- Phase 46 static smoke：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py -x -q` → `9 passed, 1 warning`
- Phase 46 targeted final：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py tests/memory/test_session_memory_schema.py tests/memory/test_session_memory_service.py tests/memory/test_session_memory_repository.py tests/memory/test_session_memory_bundle.py tests/memory/test_memory_context_bundle.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/memory/test_phase45_contract_alignment.py tests/memory/test_memory_write_service.py -q` → `133 passed, 9 warnings`

**剩余风险**
- ✅ 已修复验证。Session bundle 仍保留 prompt-safe tool summary text 与 allowlisted refs；这些仍是 contextual hints，不是 `EvidenceRefV1`、`BusinessFactRefV1`、approval/action authority 或 replay truth。

## Phase 46 Code Review Fix — SessionMemoryBundle prompt summary / hint text 边界净化 ✅已修复验证

**问题 / 根因**
- Phase 46 code review WR-02 确认：`SessionMemoryBundleService._tool_summary_views(...)` 会把 `ToolResultRecord.prompt_summary` 直接放入 `SessionToolSummaryView.prompt_summary`，而 `_safe_hint_value(...)` 只做 trim/truncate。
- 因此 same-thread session bundle / context bundle 在最终 prompt assembler 之前，仍可能携带 `raw_payload`、`private_reasoning`、`approval_authority_body`、`debug_trace`、`secret` 等 marker；原测试误改 `summary` 字段，没有命中实际 bundle 输入 `prompt_summary`。

**影响**
- 这些字符串仍是 contextual-only session context，不能直接成为 policy/business/action authority；但 bundle 边界的数据面不够 prompt-safe，会增加后续 assembler 或调用方误用风险。

**修复**
- 在 `src/memory/session_bundle.py` 增加 bundle-boundary marker scrubber：`prompt_summary` 使用同一禁用 marker 列表清洗，allowed policy/business hint 值也先清洗再截断；清洗后为空的 prompt summary 降级为固定安全占位。
- 更新 `tests/memory/test_session_memory_bundle.py`：直接污染 `prompt_summary`，并在 policy `title` / `section` hint 字段中放入 forbidden marker，断言序列化 bundle 不再携带这些 marker。

**证据**
- Phase / review：`46-REVIEW.md` WR-02
- 文件：`src/memory/session_bundle.py`、`tests/memory/test_session_memory_bundle.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py -q` → `5 passed, 1 warning`

**剩余风险**
- ✅ 已用 focused session bundle 测试覆盖 risky input 字段。该修复只保证 bundle 边界 prompt-safe marker scrub，不把 session hints 提升为 `EvidenceRefV1`、`BusinessFactRefV1`、approval/action authority 或 replay truth。

## Phase 47 Plan 02 — closed-case CWC→case-memory candidate projection seam ✅⚠️

**问题 / 根因**
- Phase 46 之后 `case_memories` 已被定位为 reviewed precedent，但还没有可信 closed-case 触发 seam；如果直接从 `AgentRun.final_status == "completed"` 推断结案，普通完成对话会被误发布为历史 precedent。
- CWC 是 `contextual_only` 工作上下文，若投影时直接序列化 rich objects 或 raw/debug/tool/policy payload，会把 claims、verified facts、policy evidence、approval/action/replay authority 混成同一种 case-memory 文本。
- `CaseMemory.scope_type/scope_id` 是检索 scope，source case identity 属于 `source_ref_json`；如果生成候选只用 source case id 做 scope，后续 merchant-scope reviewed retrieval 会漏掉可复用 precedent。

**修复**
- 新增内部 `ClosedCasePrecedentService.generate_closed_case_precedent_candidate(...)` seam，只接受显式 trusted close 输入；`TERMINAL_REFUND_CASE_STATUSES = {"closed", "refunded", "rejected"}`，`open` / `reviewing` / unknown 先返回 `non_terminal_status`，不查 case/CWC，不提交 case-memory。
- 新增 `RefundRepository.get_by_id_with_order(...)`，通过 tenant-bound `RefundCase.id + tenant_id` 查询并 `selectinload(RefundCase.order)`；merchant 可解析时生成 merchant scope，无法解析时只 fallback 到 exact case scope，绝不 fallback 到 tenant-wide scope。
- 新增 `_project_closed_case_candidate(...)`：只从 allowlisted CWC summaries/refs 构造 `CaseMemoryWriteCandidate(source_type="closed_case_cwc_candidate", embedding=None)`；claims 与 verified facts 分别标注 `Customer claim:` / `Verified fact:`；policy refs 只映射为 `doc_key/chunk_id/policy_version`；固定 caveat 声明该 precedent 不是 policy/business/approval/action/audit/replay authority；`sensitive/prohibited` CWC PII 返回 `pii_blocked` skip。
- 扩展 Phase 47 static guard，禁止 case-precedent projection 模块引入 Evidence / BusinessFact / Approval / Action / Replay authority DTO。

**证据**
- Phase / plan：`47-02`
- Commits：`c9757b1`（trusted close seam + tenant-bound scope lookup）、`f412b1d`（deterministic projection），TDD red commits `5d28154` / `6a31dcb`
- 文件：`src/memory/case_precedent.py:18`（terminal allowlist）、`src/memory/case_precedent.py:71`（service seam）、`src/memory/case_precedent.py:130`（merchant/case scope fallback）、`src/memory/case_precedent.py:138`（projection helper）、`src/repositories/refund_repo.py:23`（tenant-bound lookup）、`tests/memory/test_case_precedent_generation.py:163` / `tests/memory/test_case_precedent_generation.py:243`（behavior coverage）

**验证**
- RED 1：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` → expected fail, missing `src.memory.case_precedent`
- GREEN 1：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` → `8 passed, 1 warning`
- RED 2：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -x -q` → expected fail, missing `PRECEDENT_CAVEAT_TEXT`
- GREEN 2 / plan gate：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -q` → `21 passed, 1 warning`
- Ruff：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py src/repositories/refund_repo.py tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py` → pass

**剩余风险**
- ⚠️ 本 plan 只完成 trusted seam 与 pure projection；尚未调用 `CaseMemoryService.submit_case_memory_candidate(...)` 写入 `case_memories` / `memory_write_events`。候选提交、dedupe、tombstone、pending review visibility 属于 `47-03`；metadata/text reviewed retrieval 与 tool/reviewed-context stability 属于 `47-04`。

## Phase 47 Plan 03 — closed-case CWC candidate governed write lifecycle ✅⚠️

**问题 / 根因**
- 47-02 已能从 trusted terminal CWC 生成 `CaseMemoryWriteCandidate`，但还未提交到 `CaseMemoryService.submit_case_memory_candidate(...)`；如果后续实现直接插入 `case_memories` 或自建事件，会绕过已有 review-required、PII block、duplicate/tombstone、`memory_write_events` 与 pending review API 语义。
- 47-02 对 `sensitive/prohibited` CWC PII 是本地 skip，缺少现有 case-memory service 的 skip event，可观测性与普通 memory write policy 不一致。

**影响**
- 生成的 closed-case precedent candidate 可能绕过 reviewer governance 或缺少 audit trail；重复 close/CWC source identity 可能产生重复候选；PII block 路径如果没有 service event，后续排查无法和其他 memory write skip 行为对齐。

**修复**
- `ClosedCasePrecedentService.generate_closed_case_precedent_candidate(...)` 对 accepted terminal projection 只通过 `self.case_memory_service.submit_case_memory_candidate(candidate)` 持久化，不直接构造 `CaseMemory`，不调用 repository insert，不创建第二套 audit/review queue。
- `source_ref_json` 使用既有 allowed keys：`source_type/run_id/agent_run_id/event_id/business_object_type/business_object_id/outcome_id/policy_version`；`event_id` 固定为 `refund-case-close:{case_id}:{close_event_id}`，`outcome_id` 固定为 `cwc:{cwc_row.id}:v{cwc_row.version}`。policy refs 保持 `doc_key/chunk_id/policy_version`，不持久化 CWC 的 `doc_id/version` key。
- `sensitive/prohibited` CWC PII 改为构造固定非敏感文本 `CaseMemoryWriteCandidate`，携带原 PII classification 提交给 `CaseMemoryService`，由既有 service 返回 `skipped/pii_blocked` 并写入 skip event，不插入 `case_memories` row。
- 新增 integration coverage：terminal close writes one `needs_review` row + event；duplicate same source/content skip；不同 close event 但相同内容按 `duplicate_active_identity` skip；CWC version/content 改变可生成新候选；pending-review visible、reviewed retrieval invisible until approval、approval 后 retrieval 返回并保留 mapped policy refs；memory review API 可处理 `closed_case_cwc_candidate` rows。

**证据**
- Phase / plan：`47-03`
- Commits：`dde8fe9`（submit through service）、`7cc0179`（PII skip / dedupe lifecycle）、`1837f81`（approval-gated review lifecycle tests）、`9c6a319`（Ruff cleanup），TDD red commits `b534821` / `14def65`
- 文件：`src/memory/case_precedent.py`、`tests/memory/test_case_precedent_generation.py`、`tests/test_memory_review_api.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` → `18 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -q` → `33 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/case_precedent.py tests/memory/test_case_precedent_generation.py tests/test_memory_review_api.py` → pass

**剩余风险**
- ⚠️ 47-03 已关闭 governed write/review/audit/dedupe/PII skip lifecycle；metadata/text reviewed retrieval breadth、planner-facing `search_case_memory` / reviewed-context stability、docs/DEFER-3/final validation 仍属于 `47-04`，不要提前标记 MEM-04 phase-complete。

## Phase 47 Code Review Fix WR-01 — closed-case precedent 内容身份去泛化 ✅已修复验证

**问题 / 根因**
- Phase 47 code review 确认：`CaseMemoryService` 对 `closed_case_cwc_candidate` 生成的 case memory 只用通用 `summary` 计算 `content_hash`；同一商家、同一 `issue_type/case_type` 的不同历史退款 case 会因为 summary 均为 `Closed refund case precedent: refund_dispute.` 被误判为 `duplicate_active_identity`。

**影响**
- 不同 source case / CWC row / excerpt / outcome 的 reviewed precedent 候选可能只保留第一条，后续真实商家历史样本进入不了 `needs_review` 队列。

**修复**
- `closed_case_cwc_candidate` 的内容身份改为绑定 `summary/excerpt/applicability/outcome/caveats` 的完整投影文本；非 generated closed-case 的 case-memory writer 仍保持原 summary-only 内容身份，避免扩大既有 duplicate 行为变更面。
- 新增回归覆盖：同一 merchant、同一 `refund_dispute` case type、两条不同 closed refund case / CWC 投影都生成独立 `needs_review` row；真正相同投影内容仍按 content hash dedupe。

**证据**
- Phase / review：`47-REVIEW.md` WR-01
- 文件：`src/memory/case_memory.py`、`tests/memory/test_case_precedent_generation.py`
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -q` → `20 passed, 1 warning`

**剩余风险**
- ✅ 本修复只改变 generated closed-case precedent 的 content identity；未扩大到普通 `llm_candidate` / `human_reviewed` case memory。

## Phase 47 Code Review Fix WR-02 — reviewed-memory case_type 来源改为 issue_type ✅已修复验证

**问题 / 根因**
- Phase 47 code review 确认：`reviewed_memory_context_retrieve` 用 `primary_intent/current_intent` 作为 `CaseMemorySearchRequest.case_type`。但 generated closed-case precedent 写入时使用 CWC `issue_type` 作为 `CaseMemory.case_type`，例如 `refund_dispute`；正常退款流程的 `primary_intent` 可能是 `refund_troubleshooting`，导致真实 approved generated precedent 被 metadata filter 隐藏。

**影响**
- 已审核的 `closed_case_cwc_candidate` merchant-scope precedent 可能无法进入 reviewed memory context，削弱 Phase 47 对历史 closed case 的复用价值。

**修复**
- `reviewed_memory_context_retrieve._case_type(...)` 改为只从 `active_slots/extracted_slots.issue_type` 派生 case-memory metadata filter；没有 issue_type 时不再把 intent label 当 case_type。
- 新增真实 node→`MemoryContextService`→repository integration coverage：approved `closed_case_cwc_candidate` 行 `case_type='refund_dispute'`，state `primary_intent='refund_troubleshooting'`，merchant scope 匹配且无 case id，仍能返回 reviewed case memory item。

**证据**
- Phase / review：`47-REVIEW.md` WR-02
- 文件：`src/agent/nodes/reviewed_memory_context_retrieve.py`、`tests/agent/test_reviewed_memory_context_retrieve.py`
- 验证：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py -q` → `15 passed, 1 warning`

**剩余风险**
- ✅ 本修复不扩展 `ToolCallContext` 或 case-id contract；retrieval scope 仍由 trusted merchant scope / current slots 控制。

## Phase 49 Plan 01 — investigate deterministic planner 主路径降级为 LLM planner fallback 壳 ⚠️阶段性修复

**问题 / 根因**
- Phase 49 baseline 确认：`src/agent/nodes/investigate.py` 的主控制仍由 legacy `plan_next_step(...)` deterministic 候选表驱动，LLM 没有真正拥有 ReAct loop 内“选择下一个只读工具或 stop”的主控权。
- 旧 `_validate_planner_step(...)` 只检查 dict / tool 是否可见 / args 是否为 dict，未严格校验 `{next_tool,args,reason}` / `{stop,stop_reason}` schema、§12.4 investigate 8-tool allowlist、write tool、descriptor input schema 或 fallback 安全边界。

**影响**
- investigate 无法落地 contract-spec §9.4 的 bounded ReAct loop 主控语义；非法 planner/fallback 输出在进入 ToolPlatform.invoke 前的 fail-closed 边界不够强。

**修复**
- 新增 `src/agent/nodes/investigate_planner.py`，定义 `InvestigatePlannerDecision` structured output schema、8-tool allowlist 和 stop reason enum。
- `investigate` 主路径改为 planner → strict validation → deterministic fallback → strict validation；默认生产路径调用 `_get_llm().with_structured_output(InvestigatePlannerDecision)`，旧 deterministic 逻辑保留为 `_deterministic_fallback_plan_next_step(...)`。
- planner 输入只包含 user/query、intent、当前 slot、loop-local discovered slot 占位、projected observation summaries、ToolViewV1 allowlisted descriptors、iteration 和 attempted keys；raw tool payload 不进入 planner prompt。
- validation 在 ToolPlatform.invoke 前拒绝 write/out-of-allowlist tool、不可见 tool、非法 stop reason、额外顶层字段、descriptor schema 不合法 args；fallback 本身也必须通过同一校验。

**证据**
- Phase / plan：`49-01`
- 文件：`src/agent/nodes/investigate.py`、`src/agent/nodes/investigate_planner.py`、`src/agent/prompts.py`、`tests/agent/test_nodes/test_investigate.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` → `46 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/agent/nodes/investigate_planner.py src/agent/prompts.py tests/agent/test_nodes/test_investigate.py` → pass

**剩余风险**
- ⚠️ 49-01 只完成 planner schema / validation / fallback 壳；真正多轮 loop-local discovered slots、8-tool projection/trace/replay 完整语义、graph E2E safety regression 仍分别属于 49-02 / 49-03 / 49-04。当前不得把 GAD-01 标为 implemented。

## Phase 49 Plan 02 — investigate loop-local discovered slots 与 bounded attempt guard ⚠️阶段性修复

**问题 / 根因**
- 49-01 后 planner 已成为主路径，但 observation→slot 回流仍只是占位；`get_order` 返回的安全 relation hints 无法喂给下一轮 planner/fallback，order→ticket 等链式调查不成立。
- `ToolResultProjector` 没有 prompt-safe structured `relation_hints` surface，若后续从 summary/text/raw payload 抽取 identifier，会扩大 prompt-injection 与 raw-data 污染风险。
- runtime 只有全局 max iteration/deadline 与 duplicate set，缺少按 tool+args 的 `max_attempts` 计数；ToolPlatform.invoke 抛异常时也会直接冒泡而不是 fail-closed。

**影响**
- investigate 还不像真正 ReAct loop：observation 不能安全影响后续 action，且异常/重复调用的 boundedness 不完整。

**修复**
- `investigate` loop context 增加 `base_slots`、`discovered_slots`、`observations`、`attempt_count_by_key`；`_case_slots_for_loop(...)` 只在本次 loop 内合并 discovered slots，不写 `active_slots` / `extracted_slots` / `candidate_slots`。
- `ToolResultProjector` 增加窄的 prompt-safe `relation_hints`，并只保留 allowlisted scalar hints；raw/secret nested keys 不进入 relation_hints。
- `_discover_loop_slots_from_projection(...)` 只从 projection structured fields、business fact envelope refs、relation_hints 抽取；direct identifier discovery 按 tool 类型限定，get_order 不会因任意 top-level `data["ticket_id"]` 生成 `ticket_id`。
- runtime 增加 per tool+args `max_attempts` 计数，并将 ToolPlatform.invoke 异常转换为 `termination_reason="unrecoverable_error"` 和 safe error，不让异常逃出 node。

**证据**
- Phase / plan：`49-02`
- 文件：`src/agent/nodes/investigate.py`、`src/tools/projection.py`、`tests/agent/test_nodes/test_investigate.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` → `51 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py -q` → `47 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/tools/projection.py tests/agent/test_nodes/test_investigate.py` → pass
- `rg -n 'active_slots\s*=|active_slots\]|active_slots\.' src/agent/nodes/investigate.py || true` → no output

**剩余风险**
- ⚠️ 49-02 已完成 loop-local slot scratchpad 和 bounded attempt guard；8-tool exact coverage、projection raw-context audit、trace/replay parent/iteration semantics 仍属于 49-03。GAD-01 仍不得标为 implemented。

## Phase 49 Plan 03 — investigate 8-tool surface / projection boundary / trace replay identity ⚠️阶段性修复

**问题 / 根因**
- Catalog 已声明 §12.4 的 8 个 investigate read/retrieval tools，但 real `KnowledgeToolExecutor.has_tool(...)` 只认 `search_policy`，导致 `search_sop` 在真实 executor availability 下会被静默隐藏。
- 49-02 已有 projection-based observation，但还缺少测试证明 fake planner input 不含 raw payload sentinel，且 8-tool exact visible/invoke coverage 没有固定。
- replay/event 底层已有 `parent_operation_id`、`attempt`、`tool_call_id` 字段，但 `src.agent.events.emit_event(...)` / `emit_decision_event(...)` 没有把这些字段从 investigate 透传到 `ReplayService.append_event(...)`。

**影响**
- Planner-visible tool surface 可能与 contract-spec §12.4 不一致；investigate ReAct loop 的每轮 tool/RAG call 可审计性不完整，多个 loop operation 难以按 parent/iteration/tool_call_id 做 replay 区分。

**修复**
- `KnowledgeToolExecutor.has_tool(...)` 接受 `search_sop`，执行仍保持 declared read-only unavailable/no-data 路径，不新增 SOP 业务语义。
- 新增 ToolPlatform exact-set 与 8-tool invoke smoke 测试，证明 `get_order/get_refund_case/get_ticket/get_logistics/get_merchant_risk/search_policy/search_sop/search_case_memory` 均可经 `ToolPlatform.invoke(...)` dispatch，且 write tool 不可见。
- planner input 测试捕获第二轮 fake planner input，断言 raw payload sentinel、PII、raw key 不进入 planner context；allowlist 不含 `create_coupon_grant_draft`。
- `emit_event(...)` / `emit_decision_event(...)` 增加 existing replay fields 的参数透传：`parent_operation_id`、`attempt`、`tool_call_id`；`investigate` tool events 将 distinct operation_id、iteration、attempt、tool_call_id 和可选 `node_operation_id` parent 写入 event/emitter/DB row。

**证据**
- Phase / plan：`49-03`
- 文件：`src/tools/executors/knowledge.py`、`src/agent/nodes/investigate.py`、`src/agent/events.py`、`src/replay/decision_events.py`、`tests/agent/test_nodes/test_investigate.py`、`tests/tools/test_tool_platform.py`、`tests/replay/test_operation_pairing.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` → `52 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` → `79 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q` → `23 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_events.py tests/replay/test_decision_events.py -q` → `68 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/agent/events.py src/replay/decision_events.py src/tools/executors/knowledge.py tests/agent/test_nodes/test_investigate.py tests/tools/test_tool_platform.py tests/replay/test_operation_pairing.py` → pass
- `rg -n 'ToolPlatform\.invoke|tool_platform\.invoke|BusinessFactService|BusinessToolService|KnowledgeToolExecutor|PolicyKnowledgeService|MemoryService|CaseMemoryService|create_coupon_grant_draft|action_' src/agent/nodes/investigate.py` → only `tool_platform.invoke(...)` and redaction policy string

**剩余风险**
- ⚠️ Parent operation identity is emitted when `configurable["node_operation_id"]` / `investigate_operation_id` is available; graph-level node start/completion event emission is not introduced in 49-03. 49-04 closeout must decide whether this is sufficient for GAD-01 or record an IMPLEMENTED_WITH_LIMITATIONS replay parent-operation note.

## Phase 49 Closeout — investigate legacy deterministic planner debt ⚠️已实现但有 replay parent 限制

**问题 / 根因**
- GAD-01 的目标契约要求 `investigate` 内部是 bounded read-only ReAct loop，但 Phase 49 前生产实现仍由 legacy deterministic `plan_next_step(...)` 候选表主控，LLM 不参与每轮 tool/stop 决策。
- 该 legacy 实现还缺 8-tool exact allowlist 覆盖、loop-local observation→slot 回流、planner raw-payload boundary 测试，以及 loop 内 tool/RAG operation 的 replay-distinguishable metadata 覆盖。

**影响**
- 调查路径无法表达「订单→发现工单→再查工单→查政策」这类跨数据源动态调查，只能按固定候选表退化执行。
- 若不修 projection / trace / no-go 边界，ReAct 迁移可能污染 memory/intent/active_slots，或让 LLM 间接触达 write/action/routing/approval 权限。

**修复**
- `src/agent/nodes/investigate.py` 默认主路径改为 structured LLM planner，每轮只允许 `{next_tool,args,reason}` 或 `{stop,stop_reason}`；输出经 schema、8-tool allowlist、descriptor input schema、read/retrieval descriptor 边界严格验证后才进入 `ToolPlatform.invoke(...)`。
- legacy deterministic `plan_next_step` 未删除，降级为 planner timeout / invalid output / invalid tool / invalid args / planner unavailable 的 fallback；fallback 也必须通过同一只读校验。
- loop-local `discovered_slots` scratchpad 支持从 projected structured observation / relation hints / typed refs 发现 `ticket_id` 等标识符并喂给后续 planner iteration；不写 `active_slots` / `extracted_slots` / `candidate_slots`，不改 memory writer。
- §12.4 八个 read/retrieval tools 已 exact-set 覆盖：`get_order`、`get_refund_case`、`get_ticket`、`get_logistics`、`get_merchant_risk`、`search_policy`、`search_sop`、`search_case_memory`。`search_sop` 在 real knowledge executor 中可见，但在无 SOP backend 时保持 read-only unavailable/no-data。
- Planner input 只使用 `ToolResultProjector` 后的 projected observation summary；raw payload、PII sentinel、policy/body/debug/private 字段不进入 planner prompt。
- 每轮 tool/RAG event 已有 distinct `operation_id`、`iteration`、`attempt`、`tool_call_id`；当 graph/configurable 提供 `node_operation_id` 或 `investigate_operation_id` 时写入 `parent_operation_id`。
- 49-04 增加 graph-level fake structured planner seam 和回归：order→ticket 链式调查成立、policy-only 不强制 business context、planner 试图输出 write/action/routing/approval bypass 时只能 fallback/被拒，不能越过 router / approval / action gate。
- 收尾复核补修 planner stop reason 映射：`stop_reason="max_iterations_reached"` 已由 schema 允许，termination canonicalization 必须原样保留，避免被误降级为 `unrecoverable_error`。

**证据**
- Phase / plans：`49-01`、`49-02`、`49-03`、`49-04`
- 实现文件：`src/agent/nodes/investigate.py`、`src/agent/nodes/investigate_planner.py`、`src/tools/projection.py`、`src/tools/executors/knowledge.py`、`src/agent/events.py`、`src/replay/decision_events.py`
- 测试文件：`tests/agent/test_nodes/test_investigate.py`、`tests/agent/test_graph.py`、`tests/tools/test_tool_platform.py`、`tests/replay/test_operation_pairing.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py -q` → `81 passed, 25 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py -q` → `47 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py -q` → `41 passed, 4 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q` → `31 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/agent/test_graph.py` → pass
- `rg -n 'active_slots\s*=|active_slots\]|active_slots\.' src/agent/nodes/investigate.py || true` → no output
- `rg -n 'BusinessFactService|PolicyKnowledgeService|CaseMemoryService|RefundRepository|OrderRepository' src/agent/nodes/investigate.py || true` → no output
- `rg -n 'create_coupon_grant_draft|issue_coupon|partial_refund|full_refund|close_ticket|escalate_ticket|manual_review' src/agent/nodes/investigate.py || true` → no output

**剩余风险**
- ⚠️ GAD-01 closeout 为 `IMPLEMENTED_WITH_LIMITATIONS`，不是完全 `IMPLEMENTED`：investigate 已能在 event helper / DB row 中接收并写入 parent operation identity，但 Phase 49 没有新增 graph-level node operation start/completion emission，也没有强制 graph 自动传 `node_operation_id`。当前 replay 可通过 distinct tool operation + iteration + optional parent 区分 loop；完整“node operation 下挂多个 tool operation”的强 parent 语义留作后续 replay/trace graph-lifecycle phase。
- ✅ 本 phase 未修改 `docs/contract-spec.md`、intent contract、memory writer/CWC schema、`active_slots` writer、risk/approval/action executor。

## Phase 53 Plan 02 — active graph 切到 session_context_load -> contextual_intent_resolve ✅已修复验证

**问题 / 根因**
- Phase 52 之后 runtime graph 已有独立 `safety_pre_route`，但 safe / `safety_sensitive` continuation 仍进入旧 `classify_intent` active node，随后进入旧 `session_memory_load` active node。
- Phase 53-01 已新增 canonical `contextual_intent_resolve` 与非 active `route_after_contextual_intent`，但 active graph / router / policy route values 尚未同步切换；如果只改其中一层会产生 route-map drift。

**影响**
- CAGM-04 未满足：same-thread session context 不能在 intent LLM 之前加载，active graph 仍依赖 `classify_intent` / `session_memory_load` 作为注册节点。
- slot-required intents 仍把 policy route 指向 `session_memory_load`，会阻塞后续 Phase 54 slot gate cutover。

**修复**
- `route_after_safety` safe / `safety_sensitive` continuation 改为 `session_context_load`；`SAFETY_ROUTES` 同步更新。
- `route_after_contextual_intent` 成为 active graph router；保留的 `route_after_intent` 仅直接委托给 contextual router，不再有独立 allowlist / 行为分叉。
- slot-required `IntentDefinition.initial_route` 从 `session_memory_load` 改为 Phase 54 兼容目的地 `extract_slots`。
- `src/agent/graph.py` active graph 删除 `classify_intent` / `session_memory_load` 注册和 path-map destination，新增 `session_context_load`、`contextual_intent_resolve` 注册以及固定边 `session_context_load -> contextual_intent_resolve`。
- `MemoryService.load_session_memory(..., current_intent=None)` 不再把 pre-intent unknown 误判为 intent-incompatible；同线程 trusted slots 可以在 intent LLM 之前进入 `session_context_load` 的 contextual surface。
- `extract_slots` 仍保留为 Phase 54 兼容 active node；未引入 `slot_resolution_gate`、`memory_context_load`、`recommendation_generation`、`risk_gate` 或 Phase 58 no-debt cleanup。

**证据**
- Phase / plan：`53-02`
- 文件：`src/agent/routing.py`、`src/agent/intent_policy.py`、`src/agent/graph.py`、`src/memory/service.py`、`tests/architecture/graph_baseline.py`、`tests/architecture/test_canonical_graph_baseline.py`、`tests/test_graph_routing.py`、`tests/agent/test_intent_routing.py`、`tests/agent/test_graph.py`、`tests/memory/test_session_memory_service.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` → `1217 passed, 1 skipped`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py tests/test_graph_routing.py -q --tb=short` → `137 passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/service.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py tests/test_graph_routing.py src/agent/routing.py src/agent/intent_policy.py src/agent/graph.py tests/agent/test_intent_routing.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py` → pass
- `rg -n 'add_node\("session_context_load"|add_node\("contextual_intent_resolve"|add_edge\("session_context_load", "contextual_intent_resolve"\)' src/agent/graph.py` → 找到 active registration / fixed edge
- `! rg -n 'add_node\("classify_intent"|add_node\("session_memory_load"|"classify_intent": "classify_intent"|"session_memory_load": "session_memory_load"' src/agent/graph.py tests/architecture/graph_baseline.py` → no active-runtime hits

**剩余风险**
- ✅ CAGM-04 active graph cutover 已完成并验证。
- 🟡 `extract_slots` 仍是 active compatibility node，删除 phase 为 Phase 54 / CAGM-05。
- 🟡 `long_term_memory_retrieve`、`generate_recommendation`、`assess_risk_and_approval` 等 legacy active names 仍分别属于 Phase 55 / 56 / 57；Phase 53-02 未提前清理。

## Phase 53 Plan 03 — graph vocabulary / docs / validation closeout ✅已修复验证

**问题 / 根因**
- Phase 53-02 已完成 active graph cutover，但 trace vocabulary、SSE label、current-source architecture snapshot 和 compatibility ledger 仍可能把 `classify_intent` / `session_memory_load` 误读成 active runtime surface。
- 执行 scan 后确认剩余旧名命中来自 wrapper/import/test/historical display/output mirror，而不是 active graph registration、active route destination 或 active policy route value。

**影响**
- 如果不收口，operator-facing trace、replay/eval projection 和后续 Phase 54-58 plan 可能继续把历史名称当作当前 runtime authority。
- `llm_outputs["intent_classification"]` reader 若不登记，可能绕过 Phase 58 no-debt cleanup 变成永久 output mirror。

**修复**
- `src/agent/graph_vocabulary.py` 将 `contextual_intent_resolve` 和 `route_after_contextual_intent` 标为 `runtime`；将 `classify_intent`、`intent_classification`、`session_memory_load`、`route_after_intent` 标为 Phase 53 compatibility alias，并加 `PHASE_53_COMPATIBILITY_ALIAS` / `DELETE_BY_PHASE_58` reason code。
- `src/api/routers/agent_runs.py` 增加 `session_context_load` 和 `contextual_intent_resolve` SSE label；旧 `classify_intent` label 只保留给历史 trace display。
- `docs/current-langgraph-architecture.md` 已更新为 Phase 53 current-source snapshot：`receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve`，并明确 `classify_intent` / `session_memory_load` 不再是 active registered graph node。
- `llm_outputs["intent_classification"]` reader / adapter mirror、`classify_intent.py` wrapper、`session_memory_load.py` wrapper、`route_after_intent` helper 均登记为非 authoritative compatibility surface，删除 phase 不晚于 Phase 58。
- 未修改 `docs/contract-spec.md`：§9 已包含 Phase 53 target semantics，本 plan 只同步当前源码事实。

**兼容面台账**

| Legacy surface | Canonical owner | Reason | Trace projection / validation | Delete phase |
|----------------|-----------------|--------|-------------------------------|--------------|
| active `classify_intent` graph node / `safety_pre_route -> classify_intent` continuation | `contextual_intent_resolve` | Phase 52 compatibility path, Phase 53 已关闭 active runtime | `! rg 'add_node\("classify_intent"' src/agent/graph.py tests/architecture/graph_baseline.py` 无命中；historical trace projects to `contextual_intent_resolve` | ✅ closed in Phase 53 |
| active `session_memory_load` graph node / route destination | `session_context_load` | same-thread context before intent, Phase 53 已关闭 active runtime | `! rg 'add_node\("session_memory_load"' src/agent/graph.py tests/architecture/graph_baseline.py` 无命中；historical trace projects to `session_context_load` | ✅ closed in Phase 53 |
| `src/agent/nodes/classify_intent.py` wrapper and import/test surface | `contextual_intent_resolve` | backward-compatible imports and legacy tests | `tests/agent/test_nodes/test_classify_intent.py` and vocabulary tests pass; not registered in active graph | Phase 58 |
| `llm_outputs["intent_classification"]` reader / adapter mirror | `contextual_intent_resolve` | historical final-response / adapter compatibility | scan hit only in `src/agent/nodes/final_response.py` and tests; active contextual node writes canonical `llm_outputs["contextual_intent_resolve"]` | Phase 58 |
| `src/agent/nodes/session_memory_load.py` wrapper | `session_context_load` | backward-compatible import and historical trace node name | scan hit only in wrapper/tests; active graph uses `session_context_load` | Phase 58 |
| `route_after_intent` helper | `route_after_contextual_intent` | backward-compatible imports/tests after active router cutover | helper delegates to contextual router; active graph uses `route_after_contextual_intent` | Phase 58 |

**证据**
- Phase / plan：`53-03`
- 文件：`src/agent/graph_vocabulary.py`、`src/api/routers/agent_runs.py`、`tests/agent/test_graph_vocabulary.py`、`tests/agent/test_trace.py`、`docs/current-langgraph-architecture.md`、`.planning/phases/53-session-context-before-intent-and-contextual-intent-resolve/53-VALIDATION.md`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py -q --tb=short` → `65 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` → `1399 passed, 2 skipped, 35 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture` → pass
- `! rg -n 'add_node\("classify_intent"|add_node\("session_memory_load"|"classify_intent": "classify_intent"|"session_memory_load": "session_memory_load"' src/agent/graph.py tests/architecture/graph_baseline.py` → no active-runtime hits
- `! rg -n 'classification_trace.*pre_route_decision|pre_route_decision": pre_route|pre_route_decision": pre_route\.model_dump' src/agent/nodes/contextual_intent_resolve.py` → no duplicate pre-route ownership hits
- `rg -n '"session_memory_load"|route_after_intent|classify_intent|intent_classification' src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/nodes src/api tests/architecture/graph_baseline.py tests/agent || true` → reviewed hits are limited to wrapper/import/test/historical label/output mirror surfaces listed above.

**剩余风险**
- ✅ Phase 52 active `classify_intent` / `session_memory_load` compatibility is closed in the active graph and route maps.
- 🟡 `classify_intent.py`、`session_memory_load.py`、`route_after_intent` and `llm_outputs["intent_classification"]` remain compatibility surfaces until Phase 58 cleanup.
- 🟡 `extract_slots` remains the intentional Phase 54 active compatibility destination; Phase 53 did not promote `slot_resolution_gate`.

## Phase 54 Plan 03 — active `extract_slots` slot boundary 关闭并登记兼容面 ✅⚠️

**问题 / 根因**
- Phase 54-02 已把 active graph / router / policy route values 切到 `slot_resolution_gate` / `route_after_slot_resolution`，但 vocabulary、SSE label、current-source docs 和架构债务台账如果继续把 `extract_slots` 写成 active surface，会让后续 replay / trace / Phase 55-58 planning 误读当前 runtime authority。
- 旧 `extract_slots` 名称仍可能出现在 persisted trace rows、SSE display、`src/agent/nodes/extract_slots.py` import/test compatibility、`route_after_slots` helper 和历史测试中；这些需要显式标注 owner、reason、trace projection、validation 和 delete phase，而不能默认为当前 runtime。

**影响**
- 若 active `extract_slots` 债务不关闭，CAGM-05 会看似未完成；若直接删除所有旧名，又可能破坏历史 trace/API projection 和 legacy import tests。
- 如果 `slot_extraction` 被注册成 graph node，会违反 Phase 50 SPEC 与 `docs/contract-spec.md` §9 的 no-`slot_extraction` graph-node 约束。

**处理状态**
- ✅ 已关闭 active runtime debt：`src/agent/graph.py` 当前注册 `slot_resolution_gate`，不注册 `extract_slots`；active conditional edge source/router 为 `("slot_resolution_gate", "route_after_slot_resolution")`，不再有 `("extract_slots", "route_after_slots")`。
- ✅ `src/agent/graph_vocabulary.py` 已将 `slot_resolution_gate` node 与 `route_after_slot_resolution` router 标为 `runtime`；`extract_slots` node 与 `route_after_slots` router 保留为 `compatibility_alias`，reason codes 至少包含 `PHASE_54_COMPATIBILITY_ALIAS`、`HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。
- ✅ `src/api/routers/agent_runs.py` 已新增 `slot_resolution_gate` 中文 runtime label；旧 `extract_slots` label 仅用于历史 / persisted row display compatibility。
- ⚠️ `54-VALIDATION.md` 的最终 green 状态和完整 command evidence 由 54-03 Task 3 写入；本条先登记已基于 source/test 关闭的 architecture debt 与仍保留的 compatibility surfaces。

**保留兼容面**

| Surface | Owner | Reason | Trace/API projection | Validation | Delete phase |
|---------|-------|--------|----------------------|------------|--------------|
| `src/agent/nodes/extract_slots.py` wrapper/import/test surface | `slot_resolution_gate` | 兼容旧 import 与 legacy unit tests；active graph 不再注册 | 历史 `extract_slots` trace/API rows project to `slot_resolution_gate`，status `compatibility_alias` | `tests/agent/test_nodes/test_extract_slots.py` + Phase 54 final active graph scan | No later than Phase 58 |
| `route_after_slots` helper | `route_after_slot_resolution` | 兼容旧 router import/tests；active graph 不再使用 | `route_after_slots -> route_after_slot_resolution`，status `compatibility_alias` | graph source uses `route_after_slot_resolution`; vocabulary uniqueness / alias reason-code tests pass | No later than Phase 58 |
| Historical `extract_slots` persisted trace/API/SSE display | `slot_resolution_gate` | 不重写历史存储；保持 operator/replay 可读 | `_sse_event` preserves `node_name="extract_slots"` and adds `target_node_name="slot_resolution_gate"` | `tests/agent/test_trace.py`、`tests/test_trace_api.py`、`tests/test_agent_runs_api.py` | No later than Phase 58 or earlier if historical display compatibility is retired |

**证据**
- Phase / commits：`54-02` active graph cutover (`e46d9d2`, `9765483`)；`54-03` vocabulary/API closeout (`e2a0837`, `70048fa`)。
- Source facts：`src/agent/graph.py` registers `slot_resolution_gate`; `src/agent/routing.py` exposes `route_after_slot_resolution` and keeps `route_after_slots` as delegate-only; `tests/architecture/graph_baseline.py` active node baseline includes `slot_resolution_gate` and excludes `extract_slots`; `src/agent/graph_vocabulary.py` marks Phase 54 runtime/compatibility split.
- Verification so far：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name tests/test_agent_runs_api.py::test_sse_event_projects_runtime_slot_resolution_node_identity -q --tb=short` → `89 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/api/routers/agent_runs.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py` → pass。

**剩余风险**
- 🟡 Retained compatibility surfaces must be removed or reclassified no later than Phase 58.
- 🟡 Phase 55 / 56 / 57 still own active `long_term_memory_retrieve`、`generate_recommendation`、`assess_risk_and_approval` cutovers; Phase 54 does not activate `memory_context_load`、`recommendation_generation` or `risk_gate` as active registered graph nodes.
- ✅ `slot_extraction` remains unregistered in the main graph; Phase 54 does not introduce it as a node.

## Phase 53 code review fix — `intent_classification` output mirror 兼容回归 ✅已修复验证

**问题 / 根因**
- Phase 53-03 将 graph vocabulary 和 docs 正确登记了 `llm_outputs["intent_classification"]` 为 retained compatibility mirror，但 implementation 里 `classify_intent.py` 兼容 wrapper 直接委托 canonical `contextual_intent_resolve.intent_result_to_state()`，没有恢复 legacy mirror。
- `tests/agent/test_intent_adapter.py` 不在 Phase 53 final focused command 中，导致这个兼容测试直到 code review deep suite 才失败。

**影响**
- 仍通过 `src.agent.nodes.classify_intent.intent_result_to_state` 读取 legacy `llm_outputs["intent_classification"]` 的兼容调用方会收到 `KeyError`。
- 该问题不影响 active graph route authority：active graph 已使用 `contextual_intent_resolve` 和 canonical `llm_outputs["contextual_intent_resolve"]`。

**修复**
- 在 `src/agent/nodes/classify_intent.py` wrapper 层新增 `_with_legacy_intent_output_mirror()`，只对 legacy compatibility entrypoint 补 `llm_outputs["intent_classification"] = llm_outputs["contextual_intent_resolve"]`。
- canonical `src/agent/nodes/contextual_intent_resolve.py` 不写 legacy mirror，继续保持 active owner 为 `contextual_intent_resolve`。
- `tests/agent/test_nodes/test_classify_intent.py` 增加 wrapper mirror 断言；`tests/agent/test_intent_adapter.py` 重新通过。

**证据 / 验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short` → `21 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_routing.py tests/test_graph_routing.py tests/agent/test_graph_vocabulary.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_service.py tests/agent/test_trace.py tests/agent/test_intent_adapter.py -q --tb=short` → `1298 passed, 1 skipped, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/classify_intent.py tests/agent/test_nodes/test_classify_intent.py` → pass

**剩余风险**
- 🟡 `intent_classification` mirror 仍是 Phase 58 cleanup surface，不应新增 active graph/route authority。
- 🟡 Phase 53 final validation suite 需要在 review-fix closeout 追加 `tests/agent/test_intent_adapter.py` 覆盖，避免 retained mirror 再次漏测。

## Phase 53 code review fix WR-01 — pre-intent session slot 兼容性改为 post-intent 复核 ✅已修复验证

**问题 / 根因**
- Phase 53 将 active graph 切到 `session_context_load -> contextual_intent_resolve` 后，`MemoryService.load_session_memory(..., current_intent=None)` 会在意图未知时保留同线程 session slots，但旧 metadata 仍写 `intent_compatible=True`。
- 后续 slot resolution 已拿到真实 `primary_intent` 时，`SlotPolicyRegistry.accepts_inherited_slot()` 先信任该布尔值，再看 `compatible_intents`。这会让 pre-intent 加载进来的非业务 ID 槽位（如 `action_type`）绕过真实意图兼容性过滤。

**影响**
- `action_request` 这类需要 `action_type` 的高风险路径，可能接受只对 `compensation_suggestion` 兼容的 inherited `action_type`，从而跳过 clarification gate。
- 该问题只影响同线程 trusted session slot 继承裁决；current-turn extracted slots 仍优先，业务 ID 跨意图兼容是有意保留行为。

**修复**
- 将业务 ID 跨意图兼容规则提升到 `src/agent/intent_policy.py::slot_intent_compatible()`，供 memory load 与 slot policy 共用。
- `MemoryService.load_session_memory()` 在 `current_intent=None` 时继续保留未过期槽位，但写入 `intent_compatible=False` 与 `intent_filter_applied=False`，避免把“未过滤”误标为“已兼容”。
- `SlotPolicyRegistry` 在存在真实 intent 和 `compatible_intents` 时重新计算兼容性，不再先信任 pre-intent 布尔值；同时保留 `order_id` / `refund_case_id` / `ticket_id` 的有意跨意图兼容。

**证据 / 验证**
- 文件：`src/memory/service.py`、`src/agent/intent_policy.py`、`tests/memory/test_session_memory_service.py`、`tests/agent/test_required_slots.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ['src/agent/intent_policy.py','src/memory/service.py','tests/agent/test_required_slots.py','tests/memory/test_session_memory_service.py']]"` → pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/memory/test_session_memory_service.py -q --tb=short` → `33 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_routing.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py -q --tb=short` → `1125 passed, 8 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/memory/service.py tests/agent/test_required_slots.py tests/memory/test_session_memory_service.py` → pass

**剩余风险**
- ✅ WR-01 已在 resolver / router 层用回归测试覆盖：pre-intent inherited `action_type` 对不兼容 actual intent 被拒绝并路由到 `clarification_gate`。
- ✅ 业务 ID 跨意图兼容已覆盖：`order_id` 从 `refund_troubleshooting` 继承到 `action_request` 仍可满足 slot gate。
