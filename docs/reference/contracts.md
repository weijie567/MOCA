<!-- generated-by: gsd-doc-writer -->
# MOCA 跨边界契约参考

> 文档类型：NORMATIVE
> 描述范围：已接受的跨边界不变量、canonical schema owner 与当前状态
> 最后核验：2026-08-04（当前工作区）
> 权威来源：已接受契约、canonical schema owner、当前实现与架构边界测试
> 更新触发：schema、authority、owner、兼容策略、fail-closed 规则或 TARGET / DEFERRED 状态变化

## 阅读规则

本文是便于当前阅读与核对的契约索引；完整、细粒度的已接受契约仍在 [`docs/contract-spec.md`](../contract-spec.md)。后者包含目标语义和历史兼容内容，不能仅凭其中的 normative 描述宣称当前运行时已经实现；当前状态必须同时由本文状态标签、CURRENT 架构文档、源码与测试证明。

本文中的 NORMATIVE 表示约束已经接受，不表示所有目标能力都已实现。每项能力必须按以下状态阅读：

- **IMPLEMENTED**：当前源码存在可运行路径，并有对应静态边界或行为测试锚点。
- **TARGET**：语义与 owner 已接受，但不能据此宣称当前运行时完整具备该能力。
- **DEFERRED**：当前明确不启用；条目必须给出具体能力及重新启用所需条件。

源码中的严格 schema、服务 guard 和持久化事实优先于 prompt、自由文本、前端回显与 checkpoint 副本。状态变化必须通过本文末尾的 delta 规则留痕，不能靠新增别名或兼容分支静默改变语义。

## 全局 authority 不变量

1. 身份、tenant、权限与 merchant scope 只能由可信 API/auth/run boundary 产生；用户、LLM、memory、checkpoint、tool args 和普通聊天不能扩权。
2. 政策证据、当前业务事实、上下文记忆、审批授权、动作草稿与 replay truth 是不同 authority class，彼此不能因为字段形状相似而替代。
3. `AgentState` 只承载工作副本和引用；权威状态仍由各 canonical service、repository 与不可变 hash binding 持有。
4. 所有动作路径必须保持 `claim → risk → snapshot → approval 或 capability → draft` 的绑定链；任一 ref、版本、tenant、run、merchant 或 hash 漂移即停止。
5. 未知 enum、缺失 owner、空 scope、结构校验失败、读取异常或兼容来源无法证明语义时，默认 deny、澄清、manual review 或安全终态，不能猜测成功。

## Canonical owner 索引

