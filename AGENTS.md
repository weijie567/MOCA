# MOCA 项目说明（项目级 AGENTS.md）

> 本文件只放 MOCA 项目特有的协作工作流规则。通用的个人偏好、Boris/GSD 使用边界、Git 默认规则、测试与 secrets 规则以全局 `~/.Codex/AGENTS.md` 为准，本文件不重复。

## 语言与学习计划文档规则

- `study_plan/` 下的学习计划、作品集、岗位定位、产品规划、架构规划、复盘类文档默认使用中文。
- 必要的技术名词、API 名称、文件路径、命令、类名、函数名、测试名可以保留英文，不强行翻译。
- 如果用户明确要求英文或中英双语，以用户当次要求为准。
- 这条规则只约束文档表达语言，不要求翻译源码标识符、接口字段、配置项或测试用例名称。

## 调试问题记录规则

- 以后在 MOCA 本地调试、启动、验证、UI 手测、API 测试、RAG/agent/记忆/工具调用排查中，只要发现错误、异常、不符合预期的回答、环境坑或验证失败，就要在处理后追加到 `.planning/LOCAL-VALIDATION-ISSUES.md`。记录默认使用中文，应包含：问题现象、如何检测/复现、关键证据或命令、当前判断/根因、已做处理、剩余问题和下次继续排查入口。`AGENTS.md` 只保留这条记录规则，不写具体事故详情。

## 双 AI 协作工作流（Codex ↔ Codex）

MOCA 采用 Codex 与 Codex 的「双 AI 交叉评审」模式：**Codex 是 plan 的设计者和决策把关人，Codex 是独立第二意见、大改执行手，以及代码实现/审核的主力。** 每一道审核优先调用 GSD 原生工具，Codex 在其后做独立交叉验证。

### 铁律

- Codex 是裁决者。对 Codex 的审核意见和执行结果，都必须拿仓库真实代码、文档、测试去核对，不盲信。
- 核对优先用 `rg`/grep 定位再读必要片段；区分「已确认」与「未确认」，找不到依据写「当前仓库中没有找到依据」。
- 审核优先调用相关 GSD 工具，Codex 作为补充的独立交叉验证，不互相替代。

### 触发范围

- 本工作流只用于 **phase-level plan 和较大改动**。
- 小 bug fix、单文件小改不套此流程，按全局 Boris-style workflow 直接处理。

### 阶段 A：PLAN 设计（Codex 主导）

1. **[Codex] 设计 plan** —— 走 GSD plan-phase：research → 写 PLAN.md。
2. **[GSD 工具] 第一道审核** —— `gsd-plan-checker`（plan-phase 流程内置）。
3. **[Codex] 独立交叉审核** —— 对 PLAN.md 做批判性审核，产出 blockers/warnings，补 `gsd-plan-checker` 漏掉的问题。
4. **[Codex] 裁决 Codex 的审核结果** —— 逐条拿仓库真实代码核对，判定：成立 / 误报 / 不同意；不盲目采纳。
5. **[分流] 执行采纳的修改** —— 按下方「大改/小改判定线」分流：小改 Codex 自己改，大改交 Codex 执行。
6. **[GSD 工具 → Codex] 复核** —— 优先重跑 `gsd-plan-checker`，再由 Codex 做最终复核，确认修订正确、完整、自洽。

### PLAN 粒度硬约束

- phase-level planning 必须先做 plan 粒度检查：如果一个 phase 涉及多个 service boundary / ownership domain / wave / verification gate，第一版就要拆成多个编号 plan，不允许先写成一个大 `*-01-PLAN.md` 再留给执行阶段拆。
- 出现「只有一个大 plan」且同时覆盖契约定义、实现迁移、兼容层、调用方改造、权限/安全边界和最终验证时，视为 planning blocker。必须在执行前拆成按依赖排序的小 plan，每个 plan 有单一目标、有限文件面、可执行 task、明确 tests / acceptance criteria。
- `gsd-plan-checker` 和 Codex 独立复核都必须显式检查 plan 粒度。若 plan 太大导致 task 不具体、验收不可直接执行、或文件跨度过宽，先拆 plan，再继续后续评审或实现。
- Phase 30 曾出现把 BusinessFactService boundary 写成一个过大的 `30-01-PLAN.md` 的问题，导致计划不可具体执行；后续同类 service-boundary / platform-foundation phase 必须以此为反例，优先拆分为契约/服务边界、兼容/平台集成、调用方/最终验证等可执行单元。

### 阶段 B：代码实现（Codex 主导）

7. **[Codex] 实现代码** —— 按已定稿的 PLAN.md 实现。
8. **[GSD 工具 → Codex] 代码审核** —— 优先 `gsd-code-review` / `gsd-verify-work` 等原生工具，Codex 做独立审核。
9. **[Codex] 轻量收尾复核** —— 只检查「是否偏离 plan 的 must_haves / 是否有未覆盖的 requirement / 是否动了 plan 明确禁止的东西」。不读代码细节、不审风格。这一步读 plan + diff 摘要 + 少量 grep 即可，保持低成本。

### 大改 / 小改判定线（步骤 5）

**Codex 自己改**，需同时满足全部 5 条：

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

**边界模糊时默认交 Codex** —— 一次大改的执行成本通常低于 Codex 反复试错读文件的成本。

**本判定线 override GSD `plan-phase` workflow step 12 的「spawn gsd-planner」**：plan 修订（或任何代码改动）的执行命中大改线时交 Codex，不走 gsd-planner（gsd-planner 仍是 Codex token，结构性/多文件改动正是该交 Codex 的）。判定线一旦判 Codex 即绑定，Codex 不得自行论证改判；想偏离须先问用户。

### 设计依据（为什么这样分工）

- GSD 工具 + Codex 双审是经过验证的互补：实测中 `gsd-plan-checker` 给 0 blocker，Codex 补抓到 5 个真 blocker（含会破坏后续 replay 身份契约的 bug）。
- 分流判定线的目标是性价比与速度的平衡：真正费 token 的不是「改几行」，而是「为改对而反复读文件」，所以把需要回读源码或结构性的改动整体交给 Codex 更划算。

## spec 与 phase 实现的关系

- `docs/contract-spec.md` 是 MOCA 唯一 normative 契约源，但它只定**契约语义**，不定实现细节与范围；具体落地由各 phase 决定，不把 spec 奉为金科玉律。
- spec 描述的是「目标契约」，不是「已实现事实」。不要把目标态 normative 描述当成已经实现，也不要反向把实现妥协误当成 spec 漏洞反复返工。
- phase 实现与 spec 不一致时**禁止静默偏离**，必须留痕，二选一：
  - 判定是 spec 错 → 回 spec 修，走双 AI 复审流程；
  - 判定是实现妥协（MVP 只实现一部分）→ 在 spec 就地加 MVP scope / 目标态注解，并在 `.planning/` 留决策记录。
- defer 项必须给目标 phase 命名（如 post-Phase 17），不写模糊「以后」。
- 阶段 B 轻量收尾复核时，差异记录是该复核的必备输入。
