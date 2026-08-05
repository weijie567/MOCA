from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import create_access_token
from src.db.models import AgentRun, CaseMemory, LongTermMemory, User
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.identity import canonical_memory_content_hash, canonical_source_identity_hash
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
        source_type="semantic_episode_candidate",
        source_ref={
            "source_type": "semantic_episode_candidate",
            "run_id": str(run_id),
            "business_object_id": str(merchant.id),
        },
    )


def _pending_long_term_row(
    seeded_session: dict,
    *,
    run_id: UUID,
    memory_kind: str,
    content: str,
    source_type: str = "semantic_episode_candidate",
) -> LongTermMemory:
    merchant = seeded_session["merchant"]
    source_ref = {
        "source_type": source_type,
        "run_id": str(run_id),
        "business_object_id": str(merchant.id),
    }
    return LongTermMemory(
        id=uuid4(),
        tenant_id=merchant.tenant_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind=memory_kind,
        content=content,
        content_hash=canonical_memory_content_hash(memory_type="long_term_fact", content=content),
        source_type=source_type,
        source_ref_json=source_ref,
        source_identity_hash=canonical_source_identity_hash(source_ref),
        confidence=Decimal("0.9100"),
        pii_classification="none",
        review_status="needs_review",
        is_current=False,
        created_by_run_id=run_id,
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
        source_type="closed_case_cwc_candidate",
        source_ref={
            "source_type": "closed_case_cwc_candidate",
            "run_id": str(run_id),
            "agent_run_id": str(run_id),
            "event_id": f"refund-case-close:{refund_case.id}:api-review",
            "business_object_type": "refund_case",
            "business_object_id": str(refund_case.id),
            "outcome_id": f"cwc:{refund_case.id}:v1",
        },
    )


