from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import EVENT_RETENTION_CLASSIFICATION, MINIMAL_EVENT_TYPES, emit_event
from src.approvals.events import emit_approval_decided, emit_approval_resumed, validate_approval_event_payload
from src.approvals.service import ApprovalService
from src.db.models import AgentTraceEvent, ApprovalEvent
from tests.approvals.test_needs_info_resume import _changed_action
from tests.approvals.test_service_transitions import _approval_bundle, _decision_command as _base_decision_command


APPROVAL_EVENT_TYPES = {
    "approval_requested",
    "approval_decided",
    "approval_expired",
    "approval_resumed",
}


def _decision_command(*args, **kwargs):
    kwargs.setdefault("actor_role", "admin")
    return _base_decision_command(*args, **kwargs)


FORBIDDEN_APPROVAL_PAYLOAD_KEYS = {
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
            assert not (set(item) & FORBIDDEN_APPROVAL_PAYLOAD_KEYS)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)


def _required_ref_keys() -> set[str]:
    return {
        "request_ref",
        "level_ref",
        "assignment_ref",
        "revision_ref",
        "request_version",
        "level_version",
        "assignment_version",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    }


def test_approval_event_types_and_retention_are_registered():
    assert APPROVAL_EVENT_TYPES <= MINIMAL_EVENT_TYPES
    for event_type in APPROVAL_EVENT_TYPES:
        assert EVENT_RETENTION_CLASSIFICATION[event_type] == "minimal_event"


@pytest.mark.asyncio
async def test_approval_requested_persists_trace_and_approval_event_refs(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)

    approval_event = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == request.id,
                ApprovalEvent.event_type == "approval_requested",
            )
        )
    ).scalar_one()
    trace_event = await session.get(AgentTraceEvent, approval_event.replay_event_id)

    assert trace_event is not None
    assert trace_event.event_type == "approval_requested"
    assert approval_event.actor_id == request.requested_by
    assert approval_event.metadata_json["risk_level"] == request.risk_level
    assert approval_event.resource_refs_json["request_ref"] == f"approval_request:{request.id}:r{request.revision}"
    assert approval_event.resource_refs_json["level_ref"] == f"approval_level:{level.id}:v{level.version}"
    assert (
        approval_event.resource_refs_json["assignment_ref"]
        == f"approval_assignment:{assignment.id}:v{assignment.version}"
    )
    assert _required_ref_keys() <= set(approval_event.resource_refs_json)
    assert trace_event.actor == {"type": "approver", "id": str(request.requested_by)}
    assert trace_event.resource_refs == approval_event.resource_refs_json
    assert trace_event.redacted_payload == approval_event.redacted_payload_json
    _assert_safe_mapping(approval_event.metadata_json)
    _assert_safe_mapping(approval_event.resource_refs_json)
    _assert_safe_mapping(approval_event.redacted_payload_json)


@pytest.mark.asyncio
@pytest.mark.parametrize("decision_type", ["accept", "approve", "edit", "respond", "reject", "ignore"])
async def test_approval_decided_payload_distinguishes_all_decision_types(
    session: AsyncSession,
    seeded_session,
    decision_type: str,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    overrides: dict[str, Any] = {}
    if decision_type == "edit":
        overrides["edited_action"] = _changed_action(request)
    if decision_type == "respond":
        overrides["response_text"] = "Please confirm the refund case and coupon amount."

    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type=decision_type,
            **overrides,
        )
    )
    approval_event = await session.get(ApprovalEvent, result.event_id)
    assert approval_event is not None
    trace_event = await session.get(AgentTraceEvent, approval_event.replay_event_id)

    assert trace_event is not None
    assert approval_event.event_type == "approval_decided"
    assert trace_event.event_type == "approval_decided"
    assert approval_event.actor_id == actor_id
    assert approval_event.metadata_json["decision_type"] == decision_type
    assert approval_event.redacted_payload_json["decision_type"] == decision_type
    assert approval_event.resource_refs_json["decision_ref"] == f"approval_decision:{result.decision_id}"
    assert _required_ref_keys() <= set(approval_event.resource_refs_json)
    assert trace_event.resource_refs == approval_event.resource_refs_json
    assert trace_event.redacted_payload == approval_event.redacted_payload_json
    if decision_type in {"edit", "respond"}:
        assert "old_revision_ref" in approval_event.resource_refs_json
        assert "new_revision_ref" in approval_event.resource_refs_json
    _assert_safe_mapping(approval_event.metadata_json)
    _assert_safe_mapping(approval_event.resource_refs_json)
    _assert_safe_mapping(approval_event.redacted_payload_json)


@pytest.mark.asyncio
async def test_approval_decided_requires_old_and_new_revision_refs_for_edit_and_respond(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id
    result = await ApprovalService(session).decide(
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            decision_type="respond",
            response_text="Please confirm the refund case.",
        )
    )

    with pytest.raises(ValueError, match="old_revision_ref"):
        await emit_approval_decided(
            session,
            request=request,
            level=level,
            assignment=assignment,
            decision_id=result.decision_id,
            actor_id=actor_id,
            decision_type="respond",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_ref",
    [
        "new_action_payload_hash",
        "new_safety_snapshot_hash",
        "new_policy_config_version",
        "new_risk_config_version",
        "new_retrieval_config_version",
    ],
)
async def test_approval_decided_requires_old_and_new_revision_refs_for_hash_config_changes(
    session: AsyncSession,
    seeded_session,
    changed_ref: str,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    with pytest.raises(ValueError, match="new_revision_ref"):
        await emit_approval_decided(
            session,
            request=request,
            level=level,
            assignment=assignment,
            decision_id=None,
            actor_id=actor_id,
            decision_type="accept",
            resource_refs={changed_ref: "changed-value"},
        )


@pytest.mark.asyncio
async def test_approval_resumed_helper_uses_minimal_event_without_graph_resume_wiring(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    approval_event = await emit_approval_resumed(
        session,
        request=request,
        level=level,
        assignment=assignment,
        actor_id=actor_id,
        metadata={"resume_owner": "Phase 15 replay lifecycle"},
    )
    trace_event = await session.get(AgentTraceEvent, approval_event.replay_event_id)

    assert approval_event.event_type == "approval_resumed"
    assert approval_event.actor_id == actor_id
    assert trace_event is not None
    assert trace_event.event_type == "approval_resumed"
    assert approval_event.metadata_json["resume_owner"] == "Phase 15 replay lifecycle"
    assert _required_ref_keys() <= set(approval_event.resource_refs_json)


@pytest.mark.asyncio
@pytest.mark.parametrize("forbidden_key", sorted(FORBIDDEN_APPROVAL_PAYLOAD_KEYS))
async def test_redaction_rejects_raw_prompt_args_payload_tool_output_secrets_credentials_and_pii(
    session: AsyncSession,
    seeded_session,
    forbidden_key: str,
):
    request, level, assignment = await _approval_bundle(session, seeded_session)

    with pytest.raises(ValueError):
        validate_approval_event_payload(
            metadata={},
            resource_refs={"request_ref": f"approval_request:{request.id}"},
            redacted_payload={"summary": {forbidden_key: "must not persist"}},
        )

    with pytest.raises(ValueError):
        await emit_event(
            session,
            run_id=request.run_id,
            tenant_id=request.tenant_id,
            thread_id=request.thread_id,
            event_type="approval_decided",
            actor={"type": "approver", "id": str(request.requested_by)},
            resource_refs={"request_ref": f"approval_request:{request.id}"},
            redacted_payload={"summary": {forbidden_key: "must not persist"}},
        )
