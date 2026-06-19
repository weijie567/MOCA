from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_PLAN_DIR = REPO_ROOT / "study_plan"
PORTFOLIO_DIR = STUDY_PLAN_DIR / "portfolio"
DAILY_DIR = PORTFOLIO_DIR / "daily"
WEEKLY_DIR = PORTFOLIO_DIR / "weekly_reviews"
AUTOMATION_CONFIG = DAILY_DIR / "automation_config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "program_start_date": None,
    "timezone": "Asia/Shanghai",
    "default_work_start": "09:00",
    "daily_work_hours": 10,
    "cycle_work_minutes": 30,
    "cycle_break_minutes": 8,
    "calendar_name": "MOCA 30 Days",
    "codex_path": "/opt/homebrew/bin/codex",
}


DAY_OUTPUTS: dict[int, list[dict[str, str]]] = {
    1: [
        {"path": "study_plan/portfolio/moca_internalize/00_模块全景图.md", "purpose": "MOCA 架构开场讲解"},
        {"path": "study_plan/portfolio/interview/day01_MOCA一分钟介绍.md", "purpose": "1 分钟项目介绍稿"},
        {"path": "study_plan/portfolio/daily/day01_phase15_1_codex_prompt.md", "purpose": "Phase 15.1 GSD 启动材料"},
    ],
    2: [
        {"path": "study_plan/portfolio/moca_internalize/01_agent编排复盘.md", "purpose": "Agent 编排内化"},
        {"path": "study_plan/portfolio/interview/day02_agent怎么决策调工具.md", "purpose": "面试表达稿"},
    ],
    3: [
        {"path": "study_plan/portfolio/moca_internalize/02_审批状态机复盘.md", "purpose": "审批状态机深挖材料"},
        {"path": "study_plan/portfolio/interview/day03_审批状态机面试稿.md", "purpose": "审批状态机面试表达"},
    ],
    4: [
        {"path": "study_plan/portfolio/moca_internalize/03_RAG与证据契约复盘.md", "purpose": "RAG 与证据契约复盘"},
        {"path": "study_plan/portfolio/interview/day04_建议为何必须带证据.md", "purpose": "证据契约面试表达"},
    ],
    5: [
        {"path": "study_plan/portfolio/moca_internalize/04_记忆与可观测复盘.md", "purpose": "记忆与可观测复盘"},
        {"path": "study_plan/portfolio/interview/day05_出问题怎么定位哪层.md", "purpose": "可观测性面试表达"},
    ],
    6: [{"path": "study_plan/portfolio/product/场景树.md", "purpose": "MOCA 产品场景树"}],
    7: [
        {"path": "study_plan/portfolio/weekly_reviews/week1.md", "purpose": "第一周复盘"},
        {"path": "study_plan/portfolio/moca_internalize/05_整体架构图.md", "purpose": "MOCA 主链路验收图"},
    ],
    8: [{"path": "study_plan/portfolio/product/MOCA_PRD.md", "purpose": "MOCA PRD 上半部分"}],
    9: [{"path": "study_plan/portfolio/product/MOCA_PRD.md", "purpose": "MOCA PRD 完整 v1"}],
    10: [{"path": "study_plan/portfolio/product/竞品拆解_x3.md", "purpose": "三个竞品拆解"}],
    11: [{"path": "study_plan/portfolio/product/指标体系.md", "purpose": "MOCA 指标体系"}],
    12: [{"path": "study_plan/portfolio/demos/function_calling/README.md", "purpose": "Function calling demo 说明"}],
    13: [{"path": "study_plan/portfolio/demos/fastapi_agent/README.md", "purpose": "FastAPI Agent demo 说明"}],
    14: [{"path": "study_plan/portfolio/weekly_reviews/week2.md", "purpose": "第二周复盘"}],
    15: [{"path": "study_plan/portfolio/demos/langgraph_hello/README.md", "purpose": "LangGraph 最小例子"}],
    16: [{"path": "study_plan/portfolio/demos/langgraph_moca_lite/README.md", "purpose": "MOCA Lite LangGraph 骨架"}],
    17: [
        {"path": "study_plan/portfolio/demos/langgraph_moca_lite/README.md", "purpose": "MOCA Lite LangGraph 可运行版"}
    ],
    18: [{"path": "study_plan/portfolio/demos/rag_v2/README.md", "purpose": "RAG v2 简化版"}],
    19: [
        {"path": "study_plan/portfolio/demos/fastapi_agent/Dockerfile", "purpose": "FastAPI Agent 容器化"},
        {"path": "study_plan/portfolio/demos/fastapi_agent/deploy.md", "purpose": "部署说明"},
    ],
    20: [
        {"path": "study_plan/portfolio/evals/golden_v1.jsonl", "purpose": "Golden eval set"},
        {"path": "study_plan/portfolio/evals/redteam_v1.jsonl", "purpose": "Red-team eval set"},
        {"path": "study_plan/portfolio/evals/exception_v1.jsonl", "purpose": "Exception eval set"},
    ],
    21: [{"path": "study_plan/portfolio/weekly_reviews/week3.md", "purpose": "第三周复盘"}],
    22: [{"path": "study_plan/portfolio/README.md", "purpose": "作品集总索引"}],
    23: [{"path": "study_plan/portfolio/MOCA架构图.md", "purpose": "正式版 MOCA 架构图"}],
    24: [{"path": "study_plan/portfolio/interview/demo_脚本.md", "purpose": "Demo 视频脚本"}],
    25: [{"path": "study_plan/portfolio/interview/STAR故事库.md", "purpose": "STAR 故事库"}],
    26: [{"path": "study_plan/portfolio/interview/技术高频题.md", "purpose": "技术面高频题"}],
    27: [{"path": "study_plan/portfolio/interview/简历bullet.md", "purpose": "简历 bullet"}],
    28: [
        {"path": "study_plan/portfolio/weekly_reviews/week4.md", "purpose": "第四周复盘"},
        {"path": "study_plan/portfolio/weekly_reviews/30天总复盘.md", "purpose": "30 天总复盘"},
    ],
}


