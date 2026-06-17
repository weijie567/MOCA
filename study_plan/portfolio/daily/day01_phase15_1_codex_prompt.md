# Day 1 · Phase 15.1 GSD 启动材料

> 当前仓库事实：`.planning/ROADMAP.md` 显示 Phase 14 和 Phase 15 已完成，Phase 15.1 Memory Foundation V2 已插入但还没有计划。Day 1 不再启动 Phase 14，而是先内化 Phase 14/15，并准备 Phase 15.1 的 plan 入口。

## 目标

为 Phase 15.1 生成 plan 前置材料：只做上下文整理，不直接写代码。

## 必读文件

- `.planning/ROADMAP.md`
- `README.md`
- `TOOL_ARCHITECTURE.md`
- `docs/current-implementation-map.md`
- `docs/general_assistant_memory_design.md`
- `docs/business_agent_memory_design.md`
- `.planning/phases/15.1-memory-foundation-v2/`（如已有内容，必须先读）

## 待确认问题

1. Phase 15.1 的边界是不是只做 conversation log、tool call/result storage、WorkingStateV1、thread summary、ContextAssembler 和 token budget？
2. 哪些内容必须明确不做，留给 Phase 16 long-term / case memory？
3. Phase 15.1 和已有 Phase 12 session memory、Phase 15 replay event contract 的边界怎么切？
4. trace/audit/conversation/thread/run ID 的关系是否已经有 normative source？

## 建议给 Codex/GSD 的启动语句

```text
请基于当前 MOCA 仓库，为 Phase 15.1 Memory Foundation V2 走 gsd-plan-phase。
要求先核对 .planning/ROADMAP.md、README.md、TOOL_ARCHITECTURE.md、docs/current-implementation-map.md、
docs/general_assistant_memory_design.md、docs/business_agent_memory_design.md 和已有
.planning/phases/15.1-memory-foundation-v2/ 内容。

目标是生成 PLAN.md，不直接写代码。必须明确 Phase 15.1 与 Phase 12 session memory、Phase 15 replay、
Phase 16 long-term/case memory 的非重叠边界，并给出测试与验收门槛。
```

## 当前边界

- Phase 14/15 已完成，不重复计划。
- Phase 16/17 仍 defer，不在 Day 1 开始实现。
- 这里只准备 plan，不做 schema/migration/code。

