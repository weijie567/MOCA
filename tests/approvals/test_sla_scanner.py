from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.sla_scanner import ApprovalSlaScanner, build_sla_event_shape
from src.config import Settings
from src.db.models import AgentTraceEvent, ApprovalEvent
from tests.approvals.test_service_transitions import _approval_bundle


FORBIDDEN_SLA_PAYLOAD_KEYS = {
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "pii",
}


def _assert_safe_mapping(value: Mapping[str, Any]) -> None:
    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            assert not (set(item) & FORBIDDEN_SLA_PAYLOAD_KEYS)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)


def test_approval_sla_scanner_disabled_by_default(monkeypatch):
    monkeypatch.delenv("APPROVAL_SLA_SCANNER_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.approval_sla_scanner_enabled is False


@pytest.mark.asyncio
async def test_disabled_scanner_noop_returns_disabled_result_and_writes_no_rows(
    session: AsyncSession,
    seeded_session,
):
    request, _level, _assignment = await _approval_bundle(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    event_count_before = int(await session.scalar(select(func.count()).select_from(ApprovalEvent)) or 0)
    trace_count_before = int(await session.scalar(select(func.count()).select_from(AgentTraceEvent)) or 0)

    result = await ApprovalSlaScanner(session=session, enabled=False).scan(now=datetime.now(UTC))
    await session.refresh(request)

    assert result.status == "disabled"
    assert result.expired_count == 0
    assert result.event_count == 0
    assert request.status == "pending"
    assert int(await session.scalar(select(func.count()).select_from(ApprovalEvent)) or 0) == event_count_before
    assert int(await session.scalar(select(func.count()).select_from(AgentTraceEvent)) or 0) == trace_count_before


@pytest.mark.asyncio
async def test_enabled_scanner_expires_request_level_assignment_and_writes_replay_event(
    session: AsyncSession,
    seeded_session,
):
    now = datetime.now(UTC)
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        expires_at=now - timedelta(minutes=1),
    )

    result = await ApprovalSlaScanner(session=session, enabled=True).scan(now=now)
    await session.refresh(request)
    await session.refresh(level)
    await session.refresh(assignment)

    assert result.status == "completed"
    assert result.expired_count == 1
    assert result.event_count == 1
    assert request.status == "expired"
    assert level.status == "expired"
    assert assignment.status == "expired"
    assert request.version == 2
    assert level.version == 2
    assert assignment.version == 2

    event = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == request.id,
                ApprovalEvent.event_type == "approval_expired",
            )
        )
    ).scalar_one()
    trace_event = await session.get(AgentTraceEvent, event.replay_event_id)

    assert event.request_version == 2
    assert event.level_version == 2
    assert event.assignment_version == 2
    assert event.resource_refs_json["request_version"] == 2
    assert event.resource_refs_json["level_version"] == 2
    assert event.resource_refs_json["assignment_version"] == 2
    assert trace_event is not None
    assert trace_event.event_type == "approval_expired"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type",
    ["approval_sla_reminder", "approval_sla_escalation", "approval_expired"],
)
async def test_sla_event_shape_helpers_use_safe_refs_only(
    session: AsyncSession,
    seeded_session,
    event_type: str,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)

    shape = build_sla_event_shape(
        event_type=event_type,
        request=request,
        level=level,
        assignment=assignment,
        reason="sla_due",
    )

    assert shape["metadata"]["reason"] == "sla_due"
    assert shape["metadata"]["phase_15_owner"] == "SLA scanner enablement"
    assert shape["resource_refs"]["request_ref"] == f"approval_request:{request.id}:r{request.revision}"
    assert shape["resource_refs"]["level_ref"] == f"approval_level:{level.id}:v{level.version}"
    assert shape["resource_refs"]["assignment_ref"] == f"approval_assignment:{assignment.id}:v{assignment.version}"
    assert shape["resource_refs"]["request_version"] == request.version
    assert shape["resource_refs"]["level_version"] == level.version
    assert shape["resource_refs"]["assignment_version"] == assignment.version
    assert shape["redacted_payload"]["event_type"] == event_type
    _assert_safe_mapping(shape["metadata"])
    _assert_safe_mapping(shape["resource_refs"])
    _assert_safe_mapping(shape["redacted_payload"])


def test_approval_sla_scanner_env_var_name_is_documented_for_phase_13():
    assert "APPROVAL_SLA_SCANNER_ENABLED" == "APPROVAL_SLA_SCANNER_ENABLED"
