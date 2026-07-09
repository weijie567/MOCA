---
phase: 63
reviewers: [claude]
reviewed_at: "2026-07-10T02:24:00+08:00"
plans_reviewed:
  - 63-01-PLAN.md
  - 63-02-PLAN.md
  - 63-03-PLAN.md
  - 63-04-PLAN.md
  - 63-05-PLAN.md
---

# Cross-AI Plan Review — Phase 63

## Claude Review

## Summary

Phase 63 的 5 个计划整体方向是对的：先建立 canonical taxonomy，再分别迁移 `risk_gate`、`action_draft`、`intent_policy/routing`，最后用静态漂移测试和架构债务台账收口。计划基本覆盖了 Phase 63 的三个成功标准：统一 action taxonomy、拆分 risk severity / disposition、确保路由侧和执行侧使用同一套安全词汇。测试命令均使用 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`，符合 MOCA 规则。主要风险不在大方向，而在几个接口契约和执行边界：63-01 定义的 helper surface 不足以支撑 63-02 / 63-04 的具体迁移；63-02 对 `manual_review` / `blocked` 的 severity 映射过于固定，可能丢失原始严重度语义；63-04 的 action alias 迁移需要更强的 hard-negative 测试，避免把政策问答误判成动作请求；63-05 的 `files_modified` 与实际 summary / optional validation log 输出不完全一致。

---

## Strengths

### 1. Plan split 合理，符合 phase 级跨边界拆分

5 个计划按边界拆开：

- 63-01：taxonomy owner foundation
- 63-02：risk gate producer 迁移
- 63-03：action draft / ToolPlatform boundary 迁移
- 63-04：intent / routing safety policy 迁移
- 63-05：drift guard + closeout

这符合 Phase 63 横跨 safety policy、action draft、intent routing、approval compatibility 的复杂度，也符合项目对 phase-level plan 拆分的要求。

### 2. TDD 顺序清楚

每个实现计划都先写 RED tests，再改生产代码。尤其是：

- 63-01 先 pin taxonomy helper API 和 alias / disposition 行为。
- 63-02 先把 `risk_level in {"manual_review", "blocked"}` 类断言迁移到显式 `risk_disposition`。
- 63-03 先改 legacy freeform reject/no-support 测试，要求不再把 `manual_review` 传入 ToolPlatform。
- 63-04 先用 source inspection 捕获 `_ACTION_BOUND_INTENTS`、`english_action_terms`、`chinese_action_terms` 的移除。
- 63-05 最后加 static drift guard。

这个顺序能降低语义迁移时的回归风险。

### 3. 安全边界保护明确

计划反复强调：

- `manual_review` / `blocked` 是 disposition，不是 executable action。
- LLM risk output 只是 advisory，后端 deterministic policy 仍是安全决策源。
- `action_draft` 必须在 ToolPlatform 前拒绝 non-executable disposition。
- 不引入 real external execution、新 write tools、ActionService broad allowlist、DB/state-machine hardening。

这些边界和 Phase 63 的 scope 很匹配。

### 4. 兼容性意识较好

计划没有直接把 `RiskDecisionV1.risk_level` 改成 enum，也没有要求数据库迁移或历史 backfill。63-02 明确要求 legacy `RiskDecisionV1.risk_level="manual_review"` 仍能 validate，同时新 risk-gate 输出使用 severity-only `risk_level`。这是比较稳妥的兼容路径。

### 5. 验证命令符合 MOCA 规则

计划中的 pytest 命令均使用：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
```

没有 bare `pytest` 或 bare `python -m pytest`。这点符合项目约束。

---

## Concerns

### HIGH — 63-01 暴露的 taxonomy helper surface 不足以支撑后续计划

63-02 要求：

- 在 `_deterministic_rule_match` 中使用 registry 的 full-refund alias helper。
- 替换 local `FULL_REFUND_TERMS`。
- 用 taxonomy 辅助判断 full refund / partial refund / refund / coupon。

63-04 要求：

