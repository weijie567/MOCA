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
from unittest.mock import AsyncMock


async def smoke_agent_live():
    """Run 3 test queries against the live agent graph."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from src.agent.graph import build_graph
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

    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_database_url) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)

        for i, case in enumerate(test_cases, 1):
            print(f"\n--- Test {i}: {case['query'][:40]}...")
            mock_session = AsyncMock()
            config = {"configurable": {"thread_id": case["thread_id"], "session": mock_session}}
            input_state = {
                "user_query": case["query"],
                "thread_id": case["thread_id"],
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "user_id": "00000000-0000-0000-0000-000000000002",
                "role": "support_agent",
            }
            try:
                result = await graph.ainvoke(input_state, config)
                print(f"  intent: {result.get('current_intent')}")
                print(f"  final_response: {(result.get('final_response') or '')[:100]}")
                print(f"  trace_steps: {len(result.get('trace_steps') or [])} nodes")
                print("  PASS")
            except Exception as exc:
                print(f"  FAIL: {exc}")

    print("\nSmoke test complete.")


if __name__ == "__main__":
    asyncio.run(smoke_agent_live())
