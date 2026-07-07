#!/usr/bin/env python
"""Diagnose per-node latency for a persisted agent run."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select

from src.db.models import AgentStep
from src.db.session import SessionLocal


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def step_to_node(step: AgentStep) -> dict[str, Any]:
    metrics = step.metrics_json or {}
    return {
        "node": step.node_name,
        "step_index": step.step_index,
        "latency_ms": _safe_int(step.latency_ms) or 0,
        "provider_latency_ms": _safe_int(step.provider_latency_ms),
        "retry_count": _safe_int(step.retry_count) or 0,
        "prompt_tokens": _safe_int(step.prompt_tokens),
        "completion_tokens": _safe_int(step.completion_tokens),
        "context_chars": _safe_int(metrics.get("context_chars")),
    }


def detect_bottleneck(nodes: list[dict[str, Any]], total_latency_ms: int | None = None) -> dict[str, Any] | None:
    if not nodes:
        return None
    total = (
        total_latency_ms if total_latency_ms is not None else sum(int(node.get("latency_ms") or 0) for node in nodes)
    )
    bottleneck = max(nodes, key=lambda node: int(node.get("latency_ms") or 0))
    latency = int(bottleneck.get("latency_ms") or 0)
    pct = round((latency / total * 100), 1) if total else 0.0
    return {
        "node": bottleneck["node"],
        "latency_ms": latency,
        "pct_of_total": pct,
    }


def suspected_causes(nodes: list[dict[str, Any]], bottleneck: dict[str, Any] | None) -> list[str]:
    causes: list[str] = []
    if bottleneck:
        node = next((item for item in nodes if item["node"] == bottleneck["node"]), None)
        provider_latency = int((node or {}).get("provider_latency_ms") or 0)
        latency = int((node or {}).get("latency_ms") or 0)
        if provider_latency and latency and provider_latency / latency >= 0.8:
            causes.append(f"high provider latency on {bottleneck['node']}")

    for node in nodes:
        retry_count = int(node.get("retry_count") or 0)
        if retry_count > 0:
            causes.append(f"retry detected on {node['node']}")

    if not causes and bottleneck:
        causes.append(f"highest end-to-end node latency on {bottleneck['node']}")
    return causes


def build_report(run_id: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    total_latency_ms = sum(int(node.get("latency_ms") or 0) for node in nodes)
    bottleneck = detect_bottleneck(nodes, total_latency_ms)
    return {
        "run_id": run_id,
        "total_latency_ms": total_latency_ms,
        "node_count": len(nodes),
        "nodes": nodes,
        "bottleneck": bottleneck,
        "suspected_causes": suspected_causes(nodes, bottleneck),
    }


def mock_report(run_id: str = "00000000-0000-0000-0000-000000000000") -> dict[str, Any]:
    nodes = [
        {
            "node": "contextual_intent_resolve",
            "step_index": 1,
            "latency_ms": 1200,
            "provider_latency_ms": 1100,
            "retry_count": 0,
            "prompt_tokens": 450,
            "completion_tokens": 50,
            "context_chars": 2100,
        },
        {
            "node": "recommendation_generation",
            "step_index": 4,
            "latency_ms": 3500,
            "provider_latency_ms": 3300,
            "retry_count": 0,
            "prompt_tokens": 1400,
            "completion_tokens": 260,
            "context_chars": 7800,
        },
        {
            "node": "risk_gate",
            "step_index": 5,
            "latency_ms": 2100,
            "provider_latency_ms": 1900,
            "retry_count": 1,
            "prompt_tokens": 800,
            "completion_tokens": 120,
            "context_chars": 4300,
        },
    ]
    return build_report(run_id, nodes)


async def load_report(run_id: str) -> dict[str, Any]:
    parsed_run_id = uuid.UUID(run_id)
    async with SessionLocal() as session:
        result = await session.execute(
            select(AgentStep).where(AgentStep.run_id == parsed_run_id).order_by(AgentStep.step_index)
        )
        nodes = [step_to_node(step) for step in result.scalars()]
    return build_report(run_id, nodes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose agent node latency for a persisted run.")
    parser.add_argument("--run-id", help="Agent run UUID to inspect.")
    parser.add_argument("--mock", action="store_true", help="Emit a synthetic report without database access.")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    if args.mock:
        report = mock_report(args.run_id or "00000000-0000-0000-0000-000000000000")
    else:
        if not args.run_id:
            raise SystemExit("--run-id is required unless --mock is used")
        report = await load_report(args.run_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
