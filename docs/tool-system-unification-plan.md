# MOCA Unified Tool System Refactor Plan

本文件是执行前审核稿，不包含实现代码。目标是不再按“最小改动”迁就旧结构，而是把 MOCA 的工具系统重构成清晰、单一入口、边界稳定的架构。

## 目标判断

当前代码已经朝统一工具系统收敛，但仍处于中间态：

- `src/agent/tools/unified.py` 已承担主要 manager 职责，但还和 executor、action adapter、catalog lookup 混在一个文件里。
- `src/business_tools/registry.py` 暂时是 catalog 兼容层，但命名仍像 business-only registry。
- `ToolCallContext` / `ToolResultV2` 放在 `src/business_tools/schemas.py`，导致通用工具契约依赖 business 包。
- Knowledge/RAG 同时存在 `investigate -> UnifiedToolManager` 和 `retrieve_policy_evidence -> PolicyKnowledgeService` 两条 graph-facing 路径。
- Memory 中 session memory 已有真实 service/repository，`search_case_memory` 已通过 `MemoryToolExecutor -> CaseMemorySearchService -> SessionMemoryRepository` 检索历史 session memory。
- 旧 `src/agent/tools/*` compatibility path 已删除；生产和测试代码应使用 `src.tools` 与 domain packages。

最终目标：

```text
Graph node
  -> src.tools.manager.UnifiedToolManager.invoke(tool_name, args, context)
    -> src.tools.catalog.ToolCatalog descriptor lookup
    -> common validation: caller, permission, exposure, schema, side-effect, approval, idempotency
    -> src.tools.executors.<domain> executor
      -> domain service
        -> adapter / repository / integration
```

原则：

- Graph node 不直接 import raw adapter / repository / domain service，除非该 node 是明确的 deterministic domain node 且不属于 graph-facing tool capability。
- 所有 planner-visible 和 node-only tool call 都走 `UnifiedToolManager`。
- Domain service 不做 caller allowlist、tool permission、catalog schema、planner exposure 校验。
- Domain service 继续保留领域安全：merchant ownership、tenant scope、business state constraints、PII/memory policy、retrieval evidence policy。
- Raw adapter / repository 不知道 agent caller，不发 trace，不暴露 raw exception / prompt / raw args / 未脱敏 payload。

## Claude Review Disposition

已采纳并进入本计划：

- 统一 catalog 不等于统一暴露给模型：`ToolCatalog` 保存全量 descriptor，`UnifiedToolManager.descriptors(caller)` 只派生 caller-specific capability view。
- `UnifiedToolManager -> ToolCatalog -> domain executor -> domain service -> adapter/repository` 是目标链路；executor 保持薄，manager 不懂业务，service 不懂 agent caller。
- `BusinessToolService` 不再承担 descriptor lookup、caller allowlist、`tool:*` permission、input/output schema 等 agent-facing 校验；这些统一放在 `UnifiedToolManager` / `ToolCatalog`。
- catalog descriptor 必须表达可见性和安全边界：`exposure`、`caller_allowlist`、`required_permission`、`side_effect`、`requires_approval`、`requires_safety_snapshot`、`requires_idempotency_key`。
- planner-visible、node-only、internal capability 可以同处一个 catalog，但 planner view 只能看到 planner-visible read/retrieval tools；`create_coupon_grant_draft` 这类 action 只能走 node-only caller。
- 迁移顺序先保证 `execute_action` 通过 manager 调 action，再逐步禁止 graph node 直连 raw adapter；否则静态边界测试会先卡住现有代码。
- `ToolResult` / trace / user-visible state 不得包含 raw exception、raw args、prompt 或未脱敏 payload；原始异常只允许进内部日志或 audit reference。
- Knowledge/RAG 也应纳入统一工具入口：`search_policy` 走 manager -> knowledge executor -> `PolicyKnowledgeService` -> retrieval engine，而不是保留多条 graph-facing retrieval path。
- Memory 拆成两类：session memory lifecycle 保持 deterministic node + `MemoryService`；case/long-term memory search 作为 planner-visible retrieval tool 接入 manager。
- 后续增加静态边界测试，防止 graph node 直接 import raw adapter / repository，防止 manager 反向 import domain service。

暂不采纳或延后：

- 暂不立即拆分 `ToolCallContext` 为 trusted identity / safety context / execution context。当前字段已经被 manager 强制校验，先通过包边界和 executor 拆分降低复杂度；等 action、memory 写能力更多时再拆。
- 暂不把 `output_schema` 改成 `result_contract_version + typed refs`。当前 manager 已做输出 schema 校验，短期继续使用 schema 约束；如果 schema 继续保持 generic object，再在后续 phase 简化为 contract version。
- 暂不优先重命名 `event_family` 为 enum；这属于 trace/event contract 清理，等 raw adapter 迁移和 safe error 边界稳定后再统一改。

## 目标目录

建议目标结构：

```text
src/tools/
  __init__.py
  contracts.py
  catalog.py
  manager.py
  errors.py
  validation.py
  executors/
    __init__.py
    business.py
    knowledge.py
    memory.py
    action.py

src/business/
  __init__.py
  schemas.py
  service.py
  adapters.py

src/knowledge/
  __init__.py
  schemas.py
  service.py
  retrieval.py
  repository_adapter.py
  citation.py
  text_hash.py
  config.py

src/memory/
  __init__.py
  schemas.py
  service.py
  repository.py
  search.py              # future case/long-term memory search, initially unavailable or empty

src/actions/
  __init__.py
  schemas.py
  service.py
  drafts.py

src/integrations/
  demo_business/
    orders.py
    refunds.py
    tickets.py
```

Notes:

- `src/rag/embedder.py`, `src/rag/chunker.py`, and ingestion code can remain low-level infrastructure if they are shared.
- The retrieval/rerank algorithm for policy evidence should move behind a public `src/knowledge/retrieval.py` API. Knowledge code should not import private helpers from `src/rag/retriever.py`.
- If `src/business_tools` cannot be renamed in one step, keep compatibility import modules temporarily, but new code should target `src/business`.

## Current Code Mapping

### Tools

Current:

- `src/agent/tools/unified.py`
- `src/business_tools/registry.py`
- `src/business_tools/schemas.py`
- `src/agent/tools/contracts.py`
- `src/agent/tools/registry.py`
- `src/agent/tools/adapters.py`

Target:

- `src/tools/contracts.py`
  - `ToolDescriptor`
  - `ToolCallContext`
  - `ToolRequest`
  - `ToolError`
  - `ToolResult`
  - `BusinessFactRef`
  - tool status literals
- `src/tools/catalog.py`
  - all descriptors
  - `ToolCatalog.descriptor(name)`
  - `ToolCatalog.descriptors_for(caller)`
  - no adapter map
  - no execution
- `src/tools/manager.py`
  - `UnifiedToolManager`
  - executor registry keyed by `descriptor.executor`
- `src/tools/validation.py`
  - JSON schema subset validation or replace with a standard validator if desired
- `src/tools/executors/*`
  - one executor per domain

Delete after migration:

- `src/agent/tools/contracts.py`
- `src/agent/tools/registry.py`
- `src/agent/tools/adapters.py`

### Business

Current:

- `src/business_tools/service.py`
- `src/business_tools/adapters.py`
- `src/business_tools/schemas.py`
- `src/agent/tools/get_order.py`
- `src/agent/tools/get_refund_case.py`
- `src/agent/tools/get_ticket.py`

Target:

- `src/business/service.py`
  - business read aggregation and merchant scope / ownership logic
  - no agent-facing permission or schema checks
- `src/business/adapters.py`
  - typed projection from raw business data into `ToolResult`
- `src/integrations/demo_business/orders.py`
  - raw DB read formerly `src/agent/tools/get_order.py`
- `src/integrations/demo_business/refunds.py`
  - raw DB read formerly `src/agent/tools/get_refund_case.py`
- `src/integrations/demo_business/tickets.py`
  - raw DB read formerly `src/agent/tools/get_ticket.py`

Keep service capabilities:

- `get_order`
- `get_refund_case`
- `get_ticket`
- `fetch_context`
- merchant scope / ownership safety
- retry over retryable adapter results

