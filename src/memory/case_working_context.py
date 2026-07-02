from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseWorkingContext, CaseWorkingContextRevision
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextWriteCandidate,
)


_CWC_CONTENT_COLUMN_MAP: dict[str, str] = {
    "customer_request": "customer_request",
    "issue_type": "issue_type",
    "claims": "claims_json",
    "verified_facts": "verified_facts_json",
    "missing_info": "missing_info_json",
    "evidence_refs": "evidence_refs_json",
    "actions_taken": "actions_taken_json",
    "policy_refs": "policy_refs_json",
    "agent_recommendations": "agent_recommendations_json",
    "pending_tasks": "pending_tasks_json",
    "commitments": "commitments_json",
    "next_action": "next_action_json",
}


class CaseWorkingContextWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "conflict"]
    case_working_context_id: uuid.UUID | None
    version: int | None


class CaseWorkingContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def read_active(
        self,
        *,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> CaseWorkingContext | None:
        result = await self.session.execute(
            select(CaseWorkingContext).where(
                CaseWorkingContext.tenant_id == tenant_id,
                CaseWorkingContext.case_id == case_id,
                CaseWorkingContext.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def write_working_context(
        self,
        candidate: CaseWorkingContextWriteCandidate,
    ) -> CaseWorkingContextWriteResult:
        await self._lock_case_scope(tenant_id=candidate.tenant_id, case_id=candidate.case_id)
        row = await self._read_active_for_update(tenant_id=candidate.tenant_id, case_id=candidate.case_id)
        source_ref_json = _source_ref_json(candidate)

        if row is None:
            row = CaseWorkingContext(
                id=uuid.uuid4(),
                tenant_id=candidate.tenant_id,
                case_id=candidate.case_id,
                authority_class="contextual_only",
                version=1,
                updated_by_run_id=candidate.updated_by_run_id,
                source_ref_json=source_ref_json,
                pii_classification=candidate.pii_classification,
            )
            _apply_content(row, candidate.content)
            self.session.add(row)
            await self.session.flush()
            return CaseWorkingContextWriteResult(
                status="written",
                case_working_context_id=row.id,
                version=row.version,
            )

        if candidate.expected_version is not None and candidate.expected_version != row.version:
            return CaseWorkingContextWriteResult(
                status="conflict",
                case_working_context_id=row.id,
                version=row.version,
            )

        revision = CaseWorkingContextRevision(
            id=uuid.uuid4(),
            tenant_id=row.tenant_id,
            case_working_context_id=row.id,
            case_id=row.case_id,
            version=row.version,
            snapshot_json=dehydrate_content(hydrate_content(row)),
            edit_source="run_auto" if row.updated_by_run_id is not None else "staff_manual",
            updated_by_run_id=row.updated_by_run_id,
            source_ref_json=dict(row.source_ref_json or {}),
        )
        self.session.add(revision)

        _apply_content(row, candidate.content)
        row.authority_class = "contextual_only"
        row.version = row.version + 1
        row.updated_by_run_id = candidate.updated_by_run_id
        row.source_ref_json = source_ref_json
        row.pii_classification = candidate.pii_classification
        await self.session.flush()

        return CaseWorkingContextWriteResult(
            status="written",
            case_working_context_id=row.id,
            version=row.version,
        )

    async def _read_active_for_update(
        self,
        *,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> CaseWorkingContext | None:
        result = await self.session.execute(
            select(CaseWorkingContext)
            .where(
                CaseWorkingContext.tenant_id == tenant_id,
                CaseWorkingContext.case_id == case_id,
                CaseWorkingContext.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _lock_case_scope(self, *, tenant_id: uuid.UUID, case_id: uuid.UUID) -> None:
        lock_key = _case_scope_lock_key(tenant_id=tenant_id, case_id=case_id)
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))


def dehydrate_content(content: CaseWorkingContextContentV1) -> dict[str, Any]:
    dumped = content.model_dump(mode="json")
    return {content_field: dumped[content_field] for content_field in _CWC_CONTENT_COLUMN_MAP}


def hydrate_content(row: CaseWorkingContext) -> CaseWorkingContextContentV1:
    payload = {
        content_field: getattr(row, column_name)
        for content_field, column_name in _CWC_CONTENT_COLUMN_MAP.items()
    }
    return CaseWorkingContextContentV1.model_validate(payload)


def _apply_content(row: CaseWorkingContext, content: CaseWorkingContextContentV1) -> None:
    dehydrated = dehydrate_content(content)
    for content_field, column_name in _CWC_CONTENT_COLUMN_MAP.items():
        setattr(row, column_name, dehydrated[content_field])


def _source_ref_json(candidate: CaseWorkingContextWriteCandidate) -> dict[str, Any]:
    return candidate.source_ref.model_dump(mode="json", exclude_none=True)


def _case_scope_lock_key(*, tenant_id: uuid.UUID, case_id: uuid.UUID) -> int:
    identity = f"case-working-context:{tenant_id}:{case_id}".encode("utf-8")
    unsigned = int.from_bytes(sha256(identity).digest()[:8], "big", signed=False)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned
