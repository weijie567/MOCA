from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import uuid

import asyncpg
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import (
    AgentRun,
    Base,
    CaseWorkingContext,
    CaseWorkingContextRevision,
    Merchant,
    Order,
    RefundCase,
    Tenant,
)
from src.memory.case_working_context import (
    CaseWorkingContextRepository,
    dehydrate_content,
    hydrate_content,
)
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
        "business_object_type": "refund_case",
        "business_object_id": str(uuid.uuid4()),
    }
    payload.update(overrides)
    if "agent_run_id" in overrides and "run_id" not in overrides:
        payload["run_id"] = overrides["agent_run_id"]
    return MemorySourceRefV1.model_validate(payload)


async def _seed_case_scope(session: AsyncSession) -> dict:
    tenant = Tenant(id=uuid.uuid4(), name=f"phase44-tenant-{uuid.uuid4()}", status="active")
    merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_name="Phase 44 Shop",
        category="electronics",
        risk_level="low",
    )
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_id=merchant.id,
        order_no=f"ORD-PHASE44-{uuid.uuid4()}",
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
        refund_case_no=f"RF-PHASE44-{uuid.uuid4()}",
        reason_code="damaged",
        reason_text="收到商品破损",
        status="reviewing",
        requested_amount=Decimal("199.00"),
    )
    run = AgentRun(
        id=uuid.uuid4(),
        thread_id=f"phase44-thread-{uuid.uuid4()}",
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        input_query="测试退款工作上下文",
        final_status="completed",
        scope_classification="unknown_legacy",
        started_at=datetime.now(UTC),
    )
    session.add_all([tenant, merchant, order, refund_case, run])
    await session.flush()
    return {"tenant": tenant, "merchant": merchant, "order": order, "refund_case": refund_case, "run": run}


def _content(
    source_ref: MemorySourceRefV1, *, customer_request: str = "用户询问退款进度"
) -> CaseWorkingContextContentV1:
    return CaseWorkingContextContentV1(
        customer_request=customer_request,
        issue_type="refund_status",
        claims=[
            CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref),
        ],
        verified_facts=[
            CaseWorkingContextVerifiedFactV1(
                text="退款单状态为 reviewing",
                source_ref=source_ref,
                observed_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
            ),
        ],
        missing_info=["需要补充破损照片"],
        evidence_refs=[CaseWorkingContextEvidencePointerV1(ref_type="tool_result", ref_id="tool-result-1")],
        actions_taken=[CaseWorkingContextActionTakenV1(action="查询退款单状态", source_ref=source_ref)],
        policy_refs=[CaseWorkingContextPolicyRefV1(doc_id="refund-policy", chunk_id="refund-policy#001", version="v1")],
        agent_recommendations=[
            CaseWorkingContextRecommendationV1(recommended_step="要求用户上传照片", staff_decision=None),
        ],
        pending_tasks=["等待用户上传照片"],
        commitments=[
            CaseWorkingContextCommitmentV1(text="24 小时内回复用户", confirmed_by_staff=True, source_ref=source_ref),
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
) -> CaseWorkingContextWriteCandidate:
    return CaseWorkingContextWriteCandidate(
        tenant_id=scope["tenant"].id,
        case_id=scope["refund_case"].id,
        updated_by_run_id=scope["run"].id,
        source_ref=source_ref,
        expected_version=expected_version,
        content=content,
    )