Do not keep in business service:

- caller allowlist
- `tool:*` permission
- descriptor lookup
- catalog input/output schema validation

### Knowledge/RAG

Current:

- `src/knowledge/service.py`
- `src/knowledge/adapters.py`
- `src/knowledge/schemas.py`
- `src/rag/retriever.py`
- `src/agent/nodes/retrieve_policy_evidence.py`
- `src/tools/executors/knowledge.py`
- `src/api/routers/search.py` direct `PolicyRetrievalEngine` HTTP path

Target:

```text
UnifiedToolManager.invoke("search_policy")
  -> KnowledgeToolExecutor
    -> PolicyKnowledgeService.search()
      -> PolicyRetrievalEngine.retrieve()
        -> PolicyChunkRepository + EmbeddingService
```

Concrete changes:

- Create `src/knowledge/retrieval.py`
  - public `PolicyRetrievalEngine`
  - owns thresholds, query prefix, rerank, domain anchors, overlap logic
  - returns typed retrieval records / evidence candidates
- Replace `LegacyRagKnowledgeAdapter` with a clearly named adapter or remove it:
  - preferred: `PolicyKnowledgeService` depends directly on `PolicyRetrievalEngine`
  - acceptable transitional name: `PolicySearchRepositoryAdapter`
- Remove `src/agent/tools/search_policy.py`.
- Remove `legacy_search_policy` export from `src/knowledge/adapters.py`.
- Convert or delete `src/rag/retriever.py`:
  - if kept, it must expose public functions/classes only
  - no domain code should import underscore-private helpers
- Convert `retrieve_policy_evidence`:
  - short-term: thin wrapper node that builds `ToolCallContext` and calls manager
  - preferred final: remove graph node if `investigate` fully owns policy retrieval

Catalog stance:

- `search_policy`
  - `capability_type`: knowledge
  - `operation`: search
  - `side_effect`: retrieval
  - `exposure`: planner_visible
  - `caller_allowlist`: `["investigate"]`
  - optionally temporary `["investigate", "retrieve_policy_evidence"]` during migration only
- `search_sop`
  - keep declared
  - executor returns `unavailable` until SOP corpus/retriever exists

### Memory

Current:

- `src/memory/service.py`
  - real session memory load/write service
  - TTL checks
  - CAS merge
  - PII skip/fallback behavior
- `src/memory/repository.py`
  - `SessionMemoryRepository`
- `src/memory/schemas.py`
  - `SessionMemoryView`
  - `SessionMemoryWriteCandidate`
  - `SessionMemoryWriteResult`
  - `SessionSlotV1`
  - `SessionSlotsEnvelopeV1`
- `src/agent/nodes/session_memory_load.py`
  - direct deterministic MemoryService call
- `src/agent/nodes/memory_write.py`
  - direct deterministic MemoryService call
- `src/agent/nodes/long_term_memory_retrieve.py`
  - empty adapter, sets `long_term_memory=[]`, `case_memory=[]`
- `search_case_memory`
  - descriptor exists, `MemoryToolExecutor` calls `CaseMemorySearchService`
  - uses existing `session_memories` storage with tenant/user scope, deleted/expired filtering, and safe projection

Recommended target:

Keep two separate memory concepts:

1. Session memory lifecycle
   - deterministic graph nodes:
     - `session_memory_load`
     - `memory_write`
   - domain owner:
     - `MemoryService`
   - repository:
     - `SessionMemoryRepository`
   - these do not need to become planner-visible tools
   - they can optionally use node-only tools later, but the current deterministic nodes are acceptable and clearer

2. Searchable case/long-term memory
   - planner-visible tool:
     - `search_case_memory`
   - executor:
     - `MemoryToolExecutor`
   - domain owner:
     - future `CaseMemorySearchService` or `MemorySearchService`
  - current implementation:
    - searches existing session memory records for relevant prior case context

Recommended cleanup:

