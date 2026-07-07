---
phase: 56
reviewers: [claude]
reviewed_at: "2026-07-07T16:45:17+08:00"
plans_reviewed: [56-01-PLAN.md, 56-02-PLAN.md, 56-03-PLAN.md, 56-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 56

## Claude Review

## 总体评价

这 4 个 plan 的拆分方向是合理的：先做 canonical callable，再切 active graph，再硬化 RAG/claim fail-closed routing，最后收口 vocabulary/API/frontend/docs/validation。整体能覆盖 Phase 56 的核心目标，且明确保留 Phase 57 的 `assess_risk_and_approval -> risk_gate` 边界、Phase 58 的兼容清理边界，避免把三个 phase 混在一起。主要风险不在大方向，而在几个细节：`final_response` 仍有 legacy verifier 字段 fallback 的权威性风险、56-03 对 action claim gate 的语义需要更精确、56-04 范围偏宽且 `files_modified` 与实际 action 不完全一致，可能导致执行时遗漏文档或测试面。

---

## 56-01-PLAN.md — canonical `recommendation_generation` callable and compatibility wrapper

### Summary

56-01 作为第一步是合理的：它不碰 active graph，而是先建立 canonical callable、canonical trace/output identity，并把旧 `generate_recommendation` 收窄为兼容入口。这能降低后续 graph cutover 的风险。Plan 对 D-56-03/D-56-09 的边界写得比较清楚，但实现时要避免把一个较大的 node 文件重构成“大改写”，否则容易引入行为回归。

### Strengths

- 拆分点正确：先做 callable identity，再由 56-02 切 graph，依赖顺序清晰。
- 明确 canonical path 应写：
  - `llm_outputs["recommendation_generation"]`
  - trace node `recommendation_generation`
  - `MaterialClaimV1.generated_from_step == "recommendation_generation"`
- 明确 generation 不能写 verifier-owned 字段，符合 D-56-09/D-56-11。
- 保留旧 import/test/historical compatibility，符合 D-56-04，不做破坏性全仓 rename。
- 使用 node-level focused test，验证命令符合 MOCA `uv run pytest` 规则。

### Concerns

- **MEDIUM — 对 `generate_recommendation.py` 的 helper 参数化可能引入过度重构。**  
  Plan 要求把实现改成可传 `output_key` / `trace_node`。这是合理的最小抽象，但现有 generation node 逻辑较大，执行时如果顺手重排结构、改数据流或改 LLM output 解析，会扩大回归面。Plan 应明确“只抽出 identity 参数，不改变 draft/claim/evidence_refs 生成逻辑”。

- **MEDIUM — legacy wrapper 的输出身份需要更精确定义。**  
  Plan 同时说 canonical 写 `recommendation_generation`，legacy `generate_recommendation` “may delegate with legacy identity”。这本身可以接受，但建议明确：
  - active runtime 永远不用 legacy wrapper；
  - legacy import 调用是否仍写 `llm_outputs["generate_recommendation"]` 只服务旧测试/历史兼容；
  - legacy wrapper 不得新增 canonical+legacy 双写，避免同一次调用出现两个 recommendation draft key。

- **LOW — 兼容 metadata 可能和 56-04 的 graph vocabulary metadata 重复。**  
  56-01 要在 `generate_recommendation.py` 放 `PHASE_56_COMPATIBILITY_ALIAS` 等字符串，56-04 又要在 `graph_vocabulary.py` 放同类 reason codes。重复不是 blocker，但要防止两个地方语义漂移。

- **LOW — `tests/agent/test_phase22_recommendation_integration.py` 放在 files_modified，但 Task 1 主要只改 node tests。**  
  Task 2 才覆盖 integration test，问题不大，但执行者需要避免 Task 1 提前改太多 integration 预期。

### Suggestions

- 在 Task 1 action 中补一句：  
  “Do not change recommendation draft schema, evidence ref validation, material claim construction, LLM provider call shape, or fallback wording except for output/trace identity.”
- 明确 legacy wrapper 行为：  
  “Legacy `generate_recommendation(...)` may preserve legacy `llm_outputs["generate_recommendation"]` only when directly imported/called; canonical callable must not dual-write legacy key.”
- 对 verifier-owned 字段测试建议覆盖 both paths：
  - canonical success path
  - canonical insufficient-evidence path
  - legacy direct import path
- 兼容 metadata 可以在 `generate_recommendation.py` 写本地常量，但建议测试只断言字符串存在和含义，不要求两个模块共享 import，避免引入反向依赖。

### Risk Assessment

**Overall risk: MEDIUM.**  
风险主要来自 refactor 原大文件实现时的行为回归，而不是 plan 方向。只要执行时保持 identity-only refactor，并用现有 node tests 加 canonical/legacy identity tests，风险可控。

---

## 56-02-PLAN.md — active graph/router/baseline cutover

### Summary

56-02 的目标非常聚焦：把 active `StateGraph` 注册从 `generate_recommendation` 切到 `recommendation_generation`，并更新 route map 与 static graph baseline，同时保留 Phase 57 的 `assess_risk_and_approval` legacy row。这个 plan 是 Phase 56 success criteria 1 和 4 的核心，设计整体扎实。

### Strengths

- 精准覆盖 D-56-01/D-56-02/D-56-15：
  - active add_node 使用 `recommendation_generation`
  - `investigate` / `rag_context_build` route value 映射到 canonical node
  - `route_after_recommendation` source 改为 canonical node
  - `assess_risk_and_approval` 保留为 Phase 57 active legacy row
- static baseline 与 graph integration tests 都纳入验证，能防止只改代码不改 guardrail。
- 明确禁止提前注册 `risk_gate`，避免 Phase 57 scope creep。
- 依赖 56-01 合理：只有 canonical callable 存在后才能切 graph import。

### Concerns

- **MEDIUM — `tests/test_graph_routing.py` 可能测试 router return value，而不是 graph path-map destination。**  
  当前 `route_after_rag_context` 已返回 `recommendation_generation`（见 `src/agent/routing.py:553-566`），真正的问题是 `src/agent/graph.py` 的 path map 把 route value 指向 legacy node。Plan 要求测试 exact pair `"recommendation_generation": "recommendation_generation"` 是对的，但执行时要确保测试检查的是 graph path-map，不只是 router function return。

- **MEDIUM — baseline 更新必须同时验证 absence 和 remaining legacy row。**  
  当前 baseline 里 `generate_recommendation` 是 active node，且 legacy map 里还有 `generate_recommendation -> recommendation_generation`。Plan 已要求移除，但测试要同时断言：
  - active nodes 不含 `generate_recommendation`
  - `MIGRATION_MODE_LEGACY_NODE_MAP` 不含 `generate_recommendation`
  - 仍含 `assess_risk_and_approval -> risk_gate`
  否则后续 Phase 58/57 边界容易混乱。

- **LOW — 56-02 不改 `src/agent/routing.py` 是合理的，但如果测试命名仍带旧 node，可能需要仅改测试描述。**  
  Plan 已允许“unless a test import name must be adjusted without behavior change”，足够。

### Suggestions

- 在 Task 2 acceptance 中补充一条：  
  “Tests inspect `add_conditional_edges` path maps or architecture baseline, not only router return values.”
- 在 architecture test 中增加一条专门防回归：  
  “No conditional edge source is `generate_recommendation`.”
- 在 graph tests 中保留 Phase 57 证明：  
  `claim_verify -> assess_risk_and_approval` 和 `approval_gate -> assess_risk_and_approval` 不变。

### Risk Assessment

**Overall risk: LOW to MEDIUM.**  
改动点清晰、验证面明确。风险主要是测试没有真正检查 graph path-map destination，而只检查 router return value。补强 static AST/baseline 检查即可降到 LOW。

---

## 56-03-PLAN.md — RAG status and claim verification fail-closed hardening

### Summary

56-03 是安全语义最关键的 plan。它正确抓住了当前核心 gap：`route_after_claim_verify` 现在在 bundle `verified/continue` 后，只要有 `proposed_action` 就可能进入 `assess_risk_and_approval`（见 `src/agent/routing.py:580-592`），但 D-56-10 要求 action claim 必须显式允许 action recommendation。RAG status totality 和 `partial` fail-closed 也覆盖了 Phase 56 的主要安全目标。

### Strengths

- 直接针对当前 routing gap：proposed action 不再凭 bundle verified/continue 自动进入 risk node。
- 要求 legacy verifier fields 不能覆盖 canonical `claim_verification_bundle`，符合 D-56-11。
- RAG status 以 `src.knowledge.schemas.RAG_CONTEXT_STATUSES` 为准，避免 free-form drift。
- 对 missing/unknown/malformed/unsafe status 默认 `final_response`，符合 fail-closed。
- 明确保留当前 Phase 57 node value `assess_risk_and_approval`，不提前改 `risk_gate`。

### Concerns

- **HIGH — action route 条件描述仍有歧义。**  
  Task 2 action 写道：route to risk only when “a non-action risk signal requires risk assessment without a proposed action, or a proposed action/action-recommendation claim is present and `_has_verified_action_recommendation(state)` is true.”  
  建议更明确地表达为：
  - `proposed_action` present ⇒ 必须 `_has_verified_action_recommendation(state) is True`
  - no `proposed_action` but risk signal present ⇒ 可进入 `assess_risk_and_approval`
  - `_has_verified_action_recommendation` alone without proposed action 是否需要进 risk，要明确；否则可能产生“只有 claim result 没有 proposed_action 也进入 risk”的边界不清。

- **MEDIUM — “user-visible claims” gate 不应只靠 `_has_material_claims` / `_has_proposed_action`。**  
  `route_after_recommendation` 当前逻辑会在 `_has_material_claims`、`_has_proposed_action` 或 `_has_user_visible_claims` 时进 `claim_verify`（见 `src/agent/routing.py:569-577`）。Plan 覆盖了行为，但测试重点集中 action claim。建议也保留/补一组 non-action user-visible policy/business claim 的测试，防止未来只 action gate 强、普通 material claim 弱。

- **MEDIUM — RAG route gate 不能单独证明“不 promotable to evidence_refs / approval snapshots / risk lowering”。**  
  Task 1 action 写“this task proves the route gate blocks those paths”。路由 gate 能证明 unsafe status 不进入 generation/risk path，但不能完全证明已有 state 中的 `evidence_refs`、approval snapshot、risk lowering 不被下游消费。这个证明更适合 56-04 的 final/API projection 和 risk/action tests。当前 acceptance 可能有一点 overclaim。

- **MEDIUM — `partial` 低风险谓词需要固定字段来源。**  
  Plan 提到 action intent/operation/high risk/approval-required/unsafe evidence indicators，但没有列出具体 state fields。执行者可能临时发明字段或过拟合测试。应要求使用现有 intent/risk state 字段，找不到字段则在 test 中标明“不适用/当前仓库没有该字段依据”。

- **LOW — schema import direction需要保持轻量。**  
  `routing.py` 使用 `RAG_CONTEXT_STATUSES` 是可接受的，但不要把 knowledge service 或 Pydantic model construction 引入 router，避免 routing 层变重。

### Suggestions

- 把 `_route_after_claim_verify` 的 action gate 写成明确决策表，并放进测试名：
  | proposed_action | risk_signal | verified action claim | expected |
  |---|---|---|---|
  | yes | no/yes | no | final_response |
  | yes | no/yes | yes | assess_risk_and_approval |
  | no | yes | n/a | assess_risk_and_approval |
  | no | no | n/a | final_response |
- 增加测试：legacy fields 设置为允许，但 canonical bundle missing/blocked/manual_review/error 时必须 `final_response`。
- 对 `partial` 谓词列出具体输入字段，例如 effective intent、operation hints、risk tier、approval required flag、proposed_action 等，避免执行时新增未定义状态。
- 把“不 promotable to approval snapshots / action authority”的完整证明放到 56-04 或后续 risk/action focused tests，不要只依赖 route unit tests。

### Risk Assessment

**Overall risk: MEDIUM to HIGH.**  
这是 Phase 56 最重要的安全 hardening，且涉及 action path 权威边界。方向正确，但 action gate 条件必须无歧义，测试矩阵要覆盖 proposed_action + risk_signal 的组合，否则仍可能留下绕过路径。

---

## 56-04-PLAN.md — vocabulary/API/frontend/eval/docs/debt/validation closeout

### Summary

56-04 负责把 runtime 变化投影到 trace/API/frontend/eval/docs/debt，并补 safe final response。作为 closeout plan，它覆盖面完整，但也是 4 个 plan 中范围最大的一个。主要问题是 `final_response` 的 legacy verifier fallback 与 D-56-13 有潜在冲突，以及 action 中要求检查/可能修改很多文档，但 frontmatter `files_modified` 没有列全，执行时容易漏。

### Strengths

- 正确把 `graph_vocabulary.py` 作为 historical trace projection 的集中点。
- 同时覆盖 current `recommendation_generation` runtime identity 和 historical `generate_recommendation -> recommendation_generation` alias。
- API/SSE/frontend/eval labels 都纳入，能避免后端 graph 已切但 UI/API 仍显示旧节点。
- 要求 final response 区分：
  - insufficient evidence
  - unsafe/invalid RAG context
  - unsupported claim
  - manual review
  - verifier error
- 包含 docs、architecture debt、validation artifact 和 closeout commands，符合 MOCA phase closeout 习惯。
- 明确保留 Phase 57/58 边界。

### Concerns

- **HIGH — `final_response` 当前仍可能使用 legacy verifier fields 形成 route payload。**  
  现有 `src/agent/nodes/final_response.py:403-470` 先消费 claim bundle / RAG context，但 `src/agent/nodes/final_response.py:410-426` 仍会从 `rag_verification`、`verification_route`、`verifier_status`、`verifier_reason_codes` 生成 payload。D-56-13 要求 final response consume only safe projections from `verified_evidence_package` and `claim_verification_bundle`; D-56-11 也说 legacy fields cannot override/bypass canonical bundle。  
  56-04 只说“debug/verifier projection sentinels do not appear”，不够。需要明确：
  - legacy verifier fields 不能作为 current-run authoritative final payload；
  - 如果保留，必须限定为 historical compatibility，并且不能覆盖 canonical bundle/RAG package；
  - tests 应覆盖 canonical bundle missing + legacy allow/block 字段时的行为。

- **MEDIUM — 56-04 scope 偏大，且 `files_modified` 与 action 不一致。**  
  Task 3 action 要检查并可能更新：
  - `docs/contract-spec.md`
  - `docs/target-agent-platform-architecture-plan.md`
  - `docs/architecture-overview.md`
  - `docs/agent-architecture-routing-explanation.md`
  - `docs/rag-architecture-spec.md`
  - `README.md`
  - `.planning/DEFERRED-DECISIONS.md`
  但 frontmatter `files_modified` 没有列这些。若 GSD/Codex 执行依赖 frontmatter，可能漏改或误以为不能改。

- **MEDIUM — “safe final wording” 容易变成脆弱文案测试。**  
  应测试 semantic route/payload/source/reason code，而不是过度断言中文全文。否则后续 copy 微调会频繁破测试。

- **MEDIUM — API tests 对 historical/current projection要区分 implementation node 和 target node。**  
  Plan 已说 historical trace keeps `implementation_node == "generate_recommendation"` and target `recommendation_generation`，这是对的。测试要避免把历史 node_name 也重写成 canonical，否则会丢审计真实性。

- **LOW — frontend label 更新可能需要同步 snapshot 或类型定义。**  
  Plan 只列 `TimelineStep.tsx`，如果 frontend 有 step union/type/snapshot，也要检查。当前计划可在执行时通过 `rg` 补查。

- **LOW — `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` 可能不如直接 `git diff --check` 常见，但符合项目“approved entrypoint”风格，不是 blocker。**  
  只要仓库里该命令能跑即可。

### Suggestions

- 在 Task 2 明确新增高优先级 acceptance：
  - `verification_route`, `verifier_status`, `verifier_reason_codes` cannot create current-run final response authority when `claim_verification_bundle` is absent.
  - canonical `claim_verification_bundle` / `verified_evidence_package` always wins over legacy fields.
- 对 `final_response` 建议按 source 优先级写清楚：
  1. `claim_verification_bundle`
  2. `verified_evidence_package`
  3. historical-only fallback, if retained, must be non-authoritative and labelled compatibility
- 把可能修改的 docs/checklist files 加进 `files_modified`，或在 plan 中明确“inspect-only unless stale; if stale, update and record in summary”。
- 在 API tests 中分别断言：
  - current event: `node_name == "recommendation_generation"`, `target_node_name == "recommendation_generation"`
  - historical event: `node_name == "generate_recommendation"`, `target_node_name == "recommendation_generation"`
- closeout summary 应记录每个 skipped checklist file 的具体 no-update-needed 理由，这点 plan 已有，建议保留为 hard acceptance。

### Risk Assessment

**Overall risk: MEDIUM.**  
作为 closeout，范围较宽但必要。最大风险是 final_response 仍把 legacy verifier fields 当成 current authority；这会削弱 56-03 的 hard gate。只要把 legacy fallback 权威性收紧并补测试，整体风险可控。

---

## Cross-plan Dependency and Scope Review

### What works well

- 依赖顺序整体正确：
  - 56-01 提供 callable
  - 56-02 切 active graph
  - 56-03 独立硬化 routing，可与 56-02 并行
  - 56-04 统一投影、文档、验证
- Phase 57 boundary 明确：所有 plan 都反复强调不注册 `risk_gate`。
- Phase 58 boundary 明确：兼容 alias/wrapper 保留，删除推迟。
- 验证命令全部使用 `UV_CACHE_DIR=/tmp/uv-cache uv run ...`，符合 D-56-16。
- Plan split 符合 D-56-14，避免一个大 plan 混改 graph、routing、API、docs。

### Main risks across all plans

- **HIGH — final_response legacy verifier fallback 可能绕过 canonical bundle 语义。**  
  56-03 负责 routing hard gate，但用户可见最终输出也必须只信 canonical safe projections。`final_response.py` 的 legacy fallback 需要被 56-04 明确处理。

- **MEDIUM — action claim allowance 语义必须决策表化。**  
  “proposed action + verified bundle” 不够，必须有 explicit action-recommendation claim allow。当前 plan 已识别，但 wording 还应更硬。

- **MEDIUM — 56-04 文档检查范围与 frontmatter 不一致。**  
  可能导致执行者遗漏 stale docs 或 summary 没记录 skipped reason。

- **LOW — compatibility metadata 分散在 wrapper 和 vocabulary，需防 drift。**

---

## Final Risk Assessment

**Overall phase plan risk: MEDIUM.**

理由：

- **目标覆盖度高。** 4 个 plan 合起来能实现 Phase 56 的关键目标：active graph canonicalization、claim_verify hard gate、RAG status fail-closed、projection/docs closeout。
- **边界控制较好。** Phase 57 `risk_gate` 和 Phase 58 compatibility cleanup 都被明确排除。
- **主要风险集中在安全语义细节，而非架构方向。** 特别是 `route_after_claim_verify` 的 proposed action gate 和 `final_response` 的 legacy verifier fallback。如果这两个点按建议补强，整体风险可降到 LOW-MEDIUM。
- **执行复杂度中等。** 涉及 graph、routing、API、frontend、docs、tests 多处，但每个 plan 的职责边界基本清楚，没有明显必须重排的依赖问题。

---

## Consensus Summary

Single external reviewer run requested by autopilot Stage 3 (Claude). No multi-reviewer consensus was computed. Codex adjudication will independently verify each actionable Claude finding against repository evidence before plan repair.

### Agreed Strengths
- Not applicable for single-reviewer run. Claude found the four-plan split directionally sound, with clear Phase 57 and Phase 58 boundaries.

### Agreed Concerns
- Not applicable for single-reviewer run. Highest-priority Claude concerns for adjudication: final_response legacy verifier fallback authority, action-claim routing semantics, and 56-04 file surface/frontmatter consistency.

### Divergent Views
- Not applicable for single-reviewer run. Codex adjudication records accepted, false-positive, disagreed, and deferred outcomes in 56-PLAN-REVIEW-DECISIONS.md.
