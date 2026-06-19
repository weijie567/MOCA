import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.agent.graph import build_graph
from src.agent.schemas import IntentResultV3, RecommendationDraft, RiskAssessment, SlotExtractionResult
from src.agent.state import AgentState
from src.api.main import app
from src.auth.jwt import hash_password
from src.db.models import Base, Merchant, Order, PolicyChunk, PolicyDocument, RefundCase, Tenant, Ticket, User
from src.db.session import get_session
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.tools.catalog import ToolCatalog
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolResultV2
from src.tools.manager import UnifiedToolManager


TEST_DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"


async def _ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database
    if database_name is None or not database_name.replace("_", "").isalnum():
        raise RuntimeError(f"Unsafe test database name: {database_name!r}")

    maintenance_database = "postgres"
    try:
        connection = await asyncpg.connect(
            user=url.username,
            password=url.password,
            host=url.host or "localhost",
            port=url.port or 5432,
            database=maintenance_database,
        )
    except asyncpg.InvalidCatalogNameError:
        connection = await asyncpg.connect(
            user=url.username,
            password=url.password,
            host=url.host or "localhost",
            port=url.port or 5432,
            database="moca",
        )

    try:
        exists = await connection.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database_name)
        if not exists:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


@pytest.fixture
async def test_engine():
    await _ensure_test_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(test_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seeded_session(session: AsyncSession):
    now = datetime.now(UTC)
    demo_tenant = Tenant(id=uuid.uuid4(), name="test-tenant", status="active")
    other_tenant = Tenant(id=uuid.uuid4(), name="other-tenant", status="active")
    session.add_all([demo_tenant, other_tenant])
    await session.flush()

    merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=demo_tenant.id,
        merchant_name="Test Shop",
        category="electronics",
        risk_level="low",
    )
    other_merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        merchant_name="Other Shop",
        category="electronics",
        risk_level="low",
    )
    session.add_all([merchant, other_merchant])
    await session.flush()

    users = {
        "admin_user": User(
            id=uuid.uuid4(),
            tenant_id=demo_tenant.id,
            username="admin_user",
            password_hash=hash_password("moca2024"),
            role="admin",
            is_active=True,
        ),
        "cs_zhang": User(
            id=uuid.uuid4(),
            tenant_id=demo_tenant.id,
            username="cs_zhang",
            password_hash=hash_password("moca2024"),
            role="support",
            is_active=True,
        ),
        "approval_manager": User(
            id=uuid.uuid4(),
            tenant_id=demo_tenant.id,
            username="approval_manager",
            password_hash=hash_password("moca2024"),
            role="manager",
            is_active=True,
        ),
        "merchant_wang": User(
            id=uuid.uuid4(),
            tenant_id=demo_tenant.id,
            merchant_id=merchant.id,
            username="merchant_wang",
            password_hash=hash_password("moca2024"),
            role="merchant",
            is_active=True,
        ),
        "other_support": User(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            username="other_support",
            password_hash=hash_password("moca2024"),
            role="support",
            is_active=True,
        ),
    }
    session.add_all(users.values())
    await session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=demo_tenant.id,
        merchant_id=merchant.id,
        order_no="ORD-TEST-001",
        buyer_name="测试用户",
        item_name="蓝牙耳机",
        amount=Decimal("199.00"),
        currency="CNY",
        status="delivered",
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=3),
        delivered_at=now - timedelta(days=1),
    )
    other_order = Order(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        merchant_id=other_merchant.id,
        order_no="ORD-OTHER-001",
        buyer_name="其他租户用户",
        item_name="户外背包",
        amount=Decimal("399.00"),
        currency="CNY",
        status="delivered",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2),
        delivered_at=now - timedelta(days=1),
    )
    session.add_all([order, other_order])
    await session.flush()

    refund_case = RefundCase(
        id=uuid.uuid4(),
        tenant_id=demo_tenant.id,
        order_id=order.id,
        refund_case_no="RF-TEST-001",
        reason_code="damaged",
        reason_text="收到商品破损",
        status="reviewing",
        requested_amount=Decimal("199.00"),
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    session.add(refund_case)
    await session.flush()

    ticket = Ticket(
        id=uuid.uuid4(),
        tenant_id=demo_tenant.id,
        order_id=order.id,
        refund_case_id=refund_case.id,
        ticket_no="TK-TEST-001",
        channel="chat",
        status="open",
        summary="用户咨询退款进度",
        messages=[
            {"speaker": "user", "content": "为什么还没退款？"},
            {"speaker": "agent", "content": "正在核实物流签收情况。"},
        ],
    )
    session.add(ticket)
    await session.commit()
    return {
        "tenant": demo_tenant,
        "other_tenant": other_tenant,
        "merchant": merchant,
        "other_merchant": other_merchant,
        "users": users,
        "order": order,
        "other_order": other_order,
        "refund_case": refund_case,
        "ticket": ticket,
    }


@pytest.fixture
async def client(session: AsyncSession, seeded_session) -> AsyncIterator[AsyncClient]:
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient) -> Callable[[str, str], dict[str, str]]:
    async def _headers(username: str = "admin_user", password: str = "moca2024") -> dict[str, str]:
        response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
        token = response.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _headers


