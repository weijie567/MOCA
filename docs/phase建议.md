  推荐流程

  注意：下面的 `AAM-Px` 是 Agent Architecture Migration workstream 的 phase ID，不是历史 MOCA roadmap/demo phase 编号。使用 GSD 时必须写 `AAM-Px`，不要只写裸 `Phase x`。

  1. 先做 AAM-P1 planning

  在项目根目录 /Users/ming/projects/MOCA，在 Claude Code 里输入：

  /gsd-plan-phase AAM-P1 Contract baseline. Use docs/agent-architecture-spec.md and
  docs/agent-architecture-phase-decomposition.md as the only authoritative planning inputs. Do not
  implement yet. The phase plan must include contract inventory, current-vs-target evidence checklist,
  initial coverage matrix, review checklist, and readiness verdict. It must apply the Phase planning
  follow-up register and mark every applicable item as COVERED, PARTIAL, DEFERRED_WITH_OWNER, or MISSING.

  这是安全的 planning 操作，通常会写 planning artifact，可能会修改文档/计划文件，但不应改源码。

  AAM-P1 的目标不是开发功能，而是把 spec 变成后续开发能消费的 baseline：

  - contract inventory
  - current-vs-target evidence checklist
  - initial coverage matrix
  - review checklist
  - phase readiness verdict

  2. 审阅 AAM-P1 plan，不要立刻执行

  AAM-P1 plan 出来后，你应该要求 Claude/GSD 检查：

  请审核刚生成的 AAM-P1 plan 是否满足 docs/agent-architecture-spec.md 第 19 节和
  docs/agent-architecture-phase-decomposition.md 的 readiness rules。重点检查是否有 MISSING，是否处理了
  Phase planning follow-up register。

  如果有 MISSING，先修 plan，不执行。

  3. 执行 AAM-P1

  确认 AAM-P1 plan 没有 blocker 后，再执行：

  /gsd-execute-phase AAM-P1

  这是会修改文件的操作。它应该主要改 planning/documentation
  artifacts，不应改源码。如果它准备改源码，你要让它解释原因，因为 AAM-P1 在 spec 里是 docs-only。

  4. 验证 AAM-P1

  执行完后用：

  /gsd-verify-work AAM-P1

  或：

  /gsd-validate-phase AAM-P1

  重点看：

  - 是否产出了 contract inventory
  - 是否产出了 current-vs-target evidence checklist
  - 是否产出了 initial coverage matrix
  - 是否所有 MISSING 都被修掉或阻断执行
  - 是否没有把目标 contract 当成已实现事实

  5. 再计划 AAM-P2 和 AAM-P3

  AAM-P1 完成后，可以分别 plan AAM-P2 / AAM-P3。它们可以并行规划，但我建议先分别规划，不要一次合并执行。

  AAM-P2：

  /gsd-plan-phase AAM-P2 Knowledge facade. Use AAM-P1 outputs plus docs/agent-architecture-spec.md and
  docs/agent-architecture-phase-decomposition.md. The plan must cover EvidenceRefV1, citation validation,
  KnowledgeSearchRequest/Result, old src/rag adapter compatibility, read-switch/fallback behavior, RAG
  groundedness/citation eval gate, and whether any persistence is introduced. If persistence is introduced,
  AAM-P2 owns migration/backfill/read-switch; otherwise write N/A with reason.

  AAM-P3：

  /gsd-plan-phase AAM-P3 Business tool facade. Use AAM-P1 outputs plus docs/agent-architecture-spec.md
  and docs/agent-architecture-phase-decomposition.md. The plan must cover ToolCallContext, ToolResultV2,
  permission/scope checks, not_found/timeout/partial_success/invalid_response behavior, old tool
  compatibility, rollback, and whether any audit/cache/mapping persistence is introduced. If persistence is
  introduced, AAM-P3 owns migration/backfill/read-switch; otherwise write N/A with reason.

  6. 每个 phase 都必须过 coverage matrix

  以后每个 phase plan 都必须包含这张结构：

  | Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch /
  rollback owner | Eval gate | Status |
  | --- | --- | --- | --- | --- | --- | --- | --- |

  你要特别盯住：

  - MISSING：不得执行
  - PARTIAL：必须写 owner phase、non-blocking rationale、acceptance gate
  - DEFERRED_WITH_OWNER：必须有明确 owner 和 gate
  - N/A：只能用于 owner/impact/eval/read-switch 字段，不能作为 Status

  GSD 使用边界

  建议用这些命令顺序：

  /gsd-plan-phase ...
  /gsd-validate-phase ...
  /gsd-execute-phase ...
  /gsd-verify-work ...

  不要一上来用：

  /gsd-do 全部 phase
  /gsd-execute-phase all

  这种风险太高。这个项目的 spec 现在有很多 contract、migration、eval、rollback gate，必须逐 phase 走。

  AAM-P7/9 特别注意

  AAM-P7 之前，必须确认 plan 里写清楚：

  - AAM-P7 MVP 是 single-level approval runtime
  - multi-level 是 compatible schema/contract planning，不是 MVP runtime requirement
  - active SLA scanner 是 AAM-P7 follow-up slice
  - SLA scanner 的 gate 是能产生 reminder/escalation/expire events 且进入 replay

  AAM-P9 之前，必须确认 replay gate 覆盖：

  - normal
  - interrupted
  - resumed
  - responded
  - rejected
  - expired
  - error
  - cancelled

  少一个都不该通过 AAM-P9 readiness。

  最短行动建议

  你下一步直接从这个开始：

  /gsd-plan-phase AAM-P1 Contract baseline. Use docs/agent-architecture-spec.md and
  docs/agent-architecture-phase-decomposition.md as the only authoritative planning inputs. Do not
  implement yet. The phase plan must include contract inventory, current-vs-target evidence checklist,
  initial coverage matrix, review checklist, and readiness verdict. It must apply the Phase planning
  follow-up register and mark every applicable item as COVERED, PARTIAL, DEFERRED_WITH_OWNER, or MISSING.

  然后把生成的 AAM-P1 plan 再拿来 review。AAM-P1 过了，再进入 AAM-P2/3。