- `_has_compensation_action_cue` 使用 taxonomy alias data。
- 保留 policy-rule hard negatives。
- `detect_pre_route` 使用 `detect_pre_route_action_request(query)`。

但 63-01 Task 1 / Task 2 明确要求的 public helper 名单主要是：

- `canonical_executable_action_type`
- `resolve_action_text`
- `is_executable_action_type`
- `is_actionable_recommendation`
- `detect_pre_route_action_request`
- `normalize_risk_vocabulary`
- `risk_assessment_with_disposition`

这里没有明确提供：

- full refund alias matcher，例如 `matches_full_refund_alias(...)`
- compensation/coupon alias view，例如 `compensation_action_terms()` 或 `matches_compensation_alias(...)`
- generic alias read-only views，例如 executable aliases / pre-route aliases / disposition aliases
- routing-safe cue matcher，能区分 “compensation policy question” 与 “compensation action request”

结果是：63-02 / 63-04 执行时可能被迫临时扩展 63-01 API，或者在调用方重新写局部 tuple，反而破坏 Phase 63 的目标。

**建议：**在 63-01 的 must_haves 和 Task 2 中补齐稳定 API，例如：

- `action_aliases_for(action_type: str) -> frozenset[str]`
- `pre_route_action_aliases() -> Mapping[str, tuple[str, ...]]`
- `matches_full_refund_alias(text: str) -> bool`
- `matches_compensation_alias(text: str) -> bool`
- `resolve_action_text(...)` 返回 `matched_alias` / `matched_action_type` / `disposition` / `match_kind`

这样 63-02 / 63-04 不需要再发明 caller-local helper。

---

### HIGH — 63-02 固定把 `manual_review` 映射为 medium、`blocked` 映射为 high，可能丢失 severity 语义

63-02 要求：

- manual review -> `risk_level="medium"`, `risk_severity="medium"`, `risk_disposition="manual_review"`
- blocked/refuse -> `risk_level="high"`, `risk_severity="high"`, `risk_disposition="blocked"`

这能保证 `risk_level` 不再写入 `manual_review` / `blocked`，但也有风险：`manual_review` 是 routing disposition，不一定意味着 severity 必然是 medium。某些 manual-review 路径可能来自高金额、高风险但需要人工复核，而不是自动阻断。固定 medium 可能让后续 reason codes、audit、approval display 或 analytics 低估风险。

**建议：**

把 63-02 的 mapping 改成更精确的规则：

- 如果已有合法 severity `low|medium|high`，保留原 severity。
- 如果 legacy `risk_level=="manual_review"` 且没有其他 severity，fallback 到 `medium`。
- 如果 `blocked=True` / verifier route `refuse`，默认 `high`。
- 如果 approval-required high-risk rule 已经判 high，即使 disposition 是 `manual_review`，也保留 `high`。
- 测试增加一条：`risk_level="high"` + disposition manual_review 时，新输出保持 `risk_severity=="high"`，不被降成 medium。

这样既能保持 compatibility，又不丢掉安全严重度。

---

### MEDIUM — 63-02 对 `risk_level` 兼容字段的输出策略还需要更明确

63-02 的 truths 写：

> Legacy `risk_level` remains populated with valid severity strings for compatibility.

但 `RiskDecisionV1.risk_level` 本身是 legacy compatibility string，现有持久化/API payload 可能已经包含非 severity 值。计划里同时要求：

- legacy strings 仍可 validate
- new risk-gate decisions 不再 emit manual_review / blocked
- reason codes include semantic disposition

这个方向对，但还缺一个清晰的 contract：

- `risk_assessment.risk_level` 是否从 Phase 63 开始永远 severity-only？
- `risk_decision.risk_level` 是否新写入也永远 severity-only？
- `risk_decision.reason_codes` 中 disposition 用什么标准格式？`risk_disposition:manual_review` 还是 `manual_review`？
- `approval_plan` / `auto_allowed_binding` 中是否需要复制 `risk_disposition`？

**建议：**在 63-02 Task 2 增加一段 explicit compatibility contract：

