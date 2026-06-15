"""Approval event helpers for the Phase 10 minimal trace envelope."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import emit_event
from src.approvals.repository import ApprovalRepository
from src.approvals.schemas import ApprovalDecisionType
from src.db.models import ApprovalAssignment, ApprovalDecision, ApprovalEvent, ApprovalLevel, ApprovalRequest


APPROVAL_EVENT_TYPES = {
    "approval_requested",
    "approval_decided",
    "approval_expired",
    "approval_resumed",
}
FORBIDDEN_APPROVAL_EVENT_KEYS = {
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
REVISION_CHANGE_REF_KEYS = {
    "old_action_payload_hash",
    "new_action_payload_hash",
    "old_safety_snapshot_hash",
    "new_safety_snapshot_hash",
    "old_policy_config_version",
    "new_policy_config_version",
    "old_risk_config_version",
    "new_risk_config_version",
    "old_retrieval_config_version",
    "new_retrieval_config_version",
}


async def emit_approval_requested(
    session: AsyncSession,
    *,
    request: ApprovalRequest,
    level: ApprovalLevel,
    assignment: ApprovalAssignment,
    actor_id: UUID,
    existing_event: ApprovalEvent | None = None,
    metadata: Mapping[str, Any] | None = None,
    resource_refs: Mapping[str, Any] | None = None,
    redacted_payload: Mapping[str, Any] | None = None,
) -> ApprovalEvent:
    """Emit a redacted approval_requested event and link the approval audit row."""
    safe_metadata = {
        "approval_policy_id": request.approval_policy_id,
        "policy_version": request.policy_version,
        "risk_level": request.risk_level,
        "risk_rule_ref": request.risk_rule_ref,
        **dict(metadata or {}),
    }
    safe_payload = {
        "event_type": "approval_requested",
        "status": request.status,
        "risk_level": request.risk_level,
        "has_risk_reason": bool(request.risk_reason),
        **dict(redacted_payload or {}),
    }
    return await _emit_approval_event(
        session,
        event_type="approval_requested",
        request=request,
        level=level,
        assignment=assignment,
        actor_id=actor_id,
        actor_type="approver",
        existing_event=existing_event,
        metadata=safe_metadata,
        resource_refs=resource_refs,
        redacted_payload=safe_payload,
    )


async def emit_approval_decided(
    session: AsyncSession,
    *,
    request: ApprovalRequest,
    level: ApprovalLevel,
    assignment: ApprovalAssignment,
    decision_type: ApprovalDecisionType | str,
    actor_id: UUID,
    decision: ApprovalDecision | None = None,
    decision_id: UUID | None = None,
    old_revision_ref: str | None = None,
    new_revision_ref: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    resource_refs: Mapping[str, Any] | None = None,
    redacted_payload: Mapping[str, Any] | None = None,
) -> ApprovalEvent:
    """Emit approval_decided with required revision refs for edit/respond or changed material."""
    extra_refs = dict(resource_refs or {})
    if old_revision_ref:
        extra_refs["old_revision_ref"] = old_revision_ref
    if new_revision_ref:
        extra_refs["new_revision_ref"] = new_revision_ref
    if decision_id:
        extra_refs["decision_ref"] = f"approval_decision:{decision_id}"

    _assert_decision_revision_refs(decision_type=str(decision_type), resource_refs=extra_refs)

    safe_metadata = {
        "decision_type": str(decision_type),
        **dict(metadata or {}),
    }
    safe_payload = {
        "event_type": "approval_decided",
        "status": request.status,
        "decision_type": str(decision_type),
        "has_reason": bool(getattr(decision, "reason", None)),
        "has_response_text": bool(getattr(decision, "response_text", None)),
        "has_edited_action": bool(getattr(decision, "edited_action_json", None)),
        **dict(redacted_payload or {}),
    }
    return await _emit_approval_event(
        session,
        event_type="approval_decided",
        request=request,
        level=level,
        assignment=assignment,
        decision=decision,
        actor_id=actor_id,
        actor_type="approver",
        metadata=safe_metadata,
        resource_refs=extra_refs,
        redacted_payload=safe_payload,
    )


async def emit_approval_expired(
    session: AsyncSession,
    *,
    request: ApprovalRequest,
    level: ApprovalLevel | None = None,
    assignment: ApprovalAssignment | None = None,
    actor_id: UUID | None = None,
    metadata: Mapping[str, Any] | None = None,
    resource_refs: Mapping[str, Any] | None = None,
    redacted_payload: Mapping[str, Any] | None = None,
) -> ApprovalEvent:
    """Emit approval_expired from the SLA/system actor path."""
    safe_metadata = {
        "reason": "sla_due",
        **dict(metadata or {}),
    }
    safe_payload = {
        "event_type": "approval_expired",
        "status": request.status,
        "reason": safe_metadata["reason"],
        **dict(redacted_payload or {}),
    }
    return await _emit_approval_event(
        session,
        event_type="approval_expired",
        request=request,
        level=level,
        assignment=assignment,
        actor_id=actor_id,
        actor_type="system",
        metadata=safe_metadata,
        resource_refs=resource_refs,
        redacted_payload=safe_payload,
    )


async def emit_approval_resumed(
    session: AsyncSession,
    *,
    request: ApprovalRequest,
    level: ApprovalLevel | None = None,
    assignment: ApprovalAssignment | None = None,
    actor_id: UUID,
    metadata: Mapping[str, Any] | None = None,
    resource_refs: Mapping[str, Any] | None = None,
    redacted_payload: Mapping[str, Any] | None = None,
) -> ApprovalEvent:
    """Register a redacted graph resume lifecycle event."""
    safe_metadata = {
        "resume_owner": "approval resume lifecycle",
        **dict(metadata or {}),
    }
    safe_payload = {
        "event_type": "approval_resumed",
        "status": request.status,
        **dict(redacted_payload or {}),
    }
    return await _emit_approval_event(
        session,
        event_type="approval_resumed",
        request=request,
        level=level,
        assignment=assignment,
        actor_id=actor_id,
        actor_type="approver",
        metadata=safe_metadata,
        resource_refs=resource_refs,
        redacted_payload=safe_payload,
    )


def approval_revision_ref(request: ApprovalRequest, *, request_version: int | None = None) -> str:
    """Return a stable approval revision/version ref without raw approval payload data."""
    version = request.version if request_version is None else request_version
    return f"approval_revision:{request.id}:r{request.revision}:v{version}"


def validate_approval_event_payload(
    *,
    metadata: Mapping[str, Any],
    resource_refs: Mapping[str, Any],
    redacted_payload: Mapping[str, Any],
) -> None:
    """Reject unsafe event keys across all persisted approval event JSON fields."""
    _guard_safe_mapping(metadata, "metadata_json")
    _guard_safe_mapping(resource_refs, "resource_refs_json")
    _guard_safe_mapping(redacted_payload, "redacted_payload_json")


async def _emit_approval_event(
    session: AsyncSession,
    *,
    event_type: str,
    request: ApprovalRequest,
    level: ApprovalLevel | None,
    assignment: ApprovalAssignment | None,
    actor_id: UUID | None,
    actor_type: str,
    metadata: Mapping[str, Any] | None,
    resource_refs: Mapping[str, Any] | None,
    redacted_payload: Mapping[str, Any] | None,
    decision: ApprovalDecision | None = None,
    existing_event: ApprovalEvent | None = None,
) -> ApprovalEvent:
    if event_type not in APPROVAL_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not a Phase 13 approval event")

    safe_metadata = _json_safe(dict(metadata or {}))
    safe_refs = _json_safe(
        {
            **_base_resource_refs(request=request, level=level, assignment=assignment, decision=decision),
            **dict(resource_refs or {}),
        }
    )
    safe_payload = _json_safe(dict(redacted_payload or {}))
    validate_approval_event_payload(
        metadata=safe_metadata,
        resource_refs=safe_refs,
        redacted_payload=safe_payload,
    )

    trace_event = await emit_event(
        session,
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        thread_id=request.thread_id,
        event_type=event_type,
        actor={"type": actor_type, "id": str(actor_id) if actor_id else "approval-sla-scanner"},
        resource_refs=safe_refs,
        redacted_payload=safe_payload,
    )

    if existing_event is not None:
        approval_event = existing_event
        approval_event.replay_event_id = trace_event["event_id"]
        approval_event.actor_id = actor_id
        approval_event.metadata_json = safe_metadata
        approval_event.resource_refs_json = safe_refs
        approval_event.redacted_payload_json = safe_payload
        approval_event.level_version = level.version if level else None
        approval_event.assignment_version = assignment.version if assignment else None
        await session.flush()
        return approval_event

    approval_event = await ApprovalRepository(session).insert_approval_event(
        request=request,
        event_type=event_type,
        decision=decision,
        actor_id=actor_id,
        level=level,
        assignment=assignment,
        metadata=safe_metadata,
        resource_refs=safe_refs,
        redacted_payload=safe_payload,
    )
    approval_event.replay_event_id = trace_event["event_id"]
    await session.flush()
    return approval_event


def _base_resource_refs(
    *,
    request: ApprovalRequest,
    level: ApprovalLevel | None,
    assignment: ApprovalAssignment | None,
    decision: ApprovalDecision | None,
) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "request_ref": f"approval_request:{request.id}:r{request.revision}",
        "revision_ref": approval_revision_ref(request),
        "request_version": request.version,
        "action_payload_hash": request.action_payload_hash,
        "safety_snapshot_ref": request.safety_snapshot_ref,
        "safety_snapshot_hash": request.safety_snapshot_hash,
    }
    if level is not None:
        refs["level_ref"] = f"approval_level:{level.id}:v{level.version}"
        refs["level_version"] = level.version
    if assignment is not None:
        refs["assignment_ref"] = f"approval_assignment:{assignment.id}:v{assignment.version}"
        refs["assignment_version"] = assignment.version
    if decision is not None:
        refs["decision_ref"] = f"approval_decision:{decision.id}"
    return refs


def _assert_decision_revision_refs(*, decision_type: str, resource_refs: Mapping[str, Any]) -> None:
    requires_revision_refs = decision_type in {"edit", "respond"} or any(
        key in resource_refs for key in REVISION_CHANGE_REF_KEYS
    )
    if requires_revision_refs and (
        not resource_refs.get("old_revision_ref") or not resource_refs.get("new_revision_ref")
    ):
        raise ValueError(
            "old_revision_ref and new_revision_ref are required for edit/respond and hash/config-changing decisions"
        )


def _guard_safe_mapping(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_APPROVAL_EVENT_KEYS:
                raise ValueError(f"{path} must not carry {key}")
            _guard_safe_mapping(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _guard_safe_mapping(child, f"{path}[{index}]")


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items() if child is not None}
    if isinstance(value, list):
        return [_json_safe(child) for child in value]
    return value
