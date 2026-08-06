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

import src.memory.case_working_context_lifecycle as lifecycle_module
from src.conversation.repository import ConversationRepository
from src.db.models import AgentRun, Base, CaseWorkingContext, Merchant, Order, RefundCase, Tenant, ThreadCaseLink, User
from src.knowledge.evidence_identity import PersistedEvidenceIdentityMaterialV1, mint_canonical_evidence_identity
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_identity import CaseIdentityResult
from src.memory.case_working_context_lifecycle import (
    CaseWorkingContextLifecycleAdapter,
    TerminalProjectionResult,
    build_active_cwc_payload,
    project_terminal_write_candidate,
    skipped_status,
    trusted_case_ref_from_state,
)
from src.memory.case_working_context_schemas import CaseWorkingContextContentV1, CaseWorkingContextWriteCandidate
from src.memory.context_refs import CaseWorkingContextLifecycleStatusV1
from src.memory.fact_promotion import FactPromotionCandidateV1, promote_verified_fact
from src.tools.contracts import BusinessFactRefV1
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
    observed_at = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    business_ref = _promotion_business_ref(tenant_id, observed_at=observed_at)
    policy_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)
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
                "authority_class": "business_fact",
                "status": "success",
                "promotion_reason_code": "authoritative_business_fact",
                "source_ref": source_ref,
                "observed_at": observed_at,
                "business_fact_refs": [business_ref.model_dump(mode="json")],
                "policy_evidence_refs": [],
            }
        ],
        missing_info_json=["需要补充破损照片"],
        evidence_refs_json=[
            {
                "schema_version": "case_working_context_observation.v1",
                "summary": "无法验证跨范围来源",
                "decision": "reject",
                "authority_class": "policy_evidence",
                "status": "success",
                "reason_code": "authoritative_source_unavailable",
                "internal_reason_code": "tenant_mismatch",
                "completeness": "complete",
                "scope_result": "invalid",
                "freshness_result": "valid",
                "reference_validation": "invalid",
                "source_ref": source_ref,
                "observed_at": observed_at,
                "business_fact_refs": [],
                "policy_evidence_refs": [],
            }
        ],
        actions_taken_json=[{"action": "查询退款单状态", "source_ref": source_ref}],
        policy_refs_json=[policy_ref.model_dump(mode="json")],
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
    assert payload["content"]["evidence_refs"][0]["reason_code"] == "authoritative_source_unavailable"
    assert "internal_reason_code" not in payload["content"]["evidence_refs"][0]
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


def test_terminal_projection_result_contract() -> None:
    status_ref = skipped_status(reason_code="clarification_only")
    result = TerminalProjectionResult(candidate=None, status_ref=status_ref)

    assert set(TerminalProjectionResult.__annotations__) == {"candidate", "status_ref"}
    assert result.candidate is None
    assert isinstance(result.status_ref, CaseWorkingContextLifecycleStatusV1)


def _promotion_business_ref(tenant_id: uuid.UUID, *, observed_at: datetime) -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_fact_service",
        resource_type="refund_case",
        resource_id="RF-PROMOTION-001",
        resource_version="v7",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )


def _promotion_evidence_ref(tenant_id: uuid.UUID, *, observed_at: datetime) -> EvidenceRefV1:
    material = PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(tenant_id),
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        document_version_id=str(uuid.uuid4()),
        chunk_version_id=str(uuid.uuid4()),
        doc_key="refund-policy",
        document_version=7,
        chunk_id="refund-policy#001",
        chunk_version=3,
        text_hash=f"sha256:{'a' * 64}",
    )
    resolution = mint_canonical_evidence_identity(
        material,
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert resolution.identity is not None
    return EvidenceRefV1.from_canonical_identity(
        resolution.identity,
        retrieved_at=observed_at.isoformat(),
        retrieval_config_version="retrieval.v3",
        rank=1,
    )


def _promotion_candidate(
    *,
    tenant_id: uuid.UUID,
    observed_at: datetime,
    authority_class: str,
    status: str = "success",
    business_fact_refs: list[BusinessFactRefV1] | None = None,
    policy_evidence_refs: list[EvidenceRefV1] | None = None,
    reference_validation: str = "valid",
) -> FactPromotionCandidateV1:
    return FactPromotionCandidateV1(
        tenant_id=str(tenant_id),
        summary="退款单状态为 reviewing",
        authority_class=authority_class,
        status=status,
        completeness="complete",
        scope_result="valid",
        freshness_result="valid",
        reference_validation=reference_validation,
        observed_at=observed_at,
        business_fact_refs=business_fact_refs or [],
        policy_evidence_refs=policy_evidence_refs or [],
    )


def _promotion_tool_result(
    *,
    tenant_id: uuid.UUID,
    observed_at: datetime,
    authority_class: str,
    status: str = "success",
    summary: str = "退款单状态为 reviewing",
    business_fact_refs: list[BusinessFactRefV1] | None = None,
    policy_evidence_refs: list[EvidenceRefV1] | None = None,
    completeness: str = "complete",
    scope_result: str = "valid",
    freshness_result: str = "valid",
    reference_validation: str = "valid",
    tool_result_id: str | None = None,
) -> dict[str, object]:
    return {
        "tool_result_id": tool_result_id or f"tool-result-{uuid.uuid4()}",
        "tool_name": "search_policy" if authority_class == "policy_evidence" else "get_refund_case",
        "summary": summary,
        "prompt_summary": summary,
        "authority_class": authority_class,
        "status": status,
        "completeness": completeness,
        "scope_result": scope_result,
        "freshness_result": freshness_result,
        "reference_validation": reference_validation,
        "observed_at": observed_at.isoformat(),
        "business_fact_refs": [ref.model_dump(mode="json") for ref in business_fact_refs or []],
        "policy_evidence_refs": [ref.model_dump(mode="json") for ref in policy_evidence_refs or []],
        "tenant_id": str(tenant_id),
    }


def test_fact_promotion_contract_allows_only_typed_authoritative_sources() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    business_ref = _promotion_business_ref(tenant_id, observed_at=observed_at)
    evidence_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)

    business = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="business_fact",
            business_fact_refs=[business_ref],
        )
    )
    policy = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="policy_evidence",
            policy_evidence_refs=[evidence_ref],
        )
    )

    assert (business.decision, business.reason_code) == ("promote", "authoritative_business_fact")
    assert business.business_fact_refs == [business_ref]
    assert (policy.decision, policy.reason_code) == ("promote", "authoritative_policy_evidence")
    assert policy.policy_evidence_refs == [evidence_ref]
    assert policy.policy_evidence_refs[0].model_dump(mode="json") == evidence_ref.model_dump(mode="json")
    assert policy.policy_evidence_refs[0].scope_type == "tenant_policy"
    assert policy.policy_evidence_refs[0].scope_id == str(tenant_id)


@pytest.mark.parametrize(
    ("authority_class", "expected_decision", "expected_reason"),
    [
        ("contextual_only", "observe", "contextual_only_non_authoritative"),
        ("unknown", "reject", "unknown_authority"),
    ],
)
def test_fact_promotion_contract_never_promotes_contextual_or_unknown_authority(
    authority_class: str,
    expected_decision: str,
    expected_reason: str,
) -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    result = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class=authority_class,
            business_fact_refs=[_promotion_business_ref(tenant_id, observed_at=observed_at)],
        )
    )

    assert (result.decision, result.reason_code) == (expected_decision, expected_reason)


@pytest.mark.parametrize(
    "status",
    [
        "denied",
        "unavailable",
        "stale",
        "malformed",
        "partial",
        "partial_success",
        "timeout",
        "error",
        "invalid_request",
        "invalid_response",
        "not_found",
        "legacy_unresolved",
    ],
)
def test_fact_promotion_contract_keeps_every_prohibited_status_non_authoritative(status: str) -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    result = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="business_fact",
            status=status,
            business_fact_refs=[_promotion_business_ref(tenant_id, observed_at=observed_at)],
        )
    )

    assert (result.decision, result.reason_code) == ("observe", "status_non_promotable")


def test_fact_promotion_contract_rejects_summary_only_and_compatibility_only_sources() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    summary_only = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="business_fact",
        )
    )
    compatibility_only = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="policy_evidence",
            policy_evidence_refs=[_promotion_evidence_ref(tenant_id, observed_at=observed_at)],
            reference_validation="compatibility_only",
        )
    )

    assert (summary_only.decision, summary_only.reason_code) == ("observe", "missing_authoritative_ref")
    assert (compatibility_only.decision, compatibility_only.reason_code) == (
        "observe",
        "compatibility_only_ref",
    )


