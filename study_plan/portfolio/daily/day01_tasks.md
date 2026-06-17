# Day 1 Tasks

- 日期：2026-06-18
- 主题：建仓 + MOCA 全景 + Phase 14/15 内化
- 来源：`study_plan/30天主计划.md`
- 最低通过任务：T1, T2, T5, T6

## 今日任务表

| ID | 类型 | 任务 | 预计 | 产物 | 验收重点 |
|---|---|---|---:|---|---|
| T1 | theory | 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) | 75m | `study_plan/portfolio/daily/day01_notes.md` | 标题：今日理论笔记, 关键概念, 对 MOCA 的设计启发, 不懂的问题；关键词：MOCA；至少 500 字符 |
| T2 | analysis | 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 | 105m | `study_plan/portfolio/moca_internalize/00_模块全景图.md` | 标题：拆解对象, 核心流程, 风险点, trace / eval / risk；关键词：risk, trace, eval；至少 700 字符 |
| T3 | practice | 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 | 135m | `study_plan/portfolio/moca_internalize/00_模块全景图.md`<br>`study_plan/portfolio/interview/day01_MOCA一分钟介绍.md`<br>`study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md` | 标题：实战目标, 最小可运行版本, 验证记录, 失败路径；关键词：trace, eval, risk；至少 900 字符 |
| T4 | output | 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） | 105m | `study_plan/portfolio/moca_internalize/00_模块全景图.md`<br>`study_plan/portfolio/interview/day01_MOCA一分钟介绍.md`<br>`study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md` | 标题：用途, 核心内容, 验收标准；关键词：面试, 作品集；至少 600 字符 |
| T5 | reflection | 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 | 90m | `study_plan/portfolio/daily/day01_log.md`<br>`study_plan/portfolio/interview/day01_面试表达.md` | 标题：今日完成, 偏差, 明日 carryover, 面试表达；关键词：为什么这么设计, 不这么设计；至少 700 字符 |
| T6 | interview | 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） | 90m | `study_plan/portfolio/daily/day01_interview_questions.md` | 标题：大厂技术追问候选题, 今日 Top 5 追问, MOCA绑定, 证据路径, 当前边界；关键词：MOCA；至少 1200 字符 |

## 分任务执行要求

### T1 · 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
- 类型：theory
- 预计：75 分钟
- 产物：
  - `study_plan/portfolio/daily/day01_notes.md` —— 理论阅读与设计启发
- evidence_rule：
  - 必须包含标题：今日理论笔记
  - 必须包含标题：关键概念
  - 必须包含标题：对 MOCA 的设计启发
  - 必须包含标题：不懂的问题
  - 必须出现关键词：MOCA
  - 正文至少 500 个非空白字符
  - `今日理论笔记` 标题下必须有非占位内容
  - `关键概念` 标题下必须有非占位内容
  - `对 MOCA 的设计启发` 标题下必须有非占位内容
- 人工确认项：
  - 是否能不用原文讲清今天理论和 MOCA 的关系

### T2 · 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
- 类型：analysis
- 预计：105 分钟
- 产物：
  - `study_plan/portfolio/moca_internalize/00_模块全景图.md` —— MOCA 架构开场讲解
- evidence_rule：
  - 必须包含标题：拆解对象
  - 必须包含标题：核心流程
  - 必须包含标题：风险点
  - 必须包含标题：trace / eval / risk
  - 必须出现关键词：risk
  - 必须出现关键词：trace
  - 必须出现关键词：eval
  - 正文至少 700 个非空白字符
  - `拆解对象` 标题下必须有非占位内容
  - `核心流程` 标题下必须有非占位内容
  - `风险点` 标题下必须有非占位内容
  - `trace / eval / risk` 标题下必须有非占位内容
- 人工确认项：
  - 是否能对着拆解图或文档讲 3 分钟

