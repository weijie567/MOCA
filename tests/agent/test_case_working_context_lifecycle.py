from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
import uuid

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import AgentRun, Base, CaseWorkingContext, Merchant, Order, RefundCase, Tenant, ThreadCaseLink, User
from src.memory.case_identity import CaseIdentityResult
from src.memory.case_working_context_lifecycle import (
    CaseWorkingContextLifecycleAdapter,
    build_active_cwc_payload,
    skipped_status,
    trusted_case_ref_from_state,
)
from tests.conftest import TEST_DATABASE_URL, _ensure_test_database


@pytest.fixture
async def phase45_session_factory():
    try:
        await _ensure_test_database(TEST_DATABASE_URL)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Phase 45 PostgreSQL unavailable: {exc}")

    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _seed_lifecycle_scope(session: AsyncSession) -> dict[str, object]:
    tenant = Tenant(id=uuid.uuid4(), name=f"phase45-cwc-tenant-{uuid.uuid4()}", status="active")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        username=f"phase45-cwc-user-{uuid.uuid4()}",
        password_hash="hash",
        role="admin",
        is_active=True,
    )
    merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_name="Phase 45 CWC Shop",
        category="electronics",
        risk_level="low",
    )
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_id=merchant.id,
        order_no=f"ORD-PHASE45-CWC-{uuid.uuid4()}",
        buyer_name="测试用户",
        item_name="蓝牙耳机",
        amount=Decimal("199.00"),
        currency="CNY",
        status="delivered",
    )
    refund_case = RefundCase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        refund_case_no=f"RF-PHASE45-CWC-{uuid.uuid4()}",
        reason_code="damaged",
        reason_text="收到商品破损",
        status="reviewing",
        requested_amount=Decimal("199.00"),
    )
    run = AgentRun(
        id=uuid.uuid4(),
        thread_id=f"phase45-cwc-thread-{uuid.uuid4()}",
        tenant_id=tenant.id,
        user_id=user.id,
        input_query="测试 CWC 生命周期",
        final_status="completed",
        scope_classification="unknown_legacy",
        started_at=datetime.now(UTC),
    )
    session.add_all([tenant, user, merchant, order, refund_case, run])
    await session.flush()
    return {"tenant": tenant, "user": user, "refund_case": refund_case, "run": run}


def _source_ref(scope: dict[str, object]) -> dict[str, str]:
    return {
        "source_type": "run_auto",
        "agent_run_id": str(scope["run"].id),
        "business_object_type": "refund_case",
        "business_object_id": str(scope["refund_case"].id),
    }


async def _insert_active_cwc(session: AsyncSession, scope: dict[str, object]) -> CaseWorkingContext:
    row = CaseWorkingContext(
        id=uuid.uuid4(),
        tenant_id=scope["tenant"].id,
        case_id=scope["refund_case"].id,
        customer_request="用户询问退款进度",
        issue_type="refund_status",
        claims_json=[],
        verified_facts_json=[],
        missing_info_json=[],
        evidence_refs_json=[],
        actions_taken_json=[],
        policy_refs_json=[],
        agent_recommendations_json=[],
        pending_tasks_json=[],
        commitments_json=[],
        next_action_json={},
        source_ref_json=_source_ref(scope),
        version=1,
        updated_by_run_id=scope["run"].id,
        pii_classification="none",
    )
    session.add(row)
    await session.flush()
    return row


def test_trusted_case_ref_from_state_uses_active_slots_first() -> None:
    state = {
        "active_slots": {"refund_case_id": "RF-1"},
        "extracted_slots": {"refund_case_id": "RF-2"},
    }

    assert trusted_case_ref_from_state(state) == "RF-1"
    assert CaseWorkingContextLifecycleAdapter().trusted_case_ref_from_state(state) == "RF-1"


def test_trusted_case_ref_from_state_ignores_untrusted_memory_and_candidate_slots() -> None:
    state = {
        "candidate_slots": {"refund_case_id": "RF-CANDIDATE"},
        "session_memory": {"active_slots": {"refund_case_id": "RF-SESSION"}},
        "case_memory": [{"refund_case_id": "RF-CASE-MEMORY"}],
        "memory_context": {"case_items": [{"refund_case_id": "RF-MEMORY-CONTEXT"}]},
    }

    assert trusted_case_ref_from_state(state) is None


def test_trusted_case_ref_from_state_uses_extracted_slots_before_business_context() -> None:
    state = {
        "active_slots": {},
        "extracted_slots": {"refund_case_id": "RF-EXTRACTED"},
        "business_context": {"refund_case": {"refund_case_no": "RF-BUSINESS"}},
    }

    assert trusted_case_ref_from_state(state, include_business_context=True) == "RF-EXTRACTED"


