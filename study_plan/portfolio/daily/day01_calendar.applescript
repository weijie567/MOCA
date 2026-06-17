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

tell application "Calendar"
  set calName to "MOCA 30 Days"
  set targetCalendar to missing value
  repeat with c in calendars
    if name of c is calName then set targetCalendar to c
  end repeat
  if targetCalendar is missing value then
    set targetCalendar to make new calendar with properties {name:calName}
  end if
  delete (every event of targetCalendar whose summary contains "[MOCA-D01]")
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (1)", start date:my makeDate(2026, June, 18, 7, 50), end date:my makeDate(2026, June, 18, 8, 20), description:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (2)", start date:my makeDate(2026, June, 18, 8, 20), end date:my makeDate(2026, June, 18, 8, 50), description:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T1] 理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent) (3)", start date:my makeDate(2026, June, 18, 8, 50), end date:my makeDate(2026, June, 18, 9, 5), description:"任务：理论压缩：读 Anthropic《Building Effective Agents》(workflow vs agent)
类型：theory

产物：
- study_plan/portfolio/daily/day01_notes.md

验收：
- 标题：今日理论笔记、关键概念、对 MOCA 的设计启发、不懂的问题
- 关键词：MOCA
- 至少字符数：500"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (1)", start date:my makeDate(2026, June, 18, 9, 5), end date:my makeDate(2026, June, 18, 9, 35), description:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (2)", start date:my makeDate(2026, June, 18, 9, 35), end date:my makeDate(2026, June, 18, 10, 5), description:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (3)", start date:my makeDate(2026, June, 18, 10, 5), end date:my makeDate(2026, June, 18, 10, 35), description:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T2] 拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图 (4)", start date:my makeDate(2026, June, 18, 10, 35), end date:my makeDate(2026, June, 18, 10, 50), description:"任务：拆解：通读 README+TOOL_ARCHITECTURE.md+.planning/ROADMAP.md，画模块全景草图
类型：analysis

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md

验收：
- 标题：拆解对象、核心流程、风险点、trace / eval / risk
- 关键词：risk、trace、eval
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (1)", start date:my makeDate(2026, June, 18, 10, 50), end date:my makeDate(2026, June, 18, 11, 20), description:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (2)", start date:my makeDate(2026, June, 18, 11, 20), end date:my makeDate(2026, June, 18, 11, 50), description:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (3)", start date:my makeDate(2026, June, 18, 11, 50), end date:my makeDate(2026, June, 18, 12, 20), description:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (4)", start date:my makeDate(2026, June, 18, 12, 20), end date:my makeDate(2026, June, 18, 12, 50), description:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T3] 实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口 (5)", start date:my makeDate(2026, June, 18, 12, 50), end date:my makeDate(2026, June, 18, 13, 5), description:"任务：实战：跑通本地启动(docker-compose)；建 portfolio/ 目录；确认 Phase 15.1 计划入口
类型：practice

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：实战目标、最小可运行版本、验证记录、失败路径
- 关键词：trace、eval、risk
- 至少字符数：900"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (1)", start date:my makeDate(2026, June, 18, 13, 5), end date:my makeDate(2026, June, 18, 13, 35), description:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (2)", start date:my makeDate(2026, June, 18, 13, 35), end date:my makeDate(2026, June, 18, 14, 5), description:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (3)", start date:my makeDate(2026, June, 18, 14, 5), end date:my makeDate(2026, June, 18, 14, 35), description:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T4] 作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画） (4)", start date:my makeDate(2026, June, 18, 14, 35), end date:my makeDate(2026, June, 18, 14, 50), description:"任务：作品集产出：moca_internalize/00_模块全景图.md（手画，不许 AI 代画）
类型：output

产物：
- study_plan/portfolio/moca_internalize/00_模块全景图.md
- study_plan/portfolio/interview/day01_MOCA一分钟介绍.md
- study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md

验收：
- 标题：用途、核心内容、验收标准
- 关键词：面试、作品集
- 至少字符数：600"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (1)", start date:my makeDate(2026, June, 18, 14, 50), end date:my makeDate(2026, June, 18, 15, 20), description:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (2)", start date:my makeDate(2026, June, 18, 15, 20), end date:my makeDate(2026, June, 18, 15, 50), description:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T5] 沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结 (3)", start date:my makeDate(2026, June, 18, 15, 50), end date:my makeDate(2026, June, 18, 16, 20), description:"任务：沉淀：线A：内化已完成 Phase 14/15，准备 Phase 15.1 plan；D1 总结
类型：reflection

产物：
- study_plan/portfolio/daily/day01_log.md
- study_plan/portfolio/interview/day01_面试表达.md

验收：
- 标题：今日完成、偏差、明日 carryover、面试表达
- 关键词：为什么这么设计、不这么设计
- 至少字符数：700"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (1)", start date:my makeDate(2026, June, 18, 16, 20), end date:my makeDate(2026, June, 18, 16, 50), description:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (2)", start date:my makeDate(2026, June, 18, 16, 50), end date:my makeDate(2026, June, 18, 17, 20), description:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200"}
  make new event at end of events of targetCalendar with properties {summary:"[MOCA-D01][T6] 大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA） (3)", start date:my makeDate(2026, June, 18, 17, 20), end date:my makeDate(2026, June, 18, 17, 50), description:"任务：大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）
类型：interview

产物：
- study_plan/portfolio/daily/day01_interview_questions.md

验收：
- 标题：大厂技术追问候选题、今日 Top 5 追问、MOCA绑定、证据路径、当前边界
- 关键词：MOCA
- 至少字符数：1200"}
end tell
