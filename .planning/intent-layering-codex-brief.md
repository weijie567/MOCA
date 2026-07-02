# Codex 执行规格：意图识别三层解耦（契约拆分）

> 本文件是交给 Codex 的实现规格，等价于一次 PLAN 的 must-haves + 验收标准。
> Claude 是设计者/裁决者，Codex 实现，Claude 按本文「验收标准」拿真实代码核对。
> 关联台账：`.planning/ARCHITECTURE-DEBT.md` 第 2 节 ID-01/02/03/04 与 ID-DESIGN。
> **本次只做「三层解耦 + 显式契约」，不做多意图 TaskPlan（那是后续独立 phase）。**

## 0. 目标与非目标

**目标**：把意图识别当前混在一起的三段职责，拆成三个单向、可单测、只通过显式数据契约通信的层：
- **[1] 语义理解层**：只答「用户想干什么」——产出 effective intent/operation + 实体 + 原始置信度 + 关键词证据 + 仲裁记录。不含风险、不含路由。
- **[2] 风险授权层**：只答「当前身份/渠道下允许做到哪一步」——产出 risk_tier + evidence_required + approval_required，**只认一张声明式策略表**。
- **[3] 置信/澄清层**：只答「够不够确定、要不要反问」——产出 requires_clarification + reason。

**非目标（本次明确不做，做了算越界）**：
- 不引入多意图 / TaskPlan / DAG / 计划执行器（后续 phase）。
- 不改 `IntentResultV3` wire schema，不改 `src/agent/prompts.py` 的 few-shot。
- 不做 confidence 校准的真实实现（只在层 [3] 预留 `calibrated_confidence` 入参位，值仍取现状来源）。
- 不改变任何**对外可观测行为**（见 §5 行为等价硬约束）。
- 不改 `docs/contract-spec.md`（除非发现 spec 与实现冲突，停下报告，不自行改）。

**这次解耦的性质 = 行为等价的结构重构 + 把「谁说了算」从涌现行为提成显式代码。** 现有意图测试必须全绿。

## 1. 现状事实（Codex 不必重新摸，可直接用）

- `src/agent/intent_policy.py`
  - `resolve_intent_precedence(primary, operation, query, secondary)` 行 425-467：**层[1] 的仲裁**当前在这里，且混了关键词扫描（`"投诉"/"升级"/"申诉"/"reply"` 等 in query）往候选池追加意图，`for intent in PRECEDENCE_INTENTS: if intent in valid_candidates: return intent` 单赢家收敛。这是 ID-01 的所在。
  - `confidence_requires_clarification(primary, operation, confidence, pre_route)` 行 470-490：**层[3]**，双阈值 0.65 / 0.85。
  - `resolve_risk_tier(primary, operation, role, channel, routing_hints)` 行 493-524：**层[2]**，if-elif 链；行 521 是死分支（两侧都返回 `approval_required`），本次顺手消除。
  - `IntentPolicyRegistry`（行 ~152）已是 read-only facade，聚合了 `resolve_risk_tier` / `resolve_precedence`。`INTENT_POLICY_REGISTRY` / `SLOT_POLICY_REGISTRY` 是模块级单例。
  - `detect_pre_route(...)` 产出 `PreRouteDecision`（安全嗅探），是层[1] 之前的确定性前置，**保留不动**。
- `src/agent/nodes/classify_intent.py`
  - `intent_result_to_state(result, prior_llm_outputs, pre_route)`（adapter，行 ~124-262）：把 `IntentResultV3` + pre_route 组装成 state update，内部依次调用 precedence→risk_tier→route_after_intent，并写 `classification_trace` / `eval_metadata`。**这是三层当前实际被串起来的编排点。**
  - `_deterministic_classification_update(...)`（行 ~314-361）：活跃槽位续接路径（绕过 LLM），也调用 resolve_risk_tier + route_after_intent。
