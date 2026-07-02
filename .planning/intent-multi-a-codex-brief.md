# Codex 执行规格：多意图档位 A（识别计划 + 记录待确认后续，不自动执行链）

> 本文件是交给 Codex 的实现规格，等价于一次 PLAN 的 must-haves + 验收标准。
> Claude 是设计者/裁决者，Codex 实现，Claude 按本文「验收标准 / 检查清单」拿真实代码核对，不盲信自述。
> 关联台账：`.planning/ARCHITECTURE-DEBT.md` 第 2 节 ID-04 与 ID-DESIGN、其中的「分档决策（2026-07-02）」。
> 前置：三层契约拆分（`intent-layering-codex-brief.md`）已落地并验收，本规格站在其上。

## 0. 目标与非目标

**背景**：当前意图识别把多意图坍缩成单赢家、静默丢弃次诉求（ID-04）。档位 A 是 ID-04 的最小安全修复：**识别出用户一句话里的多个诉求并保留下来，但本 turn 只推进安全的 read 前缀，其余步（尤其 draft/action/审批）记为"待确认的后续步骤"呈现给用户，不自动执行。**

**目标**：
- 语义层能产出一个**有序意图计划**（TaskPlan，1~N 步），N=1 时完全退化为现状。
- 规范化：修饰型折进主步骤、并列同意图合并、非法计划 fail-closed。
- 本 turn 只执行"计划里从头开始、连续的 read 类安全前缀"；第一个非 read 步及其之后，全部记为 `deferred_steps`。
- 最终回复向用户显式呈现 deferred_steps（"我还注意到你想 X / Y，要我接着做吗"），不静默丢。
- 全程可回放：TaskPlan、被执行前缀、deferred_steps 写进 classification_trace。

**非目标（做了算越界，一票 blocker）**：
- **不做自动依赖执行链**（read→draft 自动跑属档位 B，禁止）。本 turn 除 read 前缀外不执行任何 step。
- 不改现有单意图路由语义：N=1 时 `primary_intent`/`requested_operation`/`risk_tier`/`route_decision` 必须与现状逐字节等价。
- 不引入 DAG/环、不引入并行执行、不引入 resume/中断（属档位 C）。
- 不改 `IntentResultV3` wire schema、不改 `docs/contract-spec.md`、不改 `src/agent/prompts.py` few-shot（除非发现冲突，停下报告）。
- 不引入外部 LLM 新调用做"计划分解"——计划从**现有单次 LLM 输出的 primary+secondary+operation**派生，不新增一次模型调用。
- 不做置信度校准（ID-02 仍 🔴）。
- 不引入 R0–R3 风险枚举——沿用 MOCA 现有 5 档 `RiskTierLiteral`。

**本档性质 = 在三层地基上，把语义层输出从"单意图"扩成"计划 + 待确认后续"，其余层与路由尽量不动。N=1 是绝对主路径，必须零行为变化。**

## 1. 现状事实（Codex 可直接用，不必重新摸）

- `src/agent/state.py:55` `AgentState(TypedDict, total=False)` —— 加字段安全。现有相关字段：`primary_intent`/`requested_operation`/`risk_tier`/`secondary_intents`/`active_flow_state`/`clarification_request`。
- `src/agent/intent_policy.py`：三层已拆分——`resolve_semantic_intent(...) -> SemanticIntent`、`resolve_risk_decision(...) -> RiskDecision`、`decide_clarification(...) -> ClarificationDecision`。`arbitrate_intent` 已修 ID-01。`SemanticIntent` 字段：intent/operation/entities/raw_confidence/keyword_signals/arbitration。
- `src/agent/nodes/classify_intent.py`：`intent_result_to_state(...)` 是 LLM 路径编排点，已调用三层并写 `semantic_intent`/`risk_decision`/`clarification_decision` 进 trace。`_deterministic_classification_update(...)` 是活跃槽位续接路径。
- `src/agent/routing.py`：`route_after_intent` / `route_after_slots` 消费**单个** effective intent + risk_tier；`INTENT_ROUTES = {clarification_gate, final_response, investigate, session_memory_load}`。**路由本次不改逻辑**，读的字段名不能变。
- `src/agent/nodes/clarification_gate.py`：已有 `missing_required_slots` 澄清机制。**deferred_steps 与它是两回事**，不要混用同一字段/reason。
- `IntentResultV3`（`schemas.py:63+`）：primary_intent/requested_operation/confidence/secondary_intents/candidate_slots/... —— wire schema，勿改。
- 现有意图测试（必须全绿，是 N=1 行为等价的回归网）：
  `tests/agent/test_intent_adapter.py`、`test_intent_policy_registry.py`、`test_intent_golden_contract.py`、`test_intent_routing.py`、`tests/agent/test_nodes/test_classify_intent.py`、`tests/agent/test_graph.py`、`tests/architecture/test_phase32_static_contract.py`。

## 2. 要新增的数据契约

在 `src/agent/intent_policy.py` 新增两个 frozen dataclass（与三层契约放一起）：

