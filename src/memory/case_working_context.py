from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, CaseWorkingContext, CaseWorkingContextRevision, RefundCase
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextWriteCandidate,
    normalize_case_working_context_content_sources,
    normalize_case_working_context_source_ref,
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
        await self._assert_case_belongs_to_tenant(tenant_id=candidate.tenant_id, case_id=candidate.case_id)
        if candidate.updated_by_run_id is not None:
            await self._assert_run_belongs_to_tenant(
                tenant_id=candidate.tenant_id,
                run_id=candidate.updated_by_run_id,
            )
        await self._lock_case_scope(tenant_id=candidate.tenant_id, case_id=candidate.case_id)
        row = await self._read_active_for_update(tenant_id=candidate.tenant_id, case_id=candidate.case_id)
        source_ref_json = _source_ref_json(candidate)
        content = normalize_case_working_context_content_sources(
            candidate.content,
            run_id=candidate.updated_by_run_id,
            case_id=candidate.case_id,
        )
        await self._assert_source_ref_runs_belong_to_tenant(
            tenant_id=candidate.tenant_id,
            source_ref_json=source_ref_json,
            content=content,
        )

        if row is None:
            if candidate.expected_version is not None:
                return CaseWorkingContextWriteResult(
                    status="conflict",
                    case_working_context_id=None,
                    version=None,
                )
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
            _apply_content(row, content)
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
            edit_source=_revision_edit_source(row.source_ref_json),
            updated_by_run_id=row.updated_by_run_id,
            source_ref_json=dict(row.source_ref_json or {}),
        )
        self.session.add(revision)

        _apply_content(row, content)
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

    async def _assert_case_belongs_to_tenant(self, *, tenant_id: uuid.UUID, case_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(RefundCase.id).where(
                RefundCase.id == case_id,
                RefundCase.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("case_id does not belong to tenant")

    async def _assert_run_belongs_to_tenant(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(AgentRun.id).where(
                AgentRun.id == run_id,
                AgentRun.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("updated_by_run_id does not belong to tenant")

    async def _assert_source_ref_runs_belong_to_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        source_ref_json: dict[str, Any],
        content: CaseWorkingContextContentV1,
    ) -> None:
        run_ids: set[uuid.UUID] = set()
        for source_ref in _iter_cwc_source_refs(source_ref_json=source_ref_json, content=content):
            run_ids.update(_source_ref_run_ids(source_ref))

        if not run_ids:
            return

        result = await self.session.execute(
            select(AgentRun.id).where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.id.in_(run_ids),
            )
        )
        tenant_run_ids = set(result.scalars().all())
        if tenant_run_ids != run_ids:
            raise ValueError("source_ref run_id/agent_run_id does not belong to tenant")


def dehydrate_content(content: CaseWorkingContextContentV1) -> dict[str, Any]:
    dumped = content.model_dump(mode="json")
    return {content_field: dumped[content_field] for content_field in _CWC_CONTENT_COLUMN_MAP}


def hydrate_content(row: CaseWorkingContext) -> CaseWorkingContextContentV1:
    payload = {
        content_field: getattr(row, column_name) for content_field, column_name in _CWC_CONTENT_COLUMN_MAP.items()
    }
    return CaseWorkingContextContentV1.model_validate(payload)


def _apply_content(row: CaseWorkingContext, content: CaseWorkingContextContentV1) -> None:
    dehydrated = dehydrate_content(content)
    for content_field, column_name in _CWC_CONTENT_COLUMN_MAP.items():
        setattr(row, column_name, dehydrated[content_field])


def _source_ref_json(candidate: CaseWorkingContextWriteCandidate) -> dict[str, Any]:
    return normalize_case_working_context_source_ref(
        candidate.source_ref,
        run_id=candidate.updated_by_run_id,
        case_id=candidate.case_id,
    ).model_dump(mode="json", exclude_none=True)


def _revision_edit_source(source_ref_json: dict[str, Any] | None) -> Literal["run_auto", "staff_manual"]:
    if (source_ref_json or {}).get("source_type") == "staff_manual":
        return "staff_manual"
    return "run_auto"


def _iter_cwc_source_refs(
    *,
    source_ref_json: dict[str, Any],
    content: CaseWorkingContextContentV1,
) -> list[dict[str, Any]]:
    source_refs = [source_ref_json]
    dehydrated = dehydrate_content(content)
    for content_field in ("claims", "verified_facts", "actions_taken", "commitments"):
        for item in dehydrated[content_field]:
            nested_source_ref = item.get("source_ref")
            if isinstance(nested_source_ref, dict):
                source_refs.append(nested_source_ref)
    return source_refs


def _source_ref_run_ids(source_ref_json: dict[str, Any]) -> set[uuid.UUID]:
    run_ids: set[uuid.UUID] = set()
    for field_name in ("run_id", "agent_run_id"):
        value = source_ref_json.get(field_name)
        if value is None:
            continue
        try:
            run_ids.add(uuid.UUID(str(value)))
        except ValueError as exc:
            raise ValueError(f"{field_name} in source_ref must be a UUID") from exc
    return run_ids


def _case_scope_lock_key(*, tenant_id: uuid.UUID, case_id: uuid.UUID) -> int:
    identity = f"case-working-context:{tenant_id}:{case_id}".encode("utf-8")
    unsigned = int.from_bytes(sha256(identity).digest()[:8], "big", signed=False)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned
