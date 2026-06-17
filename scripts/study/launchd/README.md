# launchd 定时任务安装说明

这些是本机定时触发方案。建议先手动跑通 `start_day.py`、`calendar_sync.py`、`audit_day.py`，再安装定时任务。

## 1. 建议的定时节奏

- 05:05：生成并写入 Apple Calendar。
- 05:07：生成并写入 Apple Reminders。
- 22:55：导入 Reminders 已完成记录。
- 23:00：执行机器审计并生成复盘草稿；审计完成后自动生成第二天任务与 baseline。
- 每 7 天：手动运行 `weekly_review.py --week N`，或另行加周任务。

## 2. 示例命令

```bash
cd /Users/ming/projects/MOCA
python3 scripts/study/start_day.py --day auto
python3 scripts/study/calendar_sync.py --day auto --write
python3 scripts/study/reminders_sync.py --day auto --sequential --write
bash scripts/study/build_reminders_advance.sh
scripts/study/bin/MOCARemindersAdvance.app/Contents/MacOS/MOCARemindersAdvance --day auto
python3 scripts/study/reminders_sync.py --day auto --import-completions
python3 scripts/study/audit_day.py --day auto
```

如果你想让 Codex 自动细化任务和复盘：

```bash
python3 scripts/study/start_day.py --day auto --codex
python3 scripts/study/audit_day.py --day auto --codex
```

## 3. 安装 launchd 模板

先确认 `study_plan/portfolio/daily/automation_config.json` 里的 `program_start_date` 是 Day 1 日期。

然后安装：

```bash
cp scripts/study/launchd/com.moca.study.*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.moca.study.calendar-sync.plist
launchctl load ~/Library/LaunchAgents/com.moca.study.reminders-sync.plist
launchctl load ~/Library/LaunchAgents/com.moca.study.reminders-import.plist
launchctl load ~/Library/LaunchAgents/com.moca.study.audit-day.plist
launchctl load ~/Library/LaunchAgents/com.moca.study.weekly-review.plist
```

查看状态：

```bash
launchctl list | rg 'com.moca.study'
```

卸载：

```bash
launchctl unload ~/Library/LaunchAgents/com.moca.study.calendar-sync.plist
launchctl unload ~/Library/LaunchAgents/com.moca.study.reminders-sync.plist
launchctl unload ~/Library/LaunchAgents/com.moca.study.reminders-import.plist
launchctl unload ~/Library/LaunchAgents/com.moca.study.audit-day.plist
launchctl unload ~/Library/LaunchAgents/com.moca.study.weekly-review.plist
```

## Reminders 自动推进状态

`com.moca.study.reminders-advance.plist` 是实验项：目标是每 60 秒读取 Reminders 完成状态，完成当前项后激活下一项。

当前机器上需要先给 `MOCA Reminders Advance` 授予 Reminders 权限。启用流程：

```bash
bash scripts/study/enable_reminders_advance.sh
```

脚本会打开系统设置，你需要在 Reminders 隐私项里打开 `MOCA Reminders Advance`。测试通过后，它会加载每 60 秒推进一次的 watcher。

## 4. Apple Calendar 权限

第一次运行 `calendar_sync.py --write` 时，macOS 可能会要求 Terminal 或 Python 获得 Calendar 权限。授权后后续才能自动写入事件。

## 5. 不建议无人值守修改源码

定时任务默认只负责学习计划和作品集，不要在 23:00 自动执行业务代码修改。