def test_trusted_case_ref_from_state_accepts_business_context_only_when_enabled_in_order() -> None:
    state = {
        "business_context": {
            "refund_case": {
                "refund_case_no": "RF-NO",
                "refund_case_id": "RF-ID",
                "id": "RF-UUID",
            }
        }
    }

    assert trusted_case_ref_from_state(state) is None
    assert trusted_case_ref_from_state(state, include_business_context=True) == "RF-NO"

    no_case_no = {"business_context": {"refund_case": {"refund_case_id": "RF-ID", "id": "RF-UUID"}}}
    assert trusted_case_ref_from_state(no_case_no, include_business_context=True) == "RF-ID"

    only_id = {"business_context": {"refund_case": {"id": "RF-UUID"}}}
    assert trusted_case_ref_from_state(only_id, include_business_context=True) == "RF-UUID"


def test_build_active_cwc_payload_projects_hydrated_content_and_contextual_ref() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    memory_id = uuid.uuid4()
    run_id = uuid.uuid4()
    source_ref = {
        "source_type": "run_auto",
        "agent_run_id": str(run_id),
        "business_object_type": "refund_case",
        "business_object_id": str(case_id),
    }
    row = SimpleNamespace(
        id=memory_id,
        tenant_id=tenant_id,
        case_id=case_id,
        customer_request="用户询问退款进度",
        issue_type="refund_status",
        claims_json=[
            {
                "text": "用户称商品破损",
                "verified": False,
                "source_ref": source_ref,
            }
        ],
        verified_facts_json=[
            {
                "text": "退款单状态为 reviewing",
                "source_ref": source_ref,
                "observed_at": datetime(2026, 7, 3, 8, 0, tzinfo=UTC),
            }
        ],
        missing_info_json=["需要补充破损照片"],
        evidence_refs_json=[
            {"ref_type": "tool_result", "ref_id": "tool-result-1", "summary": "退款单状态为 reviewing"}
        ],
        actions_taken_json=[{"action": "查询退款单状态", "source_ref": source_ref}],
        policy_refs_json=[{"doc_id": "refund-policy", "chunk_id": "refund-policy#001", "version": "v1"}],
        agent_recommendations_json=[{"recommended_step": "要求用户上传照片", "staff_decision": None}],
        pending_tasks_json=["等待用户上传照片"],
        commitments_json=[{"text": "24 小时内回复用户", "confirmed_by_staff": True, "source_ref": source_ref}],
        next_action_json={"recommended_step": "发送照片补充说明", "blocked_by": ["missing_damage_photo"]},
        version=2,
        updated_by_run_id=run_id,
        source_ref_json=source_ref,
    )

    payload = build_active_cwc_payload(row)

    assert payload["content"]["authority_class"] == "contextual_only"
    assert payload["content"]["customer_request"] == "用户询问退款进度"
    assert payload["content"]["claims"][0]["text"] == "用户称商品破损"
    assert payload["ref"] == {
        "schema_version": "case_working_context_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": str(tenant_id),
        "case_id": str(case_id),
        "memory_id": str(memory_id),
        "version": 2,
        "source_ref": source_ref,
        "updated_by_run_id": str(run_id),
        "prompt_safe": True,
    }


def test_skipped_status_returns_contextual_status_without_implicit_read_or_write_flags() -> None:
    status = skipped_status(reason_code="skipped_no_case")

    assert status.schema_version == "case_working_context_lifecycle_status.v1"
    assert status.authority_class == "contextual_only"
    assert status.status == "skipped"
    assert status.reason_code == "skipped_no_case"
    assert status.read_status is None
    assert status.write_status is None


@pytest.mark.asyncio
async def test_link_and_load_active_links_run_auto_before_active_read(phase45_session_factory) -> None:
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)

            result = await CaseWorkingContextLifecycleAdapter().link_and_load_active(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                state={"active_slots": {"refund_case_id": scope["refund_case"].refund_case_no}},
            )
            link = (
                await session.execute(
                    select(ThreadCaseLink).where(
                        ThreadCaseLink.tenant_id == scope["tenant"].id,
                        ThreadCaseLink.case_id == scope["refund_case"].id,
                    )
                )
            ).scalar_one()

    assert result.case_id == scope["refund_case"].id
    assert result.case_working_context is None
    assert result.status_ref.resolve_status == "resolved"
    assert result.status_ref.link_status == "linked"
    assert result.status_ref.read_status == "missing"
    assert link.link_source == "run_auto"
    assert link.linked_by_run_id == scope["run"].id