def test_cwc_fact_schema_round_trips_full_canonical_policy_ref_without_reduced_shape() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    evidence_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)
    result = promote_verified_fact(
        _promotion_candidate(
            tenant_id=tenant_id,
            observed_at=observed_at,
            authority_class="policy_evidence",
            policy_evidence_refs=[evidence_ref],
        )
    )
    content = CaseWorkingContextContentV1(
        verified_facts=[result.to_verified_fact(source_ref={"source_type": "tool_result"})],
        policy_refs=result.policy_evidence_refs,
    )
    restored = CaseWorkingContextContentV1.model_validate(content.model_dump(mode="json"))

    assert restored.policy_refs == [evidence_ref]
    assert restored.verified_facts[0].policy_evidence_refs == [evidence_ref]
    assert restored.policy_refs[0].scope_type == "tenant_policy"
    assert restored.policy_refs[0].scope_id == str(tenant_id)


def test_project_terminal_write_candidate_returns_eligible_candidate_with_terminal_source_ref() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()

    projection = project_terminal_write_candidate(
        state={
            "user_query": "请帮我看一下这个退款单为什么还没处理",
            "active_slots": {"issue_type": "refund_status"},
            "tool_results": [
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=datetime(2026, 8, 5, 9, 30, tzinfo=UTC),
                    authority_class="business_fact",
                    business_fact_refs=[
                        _promotion_business_ref(
                            tenant_id,
                            observed_at=datetime(2026, 8, 5, 9, 30, tzinfo=UTC),
                        )
                    ],
                    tool_result_id="tool-result-1",
                )
            ],
        },
        tenant_id=tenant_id,
        case_id=case_id,
        run_id=run_id,
        expected_version=7,
        final_response="退款单还在审核中。",
    )

    assert isinstance(projection, TerminalProjectionResult)
    assert isinstance(projection.candidate, CaseWorkingContextWriteCandidate)
    assert projection.status_ref.status == "eligible"
    assert projection.status_ref.write_status == "candidate_projected"
    assert projection.status_ref.reason_code == "eligible"
    assert projection.candidate.tenant_id == tenant_id
    assert projection.candidate.case_id == case_id
    assert projection.candidate.updated_by_run_id == run_id
    assert projection.candidate.expected_version == 7
    assert projection.candidate.source_ref.source_type == "run_auto_terminal"
    assert projection.candidate.source_ref.run_id == str(run_id)
    assert projection.candidate.source_ref.agent_run_id == str(run_id)
    assert projection.candidate.source_ref.business_object_type == "refund_case"
    assert projection.candidate.source_ref.business_object_id == str(case_id)


