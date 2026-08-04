from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.diagnose_latency import build_report, detect_bottleneck
from src.agent.trace import write_agent_run, write_agent_steps
from src.db.models import AgentStep


ALLOWED_METRIC_KEYS = {"model", "provider", "context_chars"}


async def _create_run(session: AsyncSession, run_id: str) -> None:
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id="latency-test-thread",
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        input_query="测试延迟诊断",
        final_status="completed",
        final_response="ok",
        started_at=now,
        completed_at=now,
        total_latency_ms=100,
    )


@pytest.mark.asyncio
async def test_write_agent_steps_persists_latency_metrics(session: AsyncSession):
    run_id = str(uuid4())
    await _create_run(session, run_id)

    await write_agent_steps(
        session,
        run_id=run_id,
        trace_steps=[
            {
                "node": "contextual_intent_resolve",
                "status": "completed",
                "latency_ms": 125,
                "provider_latency_ms": 118,
                "retry_count": 1,
                "metrics_json": {"model": "qwen-plus", "provider": "dashscope", "context_chars": 2048},
            }
        ],
    )

    result = await session.execute(select(AgentStep).where(AgentStep.run_id == run_id))
    row = result.scalar_one()
    assert row.provider_latency_ms == 118
    assert row.retry_count == 1
    assert row.metrics_json == {"model": "qwen-plus", "provider": "dashscope", "context_chars": 2048}


@pytest.mark.asyncio
async def test_write_agent_steps_computes_latency_from_timestamps(session: AsyncSession):
    run_id = str(uuid4())
    await _create_run(session, run_id)
    started_at = datetime(2026, 5, 16, 8, 0, 0, tzinfo=UTC)
    completed_at = started_at + timedelta(milliseconds=275)

    await write_agent_steps(
        session,
        run_id=run_id,
        trace_steps=[
            {
                "node": "slot_resolution_gate",
                "status": "completed",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "provider_latency_ms": 260,
                "retry_count": 0,
                "metrics_json": {"model": "qwen-plus", "provider": "dashscope", "context_chars": 3000},
            }
        ],
    )

    result = await session.execute(select(AgentStep).where(AgentStep.run_id == run_id))
    row = result.scalar_one()
    assert row.latency_ms == 275


@pytest.mark.asyncio
async def test_metrics_json_uses_allowlisted_keys(session: AsyncSession):
    run_id = str(uuid4())
    await _create_run(session, run_id)

    await write_agent_steps(
        session,
        run_id=run_id,
        trace_steps=[
            {
                "node": "recommendation_generation",
                "status": "completed",
                "provider_latency_ms": 900,
                "retry_count": 0,
                "metrics_json": {"model": "qwen-plus", "provider": "dashscope", "context_chars": 8800},
            }
        ],
    )

    result = await session.execute(select(AgentStep).where(AgentStep.run_id == run_id))
    row = result.scalar_one()
    assert set(row.metrics_json) <= ALLOWED_METRIC_KEYS


def test_diagnose_latency_mock_outputs_valid_json():
    result = subprocess.run(
        [sys.executable, "scripts/diagnose_latency.py", "--mock"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert {"run_id", "total_latency_ms", "nodes", "bottleneck", "suspected_causes"} <= set(report)
    assert report["bottleneck"]["node"] == "recommendation_generation"


def test_detect_bottleneck_selects_highest_latency_node():
    nodes = [
        {"node": "contextual_intent_resolve", "latency_ms": 120, "provider_latency_ms": 100, "retry_count": 0},
        {"node": "recommendation_generation", "latency_ms": 800, "provider_latency_ms": 720, "retry_count": 0},
        {"node": "final_response", "latency_ms": 50, "provider_latency_ms": None, "retry_count": 0},
    ]

    bottleneck = detect_bottleneck(nodes)
    report = build_report("run-1", nodes)

    assert bottleneck == {"node": "recommendation_generation", "latency_ms": 800, "pct_of_total": 82.5}
    assert report["bottleneck"] == bottleneck
