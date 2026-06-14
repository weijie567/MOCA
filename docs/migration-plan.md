NOTE: This file carries the migration roadmap and rollout rules. Phase-level decomposition canonical source remains docs/agent-architecture-phase-decomposition.md; where this file overlaps with that file, the decomposition phase table takes precedence. Do not duplicate phase numbering here.

Phase-level decomposition reference: `docs/agent-architecture-phase-decomposition.md`.

## 19. 迁移路线

迁移路线拆成 11 个 v1.1 主路线 phases，统一使用 `Phase 7` 到 `Phase 17` 作为标准 GSD phase ID。历史 v1.0 保持为已归档的 Phase 1-6；本路线从 Phase 7 连续扩展，不使用独立的前缀 phase namespace。

每个 phase 必须有依赖、输出、测试、退出条件和回滚点；MVP 不依赖 long-term memory、多级 SLA 或真实外部执行。

| Phase | Name | Dependencies | Outputs | Required tests | Exit criteria | Rollback point / non-goals |
| --- | --- | --- | --- | --- | --- | --- |
| Phase 7 | Contract baseline | none | spec contract tables；current-vs-target evidence；identifier semantics；Boris/GSD phase notes | docs lint/manual review；review checklist | 每条“当前已实现”有代码依据和限制说明；graph path 终点/resume 语义明确 | docs-only；不改 `src/`；不宣称目标已实现 |
| Phase 8 | Knowledge facade | Phase 7 | `src/knowledge/service.py`、schemas；`KnowledgeSearchRequest/Result`；Evidence/Citation contracts | strong/partial/no evidence；deterministic tenant-scoped behavior；effective-time；citation membership validation | investigate 的政策证据检索通过 facade 读 evidence；旧 `src/rag` 保持 adapter；MVP 只实现单层 tenant-scoped policy；global fallback / tenant-over-global 为 non-MVP，`DEFERRED_WITH_OWNER` 到 post-Phase 17 `Policy Scope` phase，不阻塞 Phase 8 exit | direct cutover；通过 git revert 或 retained LegacyRagKnowledgeAdapter 回滚；不换 pgvector/embedding 栈；不做 schema migration |
| Phase 9 | Business tool facade | Phase 7 | `src/business/service.py`、contracts、demo adapters；ToolCallContext/ToolResult v2；`ToolCatalog`/`UnifiedToolManager`/`ToolDescriptor`（contract-spec §12.6，工具声明/dispatch/校验单一入口，read/retrieval/write 全量声明） | permission/scope；not_found；timeout；partial_success；invalid_response | read tools 统一走 BusinessToolService；node 不直接访问 repo/tool internals | 可回滚单个 node 调用；不实现写动作 |
| Phase 10 | State lifecycle + routing migration (internal slices 10a/10b/10c) | Phase 8 and Phase 9 | AgentState lifecycle enforcement；router totality；security context injection；slot resolution helper；empty long-term/case-memory read seam；minimal event emitter/allocator/base table | 10a trusted-context/state lifecycle reset/property tests；10b routing/slot seam totality/determinism/required-slot/empty-adapter tests；10c minimal event foundation envelope/allocator concurrency/monotonic sequence tests | 10a trusted fields不可由 LLM 覆盖且 AgentState 不持久化 stale permissions/merchant_scope；10b router/slot/empty-adapter gates pass；10c minimal emitter/append API/base table gates pass 且 read-switch/rollback owner named | 可回滚具体 router；不验收真实 session memory continuity；不引入自由 ReAct；bounded tool loop（investigate 节点内只读受控循环）已采纳并提升进 contract-spec §9：外层仍是单一确定性 node（固定入边/出边 + 单一 route_after_investigate），write/action 仍走 deterministic risk_gate/approval/executor，loop 仅限只读 allowlist 且受 max_iterations 约束 |
| Phase 11 | Intent / clarification | Phase 10 | intent precedence table；confidence calibration hooks；clarification_request_id；prompt/schema split | intent golden set；risk-weighted confusion matrix；missing slot clarification | `contract-spec.md` §11.2 precedence conflicts 有确定 primary intent；low confidence 进入 safe route | 可回滚 classifier prompt；不让 intent node 决定审批/动作 |
| Phase 12 | Session memory | Phase 10 and Phase 11 | `src/memory` session memory；PostgreSQL `session_memories` CAS；active slot TTL/freshness；memory write decision v2 for session；optional Redis hot cache only if non-authoritative | same-thread continuity；cross-thread isolation；stale slot exclusion；PII blocked；Redis/cache-miss fallback if Redis is introduced | session slots 可安全补齐 required slots；memory 不作为政策依据；Postgres remains the session-memory correctness boundary | 可关闭 session memory fallback empty；Redis loss falls back to Postgres if Redis exists；不实现 long-term/case write path as required MVP |
| Phase 13 | Approval state machine (internal slices 13a/13b/13c，见 decomposition §2/§6) | Phase 11 | approval policy/SLA schema；request/level/assignment/decision/events；revision + exact payload/snapshot hash binding；immutable snapshot JSON/hash 过渡字段；SLA scanner implemented feature-disabled | single-level transition table；edit/payload/evidence/config revision invalidates old approval；snapshot hash mismatch supersedes approval；expired no resume；self approval block；multi-level-compatible schema/contract planning；disabled scanner tests | accept/edit/respond/reject/ignore/expired 语义唯一；single-level runtime 可执行；multi-level request/level/assignment contract 可验证但不要求 MVP runtime 聚合；approved action 绑定 exact payload hash + snapshot hash；scanner remains feature-disabled | 可回滚到 single-level approval；SLA scanner 由 Phase 13 实现但 feature-disabled，Phase 15 replay 落地后才启用，使 reminder/escalation/expire events 可回放；snapshot 独立表/FK 可 nullable + backfill 后 deferred 添加 |
| Phase 14 | Demo action executor boundary | Phase 13 | `src/actions/executor.py`；ActionDraftService/prepare；`DraftOutcome` / `draft_outcome` demo status；idempotency hash；action safety snapshot binding | not approved block；demo no side effect；payload/snapshot hash conflict；snapshot revision invalidation；unknown external contract unit tests | demo mode 只创建 durable draft 和 `draft_outcome`，并绑定 exact payload/snapshot hash；不创建 `ActionExecutionResult`、不写 `action_result`、不创建 `action_executions` row；final response 不说真实执行完成 | 可回滚到 existing draft path；external adapter、external outbox 和 dispatch 均非 Phase 14 MVP demo goal；跨 phase FK nullable/backfill/deferred |
| Phase 15 | Replay event contract (Full replay service) | Phase 10, Phase 12, Phase 13, Phase 14 | `src/observability/tracing.py`、`metrics.py`、`replay.py`；ReplayEventV3；operation_id/parent/attempt correlation；`agent_trace_events` migration/backfill；`/replay` API | V3 shape；timeline order；started/terminal operation pairing；retry parent/attempt；backfill stable sequence + unresolved pairing metadata；terminal status completeness；memory write failure；redaction；metrics labels；access control | `/trace` 兼容；`/replay` 返回 V3；normal/interrupted/resumed/responded/rejected/expired/error/cancelled 均可回放；新事件 operation pairing 可验证 | 可回滚到旧 `/trace` timeline；不接完整 Grafana/Loki/Tempo stack；approval/action replay FK 保持 nullable，backfill 后再 deferred 添加 |
| Phase 16 | Long-term/case memory | Phase 12, Phase 15 | long-term/case memory service；review workflow；memory canonical identity；tombstone enforcement；case outcome/source-run idempotency | memory precision/PII/deletion；canonical content/source hash；tombstone no-rewrite；review workflow；case candidate dedupe | 后续 milestone，独立验收；不阻塞 MVP；memory 不作为政策依据 | 可按 memory type 独立回滚；不得影响 session memory fallback |
| Phase 17 | External action execution | Phase 14, Phase 15 | external action adapters；`action_executions` write path；`action_outbox_events`、`action_reconciliation_jobs`、`action_compensation_records` migrations；external dispatch transaction boundary | external timeout unknown/reconciling；outbox claim-before-dispatch；reconciliation no-new-key retry guard；compensation authorization/state；duplicate active execution/key | 后续 milestone，独立验收；external adapter 只能消费 claimed outbox event；生产外部动作需单独安全评审 | 可按 adapter 独立回滚；demo draft path 保持可用 |

