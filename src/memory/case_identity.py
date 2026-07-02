from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RefundCase
from src.repositories.refund_repo import RefundRepository


class CaseIdentityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["case_identity_result.v1"] = "case_identity_result.v1"
    status: Literal["resolved", "not_found", "invalid"]
    case_id: uuid.UUID | None
    input_form: Literal["refund_case_no", "uuid", "unknown"]


async def resolve_case_id(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    raw_case_ref: str | None,
) -> CaseIdentityResult:
    stripped = raw_case_ref.strip() if raw_case_ref is not None else ""
    if not stripped:
        return CaseIdentityResult(status="invalid", case_id=None, input_form="unknown")

    parsed_case_id = _parse_uuid(stripped)
    if parsed_case_id is not None:
        result = await session.execute(
            select(RefundCase).where(
                RefundCase.id == parsed_case_id,
                RefundCase.tenant_id == tenant_id,
            )
        )
        refund_case = result.scalar_one_or_none()
        if refund_case is not None:
            return CaseIdentityResult(status="resolved", case_id=refund_case.id, input_form="uuid")

    refund_case = await RefundRepository(session).get_by_case_no(stripped, tenant_id)
    if refund_case is not None:
        return CaseIdentityResult(status="resolved", case_id=refund_case.id, input_form="refund_case_no")

    return CaseIdentityResult(status="not_found", case_id=None, input_form="refund_case_no")


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
