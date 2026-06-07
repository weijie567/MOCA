# MOCA 项目说明（项目级 CLAUDE.md）

> 本文件只放 MOCA 项目特有的协作工作流规则。通用的个人偏好、Boris/GSD 使用边界、Git 默认规则、测试与 secrets 规则以全局 `~/.claude/CLAUDE.md` 为准，本文件不重复。

## 双 AI 协作工作流（Claude ↔ Codex）

MOCA 采用 Claude 与 Codex 的「双 AI 交叉评审」模式：**Claude 是 plan 的设计者和决策把关人，Codex 是独立第二意见、大改执行手，以及代码实现/审核的主力。** 每一道审核优先调用 GSD 原生工具，Codex 在其后做独立交叉验证。

### 铁律

- Claude 是裁决者。对 Codex 的审核意见和执行结果，都必须拿仓库真实代码、文档、测试去核对，不盲信。
- 核对优先用 `rg`/grep 定位再读必要片段；区分「已确认」与「未确认」，找不到依据写「当前仓库中没有找到依据」。
- 审核优先调用相关 GSD 工具，Codex 作为补充的独立交叉验证，不互相替代。

### 触发范围

- 本工作流只用于 **phase-level plan 和较大改动**。
- 小 bug fix、单文件小改不套此流程，按全局 Boris-style workflow 直接处理。

### 阶段 A：PLAN 设计（Claude 主导）

1. **[Claude] 设计 plan** —— 走 GSD plan-phase：research → 写 PLAN.md。
2. **[GSD 工具] 第一道审核** —— `gsd-plan-checker`（plan-phase 流程内置）。
3. **[Codex] 独立交叉审核** —— 对 PLAN.md 做批判性审核，产出 blockers/warnings，补 `gsd-plan-checker` 漏掉的问题。
4. **[Claude] 裁决 Codex 的审核结果** —— 逐条拿仓库真实代码核对，判定：成立 / 误报 / 不同意；不盲目采纳。
5. **[分流] 执行采纳的修改** —— 按下方「大改/小改判定线」分流：小改 Claude 自己改，大改交 Codex 执行。
6. **[GSD 工具 → Claude] 复核** —— 优先重跑 `gsd-plan-checker`，再由 Claude 做最终复核，确认修订正确、完整、自洽。

### 阶段 B：代码实现（Codex 主导）

7. **[Codex] 实现代码** —— 按已定稿的 PLAN.md 实现。
8. **[GSD 工具 → Codex] 代码审核** —— 优先 `gsd-code-review` / `gsd-verify-work` 等原生工具，Codex 做独立审核。
9. **[Claude] 轻量收尾复核** —— 只检查「是否偏离 plan 的 must_haves / 是否有未覆盖的 requirement / 是否动了 plan 明确禁止的东西」。不读代码细节、不审风格。这一步读 plan + diff 摘要 + 少量 grep 即可，保持低成本。

### 大改 / 小改判定线（步骤 5）

**Claude 自己改**，需同时满足全部 5 条：

1. 纯文本性质改动（措辞 / 数值 / frontmatter / 单条 acceptance 微调）；
2. ≤ 5 处编辑；
3. ≤ 3 个文件；
4. 无新增 task；
5. 不需回读源码即可改对。

**否则交给 Codex 执行。** 此外，命中以下任一项一票否决、无论处数多少都交 Codex：

- 新增 / 删除 / 重排 task；
- 跨 ≥ 3 个文件；
- 改动涉及 task 之间的依赖 / wave 结构；
- 需要重新核对源码才能改对。

**边界模糊时默认交 Codex** —— 一次大改的执行成本通常低于 Claude 反复试错读文件的成本。

### 设计依据（为什么这样分工）

- GSD 工具 + Codex 双审是经过验证的互补：实测中 `gsd-plan-checker` 给 0 blocker，Codex 补抓到 5 个真 blocker（含会破坏后续 replay 身份契约的 bug）。
- 分流判定线的目标是性价比与速度的平衡：真正费 token 的不是「改几行」，而是「为改对而反复读文件」，所以把需要回读源码或结构性的改动整体交给 Codex 更划算。