def test_schema_claims_facts_actions_and_commitments_require_source_refs() -> None:
    source_ref = _source_ref()
    claim = CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref)
    fact = CaseWorkingContextVerifiedFactV1(
        text="退款单状态为 reviewing",
        source_ref=source_ref,
        observed_at=datetime.now(UTC),
    )
    action = CaseWorkingContextActionTakenV1(action="已查询退款单", source_ref=source_ref)
    commitment = CaseWorkingContextCommitmentV1(
        text="客服承诺 24 小时内回复", confirmed_by_staff=True, source_ref=source_ref
    )

    assert claim.source_ref == source_ref
    assert fact.source_ref == source_ref
    assert action.source_ref == source_ref
    assert commitment.confirmed_by_staff is True
    assert commitment.source_ref == source_ref

    with pytest.raises(ValidationError):
        CaseWorkingContextClaimV1.model_validate({"text": "missing source", "verified": False})
    with pytest.raises(ValidationError):
        CaseWorkingContextVerifiedFactV1.model_validate({"text": "missing source", "observed_at": datetime.now(UTC)})
    with pytest.raises(ValidationError):
        CaseWorkingContextActionTakenV1.model_validate({"action": "missing source"})
    with pytest.raises(ValidationError):
        CaseWorkingContextCommitmentV1.model_validate({"text": "missing confirmed flag", "source_ref": source_ref})


