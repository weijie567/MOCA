---
phase: 1
plan_id: "05"
title: "Integration Tests + README"
wave: 3
depends_on: ["01", "02", "03", "04"]
files_modified:
  - tests/__init__.py
  - tests/conftest.py
  - tests/integration/__init__.py
  - tests/integration/test_health.py
  - tests/integration/test_auth.py
  - tests/integration/test_orders.py
  - tests/integration/test_refund_cases.py
  - tests/integration/test_tickets.py
  - tests/integration/test_tenant_isolation.py
  - tests/integration/test_error_format.py
  - README.md
autonomous: true
requirements: [INFR-04, INFR-05]
---

# Plan 05: Integration Tests + README

<objective>
Create the test infrastructure (conftest with async client, test DB, auth helpers) and all required D-12 test cases. Write a concise README per D-14.
</objective>

<tasks>

<task id="05-01">
<title>Create test conftest with async client and auth fixtures</title>
<read_first>
- src/api/main.py
- src/db/session.py
- src/auth/jwt.py
- src/db/models.py
</read_first>
<action>
Create `tests/__init__.py` (empty).
Create `tests/integration/__init__.py` (empty).
Create `tests/conftest.py`:

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from src.api.main import app
from src.db.session import get_session
from src.db.models import Base
from src.auth.jwt import create_access_token, hash_password

TEST_DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    # Use Alembic-style setup: create extension + tables via migration
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def seeded_session(session):
    """Seed real users into test DB for auth testing."""
    from src.db.models import Tenant, User, Merchant
    import uuid

    tenant = Tenant(id=uuid.uuid4(), name="test-tenant", status="active")
    session.add(tenant)

    merchant = Merchant(id=uuid.uuid4(), tenant_id=tenant.id, merchant_name="Test Shop", category="electronics", risk_level="low")
    session.add(merchant)

    users = {
        "admin": User(id=uuid.uuid4(), tenant_id=tenant.id, username="admin_user", password_hash=hash_password("moca2024"), role="admin", is_active=True),
        "support": User(id=uuid.uuid4(), tenant_id=tenant.id, username="cs_zhang", password_hash=hash_password("moca2024"), role="support", is_active=True),
        "manager": User(id=uuid.uuid4(), tenant_id=tenant.id, username="mgr_li", password_hash=hash_password("moca2024"), role="manager", is_active=True),
        "merchant": User(id=uuid.uuid4(), tenant_id=tenant.id, username="merchant_wang", password_hash=hash_password("moca2024"), role="merchant", merchant_id=merchant.id, is_active=True),
    }
    for u in users.values():
        session.add(u)
    await session.flush()

    return {"tenant": tenant, "merchant": merchant, "users": users}

@pytest.fixture
async def client(session):
    async def override_get_session():
        yield session
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
async def auth_token(client, seeded_session):
    """Get real auth tokens by calling login endpoint with seeded users."""
    async def _get_token(username: str = "admin_user", password: str = "moca2024"):
        response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
        return response.json()["data"]["access_token"]
    return _get_token