| 契约组 | Canonical owner | 源码锚点 | 架构测试锚点 |
| --- | --- | --- | --- |
| `TrustedContext` / `MerchantScopeV1` | `TrustedContextFactory` | [`src/platform/trusted_context.py`](../../src/platform/trusted_context.py)、[`context_projections.py`](../../src/platform/context_projections.py) | [`test_trusted_context_boundaries.py`](../../tests/architecture/test_trusted_context_boundaries.py) |
| `AgentState` / node / router | Agent Graph | [`src/agent/state.py`](../../src/agent/state.py)、[`src/agent/graph.py`](../../src/agent/graph.py) | [`test_canonical_graph_baseline.py`](../../tests/architecture/test_canonical_graph_baseline.py) |
| `ToolPlatform` / `ToolResultV2` | Tool Platform | [`src/tools/contracts.py`](../../src/tools/contracts.py)、[`src/tools/platform.py`](../../src/tools/platform.py) | [`test_tool_boundaries.py`](../../tests/architecture/test_tool_boundaries.py) |
| `BusinessFactResultV1` / `BusinessFactRefV1` | `BusinessFactService`；ref schema 由 Tool contract 统一拥有 | [`src/business/schemas.py`](../../src/business/schemas.py)、[`src/business/service.py`](../../src/business/service.py)、[`src/tools/contracts.py`](../../src/tools/contracts.py) | [`test_tool_contract_backstops.py`](../../tests/architecture/test_tool_contract_backstops.py) |
| `EvidenceRefV1` / claim bundles | Knowledge Service | [`src/knowledge/schemas.py`](../../src/knowledge/schemas.py)、[`src/knowledge/service.py`](../../src/knowledge/service.py) | [`test_phase33_rag_claim_boundaries.py`](../../tests/architecture/test_phase33_rag_claim_boundaries.py) |
| Memory refs / bundles | Memory services | [`src/memory/context_refs.py`](../../src/memory/context_refs.py)、[`src/memory/policy.py`](../../src/memory/policy.py) | [`test_memory_contract_delta.py`](../../tests/architecture/test_memory_contract_delta.py) |
| `RiskDecisionV1` / `ActionSafetySnapshot` | Risk policy + Approval snapshot boundary | [`src/approvals/schemas.py`](../../src/approvals/schemas.py)、[`src/approvals/snapshots.py`](../../src/approvals/snapshots.py) | [`test_runtime_safety_boundaries.py`](../../tests/architecture/test_runtime_safety_boundaries.py) |
| Approval / resume | `ApprovalService` | [`src/approvals/service.py`](../../src/approvals/service.py)、[`src/approvals/schemas.py`](../../src/approvals/schemas.py) | [`test_approval_boundaries.py`](../../tests/architecture/test_approval_boundaries.py) |
| `AutoActionCapability` / `ActionDraft` | Capability service + `ActionService` | [`src/actions/capabilities.py`](../../src/actions/capabilities.py)、[`src/actions/schemas.py`](../../src/actions/schemas.py)、[`src/actions/service.py`](../../src/actions/service.py) | [`test_action_draft_boundaries.py`](../../tests/architecture/test_action_draft_boundaries.py) |
| Trace / `ReplayEventV3` | `ReplayService`；兼容 trace 由 `TraceRepository` 投影 | [`src/replay/schemas.py`](../../src/replay/schemas.py)、[`src/replay/service.py`](../../src/replay/service.py)、[`src/repositories/trace_repo.py`](../../src/repositories/trace_repo.py) | [`test_phase35_replay_eval_boundaries.py`](../../tests/architecture/test_phase35_replay_eval_boundaries.py) |

## 1. TrustedContext 与 MerchantScope

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `TrustedContextFactory` 从已验证 token、active user、role 与服务端输入构造 `trusted_context.v1`；权限先取 token scopes 与 role scopes 的交集并映射为 tool permissions，再加入经过校验的 server tool permissions，后者不能扩大 merchant scope。`support`、`manager`、兼容 `merchant` 均绑定自身 merchant；缺绑定即 deny-all，只有 `admin` 可获得 `merchant_ids=["*"]`。 |
| **IMPLEMENTED** | `MerchantScopeV1` 对请求实际提供的 merchant/category/risk 维度执行 `all_provided_dimensions`；空集合、缺少对应维度、未知 role 或越界 override 均拒绝。Knowledge、Tool、Memory、Approval、Replay 与 Agent identity 只消费最小投影。 |
| **TARGET** | 任何新增 consumer 都必须通过 canonical projector 取得身份与 scope；不得复制 schema、直接构造 authority，或把 public policy scope 与 business merchant scope 合并。 |
| **DEFERRED** | system-owned job 的 wildcard authority 当前没有通用契约。只有先定义独立 system actor/context、job identity、reason code、scope 与 decision event，并补 deny/no-widening 测试后，才可启用后台 wildcard。 |

## 2. AgentState、node 与 router

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `AgentState` 是 LangGraph TypedDict 工作状态；当前图精确注册 15 个节点。node 写字段，router 只做确定性选择；router 未知值或异常必须进入澄清/安全终态。PostgreSQL checkpoint 用于恢复，不成为权限、事实或审批 owner。 |
| **IMPLEMENTED** | 当前写面仍使用 `current_run_id`；`project_to_legacy_agent_state_identity()` 明确把它限制为兼容 identity projection。历史 node/router 名称也只能在 trace/read projection 中映射。 |
| **TARGET** | canonical identity 字段统一为 `run_id`，并按 identity、turn、run、evidence、approval、action 生命周期声明 reset/replace/merge 规则；迁移期间不得同时形成两个可写 authority。 |
| **DEFERRED** | `investigation_result`、`investigation_steps`、`investigation_trigger_reason`、`investigation_path` 等 dormant 字段只有在存在明确 producer、consumer、reset 规则和 graph/schema 测试时才可激活。 |