```
@dataclass(frozen=True)
class TaskStep:
    step_id: str                      # "s1"/"s2"... 稳定可读
    intent: IntentLiteral
    operation: RequestedOperationLiteral
    entities: Mapping[str, Any]       # 该步的槽位/实体
    depends_on: tuple[str, ...]       # 依赖的 step_id（A 阶段只记录，不用于自动执行）
    relation: Literal["root", "dependency", "modifier", "parallel"]

@dataclass(frozen=True)
class TaskPlan:
    steps: tuple[TaskStep, ...]
    terminal_step_id: str             # 用户真正的终点交付物那一步
```

约束：
- N=1 时 `steps` 恰含一步，`relation="root"`，`terminal_step_id` 指向它，`depends_on=()`。**此时下游一切等价现状。**
- `modifier` 关系的步**不进 steps**（在规范化阶段折进被修饰步），所以 steps 里不会出现 relation="modifier"。该枚举值保留给 trace 记录"某段被判为修饰"用，不落进最终 steps。
- 步数上限 **3**。规范化后 >3 步 → 判为非法计划 → fail-closed（见 §3）。

## 3. 计划构建与规范化（确定性，禁新增 LLM 调用）

来源：现有单次 LLM 输出的 `primary_intent + secondary_intents + requested_operation + candidate_slots`，叠加 `derive_keyword_signals` 已有结果。**不新增模型调用。**

`build_task_plan(semantic, result, query) -> TaskPlan | None` 规则：
1. **主步**：三层 `arbitrate_intent` 选出的 effective intent/operation 作为 root step（s1），terminal 默认指向它。
2. **候选次步**：从 `secondary_intents` 中，排除掉被判为**修饰型**的（判定见下），其余每个成为一个 `dependency` 或 `parallel` 步。
3. **修饰型折叠（白名单，A 阶段保守）**：次意图**必须命中下表之一**才折叠/丢弃，其余**一律当独立步**。拿不准 → 一律独立步（失败朝"多一个受控步"，不朝"少一个步"，见 ID-04 资损硬约束）。

   | 次意图 | 条件 | 处理 | trace 记号 |
   |---|---|---|---|
   | `complaint_escalation` | 主步 intent ∈ {compensation_suggestion, refund_troubleshooting, ticket_reply_draft, order_status_inquiry, policy_qa}（即主步本身不是升级） | 折叠为修饰（不单独成步），其"抬风险"效果若已被 arbitrate/risk 层吸收则不重复施加 | `modifier_folded:complaint_as_severity` |
   | `small_talk` | 任意 | 丢弃，不成步 | `modifier_dropped:small_talk` |
   | 其余全部 | —— | **禁止折叠，当独立步** | —— |

   **依据**：`complaint_escalation` 作为次意图在客服语境多数是情绪/严重性修饰（用来抬风险档、影响话术），真正要升级时它会是**主**意图。few-shot 里唯一的 secondary 组合正是 compensation 主 + complaint 次（`prompts.py:30-31`）。⚠️ 注意：本白名单除该条 few-shot 外**无其他样例支撑，属推测性扩充**，需靠 A 上线后的数据/eval 验证收窄或放宽。

   **禁止折叠项（显式，防越界）**：`order_status_inquiry` / `refund_troubleshooting` / `policy_qa` 作次意图是**能独立交付的查询**，`ticket_reply_draft` / `compensation_suggestion` / `appeal_or_unban` / `action_request` 作次意图是**独立交付物或写动作**（后三者 high_risk）——这些一律当独立步，折叠它们=用修饰机制静默吞诉求或藏高危步，直接违反 ID-04 资损硬约束。

   **安全网（complaint 折叠不留无痕）**：命中 `modifier_folded:complaint_as_severity` 时，**必须在最终回复里留一条可见记录**（如"已按'投诉情绪'处理本次诉求，如需正式升级请告知"），使判错时用户有一句话能纠正，诉求不至于彻底消失。这条与 §5 的 deferred 呈现并列，即使 deferred 为空也要出现。
4. **并列同意图合并**：同 intent 多实体合并为一步多 entities。
5. **关系判定（A 阶段轻量版）**：次步 operation 消费主步产物（如 draft_reply 跟在 read 后）标 `dependency`；否则标 `parallel`。A 阶段该字段只记录、不驱动执行。
6. **校验 fail-closed**：步数 >3、intent 非法、terminal 不在 steps 内 → 返回 `None`。调用方遇 `None` 时**退回现状单意图路径**（用 s1/现有 effective 值），并在 trace 记 `plan_invalid_fallback_single`。

关键：**规范化后若只剩 1 步，等价现状，后续全部走老路径。**

## 4. 执行语义（A 阶段：只跑 read 前缀）