### T3 · 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
- 类型：practice
- 预计：135 分钟
- 产物：
  - `study_plan/portfolio/moca_internalize/00_模块全景图.md` —— MOCA 架构开场讲解
  - `study_plan/portfolio/interview/day01_MOCA一分钟介绍.md` —— 1 分钟项目介绍稿
  - `study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md` —— Phase 15.1 GSD 启动材料
- evidence_rule：
  - 必须包含标题：实战目标
  - 必须包含标题：最小可运行版本
  - 必须包含标题：验证记录
  - 必须包含标题：失败路径
  - 必须出现关键词：trace
  - 必须出现关键词：eval
  - 必须出现关键词：risk
  - 正文至少 900 个非空白字符
  - `实战目标` 标题下必须有非占位内容
  - `验证记录` 标题下必须有非占位内容
  - `失败路径` 标题下必须有非占位内容
- 人工确认项：
  - 如果涉及代码，是否真的跑过最小命令；如果涉及文档，是否能说明取舍

### T4 · 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
- 类型：output
- 预计：105 分钟
- 产物：
  - `study_plan/portfolio/moca_internalize/00_模块全景图.md` —— MOCA 架构开场讲解
  - `study_plan/portfolio/interview/day01_MOCA一分钟介绍.md` —— 1 分钟项目介绍稿
  - `study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md` —— Phase 15.1 GSD 启动材料
- evidence_rule：
  - 必须包含标题：用途
  - 必须包含标题：核心内容
  - 必须包含标题：验收标准
  - 必须出现关键词：面试
  - 必须出现关键词：作品集
  - 正文至少 600 个非空白字符
  - `用途` 标题下必须有非占位内容
  - `核心内容` 标题下必须有非占位内容
  - `验收标准` 标题下必须有非占位内容
- 人工确认项：
  - 这个产物是否能直接服务作品集或面试

### T5 · 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
- 类型：reflection
- 预计：90 分钟
- 产物：
  - `study_plan/portfolio/daily/day01_log.md` —— 当天执行日志
  - `study_plan/portfolio/interview/day01_面试表达.md` —— 当天面试表达
- evidence_rule：
  - 必须包含标题：今日完成
  - 必须包含标题：偏差
  - 必须包含标题：明日 carryover
  - 必须包含标题：面试表达
  - 必须出现关键词：为什么这么设计
  - 必须出现关键词：不这么设计
  - 正文至少 700 个非空白字符
  - `今日完成` 标题下必须有非占位内容
  - `偏差` 标题下必须有非占位内容
  - `明日 carryover` 标题下必须有非占位内容
  - `面试表达` 标题下必须有非占位内容
- 人工确认项：
  - 是否能回答 3 个围绕今天主题的追问

### T6 · 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
- 类型：interview
- 预计：90 分钟
- 产物：
  - `study_plan/portfolio/daily/day01_interview_questions.md` —— 今日大厂技术追问候选题库与 Top 5（强制绑定 MOCA）
- evidence_rule：
  - 必须包含标题：大厂技术追问候选题
  - 必须包含标题：今日 Top 5 追问
  - 必须包含标题：MOCA绑定
  - 必须包含标题：证据路径
  - 必须包含标题：当前边界
  - 必须出现关键词：MOCA
  - 正文至少 1200 个非空白字符
  - `大厂技术追问候选题` 标题下必须有非占位内容
  - `今日 Top 5 追问` 标题下必须有非占位内容
  - `MOCA绑定` 标题下必须有非占位内容
  - `当前边界` 标题下必须有非占位内容
- 人工确认项：
  - 是否先按 A-F 生成候选题，再从中挑今日必须练熟的 Top 5
  - Top 5 是否每题都能用 MOCA 例子回答，而不是通用八股
  - 是否至少包含 1 题 failure/risk/fallback 和 1 题 trace/eval/evidence

## 今日执行日志模板

```md
## 今日完成
- 

## 偏差
- 

## 明日 carryover
- 

## 面试表达
- 业务语言：
- 技术实现：
- 为什么这么设计：
- 不这么设计的问题：
```