def test_project_terminal_write_candidate_skips_clarification_only_state() -> None:
    projection = project_terminal_write_candidate(
        state={
            "user_query": "这个怎么处理？",
            "clarification_request": {"question": "请提供退款单号"},
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="请先提供退款单号。",
    )

    assert projection.candidate is None
    assert projection.status_ref.status == "skipped"
    assert projection.status_ref.write_status == "skipped"
    assert projection.status_ref.reason_code == "clarification_only"


def test_project_terminal_write_candidate_caps_customer_request_and_issue_type() -> None:
    issue_type = "refund_status_" + ("x" * 80)
    query = "用户描述" * 120

    projection = project_terminal_write_candidate(
        state={
            "user_query": query,
            "active_slots": {"issue_type": issue_type},
            "tool_results": [{"summary": "退款单状态为 reviewing"}],
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="退款单还在审核中。",
    )

    assert projection.candidate is not None
    assert projection.candidate.content.customer_request == query[:500]
    assert projection.candidate.content.issue_type == issue_type[:64]

    fallback = project_terminal_write_candidate(
        state={
            "user_query": "查询退款进度",
            "primary_intent": "refund_status_from_primary_intent",
            "tool_results": [{"summary": "退款单状态为 reviewing"}],
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="退款单还在审核中。",
    )

    assert fallback.candidate is not None
    assert fallback.candidate.content.issue_type == "refund_status_from_primary_intent"


def test_project_terminal_write_candidate_uses_only_prompt_safe_tool_summaries() -> None:
    projection = project_terminal_write_candidate(
        state={
            "user_query": "查询退款进度",
            "tool_results": [
                {
                    "tool_result_id": "summary-tool",
                    "summary": "退款单状态为 reviewing",
                    "data": {"unsafe": "raw data should not leak"},
                    "raw_payload": "raw_payload should not leak",
                },
                {
                    "tool_call_id": "prompt-tool",
                    "prompt_summary": "订单已签收",
                    "raw_result": "raw_result should not leak",
                },
                {
                    "tool_result_id": "tool-summary",
                    "tool_summary": "商家风险等级低",
                    "raw_payload": "policy raw body should not leak",
                },
            ],
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="退款单还在审核中。",
    )

    assert projection.candidate is not None
    assert projection.candidate.content.verified_facts == []
    assert [observation.summary for observation in projection.candidate.content.observations] == [
        "退款单状态为 reviewing",
        "订单已签收",
        "商家风险等级低",
    ]
    projected = repr(projection.candidate.content.model_dump(mode="json"))
    assert "raw data should not leak" not in projected
    assert "raw_payload should not leak" not in projected
    assert "raw_result should not leak" not in projected
    assert "policy raw body should not leak" not in projected


def test_project_terminal_write_candidate_policy_refs_use_full_canonical_identity() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    evidence_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)
    projection = project_terminal_write_candidate(
        state={
            "user_query": "查询退款政策",
            "tool_results": [
                {
                    **_promotion_tool_result(
                        tenant_id=tenant_id,
                        observed_at=observed_at,
                        authority_class="policy_evidence",
                        summary="按租户政策继续审核",
                        policy_evidence_refs=[evidence_ref],
                    ),
                    "raw_payload": "full policy evidence text should not leak",
                }
            ],
        },
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="按政策继续审核。",
        _validated_policy_evidence_ids=frozenset({evidence_ref.evidence_id}),
    )

    assert projection.candidate is not None
    assert projection.candidate.content.policy_refs == [evidence_ref]
    assert projection.candidate.content.verified_facts[0].policy_evidence_refs == [evidence_ref]
    assert projection.candidate.content.policy_refs[0].scope_type == "tenant_policy"
    assert projection.candidate.content.policy_refs[0].scope_id == str(tenant_id)
    projected = repr(projection.candidate.content.model_dump(mode="json"))
    assert "full policy evidence text should not leak" not in projected


def test_terminal_projection_promotes_valid_mixed_members_independently_and_dedupes_exact_sources() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    business_ref = _promotion_business_ref(tenant_id, observed_at=observed_at)
    second_business_ref = business_ref.model_copy(update={"resource_id": "RF-PROMOTION-002"})
    evidence_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)
    business_result = _promotion_tool_result(
        tenant_id=tenant_id,
        observed_at=observed_at,
        authority_class="business_fact",
        business_fact_refs=[business_ref, second_business_ref],
        summary="退款单状态为 reviewing",
    )
    projection = project_terminal_write_candidate(
        state={
            "user_query": "查询退款单和租户政策",
            "tool_results": [
                business_result,
                {
                    **business_result,
                    "tool_result_id": "duplicate-source",
                    "summary": "同源重复摘要",
                    "business_fact_refs": [
                        second_business_ref.model_dump(mode="json"),
                        business_ref.model_dump(mode="json"),
                    ],
                },
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="policy_evidence",
                    policy_evidence_refs=[evidence_ref],
                    summary="租户退款政策允许继续审核",
                ),
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="contextual_only",
                    business_fact_refs=[business_ref, second_business_ref],
                    summary="历史上下文仅供参考",
                ),
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="unknown",
                    business_fact_refs=[business_ref, second_business_ref],
                    summary="未知来源声称已完成",
                ),
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="business_fact",
                    status="timeout",
                    business_fact_refs=[business_ref, second_business_ref],
                    summary="超时前的部分摘要",
                ),
            ],
        },
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="已核对当前事实和租户政策。",
        _validated_policy_evidence_ids=frozenset({evidence_ref.evidence_id}),
    )

    assert projection.candidate is not None
    assert [fact.authority_class for fact in projection.candidate.content.verified_facts] == [
        "business_fact",
        "policy_evidence",
    ]
    assert projection.candidate.content.verified_facts[0].business_fact_refs == [business_ref, second_business_ref]
    assert projection.candidate.content.verified_facts[1].policy_evidence_refs == [evidence_ref]
    assert projection.candidate.content.policy_refs == [evidence_ref]
    assert [(item.decision, item.reason_code) for item in projection.candidate.content.observations] == [
        ("observe", "contextual_only_non_authoritative"),
        ("reject", "unknown_authority"),
        ("observe", "status_non_promotable"),
    ]


