from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.study.common import (
    DAY_OUTPUTS,
    AUTOMATION_CONFIG,
    REPO_ROOT,
    DayPlan,
    daily_file,
    date_from_arg,
    ensure_portfolio_dirs,
    git_snapshot,
    load_config,
    load_json,
    now_iso,
    parse_main_plan,
    rel,
    resolve_day,
    task_output_paths,
    write_json,
    write_text,
)



def load_carryover_tasks(day: int) -> list[dict[str, Any]]:
    previous_day = day - 1
    if previous_day < 1:
        return []
    audit_path = daily_file(previous_day, "audit.json")
    previous_tasks_path = daily_file(previous_day, "tasks.json")
    if not audit_path.exists() or not previous_tasks_path.exists():
        return []

    audit = load_json(audit_path)
    previous_spec = load_json(previous_tasks_path)
    previous_tasks = {task["id"]: task for task in previous_spec.get("tasks", [])}
    carryover: list[dict[str, Any]] = []
    for audited in audit.get("tasks", []):
        status = audited.get("status")
        if status not in {"MISSING", "PARTIAL"}:
            continue
        source = previous_tasks.get(audited.get("id"))
        if not source:
            continue
        copied = dict(source)
        copied["id"] = f"C{len(carryover) + 1}"
        copied["type"] = "carryover"
        copied["title"] = f"Day {previous_day} 遗留：{source.get('title', audited.get('title', '未完成任务'))}"
        copied["carryover_from"] = {
            "day": previous_day,
            "task_id": audited.get("id"),
            "status": status,
            "audit_path": f"study_plan/portfolio/daily/day{previous_day:02d}_audit.json",
        }
        copied["human_checks"] = list(copied.get("human_checks", [])) + [
            "这是昨日遗留任务：先补完证据，再开始今日新增任务"
        ]
        carryover.append(copied)
    return carryover