```

Key changes from review feedback:
- pgvector extension created explicitly before tables
- Real users seeded in test DB (not fabricated tokens)
- auth_token fixture uses real login flow
- Tests exercise the full auth path (DB lookup in get_current_user)
</action>
<acceptance_criteria>
- tests/conftest.py contains `AsyncClient`
- tests/conftest.py contains `ASGITransport`
- tests/conftest.py contains `CREATE EXTENSION IF NOT EXISTS vector`
- tests/conftest.py contains `seeded_session`
- tests/conftest.py contains `hash_password`
- tests/conftest.py contains `auth_token`
- tests/conftest.py contains `client.post("/api/v1/auth/login"`
- tests/conftest.py contains `moca_test`
- tests/conftest.py contains `Base.metadata.create_all`
</acceptance_criteria>
</task>

<task id="05-02">
<title>Create health check test</title>
<read_first>
- src/api/main.py
- tests/conftest.py
</read_first>
<action>
Create `tests/integration/test_health.py`:

```python
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "trace_id" in data
```
</action>
<acceptance_criteria>
- tests/integration/test_health.py contains `async def test_health_returns_200`
- tests/integration/test_health.py contains `response.status_code == 200`
- tests/integration/test_health.py contains `trace_id`
</acceptance_criteria>
</task>

<task id="05-03">
<title>Create auth tests (login success/failure, me, demo-token)</title>
<read_first>
- src/api/routers/auth.py
- tests/conftest.py
</read_first>
<action>
Create `tests/integration/test_auth.py`:

Tests:
1. test_login_success: seed a user, POST /api/v1/auth/login with correct password → 200 + access_token
2. test_login_failure: POST /api/v1/auth/login with wrong password → 401 + unified error format
3. test_me_success: GET /api/v1/auth/me with valid token → 200 + user info
4. test_me_without_token: GET /api/v1/auth/me without Authorization → 401
5. test_demo_token_enabled: with ENABLE_DEMO_AUTH=true, POST /api/v1/auth/demo-token → 200
6. test_demo_token_disabled: with ENABLE_DEMO_AUTH=false, POST /api/v1/auth/demo-token → 403

Each test asserts:
- Correct status code
- Response matches ApiResponse schema (success, data/error, trace_id)
</action>
<acceptance_criteria>
- tests/integration/test_auth.py contains `test_login_success`
- tests/integration/test_auth.py contains `test_login_failure`
- tests/integration/test_auth.py contains `test_me_success`
- tests/integration/test_auth.py contains `test_me_without_token`
- tests/integration/test_auth.py contains `test_demo_token`
- tests/integration/test_auth.py contains `status_code == 401`
- tests/integration/test_auth.py contains `trace_id`
</acceptance_criteria>
</task>

<task id="05-04">
<title>Create RBAC and tenant isolation tests</title>
<read_first>
- src/api/routers/orders.py
- src/auth/permissions.py
- tests/conftest.py
</read_first>
<action>
Create `tests/integration/test_orders.py`:
- test_get_order_success: support role gets order → 200
- test_list_orders_success: admin role lists orders → 200 with items
- test_role_forbidden: create a token with no valid role, access orders → 403

Create `tests/integration/test_tenant_isolation.py`:
- test_tenant_isolation: user in tenant A cannot see tenant B's orders
  - Seed order in tenant A
  - Request with tenant B token → 404 (not found, not forbidden)
- test_merchant_isolation: merchant user cannot see other merchant's orders

Create `tests/integration/test_error_format.py`:
- test_401_format: missing token → {"success": false, "error": {"code": "UNAUTHORIZED", ...}, "trace_id": "..."}
- test_403_format: insufficient role → {"success": false, "error": {"code": "FORBIDDEN", ...}, "trace_id": "..."}
- test_404_format: non-existent order → {"success": false, "error": {"code": "ORDER_NOT_FOUND", ...}, "trace_id": "..."}
- test_all_errors_have_trace_id: verify trace_id present in all error responses
</action>
<acceptance_criteria>
- tests/integration/test_orders.py contains `test_get_order_success`
- tests/integration/test_orders.py contains `test_role_forbidden`
- tests/integration/test_tenant_isolation.py contains `test_tenant_isolation`
- tests/integration/test_tenant_isolation.py contains `test_merchant_isolation`
- tests/integration/test_error_format.py contains `test_401_format`
- tests/integration/test_error_format.py contains `test_403_format`
- tests/integration/test_error_format.py contains `test_404_format`
- tests/integration/test_error_format.py contains `trace_id`
</acceptance_criteria>
</task>

<task id="05-05">
<title>Create concise README</title>
<read_first>
- .planning/phases/01-foundation/01-CONTEXT.md (D-14: README scope)
- docker-compose.yml
- .env.example
</read_first>
<action>
Create `README.md` (max 100 lines):

```markdown
# MOCA — Multi-tenant Order & Customer Agent

AI-powered refund assistant with evidence-based reasoning, approval workflows, and full audit trail.

## Quick Start

```bash
# Start services
docker compose up --build

# Run migrations
uv run alembic upgrade head

# Seed demo data
uv run python scripts/seed_demo.py --reset

# Run tests
uv run pytest
```

## Demo Accounts

| Username | Role | Password |
|----------|------|----------|
| admin_user | admin | moca2024 |
| cs_zhang | support | moca2024 |
| mgr_li | manager | moca2024 |
| merchant_wang | merchant | moca2024 |

## API

Base URL: http://localhost:8000

- POST /api/v1/auth/login — Get JWT token
- GET /api/v1/auth/me — Current user
- GET /api/v1/orders/{id} — Order with relation hints
- GET /api/v1/refund-cases/{id} — Refund case
- GET /api/v1/tickets/{id} — Ticket history
- GET /health — Service health

Swagger UI: http://localhost:8000/docs

## Architecture

- FastAPI + SQLAlchemy 2.0 (async)
- PostgreSQL 16 + pgvector
- JWT auth with role-based access control
- Multi-tenant with application-layer isolation
- Repository pattern for data access

## Current Status

Phase 1 (Foundation) — Infrastructure, auth, seed data, read APIs.

## Development

```bash
# Local dev (without Docker)
uv run fastapi dev src/api/main.py

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

## Note

Multi-tenant isolation uses application-layer tenant_id filtering.
Production deployment should upgrade to PostgreSQL Row-Level Security.
```
</action>
<acceptance_criteria>
- README.md contains `# MOCA`
- README.md contains `docker compose up`
- README.md contains `uv run alembic upgrade head`
- README.md contains `seed_demo.py --reset`
- README.md contains `admin_user`
- README.md contains `moca2024`
- README.md contains `/api/v1/auth/login`
- README.md contains `localhost:8000/docs`
- README.md is under 100 lines
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run pytest` passes all tests (health, auth, RBAC, tenant isolation, error format)
- README.md renders correctly and contains all required sections
- Test coverage includes all D-12 required test cases
</verification>

<must_haves>
- All D-12 test cases pass
- Test infrastructure supports async + test DB + auth fixtures
- Tenant isolation verified (cross-tenant returns 404)
- Unified error format verified across all error types
- README under 100 lines with quick start, demo accounts, API list
</must_haves>

<threat_model>
| Threat | Severity | Mitigation |
|--------|----------|-----------|
| Test DB credentials exposed | Low | Test DB is local dev only; same credentials as dev compose |
| README exposes default passwords | Low | Clearly marked as demo; not production credentials |
</threat_model>
