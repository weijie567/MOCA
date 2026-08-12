# MOCA 架构债务 / 缺陷发现台账

> 本文件记录 MOCA 各子系统在代码走查、phase 实现、本地验证中**检测出的 bug、设计缺陷、遗留妥协**，以及**已完成的修复**。
> 与 `LOCAL-VALIDATION-ISSUES.md` 的分工：那个记「本地调试/启动/验证时踩到的具体事故」；本文件记「子系统级的架构缺陷与处理台账」，颗粒度更粗、生命周期更长。

## 2026-08-05 — Phase 64.2 Plan 02 Task 2 evidence cutover 精确零缺口已修复验证 ✅

- **子系统**：RAG ingestion / immutable evidence backfill / canonical-read cutover。
- **问题现象/根因**：migration 026 初版最终 gap SQL 只证明 exact tenant/scope/doc/version 下存在 document version，并通过一个对合法 `sha256:` 字符串恒真的表达式检查 hash 形状；没有重算当前 document hash，也没有比较当前/immutable chunk identity + text hash 集合。因此错误或残缺 immutable binding 可能被误计为 zero-gap 后开启 canonical reads。
- **影响**：cutover 可能在 current head 与 retained immutable evidence 不一致时错误启用 canonical reads，破坏 T64.2-02 的 append-only / watermark reconciliation 边界，并使后续 replay 引用错误历史材料。
- **处理状态**：✅ 已修复验证。migration 和 `EvidenceVersionRepository` 现在都按 exact `scope_type="tenant_policy"`、`scope_id=str(tenant_id)`、document version/fingerprint/recomputed content hash、唯一 logical chunk 与完整 chunk text-hash 集合验证绑定；final scan、zero-gap assertion 和 CAS activation 连续持有 singleton rollout lock。backfill 遇到 missing/ambiguous/mismatched mapping 只标记 `legacy_unresolved`，不猜测 scope/authority。
- **证据**：Phase 64.2 Plan 02 Task 2；`src/db/migrations/versions/026_phase64_2_evidence_cutover.py`、`src/repositories/evidence_version_repo.py`、`tests/knowledge/test_evidence_cutover.py::test_writer_and_cutover_share_rollout_lock_epoch`；GREEN commit 待本 task 提交后补记。验证：Task 2 精确命令 `10 passed, 4 warnings`，scoped Ruff 与 whitespace gate 通过。
- **剩余风险**：🟡 当前 Plan 02 focused migration test 对 026 的 staged precondition 主要是 source contract，完整 025 → 实际 dual-write health → 026 migration-chain 执行由 Phase 64.2 Plan 09 closeout gate 负责；该项不能被当前 10-test 结果替代。

## 2026-08-05 — Phase 64.2 Plan 02 Task 3 canonical current / historical / legacy 读边界已收敛 ✅

- **子系统**：RAG retrieval / evidence resolver / operational read cutover。
- **问题现象/根因**：Phase 64.2 前 production retrieval 与 `PolicyChunkRepository` 直接拼接 `doc_key/chunk_id@version`，current eligibility、retained historical resolution 与 legacy alias upgrade 共用 mutable key/hash 查找，且没有由 singleton rollout state 控制 canonical reads。禁读时存在回落到 mutable/legacy ref 的风险，superseded evidence 也无法明确区分“非 current”与“历史材料仍可精确解析”。
- **影响**：current search 可能发出非 repository-backed identity；跨 tenant/scope、缺失/伪造/歧义输入与 operational quarantine 的 fail-closed 边界不统一；replay/approval 后续难以证明引用的是 retained immutable row。
- **处理状态**：✅ 已修复验证。production `PolicyRetrievalEngine(session=...)` 只在 `canonical_reads_enabled=true` 且无 quarantine 时，从 exact current document/chunk binding 取得 immutable row并由 owner mint `EvidenceRefV1`；禁读/缺绑定统一返回无 ref 的 error，不回落。`validate_current_evidence(...)`、`resolve_immutable_evidence(...)`、`resolve_legacy_alias(...)` 已分离，历史解析不套 current freshness，但继续严格 tenant/scope。`disable_canonical_reads(...)` 复用 rollout-first CAS 锁，保留 dual-write，reconciliation zero-gap 后才可 re-enable。
- **证据**：Phase 64.2 Plan 02 Task 3；`src/repositories/evidence_version_repo.py`、`src/knowledge/retrieval.py`、`src/knowledge/service.py`、`src/repositories/policy_chunk_repo.py`、`tests/knowledge/test_evidence_cutover.py`。Task 3 精确门禁 `41 passed, 1 warning`，补充 retrieval 回归 `46 passed, 1 warning`，scoped Ruff/format/whitespace 均通过；GREEN commit 待本 task 提交后补记。
- **剩余风险**：🟡 无 DB session 的 in-memory retrieval test doubles 仍通过 owner 内部的显式 legacy test compatibility projection 保持旧测试语义；MOCA production factories均传入真实 `AsyncSession`（`src/api/routers/search.py`、`src/tools/executors/knowledge.py`、agent RAG factories），不会进入该分支。Phase 64.2 Plan 09 architecture guard 应继续锁定所有 production factory 必须使用 session-backed canonical owner。

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

## 2026-07-08 — Phase 58-02 recommendation/risk implementation ownership 已迁到 canonical modules ✅

- **子系统**：Agent Graph / RAG recommendation / 风险审批主链
- **问题现象/根因**：Phase 58 no-debt cleanup 前，active graph 已使用 `recommendation_generation` 与 `risk_gate`，但具体实现仍托管在 legacy wrapper 文件 `generate_recommendation.py` 与 `assess_risk_and_approval.py`；canonical modules 只是薄 wrapper。这会让当前-run patch seam、测试入口和实现 owner 继续依赖 legacy node name，阻碍 CAGM-09 删除 active compatibility aliases。
- **影响**：若不先迁 ownership，58-03 删除 legacy wrapper 或清理跨测试 import 时会打断 current runtime；同时 direct node tests 会继续把 legacy filename 当成事实 owner，最终 no-debt classifier 需要永久例外。
- **处理状态**：✅ 已修复验证。`src/agent/nodes/recommendation_generation.py` 现在直接承载 `_get_llm`、prompt assembly、RAG/verified-package/citation/fail-closed 逻辑和 public `recommendation_generation(...)`；`src/agent/nodes/risk_gate.py` 现在直接承载 `_get_llm`、risk rules、snapshot persistence seam、approval/action binding、fail-closed 逻辑和 public `risk_gate(...)`。Legacy files 仅保留非 owning import wrapper，当前调用也发出 canonical identity。Direct tests 已迁到 `tests/agent/test_nodes/test_recommendation_generation.py` 与 `tests/agent/test_nodes/test_risk_gate.py`；legacy-named direct tests 已删除。
- **证据**：Phase 58 Plan 58-02；commits `211e36a`（recommendation ownership）与 `b90a830`（risk ownership）；RED commits `faff3fd`、`74045b6`；文件 `src/agent/nodes/recommendation_generation.py`、`src/agent/nodes/generate_recommendation.py`、`src/agent/nodes/risk_gate.py`、`src/agent/nodes/assess_risk_and_approval.py`、`tests/agent/test_nodes/test_recommendation_generation.py`、`tests/agent/test_nodes/test_risk_gate.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short` → `40 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py -q --tb=short` → `17 passed, 1 warning`。最终组合 pytest / ruff 以 `58-02-SUMMARY.md` 为准。
- **剩余风险**：🟡 本 plan 按范围没有做跨测试 import cleanup；`generate_recommendation.py` 与 `assess_risk_and_approval.py` wrapper 文件仍存在，只是 non-owning。Wrapper 删除、scattered import cleanup、eval/script 调整和 final classifier 收敛留给 dependency-ordered Plan 58-03+。

## 2026-07-08 — Phase 58-03 recommendation/risk legacy wrapper 文件已删除 ✅

- **子系统**：Agent Graph / RAG recommendation / 风险审批主链
- **问题现象/根因**：58-02 已把实现 owner 迁到 `recommendation_generation.py` 与 `risk_gate.py`，但 `generate_recommendation.py` / `assess_risk_and_approval.py` 仍作为 import compatibility wrapper 存在；直接测试、graph/eval/知识 facade 等若继续 import 旧模块，会让 CAGM-09 的 no-debt gate 保留 current-run 兼容面。
- **影响**：旧 wrapper 文件一旦继续可 import，后续测试或脚本容易继续 patch legacy module path，造成 active canonical node 与测试 seam 漂移；同时 Phase 56/57 compatibility marker 可能被重新引入到 current node/test surface。
- **处理状态**：✅ 已修复验证。删除 `src/agent/nodes/generate_recommendation.py` 与 `src/agent/nodes/assess_risk_and_approval.py`；直接测试只 import canonical modules；`tests/architecture/test_phase33_rag_claim_boundaries.py` 改为检查 canonical recommendation owner、deleted wrapper/direct-test 文件不存在、`src/agent/nodes` 与 `tests/agent/test_nodes` 不再 import deleted module 或携带 Phase 56/57 compatibility marker。为避免删除后 broader test collection 断裂，同步把 graph / Phase 22 / knowledge facade / eval script 的 patch/import seam 改到 canonical modules。
- **证据**：Phase 58 Plan 58-03；RED commit `30ad924`；GREEN commit 为本条所在提交；文件 `src/agent/nodes/recommendation_generation.py`、`src/agent/nodes/risk_gate.py`、`tests/agent/test_nodes/test_recommendation_generation.py`、`tests/agent/test_nodes/test_risk_gate.py`、`tests/architecture/test_phase33_rag_claim_boundaries.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` → `61 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` → `active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`；wrapper/direct legacy test deletion checks passed。
- **剩余风险**：🟡 历史 trace/docs/planning 中仍有 legacy name 文本，由 strict classifier 分类为 historical / previous-state / cleanup artifact，不再是 active runtime authority。本条不处理其他 Phase 58 cleanup surfaces（如 intent/slot/memory wrappers、approval retry historical compatibility、frontend/API fallback labels）。

## 2026-07-08 — Phase 58-04 intent/session legacy wrapper 文件与直接测试已删除 ✅

- **子系统**：Agent Graph / 意图识别 / 记忆上下文
- **问题现象/根因**：Phase 53 已把 active graph 切到 `session_context_load -> contextual_intent_resolve`，但 `classify_intent.py`、`session_memory_load.py` 仍作为 import/test compatibility wrapper 存在；`test_classify_intent.py`、`test_session_memory_load.py` 也继续把旧 filename 当成直接测试入口。这会让 current-run patch seam 和直接测试继续依赖 legacy node name，阻碍 CAGM-09 no-debt 收敛。
- **影响**：旧 wrapper 可 import 时，后续测试、fixture 或脚本容易重新 patch legacy module path；session wrapper 还会把 trace node 写成 `session_memory_load`，与当前 canonical runtime identity 不一致。
- **处理状态**：✅ 已修复验证。删除 `src/agent/nodes/classify_intent.py`、`src/agent/nodes/session_memory_load.py`、`tests/agent/test_nodes/test_classify_intent.py`、`tests/agent/test_session_memory_load.py`；把非重复断言迁入 `tests/agent/test_nodes/test_contextual_intent_resolve.py` 与新建 `tests/agent/test_nodes/test_session_context_load.py`；`tests/agent/test_intent_adapter.py`、intent golden/routing/memory-boundary fixture 和 empty-session adapter 测试改到 canonical import/patch seam。
- **证据**：Phase 58 Plan 58-04；commits `7a45cba`（intent RED guard）、`4029e9b`（intent wrapper deletion）、`ac6af9c`（session RED guard）、`0034a4e`（session wrapper deletion）；文件 `src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/session_context_load.py`、`tests/agent/test_nodes/test_contextual_intent_resolve.py`、`tests/agent/test_nodes/test_session_context_load.py`、`tests/agent/test_intent_adapter.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_session_context_load.py tests/agent/test_intent_adapter.py -q --tb=short` → `31 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` → `active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`；legacy intent/session wrapper 与 legacy direct test deletion checks passed。
- **剩余风险**：🟡 历史 docs/planning/test guard 中仍有 legacy name 文本，由 strict classifier 分类为 previous-state / cleanup artifact / legacy-wrapper-test，不再是 active runtime authority。本条不处理 slot、long-term-memory、approval retry historical compatibility、frontend/API fallback labels等后续 Phase 58 cleanup surfaces。

## 2026-07-08 — Phase 58-05 slot/memory legacy wrapper 文件与直接测试已删除 ✅

- **子系统**：Agent Graph / Slot Resolution / 记忆上下文
- **问题现象/根因**：Phase 54/55 已把 active graph 切到 `slot_resolution_gate` 与 `memory_context_load`，但 `extract_slots.py`、`long_term_memory_retrieve.py` 仍作为 import/test compatibility surface 存在；`test_extract_slots.py` 和部分直接测试继续把旧 filename 当成 patch/import seam。这会让 current-run slot/memory 测试继续依赖 legacy node name，阻碍 CAGM-09 no-debt 收敛。
- **影响**：旧 wrapper 文件可 import 时，后续测试、fixture 或脚本容易重新 patch legacy module path；slot prompt helper 和 memory wrapper metrics 也会让 canonical node owner 与测试 owner 漂移。
- **处理状态**：✅ 已修复验证。删除 `src/agent/nodes/extract_slots.py`、`src/agent/nodes/long_term_memory_retrieve.py`、`tests/agent/test_nodes/test_extract_slots.py`；把 slot prompt assembly helper 内部化到 `src/agent/nodes/slot_resolution_gate.py`；把 bounded candidate hint、prompt assembly、no-query case-memory skip 等非重复断言迁到 canonical `tests/agent/test_nodes/test_slot_resolution_gate.py` 与 `tests/agent/test_memory_context_load.py`；同步把受删除影响的 `tests/conftest.py`、`tests/agent/test_session_memory_integration.py`、`tests/agent/test_graph.py` retarget 到 canonical modules。
- **证据**：Phase 58 Plan 58-05；commits `0b24143`（slot RED guard）、`72b2a7d`（slot wrapper deletion）、`d60cef7`（memory RED guard）、`7a19ef3`（memory wrapper deletion）；文件 `src/agent/nodes/slot_resolution_gate.py`、`src/agent/nodes/memory_context_load.py`、`tests/agent/test_nodes/test_slot_resolution_gate.py`、`tests/agent/test_memory_context_load.py`、`tests/agent/test_graph.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_memory_context_load.py -q --tb=short` → `16 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` → `active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`；deleted wrapper/test absence checks passed；touched-file `ruff check` and `git diff --check` passed。
- **剩余风险**：🟡 历史 docs/planning/API/eval/test guard 中仍有 `extract_slots`、`long_term_memory_retrieve` 文本，由 strict classifier 分类为 historical / previous-state / cleanup artifact / legacy-wrapper-test，不再是 active runtime authority。本条不处理 approval retry historical compatibility、frontend/API fallback labels 或 eval manifest 等后续 Phase 58 surfaces。

---

# 1. 工具调用（Tool Platform）

**范围**：`src/tools/`（catalog / contracts / runtime / policy / platform / projection / validation / executors）。
**这一轮 = milestone v2.1「Tool Platform Hardening」，Phase 37–41，5 phase / 14 plan，全部标记 complete（`.planning/STATE.md`）。**
**主要契约参考**：`docs/contract-spec.md` §8.0 / §12.5 / §12.6；phase plan 若发现冲突，应先提出 spec delta。

## 2026-07-10 — Phase 64.1 审批授权、bounded capability 与终态完整性 ✅已修复验证

- **子系统**：工具调用 / approval / action draft / Agent Graph / agent-runs API-SSE / memory projection
- **问题现象/根因**：跨层审批路径原先没有一个 backend-owned decision context，前端拿到的字段不足以满足后端严格 decide schema，只能猜测或补默认值；normal auto-allow 又依赖 graph 内普通 binding，缺少 durable、server-minted、actor/action/scope/hash/handler/TTL/replay 边界。`action_draft` 无条件进入 `final_response`，API、SSE、DB 与 memory 对成功的判断也未统一，授权、store、tool 或关键 audit 失败可能被包装成 completed。Plan 06 全量回归还确认了一个优先级回归：action-draft 终态 guard 过早执行，会把已经存在的 evidence/claim verification non-allow 错归类为 draft failure。
- **影响**：旧路径无法证明用户决定对应最新 request/level/assignment/revision/hash；auto-allow 授权可能被跨 tenant/run/actor/merchant/action/handler 复用或扩成通用工具权限；失败状态可能在 graph、最终文案、持久化、SSE 和 memory 之间漂移，形成成功洗白。
- **处理状态**：✅ 已修复并通过 phase-wide 验证。`ApprovalDecisionContextV1` 由 approval service/projector 单一生成并供 list/get/SSE 共用；前端 runtime validator 对缺失或 invalid v1 必需字段 fail closed，serializer 精确回显服务端 versions/hashes，且不发送 legacy `decision` 或补造 integrity 默认值。durable opaque capability 由服务端签发并原子消费，绑定 tenant、actor、run、canonical action、payload/risk hash、merchant scope、固定 draft handler、expiry 与 replay state；它只授权 demo durable draft，不扩宽通用 ToolPolicy permission 或生产执行权限，新增的 exact pending-verification dispatch 仍只能把 capability-only 请求送到权威 verifier。post-draft terminal 改为共享 typed projector 和 conditional edge，只有 identity、`DraftOutcomeV1`、durable lifecycle 与 critical audit 全部一致才可 completed；API/SSE/DB/resume/memory 复用同一 fail-closed 语义。Plan 06 同时把 evidence/claim verification non-allow 恢复为高于 action-draft terminal guard 的权威失败，避免错误分类覆盖原始安全结论。
- **证据**：Phase 64.1 commits `89afe7e`、`fae3059`、`08777d3`、`0afddea`、`fa13100`、`80bf50a`、`4c140c6`、`e2408ec`、`a0773b8`、`8ae3c4b`；`src/approvals/schemas.py`、`src/approvals/service.py`、`src/api/routers/approvals.py`、`src/api/routers/agent_runs.py`、`src/actions/capabilities.py`、`src/actions/service.py`、`src/agent/graph.py`、`src/agent/routing.py`、`src/agent/nodes/final_response.py`、`src/api/services/agent_run_memory.py`、`tests/integration/test_phase64_1_runtime_safety_matrix.py`、`tests/architecture/test_runtime_safety_boundaries.py`、`frontend/e2e/phase64_1-approval-safety.spec.ts`。
- **验证**：Plan 06 matrix → `26 passed`；architecture ownership gate → `42 passed`，canonical graph supplemental → `21 passed`；Phase 64.1 exact backend full gate → `2862 passed, 1 skipped, 109 warnings in 837.35s`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` → `All checks passed!`；frontend chained gate → Vitest `4 files / 20 tests`、production build 通过、mocked Playwright desktop/mobile `16 passed in 1.8m`。
- **剩余风险/明确 defer**：🟡 本 phase 没有实现 Phase 66 的 general operation/tool gateway，没有处理 Phase 64.2 的 evidence/replay/memory identity，没有中央化 Phase 69 的 LLM provider/model gateway 与 observability，也没有新增生产外部副作用 executor。生产 external effects 必须进入另一个明确授权、独立 threat model/approval/rollback 门禁的 phase；不得从本条“demo durable draft 已安全”推导为生产执行已完成。现有 LangGraph/LangChain annotation/deprecation warning 仍是可见的非阻塞噪声。

## 2026-07-10 — Phase 62 business_query denied/projection no-leak 缺口已修复 ✅

- **子系统**：工具调用 / Business Query / Agent Console 投影
- **问题现象/根因**：Phase 62 code review WR-01/WR-02 发现两个 no-existence-leak 缺口：`BusinessFactService.query_business()` 在 scope denial 时返回通用 `business_query` permission error，导致 `final_response` 只能合成固定 `detail/order` payload；同时 already-projected `business_query_answer` 路径信任 `resource_label`、`result_label`、`filters_label`、`fields_label`、`cursor_label` 等 display 字段，raw cursor / tenant / denied id 标记可藏在 allowlisted label 值中进入 API 和 Console。
- **影响**：未授权 list/breakdown/compare 请求可能丢失原始 operation/resource 形状；未来 executor/test fixture 若把 `MERCHANT-SECRET`、`ORD-SECRET-DENIED` 或 raw cursor 放进 label 值，React escape 只能防 XSS，不能防业务存在性/原始 payload 泄漏。
- **处理状态**：✅ 已修复验证。WR-01 新增 typed `BusinessQueryResultV1(status="permission_denied")` denial helper，保留请求 operation/resource，清空 `merchant_id` / `resource_id` 后再进入 business_query fact/result 包装。WR-02 将 display label sanitizer 与 row value sanitizer 分离，对 projected API label 值拒绝 raw/cursor/tenant/merchant/denied-id marker，并将 `cursor_label` 收敛为 `"还有更多结果"` 枚举显示；Console 组件增加同类 display-label 防御。
- **证据**：Phase 62 review `.planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md` WR-01/WR-02；commit `07419cb`（WR-01）；`src/business/service.py:284`、`src/business/service.py:330`；`src/business/query/projection.py:203`、`src/business/query/projection.py:413`；`frontend/src/components/details/BusinessQueryResultTab.tsx:26`；`tests/business/test_business_query_service.py`、`tests/tools/test_projection.py`、`tests/test_agent_runs_api.py`、`frontend/src/components/details/BusinessQueryResultTab.test.tsx`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py::test_business_query_denied_list_returns_typed_no_leak_payload` → passed；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py::test_projected_business_query_payload_rejects_sensitive_values_inside_labels tests/test_agent_runs_api.py::test_final_response_payload_strips_sensitive_business_query_label_values` → passed；`npx tsc --noEmit --pretty false`（frontend）→ passed；`npx vitest run --environment jsdom src/components/details/BusinessQueryResultTab.test.tsx` → passed。
- **剩余风险**：🟡 label 拒绝规则是 marker-based，不是完整 DLP；若后续新增业务 ID 前缀或 cursor 文案，需要同步扩展 `projection.py` 和 Console 回归测试。当前 Phase 62 typed payload / no-existence-leak 合约已由上述 focused tests 锁定。

## 2026-07-10 — Phase 62 REVIEW-FIX iteration 2 business_query denied 外层 envelope 回归已修复 ✅

- **子系统**：工具调用 / Business Query / ToolPlatform projection
- **问题现象/根因**：Phase 62 re-review WR-01 发现上一轮只修了内层 `BusinessQueryResultV1(status="permission_denied")`，但 `_business_query_result_to_fact_result(...)` 仍把它包装成外层 `BusinessFactResultV1(status="ok", scope_check_result="allowed")` 并附带 `business_query` fact ref；`BusinessToolService._wrap_business_fact_result(...)` 因此继续把 denied business query 变成 `ToolResultV2.status="success"`，可能被 investigate 当成 authoritative allowed fact。
- **影响**：empty merchant scope 或 domain-scope denial 下，最终事实上下文可能出现 denied payload/fact ref，破坏 no-existence-leak 控制面语义；如果只把外层改成 denied 但丢弃 `data`，final/API/projection 又会失去已经脱敏的 operation/resource payload。
- **处理状态**：✅ 已修复验证。`BusinessFactService` 现在按内层 business query status 派生外层 `status`、`scope_check_result` 和 fact refs：permission denied 保留 `fact["business_query"]` 但不产生 `business_fact_refs`。`BusinessToolService` 只在 payload 可验证为 safe no-leak denied business query、且 `merchant_id/resource_id` 已清空时，把该 payload 放入 denied `ToolResultV2.data`；错误状态仍不属于 `FACT_STATUSES`，ToolPlatform projection 也不产生 resource refs。
- **证据**：Phase 62 re-review `.planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md` WR-01；文件 `src/business/service.py`、`tests/business/test_business_query_service.py`、`tests/tools/test_tool_platform.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/tools/test_tool_platform.py tests/tools/test_projection.py tests/test_agent_runs_api.py tests/eval/test_phase62_business_query_golden.py -q --tb=short` → `152 passed, 1 warning`；focused regression `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py::test_business_query_denied_list_returns_typed_no_leak_payload tests/business/test_business_query_service.py::test_business_query_tool_denial_preserves_safe_payload_without_fact_refs tests/business/test_business_query_service.py::test_business_query_invalid_inputs_fail_closed_without_querying tests/tools/test_tool_platform.py::test_tool_platform_business_query_dispatches_to_service_runtime tests/tools/test_tool_platform.py::test_tool_platform_business_query_denial_preserves_safe_payload_without_fact_refs -q --tb=short` → `5 passed, 1 warning`。
- **剩余风险**：🟡 该修复只允许当前 service 生成的 typed no-leak denied payload 进入 denied tool-result data；后续若新增其他 denied business_query shape，必须继续证明 identifier 已清空且 projection/resource refs 仍为空。

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

## 2026-07-10 — Phase 64.1 canonical action 与 deterministic risk authority ✅已修复验证

- **子系统**：意图识别 / recommendation routing / safety taxonomy / risk gate
- **问题现象/根因**：`recommendation_generation` 曾用 node-local 中英文 substring 集合判断 actionable recommendation，canonical action、alias、unknown、ambiguous 与 schema-invalid 值没有一个 material-claim 前置权威；`risk_gate` 的 fallback 又只完整检查 high risk，未命中后直接取第一条 low rule，配置中的 medium rules 在 provider timeout/unavailable/schema failure 路径可能消失并被降成 low/auto-allow。
- **影响**：中文或英文动作表达可能绕过 action claim/risk/approval；未知、歧义或 malformed action 可能进入普通 completed advice；LLM/provider/config 故障可能降低确定性风险并错误形成 auto-allowed draft 候选。
- **处理状态**：✅ 已修复并通过 phase-wide 验证。共享 `ActionResolution` 在 material claim 前统一处理 canonical/中英文 alias/strict structured input，unknown、ambiguous、schema-invalid 与 approval-chat hard negative 均稳定 fail closed；recommendation 与 router 不再维护本地 actionable authority。一个 validated deterministic evaluator 以 high > medium > low 顺序消费现有 taxonomy/rule data，拒绝缺组、空组、重复 id、未知条件和 malformed config；LLM merge 只能保留或升级确定性结论，不能降级，auto-allow 只接受 deterministic `low + allow + approval_required=false`。Plan 06 AST/source guards锁定 resolver/evaluator 单一 owner，并用中英文、provider failure、unknown/ambiguous/schema-invalid 的跨层 matrix 防止回漂。
- **证据**：Phase 64.1 commits `deb8ee3`、`74e78d7`、`e2408ec`、`a0773b8`；`src/agent/safety/taxonomy.py`、`src/agent/nodes/recommendation_generation.py`、`src/agent/nodes/risk_gate.py`、`src/agent/routing.py`、`tests/agent/test_safety_taxonomy.py`、`tests/agent/test_nodes/test_risk_gate.py`、`tests/integration/test_phase64_1_runtime_safety_matrix.py`、`tests/architecture/test_runtime_safety_boundaries.py`。
- **验证**：Plan 01 focused → `226 passed`；Plan 02 focused → `69 passed`；Plan 06 matrix → `26 passed`；Phase 64.1 exact backend full gate → `2862 passed, 1 skipped, 109 warnings in 837.35s`；全量 Ruff → `All checks passed!`。
- **剩余风险/明确 defer**：🟡 Phase 69 才负责 LLM provider/model gateway 与 observability；Phase 66 才负责 general operation/tool gateway。既有 ID-02“未校准的 LLM 自报 confidence”仍是本节独立开放债务，本次 risk no-downgrade 修复不等于完成 confidence calibration。

## 2026-07-09 — direct-response intent 缺少专用最终回复模板 ✅

**子系统**：Agent Graph / 意图识别 / final_response

**问题现象 / 根因**：本地 UI 验证发现 `small_talk` 这类 direct-response intent 在没有 recommendation draft / RAG evidence 时，会落到 `final_response._completed_response()` 的通用政策建议文案，导致 `你好` 返回“建议按已检索到的政策依据处理”。另一个相关缺口是无 ID 的订单聚合统计请求（如 `当前有多少订单`）不属于当前单订单查询能力，但缺少 deterministic unsupported guard，可能被归入 `order_status_inquiry` 并触发 slot gate 要求订单号。

**影响**：用户会误以为系统已经检索了政策证据，或误以为订单总数统计只是缺少订单号；trace 虽然可见没有进入 RAG / investigate，但最终回复文案和真实执行路径不一致，削弱 Agent Console 的可解释性。

**处理状态**：✅ 已修复验证。`contextual_intent_resolve` 新增 standalone small-talk guard 和 unsupported aggregate order-count guard；`final_response` 新增 direct-response 模板，分别处理 `small_talk`、通用 `unsupported` 和 `unsupported_reason=aggregate_order_query`。新增节点级和 graph 级回归测试，确认这两类请求直接走 `contextual_intent_resolve -> final_response`，不进入 slot gate / clarification gate，也不再使用默认政策建议话术。

**证据**：`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/final_response.py`、`tests/agent/test_nodes/test_contextual_intent_resolve.py`、`tests/agent/test_nodes/test_final_response.py`、`tests/agent/test_graph.py`；本地 live API run `3b4cb7ef-e9b3-4383-8785-7916f74e39cc`（`你好`）和 `b078fd8f-9d90-428f-924d-feeee2b90920`（`当前有多少订单`）均返回直接说明并只经过 `receive_request,safety_pre_route,session_context_load,contextual_intent_resolve,final_response`。

**验证**：`uv run ruff check src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/final_response.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py` → pass；`uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_final_response.py tests/agent/test_graph.py -q --tb=short` → `78 passed, 31 warnings`；`docker compose up --build -d` 后 API / frontend / postgres healthy，live API 验证通过。

**剩余风险**：🟡 本次只修正未支持能力的表达与路由，不实现订单总数统计。若后续要支持聚合统计，需要新增独立 intent、只读统计 tool、租户/角色权限、范围参数和 eval；不得复用单订单查询 slot gate。

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

## 2026-08-10 — Phase 64.3 format-parity fixture 生成缺少确定性 identity ✅已修复验证

- **子系统**：RAG evaluation / format-parity fixture contract / baseline identity。
- **问题现象 / 根因**：隔离临时根目录双构建验证确认，相同 Markdown、工具和字体环境下，三份 Markdown 哈希稳定，但六份 PDF 与 manifest SHA-256 全部变化。当前 `evaluation/rag_sources/build_fixtures.py` 没有固定 PDF metadata、document/trailer ID、时间字段，也没有把 builder、ReportLab/Pillow/PDFium、字体 SHA 与 raster 参数作为 generator identity 写入 manifest。
- **影响**：即使语义内容和页数/文本层完全一致，重跑 generator 也会产生新 fixture hash，导致 Phase 64.3 以 byte hash 绑定的 baseline identity 无法证明可复现；维护者也无法区分真实内容变化和容器 metadata 漂移。
- **处理状态**：✅ 已修复验证。数字 PDF 现在固定 ReportLab invariant metadata/trailer identity，扫描 PDF 固定时间、image metadata、DPI/MediaBox 与编码参数；每条 manifest record 记录同一版本化 builder/tool/font identity。隔离输出根目录间隔 1.1 秒双构建的 3 Markdown、6 PDF 与完整 manifest 逐字节一致；identity 改变时在写 manifest 前 fail closed。完整 3/9 family 已原子重生成，并通过语义 anchor/table 顺序、文本层、页数、30 页像素与 contact-sheet 目检。
- **证据**：Phase 64.3 Plan 01 Task 3，commit `76f88cc`；`evaluation/rag_sources/build_fixtures.py`、`evaluation/rag_sources/format_parity_manifest.jsonl`、`tests/eval/test_rag_format_parity_contract.py`、`evaluation/rag_sources/README.md`；focused gate `28 passed, 1 warning`，scoped Ruff lint/format 均通过；本地 renderer 排查记录见 `.planning/LOCAL-VALIDATION-ISSUES.md`。
- **剩余风险**：🟡 跨机器复现仍必须拿到相同字体字节和 manifest 记录的工具版本；identity 不同必须建立新 baseline，不能把 fixture 字节可复现夸大成 live provider 指标逐位相同。

## 2026-08-10 — Phase 64.3 parser-direct baseline 确认 Markdown / digital PDF / scanned PDF 均有质量缺口 🔴待立项

- **子系统**：RAG parser / OCR / document structure and provenance projection。
- **问题现象 / 根因**：真实 `ParserRegistry` 对固定 3-policy/9-variant corpus 的运行完成但质量失败。Markdown 三例均未命中 critical-table anchor；digital PDF 三例均 degraded 且带 `hidden_text_ignored`，同时丢失 heading/semantic/page/provenance 维度；scanned PDF 在 Tesseract 5.5.2 + `chi_sim/eng` 已可用时仍为 empty output、zero anchor recall 和 `malformed_source`。具体底层根因尚未确认，不在 Phase 64.3 evaluation-only 范围内猜测。
- **影响**：当前生产 parser/OCR 无法对等保留同一 policy 的表格、语义 anchor、页码和 provenance locator；后续 retrieval/chunking 指标会被 parser 失真前置限制，不能将该结果当成 provider unavailable 或用 deterministic fake 粉饰。
- **处理状态**：🔴 质量缺陷未修复；评估 taxonomy 已修正并验证，所有 OCR runtime 可用但 empty/garbled/zero-anchor 的结果都是 `completed_quality_fail` / `primary_stage=ocr`，而不是 unavailable 或 execution error。
- **证据**：Phase 64.3 Plan 02 commits `eec8b48`、`bce7d0c`、`a70dffb`、`f917869`；`src/rag/evaluation/parser_parity.py`、`scripts/eval_rag_parser_parity.py`、`tests/eval/test_rag_parser_parity.py`；父级门禁 `46 passed, 1 warning`；真实 CLI 输出 `parser_parity_run.v1` / `parser_direct` / 9 variants / `completed_quality_fail`。详细事故见 `.planning/LOCAL-VALIDATION-ISSUES.md` 第 33 条。
- **剩余风险 / 目标 phase**：Phase 64.4 必须消费 baseline，但只拥有 token/chunk-boundary、reindex 与 A/B；parser/OCR/table/ingestion projection 不得误归 Phase 64.4。后者统一命名为 post-Phase 64.3 `RAG Parser/OCR And Ingestion Hardening`，若未作为 64.4 的显式前置配套，则必须在 Phase 65 前正式插入 Phase 64.5，分别定位 hidden-text policy、OCR raster/input 适配与 table/page/provenance projection，不得静默 defer。

## 2026-08-10 — Phase 64.3 same-token nonzero-progress recovery 误拒绝已修复 ✅已修复验证

- **子系统**：RAG evaluation round state machine / ingestion crash recovery / immutable replay preservation。
- **问题现象 / 根因**：Plan 03 初版 runtime 只接受刚 claim 且 progress=0 的 round。即使 durable repository 已能安全分类 reservation-only、NULL-doc job-only、failure-job 或 exact-complete projection，同一 owner/run/round token 在 nonzero progress 重试时仍会被 runtime 提前拒绝。
- **影响**：合法的 crash retry 无法进入已规划的精确投影分类/CAS 恢复，会把可证明的 evaluation-owned 中间状态变成人工卡死；但不存在跨 token 放宽或广泛删除权限。
- **处理状态**：✅ 已修复验证。runtime 现在每次重新加锁并读取 durable round，继续校验 exact tenant/marker/allowlist/run token/round token/format/state/progress，然后才通过现有分类与 CAS 协议恢复。只有 exact-complete 投影可推进；reservation/job-only/failure 精确清理后重试；malformed/multiple/mismatched 继续 fail closed。
- **证据**：Phase 64.3 Plan 03 follow-up commit `16f3007`；`src/rag/evaluation/retrieval_rounds.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；focused gate `35 passed`，Plans 01–03 + facade gate `81 passed`，Phase 64.2 historical replay regression `1 passed`；真实 PostgreSQL 029 upgrade/downgrade/re-upgrade 与 immutable sentinel/trigger 保真通过。
- **剩余风险**：🟡 real-provider 三轮已在 Plan 04 完成，并产出 strict `completed_quality_fail` canonical pair；恢复协议继续由 deterministic/DB-backed tests、safe cleanup 和 baseline-eligibility 门禁保护。Observed quality misses 分别交由下述 Phase 64.4 chunk-boundary、Phase 64.5 parser/ingestion 与命名 retrieval follow-up，不把 evaluation runtime 修复误报成生产质量已通过。

## 2026-08-10 — Phase 64.3 evaluation/production checksum bridge ✅已修复验证

