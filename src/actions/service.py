from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.drafts import ActionDraftStore
from src.db.models import ActionSafetySnapshot, ApprovalRequest

_IDEMPOTENCY_CONFLICT = "idempotency_key_conflict"


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

        try:
            async with self.session.begin_nested():
                binding_error = await self._validate_action_binding(
                    tenant_id=tenant_uuid,
                    run_id=run_uuid,
                    approval_request_id=approval_uuid,
                    action_payload_hash=action_payload_hash,
                    safety_snapshot_ref=safety_snapshot_ref,
                    safety_snapshot_hash=safety_snapshot_hash,
                )
                if binding_error is not None:
                    return binding_error
                draft, created = await self.draft_store.create_or_get(
                    run_id=run_uuid,
                    tenant_id=tenant_uuid,
                    approval_request_id=approval_uuid,
                    idempotency_key=idempotency_key,
                    action_type=action_type,
                    payload=payload,
                )
            return _tool_success(
                {
                    "draft_id": str(draft.id),
                    "idempotency_key": draft.idempotency_key,
                    "status": draft.status,
                    "created": created,
                    "idempotent_reused": not created,
                }
            )
        except ValueError as exc:
            if str(exc) == _IDEMPOTENCY_CONFLICT:
                return _tool_error(
                    "IDEMPOTENCY_CONFLICT",
                    "Action draft idempotency key conflicts with another tenant",
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
    ) -> dict[str, Any] | None:
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
            return None

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
        return None


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
    )
