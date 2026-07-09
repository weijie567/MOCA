---
phase: 62
reviewers: [claude]
reviewed_at: 2026-07-09T12:18:27Z
plans_reviewed:
  - 62-01-PLAN.md
  - 62-02-PLAN.md
  - 62-03-PLAN.md
  - 62-04-PLAN.md
  - 62-05-PLAN.md
  - 62-06-PLAN.md
  - 62-07-PLAN.md
---

# Cross-AI Plan Review — Phase 62

## Claude Review

### Summary

Phase 62 的 7 个计划整体质量较高，拆分顺序合理：先 registry，再 schema/spec，再 ToolPlatform 权限，再 BusinessFactService runtime，再 drilldown state，最后 backend projection/eval 与 frontend UI。它基本覆盖了 Phase 62 的核心目标：单一来源、`business_query` 主契约、scope/no-existence-leak、五类读操作、drilldown、typed payload、eval/UI。当前我不认为需要在执行前整体返工；但有几处高风险边界需要在 plan 内补更明确的验收，否则实现时容易出现“看似通过、实际漏契约”的问题。

### Blockers

- 无明确 BLOCKER。现有计划可以进入执行。
- 但建议在执行前做小幅补充，尤其是 62-04、62-05、62-06 的契约衔接和 no-existence-leak 验证点。

### Warnings

- **HIGH — 62-04 runtime 面过大。** `BusinessFactService.query_business` 一次覆盖 aggregate/list/detail/breakdown/compare、scope、cursor、compat metric、ToolResult 适配，执行风险最高；需要防止“为了赶通路”把 compare/breakdown 做成弱实现。
- **HIGH — 62-04/62-06 结果模型衔接需更硬。** 62-04 说返回 `BusinessFactResultV1`，62-06 又按 `BusinessQueryResultV1` 或 projected dict 投影；如果没有明确嵌套字段/adapter contract，后续 final/API/UI 很容易依赖不稳定 dict。
- **HIGH — 62-05 state 失效规则不够具体。** 计划说 same-thread 可携带 `last_query_spec`，但应明确在 user/tenant/session/thread/auth scope/role 改变、unsupported/new unrelated query、permission denial 后如何清空或降级。
- **MEDIUM — 62-03 新增 `business:query` scope 有兼容风险。** 若现有 demo/admin/support/manager token 只带 `metrics:read`，Phase 62 默认走 `business_query` 后可能出现权限缺失；计划应明确 role fixture/JWT scope 更新与兼容映射策略。
- **MEDIUM — 62-01 registry 有“万能注册表”风险。** registry 同时装 operation/resource/metric/time/status/field/sort/parser alias/projection hints，后续可能混入 UI 文案或 runtime 逻辑；需保持“描述允许形状”，不要放执行、权限、SQL、前端布局事实。
- **MEDIUM — 62-05 expected-slot flow 可能影响非 metric 流。** time/resource_id/merchant_filter/field_request/cursor_request 泛化后，需防止 approval、unsupported、small talk、普通 clarification 被误吸进 business-query follow-up。
- **MEDIUM — 62-06 eval/golden 可能只测 fixture 结构，不测真实 graph/runtime。** `scripts/eval_phase62_business_query.py` 若只是校验 JSONL，会遗漏真实 agent path；需要至少有 pytest graph/API 对应这些 golden categories。
- **MEDIUM — 62-07 E2E 不在 task-local verify 是合理的，但 phase gate 必须真的执行。** 否则 UI typed payload 和 no-overlap 只停留在用例存在。
- **LOW — 62-02 spec 更新要避免写成“已实现事实”。** 计划已提醒这是 target contract，但执行总结也要保持这个边界。
- **LOW — 性能风险主要在 list/detail/compare。** 计划已有 limit/cursor，但应关注排序字段索引、limit+1、compare 双时间窗查询、避免按 merchant scope 做 Python 侧过滤。

### Suggestions

- 在 **62-04** 明确 `BusinessQueryResultV1` 如何进入 `BusinessFactResultV1`：例如固定 `fact_data["business_query"]` schema，禁止下游猜测 tool raw dict。
- 在 **62-04** 增加 service 测试：unauthorized detail 不能先 fetch by id；可用 spy/mock repository 或 query counter 证明 scope-before-existence。
- 在 **62-04** 增加 compare 时间边界测试：`effective_time`、周/月边界、previous equivalent period、空上一周期。
- 在 **62-05** 增加 state invalidation 表：保留、清空、只作为 drilldown context 的条件分别列出。
- 在 **62-05** 增加 cross-role/cross-scope stale context 测试：同 thread 但 trusted scope 变化时必须重新校验且不能复用旧 rows/cursor。
- 在 **62-03** 明确 `metrics:read` 与 `business:query` 的过渡策略：是 role 默认同时授予，还是 `query_business_metric` 继续只需 `metrics:read`，新 `business_query` 才需 `business:query`。
- 在 **62-01/62-02** 加 registry/schema parity test：ToolCatalog schema enum、Pydantic accepted enum、registry enum 三者一致。
- 在 **62-06** 增加 API schema snapshot 或 contract test，锁定 `business_query_answer.business_query` allowlist，避免 frontend 与 backend drift。
- 在 **62-06** golden eval 中区分两类测试：fixture validator 通过、真实 graph/API behavior 通过；不要把前者当成后者。
- 在 **62-07** 明确 `BusinessQueryResultTab` 对未知 operation/unknown field 的 fallback：安全降级为 unsupported/empty-safe，不显示 raw JSON。
- 每个计划 summary 应记录执行后的实际偏离：特别是 spec delta、auth scope、runtime examples、drilldown state 字段、payload allowlist。

### Risk Assessment

- **Overall risk: MEDIUM-HIGH。**
- 原因不是计划方向错误，而是 Phase 62 同时改 parser、schema、ToolPlatform、auth permission、BusinessFactService、state、projection、API、eval、frontend，跨边界多，且 no-existence-leak 与 drilldown state 都属于容易“单测绿但集成漏”的区域。
- 风险最高的计划是 **62-04** 和 **62-05**；它们决定真实权限边界、runtime 查询语义、follow-up 是否安全。
- 风险次高的是 **62-06/62-07**；它们决定 raw payload 是否被 strip，以及 UI 是否只信 typed backend payload。

### Verdict

- **Verdict: APPROVE WITH WARNINGS。**
- 不需要重写 7 个计划，也没有必须阻塞执行的结构性缺陷。
- 执行前建议补强 62-04/62-05/62-06 的契约衔接、state 失效、auth scope 迁移、真实 graph/API 验证点；这些是小修订，不改变计划拆分和总体方向。

## Consensus Summary

Only the Claude reviewer was invoked in this pass, because the autopilot review gate requested the Claude Code plan review path. Treat this as external review input, then apply Codex adjudication before revising plans.

### Agreed Strengths

- The seven-plan dependency chain is coherent.
- The phase correctly centers `business_query`, controlled backend execution, no-existence-leak, answer context, projection, eval, and UI.
- No structural blocker requires rewriting the plan set.

### Agreed Concerns

- 62-04 and 62-05 carry the highest integration/security risk.
- The result-model boundary between runtime and projection needs to be explicit.
- State invalidation, auth scope migration, no-existence-leak tests, and graph/API validation should be sharpened before execution.

### Divergent Views

- None recorded in this pass; there was one external reviewer.
