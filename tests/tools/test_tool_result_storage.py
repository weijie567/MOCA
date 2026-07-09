from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, ToolCallRecord, ToolResultRecord
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


RAW_PHONE = "13800000000"
RAW_MARKER = "SHOULD_NOT_APPEAR"


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id=thread_id,
            input_query="test",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _raw_payload_result(tenant_id: uuid.UUID) -> ToolResultV2:
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-RAW-001",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={
            "order_id": "ORD-RAW-001",
            "raw_payload": {
                "customer_phone": RAW_PHONE,
                "nested": [RAW_MARKER],
            },
        },
        summary="Order ORD-RAW-001 loaded with safe summary only.",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[business_ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=17,
        audit_ref="audit/tool-result/ORD-RAW-001",
    )


def _metric_result(tenant_id: uuid.UUID) -> ToolResultV2:
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_fact_service",
        resource_type="business_metric",
        resource_id="order_count",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={
            "metric_id": "order_count",
            "status": "ok",
            "value": 7,
            "rate": None,
            "numerator": None,
            "denominator": None,
            "unit": "count",
            "display_value": "7",
            "scope": {
                "tenant_id": str(tenant_id),
                "merchant_ids": ["MERCHANT-ID-SHOULD-NOT-BE-IN-PROMPT"],
                "scope_label": "authorized_merchants",
            },
            "time_range": {
                "start_at": "2026-07-08T16:00:00Z",
                "end_at": "2026-07-09T04:00:00Z",
                "preset": "today",
                "timezone": "Asia/Shanghai",
            },
            "filters": {"merchant_id": None, "status_filter": []},
            "freshness": {
                "data_freshness_at": datetime.now(UTC).isoformat(),
                "computed_at": datetime.now(UTC).isoformat(),
                "source_system": "business_fact_service",
            },
            "formula": "count orders by created_at in authorized merchant scope",
            "caveats": [],
            "no_leak_status": "not_applicable",
        },
        summary="Business fact read succeeded",
        source_system="business_fact_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[business_ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=17,
        audit_ref=None,
    )


@pytest.mark.asyncio
async def test_tool_result_storage_keeps_four_layers_separate(session: AsyncSession, seeded_session: dict) -> None:
    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-tool-layering"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()

    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-layering",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-RAW-001", "customer_phone": RAW_PHONE},
        argument_summary_json={"order_no": "ORD-RAW-001", "omitted": ["customer_phone"]},
        redaction_policy_version="conversation_redaction.v1",
    )
    prompt_summary = await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-layering",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-layered-1",
        tool_name="get_order",
        result=_raw_payload_result(tenant_id),
        raw_result_ref="raw-result://orders/ORD-RAW-001",
        raw_result_hash="sha256:rawresultfixture",
    )

    stored = (
        await session.execute(
            select(ToolResultRecord).where(ToolResultRecord.tool_result_id == "tool-result-layered-1")
        )
    ).scalar_one()

    assert stored.raw_result_ref == "raw-result://orders/ORD-RAW-001"
    assert stored.raw_result_hash == "sha256:rawresultfixture"
    # Phase 29: normalized_result_json is projector-normalized, raw sentinels stripped.
    assert "raw_payload" not in stored.normalized_result_json
    assert stored.summary == "Order ORD-RAW-001 loaded with safe summary only."
    assert stored.prompt_summary == prompt_summary.prompt_summary
    assert stored.prompt_summary != stored.summary
    assert RAW_PHONE not in stored.prompt_summary
    assert RAW_MARKER not in stored.prompt_summary
    assert set(prompt_summary.model_dump(mode="json")) == {
        "tool_call_id",
        "tool_result_id",
        "tool_name",
        "status",
        "summary",
        "prompt_summary",
        "business_fact_refs",
        "policy_evidence_refs",
        "raw_result_ref",
        "audit_ref",
    }


@pytest.mark.asyncio
async def test_prompt_summary_excludes_large_nested_data(session: AsyncSession, seeded_session: dict) -> None:
    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-tool-prompt-safe"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()

    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-prompt-safe",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-RAW-001", "customer_phone": RAW_PHONE},
        argument_summary_json={"order_no": "ORD-RAW-001", "omitted": ["customer_phone"]},
        redaction_policy_version="conversation_redaction.v1",
    )
    prompt_summary = await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-prompt-safe",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-prompt-safe-1",
        tool_name="get_order",
        result=_raw_payload_result(tenant_id),
        raw_result_ref="raw-result://orders/ORD-RAW-001",
        raw_result_hash="sha256:rawresultfixture",
    )

    dumped = prompt_summary.model_dump(mode="json")

    assert "data" not in dumped
    assert "raw_payload" not in dumped
    assert RAW_PHONE not in str(dumped)
    assert RAW_MARKER not in str(dumped)
    # Phase 29: prompt_summary uses projection format [tool_name] status — summary
    assert "get_order" in dumped["prompt_summary"]
    assert "success" in dumped["prompt_summary"]


@pytest.mark.asyncio
async def test_metric_prompt_summary_is_concise_and_scope_safe(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-tool-metric-summary"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()

    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-metric-summary",
        tool_call_id=str(operation_id),
        tool_name="query_business_metric",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"metric_id": "order_count", "time_preset": "today"},
        argument_summary_json={"metric_id": "order_count", "time_preset": "today"},
        redaction_policy_version="conversation_redaction.v1",
    )
    prompt_summary = await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-metric-summary",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-metric-1",
        tool_name="query_business_metric",
        result=_metric_result(tenant_id),
    )

    dumped = prompt_summary.model_dump(mode="json")

    assert "order_count" in dumped["prompt_summary"]
    assert "7" in dumped["prompt_summary"]
    assert "MERCHANT-ID-SHOULD-NOT-BE-IN-PROMPT" not in dumped["prompt_summary"]
    assert str(tenant_id) not in dumped["prompt_summary"]
    assert "SELECT" not in dumped["prompt_summary"]


@pytest.mark.asyncio
async def test_tool_argument_summary_uses_hash_not_raw_args(session: AsyncSession, seeded_session: dict) -> None:
    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-tool-argument-hash"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()

    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-tool-argument-hash",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={
            "order_no": "ORD-RAW-001",
            "raw_payload": {"customer_phone": RAW_PHONE, "nested": [RAW_MARKER]},
        },
        argument_summary_json={"order_no": "ORD-RAW-001", "omitted": ["raw_payload"]},
        redaction_policy_version="conversation_redaction.v1",
    )

    stored = (await session.execute(select(ToolCallRecord).where(ToolCallRecord.id == tool_call.id))).scalar_one()

    assert stored.argument_hash.startswith("sha256:")
    assert stored.argument_summary_json == {"order_no": "ORD-RAW-001", "omitted": ["raw_payload"]}
    assert RAW_PHONE not in str(stored.argument_summary_json)
    assert RAW_MARKER not in str(stored.argument_summary_json)
    assert "raw_payload" not in stored.argument_summary_json
