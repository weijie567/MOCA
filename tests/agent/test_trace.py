from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import build_trace_summary, write_agent_run, write_agent_steps
from src.db.models import AgentStep


@pytest.mark.asyncio
async def test_agent_steps_persist_tools_called_and_evidence_refs(session: AsyncSession):
    run_id = str(uuid4())
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    now = datetime.now(UTC)
    evidence_ref = {
        "doc_key": "policy_refund_timeout",
        "chunk_id": "chunk_001",
        "title": "退款超时规则",
        "confidence": 0.82,
        "retrieved_at": "2026-05-11T08:00:00+00:00",
    }

    await write_agent_run(
        session,
        run_id=run_id,
        thread_id="trace-test-thread",
        tenant_id=tenant_id,
        user_id=user_id,
        input_query="订单退款为什么超时？",
        final_status="completed",
        final_response="根据政策建议核实退款通道。",
        started_at=now,
        completed_at=now,
        total_latency_ms=12,
    )
    await write_agent_steps(
        session,
        run_id=run_id,
        trace_steps=[
            {
                "node": "investigate",
                "status": "completed",
                "tools_called": ["get_order", "get_refund_case", "search_policy"],
                "evidence_refs": [evidence_ref],
            },
            {
                "node": "legacy_tool_step",
                "status": "completed",
                "tool_name": "get_ticket",
            },
        ],
    )

    result = await session.execute(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index))
    rows = list(result.scalars())

    assert [row.node_name for row in rows] == [
        "investigate",
        "legacy_tool_step",
    ]
    assert rows[0].tool_name == "get_order,get_refund_case,search_policy"
    assert rows[0].tool_output_summary["tools_called"] == ["get_order", "get_refund_case", "search_policy"]
    assert rows[0].evidence_refs[0]["doc_key"] == "policy_refund_timeout"
    assert rows[0].evidence_refs[0]["chunk_id"] == "chunk_001"
    assert rows[1].tool_name == "get_ticket"


def test_trace_summary_counts_v2_evidence_refs():
    summary = build_trace_summary(
        "run-001",
        {
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [
                    {"evidence_id": "policy/chunk@v1"},
                    {"evidence_id": "policy/chunk@v2"},
                ],
            },
            "final_response": "done",
        },
        10,
    )

    assert summary["evidence_count"] == 2


def test_trace_summary_projects_target_graph_names_without_rewriting_legacy_nodes():
    summary = build_trace_summary(
        "run-graph-projection",
        {
            "current_intent": "refund_troubleshooting",
            "trace_steps": [
                {"node": "classify_intent", "status": "completed"},
                {"node": "extract_slots", "status": "completed"},
                {"node": "route_after_slots", "status": "completed"},
                {"node": "rag_context_build", "status": "deferred"},
            ],
            "final_response": "done",
        },
        25,
    )

    assert summary["nodes_executed"] == [
        "classify_intent",
        "extract_slots",
        "route_after_slots",
        "rag_context_build",
    ]
    assert summary["target_nodes_executed"] == [
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "route_after_slot_resolution",
        "rag_context_build",
    ]
    assert summary["graph_projection"]["schema_version"] == "target_graph_projection.v1"
    assert summary["graph_projection"]["steps"] == [
        {
            "implementation_node": "classify_intent",
            "target_node": "contextual_intent_resolve",
            "target_graph_status": "compatibility_alias",
            "target_graph_runnable": True,
        },
        {
            "implementation_node": "extract_slots",
            "target_node": "slot_resolution_gate",
            "target_graph_status": "compatibility_alias",
            "target_graph_runnable": True,
        },
        {
            "implementation_node": "route_after_slots",
            "target_node": "route_after_slot_resolution",
            "target_graph_status": "compatibility_alias",
            "target_graph_runnable": True,
        },
        {
            "implementation_node": "rag_context_build",
            "target_node": "rag_context_build",
            "target_graph_status": "deferred_non_runnable",
            "target_graph_runnable": False,
        },
    ]