Phase sequencing rules：

- Phase 8 和 Phase 9 可并行；Phase 9 business tool results 使用独立 business_fact_refs，不依赖 Phase 8 EvidenceRefV1；Phase 10 必须等两者的 service boundary 明确。
- Phase 11 依赖 Phase 10 的 deterministic routing，否则 intent precedence 无法落地。
- Phase 13/Phase 14 必须先于 Phase 15，否则 replay 无法完整覆盖 approval/action lifecycle。
- Phase 15 依赖 Phase 12，因为 ReplayEventV3 的 MVP lifecycle 包含 `memory_write_failed`。
- Phase 15 does not first define Phase 12-14 event types; Phase 12 owns memory-write additions, Phase 13 owns approval additions, and Phase 14 owns `action_draft_created`, each registered on the Phase 10 envelope/event registry before its emitter is enabled.
- Phase 16 和 Phase 17 不属于 MVP completion gate；两者互不依赖，除非具体 adapter 明确需要 case-memory outcome.

Schema migration ownership：

- Phase 10：minimal event base table（`agent_trace_events` 初始列子集）和 per-run sequence allocator/append API，供 Phase 10-14 emitter 使用。
- Phase 12：session memory tables/migrations，包括 `session_memories.version` CAS；Redis 若引入仅为带 TTL 的非权威 hot cache，不拥有 schema/migration truth。
- Phase 13：approval request/level/assignment/decision/event versioning、`action_safety_snapshots` schema、snapshot JSON/hash 过渡字段、约束和 backfill。
- Phase 14：`action_drafts` version/retention/snapshot binding fields；demo path 不创建或写入 `action_executions` row。
- Phase 15：`agent_trace_events` operation correlation migration/backfill、nullable/deferred FK 和 retention indexes。
- Phase 16：long-term/case memory tables、`memory_tombstones`、memory canonical identity indexes、review workflow indexes。
- Phase 17：`action_executions` external write path、`action_outbox_events`、`action_reconciliation_jobs`、`action_compensation_records` migrations；external dispatch claim/lock indexes；outbox/reconciliation/compensation retention indexes。
- 跨 phase FK 统一采用 nullable column -> deterministic backfill -> deferred nullable FK 策略；无法解析的历史引用保持 null 并记录 migration report，避免 Phase 13/Phase 14/Phase 15 循环依赖。