- **子系统**：RAG evaluation isolation / production ingestion job identity。
- **问题现象 / 根因**：evaluation round owner 持有 64 位裸 SHA-256，production `RagIngestionJob.source_checksum` 持久化 `sha256:<digest>`；exact attempt lookup、projection classification 与删除因此无法证明同一 job，真实 provider round 被阻断。
- **影响**：合法 evaluation attempt 会被误判为 reservation-only/malformed，无法安全恢复或 cleanup；若改成宽松 doc-key 查询又会扩大删除边界。
- **处理状态**：✅ 已修复验证。只在 evaluation exact-attempt seam 增加严格单向 owner digest canonicalization，lookup/all-attempt/delete 均使用同一 production representation；任意非 64-hex 或已带前缀输入继续拒绝，未新增 doc-key-only 删除。
- **证据**：Phase 64.3 Plan 03 RED/GREEN commits `4c00863` / `c4b71c3`；`src/repositories/rag_evaluation_round_repo.py`、`src/repositories/rag_ingestion_job_repo.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；sealed Plan 05 focused gate 143 passed，expanded RAG/eval/parser/knowledge regression 442 passed。
- **剩余风险**：当前 bridge 仅服务固定 evaluation owner 的 exact attempt，不是全局 checksum alias API；后续必须保留 strict input pattern、tenant/doc/checksum/reservation tuple 与 CAS deletion。

## 2026-08-10 — Phase 64.3 retrieval implicit transaction leak ✅已修复验证

- **子系统**：RAG evaluation runtime / production KnowledgeService retrieval / cleanup transaction boundary。
- **问题现象 / 根因**：production search 与 recording capture 留下 SQLAlchemy implicit transaction；随后 `session.begin()` 执行 exact cleanup 时因已有 transaction 失败，并把真实 stage reason 覆盖成 cleanup/execution error。
- **影响**：三轮 provider baseline 无法在 retrieval observation 后证明 zero-residual cleanup；错误归因也会从质量 miss 漂移为 evaluator error。
- **处理状态**：✅ 已修复验证。每次 service search 与单次 recorded capture 都在短事务内完成，离开该边界前 commit/rollback，cleanup 才开启自己的 exact transaction；未修改 production retrieval/rerank 逻辑或指标。
- **证据**：Phase 64.3 Plan 03 RED/GREEN commits `7ea1b99` / `be32691`；`src/rag/evaluation/retrieval_rounds.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；Plan 04 real-provider 三轮完成，sealed Plan 05 143/442 tests 与 scoped Ruff 通过。
- **剩余风险**：当前无已知未闭合 transaction；后续调整 KnowledgeService capture 顺序时必须继续断言 search observation 与 cleanup 不共享隐式 transaction。

## 2026-08-10 — Phase 64.3 controlled scanned progression ✅已修复验证

- **子系统**：RAG evaluation runtime / scanned ingestion quality taxonomy / immutable isolation。
- **问题现象 / 根因**：OCR runtime 可用时，scanned fixture 的真实 `malformed_source` 属于本次待记录的 parser/OCR 质量结果；旧 runtime 却把第二次 persisted failure 一律当 execution error，无法完成 honest red baseline。
- **影响**：scanned parser/OCR 质量缺口会被错误描述为 evaluator 不可用，Phase 64.3 无法对三种格式给出 completed attribution。
- **处理状态**：✅ 已修复验证。仅允许 scanned-PDF 的第二次真实 persisted `malformed_source` 在 exact job deletion、zero-residual current proof 和 immutable non-regression 后推进并记录 quality failure；其他 error code、format、次数或 projection 一律 fail closed。
- **证据**：Phase 64.3 Plan 03 RED/GREEN commits `bb88d1d` / `9186cb9`；`src/rag/evaluation/retrieval_rounds.py`、`src/repositories/rag_evaluation_round_repo.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；post-review canonical report 为 `completed_quality_fail`、54 cases/45 failures。
- **剩余风险**：🔴 此条只修复 evaluation taxonomy；production OCR 的 macOS temp-path 和错误分类缺口仍见下一条，不得把 controlled progression 解释成 OCR 已修复。

## 2026-08-10 — Phase 64.3 evaluator deep-review WR-01–WR-08 hardening ✅已修复验证

- **子系统**：RAG format-parity evaluation / locator proof / strict report / round recovery / cleanup isolation。
- **问题现象 / 根因**：deep review 与 iteration 2 确认评测器仍有多类可信度缺口：retrieval locator coverage 可由 rank 推断而非绑定实际 recorded provenance/source block；PDF anchor 未按 case-specific allowed page 验证；case classification 与 strict report 的 target、parser input、metrics、gate、failure/outcome 可能彼此矛盾；same-token resume 没有完整校验 UUIDv5 round identity、lease/state/projection，也没有把 stable input/time/mode/provider/rollout identity 持久封印到每轮；final write crash 后无法在精确 terminal proof 上安全恢复；retrieval-ready/cleanup 未重新核验 exact projection；orphan jobs 可能漏计；invalid contract 可能被误归 prerequisite unavailable。
- **影响**：这些缺口不会直接改变生产检索行为，但会让错误或自相矛盾的 artifact 获得 baseline 资格、让 locator 分数高估、让不同输入的同 token 恢复混线、让 final crash 遗留无法证明的状态，或把评测器故障伪装成环境缺失。
- **处理状态**：✅ 已修复验证。首轮 WR-01–WR-07 已关闭 locator/page、strict report、round/projection/cleanup、orphan job 与 invalid-contract 边界；iteration 2 进一步要求 anchor 绑定 exact recorded source block（`89a90c8`），从 canonical measurements 重导并校验 case classifications（`01429a7`），并把 allowlisted run identity SHA-256 持久化到所有 durable rounds、在 claim/resume/rebuild/final crash recovery 上逐次精确验证（`638b5b4`，WR-04/WR-08）。全部修复 commits 为 `8105b3e`、`175149e`、`dc26464`、`ee9f367`、`3299e66`、`89a90c8`、`01429a7`、`638b5b4`。
- **证据**：sealed canonical commit `dbaef79`，run token `64f30400-0000-4000-8000-000000000008`，generated at `2026-08-10T16:00:00Z`；三轮 durable rows 共用 1 个 64-char `run_identity_hash`：`4a4e7557c0b6132cb8070e42e00cd4be7eeb1bca4569b34d06dd7e8487cb8b7a`，allowlisted field machine gate 可离线重算同值。Strict result 为 `completed_quality_fail` / `baseline_eligible=true` / `full_provider`，54 cases/45 failures，overall locator coverage 0.333333，PDF locator gate 0.528571，6 个 parser gate inputs；JSON/Markdown SHA-256 分别为 `c4dc6f8ee7a154a416b4474691b0bff98c4d608a7d160f76583db9030f7c1bae` / `8b882a9ad7d6de3b5c44d4bb2b0690a1a588a3fd13df169374857d386fb7652e`。验证为 focused 143 passed、expanded 442 passed、scoped Ruff 与 stable-base production diff 全绿；current blocks/chunks/jobs 0/0/0、immutable documents/chunks 9/53，container/process/diagnostic clean。
- **剩余风险**：本条只关闭 evaluation trust boundary，不表示生产质量已修复。下面已登记的 production `OcrEngine` macOS temp/error taxonomy、pdfplumber hidden-text false positive、table/provenance projection 与 exact-cleanup `reused_binding` 重建债务仍保持 🔴，继续由 post-Phase 64.3 `RAG Parser/OCR And Ingestion Hardening` / Phase 64.5（若非 64.4 显式前置）负责；Phase 64.4 仍只拥有 token/chunk-boundary、reindex 与 A/B。

## 2026-08-10 — Production `OcrEngine` macOS temp symlink 路径与错误分类 🔴待立项

- **子系统**：RAG production parser / OCR runtime boundary。
- **问题现象 / 根因**：同一三份 scanned fixture 的 15 页在 macOS platform-default symlink temp mode 下由 pytesseract/Tesseract/Leptonica 读取失败，realpath-normalized mode 下 15/15 OCR 成功。`OcrEngine.parse_image()` 直接将 Pillow image 交给 pytesseract，并把除 timeout 外的 RuntimeError/Exception 全部收敛为 `malformed_source`（`src/rag/parsers/ocr.py:53-70,157-164`），无法区分 source malformed 与 temp runtime transport failure。
- **影响**：有效扫描文档可能因主机 temp path 表示而失败，并被错误归因为源文件损坏；command-level normalization 依赖运维记忆，跨入口不一致。
- **处理状态**：🔴 待立项。Phase 64.3 只以 safe enum `explicit_macos_private_tmp` 记录并归一化 final baseline 环境，没有修改 production parser。
- **证据**：Phase 64.3 Plan 04 commit `518b26b` 与 `64.3-04-SUMMARY.md`；`src/rag/parsers/ocr.py:53-70,157-164`；canonical report 记录 Tesseract 5.5.2 和 safe temp mode；本地事故细节见 `.planning/LOCAL-VALIDATION-ISSUES.md` 同日条目。
- **剩余风险 / 目标 phase**：由 post-Phase 64.3 `RAG Parser/OCR And Ingestion Hardening` 修复 production temp input realpath/文件生命周期与安全错误 taxonomy；不属于 Phase 64.4。若未作为 64.4 显式前置配套，则 Phase 64.5、Phase 65 前立项。

## 2026-08-10 — pdfplumber 0.11.10 unsupported rendering attrs 触发 digital hidden-text false positive 🔴待立项

- **子系统**：RAG production PDF parser / hidden-text detection / provenance。
- **问题现象 / 根因**：当前环境 pdfplumber 0.11.10；`_page_words()` 请求 `rendering_mode` 与 `text_rendering_mode` extra attrs（`src/rag/parsers/pdf.py:259-274`），该版本不提供这些 word attrs 时 exception 被吞并返回空列表。`_visible_page_text()` 随后看到 raw text 非空却无 visible words，统一发出 `hidden_text_ignored` 并丢弃可见 digital text（`src/rag/parsers/pdf.py:277-308`）。
- **影响**：正常 digital PDF 被误判为隐藏文本，导致 semantic anchor、heading、table 与 PDF locator gate 大面积失败；错误吞并还让工具版本不兼容难以定位。
- **处理状态**：🔴 待立项。Phase 64.3 保留 false positive 与质量红线，没有删掉 hidden-text safety guard 或修改 production parser。
- **证据**：`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import pdfplumber; print(pdfplumber.__version__)"` -> `0.11.10`；`src/rag/parsers/pdf.py:259-308`；Plan 04 canonical gates digital-PDF anchor 0.314286、PDF locator 0.528571，failure attribution保持真实。
- **剩余风险 / 目标 phase**：post-Phase 64.3 `RAG Parser/OCR And Ingestion Hardening` 必须做版本兼容的 attrs 能力检测/降级，并保留真正 invisible text 的 fail-safe；不归 Phase 64.4。若未作为其显式前置配套，则 Phase 64.5、Phase 65 前立项。

## 2026-08-10 — exact cleanup 后 production `reused_binding` 不能重建 current projection 🔴待立项

- **子系统**：RAG production ingestion / immutable binding reuse / evaluation current-projection isolation。
- **问题现象 / 根因**：evaluation cleanup 合法删除 current blocks/chunks并保留 document head/immutable versions（`src/repositories/rag_evaluation_round_repo.py:440-469`）。相同 fingerprint 再摄取时 production ingestion 可命中 `reused_binding`，却只对 cleanup 后为空的 `locked_chunks` 投影 sequence并把它作为 `persisted_chunks`，不会写入新解析出的 `db_blocks/db_chunks`（`src/rag/ingestion.py:358-381`）。
- **影响**：head 与 exact immutable binding 仍存在时，current projection 无法从相同内容安全重建；后续 ingestion job 可报告 success/zero chunks，而 retrieval round 得到不完整 projection。
- **处理状态**：🔴 待立项。旧 provider attempt 已诊断该组合边界；Phase 64.3 没有越界修改 production ingestion，也没有通过删除 immutable history或 broad reset规避。
- **证据**：`src/rag/ingestion.py:358-381`、`src/repositories/rag_evaluation_round_repo.py:440-469`；Plan 05 stable-base diff 证明 production ingestion 未被 Phase 64.3 修改；本地事故见 `.planning/LOCAL-VALIDATION-ISSUES.md` 同日条目。
- **剩余风险 / 目标 phase**：由 post-Phase 64.3 `RAG Parser/OCR And Ingestion Hardening` 定义“exact binding 存在但 current projection 缺失”的安全 rebuild contract 与 integration RED；不属于 Phase 64.4 token/chunk-boundary。若未作为 64.4 显式前置配套，则 Phase 64.5、Phase 65 前立项。

## RAG-56-03-01：RAG context routing status drift 与 partial action/risk 漏挡 ✅已修复验证

- **问题现象/根因**：`route_after_rag_context` 原本在 router 内维护一份手写 `RAG_CONTEXT_STATUSES`，虽然当时与 schema 一致，但存在后续 drift 风险；同时顶层 `rag_context_status` 缺失时会回退读取 `verified_evidence_package.status`，`no_evidence` 携带 missing business facts 时会先进入 `clarification_gate`，`partial` 允许谓词也没有覆盖 action intent、`risk_signals`、`evidence_policy.risk_level`、package stale/conflict/rejected evidence 指示，导致 unsafe evidence 或 action/risk-bound partial 可能进入 generation。
- **影响**：RAG 证据包状态与路由状态不是单一词表来源，且 `partial` 的低风险边界不够可穷举；在 Phase 56 CAGM-07 目标下，这会让 unsafe evidence 或未充分验证的 partial context 进入 recommendation generation。
- **处理状态**：✅ 已修复验证。`src/agent/routing.py` 改为从 `src.knowledge.schemas.RAG_CONTEXT_STATUSES` 派生 router 词表；缺失/未知/malformed 顶层 `rag_context_status` 和 unsafe statuses fail closed 到 `final_response`；`partial` 只允许低风险 `policy_qa` 或 answer-only fact intent，且 action/risk/unsafe evidence 指示一律 fail closed。
- **证据**：Phase 56 Plan 56-03 Task 1；`src/agent/routing.py`（`RAG_CONTEXT_STATUSES` schema 派生、`_route_after_rag_context`、`_partial_rag_context_can_generate`、`_action_bound_or_high_risk`、`_partial_rag_has_unsafe_evidence_indicator`）；`tests/agent/test_rag_context_routing.py`（schema equality、exact status set、unsafe statuses、missing/unknown/malformed status、partial action/risk/unsafe evidence matrix）；验证命令 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` 通过，55 passed。
- **剩余风险**：本条只证明 deterministic route gate 阻断 unsafe RAG status 进入 generation；stale candidate refs 不会成为 approval snapshots、risk lowering 或 action authority 的下游端到端证明仍按 Phase 56 final closeout / risk-action 测试边界处理，不在 56-03 Task 1 过度声称。

## RAG-56-03-02：claim_verify 后 proposed_action 可绕过显式 action claim allowance ✅已修复验证

- **问题现象/根因**：`route_after_claim_verify` 原本在 canonical bundle 为 `verified/continue` 后，只要 state 中存在 `proposed_action`、任意 risk signal，或任意 allowed `action_recommendation` claim result，就路由到 `assess_risk_and_approval`。这让已有 `proposed_action` 在没有显式 allowed action-recommendation claim result 时也能进入风险/审批路径；第一轮修复又过度收紧，把尚未 materialize `proposed_action` 的 verified low-risk action recommendation 也挡到 `final_response`。
- **影响**：claim verification bundle 的 action authority 边界不够精确时，unsupported action claims 可能过早进入风险节点；边界过度收紧时，`recommendation_generation` 产出的 low-risk actionable draft 无法进入当前 Phase 57 风险节点构造 `proposed_action`、snapshot 与 auto-allowed binding。
- **处理状态**：✅ 已修复验证。`src/agent/routing.py` 现在按 repaired decision table 执行：已有 `proposed_action` 时必须存在 `_has_verified_action_recommendation(state)` 才能进入 `assess_risk_and_approval`；没有 `proposed_action` 时，verified allowed `action_recommendation` claim 或独立 risk signal 可以进入当前 Phase 57 风险节点；legacy `verification_route` / `verifier_status` / `verifier_reason_codes` 不能绕过 canonical bundle。
- **证据**：Phase 56 Plan 56-03 Task 2 与 Phase 56 REVIEW iteration 2 WR-01；`src/agent/routing.py`（`_route_after_claim_verify` decision table）；`tests/agent/rag_context/test_routing.py`（unsupported proposed action negative、allowed action recommendation positive、no-preexisting-proposed-action positive、non-action risk positive、legacy verifier non-authority cases）；`tests/test_graph_routing.py`（low-risk `recommendation_draft` + verified `action_recommendation` + no `proposed_action` route to `assess_risk_and_approval`）。
- **剩余风险**：本条保持 `assess_risk_and_approval` 为 Phase 57 当前节点，不处理 `risk_gate` rename；final_response 对 legacy verifier projection 的展示/历史兼容收敛仍属 56-04。

## 2026-07-07 — Phase 56 review-fix：action/tool authority 最终边界补强 ✅已修复验证

- **子系统**：RAG claim verification / Agent Graph / 工具调用 action draft 边界
- **问题现象/根因**：Phase 56 第一轮只在 graph/risk 层要求 positive `action_recommendation` claim，`action_draft()` 最终写边界仍只挡显式 negative action claim；verified/continue 但空 claim bundle 或仅 policy/business claim 的状态，理论上可在 stale approval、direct node call 或未来 graph path 下触达 `create_coupon_grant_draft`。
- **处理状态**：✅ 已修复验证。`action_draft()` 复用 `src.agent.routing._has_allowed_action_recommendation`，在存在 `proposed_action` 时要求 bundle 为 `continue`、`verified/not_required`、无 blocked claims，且至少有 `claim_type="action_recommendation"` 且 `allows_action_recommendation is True`；否则返回 `VERIFIER_NOT_ALLOW`，不调用 action tool。WR-01 同步恢复 no-preexisting-`proposed_action` 的 verified action recommendation 到 risk route，让 risk 节点负责构造后续 binding。
- **证据**：Phase 56 REVIEW iteration 2 CR-01/WR-01；commit `cb3ec9a`；`src/agent/nodes/action_draft.py`、`src/agent/routing.py`、`tests/agent/test_phase22_action_boundary.py`、`tests/test_graph_routing.py`、`tests/agent/rag_context/test_routing.py`。
- **剩余风险**：🟡 Phase 57 仍负责把当前 `assess_risk_and_approval` 收敛为 canonical `risk_gate`/approval boundary；本次只修复 Phase 56 claim authority 与最终 action draft write boundary，不删除历史 compatibility aliases。

## RAG-57-02-01：approved resume reconciliation 缺少 explicit action claim allowance ✅已修复验证

- **子系统**：RAG claim verification / approval resume / action draft boundary
- **问题现象/根因**：Phase 56 将 `action_draft()` 收紧为存在 `proposed_action` 时必须有 explicit allowed `action_recommendation` claim result，但 approval API 的 approved resume reconciliation 仍用空 `claim_results` 的 `_approved_resume_claim_bundle()` 代表已审批动作。结果是 trusted approval approve/accept 路径在恢复后调用 `action_draft()` 时被 `VERIFIER_NOT_ALLOW` fail closed，`AgentRun.final_status` 变成 `error`。
- **影响**：可信审批通过后的 demo action draft reconcile 可能无法创建草稿，用户/trace 看到 approval 已通过但 run 以 error 收尾；如果直接放宽 `action_draft` 又会破坏 Phase 56 的最终写边界。
- **处理状态**：✅ 已修复验证。`_approved_resume_claim_bundle()` 现在显式产出 approval-service-owned `claim_type="action_recommendation"`、`support_status="supported"`、`allows_action_recommendation=True` 的 claim result，并保留 `action_draft()` 的 allowed action claim gate。
- **证据**：Phase 57 Plan 57-02 Task 1；`src/api/routers/approvals.py::_approved_resume_claim_bundle`；`src/agent/nodes/action_draft.py::_claim_bundle_blocks_action`；`tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval`、`tests/test_approval_api.py::test_agent_run_status_updates_to_completed_after_service_resume`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_agent_run_status_updates_to_completed_after_service_resume -q --tb=short` → `2 passed, 1 warning`；Task 1 full command → `231 passed, 1 skipped, 28 warnings`。
- **剩余风险**：🟡 本条只修复 approved resume reconciliation 与 final action-draft boundary 的 claim allowance 对齐；Phase 57 后续计划仍负责 projection/docs/debt closeout，Phase 58 仍负责 legacy alias final cleanup。

## RAG-56-04-01：recommendation_generation active cutover、trace/API 投影与 final_response authority 收敛 ✅已修复验证

- **问题现象/根因**：Phase 56 前后存在三类会混淆当前 authority 的残留面：active graph 已切向 `recommendation_generation`，但 graph vocabulary/API/frontend/eval/docs 仍可能把历史 `generate_recommendation` 读成当前 runtime owner；`final_response` 仍可能从 legacy `rag_verification` / `verification_route` / `verifier_status` / `verifier_reason_codes` 构造当前-run 权威 route payload；当前源码图和 validation artifact 仍可能保留旧节点名或旧测试入口。
- **影响**：历史 trace 可以读，但如果投影和最终回复 authority 不分层，当前-run 缺少 `claim_verification_bundle` / `verified_evidence_package` 时可能被 legacy verifier 字段误判为安全；后续 Phase 57/58 也容易误删或误保留 compatibility surface。
- **处理状态**：✅ 已修复验证。`src/agent/graph_vocabulary.py` 将 `recommendation_generation` 标为 runtime node，并将 `generate_recommendation -> recommendation_generation` 标为 Phase 56 `compatibility_alias`，reason codes 包含 `PHASE_56_COMPATIBILITY_ALIAS`、`HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。API/SSE/frontend/eval 当前投影识别 `recommendation_generation`，历史 `generate_recommendation` 保留可读且不重写原始 implementation node。`final_response` 的 route payload authority 顺序已收敛为 `claim_verification_bundle` 优先，其次 `verified_evidence_package`；legacy verifier fields 只有在已有历史/compatibility marker 时才作为非权威 historical fallback，否则 fail closed 为 non-authoritative manual review。当前 docs/validation artifact 已同步 active `recommendation_generation`，同时明确 `assess_risk_and_approval` 仍属 Phase 57、`generate_recommendation` alias/wrapper 删除仍属 Phase 58。
- **证据**：Phase 56 Plan 56-04；commits `54290f0`（vocabulary RED tests）、`920c265`（vocabulary implementation）、`4915a38`（API/final-response RED tests）、`2abf5c7`（projection/final-response implementation）；文件 `src/agent/graph_vocabulary.py`、`src/api/routers/agent_runs.py`、`frontend/src/components/timeline/TimelineStep.tsx`、`scripts/eval_agent.py`、`src/agent/nodes/final_response.py`、`tests/agent/test_graph_vocabulary.py`、`tests/agent/test_trace.py`、`tests/test_trace_api.py`、`tests/test_agent_runs_api.py`、`tests/agent/test_nodes/test_final_response.py`、`tests/agent/test_phase22_final_response.py`、`docs/current-langgraph-architecture.md`、`.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_final_response.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_facade_integration.py -q --tb=short` → `474 passed, 1 skipped, 32 warnings`；focused Ruff → pass；Phase 56 artifact command scan → pass；`UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` → pass。
- **剩余风险**：🟡 Phase 57 仍负责 `assess_risk_and_approval -> risk_gate` active rename 与 approval/risk boundary canonicalization；🟡 Phase 58 仍负责删除 retained `generate_recommendation` wrapper/import/test/historical display compatibility 和其他 Phase 53-56 alias surfaces。本条不启用 `risk_gate`，也不删除 recommendation compatibility alias/wrapper。

## RAG-56-REVIEW-FIX-01：missing-info action draft 与 partial evidence direct-node guard 漏挡 ✅已修复验证

- **子系统**：RAG / claim verification / recommendation_generation / action recommendation final rendering
- **问题现象/根因**：Phase 56 review 发现两个同源边界漂移：一是带 `missing_info` 的 actionable `recommendation_draft` 会经 `route_after_recommendation -> final_response`，最终被 `_completed_response` 渲染成 `final_status=completed`；二是 direct `generate_recommendation` compatibility surface 对 partial evidence 的允许条件弱于 router，漏掉 `approval_decision`、action-bound intent、`risk_signals`、`evidence_policy` high risk 以及 stale/conflict/rejected refs 等阻断条件。
- **影响**：缺少业务事实或证据不完整时，用户可见最终回复可能误显示动作建议已完成；直接调用历史 node surface 时，partial RAG context 可能绕过 graph router 的 fail-closed 策略进入生成。
- **处理状态**：✅ 已修复验证。`final_response()` 在 completed branch 前对 `_displayable_missing_info(draft)` fail closed，转为 `insufficient_evidence`；`generate_recommendation._partial_package_can_generate()` 改为复用 router 的 `_partial_rag_context_can_generate()`，删除 direct node 的弱复制 guard。
- **证据**：Phase 56 REVIEW WR-01/WR-02；commit `d9ee345`（WR-01）；本条所在提交（WR-02）；`src/agent/nodes/final_response.py`、`src/agent/nodes/generate_recommendation.py`、`tests/agent/test_phase22_final_response.py`、`tests/agent/test_nodes/test_generate_recommendation.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_final_response.py::test_missing_info_action_draft_downgrades_before_completed_response -q --tb=short` → passed；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py::test_partial_package_direct_generation_uses_router_blockers -q --tb=short` → 7 passed。
- **剩余风险**：🟡 本次只对当前 renderer 和 retained `generate_recommendation` compatibility surface 补 fail-closed guard；Phase 58 仍需删除 legacy direct import/wrapper 面，Phase 57 仍负责 risk/approval canonical boundary rename。

## RAG-56-REVIEW-FIX-02：allowed claim bundle 被 legacy allow 字段误判为 missing canonical projection ✅已修复验证

- **子系统**：RAG / claim verification / final_response authority / action draft final rendering
- **问题现象/根因**：Phase 56 REVIEW IN-01 补齐 approved action-draft CI graph contract 后，`GS-28 approval_approved` 已成功经过 `approval_gate -> action_draft -> final_response`，并带有合法 `draft_outcome.v1(status=not_executed_demo, external_side_effect=false)`；但最终回复仍进入 `missing_canonical_projection` manual-review 分支，没有告知「补偿草稿已创建」和「演示模式未执行任何外部动作」。根因是 `claim_verify` 为兼容旧 surface 同时写 `verification_route=allow` / `verifier_status=verified`，`final_response._verification_route_payload()` 在 canonical `claim_verification_bundle(route=continue, overall_status=verified)` 允许继续后，又把这些 legacy allow 字段误判为缺少 canonical projection。
- **影响**：已通过 canonical claim verification 且成功创建 demo action draft 的 approved path，用户可见回复会错误显示「需要人工复核，未创建审批请求或动作草稿」，与实际 trace/action outcome 不一致；同时 CI graph contract 无法覆盖 approved draft 的最终用户可见语义。
- **处理状态**：✅ 已修复验证。`final_response` 新增 `_claim_verification_allows_response()`，当 canonical claim bundle 明确 `continue + verified/not_required + no blocked_claims` 时，legacy allow 字段不再触发 missing-canonical fail-closed；blocked/manual-review canonical bundle 仍优先 fail closed。`scripts/eval_agent.py` 已将 `approval_approved` 纳入 `GRAPH_CONTRACT_CATEGORIES`，CI action stub 输出完整 current `draft_outcome.v1` / `action_draft.v2` demo payload，并断言 approved graph summary 包含 `approval_gate`、`action_draft`、`final_response` 与无外部副作用的草稿创建回复。
- **证据**：Phase 56 REVIEW IN-01；文件 `src/agent/nodes/final_response.py`、`scripts/eval_agent.py`、`tests/agent/test_nodes/test_final_response.py`；本地失败记录见 `.planning/LOCAL-VALIDATION-ISSUES.md` 同名条目。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_final_response.py -q --tb=short` → `21 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import asyncio; from scripts.eval_agent import DEFAULT_GOLDEN_SET, _load_cases, _run_ci_graph_contracts; failures = asyncio.run(_run_ci_graph_contracts(_load_cases(DEFAULT_GOLDEN_SET))); print({'failures': failures}); raise SystemExit(1 if failures else 0)"` → `{'failures': []}`。
- **剩余风险**：🟡 本条只修复 legacy allow 字段与 canonical claim bundle allowed 状态的 final rendering 冲突；Phase 58 仍需清理 retained legacy verifier fields / compatibility alias surfaces。

## 2026-08-05 — Phase 64.2 Plan 01 Task 1 证据 identity 多点别名与可变版本绑定已收敛 ✅已修复验证

- **子系统**：RAG / evidence identity / tenant-scope trust boundary。
- **问题现象 / 根因**：现有 `EvidenceRefV1.build` 与多个检索调用方使用 `doc_key/chunk_id@vN` 展示别名，identity 未覆盖 tenant、精确 policy scope、不可变 document/chunk version row 与完整 text hash；旧别名语法本身也没有可信持久化解析边界。
- **影响**：调用方可本地重建或伪造看似有效的 evidence id；同 tenant 跨 scope、版本替换和 legacy ambiguity 无法由一个 owner 稳定区分，历史 replay 也不能据此证明消费的是原始不可变证据。
- **处理状态**：✅ `src/knowledge/evidence_identity.py` 成为 `evidence_identity.v1` 唯一 hash/mint/validate/resolve owner，固定 `scope_type="tenant_policy"` 与 `scope_id=str(tenant_id)`，所有失败对外统一为 `evidence_unavailable`、对内保留稳定 reason code；`EvidenceRefV1` 仅扩展这一份 schema 承载完整 immutable binding，旧 alias 只能作为显式 compatibility input，不能凭语法升级为 canonical。
- **证据**：Phase 64.2 Plan 01 Task 1；RED commit `4d9eff6`，GREEN commit `cb6ded5`，format commit `74d0f1b`；`src/knowledge/evidence_identity.py`、`src/knowledge/schemas.py`、`tests/knowledge/test_evidence_identity.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge/test_evidence_identity.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_text_hash.py -q --tb=short` → `26 passed, 1 warning`；对应 scoped Ruff → `All checks passed!`。
- **剩余风险**：🟡 当前 ingestion/retrieval 仍由后续 Plan 02 安装 dual-write、backfill/reconciliation 与 canonical-read cutover；Task 1 有意保留旧 `EvidenceRefV1.build` 为无 canonical binding 的兼容输入，不把它误报为已迁移生产 writer。

## 2026-08-05 — Phase 64.2 Plan 01 Task 2 可变证据头缺少不可变 replay 基础已收敛 ✅已修复验证

- **子系统**：RAG ingestion persistence / immutable evidence retention / replay dependency foundation。
- **问题现象 / 根因**：现有 `PolicyDocument` 版本号和内容原地更新，`PolicyChunk` 在 re-ingestion 时整批替换；数据库没有保留 exact document/chunk version content、精确 scope/hash/locator，也没有 replay snapshot 到历史证据的 restrictive dependency。旧 migration chain 因而无法阻止审计保留期内的历史证据被改写或删除。
- **影响**：旧 run 只能再次解析可变 head/别名，不能证明原始版本；expiry/tombstone/purge 或 schema downgrade 可能丢失 replay 所需内容与 locator；并发 cutover 也缺少数据库单调 sequence 与 CAS rollout 基础。
- **处理状态**：✅ migration 025 以 expansion-only 方式新增 append-only `policy_document_versions` / `policy_chunk_versions`、精确 `tenant_policy` 字符串 scope/composite identity FK/hash/locator constraints、immutable update 与 retention delete triggers、`evidence_snapshot_dependencies` restrictive FK、nullable head sequence/snapshot columns、数据库原生 `evidence_ingestion_write_seq`，以及默认 inactive 的 singleton rollout/CAS row；downgrade 在存在历史、snapshot dependency/JSON 或 active rollout state 时拒绝执行。
- **证据**：Phase 64.2 Plan 01 Task 2；RED commit `d3b8be3`，GREEN commit `b175ae1`；`src/db/models.py`、`src/db/migrations/versions/025_phase64_2_immutable_evidence.py`、`tests/knowledge/test_immutable_evidence_migration.py`。
- **验证**：从真实 PostgreSQL 024 schema seed mutable heads 后升级 025，证明 immutable/version/dependency 行数均为 0、head sequences 为 NULL、rollout inactive、sequence 严格递增；随后验证错误 scope insert、immutable content update、retained delete 与 downgrade 均 fail closed。Task 2 计划命令结果为 `9 passed, 4 warnings`，scoped Ruff/format/whitespace 门禁通过。
- **剩余风险**：🟡 migration 025 有意不安装生产 dual-write、不复制 mutable heads、不启用 canonical reads；Plan 02 仍需以 rollout-first lock/CAS 安装 writer、watermarked reconciliation/backfill 与 operational rollback，Plan 06 才负责 production replay emitter/snapshot 写入。

## 2026-08-05 — Phase 64.2 Plan 02 Task 1 ingestion 与 cutover 锁序/sequence/immutable binding 已收敛 ✅已修复验证

- **子系统**：RAG ingestion / immutable evidence dual-write / rollout CAS。
- **问题现象 / 根因**：Plan 01 前的生产 ingestion 只锁可变 `PolicyDocument`，更新 head 后删除并重建 chunks；writer 不参与 singleton rollout epoch，也不分配数据库原生 sequence，更不会在同一事务追加 immutable document/chunk version。相同内容重摄取仍替换 current chunks，因此无法证明 watermark 两侧的 unchanged write 复用同一 immutable binding。
- **影响**：最终 zero-gap cutover 可能与仍在发布可变 head 的 writer 交错；成功写入可能没有可对账 sequence 或不可变版本；失败写入可能让 current projection 与 immutable history 分叉；exact `tenant_policy` scope/hash 只能停留在 schema，而未进入真实 writer。
- **处理状态**：✅ 新增 `EvidenceVersionRepository` 作为 rollout lock/CAS、sequence、immutable append/exact binding 的唯一 owner；生产 `AsyncSession` writer 固定先锁 `evidence_identity_rollouts(id=1)` 并校验 expected epoch/dual-write，再锁 document/current chunks，成功 ingestion 恰分配一个 sequence。first/changed/correction 在同一事务写 exact `scope_type="tenant_policy"`、`scope_id=str(tenant_id)` 的 immutable document/chunk rows与 current projection；unchanged 只有在 document/chunk identity/hash 全量吻合时复用原 binding、保持 immutable row count，仅推进 current sequence。任一 append/current mutation 失败统一 rollback。
- **证据**：Phase 64.2 Plan 02 Task 1；RED commit `73afc55`；`src/repositories/evidence_version_repo.py`、`src/repositories/policy_chunk_repo.py`、`src/rag/ingestion.py`、`tests/knowledge/test_evidence_cutover.py`。
- **验证**：计划 Task 1 focused pytest 为 `14 passed, 1 warning`，并补跑既有 ingestion/job 回归；scoped Ruff 为 `All checks passed!`。PostgreSQL 断言覆盖 activation-before-backfill、stale epoch、first/unchanged/correction/concurrent-change sequence、stored scope/hash/binding row-count parity 与失败原子回滚。
- **剩余风险**：🟡 Task 2 仍需让 migration 026 执行 staged watermark/backfill/reconciliation，并以真实双 session 两种边界交错证明 final activation 与 writer 共享同一锁/epoch；Task 3 仍需切换 canonical-only current reads 和 operational disable/quarantine/re-enable。当前 test-double compatibility 分支仅服务不具备 SQLAlchemy transaction/execute 能力的历史 parser 单元测试，不构成生产 writer fallback。

---

## 2026-08-06 — Phase 64.2 Plan 09 RAG 跨系统完整性门禁闭环（`phase64.2-rag-integrity:implemented`）✅已修复验证

- **问题现象 / 根因**：evidence identity、cutover、approval snapshot 与 replay snapshot 已分别落地，但缺少一个跨系统门禁证明新写只使用 exact canonical identity，也缺少对 caller-local serializer、raw append、mutable-head replay 与错误 scope 扩散的统一回归保护。
- **影响**：单个 owner 的测试即使通过，后续调用方仍可能重引入 reduced/legacy ref、绕过 repository validation，令审批或历史 replay 无法绑定原始 immutable evidence。
- **处理状态**：✅已修复验证。Phase `64.2-09` 新增真实 current/retained replay 与 negative authority matrix，并用 AST/source guard 锁定 `EvidenceVersionRepository`、approval/replay canonical owner、exact `tenant_policy` scope 及只读 legacy adapter。
- **证据**：`tests/integration/test_phase64_2_integrity_matrix.py`、`tests/architecture/test_evidence_memory_integrity_boundaries.py`；实现 owner 包括 `src/knowledge/evidence_identity.py`、`src/repositories/evidence_version_repo.py`、`src/approvals/service.py`、`src/replay/service.py`。
- **验证**：Plan 09 最终 13-file focused aggregate 为 `204 passed, 15 warnings`，全仓 `uv run ruff check src tests` 为 `All checks passed!`；lastfailed 清空后 `uv run pytest --lf -q --tb=short` 自动回退执行完整 suite，结果为 `4455 passed, 4 skipped, 152 warnings in 1993.29s`。
- **剩余风险**：legacy risk 是已持久化的歧义 legacy JSON 只能保持 unresolved，不能补造权威内容；target/defer 为 post-Phase 17 Policy Scope 的 named/versioned 非 tenant scope，以及 Phase 65 的 trace labeling，均不得被误报为当前已实现。

---

# 4. 记忆（Memory）

**范围**：短期/会话记忆、thread summary、ContextAssembler、记忆边界与 fail-closed。
**已 ship**：v1.1 Memory Foundation V2、v1.7 短期记忆统一。
**在册探索**：Phase 999.1「评估 mem0 作为 MemoryContextService 背后可选 backend」。

## 2026-07-09 — Redis 运行时依赖从当前实现降级为瓶颈后可选方案 ✅已修复验证

