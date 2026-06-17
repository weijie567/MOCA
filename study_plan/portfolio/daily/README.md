# MOCA 每日自动化说明

这套脚本把 30 天计划拆成可审计的每日任务，并支持晚间复盘、Apple Calendar 事件生成和每周总结。

## 1. 计划生成策略

正常自动流程不在早上生成当天任务。每天 23:00 的晚间审计完成后，会自动触发 `plan-next-day`，生成第二天的具体任务、baseline 和 Codex 细化结果。

只有初始化第一天、补救失败、或手动重建某天计划时，才在仓库根目录运行：

```bash
python3 scripts/study/start_day.py --day auto
```

运行会创建：

- `study_plan/portfolio/daily/automation_config.json`
- `study_plan/portfolio/daily/dayXX_tasks.json`
- `study_plan/portfolio/daily/dayXX_tasks.md`
- `study_plan/portfolio/daily/dayXX_log.md`
- `study_plan/portfolio/daily/dayXX_baseline.json`
- `study_plan/portfolio/daily/dayXX_start_prompt.md`

如果要让 Codex 继续细化任务：

```bash
python3 scripts/study/start_day.py --day auto --codex
```

## 2. 写入 Apple Calendar

先生成 AppleScript 草稿：

```bash
python3 scripts/study/calendar_sync.py --day auto
```

确认 `dayXX_calendar.applescript` 后再写入日历：

```bash
python3 scripts/study/calendar_sync.py --day auto --write
```

脚本会写入名为 `MOCA 30 Days` 的日历，并按 30 分钟工作 + 8 分钟休息拆事件。

## 3. 同步到 Apple Reminders

如果想用 Reminders 的“今天”和勾选完成状态：

```bash
python3 scripts/study/reminders_sync.py --day auto
python3 scripts/study/reminders_sync.py --day auto --sequential --write
```

脚本会写入 `MOCA 30 Days` 提醒事项列表，并为每个 30 分钟任务块创建一个提醒；休息时间由人工自行安排，不生成 Reminders 休息提醒。顺序模式下只有第一个任务是 `ACTIVE` 并有提醒时间，后续任务是 `WAIT`。

点击完成后，可以手动推进下一项：

```bash
bash scripts/study/build_reminders_advance.sh
scripts/study/bin/MOCARemindersAdvance.app/Contents/MacOS/MOCARemindersAdvance --day auto
```

`com.moca.study.reminders-advance` 需要先给 `MOCA Reminders Advance` 授予 Reminders 权限：

```bash
bash scripts/study/enable_reminders_advance.sh
```

授权和测试通过后，后台会每 60 秒检查一次 Reminders：如果当前 `[ACTIVE]` 已完成，就把下一项 `[WAIT]` 改成 `[ACTIVE]`，并把提醒时间设置为当前时间。

晚上可以把已完成提醒导入日志：

```bash
python3 scripts/study/reminders_sync.py --day auto --import-completions
```

说明：

- Reminders 原生适合查看“今天任务”和手动勾完成。
- Calendar 仍适合时间占位；如需休息占位，看 Calendar，不用 Reminders 提醒。
- Reminders 本身没有任务依赖；动态推进由 `--advance-on-completion` 轮询脚本实现。

## 4. 自动触发策略

当前自动化以 `scripts/study/` 为唯一真身，LaunchAgent 不再调用 `~/Documents/MOCA-study-reminders/`。

- 晚间审计：`morning_autorun.py audit-day` 在 23:00 运行；完成当天审计后，会自动触发 `plan-next-day`，生成第二天任务并带 `--codex` 细化。
- 遗留策略：生成 Day N 时会读取 Day N-1 的 `dayXX_audit.json`，把所有 `MISSING` / `PARTIAL` 任务作为 `C*` carryover 置顶带入当天。
- 安全边界：如果当天审计命令异常退出，就不会生成第二天计划；如果第二天任务文件已存在，脚本不会覆盖。

## 5. 面试追问规则

每日技术面追问必须引用 `study_plan/portfolio/daily/interview_question_rules.md`：每道题都要回到 MOCA，包含 `MOCA绑定`、`证据路径`、`当前边界` 和状态，避免答成通用八股。

## 6. 晚上自动审计与复盘草稿

```bash
python3 scripts/study/audit_day.py --day auto
```

输出：

- `dayXX_audit.json`
- `dayXX_review_prompt.md`
- `dayXX_review_draft.md`

如果要让 Codex 基于机器审计结果重写复盘草稿：

```bash
python3 scripts/study/audit_day.py --day auto --codex
```

## 6. 每七天总结

```bash
python3 scripts/study/weekly_review.py --week 1
```

输出：

- `study_plan/portfolio/weekly_reviews/week1_auto_summary.md`
- `study_plan/portfolio/daily/week1_review_prompt.md`

## 6. 自动化边界

- 自动任务只应该写 `study_plan/portfolio/`。
- 不要让无人值守任务修改 `src/`、`tests/` 或 `.planning/`。
- Codex 只能判断文件证据完成度，不能判断你是否真的理解。
- 所有 `UNVERIFIABLE` 项都需要人工确认。
