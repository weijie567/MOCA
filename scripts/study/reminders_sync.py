from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.study.calendar_sync import build_events
from scripts.study.common import (
    REPO_ROOT,
    daily_file,
    date_from_arg,
    load_config,
    load_json,
    parse_hhmm,
    rel,
    resolve_day,
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


def apple_date_call(dt: datetime) -> str:
    return f"my makeDate({dt.year}, {MONTH_NAMES[dt.month - 1]}, {dt.day}, {dt.hour}, {dt.minute})"


def event_reminder_name(day: int, event: dict[str, Any]) -> str:
    return event["title"].replace(f"[MOCA-D{day:02d}]", f"[D{day:02d}]")


def sequential_reminder_name(day: int, event: dict[str, Any], index: int, active: bool) -> str:
    status = "ACTIVE" if active else "WAIT"
    base = event["title"].replace(f"[MOCA-D{day:02d}]", "").strip()
    return f"[D{day:02d}][S{index:02d}][{status}] {base}"


def render_reminders_applescript(list_name: str, day: int, events: list[dict[str, Any]], *, sequential: bool) -> str:
    day_tag = f"[D{day:02d}]"
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
        "tell application \"Reminders\"",
        f"  set listName to {apple_quote(list_name)}",
        "  if not (exists list listName) then",
        "    make new list with properties {name:listName}",
        "  end if",
        "  set targetList to list listName",
        f"  delete (every reminder of targetList whose name contains {apple_quote(day_tag)})",
    ]
    for index, event in enumerate(events, start=1):
        active = index == 1
        name = sequential_reminder_name(day, event, index, active) if sequential else event_reminder_name(day, event)
        status_text = "ACTIVE：当前任务，完成后自动启动下一项。" if active else "WAIT：等待前一项完成后由后台自动激活。"
        body = "\n".join(
            [
                event["description"],
                "",
                f"计划时间：{event['start'].strftime('%H:%M')}-{event['end'].strftime('%H:%M')}",
                f"顺序状态：{status_text}" if sequential else "顺序状态：固定时间提醒",
                f"序号：{index}/{len(events)}",
                "完成方式：在 Reminders 勾选完成，晚上审计时作为人工确认参考。",
            ]
        )
        properties = "{name:" + apple_quote(name) + ", body:" + apple_quote(body)
        if not sequential or active:
            properties += ", due date:" + apple_date_call(event["start"])
            properties += ", remind me date:" + apple_date_call(event["start"])
        properties += "}"
        lines.append("  make new reminder at end of reminders of targetList with properties " + properties)
    lines.append("end tell")
    lines.append("")
    return "\n".join(lines)


def reminder_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if "[BREAK]" not in str(event.get("title", ""))]


def render_import_completions_applescript(list_name: str, day: int) -> str:
    day_tag = f"[D{day:02d}]"
    return "\n".join(
        [
            "set output to \"\"",
            "tell application \"Reminders\"",
            f"  if not (exists list {apple_quote(list_name)}) then return output",
            f"  set targetList to list {apple_quote(list_name)}",
            f"  set matchedReminders to every reminder of targetList whose name contains {apple_quote(day_tag)}",
            "  repeat with r in matchedReminders",
            "    set completedFlag to completed of r",
            "    set completionValue to \"\"",
            "    try",
            "      set completionValue to completion date of r as string",
            "    end try",
            "    set output to output & (name of r) & tab & completedFlag & tab & completionValue & linefeed",
            "  end repeat",
            "end tell",
            "return output",
            "",
        ]
    )


def render_status_applescript(list_name: str, day: int) -> str:
    day_tag = f"[D{day:02d}]"
    return "\n".join(
        [
            "set output to \"\"",
            "tell application \"Reminders\"",
            f"  if not (exists list {apple_quote(list_name)}) then return output",
            f"  set targetList to list {apple_quote(list_name)}",
            f"  set matchedReminders to every reminder of targetList whose name contains {apple_quote(day_tag)}",
            "  repeat with r in matchedReminders",
            "    set completedFlag to false",
            "    try",
            "      set completedFlag to completed of r",
            "    end try",
            "    set output to output & (name of r) & tab & (completedFlag as string) & linefeed",
            "  end repeat",
            "end tell",
            "return output",
            "",
        ]
    )


def render_activate_applescript(list_name: str, day: int, seq: int, new_name: str) -> str:
    seq_tag = f"[D{day:02d}][S{seq:02d}]"
    started = datetime.now().strftime("%Y-%m-%d %H:%M")
    return "\n".join(
        [
            "tell application \"Reminders\"",
            f"  set targetList to list {apple_quote(list_name)}",
            f"  set matchedReminders to every reminder of targetList whose name contains {apple_quote(seq_tag)}",
            "  if (count of matchedReminders) is greater than 0 then",
            "    set r to item 1 of matchedReminders",
            f"    set name of r to {apple_quote(new_name)}",
            "    set due date of r to current date",
            "    set remind me date of r to current date",
            f"    set body of r to (body of r) & linefeed & {apple_quote('实际开始：' + started)}",
            "  end if",
            "end tell",
            "",
        ]
    )