- **问题现象/根因**：当前源码没有 Redis client 使用路径，session memory、checkpoint、RAG、trace/replay、approval/action draft 均以 PostgreSQL 为权威源；但 `docker-compose.yml`、`.env.example`、`src/config.py`、`pyproject.toml` 和 README 仍把 Redis 表现为当前运行依赖。这会造成启动链路多一个无功能服务，也会误导后续实现者把 Redis 视为 memory/checkpoint authority。
- **影响**：本地启动需要等待 Redis healthy，即使产品功能不使用它；作品集/README 技术栈也会夸大当前实现。更重要的是，若保留“已配置即已使用”的信号，后续 memory/cache 改动可能绕过 PostgreSQL CAS / replay / approval authority 边界。
- **处理状态**：✅ 已修复验证。移除 Compose Redis service、API `depends_on.redis` 和 `REDIS_URL` 注入；移除 `.env.example` 的 `REDIS_URL`、`src.config.Settings.redis_url` 和 `pyproject.toml` 的 `redis` 依赖；同步 README、`docs/current-implementation-map.md`、`docs/architecture-overview.md`、`docs/contract-spec.md` 与 `docs/evaluation.md`。Redis 现在仅作为“量化瓶颈出现后”的 future option：非权威 TTL hot cache、rate limit、short lock、SSE buffer 或 worker hint，且必须 PostgreSQL fallback。
- **证据**：本条提交文件 `docker-compose.yml`、`.env.example`、`src/config.py`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/current-implementation-map.md`、`docs/architecture-overview.md`、`docs/contract-spec.md`、`docs/evaluation.md`。
- **剩余风险**：🟡 历史 planning / milestone artifact 中仍有 Redis 作为早期架构候选或未来选项的记录，未批量重写；当前事实文档已改为无 Redis runtime dependency。若未来重新引入 Redis，必须先给出量化瓶颈证据，并补 cache miss / Redis unavailable / stale cache / TTL / tenant-scope 回归。

## Phase 59 Plan 01 — approval-resume terminal finalizer 共享基础已落地 ✅

- **问题现象/根因**：milestone audit 发现 approval resume completed path 没有复用普通 `agent-runs` terminal memory finalizer；同时普通 finalizer 的 trace append helper 位于 `agent_runs.py` 私有函数且不幂等，retry 可能重复追加 `agent_run_memory_finalize` 行。另一个细节是 approval-resume final state 往往带 `approval_result` / `approval_required` / `risk_assessment.approval_required=True`，若直接进入 `memory_write(...)` 会被普通 pending/interrupted approval skip predicate 当作 `not_completed_path` 跳过。
- **影响**：approval-resume run 可以显示 completed，但 assistant message / thread summary / session memory / Case Working Context finalization surface 与普通 run 生命周期不一致；retry 还可能造成 finalizer trace 行重复，影响 replay/trace 可解释性。
- **处理状态**：✅ Phase 59-01 已修复验证。新增 `build_agent_run_finalizer_input_state(...)` 从 persisted `AgentRun` 与原 requester `User` 构造 finalizer input identity；新增 `_terminal_memory_write_state(...)` 只在 completed terminal finalizer 调用 `memory_write(...)` 前移除审批 gating marker，不修改 `src/agent/nodes/memory_write.py` 的全局 pending/interrupted skip 行为，CWC 仍收到原始 `final_state`。新增 `persist_agent_run_memory_finalize_trace_steps(...)` 作为 shared helper，先查 `AgentStep.run_id + FINALIZER_NODE`，已存在则返回；普通 `agent_runs` 两个 completion call site 已迁移到 shared helper。
- **证据**：Phase 59 Plan 59-01；commits `98a2482`（RED terminal finalizer memory-state tests）、`d2edef0`（terminal input-state/sanitizer）、`4e034ba`（RED idempotent trace tests）、`b22dd5e`（shared trace helper + router migration）；文件 `src/api/services/agent_run_memory.py`、`src/api/routers/agent_runs.py`、`tests/test_agent_runs_api.py`、`tests/agent/test_memory_write_node.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/agent/test_memory_write_node.py::test_memory_write_node_skips_when_final_response_missing -q` → `3 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context -q` → `3 passed, 1 warning`；focused new tests → `8 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py` → pass。
- **剩余风险**：⚠️ 59-01 只建立 shared finalizer seam 与普通 run helper migration；approval resume route 尚未在 completed branch 调用 finalizer，需由 Phase 59-02 接线，并由 Phase 59-03 做 approval-resume completed / interrupted-again / retry-dedupe regression 和 broader canonical graph verification。

## Phase 59 Plan 02 — approval-resume completed path terminal finalizer 接线 ✅已修复验证

- **问题现象/根因**：59-01 建好了 shared finalizer seam，但 `src/api/routers/approvals.py` 的审批恢复完成路径仍只更新 `AgentRun` 与 post-approval trace，未在 durable status/trace 之后调用 terminal finalizer；若 finalizer 已提交 assistant/summary/memory/CWC surface、但最终 `approval_resumed/completed` event 失败，历史 retry 还会面临「run 已 completed 但 latest resume event 仍 attempted/failed」的 reconciliation 窗口。
- **影响**：completed approval resume 可能继续跳过普通 run completion 的 assistant message、thread summary、session memory 和 CWC terminal writeback；或者 retry 时为了补 event 而重新执行 graph resume / action_draft side effects，造成 side-effect 重放风险。
- **处理状态**：✅ Phase 59-02 已修复验证。`_resume_graph_after_decision(...)` 在 `_reconcile_approved_action_draft(...)`、`update_agent_run_status(...)` 和 post-approval `append_agent_steps(...)` 之后，仅当 `final_status == "completed"` 且有 final response 时，按 persisted `run.user_id` 取 requester，调用 `build_agent_run_finalizer_input_state(...)`、`finalize_completed_agent_run_memory(...)` 和 `persist_agent_run_memory_finalize_trace_steps(...)`；trusted graph resume 仍使用 reviewer/admin `actor_user`。`_recoverable_resume_retry_result(...)` 仅允许 latest same resume key 为 attempted/failed 且 run 已 completed+有 final_response 的 retry 进入 reconciliation；`_run_resume_lifecycle(...)` 先查 `AgentStep.node_name == "agent_run_memory_finalize"` 且 `metrics_json.memory_write_status == "completed"`，证据存在时只补 `approval_resumed/completed` event，不再调用 graph/action draft；证据缺失时抛 `approval resume completed run missing terminal finalizer evidence`。
- **证据**：Phase 59 Plan 59-02；commits `1959a12`（RED approval resume finalizer tests）、`288d2a5`（completed resume finalizer wiring + retry reconciliation）、`c54db83`（interrupted/error skip boundary regression）；文件 `src/api/routers/approvals.py`、`tests/test_approval_api.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_agent_run_status_updates_to_completed_after_service_resume tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_approval_resume_reconciliation_accepts_not_executed_demo_draft_outcome -q` → `3 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_approval_resume_error_skips_terminal_finalizer_surfaces tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `34 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` → `35 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `31 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py` → pass。
- **剩余风险**：⚠️ 59-02 完成 approval route 接线与核心 retry reconciliation；Phase 59-03 仍需做最终 broader regression/validation sign-off、更新 Phase 59 validation artifact，并确认 milestone archive evidence closure 前无遗漏。

## Phase 59 Plan 03 — approval-resume terminal memory lifecycle 最终回归与验证收口 ✅已修复验证

- **问题现象/根因**：59-01/59-02 已完成 shared finalizer 与 approval-resume completed path 接线，但 milestone archive 前仍需要把真实 DB surface 锁成回归证据：completed approval resume 必须持久化 assistant message、thread summary、session-memory `MemoryWriteEvent`、`agent_run_memory_finalize` trace step 与 CWC metrics；interrupted-again path 必须不产生 terminal memory/finalizer surface；post-finalizer failure retry 必须只补 completed resume event，不重跑 graph/action/finalizer。
- **影响**：如果缺少这些回归，后续修改 `src/api/services/agent_run_memory.py`、`src/api/routers/approvals.py` 或 approval/action retry 逻辑时，可能重新引入「run completed 但 memory surface 缺失」、approval marker 导致 terminal memory 写入被误跳过、或 retry 重复 graph/action side effect 的架构债。
- **处理状态**：✅ Phase 59-03 已修复验证。`tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer` 现在断言 completed approval resume 产生一个 assistant `ConversationMessage`（metadata source 为 `agent_runs.finalizer`）、一个 thread `ConversationSummary`、一个 `MemoryWriteEvent(memory_type="session_slot", decision="write")`、一个 `AgentStep(node_name="agent_run_memory_finalize")`，并验证 `memory_write_status == "completed"`、`memory_write_reason_code != "not_completed_path"`、存在 `case_working_context_status`。`test_decide_edit_rebinds_replacement_approval_from_resume_interrupt` 断言 interrupted-again path 不产生 assistant message、summary、session-memory event 或 finalizer step。`test_decide_records_recoverable_resume_failure_and_retries_terminal_approval` 在 `_record_resume_event(resume_status="completed")` 后置失败注入后，断言 retry 不重复 graph call、action draft、assistant message、summary、session-memory event 或 finalizer step。`tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states` 明确锁住直接 `memory_write(...)` 遇到 `approval_result` / `approval_required` / `risk_assessment.approval_required` 时仍按 `not_completed_path` 跳过，未在 `src/agent/nodes/memory_write.py` 增加 terminal bypass flag。
- **证据**：Phase 59 Plan 59-03；commits `748c040`（approval resume terminal finalizer regressions）、`ba484cd`（direct approval memory-write skip regression）；文件 `tests/test_approval_api.py`、`tests/agent/test_memory_write_node.py`、`src/api/services/agent_run_memory.py`、`src/api/routers/approvals.py`；验证签收见 `.planning/phases/59-approval-resume-terminal-memory-finalization/59-VALIDATION.md`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` → `35 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` → `4 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py -q` → `57 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `31 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `193 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` → pass。
- **剩余风险**：🟡 Phase 59 已关闭 approval-resume terminal memory finalization gap；milestone archive evidence refresh 仍属于 Phase 60，不在本条实现。当前 remaining risk 是未来改动需继续保留这些回归命令在 archive / release gate 中运行。

## Phase 59 Code Review Fix — approval-resume finalizer evidence fail-closed 与 completed event 加锁 ✅已修复验证

- **问题现象/根因**：Phase 59 代码审查发现两个收尾风险。第一，approval resume completed path 调用 `persist_agent_run_memory_finalize_trace_steps(...)` 时沿用普通 `agent-runs` 的 suppress-and-rollback 语义；如果 finalizer trace append 失败，仍可能继续记录 `approval_resumed/completed`，留下 completed run 但缺 `agent_run_memory_finalize` evidence，且 rollback 会撤销尚未提交的 CWC write。第二，completed-run retry reconciliation 在读取 latest resume status 与写 completed event 之间没有锁；并发 retry 可能都看到 attempted/failed 并重复写 completed event。
- **影响**：会削弱 Phase 59 的核心保证：retry fail-closed 依赖 finalizer evidence，但 completed event 一旦误写，后续 retry 不再进入修复分支；并发 completed event 也会污染 approval replay/audit event stream。
- **处理状态**：✅ 已修复验证。`persist_agent_run_memory_finalize_trace_steps(...)` 新增 `suppress_errors`，普通 run 默认保持兼容，approval resume 调用传 `suppress_errors=False`；approval resume 在 finalizer result 返回后先 `commit()` terminal surfaces，再要求 finalizer trace persistence 成功。新增 `_lock_approval_request_for_resume(...)` 与 `_record_resume_completed_event_once(...)`，用 `SELECT ... FOR UPDATE` 锁住 approval row，锁内重查 latest same-key resume status，已 completed 时不再追加 event；只有 run 已 completed 时才强制 finalizer evidence，interrupted/error resume 仍保留流程 completed event 语义且不跑 terminal finalizer。
- **证据**：Phase 59 code review fix；文件 `src/api/services/agent_run_memory.py`、`src/api/routers/approvals.py`、`tests/test_agent_runs_api.py`、`tests/test_approval_api.py`、`.planning/phases/59-approval-resume-terminal-memory-finalization/59-REVIEW.md`、`.planning/phases/59-approval-resume-terminal-memory-finalization/59-REVIEW-FIX.md`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q` → `37 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_is_idempotent tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_rolls_back_and_suppresses_append_failure tests/test_agent_runs_api.py::test_persist_agent_run_memory_finalize_trace_steps_can_fail_closed tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` → `5 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `88 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py -q` → `196 passed, 1 warning`；focused Ruff → pass。
- **剩余风险**：🟡 现有加锁依赖数据库 row lock；测试覆盖了锁后重查和串行幂等语义，没有做真实双连接并发压力测试。若未来 approval event stream 增加 uniqueness/index 约束，可进一步把此保证下沉到数据库唯一性。

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

## Phase 57 Plan 03 — persisted legacy approval edit retry 规范化到 `risk_gate` ✅已修复验证

**问题 / 根因**
- Phase 57-02 已把 current approval edit `resume_route` 切到 `risk_gate`，但 API retry reconstruction 仍缺少对历史持久化 `resume_route="assess_risk_and_approval"` 的只读兼容规范化。
- 如果直接接受 legacy route 作为 graph resume payload，会让旧 route 重新变成 current authority；如果完全拒绝，又会破坏已经持久化的 pre-cutover edit retry。

**影响**
- 历史 edit approval 在 graph resume 失败后可能无法重试，或在错误实现中把 legacy route 重新注入 current graph resume。

**修复**
- 在 `src/api/routers/approvals.py` 新增 `CANONICAL_RISK_ROUTE = "risk_gate"` 与 `LEGACY_RISK_ROUTE = "assess_risk_and_approval"`，legacy 常量和兼容分支均标记 `DELETE_BY_PHASE_58`。
- `_terminal_decision_result_for_retry(...)` 只在读取 persisted approval event metadata 时接受 legacy route，并在构造 `TrustedApprovalResultV1` 前规范化为 canonical `risk_gate`。
- `_should_resume_graph(...)` 与 `route_after_approval(...)` 仍只接受 current canonical `risk_gate`，fresh/current legacy edit payload fail closed。

**证据 / 验证**
- 文件：`src/api/routers/approvals.py`、`src/approvals/service.py`、`src/agent/graph.py`、`tests/test_approval_api.py`、`tests/test_graph_routing.py`
- Phase / commit：57-03 Task 1 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_graph_routing.py -q --tb=short` → `111 passed, 1 warning`

**剩余风险**
- 🟡 Phase 58 仍需删除 `assess_risk_and_approval` legacy route compatibility branch and related retained compatibility aliases after no-debt cleanup。

## Phase 58 Plan 09 — approval retry / graph resume route authority 收敛为 canonical-only ✅已修复验证

**问题 / 根因**
- Phase 57 为支持历史 persisted edit retry，临时保留 `LEGACY_RISK_ROUTE = "assess_risk_and_approval"` 与 `_canonical_retry_resume_route(...)`。虽然实际 graph resume 已规范化到 `risk_gate`，但命名仍像 active graph route vocabulary，Phase 58 no-debt gate 下容易被误解为 current route authority。

**影响**
- 历史数据读取兼容和 current graph route authority 的边界不够清晰；后续维护者可能把 legacy route 当作新请求 / service payload 可用值，削弱 canonical-only `risk_gate` 约束。

**处理状态**
- ✅ 已修复验证。`src/api/routers/approvals.py` 删除 `LEGACY_RISK_ROUTE` 常量，改为 `HISTORICAL_RETRY_ROUTE_TO_CANONICAL = {"assess_risk_and_approval": CANONICAL_RISK_ROUTE}`。
- ✅ 映射只在 `_terminal_decision_result_for_retry(...)` 读取 persisted `approval_decided` event metadata 后使用，且保留 approval/run/hash/snapshot/request/level/assignment version 校验在 resume payload 构造前执行。
- ✅ `_should_resume_graph(...)` 和 API response payload 继续只放行 / 输出 canonical `risk_gate`；fresh/current legacy `resume_route` fail closed。
- ✅ `route_after_approval(...)` 对 legacy `resume_route` 明确 fail closed，approval gate / approval API fake trace fixture 改用 canonical `risk_gate`，不再把 deleted risk node name 当作 current fixture。

**证据 / 验证**
- 文件：`src/api/routers/approvals.py`、`src/agent/graph.py`、`tests/test_approval_api.py`、`tests/test_approval_gate.py`、`tests/test_graph_routing.py`
- Phase / commit：58-09 Task 1/2 GREEN（本条所在提交）
- RED evidence：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only -q --tb=short` → `1 failed, 1 warning`
- GREEN evidence：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` → `66 passed, 1 warning`
- Task 2 RED evidence：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py::test_approval_gate_tests_do_not_reference_legacy_risk_node_name tests/test_graph_routing.py::test_route_after_approval_rejects_legacy_risk_resume_route_authority -q --tb=short` → `1 failed, 1 passed, 1 warning`
- Task 2 GREEN evidence：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` → `160 passed, 1 warning`
- Ruff：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/approvals.py src/agent/graph.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py` → pass

**剩余风险**
- ✅ 本计划范围内无剩余 route-authority 风险。历史 persisted row mapping 仍保留为只读数据兼容，不是 current graph route vocabulary。

## 2026-07-08 — Phase 58 / CAGM-09 Agent Graph migration no-debt closeout ✅已修复验证

**子系统**
- Agent Graph / 意图识别 / RAG recommendation / 记忆上下文 / 风险审批主链

**问题 / 根因**
- Phase 50-57 逐步把 active graph 切到 canonical nodes，但历史 wrapper、route delegate、trace/API/frontend/eval fallback、approval retry metadata、current-source docs 和 planning ledger 中仍保留迁移期旧名。若不统一收口，后续维护者可能把历史兼容读法误当成 current runtime authority。

**影响**
- CAGM-09 不能只看 `src/agent/graph.py` 的 15-node 注册结果；还必须证明 active route values、current resume route、current eval node、docs authority 和 package metadata 都不再依赖 legacy graph names，否则 replay/eval/API 文档可能继续传播双轨语义。

**处理状态**
- ✅ 已修复验证。Phase 58 Plan 01-09 已删除或内化 public legacy route delegates、active graph vocabulary compatibility aliases、recommendation/risk/intent/session/slot/memory legacy wrapper 文件与 direct legacy tests，并把 trace/API/SSE/frontend/eval/approval retry route authority 收敛为 canonical-only current surface。
- ✅ 本次 Plan 10 已同步 current-source docs 和 README：当前 active main graph 明确为 final 15 canonical registered nodes；旧 graph/node/router 名称只可作为历史 trace/read 投影、旧 planning 文档、测试防回归或 classifier artifact，不再作为 active graph registration、current route value、current resume route、current eval node 或 current docs authority。
- ✅ `docs/contract-spec.md` §9 已核对：canonical node list、router contract、deterministic gate 和 risk/approval/action 边界与当前 final 15-node 实现一致；其中 legacy alias 段落是 migration policy / historical compatibility 说明，不要求修改为实现事实，因此本次未编辑 spec。

**证据 / 验证**
- Phase / requirement：Phase 58 Plan 10 / CAGM-09。
- Docs evidence：`docs/current-langgraph-architecture.md`、`docs/architecture-overview.md`、`docs/target-agent-platform-architecture-plan.md`、`README.md`。
- Strict classifier：`UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` → pass；`total_hits=824`、`files=76`、`active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`；category counts：`classifier_implementation=8`、`historical_data_read_projection=20`、`legacy_wrapper_or_import_test=213`、`phase58_cleanup_artifact=316`、`previous_state_documentation=267`。
- Current-doc canonical concept assertion：`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "...required final graph concepts..."` → `phase58-current-doc-canonical-concepts: pass`。

**Residual historical-read caveats**
- 🟡 不 bulk rewrite historical DB rows。历史 trace/API/SSE/approval retry metadata 中若仍有旧名，只允许在 bounded historical read/projection path 中映射到 canonical owner；fresh/current graph route、resume route、eval node 和 docs authority 不接受旧名。
- 🟡 旧 planning 文档、历史架构草稿和测试防回归文本仍会被 strict classifier 统计为 classified historical/reference rows；这不是 runtime debt，后续只需维持 `active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`。

**剩余风险**
- ✅ 当前 CAGM-09 no-debt scope 无剩余 active-runtime 风险。剩余风险仅是未来改动重新引入旧名 current authority；由 strict classifier、graph baseline tests、approval route tests 和 docs review 继续防回归。

## Phase 57 Plan 03 — approval_gate trusted result validation 与新回合 approval authority 清空 ✅已修复验证

**问题 / 根因**
- `src/agent/nodes/approval_gate.py` 原先只检查 interrupt resume payload 是 dict 且 `schema_version == "approval_result.v1"`，未在写入 `approval_result` 前执行完整 `TrustedApprovalResultV1` schema 校验与 tenant/run/hash 绑定校验。
- `src/agent/nodes/receive_request.py` 已清空 `approval_result`、`proposed_action`、snapshot hash 等字段，但漏掉 `approval_plan`、`risk_decision`、target merchant refs、business/verified refs、`approval_idempotency_key`、`auto_allowed_binding` 等 approval/risk authority 字段。

**影响**
- schema-only 或带 `raw_text` 的非可信 resume payload 可能短暂进入 `approval_result` state，虽然后续 `route_after_approval` 仍会 fail closed，但 approval boundary 的 defense-in-depth 不完整。
- 普通 approval-like chat 新回合不会进入 `approval_gate` / `action_draft`，但旧 approval authority 字段可能从 checkpoint state 残留，增加后续节点误用风险。

**修复**
- 在 `approval_gate` 中新增 `_is_trusted_decision_for_state(...)`，用 `TrustedApprovalResultV1.model_validate(...)` 校验完整 trusted resume schema，并校验 tenant、run、`action_payload_hash`、`safety_snapshot_ref`、`safety_snapshot_hash` 与当前 state 绑定一致。
- 在 `receive_request` 新回合 reset 中补齐 approval/risk/action authority 字段：`approval_plan`、`risk_decision`、target merchant refs、business/verified refs、claim verification refs、`approval_idempotency_key`、`auto_allowed_binding` 等。
- 新增 AST static test，防止 `approval_gate` 引入 risk/action/snapshot runtime coupling，同时避免 comments/docs/type-only false positives。

**证据 / 验证**
- 文件：`src/agent/nodes/approval_gate.py`、`src/agent/nodes/receive_request.py`、`tests/test_approval_gate.py`、`tests/agent/test_graph.py`
- Phase / commit：57-03 Task 2 GREEN（本条所在提交）
- RED evidence：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py tests/agent/test_graph.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_intent_routing.py tests/agent/test_clarification_gate.py -q --tb=short` → `3 failed, 1169 passed, 29 warnings`
- GREEN evidence：同一 focused command → `1172 passed, 29 warnings`

**剩余风险**
- 🟡 Phase 58 仍需删除 `assess_risk_and_approval` retained compatibility surfaces；本条只关闭 approval_gate / receive_request 的 current trust-boundary 缺口。

## Phase 57 Plan 04 — `risk_gate` runtime 投影 / eval / diagnostic / frontend 收口 ✅已修复验证

**问题 / 根因**
- 57-01 至 57-03 已完成 active graph、approval edit resume 和 persisted retry compatibility 的 `risk_gate` 切换，但 trace/API/frontend/eval/diagnostic 收尾面仍可能把 `assess_risk_and_approval` 误读成 current runtime surface。
- eval graph contract harness 仍 patch 旧 `assess_risk_and_approval` module；若后续只改 graph 注册名，CI fake LLM 和 snapshot seam 可能绕过 canonical `risk_gate` wrapper，形成 active-node 名称与测试 patch target 漂移。
- architecture route-value parser 不支持 `return CANONICAL_RISK_ROUTE` 这种 canonical route constant，导致当前 route authority 的静态验证出现 parser false negative。

**影响**
- 历史 trace payload 需要继续可读，但 current-run projection、SSE target、frontend label、eval current node list、diagnostic mock report 都必须使用 `risk_gate`；否则 Phase 58 no-debt cleanup 前会混淆“历史兼容投影”和“当前运行权威”。
- eval harness patch 旧 module 会让 `risk_gate` wrapper 的可 patch 性缺口长期隐藏，后续风险/审批 graph contract 可能无法证明 current canonical node 的真实行为。

**修复**
- `src/agent/graph_vocabulary.py` 新增 `risk_gate` runtime identity entry，并把 `assess_risk_and_approval -> risk_gate` 标为 non-runnable Phase 57 compatibility alias，reason codes 含 `HISTORICAL_TRACE_PROJECTION`、`IMPORT_TEST_COMPATIBILITY`、`DELETE_BY_PHASE_58`。
- `src/api/routers/agent_runs.py` 补齐 `risk_gate` SSE label 和 current/historical 风险 payload projection，保留历史 `assess_risk_and_approval` trace readability。
- `frontend/src/components/timeline/TimelineStep.tsx`、`scripts/eval_agent.py`、`scripts/diagnose_latency.py` current-run surface 改用 `risk_gate`；frontend 旧 label 只作为 historical display fallback 并标记 Phase 58 删除。
- `src/agent/nodes/risk_gate.py` 暴露 `_get_llm` 与 `persist_action_safety_snapshot` patch seam，并通过 lazy dependency injection 调用 shared risk implementation，兼容旧 import tests 和新 eval harness patch target。
- `tests/architecture/graph_baseline.py` 支持 module-level string constant route returns，避免 canonical route constants 被静态验证误判。

**证据 / 验证**
- 文件：`src/agent/graph_vocabulary.py`、`src/api/routers/agent_runs.py`、`src/agent/nodes/risk_gate.py`、`src/agent/nodes/assess_risk_and_approval.py`、`frontend/src/components/timeline/TimelineStep.tsx`、`scripts/eval_agent.py`、`scripts/diagnose_latency.py`、`tests/architecture/graph_baseline.py`、`tests/architecture/test_canonical_graph_baseline.py`、`tests/agent/test_graph_vocabulary.py`、`tests/agent/test_trace.py`、`tests/test_trace_api.py`、`tests/test_agent_runs_api.py`
- Phase / commit：57-04 Task 1 GREEN `b93ff43`；57-04 Task 2 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` → `175 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py -q --tb=short` → `134 passed, 1 skipped, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` → `20 passed, 1 warning`
- `npm --prefix frontend run build` → pass

**剩余风险**
- 🟡 Phase 58 仍需删除 `assess_risk_and_approval` wrapper/import/test/historical display fallback 和 retained compatibility alias；57-04 只保留只读历史投影可读性，不再允许它作为 current runtime authority。

## Phase 57 Plan 05 — `risk_gate` current-source 文档与静态 legacy hit 分类收口 ✅已修复验证

**问题 / 根因**
- 57-01 至 57-04 已把 active graph、route maps、approval edit resume、runtime/API/frontend/eval/diagnostic projection 收敛到 `risk_gate`，但 current-source docs 和 README 仍有多处把 `assess_risk_and_approval` 写成当前 active node / current route / current resume route。
- `57-VALIDATION.md` 仍只要求未来扫描，没有落入实际 scan command、总命中数、分类结果和 Phase 58 删除候选清单。

**影响**
- 后续 Phase 58 planning 可能把历史兼容 alias 误读成 current authority，或反过来把仍需保留到 Phase 58 的 wrapper/import/test/historical projection 当作 Phase 57 遗漏。
- CAGM-08 若在没有静态分类证据的情况下标记完成，会缺少“当前 `risk_gate` / 历史 compatibility / Phase 58 deletion candidate”的可审计交接。

**处理状态**
- ✅ 已更新 `docs/current-langgraph-architecture.md`、`docs/architecture-overview.md`、`docs/target-agent-platform-architecture-plan.md` 和 `README.md`：current runtime graph 使用 `risk_gate`；`approval_gate` 仅作为 request/resume state machine，edit rerisk 走 canonical `risk_gate`；旧 `assess_risk_and_approval` 只保留为历史 trace/import/test/persisted retry metadata compatibility 或 Phase 58 删除上下文。
- ✅ `57-VALIDATION.md` 由 57-05 记录五个 plan wave、approved-entrypoint verification commands、静态 `assess_risk_and_approval` scan command、总命中数、分类计数和零 `UNCLASSIFIED` 结论。
- ✅ 目标契约事实与实现事实分开：`docs/contract-spec.md` / target plan 已将 `risk_gate` 作为 canonical target；已实现事实来自 Phase 57 commits、source docs 和 tests；Phase 58 仍负责最终删除 retained compatibility surfaces。

**证据 / 验证**
- 文件：`docs/current-langgraph-architecture.md`、`docs/architecture-overview.md`、`docs/target-agent-platform-architecture-plan.md`、`README.md`、`.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md`
- Phase：57-05 Task 1/2
- Task 1 文档 guard：已用 57-05 计划指定的 approved `uv run python -c ...` 检查 current-source docs / README / 本台账均包含 `risk_gate` 且不含 active legacy diagram、current route 或 current resume-route marker；完整命令与输出记录在 `57-VALIDATION.md` / `57-05-SUMMARY.md`。
- Phase closeout suites and static hit classification evidence are recorded in `57-VALIDATION.md` and `57-05-SUMMARY.md`.

**剩余风险**
- 🟡 Phase 58 仍需删除或重新分类 `src/agent/nodes/assess_risk_and_approval.py` wrapper、direct legacy tests、historical frontend/API fallback labels、persisted retry compatibility constants、old dev-contract manifest rows and historical docs. 57-05 不 bulk rewrite historical DB rows，不删除 compatibility aliases。

## 2026-07-08 — Phase 58 code review WR-01 strict legacy classifier hardening ✅已修复验证

**子系统**
- Agent Graph / 意图识别 / 记忆上下文

**问题 / 根因**
- `scripts/classify_phase58_legacy_hits.py` 原先在 active runtime 判断之后，用 broad `src/agent/nodes/` bucket 把所有 node implementation 文件命中归为 `legacy_wrapper_or_import_test`。这会让 canonical active node file 中重新出现的 legacy graph/output name 不触发 `--strict`。
- `src/agent/nodes/final_response.py` 仍从 `llm_outputs["intent_classification"]` 读取历史 intent classification trace mirror，和 Phase 58 final no-debt gate 的 canonical `classification_trace` state field 收敛目标不一致。

**影响**
- Phase 58 strict classifier 可能报告 `active_runtime_legacy=0`，但 active canonical node implementation 中已经重新出现 legacy graph/output name。
- 后续维护者可能把历史 intent output mirror 当成 current runtime 可读来源，削弱 `contextual_intent_resolve` 的 canonical output owner 边界。

**修复**
- 新增 `ACTIVE_NODE_PATHS`，把 final 15 canonical node implementation files 中的 quoted legacy graph/output term 判为 `active_runtime_legacy`。
- 删除 `final_response.py` 对 `llm_outputs["intent_classification"]` 的 fallback，只读取 canonical `classification_trace`。
- 对 `memory_context_load.py` 中删除旧 `llm_outputs` metrics key 的单行兼容清理增加显式 row-level allowlist，避免把清理历史 key 的代码误判为 current authority。
- 新增 regression test，证明临时 active node file 中的 `intent_classification` 会让 `--strict` 失败且计入 `active_runtime_legacy`。

**证据 / 验证**
- 文件：`scripts/classify_phase58_legacy_hits.py`、`src/agent/nodes/final_response.py`、`tests/architecture/test_canonical_graph_baseline.py`、`tests/agent/test_nodes/test_final_response.py`
- Phase / commit：Phase 58 code review WR-01（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` → `active_runtime_legacy=0`、`current_docs_legacy_authority=0`、`unclassified_rows=0`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_phase58_legacy_hit_classifier_exposes_main_and_strict_report_fields tests/architecture/test_canonical_graph_baseline.py::test_phase58_legacy_hit_classifier_strict_fails_active_node_runtime_alias tests/agent/test_nodes/test_final_response.py::test_final_response_complaint_folded_note_visible_without_deferred_steps -q --tb=short` → `3 passed, 1 warning`

**剩余风险**
- ✅ 本条已关闭 active canonical node file broadly masked by classifier 的回归风险。未来如果 active node file 需要保留历史兼容读取，必须在 classifier 中增加显式、逐行、可审计的 allowlist，而不是依赖 broad node-file bucket。

## 2026-07-09 — Phase 61 Plan 02 — `business_metric_query` 操作标签 MVP 妥协 🟡有意妥协

**子系统**
- 意图识别 / slot resolution contract

**问题 / 根因**
- Phase 61 需要新增单一 generic `business_metric_query` 意图，但当前 `RequestedOperationLiteral` 只有 `read_status`、`advise`、`draft_reply`、`draft_action`、`execute_action`、`escalate`，没有 metric-specific read operation。
- 61-02 只落 metric intent / slot / clarification contract，不落 SQL-backed metric runtime；在这一层新增 `read_metric` 会扩大 operation taxonomy 和多处下游判断面。

**影响**
- metric intent 必须被测试锁定为 read-only、非 high-risk、非 direct-response、非 evidence/RAG-required，避免 `read_status` 复用被误读成订单状态查询或写操作入口。
- 后续 61-03/61-04 runtime 和 graph 集成不得因为 operation 仍叫 `read_status` 而让 metric query 走 per-resource status/id-required 逻辑。

**处理状态**
- 🟡 61-02 Task 1 将 `business_metric_query` 注册为唯一 metric intent，`initial_route="slot_resolution_gate"`、`required_slots=["metric_id"]`、`evidence_required=False`、`high_risk=False`。
- 🟡 tests 锁定 no per-metric intents、read-only risk tier、not in `DIRECT_RESPONSE_INTENTS` / `EVIDENCE_REQUIRED_INTENTS`，并用 prompt/golden manifest 覆盖订单数、退款单数、待处理工单数、补偿券记录数、商户退款率。

**证据 / 验证**
- 文件：`src/agent/schemas.py`、`src/agent/intent_policy.py`、`src/agent/prompts.py`、`tests/agent/test_intent_policy_registry.py`、`tests/agent/test_intent_manifest.py`
- Phase / commit：61-02 Task 1 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_manifest.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py -q --tb=short` → `109 passed, 1 warning`

**剩余风险**
- 🟡 若后续 metric operation taxonomy 需要在 API/SSE/trace 上与 `read_status` 明确区分，应由 post-Phase 61 contract cleanup 或单独 plan 引入 `read_metric`，并同步更新 intent/risk/task-plan/final-response 测试。

## 2026-07-09 — Phase 61 Plan 03 — ToolCatalog 与 investigate planner allowlist 漂移风险 ⚠️修复但验证有缺口

**子系统**
- 工具调用 / Agent Graph investigate planner

**问题 / 根因**
- `src/tools/catalog.py` 已是 graph-facing tool declaration 单一来源，但 `src/agent/nodes/investigate_planner.py` 仍保留独立 `INVESTIGATE_ALLOWED_TOOL_NAMES` 静态 allowlist。
- 61-03 新增 `query_business_metric` 时，如果只更新 catalog，planner 会看到/需要 metric tool contract，但结构化 planner 校验仍可能拒绝该工具，形成 catalog 与 planner 可调用工具集漂移。

**影响**
- 新增只读工具时容易出现「ToolPlatform 可见但 planner output schema 拒绝」的运行时断裂。
- 这类漂移会绕过单一 catalog contract，增加后续工具扩展的维护成本。

**处理状态**
- ⚠️ 本 plan 已把 `query_business_metric` 同步加入 `INVESTIGATE_ALLOWED_TOOL_NAMES`，并用 `tests/tools/test_tool_platform.py` 更新 metric-inclusive allowlist/dispatch regression。
- ⚠️ 仍未移除 duplicate static allowlist；更彻底的修复应由 post-Phase 61 tool contract cleanup 将 planner allowlist 从 `ToolCatalog.investigate_tool_names(...)` 派生，或增加强一致性测试覆盖 planner allowlist 与 catalog 的双向一致。

**证据 / 验证**
- 文件：`src/tools/catalog.py`、`src/agent/nodes/investigate_planner.py`、`tests/tools/test_tool_platform.py`
- Phase / commit：61-03 Task 1 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/platform/test_trusted_context_factory.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q --tb=short` → `128 passed, 1 warning`

**剩余风险**
- ⚠️ duplicate static allowlist 仍存在；post-Phase 61 cleanup 前，新增 investigate tool 必须同时更新 catalog、planner allowlist 与 tests。

## 2026-07-09 — Phase 61 `aggregate_order_query` legacy fallback 文案残留 ✅已修复验证

**子系统**
- 意图识别 / Final Response UX

**问题 / 根因**
- Phase 61 当前主路径已经把“当前/现在有多少订单”识别为 `business_metric_query`，并在缺少时间范围时进入 clarification，而不是 unsupported。
- `src/agent/nodes/final_response.py` 仍保留 legacy `routing_hints.unsupported_reason == "aggregate_order_query"` 分支，文案仍说“当前控制台还不支持统计订单总数”，与新的 metric contract 和前端 safe reason label（缺少时间范围）不一致。
- 用户本地截图主要由旧 Docker 镜像触发，但该残留 fallback 会让 legacy 状态再次产生同类误导。

**影响**
- 用户会误以为订单数统计能力整体未实现，而实际缺的是时间范围槽位。
- 前端 timeline/details 可能显示“缺少时间范围”，聊天气泡却说“不支持统计订单总数”，造成 UX 口径冲突。

**处理状态**
- ✅ 已将 legacy aggregate-order fallback 改为时间范围澄清：“要统计订单数，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。”
- ✅ 已更新 final response 单测，锁定不再出现“不支持统计订单总数”和“具体订单号”提示。
- ✅ 已重建 Docker API 镜像，并用真实 `/api/v1/agent-runs` smoke 验证“现在有多少订单”返回时间范围澄清。