- New `risk_assessment["risk_level"]` = severity only。
- New `risk_assessment["risk_severity"]` = same severity。
- New `risk_assessment["risk_disposition"]` = routing outcome。
- New `RiskDecisionV1.risk_level` = severity only。
- `RiskDecisionV1.reason_codes` includes `risk_severity:<value>` and `risk_disposition:<value>` 或等价稳定格式。
- Legacy `RiskDecisionV1.model_validate(...)` 继续接受 arbitrary non-empty `risk_level`。

---

### MEDIUM — 63-03 新 error code 可能成为隐式 contract，计划未说明响应兼容

63-03 引入：

- `NON_EXECUTABLE_ACTION_DISPOSITION`
- `NON_EXECUTABLE_ACTION_TYPE`

这在安全上合理，但 action_result error code 往往会被 console timeline、tests、debug logs 或 API consumers 依赖。计划没有说明这些 error code 是否是内部-only、是否需要 console 显示映射、是否需要 final_response fallback。

**建议：**

在 63-03 增加 acceptance：

- error shape 与现有 `VERIFIER_NOT_ALLOW` / `AUTO_ALLOWED_BINDING_REQUIRED` 一致。
- error message 不泄露内部 taxonomy 细节。
- `trace_steps[-1]` 包含 `node="action_draft"`、`status="error"`、`tool_name` 是否为空/缺省要稳定。
- 不创建 `action_draft` / `draft_outcome`。
- 如果当前 final response pipeline 会读取 `action_result.error.error_code`，补一条测试或明确不属于本计划。

---

### MEDIUM — 63-04 的 action alias 迁移容易误伤 policy QA / compensation policy hard negatives

63-04 要把 `_has_compensation_action_cue` 的 compensation/coupon terms 迁到 taxonomy。风险是：共享 alias 越强，越容易把 “询问补偿规则” 判成 “请求创建补偿动作”。

计划保留了三条 hard negatives：

- `通过订单号 ORD-1 查询退款状态`
- `通过规则判断是否要补偿`
- `accept language preference`

但 Phase 63 涉及中英混合 alias，建议 hard-negative 覆盖再加几类：

- “补偿规则是什么”
- “什么情况下可以发券”
- “coupon policy for late delivery”
- “should we compensate under policy”
- “how much compensation is allowed by rule” 这类读规则/建议边界句

否则 taxonomy alias 改动可能让政策问答更频繁地进入 action_request 路由。

**建议：**63-04 Task 1 增加中英文 hard-negative 和 positive 对照：

- Positive：`请对 ORD-1 直接退款`、`refund now`、`发券给商家`
- Negative：`查询退款状态`、`补偿规则是什么`、`what is the coupon policy`、`通过规则判断是否要补偿`

---

### MEDIUM — 63-04 对 fail-closed registry exception 的描述偏抽象

63-04 要求：

> Preserve fail-closed behavior if registry calls raise or return invalid values: default to evidence required / action-bound true where safety would otherwise be weakened.

这是好目标，但实现上容易产生副作用：如果 `_policy_evidence_required` 对所有 registry exception 都返回 true，可能把 direct response / unsupported / metric query 误送入 evidence path，影响 UX；如果 `_action_bound_or_high_risk` 对所有 exception 都 true，可能把普通 read-only routing 推向 risk gate。

**建议：**

明确 fail-closed 策略分层：

- Unknown intent：`requires_evidence=True` 是合理的。
- Registry exception：route helper 可返回 safe default，但要加 reason code / test，避免静默。
- Direct-response intents：仍优先由 `_route_after_contextual_intent` 或 registry route policy 处理，不应因为 `_policy_evidence_required` fallback 被强制证据化。
- 测试加一条 fake registry raises 的 case，验证安全 fallback 是 clarification/risk gate，而不是 unsafe action path，也不是错误地执行 action。

---

### LOW — 63-01 的 “RED tests are committed” wording 与项目 Git 规则不一致

63-01 Task 1 `<done>` 写：

