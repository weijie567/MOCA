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

# 1. 工具调用（Tool Platform）

**范围**：`src/tools/`（catalog / contracts / runtime / policy / platform / projection / validation / executors）。
**这一轮 = milestone v2.1「Tool Platform Hardening」，Phase 37–41，5 phase / 14 plan，全部标记 complete（`.planning/STATE.md`）。**
**唯一 normative 契约源**：`docs/contract-spec.md` §8.0 / §12.5 / §12.6。

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

> 待后续修改 RAG 时按「写入规则」补充检出的缺陷与修复。当前无本轮新检出条目。

---

# 4. 记忆（Memory）

**范围**：短期/会话记忆、thread summary、ContextAssembler、记忆边界与 fail-closed。
**已 ship**：v1.1 Memory Foundation V2、v1.7 短期记忆统一。
**在册探索**：Phase 999.1「评估 mem0 作为 MemoryContextService 背后可选 backend」。

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
