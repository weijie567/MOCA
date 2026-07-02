from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import src.memory.case_working_context_service as service_module
from src.db.models import (
    AgentRun,
    Base,
    CaseWorkingContext,
    CaseWorkingContextRevision,
    MemoryWriteEvent,
    Merchant,
    Order,
    RefundCase,
    Tenant,
)
from src.memory.case_working_context import CaseWorkingContextRepository, dehydrate_content, hydrate_content
from src.memory.case_working_context_schemas import (
    CaseWorkingContextActionTakenV1,
    CaseWorkingContextClaimV1,
    CaseWorkingContextCommitmentV1,
    CaseWorkingContextContentV1,
    CaseWorkingContextEvidencePointerV1,
    CaseWorkingContextNextActionV1,
    CaseWorkingContextPolicyRefV1,
    CaseWorkingContextRecommendationV1,
    CaseWorkingContextVerifiedFactV1,
    CaseWorkingContextWriteCandidate,
    normalize_case_working_context_content_sources,
)
from src.memory.schemas import MemorySourceRefV1
from tests.conftest import TEST_DATABASE_URL, _ensure_test_database


@pytest.fixture
async def phase44_session_factory():
    try:
        await _ensure_test_database(TEST_DATABASE_URL)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Phase 44 PostgreSQL unavailable: {exc}")

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


def _source_ref(**overrides: str) -> MemorySourceRefV1:
    payload = {
        "source_type": "deterministic_tool_result",
        "run_id": str(uuid.uuid4()),
        "agent_run_id": str(uuid.uuid4()),
        "business_object_type": "refund_case",
        "business_object_id": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return MemorySourceRefV1.model_validate(payload)


async def _seed_case_scope(session: AsyncSession) -> dict:
    tenant = Tenant(id=uuid.uuid4(), name=f"phase44-cwc-service-tenant-{uuid.uuid4()}", status="active")
    merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_name="Phase 44 CWC Shop",
        category="electronics",
        risk_level="low",
    )
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_id=merchant.id,
        order_no=f"ORD-PHASE44-CWC-{uuid.uuid4()}",
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
        refund_case_no=f"RF-PHASE44-CWC-{uuid.uuid4()}",
        reason_code="damaged",
        reason_text="收到商品破损",
        status="reviewing",
        requested_amount=Decimal("199.00"),
    )
    run = AgentRun(
        id=uuid.uuid4(),
        thread_id=f"phase44-cwc-thread-{uuid.uuid4()}",
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        input_query="测试案件工作上下文写入",
        final_status="completed",
        scope_classification="unknown_legacy",
        started_at=datetime.now(UTC),
    )
    session.add_all([tenant, merchant, order, refund_case, run])
    await session.flush()
    return {"tenant": tenant, "merchant": merchant, "order": order, "refund_case": refund_case, "run": run}


def _content(source_ref: MemorySourceRefV1, *, customer_request: str = "用户询问退款进度") -> CaseWorkingContextContentV1:
    return CaseWorkingContextContentV1(
        customer_request=customer_request,
        issue_type="refund_status",
        claims=[CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref)],
        verified_facts=[
            CaseWorkingContextVerifiedFactV1(
                text="退款单状态为 reviewing",
                source_ref=source_ref,
                observed_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
            )
        ],
        missing_info=["需要补充破损照片"],
        evidence_refs=[CaseWorkingContextEvidencePointerV1(ref_type="tool_result", ref_id="tool-result-1")],
        actions_taken=[CaseWorkingContextActionTakenV1(action="查询退款单状态", source_ref=source_ref)],
        policy_refs=[CaseWorkingContextPolicyRefV1(doc_id="refund-policy", chunk_id="refund-policy#001", version="v1")],
        agent_recommendations=[
            CaseWorkingContextRecommendationV1(recommended_step="转人工复核高金额退款", staff_decision=None)
        ],
        pending_tasks=["等待用户上传照片"],
        commitments=[
            CaseWorkingContextCommitmentV1(text="24 小时内回复用户", confirmed_by_staff=False, source_ref=source_ref)
        ],
        next_action=CaseWorkingContextNextActionV1(
            recommended_step="发送照片补充说明",
            blocked_by=["missing_damage_photo"],
        ),
    )