def test_schema_claims_and_verified_facts_are_distinct_types() -> None:
    source_ref = _source_ref()
    claim = CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref)
    fact = CaseWorkingContextVerifiedFactV1(
        text="系统确认物流已签收",
        source_ref=source_ref,
        observed_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        CaseWorkingContextVerifiedFactV1.model_validate(claim.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        CaseWorkingContextClaimV1.model_validate(fact.model_dump(mode="json"))


def test_schema_content_forbids_extra_keys_and_defaults_lists() -> None:
    content = CaseWorkingContextContentV1()

    assert content.authority_class == "contextual_only"
    assert content.claims == []
    assert content.verified_facts == []
    assert content.missing_info == []
    assert content.evidence_refs == []
    assert content.actions_taken == []
    assert content.policy_refs == []
    assert content.agent_recommendations == []
    assert content.pending_tasks == []
    assert content.commitments == []
    assert content.next_action.recommended_step is None
    assert content.next_action.blocked_by == []

    with pytest.raises(ValidationError):
        CaseWorkingContextContentV1.model_validate({"unexpected": "forbidden"})


def test_schema_evidence_refs_are_contextual_pointers_not_evidence_refs() -> None:
    pointer = CaseWorkingContextEvidencePointerV1(
        ref_type="tool_result",
        ref_id="tool-result-1",
        summary="退款单状态为 reviewing",
        observed_at=datetime.now(UTC),
    )

    content = CaseWorkingContextContentV1(evidence_refs=[pointer])

    assert content.evidence_refs[0].ref_type == "tool_result"
    assert content.evidence_refs[0].ref_id == "tool-result-1"

    for invalid_ref in (
        {
            "schema_version": "evidence_ref.v1",
            "doc_id": "refund-policy",
            "chunk_id": "refund-policy#001",
            "quote": "policy body text",
        },
        {
            "ref_type": "tool_result",
            "ref_id": "tool-result-2",
            "policy_body": "raw policy body must not be stored",
        },
    ):
        with pytest.raises(ValidationError):
            CaseWorkingContextContentV1.model_validate({"evidence_refs": [invalid_ref]})


def test_schema_write_candidate_requires_scope_source_ref_and_content() -> None:
    source_ref = _source_ref()
    candidate = CaseWorkingContextWriteCandidate(
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        updated_by_run_id=None,
        source_ref=source_ref,
        expected_version=None,
        content=CaseWorkingContextContentV1(customer_request="用户询问退款进度"),
    )

    assert candidate.source_ref == source_ref
    assert candidate.pii_classification == "none"
    assert candidate.content.customer_request == "用户询问退款进度"

    with pytest.raises(ValidationError):
        CaseWorkingContextWriteCandidate.model_validate(
            {
                "tenant_id": str(uuid.uuid4()),
                "case_id": str(uuid.uuid4()),
                "updated_by_run_id": None,
                "expected_version": None,
                "content": {},
            }
        )


@pytest.mark.asyncio
async def test_repo_write_creates_version_one_without_revision(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(scope["run"].id))
            candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref)

            result = await CaseWorkingContextRepository(session).write_working_context(candidate)
            revision_count = await session.scalar(select(func.count()).select_from(CaseWorkingContextRevision))
            row = await CaseWorkingContextRepository(session).read_active(
                tenant_id=scope["tenant"].id,
                case_id=scope["refund_case"].id,
            )

    assert result.status == "written"
    assert result.version == 1
    assert row is not None
    assert row.version == 1
    assert row.authority_class == "contextual_only"
    assert row.source_ref_json["agent_run_id"] == str(scope["run"].id)
    assert revision_count == 0


@pytest.mark.asyncio
async def test_repo_write_updates_version_and_snapshots_prior_content(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(scope["run"].id))
            repository = CaseWorkingContextRepository(session)
            await repository.write_working_context(
                _candidate(scope, content=_content(source_ref, customer_request="初始请求"), source_ref=source_ref)
            )

            result = await repository.write_working_context(
                _candidate(
                    scope,
                    content=_content(source_ref, customer_request="更新后的请求"),
                    source_ref=source_ref,
                    expected_version=1,
                )
            )
            row = await repository.read_active(tenant_id=scope["tenant"].id, case_id=scope["refund_case"].id)
            revision = (
                await session.execute(select(CaseWorkingContextRevision).order_by(CaseWorkingContextRevision.version))
            ).scalar_one()

    assert result.status == "written"
    assert result.version == 2
    assert row is not None
    assert row.version == 2
    assert hydrate_content(row).customer_request == "更新后的请求"
    assert revision.version == 1
    assert revision.snapshot_json["customer_request"] == "初始请求"
    assert revision.snapshot_json["claims"][0]["text"] == "用户称商品破损"
    assert revision.source_ref_json["agent_run_id"] == str(scope["run"].id)


@pytest.mark.asyncio
async def test_repo_write_expected_version_conflict_does_not_clobber(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(scope["run"].id))
            repository = CaseWorkingContextRepository(session)
            first = await repository.write_working_context(
                _candidate(scope, content=_content(source_ref, customer_request="初始请求"), source_ref=source_ref)
            )
            conflict = await repository.write_working_context(
                _candidate(
                    scope,
                    content=_content(source_ref, customer_request="冲突写入"),
                    source_ref=source_ref,
                    expected_version=99,
                )
            )
            row = await repository.read_active(tenant_id=scope["tenant"].id, case_id=scope["refund_case"].id)
            revision_count = await session.scalar(select(func.count()).select_from(CaseWorkingContextRevision))

    assert first.status == "written"
    assert conflict.status == "conflict"
    assert conflict.case_working_context_id == first.case_working_context_id
    assert conflict.version == 1
    assert row is not None
    assert hydrate_content(row).customer_request == "初始请求"
    assert revision_count == 0


@pytest.mark.asyncio
async def test_repo_write_expected_version_without_active_row_returns_conflict(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(scope["run"].id))
            repository = CaseWorkingContextRepository(session)

            result = await repository.write_working_context(
                _candidate(
                    scope,
                    content=_content(source_ref, customer_request="stale create"),
                    source_ref=source_ref,
                    expected_version=1,
                )
            )
            cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))
            revision_count = await session.scalar(select(func.count()).select_from(CaseWorkingContextRevision))

    assert result.status == "conflict"
    assert result.case_working_context_id is None
    assert result.version is None
    assert cwc_count == 0
    assert revision_count == 0


@pytest.mark.asyncio
async def test_repo_rejects_updated_by_run_id_from_another_tenant(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            other_scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(other_scope["run"].id))
            candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref).model_copy(
                update={"updated_by_run_id": other_scope["run"].id}
            )

            with pytest.raises(ValueError, match="updated_by_run_id does not belong to tenant"):
                await CaseWorkingContextRepository(session).write_working_context(candidate)

            cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))
            revision_count = await session.scalar(select(func.count()).select_from(CaseWorkingContextRevision))

    assert cwc_count == 0
    assert revision_count == 0