class _FakeStructuredLLM:
    def __init__(self, schema: type, responses: dict[str, dict[str, Any]]):
        self.schema = schema
        self.responses = responses

    async def ainvoke(self, messages):
        user_content = " ".join(
            str(message.get("content", "")) for message in messages if message.get("role") == "user"
        )
        if self.schema is IntentResultV3:
            key = "policy_qa" if "政策" in user_content or "规则" in user_content else "high_risk"
            return IntentResultV3(**self.responses["intent"][key])
        if self.schema is SlotExtractionResult:
            return SlotExtractionResult(**self.responses["slots"])
        if self.schema is RecommendationDraft:
            key = "high_risk" if "600" in user_content else "low_risk"
            return RecommendationDraft(**self.responses["recommendation"][key])
        if self.schema is RiskAssessment:
            key = "low_risk" if "policy_answer" in user_content else "high_risk"
            return RiskAssessment(**self.responses["risk"][key])
        raise AssertionError(f"Unexpected structured-output schema: {self.schema!r}")


class _FakeLLM:
    def __init__(self, responses: dict[str, dict[str, Any]]):
        self.responses = responses

    def with_structured_output(self, schema: type):
        return _FakeStructuredLLM(schema, self.responses)


@pytest.fixture
def mock_llm_responses() -> dict[str, dict[str, Any]]:
    evidence_ref = {
        "doc_key": "approval_refund_policy",
        "chunk_id": "approval_refund_policy#001",
        "title": "售后补偿政策",
        "section": "高风险补偿",
    }
    return {
        "intent": {
            "high_risk": {
                "schema_version": "intent_result.v3",
                "primary_intent": "compensation_suggestion",
                "requested_operation": "draft_action",
                "confidence": 0.98,
                "calibrated_confidence": 0.95,
                "secondary_intents": [],
                "required_slots": {
                    "all_of": ["action_type"],
                    "any_of": [["order_id", "refund_case_id", "ticket_id"]],
                    "optional": ["amount"],
                },
                "candidate_slots": {"order_id": "ORD-TEST-001", "action_type": "issue_coupon"},
                "routing_hints": {},
                "classifier_version": "intent_classifier.v2",
                "calibration_version": "calibration.unverified",
                "reason_codes": ["test_high_risk"],
            },
            "policy_qa": {
                "schema_version": "intent_result.v3",
                "primary_intent": "policy_qa",
                "requested_operation": "advise",
                "confidence": 0.97,
                "calibrated_confidence": 0.94,
                "secondary_intents": [],
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "candidate_slots": {},
                "routing_hints": {},
                "classifier_version": "intent_classifier.v2",
                "calibration_version": "calibration.unverified",
                "reason_codes": ["test_policy"],
            },
        },
        "slots": {
            "order_id": "ORD-TEST-001",
            "refund_case_id": "RF-TEST-001",
            "ticket_id": "TK-TEST-001",
            "issue_type": "compensation",
            "action_type": "issue_coupon",
        },
        "recommendation": {
            "high_risk": {
                "recommended_action": "issue_coupon",
                "reasoning_summary": "补偿超过500元需人工审批。",
                "evidence_refs": [evidence_ref],
                "confidence": 0.91,
                "risk_level": "high",
                "missing_info": [],
            },
            "low_risk": {
                "recommended_action": "policy_answer",
                "reasoning_summary": "补偿超过500元需人工审批。",
                "evidence_refs": [evidence_ref],
                "confidence": 0.9,
                "risk_level": "low",
                "missing_info": [],
            },
        },
        "risk": {
            "high_risk": {
                "risk_level": "high",
                "risk_reason": "Compensation amount exceeds threshold",
                "approval_required": True,
                "rule_ref": "HR-01",
            },
            "low_risk": {
                "risk_level": "low",
                "risk_reason": "Policy explanation only; no customer action proposed.",
                "approval_required": False,
                "rule_ref": "LR-01",
            },
        },
    }


