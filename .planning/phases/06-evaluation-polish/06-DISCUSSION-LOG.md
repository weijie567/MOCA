# Phase 6: Evaluation & Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 06-evaluation-polish
**Areas discussed:** Golden set 扩展策略, 评估报告格式与阈值, README 深度与展示, Demo 脚本形式, 交付边界

---

## Golden set 扩展策略

| Option | Description | Selected |
|--------|-------------|----------|
| 统一为 Agent 端到端 golden set | 保留 RAG 14 cases 不动，只扩展 Agent golden set 到 25-40 cases | |
| 双层分开评估 | RAG 和 Agent 各自独立扩展，分别评分 | ✓ |
| 合并为统一格式 | 合并两个 golden set 为一个统一格式 | |

**User's choice:** 分层评估 + 统一汇总报告。RAG 14 cases 保持稳定作为组件级回归测试，Agent 扩展到 30-35 cases 覆盖 10 个业务类别。eval_all.py 统一入口输出合并报告。
**Notes:** 用户详细说明了两个 golden set 的不同评估目标（RAG = retrieval regression, Agent = 端到端系统评估），以及为什么不应合并。

---

## 评估报告格式与阈值

| Option | Description | Selected |
|--------|-------------|----------|
| JSON + Markdown 双输出 | JSON 机器可读 + Markdown 人可读，CI 用 exit code | ✓ |
| 纯 Markdown | 只输出 Markdown，CI 通过 grep 判断 | |
| 纯 JSON | 只输出 JSON，需要时转 Markdown | |

**User's choice:** JSON + Markdown 双输出。JSON 是 source of truth，Markdown 从 JSON 渲染。CI 只依赖 exit code。
**Notes:** 用户详细定义了 JSON schema（overall_status, generated_at, rag/agent summaries, thresholds, failed/warning cases, metrics, baseline_comparison）和 Markdown 内容结构。

---

## README 深度与展示 — 架构图格式

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid 图 | GitHub 原生渲染，维护成本低 | ✓ |
| ASCII art | 任何终端可看，复杂图可读性差 | |
| 图片文件 | 视觉效果最好，维护成本高 | |

**User's choice:** Mermaid 图。2 张：System Architecture + Agent Workflow。
**Notes:** 用户明确不用图片文件，后续如需面试 PPT 可单独生成。

## README 深度与展示 — 受众

| Option | Description | Selected |
|--------|-------------|----------|
| 面试官视角优先 | 1-2 分钟看懂核心价值，技术细节放 docs/ | |
| 开发者文档全集 | 完整开发文档，内容全面但较长 | |
| 分层：上半展示 + 下半技术 | 上半面试官，下半开发者，详细内容放 docs/ | ✓ |

**User's choice:** 分层结构。上半服务面试展示，下半服务复现和维护。详细内容放 docs/ 子目录。
**Notes:** 用户给出了完整 README 9 段结构和 docs/ 文件拆分方案。

---

## Demo 脚本形式

| Option | Description | Selected |
|--------|-------------|----------|
| 纯文档 + curl 示例 | Markdown 文档，手动复制粘贴执行 | |
| 可执行 shell 脚本 | 一键跑完整 demo 流程 | |
| 文档 + 脚本都有 | 文档讲解 + 脚本复现 | ✓ |

**User's choice:** 两者都有。docs/demo-walkthrough.md 负责讲清楚，scripts/demo_phase6.sh 负责证明能复现。
**Notes:** 用户定义了 6-7 个 demo 场景、10 分钟节奏分配、脚本不依赖真实 LLM。

---

## 交付边界（补充讨论）

**User's decisions (freeform):**
1. 不新增大业务功能，只允许 eval/demo/trace 可复现的小修复
2. CI eval 用 deterministic/mock path，真实 LLM 只做 optional local eval
3. Baseline comparison 只做简单 diff，不做趋势图
4. Metrics badge 可选，不阻塞
5. Demo 不依赖前端，API/curl 为主
6. Trace 展示：run_id, intent, tool calls, evidence refs, approval decision, final status
7. 文档拆分：README 入口 + docs/ 详细
8. 完成标准：eval_all.py 可运行、golden set 扩展、README 完成、demo 可运行、CI 通过

---

## Claude's Discretion

- CI workflow file structure
- Mermaid diagram content and styling
- Agent eval scoring algorithm internals
- File migration strategy for existing golden sets

## Deferred Ideas

- 复杂趋势图 / 历史 dashboard
- Metrics badge 自动更新
- 完整 trace visualization UI
- 面试 PPT 生成
- Frontend screenshot 嵌入 README
