"""Run lifecycle replay event finalizer."""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.replay.service import ReplayService


class RunLifecycleService:
    """Own run lifecycle replay events for normal and non-happy paths."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.replay_service = ReplayService(session)

    async def mark_running(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None = "pending",
        reason_code: str = "run_started",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="running",
            previous_status=previous_status,
            reason_code=reason_code,
            trace_id=trace_id,
        )

    async def mark_interrupted(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "approval_required",
        clarification_ref: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="interrupted",
            previous_status=previous_status,
            reason_code=reason_code,
            clarification_ref=clarification_ref,
            trace_id=trace_id,
        )

    async def mark_resumed(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None = "interrupted",
        reason_code: str = "approval_resumed",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="resumed",
            previous_status=previous_status,
            reason_code=reason_code,
            trace_id=trace_id,
        )

    async def mark_completed(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "normal_completed",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="completed",
            previous_status=previous_status,
            reason_code=reason_code,
            trace_id=trace_id,
        )

    async def mark_rejected(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "approval_rejected",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="rejected",
            previous_status=previous_status,
            reason_code=reason_code,
            trace_id=trace_id,
        )

    async def mark_expired(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "approval_expired",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="expired",
            previous_status=previous_status,
            reason_code=reason_code,
            trace_id=trace_id,
        )

    async def mark_error(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "run_error",
        error_code: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="error",
            previous_status=previous_status,
            reason_code=reason_code,
            error_code=error_code,
            trace_id=trace_id,
        )

    async def mark_cancelled(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        previous_status: str | None,
        reason_code: str = "run_cancelled",
        cancellation_source: str | None = "system",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._append_status_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            status="cancelled",
            previous_status=previous_status,
            reason_code=reason_code,
            cancellation_source=cancellation_source,
            trace_id=trace_id,
        )

    async def _append_status_event(
        self,
        *,
        run_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str,
        thread_id: str,
        status: str,
        previous_status: str | None,
        reason_code: str,
        trace_id: str | None = None,
        clarification_ref: str | None = None,
        error_code: str | None = None,
        cancellation_source: str | None = None,
    ) -> dict[str, Any]:
        run_uuid = _as_uuid(run_id)
        payload: dict[str, Any] = {
            "status": status,
            "previous_status": previous_status,
            "reason_code": reason_code,
        }
        if clarification_ref is not None:
            payload["clarification_ref"] = clarification_ref
        if error_code is not None:
            payload["error_code"] = error_code
        if cancellation_source is not None:
            payload["cancellation_source"] = cancellation_source

        return await self.replay_service.append_event(
            run_id=run_uuid,
            tenant_id=tenant_id,
            thread_id=thread_id,
            trace_id=trace_id,
            event_type="run_status_changed",
            actor={"type": "system", "id": "run_lifecycle_service"},
            resource_refs={"run_id": str(run_uuid)},
            redacted_payload=payload,
        )


def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
