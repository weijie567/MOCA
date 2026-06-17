from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.study.common import (
    DAILY_DIR,
    REPO_ROOT,
    daily_file,
    date_from_arg,
    git_snapshot,
    load_config,
    load_json,
    now_iso,
    rel,
    repo_path,
    resolve_day,
    task_output_paths,
    write_json,
    write_text,
)


def visible_chars(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def jsonl_report(path: Path) -> tuple[int, int]:
    valid = 0
    invalid = 0
    if not path.exists():
        return valid, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
            valid += 1
        except json.JSONDecodeError:
            invalid += 1
    return valid, invalid


def section_has_content(text: str, heading: str) -> bool:
    pattern = re.compile(rf"(?m)^#+\s*{re.escape(heading)}\s*$")
    match = pattern.search(text)
    if not match:
        return False
    next_heading = re.search(r"(?m)^#+\s+", text[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(text)
    section = text[match.end() : end]
    meaningful = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"-", "- ", "：", ":"}:
            continue
        if line in {"- 业务语言：", "- 技术实现：", "- 为什么这么设计：", "- 不这么设计的问题："}:
            continue
        if line.endswith("：") and len(line) <= 20:
            continue
        meaningful.append(line)
    return bool(meaningful)


def inspect_file(path_value: str) -> dict[str, Any]:
    path = repo_path(path_value)
    report: dict[str, Any] = {
        "path": path_value,
        "exists": path.exists(),
        "missing": [],
        "evidence": [],
    }
    if not path.exists():
        report["missing"].append("file_missing")
        return report

    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    report["char_count"] = visible_chars(text)
    report["evidence"].append("file_exists")
    return report


def inspect_task_content(outputs: list[dict[str, Any]], checks: dict[str, Any]) -> dict[str, Any]:
    parts: list[str] = []
    jsonl_valid = 0
    jsonl_invalid = 0
    for output in outputs:
        path_value = output["path"]
        path = repo_path(path_value)
        if not path.exists() or not path.is_file():
            continue
        if path.suffix == ".jsonl":
            valid, invalid = jsonl_report(path)
            jsonl_valid += valid
            jsonl_invalid += invalid
        parts.append(f"\n\n<!-- {path_value} -->\n\n")
        parts.append(path.read_text(encoding="utf-8", errors="replace"))

    text = "".join(parts)
    report: dict[str, Any] = {
        "char_count": visible_chars(text),
        "missing": [],
        "evidence": [],
    }

    for heading in checks.get("required_headings", []):
        if heading not in text:
            report["missing"].append(f"heading:{heading}")
        else:
            report["evidence"].append(f"heading:{heading}")

    for heading in checks.get("required_nonempty_headings", []):
        if section_has_content(text, heading):
            report["evidence"].append(f"section_content:{heading}")
        else:
            report["missing"].append(f"section_empty:{heading}")

    for keyword in checks.get("required_keywords", []):
        if keyword not in text:
            report["missing"].append(f"keyword:{keyword}")
        else:
            report["evidence"].append(f"keyword:{keyword}")

    min_chars = int(checks.get("min_chars") or 0)
    if min_chars and report["char_count"] < min_chars:
        report["missing"].append(f"min_chars:{min_chars}")
    elif min_chars:
        report["evidence"].append(f"min_chars:{min_chars}")

    if checks.get("requires_mermaid") and "```mermaid" not in text and "flowchart " not in text:
        report["missing"].append("mermaid")
    elif checks.get("requires_mermaid"):
        report["evidence"].append("mermaid")

    min_jsonl = int(checks.get("jsonl_min_lines") or 0)
    if min_jsonl:
        report["jsonl_valid_lines"] = jsonl_valid
        report["jsonl_invalid_lines"] = jsonl_invalid
        if jsonl_valid < min_jsonl:
            report["missing"].append(f"jsonl_min_lines:{min_jsonl}")
        if jsonl_invalid:
            report["missing"].append(f"jsonl_invalid_lines:{jsonl_invalid}")
        if jsonl_valid >= min_jsonl and jsonl_invalid == 0:
            report["evidence"].append(f"jsonl_valid_lines:{jsonl_valid}")

    return report


def task_status(
    task: dict[str, Any], file_reports: list[dict[str, Any]], content_report: dict[str, Any], log_text: str
) -> str:
    marker = task["id"]
    if marker in log_text and "CUT" in log_text:
        return "CUT"
    if marker in log_text and "BLOCKED" in log_text:
        return "BLOCKED"
    if not file_reports or not any(report["exists"] for report in file_reports):
        return "MISSING"
    if all(report["exists"] for report in file_reports) and not content_report["missing"]:
        return "DONE"
    return "PARTIAL"


def build_audit(spec: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    day = spec["day"]
    log_path = daily_file(day, "log.md")
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    tasks = []
    for task in spec["tasks"]:
        checks = task.get("checks", {})
        reports = [inspect_file(output["path"]) for output in task.get("outputs", [])]
        content_report = inspect_task_content(task.get("outputs", []), checks)
        status = task_status(task, reports, content_report, log_text)
        tasks.append(
            {
                "id": task["id"],
                "title": task["title"],
                "type": task["type"],
                "status": status,
                "outputs": reports,
                "content_check": content_report,
                "human_checks": task.get("human_checks", []),
                "unverifiable": task.get("human_checks", []),
            }
        )

    done = sum(1 for task in tasks if task["status"] == "DONE")
    partial = sum(1 for task in tasks if task["status"] == "PARTIAL")
    missing = sum(1 for task in tasks if task["status"] == "MISSING")
    blocked = sum(1 for task in tasks if task["status"] == "BLOCKED")
    cut = sum(1 for task in tasks if task["status"] == "CUT")
    minimum_ids = set(spec.get("minimum_pass_task_ids", []))
    minimum_pass = all(task["status"] == "DONE" for task in tasks if task["id"] in minimum_ids)

    return {
        "schema_version": 1,
        "day": day,
        "date": spec.get("date"),
        "theme": spec.get("theme"),
        "created_at": now_iso(),
        "summary": {
            "done": done,
            "partial": partial,
            "missing": missing,
            "blocked": blocked,
            "cut": cut,
            "total": len(tasks),
            "minimum_pass": minimum_pass,
        },
        "baseline": baseline,
        "git_now": git_snapshot(),
        "tasks": tasks,
    }


def render_review_draft(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        f"# Day {audit['day']} Review Draft",
        "",
        "## 1. 总体结论",
        f"- 主题：{audit['theme']}",
        f"- 完成度：{summary['done']}/{summary['total']} DONE，{summary['partial']} PARTIAL，{summary['missing']} MISSING",
        f"- 是否达到最低通过线：{'是' if summary['minimum_pass'] else '否'}",
        "- 说明：此草稿只基于仓库文件证据，不判断真实理解程度。",
        "",
        "## 2. 任务完成表",
        "",
        "| ID | 任务 | 状态 | 证据 | 缺口 |",
        "|---|---|---|---|---|",
    ]
    for task in audit["tasks"]:
        evidence: list[str] = []
        missing: list[str] = []
        for output in task["outputs"]:
            if output.get("evidence"):
                evidence.extend(f"`{output['path']}`:{item}" for item in output["evidence"])
            if output.get("missing"):
                missing.extend(f"`{output['path']}`:{item}" for item in output["missing"])
        evidence.extend(task.get("content_check", {}).get("evidence", []))
        missing.extend(task.get("content_check", {}).get("missing", []))
        lines.append(
            f"| {task['id']} | {task['title']} | {task['status']} | {'<br>'.join(evidence) or '无'} | {'<br>'.join(missing) or '无'} |"
        )

    lines.extend(["", "## 3. 产物审计", ""])
    for task in audit["tasks"]:
        for output in task["outputs"]:
            lines.append(f"- `{output['path']}` —— {'存在' if output['exists'] else '缺失'}；状态：{task['status']}")

    lines.extend(["", "## 4. 今日偏差", ""])
    for task in audit["tasks"]:
        if task["status"] != "DONE":
            lines.append(f"- {task['id']} {task['status']}：需要补 `{', '.join(report['path'] for report in task['outputs'])}`")
    if all(task["status"] == "DONE" for task in audit["tasks"]):
        lines.append("- 当前机器审计未发现计划内缺口。")

    lines.extend(
        [
            "",
            "## 5. 面试资产提取",
            "- 面试可讲点 1：待人工从今日产物中确认。",
            "- 面试可讲点 2：待人工从今日产物中确认。",
            "- 面试可讲点 3：待人工从今日产物中确认。",
            "",
            "## 6. 明日调整建议",
            "- 优先补 PARTIAL / MISSING 任务对应的核心产物。",
            "- 如果最低通过线未达成，明天第一个任务先补最低通过线。",
            "- 保留 trace / eval / risk 三件事，不为完整性硬啃偏题内容。",
            "",
            "## 7. 需要我人工确认的问题",
        ]
    )
    unverifiable = []
    for task in audit["tasks"]:
        for item in task.get("unverifiable", []):
            unverifiable.append(f"- {task['id']}：{item}")
    lines.extend(unverifiable or ["- 当前无人工确认项。"])
    lines.append("")
    return "\n".join(lines)


def render_review_prompt(day: int) -> str:
    return f"""你现在是我的「每日学习任务审计员 + 复盘草稿生成器」。

请基于当前 MOCA 仓库，审计第 {day} 天任务完成情况。

请读取：
- `study_plan/portfolio/daily/day{day:02d}_tasks.json`
- `study_plan/portfolio/daily/day{day:02d}_audit.json`
- `study_plan/portfolio/daily/day{day:02d}_baseline.json`
- `study_plan/portfolio/daily/day{day:02d}_log.md`

请只基于仓库真实证据判断，不要猜测，不要美化。
凡是机器审计标记 PARTIAL/MISSING/BLOCKED/CUT 的任务，不得改写成 DONE。
凡是涉及「是否理解」「是否能讲清」「是否读完」的内容，一律放入人工确认区。

请更新：
- `study_plan/portfolio/daily/day{day:02d}_review_draft.md`
- 如有明日债务，生成 `study_plan/portfolio/daily/day{day:02d}_carryover.json`

输出结构：
1. 总体结论
2. 任务完成表
3. 产物审计
4. 今日偏差
5. 面试资产提取
6. 明日调整建议
7. 需要我人工确认的问题
"""


def maybe_run_codex(prompt_path: Path, output_path: Path, codex_path: str) -> None:
    with prompt_path.open("r", encoding="utf-8") as prompt:
        subprocess.run(
            [codex_path, "exec", "-C", str(REPO_ROOT), "-s", "workspace-write", "-o", str(output_path), "-"],
            stdin=prompt,
            cwd=REPO_ROOT,
            check=False,
            text=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a daily MOCA study task file.")
    parser.add_argument("--day", default="auto", help="Day number 1..30, or auto from automation_config.json")
    parser.add_argument("--date", default=None, help="Audit date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--no-draft", action="store_true", help="Do not write deterministic review draft.")
    parser.add_argument("--codex", action="store_true", help="Run codex exec with the generated review prompt.")
    args = parser.parse_args()

    run_date = date_from_arg(args.date)
    config = load_config(run_date, create_if_missing=False)
    day = resolve_day(args.day, config, run_date)
    tasks_path = daily_file(day, "tasks.json")
    baseline_path = daily_file(day, "baseline.json")
    if not tasks_path.exists():
        raise SystemExit(f"Missing tasks file: {rel(tasks_path)}. Run scripts/study/start_day.py first.")

    spec = load_json(tasks_path)
    baseline = load_json(baseline_path) if baseline_path.exists() else None
    audit = build_audit(spec, baseline)
    audit_path = daily_file(day, "audit.json")
    review_draft = daily_file(day, "review_draft.md")
    review_prompt = daily_file(day, "review_prompt.md")
    codex_output = daily_file(day, "review_codex_output.md")

    write_json(audit_path, audit, force=True)
    write_text(review_prompt, render_review_prompt(day), force=True)
    if not args.no_draft:
        write_text(review_draft, render_review_draft(audit), force=True)

    print(f"Day {day} audit written: {rel(audit_path)}")
    print(f"Review prompt written: {rel(review_prompt)}")
    if not args.no_draft:
        print(f"Review draft written: {rel(review_draft)}")

    if args.codex:
        maybe_run_codex(review_prompt, codex_output, str(config["codex_path"]))
        print(f"Codex output: {rel(codex_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
