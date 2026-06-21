from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import create_access_token
from src.db.models import AgentRun, CaseMemory, LongTermMemory, User
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import CaseMemoryWriteCandidate, LongTermMemoryWriteCandidate


def _auth_header(user: User, scopes: list[str]) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "scopes": scopes,
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def _insert_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID, thread_id: str) -> UUID:
    run_id = uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            input_query="memory review api",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _long_term_candidate(seeded_session: dict, *, run_id: UUID) -> LongTermMemoryWriteCandidate:
    merchant = seeded_session["merchant"]
    return LongTermMemoryWriteCandidate(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind="preference",
        content="Model candidate awaiting memory review.",
        source_type="llm_candidate",
        source_ref={"source_type": "llm_candidate", "run_id": str(run_id), "business_object_id": str(merchant.id)},
    )


def _case_candidate(seeded_session: dict, *, run_id: UUID) -> CaseMemoryWriteCandidate:
    refund_case = seeded_session["refund_case"]
    return CaseMemoryWriteCandidate(
        tenant_id=refund_case.tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(refund_case.id),
        case_type="refund_dispute",
        summary="Case candidate awaiting memory review.",
        excerpt="A reviewed case can guide similar refund dispute handling.",
        applicability="Applies to refund disputes with comparable evidence.",
        outcome="Support resolved the refund dispute.",
        caveats="Precedent only; not execution authority.",
        source_type="summary_candidate",
        source_ref={
            "source_type": "summary_candidate",
            "run_id": str(run_id),
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
        },
    )


@pytest.mark.asyncio
async def test_memory_review_api_lists_pending_and_applies_review_actions(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    manager = seeded_session["users"]["approval_manager"]
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=support.id,
        thread_id="memory-review-api",
    )
    long_result = await LongTermMemoryService(LongTermMemoryRepository(session)).write_memory(
        _long_term_candidate(seeded_session, run_id=run_id)
    )
    case_result = await CaseMemoryService(CaseMemoryRepository(session)).submit_case_memory_candidate(
        _case_candidate(seeded_session, run_id=run_id)
    )
    await session.commit()

    response = await client.get(
        "/api/v1/memory/review/pending",
        headers=_auth_header(manager, ["approvals:review"]),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 2
    assert {(item["memory_type"], item["memory_id"]) for item in payload["items"]} == {
        ("long_term", str(long_result.memory_id)),
        ("case", str(case_result.memory_id)),
    }

    approve_response = await client.post(
        f"/api/v1/memory/long-term/{long_result.memory_id}/approve",
        json={"run_id": str(run_id)},
        headers=_auth_header(manager, ["approvals:review"]),
    )
    reject_response = await client.post(
        f"/api/v1/memory/case/{case_result.memory_id}/reject",
        json={"run_id": str(run_id), "review_reason": "not durable enough"},
        headers=_auth_header(manager, ["approvals:review"]),
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["decision"] == "write"
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["decision"] == "skip"

    long_row = await session.get(LongTermMemory, long_result.memory_id)
    case_row = await session.get(CaseMemory, case_result.memory_id)
    assert long_row is not None
    assert case_row is not None
    await session.refresh(long_row)
    await session.refresh(case_row)
    assert long_row.review_status == "approved"
    assert long_row.is_current is True
    assert case_row.review_status == "rejected"
    assert case_row.reviewed_by_user_id == manager.id
    assert case_row.review_reason == "not durable enough"


@pytest.mark.asyncio
async def test_memory_review_api_requires_manager_or_admin_role(
    client: AsyncClient,
    seeded_session: dict,
) -> None:
    support = seeded_session["users"]["cs_zhang"]

    response = await client.get(
        "/api/v1/memory/review/pending",
        headers=_auth_header(support, ["approvals:review"]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
