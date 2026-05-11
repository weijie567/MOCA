#!/usr/bin/env python
"""Live smoke test for the MOCA refund agent.

Requires: DASHSCOPE_API_KEY set in environment, running Postgres DB.
NOT for CI - run manually to verify real LLM chain.
Usage: uv run python scripts/smoke_agent_live.py

Per D-11e.
"""

from __future__ import annotations

import asyncio
import os
import sys


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

    test_cases = [
        {
            "query": "退款超时规则是什么？",
            "thread_id": "smoke-test-001",
            "expected_intent": "policy_qa",
        },
        {
            "query": "订单ORD-001为什么还没退款？",
            "thread_id": "smoke-test-002",
            "expected_intent": "refund_troubleshooting",
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
                print(f"\n--- Test {i}: {case['query'][:40]}...")
                async with session_factory() as session:
                    config = {"configurable": {"thread_id": case["thread_id"], "session": session}}
                    input_state = {
                        "user_query": case["query"],
                        "thread_id": case["thread_id"],
                        "tenant_id": "00000000-0000-0000-0000-000000000001",
                        "user_id": "00000000-0000-0000-0000-000000000002",
                        "role": "support_agent",
                    }
                    try:
                        result = await graph.ainvoke(input_state, config)
                        summary = build_trace_summary(result["current_run_id"], result, 0)
                        if case.get("expected_intent") and result.get("current_intent") != case["expected_intent"]:
                            raise AssertionError(
                                f"intent mismatch: expected {case['expected_intent']}, got {result.get('current_intent')}"
                            )
                        if (
                            case.get("expected_final_status")
                            and summary["final_status"] != case["expected_final_status"]
                        ):
                            raise AssertionError(
                                "final status mismatch: "
                                f"expected {case['expected_final_status']}, got {summary['final_status']}"
                            )
                        print(f"  intent: {result.get('current_intent')}")
                        print(f"  final_status: {summary['final_status']}")
                        print(f"  final_response: {(result.get('final_response') or '')[:100]}")
                        print(f"  trace_steps: {len(result.get('trace_steps') or [])} nodes")
                        print("  PASS")
                    except Exception as exc:
                        failures += 1
                        print(f"  FAIL: {exc}")
    finally:
        await engine.dispose()

    if failures:
        print(f"\nSmoke test failed: {failures} case(s)")
        sys.exit(1)
    print("\nSmoke test complete.")


if __name__ == "__main__":
    asyncio.run(smoke_agent_live())