## 3. ToolPlatform 与 ToolResult

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `ToolCatalog` 是声明来源，`ToolPlatform` 是 graph-facing visibility、runtime authorization、dispatch、input/output validation 与 projection 入口。Planner 看见工具不等于调用获准；每次 invoke 都重新检查 caller、permission、scope、side effect 与 availability。 |
| **IMPLEMENTED** | executor 输出必须收敛为严格 `ToolResultV2`，prompt 只消费 `ToolView` 与 `ToolResultProjectionV1` 的安全面；raw adapter payload、异常对象和 hidden capability 不进入 graph/prompt。 |
| **TARGET** | 新增工具必须单点注册 descriptor，并让 catalog、caller allowlist、resource type、event family 与 output schema 由同一描述或 parity test 防漂移。write 工具不得混入 `investigate` read/retrieval loop。 |
| **DEFERRED** | `get_logistics`、`get_merchant_risk`、`search_sop` 当前只可保持 typed unavailable；具备真实 adapter/executor、scope guard、严格 result schema、projection、decision event 与负向测试后才可改为 available。Raw artifact store 也须先有访问、脱敏、保留与 hash 契约。 |

## 4. BusinessFact

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `BusinessFactResultV1` 由 `BusinessFactService` 拥有；canonical `BusinessFactRefV1` 在 `src/tools/contracts.py` 定义，由 business schema 兼容导出。订单、退款单、工单与受限业务查询通过 service boundary 完成 tenant/scope/freshness 校验。 |
| **IMPLEMENTED** | scope denial 必须发生在 adapter 查询前；越权结果不能泄露资源是否存在。成功事实携带 source、resource identity/version、freshness 与 retrieved time。 |
| **TARGET** | 当前业务陈述必须可追溯到本轮、同 tenant、同 scope 的 typed fact ref；memory、policy evidence、LLM 文本或旧 checkpoint 不能代替当前事实。所有 graph 调用方只经 ToolPlatform → BusinessFactService。 |
| **DEFERRED** | logistics、merchant risk 等新 fact producer 随对应工具保持不可用；启用条件是 domain ownership proof、freshness 规则、no-existence-leak 行为、typed projection 和 scope backstop 测试同时落地。 |

## 5. Evidence 与 Claim

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `EvidenceRefV1`、`VerifiedEvidencePackageV1`、`MaterialClaimV1`、`ClaimVerificationResultV1` 与 `ClaimVerificationBundleV1` 由 Knowledge Service 拥有。Evidence identity 绑定 tenant、文档/chunk、policy version、text hash 与 retrieval config。 |
| **IMPLEMENTED** | citation membership 只证明引用属于本轮 package，不等于语义支持。当前 canonical verifier 继续检查 authority、文本 negation gate、deterministic lexical support 与 business fact dependencies；其他 domain hard-rule helper 因缺少结构化 metadata producer 尚未形成在线保证。Blocked/error/unknown 都不能进入 action path。 |
| **TARGET** | `unauthorized`、`stale`、`conflict`、`invalid_hash`、`invalid_scope` 等状态保持 fail-closed；document ACL、supersedes/authority hierarchy、conflict detection 与 OCR-quality gate 只有在 repository/validator 真正执行时才可宣称已实现。 |
| **DEFERRED** | 在线 semantic support verifier 尚未接 canonical claim path。启用条件是 reviewed mapping 或评测集、阈值与预算、provider timeout/error 的 fail-closed 行为、可审计版本以及正负 contract tests。 |

## 6. Memory

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `SessionContextRef`、`ReviewedMemoryRef`、`CaseWorkingContextRef`、bundle 与 write decision 均固定 `authority_class=contextual_only`。Session、CWC、已审案例与显式软偏好可补充上下文，但不能生产 evidence、当前 business fact、审批、动作授权或 replay truth。 |
| **IMPLEMENTED** | 当前真正接通的 durable 长期偏好写入主路径只有管理员 API；显式用户软偏好的 projector/service contract 已实现，但生产 terminal writers 未传 `trusted_context`，尚不能解析可信 merchant scope。已持久化记录仍由 review status、scope、TTL/current、PII 与 tombstone/no-rewrite 共同限制 prompt 可见性；兼容读取可丢弃旧的无语义 tenant 字段，但不能提升 authority。 |
| **TARGET** | durable memory 继续要求明确 scope、source、review/lifecycle 与 prompt-safe projection；schema 可表达的 scope 不等于 runtime 已开放的 scope，新增检索面必须先证明 merchant/case 归属。 |
| **DEFERRED** | semantic episode 与 closed-case precedent 的自动候选接线要等生产调用方、review queue 和 lifecycle 测试；向量查询要等 query embedding 生产与质量评测；Redis 仅在测得瓶颈后作为有 TTL、可回退 PostgreSQL 的非权威热层。 |

## 7. Risk 与 ActionSafetySnapshot

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `RiskDecisionV1` 绑定 tenant、run、canonical action hash、risk/policy config、rule ref 与 approval requirement。`risk_gate` 可提高风险等级，LLM 不能降低确定性结果。 |
| **IMPLEMENTED** | `ActionSafetySnapshot` 是 approval/action safety 的不可变 snapshot owner；hash projection 绑定 evidence、business fact refs、target merchant、action hash 与 config versions，并拒绝 raw prompt/payload/tool output、secret、credential 与 PII 键。 |
| **TARGET** | action payload、evidence、fact、merchant、policy/risk/retrieval config 任一变化都必须生成新 snapshot/hash，并使旧 approval revision 失效；下游只校验 snapshot，不重新生产它。 |
| **DEFERRED** | 新 action/risk taxonomy 只有在 canonical action registry、deterministic risk rule、snapshot/hash profile、approval policy 和 golden/negative tests 同步落地后才可进入 runtime。 |

## 8. Approval 与 Resume

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `ApprovalService` 是 request/revision/level/assignment/decision transition owner；当前 runtime 固定一个 level 和一个 assignment。Decision command 带 expected versions、revision 与 hashes，并在事务锁/CAS 下更新。 |
| **IMPLEMENTED** | 只有 ApprovalService 产生、并与 tenant/run/action/snapshot 精确匹配的 `TrustedApprovalResultV1` 可恢复 checkpoint。普通聊天、前端 dict、过期/错版结果、自审批或跨 scope 结果均不能形成 resume authority。 |
| **TARGET** | 多 level、`any_one` / `all` 聚合、下一 level interrupt、完整 request idempotency 与 policy-driven assignment 是已接受目标；在运行时和约束测试完成前仍应描述为 TARGET。 |
| **DEFERRED** | 主动 SLA 扫描、提醒与升级 worker 当前不因 schema/事件存在而视为启用。只有 job identity、调度/lease、同一 replay sequence allocator、assignment transition、告警与生产 enablement gate 完整后才可启用。 |

## 9. AutoActionCapability 与 ActionDraft

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | auto path 仅允许低风险、无需审批的 `issue_coupon`，handler 固定 `create_coupon_grant_draft`；capability 是服务端持久化、最长五分钟、一次性且按 actor/run/merchant/action/snapshot/risk 绑定的 opaque bearer ref。 |
| **IMPLEMENTED** | `ActionService` 只创建 durable demo draft；`DraftOutcomeV1` 固定 `not_executed_demo` 与 `external_side_effect=false`。审批路径与 capability 路径都必须再次校验完整 binding 和 idempotency。 |
| **TARGET** | `ActionDraft` 始终只是 proposed action 的 durable record。任何未来 execution boundary 都必须消费已授权 draft，并保留 exact action/snapshot hash、幂等与审计语义，不能把 draft success 改写成外部执行成功。 |
| **DEFERRED** | 真实退款、付款、发券或其他外部 side effect 明确未启用。只有 external adapter、outbox/dispatch、unknown 状态、reconciliation、compensation、幂等、权限与 replay 事件测试全部具备后，才能注册独立 execution capability。 |

## 10. Trace 与 Replay

| 状态 | 约束 |
| --- | --- |
| **IMPLEMENTED** | `TraceRepository` 从 step/approval/draft 构建面向人的兼容时间线；`ReplayService` 从 `AgentTraceEvent` 按 run 内严格递增 `sequence` 构建 `ReplayResponseV3`。两者都不执行 graph、LLM、tool、RAG 或 action。 |
| **IMPLEMENTED** | `ReplayEventV3` 绑定 event/run/tenant/thread、operation pairing、actor、safe refs、redacted payload、provenance 与 retention metadata。Minimal envelope 可读投影为 V3，但保留真实 source schema，且 pairing 仍为 unresolved。 |
| **TARGET** | 所有 producer 共用 event registry、redaction guard 与 per-run allocator；新增事件必须同时定义 schema、owner、pairing、redaction、retention 与 contract test。自动归档/删除和读取过滤只有执行器落地后才算实现。 |
| **DEFERRED** | deterministic rerun 不是 replay。只有固定 input/model/config/tool/evidence 版本、外部依赖替身、结果比较规则与独立权限/审计契约后，才可另立 rerun 能力；不得复用 `/replay` 名义静默执行。 |

## Fail-closed 汇总

| 失败面 | 必须行为 | 禁止行为 |
| --- | --- | --- |
| 身份 / scope | deny-all、403 或 no-existence-leak 404 | 从 payload、checkpoint 或名字猜测 wildcard |
| Tool / business fact | adapter 前拒绝；返回 typed safe error | 透传 raw payload、泄露资源存在性 |
| Evidence / claim | insufficient evidence、clarification 或 safe final | 用 citation、memory 或模型常识冒充支持 |
| Risk / snapshot | blocked 或 manual review，并清除旧 authority | 缺 hash/ref 时降级执行 |
| Approval / capability | 拒绝 resume/consume，保持无副作用 | 接受普通 dict、聊天文本或过期 binding |
| Replay compatibility | 保留 source/provenance，未知 pairing 标 unresolved | 为旧事件伪造 V3 原生证明或重新执行 |

## 兼容策略

兼容只允许发生在 **read/projection 边界**：历史 node 名可映射为当前显示名，minimal event 可投影为 V3 输出，旧 schema 可被严格 parser 读取并映射到 canonical view。兼容层必须保留来源、不能回写伪造的新版本事实，也不能恢复旧的 write、approval、capability 或 action authority。

新增写入一律使用 canonical owner 当前 schema；新增 consumer 一律消费 canonical public method 或 projector。兼容 alias 不得成为第二 schema owner，不得加入新的 runtime branch，也不得以“旧客户端需要”为由跳过 tenant、scope、version、hash、review 或 redaction guard。

## Contract delta 与追踪规则

任何 schema、owner、字段语义、状态枚举、authority、兼容或 fail-closed 变化都必须形成显式 delta；禁止只改 producer 或只放宽 parser 后让契约悄然漂移。Delta 至少记录：

1. 旧不变量与新不变量，以及变化原因；
2. canonical owner、producer、consumer、持久化表和 API/事件影响面；
3. 当前状态从 `IMPLEMENTED` / `TARGET` / `DEFERRED` 如何变化；若为 DEFERRED，写明能力与启用条件；
4. migration/backfill 与 read-only compatibility 策略，及旧写 authority 的终止点；
5. fail-closed 行为、负向案例、schema/hash golden sample 和架构测试锚点；
6. 生效版本、首次可写版本、最后兼容读版本与回滚边界。

若 accepted constraint 与当前实现不一致，必须把它标成 TARGET 或 DEFERRED，并同步更新本页和相关架构文档；不能把目标态描述成当前事实，也不能把当前妥协反向写成永久契约。只有 owner 源码、调用方、迁移与测试共同证明后，状态才可改为 IMPLEMENTED。
