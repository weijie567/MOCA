from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, MemoryWriteEvent, RefundCase
from src.memory.case_working_context import CaseWorkingContextRepository
from src.memory.case_working_context_schemas import (
    CaseWorkingContextWriteCandidate,
    normalize_case_working_context_content_sources,
    normalize_case_working_context_source_ref,
)
from src.memory.identity import build_case_working_context_candidate_identity
from src.memory.policy import (
    BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS,
    MEMORY_POLICY_AUTHORITY_CLASS,
    MEMORY_POLICY_VERSION,
)
from src.memory.write_isolation import run_memory_side_effect_in_isolated_session


CASE_WORKING_CONTEXT_MEMORY_TYPE = "case_working_context"


class CaseWorkingContextServiceWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "blocked", "conflict"]
    memory_id: uuid.UUID | None = None
    version: int | None = None
    decision: Literal["write", "write_blocked", "skip"]
    reason_code: str
    pii_classification: Literal["none", "low", "sensitive", "prohibited"]
    candidate_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event_id: uuid.UUID


class CaseWorkingContextService:
    async def write_case_working_context(
        self,
        parent_session: AsyncSession,
        candidate: CaseWorkingContextWriteCandidate,
        *,
        run_id: uuid.UUID,
    ) -> CaseWorkingContextServiceWriteResult:
        _validate_write_inputs(candidate=candidate, run_id=run_id)
        trusted_candidate = _trusted_write_candidate(candidate=candidate, run_id=run_id)

        async def operation(child_session: AsyncSession) -> CaseWorkingContextServiceWriteResult:
            await _assert_run_belongs_to_tenant(
                child_session,
                tenant_id=trusted_candidate.tenant_id,
                run_id=run_id,
            )
            await _assert_case_belongs_to_tenant(
                child_session,
                tenant_id=trusted_candidate.tenant_id,
                case_id=trusted_candidate.case_id,
            )
            identity = build_case_working_context_candidate_identity(trusted_candidate)
            source_ref_json = identity.normalized_source_ref.model_dump(mode="json", exclude_none=True)
            candidate_hash = identity.candidate_hash

            if trusted_candidate.pii_classification in BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS:
                event = await _emit_write_event(
                    child_session,
                    tenant_id=trusted_candidate.tenant_id,
                    run_id=run_id,
                    memory_id=None,
                    decision="write_blocked",
                    reason_code="pii_blocked",
                    pii_classification=trusted_candidate.pii_classification,
                    candidate_hash=candidate_hash,
                    source_ref_json=source_ref_json,
                    blocked_by=["pii_classification"],
                )
                return CaseWorkingContextServiceWriteResult(
                    status="blocked",
                    memory_id=None,
                    version=None,
                    decision="write_blocked",
                    reason_code="pii_blocked",
                    pii_classification=trusted_candidate.pii_classification,
                    candidate_hash=candidate_hash,
                    event_id=event.id,
                )

            repository_result = await CaseWorkingContextRepository(child_session).write_working_context(
                trusted_candidate
            )
            if repository_result.status == "conflict":
                event = await _emit_write_event(
                    child_session,
                    tenant_id=trusted_candidate.tenant_id,
                    run_id=run_id,
                    memory_id=None,
                    decision="skip",
                    reason_code="version_conflict",
                    pii_classification=trusted_candidate.pii_classification,
                    candidate_hash=candidate_hash,
                    source_ref_json=source_ref_json,
                )
                return CaseWorkingContextServiceWriteResult(
                    status="conflict",
                    memory_id=None,
                    version=repository_result.version,
                    decision="skip",
                    reason_code="version_conflict",
                    pii_classification=trusted_candidate.pii_classification,
                    candidate_hash=candidate_hash,
                    event_id=event.id,
                )

            event = await _emit_write_event(
                child_session,
                tenant_id=trusted_candidate.tenant_id,
                run_id=run_id,
                memory_id=repository_result.case_working_context_id,
                decision="write",
                reason_code="eligible",
                pii_classification=trusted_candidate.pii_classification,
                candidate_hash=candidate_hash,
                source_ref_json=source_ref_json,
            )
            return CaseWorkingContextServiceWriteResult(
                status="written",
                memory_id=repository_result.case_working_context_id,
                version=repository_result.version,
                decision="write",
                reason_code="eligible",
                pii_classification=trusted_candidate.pii_classification,
                candidate_hash=candidate_hash,
                event_id=event.id,
            )

        return await run_memory_side_effect_in_isolated_session(parent_session, operation)


def _validate_write_inputs(
    *,
    candidate: CaseWorkingContextWriteCandidate,
    run_id: uuid.UUID | None,
) -> None:
    if candidate.tenant_id is None:
        raise ValueError("candidate.tenant_id is required")
    if candidate.case_id is None:
        raise ValueError("candidate.case_id is required")
    if candidate.source_ref is None:
        raise ValueError("candidate.source_ref is required")
    if run_id is None:
        raise ValueError("run_id is required")
    if candidate.updated_by_run_id is not None and candidate.updated_by_run_id != run_id:
        raise ValueError("candidate.updated_by_run_id must match run_id")


def _trusted_write_candidate(
    *,
    candidate: CaseWorkingContextWriteCandidate,
    run_id: uuid.UUID,
) -> CaseWorkingContextWriteCandidate:
    return candidate.model_copy(
        update={
            "updated_by_run_id": run_id,
            "source_ref": normalize_case_working_context_source_ref(
                candidate.source_ref,
                run_id=run_id,
                case_id=candidate.case_id,
            ),
            "content": normalize_case_working_context_content_sources(
                candidate.content,
                run_id=run_id,
                case_id=candidate.case_id,
            ),
        }
    )


async def _assert_run_belongs_to_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(AgentRun.id).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == tenant_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("run_id does not belong to tenant")


async def _assert_case_belongs_to_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(RefundCase.id).where(
            RefundCase.id == case_id,
            RefundCase.tenant_id == tenant_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("case_id does not belong to tenant")


async def _emit_write_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    memory_id: uuid.UUID | None,
    decision: str,
    reason_code: str,
    pii_classification: str,
    candidate_hash: str,
    source_ref_json: dict,
    blocked_by: list[str] | None = None,
) -> MemoryWriteEvent:
    event = MemoryWriteEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        run_id=run_id,
        memory_type=CASE_WORKING_CONTEXT_MEMORY_TYPE,
        memory_id=memory_id,
        decision=decision,
        reason_code=reason_code,
        policy_version=MEMORY_POLICY_VERSION,
        blocked_by_json=list(blocked_by or []),
        authority_class=MEMORY_POLICY_AUTHORITY_CLASS,
        pii_classification=pii_classification,
        candidate_hash=candidate_hash,
        source_ref_json=dict(source_ref_json),
    )
    session.add(event)
    await session.flush()
    return event