> RED parity tests are committed before production taxonomy implementation.

项目规则是不要主动 commit，除非用户明确要求。这里可能只是 GSD 模板语义，但对执行代理容易造成误导。

**建议：**改成：

> RED parity tests are written and observed failing before production taxonomy implementation.

避免触发不必要 commit。

---

### LOW — 63-05 `files_modified` 与实际输出不完全一致

63-05 frontmatter 写 `files_modified` 包含：

- `tests/architecture/test_safety_taxonomy_boundaries.py`
- `.planning/ARCHITECTURE-DEBT.md`
- `.planning/LOCAL-VALIDATION-ISSUES.md`

但计划本身说 `.planning/LOCAL-VALIDATION-ISSUES.md` 只有遇到真实 validation/debug failure 才更新。把它放进 required files_modified 容易让执行者为了满足清单而写空/无事故记录。

同时 5 个计划都要求创建 `63-xx-SUMMARY.md`，但各计划 frontmatter 的 `files_modified` 没列 summary 文件。

**建议：**

- 把 `.planning/LOCAL-VALIDATION-ISSUES.md` 标为 optional / conditional，不放入 required `files_modified`。
- 每个计划的 `files_modified` 加上对应 summary，例如：
  - `.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-01-SUMMARY.md`
  - ...
- 或单独加 `outputs:` 字段区分 implementation files 与 generated summary artifacts。

---

### LOW — 63-05 drift guard 对 `manual_review` / `blocked` 的检查需要避免误报

63-05 已经说明不要 broad scan generic words like `manual_review`，这是正确的。但 Test 5 写：

> `manual_review` and `blocked` may appear as compatibility values/tests but cannot appear inside executable action owner sets outside the taxonomy owner.

这个静态检查如果用文本 grep 很容易误报；如果用 AST，也要精确定位 set/list/dict assignment 的变量名和上下文。

**建议：**

明确只检查这些模式：

- assignment name includes `ACTIONABLE`, `EXECUTABLE`, `ACTION_TYPES`, `WRITE_ACTIONS`
- local `_canonical_action_type` returning `"manual_review"` / `"blocked"` outside taxonomy
- `ToolPlatform` args / proposed_action construction中硬编码 `action_type="manual_review"` / `"blocked"`

不要禁止 reason codes、test fixtures、compatibility schema 中出现这些字符串。

---

## Suggestions

### Cross-plan improvement checklist

1. **补齐 63-01 taxonomy public API**
   - full refund alias matcher
   - compensation/coupon alias matcher
   - pre-route alias view
   - action alias read-only mapping
   - disposition alias mapping
   - stable `ActionResolution` fields：`executable_action_type`, `disposition`, `matched_alias`, `match_kind`

2. **调整 63-02 severity/disposition normalization**
   - 保留已有合法 severity，不要无条件把 manual_review 降为 medium。
   - blocked/refuse fallback high 可以保留。
   - reason codes 使用稳定 prefix，如 `risk_severity:high`、`risk_disposition:manual_review`。

3. **强化 63-03 error contract**
   - 明确 error shape、trace step、message、安全不泄露。
   - 新 error code 是否内部 contract，要通过测试固定。

4. **增强 63-04 hard-negative coverage**
   - 加中英文 compensation/coupon policy questions。
   - 加 fake registry exception 的 fail-closed test。
   - 确认 direct response / unsupported / metric intents 不被错误 evidence/action-bound 化。

5. **修正 63-05 artifact 清单**
   - summary 文件加入 outputs 或 files_modified。
   - `.planning/LOCAL-VALIDATION-ISSUES.md` 改为 conditional。
   - static drift guard 使用 AST 精确检查，避免扫普通 `manual_review` 字符串。

---

## Risk Assessment

**Overall risk level: MEDIUM**

理由：

- **方向风险低**：phase split、测试优先、taxonomy owner、disposition/executable separation 都符合 Phase 63 目标。
- **安全风险中等**：如果 63-02 severity normalization 过于固定，可能降低风险严重度表达；如果 63-04 action alias 迁移 hard negatives 不够，可能把政策问答误路由为动作请求。
- **兼容风险中等**：新 `risk_severity` / `risk_disposition` 字段、new action error codes、reason code 格式都需要更明确，否则容易出现下游测试或 console 行为漂移。
- **执行风险中等偏低**：计划使用 focused tests 和 `uv run` 命令，且不引入 DB migration / real execution；但 63-01 helper contract 不够完整，可能导致后续计划返工或临时扩 API。

如果按上面的建议补齐 helper surface、放宽 severity preservation、增强 routing hard-negative 测试，整体风险可以降到 **LOW-MEDIUM**。

---

## Consensus Summary

Only the requested Claude reviewer was run for this autopilot stage. Treat the concerns below as external-review findings requiring Codex adjudication before execution.

### Agreed Strengths

- Plan split, TDD order, safety boundary, compatibility stance, and MOCA test-entry compliance are sound according to the reviewer.

### Agreed Concerns

- HIGH: `63-01` taxonomy helper surface may be too narrow for `63-02` and `63-04`.
- HIGH: `63-02` severity/disposition mapping may discard existing severity when disposition is `manual_review`.
- MEDIUM: `63-04` needs stronger hard-negative coverage for policy/compensation questions and clearer fail-closed registry exception behavior.
- LOW: `63-05` should distinguish conditional local-validation logging from required modified files.

### Divergent Views

- No divergent views because only one external reviewer was requested and run.

---

## Claude Review Round 2

## Stance: CLEAN_WITH_LOW_RISK_NOTES

我没有发现需要在执行前修复的 blocker 或 warning。Round 1 接受的 findings 在修订后的 5 个 plan 中都已有明确 repair，并且大多被落成了可测试的 acceptance / RED test 要求。

## Repair Check

### 1. Helper surface completeness — Clean

`63-01-PLAN.md` 已补齐后续计划需要的 taxonomy helper surface：

- `action_aliases_for`
- `pre_route_action_aliases`
- `matches_full_refund_alias`
- `matches_compensation_alias`
- `ActionResolution.raw_value`
- `ActionResolution.executable_action_type`
- `ActionResolution.disposition`
- `ActionResolution.matched_alias`
- `ActionResolution.match_kind`

这足够支撑 `63-02 risk_gate`、`63-03 action_draft`、`63-04 intent_policy/routing` 迁移，避免 caller 重新定义局部 tuple 或 alias set。

### 2. Severity / disposition preservation — Clean

`63-02-PLAN.md` 已修复原先的 severity downgrade 风险：

- `manual_review` 保留已有合法 severity。
- 只有 legacy / absent severity 才 fallback 到 `medium`。
- `blocked/refuse` 明确为 high + blocked disposition。
- 新输出中 `risk_level` / `risk_severity` 为 severity-only。
- `risk_disposition` 承载 routing outcome。
- 增加 high-severity manual-review regression，防止降级成 medium。
- `RiskDecisionV1` legacy validation 继续兼容 arbitrary string。

这覆盖了 Round 1 的 HIGH finding。

### 3. Risk compatibility contract — Clean

`63-02` 现在明确：

- 新 `risk_assessment["risk_level"]` = severity only。
- 新 `risk_assessment["risk_severity"]` = same severity。
- 新 `risk_assessment["risk_disposition"]` = routing outcome。
- 新 `RiskDecisionV1.risk_level` = severity only。
- legacy `RiskDecisionV1.model_validate(...)` 继续接受旧字符串。
- reason codes 要包含 `risk_severity:<value>` 和 `risk_disposition:<value>` 或等价稳定格式。

兼容边界足够清楚。

### 4. Action-draft error contract — Clean

`63-03-PLAN.md` 已补上安全 error contract：

- `NON_EXECUTABLE_ACTION_DISPOSITION`
- `NON_EXECUTABLE_ACTION_TYPE`
- no ToolPlatform invocation
- no `action_draft`
- no `draft_outcome`
- error shape 与现有 action-boundary failures 对齐
- message 不泄露 taxonomy internals / alias list / tenant data
- final trace step 固定 `node="action_draft"`、`status="error"`、`tool_name` absent or empty