- Keep `session_memory_load.py` direct to `MemoryService` because it is deterministic pre-tool context load, not planner-selected capability.
- Keep `memory_write.py` direct to `MemoryService` for now because it is deterministic post-response persistence with PII policy and timeout behavior.
- Do not expose `write_session_memory` to planner.
- Add a node-only catalog entry later only if another graph node needs manager-enforced idempotency/permission for memory writes.
- Replace `long_term_memory_retrieve.py` with manager-backed `search_case_memory` in a later graph simplification phase if the empty adapter is no longer useful.

This keeps memory clear:

```text
session memory = deterministic continuity state
case memory search = planner-visible retrieval capability
```

### Actions

Current:

- `src/agent/nodes/execute_action.py`
- `src/agent/tools/create_coupon_grant_draft.py`
- `ActionToolExecutor` inside `src/agent/tools/unified.py`
- `src/repositories/action_draft_repo.py`

Target:

- `src/actions/service.py`
  - action draft / execute semantics
  - idempotency semantics
  - safe errors
- `src/actions/drafts.py`
  - draft persistence adapter around `ActionDraftRepository`
- `src/tools/executors/action.py`
  - maps `ToolCallContext + args` to `ActionService`
- `execute_action.py`
  - deterministic graph node
  - builds tool context
  - calls `UnifiedToolManager.invoke("create_coupon_grant_draft", ...)`
  - never imports raw action adapter

Catalog stance:

- `create_coupon_grant_draft`
  - `exposure`: node_only
  - `caller_allowlist`: `["execute_action"]`
  - `requires_idempotency_key`: true
  - approval/safety snapshot flags should be true once approval path consistently provides them

## Refactor Phases

当前执行状态：

- Phase 1 已开始落地：新增 `src/tools/contracts.py`、`src/tools/catalog.py`、`src/tools/manager.py`、`src/tools/validation.py`，旧 `business_tools.schemas` / `business_tools.registry` 改为兼容导出。
- Phase 2 已开始落地：新增 `src/tools/executors/{business,knowledge,memory,action}.py`，生产节点开始从 `src.tools` 导入 manager/contracts。
- Phase 3 已落地：新增 `src/business/{service,adapters,schemas}.py` 和 `src/integrations/demo_business/*`，`BusinessToolExecutor` / `load_business_context` 已改用 `src.business`，旧 `business_tools` 保留兼容导出，`src.agent.tools.get_*` wrapper 已删除。
- Phase 4 已落地：新增 `src/knowledge/retrieval.py`，`KnowledgeToolExecutor` 默认使用 `PolicyRetrievalEngine -> PolicyKnowledgeService`，`retrieve_policy_evidence` 改为 `UnifiedToolManager.invoke("search_policy")` wrapper，API search endpoint 已直接切到 `PolicyRetrievalEngine` 并保持 HTTP response contract。
- Phase 5 已落地：新增真实 `src/memory/search.py` 和 `CaseMemorySearchResult` / `CaseMemorySearchItem`，`MemoryToolExecutor` 调 `CaseMemorySearchService` 检索 `session_memories`。
- Phase 6 已落地：新增 `src/actions/{service,drafts,schemas}.py`，`ActionToolExecutor` 直连 `ActionService`，旧 `src.agent.tools.create_coupon_grant_draft` wrapper 已删除。
- Phase 8 已开始落地：新增 `tests/architecture/test_tool_boundaries.py`，先锁住 graph node 不再 import legacy agent tools/raw integrations、manager 不直接 import domain service、domain package 不反向 import graph/manager。
- Phase 7 已落地：legacy `src/agent/tools/*` 和旧 API 测试已删除，`rg "src.agent.tools" src tests` 不应出现生产/测试依赖。
- Citation content re-fetch 已收进 `PolicyKnowledgeService.get_verified_evidence_contents(...)`；`generate_recommendation` 不再直接 import `PolicyChunkRepository`。

### Phase 1: Extract Neutral Tool Package

Goal: move generic contracts and manager out of `agent` and `business_tools`.

Operations:

- Add `src/tools/contracts.py`.
- Move/copy from `src/business_tools/schemas.py`:
  - `ToolCallContext`
  - `ToolRequest`
  - `ToolError`
  - `ToolResultV2` renamed to `ToolResult`
  - `BusinessFactRefV1` can stay if used by business, or move to `src/tools/contracts.py` if `ToolResult` embeds it.
