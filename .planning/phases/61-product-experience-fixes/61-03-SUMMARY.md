---
phase: 61-product-experience-fixes
plan: 03
subsystem: tools-business-metrics
tags: [tool-platform, business-fact-service, metrics, sqlalchemy, trusted-context]

requires:
  - phase: 61-product-experience-fixes
    plan: 02
    provides: metric intent and contract planning used by the runtime tool
provides:
  - trusted metrics:read to tool:query_business_metric permission mapping
  - read-only query_business_metric ToolPlatform descriptor
  - strict business_metric input/result contracts and provenance
  - scoped SQLAlchemy calculations for five MVP business metrics
  - prompt-safe metric projection and investigate accumulation
affects: [phase-61, tool-platform, business-facts, investigate, final-response]

tech-stack:
  added: []
  patterns:
    - fixed SQLAlchemy expression metrics behind BusinessFactService
    - trusted ToolCallContext tenant/merchant scope only
    - prompt-safe metric projection without tenant or merchant identifiers

key-files:
  created:
    - .planning/phases/61-product-experience-fixes/61-03-SUMMARY.md
  modified:
    - src/auth/jwt.py
    - src/auth/permissions.py
    - src/platform/trusted_context.py
    - src/tools/contracts.py
    - src/tools/catalog.py
    - src/tools/policy.py
    - src/tools/projection.py
    - src/tools/executors/business.py
    - src/business/schemas.py
    - src/business/service.py
    - src/agent/nodes/investigate.py
    - src/agent/nodes/investigate_planner.py
    - docs/contract-spec.md
    - tests/integration/test_auth.py
    - tests/platform/test_trusted_context_factory.py
    - tests/business/test_schemas.py
    - tests/business/test_service.py
    - tests/tools/test_catalog.py
    - tests/tools/test_tool_platform.py
    - tests/tools/test_tool_result_storage.py
    - tests/agent/test_nodes/test_investigate.py

key-decisions:
  - "指标计算只接受 ToolCallContext 中的 trusted tenant_id 与 merchant_scope；工具参数不得提供 tenant_id、merchant_scope 或 wildcard 扩权。"
  - "coupon_record_count 只统计 MOCA demo 的 issue_coupon ActionDraft 草稿/记录，并在结果 caveats 中说明不代表外部发券成功。"
  - "merchant_refund_rate 分母为 0 时返回 non_computable，而不是 0%。"
  - "投影层保留指标值与 display_value，但 prompt summary 不输出 tenant_id 或 merchant_id。"

patterns-established:
  - "BusinessFactService 负责业务指标的 scope/no-leak 校验与 ORM 聚合。"
  - "ToolResultProjector 对 business_metric 使用专门的 prompt-safe metric_summary。"
  - "TDD test -> feat commits 按任务切片提交。"

requirements-completed: []

duration: 31min
completed: 2026-07-09
---

# Phase 61 Plan 03: Scoped Business Metric Runtime Summary

**`query_business_metric` 已通过 ToolPlatform 暴露为只读工具，基于 trusted scope 计算五个 MVP 业务指标并输出 prompt-safe metric facts。**

## Performance

- **Duration:** 31min
- **Started:** 2026-07-09T04:02:08Z
- **Completed:** 2026-07-09T04:32:54Z
- **Tasks:** 4/4
- **Files modified:** 21

## Accomplishments

- 增加 `metrics:read` / `tool:query_business_metric` trusted permission 映射与 ToolCatalog 只读 descriptor。
- 增加 strict `BusinessMetricQueryInput` / `BusinessMetricResultV1` contract，并允许 `BusinessFactRefV1.resource_type="business_metric"`。
- 用 SQLAlchemy 表达式实现 `order_count`、`refund_case_count`、`pending_ticket_count`、`coupon_record_count`、`merchant_refund_rate`。
- 指标查询统一从 `ToolCallContext` 派生 tenant/merchant scope；恶意 `tenant_id`、`merchant_scope`、wildcard 工具参数 fail closed。
- 投影层生成简洁 metric prompt summary，investigate 可累积到 `business_context.facts["business_metric"]`。

## Task Commits