def _candidate(
    scope: dict,
    *,
    content: CaseWorkingContextContentV1,
    source_ref: MemorySourceRefV1,
    expected_version: int | None = None,
    updated_by_run_id: uuid.UUID | None = None,
    pii_classification: str = "none",
) -> CaseWorkingContextWriteCandidate:
    return CaseWorkingContextWriteCandidate(
        tenant_id=scope["tenant"].id,
        case_id=scope["refund_case"].id,
        updated_by_run_id=updated_by_run_id,
        source_ref=source_ref,
        expected_version=expected_version,
        content=content,
        pii_classification=pii_classification,  # type: ignore[arg-type]
    )


async def _events(session: AsyncSession, run_id: uuid.UUID) -> list[MemoryWriteEvent]:
    result = await session.execute(
        select(MemoryWriteEvent).where(MemoryWriteEvent.run_id == run_id).order_by(MemoryWriteEvent.created_at)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_service_rejects_missing_scope_source_ref_and_run_id_before_db_write(
    phase44_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_if_isolation_opens(*args, **kwargs):  # pragma: no cover - proves validation order
        pytest.fail("isolated write opened before validation")

    monkeypatch.setattr(service_module, "run_memory_side_effect_in_isolated_session", fail_if_isolation_opens)
    async with phase44_session_factory() as session:
        scope = {
            "tenant": type("TenantScope", (), {"id": uuid.uuid4()})(),
            "refund_case": type("CaseScope", (), {"id": uuid.uuid4()})(),
        }
        source_ref = _source_ref()
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref)
        service = service_module.CaseWorkingContextService()

        for invalid_candidate, run_id in (
            (candidate.model_copy(update={"tenant_id": None}), uuid.uuid4()),
            (candidate.model_copy(update={"case_id": None}), uuid.uuid4()),
            (candidate.model_copy(update={"source_ref": None}), uuid.uuid4()),
            (candidate.model_copy(update={"updated_by_run_id": uuid.uuid4()}), uuid.uuid4()),
            (candidate, None),
        ):
            with pytest.raises(ValueError):
                await service.write_case_working_context(
                    session,
                    invalid_candidate,  # type: ignore[arg-type]
                    run_id=run_id,  # type: ignore[arg-type]
                )

        event_count = await session.scalar(select(func.count()).select_from(MemoryWriteEvent))
        cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))

    assert event_count == 0
    assert cwc_count == 0


@pytest.mark.asyncio
async def test_service_rejects_cross_tenant_case_without_event_or_row(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            other_scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(other_scope["refund_case"].id))
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref).model_copy(
            update={"case_id": other_scope["refund_case"].id}
        )

        with pytest.raises(ValueError, match="case_id does not belong to tenant"):
            await service_module.CaseWorkingContextService().write_case_working_context(
                session,
                candidate,
                run_id=scope["run"].id,
            )
        event_count = await session.scalar(select(func.count()).select_from(MemoryWriteEvent))
        cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))

    assert event_count == 0
    assert cwc_count == 0


@pytest.mark.asyncio
async def test_service_rejects_cross_tenant_run_without_event_or_row(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            other_scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(other_scope["run"].id), business_object_id=str(scope["refund_case"].id))
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref, updated_by_run_id=None)

        with pytest.raises(ValueError, match="run_id does not belong to tenant"):
            await service_module.CaseWorkingContextService().write_case_working_context(
                session,
                candidate,
                run_id=other_scope["run"].id,
            )
        event_count = await session.scalar(select(func.count()).select_from(MemoryWriteEvent))
        cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))

    assert event_count == 0
    assert cwc_count == 0