**证据 / 验证**
- 文件：`src/agent/nodes/final_response.py`、`tests/agent/test_nodes/test_final_response.py`
- 本地问题记录：`.planning/LOCAL-VALIDATION-ISSUES.md` 2026-07-09 “Docker 旧镜像导致 Phase 61 指标查询 UI 仍显示‘不支持统计订单总数’”
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_final_response.py::test_final_response_handles_legacy_aggregate_order_query_as_time_clarification tests/agent/test_nodes/test_contextual_intent_resolve.py::test_aggregate_order_count_request_routes_to_metric_intent_without_llm -q --tb=short` → `2 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py::test_slot_resolution_gate_order_count_current_requires_time_not_order_id tests/agent/test_graph.py::test_metric_order_count_missing_time_routes_to_clarification_without_tool_call tests/agent/test_graph.py::test_aggregate_order_count_routes_to_metric_clarification_without_tool_call -q --tb=short` → `3 passed, 3 warnings`
- Docker API smoke：`final_response="要统计业务指标，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。"`

**剩余风险**
- 🟡 `aggregate_order_query` 作为 legacy safe reason / fallback key 仍存在；当前未发现主路径 setter。若后续要完全删除该 alias，需要同步清理 API safe reason allowlist、frontend reason label 和 legacy final-response test。

## 2026-07-09 — Phase 61 metric clarification follow-up 续接缺口 ✅已修复验证

**子系统**
- 意图识别 / slot resolution / 工具调用

**问题 / 根因**
- Phase 61 支持 `business_metric_query` 后，“当前/现在有多少订单”会正确澄清时间范围，但同一 thread 下一轮只回答“本周”时没有被识别为 `metric_time_range` answer。
- 根因是 pending flow 续接只识别 identifier-like answer（订单号/退款单号/工单号），没有 metric time answer 分支；并且 pending flow 只传候选槽位，没有显式携带上一轮已解析的 metric active slots。
- metric 槽齐后 `investigate` 仍可能进入 LLM planner；如果 planner 选择 `search_policy`，metric answer 会走偏到 policy/RAG/recommendation 状态。
- metric tool result 还会继承 policy insufficient-evidence draft，导致 API run `final_status` 与 metric answer 不一致。

**影响**
- 用户在同一个对话中按系统要求回答“本周/本月/今年”仍被要求补业务背景，破坏 clarification UX。
- 指标查询可能不稳定地依赖 planner，而不是确定性只读 metric tool。
- API Run Info 可能显示 `insufficient_evidence`，但聊天气泡实际已经给出 metric answer。

**处理状态**
- ✅ `receive_request` 的 active flow projection 增加上一轮已解析 `resolved_slots`。
- ✅ `contextual_intent_resolve` 新增 pending metric time answer 续接，确定性识别“今天/本周/本月/本季度/今年”。
- ✅ `slot_resolution_gate` 对 `answered_pending_metric_time_range` 合并 active flow metric slots 与当前时间范围。
- ✅ `investigate` 对 `business_metric_query` 优先使用 deterministic `query_business_metric` planner，避免 LLM planner 误选 `search_policy`。
- ✅ metric intent 不再生成 policy insufficient-evidence recommendation draft，真实 API status 与 metric answer 一致为 `completed`。

**证据 / 验证**
- 文件：`src/agent/nodes/receive_request.py`、`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/slot_resolution_gate.py`、`src/agent/nodes/investigate.py`
- 测试：`tests/agent/test_nodes/test_contextual_intent_resolve.py`、`tests/agent/test_nodes/test_slot_resolution_gate.py`、`tests/agent/test_nodes/test_investigate.py`、`tests/agent/test_graph.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py::test_contextual_intent_resolve_pending_metric_time_answer_uses_same_thread_flow tests/agent/test_nodes/test_slot_resolution_gate.py::test_slot_resolution_gate_merges_pending_metric_time_answer_with_active_flow tests/agent/test_graph.py::test_metric_time_followup_reuses_pending_order_count_flow tests/agent/test_graph.py::test_complete_metric_query_routes_through_slot_gate_investigate_and_final_response tests/agent/test_nodes/test_final_response.py::test_metric_count_response_is_number_first_with_scope_time_filter_freshness -q --tb=short` → 通过
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_contextual_intent_resolve.py::test_contextual_intent_resolve_pending_slot_identifier_uses_same_thread_state_only tests/agent/test_nodes/test_contextual_intent_resolve.py::test_pending_required_slot_ambiguous_reply_reasks_for_slot tests/agent/test_required_slots.py::test_metric_slot_policy_locks_metric_ids_and_candidate_hints_do_not_satisfy tests/agent/test_nodes/test_investigate.py::test_deterministic_fallback_calls_metric_tool_from_complete_active_slots tests/agent/test_nodes/test_investigate.py::test_deterministic_fallback_stops_metric_query_with_incomplete_active_slots tests/agent/test_nodes/test_investigate.py::test_metric_result_accumulates_under_business_metric_fact -q --tb=short` → `22 passed, 1 warning`
- Docker API smoke：同一 `thread_id` 先问“现在有多少订单”，再答“本周”，第二轮返回 `3（订单数）... this_week ...` 且 `status=completed`。

**剩余风险**
- 🟡 当前 follow-up 只覆盖预设时间范围；自定义自然语言时间区间仍需单独 parser / test。
- 🟡 这次修复保留 `business_metric_query` 使用 `read_status` operation 的 Phase 61 MVP 妥协；未来引入 `read_metric` 时需要重新检查 route/planner/status 口径。

## 2026-07-10 — Phase 63 Plan 02 — `risk_gate` risk severity/disposition 与 action proposal taxonomy 已收敛 ✅

**子系统**
- 风险审批主链 / 工具调用 / action taxonomy

**问题现象 / 根因**
- Phase 63 前，`src/agent/nodes/risk_gate.py` 本地维护 `FULL_REFUND_TERMS`、`ACTIONABLE_ACTIONS`、`_canonical_action_type(...)` 和 `_is_actionable_recommendation(...)`，与新建 safety taxonomy registry、后续 `action_draft` / `intent_policy` 迁移目标重复。
- 同一 `risk_level` 字段同时承载 severity（`low` / `medium` / `high`）和 disposition（`manual_review` / `blocked`），导致 approval/replay/audit 读取风险字段时无法稳定区分“严重度”和“处置结果”。
- `manual_review` 这类非可执行 disposition 可能在 `approval_required=True` 时继续进入 proposed action / snapshot binding 路径，削弱 action execution boundary 的可审计性。

**影响**
- 新增 action alias、risk route 或 manual review 分支时，`risk_gate` 与 taxonomy/action-draft/intent-policy 容易漏同步。
- 审批风险决策与 trace reason codes 中若继续混用 `risk_level=manual_review|blocked`，后续指标、回放和安全审计会把处置结果误读成严重度。
- 非可执行 disposition 若绑定为 proposed action，会让 approval plan / snapshot hash 看起来像存在可执行写动作。

**处理状态**
- ✅ 已修复验证。`risk_gate.py` 删除本地 action alias/actionable/canonical helper 副本，改用 `src.agent.safety.taxonomy` 的 `canonical_executable_action_type`、`is_actionable_recommendation`、`matches_full_refund_alias` 和 `risk_assessment_with_disposition`。
- ✅ 风险输出现在保持 `risk_level` 为 severity-only，同时写入 `risk_severity` 和 `risk_disposition`；manual review fail-closed 保留已有合法 severity，缺失/legacy 时由 taxonomy fallback。
- ✅ 非可执行 disposition 在 snapshot/action binding 前 fail closed，不再生成 `proposed_action.action_type=manual_review`。
- ✅ `RiskDecisionV1.reason_codes` 现在包含 `risk_severity:*` 和 `risk_disposition:*`，方便审批/audit 追踪。

**证据**
- Phase 63 Plan 02；RED commit `2240af0`；GREEN commit `c584d80`。
- 文件：`src/agent/nodes/risk_gate.py`、`tests/agent/test_nodes/test_risk_gate.py`、`tests/agent/test_phase22_action_boundary.py`、`tests/approvals/test_hash_binding.py`、`.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-02-SUMMARY.md`。

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/approvals/test_hash_binding.py -q --tb=short` → `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` → `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/risk_gate.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/approvals/test_hash_binding.py` → `All checks passed!`

**剩余风险**
- 🟡 `action_draft.py`、ToolPlatform 写工具边界、`intent_policy.py` 与 routing 的 action/risk/evidence-required taxonomy 迁移仍在 Phase 63 Plan 03/04。
- 🟡 Phase 63 Plan 05 仍需加入 drift guards / parity tests，防止后续重新引入本地 action/risk 字面量副本。

## 2026-07-10 — Phase 63 Plan 03 — `action_draft` 写工具入口已拒绝非可执行 disposition ✅

**子系统**
- 工具调用 / 风险审批主链 / action draft

**问题现象 / 根因**
- Phase 63 前，`src/agent/nodes/action_draft.py` 与 `risk_gate.py` 各自维护一份 action alias / canonical action type 逻辑。
- `manual_review` 被包含在 `ACTIONABLE_ACTIONS`，旧逻辑会把拒绝/不支持类文本 canonicalize 为 `manual_review` 并继续调用 `create_coupon_grant_draft`，导致非可执行 disposition 被包装成 action draft。
- `compensation` 被当作独立 action type 传给写工具，而不是通过统一 taxonomy 兼容为当前可执行的 `issue_coupon`。

**影响**
- 写工具入口与 risk gate 判断可能分叉，新增 action/disposition 时可能在 action_draft 漏拦。
- 审批通过后的 action draft 路径可能对 disposition-like payload 创建 demo draft，削弱“写操作必须是具体工具”的边界。
- action type 别名漂移会让 action service / ToolPlatform payload 与 taxonomy 语义不一致。

**处理状态**
- ✅ 已修复验证。`action_draft.py` 删除本地 `FULL_REFUND_TERMS`、`ACTIONABLE_ACTIONS` 和 `_canonical_action_type(...)`，改用 `src.agent.safety.taxonomy.resolve_action_text(...)`。
- ✅ 在 approval / auto-allowed binding 通过之后、`project_to_tool_context(...)` 和 ToolPlatform invoke 之前，统一校验 executable action。
- ✅ 显式 `manual_review` / `blocked` 或拒绝类文本返回 safe `action_result.status="error"`，`error_code="NON_EXECUTABLE_ACTION_DISPOSITION"`，不生成 `action_draft` / `draft_outcome`，不调用写工具。
- ✅ `compensation` 兼容别名 canonicalize 为 `issue_coupon`，没有新增 ToolCatalog 工具。
- ✅ 收窄 architecture guard 的外部执行路径检测，避免把 taxonomy alias helper 误报为 external compensation execution。

**证据**
- Phase 63 Plan 03；RED commit `8b2a04c`；GREEN commit `1842316`。
- 文件：`src/agent/nodes/action_draft.py`、`tests/test_execute_action.py`、`tests/architecture/test_action_draft_boundaries.py`、`.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-03-SUMMARY.md`。

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` → `64 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` → `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/action_draft.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py` → `All checks passed!`

**剩余风险**
- 🟡 `intent_policy.py` 与 routing 中的 action-bound / evidence-required / pre-route keyword taxonomy 仍待 Phase 63 Plan 04 迁移。
- 🟡 Phase 63 Plan 05 仍需补 drift guards，防止 `risk_gate.py` / `action_draft.py` 之外重新引入本地 action taxonomy 副本。

## 2026-07-10 — Phase 63 Plan 04 — intent/routing 安全策略已从 registry/taxonomy 派生 ✅

**子系统**
- 意图识别 / 路由规则 / 风险审批主链

**问题现象 / 根因**
- Phase 63 前，`src/agent/routing.py` 手写 `_ACTION_BOUND_INTENTS`，`_policy_evidence_required(...)` 还维护一份 evidence-required fallback intent set；这些集合与 `IntentDefinition.evidence_required` / high-risk policy 存在 drift 风险。
- `src/agent/intent_policy.py::detect_pre_route(...)` 本地维护英文/中文直接动作关键词 tuple，与 safety taxonomy 中的 pre-route alias 语义重复。
- `_has_compensation_action_cue(...)` 用本地 compensation/coupon token 判断补偿动作 cue，可能与 action taxonomy 对 `compensation -> issue_coupon` 的兼容语义分叉。

**影响**
- 新增或调整 intent/action alias 时，runtime routing 可能绕过 evidence/RAG 或误触发 action/escalation。
- 普通 chat 中的审批/动作短语若绕过 hard-negative 或本地 alias 漂移，可能被误当作可信 action/approval truth。
- policy question 中出现“发券/补偿”词时，若没有 hard-negative 先于 action alias，可能误进入 execute/draft action 路径。

**处理状态**
- ✅ 已修复验证。`IntentDefinition` 新增 `action_bound`，`IntentPolicyRegistry` 暴露 `action_bound_intents()` 与 `is_action_bound_intent(...)`。
- ✅ `action_request`、`compensation_suggestion`、`complaint_escalation` 由 registry 标记 action-bound。
- ✅ `detect_pre_route(...)` 改用 `src.agent.safety.taxonomy.detect_pre_route_action_request(...)`，保留 approval-chat / multi-target hard-negative，并新增补偿/发券 policy question hard-negative。
- ✅ `routing._policy_evidence_required(...)` 和 `_action_bound_or_high_risk(...)` 改为从 `INTENT_POLICY_REGISTRY` 派生；registry 异常时写 `safe_routing_reasons` 并 fail closed。
- ✅ `routing.py` 中的 `_ACTION_BOUND_INTENTS` 已删除。

**证据**
- Phase 63 Plan 04；RED commit `535a63d`；GREEN commit `379bcf8`。
- 文件：`src/agent/intent_policy.py`、`src/agent/routing.py`、`tests/agent/test_intent_policy_registry.py`、`tests/agent/test_intent_routing.py`、`.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-04-SUMMARY.md`。

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py -q --tb=short` → `1223 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` → `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py` → `All checks passed!`

**剩余风险**
- 🟡 Phase 63 Plan 05 仍需新增 drift guards / static parity checks，防止 `risk_gate.py`、`action_draft.py`、`intent_policy.py`、`routing.py` 重新引入本地 action/risk taxonomy 副本。
- 🟡 `_FACT_ONLY_INTENTS` 等非 action/risk taxonomy 的 routing-local集合仍不在本计划范围；若后续扩展 fact-only intent，应由对应 business-query / routing phase 处理。

## 2026-07-10 — Phase 63 closeout — safety taxonomy / risk vocabulary 硬编码债已收敛 ✅

**子系统**
- 意图识别 / 工具调用 / 风险审批主链

**问题现象 / 根因**
- 源码级硬编码审查确认，Phase 63 前 `risk_gate.py`、`action_draft.py`、`intent_policy.py`、`routing.py` 分别维护 action alias、canonical action type、pre-route action terms、action-bound intent set、risk severity/disposition 等安全语义。
- `risk_level` 字段曾同时承载 severity 与 disposition；`manual_review` / `blocked` 等处置值可能被当作 action type 或 risk level 使用。

**影响**
- 新增 action、disposition、risk route 或 intent 时，需要跨多个文件同步，容易造成 action draft 写工具边界、risk gate 审批边界、pre-route 安全路由和 evidence-required 策略漂移。
- 安全审计、approval hash/replay 和工具执行路径难以稳定区分“风险严重度”“处置结果”“可执行动作”。

**处理状态**
- ✅ 已修复验证。Phase 63 建立 `src/agent/safety/taxonomy.py` 作为 canonical owner，统一 executable action types、non-executable dispositions、action aliases、pre-route action aliases、risk severities 和 risk dispositions。
- ✅ `risk_gate.py` 改为 taxonomy-backed action resolution，`risk_level` 只保留 severity，同时输出 `risk_severity` / `risk_disposition`；非可执行 disposition 不再进入 proposed action / snapshot binding。
- ✅ `action_draft.py` 在 ToolPlatform invoke 前用 taxonomy resolver 校验 executable action；`manual_review` / `blocked` fail closed，`compensation` 兼容为 `issue_coupon`。
- ✅ `intent_policy.py` / `routing.py` 从 intent registry / safety taxonomy 派生 action-bound、evidence-required 和 deterministic pre-route action matching；routing-local `_ACTION_BOUND_INTENTS` 已删除。
- ✅ 新增 `tests/architecture/test_safety_taxonomy_boundaries.py`，静态防回归：禁止 migrated callers 重新定义本地 action taxonomy 常量、local canonicalizer、pre-route action tuple、routing action-bound set，或把 `manual_review` / `blocked` 硬编码为 action type。

**证据**
- Phase 63 Plan 01-05；RED/GREEN commits：`de4a916` / `de30961`、`2240af0` / `c584d80`、`8b2a04c` / `1842316`、`535a63d` / `379bcf8`、`741382b` / `0159703`。
- 文件：`src/agent/safety/taxonomy.py`、`src/agent/nodes/risk_gate.py`、`src/agent/nodes/action_draft.py`、`src/agent/intent_policy.py`、`src/agent/routing.py`、`tests/agent/test_safety_taxonomy.py`、`tests/agent/test_nodes/test_risk_gate.py`、`tests/test_execute_action.py`、`tests/agent/test_intent_policy_registry.py`、`tests/agent/test_intent_routing.py`、`tests/architecture/test_safety_taxonomy_boundaries.py`。

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` → `1388 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/safety src/agent/nodes/risk_gate.py src/agent/nodes/action_draft.py src/agent/intent_policy.py src/agent/routing.py tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_safety_taxonomy_boundaries.py` → `All checks passed!`

**剩余风险**
- 🟡 Phase 63 不实现 Phase 64 RAG risk label registry、Phase 65 trace/console label registry、Phase 66 unified operation gateway、Phase 67 config/demo hygiene。
- 🟡 跨 DB/API/frontend/service writer 的状态机 registry 与 DB CHECK hardening 仍按审查结论 defer 到 Phase 68；Phase 63 仅处理 safety taxonomy / action-risk vocabulary drift。
- 🟡 现有 legacy tests / API projection 中仍可能保留 `risk_level="manual_review"` 兼容样例；Phase 63 已通过 taxonomy normalization 和 drift guard 限制其不能重新成为 active executable action 或 risk severity source。

## 2026-07-10 — Phase 63 review loop — recommendation_generation evidence policy drift 已修复验证 ✅

**子系统**
- RAG / recommendation_generation / 意图识别 policy registry

**问题现象 / 根因**
- Phase 63 已将 evidence-required intent policy 迁移到 `IntentPolicyRegistry`，但 code review 发现 `src/agent/nodes/recommendation_generation.py::_policy_evidence_required_for_generation(...)` 仍维护一份手写 intent 集合。
- 该集合与 registry 已发散：`EVIDENCE_REQUIRED_INTENTS` 包含 `order_status_inquiry`，手写集合不包含它。

**影响**
- 新增或调整 intent 的 evidence policy 时，recommendation generation 可能绕过 registry 决策，导致 RAG partial/no-evidence gate 与 routing policy 不一致。
- 如果 registry 不可用，旧实现没有 fail-closed 分支。

**处理状态**
- ✅ 已修复验证。`recommendation_generation.py` 改为调用 `INTENT_POLICY_REGISTRY.requires_evidence(...)`，registry 异常时 fail closed。
- ✅ 新增节点测试锁定 recommendation_generation 消费 registry，并覆盖 registry error fail-closed。

**证据 / 验证**
- 文件：`src/agent/nodes/recommendation_generation.py`、`tests/agent/test_nodes/test_recommendation_generation.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py -q --tb=short` → `1263 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/recommendation_generation.py tests/agent/test_nodes/test_recommendation_generation.py` → `All checks passed!`

**剩余风险**
- 🟡 `recommendation_generation.py` 仍有 RAG risk label 集合与 actionable recommendation 集合，按计划由 Phase 64 统一处理。

## 2026-07-10 — Phase 63 review loop WR-02 — 可执行操作 evidence policy 排序已修复验证 ✅

**子系统**
- 意图识别 / routing / RAG recommendation_generation

**问题现象 / 根因**
- Phase 63 code review 发现 `resolve_risk_decision("small_talk", "execute_action")` 会先套用 no-evidence intent 定义，覆盖 action operation risk template，返回 `evidence_required=False`。
- `routing._policy_evidence_required(...)` 与 `recommendation_generation._policy_evidence_required_for_generation(...)` 也先信任 `evidence_policy` / `routing_hints` 中的显式 `False`，再检查 `draft_action` / `execute_action` / `escalate`，导致可执行操作可能绕过 RAG evidence gate。

**影响**
- 资损相关 action/escalation 在 `rag_context_status="not_required"` 或 explicit false policy flag 下可能进入 `recommendation_generation`，与 Phase 63 action/risk/evidence 词表目标不一致。

**处理状态**
- ✅ 已修复验证。新增共享 `ACTION_EVIDENCE_OPERATIONS`，正常 risk decision 与 routing/generation evidence policy helper 均先判断可执行操作，强制 `evidence_required=True`。
- ✅ 保留 approval-chat hard-negative 例外：`approval_chat_not_trusted` 仍走 `forbidden_in_chat` 且不要求 evidence。

**证据 / 验证**
- Phase 63 REVIEW WR-02；文件：`src/agent/intent_policy.py`、`src/agent/routing.py`、`src/agent/nodes/recommendation_generation.py`、`tests/agent/test_intent_routing.py`、`tests/agent/test_rag_context_routing.py`、`tests/agent/test_nodes/test_recommendation_generation.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_routing.py tests/agent/test_rag_context_routing.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short` → `1314 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/intent_policy.py src/agent/routing.py src/agent/nodes/recommendation_generation.py tests/agent/test_intent_routing.py tests/agent/test_rag_context_routing.py tests/agent/test_nodes/test_recommendation_generation.py` → `All checks passed!`
- Review probe 复核：`resolve_risk_decision("small_talk", "execute_action")` 现在返回 `evidence_required=True`，同类 `route_after_rag_context` 状态返回 `final_response`。

**剩余风险**
- 🟡 本次只修复可执行 operation 对 evidence-required 的优先级；非 action 的 no-evidence intent（如 `small_talk`、当前 metric read）仍按 registry/policy 显式配置处理。

## 2026-07-10 — Phase 64 — RAG risk label 单一事实源与 `manual_review_sensitive` 漂移已修复验证 ✅

**子系统**
- RAG / ContextBuilder / verifier / routing / metrics / recommendation_generation

**问题现象 / 根因**
- Phase 64 前，RAG risk label 集合在 `builder.py`、`metrics.py`、`verifier.py`、`routing.py`、`recommendation_generation.py` 多处维护。
- 其中 `manual_review_sensitive` 已被 verifier、routing、metrics、recommendation_generation 当作语义复核 / manual-review 触发标签，但 `ContextBuilder` 的 `_SAFE_RISK_LABELS` 不包含它，会在 prompt-safe RAG context 构建时过滤掉。
- route reason code（如 `semantic_provider_timeout`）与 evidence risk label（如 `manual_review_sensitive`）边界没有单一 owner，后续新增标签时容易再次混淆。

**影响**
- 敏感证据标签可能无法进入 prompt/final/memory/replay 等安全投影面，导致 downstream manual-review / semantic-review 语义不一致。
- 新增或调整 RAG 标签时，需要同步多个本地集合，缺少 architecture guard 时容易漏改。

**处理状态**
- ✅ 已修复验证。新增 `src/agent/rag_context/risk_labels.py` 作为 canonical RAG risk label owner，统一 prompt-safe evidence labels、semantic/manual-review trigger labels、routing risk labels、metric level-3 trigger markers 和 RAG-coupled route reason groups。
- ✅ `builder.py` 改为使用 `filter_prompt_safe_risk_labels(...)`，`manual_review_sensitive` 可进入现有安全投影面，unknown label 继续 fail-closed。
- ✅ `recommendation_generation.py`、`verifier.py`、`routing.py`、`metrics.py` 均迁移到 registry helper / group。
- ✅ 新增 `tests/architecture/test_rag_risk_label_boundaries.py`，防止迁移后的 caller 重新定义 `_SAFE_RISK_LABELS`、`_SAFE_EVIDENCE_RISK_LABELS`、`_ROUTING_RISK_LABELS`、`_ROUTE_MANUAL_REVIEW_REASONS`、`_ROUTE_STALE_OR_OCR_REASONS`，并校验 helper import source。
- ✅ Phase 64 review IN-01 已补强 drift guard：同一 architecture test 现在会扫描迁移后 caller 的 AST，只要集合字面量或 collection assignment 硬编码两个及以上 canonical RAG risk-label 字符串即失败，避免用新变量名重新建立本地标签事实源。

**证据 / 验证**
- Phase 64 Plan 01-04；summary：`.planning/phases/64-rag-risk-label-unification/64-01-SUMMARY.md`、`64-02-SUMMARY.md`、`64-03-SUMMARY.md`、`64-04-SUMMARY.md`。
- 文件：`src/agent/rag_context/risk_labels.py`、`src/agent/rag_context/builder.py`、`src/agent/rag_context/verifier.py`、`src/agent/rag_context/routing.py`、`src/agent/rag_context/metrics.py`、`src/agent/nodes/recommendation_generation.py`。
- Tests：`tests/agent/rag_context/test_risk_labels.py`、`tests/agent/rag_context/test_context_builder.py`、`tests/agent/rag_context/test_semantic_verifier.py`、`tests/agent/rag_context/test_verifier.py`、`tests/agent/rag_context/test_routing.py`、`tests/agent/rag_context/test_metrics.py`、`tests/agent/test_nodes/test_recommendation_generation.py`、`tests/architecture/test_rag_risk_label_boundaries.py`。
- Focused verification：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_risk_labels.py tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short`。
- Focused ruff：`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/rag_context/risk_labels.py src/agent/rag_context/builder.py src/agent/rag_context/verifier.py src/agent/rag_context/routing.py src/agent/rag_context/metrics.py src/agent/nodes/recommendation_generation.py tests/agent/rag_context/test_risk_labels.py tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py tests/agent/test_nodes/test_recommendation_generation.py tests/architecture/test_rag_risk_label_boundaries.py`。
- Review fix IN-01：`tests/architecture/test_rag_risk_label_boundaries.py`；`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short` → `3 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/architecture/test_rag_risk_label_boundaries.py` → `All checks passed!`。

**剩余风险**
- 🟡 RAG risk label 的前端展示文案、trace/console label 一致性不在 Phase 64 范围内，已明确 defer 到 Phase 65。
- 🟡 route reason code 与 evidence risk label 仍在同一 registry 文件中有少量耦合分组；Phase 64 已用 docstring、trigger 命名和 tests 锁定边界，若后续 reason code 体系扩大，应在 Phase 65 或后续 RAG quality phase 单独拆 registry。

## 2026-07-10 — Phase 64 review fix — duplicate `risk_hints` 合并缺口已修复验证 ✅

**子系统**
- RAG / ContextBuilder / risk label projection

**问题现象 / 根因**
- Phase 64 code review WR-01 发现 `_risk_labels_by_evidence_id(...)` 对同一 `evidence_id` 的多条 `risk_hints` 逐条赋值覆盖，后一条 hint 会替换前一条已过滤出的 prompt-safe label。

**影响**
- 若第一条 hint 含 `manual_review_sensitive`、后一条只含 `authority_checked` 或 unknown label，`citation_map.risk_labels` 和 prompt/final safe context 可能丢失 manual-review 语义，导致 verifier / recommendation 下游无法稳定识别敏感证据。

**处理状态**
- ✅ 已修复验证。`src/agent/rag_context/builder.py` 改为按 `evidence_id` 建 bucket，并在保持输入顺序的前提下合并 prompt-safe labels、去重、继续过滤 unknown labels。
- ✅ 新增 `tests/agent/rag_context/test_context_builder.py::test_duplicate_risk_hints_merge_prompt_safe_labels_for_same_evidence`，覆盖同一 evidence id 两条 hint 中 `manual_review_sensitive` 与 `authority_checked` 同时保留、`raw_debug_secret` 不进入安全投影。

**证据 / 验证**
- Phase 64 REVIEW WR-01；文件：`src/agent/rag_context/builder.py`、`tests/agent/rag_context/test_context_builder.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py -q --tb=short` → `7 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/rag_context/builder.py tests/agent/rag_context/test_context_builder.py` → `All checks passed!`

**剩余风险**
- 🟡 本次只修复同一 evidence id 多条 risk hint 的合并语义；跨 evidence merge、route reason code 与 evidence risk label 分组边界仍沿用 Phase 64 既定 registry 设计。

## 2026-07-09 — Phase 62-68 覆盖矩阵补齐项（源码级硬编码审查）⚠️待规划落地

**子系统**
- 工具调用 / RAG / 记忆 / 意图识别 / 状态机 / 前后端契约 / 本地配置

**问题 / 根因**
- 源码级硬编码审查确认，Phase 62-68 的 roadmap 方向能覆盖大多数已发现的 hardcoding debt，但仍需要在各 phase 的 PLAN.md 中显式锁定具体补齐项，否则容易在执行时只做局部清理。
- 另有一类 LLM-facing 具体工具面过宽的问题，需要在 Phase 65 建立 tool/event/label registry 后由 Phase 66 统一 Operation Contract / Tool Gateway 收敛。

**影响**
- 若 Phase 62 未锁定 business query / metric registry / business id resolver / time policy，`business_metric_query` 可能继续沿用多处硬编码 parser、metric id、status、time preset，新增 list/detail/drilldown 时继续扩大分叉。
- 若 Phase 63 未拆分 risk severity 与 risk disposition，`manual_review` / `blocked` 等处置结果仍可能混入 `risk_level`，action taxonomy 也会继续在 `risk_gate`、`action_draft`、`intent_policy` 多处复制。
- 若 Phase 64 只做命名整理而不统一 RAG label registry，`manual_review_sensitive` 这类标签仍可能在 builder / verifier / routing / metrics 之间被过滤或解释不一致。
- 若 Phase 65 只做 console 文案，不做 event / response_kind / tool name / graph node / frontend payload registry 或 parity 测试，后续新增工具、节点、响应类型仍会漏改前端或 replay validator。
- 若 Phase 66 不收敛 LLM-facing tool surface，`get_order` / `get_refund_case` / `get_ticket` / `business_query` / RAG / action tools 仍会作为具体工具名被 planner 和 UI 多处硬编码，后续新增 operation 时继续扩大漂移面。
- 若 Phase 67 只清单点 demo 常量，不处理 fixture/settings 边界，magic dates、demo IDs、local DB/port、investigate max_iterations、demo adapter role/scope 副本仍会作为隐性环境假设留存。
- 若 Phase 68 不实现状态机 registry，`AgentRun.final_status`、`ActionDraft.status`、API schema、frontend types、DB CHECK / migration 之间仍缺少统一约束与漂移测试。

**处理状态**
- ⚠️ 已完成源码级审查和 phase 归属裁决，尚未进入 Phase 65-68 后续 PLAN.md。
- ⚠️ Phase 62 必须覆盖：metric id / resource / status / time preset registry，metric parser parity，`query_business_metric` service/tool contract 的 `current_snapshot` 边界，business id resolver，`business_query` schema、field/sort/status/time/limit/cursor allowlist，`last_query_spec` / `last_answer_context` / `result_cursor`。
- ⚠️ Phase 63 必须覆盖：risk severity vs risk disposition 拆分，action taxonomy / canonical action type，money/risk extraction 假设，evidence-required / action-bound intent routing registry。
- ⚠️ Phase 64 必须覆盖：RAG risk label registry，尤其 `manual_review_sensitive` 在 builder / verifier / routing / metrics / recommendation 之间的单一事实源和 parity 测试。
- ⚠️ Phase 65 必须覆盖：tool name / event_family / tool label registry，trace event type 与 DB CHECK / replay validator parity，response_kind / SSE payload / frontend type contract，graph node label 与 safe reason label parity。
- ⚠️ Phase 66 必须覆盖：Unified Operation Contract / Tool Gateway、LLM-facing operation spec、ToolCatalog/planner/event/policy/projection/frontend label parity、exact-id compatibility tool migration plan、RAG/action/business operation family separation。
- ⚠️ Phase 67 必须覆盖：demo seed constants、test magic dates、local config / port / DB defaults、demo action status residue、investigate iteration settings、demo authz role/scope 副本。
- ⚠️ Phase 68 必须覆盖：State Machine Registry And DB Constraint Hardening。若 Phase 62 被规划成完整 business query mainline，则原先的 Business Query Production Hardening 不单独开新 phase；若 Phase 62 执行时被缩成 foundation MVP，再考虑在 Phase 68 之后新增 business query coverage expansion。

**证据 / 验证**
- Roadmap phase 边界：`.planning/ROADMAP.md` Phase 62-68。
- 当前状态：`.planning/STATE.md` 显示 Phase 65 为当前待规划焦点，Phase 66-68 已注册待规划。
- 已核实代码证据包括：
  - `src/business/schemas.py`、`src/agent/schemas.py`、`src/agent/routing.py`、`src/business/service.py`、`src/tools/catalog.py`、`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/slot_resolution_gate.py` 的 metric / time / status / parser 重复。
  - `src/agent/rag_context/builder.py`、`src/agent/rag_context/metrics.py`、`src/agent/rag_context/verifier.py`、`src/agent/rag_context/routing.py` 的 RAG risk label 重复与 `manual_review_sensitive` 发散风险。
  - `src/agent/nodes/risk_gate.py`、`src/agent/nodes/action_draft.py`、`src/agent/intent_policy.py` 的 action taxonomy / risk vocabulary 重复。
  - `src/tools/catalog.py`、`src/agent/nodes/investigate_planner.py`、`src/agent/events.py`、`frontend/src/components/timeline/TimelineStep.tsx` 的 tool name / event family / label 重复。
  - `src/replay/validators.py`、`src/db/models.py`、`src/db/migrations/versions/010_replay_event_v3.py`、`src/db/migrations/versions/017_tool_policy_events.py` 的 trace event type 多源维护。
  - `src/api/schemas/agent_runs.py`、`frontend/src/types/events.ts`、`src/db/models.py`、`src/actions/schemas.py` 的 run/action 状态多源维护。
- 本条为审查记录，未运行测试；后续 phase planning / implementation 中的验证命令必须使用 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`。

**剩余风险**
- 🔴 Phase 65-68 尚未生成 PLAN.md；上述补齐项目前只是审查裁决，未被任务化。
- 🔴 统一 Operation Contract / Tool Gateway 与状态机 registry / DB CHECK / API / frontend parity 都已注册为后续 phase，但尚未计划和实现。
- 🟡 Phase 62 若只落 foundation 而不覆盖生产 drilldown/list/detail/cursor/UI/eval，则还需要后续 business query coverage expansion phase。

## 2026-07-09 — Phase 62 Plan 01 business query registry 与 metric routing 派生 ⚠️修复但验证有缺口

**子系统**
- 工具调用 / 意图识别 / agent metric parser / ToolCatalog

**问题 / 根因**
- Phase 61 的 `business_metric_query` 在 `routing`、contextual intent parser、slot resolution parser、investigate fallback、prompt 与 ToolCatalog schema 中各自维护 metric id、resource type、status filter、time preset 和 parser alias。
- 这些枚举和策略属于 business query/drilldown 基础契约；多源维护会导致新增 `list/detail/breakdown/compare` 或新增指标时出现 route/schema/parser 漂移。

**影响**
- metric id、resource type、time policy、status policy 在 agent 与 tool catalog 之间可能不一致。
- `current_snapshot` 与窗口型 time preset 的边界容易被局部硬编码改坏。
- ToolCatalog schema 若漏改，LLM planner 与 deterministic routing 会看到不同的可用枚举。

**处理状态**
- ✅ 新增 `src/business/query/registry.py`，用 frozen descriptor / `MappingProxyType` / `frozenset` 建立 Phase 62 business query registry。
- ✅ registry 锁定 operation/resource/time/status/field/sort/metric descriptor，并保留 Phase 61 `business_metric_query` 兼容 resource mapping（如 `coupon_record_count` → `action_draft`）。
- ✅ `src/agent/routing.py`、`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/slot_resolution_gate.py`、`src/agent/nodes/investigate.py`、`src/agent/prompts.py`、`src/tools/catalog.py` 已改为从 `BUSINESS_QUERY_REGISTRY` 派生 metric/time/status/parser/schema 口径。
- ⚠️ `src/business/service.py` 仍保留 Phase 61 metric runtime 分支和状态过滤实现；这是后续 BusinessQuerySpec/runtime plan 的执行边界，本计划未迁移业务执行层。

**证据 / 验证**
- 文件：`src/business/query/registry.py`、`src/agent/routing.py`、`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/slot_resolution_gate.py`、`src/agent/nodes/investigate.py`、`src/agent/prompts.py`、`src/tools/catalog.py`。
- 测试：`tests/business/test_business_query_registry.py`、`tests/agent/test_required_slots.py`、`tests/agent/test_nodes/test_contextual_intent_resolve.py`、`tests/agent/test_nodes/test_slot_resolution_gate.py`、`tests/agent/test_nodes/test_investigate.py`、`tests/tools/test_catalog.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/tools/test_catalog.py tests/agent/test_nodes/test_investigate.py -q --tb=short` → `185 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/registry.py src/business/query/__init__.py src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/agent/nodes/investigate.py src/agent/prompts.py src/tools/catalog.py tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/tools/test_catalog.py` → 通过
- `rg -n "BUSINESS_QUERY_REGISTRY|BusinessQueryRegistry" src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/tools/catalog.py src/agent/nodes/investigate.py` → 以上 agent/tool catalog surface 均命中 registry import / use。

**剩余风险**
- 🟡 `business_metric_query` 仍是 Phase 61 兼容 entry；后续 plan 需要把 BusinessQuerySpec/runtime/service 边界接上 registry。
- 🟡 registry 当前只覆盖 Phase 62 foundation allowlist 与 parser/schema 派生；cursor、drilldown state、detail/list runtime 与 UI drilldown 仍在后续计划。