def parse_reminder_status(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        name, _, completed = line.partition("\t")
        seq_match = re.search(r"\[S(\d+)\]", name)
        status_match = re.search(r"\[(ACTIVE|WAIT)\]", name)
        if not seq_match:
            continue
        rows.append(
            {
                "seq": int(seq_match.group(1)),
                "name": name,
                "completed": completed.strip().lower() == "true",
                "status": status_match.group(1) if status_match else "",
            }
        )
    return sorted(rows, key=lambda item: item["seq"])


def advance_on_completion(list_name: str, day: int) -> str:
    status_script = render_status_applescript(list_name, day)
    status_path = daily_file(day, "reminders_status.applescript")
    write_text(status_path, status_script, force=True)
    result = subprocess.run(["osascript", str(status_path)], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    rows = parse_reminder_status(result.stdout)
    if not rows:
        return "no reminders"
    first_open = next((row for row in rows if not row["completed"]), None)
    if first_open is None:
        return "all complete"
    if first_open["status"] == "ACTIVE":
        return f"active unchanged: S{first_open['seq']:02d}"

    new_name = first_open["name"].replace("[WAIT]", "[ACTIVE]")
    activate_script = render_activate_applescript(list_name, day, first_open["seq"], new_name)
    activate_path = daily_file(day, "reminders_activate.applescript")
    write_text(activate_path, activate_script, force=True)
    result = subprocess.run(["osascript", str(activate_path)], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    log_path = daily_file(day, "log.md")
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else f"# Day {day} 执行日志\n"
    if "## Reminders 自动推进记录" not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n## Reminders 自动推进记录\n"
    text += f"- {datetime.now().isoformat(timespec='seconds')} 激活 S{first_open['seq']:02d}：{new_name}\n"
    log_path.write_text(text, encoding="utf-8")
    return f"activated S{first_open['seq']:02d}"


def append_imported_completions(day: int, raw: str) -> None:
    if not raw.strip():
        return
    log_path = daily_file(day, "log.md")
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else f"# Day {day} 执行日志\n"
    if "## Reminders 完成记录" not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n## Reminders 完成记录\n"
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, completed = parts[0], parts[1]
        completion_date = parts[2] if len(parts) > 2 else ""
        if completed.lower() == "true":
            text += f"- DONE {name} {completion_date}\n"
    log_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync MOCA study blocks into Apple Reminders.")
    parser.add_argument("--day", default="auto", help="Day number 1..30, or auto from automation_config.json")
    parser.add_argument("--date", default=None, help="Reminder date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--start", default=None, help="Work start time HH:MM. Defaults to tasks/config.")
    parser.add_argument("--list", default="MOCA 30 Days", help="Reminders list name.")
    parser.add_argument("--sequential", action="store_true", help="Only the first reminder is active; future tasks wait.")
    parser.add_argument("--write", action="store_true", help="Write reminders via osascript.")
    parser.add_argument("--import-completions", action="store_true", help="Import completed reminders into day log.")
    parser.add_argument("--advance-on-completion", action="store_true", help="Activate the next waiting reminder if current is complete.")
    args = parser.parse_args()

    run_date = date_from_arg(args.date)
    config = load_config(run_date, create_if_missing=False)
    day = resolve_day(args.day, config, run_date)
    tasks_path = daily_file(day, "tasks.json")
    if not tasks_path.exists():
        raise SystemExit(f"Missing tasks file: {rel(tasks_path)}. Run scripts/study/start_day.py first.")

    if args.advance_on_completion:
        message = advance_on_completion(args.list, day)
        print(message)
        return 0

    if args.import_completions:
        script = render_import_completions_applescript(args.list, day)
        script_path = daily_file(day, "reminders_import.applescript")
        write_text(script_path, script, force=True)
        result = subprocess.run(["osascript", str(script_path)], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip())
        append_imported_completions(day, result.stdout)
        print(f"Imported completed reminders into {rel(daily_file(day, 'log.md'))}")
        return 0

    spec = load_json(tasks_path)
    start_time = args.start or spec.get("schedule", {}).get("work_start") or config["default_work_start"]
    parse_hhmm(start_time)
    events = reminder_events(build_events(spec, run_date.isoformat(), start_time))
    script = render_reminders_applescript(args.list, day, events, sequential=args.sequential)
    script_path = daily_file(day, "reminders.applescript")
    write_text(script_path, script, force=True)

    print(f"AppleScript written: {rel(script_path)}")
    print(f"Reminders: {len(events)}")
    print(f"List: {args.list}")
    if args.write:
        subprocess.run(["osascript", str(script_path)], cwd=REPO_ROOT, check=False)
        print("osascript executed. macOS may ask for Reminders permission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
