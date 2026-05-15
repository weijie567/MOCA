#!/usr/bin/env python
"""Live smoke test for the MOCA refund agent.

Requires: DASHSCOPE_API_KEY set in environment, running Postgres DB.
NOT for CI - run manually to verify real LLM chain.
Usage: uv run python scripts/smoke_agent_live.py

Per D-11e.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime


MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")


def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")


def _print_case_diagnostics(result: dict) -> None:
    diagnostic = {
        "intent": result.get("current_intent"),
        "recommendation_draft": result.get("recommendation_draft"),
        "risk_assessment": result.get("risk_assessment"),
        "node_errors": result.get("node_errors"),
        "retrieved_evidence_status": (result.get("retrieved_evidence") or {}).get("data", {}).get("retrieval_status"),
        "retrieved_evidence_count": len((result.get("retrieved_evidence") or {}).get("data", {}).get("evidence") or []),
    }
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2, default=str), flush=True)


async def smoke_agent_live():
    """Run 3 test queries against the live agent graph."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.agent.graph import build_graph
    from src.agent.trace import build_trace_summary
    from src.config import settings

    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("ERROR: DASHSCOPE_API_KEY not set")
        sys.exit(1)

    tenant_id = str(deterministic_id("tenant", "demo"))
    user_id = str(deterministic_id("user", "demo_support_1"))
    run_suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    case_timeout_seconds = int(os.environ.get("LIVE_SMOKE_CASE_TIMEOUT_SECONDS", "240"))
    test_cases = [
        {
            "query": "退款超时规则是什么？",
            "thread_id": "smoke-test-001",
            "expected_intent": "policy_qa",
            "expected_final_status": "completed",
            "min_evidence_count": 1,
        },
        {
            "query": "订单ORD-2024-001为什么还没退款？",
            "thread_id": "smoke-test-002",
            "expected_intent": "refund_troubleshooting",
            "expected_final_status": "completed",
            "min_evidence_count": 1,
        },
        {
            "query": "这个问题没有任何相关规则",
            "thread_id": "smoke-test-003",
            "expected_final_status": "insufficient_evidence",
        },
    ]

    failures = 0
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_database_url) as checkpointer:
            await checkpointer.setup()
            graph = build_graph(checkpointer)

            for i, case in enumerate(test_cases, 1):
                print(f"\n--- Test {i}: {case['query'][:40]}...", flush=True)
                async with session_factory() as session:
                    scoped_thread_id = f"{tenant_id}:{user_id}:{case['thread_id']}:{run_suffix}"
                    config = {"configurable": {"thread_id": scoped_thread_id, "session": session}}
                    input_state = {
                        "user_query": case["query"],
                        "thread_id": case["thread_id"],
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "role": "support_agent",
                    }
                    try:
                        result = await asyncio.wait_for(
                            graph.ainvoke(input_state, config),
                            timeout=case_timeout_seconds,
                        )
                        summary = build_trace_summary(result["current_run_id"], result, 0)
                        if case.get("expected_intent") and result.get("current_intent") != case["expected_intent"]:
                            _print_case_diagnostics(result)
                            raise AssertionError(
                                f"intent mismatch: expected {case['expected_intent']}, got {result.get('current_intent')}"
                            )
                        if (
                            case.get("expected_final_status")
                            and summary["final_status"] != case["expected_final_status"]
                        ):
                            _print_case_diagnostics(result)
                            raise AssertionError(
                                "final status mismatch: "
                                f"expected {case['expected_final_status']}, got {summary['final_status']}"
                            )
                        min_evidence_count = case.get("min_evidence_count")
                        if min_evidence_count is not None and summary["evidence_count"] < min_evidence_count:
                            _print_case_diagnostics(result)
                            raise AssertionError(
                                f"evidence_count below minimum: expected >= {min_evidence_count}, "
                                f"got {summary['evidence_count']}"
                            )
                        print(f"  intent: {result.get('current_intent')}", flush=True)
                        print(f"  final_status: {summary['final_status']}", flush=True)
                        print(f"  evidence_count: {summary['evidence_count']}", flush=True)
                        print(f"  final_response: {(result.get('final_response') or '')[:100]}", flush=True)
                        print(f"  trace_steps: {len(result.get('trace_steps') or [])} nodes", flush=True)
                        print("  PASS", flush=True)
                    except Exception as exc:
                        failures += 1
                        print(f"  FAIL: {exc}", flush=True)
    finally:
        await engine.dispose()

    if failures:
        print(f"\nSmoke test failed: {failures} case(s)", flush=True)
        sys.exit(1)
    print("\nSmoke test complete.", flush=True)


if __name__ == "__main__":
    asyncio.run(smoke_agent_live())