在 `classify_intent` 产出后、进入现有路由前，计算：
- `executable_prefix` = 从 s1 起、连续的、operation ∈ {read_status} 的最长前缀（advise 视情况归入只读——**以现有 `resolve_risk_decision` 判 tier == "read_only" 为准**，不自己硬编码 operation 列表）。
- `deferred_steps` = executable_prefix 之后的所有步。
- **本 turn 的 effective 单意图 = executable_prefix 的最后一步**（若前缀为空则 = s1），写进 `primary_intent`/`requested_operation`/`risk_tier`，**使现有路由/investigate/clarification 链原样工作**。
- `deferred_steps` 非空时：写入 `AgentState` 新增字段 `deferred_steps`（list[dict]），并在最终回复阶段呈现。**A 阶段不改路由目标去自动执行它们。**

硬约束（资损）：
- deferred_steps 里任何 draft_action/execute_action/escalate 步，**本 turn 绝不执行**，只呈现。
- executable_prefix 只允许 `resolve_risk_decision().tier == "read_only"` 的步；任何非 read_only 步都进 deferred，即使它排在最前（即前缀可能为空，此时退回：本 turn 就处理 s1 一步，其余 deferred）。

## 5. 状态与呈现

- `AgentState` 新增（total=False，安全）：`task_plan: dict | None`、`deferred_steps: list[dict]`。
- `classification_trace` 新增：`task_plan`（序列化）、`executable_prefix`（step_id 列表）、`deferred_steps`、`plan_normalization`（folded/fallback 记录）。
- 最终回复：deferred_steps 非空时，回复末尾追加确认句式（中文），列出被推迟的诉求，问用户是否继续。**具体措辞 Codex 可定，但必须逐条列出 deferred 的意图，不得静默丢弃。**
- **complaint 折叠安全网**：trace 命中 `modifier_folded:complaint_as_severity` 时，回复必须另留一条可见记录（如"已按'投诉情绪'处理本次诉求，如需正式升级请告知"）。**此记录独立于 deferred 呈现，deferred 为空时也要出现。**

## 6. 必须新增的测试

放 `tests/agent/`（不依赖 DB）：
1. **N=1 等价**：单意图输入，`task_plan.steps` 恰 1 步，且 `primary_intent`/`requested_operation`/`risk_tier`/`route_decision` 与关闭多意图路径逐字段相同。
2. **依赖型双步**："查退款卡哪+拟回复" → 2 步、s2 relation=dependency、executable_prefix=[s1]、deferred=[s2]、s2 本 turn 未执行。
3. **修饰型折叠 + 安全网**："投诉严重给多少补偿券" → 1 步（compensation），complaint 未成步、trace 记 `modifier_folded:complaint_as_severity`，risk tier=suggest_action（沿用现有）；断言最终回复含 complaint 安全网可见记录。
4. **独立查询不折叠（白名单边界）**：主步 + 次意图 ∈ {order_status_inquiry / refund_troubleshooting / policy_qa} 的组合 → 次意图**必须成独立步**，不得折叠（防止扩充白名单误伤能独立交付的查询）。
5. **资损硬约束**："查订单+直接退款" → execute step 进 deferred，本 turn 不执行，回复呈现待确认。
6. **fail-closed**：造 >3 步或非法计划 → 退回单意图路径 + trace 记 plan_invalid_fallback_single。
7. **deferred 不静默丢**：断言 deferred_steps 非空时最终回复文本包含被推迟意图的可见提示。
8. **small_talk 次意图丢弃**：主步 + small_talk 次意图 → small_talk 不成步、trace 记 `modifier_dropped:small_talk`，不影响主步。

## 7. 验证命令（遵守 MOCA 禁裸 pytest 硬规则）

```
uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q
uv run ruff check src/agent tests/agent
```
需要缓存目录时用 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`。禁止裸 `pytest` / 裸 `python -m pytest`。

## 8. Claude 收尾复核清单（Codex 不必做，Claude 核对用）

1. N=1 路径逐字段等价现状（拿现有 6 个测试文件全绿 + 抽查 trace）。
2. 无新增 LLM 调用（grep 计划构建路径，确认只用既有 result 派生）。
3. deferred_steps 里的 draft/action/escalate 本 turn 确未执行（看执行/路由代码路径，不只看测试）。
4. executable_prefix 的"只读"判定走 `resolve_risk_decision().tier=="read_only"`，未自己硬编码 operation 白名单绕过风险层。
5. 修饰折叠是保守白名单，拿不准朝"多一个受控步"（不朝少一步）。
6. fail-closed 分支真的退回单意图，不是抛异常或吞掉。
7. 无越界：无自动依赖执行、无 DAG/并行/resume、未改 IntentResultV3/spec/prompts。
8. deferred 非空 → 回复确有可见呈现（不静默丢，ID-04 核心验收点）。

## 9. Scope 锁（一票 blocker）

- 出现"read→draft/action 本 turn 自动执行" = 越界到档位 B，blocker。
- 新增任何 LLM 调用 = blocker。
- N=1 行为发生任何可观测变化 = blocker。
- 引入 R0–R3 或改 5 档 tier = blocker。
- 改 IntentResultV3 / contract-spec / prompts few-shot = blocker（除非发现冲突，停下报告，不自行改）。