## 2026-07-09 — Phase 62 Plan 03 trusted business_query 权限投影边界 ⚠️修复但验证有缺口

**子系统**
- 工具调用 / TrustedContext / ToolPlatform permission boundary

**问题 / 根因**
- Plan 62-02 已建立 `BusinessQuerySpec` strict schema，但 ToolPlatform 侧尚无独立的 trusted `business_query` 权限投影；如果复用 `metrics:read`，会把 Phase 61 metric compatibility 权限直接扩大到新的 list/detail/drilldown read surface。
- `tool:business_query` 必须只能来自已验证 token scope 与角色 scope 的交集，不能从 user text、LLM output、tool args 或 frontend payload 注入。

**影响**
- 没有独立 `business:query -> tool:business_query` 映射时，62-03 无法注册安全的 `business_query` descriptor；后续 62-04 runtime 接入前缺少可信权限边界。
- 若 `metrics:read` 一并授权 `business_query`，现有 metric 兼容路径会静默变成更宽的 business read 权限。

**处理状态**
- ✅ 在 `ROLE_SCOPES` 中为 `support` / `manager` / `admin` 增加 `business:query`，保留 deprecated `merchant` role 仅默认持有 `metrics:read` metric compatibility scope。
- ✅ OAuth password flow scope 表增加 `business:query`。
- ✅ `TrustedContextFactory` 的 `SCOPE_TO_TOOL_PERMISSION` 增加一对一映射 `business:query -> tool:business_query`，并保留 `metrics:read -> tool:query_business_metric`。
- ⚠️ 本条只完成权限投影边界；`business_query` ToolCatalog descriptor/policy denial 与 runtime execution 分别由 62-03 Task 2 和 62-04 继续完成。

**证据 / 验证**
- 文件：`src/auth/jwt.py`、`src/auth/permissions.py`、`src/platform/trusted_context.py`、`tests/platform/test_trusted_context_factory.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py -q --tb=short` → `40 passed, 1 warning`
- `rg -n "business:query|tool:business_query|tool:query_business_metric" src/auth/jwt.py src/auth/permissions.py src/platform/trusted_context.py tests/platform/test_trusted_context_factory.py` → required mappings/tests found。

**剩余风险**
- 🟡 `tool:business_query` 目前只是 trusted permission；descriptor visibility, policy denial, executor safe failure 仍需本 plan Task 2 完成。
- 🟡 runtime query scope/no-existence-leak enforcement 仍属于 62-04，当前不执行数据库 query。

## 2026-07-09 — Phase 62 Plan 03 business_query ToolPlatform descriptor 与 planner allowlist 同步 ⚠️修复但验证有缺口

**子系统**
- 工具调用 / ToolCatalog / ToolPolicy / investigate planner

**问题 / 根因**
- Plan 62-02 的 `BusinessQuerySpec` 已能拒绝 authority fields 与 raw SQL 类字段，但 ToolCatalog 尚未注册 `business_query` 主读工具，ToolPolicy 也没有可验证的 descriptor schema 来在 executor 前拒绝 `tenant_id`、`merchant_scope`、`raw_sql`、`where`、任意 filter object 或 raw cursor string。
- `investigate_planner.py` 仍维护静态 `INVESTIGATE_ALLOWED_TOOL_NAMES`，新增 planner-visible tool 时若只改 catalog，会复现 Phase 61 已登记的 catalog/planner allowlist 漂移风险。

**影响**
- 没有 descriptor 时，LLM planner / ToolPlatform 看不到 Phase 62 主读契约，只能继续依赖 `query_business_metric` 兼容入口。
- 没有 schema-denial 测试时，authority-bearing 或 free-form DB shape 可能进入 executor/service 层后才失败，削弱 ToolPlatform 边界。
- planner allowlist 漏改会造成「ToolPlatform 可见但 planner output schema 拒绝」的运行时断裂。

**处理状态**
- ✅ 新增 `business_query` read-only ToolCatalog descriptor：`required_permission="tool:business_query"`、`caller_allowlist=["investigate"]`、`resource_type="business_query"`、`executor="business"`、`additionalProperties: false`。
- ✅ descriptor input schema 从 `BusinessQuerySpec` 字段和 `BUSINESS_QUERY_REGISTRY` operation/resource/metric/time/status/field/sort allowlist 派生；output schema 锁定 `BusinessQueryResultV1` 顶层 shape。
- ✅ ToolPlatform tests 覆盖 wrong caller、missing permission、authority fields、raw SQL keys、arbitrary filters、raw cursor strings 均在 dispatch 前 fail closed。
- ✅ `BusinessToolExecutor` 对 `business_query` 只做 schema validation 后返回 safe deferred `unavailable`，不接数据库 runtime、不构造 SQL、不调用 repository。
- ✅ `INVESTIGATE_ALLOWED_TOOL_NAMES` 同步加入 `business_query`，并新增 catalog/planner allowlist parity 测试。
- ⚠️ 静态 planner allowlist 尚未从 ToolCatalog 自动派生；本次只做同步与测试护栏。

**证据 / 验证**
- 文件：`src/tools/catalog.py`、`src/tools/executors/business.py`、`src/agent/nodes/investigate_planner.py`、`tests/tools/test_catalog.py`、`tests/tools/test_tool_platform.py`。
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/business/test_business_query_schemas.py -q --tb=short` → `103 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools/catalog.py src/tools/policy.py src/tools/executors/business.py src/agent/nodes/investigate_planner.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py` → 通过
- `rg -n "name=\"business_query\"|tool:business_query|additionalProperties|raw_sql|merchant_scope|tenant_id" src/tools/catalog.py src/tools/policy.py src/tools/executors/business.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py` → required descriptor/schema/policy-denial evidence found。

**剩余风险**
- ✅ business_query runtime execution deferred 风险已由 Phase 62 Plan 04 Task 2 关闭：`BusinessToolExecutor` 现委托 `BusinessToolService.invoke_tool(...)`。
- 🟡 planner allowlist 仍是静态副本；post-Phase 62 或 Phase 65 tool-label/registry cleanup 可考虑把 planner allowlist 从 ToolCatalog 派生。

## 2026-07-09 — Phase 62 Plan 04 BusinessFactService business_query runtime ✅已修复验证

**子系统**
- 工具调用 / BusinessFactService / business query runtime

**问题 / 根因**
- 62-03 已注册 `business_query` ToolCatalog descriptor 和 trusted `tool:business_query` 权限，但 runtime 仍是 executor 里的 safe deferred `unavailable`，`BusinessFactService` 尚未拥有 `aggregate/list/detail/breakdown/compare` 的受控执行路径。
- `BusinessFactRefV1.resource_type` 只允许旧业务资源和 `business_metric`，无法表达新 `business_query` fact ref，导致 62-04 的稳定 fact envelope 无法通过契约校验。

**影响**
- Phase 62 主读契约只能停留在 schema/policy 层，后续 drilldown/projection/eval 无法依赖 `fact["business_query"]` 的稳定结构。
- 若不补 service runtime，新增 list/detail/drilldown 容易重新落回 agent/tool 侧拼 query 或 repository generic list helper，破坏 D-62-06 与 no-existence-leak 边界。

**处理状态**
- ✅ 新增 `BusinessQueryCompiler`，只从 registry-backed `BusinessQuerySpec` 编译 SQLAlchemy `select()` statement，不引入 raw SQL 或 generic list helper。
- ✅ `BusinessFactService.query_business(...)` 执行 aggregate/list/detail/breakdown/compare，并把 normalized result 固定放在 `fact["business_query"]`。
- ✅ `query_business_metric(...)` 改为先验证旧 `BusinessMetricQueryInput`，再转换为 `BusinessQuerySpec`，委托 `query_business(...)` 后恢复旧 `business_metric` result shape。
- ✅ `BusinessFactRefV1.resource_type` 增加 `business_query`，支持新 fact ref 契约。

**证据 / 验证**
- 文件：`src/business/query/compiler.py`、`src/business/service.py`、`src/tools/contracts.py`、`tests/business/test_business_query_service.py`、`tests/business/test_service.py`。
- Phase / commit：62-04 Task 1 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_service.py tests/business/test_service.py -q --tb=short` → `57 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/compiler.py src/business/query/__init__.py src/business/service.py src/tools/contracts.py tests/business/test_business_query_service.py tests/business/test_service.py` → 通过
- `rg -n "async def query_business|BusinessQueryCompiler|metric_input_to_business_query" src/business/service.py src/business/query/compiler.py` → required symbols found。

**剩余风险**
- ✅ `business_query` ToolPlatform runtime 接入已由 62-04 Task 2 关闭。
- 🟡 final response / API / frontend projection 仍未消费 `fact["business_query"]`；按计划留给 62-06/62-07。

## 2026-07-09 — Phase 62 Plan 04 business_query ToolPlatform dispatch ✅已修复验证

**子系统**
- 工具调用 / investigate business_context / business query runtime

**问题 / 根因**
- 62-03 为 `business_query` 注册了 catalog/policy/allowlist，但 `BusinessToolExecutor` 仍有 `_business_query_deferred_result(...)` 分支，对合法请求返回 `BUSINESS_QUERY_RUNTIME_DEFERRED`。
- investigate 聚合 business fact 时统一写入 `ToolResultProjector.normalized_result`，对 `fact["business_query"]` 这类已在 service 层脱敏和规范化的嵌套 payload 会丢失 `operation/resource/rows/cursor/answer_context` 等 drilldown 所需结构。

**影响**
- ToolPlatform 允许 `business_query` 后仍无法到达 service runtime，agent 端只能得到 unavailable。
- 即使 service 返回 `fact["business_query"]`，investigate 的 `business_context.facts["business_query"]` 也无法承载后续 final/API/frontend drilldown 需要的稳定查询结果。

**处理状态**
- ✅ 移除 executor deferred 分支，`BusinessToolExecutor.has_tool(...)` 和 `execute(...)` 统一委托 `BusinessToolService`。
- ✅ investigate 对 `resource_type == "business_query"` 且 `result.data["business_query"]` 为 dict 的结果，写入该规范 payload；其他业务 fact 仍沿用 projection normalized result。
- ✅ 修正 `business_query` ToolCatalog output schema：ToolPlatform 验证 `ToolResultV2.data` 时使用 `{"business_query": BusinessQueryResultV1}` fact envelope，而不是只验证内部 result。
- ✅ 新增 ToolPlatform runtime dispatch、investigate accumulation、catalog output envelope 回归测试。

**证据 / 验证**
- 文件：`src/tools/executors/business.py`、`src/tools/catalog.py`、`src/agent/nodes/investigate.py`、`tests/tools/test_tool_platform.py`、`tests/tools/test_catalog.py`、`tests/agent/test_nodes/test_investigate.py`。
- Phase / commit：62-04 Task 2 GREEN（本条所在提交）
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/tools/test_catalog.py -q --tb=short` → `155 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools/executors/business.py src/tools/catalog.py src/agent/nodes/investigate.py tests/tools/test_tool_platform.py tests/tools/test_catalog.py tests/agent/test_nodes/test_investigate.py .planning/ARCHITECTURE-DEBT.md .planning/LOCAL-VALIDATION-ISSUES.md` → 通过

**剩余风险**
- 🟡 final response / API / frontend projection 仍未消费 `fact["business_query"]`；按计划留给 62-06/62-07。
- 🟡 planner allowlist 仍是静态副本；post-Phase 62 或 Phase 65 tool-label/registry cleanup 可考虑把 planner allowlist 从 ToolCatalog 派生。

## 2026-07-09 — Phase 62 Plan 05 Task 1 business_query 安全答案上下文状态边界 ⚠️修复但验证有缺口

- **子系统**：工具调用 / Agent Graph 状态 / 意图识别 drilldown 上下文
- **问题现象 / 根因**：62-04 已让 `BusinessFactService` 返回稳定 `fact["business_query"]`，但 `AgentState` 尚无 `last_query_spec`、`last_answer_context`、`result_cursor` 和 expected-slot 上下文字段；`receive_request` 也没有同线程/同身份上下文绑定检查。这样后续 `订单号是多少？` 等 drilldown 只能重新解析最终回复文本或失去上轮查询结构，且存在跨 user/tenant/thread/scope 误用旧上下文的风险。
- **影响**：多轮 drilldown 无法安全复用上一轮查询范围，也无法证明未把 raw rows、raw tool args、tenant_id、merchant_scope 或 denied id 放进可回放状态。若后续直接做 follow-up parser，会缺少可信状态边界。
- **处理状态**：⚠️ 已完成 Task 1 范围内修复并通过节点级验证。`AgentState` 新增 drilldown 上下文字段；`investigate` 在成功 `business_query` 后只从 `BusinessQueryResultV1.answer_context` 提取 replayable `BusinessQuerySpec`、safe answer context 和结构化 cursor，并在 `permission_denied` 等非成功结果时显式清空旧上下文；`receive_request` 用 fingerprint 绑定 tenant/user/role/thread/session/scope，不在状态中存 raw authority fields，fingerprint 不匹配时清空上下文。
- **证据**：Phase 62 Plan 05 Task 1；文件 `src/agent/state.py`、`src/agent/nodes/receive_request.py`、`src/agent/nodes/investigate.py`、`tests/agent/test_nodes/test_receive_request.py`、`tests/agent/test_nodes/test_investigate.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` → `106 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/investigate.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_investigate.py` → 通过。
- **剩余风险**：🟡 本 task 只建立安全状态边界；follow-up phrase 解析、`business_query_spec` 派生、slot gate 路由和 graph 级 `本周多少订单？ -> 订单号是多少？` 重执行验证仍由 62-05 Task 2 完成。final/API/frontend 投影仍按计划留给 62-06/62-07。

## 2026-07-09 — Phase 62 Plan 05 Task 2 business_query drilldown expected-slot pipeline ✅已修复验证

- **子系统**：意图识别 / slot resolution / 工具调用 / business_query drilldown
- **问题现象 / 根因**：Task 1 建立了安全 answer context，但 `contextual_intent_resolve` 尚不会把 `订单号是多少？` 这类同线程 field request 映射为 `business_query_spec`；`slot_resolution_gate` 只认 metric slots；`investigate` deterministic fallback 只会调用 `query_business_metric`。此外，旧 metric 首轮结果若不生成兼容 `last_query_spec`，`本周多少订单？ -> 订单号是多少？` 无法接上 drilldown。
- **影响**：用户看到聚合答案后追问列表字段时，系统要么退回 clarification/unsupported，要么只能重新让 LLM/planner 猜工具参数，无法证明时间范围、filter、scope 与上一轮安全上下文一致。
- **处理状态**：✅ 已修复并通过节点级和 graph 级验证。新增共享 expected-slot type 约束；`contextual_intent_resolve` 仅在 `business_query_context_binding(...)` 匹配时从 `last_answer_context` 派生 registry-validated `BusinessQuerySpec`；`slot_resolution_gate` 将 `business_query_spec` 作为 deterministic resolved slot；`routing` 在 `business_metric_query` 路径中优先认可 validated `business_query_spec`；`investigate` 优先通过 ToolPlatform 调用 `business_query`，并为成功 `query_business_metric` 生成安全兼容 drilldown context。
- **证据**：Phase 62 Plan 05 Task 2；文件 `src/agent/routing.py`、`src/agent/nodes/contextual_intent_resolve.py`、`src/agent/nodes/slot_resolution_gate.py`、`src/agent/nodes/investigate.py`、`tests/agent/test_nodes/test_contextual_intent_resolve.py`、`tests/agent/test_nodes/test_slot_resolution_gate.py`、`tests/agent/test_nodes/test_investigate.py`、`tests/agent/test_graph.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py -q --tb=short` → `147 passed, 36 warnings`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/state.py src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/agent/nodes/investigate.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py` → 通过。
- **剩余风险**：🟡 当前 field request parser 只覆盖 registry-backed 常见安全字段（如 `order_no`）与 cursor request；更复杂自然语言字段组合、final/API/frontend drilldown projection 仍按计划留给 62-06/62-07。

## 2026-07-09 — Phase 62 Plan 06 Task 1 business_query projection / final / API 安全投影 ✅已修复验证

- **子系统**：工具调用 / final_response / agent-runs API-SSE / business_query projection
- **问题现象 / 根因**：62-04/62-05 已能产生并保存稳定 `fact["business_query"]`，但 `ToolResultProjector`、`final_response` 和 `/agent-runs` final SSE payload 仍只认识 Phase 61 `metric_answer` 投影；如果直接把 business_query runtime payload 透传给最终回复或 API，可能泄漏 raw rows、raw args、tenant_id、merchant_scope、raw cursor token、routing hints 或 denied resource id。
- **影响**：Phase 62 list/detail/breakdown/compare 即使 runtime 安全，也无法保证 prompt/UI/API 表面只消费 allowlisted rows 和安全标签；frontend 也无法用稳定 `business_query_answer.business_query` contract 渲染结果。
- **处理状态**：✅ 已修复并通过 focused backend 验证。新增 `src/business/query/projection.py`，从 normalized `BusinessQueryResultV1` 生成固定 allowlist 的 prompt-safe / UI-safe metadata；`ToolResultProjector` 增加 business_query prompt summary；`final_response` 优先消费 `business_context.facts["business_query"]` 并输出 `response_kind="business_query_answer"`；`agent_runs` final payload 只输出 `business_query` allowlist；`SseEventPayload` 增加 schema 字段用于 drift 检测。
- **证据**：Phase 62 Plan 06 Task 1；文件 `src/business/query/projection.py`、`src/tools/projection.py`、`src/agent/nodes/final_response.py`、`src/api/routers/agent_runs.py`、`src/api/schemas/agent_runs.py`、`tests/tools/test_projection.py`、`tests/agent/test_nodes/test_final_response.py`、`tests/test_agent_runs_api.py`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py -q --tb=short` → `124 passed, 1 warning`；`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/projection.py src/business/query/__init__.py src/tools/projection.py src/agent/nodes/final_response.py src/api/routers/agent_runs.py src/api/schemas/agent_runs.py tests/tools/test_projection.py tests/agent/test_nodes/test_final_response.py tests/test_agent_runs_api.py` → 通过。
- **剩余风险**：🟡 frontend Timeline/Details 对 `business_query_answer` 的展示仍按计划留给 62-07；Phase 65 仍需处理全局 response-kind / tool-label / console-label registry parity。

## 2026-07-10 — Phase 64.1 Plan 01 推荐动作 canonicalization 与 fail-closed 路由 ✅已修复验证

- **子系统**：意图识别 / safety taxonomy / recommendation routing
- **问题现象 / 根因**：`recommendation_generation` 维护本地 `_ACTIONABLE_RECOMMENDATIONS` 并用 substring 判定 action claim；中英文别名、多个动作同时出现、未知值和结构异常值没有统一 typed candidate，router 也无法区分“普通无动作建议”和“未解析的潜在动作”。
- **影响**：LLM 输出可绕过 Phase 63 taxonomy；未知、歧义或 malformed action candidate 可能进入普通 material claim / final response 路径，无法证明风险判断消费的是 canonical action identity。
- **处理状态**：✅ `ActionResolution` 增加 registry provenance 与 schema validity；shared resolver 支持 canonical/中英文 alias/严格结构化输入，并对 approval-chat hard negative、unknown、ambiguous、schema-invalid 值稳定返回 `manual_review`。推荐节点在 material claim 之前写入 `canonical_action`，只有 canonical executable action 才生成 action claim；未解析候选写入 `manual_review_required`。router 消费 typed candidate，把未解析候选送入 claim/risk fail-closed 链，不走普通完成分支。本地 actionable set 已删除。
- **证据**：Phase 64.1 Plan 01；`src/agent/safety/taxonomy.py`、`src/agent/state.py`、`src/agent/nodes/recommendation_generation.py`、`src/agent/routing.py`；RED commit `80cd526`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_recommendation_generation.py tests/agent/rag_context/test_routing.py tests/test_graph_routing.py -q --tb=short` → `226 passed, 1 warning`；对应 `uv run ruff check` → 通过。
- **剩余风险**：🟡 本 plan 只修 canonical candidate 与 recommendation/claim routing；deterministic risk parity、approval contract、capability 和 terminal propagation 分别由 64.1-02 至 64.1-05 完成，最终 architecture guard/full matrix 由 64.1-06 收口。
## 2026-07-10 — Phase 64.1 Plan 02 deterministic risk authority ✅已修复验证

- **子系统**：意图识别 / Agent safety risk gate
- **问题 / 根因**：`risk_gate` 的 deterministic fallback 只遍历 `high_risk`，未命中就直接取第一条 `low_risk`；YAML 中的 `medium_risk` 完全不参与 runtime 判定。LLM timeout、unavailable 或 schema failure 因而可能把 partial refund 等 medium action 降为 low/allow，且 `approval_required=false` 曾被直接等价为 auto-allowed binding。
- **影响**：配置中的 medium 规则会在失败路径消失；LLM 或配置故障可造成风险降级与自动 draft 授权候选，违反 Phase 63 taxonomy 和 backend deterministic authority。
- **处理状态**：✅ 统一 validated high/medium/low evaluator，固定 high > medium > low precedence，拒绝缺组、空组、重复 rule id、未知 condition 和 malformed YAML；unknown/unmatched/config invalid 均稳定进入 medium/manual_review。LLM 合并只能保留或升级 deterministic 结果，不能覆盖其 rule identity 做降级。auto-allowed 现在只接受 `low + allow + approval_required=false`。
- **证据**：Phase 64.1 Plan 02；`src/agent/nodes/risk_gate.py`、`tests/agent/test_nodes/test_risk_gate.py`、`tests/test_interception_rate.py`；RED commit `6f3e881`。
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/test_interception_rate.py tests/approvals/test_hash_binding.py tests/approvals/test_snapshots.py -q --tb=short` → `69 passed`；plan-scoped `uv run ruff check` → `All checks passed!`。
- **剩余风险**：🟡 本 plan 保留现有 `RiskDecisionV1`、snapshot/hash 与 approval contract；server-minted bounded capability、approval API/frontend parity 和 terminal failure propagation仍由 64.1-03 至 64.1-05 完成，64.1-06 做最终跨层 guard。

## 2026-07-10 — Phase 64.1 Plan 05 action-draft 跨层终态完整性 ✅已修复验证

- **子系统**：工具调用 / Agent Graph / approval resume / agent-runs API-SSE / 记忆投影
- **问题现象 / 根因**：`action_draft` 原先无条件连接 `final_response`，API completion 又主要依赖已有 copy 或 `node_errors`；因此授权、工具/存储、`DraftOutcomeV1` identity 或关键 audit 失败可能被包装成 completed response/run，approval resume 在没有 `node_errors` 时也可能漏判，memory finalizer 只信调用方传入的 completed status。
- **影响**：失败动作可能在 graph、DB、polling、SSE、approval resume 与 memory 中出现互相矛盾的成功终态，并可能把内部错误文本或失败路径写成 assistant message / memory projection。
- **处理状态**：✅ 新增共享 typed `ActionDraftTerminalV1` projector；只有 tenant/run/draft identity 一致、`status=not_executed_demo`、`external_side_effect=false`、durable `action_draft.v2` 且存在 completed `create_coupon_grant_draft` audit 的结果可完成。graph 改为 conditional terminal edge；final response、agent-runs、approval resume 与 memory 复用同一 fail-closed contract，失败只输出稳定安全文案/错误码且不执行 completed memory finalizer。resume reconciliation 现在保留其构造的 trusted identity state，避免成功草稿在终态校验时丢失 tenant/run 绑定。
- **证据**：Phase 64.1 Plan 05；commits `ebf12c3`、`80bf50a`、`4c140c6`、`94ac0ad`；`src/agent/routing.py`、`src/agent/graph.py`、`src/agent/nodes/action_draft.py`、`src/agent/nodes/final_response.py`、`src/api/routers/agent_runs.py`、`src/api/routers/approvals.py`、`src/api/services/agent_run_memory.py`。
- **验证**：Plan 05 聚合 pytest → `299 passed, 87 warnings`；API/approval/integration 聚合 → `125 passed, 11 warnings`；action-draft architecture focused → `13 passed, 1 warning`；全部 scoped Ruff → `All checks passed!`。
- **剩余风险**：🟡 现有 LangGraph/LangChain warnings 为既有 annotation/deprecation 噪声；Phase 64.1-06 仍需跑最终跨层 architecture guard/full matrix，确认后续改动不会重新引入无条件成功边或 completed-memory 漂移。

## 2026-07-10 — Phase 64.1 code-review terminal / approval / frontend safety gaps ✅已修复验证

- **子系统**：意图识别 / 风险审批 / 工具调用终态 / 记忆投影 / agent-runs API-SSE / Console
- **问题现象 / 根因**：Phase 64.1 初次 deep code review 确认七项跨层缺口：unresolved action 与 `risk_disposition=manual_review|blocked` 没有共享非成功终态，可能被 final/API/memory 默认成 completed；新 `canonical_action` / `risk_signals` 未在 turn ingress 与所有 recommendation 出口清空；approval GET/list/SSE 复用 `FOR UPDATE` level read，decision preflight 形成 Level→Request，而 mutation 为 Request→Level→Assignment；terminal approval GET 只能查 pending level/assignment；Console polling/reconnect 只要有 `final_response` 就把消息标 completed，active callback 又无法区分 submitted/stale/ambiguous/error；SSE context 只校验 run id，没有 immutable identity 与单调版本约束。
- **影响**：未证明安全的动作建议可能进入 completed assistant/message/memory；跨 turn checkpoint 可能继承旧人工复核信号；并发 decision/expiry 可能触发 PostgreSQL deadlock；丢失 POST 响应后无法用权威 terminal GET 收敛；旧/跨 assignment SSE 可回退 Console context，且失败提交可能误报成功。
- **处理状态**：✅ commits `19f2d05`、`573bd12`、`727a388`、`5e8850e` 已修复。`RunTerminalV1` 统一 action error、deterministic final output、manual review/refused/blocked 的 graph/API/SSE/lifecycle/memory 分类并禁止非成功 memory；turn ingress 与 recommendation success/skip/failure 显式重置安全字段。approval read path 改为 nonlocking，mutation 保持 Request→Level→Assignment；terminal GET 返回 scoped record + `decision_context=null`，重复 decide 对 scoped terminal request 保持稳定 409，而 absent/cross-tenant 仍为 404/no-existence-leak。Console 使用 status-first message、discriminated submission outcome、query-first terminal reconciliation（不重放 POST）和 immutable identity + monotonic clock replacement predicate。
- **证据**：`src/agent/routing.py`、`src/agent/nodes/final_response.py`、`src/agent/nodes/receive_request.py`、`src/agent/nodes/recommendation_generation.py`、`src/api/routers/agent_runs.py`、`src/api/services/agent_run_memory.py`、`src/approvals/repository.py`、`src/approvals/service.py`、`src/api/routers/approvals.py`、`frontend/src/lib/api.ts`、`frontend/src/hooks/useAgentRun.ts`、`frontend/src/components/details/ApprovalTab.tsx` 及对应 integration/API/PostgreSQL concurrency/Vitest/Playwright tests。
- **验证**：terminal/turn/lifecycle focused backend `242 passed`；approval service/API aggregate `110 passed`；approval architecture focused `23 passed`；最终跨层聚合首轮为 `449 passed / 1 failed` 并捕获重复 decide 404 回归，修复后 approval API/integration 回归 `45 passed`；frontend Vitest `4 files / 30 tests`、production build 通过、mocked desktop/mobile Playwright `10 passed`；相关 Ruff 通过。
- **剩余风险**：🟡 本轮没有引入通用 operation gateway、production external effect 或新的 permission；Phase 64.2 的 evidence/replay/memory identity、Phase 66 的通用 gateway、Phase 69 的 LLM gateway 仍按既定 named phase 负责。后续改动须保留 nonlocking read、Request→Level→Assignment、terminal GET nullable context、monotonic SSE context 与 non-completed memory guards。

## 2026-07-10 — Phase 64.1 code-review iteration 2 terminal / resume / freshness / scope gaps ✅已修复验证

- **子系统**：工具调用终态 / 记忆投影 / approval resume / agent-runs API-SSE / Console
- **问题现象 / 根因**：第二轮 deep review 确认四项剩余缺口：共享 `project_run_terminal()` 先检查 stale action-draft shape，再读取 renderer 已产出的权威 evidence/claim 非成功终态；`APPROVAL_RESUME_FAILED` 在 Console 中会被 terminal approval GET 误当成已收敛，且丢失后端恢复所需的 frozen decision body；strict-newer replacement 被错误复用为 freshness revalidation，导致 exact authoritative context 不能恢复 freshness，而 pre-submit GET 又可能直接提交未重新审阅的新版本；manager 单资源 get/decide 在 cross-merchant 时返回 403，且 terminal retry 可能在 scope check 前泄出 binding 409。
- **影响**：同一 run 的 graph 文案与 DB/SSE/polling/replay/memory reason 可能对真实 claim/evidence failure 分类不一致；已落库但恢复未完成的审批没有安全可达的人工恢复入口；审批上下文可能永久不可决定或在未重新审阅新版 payload 时提交；manager 可区分其他 merchant 的 approval 是否存在。
- **处理状态**：✅ commits `3d644a4`、`b4b0c61`、`34fef39`、`4870796` 已修复。显式 `manual_review/refused/error` 终态现在先于 stale draft 分类；Console 将 resume failure 保留为独立 `resume_incomplete`，冻结 byte-identical body，查询 approval + run 后只在用户二次确认时调用既有 backend retry，且后端事件/decision cardinality保持一次决定；exact 全 payload/context equality 只恢复 freshness、不替换对象，strict-newer 才替换且必须重新审阅，older/cross-identity 保持拒绝；scope-aware lookup 在 terminal retry/body 校验前执行，cross-merchant 与不存在资源统一返回同一 generic 404。
- **证据**：`src/agent/routing.py`、`src/api/routers/approvals.py`、`frontend/src/lib/api.ts`、`frontend/src/hooks/useAgentRun.ts`、`frontend/src/components/details/ApprovalTab.tsx`、`tests/test_agent_runs_api.py`、`tests/test_approval_api.py` 及对应 frontend contract/hook/component tests。
- **验证**：terminal/recommendation/lifecycle/API 聚合 → `255 passed, 3 warnings`；approval service/API 聚合 → `62 passed, 1 warning`；frontend Vitest → `4 files / 36 tests passed`；production build 通过；mocked desktop/mobile Playwright → `10 passed`；相关 Ruff → `All checks passed!`。
- **剩余风险**：🟡 网络层若在用户显式恢复重试时再次丢失响应，Console 保持 ambiguous 且不会自动再发 POST；需要用户查询最新状态后再决定。Phase 64.2/66/69 与 production external effects 的既定边界未改变。

## 2026-08-04 — citation-invalid 无动作结果被误投影为 unresolved action ✅已修复验证

- **子系统**：RAG 引用成员校验 / recommendation generation / final response 终态。
- **问题现象 / 根因**：当 LLM 的全部 citation 都不属于当前 verified evidence package 时，`recommendation_generation` 会把 `recommended_action` 改为 `citation_invalid`；但随后仍调用 executable-action taxonomy 解析该安全哨兵值，生成 `canonical_action.disposition=manual_review` 与 `manual_review_required`。`project_run_terminal()` 因而在 final response 的既有 `citation_invalid -> insufficient_evidence` 分支之前，把结果误分类为 `unresolved_action / manual_review`。
- **影响**：无效引用仍不会创建动作，但用户可见终态、trace 与预期的证据不足语义不一致；旧 facade integration 回归稳定失败为 `manual_review != insufficient_evidence`。
- **处理状态**：✅ 已将 `insufficient_evidence`、`citation_invalid`、`retrieval_error` 统一为 recommendation 层 no-action 集合；这些值不再生成 canonical action 或 manual-review risk signal，并新增 membership-invalid 回归断言。
- **证据**：`src/agent/nodes/recommendation_generation.py`、`tests/agent/test_nodes/test_recommendation_generation.py`、`tests/knowledge/test_facade_integration.py`；focused recommendation/final/routing 聚合为 `164 passed, 2 warnings`；最终 CI 等价全量为 `4211 passed, 4 skipped, 126 warnings`；全仓 Ruff check/format 与 Phase 58 strict classifier 均通过。
- **剩余风险**：无本条已知阻塞；现有 LangGraph annotation、Alembic 配置与部分 AsyncMock runtime warnings 为既有告警，未改变本条 no-action 终态结论。

## 2026-08-05 — RAG evaluator 双实现与测试事实源漂移 ✅已修复验证

- **子系统**：RAG 检索评测 / golden dataset / 诊断 trace。
- **问题现象 / 根因**：`Makefile` 与聚合 evaluator 已使用 `scripts/eval_rag.py`，但单元测试仍导入保留完整旧实现的 `scripts/eval_rag_hit_at_5.py`；演进时未同步迁移 owner，造成 22 条与 14 条 golden、`0.85` 与 `0.80` 阈值、JSON report 与 hybrid trace 能力分叉。
- **影响**：旧测试通过不能证明活跃 evaluator 的 CLI、报告、默认数据集和诊断投影受到保护，后续 benchmark 结果可能因入口不同而不可比较。
- **处理状态**：✅ `scripts/eval_rag.py` 已成为唯一实现并保留 hybrid trace；legacy 文件已收为带弃用提示的兼容转发；测试直接覆盖 canonical CLI/report/scorer/22 条 golden schema，并增加 Makefile、`scripts/eval_all.py` 与 legacy delegation parity guard。
- **证据**：quick fix（未提交）；`scripts/eval_rag.py:80-98,128-170`、`scripts/eval_rag_hit_at_5.py:1-60`、`tests/test_rag_eval.py:148-296`；focused pytest → `20 passed, 1 warning`；scoped Ruff check → `All checks passed!`；format check → `3 files already formatted`。
- **剩余风险**：无当前架构阻断。legacy wrapper 是有意兼容面且不再拥有独立逻辑；旧 14 条数据文件不再被活跃入口或测试读取。DB-backed 指标质量与多格式 benchmark 扩充属于后续评测内容，不影响本条单一 evaluator owner 的关闭结论。

## 2026-08-05 — Phase 64.2 Plan 03 memory candidate identity 多 owner 漂移 ✅已修复验证

- **子系统**：记忆（session / long-term / case memory / case working context）identity、dedupe、write event。
- **问题现象 / 根因**：session node、session service、long-term、case-memory 与 CWC 各自维护 content/source serializer 或 candidate hash helper；同一候选可在 node、store、event、retry 与 lifecycle 路径得到不同 identity。旧 `NFKC + casefold` normalization 还会折叠 proper noun 大小写，且 source-only tombstone 若继续用 legacy 默认 profile，会与新 v2 candidate 失配。
- **影响**：dedupe、tombstone、review/delete event 和用户可见投影可能无法指向同一候选；旧 hash 若被静默按新规则解释，会破坏已存身份的可验证性。
- **处理状态**：✅ 已修复并通过精确验证。`src/memory/identity.py` 现为 normalization、content/source/candidate hash 与四类 typed builder 的唯一 owner；新写入固定 `nfc_selective_v2`（NFC、空白归一、仅注册 enum-like 字段小写、proper noun 保持），legacy profile 只按旧 namespace 验证。session service 每个候选只计算一次并在 result/event/node 投影复用；long-term、case 与 CWC 的 store/dedupe/review/delete 路径消费同一个 typed result；stored row 只有在其既有 hashes 与某个 profile 精确匹配时才采用该 profile。
- **证据**：Phase 64.2 Plan 03；commits `756a214`、`c727fae`、`705a448`、`e8b3d68`、`1742c9e`、`ed9aa13`、`8ee94a0`；`src/memory/identity.py`、`src/memory/service.py`、`src/agent/nodes/memory_write.py`、`src/memory/long_term.py`、`src/memory/case_memory.py`、`src/memory/case_working_context_service.py`。
- **验证**：三条 plan 精确 pytest 分别为 `17 passed`、`55 passed`、`79 passed`，全部 scoped Ruff 通过；跨 builder 测试验证 named owner 每候选调用一次，stored/event/result hashes 与 normalized source ref 完全一致。
- **剩余风险**：🟡 Plan 07/08 仍负责 reviewed provenance persistence 与 lifecycle columns/约束；Plan 09 仍需增加 AST ownership guard，防止后续重新引入 caller-local serializer。这些是已命名后续范围，不影响 Plan 03 当前 identity parity。

## 2026-08-05 — Phase 64.2 Plan 04 approval snapshot evidence 信任边界 ✅已修复验证

- **子系统**：RAG 证据身份 / 风险审批 snapshot / revision re-risk。
- **问题现象 / 根因**：approval create、edit revision 与 attach-info replacement 原先把调用方提供的 `EvidenceRefV1` 通过 Pydantic shape 校验和本地 projection 后直接写入 snapshot；create 还会在 `verified_evidence_refs` 与 `evidence_refs` 之间选择持久化来源。该路径没有在审批 tenant 下重算 exact immutable document/chunk identity，existing snapshot 复用也只校验 ref/hash/action binding，没有比较 snapshot 已存 evidence。
- **影响**：伪造 hash/version、legacy ambiguous alias、跨 tenant 或同 tenant 跨 scope ref 可能成为审批 snapshot/re-risk 的可信依据；独立 verified list 可与 snapshot evidence 漂移，破坏后续 replay 与人工审批权威性。
- **处理状态**：✅ `ApprovalService` 现统一调用 `EvidenceVersionRepository.resolve_exact(...)`，固定 exact `scope_type="tenant_policy"`、`scope_id=str(tenant_id)`，由 repository identity 重建并 canonical 排序一次；该单一列表驱动 proposed action、snapshot、create-time `ApprovalRequest.verified_evidence_refs` 及 edit re-risk result。所有独立 supplied verified list 仅作 exact-equality assertion，existing snapshot evidence 也必须完全一致；失败在 snapshot/decision/status 写入前以统一 `approval_not_executable` 外部语义回滚。
- **证据**：Phase 64.2 Plan 04；commits `3b285cf`、`e708c0e`；`src/approvals/service.py`、`tests/approvals/test_phase64_2_evidence_validation.py`。
- **验证**：Task 1 最终精确门禁 `81 passed, 1 warning`；Task 2 精确门禁 `80 passed, 1 warning`；两条 scoped Ruff 均为 `All checks passed!`。负向矩阵覆盖 forged ID/hash/document+chunk version、missing/extra/mixed verified、legacy ambiguous、cross-tenant、request/cross-scope，并断言 approval-owned row count 与旧 revision 可执行状态不变。
- **剩余风险**：🟡 Phase 64.2 Plan 09 仍需以 architecture/ownership guard 防止 caller-local evidence projector 或 verified fallback 回流；本 plan 未改变 API schema、数据库 schema 或外部 effect 边界。

## 2026-08-05 — Phase 64.2 Plan 05 CWC status-blind verified-fact 提升边界 ✅已修复验证

- **子系统**：记忆 / Case Working Context / 工具与 RAG 结果权威投影。
- **问题现象 / 根因**：`case_working_context_lifecycle._project_verified_facts` 原先只取非空 `summary/prompt_summary/tool_summary` 就构造 `verified_facts`，不检查 transport status、authority、completeness、scope、freshness 或 authoritative ref；policy refs 又降格为本地 `doc_id/chunk_id/version` triple。失败、拒绝、partial、stale、contextual-only、unknown 或 summary-only 结果因此可能被洗成 verified fact，且 CWC 无法保留完整 canonical evidence identity。
- **影响**：CWC 与后续 reviewed case-memory 候选可能把无权威观察误当当前业务事实/政策证据；跨 tenant/scope 失败细节还可能经 active payload 暴露，破坏 D-01..D-04 与 no-existence-leak 边界。
- **处理状态**：✅ 新增唯一 `FactPromotionCandidateV1` / `FactPromotionResultV1` owner。只有 `business_fact` 或 `policy_evidence` 在 `success + complete + valid scope + valid freshness + valid full ref` 时可 promote；policy 固定 exact `scope_type="tenant_policy"`、`scope_id=str(tenant_id)` 并验证完整 canonical identity。`contextual_only` 永远 `observe/contextual_only_non_authoritative`，`unknown` 永远 `reject/unknown_authority`；所有命名负状态、legacy/compatibility、invalid/missing ref 与 summary-only 均进入 typed observation。CWC verified fact 保存 authority/status/reason/time 与完整 `BusinessFactRefV1[]` / `EvidenceRefV1[]`，policy_refs 直接使用 canonical `EvidenceRefV1`，不再存在 reduced shape。
- **证据**：Phase 64.2 Plan 05；commits `f24f313`、`2719a8b`、`57adcbe`、`471e8fc`、`d9a1930`；`src/memory/fact_promotion.py`、`src/memory/case_working_context_schemas.py`、`src/memory/case_working_context_lifecycle.py`、`tests/agent/test_case_working_context_lifecycle.py`。non-promoted observation 沿用既有 `case_working_contexts.evidence_refs_json` 物理列保存，但 runtime/hydration 使用 `CaseWorkingContextObservationV1`，未新增 competing ref schema；active payload 会移除 internal mismatch reason，只保留统一外部原因。
- **验证**：计划精确聚合 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py tests/memory/test_case_working_context_service.py -q --tb=short` → `65 passed, 1 warning`；Task 1 / Task 2 两条 scoped Ruff 与直接 fixture Ruff 均通过。矩阵覆盖 12 个禁止状态、contextual/unknown、summary-only、compatibility-only、freshness、forged/cross-scope、canonical round-trip、混合批次独立处理、source-set 去重与持久化/hydration。
- **剩余风险**：🟡 Plan 07 仍必须保证 CWC rejected/observed material 不进入 CaseMemory content/caveat/provenance 任一字段；Plan 09 仍需 architecture guard 防止 summary-first projector、reduced policy ref 或本地 promotion owner 回流。现有物理列名 `evidence_refs_json` 是 Phase 22 storage compatibility，不表示 observation 获得 evidence authority。

## 2026-08-05 — Phase 64.2 Plan 06 production evidence snapshot 与 exact replay 边界 ✅已修复验证

- **子系统**：RAG / 工具调用事件 / immutable evidence retention / Replay V3。
- **问题现象 / 根因**：production `investigate -> emit_event -> emit_decision_event -> ReplayService.append_event` 原先没有传递 typed canonical evidence，append 边界仍暴露 raw `evidence_refs_json`，也没有在 event transaction 内构造完整 snapshot 与 normalized retention dependency；replay 因而缺少 exact immutable version、scope/hash/locator 绑定。实现收尾又核实 ORM 与尚未发布的 migration 025 生命周期 check 漏掉锁定契约要求的 `archived`，使归档状态无法真实持久化和回放。
- **影响**：历史 run 可能只能依赖可变 current head 或歧义 legacy alias，无法证明原始政策内容；伪造、混合或跨 scope ref 可能越过新写边界；保留期内 purge 缺少依赖阻断；归档证据虽在 API vocabulary 中存在，却会被数据库约束拒绝。
- **处理状态**：✅ 新写链只接受 `list[EvidenceRefV1]` 的 `canonical_evidence_refs` 并保持对象逐层不变；`append_event` 成为唯一 snapshot builder，通过 `EvidenceVersionRepository.resolve_exact` 在可信 tenant 与 exact `tenant_policy` scope 下重算完整 identity/scope/version/hash/locator，原子写入 snapshot 与 `EvidenceSnapshotDependency`，raw/reduced/forged/mixed/cross-scope 输入零写入。Replay 仅从 exact immutable rows 恢复原始 retained content/hash/locator，并投影 current/superseded/corrected/archived/expired/tombstoned；旧 JSON 只允许由已持久化 event-id 的显式只读 adapter 解析，歧义或缺失保持 `legacy_unresolved`。ORM 与 migration 025 的既有生命周期 check 已最小扩充 `archived`，未新增 archive service/API。
- **证据**：Phase 64.2 Plan 06；commits `cedf10d`、`ac17f0a`、`f1dffc3`、`b08578b`、`a6ea724`、`5f30b96`；`src/agent/nodes/investigate.py`、`src/agent/events.py`、`src/replay/decision_events.py`、`src/replay/schemas.py`、`src/replay/service.py`、`src/api/routers/traces.py`、`src/db/models.py`、`src/db/migrations/versions/025_phase64_2_immutable_evidence.py`。
- **验证**：Task 1 精确门禁 `132 passed, 1 warning`；Task 2 精确门禁 `42 passed, 1 warning`；归档 ORM/migration/replay 偏差门禁 `3 passed, 4 warnings`；最终两任务联合回归 `171 passed, 1 warning`；计划相关 Ruff 全部通过。依赖 FK 在 retention 内拒绝删除，伪造 snapshot 的 owner API 返回无标识符泄漏的 generic 404。
- **剩余风险**：🟡 pre-Phase-64.2 `evidence_refs_json` 仍作为显式 read-only compatibility surface 保留；无法唯一解析的历史行只返回 `legacy_unresolved` 且不提供 verified content。Plan 09 仍需用跨系统 ownership/static guard 防止 raw new-write input、mutable-head replay 或 caller-local snapshot builder 回流。

## 2026-08-05 — Phase 64.2 Plan 07 reviewed CaseMemory provenance 与 unresolved authority 边界 ✅已修复验证

- **子系统**：记忆 / reviewed CaseMemory / CWC provenance / review API。
- **问题现象 / 根因**：CaseMemory 原先只保存 summary、reduced policy refs、source ref 与候选 hash，无法逐 source 证明原始 `business_fact|policy_evidence` authority/status，也没有把 contextual-only memory authority、CWC revision、完整 canonical refs、reviewer provenance 与 correction/supersession lineage 绑定为一个可验证 envelope。历史行若缺失这些事实，旧路径仍可能进入 pending/review/retrieval/dedupe，存在把“无法证明”静默升级成已解析权威的风险。
- **影响**：rejected/observed CWC 内容可能经 summary-first projection 混入 reviewed memory；review 动作可能覆盖或抬升原始 source authority；伪造、跨 tenant 或不完整 legacy 行可能参与 authoritative matching 并从 API 暴露内部 mismatch/source 信息；单值 lineage 无法表达 survivor-to-many dedupe 关系。
- **处理状态**：✅ 新增冻结的 `CaseMemorySourceAuthorityV1`、resolved `CaseMemoryProvenanceV1` 与互不冒充的 `LegacyUnresolvedCaseMemoryProvenanceV1`。closed-case projection 只消费 Plan 05 promoted facts并复制原始 source authority/status、完整 `BusinessFactRefV1`/canonical `EvidenceRefV1`；memory authority 永远为 `contextual_only`。migration 027 对所有无法从 pre-027 字段证明完整 provenance 的历史行保守标记 `legacy_unresolved`，不伪造 scope/authority/reviewer/identity；新增 tenant-safe restrictive direct lineage FK 和 normalized survivor-to-many lineage table。中央 validator 绑定 tenant/scope/source/run/CWC/hash/profile/ref/review/lineage，unresolved 或 forged 行不能进入 insert promotion、pending、approve/reject/delete/forget、published retrieval 或 idempotent winner matching。review 只增补 decision/reviewer/time/reason 并提升 lifecycle version，原 source authorities 与 contextual-only memory authority 保持不变。
- **证据**：Phase 64.2 Plan 07；commits `8cfe521`、`78b9d3f`、`a3031f3`、`bcac7cd`；`src/memory/schemas.py`、`src/memory/case_precedent.py`、`src/memory/case_memory.py`、`src/db/models.py`、`src/db/migrations/versions/027_phase64_2_memory_provenance.py`、`src/api/routers/memory.py`、`tests/memory/test_case_memory_provenance.py`。
- **验证**：Task 1 精确门禁 `52 passed, 7 warnings`；Task 2 精确门禁 `37 passed, 1 warning`；额外 retrieval 回归 `14 passed, 1 warning`；最终联合回归 `64 passed, 7 warnings`；全部计划相关 Ruff 与 `git diff --check` 通过。API 对 resolved row 只返回 bounded scope/source/ref/identity/review/lineage，对 valid unresolved detail 仅返回 resolution status 与稳定 safe reasons，跨 tenant/forged/unresolved action 统一 generic 404。
- **剩余风险**：🟡 Plan 08 仍负责 `expected_lifecycle_version` CAS、expiry、durable full-key claim 与并发 survivor lifecycle；本 plan 只预留请求/响应字段，没有提前实现 CAS。Plan 09 仍需锁定唯一 provenance/identity owner、禁止 reduced ref/status-blind projector 回流，并验证所有生产调用方不绕过中央 resolved validator。

## 2026-08-05 — Phase 64.2 Plan 08 CaseMemory exact identity 与 terminal lifecycle ✅已修复验证

- **子系统**：记忆 / reviewed CaseMemory identity、review lifecycle、correction lineage、tombstone。
- **问题现象 / 根因**：CaseMemory 原先用 active row 的 content/source 查询做去重，终态后没有独立持久 identity authority；review/delete/forget 是 read-then-mutate，没有 required lifecycle CAS；pending expiry、claim、lineage 与 event 未形成同一事务。不同 source 的相同 content 会被错误合并，terminal row 也可能在 active 索引释放后被延迟 writer 复活；并发 identical correction retry 会让一个请求成功、另一个误报 conflict。
- **影响**：exact retry、source-distinct candidate、approve/reject/expiry、delete/forget、correction 与 delayed submit 在并发下可能产生多 owner、错误 winner、重复 event、丢失 lineage 或 no-resurrection 失效，审计者无法证明唯一终态。
- **处理状态**：✅ 已修复验证。Migration 028 建立七段 full-key durable claim，并按 oldest `created_at/id` 选择 survivor、为四行 duplicate group 写 deterministic survivor-to-many lineage；unresolved 永不 claim，downgrade 在有 claim/lineage 时 fail closed。写入先获得 exact unique claim；只有 active exact owner 可作为幂等结果，terminal claim 永不释放且冲突不返回 winner。review/expiry/delete/forget/correction 在 claim row lock 下同步提升 row/claim version并写 event/tombstone/lineage；API 要求 case lifecycle version并统一输出 generic 409。identical review/correction retry仅在 persisted payload、reviewer、lineage、provenance与原 event 完全匹配时复用。
- **证据**：Phase 64.2 Plan 08；commits `fe4e12c`、`073d634`、`6e431ea`、`5494b66`、`b3c6125`、`b527c72`；`src/db/migrations/versions/028_phase64_2_memory_lifecycle.py`、`src/db/models.py`、`src/memory/case_memory.py`、`src/memory/schemas.py`、`src/api/routers/memory.py`、`tests/memory/test_case_memory_lifecycle.py`、`tests/memory/test_case_memory_concurrency.py`。
- **验证**：Task 1/2/3 精确 PostgreSQL 门禁分别 `19 passed`、`60 passed`、`28 passed`，scoped Ruff 全绿；真实双会话 barrier matrix 单独为 `11 passed`，覆盖 exact submit、source-distinct、review retry、approve/reject、review/expiry、rejected/expired/deleted/tombstoned delayed submit、correction/duplicate submit 与 correction retry。
- **剩余风险**：🟡 本 plan 只收敛 CaseMemory，不建立 Phase 68 的通用 lifecycle registry。`source_identity_hash_for_tombstone()` 默认仍保留 legacy profile 供旧调用者使用；新 v2 writer 必须显式传其已计算的 source identity，后续统一迁移属于 Phase 68，而不是在本 plan 静默改变全局 tombstone 兼容语义。Plan 09 仍需最终 ownership/static guard 与 phase 级 negative matrix。

## 2026-08-06 — Phase 64.2 Plan 09 Memory provenance/lifecycle 完整性门禁闭环（`phase64.2-memory-integrity:implemented`）✅已修复验证

- **问题现象 / 根因**：memory identity、CWC promotion、reviewed provenance 与 terminal lifecycle 虽由 Plans 03/05/07/08 分别收敛，但此前没有统一证明 rejected observation 不进入 reviewed content、各 source authority 不被 review 抬升、以及 terminal full-key claim 不会因延迟 writer 复活。
- **影响**：局部回归可能漏掉跨 owner 的 status-blind promotion、caller-local hash、unresolved authority upgrade、lineage 丢失或 terminal resurrection。
- **处理状态**：✅已修复验证。Phase `64.2-09` 通过真实 promotion→review→approve→delete lifecycle、全禁止状态矩阵与 repository-wide ownership guard，锁定 single identity/provenance owner、contextual-only memory authority、durable terminal claims 与 CAS/no-resurrection。
- **证据**：`tests/integration/test_phase64_2_integrity_matrix.py`、`tests/architecture/test_evidence_memory_integrity_boundaries.py`；实现 owner 包括 `src/memory/identity.py`、`src/memory/fact_promotion.py`、`src/memory/case_memory.py`、`src/memory/case_precedent.py`。
- **验证**：Plan 09 最终 13-file focused aggregate 为 `204 passed, 15 warnings`，memory provenance/identity architecture guards 包含在该绿色门禁；全仓 Ruff 与完整 suite 分别为 `All checks passed!`、`4455 passed, 4 skipped, 152 warnings in 1993.29s`。
- **剩余风险**：legacy risk 是 pre-027 行继续使用 `LegacyUnresolvedCaseMemoryProvenanceV1`，不能加入 authoritative matching；target/defer 为 Phase 68 通用 lifecycle registry 与 Phase 70 retrieval quality/PII governance，本 plan 不提前实现。

## 2026-08-06 — Phase 64.2 Plan 09 working-state canonical evidence binding 丢失 ✅已修复验证

- **子系统**：RAG / agent working-state / immutable evidence identity。
- **问题现象 / 根因**：`src/agent/working_state.py` 的 `EVIDENCE_REF_KEYS` 停留在 Phase 64.2 前的 11 字段 allowlist；完整 canonical `EvidenceRefV1` 经 working-state 投影后会静默丢失 `scope_type`、`scope_id`、document/chunk version id 与 version 六个 exact binding 字段，退化为无法 exact-resolve 的 reduced/legacy shape。
- **影响**：working-state 的 prompt-safe verified refs 虽不泄露 raw provenance，却不能继续证明 immutable tenant/scope/document/chunk binding；后续依赖该投影的 claim/action/replay 边界可能把 canonical authority 降格。
- **处理状态**：✅ 已修复验证。先用 owner-minted 完整 canonical ref 新增 RED，稳定证明六字段被删；随后只把这六个 `EvidenceRefV1` identity/version 字段加入既有 allowlist。未加入 query、risk、ranking、rerank/provider 或 raw provenance diagnostics，也未增加 raw dict fallback。
- **证据**：Phase 64.2 Plan 09 remediation B；`src/agent/working_state.py`、`tests/agent/test_working_state.py` 及五个 EvidenceRef shape/diagnostic 测试；RED 为 `1 failed`，B 六文件为 `76 passed, 1 warning`，architecture/integration guard 为 `16 passed, 8 warnings`，全局 lastfailed 从 29 收敛到 22。
- **剩余风险**：当前无已知 canonical working-state binding 缺口；最终 13-file focused aggregate、全仓 Ruff 与完整 suite 均绿色。`score` 仍是既有 `EvidenceRefV1` display 字段，但 approval authority projection 会剥离它；query/risk/rerank diagnostics 继续只存在于各自 bounded container。Phase 70 可统一评估 display score 是否最终从 ref schema 拆出。

## 2026-08-06 — Phase 64.2 Review WR-01 evidence cutover 失败门禁被错误盖章 ✅已修复验证

- **子系统**：RAG ingestion / immutable evidence migration cutover。
- **问题现象 / 根因**：migration 026 在 final reconciliation 检出 unresolved current heads 后只写 quarantine/audit 并正常返回，Alembic 因此仍会把 026 记录为已应用；后续 migration 可越过本应阻断的 canonical-read gate，且正常重试不能再次执行 026。
- **影响**：canonical reads 尚未启用、legacy head 仍无法证明 exact immutable binding 时，数据库 revision 却可能继续推进到 027/028，部署状态与真实证据可用性分裂。
- **处理状态**：✅ 已修复验证。unresolved 分支现在先通过 Alembic autocommit block 持久化 backfill/quarantine/audit preflight 结果，再抛出稳定的 retryable `RuntimeError`；因此 version table 保持 025。修复 legacy head 后可正常重跑 026，并仅在零 unresolved 时启用 canonical reads 与盖章 026。
- **证据**：Phase 64.2 REVIEW WR-01；`src/db/migrations/versions/026_phase64_2_evidence_cutover.py`；`tests/integration/test_phase64_2_integrity_matrix.py::test_unresolved_cutover_remains_at_025_and_is_retryable`；定向 PostgreSQL 回归 `1 passed`，scoped Ruff 通过。
- **剩余风险**：无当前已知缺口；运维仍必须按 025 → dual-write health → 026 的 staged 顺序执行，且 unresolved audit 中的具体 legacy head 需要在再次运行 migration 前修复。

## 2026-08-06 — Phase 64.2 Review WR-02 verified-context 绕过 exact immutable identity ✅已修复验证

- **子系统**：RAG verified package / prompt context builder / immutable evidence identity。
- **问题现象 / 根因**：`PolicyKnowledgeService.build_verified_context()` 与独立 `ContextBuilder` 都调用 mutable logical-key details/compatibility content lookup；即使输入携带完整 canonical shape，也没有比较 persisted `evidence_id`、document/chunk version IDs、scope 与版本字段。
- **影响**：调用方可保留真实 current `doc_key/chunk_id/text_hash`，但重新生成一组不存在的 immutable IDs 与自洽 `evidence_id`，让 unsupported policy content 进入非审批回答的 verified prompt/verifier surfaces。
- **处理状态**：✅ 已修复验证。package owner 先调用 `validate_current_evidence()` 做 exact current-row comparison，并把同一个 typed validation result 通过私有参数传给 `ContextBuilder`，避免二次 mutable lookup 与两次校验之间的 current-head race；builder 独立使用时也优先 exact validator，validator 抛错或拒绝时不回落 compatibility content。只有不具备 exact seam 的历史 test double 才保留既有兼容分支。
- **证据**：Phase 64.2 REVIEW WR-02；`src/knowledge/service.py`、`src/agent/rag_context/builder.py`；真实 PostgreSQL forged-ID 负向 `tests/knowledge/test_evidence_cutover.py::test_verified_context_rejects_forged_immutable_ids_for_real_current_logical_head`；builder no-fallback 测试与 package/status 回归合计 `25 passed`，scoped Ruff 通过。
- **剩余风险**：🟡 compatibility 分支仍服务没有 `validate_current_evidence` seam 的隔离 test doubles；生产 `PolicyKnowledgeService` 始终实现 exact seam。architecture guard 后续应继续禁止 production owner 绕过该方法。

## 2026-08-06 — Phase 64.2 Review WR-03 CWC policy authority 只验 shape 未验 retained row ✅已修复验证

- **子系统**：记忆 / Case Working Context promotion / RAG immutable evidence provenance。
- **问题现象 / 根因**：terminal CWC projection 只用 Pydantic、tenant/scope 字符串与本地 canonical shape 检查 policy refs，随后把未显式声明的 `reference_validation` 默认成 `valid`；没有在可信 tenant 下解析 retained immutable row。
- **影响**：随机生成但结构自洽的 document/chunk version IDs 可被提升为 `policy_evidence` verified fact，并继续进入 reviewed CaseMemory provenance，形成不存在的政策 authority。
- **处理状态**：✅ 已修复验证。async lifecycle adapter 现在注入单 ref exact resolver，生产默认调用 `EvidenceVersionRepository(session).resolve_immutable_evidence(...)`，固定可信 `tenant_id`、`scope_type="tenant_policy"`、`scope_id=str(tenant_id)` 并比较返回 identity。每个 tool result 的全部 policy refs 都成功解析后，sync projection 才收到私有 validated-ID 集；未提供验证集的纯 projection 默认 fail-closed，business-fact promotion 不受影响。missing/forged/cross-tenant/cross-scope 或 resolver 异常只保留 observation/rejection，不进入 `verified_facts`/`policy_refs`。
- **证据**：Phase 64.2 REVIEW WR-03；`src/memory/case_working_context_lifecycle.py`；`tests/agent/test_case_working_context_lifecycle.py::test_terminal_policy_promotion_requires_explicit_exact_resolver_success` 与 `::test_terminal_policy_promotion_rejects_canonical_shaped_nonexistent_ids`；memory/architecture/integration 定向回归 `79 passed`，scoped Ruff 通过。
- **剩余风险**：🟡 business-fact refs 仍按其自身 service contract、tenant/freshness 字段验证；本条只收敛 policy evidence retained-row authority。后续 architecture guard 应继续锁定 production adapter 的 exact resolver 默认值与纯 projection 的无验证 fail-closed 行为。

## 2026-08-06 — Phase 64.2 Review iteration 2 authoritative ref 混合列表未 fail-closed ✅已修复验证

- **子系统**：记忆 / Case Working Context promotion / 工具与 RAG authoritative refs。
- **问题现象 / 根因**：`_parse_business_refs()` 与 `_parse_policy_refs()` 共用 `_iter_mappings()`；该 helper 会从 list/tuple 中静默过滤 scalar 等非 mapping 成员。含一条有效 ref 与一条 malformed member 的 authoritative-ref 集因此只保留有效项，`refs_invalid` 仍为 false，可继续进入 business promotion，或先通过 policy exact resolver 再 promotion。
- **影响**：不完整或被污染的原始 authority 集可能被当成完整有效集合，进入 CWC `verified_facts`；policy ref 还可能进入 `policy_refs` 并继续流向 reviewed CaseMemory provenance，违反 complete-per-result 与 fail-closed 契约。
- **处理状态**：✅ 已修复验证。两个 ref parser 现先用 `_raw_ref_members()` 检查原始容器：`None` 表示无 refs，单 mapping 与 list/tuple 保持兼容；unexpected container、任一非 mapping member 或 typed model validation 失败都会设置 `refs_invalid=True`。policy 集只有完整解析成功才调用 exact resolver；混合 business/policy 列表均只保留 non-promoted observation，不进入 promoted facts/provenance。
- **证据**：Phase 64.2 REVIEW iteration 2 WR-01；`src/memory/case_working_context_lifecycle.py`；`tests/agent/test_case_working_context_lifecycle.py::test_terminal_projection_rejects_mixed_malformed_business_ref_list`、`::test_terminal_projection_rejects_mixed_malformed_policy_ref_list_before_exact_resolution`。
- **验证**：两条新增负向与既有 exact resolver 正/负向定向回归通过；生命周期测试文件与 scoped Ruff 通过。
- **剩余风险**：当前无已知缺口；后续必须保留原始 ref 容器成员完整性检查，不能在 typed validation 前用通用 mapping filter 丢弃非法成员。

## 2026-08-11 — Phase 64.4 Plan 05 — policy document 身份被 chunk 边界反向污染 ✅已修复验证

- **子系统**：RAG ingestion / policy chunking / immutable evidence identity / replay。
- **问题现象 / 根因**：当前 ingestion 先按字符切块，再用 `_document_citation_text(chunks)` 拼接 chunk body 写入 `PolicyDocument.content` 并参与 policy fingerprint。由于 chunk overlap 和切分边界会改变拼接结果，同一 authoritative source 在 character/token 配置间可能被误判为不同 document content/version；同时最终 embedding envelope 在 chunk 之后才追加，实际 provider 输入不受 chunk budget 约束。
- **影响**：Phase 64.4 若只替换 chunk 算法，同一源文档可能因 rollout/config 而漂移 immutable document identity，进而错误新建或错误拒绝 Phase 64.2 evidence binding；历史 replay 与 current projection 的职责也会混在一起。
- **处理状态**：✅ 已实现 `canonical_document_content.v2`：new writes 在 chunking 前从按 `block_index` 排序的 authoritative `ParsedBlock` snapshot 生成 citation content、content hash 与 blocks hash；duplicate order/source block fail closed。immutable document compatibility 比较 tenant/source checksum/schema/block content+provenance，忽略 chunk config/corpus；chunk compatibility 独立比较 citation/search/final-input hash/count/config/provenance，忽略 corpus。相同 source 的 character/token 写入复用同一个 document-version row，配置不兼容才追加 chunk version，兼容配置再次复用；legacy 四个 canonical 字段保持 SQL NULL 且 replay 可读，不回写历史。
- **证据**：Phase 64.4 Plan 05 Task 2；`src/repositories/document_block_repo.py`、`src/rag/ingestion.py`、`src/repositories/evidence_version_repo.py`、`tests/knowledge/test_document_source_identity.py`、`tests/test_ingestion.py`、`tests/replay/test_production_evidence_binding.py`；真实 PostgreSQL source/config versioning test `7 passed, 3 warnings`，Task 2 replay gate `14 passed, 3 warnings`，ingestion audit 回归 `41 passed, 1 warning`。
- **剩余风险**：Plan 06 仍负责 active-scope routing 与 candidate shared-head isolation，Plan 07 负责 resumable reindex；Plan 09/10 仍需完成 A/B selection 与真实 provider-backed activation。本 plan 未提前实现这些行为。

## 2026-08-11 — Phase 64.4 Plan 01 — DashScope offline tokenizer 映射缺少厂商保证 🟡有意妥协