- Add compatibility aliases:
  - `src/business_tools/schemas.py` re-exports from `src/tools/contracts.py` temporarily.
- Add `src/tools/catalog.py`.
- Move `ToolDescriptor`, descriptor construction, and schema helper out of `src/business_tools/registry.py`.
- Keep `src/business_tools/registry.py` as compatibility import only, then delete in a later phase.
- Add `src/tools/manager.py`.
- Move `UnifiedToolManager` out of `src/agent/tools/unified.py`.

Tests:

- `tests/tools/test_catalog.py`
- `tests/tools/test_manager.py`
- update existing imports gradually.

Acceptance:

- No code outside `src/tools` imports `ToolDescriptor` from `src/business_tools.registry`.
- No code outside compatibility modules imports `ToolCallContext` from `src.business_tools.schemas`.

### Phase 2: Split Executors

Goal: remove executor classes from the manager file.

Operations:

- Add:
  - `src/tools/executors/business.py`
  - `src/tools/executors/knowledge.py`
  - `src/tools/executors/memory.py`
  - `src/tools/executors/action.py`
- `UnifiedToolManager` receives an executor registry:

```python
executors = {
    "business": BusinessToolExecutor(...),
    "knowledge": KnowledgeToolExecutor(...),
    "memory": MemoryToolExecutor(...),
    "action": ActionToolExecutor(...),
}
```

- Dispatch by `descriptor.executor`, not by scanning `executor.get_tools()`.
- Executors no longer need to duplicate descriptor lists.

Acceptance:

- Adding a tool only requires catalog descriptor + executor implementation.
- Manager does not import domain services directly.
- Manager does not know business/knowledge/memory/action internals.

### Phase 3: Rename Business Package and Move Raw Reads

Goal: remove `agent.tools` raw business functions and clarify business ownership.

Operations:

- Create `src/business/` package.
- Move:
  - `src/business_tools/service.py` -> `src/business/service.py`
  - `src/business_tools/adapters.py` -> `src/business/adapters.py`
  - business-specific schemas if any -> `src/business/schemas.py`
- Move raw DB reads:
  - `src/agent/tools/get_order.py` -> `src/integrations/demo_business/orders.py`
  - `src/agent/tools/get_refund_case.py` -> `src/integrations/demo_business/refunds.py`
  - `src/agent/tools/get_ticket.py` -> `src/integrations/demo_business/tickets.py`
- Leave compatibility imports during transition if needed.

Acceptance:

- `src/agent/nodes/*` does not import `src.agent.tools.get_*`.
- `src/business` does not import `src.agent.tools.adapters`.
- Raw business data access lives under `src/integrations/demo_business` or repositories.

Current migration note:

- `src/business/service.py`, `src/business/adapters.py`, and `src/business/schemas.py` are the production business package.
- `src/integrations/demo_business/{orders,refunds,tickets,authz}.py` owns demo DB reads and merchant ownership checks.
- `src/business_tools/{service,adapters,schemas}.py` remain compatibility exports.
- `src/agent/tools/{get_order,get_refund_case,get_ticket,authz}.py` compatibility wrappers have been deleted.

### Phase 4: Rebuild Knowledge/RAG Around One Public Retrieval Engine

Goal: eliminate duplicated policy search paths and private helper coupling.

Operations:

- Add `src/knowledge/retrieval.py` with `PolicyRetrievalEngine`.
- Move retrieval constants/helpers from `src/rag/retriever.py` into public knowledge-owned functions/classes.
- Update `PolicyKnowledgeService` to depend on a retrieval protocol implemented by `PolicyRetrievalEngine`.
- Remove `LegacyRagKnowledgeAdapter` or rename it if still needed.
- Delete `src/agent/tools/search_policy.py`.
- Delete policy pieces from `src/agent/tools/adapters.py`.
- Convert `retrieve_policy_evidence.py`:
  - Option A: remove from graph if `investigate` replaces it fully.
  - Option B: temporary wrapper that calls `UnifiedToolManager.invoke("search_policy", ...)`.
