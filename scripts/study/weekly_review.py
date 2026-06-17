from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.study.common import (
    DAILY_DIR,
    WEEKLY_DIR,
    daily_file,
    date_from_arg,
    load_config,
    load_json,
    rel,
    resolve_day,
    week_range,
    write_text,
)


def load_audits(start: int, end: int) -> list[dict[str, Any]]:
    audits = []
    for day in range(start, end + 1):
        path = daily_file(day, "audit.json")
        if path.exists():
            audits.append(load_json(path))
    return audits


def render_weekly_review(week: int, audits: list[dict[str, Any]], start: int, end: int) -> str:
    lines = [
        f"# Week {week} 自动周复盘",
        "",
        f"- 覆盖范围：Day {start} - Day {end}",
        f"- 已找到 audit：{len(audits)} 天",
        "",
        "## 1. 完成度汇总",
        "",
        "| Day | 主题 | DONE | PARTIAL | MISSING | BLOCKED | 最低通过 |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for audit in audits:
        summary = audit["summary"]
        lines.append(
            f"| {audit['day']} | {audit['theme']} | {summary['done']} | {summary['partial']} | "
            f"{summary['missing']} | {summary['blocked']} | {'是' if summary['minimum_pass'] else '否'} |"
        )

    lines.extend(["", "## 2. 本周未完成债务", ""])
    has_debt = False
    for audit in audits:
        for task in audit["tasks"]:
            if task["status"] != "DONE":
                has_debt = True
                output_paths = ", ".join(report["path"] for report in task["outputs"])
                lines.append(f"- Day {audit['day']} {task['id']} {task['status']}：{output_paths}")
    if not has_debt:
        lines.append("- 当前机器审计未发现计划内债务。")

    lines.extend(
        [
            "",
            "## 3. 面试资产候选",
            "- 从 DONE 的 moca_internalize / product / demos / evals / interview 产物中人工挑选 3-5 个。",
            "",
            "## 4. 下周调整建议",
            "- 把 PARTIAL / MISSING 中属于最低通过线的任务放到下周第一天。",
            "- 每天只保留一个最重要产物，避免为了完整性稀释面试资产。",
            "- 继续保留 trace / eval / risk 三件事。",
            "",
            "## 5. 人工确认",
            "- 本周最能讲的一个模块：",
            "- 本周最虚的一个产物：",
            "- 下周必须补的一个能力：",
            "",
        ]
    )
    return "\n".join(lines)


def render_weekly_prompt(week: int, start: int, end: int) -> str:
    return f"""你现在是我的「AI Builder 30 天训练周复盘教练」。

请基于 MOCA 仓库真实文件证据，汇总 Week {week}（Day {start}-{end}）。

请读取：
- `study_plan/portfolio/daily/day{start:02d}_audit.json` 到 `day{end:02d}_audit.json`
- 已存在的 `review_final.md`，如果没有则读取 `review_draft.md`
- 本周新增的 portfolio 产物

请生成：
- `study_plan/portfolio/weekly_reviews/week{week}.md`

要求：
- 不要夸奖，不要泛泛总结。
- 明确列出 DONE/PARTIAL/MISSING 的证据。
- 提取 3-5 条面试资产。
- 生成下周 carryover。
- 凡是理解程度无法从文件判断，一律放入人工确认区。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an automatic weekly study review from daily audits.")
    parser.add_argument("--week", default="auto", help="Week number starting from 1, or auto from config/date.")
    parser.add_argument("--date", default=None, help="Review date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--codex", action="store_true", help="Accepted for launchd compatibility; prompt output is always written.")
    args = parser.parse_args()

    if args.week == "auto":
        run_date = date_from_arg(args.date)
        config = load_config(run_date, create_if_missing=False)
        day = resolve_day("auto", config, run_date)
        week = ((day - 1) // 7) + 1
    else:
        week = int(args.week)

    start, end = week_range(week)
    audits = load_audits(start, end)
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    review_path = WEEKLY_DIR / f"week{week}_auto_summary.md"
    prompt_path = DAILY_DIR / f"week{week}_review_prompt.md"
    write_text(review_path, render_weekly_review(week, audits, start, end), force=True)
    write_text(prompt_path, render_weekly_prompt(week, start, end), force=True)
    print(f"Weekly auto summary written: {rel(review_path)}")
    print(f"Weekly Codex prompt written: {rel(prompt_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
