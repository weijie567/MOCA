# MOCA Agent 架构 Spec

> 状态：实现规划基线 spec。本文定义目标架构/contract，不表示目标已实现，也不要求立即实现代码。
>
> 依据来源：当前 MOCA 仓库代码与文档、`docs/agent-architecture-reference-draft.md`、本地参考仓库代码级检查。
>
> 重要边界：本文不会把参考仓库能力写成 MOCA 已实现；不会把目标架构写成当前事实；不会建议照抄参考仓库目录、代码或业务假设。

## Reading order & authority

1. `docs/architecture-overview.md` for orientation.
2. `docs/target-agent-platform-architecture-plan.md` §6.1 for the readable target canonical runtime graph.
3. `docs/contract-spec.md` is the primary accepted contract reference; if it conflicts with source code, tests, product judgment, or target-plan deltas, the next phase must record a spec delta / MVP scope / deferral before implementation.
4. `docs/agent-architecture-phase-decomposition.md` is the historical phase/owner decomposition.
5. `docs/migration-plan.md` defines rollout/process.
6. `docs/eval-test-plan.md` defines tests/golden cases.
7. `.planning/` artifacts record phase state and may supersede older planning text when they explicitly name the conflict and owner.

---

This file has been split. Use the table below to locate old section-number references in the new files. For current Agent Graph target shape, use `docs/target-agent-platform-architecture-plan.md` §6.1 plus `docs/contract-spec.md` §9 as the primary accepted contract references.

| Old section | New home |
| --- | --- |
| Section 1 Title 和目标说明 | docs/architecture-overview.md |
| Section 2 Scope / Non-goals | docs/architecture-overview.md |
| Section 3 设计依据矩阵 | docs/architecture-overview.md |
| Section 4 当前 MOCA 架构事实 | docs/architecture-overview.md |
| Section 5 参考仓库分析结论 | docs/architecture-overview.md |
| Section 6 目标架构总览 | docs/architecture-overview.md |
| Section 7 架构图 | docs/architecture-overview.md |
| Section 8.0 Canonical TrustedContext（normative，新增） | docs/contract-spec.md §8.0 |
| Section 8 模块分层设计（叙述层） | docs/architecture-overview.md §8 |
| Section 8.3 / 8.4 服务契约（normative：Knowledge / Business Tools） | docs/contract-spec.md §8.3 / §8.4（另见 §12.5 Tool contract） |
| Section 9 LangGraph workflow 设计 | docs/contract-spec.md |
| Section 10 AgentState 目标 schema | docs/contract-spec.md |
| Section 11 Intent classification 设计 | docs/contract-spec.md |
| Section 12 Tool calling 设计 | docs/contract-spec.md |
| Section 13 Memory 设计 | docs/contract-spec.md |
| Section 14 Prompt 设计 | docs/contract-spec.md |
| Section 15 Approval / SLA / Risk policy 设计 | docs/contract-spec.md |
| Section 16 Action execution 设计 | docs/contract-spec.md |
| Section 17 Observability / Replay 设计 | docs/contract-spec.md |
| Section 18 数据模型建议 | docs/contract-spec.md |
| Section 19 迁移路线 | docs/migration-plan.md |
| Section 20 测试和 eval 计划 | docs/eval-test-plan.md |
| Section 21 Golden cases | docs/eval-test-plan.md |
| Section 22 风险和取舍 | docs/architecture-overview.md |
| Section 23 明确不采用的参考模式和原因 | docs/architecture-overview.md |
| Section 24 结论 | docs/architecture-overview.md |