这足以避免新 error code 变成未定义的隐式 contract。

### 5. Compensation policy hard negatives — Clean

`63-04-PLAN.md` 已补强中英文 hard negatives：

- `补偿规则是什么`
- `什么情况下可以发券`
- `coupon policy for late delivery`
- `should we compensate under policy`
- `how much compensation is allowed by rule`

并保留 positive controls：

- `请对 ORD-1 直接退款`
- `refund now`
- `发券给商家`

这能覆盖 taxonomy alias 迁移后最容易误伤的 policy QA / compensation policy 问句。

### 6. Registry exception fallback — Clean, implementation-sensitive

`63-04` 已把原先抽象的 fail-closed 要求拆成较清楚的 layering：

- direct-response / unsupported intents 仍由 existing route policy 优先处理。
- unknown intent / registry exception 才进入 safe fallback。
- registry exception 必须产生 test-visible marker / safe reason。
- fallback 不得到 action execution。
- fake-registry-raises test 被列为 RED test。

这不是 plan blocker。执行时要小心别把所有 registry exception 都粗暴变成 action-bound true，计划已通过测试要求约束这个风险。

### 7. Conditional local-validation logging — Clean

`63-05-PLAN.md` 已把 `.planning/LOCAL-VALIDATION-ISSUES.md` 移到：

```yaml
conditional_files_modified:
  - .planning/LOCAL-VALIDATION-ISSUES.md
```

并明确只有真实 validation/debug failure 才追加记录。这个 repair 到位。

### 8. Drift guard precision — Clean

`63-05` 没有 broad grep `manual_review` / `blocked`，而是要求精确检查：

- assignment name includes `ACTIONABLE`, `EXECUTABLE`, `ACTION_TYPES`, `WRITE_ACTIONS`
- local `_canonical_action_type` returning `"manual_review"` / `"blocked"`
- ToolPlatform / proposed-action construction hardcoding `action_type="manual_review"` / `"blocked"`

并明确不禁止 reason codes、compatibility schemas/tests、safe error payload tests 中出现这些字符串。误报风险已被计划约束住。

### 9. MOCA test entrypoints — Clean

计划中的验证命令都使用：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...
```

没有发现 bare `pytest` / bare `python -m pytest` 入口问题。

### 10. Phase 64/65/66/67 scope boundaries — Clean

`63-05` 明确禁止引入：

- Phase 64 RAG risk label work
- Phase 65 trace / console label work
- Phase 66 config / demo hygiene
- real external execution
- new write tools
- broad DB / state-machine hardening

同时把 broader DB/status-machine CHECK hardening 记录为 Phase 67 deferral。scope boundary 清楚。

## Low-Risk Notes

1. **`63-04` fallback 行为仍是执行时最容易写错的点。**
   Plan 已经有足够测试要求，不需要再修 plan；执行时应优先让 fake-registry-raises case pin 住 route outcome 和 reason marker。

2. **`63-05` static AST guard 要保持精确。**
   Plan 已明确不要 broad scan generic strings；执行时不要为了简单实现改成全文 grep `manual_review|blocked`。

3. **Summary artifacts 通过 `<output>` 明确要求创建。**
   各 plan frontmatter 的 `files_modified` 未列 summary 文件，但每个 plan 的 `<output>` 都要求创建 `63-xx-SUMMARY.md`。这不是执行前 blocker。

## Final Verdict

**CLEAN_WITH_LOW_RISK_NOTES**

这些 notes 都是执行注意点，不需要再次修 plan。Phase 63 repaired plans 可以进入执行。

---

## Round 2 Consensus Summary

Claude returned `CLEAN_WITH_LOW_RISK_NOTES`. No additional plan blockers or warnings require repair before execution. The remaining notes are execution cautions for registry exception fallback precision and static drift guard implementation.
