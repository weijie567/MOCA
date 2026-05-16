from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.action_draft_repo import ActionDraftRepository


def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool) -> dict:
    return {"status": "error", "data": {}, "error": {"error_code": error_code, "message": message, "retryable": retryable}}


async def create_coupon_grant_draft(
    *,
    tenant_id: str,
    user_id: str,
    run_id: str,
    approval_request_id: str | None,
    idempotency_key: str,
    action_type: str,
    payload: dict,
    session: AsyncSession,
) -> dict:
    try:
        repo = ActionDraftRepository(session)
        draft, created = await repo.create_or_get(
            run_id=UUID(run_id),
            tenant_id=UUID(tenant_id),
            approval_request_id=UUID(approval_request_id) if approval_request_id else None,
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
    except Exception as exc:
        return _tool_error("DRAFT_CREATION_FAILED", str(exc), retryable=True)