1. **Task 1 RED:** `6afa02e` test(61-03): add failing metric tool visibility tests
2. **Task 1 GREEN:** `6002fcf` feat(61-03): add metric tool visibility contract
3. **Task 2 RED:** `e845913` test(61-03): add failing metric result contract tests
4. **Task 2 GREEN:** `aaceac8` feat(61-03): add metric result contract
5. **Task 3 RED:** `3196dc7` test(61-03): add failing metric calculation tests
6. **Task 3 GREEN:** `bd222e7` feat(61-03): implement scoped metric calculations
7. **Task 4 RED:** `760580e` test(61-03): add failing metric projection tests
8. **Task 4 GREEN:** `d45c39c` feat(61-03): project metric tool results safely

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/platform/test_trusted_context_factory.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q --tb=short` -> 128 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_schemas.py tests/business/test_service.py -q --tb=short` -> 75 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py -q --tb=short` -> 49 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py tests/agent/test_nodes/test_investigate.py -q --tb=short` -> 95 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/platform/test_trusted_context_factory.py tests/business/test_schemas.py tests/business/test_service.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py tests/agent/test_nodes/test_investigate.py -q --tb=short` -> 267 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/service.py tests/business/test_service.py` -> passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools/projection.py tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py tests/agent/test_nodes/test_investigate.py` -> passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补上 investigate planner 静态 allowlist**
- **Found during:** Task 1
- **Issue:** Plan 要求 `query_business_metric` 对 investigate 可见，但已有 `_validate_planner_step` 还会用 `INVESTIGATE_ALLOWED_TOOL_NAMES` 做静态拦截；只改 ToolCatalog 会导致工具可见但 planner 不能选择。
- **Fix:** 将 `query_business_metric` 加入 `src/agent/nodes/investigate_planner.py` allowlist，并在 `.planning/ARCHITECTURE-DEBT.md` 记录 ToolCatalog 与 planner 静态 allowlist 的漂移风险。
- **Files modified:** `src/agent/nodes/investigate_planner.py`, `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** Task 1 visibility tests 与最终 267-test suite 通过。
- **Committed in:** `6002fcf`

**2. [Rule 1 - Bug] 修复 visibility decision helper 的 ctx 参数缺失**
- **Found during:** Task 1 本地验证
- **Issue:** `src/tools/policy.py` 的 visibility helper 在新增 metric visibility 分支后引用 `ctx` 但未作为参数传入，导致 visibility tests 失败。
- **Fix:** 最小修改 helper 签名/调用，保留原 runtime auth 语义，并在 `.planning/LOCAL-VALIDATION-ISSUES.md` 记录本地验证事故。
- **Files modified:** `src/tools/policy.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** Task 1 subset 与最终 suite 通过。
- **Committed in:** `6002fcf`

**Total deviations:** 2 auto-fixed
**Impact on plan:** 两项均为完成计划目标所需的正确性修复，无新增产品范围。

## Known Stubs

None. Stub scan only found existing empty-list/default-container patterns in tests and safe-result constructors; no created/modified production stub blocks this plan.

## Threat Flags

None. New security-relevant surfaces match the plan threat model: trusted scope -> metric tool permission, schema-validated tool args, SQLAlchemy-only DB reads, and prompt-safe projection.

## Issues Encountered

- Task 3 RED helper 最初未 flush `AgentRun` 就创建 `ActionDraft`，触发 FK failure；已在 RED 测试提交前修正 helper，使失败点回到预期的 `NotImplementedError`。
- Ruff 发现 Task 3 RED 测试中 `RefundCase` / `Ticket` 未使用 import；GREEN commit 中删除，验证通过。

## User Setup Required

None - no external service configuration required.

## State Update Note

按用户明确要求，本计划未修改 `.planning/ROADMAP.md`、`.planning/STATE.md` 或 `.planning/autopilot/phase-61.md`。

## Next Phase Readiness

- `query_business_metric` 已可被 trusted investigate flow 调用，并能提供 typed metric fact refs。
- 61-04/61-05 可基于 `business_context.facts["business_metric"]` 做 final response/UX 验证；本执行未触碰 61-04 或 61-05。

## Self-Check: PASSED

- Summary file exists: `.planning/phases/61-product-experience-fixes/61-03-SUMMARY.md`
- Commits found: `6afa02e`, `6002fcf`, `e845913`, `aaceac8`, `3196dc7`, `bd222e7`, `760580e`, `d45c39c`

---
*Phase: 61-product-experience-fixes*
*Completed: 2026-07-09*