def test_terminal_projection_rejects_mixed_malformed_business_ref_list() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    business_ref = _promotion_business_ref(tenant_id, observed_at=observed_at)
    item = _promotion_tool_result(
        tenant_id=tenant_id,
        observed_at=observed_at,
        authority_class="business_fact",
        business_fact_refs=[business_ref],
    )
    item["business_fact_refs"] = [business_ref.model_dump(mode="json"), "malformed-member"]

    projection = project_terminal_write_candidate(
        state={"user_query": "查询退款单", "tool_results": [item]},
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="无法验证业务事实来源。",
    )

    assert projection.candidate is not None
    content = projection.candidate.content
    assert content.verified_facts == []
    assert content.policy_refs == []
    assert len(content.observations) == 1
    assert content.observations[0].decision == "observe"
    assert content.observations[0].reference_validation == "invalid"


@pytest.mark.asyncio
async def test_terminal_projection_rejects_mixed_malformed_policy_ref_list_before_exact_resolution() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    evidence_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at)
    item = _promotion_tool_result(
        tenant_id=tenant_id,
        observed_at=observed_at,
        authority_class="policy_evidence",
        policy_evidence_refs=[evidence_ref],
    )
    item["policy_evidence_refs"] = [evidence_ref.model_dump(mode="json"), "malformed-member"]
    state = {"user_query": "查询退款政策", "tool_results": [item]}
    resolver_calls: list[str] = []

    async def exact_resolver(
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        evidence_ref: EvidenceRefV1,
    ) -> bool:
        del session, tenant_id
        resolver_calls.append(evidence_ref.evidence_id)
        return True

    validated_ids = await lifecycle_module._validated_policy_evidence_ids(
        state,
        session=SimpleNamespace(),
        tenant_id=tenant_id,
        resolver=exact_resolver,
    )
    projection = project_terminal_write_candidate(
        state=state,
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="无法验证政策来源。",
        _validated_policy_evidence_ids=validated_ids,
    )

    assert resolver_calls == []
    assert validated_ids == frozenset()
    assert projection.candidate is not None
    content = projection.candidate.content
    assert content.verified_facts == []
    assert content.policy_refs == []
    assert len(content.observations) == 1
    assert content.observations[0].decision == "reject"
    assert content.observations[0].reference_validation == "invalid"


@pytest.mark.parametrize(
    ("mutation", "expected_internal_reason"),
    [
        ({"scope_id": "same-tenant-request-scope"}, "scope_mismatch"),
        ({"text_hash": f"sha256:{'b' * 64}"}, "scope_mismatch"),
    ],
)
def test_terminal_projection_rejects_forged_or_cross_scope_policy_refs_with_generic_reason(
    mutation: dict[str, str],
    expected_internal_reason: str,
) -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    forged_ref = _promotion_evidence_ref(tenant_id, observed_at=observed_at).model_dump(mode="json")
    forged_ref.update(mutation)
    item = _promotion_tool_result(
        tenant_id=tenant_id,
        observed_at=observed_at,
        authority_class="policy_evidence",
        policy_evidence_refs=[],
    )
    item["policy_evidence_refs"] = [forged_ref]
    projection = project_terminal_write_candidate(
        state={"user_query": "查询退款政策", "tool_results": [item]},
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="无法验证政策来源。",
    )

    assert projection.candidate is not None
    assert projection.candidate.content.verified_facts == []
    assert projection.candidate.content.policy_refs == []
    assert len(projection.candidate.content.observations) == 1
    observation = projection.candidate.content.observations[0]
    assert observation.reason_code == "authoritative_source_unavailable"
    assert observation.internal_reason_code == expected_internal_reason