def build_tasks(day_plan: DayPlan, config: dict[str, Any], run_date: str, work_start: str) -> dict[str, Any]:
    day = day_plan.day
    target_outputs = DAY_OUTPUTS.get(day, [])
    daily_notes = f"study_plan/portfolio/daily/day{day:02d}_notes.md"
    daily_log = f"study_plan/portfolio/daily/day{day:02d}_log.md"
    daily_interview_questions = f"study_plan/portfolio/daily/day{day:02d}_interview_questions.md"
    interview_output = f"study_plan/portfolio/interview/day{day:02d}_面试表达.md"

    task_minutes = [75, 105, 135, 105, 90, 90]
    tasks: list[dict[str, Any]] = [
        {
            "id": "T1",
            "type": "theory",
            "title": f"理论压缩：{day_plan.theory or day_plan.theme}",
            "duration_minutes": task_minutes[0],
            "outputs": [{"path": daily_notes, "required": True, "purpose": "理论阅读与设计启发"}],
            "checks": {
                "required_headings": ["今日理论笔记", "关键概念", "对 MOCA 的设计启发", "不懂的问题"],
                "required_nonempty_headings": ["今日理论笔记", "关键概念", "对 MOCA 的设计启发"],
                "required_keywords": ["MOCA"],
                "min_chars": 500,
            },
            "human_checks": ["是否能不用原文讲清今天理论和 MOCA 的关系"],
        },
        {
            "id": "T2",
            "type": "analysis",
            "title": f"拆解：{day_plan.analysis or day_plan.theme}",
            "duration_minutes": task_minutes[1],
            "outputs": target_outputs[:1] or [{"path": daily_notes, "required": True, "purpose": "拆解记录"}],
            "checks": {
                "required_headings": ["拆解对象", "核心流程", "风险点", "trace / eval / risk"],
                "required_nonempty_headings": ["拆解对象", "核心流程", "风险点", "trace / eval / risk"],
                "required_keywords": ["risk", "trace", "eval"],
                "min_chars": 700,
            },
            "human_checks": ["是否能对着拆解图或文档讲 3 分钟"],
        },
        {
            "id": "T3",
            "type": "practice",
            "title": f"实战：{day_plan.practice or day_plan.theme}",
            "duration_minutes": task_minutes[2],
            "outputs": target_outputs or [{"path": daily_notes, "required": True, "purpose": "实战记录"}],
            "checks": {
                "required_headings": ["实战目标", "最小可运行版本", "验证记录", "失败路径"],
                "required_nonempty_headings": ["实战目标", "验证记录", "失败路径"],
                "required_keywords": ["trace", "eval", "risk"],
                "min_chars": 900,
                "jsonl_min_lines": 5 if any(item["path"].endswith(".jsonl") for item in target_outputs) else 0,
            },
            "human_checks": ["如果涉及代码，是否真的跑过最小命令；如果涉及文档，是否能说明取舍"],
        },
        {
            "id": "T4",
            "type": "output",
            "title": f"作品集产出：{day_plan.output or day_plan.theme}",
            "duration_minutes": task_minutes[3],
            "outputs": target_outputs or [{"path": daily_notes, "required": True, "purpose": "作品集产出"}],
            "checks": {
                "required_headings": ["用途", "核心内容", "验收标准"],
                "required_nonempty_headings": ["用途", "核心内容", "验收标准"],
                "required_keywords": ["面试", "作品集"],
                "min_chars": 600,
            },
            "human_checks": ["这个产物是否能直接服务作品集或面试"],
        },
        {
            "id": "T5",
            "type": "reflection",
            "title": f"沉淀：{day_plan.reflection or '今日复盘与面试表达'}",
            "duration_minutes": task_minutes[4],
            "outputs": [
                {"path": daily_log, "required": True, "purpose": "当天执行日志"},
                {"path": interview_output, "required": True, "purpose": "当天面试表达"},
            ],
            "checks": {
                "required_headings": ["今日完成", "偏差", "明日 carryover", "面试表达"],
                "required_nonempty_headings": ["今日完成", "偏差", "明日 carryover", "面试表达"],
                "required_keywords": ["为什么这么设计", "不这么设计"],
                "min_chars": 700,
            },
            "human_checks": ["是否能回答 3 个围绕今天主题的追问"],
        },
        {
            "id": "T6",
            "type": "interview",
            "title": "大厂技术追问模拟器：候选题库 + 今日 Top 5（全部绑定 MOCA）",
            "duration_minutes": task_minutes[5],
            "outputs": [
                {
                    "path": daily_interview_questions,
                    "required": True,
                    "purpose": "今日大厂技术追问候选题库与 Top 5（强制绑定 MOCA）",
                }
            ],
            "checks": {
                "required_headings": ["大厂技术追问候选题", "今日 Top 5 追问", "MOCA绑定", "证据路径", "当前边界"],
                "required_nonempty_headings": ["大厂技术追问候选题", "今日 Top 5 追问", "MOCA绑定", "当前边界"],
                "required_keywords": ["MOCA"],
                "min_chars": 1200,
            },
            "human_checks": [
                "是否先按 A-F 生成候选题，再从中挑今日必须练熟的 Top 5",
                "Top 5 是否每题都能用 MOCA 例子回答，而不是通用八股",
                "是否至少包含 1 题 failure/risk/fallback 和 1 题 trace/eval/evidence",
            ],
        },
    ]

    carryover_tasks = load_carryover_tasks(day)
    tasks = carryover_tasks + tasks

    return {
        "schema_version": 1,
        "day": day,
        "date": run_date,
        "theme": day_plan.theme,
        "source_plan": "study_plan/30天主计划.md",
        "created_at": now_iso(),
        "schedule": {
            "work_start": work_start,
            "daily_work_hours": config["daily_work_hours"],
            "cycle_work_minutes": config["cycle_work_minutes"],
            "cycle_break_minutes": config["cycle_break_minutes"],
            "calendar_name": config["calendar_name"],
        },
        "minimum_pass_task_ids": ["T1", "T2", "T5", "T6"],
        "plan_row": {
            "theory": day_plan.theory,
            "analysis": day_plan.analysis,
            "practice": day_plan.practice,
            "output": day_plan.output,
            "reflection": day_plan.reflection,
        },
        "tasks": tasks,
        "manual_review_questions": [
            "我是否真的能脱稿讲清今天主题？",
            "今天哪个产物最虚，需要明天补？",
            "今天是否有任务虽然有文件但理解没有过关？",
            "今天的面试追问有没有先形成候选题库，再挑出必须练熟的 Top 5？",
            "今天的面试 Top 5 里，有没有哪题我只会通用答法、答不出 MOCA 怎么做？",
        ],
    }


