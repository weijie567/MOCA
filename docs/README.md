<!-- generated-by: gsd-doc-writer -->
# MOCA 文档入口

| 元数据 | 值 |
| --- | --- |
| 文档类型 | CURRENT |
| 描述范围 | `docs/` 目录导航、文档权威、阅读路径与维护规则 |
| 最后核验 | 2026-08-04（当前工作区） |
| 权威来源 | 本目录文档清单与当前工作区事实基线 |
| 更新触发 | docs 信息架构、权威分类、文件名或核心阅读路径变化 |

## 如何使用本目录

这套公开文档由本入口和 12 份专题文档组成，共 13 份。它面向想快速理解产品、深入架构、运行演示或核对质量与契约的读者；正文聚焦当前实现、已接受契约和可执行指南，不要求先阅读项目过程历史。

## 三类文档权威

| 类型 | 回答的问题 | 事实依据 | 不能被误用为 |
| --- | --- | --- | --- |
| **CURRENT** | 当前工作区实际实现了什么、边界在哪里 | 源码、测试、迁移、配置及核验日期 | 永久不变的目标契约 |
| **NORMATIVE** | 项目已经接受的语义、术语和约束是什么 | 接受契约与 canonical vocabulary | 已经全部落地的实现事实 |
| **GUIDE** | 如何在当前环境完成一项操作 | 当前命令、脚本、API、UI 与可见信号 | 独立的实现或契约权威 |

三类文档按职责互补，没有一条可以把冲突静默“解释掉”。发现 CURRENT、NORMATIVE、GUIDE 或代码行为不一致时，先用源码与测试确认已实现事实，再判断是实现缺陷、契约需要修订还是指南过期；随后显式修改对应文档、差异说明与核验日期。

## 文档地图

| 文档 | 类型 | 用途 |
| --- | --- | --- |
| `docs/README.md`（本页） | CURRENT | 导航、权威分类、阅读路径和维护规则 |
| [architecture/system-overview.md](architecture/system-overview.md) | CURRENT | 系统边界、分层架构、真实调用边界、数据落点与当前限制 |
| [architecture/agent-workflow.md](architecture/agent-workflow.md) | CURRENT | 15 个 LangGraph 节点、条件路由、状态、终态与 interrupt/resume |
| [architecture/tools-and-business-facts.md](architecture/tools-and-business-facts.md) | CURRENT | ToolPlatform、工具契约、BusinessFactService、权限与事实边界 |
| [architecture/rag-and-grounding.md](architecture/rag-and-grounding.md) | CURRENT | 摄取、hybrid retrieval、证据验证、citation、claim grounding 与 fail-closed |
| [architecture/memory.md](architecture/memory.md) | CURRENT | checkpoint、session/CWC/长期记忆、review、隔离与 contextual authority |
| [architecture/security-approval-and-actions.md](architecture/security-approval-and-actions.md) | CURRENT | JWT/scope、风险 snapshot、审批恢复、capability 与 draft-only 动作边界 |
| [architecture/trace-and-replay.md](architecture/trace-and-replay.md) | CURRENT | run/step/event、SSE、trace/replay 投影、顺序与数据最小化 |
| [quality/evaluation.md](quality/evaluation.md) | CURRENT | golden 数据、评测脚本、阈值、gate manifest 与当前报告状态 |
| [guides/demo.md](guides/demo.md) | GUIDE | reset/seed、UI/API 五个演示场景、预期信号、fallback 与排障 |
| [reference/contracts.md](reference/contracts.md) | NORMATIVE | 已接受契约的索引、适用范围，以及 current implementation 差异入口 |
| [reference/glossary.md](reference/glossary.md) | NORMATIVE | canonical 术语、易混概念和禁止混用的命名边界 |
| [contract-spec.md](contract-spec.md) | NORMATIVE | 详细契约正文；包含目标语义与历史兼容内容，不能直接当作当前实现证明 |

## 建议阅读路径

### 快速了解

1. 从本页了解文档权威。
2. 阅读 [系统总览](architecture/system-overview.md)，建立产品与部署边界。
3. 阅读 [Agent 工作流](architecture/agent-workflow.md)，了解一次请求怎样流转。
4. 需要直观看结果时进入 [演示指南](guides/demo.md)。

### 架构深读

1. [系统总览](architecture/system-overview.md) → [Agent 工作流](architecture/agent-workflow.md)。
2. [工具与业务事实](architecture/tools-and-business-facts.md) → [RAG 与 grounding](architecture/rag-and-grounding.md) → [记忆](architecture/memory.md)。
3. [安全、审批与动作](architecture/security-approval-and-actions.md) → [Trace 与 Replay](architecture/trace-and-replay.md)。
4. 遇到术语歧义时回查 [Glossary](reference/glossary.md)，遇到语义边界时回查 [Contracts](reference/contracts.md)。

### 运行演示

1. 按 [演示指南](guides/demo.md) 准备环境、reset/seed 并运行五个场景。
2. 用 [安全、审批与动作](architecture/security-approval-and-actions.md) 解释为什么 chat 不是审批入口、为什么只有 action draft。
3. 用 [Trace 与 Replay](architecture/trace-and-replay.md) 核对持久化时间线和安全投影。

### 质量与契约

1. 先读 [Contracts](reference/contracts.md) 与 [Glossary](reference/glossary.md)，明确接受语义与名词；需要逐条详细契约时再进入 [Contract Specification](contract-spec.md)。
2. 再读 [Evaluation](quality/evaluation.md)，区分数据规模、通过阈值和真实运行结果。
3. 最后回到相关 CURRENT 架构文档，逐项核对目标契约与当前实现差异。

## 维护规则

- 每份文档必须保留 `文档类型`、`描述范围`、`最后核验`、`权威来源`、`更新触发` 五项 metadata。
- 源码、测试、迁移、配置或运行边界变化时，更新受影响的 CURRENT 文档；不能只改概览而留下专题文档失真。
- 接受契约或 canonical terminology 变化时，更新 NORMATIVE 文档，并显式检查对应 CURRENT/GUIDE 是否需要同步。
- 命令、seed、账号、endpoint、UI flow 或可见信号变化时，更新 GUIDE，并回查实际脚本、router、frontend 与测试。
- 文件名、分类或核心阅读顺序变化时，同步更新本入口及所有指向它的链接。
- 新增声明必须给出可复查依据；外部环境值无法从仓库确认时应显式标记，不把推测写成事实。
- 文档之间有冲突时必须留下明确修订，禁止用“目标态即现状”或“现状自动覆盖契约”来消解差异。

## 过程历史与旧资料边界

公开 `docs/` 只维护 CURRENT、NORMATIVE 和 GUIDE，不要求读者阅读具体阶段历史。讨论、决策、验证过程和阶段性记录保存在 [`.planning/`](../.planning/)；提交演进与逐行变更由 Git 历史承载。

旧的 flat docs 已移出当前公开文档面；需要追溯“为什么这样演进”时查归档分支、`.planning/` 与 Git，需要回答“现在是什么、接受什么、怎么操作”时使用本目录。