def test_terminal_projection_keeps_summary_only_and_freshness_mismatch_out_of_verified_facts() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 30, tzinfo=UTC)
    business_ref = _promotion_business_ref(tenant_id, observed_at=observed_at)
    projection = project_terminal_write_candidate(
        state={
            "user_query": "查询退款单",
            "tool_results": [
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="business_fact",
                    summary="只有摘要，没有权威引用",
                ),
                _promotion_tool_result(
                    tenant_id=tenant_id,
                    observed_at=observed_at,
                    authority_class="business_fact",
                    business_fact_refs=[business_ref],
                    freshness_result="stale",
                    summary="过期退款状态",
                ),
            ],
        },
        tenant_id=tenant_id,
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="未获得可验证的新事实。",
    )

    assert projection.candidate is not None
    assert projection.candidate.content.verified_facts == []
    assert [item.reason_code for item in projection.candidate.content.observations] == [
        "missing_authoritative_ref",
        "freshness_not_valid",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("用户留下手机号请联系", "prohibited"),
        ("merchant password=abc123", "prohibited"),
        ("请联系 13800138000", "sensitive"),
        ("access_token: abc123", "sensitive"),
        ("普通退款咨询", "none"),
    ],
)
def test_project_terminal_write_candidate_classifies_pii_deterministically(text: str, expected: str) -> None:
    projection = project_terminal_write_candidate(
        state={
            "user_query": text,
            "tool_results": [{"summary": "退款单状态为 reviewing"}],
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="退款单还在审核中。",
    )

    assert projection.candidate is not None
    assert projection.candidate.pii_classification == expected


def _terminal_state(scope: dict[str, object], **overrides: object) -> dict[str, object]:
    observed_at = datetime.now(UTC)
    state: dict[str, object] = {
        "user_query": "请帮我更新这个退款单的处理上下文",
        "active_slots": {
            "refund_case_id": scope["refund_case"].refund_case_no,
            "issue_type": "refund_status",
        },
        "tool_results": [
            _promotion_tool_result(
                tenant_id=scope["tenant"].id,
                observed_at=observed_at,
                authority_class="business_fact",
                business_fact_refs=[_promotion_business_ref(scope["tenant"].id, observed_at=observed_at)],
                tool_result_id="terminal-tool-1",
            )
        ],
    }
    state.update(overrides)
    return state


class _CapturingCwcService:
    calls: list[dict[str, object]] = []
    result = SimpleNamespace(status="written", reason_code="eligible", memory_id=uuid.uuid4(), version=1)

    async def write_case_working_context(
        self,
        session: AsyncSession,
        candidate: CaseWorkingContextWriteCandidate,
        *,
        run_id: uuid.UUID,
    ) -> SimpleNamespace:
        type(self).calls.append({"session": session, "candidate": candidate, "run_id": run_id})
        return type(self).result


def _reset_capturing_service(
    *,
    status: str = "written",
    reason_code: str = "eligible",
    memory_id: uuid.UUID | None = None,
    version: int | None = 1,
) -> None:
    _CapturingCwcService.calls = []
    _CapturingCwcService.result = SimpleNamespace(
        status=status,
        reason_code=reason_code,
        memory_id=memory_id if memory_id is not None else uuid.uuid4(),
        version=version,
    )


@pytest.mark.asyncio
async def test_terminal_policy_promotion_requires_explicit_exact_resolver_success(
    phase45_session_factory,
) -> None:
    _reset_capturing_service()
    resolver_calls: list[tuple[uuid.UUID, str]] = []

    async def exact_success_resolver(
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        evidence_ref: EvidenceRefV1,
    ) -> bool:
        assert session is not None
        assert evidence_ref.scope_type == "tenant_policy"
        assert evidence_ref.scope_id == str(tenant_id)
        resolver_calls.append((tenant_id, evidence_ref.evidence_id))
        return True

    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            observed_at = datetime.now(UTC)
            evidence_ref = _promotion_evidence_ref(scope["tenant"].id, observed_at=observed_at)
            result = await CaseWorkingContextLifecycleAdapter(
                case_working_context_service_cls=_CapturingCwcService,
                policy_evidence_resolver=exact_success_resolver,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(
                    scope,
                    tool_results=[
                        _promotion_tool_result(
                            tenant_id=scope["tenant"].id,
                            observed_at=observed_at,
                            authority_class="policy_evidence",
                            policy_evidence_refs=[evidence_ref],
                        )
                    ],
                ),
                final_response="按已验证政策继续审核。",
            )

    assert result.status_ref.write_status == "written"
    assert resolver_calls == [(scope["tenant"].id, evidence_ref.evidence_id)]
    content = _CapturingCwcService.calls[0]["candidate"].content
    assert [fact.authority_class for fact in content.verified_facts] == ["policy_evidence"]
    assert content.policy_refs == [evidence_ref]


@pytest.mark.asyncio
async def test_terminal_policy_promotion_rejects_canonical_shaped_nonexistent_ids(
    phase45_session_factory,
) -> None:
    _reset_capturing_service()
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            observed_at = datetime.now(UTC)
            nonexistent_ref = _promotion_evidence_ref(scope["tenant"].id, observed_at=observed_at)
            result = await CaseWorkingContextLifecycleAdapter(
                case_working_context_service_cls=_CapturingCwcService,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(
                    scope,
                    tool_results=[
                        _promotion_tool_result(
                            tenant_id=scope["tenant"].id,
                            observed_at=observed_at,
                            authority_class="policy_evidence",
                            policy_evidence_refs=[nonexistent_ref],
                        )
                    ],
                ),
                final_response="无法验证政策来源。",
            )

    assert result.status_ref.write_status == "written"
    content = _CapturingCwcService.calls[0]["candidate"].content
    assert content.verified_facts == []
    assert content.policy_refs == []
    assert len(content.observations) == 1
    assert content.observations[0].reason_code == "invalid_authoritative_ref"
    assert content.observations[0].reference_validation == "invalid"


@pytest.mark.asyncio
async def test_write_after_terminal_success_links_run_auto_and_calls_cwc_service(
    phase45_session_factory,
) -> None:
    _reset_capturing_service(memory_id=uuid.uuid4(), version=1)
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)

            result = await CaseWorkingContextLifecycleAdapter(
                case_working_context_service_cls=_CapturingCwcService,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(scope),
                final_response="退款单还在审核中。",
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
    assert result.status_ref.resolve_status == "resolved"
    assert result.status_ref.link_status == "linked"
    assert result.status_ref.write_status == "written"
    assert result.status_ref.reason_code == "eligible"
    assert link.link_source == "run_auto"
    assert link.linked_by_run_id == scope["run"].id
    assert len(_CapturingCwcService.calls) == 1
    captured = _CapturingCwcService.calls[0]
    assert captured["run_id"] == scope["run"].id
    assert captured["candidate"].updated_by_run_id == scope["run"].id
    assert captured["candidate"].expected_version is None


@pytest.mark.asyncio
async def test_write_after_terminal_success_passes_active_expected_version(
    phase45_session_factory,
) -> None:
    _reset_capturing_service(memory_id=uuid.uuid4(), version=2)
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            await _insert_active_cwc(session, scope)

            result = await CaseWorkingContextLifecycleAdapter(
                case_working_context_service_cls=_CapturingCwcService,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(scope),
                final_response="退款单还在审核中。",
            )

    assert result.status_ref.write_status == "written"
    assert _CapturingCwcService.calls[0]["candidate"].expected_version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_status", "service_reason", "expected_write_status", "expected_reason"),
    [
        ("blocked", "pii_blocked", "blocked", "pii_blocked"),
        ("conflict", "version_conflict", "conflict", "version_conflict"),
    ],
)
async def test_write_after_terminal_success_maps_blocked_and_conflict_without_memory_payload(
    phase45_session_factory,
    service_status: str,
    service_reason: str,
    expected_write_status: str,
    expected_reason: str,
) -> None:
    _reset_capturing_service(status=service_status, reason_code=service_reason, memory_id=None, version=None)
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            row = await _insert_active_cwc(session, scope)

            result = await CaseWorkingContextLifecycleAdapter(
                case_working_context_service_cls=_CapturingCwcService,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(scope, user_query="merchant password=abc123"),
                final_response="退款单还在审核中。",
            )
            persisted = await session.get(CaseWorkingContext, row.id)

    assert result.case_working_context is None
    assert result.status_ref.write_status == expected_write_status
    assert result.status_ref.reason_code == expected_reason
    assert persisted is not None
    assert persisted.customer_request == "用户询问退款进度"


