# Phase 24: Agent Runs Short-term Memory Parity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `24-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-20T19:35:01+08:00  
**Phase:** 24-agent-runs-short-term-memory-parity  
**Mode:** discuss fallback defaults  
**Reason:** `request_user_input` was unavailable in Codex Default mode, so the workflow fallback selected recommended defaults.

---

## `/agent-runs` User Message Timing

| Option | Description | Selected |
|--------|-------------|----------|
| CreateRun 时 | POST 创建 run 时就写 exactly one user message，SSE 重连/重复打开不会重复写。 | Yes |
| SSE claim 时 | 只有真正开始执行时才写 user message，但需要额外处理 claim 后失败和重连幂等。 | |
| 完成后再写 | 避免 pending run 留消息，但工具记录和 graph config 很难拿到可信 conversation_message_id。 | |

**Selected default:** CreateRun 时.  
**Notes:** This matches the run creation boundary and gives graph execution a stable conversation identity to reuse.

---

## Prompt Context Scope

| Option | Description | Selected |
|--------|-------------|----------|
| 全量短期栈 | 同时加载 trusted session slots、recent messages、tool prompt summaries、latest prior rolling summary，但只作为上下文。 | Yes |
| 只接 slots | 只修复订单号等 slot continuity，rolling summary 和 recent messages 暂时不进当前主路径。 | |
| 保守开关 | 实现全量栈但默认只开 slots，其余通过配置或测试环境开启。 | |

**Selected default:** 全量短期栈.  
**Notes:** Full short-term stack is the milestone goal, but it remains contextual only and cannot replace policy evidence, current business facts, approval/action authority, or replay truth.

---

## Terminal and Failure Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| 完成才总结 | completed 才写 assistant message、rolling summary、bounded session memory；error/interrupted/cancelled 不写假完成总结。 | Yes |
| 错误也进对话 | error/cancelled 也写 assistant 错误消息，用户聊天历史会完整但可能污染 rolling summary。 | |
| 中断也总结 | interrupted 写等待审批 summary，便于恢复但需要更强边界避免被当成完成回答。 | |

**Selected default:** 完成才总结.  
**Notes:** Error, cancelled, and interrupted states remain visible through run/trace/approval surfaces, not false completed assistant messages or rolling summaries.

---

## the agent's Discretion

- Exact helper names, idempotency keys, and repository method names are left to the planner.
- The planner may choose whether terminal persistence is represented as explicit SSE timeline nodes or backend-only, as long as timeline statuses remain truthful.

## Deferred Ideas

- Full memory management UI.
- Retention/deletion controls.
- Admin promotion workflow for reviewed long-term/case memory.
- Full SSE event replay/reconnect UX beyond no-duplicate execution/write semantics.
