from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.merchant_context import project_target_merchant_context
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


def test_target_merchant_context_resolves_only_from_service_approved_business_fact_refs():
    state = {
        "tenant_id": "tenant-001",
        "current_intent": "refund_troubleshooting",
        "last_business_context_refs": {
            "business_fact_refs": [_business_fact_ref("tenant-001", resource_id="ORD-SECRET-001")]
        },
        "business_context": {
            "merchant_id": "MERCHANT-SECRET",
            "facts": [{"order_id": "ORD-SECRET-001"}],
            "raw_tool_payload": {"ticket_id": "TICKET-SECRET"},
        },
        "user_query": "请帮我查 ORD-SECRET-001",
    }

    projection = project_target_merchant_context(state)
    serialized = json.dumps(projection, ensure_ascii=False)

    assert projection == {
        "schema_version": "target_merchant_context.v1",
        "status": "resolved",
        "source": "business_fact_refs",
        "reason_codes": [],
        "business_fact_ref_count": 1,
    }
    for forbidden in ("ORD-SECRET-001", "MERCHANT-SECRET", "TICKET-SECRET", "请帮我查"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("source_system", "resource_type", "resource_id"),
    [
        ("demo_orders_db", "order", "ORD-ADAPTER-001"),
        ("demo_refund_cases_db", "refund_case", "REF-ADAPTER-001"),
        ("demo_tickets_db", "ticket", "TICKET-ADAPTER-001"),
    ],
)
def test_target_merchant_context_resolves_adapter_business_fact_refs(
    source_system: str,
    resource_type: str,
    resource_id: str,
) -> None:
    projection = project_target_merchant_context(
        {
            "tenant_id": "tenant-001",
            "current_intent": "refund_troubleshooting",
            "last_business_context_refs": {
                "business_fact_refs": [
                    _business_fact_ref(
                        "tenant-001",
                        source_system=source_system,
                        resource_type=resource_type,
                        resource_id=resource_id,
                    )
                ]
            },
        }
    )

    assert projection == {
        "schema_version": "target_merchant_context.v1",
        "status": "resolved",
        "source": "business_fact_refs",
        "reason_codes": [],
        "business_fact_ref_count": 1,
    }


def test_target_merchant_context_downgrades_spoofed_resolved_status_without_business_fact_refs():
    projection = project_target_merchant_context(
        {
            "tenant_id": "tenant-001",
            "current_intent": "refund_troubleshooting",
            "target_merchant_context": {
                "schema_version": "target_merchant_context.v1",
                "status": "resolved",
                "source": "active_slots",
                "merchant_id": "MERCHANT-SPOOF",
                "order_id": "ORD-SPOOF",
            },
            "active_slots": {"merchant_id": "MERCHANT-SPOOF", "order_id": "ORD-SPOOF"},
            "classification_trace": {"llm_text": "merchant MERCHANT-SPOOF is selected"},
        }
    )
    serialized = json.dumps(projection, ensure_ascii=False)

    assert projection == {
        "schema_version": "target_merchant_context.v1",
        "status": "deferred",
        "source": "business_fact_refs",
        "reason_codes": ["TARGET_MERCHANT_CONTEXT_DEFERRED_UNTIL_BUSINESS_FACT_REF"],
    }
    assert "MERCHANT-SPOOF" not in serialized
    assert "ORD-SPOOF" not in serialized


def test_target_merchant_context_marks_direct_response_paths_not_applicable():
    assert project_target_merchant_context({"current_intent": "small_talk"}) == {
        "schema_version": "target_merchant_context.v1",
        "status": "not_applicable",
        "source": "intent_policy",
        "reason_codes": [],
    }


def test_trace_summary_includes_safe_target_merchant_context_projection():
    summary = build_trace_summary(
        "run-merchant-context",
        {
            "tenant_id": "tenant-001",
            "current_intent": "order_status_inquiry",
            "last_business_context_refs": {
                "business_fact_refs": [_business_fact_ref("tenant-001", resource_id="ORD-SECRET-002")]
            },
            "final_response": "done",
        },
        11,
    )

    assert summary["target_merchant_context"] == {
        "schema_version": "target_merchant_context.v1",
        "status": "resolved",
        "source": "business_fact_refs",
        "reason_codes": [],
        "business_fact_ref_count": 1,
    }


def _business_fact_ref(
    tenant_id: str,
    *,
    resource_id: str,
    resource_type: str = "order",
    source_system: str = "business_fact_service",
) -> dict[str, str]:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": tenant_id,
        "source_system": source_system,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_version": "v1",
        "data_freshness_at": "2026-06-28T00:00:00+00:00",
        "retrieved_at": "2026-06-28T00:00:00+00:00",
    }