Migration rollout protocol：

1. Expand：新增 nullable columns/tables/indexes，不改变旧读写路径。
2. Dual-write or adapter-write：新 active records 写入新 contract；旧记录保持只读兼容。若不能 dual-write，必须写 migration report 说明缺口。
3. Backfill：用 deterministic key 回填，记录 `{table, row_count, matched_count, unresolved_count, hash/version}`；无法回填的 approval/action 历史记录必须标记 `non_executable_legacy` 或等价审计状态。
4. Verify：运行 row-count、hash equality、tenant/run ownership、cross-table mismatch negative tests；失败不得进入 read-switch。
5. Read-switch：service 优先读新 contract，旧字段只作为 fallback/source；fallback 命中必须可观测。
6. Enforce：新增 non-null、composite FK、partial unique 或 service-level hard guard；审计保留期内 immutable hash/status 不可原地修改。
7. Cleanup/rollback：cleanup 只能在 fallback 命中为 0 且 migration report 归档后执行；rollback 必须说明新数据是否仍可读、哪些新 records 会保留为 inert/audit-only，且不得删除用户/审批/action 审计事实。

Phase planning traceability requirements：

后续任何 phase planning 都必须先从本 spec 做 coverage extraction，再写 phase plan，最后做 coverage verification。不得只按功能直觉拆分。

本 Section 19 是默认 planning source of truth，但不是免审真理。phase planning 必须把 spec、phase decomposition、当前源码事实和已生成 planning artifacts 做一致性检查；如果发现 Section 19 的 owner、phase boundary、exit criteria、migration/read-switch、eval gate 或命名与其他依据不一致，必须在 phase plan 或 baseline artifact 中显式记录为 `Spec Consistency Findings` / `Planning Deviations`，说明原要求、冲突证据、建议处理、readiness impact 和 owner。不得为了通过检查把不合理或未证实的 target contract 强行标为 `COVERED`；找不到依据写 `MISSING`，只能部分确认写 `PARTIAL`，明确属于后续 owner 写 `DEFERRED_WITH_OWNER`。

每个 phase plan 必须包含：

