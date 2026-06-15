from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.schemas import ApprovalDecisionCommand
from src.approvals.service import ApprovalService
from src.db.models import ApprovalAssignment, ApprovalDecision, ApprovalEvent, ApprovalLevel, ApprovalRequest
from tests.approvals.test_service_transitions import (
    _approval_bundle,
    _create_command,
    _create_run,
    _decision_command,
)


@pytest.mark.asyncio
async def test_single_level_request_has_one_level_one_assignment(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)

    levels = (
        await session.execute(select(ApprovalLevel).where(ApprovalLevel.approval_request_id == request.id))
    ).scalars().all()
    assignments = (
        await session.execute(
            select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id)
        )
    ).scalars().all()

    assert len(levels) == 1
    assert len(assignments) == 1
    assert level.level_number == 1
    assert level.required_role == "manager"
    assert level.mode == "any_one"
    assert level.status == "pending"
    assert assignment.assigned_role == "manager"
    assert assignment.status == "pending"
    assert request.status == "pending"


@pytest.mark.asyncio
async def test_single_level_runtime_approves_only_after_required_assignment_accepts(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

    result = await ApprovalService(session).decide(
        _decision_command(request, level, assignment, actor_id=actor_id, decision_type="approve")
    )

    await session.refresh(request)
    await session.refresh(level)
    await session.refresh(assignment)
    decisions = (await session.execute(select(ApprovalDecision))).scalars().all()
    events = (
        await session.execute(select(ApprovalEvent).where(ApprovalEvent.event_type == "approval_decided"))
    ).scalars().all()

    assert request.status == "approved"
    assert level.status == "approved"
    assert assignment.status == "approved"
    assert result.status == "approved"
    assert result.decision_type == "approve"
    assert result.resume_payload is not None
    assert len(decisions) == 1
    assert len(events) == 1


@pytest.mark.asyncio
async def test_create_request_persists_risk_level_and_nullable_risk_rule_ref(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=requested_by,
        thread_id="nullable-risk-rule-thread",
    )

    result = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id="nullable-risk-rule-thread",
            risk_level="medium",
            risk_rule_ref=None,
        )
    )
    request = await session.get(ApprovalRequest, result.approval_id)

    assert request is not None
    assert request.risk_level == "medium"
    assert request.risk_rule_ref is None


@pytest.mark.asyncio
async def test_create_request_uses_max_existing_revision_plus_one_for_run(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=requested_by,
        thread_id="revision-backfill-thread",
    )
    legacy = ApprovalRequest(
        run_id=run_id,
        tenant_id=tenant_id,
        schema_version="approval_request.v1",
        status="superseded",
        revision=7,
        version=1,
        legacy_non_executable=True,
        requested_by=requested_by,
        proposed_action={"legacy": True},
        risk_level="high",
        risk_rule_ref="legacy",
        risk_reason="legacy backfill",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        thread_id="revision-backfill-thread",
    )
    session.add(legacy)
    await session.flush()

    result = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id="revision-backfill-thread",
        )
    )
    request = await session.get(ApprovalRequest, result.approval_id)

    assert request is not None
    assert request.revision == 8


def test_decision_command_requires_level_assignment_run_and_thread_binding():
    missing_binding = {
        "approval_id": uuid4(),
        "tenant_id": uuid4(),
        "actor_id": uuid4(),
        "actor_role": "manager",
        "decision_type": "accept",
        "expected_request_version": 1,
        "expected_level_version": 1,
        "expected_assignment_version": 1,
        "expected_revision": 1,
        "action_payload_hash": "sha256:" + "a" * 64,
        "safety_snapshot_hash": "sha256:" + "b" * 64,
    }

    with pytest.raises(Exception):
        ApprovalDecisionCommand.model_validate(missing_binding)