@dataclass(frozen=True)
class DayPlan:
    day: int
    theme: str
    theory: str
    analysis: str
    practice: str
    output: str
    reflection: str


def ensure_portfolio_dirs() -> None:
    for path in [
        DAILY_DIR,
        WEEKLY_DIR,
        PORTFOLIO_DIR / "product",
        PORTFOLIO_DIR / "moca_internalize",
        PORTFOLIO_DIR / "demos",
        PORTFOLIO_DIR / "evals",
        PORTFOLIO_DIR / "interview",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str, *, force: bool = False) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def write_json(path: Path, data: dict[str, Any], *, force: bool = True) -> bool:
    return write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", force=force)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def clean_md_cell(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value)
    value = value.replace("**", "").replace("`", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_main_plan() -> dict[int, DayPlan]:
    plan_path = STUDY_PLAN_DIR / "30天主计划.md"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing main plan: {plan_path}")

    days: dict[int, DayPlan] = {}
    for raw_line in read_text(plan_path).splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "D" not in line:
            continue
        cols = [clean_md_cell(col) for col in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        match = re.search(r"\bD(\d+)\b", cols[0])
        if not match:
            continue
        day = int(match.group(1))
        # Tables in the plan use: Day, theme, theory, analysis, practice, output, reflection.
        padded = cols + [""] * 7
        days[day] = DayPlan(
            day=day,
            theme=padded[1],
            theory=padded[2],
            analysis=padded[3],
            practice=padded[4],
            output=padded[5],
            reflection=padded[6],
        )
    return days


def load_config(today: date | None = None, *, create_if_missing: bool = False) -> dict[str, Any]:
    ensure_portfolio_dirs()
    today = today or date.today()
    if AUTOMATION_CONFIG.exists():
        config = DEFAULT_CONFIG | load_json(AUTOMATION_CONFIG)
    else:
        config = DEFAULT_CONFIG.copy()
        config["program_start_date"] = today.isoformat()
        if create_if_missing:
            write_json(AUTOMATION_CONFIG, config, force=False)
    if not config.get("program_start_date"):
        config["program_start_date"] = today.isoformat()
    return config


def resolve_day(day_arg: str, config: dict[str, Any], today: date | None = None) -> int:
    if day_arg != "auto":
        day = int(day_arg)
        if day < 1 or day > 30:
            raise argparse.ArgumentTypeError("day must be 1..30 or auto")
        return day
    today = today or date.today()
    start = date.fromisoformat(str(config["program_start_date"]))
    day = (today - start).days + 1
    if day < 1:
        raise ValueError(f"Today {today.isoformat()} is before program_start_date {start.isoformat()}")
    return min(day, 30)


def daily_file(day: int, suffix: str) -> Path:
    return DAILY_DIR / f"day{day:02d}_{suffix}"


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def repo_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return (result.stdout + result.stderr).strip()


def git_snapshot() -> dict[str, str]:
    return {
        "head": run_git(["rev-parse", "HEAD"]),
        "status_short": run_git(["status", "--short"]),
        "diff_stat": run_git(["diff", "--stat"]),
    }


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def parse_hhmm(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if not match:
        raise argparse.ArgumentTypeError("time must be HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise argparse.ArgumentTypeError("time must be HH:MM")
    return hour, minute


def date_from_arg(value: str | None) -> date:
    return date.fromisoformat(value) if value else date.today()


def task_output_paths(task: dict[str, Any]) -> list[str]:
    return [item["path"] for item in task.get("outputs", []) if item.get("path")]


def week_range(week: int) -> tuple[int, int]:
    if week < 1:
        raise argparse.ArgumentTypeError("week must be >= 1")
    start = (week - 1) * 7 + 1
    end = min(start + 6, 30)
    return start, end


def add_minutes(base: datetime, minutes: int) -> datetime:
    return base + timedelta(minutes=minutes)