def render_tasks_md(spec: dict[str, Any]) -> str:
    lines = [
        f"# Day {spec['day']} Tasks",
        "",
        f"- 日期：{spec['date']}",
        f"- 主题：{spec['theme']}",
        f"- 来源：`{spec['source_plan']}`",
        f"- 最低通过任务：{', '.join(spec['minimum_pass_task_ids'])}",
        "",
    ]
    if any(task.get("type") == "carryover" for task in spec["tasks"]):
        lines.extend(
            [
                "> 昨日遗留任务已置顶为 `C*`。先补完 carryover，再开始今日新增任务。",
                "",
            ]
        )
    lines.extend(
        [
            "## 今日任务表",
            "",
            "| ID | 类型 | 任务 | 预计 | 产物 | 验收重点 |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for task in spec["tasks"]:
        outputs = "<br>".join(f"`{path}`" for path in task_output_paths(task))
        checks = task.get("checks", {})
        check_text = "；".join(
            item
            for item in [
                f"标题：{', '.join(checks.get('required_headings', []))}" if checks.get("required_headings") else "",
                f"关键词：{', '.join(checks.get('required_keywords', []))}" if checks.get("required_keywords") else "",
                f"至少 {checks.get('min_chars')} 字符" if checks.get("min_chars") else "",
                f"JSONL 至少 {checks.get('jsonl_min_lines')} 条" if checks.get("jsonl_min_lines") else "",
            ]
            if item
        )
        lines.append(
            f"| {task['id']} | {task['type']} | {task['title']} | {task['duration_minutes']}m | {outputs} | {check_text} |"
        )

    lines.extend(["", "## 分任务执行要求", ""])
    for task in spec["tasks"]:
        lines.extend(
            [
                f"### {task['id']} · {task['title']}",
                f"- 类型：{task['type']}",
                f"- 预计：{task['duration_minutes']} 分钟",
                "- 产物：",
            ]
        )
        for output in task.get("outputs", []):
            lines.append(f"  - `{output['path']}` —— {output.get('purpose', '')}")
        checks = task.get("checks", {})
        lines.extend(["- evidence_rule："])
        for heading in checks.get("required_headings", []):
            lines.append(f"  - 必须包含标题：{heading}")
        for keyword in checks.get("required_keywords", []):
            lines.append(f"  - 必须出现关键词：{keyword}")
        if checks.get("min_chars"):
            lines.append(f"  - 正文至少 {checks['min_chars']} 个非空白字符")
        for heading in checks.get("required_nonempty_headings", []):
            lines.append(f"  - `{heading}` 标题下必须有非占位内容")
        if checks.get("jsonl_min_lines"):
            lines.append(f"  - JSONL 至少 {checks['jsonl_min_lines']} 条有效样例")
        lines.append("- 人工确认项：")
        for item in task.get("human_checks", []):
            lines.append(f"  - {item}")
        lines.append("")

    lines.extend(
        [
            "## 今日执行日志模板",
            "",
            "```md",
            "## 今日完成",
            "- ",
            "",
            "## 偏差",
            "- ",
            "",
            "## 明日 carryover",
            "- ",
            "",
            "## 面试表达",
            "- 业务语言：",
            "- 技术实现：",
            "- 为什么这么设计：",
            "- 不这么设计的问题：",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_log_template(spec: dict[str, Any]) -> str:
    lines = [
        f"# Day {spec['day']} 执行日志",
        "",
        f"- 日期：{spec['date']}",
        f"- 主题：{spec['theme']}",
        "",
        "## 任务状态",
        "",
        "| ID | 状态 | 实际用时 | 产物 | 偏差/卡点 |",
        "|---|---|---:|---|---|",
    ]
    for task in spec["tasks"]:
        outputs = "<br>".join(f"`{path}`" for path in task_output_paths(task))
        lines.append(f"| {task['id']} | TODO |  | {outputs} |  |")
    lines.extend(
        [
            "",
            "## 今日完成",
            "- ",
            "",
            "## 偏差",
            "- ",
            "",
            "## 明日 carryover",
            "- ",
            "",
            "## 面试表达",
            "- 业务语言：",
            "- 技术实现：",
            "- 为什么这么设计：",
            "- 不这么设计的问题：",
            "",
            "## 人工确认",
            "- 我是否能脱稿讲清今天主题：",
            "- 我是否能回答 3 个追问：",
            "- 今天最虚的产物：",
            "",
        ]
    )
    return "\n".join(lines)


def render_start_prompt(spec: dict[str, Any]) -> str:
    day = spec["day"]
    tasks_json = f"study_plan/portfolio/daily/day{day:02d}_tasks.json"
    tasks_md = f"study_plan/portfolio/daily/day{day:02d}_tasks.md"
    baseline = f"study_plan/portfolio/daily/day{day:02d}_baseline.json"
    return f"""你现在是我的「AI Agent 产品经理训练助教 + 技术实现助教 + 作品集产出教练」。

请基于当前 MOCA 仓库和 30 天主计划，细化 Day {day} 的今日任务。

已生成的机器任务规格：
- `{tasks_json}`
- `{tasks_md}`
- `{baseline}`

今日主题：{spec['theme']}
今日计划来源：`study_plan/30天主计划.md`
面试追问规则：`study_plan/portfolio/daily/interview_question_rules.md`

请只修改 `study_plan/portfolio/` 下的学习产物，不要修改 `src/`、`tests/` 或 `.planning/`。

你的任务：
1. 读取 `{tasks_json}` 和 `{tasks_md}`。
2. 读取必要上下文：`study_plan/30天主计划.md`、`study_plan/MOCA内化训练法.md`、`study_plan/交付物清单.md`、`study_plan/portfolio/daily/interview_question_rules.md`。
3. 把 `{tasks_md}` 细化到可直接执行：资料、文件路径、rg 命令、模板、验收标准、卡住降级方案。
4. 如需更新 `{tasks_json}`，必须保持合法 JSON，并保留 schema_version/day/tasks/evidence_rule 结构。
5. 生成或更新今日需要的空白产物模板文件。
6. 生成或更新今日大厂技术追问候选题库，并从中挑出今日 Top 5；每题都必须绑定 MOCA，包含 `MOCA绑定`、`证据路径`、`当前边界` 和状态。

硬性要求：
- 所有命令都说明在 `/Users/ming/projects/MOCA` 运行。
- shell 搜索 pattern 使用单引号。
- 默认保留 trace / eval / risk。
- 没有仓库证据的内容不要写成已完成。
- 不要安排高并发、K8s、微调、多 Agent 编队等当前阶段不必要内容。
- 面试候选题优先覆盖 A-F：今日主题直连、MOCA 项目深挖、底层工程追问、架构升级、模型与框架、高级识别题。
- 面试追问不能写成通用八股；每道题都必须回答“MOCA 里怎么做 / 没做但为什么没做 / 如果升级怎么做”。
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
    parser = argparse.ArgumentParser(description="Create the daily MOCA study task scaffold.")
    parser.add_argument("--day", default="auto", help="Day number 1..30, or auto from automation_config.json")
    parser.add_argument("--date", default=None, help="Run date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--start", default=None, help="Work start time HH:MM. Defaults to config.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing tasks/log/prompt files.")
    parser.add_argument("--force-baseline", action="store_true", help="Overwrite existing baseline file.")
    parser.add_argument("--codex", action="store_true", help="Run codex exec with the generated start prompt.")
    args = parser.parse_args()

    run_date = date_from_arg(args.date)
    config = load_config(run_date, create_if_missing=True)
    day = resolve_day(args.day, config, run_date)
    work_start = args.start or str(config["default_work_start"])

    ensure_portfolio_dirs()
    days = parse_main_plan()
    if day not in days:
        raise SystemExit(f"Day {day} not found in study_plan/30天主计划.md")

    spec = build_tasks(days[day], config, run_date.isoformat(), work_start)
    tasks_json = daily_file(day, "tasks.json")
    tasks_md = daily_file(day, "tasks.md")
    log_md = daily_file(day, "log.md")
    baseline_json = daily_file(day, "baseline.json")
    start_prompt = daily_file(day, "start_prompt.md")
    codex_output = daily_file(day, "start_codex_output.md")

    written = []
    if write_json(tasks_json, spec, force=args.force):
        written.append(rel(tasks_json))
    if write_text(tasks_md, render_tasks_md(spec), force=args.force):
        written.append(rel(tasks_md))
    if write_text(log_md, render_log_template(spec), force=args.force):
        written.append(rel(log_md))
    baseline = {
        "schema_version": 1,
        "day": day,
        "date": run_date.isoformat(),
        "created_at": now_iso(),
        "git": git_snapshot(),
        "tasks_file": rel(tasks_json),
        "planned_outputs": sorted({path for task in spec["tasks"] for path in task_output_paths(task)}),
    }
    if write_json(baseline_json, baseline, force=args.force_baseline or args.force):
        written.append(rel(baseline_json))
    if write_text(start_prompt, render_start_prompt(spec), force=args.force):
        written.append(rel(start_prompt))

    print(f"Day {day} scaffold ready for {run_date.isoformat()}: {spec['theme']}")
    if written:
        print("Written:")
        for path in written:
            print(f"- {path}")
    else:
        print("No files overwritten. Use --force to regenerate existing files.")
    print(f"Config: {rel(AUTOMATION_CONFIG)}")

    if args.codex:
        maybe_run_codex(start_prompt, codex_output, str(config["codex_path"]))
        print(f"Codex output: {rel(codex_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