@pytest.mark.asyncio
async def test_repo_rejects_source_ref_run_ids_from_another_tenant_when_updater_missing(
    phase44_session_factory,
) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            other_scope = await _seed_case_scope(session)
            source_ref = _source_ref(
                run_id=str(other_scope["run"].id),
                agent_run_id=str(other_scope["run"].id),
            )
            candidate = _candidate(scope, content=_content(source_ref), source_ref=source_ref).model_copy(
                update={"updated_by_run_id": None}
            )

            with pytest.raises(ValueError, match="source_ref run_id/agent_run_id does not belong to tenant"):
                await CaseWorkingContextRepository(session).write_working_context(candidate)

            cwc_count = await session.scalar(select(func.count()).select_from(CaseWorkingContext))
            revision_count = await session.scalar(select(func.count()).select_from(CaseWorkingContextRevision))

    assert cwc_count == 0
    assert revision_count == 0


@pytest.mark.asyncio
async def test_repo_maps_every_content_field_to_json_columns_and_hydrates(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            source_ref = _source_ref(agent_run_id=str(scope["run"].id))
            content = _content(source_ref)
            expected_content = normalize_case_working_context_content_sources(
                content,
                run_id=scope["run"].id,
                case_id=scope["refund_case"].id,
            )
            result = await CaseWorkingContextRepository(session).write_working_context(
                _candidate(scope, content=content, source_ref=source_ref)
            )
            row = await session.get(CaseWorkingContext, result.case_working_context_id)

    assert row is not None
    assert row.customer_request == content.customer_request
    assert row.issue_type == content.issue_type
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
    assert hydrated.claims[0].text == content.claims[0].text
    assert hydrated.verified_facts[0].observed_at == content.verified_facts[0].observed_at
    assert hydrated.commitments[0].confirmed_by_staff is True


@pytest.mark.asyncio
async def test_repo_read_active_returns_none_for_missing_scope(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            result = await CaseWorkingContextRepository(session).read_active(
                tenant_id=scope["tenant"].id,
                case_id=scope["refund_case"].id,
            )

    assert result is None


@pytest.mark.asyncio
async def test_repo_concurrent_first_writes_serialize_without_integrity_error(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_case_scope(session)
            scope_ids = {
                "tenant_id": scope["tenant"].id,
                "case_id": scope["refund_case"].id,
                "run_id": scope["run"].id,
            }

    async def write_context(label: str):
        async with phase44_session_factory() as session:
            async with session.begin():
                source_ref = _source_ref(agent_run_id=str(scope_ids["run_id"]), event_id=label)
                candidate = CaseWorkingContextWriteCandidate(
                    tenant_id=scope_ids["tenant_id"],
                    case_id=scope_ids["case_id"],
                    updated_by_run_id=scope_ids["run_id"],
                    source_ref=source_ref,
                    expected_version=None,
                    content=_content(source_ref, customer_request=label),
                )
                return await CaseWorkingContextRepository(session).write_working_context(candidate)

    first, second = await asyncio.gather(write_context("first-write"), write_context("second-write"))

    async with phase44_session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(CaseWorkingContext)
            .where(
                CaseWorkingContext.tenant_id == scope_ids["tenant_id"],
                CaseWorkingContext.case_id == scope_ids["case_id"],
                CaseWorkingContext.deleted_at.is_(None),
            )
        )
        row = (
            await session.execute(
                select(CaseWorkingContext).where(
                    CaseWorkingContext.tenant_id == scope_ids["tenant_id"],
                    CaseWorkingContext.case_id == scope_ids["case_id"],
                    CaseWorkingContext.deleted_at.is_(None),
                )
            )
        ).scalar_one()

    assert [first.status, second.status] == ["written", "written"]
    assert active_count == 1
    assert row.version == 2
