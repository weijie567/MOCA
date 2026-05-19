"""Unified evaluation runner.

Usage:
    uv run python scripts/eval_all.py
    uv run python scripts/eval_all.py --output evaluation/reports/latest.json
    uv run python scripts/eval_all.py --agent-mode live

Runs RAG and Agent evaluations, merges results into unified report.
Exits 0 if all thresholds pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.eval_agent import THRESHOLDS as AGENT_THRESHOLDS
from scripts.eval_agent import run_agent_eval
from scripts.eval_rag import DEFAULT_THRESHOLD as RAG_THRESHOLD
from scripts.eval_rag import run_rag_eval


DEFAULT_OUTPUT = "evaluation/reports/latest.json"
DEFAULT_MARKDOWN = "evaluation/reports/latest.md"
BASELINE_PATH = "evaluation/reports/baseline.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified MOCA evaluation runner")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write unified JSON report")
    parser.add_argument("--agent-mode", choices=("ci", "live"), default="ci", help="Agent evaluation mode")
    parser.add_argument("--timestamp", action="store_true", help="Also write timestamped JSON and Markdown reports")
    parser.add_argument("--save-baseline", action="store_true", help="Copy latest JSON report to baseline.json")
    return parser


async def run_all_evals(agent_mode: str = "ci") -> dict[str, Any]:
    rag_eval_summary = await run_rag_eval()
    agent_eval_summary = await run_agent_eval(mode=agent_mode)
    return _build_unified_report(rag_eval_summary, agent_eval_summary)


def _build_unified_report(rag_eval_summary: dict[str, Any], agent_eval_summary: dict[str, Any]) -> dict[str, Any]:
    rag_metrics = rag_eval_summary["metrics"]
    agent_metrics = agent_eval_summary["metrics"]
    overall_status = "pass" if rag_eval_summary["status"] == "pass" and agent_eval_summary["status"] == "pass" else "fail"
    failed_cases = _tag_failed_cases("rag", rag_eval_summary) + _tag_failed_cases("agent", agent_eval_summary)
    warning_cases = _warning_cases(rag_eval_summary, agent_eval_summary)
    total_cases = int(rag_metrics.get("total_cases", 0)) + int(agent_metrics.get("total_cases", 0))

    return {
        "overall_status": overall_status,
        "generated_at": datetime.now(UTC).isoformat(),
        "rag_eval_summary": rag_eval_summary,
        "agent_eval_summary": agent_eval_summary,
        "thresholds": {
            "rag": {"hit_at_5": RAG_THRESHOLD, "fallback_accuracy": RAG_THRESHOLD},
            "agent": AGENT_THRESHOLDS,
        },
        "failed_cases": failed_cases,
        "warning_cases": warning_cases,
        "metrics": {
            "rag_hit_at_5": rag_metrics.get("hit_at_5", 0.0),
            "agent_intent_accuracy": agent_metrics.get("intent_accuracy", 0.0),
            "agent_tool_accuracy": agent_metrics.get("tool_selection_accuracy", 0.0),
            "agent_citation_rate": agent_metrics.get("citation_rate", 0.0),
            "agent_safety_rate": agent_metrics.get("safety_critical_pass_rate", 0.0),
            "average_latency_ms": agent_metrics.get("average_latency_ms"),
            "total_cases": total_cases,
        },
        "baseline_comparison": None,
    }


def _tag_failed_cases(eval_type: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for failed in report.get("failed_cases", []):
        tagged.append({"eval_type": eval_type, **failed})
    return tagged


def _warning_cases(rag_report: dict[str, Any], agent_report: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    rag_metrics = rag_report["metrics"]
    if rag_report["status"] == "pass" and rag_metrics["hit_at_5"] - RAG_THRESHOLD < 0.05:
        warnings.append({"eval_type": "rag", "metric": "hit_at_5", "value": rag_metrics["hit_at_5"]})
    for metric, threshold in AGENT_THRESHOLDS.items():
        value = agent_report["metrics"].get(metric, 0.0)
        if agent_report["status"] == "pass" and value - threshold < 0.05:
            warnings.append({"eval_type": "agent", "metric": metric, "value": value})
    if not Path(BASELINE_PATH).exists():
        warnings.append({"eval_type": "baseline", "metric": "baseline_comparison", "message": "baseline.json not found"})
    return warnings


def _compare_baseline(path: Path, latest_metrics: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    baseline = json.loads(path.read_text(encoding="utf-8"))
    baseline_metrics = baseline.get("metrics", {})
    regressions = []
    improvements = []
    for metric, latest_value in latest_metrics.items():
        baseline_value = baseline_metrics.get(metric)
        if not isinstance(baseline_value, int | float) or not isinstance(latest_value, int | float):
            continue
        if latest_value < baseline_value:
            regressions.append({"metric": metric, "baseline": baseline_value, "latest": latest_value})
        elif latest_value > baseline_value:
            improvements.append({"metric": metric, "baseline": baseline_value, "latest": latest_value})
    return {"baseline_file": str(path), "regressions": regressions, "improvements": improvements}


def _attach_baseline_comparison(report: dict[str, Any]) -> None:
    report["baseline_comparison"] = _compare_baseline(Path(BASELINE_PATH), report["metrics"])


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    rag = report["rag_eval_summary"]
    agent = report["agent_eval_summary"]
    lines = [
        f"# MOCA Evaluation Report - {report['overall_status'].upper()}",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Threshold |",
        "| --- | ---: | ---: |",
        f"| RAG Hit@5 | {_pct(metrics['rag_hit_at_5'])} | {_pct(report['thresholds']['rag']['hit_at_5'])} |",
        (
            "| Agent intent accuracy | "
            f"{_pct(metrics['agent_intent_accuracy'])} | {_pct(report['thresholds']['agent']['intent_accuracy'])} |"
        ),
        (
            "| Agent tool accuracy | "
            f"{_pct(metrics['agent_tool_accuracy'])} | "
            f"{_pct(report['thresholds']['agent']['tool_selection_accuracy'])} |"
        ),
        (
            "| Agent citation rate | "
            f"{_pct(metrics['agent_citation_rate'])} | {_pct(report['thresholds']['agent']['citation_rate'])} |"
        ),
        (
            "| Agent safety rate | "
            f"{_pct(metrics['agent_safety_rate'])} | "
            f"{_pct(report['thresholds']['agent']['safety_critical_pass_rate'])} |"
        ),
        f"| Total cases | {metrics['total_cases']} | - |",
        f"| Average latency | {_latency(metrics.get('average_latency_ms'))} | - |",
        "",
        "## RAG Per Category",
        "",
        "| Category | Total | Hit | Rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, stats in rag.get("per_category", {}).items():
        lines.append(f"| {category} | {stats['total']} | {stats['hit']} | {_pct(stats['rate'])} |")

    lines.extend(
        [
            "",
            "## Agent Per Category",
            "",
            "| Category | Total | Passed | Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for category, stats in agent.get("per_category", {}).items():
        lines.append(f"| {category} | {stats['total']} | {stats['passed']} | {_pct(stats['rate'])} |")

    lines.extend(["", "## Failed Cases", ""])
    if report["failed_cases"]:
        for failed in report["failed_cases"]:
            failures = ", ".join(str(item) for item in failed.get("failures", [failed.get("reason", "failed")]))
            lines.append(f"- `{failed.get('eval_type')}` `{failed.get('id', 'unknown')}`: {failures}")
    else:
        lines.append("None.")

    lines.extend(["", "## Threshold Comparison", ""])
    for warning in report.get("warning_cases", []):
        lines.append(f"- Warning: `{warning['eval_type']}` `{warning.get('metric')}` is close to threshold or missing baseline.")
    if not report.get("warning_cases"):
        lines.append("No threshold warnings.")

    lines.extend(["", "## Baseline Comparison", ""])
    baseline = report.get("baseline_comparison")
    if baseline is None:
        lines.append("No baseline file found at `evaluation/reports/baseline.json`; comparison skipped.")
    else:
        lines.append(f"Baseline file: `{baseline['baseline_file']}`")
        lines.append(f"Regressions: {len(baseline['regressions'])}")
        lines.append(f"Improvements: {len(baseline['improvements'])}")

    return "\n".join(lines) + "\n"


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1%}"


def _latency(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f} ms"


def _timestamp_paths(output_path: Path) -> tuple[Path, Path]:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    return output_path.with_name(f"{stamp}.json"), output_path.with_name(f"{stamp}.md")


async def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    report = await run_all_evals(agent_mode=args.agent_mode)
    _attach_baseline_comparison(report)

    output_path = Path(args.output)
    markdown_path = output_path.with_suffix(".md") if output_path != Path(DEFAULT_OUTPUT) else Path(DEFAULT_MARKDOWN)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(report)
    markdown_path.write_text(markdown, encoding="utf-8")

    if args.timestamp:
        timestamp_json, timestamp_md = _timestamp_paths(output_path)
        timestamp_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        timestamp_md.write_text(markdown, encoding="utf-8")

    if args.save_baseline:
        shutil.copyfile(output_path, BASELINE_PATH)

    print(f"Unified evaluation report written to {output_path} and {markdown_path}")
    sys.exit(0 if report["overall_status"] == "pass" else 1)


if __name__ == "__main__":
    asyncio.run(main())