@pytest.mark.asyncio
async def test_service_writes_cwc_and_emits_case_working_context_event(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref)

        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            candidate,
            run_id=scope["run"].id,
        )
        row = await CaseWorkingContextRepository(session).read_active(
            tenant_id=scope["tenant"].id,
            case_id=scope["refund_case"].id,
        )
        events = await _events(session, scope["run"].id)

    assert result.status == "written"
    assert result.decision == "write"
    assert result.memory_id == row.id
    assert result.event_id == events[-1].id
    assert result.candidate_hash == events[-1].candidate_hash
    assert row is not None
    assert row.updated_by_run_id == scope["run"].id
    assert events[-1].memory_type == "case_working_context"
    assert events[-1].memory_id == row.id
    assert events[-1].run_id == scope["run"].id
    assert events[-1].source_ref_json["agent_run_id"] == str(scope["run"].id)
    assert events[-1].authority_class == "contextual_only"
    assert events[-1].candidate_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_service_normalizes_cwc_source_refs_to_trusted_run_and_case(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(
            run_id=str(uuid.uuid4()),
            agent_run_id=str(uuid.uuid4()),
            business_object_type="order",
            business_object_id=str(uuid.uuid4()),
        )
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref, updated_by_run_id=None)

        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            candidate,
            run_id=scope["run"].id,
        )
        row = await session.get(CaseWorkingContext, result.memory_id)
        events = await _events(session, scope["run"].id)

    assert row is not None
    assert row.source_ref_json["run_id"] == str(scope["run"].id)
    assert row.source_ref_json["agent_run_id"] == str(scope["run"].id)
    assert row.source_ref_json["business_object_type"] == "refund_case"
    assert row.source_ref_json["business_object_id"] == str(scope["refund_case"].id)
    assert events[-1].source_ref_json == row.source_ref_json
    assert row.claims_json[0]["source_ref"]["agent_run_id"] == str(scope["run"].id)
    assert row.verified_facts_json[0]["source_ref"]["business_object_id"] == str(scope["refund_case"].id)
    assert row.actions_taken_json[0]["source_ref"]["business_object_type"] == "refund_case"
    assert row.commitments_json[0]["source_ref"]["run_id"] == str(scope["run"].id)


@pytest.mark.asyncio
async def test_staff_manual_candidate_succeeds_with_real_run_id_and_sets_row_run(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(
            source_type="staff_manual",
            agent_run_id=str(scope["run"].id),
            business_object_id=str(scope["refund_case"].id),
        )
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref, updated_by_run_id=None)

        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            candidate,
            run_id=scope["run"].id,
        )
        row = await session.get(CaseWorkingContext, result.memory_id)

    assert result.status == "written"
    assert row is not None
    assert row.updated_by_run_id == scope["run"].id


@pytest.mark.asyncio
async def test_staff_manual_revision_preserves_manual_edit_source(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(
            source_type="staff_manual",
            agent_run_id=str(uuid.uuid4()),
            business_object_id=str(uuid.uuid4()),
        )
        service = service_module.CaseWorkingContextService()
        first = await service.write_case_working_context(
            session,
            _candidate(
                scope,
                content=_content(source_ref, customer_request="人工修正前"),
                source_ref=source_ref,
                updated_by_run_id=None,
            ),
            run_id=scope["run"].id,
        )
        second = await service.write_case_working_context(
            session,
            _candidate(
                scope,
                content=_content(source_ref, customer_request="人工修正后"),
                source_ref=source_ref,
                expected_version=first.version,
                updated_by_run_id=None,
            ),
            run_id=scope["run"].id,
        )
        revision = (
            await session.execute(select(CaseWorkingContextRevision).order_by(CaseWorkingContextRevision.version))
        ).scalar_one()

    assert second.status == "written"
    assert revision.version == 1
    assert revision.edit_source == "staff_manual"
    assert revision.updated_by_run_id == scope["run"].id
    assert revision.source_ref_json["source_type"] == "staff_manual"
    assert revision.source_ref_json["agent_run_id"] == str(scope["run"].id)


@pytest.mark.asyncio
@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
async def test_service_blocks_sensitive_or_prohibited_pii_with_audit_event(
    phase44_session_factory,
    pii_classification: str,
) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        candidate = _candidate(
            scope,
            content=_content(source_ref),
            source_ref=source_ref,
            pii_classification=pii_classification,
        )

        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            candidate,
            run_id=scope["run"].id,
        )
        row = await CaseWorkingContextRepository(session).read_active(
            tenant_id=scope["tenant"].id,
            case_id=scope["refund_case"].id,
        )
        events = await _events(session, scope["run"].id)

    assert result.status == "blocked"
    assert result.decision == "write_blocked"
    assert result.reason_code == "pii_blocked"
    assert result.memory_id is None
    assert row is None
    assert events[-1].memory_type == "case_working_context"
    assert events[-1].decision == "write_blocked"
    assert events[-1].reason_code == "pii_blocked"
    assert events[-1].memory_id is None
    assert events[-1].blocked_by_json == ["pii_classification"]
    assert events[-1].pii_classification == pii_classification


