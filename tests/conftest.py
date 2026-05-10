import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.main import app
from src.auth.jwt import hash_password
from src.db.models import Base, Merchant, Order, RefundCase, Tenant, Ticket, User
from src.db.session import get_session


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
