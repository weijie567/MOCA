from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.study.common import (
    REPO_ROOT,
    add_minutes,
    daily_file,
    date_from_arg,
    load_config,
    load_json,
    parse_hhmm,
    rel,
    resolve_day,
    task_output_paths,
    write_text,
)


MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def apple_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_events(spec: dict[str, Any], run_date: str, start_time: str) -> list[dict[str, Any]]:
    schedule = spec.get("schedule", {})
    cycle_work = int(schedule.get("cycle_work_minutes") or 30)
    cycle_break_value = schedule.get("cycle_break_minutes")
    cycle_break = 8 if cycle_break_value is None else int(cycle_break_value)
    hour, minute = parse_hhmm(start_time)
    current = datetime.fromisoformat(f"{run_date}T{hour:02d}:{minute:02d}:00")
    events: list[dict[str, Any]] = []
    day_tag = f"[MOCA-D{spec['day']:02d}]"

    for task in spec["tasks"]:
        remaining = int(task.get("duration_minutes") or 0)
        part = 1
        while remaining > 0:
            work_minutes = min(cycle_work, remaining)
            end = add_minutes(current, work_minutes)
            outputs = "\n".join(f"- {path}" for path in task_output_paths(task))
            checks = task.get("checks", {})
            description = "\n".join(
                [
                    f"任务：{task['title']}",
                    f"类型：{task['type']}",
                    "",
                    "产物：",
                    outputs or "- 无",
                    "",
                    "验收：",
                    "- 标题：" + "、".join(checks.get("required_headings", [])),
                    "- 关键词：" + "、".join(checks.get("required_keywords", [])),
                    f"- 至少字符数：{checks.get('min_chars') or 0}",
                ]
            )
            events.append(
                {
                    "title": f"{day_tag}[{task['id']}] {task['title']} ({part})",
                    "start": current,
                    "end": end,
                    "description": description,
                }
            )
            remaining -= work_minutes
            current = end
            if cycle_break > 0 and (remaining > 0 or task != spec["tasks"][-1]):
                break_end = add_minutes(current, cycle_break)
                events.append(
                    {
                        "title": f"{day_tag}[BREAK] 休息 {cycle_break} 分钟",
                        "start": current,
                        "end": break_end,
                        "description": "离开屏幕，喝水，活动。不要开新资料。",
                    }
                )
                current = break_end
            part += 1
    return events


def apple_date_call(dt: datetime) -> str:
    return f"my makeDate({dt.year}, {MONTH_NAMES[dt.month - 1]}, {dt.day}, {dt.hour}, {dt.minute})"


def render_applescript(calendar_name: str, day: int, events: list[dict[str, Any]]) -> str:
    day_tag = f"[MOCA-D{day:02d}]"
    lines = [
        "on makeDate(y, m, d, h, minValue)",
        "  set dt to current date",
        "  set year of dt to y",
        "  set month of dt to m",
        "  set day of dt to d",
        "  set hours of dt to h",
        "  set minutes of dt to minValue",
        "  set seconds of dt to 0",
        "  return dt",
        "end makeDate",
        "",
        'tell application "Calendar"',
        f"  set calName to {apple_quote(calendar_name)}",
        "  set targetCalendar to missing value",
        "  repeat with c in calendars",
        "    if name of c is calName then set targetCalendar to c",
        "  end repeat",
        "  if targetCalendar is missing value then",
        "    set targetCalendar to make new calendar with properties {name:calName}",
        "  end if",
        f"  delete (every event of targetCalendar whose summary contains {apple_quote(day_tag)})",
    ]
    for event in events:
        lines.append(
            "  make new event at end of events of targetCalendar with properties "
            + "{summary:"
            + apple_quote(event["title"])
            + ", start date:"
            + apple_date_call(event["start"])
            + ", end date:"
            + apple_date_call(event["end"])
            + ", description:"
            + apple_quote(event["description"])
            + "}"
        )
    lines.append("end tell")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or write Apple Calendar events for a MOCA study day.")
    parser.add_argument("--day", default="auto", help="Day number 1..30, or auto from automation_config.json")
    parser.add_argument("--date", default=None, help="Calendar date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--start", default=None, help="Work start time HH:MM. Defaults to config/tasks.")
    parser.add_argument("--write", action="store_true", help="Run osascript to write events into Apple Calendar.")
    args = parser.parse_args()

    run_date = date_from_arg(args.date)
    config = load_config(run_date, create_if_missing=False)
    day = resolve_day(args.day, config, run_date)
    tasks_path = daily_file(day, "tasks.json")
    if not tasks_path.exists():
        raise SystemExit(f"Missing tasks file: {rel(tasks_path)}. Run scripts/study/start_day.py first.")
    spec = load_json(tasks_path)
    start_time = args.start or spec.get("schedule", {}).get("work_start") or config["default_work_start"]
    calendar_name = spec.get("schedule", {}).get("calendar_name") or config["calendar_name"]
    events = build_events(spec, run_date.isoformat(), start_time)
    script = render_applescript(calendar_name, day, events)
    script_path = daily_file(day, "calendar.applescript")
    write_text(script_path, script, force=True)

    print(f"AppleScript written: {rel(script_path)}")
    print(f"Events: {len(events)}")
    print(f"Calendar: {calendar_name}")
    if args.write:
        subprocess.run(["osascript", str(script_path)], cwd=REPO_ROOT, check=False)
        print("osascript executed. macOS may ask for Calendar permission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