@pytest.mark.asyncio
async def test_link_and_load_active_duplicate_link_reports_deduped_status(phase45_session_factory) -> None:
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            adapter = CaseWorkingContextLifecycleAdapter()
            call_args = {
                "session": session,
                "tenant_id": scope["tenant"].id,
                "user_id": scope["user"].id,
                "thread_id": scope["run"].thread_id,
                "run_id": scope["run"].id,
                "state": {"active_slots": {"refund_case_id": str(scope["refund_case"].id)}},
            }

            first = await adapter.link_and_load_active(**call_args)
            second = await adapter.link_and_load_active(**call_args)
            active_count = await session.scalar(
                select(func.count())
                .select_from(ThreadCaseLink)
                .where(
                    ThreadCaseLink.tenant_id == scope["tenant"].id,
                    ThreadCaseLink.case_id == scope["refund_case"].id,
                    ThreadCaseLink.deleted_at.is_(None),
                )
            )

    assert first.status_ref.link_status == "linked"
    assert second.status_ref.link_status == "deduped"
    assert active_count == 1


@pytest.mark.asyncio
async def test_link_and_load_active_skips_without_trusted_case_ref() -> None:
    class FailReadRepository:
        def __init__(self, session: AsyncSession) -> None:
            self.session = session

        async def read_active(self, **_: object) -> None:
            raise AssertionError("read_active must not be called without a trusted case ref")

    adapter = CaseWorkingContextLifecycleAdapter(repository_cls=FailReadRepository)
    result = await adapter.link_and_load_active(
        session=object(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        thread_id="thread-no-case",
        run_id=uuid.uuid4(),
        state={"candidate_slots": {"refund_case_id": "RF-CANDIDATE"}},
    )

    assert result.case_id is None
    assert result.case_working_context is None
    assert result.status_ref.status == "skipped"
    assert result.status_ref.reason_code == "skipped_no_case"
    assert result.status_ref.read_status is None
    assert result.status_ref.link_status is None


@pytest.mark.asyncio
async def test_link_and_load_active_skips_unresolved_case_without_link_or_read() -> None:
    class FailReadRepository:
        def __init__(self, session: AsyncSession) -> None:
            self.session = session

        async def read_active(self, **_: object) -> None:
            raise AssertionError("read_active must not be called for unresolved case refs")

    async def not_found_resolver(*_: object, **__: object) -> CaseIdentityResult:
        return CaseIdentityResult(status="not_found", case_id=None, input_form="refund_case_no")

    adapter = CaseWorkingContextLifecycleAdapter(
        case_resolver=not_found_resolver,
        repository_cls=FailReadRepository,
    )
    result = await adapter.link_and_load_active(
        session=object(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        thread_id="thread-unresolved-case",
        run_id=uuid.uuid4(),
        state={"active_slots": {"refund_case_id": "RF-MISSING"}},
    )

    assert result.case_id is None
    assert result.case_working_context is None
    assert result.status_ref.status == "skipped"
    assert result.status_ref.reason_code == "skipped_unresolved_case"
    assert result.status_ref.resolve_status == "not_found"
    assert result.status_ref.read_status is None
    assert result.status_ref.link_status is None


@pytest.mark.asyncio
async def test_link_and_load_active_link_failure_uses_savepoint_and_leaves_parent_session_usable(
    phase45_session_factory,
) -> None:
    async def cross_tenant_resolver(*_: object, **__: object) -> CaseIdentityResult:
        return CaseIdentityResult(status="resolved", case_id=other_scope["refund_case"].id, input_form="uuid")

    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            other_scope = await _seed_lifecycle_scope(session)

            result = await CaseWorkingContextLifecycleAdapter(case_resolver=cross_tenant_resolver).link_and_load_active(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                state={"active_slots": {"refund_case_id": str(other_scope["refund_case"].id)}},
            )
            tenant_count = await session.scalar(select(func.count()).select_from(Tenant))
            cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))

    assert result.case_id == other_scope["refund_case"].id
    assert result.case_working_context is None
    assert result.status_ref.status == "error"
    assert result.status_ref.reason_code == "link_failed"
    assert result.status_ref.link_status == "error"
    assert result.status_ref.read_status == "skipped_link_failed"
    assert tenant_count == 2
    assert cwc_count == 0


@pytest.mark.asyncio
async def test_link_and_load_active_returns_active_context_payload(phase45_session_factory) -> None:
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            row = await _insert_active_cwc(session, scope)

            result = await CaseWorkingContextLifecycleAdapter().link_and_load_active(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                state={"active_slots": {"refund_case_id": scope["refund_case"].refund_case_no}},
            )

    assert result.case_id == scope["refund_case"].id
    assert result.case_working_context is not None
    assert result.case_working_context["content"]["customer_request"] == "用户询问退款进度"
    assert result.case_working_context["ref"]["memory_id"] == str(row.id)
    assert result.status_ref.read_status == "loaded"