@pytest.mark.asyncio
async def test_version_conflict_emits_skip_event_without_written_memory_id(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        service = service_module.CaseWorkingContextService()
        first = await service.write_case_working_context(
            session,
            _candidate(scope, content=_content(source_ref, customer_request="初始请求"), source_ref=source_ref),
            run_id=scope["run"].id,
        )
        conflict = await service.write_case_working_context(
            session,
            _candidate(
                scope,
                content=_content(source_ref, customer_request="冲突写入"),
                source_ref=source_ref,
                expected_version=99,
            ),
            run_id=scope["run"].id,
        )
        row = await session.get(CaseWorkingContext, first.memory_id)
        events = await _events(session, scope["run"].id)

    assert first.status == "written"
    assert conflict.status == "conflict"
    assert conflict.decision == "skip"
    assert conflict.reason_code == "version_conflict"
    assert conflict.memory_id is None
    assert events[-1].decision == "skip"
    assert events[-1].reason_code == "version_conflict"
    assert events[-1].memory_id is None
    assert row is not None
    assert hydrate_content(row).customer_request == "初始请求"


@pytest.mark.asyncio
async def test_candidate_hash_binds_tenant_and_source_identity(
    phase44_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    captured_kwargs: dict | None = None
    original = service_module.canonical_memory_candidate_hash

    def spy_candidate_hash(**kwargs):
        nonlocal captured_kwargs
        captured_kwargs = dict(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(service_module, "canonical_memory_candidate_hash", spy_candidate_hash)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref)

        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            candidate,
            run_id=scope["run"].id,
        )

    assert result.status == "written"
    assert captured_kwargs is not None
    assert captured_kwargs["tenant_id"] == str(scope["tenant"].id)
    assert captured_kwargs["memory_type"] == "case_working_context"
    assert captured_kwargs["scope_type"] == "case"
    assert captured_kwargs["scope_id"] == str(scope["refund_case"].id)
    assert captured_kwargs["source_identity_hash"] is not None
    assert captured_kwargs["source_identity_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_service_persists_high_consequence_content_as_contextual_and_staff_correctable(
    phase44_session_factory,
) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async with phase44_session_factory() as session:
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        content = _content(source_ref)
        expected_content = normalize_case_working_context_content_sources(
            content,
            run_id=scope["run"].id,
            case_id=scope["refund_case"].id,
        )
        result = await service_module.CaseWorkingContextService().write_case_working_context(
            session,
            _candidate(scope, content=content, source_ref=source_ref),
            run_id=scope["run"].id,
        )
        row = await session.get(CaseWorkingContext, result.memory_id)

    assert row is not None
    assert row.authority_class == "contextual_only"
    assert row.claims_json == dehydrate_content(expected_content)["claims"]
    assert row.verified_facts_json == dehydrate_content(expected_content)["verified_facts"]
    assert row.missing_info_json == dehydrate_content(content)["missing_info"]
    assert row.evidence_refs_json == dehydrate_content(content)["evidence_refs"]
    assert row.actions_taken_json == dehydrate_content(expected_content)["actions_taken"]
    assert row.policy_refs_json == dehydrate_content(content)["policy_refs"]
    assert row.agent_recommendations_json == dehydrate_content(content)["agent_recommendations"]
    assert row.pending_tasks_json == dehydrate_content(content)["pending_tasks"]
    assert row.commitments_json == dehydrate_content(expected_content)["commitments"]
    assert row.next_action_json == dehydrate_content(content)["next_action"]

    hydrated = hydrate_content(row)
    assert hydrated.claims[0].verified is False
    assert hydrated.commitments[0].confirmed_by_staff is False
    assert hydrated.agent_recommendations[0].staff_decision is None


@pytest.mark.asyncio
async def test_isolated_service_failure_does_not_poison_parent_transaction(
    phase44_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)

    async def fail_inside_child(self, candidate):  # pragma: no cover - assertion is parent txn survival
        raise RuntimeError("child repository failure")

    monkeypatch.setattr(service_module.CaseWorkingContextRepository, "write_working_context", fail_inside_child)

    async with phase44_session_factory() as session:
        run = await session.get(AgentRun, scope["run"].id)
        run.final_status = "completed_after_child_failure"
        source_ref = _source_ref(agent_run_id=str(scope["run"].id), business_object_id=str(scope["refund_case"].id))
        candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref)

        with pytest.raises(RuntimeError, match="child repository failure"):
            await service_module.CaseWorkingContextService().write_case_working_context(
                session,
                candidate,
                run_id=scope["run"].id,
            )
        await session.commit()

    async with phase44_session_factory() as session:
        persisted = await session.get(AgentRun, scope["run"].id)
        event_count = await session.scalar(select(func.count()).select_from(MemoryWriteEvent))

    assert persisted is not None
    assert persisted.final_status == "completed_after_child_failure"
    assert event_count == 0