@pytest.mark.asyncio
async def test_write_after_terminal_success_link_failure_skips_write_service() -> None:
    class LinkFailureConversationRepository:
        def __init__(self, session: object) -> None:
            self.session = session

        async def get_thread(self, **_: object) -> None:
            return None

        async def link_case(self, **_: object) -> None:
            raise RuntimeError("link failed")

    class FailService:
        async def write_case_working_context(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("CWC service must not be called after link failure")

    async def resolved_resolver(*_: object, **__: object) -> CaseIdentityResult:
        return CaseIdentityResult(status="resolved", case_id=uuid.uuid4(), input_form="uuid")

    result = await CaseWorkingContextLifecycleAdapter(
        case_resolver=resolved_resolver,
        conversation_repository_cls=LinkFailureConversationRepository,
        case_working_context_service_cls=FailService,
    ).write_after_terminal_success(
        session=object(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        thread_id="thread-link-failure",
        run_id=uuid.uuid4(),
        final_state={"active_slots": {"refund_case_id": "RF-LINK-FAIL"}},
        final_response="退款单还在审核中。",
    )

    assert result.case_id is not None
    assert result.case_working_context is None
    assert result.status_ref.status == "skipped"
    assert result.status_ref.link_status == "error"
    assert result.status_ref.write_status == "skipped"
    assert result.status_ref.reason_code == "link_failed"


@pytest.mark.asyncio
async def test_write_after_terminal_success_skips_missing_and_unresolved_case_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_projection(**_: object) -> TerminalProjectionResult:
        raise AssertionError("projection must not run before a resolved canonical case id")

    async def not_found_resolver(*_: object, **__: object) -> CaseIdentityResult:
        return CaseIdentityResult(status="not_found", case_id=None, input_form="refund_case_no")

    monkeypatch.setattr(lifecycle_module, "project_terminal_write_candidate", fail_projection)
    no_case = await CaseWorkingContextLifecycleAdapter().write_after_terminal_success(
        session=object(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        thread_id="thread-no-case",
        run_id=uuid.uuid4(),
        final_state={"candidate_slots": {"refund_case_id": "RF-CANDIDATE"}},
        final_response="退款单还在审核中。",
    )
    unresolved = await CaseWorkingContextLifecycleAdapter(
        case_resolver=not_found_resolver
    ).write_after_terminal_success(
        session=object(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        thread_id="thread-unresolved",
        run_id=uuid.uuid4(),
        final_state={"active_slots": {"refund_case_id": "RF-MISSING"}},
        final_response="退款单还在审核中。",
    )

    assert no_case.status_ref.reason_code == "skipped_no_case"
    assert no_case.status_ref.write_status == "skipped"
    assert unresolved.status_ref.reason_code == "skipped_unresolved_case"
    assert unresolved.status_ref.resolve_status == "not_found"
    assert unresolved.status_ref.write_status == "skipped"


@pytest.mark.asyncio
async def test_write_after_terminal_success_dedupes_read_seam_run_auto_link(
    phase45_session_factory,
) -> None:
    _reset_capturing_service(memory_id=uuid.uuid4(), version=1)
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            adapter = CaseWorkingContextLifecycleAdapter(case_working_context_service_cls=_CapturingCwcService)
            read_result = await adapter.link_and_load_active(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                state={"active_slots": {"refund_case_id": scope["refund_case"].refund_case_no}},
            )

            write_result = await adapter.write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(scope),
                final_response="退款单还在审核中。",
            )
            active_count = await session.scalar(
                select(func.count())
                .select_from(ThreadCaseLink)
                .where(
                    ThreadCaseLink.tenant_id == scope["tenant"].id,
                    ThreadCaseLink.case_id == scope["refund_case"].id,
                    ThreadCaseLink.deleted_at.is_(None),
                )
            )

    assert read_result.status_ref.link_status == "linked"
    assert write_result.status_ref.link_status == "deduped"
    assert write_result.status_ref.write_status == "written"
    assert active_count == 1


@pytest.mark.asyncio
async def test_write_after_terminal_success_dedupes_any_existing_active_link_before_terminal_attempt(
    phase45_session_factory,
) -> None:
    class NoTerminalLinkAttemptRepository(ConversationRepository):
        async def link_case(self, **_: object) -> None:
            raise AssertionError("terminal writeback must not attempt link_case for an active link")

    _reset_capturing_service(memory_id=uuid.uuid4(), version=1)
    async with phase45_session_factory() as session:
        async with session.begin():
            scope = await _seed_lifecycle_scope(session)
            staff_link = await ConversationRepository(session).link_case(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                case_id=scope["refund_case"].id,
                link_source="staff_manual",
            )

            write_result = await CaseWorkingContextLifecycleAdapter(
                conversation_repository_cls=NoTerminalLinkAttemptRepository,
                case_working_context_service_cls=_CapturingCwcService,
            ).write_after_terminal_success(
                session=session,
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id=scope["run"].thread_id,
                run_id=scope["run"].id,
                final_state=_terminal_state(scope),
                final_response="退款单还在审核中。",
            )
            active_links = list(
                (
                    await session.execute(
                        select(ThreadCaseLink).where(
                            ThreadCaseLink.tenant_id == scope["tenant"].id,
                            ThreadCaseLink.case_id == scope["refund_case"].id,
                            ThreadCaseLink.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )

    assert write_result.status_ref.link_status == "deduped"
    assert write_result.status_ref.write_status == "written"
    assert len(active_links) == 1
    assert active_links[0].id == staff_link.id
    assert active_links[0].link_source == "staff_manual"
    assert active_links[0].linked_by_run_id is None
    assert len(_CapturingCwcService.calls) == 1


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