- **子系统**：RAG embedding tokenizer / offline token counting / provider parity。
- **问题现象 / 根因**：Alibaba Cloud 官方文档确认 `text-embedding-v4` 的 1024 默认维度、单条 8192 token、每请求最多 10 条和 request-level `prompt_tokens`，但没有发布或保证可离线使用的精确 tokenizer revision。Phase 64.4 research 的 10 组安全合成 probe 证明 Qwen 官方 `Qwen3-Embedding-0.6B` tokenizer 在固定 revision、包含 EOS 时与当前 provider usage 10/10 精确一致；该结论是实证映射，不是厂商兼容承诺。
- **影响**：provider 或 tokenizer 资产漂移时，若仅依赖模型名猜测或 ambient library 行为，new ingestion/reindex 可能低估 final input、错误复用配置身份或把不可验证状态当成通过。
- **处理状态**：🟡 有意妥协。Plan 01 已 vendor revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` 的 11,423,705-byte asset（SHA-256 `def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a`），精确锁定 `tokenizers==0.23.1`、EOS、8192/10、512/384/48 和 canonical fingerprint；missing/hash/runtime/count/nondeterminism 只返回 allowlisted typed failure，没有下载、字符回退或 provider/persistence side effect。contract 与 SOURCE 明示 `empirically_provider_parity_approved_not_vendor_guaranteed`。
- **证据**：Phase 64.4 Plan 01 commits `c2bf8ccc`、`2bde39bd`；`src/rag/assets/embedding_tokenizer.v1.json:1`、`src/rag/embedding_tokenizer.py:18`、`src/rag/embedding_tokenizer.py:119`、`src/rag/embedding_tokenizer.py:155`、`tests/rag/test_embedding_tokenizer.py`；最终 Plan 01 gate 为 `make lint` 通过、tokenizer tests `21 passed`、`uv lock --check` 通过。
- **剩余风险 / 继续入口**：Plan 03 必须用同一 authoritative final-input seam 产生新的 create-only provider parity artifact；`unavailable` / `quarantined` 均不得授权 new token-aware writes 或 cutover。Plan 09/10 的 selection/activation 还必须绑定 fresh parity hash；在这些 gate 完成前不能把本条升级为“厂商保证”或“端到端已修复”。

## 2026-08-11 — Phase 64.4 Plan 02 — 字符 chunk budget 与 provider final input 分离 ⚠️修复但验证有缺口

- **子系统**：RAG policy chunking / embedding input assembly / parser provenance。
- **问题现象 / 根因**：既有 `chunk_blocks` 只按 `max_chars/target_chars/overlap_chars` 控制 citation body；title、section 与 `source_block_id` envelope 由 ingestion 在 chunk 完成后追加，因而 chunker 无法证明实际 provider string 不溢出，table header、oversized row 与 Unicode/no-progress 分支也没有共同的 token budget owner。
- **影响**：中英/混合/OCR/table 内容可能因字符-token 比例与 post-count decoration 产生不一致边界；极端输入可能超过 provider 限制，或在拆分时丢失 row/header/source provenance。citation content、retrieval-only search text 与 provider input 若由调用方各自重建，还会形成新的契约漂移点。
- **处理状态**：⚠️ 已完成 assembler 本体与 Task 2 adversarial 修复。新增唯一 `PolicyEmbeddingInputAssembler`，每次结构分组、表格 row/header 重复、sentence/clause/whitespace 与最终 tokenizer-window 分割都用 Plan 01 `EmbeddingTokenCounter` 对完整 envelope 计数；最终 frozen DTO 同时返回 citation/search/exact provider string、hash/count/config fingerprint 与深冻结 provenance。Task 2 RED 进一步发现 structural piece packing 会在同一 source block 内插入额外换行，现已用显式 source joiner 区分 block 边界与 block 内 split，中文/英文/混合/OCR-like/combining/emoji/URL/number 与 oversized table cell 均可按 `primary_content` 重组原文。空输入有界返回，envelope-dominant/no-progress/overflow/tokenizer failure fail closed；没有第二套 tokenizer 或字符预算 fallback。
- **证据**：Phase 64.4 Plan 02 Tasks 1-2；commits `890eed62`（Task 1）与 Task 2 原子提交；`src/rag/policy_embedding_input.py`、`src/rag/chunker.py`、`tests/rag/test_token_aware_chunker.py`、`tests/rag/test_block_chunker.py`、`tests/test_chunker.py`；Task 1 Wave-0/Green 为 3 个预期 collection error → `23 passed, 1 warning`，Task 2 adversarial RED 为 8 个真实 separator invariant failures 加 1 个测试 zip 边界错误，修复后 Task 2 精确门禁为 `27 passed, 1 warning`；全仓 `make lint` 与 `git diff --check` 通过。

## 2026-08-11 — Phase 64.4 Plan 03 Task 1 — embedding provider usage 被丢弃且 batch 总量无可信分配语义 ✅已修复验证

- **子系统**：RAG embedding provider / token accounting / evaluation provenance。
- **问题现象 / 根因**：原 `EmbeddingService` 只从 OpenAI-compatible response 提取 vectors，直接丢弃 request-level `usage.prompt_tokens/total_tokens`；provider 又不提供 per-input usage 数组，因此后续若把 batch 总量平均或按比例摊给输入，会制造不存在的 per-input 事实。
- **影响**：Phase 64.3/64.4 无法保留真实 provider token 成本；parity 与 A/B 若误把 aggregate usage 当单条 usage，会错误授权 tokenizer 映射或选择结论。
- **处理状态**：✅ 已增加冻结的 request usage 与 batch result DTO，以及 `embed_documents_with_usage`；仅按 provider request 记录 usage，只有每个 request 都报告完整 usage 时才汇总 totals，缺失/非法 usage 统一为 `unavailable`，从不生成 per-input 分配。既有 `embed_documents`/`embed_query` vector-only list 契约、最多十条 batching、index 顺序、dimensions 参数和 retry 行为保留。
- **证据**：Phase 64.4 Plan 03 Task 1；`src/rag/embedder.py`、`tests/rag/test_embedding_usage.py`、`tests/test_embedder.py`；Wave-0 RED 为缺少 `EmbeddingBatchResultV1` 的预期 collection error，完成后完整 `make lint` 通过，精确 gate 为 `7 passed, 1 warning`。
- **剩余风险**：Task 2 仍需把这些 request-level usage 接入 create-only parity artifact，并以 10 个 single request 加一个 10-input aggregate request 做精确 freshness/identity gate；Plan 04 继续负责所有 live final strings 收敛到唯一 assembler。

## 2026-08-11 — Phase 64.4 Plan 03 Task 2 — tokenizer parity 缺少不可变身份与 freshness 授权边界 ✅已修复验证

- **子系统**：RAG embedding tokenizer parity / selection authorization / provider evidence。
- **问题现象 / 根因**：Plan 01 只有离线 fixture 与一次 planning 期实证，原仓库没有 create-only run identity、精确 final-input content hash、freshness、provider/model/config 复核或 `passed|quarantined|unavailable` 的严格 artifact；旧实证若被复制、覆盖或跨 fingerprint 使用，会把陈旧/变异 provider 事实错误带入后续 selection。
- **影响**：缺少该边界时，Plan 09/10 无法证明选择消费的是当前 pinned tokenizer、当前 provider/model 和 assembler exact final strings，也无法区分 usage 缺失与真正 count mismatch。
- **处理状态**：✅ 已定义严格 `embedding_tokenizer_parity.v1`、UUID/timestamp/region/config/model/fixture/content identity、10 个 single request 加一个 10-input aggregate 的 prompt-token exact gate，以及 fingerprint/run-id create-only 原子 writer。`unavailable`、`quarantined` 均不能通过 `require_fresh_provider_parity`；所有 report/failure 字段只允许安全 label/count/hash/code，不含文本、key、URL、raw response、path 或 exception。
- **证据**：Phase 64.4 Plan 03 Task 2；`src/rag/tokenizer_parity.py`、`scripts/check_embedding_tokenizer_parity.py`、`evaluation/golden/embedding_tokenizer_parity_probes.v1.json`、`evaluation/reports/rag_embedding_tokenizer/v1/README.md`、`tests/rag/test_tokenizer_parity.py`；Wave-0 RED 为缺少 module 的预期 collection error，完成后完整 `make lint` 与精确 gate `11 passed, 1 warning` 通过。显式清空 credential 的 CLI 安全探针写出真实 `unavailable/provider_credentials_unavailable` artifact 并以 exit 2 结束，没有 provider 请求或成功声明。
- **剩余风险**：本 plan 没有伪造或宣称 live `passed`；Plan 04 仍需完成 production/dry-run/golden/parity/A-B 的 assembler seam 静态收敛，Plan 10 必须在真实 provider 与 selected configuration 上产生 fresh passed artifact 后才能激活。
- **剩余风险 / 继续入口**：Plan 04 前 production ingestion/dry-run 尚未消费该 DTO，所以当前生产 character path 仍保持不变；必须在 Plan 04 convergence gate 证明 embedder 直接消费 `embedding_input` 且提交/持久化前复算一致，才能将本条升级为端到端已修复。Plan 03 仍负责 fresh provider parity，而 persistence/reindex/cutover 由后续 Plans 05-10 负责。

## 2026-08-11 — Phase 64.4 Plan 04 Task 1 — production/dry-run final-input owner 分叉 ✅已修复验证

- **子系统**：RAG ingestion / embedding-input assembly / CLI dry-run。
- **问题现象 / 根因**：production 原先调用 `chunk_blocks` 后由 ingestion 本地拼接 title/section/source envelope，dry-run 则直接调用独立的 `chunk_markdown`；两条路径既不共享 parsed-block assembly owner，也没有把实际 provider 字符串、Plan 01 token count、input hash 与配置身份绑定在同一 DTO 中。
- **影响**：token-aware 模式若直接替换 shared `policy_chunks` 会在 Plans 05-06 corpus isolation 前制造 character/token 混合语料；继续本地重建又可能在 count 后追加内容。dry-run 也无法证明真实 production parser/provenance 与 final-input 契约。
- **处理状态**：✅ 已修复验证。`IngestionService` 默认显式选择 `CharacterCompatibilityAssembler`，保持 pre-Plan04 provider bytes；只有 `IngestionAssemblyMode.TOKEN_AWARE` 才选择 `PolicyEmbeddingInputAssembler`，且 assembly 失败不会回退。两者返回同一 `PolicyEmbeddingInputV1`，character incumbent 用 Plan 01 counter 记录真实 final-input token count/hash 与 `character_compatibility.v1` 配置 fingerprint。embedder 只接收 DTO `embedding_input`，projection 只消费 DTO citation/search/provenance；Plan 05 前 count/hash/config 仍只存在内存，不写入任何新列。CLI dry-run 改走 production parser + token assembler，并在构造 provider/DB client 前结束。
- **证据**：Phase 64.4 Plan 04 Task 1；`src/rag/ingestion.py`、`scripts/ingest_policies.py`、`tests/test_ingestion.py`；Wave-0 RED 为缺少新 assembly mode/compatibility owner 的预期 collection error，`make format` 与完整 `make lint` 通过，精确 gate 为 `39 passed, 1 warning`。
- **剩余风险 / 继续入口**：Task 2 仍需把 golden/Phase64.3 evaluation seam 收敛到同一 parsed-block入口并加入 AST/rg guard；Plan 05 才能新增并持久化 token/config audit 字段，Plan 06 才能按 active corpus/config 路由普通 production token writes。当前普通生产保持 character-compatible 是有意且限时的 staging contract，不代表 token corpus 已激活。

## 2026-08-11 — Phase 64.4 Plan 04 Task 2 — golden 与 Phase64.3 evaluation 绕过统一 assembly seam ✅已修复验证

- **子系统**：RAG golden validation / retrieval parity evaluation / embedding-input assembly。
- **问题现象 / 根因**：golden seed validator 直接调用 `chunk_markdown`，没有复用 production parser、manifest 与 typed assembler；Phase64.3 parity runner 又在内部构造默认 character-compatible 的 `IngestionService`，即使外层脚本声明 token candidate，实际运行也无法把同一个 assembler 注入 ingestion。两处都会让验证对象与候选 production final input 分叉。
- **影响**：golden corpus identity、token A/B 与 provider input 可能来自不同 chunk owner；外层“token candidate”名称不能证明真实 ingestion bytes 已切到 token assembler，也会给后续 Plan09 selection 留下错误证据。
- **处理状态**：✅ 已修复验证。golden validator 现在按 production manifest 顺序经 parser registry 生成 `ParsedBlock`，再调用唯一 shared typed assembly entry；Phase64.3 parity 明确暴露 `PolicyInputAssembler` seam，默认运行 token candidate，只有显式命名的 `_character_baseline()` 可构造 `CharacterCompatibilityAssembler`。AST/static guards 禁止其他 production `chunk_markdown`/`chunk_blocks` 调用、第二套 budget split/envelope renderer 或未命名 compatibility owner。`src/rag/evaluation/retrieval_rounds.py` 不在 Plan04 原 `<files>` 清单，但内部隐藏的 `IngestionService` constructor 是完成“Expose same assembly seam to Phase64.3 evaluation”的必要缺口；本次按 Rule 2 仅增加 typed injection/default-token wiring，没有预做 Plan09 selection、报告或 retrieval algorithm 逻辑。
- **证据**：Phase 64.4 Plan 04 Task 2；`scripts/validate_golden_seeds.py`、`scripts/eval_rag_format_parity.py`、`src/rag/evaluation/retrieval_rounds.py`、`tests/eval/test_rag_format_parity_contract.py`、`tests/architecture/test_rag_chunking_boundaries.py`；Wave-0 为 `4 failed, 37 passed, 1 warning`，完成后精确 gate 为 `41 passed, 1 warning`，Phase64.3 isolation 回归为 `71 passed, 1 warning`，checked-in golden seed validation 为 `SEED VALIDATION PASSED`。
- **剩余风险 / 继续入口**：Plan 05 才能持久化 token/config audit 字段，Plan 06 才能切换 ordinary production；Plan 09 仍负责同次 A/B selection 与独立 corpus 的选择逻辑。本次没有新 schema/reindex/cutover 行为，character compatibility 仍只能作为显式 baseline 使用。

## 2026-08-11 — Phase 64.4 Plan 05 Task 1 — shared current projection 缺少 corpus visibility 边界 ✅已修复验证

- **子系统**：RAG corpus lifecycle / immutable evidence projection / migration bootstrap。
- **问题现象 / 根因**：既有 `policy_documents`、`document_blocks`、`policy_chunks` 只有单一 shared current head，没有 tenant-scoped corpus manifest、active rollout 或 append-only projection binding；直接写 token candidate 会与 character incumbent 混合，而直接新增 active filter 又会让 migration 前 legacy rows 失去可见性。
- **影响**：无法在不污染当前生产 head 的前提下构建候选；错误 bootstrap 还可能产生不可见、孤立、重复或跨租户绑定，并破坏历史 evidence/replay identity。
- **处理状态**：✅ 已新增 corpus manifest revision/version、tenant rollout、activation history 与 document/block/chunk projection binding schema；migration 030 为每个有 legacy document 的 tenant 创建且只创建一个 complete + active `character.v1` corpus，并以逐租户 before/after distinct counts、exact immutable document/chunk binding 和 cross-tenant constraints fail closed。manifest/history/projection bindings 由数据库 trigger 保持 append-only；token-dependent audit rows 出现后 downgrade 明确拒绝。corpus id 仅存在于 visibility projection，没有进入 immutable evidence/document/chunk identity。
- **证据**：Phase 64.4 Plan 05 Task 1；`src/db/migrations/versions/030_phase64_4_token_corpora.py`、`src/db/models.py`、`src/repositories/policy_corpus_repo.py`、`tests/knowledge/test_token_corpus_migration.py`、`tests/test_rag_migration.py`；真实 PostgreSQL/pgvector gate 为 `5 passed, 7 warnings`，完整 `make lint` 通过。
- **剩余风险 / 继续入口**：本 task 只提供 schema、bootstrap 与 read-only/bootstrap assertions；Plan 06 才能实现 active-scope production routing/candidate write isolation，Plan 07 才能实现 resumable reindex。不得提前把新 corpus projection 当成 ordinary write router。

## 2026-08-11 — Phase 64.4 Plan 06 Task 1 — current RAG 查询绕过 tenant active corpus pointer ✅已修复验证

- **子系统**：RAG current retrieval / canonical evidence / corpus visibility / immutable replay。
- **问题现象 / 根因**：migration 030 已建立 tenant rollout 与 document/block/chunk projection bindings，但 `PolicyChunkRepository`、`DocumentBlockRepository`、current canonical identity 和 evaluation current inspection 仍直接按 tenant 查询 shared current tables；inactive corpus row 可能进入 dense/sparse/fuzzy、canonical re-fetch、provenance 或 cleanup 视图。相反，历史 replay 应继续只按 stored immutable version ID 解析，不能受当前 pointer 影响。
- **影响**：candidate/inactive chunks 可能泄漏到生产检索，pointer 切换后 production caller 也无法保证只观察一个 generation；cross-tenant 或配置不兼容的 current row 可能被误绑定为当前 evidence。若把 pointer 反向加入历史 resolver，又会破坏 Phase 64.2 byte-exact replay。
- **处理状态**：✅ 已新增单一 `ActivePolicyCorpusScope` 和显式 `ExactPolicyCorpusScope`；所有已知 current `PolicyChunk`/`DocumentBlock` repository SQL 通过 tenant rollout、complete active corpus 和同一 corpus projection binding，current canonical identity 直接消费 active projection 指定的 exact immutable chunk version，并复核 corpus-free content/search/provenance/config compatibility。production 方法签名不接受 caller-supplied corpus；evaluation/reindex exact scope 必须显式命名。`resolve_immutable_evidence`、`resolve_exact` 与 legacy alias 仍只按 retained immutable ID/tenant/scope 解析，不读取 active pointer。
- **证据**：Phase 64.4 Plan 06 Task 1；`src/repositories/policy_corpus_scope.py`、`src/repositories/policy_chunk_repo.py`、`src/repositories/document_block_repo.py`、`src/repositories/evidence_version_repo.py`、`src/repositories/rag_evaluation_round_repo.py`、`tests/repositories/test_policy_chunk_repo.py`、`tests/knowledge/test_evidence_projection.py`、`tests/knowledge/test_retrieval.py`；RED 为缺失 scope owner 的 collection error，完成后完整 `make lint` 通过，Task 1 精确 gate 为 `34 passed, 1 warning`。
- **剩余风险 / 继续入口**：Task 2 仍须让 ordinary ingestion、search-text backfill、seed/reset/delete 按 active named config fail-closed，并扩展静态 guard 覆盖所有 current table paths。Plan 07 才拥有 reindex claim/build/resume 状态机；Plan 08 才拥有 pointer CAS activation、manifest epoch refresh 与 source-drift continuity，本 task 未提前实现。

## 2026-08-11 — Phase 64.4 Plan 06 Task 2 — ordinary write/maintenance 路径可绕过 active named config ✅已修复验证

- **子系统**：RAG ingestion / corpus projection binding / search-text backfill / demo seed-reset / architecture guard。
- **问题现象 / 根因**：Plan 04 的 ordinary ingestion 仍由 caller `assembly_mode` 决定 assembler；repository `bulk_insert`、search-text backfill 与 demo seed/reset 不解析 tenant active pointer，seed 还直接构造无 canonical block/immutable binding/config audit 的 `PolicyChunk`。Phase 64.2 current-head backfill/reconcile 也会跨 tenant 全局直读 shared current rows。migration 030 后这些路径可能写入错误 config、修改 inactive row，或制造没有 active projection binding 的 current material。
- **影响**：active corpus 的命名配置与实际 provider input/chunk bytes 可漂移；新 current row 在生产检索中不可见或错误可见；直接 seed/delete 会碰撞 append-only projection FK，并绕过 corpus-free immutable compatibility。
- **处理状态**：✅ 已修复验证。ordinary real-session ingestion 在 parser/provider/persistence 前内部解析 active pointer，`character.v1` 只选 `CharacterCompatibilityAssembler`，pinned `embedding_tokenizer.v1` 只选唯一 token assembler，unknown/mixed/fingerprint drift 返回固定 fail-closed code；current block/chunk writes 再次在 repository 内解析 scope，immutable append 后由无 caller corpus 参数的 binder 追加 document/block/chunk exact bindings。backfill 强制单 tenant active join；Phase 64.2 current backfill/reconcile 改为逐 tenant pointer 锁定。demo seed 只接受已存在且配置可证明的 active ingested corpus，不再伪造 bare chunks；reset 对 append-only active policy projection 明确拒绝破坏性删除。
- **证据**：Phase 64.4 Plan 06 Task 2；`src/rag/ingestion.py`、`src/rag/search_text_backfill.py`、`scripts/seed_demo.py`、`src/repositories/policy_corpus_scope.py`、`src/repositories/evidence_version_repo.py`、`tests/knowledge/test_evidence_projection.py`、`tests/architecture/test_rag_chunking_boundaries.py`；RED 为缺失 active config selector 的预期 collection error；最终完整 `make lint` 通过，Task 2 gate `65 passed, 1 warning`，Task 1 回归 gate `41 passed, 1 warning`。静态枚举锁定所有已知 production/repository/script `PolicyChunk`/`DocumentBlock` constructor 与 SQL current path，并拒绝 corpus ID 进入 identity/compatibility 或恢复 `_document_citation_text(chunks)`。
- **剩余风险 / 继续入口**：🟡 demo seed/reset 现在刻意要求 operator 先通过受控 ingestion 建立 active corpus，且不会删除 append-only corpus-bound政策资料；这是避免伪造或破坏 projection 的 fail-closed 行为。Plan 07 才实现 inactive candidate reindex state machine，Plan 08 才实现 source-manifest refresh、pointer CAS 与 active corpus 上持续 create/update/delete 的并发连续性；本 plan 未提前实现这些状态或 activation。

## 2026-08-11 — Phase 64.4 Plan 07 Task 1 — inactive candidate 缺少固定身份、lease/CAS 与 source-stale resume 边界 ✅已修复验证

- **子系统**：RAG policy reindex lifecycle / tenant corpus isolation / provider parity authorization。
- **问题现象 / 根因**：migration 030 与 Plan 06 已提供 corpus rows、active pointer 和 exact scope，但仓库没有 claim/resume owner；任何后续 builder 若只凭 corpus ID 或 mutable current pointer 继续，会在 config/parity、manifest、active corpus/epoch、tenant/run/owner 或 lease 已变化时继续写 candidate，也没有 transactionally ordered document cursor。
- **影响**：中断恢复可能混入两次 source/config，foreign tenant/run worker 可能推进错误 cursor；如果把 `active` 当 corpus state 或 claim 时改 pointer，partial candidate 会泄漏到 current retrieval。过期/被接管的 lease 继续执行还会形成双 writer。
- **处理状态**：✅ 已实现并验证。`PolicyReindexService` 在 tenant advisory lock 与 rollout row lock 下固定 UUID run、config schema/fingerprint、fresh passed parity artifact hash/capture expiry、manifest revision/hash、source active corpus/epoch、evidence epoch、owner/lease 与 ordered doc keys；状态仅允许 `claimed/building/built/validating/complete/failed/source_stale`，active authority 始终只来自 rollout pointer。resume/checkpoint 以 tenant/run/owner/state version/cursor CAS fail closed，拒绝 config/parity/manifest/pointer/epoch/owner/expired-or-taken lease drift；每个 ordered document checkpoint 不 commit，必须与调用方 projection writes 共用单事务，rollback 后 cursor 不前进。
- **证据**：Phase 64.4 Plan 07 Task 1；`src/rag/policy_reindex.py`、`src/repositories/policy_corpus_repo.py`、`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex.py`；真实 PostgreSQL gate `5 passed, 1 warning`，完整 `make lint` 通过。负向覆盖 cross-tenant/run、foreign/taken owner、expired lease、stale CAS、out-of-order doc、manifest/pointer drift；rollout pointer 在 claim/build checkpoint 全程不变。
- **剩余风险 / 继续入口**：Task 2 仍须从 active `PolicyDocument` + ordered authoritative `DocumentBlock` 生成 sealed snapshot，做 per-document recheck、inactive projection/immutable binding/count/determinism/replay 与 interrupted idempotency；Plan 08 才拥有 pointer activation、ordinary ingestion continuity 和 retention cleanup，本 task 未提前实现。

## 2026-08-11 — Phase 64.4 Plan 07 Task 2 — candidate reindex 会误投影 shared current evidence head ✅已修复验证

- **子系统**：RAG policy reindex / authoritative DB source snapshot / immutable evidence binding。
- **问题现象 / 根因**：Plan 05 的 `EvidenceVersionRepository.append_immutable_version()` 同时拥有 immutable append 与 ordinary current-head write-sequence projection，原签名没有 candidate-only 模式。Plan 07 若直接复用，会把 inactive token candidate 的 sequence 写回 shared `PolicyDocument`/`PolicyChunk`；若绕开该 repository 自行写 immutable rows，又会复制 Phase 64.2/64.4 的 compatibility、retention 与 replay owner。另一个缺口是仓库没有显式 source-corpus 的 `PolicyDocument` + ordered `DocumentBlock` sealed snapshot/read-back recheck，reindex 容易重新读原始文件或混入 mutable latest source。
- **影响**：未激活 candidate 可能污染 current evidence head，ordinary ingestion/canonical current identity 与 inactive build 混合；中断恢复可能重复 vector/binding 或跨 source epoch 继续；缺少 exact recount/rebuild 时，持久化 hash/count 无法证明对应真正 provider input。
- **处理状态**：✅ 已修复验证。`DocumentBlockRepository` 新增 corpus-qualified authoritative snapshot，锁定 manifest 指定 document/immutable document/block bindings，完整 hash 文本与 provenance，并在每文档 checkpoint 前重读比较；`PolicyReindexService` 只消费该 DB snapshot，经唯一 `PolicyEmbeddingInputAssembler` 生成 frozen provider input，复算 hash/EOS-inclusive count、验证 1024 维 vector 数量，append/reuse immutable document/chunk 后只绑定 inactive candidate。immutable repository 最小增加 `project_current_head: bool = True`：ordinary caller 默认语义不变，candidate 唯一显式 `False`，对应回归证明 shared document/chunk sequence 不变。document projection、block projection、chunk/vector、immutable binding 与 cursor CAS 同一事务，rollback 后零 candidate binding 且 retry 不重复；complete validation 从 source snapshots 重建 count/hash/content/provenance，封存 config/parity/manifest/source epoch、coverage、no-mixed-source 与 corpus-free immutable compatibility proof。该 ownership deviation 已获 Plan 07 executor 上层确认。
- **证据**：Phase 64.4 Plan 07 Task 2；commits `34edced6`（Wave-0 RED）及 Task 2 GREEN commit；`src/repositories/document_block_repo.py`、`src/repositories/evidence_version_repo.py`、`src/rag/policy_reindex.py`、`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex.py`、`tests/knowledge/test_document_source_identity.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；真实 PostgreSQL/pgvector 三文件 gate `89 passed, 3 warnings`，完整 `make lint` 通过。
- **剩余风险 / 继续入口**：Plan 08 才拥有 candidate pointer CAS activation、active manifest/epoch refresh、ordinary create/update/delete continuity 与 retention/cleanup；Plan 09 才拥有同次 A/B selection。本 task 没有增加 activation、current retrieval 或 ordinary ingestion selection 语义。真实 provider build 仍需由 operator 提供 fresh passed parity/credential 后通过 CLI 执行，本地测试只用确定性 1024 维 fake vector，未伪造 live provider 事实。

## 2026-08-11 — Phase 64.4 Plan 08 — append-only corpus 与普通 ingestion 缺少 COW 演进模型 ✅已修复验证

- **子系统**：RAG ordinary ingestion / corpus rollout / immutable evidence retention。
- **问题现象 / 根因**：migration 030 的 manifest、activation history 与 projection bindings 均 append-only，binding FK RESTRICT；同时单一 `PolicyDocument` head 和 `DocumentBlock(tenant, doc, source_block)` 唯一约束使 create/update/delete 无法既原地替换又保留旧 corpus replay。原 Plan 08 action 若直接沿用 repository delete 路径会破坏已接受的 immutable history 边界。
- **影响**：普通写入可能删除旧 activation/replay 证据、让当前 pointer 指向不完整 projection，或允许 source drift 后直接 rollback 到过时政策；并发 ingestion/cutover 还可能出现 mixed authority。
- **处理状态**：✅ 已修复验证。经 Rule 4 用户批准，migration 031 仅移除 block source identity 唯一约束并保留非唯一索引，downgrade 检出重复即 fail closed；普通 create/update/delete 固定 evidence rollout→tenant corpus rollout→manifest→document 锁序，构建同 config complete COW corpus，复制未变 bindings、为变更 source 追加 block/chunk/immutable rows、append manifest/history 后 CAS 唯一 pointer+epoch。所有绑定旧 manifest 的可用/在建 corpus（除新 COW）同事务标 `source_stale`，过时 corpus拒绝直接 rollback/restore，必须用当前 source 按旧 config rebuild。cleanup 仅逻辑终止 exact tenant/run/owner candidate，不删 immutable/binding/history。
- **证据**：Phase 64.4 Plan 08；`src/db/migrations/versions/031_phase64_4_policy_corpus_cow.py`、`src/db/models.py`、`src/rag/ingestion.py`、`src/repositories/policy_corpus_repo.py`、`src/rag/policy_reindex.py`、`tests/knowledge/test_policy_corpus_cow_migration.py`、`tests/rag/test_ingestion_continuity.py`、`tests/rag/test_policy_reindex.py`；Task 2 gate `47 passed, 1 warning`，合并真实 PostgreSQL gate `94 passed, 4 warnings`。
- **剩余风险 / 继续入口**：Plan 08 activation 只接受 immutable selection DTO fixture，不读取、生成或宣称真实 selected artifact；Plan 09 才拥有同次 A/B selection，Plan 10 才拥有真实 receipt hash chain/drill。`receipt_hash` 本 plan 保持 NULL，未伪造 provider/selection success。

## 2026-08-11 — Phase 64.4 Plan 08 — active current projection helper 与 retained canonical v2 复用缺陷 ✅已修复验证

- **子系统**：RAG current retrieval / canonical evidence reconciliation / immutable replay。
- **问题现象 / 根因**：active chunk projection helper 以 `PolicyDocument.id` 连接 corpus document binding，但部分 current statements 只选择 `PolicyChunk`，PostgreSQL 因缺少 FROM 失败；修正 helper 后，一个 current identity caller 又重复 join 同名 `CorpusChunkBinding`。另外 canonical document matcher 在未携带 canonical source DTO 的 reconciliation 路径对所有 v2 retained rows返回不匹配。
- **影响**：canonical current identity/retrieval 可在 runtime SQL 编译或执行时失败；已有 v2 immutable document version 可能被误判为 drift，阻断 canonical read cutover。若为了修复而把 active pointer 加入历史 resolver，则会进一步破坏 retained immutable identity。
- **处理状态**：✅ 已修复验证。helper 统一通过 `PolicyChunk.doc_id` 证明同 active corpus 的 document binding，current identity caller复用该唯一 binding join；canonical v2 无 DTO 分支严格验证 source checksum、persisted content hash/canonical fields，并与 current head content/hash再比较。历史 `resolve_immutable_evidence` 保持只按 retained immutable ID/tenant/scope，不读取当前 pointer。
- **证据**：Phase 64.4 Plan 08 Task 1/2 Rule 1；`src/repositories/policy_corpus_scope.py`、`src/repositories/evidence_version_repo.py`、`tests/knowledge/test_evidence_cutover.py`、`tests/knowledge/test_evidence_projection.py`；targeted regression `2 passed`，最终合并 gate `94 passed`。
- **剩余风险 / 继续入口**：当前无已知缺口。后续修改 active projection helper 时须避免 caller 重复 join同一 ORM entity；历史 identity resolver 必须继续与 current authority 解耦。

## 2026-08-11 — Phase 64.4 Plan 09 Task 1 — A/B 选择缺少精确数值与不可变终态 owner ✅已修复验证

- **子系统**：RAG token chunk A/B evaluation / selection evidence。
- **问题现象 / 根因**：Phase64.3 canonical report 以六位小数展示 retrieval 指标，仓库此前没有 character/token 同次比较 owner，也没有为 quality red、safety red、provider unavailable、execution error 都保留 create-only 终态证据的 strict schema。若直接比较 `0.022223/0.066667/0.018519` 等展示值，边界舍入可能改变 selection；若把 selection 与 activation 写入同一 artifact，后续 cutover 会反向改写授权证据。
- **影响**：候选可能因 round drift 被错误选中/拒绝；red/unavailable/error 运行可能无证据；selection hash 可能被 pointer/receipt 字段污染，无法作为 Plan10 独立 activation 的稳定授权输入。
- **处理状态**：✅ 已修复验证。新增 `rag_token_chunk_ab.v1`：所有命中、MRR、format spread、anchor/locator/fallback、duplicate、chunk/token 比例只保存 raw numerator/denominator 并用 `Fraction` 比较；成本用版本化 `Decimal` basis，六位小数只在 Markdown 投影。固定 14 个门禁精确实现 9/10、1/10、1/45、1/15、1/54、1/50、3/2、5/4 边界，并封存 Phase64.3 三个 hash 与 45/54 case counts。四种终态均写 create-only canonical JSON/MD；只有真实 full-provider `selected_pass` 可额外生成独立 `rag_token_chunk_selection.v1` JSON/MD/hash，schema 不含 activation/pointer/cutover/rollback/history/receipt 字段。
- **证据**：Phase64.4 Plan09 Task1；`src/rag/evaluation/token_chunk_ab.py`、`src/rag/evaluation/reporting.py`、`tests/eval/test_rag_token_chunk_ab.py`、`evaluation/reports/rag_token_chunk_ab/v1/README.md`；Wave-0 以缺少 module 的 collection error 正确 RED，完成后 `make lint` 通过，精确 report gate 为 `41 passed, 1 warning`。
- **剩余风险 / 继续入口**：Task2 仍须把 exact contract 接到 production-capable full-provider CLI，并证明 character/token 使用相同 provider/retrieval 配置和隔离 inactive corpus/round owner。Plan10 才执行 live parity/A-B、cutover/rollback/restore 与 receipt chain；当前没有伪造 selected_pass，也没有修改 rollout pointer/history。

## 2026-08-11 — Phase 64.4 Plan 09 Task 2 — Phase64.3 evaluator 在 COW 后缺少无 pointer 副作用的 A/B 运行面 ✅已修复验证

- **子系统**：RAG evaluation / ordinary-ingestion COW / token chunk A/B。
- **问题现象 / 根因**：Phase64.3 三格式 evaluator 以短事务提交 ingestion/cleanup；Plan08 把 ordinary ingestion 纳入正确的 active-corpus COW 后，直接复用该 evaluator 做 Plan09 A/B 会提交 evaluation tenant 的 rollout pointer/history 变化，而且原 round terminal observation 没有在 job 删除前保留 chunk、duplicate、offline/provider token 与 config fingerprint 原始统计。
- **影响**：selection 评估可能违反“Plan09 不改 pointer”的授权边界；资源 gate 无法从已清理 round 重建，provider usage 可被不真实地推断或丢失。
- **处理状态**：✅ 已修复验证。新增 deterministic incumbent/candidate namespace；rollback owner 是独占 `AsyncConnection` 的外层 transaction，内部 evaluator session 使用 `join_transaction_mode="create_savepoint"`，因此 production ingestion/COW 内部 commit 只释放 savepoint，完成/异常最终均 rollback connection transaction，不提交 pointer/history。提交前深审曾发现最初使用 `AsyncSession.begin()` 作为 root 会被 production `session.commit()` 提前结束，已用模拟内部 commit 的回归修正。在 exact-complete job 删除前捕获资源 proof，resume 仅从持久 projection 重算可证明字段，provider usage 不可恢复时明确标 `unavailable`。CLI 前后复验 active incumbent 与 complete inactive token candidate，且 selection 绑定真实 candidate corpus/run/lease/parity hash。
- **证据**：Phase64.4 Plan09 Task2；`src/rag/evaluation/retrieval_rounds.py`、`src/repositories/rag_evaluation_round_repo.py`、`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；scoped gate `118 passed, 1 warning`。
- **剩余风险 / 继续入口**：Plan09 只交付生产可运行命令与隔离 contract tests，不把 deterministic fixture 当 live evidence。Plan10 必须提供新鲜 live parity 和 complete inactive candidate 后执行命令；真实 selected_pass、cutover/rollback/restore 与 receipt chain 仍由 Plan10 独占。

## 2026-08-11 — Phase 64.4 Plan 10 Task 1 — activation history 缺少独立 create-only receipt chain ✅已修复验证

- **子系统**：RAG corpus activation / immutable selection evidence / operator reconciliation。
- **问题现象 / 根因**：Plan08 已把 pointer event 写入 append-only PostgreSQL history，但 `receipt_hash` 因不可变 trigger 与自引用循环保持 NULL；Plan09 的 selection、terminal run、provider parity 又必须保持只读。此前没有一个 owner 能在 DB commit 后把 exact history row、live pointer 与三份上游 artifact 绑定成可独立审计的 receipt，也无法在 DB 已提交但文件写入中断时安全补写。
- **影响**：cutover / rollback / restore 的 from-to corpus、before-after epoch、actor/time 与 selection/provider evidence 之间缺少不可改写的文件链；若直接回写 history 或覆盖 selection，会破坏 append-only/COW/replay 边界；若普通覆盖文件，重试可能掩盖不一致。
- **处理状态**：✅ 已修复验证。新增严格 `rag_token_chunk_activation.v1`：以 tenant + 20 位 rollout/history sequence 定址，首条为 `genesis`、后续绑定前一 receipt 文件 hash；receipt 同时封存 canonical DB row hash、event/from/to/before-after epoch、actor/commit time、selection 文件与 payload hash、terminal/parity hash、candidate run/lease、source manifest 与 config。CLI 先结束 activation transaction，再用新 session 重读 live DB、重算三个只读 artifact hash并以临时文件 + hard-link 原子 create-only 落盘。已存在 exact bytes 幂等接受，任何 bytes/history/pointer/artifact mismatch fail closed；缺失文件只按 committed history 顺序确定性 reconciliation，不修改 DB history 或上游 selection/parity。
- **证据**：Phase64.4 Plan10 Task1；RED commit `d2a698fd` 与本条所在 GREEN commit；`src/rag/activation_receipt.py`、`scripts/reindex_policies.py`、`src/rag/policy_reindex.py`、`tests/rag/test_activation_receipt.py`、`tests/rag/test_policy_reindex.py`、`evaluation/reports/rag_token_chunk_ab/v1/activations/README.md`；完整 `make lint` 通过，scoped gate `20 passed, 1 warning`，CLI help smoke 确认 `activate` / `reconcile-receipts` 已注册。
- **剩余风险 / 继续入口**：Task2 仍须在真实 evaluation tenant 上用真实 selected_pass artifact 执行三次 pointer event，核对三条 DB history、三份 hash-chain receipt、stale CAS no-op 与 legacy replay；本 Task1 的 deterministic test artifact 不代表 live provider 成功。

## 2026-08-11 — Phase 64.4 Plan 10 Task 2 — A/B preflight 把 Phase64.4 head031 误判为旧 schema ✅已修复验证

- **子系统**：RAG full-provider A/B evaluation / database prerequisite boundary。
- **问题现象 / 根因**：Plan09 A/B 的 `_validate_corpus_pair` 直接复用 Phase64.3 evaluator 的 `_database_prerequisites`；该旧函数为当时 canonical baseline 固定要求 Alembic revision 恰等于 029。Plan10 必须在包含 token corpus/COW 的 031 上执行，因此真实 attempt 1 尚未运行 retrieval 就被 `database_schema` 拒绝并产生 `execution_error`。
- **影响**：即使 pgvector、evaluation tenant、canonical evidence rollout、complete token candidate 全部健康，也不可能生成真实 selected_pass；若为绕过而放松 Phase64.3 gate，会反向改变已封存 baseline 的运行契约。
- **处理状态**：✅ 已修复验证。Phase64.3 函数保持不变；A/B 新增局部向上兼容 owner，先执行旧 tenant/evidence检查，只在旧结果含 `database_schema` 且 live DB 同时证明 evaluation rounds、corpus rollout、chunk binding、activation history、pgvector 与 exact `031_phase64_4_policy_corpus_cow` 时移除该单项。其他 missing 原样保留，未来未知 revision 不自动放行。
- **证据**：Phase64.4 Plan10 Task2；RED commit `f3c85309` 与本条所在修复 commit；`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_token_chunk_ab.py`；RED 为缺少 Phase64.4 compatibility owner，完成后 format/full lint 通过，A/B scoped gate `94 passed, 1 warning`，真实 031 probe 从 `['database_schema']` 变为 `[]`；attempt 1 artifact `runs/3d4dae9c-a692-482d-b172-965edf5890e0.json` 保留且 pointer/history 零漂移。
- **剩余风险 / 继续入口**：只允许因该已验证实现缺陷启动 attempt 2；若后续得到 genuine `candidate_failed`，必须停止并保留 prior active，不能再以 schema compatibility 为理由重跑或调阈值。

## 2026-08-11 — Phase 64.4 Plan 10 Task 2 — rollback-only evaluator 与合法非空 COW baseline 冲突 ✅已修复验证

- **子系统**：RAG full-provider evaluation / append-only corpus COW / transaction isolation。
- **问题现象 / 根因**：Plan09 rollback wrapper 已保护 outer connection transaction，但 Phase64.3 repository 仍把 current blocks/chunks/jobs 非空视为残留，并在 terminal cleanup DELETE current projection。Plan08 后 evaluation tenant 的 active corpus 合法绑定非空 current projection；DELETE 会破坏 append-only binding/replay，且后续格式不能在同一 root transaction 内证明回到原 baseline。
- **影响**：真实 A/B attempt 2 在 ingestion 前 `execution_error`；若简单放宽 clean check 或继续 DELETE，可能破坏 active corpus、历史 evidence 与 pointer authority。
- **处理状态**：✅ 已修复验证。`[Rule 4 - Architectural change]` 经用户明确批准，仅为 `rollback_only=True` 增加 baseline-aware contract：独立只读 session 封存 rollout/history、active corpus/config/manifest、exact current view/jobs、evidence rollout 与 corpus/evidence immutable counts；每个 format 使用独立 outer connection transaction，production commit 只释放 savepoint，terminal repository 只写 rollback-pending proof而不 DELETE；outer rollback 后全新 session 必须字节语义等价重读，只有完全一致才把返回 round 的 post-state/immutable flags 设 true。Phase64.3 non-rollback pre-state、cleanup DELETE 与 resume payload 调用保持原路径。
- **证据**：Phase64.4 Plan10 Task2；用户 2026-08-11 Rule4 rollback-only baseline 批准；RED `7440b0df`、GREEN `2851d385`；`src/rag/evaluation/retrieval_rounds.py`、`src/repositories/rag_evaluation_round_repo.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；format/full lint，Plan09 `122 passed`、Plan10 `38 passed`，attempt3 前后 live baseline proof 同为 `sha256:4dae8f0ec1c9e4c7b2010786fbd94f05af7b2d8623f0ae4df196d14ff26823f3`。
- **剩余风险 / 继续入口**：当前 rollback isolation 零漂移已由 live exact proof验证；full-provider run 仍因下条诊断证据缺口无法定位最后 execution_error，本 plan 已耗尽 attempt budget。

## 2026-08-11 — Phase 64.4 Plan 10 Task 2 — baseline proof 未规范化 pgvector ndarray ✅已修复验证

- **子系统**：RAG evaluation baseline hashing / PostgreSQL pgvector adapter。
- **问题现象 / 根因**：新 baseline proof 的 canonical JSON helper 支持 UUID/date/list，但真实 pgvector ORM 返回 NumPy `ndarray`，只读 preflight 因无法序列化 embedding 中止；单元 fixture 的 list 形态未覆盖 driver representation。
- **影响**：即使 DB/candidate/provider prerequisites 健康，rollback baseline 无法在 live DB 封存，最后 attempt 不应启动。
- **处理状态**：✅ 已修复验证。只接受带 `tolist()` 且归一结果为 list 的 array-like DB 值，等价 array/list 生成相同 canonical hash；不保存或输出 embedding/content。RED `55d6458d`、GREEN `c4bc6aea`，Plan09 `123 passed`、Plan10 `38 passed`，live baseline capture 与 candidate preflight `missing=[]`。
- **证据**：Phase64.4 Plan10 Task2；`src/repositories/rag_evaluation_round_repo.py`、`tests/eval/test_rag_retrieval_round_isolation.py`；live PostgreSQL baseline proof `sha256:4dae8f0ec1c9e4c7b2010786fbd94f05af7b2d8623f0ae4df196d14ff26823f3`。
- **剩余风险 / 继续入口**：当前无此 representation 缺口；未来更换 pgvector adapter 时仍须用 live read-only proof确认 canonical shape。

## 2026-08-11 — Phase 64.4 Plan 10 Task 2 — A/B terminal broad catch 丢失 role-level failure provenance 🔴待立项

- **子系统**：RAG full-provider A/B orchestration / immutable failure reporting。
- **问题现象 / 根因**：attempt3 run `9aa10545-2350-4053-b4ef-03a57fda0535` 终态只有 `terminal_stage=execution` 与 `provider_execution_failed`；`scripts/eval_rag_token_chunk_ab.py` 在 role run 非完成时先抛 `retrieval_round_incomplete`，随后 broad catch 使用 `_terminal_without_observations`，丢弃已计算的 role rounds/reason codes。
- **影响**：create-only artifact 能证明“没有 selected_pass”，但不能区分 provider transient、ingestion/retrieval实现错误或 baseline cleanup error；三次上限后无法用 immutable证据裁定是否允许新 attempt，也不能安全声称 genuine candidate quality fail。
- **处理状态**：🔴 待新 reviewed diagnostic plan。当前不在 attempt 已耗尽后修改 artifact schema或重跑；三份 immutable execution_error report与 prior active corpus全部保留。
- **证据**：Phase64.4 Plan10 attempt3；artifact JSON SHA `sha256:863a88ec87c575668712e4b56937b45d7d24d9773f0af0dbe8e6b8b89e9d7c49`；selection `30ffe6e0-6f91-4429-91b2-2dee8c20ee73` 不存在；attempt 前后 baseline proof完全相同。
- **剩余风险 / 继续入口**：用户需决定是否新建诊断/config plan。建议先让 execution-error terminal artifact保留每个已完成/失败 role round的 safe `reason_code` 与 rollback proof，再由新的显式 provider budget决定是否允许额外 attempt；禁止在 Plan10 内第四次执行。

## 2026-08-12 — Phase 64.4 Plan 11 — role failure provenance 与 execution-error bundle 提交点缺失 ✅已修复验证