- `src/agent/schemas.py`：`IntentResultV3`（行 63+，字段 primary_intent/requested_operation/confidence/calibrated_confidence/secondary_intents/required_slots/candidate_slots/routing_hints/reason_codes 等），`RiskTierLiteral`（行 30+）。**wire schema，勿改。**
- `src/agent/routing.py`：`route_after_intent(update)`，消费 effective intent + risk_tier + routing_hints 做路由。**路由属层外，本次不改其逻辑**，但它读的 state 字段名不能变。
- 现有测试（必须保持绿，是行为等价的回归网）：
  `tests/agent/test_intent_adapter.py`、`test_intent_policy_registry.py`、`test_intent_golden_contract.py`、`test_intent_routing.py`、`tests/agent/test_nodes/test_classify_intent.py`、`tests/architecture/test_phase32_static_contract.py`。

## 2. 三层契约（Codex 需新增的显式数据结构）

三个层各自输出一个 frozen dataclass（放 `src/agent/intent_policy.py` 或新建 `src/agent/intent_layers.py`，Codex 自选，但三层与编排必须清晰可辨）。字段名是契约，需按下面命名：

### [1] 语义层输出 `SemanticIntent`
```
SemanticIntent(frozen):
    intent: IntentLiteral            # 仲裁后的 effective intent
    operation: RequestedOperationLiteral
    entities: Mapping[str, Any]      # 来自 candidate_slots，勿新解析
    raw_confidence: float | None     # LLM 自报 confidence 原值
    keyword_signals: tuple[str, ...] # 关键词命中的意图候选（作为独立证据，不是结论）
    arbitration: tuple[str, ...]     # 仲裁 reason_codes（如 intent_precedence_applied）
```
**关键要求（修 ID-01）**：把「关键词扫描产出候选」与「在候选中按优先级选赢家」显式拆成两个函数：
- `derive_keyword_signals(query) -> tuple[intent,...]`：只扫关键词、只产候选，**不做任何选择**。
- `arbitrate_intent(llm_primary, llm_secondary, keyword_signals, raw_confidence) -> (intent, operation, arbitration_codes)`：唯一决定赢家的地方，**仲裁规则写成显式可读分支**，且必须落一条明确规则：
  > 关键词候选只有在「LLM 自身也把该意图列进了 primary/secondary」**或**「raw_confidence 低于层[3] 的普通阈值」时，才可覆盖 LLM primary；否则以 LLM primary 为准。
  这条规则要有专门单测（见 §4）。本次**允许**因此改变一个具体行为：`"这个不算投诉吧，我就是问下退款进度"` 类 query 不再被误抬成 complaint_escalation——这属于**有意的行为修正**，需在该 case 上新增断言，且在 §5 豁免清单登记。

### [2] 风险层输出 `RiskDecision`
```
RiskDecision(frozen):
    tier: RiskTierLiteral
    evidence_required: bool
    approval_required: bool
    reason_codes: tuple[str, ...]
```
**关键要求（修 ID-03）**：新增一张声明式策略表（module-level 常量，如 `RISK_POLICY_TABLE`），键为 `(operation, intent_class 或 "*", channel_class)`，值为 `RiskDecision` 模板。`resolve_risk_tier` 改为「查表 + 少量确定性兜底」，删除行 521 死分支。表必须能被单测逐行覆盖。**tier 的取值集合、每个 (intent,operation,channel) 组合的结果必须与当前 `resolve_risk_tier` 逐一等价**（这是行为等价约束，见 §5），本次只换实现形态不换结论。

### [3] 澄清层输出 `ClarificationDecision`
```
ClarificationDecision(frozen):
    requires_clarification: bool
    reason: str | None
    threshold_applied: float | None   # 实际生效的阈值，便于 trace/校准
```
**关键要求（为 ID-02 铺路，但本次不实现校准）**：签名新增 `calibrated_confidence: float | None = None` 入参**位**，当前传入值仍是现状来源（未校准）；逻辑先保持与 `confidence_requires_clarification` 等价。仅把「阈值决策」独立成层、并在输出里暴露 `threshold_applied`，供将来接校准。**不得改变当前澄清与否的判定结果。**

## 3. 编排与单向数据流（硬要求）

