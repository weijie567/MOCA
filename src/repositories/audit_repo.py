from __future__ import annotations

from typing import Any
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

    async def record_conversation_reference(
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
        tool_call_id: str | None = None,
        error_code: str | None = None,
        idempotency_key: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> str:
        metadata = {
            "schema_version": "conversation_reference_audit.v1",
            "action": action,
            "resource_type": resource_type,
            **(metadata_json or {}),
        }
        _guard_safe_metadata(metadata)
        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=user.id,
            role=user.role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            tool_call_id=tool_call_id or str(uuid.uuid4()),
            run_id=run_id,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
            idempotency_key=idempotency_key,
            metadata_json=metadata,
        )
        self.session.add(audit_log)
        await self.session.flush()
        return f"audit/conversation/{audit_log.id}"


def _guard_safe_metadata(metadata: Any) -> None:
    forbidden = {
        "raw",
        "raw_prompt",
        "raw_args",
        "raw_payload",
        "raw_tool_output",
        "data",
        "prompt",
        "private_reasoning",
        "chain_of_thought",
        "approval_authority_body",
        "action_authority_body",
    }

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in forbidden:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(metadata, "audit_metadata")
