from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.snapshots import build_action_safety_snapshot
from src.db.models import ActionSafetySnapshot, ApprovalRequest
from tests.approvals.test_service_transitions import (
    _approval_bundle,
    _assert_transition_error,
    _create_run,
    _decision_command,
    _evidence_ref,
)


def _changed_snapshot_hash(*, tenant_id, run_id, field: str) -> str:
    evidence = [_evidence_ref(tenant_id=tenant_id)]
    kwargs = {
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "snapshot_id": f"snap-{field}",
        "snapshot_ref": f"snapshot:{field}",
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "retrieval_config_version": "retrieval.v1",
        "evidence": evidence,
        "action_payload_hash": "sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094",
        "created_at": "2026-06-15T00:00:00.000Z",
    }
    if field == "changed_evidence_hash":
        kwargs["evidence"] = [
            _evidence_ref(
                tenant_id=tenant_id,
                text_hash="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            )
        ]
    elif field == "changed_evidence_ref":
        kwargs["evidence"] = [
            _evidence_ref(
                tenant_id=tenant_id,
                evidence_id="refund-policy/chunk-999@v3",
                chunk_id="chunk-999",
            )
        ]
    elif field == "changed_evidence_rank":
        kwargs["evidence"] = [_evidence_ref(tenant_id=tenant_id, rank=2)]
    elif field == "changed_policy_config_version":
        kwargs["policy_config_version"] = "approval-policy.v2"
    elif field == "changed_risk_config_version":
        kwargs["risk_config_version"] = "risk-rules.v2"
    elif field == "changed_retrieval_config_version":
        kwargs["retrieval_config_version"] = "retrieval.v2"
        kwargs["evidence"] = [
            _evidence_ref(
                tenant_id=tenant_id,
                retrieval_config_version="retrieval.v2",
            )
        ]
    else:
        raise AssertionError(f"unhandled changed snapshot field {field}")

    return build_action_safety_snapshot(**kwargs).immutable_hash


@pytest.mark.asyncio
async def test_changed_action_payload_hash_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            action_payload_hash="sha256:" + "9" * 64,
        ),
        code="approval_hash_mismatch",
    )


@pytest.mark.asyncio
async def test_changed_safety_snapshot_hash_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            safety_snapshot_hash="sha256:" + "8" * 64,
        ),
        code="approval_hash_mismatch",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "changed_evidence_hash",
        "changed_evidence_ref",
        "changed_evidence_rank",
        "changed_policy_config_version",
        "changed_risk_config_version",
        "changed_retrieval_config_version",
    ],
)
async def test_changed_snapshot_material_fails_closed_via_snapshot_hash(
    session: AsyncSession,
    seeded_session,
    field: str,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id
    changed_hash = _changed_snapshot_hash(tenant_id=request.tenant_id, run_id=request.run_id, field=field)

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            safety_snapshot_hash=changed_hash,
        ),
        code="approval_hash_mismatch",
    )


@pytest.mark.asyncio
async def test_missing_snapshot_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["approval_manager"].id
    await session.execute(
        delete(ActionSafetySnapshot).where(
            ActionSafetySnapshot.tenant_id == request.tenant_id,
            ActionSafetySnapshot.immutable_hash == request.safety_snapshot_hash,
        )
    )
    await session.flush()

    await _assert_transition_error(
        session,
        _decision_command(request, level, assignment, actor_id=actor_id),
        code="approval_not_executable",
    )


@pytest.mark.asyncio
async def test_legacy_v1_rows_fail_closed(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    actor_id = seeded_session["users"]["approval_manager"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=requested_by, thread_id="legacy-v1-thread")
    legacy = ApprovalRequest(
        run_id=run_id,
        tenant_id=tenant_id,
        schema_version="approval_request.v1",
        status="pending",
        revision=1,
        version=1,
        legacy_non_executable=True,
        requested_by=requested_by,
        proposed_action={"legacy": True},
        risk_level="high",
        risk_rule_ref="legacy",
        risk_reason="legacy row",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        thread_id="legacy-v1-thread",
    )
    session.add(legacy)
    await session.flush()
    request = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == legacy.id))).scalar_one()

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level=type("Level", (), {"id": uuid4(), "version": 1})(),
            assignment=type("Assignment", (), {"id": uuid4(), "version": 1})(),
            actor_id=actor_id,
            action_payload_hash="sha256:" + "7" * 64,
            safety_snapshot_hash="sha256:" + "6" * 64,
        ),
        code="approval_not_executable",
    )
