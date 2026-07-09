# Phase 61: Product Experience Fixes - Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.
> Decisions are captured in `61-CONTEXT.md`; this log preserves alternatives considered.

**Date:** 2026-07-09
**Phase:** 61 - Product Experience Fixes
**Areas discussed:** Metric Semantics And Defaults, Role And Merchant Scope Boundaries, Agent Routing And Response Copy, Console Timeline Presentation, Regression And Demo Validation

---

## Metric Semantics And Defaults

| Question | Option | Description | Selected |
| --- | --- | --- | --- |
| 用户没说时间范围时怎么办？ | 要求澄清 | 先问统计今天、本周，还是全部当前范围，避免隐藏口径。 | Yes |
| 用户没说时间范围时怎么办？ | 默认截至当前全部历史 | 回答快，但容易被理解成真实经营总览。 | No |
| 用户没说时间范围时怎么办？ | 按指标类型默认 | 待处理工单=当前快照；订单/退款/补偿券=必须有时间范围。 | No |
| 用户说“今天 / 本周 / 当前”时如何解释？ | 按自然语言解析 | 今天=本地当天 00:00 到现在；本周=周一 00:00 到现在；当前=当前状态快照。 | Yes |
| 用户说“今天 / 本周 / 当前”时如何解释？ | 全部转成澄清 | 最安全，但体验偏笨。 | No |
| 用户说“今天 / 本周 / 当前”时如何解释？ | 全部按过去 24 小时 / 7 天 | 简单，但不完全符合中文业务语义。 | No |
| 支持的 MVP 指标是否就锁这 5 个？ | 锁 5 个 | 订单数、退款单数、待处理工单数、补偿券记录数、商家退款率。 | Yes |
| 支持的 MVP 指标是否就锁这 5 个？ | 允许同类扩展 | 可顺手做退款金额、订单金额、关闭工单数等。 | No |
| 支持的 MVP 指标是否就锁这 5 个？ | 先只做 3 个高频 | 订单数、退款单数、待处理工单数。 | No |
| “本周补偿券发了多少”的口径怎么写？ | 明确演示系统记录口径 | 统计 MOCA 内 `issue_coupon` 动作草稿/记录，并说明不是外部真实发券成功数。 | Yes |
| “本周补偿券发了多少”的口径怎么写？ | 直接叫发放数 | 更自然，但可能误导。 | No |
| “本周补偿券发了多少”的口径怎么写？ | 没有真实发券流水就 unsupported | 最保守，但会削弱 demo。 | No |

**User notes:** 需要支持更多时间段，包括本季度、本月以及今年。

---

## Role And Merchant Scope Boundaries

| Question | Option | Description | Selected |
| --- | --- | --- | --- |
| support 用户能看什么？ | 只能看 trusted merchant_scope 内的商户 | 当前 demo 通常就是自己绑定的商户。 | Yes |
| support 用户能看什么？ | support 可以看全租户 | 方便演示，但违反当前权限模型。 | No |
| support 用户能看什么？ | support 可以看自己商户 + 用户显式输入的商户 | 用户输入不能扩大权限。 | No |
| manager 用户能看什么？ | 只能看 trusted merchant_scope 内的商户/商户组 | Phase 61 不单独设计新的组织层级，只消费已有 trusted scope。 | Yes |
| manager 用户能看什么？ | manager 默认看全租户 | 简单，但和管理权限范围不一致。 | No |
| manager 用户能看什么？ | manager 必须每次指定商户 | 严格但体验差。 | No |
| admin 用户能看什么？ | 只看 configured management scope | `["*"]` 才能看全租户；服务端收窄后按收窄范围。 | Yes |
| admin 用户能看什么？ | admin 永远看全租户 | 简单，但绕过配置范围。 | No |
| admin 用户能看什么？ | admin 查询跨商户指标也必须澄清商户 | 安全但降低运营视角。 | No |
| 用户指定了无权商户时，回复怎么处理？ | 不泄露存在性 | 统一说当前权限范围内无法提供该商户指标。 | Yes |
| 用户指定了无权商户时，回复怎么处理？ | 明确说无权访问该商户 | 清楚，但会暴露商户存在。 | No |
| 用户指定了无权商户时，回复怎么处理？ | 静默改成当前商户范围 | 体验顺，但容易误导。 | No |

---

## Agent Routing And Response Copy