- 新增一个显式编排函数（如 `classify(llm_result, pre_route, context) -> (SemanticIntent, RiskDecision, ClarificationDecision)`），三层**严格单向**：[1] 不读风险/路由；[2] 只吃 `SemanticIntent` + 身份/渠道，不知道分类怎么来的；[3] 只吃 [1] 的 confidence + [2] 的 tier。
- `intent_result_to_state` 和 `_deterministic_classification_update` 改为**调用编排函数**再落 state，不再各自内联三段逻辑。
- `classification_trace` 必须记全三层各自的输出（含 `arbitration`、`RiskDecision.reason_codes`、`threshold_applied`），使「最终意图是 LLM 定/关键词抬/策略表压」可回放。
- `IntentPolicyRegistry` 现有方法签名**保持向后兼容**（`resolve_risk_tier`/`resolve_precedence` 可内部改为委托新层，但对外签名与返回类型不变），避免打穿现有 facade 调用方。

## 4. 必须新增的单测（行为锁 + 新契约锁）

- 层[1]：`derive_keyword_signals` 只产候选不选择；`arbitrate_intent` 覆盖规则——(a) 关键词与 LLM 一致时抬升、(b) 高置信 LLM + 无关联关键词时**不**被覆盖（含"这个不算投诉吧"case）、(c) 低置信时关键词可抬升。
- 层[2]：`RISK_POLICY_TABLE` 对当前 `resolve_risk_tier` 做**逐组合等价性**参数化测试（遍历 intent × operation × {ordinary_chat, 非chat} × 关键 routing_hints），断言新旧结论一致；单列一条断言行 521 死分支已消除且结果不变。
- 层[3]：普通/安全敏感双阈值边界（0.64/0.65/0.84/0.85）判定与旧函数一致；`threshold_applied` 被正确暴露。
- 编排：单向性结构测试（如层[2]/[3] 函数签名不含 query/关键词入参，防止职责回流）。

## 5. 行为等价硬约束 + 豁免清单

- **默认**：所有现有意图测试（§1 末列表）必须全绿，不改断言。
- **唯一允许的行为变化**：ID-01 仲裁修正导致的「关键词不再无条件覆盖高置信 LLM」。凡因此变化的 case，必须：(a) 新增/更新断言明确新行为；(b) 在本节豁免清单登记 query + 旧结论 → 新结论 + 理由。
- 豁免清单（Codex 实现时如实填写）：
  - `"这个不算投诉吧，我就是问下退款进度"`：旧 = complaint_escalation（关键词命中"投诉"）→ 新 = refund_troubleshooting（LLM 高置信且未列 complaint）。理由：ID-01 仲裁规则。
  - （其余如有，Codex 补）
- 若发现任何**无法保持等价**的风险层组合（新表与旧 if-elif 结论不一致且非死分支），**停下报告 Claude**，不擅自改结论。

## 6. 验证命令（MOCA 硬规则，禁裸 pytest）

```
uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py \
  tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py \
  tests/agent/test_nodes/test_classify_intent.py tests/architecture/test_phase32_static_contract.py -q
uv run ruff check src/agent tests/agent
```
DB-backed 套件若因本地 PostgreSQL 未启动而报 fixture 连接错，按仓库惯例记入 `.planning/LOCAL-VALIDATION-ISSUES.md`，不算产品代码失败。

## 7. Claude 收尾复核清单（实现后由 Claude 执行，Codex 无需做）

1. 三层是否真单向：grep 层[2]/[3] 的实现，确认不含 query/关键词/路由入参（职责无回流）。
2. `arbitrate_intent` 的覆盖规则是否显式成文且有 (a)(b)(c) 三个 case 锁定；"不算投诉"case 是否真的翻正。
3. `RISK_POLICY_TABLE` 逐组合等价测试是否存在且通过；行 521 死分支是否消除。
4. `IntentResultV3` / `prompts.py` / `docs/contract-spec.md` 是否零改动（`git diff` 确认）。
5. `classification_trace` 是否记全三层输出、可回放。
6. 豁免清单是否与实际行为变化一一对应，无未登记的静默行为漂移。
7. 是否越界碰了多意图/TaskPlan（本次禁止）。