- Update ownership tests to assert manager path:
  - graph node calls manager
  - `KnowledgeToolExecutor` calls `PolicyKnowledgeService`
  - no graph node imports `PolicyKnowledgeService` directly

Acceptance:

- Exactly one production path for `search_policy`.
- No graph-facing production import of `src.agent.tools.search_policy`.
- No knowledge service import of underscore-private `src.rag.retriever` helpers.

Current migration note:

- `src.agent.nodes.retrieve_policy_evidence` is now a compatibility wrapper over `UnifiedToolManager`.
- `src.knowledge.adapters.LegacyRagKnowledgeAdapter` remains only as a compatibility alias to `PolicyRetrievalEngine`.
- `src.agent.tools.search_policy`, `src.agent.tools.adapters`, and `src.agent.tools.registry` have been deleted.
- `src.api.routers.search` now uses `PolicyRetrievalEngine.retrieve_hits(...)` directly while preserving the legacy `RetrievalResult` HTTP contract.
- `src.rag.retriever.Retriever` remains only as a compatibility facade over `PolicyRetrievalEngine`, not as a second retrieval implementation.

### Phase 5: Clarify Memory Integration

Goal: keep deterministic session memory clean while preparing searchable memory as a real tool.

Operations:

- Leave `MemoryService`, `SessionMemoryRepository`, and session memory schemas in `src/memory`.
- Keep `session_memory_load.py` as deterministic node, direct service call.
- Keep `memory_write.py` as deterministic post-response persistence node, direct service call.
- Add `src/memory/search.py` with placeholder `CaseMemorySearchService` interface:
  - initially returns unavailable/empty in a typed way
  - later can use embeddings or session history store
- Update `MemoryToolExecutor` to call `CaseMemorySearchService` for `search_case_memory`.
- Keep `long_term_memory_retrieve.py` as empty adapter until replaced by real case-memory search.

Acceptance:

- Planner-visible `search_case_memory` only reads/searches; it never writes session memory.
- `memory_write` is never planner-visible.
- Session memory load/write behavior and existing CAS/TTL/PII tests continue to pass.

Current migration note:

- `src/memory/search.py` now provides `CaseMemorySearchService`.
- `MemoryToolExecutor` calls `CaseMemorySearchService.search(...)` with a `SessionMemoryRepository` built from the manager session.
- `CaseMemorySearchService` searches existing `session_memories` by tenant/user scope and projects bounded, structured case memory items. No session memory write path was changed.

### Phase 6: Move Actions Into Domain Package

Goal: remove raw action adapter from `src/agent/tools`.

Operations:

- Create:
  - `src/actions/service.py`
  - `src/actions/drafts.py`
  - `src/actions/schemas.py`
- Move `create_coupon_grant_draft` logic into action service/draft adapter.
- Update `ActionToolExecutor` to call `ActionService`.
- Delete `src/agent/tools/create_coupon_grant_draft.py` after tests migrate.

Acceptance:

- `execute_action.py` imports only `UnifiedToolManager` and tool contracts.
- Raw action draft persistence lives under `src/actions` and repository.
- Raw exception never appears in `action_result`, trace event, or `ToolResult`.

Current migration note:

- `src/actions/service.py` owns UUID validation, idempotency conflict mapping, safe action errors, and draft transaction handling.
- `src/actions/drafts.py` wraps `ActionDraftRepository`.
- `src/tools/executors/action.py` calls `ActionService` directly.
- `src/agent/tools/create_coupon_grant_draft.py` compatibility wrapper has been deleted.

### Phase 7: Delete Legacy Agent Tools

Goal: remove the old tool system entirely.

Delete:

- `src/agent/tools/contracts.py`
- `src/agent/tools/registry.py`
- `src/agent/tools/adapters.py`
- `src/agent/tools/search_policy.py`
- `src/agent/tools/get_order.py`
- `src/agent/tools/get_refund_case.py`
- `src/agent/tools/get_ticket.py`
- `src/agent/tools/create_coupon_grant_draft.py`
- `src/agent/tools/unified.py` after compatibility import points to `src/tools/manager.py`