| Question | Option | Description | Selected |
| --- | --- | --- | --- |
| `business_metric_query` 应该走哪条路径？ | `slot_resolution_gate -> investigate/tool -> final_response` | 缺槽时澄清，槽齐后用只读 metric tool 查数据。 | Yes |
| `business_metric_query` 应该走哪条路径？ | 单独建 metric node | 更清晰但会扩大 graph 变更。 | No |
| `business_metric_query` 应该走哪条路径？ | 直接在 final_response 查数据库 | 最短，但破坏边界。 | No |
| 缺少必要指标槽时，澄清文案应该怎么写？ | 解释缺什么 + 给可选项 | 给出今天、本周、本月、本季度、今年或起止时间等选项。 | Yes |
| 缺少必要指标槽时，澄清文案应该怎么写？ | 只问一句请补充时间范围 | 短，但不够友好。 | No |
| 缺少必要指标槽时，澄清文案应该怎么写？ | 自动猜默认 | 减少追问，但与澄清决策冲突。 | No |
| unsupported 能力的文案风格？ | 能力边界 + 可替代输入 | 说明不支持什么，并告诉用户可以问哪些已支持问题。 | Yes |
| unsupported 能力的文案风格？ | 只说暂不支持 | 简洁但帮助少。 | No |
| unsupported 能力的文案风格？ | 尽量给猜测性建议 | 看起来聪明，但容易伪造能力。 | No |
| metric answer 的最终格式？ | 数字先行 + 口径脚注 | 第一句给数值/比例；第二句说明范围、时间、过滤条件、freshness。 | Yes |
| metric answer 的最终格式？ | 先解释口径再给数字 | 严谨但读起来慢。 | No |
| metric answer 的最终格式？ | 只给数字 | 清爽但审计和 demo 可信度不足。 | No |

---

## Console Timeline Presentation

| Question | Option | Description | Selected |
| --- | --- | --- | --- |
| timeline 要不要展示“结果类型”？ | 要区分结果类型 | direct response、clarification、unsupported、metric answer、RAG answer、tool call 用不同文案/标签。 | Yes |
| timeline 要不要展示“结果类型”？ | 只按节点名展示 | 改动小，但用户仍看不懂原因。 | No |
| timeline 要不要展示“结果类型”？ | 只改最终回复，不改 timeline | 更快，但截图里的体验问题会残留。 | No |
| metric 查询在 timeline 里怎么显示？ | 显示为业务指标查询 | 例如“正在查询业务指标”，副标题显示 `metric: refund_count · scope: 当前权限范围`。 | Yes |
| metric 查询在 timeline 里怎么显示？ | 仍显示普通 investigate | 简单，但看不出统计指标。 | No |
| metric 查询在 timeline 里怎么显示？ | 每个指标一个独立中文节点名 | 直观，但让前端和指标类型强耦合。 | No |
| clarification / unsupported 在 timeline 里要显示 reason 吗？ | 显示安全 reason | 例如“缺少时间范围”，不显示内部 debug。 | Yes |
| clarification / unsupported 在 timeline 里要显示 reason 吗？ | 不显示 reason | 界面干净，但用户不知道为什么停住。 | No |
| clarification / unsupported 在 timeline 里要显示 reason 吗？ | 显示完整 routing_hints | 方便调试，但可能泄露内部实现。 | No |
| freshness / scope 显示在哪里？ | 主要放最终回答，timeline 只放简短标签 | 避免 timeline 太拥挤。 | Yes |
| freshness / scope 显示在哪里？ | timeline 和回答都完整显示 | 透明但显得吵。 | No |
| freshness / scope 显示在哪里？ | 只放 timeline，不放最终回答 | 不利于用户复制答案。 | No |

---

## Regression And Demo Validation

| Question | Option | Description | Selected |
| --- | --- | --- | --- |
| 回归覆盖范围要到哪一级？ | 后端节点 + graph + 前端渲染核心逻辑 | 覆盖路由、final_response、SSE/timeline 标签，不做完整 E2E。 | No |
| 回归覆盖范围要到哪一级？ | 只做后端 pytest | 快，但 timeline UX 容易漏。 | No |
| 回归覆盖范围要到哪一级？ | 加完整 Playwright E2E | 覆盖强，但 Phase 61 成本会上升。 | Yes |
| 必须固化哪些坏 prompt？ | 固化当前已知坏例 | 覆盖当前具体坏例和角色/scope metric case。 | No |
| 必须固化哪些坏 prompt？ | 只固化 3 个最明显的 | `你好`、`当前有多少订单`、缺订单号。 | No |
| 必须固化哪些坏 prompt？ | 建一个大 golden set | 全面但会拖慢这次 phase。 | Yes |
| demo 验收是否需要本地 UI 手测记录？ | 需要 | 用本地验证记录或 Phase 61 validation 记录最终 UI/API 验证。 | Yes |
| demo 验收是否需要本地 UI 手测记录？ | 不需要，自动测试通过即可 | 自动化足够但缺少 demo 观察记录。 | No |
| demo 验收是否需要本地 UI 手测记录？ | 只截图，不写验证记录 | 证据不够结构化。 | No |
| 计划粒度怎么切？ | 按实现边界拆 4-5 个 plan | 响应 UX、metric contract/scope、metric runtime、agent integration、console/regression。 | Yes |
| 计划粒度怎么切？ | 一个大 plan 全做 | 简单但容易失控。 | No |
| 计划粒度怎么切？ | 每个小 prompt 一个 plan | 过碎，会回到多个 phase 的问题。 | No |

---

## the agent's Discretion

- Exact metric schema/type names.
- Exact pending-ticket status enum mapping after inspecting current demo status values.
- Exact Playwright fixture and golden-set file format.
- Exact visual styling of timeline labels.

## Deferred Ideas

- Full dashboard/chart/export/scheduled analytics.
- Real external coupon delivery success metrics.
- New manager organization hierarchy.
- Arbitrary SQL or natural-language database exploration.
