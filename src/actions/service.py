from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.drafts import ActionDraftStore
from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1
from src.agent.events import emit_event
from src.approvals.snapshot_service import compute_action_payload_hash
from src.common.canonical_hash import CanonicalHashError
from src.db.models import ActionSafetySnapshot, AgentRun, ApprovalRequest

_IDEMPOTENCY_CONFLICTS = {"idempotency_key_conflict", "idempotency_binding_conflict"}
_ACTION_RESULT_COMPAT_GATE = (
    "Phase 14 deprecated compatibility output; replace/remove at Phase 15 Replay Event Contract "
    "before Phase 15 verification, target no later than 2026-07-16 unless Phase 15 is replanned."
)


@dataclass(frozen=True)
class _ValidatedActionBinding:
    revision_marker: str
    approval_revision_ref: str | None


def _tool_success(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool) -> dict[str, Any]:
    return {
        "status": "error",
        "data": {},
        "error": {"error_code": error_code, "message": message, "retryable": retryable},
    }


class ActionService:
    """Business owner for durable action draft creation."""

    def __init__(self, session: AsyncSession, *, draft_store: ActionDraftStore | None = None) -> None:
        self.session = session
        self.draft_store = draft_store or ActionDraftStore(session)

    async def create_coupon_grant_draft(
        self,
        *,
        tenant_id: str,
        user_id: str,
        run_id: str,
        approval_request_id: str | None,
        idempotency_key: str,
        action_type: str,
        payload: dict[str, Any],
        action_payload_hash: str | None = None,
        safety_snapshot_ref: str | None = None,
        safety_snapshot_hash: str | None = None,
        thread_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        del user_id
        try:
            run_uuid = UUID(run_id)
            tenant_uuid = UUID(tenant_id)
            approval_uuid = UUID(approval_request_id) if approval_request_id else None
        except (AttributeError, TypeError, ValueError):
            return _tool_error("INVALID_REQUEST", "Action draft request is invalid", retryable=False)

        if not action_payload_hash or not safety_snapshot_ref or not safety_snapshot_hash:
            return _tool_error("ACTION_BINDING_REQUIRED", "Action draft requires exact safety binding", retryable=False)

        target_id = _target_id(payload)
        if target_id is None:
            return _tool_error("TARGET_ID_REQUIRED", "Action draft target_id is required", retryable=False)
        try:
            computed_payload_hash = compute_action_payload_hash(payload)
        except (CanonicalHashError, TypeError, ValueError):
            return _tool_error(
                "ACTION_BINDING_MISMATCH",
                "Action draft payload does not match approved safety binding",
                retryable=False,
            )
        if computed_payload_hash != action_payload_hash or str(payload.get("action_type") or "") != action_type:
            return _tool_error(
                "ACTION_BINDING_MISMATCH",
                "Action draft payload does not match approved safety binding",
                retryable=False,
            )

        try:
            async with self.session.begin_nested():
                binding = await self._validate_action_binding(
                    tenant_id=tenant_uuid,
                    run_id=run_uuid,
                    approval_request_id=approval_uuid,
                    action_payload_hash=action_payload_hash,
                    safety_snapshot_ref=safety_snapshot_ref,
                    safety_snapshot_hash=safety_snapshot_hash,
                )
                if isinstance(binding, dict):
                    return binding
                idempotency_key = _build_idempotency_key(
                    tenant_id=tenant_uuid,
                    run_id=run_uuid,
                    revision_marker=binding.revision_marker,
                    action_type=action_type,
                    target_id=target_id,
                    action_payload_hash=action_payload_hash,
                )
                draft, created = await self.draft_store.create_or_get(
                    run_id=run_uuid,
                    tenant_id=tenant_uuid,
                    approval_request_id=approval_uuid,
                    idempotency_key=idempotency_key,
                    action_type=action_type,
                    target_id=target_id,
                    approval_revision_ref=binding.approval_revision_ref,
                    action_payload_hash=action_payload_hash,
                    safety_snapshot_ref=safety_snapshot_ref,
                    safety_snapshot_hash=safety_snapshot_hash,
                    payload=payload,
                    draft_outcome=_draft_outcome(
                        tenant_id=tenant_uuid,
                        run_id=run_uuid,
                        draft_id=None,
                    ),
                    execution_mode="demo",
                    draft_version=1,
                    lifecycle_status="active",
                    retention_policy="phase14_demo_draft",
                )
                draft_outcome = _draft_outcome_from_draft(draft)
                draft.draft_outcome = draft_outcome
                if created:
                    await self._emit_action_draft_created(
                        run_id=run_uuid,
                        tenant_id=tenant_uuid,
                        thread_id=thread_id,
                        trace_id=trace_id,
                        draft_id=draft.id,
                        target_id=target_id,
                        action_type=action_type,
                        action_payload_hash=action_payload_hash,
                        safety_snapshot_hash=safety_snapshot_hash,
                        draft_outcome=draft_outcome,
                    )
            return _tool_success(
                {
                    "draft_id": str(draft.id),
                    "idempotency_key": draft.idempotency_key,
                    "status": draft.status,
                    "created": created,
                    "idempotent_reused": not created,
                    "action_draft": _action_draft_data(draft),
                    "draft_outcome": draft_outcome,
                    "execution_mode": draft.execution_mode,
                    "action_result": _compat_action_result(draft, draft_outcome),
                }
            )
        except ValueError as exc:
            if str(exc) in _IDEMPOTENCY_CONFLICTS:
                return _tool_error(
                    "IDEMPOTENCY_CONFLICT",
                    "Action draft idempotency binding conflicts with an existing draft",
                    retryable=False,
                )
            return _tool_error("INVALID_REQUEST", "Action draft request is invalid", retryable=False)
        except Exception:
            return _tool_error("DRAFT_CREATION_FAILED", "Action draft creation failed", retryable=True)

    async def _validate_action_binding(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        approval_request_id: UUID | None,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
    ) -> _ValidatedActionBinding | dict[str, Any]:
        snapshot = (
            await self.session.execute(
                select(ActionSafetySnapshot).where(
                    ActionSafetySnapshot.tenant_id == tenant_id,
                    ActionSafetySnapshot.run_id == run_id,
                    ActionSafetySnapshot.snapshot_ref == safety_snapshot_ref,
                    ActionSafetySnapshot.immutable_hash == safety_snapshot_hash,
                    ActionSafetySnapshot.action_payload_hash == action_payload_hash,
                    ActionSafetySnapshot.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            return _tool_error("ACTION_BINDING_MISMATCH", "Action safety snapshot binding is invalid", retryable=False)

        if approval_request_id is None:
            return _tool_error(
                "AUTO_ALLOWED_BINDING_REQUIRED",
                "No-approval action draft requires a durable auto-allowed binding",
                retryable=False,
            )

        approval = (
            await self.session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.id == approval_request_id,
                    ApprovalRequest.tenant_id == tenant_id,
                    ApprovalRequest.run_id == run_id,
                )
            )
        ).scalar_one_or_none()
        if approval is None:
            return _tool_error("APPROVAL_NOT_FOUND", "Approved request was not found", retryable=False)
        if (
            approval.legacy_non_executable
            or approval.schema_version != "approval_request.v2"
            or approval.status != "approved"
            or approval.action_payload_hash != action_payload_hash
            or approval.safety_snapshot_ref != safety_snapshot_ref
            or approval.safety_snapshot_hash != safety_snapshot_hash
        ):
            return _tool_error("APPROVAL_BINDING_MISMATCH", "Approved request binding is invalid", retryable=False)
        return _ValidatedActionBinding(
            revision_marker=f"approval_revision_{approval.revision}",
            approval_revision_ref=f"approval_request/{approval.id}@rev{approval.revision}",
        )

    async def _emit_action_draft_created(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        thread_id: str | None,
        trace_id: str | None,
        draft_id: UUID,
        target_id: str,
        action_type: str,
        action_payload_hash: str,
        safety_snapshot_hash: str,
        draft_outcome: dict[str, Any],
    ) -> None:
        await emit_event(
            self.session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id or await _run_thread_id(self.session, run_id) or str(run_id),
            trace_id=trace_id,
            event_type="action_draft_created",
            actor={"type": "agent", "id": "moca"},
            resource_refs={
                "draft_id": str(draft_id),
                "target_id": target_id,
                "action_payload_hash": action_payload_hash,
                "safety_snapshot_hash": safety_snapshot_hash,
            },
            redacted_payload={
                "action_type": action_type,
                "execution_mode": "demo",
                "external_side_effect": False,
                "draft_outcome": DraftOutcomeV1.model_validate(draft_outcome).model_dump(mode="json"),
            },
        )


def _target_id(payload: dict[str, Any]) -> str | None:
    raw_target = payload.get("target_id")
    if raw_target is None:
        return None
    target = str(raw_target).strip()
    return target or None


async def _run_thread_id(session: AsyncSession, run_id: UUID) -> str | None:
    return (await session.execute(select(AgentRun.thread_id).where(AgentRun.id == run_id))).scalar_one_or_none()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_idempotency_key(
    *,
    tenant_id: UUID,
    run_id: UUID,
    revision_marker: str,
    action_type: str,
    target_id: str,
    action_payload_hash: str,
) -> str:
    raw_key = f"{tenant_id}:{run_id}:{revision_marker}:{action_type}:{target_id}:{action_payload_hash}"
    if len(raw_key) <= 256:
        return raw_key
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"{tenant_id}:{run_id}:{revision_marker}:key_sha256:{digest}"


def _draft_outcome(*, tenant_id: UUID, run_id: UUID, draft_id: UUID | None) -> dict[str, Any]:
    return DraftOutcomeV1(
        tenant_id=str(tenant_id),
        run_id=str(run_id),
        draft_id=str(draft_id) if draft_id is not None else None,
        created_at=_now_iso(),
    ).model_dump(mode="json")


def _draft_outcome_from_draft(draft) -> dict[str, Any]:
    outcome = dict(draft.draft_outcome or {})
    if not outcome:
        outcome = _draft_outcome(tenant_id=draft.tenant_id, run_id=draft.run_id, draft_id=draft.id)
    else:
        outcome["draft_id"] = str(draft.id)
    return DraftOutcomeV1.model_validate(outcome).model_dump(mode="json")


def _action_draft_data(draft) -> dict[str, Any]:
    data = {
        "schema_version": draft.schema_version,
        "tenant_id": str(draft.tenant_id),
        "run_id": str(draft.run_id),
        "draft_id": str(draft.id),
        "proposed_action": draft.payload,
        "approval_revision_ref": draft.approval_revision_ref,
        "approval_ref": str(draft.approval_request_id) if draft.approval_request_id else None,
        "action_payload_hash": draft.action_payload_hash,
        "safety_snapshot_ref": draft.safety_snapshot_ref,
        "safety_snapshot_hash": draft.safety_snapshot_hash,
        "target_id": draft.target_id,
        "idempotency_key": draft.idempotency_key,
        "status": draft.status,
        "execution_mode": draft.execution_mode,
        "draft_version": draft.draft_version,
        "lifecycle_status": draft.lifecycle_status,
        "retention_policy": draft.retention_policy,
        "draft_outcome": _draft_outcome_from_draft(draft),
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }
    return ActionDraftV2Data.model_validate(data).model_dump(mode="json")


def _compat_action_result(draft, draft_outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "draft_created",
        "data": {
            "draft_id": str(draft.id),
            "draft_outcome": draft_outcome,
        },
        "error": {},
        "compatibility": _ACTION_RESULT_COMPAT_GATE,
    }


async def create_coupon_grant_draft(
    *,
    tenant_id: str,
    user_id: str,
    run_id: str,
    approval_request_id: str | None,
    idempotency_key: str,
    action_type: str,
    payload: dict[str, Any],
    session: AsyncSession,
    action_payload_hash: str | None = None,
    safety_snapshot_ref: str | None = None,
    safety_snapshot_hash: str | None = None,
    thread_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Compatibility function for old call sites."""

    return await ActionService(session).create_coupon_grant_draft(
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        approval_request_id=approval_request_id,
        idempotency_key=idempotency_key,
        action_type=action_type,
        payload=payload,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        thread_id=thread_id,
        trace_id=trace_id,
    )