Acceptance:

- `rg "src.agent.tools" src tests` shows only compatibility tests or no results.
- Graph-facing capability tests use `src.tools`.

### Phase 8: Static Boundary Tests

Goal: keep architecture from regressing.

Add tests:

- `tests/architecture/test_tool_boundaries.py`
  - graph nodes may import `src.tools.*`
  - graph nodes may not import raw adapters / repositories
  - `src.tools.manager` may not import domain services directly
  - `src.tools.executors.*` may import domain services
  - domain services may not import graph nodes or manager
- `tests/tools/test_catalog_views.py`
  - investigate planner view excludes action write tools
  - execute_action node-only view excludes planner-visible read/search tools
  - memory_write, if added, is node-only
- `tests/tools/test_safe_errors.py`
  - invalid input/missing permission/caller blocked never includes raw args
  - executor exceptions return safe `ToolResult`

Current migration note:

- Added `tests/architecture/test_tool_boundaries.py`.
- Current enforced checks:
  - graph nodes do not import `src.agent.tools` or `src.integrations`
  - `src.tools.manager` does not directly import domain services
  - domain packages do not import graph nodes or `src.tools.manager`
- `generate_recommendation` citation text re-fetch now goes through `PolicyKnowledgeService`; repository imports from graph nodes can be tightened in a later static boundary pass.

## Suggested Execution Order

Recommended order for actual implementation:

1. Extract `src/tools/contracts.py`, `catalog.py`, `manager.py` with compatibility re-exports.
2. Split executors from `src/agent/tools/unified.py`.
3. Convert imports in graph nodes and tests to `src.tools`.
4. Move business package and raw business reads.
5. Convert knowledge/RAG to single manager path and retrieval engine.
6. Add memory search service placeholder and wire `search_case_memory`.
7. Move action draft logic to `src/actions`.
8. Delete old `src/agent/tools/*`.
9. Add static boundary tests.

This order keeps the system testable after every phase.

## Test Plan

Run after each phase:

```bash
uv run ruff check src tests
uv run pytest tests/tools tests/business_tools tests/knowledge tests/memory tests/agent/test_nodes tests/test_execute_action.py -q --tb=short
```

Run integration tests when touching repositories, DB models, or memory persistence:

```bash
uv run pytest tests/integration tests/agent/test_session_memory_integration.py tests/memory -q --tb=short
```

Specific regression targets:

- Manager rejects missing permission before executor call.
- Manager rejects invalid input before executor call.
- Manager validates executor output schema.
- Business service does not repeat agent-facing permission/schema/caller checks.
- Business retry still works.
- `fetch_context` still aggregates order/refund/ticket.
- Knowledge search still produces `EvidenceRefV1`.
- Knowledge/RAG errors return safe `ToolResult`.
- Session memory load respects tenant/user/thread/freshness/intent compatibility.
- Memory write preserves TTL, CAS merge, PII skip, timeout fallback.
- `search_case_memory` remains read-only and unavailable until implemented.
- Action draft requires node-only caller and idempotency key.

## Open Decisions For Review

1. Rename `src/business_tools` to `src/business` now, or keep compatibility package for one milestone?
2. Remove `retrieve_policy_evidence` node entirely, or temporarily convert it to a manager wrapper?
3. Keep `src/rag` as low-level embedding/chunking package, or merge all policy retrieval code under `src/knowledge`?
4. Should `memory_write` become node-only tool-managed capability, or remain deterministic node calling `MemoryService` directly?
5. Should `ToolResultV2` be renamed to `ToolResult` immediately, or kept as alias until API/tests migrate?

Recommended answers:

- Rename to `src/business` with compatibility re-exports.
- Remove `retrieve_policy_evidence` if graph already routes policy retrieval through `investigate`; otherwise wrapper for one migration phase.
- Keep `src/rag` for low-level embed/chunk/ingest only; move policy retrieval orchestration to `src/knowledge/retrieval.py`.
- Keep `memory_write` deterministic for now; only `search_case_memory` is planner-visible memory tool.
- Rename to `ToolResult`, keep `ToolResultV2 = ToolResult` alias for one phase.