async def _seed_approval_policy(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    policy_content = "补偿超过500元需人工审批。"
    policy_document = PolicyDocument(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        doc_key="approval_refund_policy",
        doc_type="refund_rule",
        title="售后补偿政策",
        effective_date=(datetime.now(UTC) - timedelta(days=30)).date(),
        risk_level="high",
        version=1,
        content=policy_content,
        source_type="test_fixture",
        source_checksum="test-approval-refund-policy-v1",
        parser_metadata_json={},
        policy_version_fingerprint="test-approval-refund-policy-v1",
    )
    session.add(policy_document)
    await session.flush()
    session.add(
        PolicyChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            doc_id=policy_document.id,
            chunk_id="approval_refund_policy#001",
            section="高风险补偿",
            content=policy_content,
            search_text=policy_content,
            source_block_refs_json=[],
            ocr_metadata_json={},
            risk_level="high",
            effective_date=policy_document.effective_date,
            embedding=None,
        )
    )
    await session.flush()


@pytest.fixture
async def mock_graph(monkeypatch, mock_llm_responses, session: AsyncSession, seeded_session):
    await _seed_approval_policy(session, seeded_session["tenant"].id)
    fake_llm = _FakeLLM(mock_llm_responses)

    import src.agent.nodes.assess_risk_and_approval as assess_node
    import src.agent.nodes.classify_intent as classify_node
    import src.agent.nodes.extract_slots as extract_node
    import src.agent.nodes.generate_recommendation as recommendation_node
    import src.agent.nodes.investigate as investigate_node

    monkeypatch.setattr(classify_node, "_get_llm", lambda: fake_llm)
    monkeypatch.setattr(extract_node, "_get_llm", lambda: fake_llm)
    monkeypatch.setattr(recommendation_node, "_get_llm", lambda: fake_llm)
    monkeypatch.setattr(assess_node, "_get_llm", lambda: fake_llm)

    monkeypatch.setattr(
        investigate_node.UnifiedToolManager,
        "with_defaults",
        lambda session: _ApprovalGraphToolManager(),
    )
    return build_graph(MemorySaver())