- **子系统**：RAG full-provider A/B orchestration / rollback isolation / immutable diagnostic publication。
- **问题现象 / 根因**：Plan10 attempt3 已证实 top-level broad catch 会把 role/format/stage 与 rollback proof 压成 `provider_execution_failed`；旧 run JSON/Markdown 又是顺序发布，没有能同时约束 run 与 diagnostic 四文件的单一 reader-visible 提交点。进程在任一写入/link 边界中断时，消费者无法区分完整证据与 partial bundle。
- **影响**：无法从不可变证据裁定失败属于 shared preflight、character/token role、ingestion/provider/resource proof 或 post-rollback baseline；partial/mismatched artifact 还可能误导后续 retry owner。该缺口不允许通过第四次 Plan10 provider attempt 试错。
- **处理状态**：✅ 已修复验证。新增 frozen `SafeRoleFailureV1`，只允许 typed role/round/stage/reason、provider classification、rollback attempted/proved 与安全 hash/count；outer connection rollback 后必须经全新 session baseline 等价证明才传播 `proved=true`，所有 raw exception/trace/provider payload/content/credential/DSN/path 均无序列化入口。`rag_token_chunk_execution_diagnostic.v1` 与旧 `rag_token_chunk_ab.v1` run bytes 分离；四个 canonical 文件先在 per-run staging 写入/fsync，再 create-only link，最后以原子 rename 的 `rag_token_chunk_execution_bundle.v1` manifest 目录作为唯一 bundle commit point。byte-identical partial 可恢复，任一冲突 fail closed；diagnostic 路径不含 selection/activation/pointer/history authority。
- **证据**：Phase64.4 Plan11；Task1 RED `628ed345`、GREEN `89516464`、Task2 RED `f822880c` 与本条所在 Task2 GREEN commit；`src/rag/evaluation/token_chunk_ab.py`、`src/rag/evaluation/retrieval_rounds.py`、`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_token_chunk_ab.py`、`tests/eval/test_rag_retrieval_round_isolation.py`、`evaluation/reports/rag_token_chunk_ab/v1/diagnostics/README.md`。完整 `make lint` 通过，最终 prescribed gate `166 passed, 1 warning`；fault injection 覆盖 stage file write/fsync、所有 parent/final dir fsync、四个 create-only link、manifest stage/fsync/rename 及 rename 后恢复语义。
- **剩余风险 / 继续入口**：Plan11 未调用 live provider，不能追溯重建 attempt3 的缺失 role 事实；Plan12 只能在机器预算与 retry matrix 通过后，用新 manifest-committed diagnostic 解释未来 execution error。旧三份 Plan10 run、selection 缺失事实与 active character pointer 均保持不变。

## 2026-08-12 — Phase 64.4 Plan 12 Task 1 — recovery provider budget 与 retry authority 仅靠流程约束 ✅已修复验证

- **子系统**：RAG full-provider A/B recovery / immutable attempt authority / failure retry classification。
- **问题现象 / 根因**：Plan10 的三次耗尽与新 Plan12 最多两次预算原先只存在于 planning 文本和 immutable run 数量中；入口没有 plan-scoped machine counter，也无法在 provider 前原子绑定 ordinal、run/selection UUID。即使 Plan11 已提供 typed diagnostic，仓库仍没有 closed matrix 区分 genuine candidate/safety stop、manifest-committed transient execution retry、无 sidecar unavailable prerequisite transition 与 ambiguous/implementation-defect stop。
- **影响**：并发或崩溃 executor 可能越过人工计数，第三次 Plan12 或复用 Plan10 identity 可能在 provider 已调用后才因 artifact conflict 暴露；缺失/不完整 diagnostic、未证明 rollback 或未变化 prerequisite 也可能被错误当成 retry authority。
- **处理状态**：✅ 已修复验证。新增 frozen `rag_token_chunk_recovery_budget.v1`，固定 Plan12 identity、cap=2、三份 Plan10 terminal hash、live baseline proof、candidate/fresh-parity identity、sealed input、provider/model 与 `512/384/48`；manifest 和 `rag_token_chunk_recovery_attempt.v1` ordinal 使用 fsynced tempfile + create-only hard-link。reservation 在 provider factory 前提交，crash 消耗 slot，并发只有一个 ordinal winner；Plan10 identity、重复 UUID 和第三次 Plan12 均在 provider 构造前拒绝。retry matrix 仅允许 rollback proved 的 `retrieval_resource_proof/provider_request_failed` committed bundle，或无任何 sidecar且 prerequisite hash 已变化的 allowlisted unavailable；selected/candidate_failed/safety/unknown/missing/mismatch/rollback-unproved/resource/setup defect 全部 stop。
- **证据**：Phase64.4 Plan12 Task1；RED `913aece8` 与本条所在 GREEN commit；`src/rag/evaluation/token_chunk_ab.py`、`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_token_chunk_ab.py`、`evaluation/reports/rag_token_chunk_ab/v1/recovery-budgets/README.md`；Task1 focused GREEN `70 passed, 1 warning`，最终 full lint / prescribed gate 见 Plan12 SUMMARY。
- **剩余风险 / 继续入口**：Task1 只建立 authority，不生成 live manifest/reservation，不调用 provider。Task2 必须先严格复核 Plan10 artifacts、evaluation-only DB baseline、inactive candidate 与 fresh parity，再用该入口保留 ordinal1；任何真实非通过按 closed matrix 停止，不能在本 plan 修 Python、阈值、参数或旧 evidence。

## 2026-08-12 — Phase 64.4 Plan 12 Task 2 — immutable candidate 精确绑定旧 parity run hash，fresh parity 无法通过 preflight 🔴待立项

- **子系统**：RAG token candidate identity / provider parity freshness / full-provider A/B recovery。
- **问题现象 / 根因**：Plan10 complete inactive candidate 的 state artifact 与 DB corpus row 都精确绑定旧 parity report SHA `sha256:7ed994e05e52df4c93ef831669bcd120c731ab689f561c6c699d44ef239d33c5`。Plan12 按契约生成 fresh `passed/exact_match` parity run `c760c106-7e85-440e-a56d-ed7e00eb2fb7`（SHA `sha256:166aba9633018ac529ab33c7dfe65126f2850ecf275987f46cfad9eb984ec1de`）；两次的 config fingerprint、probe fixture SHA 与 submitted-content SHA 完全相同，但 create-only run UUID/timestamp 使 report SHA 必然不同。`scripts/eval_rag_token_chunk_ab.py::_validate_corpus_pair` 同时要求 candidate DB hash、immutable identity hash和 `expected_parity_hash` 精确相等，因此 unchanged candidate + mandatory fresh parity 组合必然返回 `candidate_identity_invalid`。
- **影响**：即使 provider parity、evaluation-only PostgreSQL prerequisites、Plan10 baseline 和 candidate completeness 全部健康，也无法合法进入 Plan12 reserve-before-provider 边界。若就地改 candidate state/DB 会破坏 complete candidate 与旧 artifact 的 immutable identity；若在本 plan 放松 Python gate，则违反“verified defect 必须 stop、单独 reviewed repair”以及 Task2 no-Python 约束。
- **处理状态**：🔴 待单独 reviewed bounded repair plan。Plan12 Task2 未修改 Python、DB、candidate、阈值、`512/384/48`、sealed hashes、provider/model 或任何旧 artifact；未创建 recovery budget manifest，未保留 ordinal，未调用 full-provider A/B。fresh parity report 如实保留为新 immutable prerequisite evidence。
- **证据**：candidate state `evaluation/reports/rag_token_chunk_ab/v1/candidates/6ad12487-4769-48eb-8b0a-5e7efbeeccf7/06-complete.json` SHA `sha256:e643a58b6f6b195c6e6c64625efa1d44290a35f1159416a33488c4bebab4e167`；candidate `b293e0b4-ada6-4165-8e2f-4f1739c88fdf` complete/inactive，projection `3/158/60`；fresh parity report path under config `925446...584` / run `c760c106...2fb7`；read-only `_validate_corpus_pair(... expected_parity_hash=fresh_sha)` 得到 `ValueError:candidate_identity_invalid`；budget manifest absent、reserved slots `0/2`。
- **剩余风险 / 继续入口**：新 plan 必须在不改写旧 evidence 的前提下明确 freshness 与 build-identity 的边界，例如新增独立的 fresh runtime parity binding/proof，或重建一个绑定 fresh report 的全新 candidate generation；不得静默把 exact report hash 降级成宽松字符串比较。修复需先补 RED，证明旧 candidate replay identity仍严格、fresh equivalent parity可授权新运行、parity config/content drift继续 fail closed；之后才能重新评审是否使用仍剩余的 2/2 Plan12 slots。

## 2026-08-12 — Phase 64.4 Plan 13 Task 1 — candidate DB commit 与 state artifact 发布之间缺少可恢复身份 ✅已修复验证

- **子系统**：RAG policy reindex / candidate identity / crash-safe filesystem authority。
- **问题现象 / 根因**：旧 `reindex_policies.py` 在 claim/build/validate transaction 提交后才用普通 `Path.open("x")` 写 state；进程在 DB commit 与文件完成之间退出时，只剩 DB current row，而 CLI 只能从旧 state 恢复并可能重新生成 run token/lease。state 写入也没有 staged file、file/directory fsync、原子 no-replace、exact replay 或截断冲突语义。
- **影响**：同一次 rebuild 可能失去唯一恢复入口，人工重跑存在创建第二 candidate、续租或用 partial state 驱动后续 provider 的风险；descriptor/source/evidence/fresh parity identity 没有共同的 create-only forcing function。
- **处理状态**：✅ 已修复验证。新增 frozen `policy_reindex_recovery_descriptor.v1`，在 claim 前固定 tenant/run/generation/owner、最长两小时绝对 lease、完整 config、fresh parity file/config/probe/content/capture/expiry、source manifest/current corpus/epoch 与 evidence rollout，并用 canonical payload hash自校验。`claim_from_descriptor` 不生成 UUID/lease，DB claim proof封存 descriptor/probe/content hash；`recover_identity` 只锁 exact tenant/run，要求唯一 row、descriptor、config、manifest/pointer/evidence 全匹配，返回 current identity而不 transition/renew/create。descriptor/state/legacy state writer统一使用 staging + file/directory fsync + hard-link no-replace；descriptor existing 必拒绝，state exact bytes幂等，截断或冲突 fail closed。claim/build/validate DB commit 后未发 state 的 fault tests均由同一 descriptor恢复 exact corpus/run/state_version。
- **证据**：Phase64.4 Plan13 Task1；RED `8b2551e7` 与本条所在 GREEN commit；`src/rag/policy_reindex_artifacts.py`、`src/rag/policy_reindex.py`、`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex_artifacts.py`、`tests/rag/test_policy_reindex.py`、`evaluation/reports/rag_token_chunk_ab/v1/candidates/README.md`。RED 为缺少新 artifacts module 的预期 2 个 collection errors；完成后 full lint 与 deterministic PostgreSQL/fault gate 通过，未调用 live provider或修改 live evaluation DB。
- **剩余风险 / 继续入口**：Task2 仍须把每文档 provider 执行次数变成 reserve-before-provider 的 create-only 机器预算；Plan13 只实现 deterministic contract，Plan15 之前不得 claim live candidate或调用 provider。

## 2026-08-12 — Phase 64.4 Plan 13 Task 2 — candidate build provider 执行预算仅靠流程约束 ✅已修复验证

- **子系统**：RAG policy candidate rebuild / crash recovery / provider execution authority。
- **问题现象 / 根因**：旧 reviewed candidate 流程没有 descriptor-bound per-document machine counter；并发 executor、provider 后崩溃或 DB commit/state publication 之间退出时，人工重跑无法证明本 document 已执行多少次，也没有 closed safe result matrix 决定第二次是否允许。
- **影响**：同一 document 可能无限重复调用 provider，或在 state/candidate 已前进后再次执行；alternate root、过期 lease/parity 与 config/source/response failure 也可能在 provider 构造后才暴露。
- **处理状态**：✅ 已修复验证。新增 create-only `policy_candidate_build_budget.v1`，固定 ordered document hashes 与 `max_build_executions_per_document=2`；每个 ordinal 在 provider client 构造前用 staged/fsynced/hard-link no-replace 预留，crash 消耗 ordinal，并发只有一个 winner。第二次只接受同 document/state/artifact/count 未变化且第一结果为 `provider_unavailable` 或 `provider_transient`；config/parity/source/response/projection、缺失 result、state advance、第三次、alternate root 和 expiry 全部 fail closed。success 必须精确前进一个 document 并绑定 post-state artifact；recover-state 可在 DB 已提交但 post-state/result 未发布时确定性补齐 success evidence，validate-reviewed 要求每文档恰一份 success。
- **证据**：Phase64.4 Plan13 Task2；RED `8d5d6cc4` 与本条所在 GREEN 提交；`src/rag/policy_reindex_artifacts.py`、`src/rag/policy_reindex.py`、`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex_artifacts.py`、`tests/rag/test_policy_reindex.py`。deterministic concurrency/crash/fault/retry/refusal tests 与精确 PostgreSQL gate通过，未调用 live provider或修改 live evaluation DB。
- **剩余风险 / 继续入口**：本 plan 只建立 deterministic authority；真实 candidate claim/provider build 仍属于后续 reviewed plan，必须使用新 descriptor/root，不能把旧 unreviewed CLI output 或本地 fake test 当成 live success。

## 2026-08-12 — Phase 64.4 Plan 13 Task 2 — MOCA 外层 retry 与 OpenAI SDK 隐式 retry 嵌套 ✅已修复验证

- **子系统**：RAG embedding provider client / retry ownership。
- **问题现象 / 根因**：`EmbeddingService.max_retries` 已实现 MOCA 外层重试，但 `_get_client()` 构造 `AsyncOpenAI` 时未传 `max_retries`；openai-python 默认还会进行 SDK 内部重试，因此 `EmbeddingService(max_retries=1)` 不能兑现“每 batch 单次 HTTP request”的 build-budget 语义。
- **影响**：一次 machine reservation 可能隐式产生多次 provider request，外层计数、per-document cap 与实际调用数失真；provider transient 时风险最高。
- **处理状态**：✅ 已修复验证。按 Plan13 执行裁决的 Rule 2 correctness deviation，将 `AsyncOpenAI(..., max_retries=0)` 固定为无 SDK 隐式 retry，保留 MOCA 外层默认 `max_retries=3` 生产语义；reviewed build 显式使用外层 `max_retries=1`。新增真实 client 可观察断言 `client.max_retries == 0`，并用 fake client 证明外层 3 次行为及 `request_attempt_count` 不变。
- **证据**：Phase64.4 Plan13 Task2；`src/rag/embedder.py`、`tests/test_embedder.py`；openai-python 官方文档确认默认 retry 与 `max_retries=0` 禁用方式；本条所在 GREEN 提交，format/full lint/精确三文件 gate通过。
- **剩余风险 / 继续入口**：该修复不新增配置或阈值；未来若替换 provider SDK，仍须在 client 层显式关闭隐式 retry，并由 MOCA 单一 authority 计数。真实 provider 行为只能由后续获批 live plan 验证。

## 2026-08-12 — Phase 64.4 Plan 14 Task 1 — A-B recovery budget root 与 candidate state 仅受 caller 参数约束 ✅已修复验证

- **子系统**：RAG token-chunk A-B recovery authority / candidate lineage。
- **问题现象 / 根因**：仓库核对确认 production `eval_rag_token_chunk_ab.py` 直接接受任意 `--output-root`，而 `reserve_recovery_attempt` 只检查 manifest 位于 caller 所给 root 下；复制整个 manifest 到另一个 root 后可重新得到 `01/02` namespace。reservation 同时只信任 caller 给出的 `prerequisite_state_sha256`，没有重新哈希并 strict-load Plan13 canonical candidate state，也没有逐字段核对 corpus/run/owner/config/parity/source/evidence identity。
- **影响**：攻击者或误操作可通过 alternate/copied/symlink root 重置 cap=2，或把 unrelated/stale candidate state 与一个合法 manifest 组合后进入 provider-capable路径；现有 selection 也尚未携带该 ordinal/candidate authority。
- **处理状态**：✅ 已加入 repository canonical resolved root 与 symlink/alternate/outside refusal；production CLI 在任何 provider-capable run 前校验唯一 root。manifest 现绑定 canonical candidate state path、state/descriptor file SHA、corpus/run/owner/version/config、source manifest/current corpus/epoch、evidence rollout 与 fresh parity全身份；每次 reserve 都重新哈希、经 Plan13 descriptor/state strict loader复读，并逐字段核对 fresh passed parity后才发布 ordinal。temporary root 仅保留在 unit store API。
- **证据**：Phase64.4 Plan14 Task1；RED `2b0f56d5` 与本条所在 GREEN 提交；`src/rag/evaluation/token_chunk_ab.py`、`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_token_chunk_ab.py`、recovery budget README。RED 用有效入口 collection 失败于缺少 `canonical_recovery_root`；完成后 format/full lint 与精确 gate `163 passed, 1 warning`。全程未调用 provider、DB、live candidate/A-B slot 或 pointer/history。
- **剩余风险 / 继续入口**：Task1 必须保持 temporary roots 仅供 unit store API 注入，production CLI只能接受仓库唯一 canonical root；Task2 前 selection/activation authority仍未闭合，不能据此执行 live selection 或 activation。

## 2026-08-12 — Phase 64.4 Plan 14 Task 2 — selection 到 activation 未绑定 recovery ordinal/candidate authority ✅已修复验证

- **子系统**：RAG token-chunk recovery selection / activation authority / pointer CAS。
- **问题现象 / 根因**：仓库核对确认 `load_activation_authority` 当前只加载并交叉验证 selection、terminal run 与 provider parity；`ImmutableSelectionDecisionV1` 不含 recovery authorization SHA，`PolicyReindexService._validate_selection_proof` 因而可让真实 selected cutover/restore 在不知道 canonical budget manifest、exact ordinal reservation 与 exact candidate state file 的情况下进入 CAS。
- **影响**：即使 Plan14 Task1 已把 provider 前的两槽预算绑定到唯一 root/candidate，后续 selection artifact 仍可脱离该 reservation lineage；伪造或复制的 selection/terminal/parity 组合无法在 pointer mutation 前证明它来自一个合法未超额 ordinal。
- **处理状态**：✅ 已修复验证。新增 separate create-only `rag_token_chunk_recovery_authorization.v1`，只在 strict `selected_pass` lineage 后发布，并可对 existing exact bytes 幂等 reconcile；它绑定 canonical manifest path/SHA、ordinal reservation path/SHA、exact candidate state/corpus/run/owner/config/parity/source/evidence、terminal 与 selection ID/SHA。activation loader 重读全链并在 production 校验仓库 canonical root，project authorization file SHA；真实 selection 类型缺少有效 SHA 时在 pointer/history CAS 前拒绝。Plan08 fixture 仍是独立 dataclass/schema，不借真实路径 bypass。
- **证据**：Phase64.4 Plan14 Task2；RED `def54dcc` 与本条所在 GREEN commit；`src/rag/evaluation/token_chunk_ab.py`、`scripts/eval_rag_token_chunk_ab.py`、`src/rag/activation_receipt.py`、`src/rag/policy_reindex.py`、`scripts/reindex_policies.py`、`tests/eval/test_rag_token_chunk_ab.py`、`tests/rag/test_activation_receipt.py`、`tests/rag/test_policy_reindex.py`；最终 `make format`、完整 `make lint` 与 prescribed gate `114 passed, 1 warning`。
- **剩余风险 / 继续入口**：本 Task2 仅验证 deterministic artifact/PostgreSQL contract，未创建 live authorization、未激活 pointer；后续 live plan 必须从 canonical root 提供全部七条 artifact paths，不能把 unit temporary root 或任意 SHA字符串当作 provider/activation 成功证据。

## 2026-08-12 — Phase 64.4 Plan 15 / Plan 16 — reviewed claim 只发布 state v2，与 build 的连续 state artifact 契约冲突 ✅已修复验证

- **子系统**：RAG policy candidate rebuild / crash-safe state publication / provider execution authority。
- **问题现象 / 根因**：仓库 live 核对确认 `scripts/reindex_policies.py::_claim_reviewed`（约 286 行）在一个 DB transaction 内完成 claim v1 与 resume v2，提交后仅调用一次 `write_policy_reindex_state_create_only(owner, ...)`，所以新 candidate artifact 只有 `states/00000002.json`。同文件 `_latest_reviewed_state_artifact`（约 308 行）却把当前目录文件数映射为必须从 `00000001.json` 开始连续，并在缺 v1 时抛出 `reindex_state_invalid`。Plan13 deterministic tests验证了单状态 exact replay/fault recovery，但没有覆盖真实 `claim-reviewed` 产物随后直接进入 `build-next-reviewed` 的组合路径。
- **影响**：经过 reviewed descriptor 成功 claim 的合法 candidate 无法进入第一份文档的 reserve-before-provider 边界；若 operator 擅自补 compatibility state、跳号或重新 claim，会破坏 create-only authority、可能制造第二 candidate，且让 per-document执行预算失去可信起点。
- **处理状态**：✅ 已完成 deterministic 修复验证。Plan15 仍保留原始 fail-closed 证据；Plan16 将 future `claim-reviewed` 拆为 claimed/v1 commit→publish 与独立 recover/resume building/v2 commit→publish，四个 commit/publication fault boundary 重入均收敛到同一 row 与连续 v1/v2。`recover-state` 只在 current DB 与 canonical v2 精确为同 descriptor/run/corpus 的 building/v2/index0 时，允许把仅 state/version 改为 claimed/v1 的唯一逻辑前驱补齐；v3+、非零 index、terminal 或任一 identity drift 全拒绝。命令内部还在任何 artifact write 前重查绝对 lease/parity。
- **证据**：Phase64.4 Plan15/16；descriptor commit `38378cc1`、claim artifact commit `3d01f29c`；Plan16 RED `9b4c9e9b`；`scripts/reindex_policies.py`、`src/rag/policy_reindex_artifacts.py`、`tests/rag/test_policy_reindex.py`、`tests/rag/test_policy_reindex_artifacts.py`；`make format`、完整 `make lint`、精确 gate `53 passed, 1 warning`。另修复 identical replay 两个 fast path 未 fsync target parent 的耐久性窗口。
- **剩余风险 / 继续入口**：deterministic 代码已修；live v1 reconcile 仍必须在 Plan16 Task2 重新证明 lease/parity/source/evidence/DB/zero-budget 后执行。若 authority 过期，不得写 v1、续租、rebind、创建第二 candidate或进入 provider/A-B。

## 2026-08-12 — Phase 64.4 Plan 17 Task 1 — canonical recovery manifest 缺少生产签发边界与当前时间 authority gate ✅已修复验证

- **子系统**：RAG token-chunk A-B recovery manifest / live authority / provider forcing boundary。
- **问题现象 / 根因**：Plan14 已定义 fixed cap=2 schema、reservation 与 canonical root，但仓库没有生产命令从 exact complete candidate + fresh parity + live DB authority 签发唯一 manifest；正常 A-B 仍用可由 `--generated-at` 回填的时间做 candidate/parity验证，existing manifest、reservation 与 provider construction 也没有共同的绝对 lease/parity 到期强制点。
- **影响**：operator 无法通过受控入口创建 canonical manifest；过期 authority 可能通过 backdated evidence timestamp、既有 manifest fast path 或 provider 前长链路被继续使用，building candidate也缺少明确的签发拒绝 owner。
- **处理状态**：✅ 已修复验证。新增 domain `issue_canonical_recovery_budget_manifest` 与 production `issue-recovery-budget`；入口内部捕获一个 UTC instant，不接受 authority timestamp 参数，严格加载 canonical descriptor/state/parity并复核 active incumbent、source manifest、rollout/evidence version、candidate row/projection/proofs、Plan10 与 Phase64.3 sealed inputs。签发、existing manifest reconcile、每次 reservation 与 provider construction 前均要求 `checked_at` 严格早于 descriptor lease和parity expiry；相等即 `recovery_authority_expired`。byte-identical manifest replay重新 fsync parent，冲突 bytes fail closed。
- **证据**：Plan17 RED `d643a13d`；`src/rag/evaluation/token_chunk_ab.py`、`scripts/eval_rag_token_chunk_ab.py`、`tests/eval/test_rag_token_chunk_ab.py`、两份 recovery README；最小 RED collection 因缺少新 owner失败，最小 GREEN `4 passed`，完整单文件回归 `85 passed, 1 warning`，最终 full lint/prescribed gate见 Plan17 SUMMARY。
- **剩余风险 / 继续入口**：Task1没有生成 repository live manifest、reservation或调用 provider。Plan17 Task2只能对保留的 building/v2/index0候选执行签发拒绝验证；若绝对 lease已到期，只允许只读证明 `recovery_authority_expired` 和零副作用，不续租、不新建候选。后续 build/issuance/A-B仍由已冻结的 Plan18独占。

## 2026-08-12 — Phase 64.4 Plan 17 Task 2 — 保留候选 authority 在签发验证前到期 ⚠️修复已验证但 live closeout 受阻

- **子系统**：RAG token candidate recovery / absolute lease / live A-B closeout。
- **问题现象 / 根因**：保留 descriptor 的不可续租绝对 lease 为 `2026-08-12T04:13:52.208631Z`；Task1完成完整 lint与 `198 passed` deterministic gate后，UTC已到 `04:14:12Z`。同一 canonical state/parity 的只读 strict issuance loader按新 forcing function返回 `recovery_authority_expired`，早于 candidate completeness、manifest、reservation或provider边界。
- **影响**：当前 building/v2/index0候选不能签发 cap=2 manifest，也不能继续 Plan18 build/A-B。既有 phase计划数量冻结为20；本条不扩展计划、不续租、不新建候选，也不把过期 authority误报成candidate quality/provider结果。
- **处理状态**：⚠️ deterministic修复与过期拒绝已验证，live closeout停在安全checkpoint。未调用production `issue-recovery-budget`，只读 loader没有写入能力；manifest absent，candidate build attempts/results `0/0`，A-B reservations/runs added/selections/authorizations/activations均为0，provider调用为0。candidate与active pointer/history/current view/evidence rollout无变化。
- **证据**：UTC `2026-08-12T04:14:12Z`；safe code `recovery_authority_expired`；descriptor/v1/v2/build-manifest SHA依次仍为 `0c1734…82a`、`7e0dc9…d7dd`、`66ea0d…f84`、`23e5ea…4a8`；candidate `64932871…151f`仍 `building/v2/index0`、projection `0/0/0`；active `55d651e5…e007`、epoch/history `4/4`、current `3/158/13`、jobs `4`、evidence rollout `1`，read-only proof `sha256:dbefab2e86a5b8cd44a24ab1ed0f48a8f858534f78e6b10f18b2850d21051a0b` 前后相同。
- **剩余风险 / 继续入口**：当前授权边界禁止Plan18继续。下一步必须由orchestrator依据已冻结Plans18-20与用户新授权裁决如何结束phase；本Plan17不得续租、rebind、生成第二candidate或追加Plan21。

## 2026-08-12 — Phase 64.4 CR-01 — reviewed candidate budget 可被复制 artifact root 重置 ✅已修复验证

- **子系统**：RAG policy candidate rebuild / provider execution budget authority。
- **问题现象 / 根因**：`claim-reviewed`、`recover-state`、`build-next-reviewed`、`validate-reviewed` 原先把 caller 的 `--artifact-root` 同时当作 descriptor/state/budget/reservation authority；完整复制自洽目录即可获得新的 per-document ordinal namespace，重置最多两次 provider execution 的安全边界。
- **影响**：allowlisted transient/unavailable 或 provider 后 crash 可通过重复复制目录无限重新 reserve，并在同一 DB candidate 上反复构造 provider，机器预算不再可强制。
- **处理状态**：✅ 已修复验证。production reviewed 入口先从 resolved repository root 推导唯一 `evaluation/reports/rag_token_chunk_ab/v1/candidates`，要求 caller 路径逐字归一后等于 canonical root，并拒绝 root 到 repository boundary 的任何 symlink component；拒绝发生在 descriptor/state/budget load、reservation 与 provider factory 之前。临时 canonical root 只保留为 argparse 不可选择的测试内部注入。
- **证据**：Phase64.4 review CR-01；`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex.py`；copied-tree 与 symlink-root adversarial gate `1 passed`，reservation/provider 均为 0，Ruff scoped check通过。
- **剩余风险 / 继续入口**：尚未执行 live candidate/provider，也不得用本 deterministic 修复恢复已过期 authority；Plans18-20 仍未执行。共享 PostgreSQL schema 的并发 fixture 冲突另记 `LOCAL-VALIDATION-ISSUES.md`，不作为本安全边界失败。

## 2026-08-12 — Phase 64.4 WR-01 — clean/new tenant 缺少首个 policy corpus authority ✅已修复验证

- **子系统**：RAG ordinary ingestion / tenant corpus bootstrap / demo seed。
- **问题现象 / 根因**：migration 030 只遍历已有 `policy_documents` 的 tenant；clean install 与 migration 后新建 tenant 没有 manifest/corpus/rollout/history。ordinary ingestion 又在解析前要求 active scope、写入时要求 locked rollout/manifest，`seed_demo` 同样只接受已有 active projection，形成首文档 bootstrap deadlock。
- **影响**：全新安装、零文档 tenant、未来 tenant 均无法通过受支持入口写入第一份 policy；并发首次写入若各自临时建 authority，还可能破坏 tenant isolation 或产生多个 epoch-1 pointer。
- **处理状态**：✅ 已修复验证。migration 改为遍历全部既有 tenant并把完整性核对从 `policy_documents` 驱动改为 `tenants LEFT JOIN`。runtime repository 新增 tenant advisory transaction lock 下的 idempotent empty bootstrap：仅在 manifest/corpus/rollout 全空时创建 revision-1 empty manifest、complete character corpus、epoch-1 rollout 与唯一 bootstrap history；已有 rollout原样保留，残缺 authority拒绝。ordinary ingestion在 parser/provider前调用，seed_demo复用同一 owner且允许 empty active projection。
- **证据**：Phase64.4 review WR-01；`src/db/migrations/versions/030_phase64_4_token_corpora.py`、`src/repositories/policy_corpus_repo.py`、`src/rag/ingestion.py`、`scripts/seed_demo.py`、三组对应测试；static migration、真实 PostgreSQL migration、clean seed、empty first-ingest、concurrent first-ingest gates分别通过。
- **剩余风险 / 继续入口**：initializer只创建 character-compatible empty authority，不改变已有 active config，也不推断/修补残缺历史。未运行 live ingestion、provider或 live DB mutation；Plans18-20 仍未执行。

## 2026-08-12 — Phase 64.4 WR-02 — reviewed claim transaction B 使用 descriptor seal time 回填授权 ✅已修复验证

- **子系统**：RAG policy reindex / recovery identity / lease-parity authorization。
- **问题现象 / 根因**：`claim-reviewed` 的 transaction A 用当前时间 claim/commit，但 transaction B 把 `descriptor.sealed_at` 同时传给 `recover_identity` 与 `resume`；`recover_identity` 又只规范化后丢弃 `now`。authority 若在 A/B 之间到期，backdated timestamp仍可把 DB row推进 building/v2并发布 budget。
- **影响**：不可续租的 lease或 provider parity 已失效后，reviewed composition仍能完成，后续 provider budget artifacts看似获合法授权。
- **处理状态**：✅ 已修复验证。transaction A 及 v1 publication完成后，CLI重新采一个 current UTC instant；必须严格早于 lease/parity expiry才允许打开 transaction B，并把同一 instant传给 recovery/resume。`PolicyReindexService.recover_identity` 自身也对 lease/parity执行 `checked_at >= expiry`拒绝，不依赖 CLI防线。
- **证据**：Phase64.4 review WR-02；`scripts/reindex_policies.py`、`src/rag/policy_reindex.py`、`tests/rag/test_policy_reindex.py`；A/B 间 lease equality fault证明 DB 保持 claimed/v1、仅 v1存在、v2/budget不存在、resume调用为0；service lease/parity expiry两条 gate均返回对应 safe code。
- **剩余风险 / 继续入口**：该修复不续租、不改变 descriptor、不构造 provider，也未作用于已过期 live candidate。Plans18-20 仍未执行。

## 2026-08-12 — Phase 64.4 WR-03 — parity expiry 等号仍被当作 fresh ✅已修复验证

- **子系统**：RAG policy reindex / provider parity freshness。
- **问题现象 / 根因**：统一 candidate lock gate 对 lease使用 `lease_expires_at <= checked_at`，对 parity却只在 `checked_at > parity_expires_at` 时拒绝，导致等于 expiry 的瞬间仍可授权 lifecycle transition与 build/validation。
- **影响**：违反所有 authorization boundary 必须严格早于 expiry 的契约；精确 equality 可让已过期 parity驱动 provider-capable work。
- **处理状态**：✅ 已修复验证。parity gate改为 `checked_at >= parity_expires_at` 一律返回 `parity_stale`。
- **证据**：Phase64.4 review WR-03；`src/rag/policy_reindex.py`、`tests/rag/test_policy_reindex.py`；同一 equality instant 覆盖 resume、prepare、build、validate，build拒绝时 embedder calls 为0，scoped gate通过。
- **剩余风险 / 继续入口**：未修改 lease/parity时长、descriptor或 provider配置；未触碰 live candidate。Plans18-20 仍未执行。

## 2026-08-12 — Phase 64.4 WR-04 — parity/activation create-only link 未持久化目录项 ✅已修复验证

- **子系统**：RAG provider parity authority / activation committed-history receipt。
- **问题现象 / 根因**：两类 writer均 fsync temporary file后以 hard link create-only发布，但成功返回前没有 fsync destination parent；activation existing identical reconciliation也直接返回。新建目录链只用 `mkdir(parents=True)`，没有逐级持久化目录项。
- **影响**：调用方已观察成功后若主机崩溃，authority/evidence filename仍可能丢失；activation receipt reconciliation可能在相同窗口反复报告成功但证据目录项未 durable。
- **处理状态**：✅ 已修复验证。新目录链逐级创建并 fsync 每一级父目录；link成功后在最终 destination parent fsync前清理 temporary link，再 fsync parent才返回。activation exact-byte replay同样 fsync parent。两类 writer暴露仅供 deterministic fault test 的 `published` 与 `parent_fsynced` 注入边界。
- **证据**：Phase64.4 review WR-04；`src/rag/tokenizer_parity.py`、`src/rag/activation_receipt.py` 与对应 tests；四个 link/fsync fault cases通过，完整两文件 gate `17 passed, 1 warning`，full lint通过。
- **剩余风险 / 继续入口**：fault tests验证 POSIX file/directory fsync与 hard-link顺序，不代表 live filesystem/power-loss演练；未创建或修改 repository live parity/activation evidence。Plans18-20 仍未执行。

## 2026-08-12 — Phase 64.4 review iteration 2 CR-01 — canonical root 下 descendant symlink 与 namespace TOCTOU ✅已修复验证

- **子系统**：RAG policy candidate rebuild / reviewed artifact authority / provider execution budget。
- **问题现象 / 根因**：iteration 1 已把 production root 固定为仓库路径并拒绝 root/ancestor symlink，但 `tenants/<tenant>/runs/<run>` 仍由普通 `Path` 跟随；入口校验后替换 descendant directory 也可让 descriptor/state/budget/reservation I/O 转向 copied tree。
- **影响**：攻击者或误操作可绕开唯一 per-document ordinal namespace，在同一 DB candidate 上读取或发布替代 budget/attempt evidence；一次性路径检查还留下 check-to-use 窗口。
- **处理状态**：✅ 已修复验证。reviewed command 全生命周期固定 canonical root 与 exact run dirfd，以 `O_NOFOLLOW` 逐级解析四个 descendant，所有 artifact I/O 改为相对该句柄的 no-follow read/list/create-only publish；每次 I/O 及 reservation 后/provider construction 前重新打开 canonical chain并核对 exact run inode。临时 root仍只能通过 argparse 不可达的测试内部属性注入。
- **证据**：Phase64.4 review iteration 2 CR-01；`src/rag/policy_reindex_artifacts.py`、`scripts/reindex_policies.py`、`tests/rag/test_policy_reindex.py`、`tests/rag/test_policy_reindex_artifacts.py`；四级 descendant symlink加 open 后 exact-run substitution gate `5 passed, 1 warning`，reservation/provider均为0。
- **剩余风险 / 继续入口**：这是本地 POSIX dirfd/no-follow deterministic gate，不替代真实 power-loss演练；未读取或修改 repository live candidate、未调用 provider/新建 lease/candidate，Plans18-20 仍未执行。

## 2026-08-12 — Phase 64.4 review iteration 2 WR-01 — initial parity/claim expiry equality仍可授权 ✅已修复验证

- **子系统**：RAG tokenizer provider parity / policy reindex initial claim authority。
- **问题现象 / 根因**：`require_fresh_provider_parity` 与 `PolicyReindexService._validate_claim` 均以 `>` 判断 age；current/age恰等于 expiry/maximum age 时仍视为 fresh。ordinary CLI 使用该结果继续 claim，reviewed claim也未在 transaction A 前固定 current UTC。
- **影响**：已到绝对 expiry 的 provider parity可创建 ordinary/reviewed candidate；reviewed路径还可能发布 canonical v1，形成不应存在的恢复证据。
- **处理状态**：✅ 已修复验证。loader与 service claim统一使用 `>=`拒绝；ordinary/reviewed入口各自捕获内部 current UTC并传入 service，reviewed在 initial DB transaction及v1前强制 lease/parity严格未到期。direct/ordinary/reviewed equality均证明无新增 candidate row，reviewed无v1。
- **证据**：Phase64.4 review iteration 2 WR-01；`src/rag/tokenizer_parity.py`、`src/rag/policy_reindex.py`、`scripts/reindex_policies.py`、对应两份 tests；最小 RED `4 failed`、GREEN `4 passed`、完整两文件 gate `51 passed, 1 warning`。
- **剩余风险 / 继续入口**：没有改变24小时 parity window、lease期限或 provider配置；未触碰 live DB/artifact，Plans18-20 仍未执行。