@pytest.mark.asyncio
async def test_memory_review_api_lists_pending_and_applies_review_actions(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
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
        headers=_auth_header(admin, ["approvals:review"]),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 2
    assert {(item["memory_type"], item["memory_id"]) for item in payload["items"]} == {
        ("long_term", str(long_result.memory_id)),
        ("case", str(case_result.memory_id)),
    }
    case_pending = next(item for item in payload["items"] if item["memory_type"] == "case")
    assert case_pending["source_type"] == "closed_case_cwc_candidate"

    approve_response = await client.post(
        f"/api/v1/memory/long-term/{long_result.memory_id}/approve",
        json={"run_id": str(run_id)},
        headers=_auth_header(admin, ["approvals:review"]),
    )
    reject_response = await client.post(
        f"/api/v1/memory/case/{case_result.memory_id}/reject",
        json={
            "run_id": str(run_id),
            "expected_lifecycle_version": 1,
            "review_reason": "not durable enough",
        },
        headers=_auth_header(admin, ["approvals:review"]),
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
    assert long_row.source_type == "human_reviewed"
    assert long_row.source_ref_json["source_type"] == "human_reviewed"
    assert case_row.review_status == "rejected"
    assert case_row.reviewed_by_user_id == admin.id
    assert case_row.review_reason == "not durable enough"


@pytest.mark.asyncio
async def test_case_review_api_requires_version_and_returns_generic_stale_conflict(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=admin.id,
        thread_id="memory-review-api-cas",
    )
    written = await CaseMemoryService(CaseMemoryRepository(session)).submit_case_memory_candidate(
        _case_candidate(seeded_session, run_id=run_id)
    )
    await session.commit()
    url = f"/api/v1/memory/case/{written.memory_id}/approve"
    headers = _auth_header(admin, ["approvals:review"])

    missing = await client.post(url, json={"run_id": str(run_id)}, headers=headers)
    approved = await client.post(
        url,
        json={"run_id": str(run_id), "expected_lifecycle_version": 1},
        headers=headers,
    )
    stale = await client.post(
        f"/api/v1/memory/case/{written.memory_id}/reject",
        json={"run_id": str(run_id), "expected_lifecycle_version": 1},
        headers=headers,
    )

    assert missing.status_code == 422
    assert approved.status_code == 200
    assert approved.json()["data"]["lifecycle_version"] == 2
    assert stale.status_code == 409
    assert stale.json()["error"] == {
        "code": "CONFLICT",
        "message": "Memory state conflict",
        "details": {},
    }


@pytest.mark.asyncio
async def test_review_api_rejects_non_preference_long_term_approval_with_controlled_error(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=support.id,
        thread_id="review-api-non-preference-long-term",
    )
    row = _pending_long_term_row(
        seeded_session,
        run_id=run_id,
        memory_kind="fact",
        content="Pending long-term fact must not be approved.",
    )
    session.add(row)
    await session.commit()

    response = await client.post(
        f"/api/v1/memory/long-term/{row.id}/approve",
        json={"run_id": str(run_id)},
        headers=_auth_header(admin, ["approvals:review"]),
    )
    await session.refresh(row)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=row.tenant_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
    )

    assert response.status_code in {409, 422}
    assert response.json()["error"]["message"] == "long-term approval requires preference memory"
    assert row.review_status == "needs_review"
    assert row.is_current is False
    assert row.source_type == "semantic_episode_candidate"
    assert row.source_ref_json["source_type"] == "semantic_episode_candidate"
    assert retrieved == []


@pytest.mark.asyncio
async def test_memory_review_api_requires_admin_role(
    client: AsyncClient,
    seeded_session: dict,
) -> None:
    support = seeded_session["users"]["cs_zhang"]
    manager = seeded_session["users"]["approval_manager"]
    manager_other_merchant = seeded_session["users"]["manager_other_merchant"]

    for actor in (support, manager, manager_other_merchant):
        response = await client.get(
            "/api/v1/memory/review/pending",
            headers=_auth_header(actor, ["approvals:review"]),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_save_long_term_preference_directly(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    support = seeded_session["users"]["cs_zhang"]
    merchant = seeded_session["merchant"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=support.id,
        thread_id="admin-save-memory-preference",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json={
            "run_id": str(run_id),
            "scope_type": "merchant",
            "scope_id": str(merchant.id),
            "content": "Merchant prefers concise refund updates.",
        },
        headers=_auth_header(admin, ["memory:write"]),
    )
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["decision"] == "write"
    assert data["review_status"] == "auto_approved"
    assert data["source_type"] == "explicit_admin_preference"

    row = await session.get(LongTermMemory, UUID(data["memory_id"]))
    assert row is not None
    assert row.source_type == "explicit_admin_preference"
    assert row.memory_kind == "preference"
    assert row.scope_type == "merchant"
    assert row.scope_id == str(merchant.id)
    assert row.review_status == "auto_approved"
    assert row.is_current is True


@pytest.mark.asyncio
async def test_admin_can_save_tenant_scoped_long_term_preference_directly(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=admin.id,
        thread_id="admin-save-tenant-memory-preference",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json={
            "run_id": str(run_id),
            "scope_type": "tenant",
            "scope_id": str(seeded_session["tenant"].id),
            "content": "Tenant prefers concise refund update language.",
        },
        headers=_auth_header(admin, ["memory:write"]),
    )
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["decision"] == "write"
    row = await session.get(LongTermMemory, UUID(data["memory_id"]))
    assert row is not None
    assert row.scope_type == "tenant"
    assert row.scope_id == str(seeded_session["tenant"].id)
    assert row.source_type == "explicit_admin_preference"


@pytest.mark.asyncio
async def test_admin_preference_save_requires_admin_role_and_memory_write_scope(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    manager = seeded_session["users"]["approval_manager"]
    merchant = seeded_session["merchant"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=admin.id,
        thread_id="admin-save-memory-permission",
    )
    await session.commit()
    body = {
        "run_id": str(run_id),
        "scope_type": "merchant",
        "scope_id": str(merchant.id),
        "content": "Merchant prefers concise refund updates.",
    }

    manager_response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json=body,
        headers=_auth_header(manager, ["approvals:review", "memory:write"]),
    )
    admin_without_scope_response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json=body,
        headers=_auth_header(admin, ["approvals:review"]),
    )

    assert manager_response.status_code == 403
    assert manager_response.json()["error"]["code"] == "FORBIDDEN"
    assert admin_without_scope_response.status_code == 403
    assert admin_without_scope_response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_preference_save_rejects_hard_rule_text_without_insert(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    merchant = seeded_session["merchant"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=admin.id,
        thread_id="admin-save-hard-rule",
    )
    await session.commit()

    response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json={
            "run_id": str(run_id),
            "scope_type": "merchant",
            "scope_id": str(merchant.id),
            "content": "低于10元必须退款。",
        },
        headers=_auth_header(admin, ["memory:write"]),
    )
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == seeded_session["tenant"].id,
                    LongTermMemory.content == "低于10元必须退款。",
                )
            )
        )
        .scalars()
        .all()
    )

    assert response.status_code == 422
    assert rows == []


@pytest.mark.asyncio
async def test_admin_preference_save_skips_sensitive_pii_without_insert(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    admin = seeded_session["users"]["admin_user"]
    merchant = seeded_session["merchant"]
    run_id = await _insert_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=admin.id,
        thread_id="admin-save-sensitive-pii",
    )
    await session.commit()
    content = "Merchant prefers updates mentioning customer 手机号 13800138000."

    response = await client.post(
        "/api/v1/memory/long-term/preferences",
        json={
            "run_id": str(run_id),
            "scope_type": "merchant",
            "scope_id": str(merchant.id),
            "content": content,
        },
        headers=_auth_header(admin, ["memory:write"]),
    )
    data = response.json()["data"]
    rows = (
        (
            await session.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == seeded_session["tenant"].id,
                    LongTermMemory.content == content,
                )
            )
        )
        .scalars()
        .all()
    )

    assert response.status_code == 200
    assert data["decision"] == "skip"
    assert data["reason_code"] == "pii_blocked"
    assert data["memory_id"] is None
    assert rows == []