- `Spec sections covered`：引用章节号/标题，覆盖对应 node、router、state、schema、migration、test、golden case、non-goal。
- `Spec consistency findings`：列出 Section 19、phase decomposition、当前源码事实和 planning artifacts 之间的不一致；无发现时写 `None found after checking <files>`，不能省略。若有发现，必须使用 `docs/agent-architecture-phase-decomposition.md` Section 1 的 Deviation Handling Protocol，至少记录 `ID`、`Source requirement`、`Conflicting evidence`、`Type`、`Recommended handling`、`Readiness impact`、`Owner`、`Status`。
- `Schema/migration owner`：列出 owned tables/columns/indexes/FKs/backfill reports；无 schema 变更时写 `N/A` 和原因；有 read-switch 时必须列出 owner、config/feature flag、fallback telemetry 和 rollback behavior。
- `Service/API owner`：列出 service facade、API/inbox entry、worker 或 adapter；无 API/service 变更时写 `N/A` 和原因。
- `State/router impact`：列出 AgentState fields、router decisions、interrupt/resume path；不适用时写 `N/A`。
- `Required tests`：contract、integration/golden、migration verification、eval gate 中哪些必须随 phase 落地；每个 eval gate 必须标明 `blocking` / `non_blocking`、dataset/version owner 和未通过时的 phase readiness 影响。
- `Acceptance criteria`：必须能被测试或 migration report 验证，不能只写“支持/完成”。
- `Rollback/non-goals/deferred items`：deferred item 必须有 owner phase、why deferred、blocking dependency 和 acceptance gate。

全局 phase plan 必须输出 coverage matrix：

| Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |

`Status` 只能是：

- `COVERED`：本次 phase plan 已覆盖并有验收/测试。
- `PARTIAL`：本次只覆盖一部分，缺口明确且不阻塞当前 phase；必须在 `Gap / owner gate` 写明 non-blocking rationale、owner phase 和 acceptance gate。
- `DEFERRED_WITH_OWNER`：明确延后到某个 owner phase，并写出 gate。
- `MISSING`：没有 owner 或验收；phase plan 不得进入执行，必须先修 plan 或 spec。

Coverage matrix field rules：`Status` 只能使用上述四个枚举；`N/A` 只能出现在 `Migration owner`、`Read-switch / rollback owner`、`Eval gate` 或其他 impact/owner 字段，并且必须说明原因。不得把 `N/A` 当作 `Status`。

Deviation handling rule：phase plan 不负责证明蓝图永远正确，而是负责把蓝图、当前代码和本 phase 可执行计划对齐。发现不一致时，允许继续 planning 的条件是 deviation 已记录、owner/gate 明确、且不影响当前 phase 核心 exit criteria；允许继续 execution 的条件是 deviation 对当前 phase `NON_BLOCKING`、fallback 行为明确、并有测试覆盖实际行为。若 deviation ownerless、影响安全/租户/approval/action/hash/replay 边界、造成 phase dependency 反转/循环、或使 phase 输出与 `docs/contract-spec.md` 矛盾，则 readiness 为 `BLOCKED`，必须先修 plan 或 blueprint。

Coverage matrix 至少覆盖这些 spec areas：AgentState lifecycle、router totality、intent/slot/ordinary clarification、approval `needs_info` resume、EvidenceRefV1/citation/canonical hash、ToolCallContext/ToolResultV2、session memory CAS、long-term/case memory + `memory_identity.v1` + tombstone、approval assignment/SLA/revision invalidation、`action_safety_snapshots` owner、demo action boundary、external action/outbox/reconciliation/compensation、minimal event foundation (Phase 10 emitter/allocator/base table)、ReplayEventV3/finalizer/redaction/retention、cross-table enforcement matrix、migration rollout protocol、contract tests、integration golden flows、eval gates、explicit non-goals、phase planning follow-up register.

Phase decomposition follow-up register：

后续正式 phase decomposition 必须把下列 planning hygiene items 当作 coverage extraction 输入；不得只依赖本次审阅对话记忆。若某项不适用于当前 phase，coverage matrix 的 owner/impact/eval/read-switch 字段可写 `N/A` 并说明原因，但 `Status` 仍必须使用 `COVERED`、`PARTIAL`、`DEFERRED_WITH_OWNER` 或 `MISSING`。

> Canonical source：phase planning follow-up register 的权威版本是 `docs/agent-architecture-phase-decomposition.md` Section 6。该表包含 read-switch type-split 规则（schema-introducing vs service-only）、Phase 13 internal slices（13a/13b/13c）、Deferred memory read seam 等最新条目。本文件不重复维护该表，以免出现 normative 漂移；如需查阅 follow-up items，请以 decomposition Section 6 为准。

Readiness verdict for each phase plan：

- `PASS`：所有 relevant spec areas 为 `COVERED` 或 `DEFERRED_WITH_OWNER`，无 `MISSING`。
- `PARTIAL`：可执行但存在 named gaps，且每个 gap 有 owner phase 和 gate。
- `BLOCKED`：存在 `MISSING` 或 blocker gap；不得执行该 phase。

---
