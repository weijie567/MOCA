from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuditLog, User


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_tool_call(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None,
        trace_id: str,
        run_id: str,
        latency_ms: int,
        status: str,
        tenant_id: uuid.UUID,
        user: User,
        error_code: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        tool_call_id = str(uuid.uuid4())
        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=user.id,
            role=user.role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            tool_call_id=tool_call_id,
            run_id=run_id,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
            idempotency_key=idempotency_key,
            metadata_json={"action": action},
        )
        self.session.add(audit_log)
        await self.session.commit()
        return tool_call_id