class _ApprovalGraphToolManager(UnifiedToolManager):
    def __init__(self):
        super().__init__(descriptors=ToolCatalog().descriptors())

    def descriptors(self, caller_node: str = "investigate"):
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist
            and descriptor.kind != "write"
            and descriptor.name in {"get_order", "search_policy"}
        ]

    def event_family(self, name: str) -> str:
        family = self._descriptors[name].event_family
        return "rag_retrieval" if family == "rag_retrieval_*" else "tool_call"

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name == "get_order":
            return self._order_result(args.get("order_no") or "ORD-TEST-001", ctx)
        if name == "get_refund_case":
            return self._refund_case_result(args.get("refund_case_no") or "RF-TEST-001", ctx)
        if name == "get_ticket":
            return self._ticket_result(args.get("ticket_id") or "TK-TEST-001", ctx)
        if name == "search_policy":
            return self._policy_result(ctx)
        raise AssertionError(f"Unexpected approval graph tool call: {name}")

    def _order_result(self, order_no: str, ctx: ToolCallContext) -> ToolResultV2:
        return ToolResultV2(
            status="success",
            data={"order_no": order_no, "status": "delivered", "amount": "199.00"},
            summary="order result",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[self._fact_ref(ctx.tenant_id, "order", order_no)],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

    def _refund_case_result(self, refund_case_no: str, ctx: ToolCallContext) -> ToolResultV2:
        return ToolResultV2(
            status="success",
            data={"refund_case_no": refund_case_no, "status": "reviewing", "requested_amount": "199.00"},
            summary="refund case result",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[self._fact_ref(ctx.tenant_id, "refund_case", refund_case_no)],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

    def _ticket_result(self, ticket_id: str, ctx: ToolCallContext) -> ToolResultV2:
        return ToolResultV2(
            status="success",
            data={"ticket_no": ticket_id, "status": "open", "summary": "用户咨询退款进度"},
            summary="ticket result",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[self._fact_ref(ctx.tenant_id, "ticket", ticket_id)],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

    def _policy_result(self, ctx: ToolCallContext) -> ToolResultV2:
        evidence = EvidenceRefV1.build(
            tenant_id=ctx.tenant_id,
            doc_key="approval_refund_policy",
            chunk_id="approval_refund_policy#001",
            policy_version="v1",
            text="补偿超过500元需人工审批。",
            retrieved_at=datetime.now(UTC).isoformat(),
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            score=0.93,
            rank=1,
        )
        return ToolResultV2(
            status="success",
            data={"retrieval_status": "strong_evidence", "best_score": 0.93, "threshold": 0.55},
            summary="policy found",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=[evidence],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

    @staticmethod
    def _fact_ref(tenant_id: str, resource_type: str, resource_id: str) -> BusinessFactRefV1:
        return BusinessFactRefV1(
            tenant_id=tenant_id,
            source_system="moca",
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=None,
            data_freshness_at=None,
            retrieved_at=datetime.now(UTC),
        )


@pytest.fixture
def approval_test_user(seeded_session) -> User:
    return seeded_session["users"]["approval_manager"]


@pytest.fixture
def agent_test_user(seeded_session) -> User:
    return seeded_session["users"]["cs_zhang"]


@pytest.fixture
def high_risk_state(seeded_session, agent_test_user) -> AgentState:
    return {
        "thread_id": "high-risk-fixture",
        "tenant_id": str(seeded_session["tenant"].id),
        "user_id": str(agent_test_user.id),
        "role": agent_test_user.role,
        "current_run_id": str(uuid.uuid4()),
        "current_intent": "refund_troubleshooting",
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "建议补偿600元 CNY。",
            "evidence_refs": [
                {
                    "doc_key": "approval_refund_policy",
                    "chunk_id": "approval_refund_policy#001",
                    "title": "售后补偿政策",
                    "section": "高风险补偿",
                }
            ],
            "confidence": 0.91,
            "risk_level": "high",
            "missing_info": [],
        },
        "business_context": {
            "order": {"order_no": "ORD-TEST-001", "status": "delivered"},
            "refund_case": {"refund_case_no": "RF-TEST-001", "requested_amount": "199.00"},
        },
        "risk_assessment": {
            "risk_level": "high",
            "risk_reason": "Compensation amount exceeds threshold",
            "approval_required": True,
            "rule_ref": "HR-01",
        },
        "proposed_action": {
            "action_type": "issue_coupon",
            "target_id": "RF-TEST-001",
            "amount": "600",
            "currency": "CNY",
            "reasoning_summary": "建议补偿600元 CNY。",
        },
        "trace_steps": [],
    }
