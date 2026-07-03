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
from src.db.models import AgentRun, Base, CaseWorkingContext, Merchant, Order, RefundCase, Tenant, ThreadCaseLink, User
from src.memory.case_identity import CaseIdentityResult
from src.memory.case_working_context_lifecycle import (
    CaseWorkingContextLifecycleAdapter,
    TerminalProjectionResult,
    build_active_cwc_payload,
    project_terminal_write_candidate,
    skipped_status,
    trusted_case_ref_from_state,
)
from src.memory.case_working_context_schemas import CaseWorkingContextWriteCandidate
from src.memory.context_refs import CaseWorkingContextLifecycleStatusV1
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


def test_terminal_projection_result_contract() -> None:
    status_ref = skipped_status(reason_code="clarification_only")
    result = TerminalProjectionResult(candidate=None, status_ref=status_ref)

    assert set(TerminalProjectionResult.__annotations__) == {"candidate", "status_ref"}
    assert result.candidate is None
    assert isinstance(result.status_ref, CaseWorkingContextLifecycleStatusV1)


def test_project_terminal_write_candidate_returns_eligible_candidate_with_terminal_source_ref() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()

    projection = project_terminal_write_candidate(
        state={
            "user_query": "请帮我看一下这个退款单为什么还没处理",
            "active_slots": {"issue_type": "refund_status"},
            "tool_results": [{"tool_result_id": "tool-result-1", "summary": "退款单状态为 reviewing"}],
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
    assert [fact.text for fact in projection.candidate.content.verified_facts] == [
        "退款单状态为 reviewing",
        "订单已签收",
        "商家风险等级低",
    ]
    projected = repr(projection.candidate.content.model_dump(mode="json"))
    assert "raw data should not leak" not in projected
    assert "raw_payload should not leak" not in projected
    assert "raw_result should not leak" not in projected
    assert "policy raw body should not leak" not in projected


def test_project_terminal_write_candidate_policy_refs_use_identifiers_only() -> None:
    projection = project_terminal_write_candidate(
        state={
            "user_query": "查询退款政策",
            "tool_results": [{"summary": "退款单状态为 reviewing"}],
            "rag_context_bundle": {
                "evidence_refs": [
                    {
                        "doc_key": "refund-policy",
                        "chunk_id": "chunk-001",
                        "policy_version": "2026-07",
                        "text": "full policy evidence text should not leak",
                    },
                    {
                        "doc_id": "refund-sop",
                        "chunk_id": "chunk-002",
                        "version": "v3",
                        "evidence_text": "SOP evidence body should not leak",
                    },
                ]
            },
        },
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        expected_version=None,
        final_response="按政策继续审核。",
    )

    assert projection.candidate is not None
    assert [item.model_dump() for item in projection.candidate.content.policy_refs] == [
        {"doc_id": "refund-policy", "chunk_id": "chunk-001", "version": "2026-07"},
        {"doc_id": "refund-sop", "chunk_id": "chunk-002", "version": "v3"},
    ]
    projected = repr(projection.candidate.content.model_dump(mode="json"))
    assert "full policy evidence text should not leak" not in projected
    assert "SOP evidence body should not leak" not in projected


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
    state: dict[str, object] = {
        "user_query": "请帮我更新这个退款单的处理上下文",
        "active_slots": {
            "refund_case_id": scope["refund_case"].refund_case_no,
            "issue_type": "refund_status",
        },
        "tool_results": [{"tool_result_id": "terminal-tool-1", "summary": "退款单状态为 reviewing"}],
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
    unresolved = await CaseWorkingContextLifecycleAdapter(case_resolver=not_found_resolver).write_after_terminal_success(
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
