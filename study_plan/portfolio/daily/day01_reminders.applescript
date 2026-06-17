on makeDate(y, m, d, h, minValue)
  set dt to current date
  set year of dt to y
  set month of dt to m
  set day of dt to d
  set hours of dt to h
  set minutes of dt to minValue
  set seconds of dt to 0
  return dt
end makeDate

tell application "Reminders"
  set listName to "MOCA 30 Days"
  if not (exists list listName) then
    make new list with properties {name:listName}
  end if
  set targetList to list listName
  delete (every reminder of targetList whose name contains "[D01]")
  make new reminder at end of reminders of targetList with properties {name:"[D01][S01][ACTIVE] [T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (1)", body:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500

计划时间：07:50-08:20
顺序状态：ACTIVE：当前任务，完成后自动启动下一项。
序号：1/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。", due date:my makeDate(2026, June, 18, 7, 50), remind me date:my makeDate(2026, June, 18, 7, 50)}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S02][WAIT] [T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (2)", body:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500

计划时间：08:20-08:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：2/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S03][WAIT] [T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (3)", body:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500

计划时间：08:50-09:05
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：3/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S04][WAIT] [T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (1)", body:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700

计划时间：09:05-09:35
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：4/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S05][WAIT] [T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (2)", body:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700

计划时间：09:35-10:05
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：5/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S06][WAIT] [T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (3)", body:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700

计划时间：10:05-10:35
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：6/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S07][WAIT] [T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (4)", body:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700

计划时间：10:35-10:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：7/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S08][WAIT] [T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (1)", body:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900

计划时间：10:50-11:20
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：8/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S09][WAIT] [T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (2)", body:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900

计划时间：11:20-11:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：9/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S10][WAIT] [T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (3)", body:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900

计划时间：11:50-12:20
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：10/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S11][WAIT] [T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (4)", body:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900

计划时间：12:20-12:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：11/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S12][WAIT] [T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (5)", body:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900

计划时间：12:50-13:05
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：12/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S13][WAIT] [T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (1)", body:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600

计划时间：13:05-13:35
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：13/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S14][WAIT] [T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (2)", body:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600

计划时间：13:35-14:05
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：14/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S15][WAIT] [T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (3)", body:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600

计划时间：14:05-14:35
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：15/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S16][WAIT] [T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (4)", body:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600

计划时间：14:35-14:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：16/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S17][WAIT] [T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (1)", body:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700

计划时间：14:50-15:20
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：17/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S18][WAIT] [T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (2)", body:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700

计划时间：15:20-15:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：18/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S19][WAIT] [T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (3)", body:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700

计划时间：15:50-16:20
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：19/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S20][WAIT] [T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (1)", body:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200

计划时间：16:20-16:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：20/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S21][WAIT] [T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (2)", body:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200

计划时间：16:50-17:20
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：21/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
  make new reminder at end of reminders of targetList with properties {name:"[D01][S22][WAIT] [T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (3)", body:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200

计划时间：17:20-17:50
顺序状态：WAIT：等待前一项完成后由后台自动激活。
序号：22/22
完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。"}
end tell
