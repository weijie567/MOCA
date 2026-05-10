# Phase 1: Foundation — Research

**Researched:** 2026-05-09
**Status:** Complete

## 1. Technology Stack & Versions

| Component | Choice | Notes |
|-----------|--------|-------|
| Python | 3.12 | Per D-03 |
| Package manager | uv | Per D-03 |
| Web framework | FastAPI 0.115+ | Async, Pydantic v2 native |
| ORM | SQLAlchemy 2.0 (async) | `mapped_column`, `AsyncSession` |
| Migrations | Alembic | async-compatible with `asyncpg` |
| DB driver | asyncpg | Fastest async PostgreSQL driver |
| PostgreSQL | 16 + pgvector | Docker image: `pgvector/pgvector:pg16` |
| Redis | 7-alpine | Phase 1 only starts, minimal use |
| Auth | PyJWT + passlib[bcrypt] | JWT creation/validation + password hashing |
| Testing | pytest + pytest-asyncio + httpx | `AsyncClient` for API tests |
| Linter/Formatter | ruff | Per D-03 |
| Settings | pydantic-settings | `.env` loading, type validation |

## 2. Database Schema — Phase 1 Scope

### Tables to build (per D-05)

| Table | Key Fields | Notes |
|-------|-----------|-------|
| tenants | id, name, status | Status enum: active, suspended |
| users | id, tenant_id, username, password_hash, is_active | Password stored as bcrypt hash |
| roles | id, name | Fixed enum: support, manager, merchant, admin |
| user_roles | id, user_id, role_id | Many-to-many |
| merchants | id, tenant_id, merchant_name, category, risk_level | risk_level: low/medium/high |
| orders | id, tenant_id, merchant_id, order_no, amount(DECIMAL 12,2), status, product_name, created_at, delivered_at | Status enum per ARCHITECTURE.md |
| refund_cases | id, tenant_id, order_id, refund_case_no, reason_code, reason_text, status, requested_amount, created_at | Status enum per ARCHITECTURE.md |
| tickets | id, tenant_id, order_id, refund_case_id, channel, status, summary, created_at | Status enum per ARCHITECTURE.md |
| policy_documents | id, tenant_id, doc_type, title, effective_date, risk_level, version | doc_type enum per ARCHITECTURE.md |
| policy_chunks | id, tenant_id, doc_id, chunk_id, section, content, risk_level, effective_date, embedding(vector) | embedding column present but unused until Phase 2 |
| audit_logs | id, tenant_id, user_id, role, action, resource_type, resource_id, trace_id, created_at | Lightweight per D-08 |

### Tables NOT built in Phase 1 (per D-05)

- agent_runs, agent_steps → Phase 3
- approval_requests, approval_steps → Phase 4
- llm_usage_events → Phase 3

### Requirement Mapping Conflict

REQUIREMENTS.md maps DATA-04 (agent_runs/agent_steps), DATA-05 (approval_requests/approval_steps), DATA-06 (audit_logs/llm_usage_events) all to Phase 1. However, CONTEXT.md D-05 (user decision from discuss-phase) explicitly defers agent runtime tables to Phase 3.

**Resolution:** CONTEXT.md user decisions take precedence. Phase 1 builds audit_logs only from DATA-06. DATA-04 and DATA-05 are deferred. The planner should note this deviation and mark those REQ-IDs as partially addressed (audit_logs portion) or deferred.

## 3. Auth Implementation

### Login Flow (D-02)

```
POST /api/v1/auth/login
  Body: {"username": "...", "password": "..."}
  Response: {"access_token": "...", "token_type": "bearer"}

GET /api/v1/auth/me
  Header: Authorization: Bearer <token>
  Response: {"id": "...", "username": "...", "role": "...", "tenant_id": "..."}

POST /api/v1/auth/demo-token
  Only when ENABLE_DEMO_AUTH=true
  Body: {"username": "...", "role": "..."}
  Response: {"access_token": "..."}
```

### JWT Payload

```json
{
  "sub": "<user_id>",
  "username": "admin_user",
  "role": "admin",
  "tenant_id": "<tenant_uuid>",
  "exp": 1234567890
}
```

### RBAC Dependencies (D-07)

```python
# FastAPI dependency pattern
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User: ...
def require_roles(allowed: list[str]) -> Callable: ...

# Usage
@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, user: User = Depends(require_roles(["support", "manager", "admin"]))): ...
```

### Role Permissions

| Role | Orders | Refund Cases | Tickets | Admin APIs |
|------|--------|-------------|---------|-----------|
| support | Read all | Read all | Read all | No |
| manager | Read all | Read all + approve | Read all | No |
| merchant | Own merchant only | Own merchant only | Own merchant only | No |
| admin | All | All | All | Yes |

## 4. Repository Pattern

### Base Class Design

```python
class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> T | None:
        # Always filter by tenant_id
        ...

    async def list(self, tenant_id: UUID, **filters) -> list[T]:
        ...
```

Key principles:
- Every query method requires `tenant_id` parameter (D-06)
- merchant role additionally filters by `merchant_id`
- Never expose raw session to tools/routers
- Return domain models, not ORM instances

## 5. API Endpoints — Phase 1

### Auth Router (`/api/v1/auth/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /login | None | Username + password login |
| GET | /me | Bearer | Current user info |
| POST | /demo-token | None (env-gated) | Quick token for dev |

### Orders Router (`/api/v1/orders/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /{order_id} | support, manager, merchant, admin | Get order with relation_hints |
| GET | / | support, manager, admin | List orders (paginated) |

### Refund Cases Router (`/api/v1/refund-cases/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /{refund_case_id} | support, manager, merchant, admin | Get refund case |
| GET | / | support, manager, admin | List refund cases |

### Tickets Router (`/api/v1/tickets/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /{ticket_id} | support, manager, merchant, admin | Get ticket with history |
| GET | / | support, manager, admin | List tickets |

### Health (`/health`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Service health + DB connectivity |

## 6. Unified Response Format (D-10)

```python
# Success
{"success": True, "data": {...}, "trace_id": "..."}

# Error
{"success": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Order not found", "details": {}}, "trace_id": "..."}
```

Implementation: FastAPI exception handlers + response model wrapper.

## 7. Tool Return Structure (D-11)

### get_order response

```json
{
  "id": "uuid",
  "order_no": "ORD-2024-001",
  "merchant_name": "星河数码旗舰店",
  "product_name": "蓝牙降噪耳机 Pro",
  "amount": 599.00,
  "status": "delivered",
  "created_at": "...",
  "delivered_at": "...",
  "relation_hints": {
    "has_active_refund": true,
    "latest_refund_case_id": "uuid",
    "has_open_ticket": false,
    "latest_ticket_id": null
  }
}
```

### get_refund_case response

```json
{
  "id": "uuid",
  "refund_case_no": "RF-2024-001",
  "order_id": "uuid",
  "reason_code": "damaged_goods",
  "reason_text": "收到商品破损",
  "status": "submitted",
  "requested_amount": 599.00,
  "created_at": "..."
}
```

### get_ticket_history response

```json
{
  "id": "uuid",
  "order_id": "uuid",
  "refund_case_id": "uuid",
  "channel": "online_chat",
  "status": "open",
  "summary": "客户反映收到的耳机外壳有明显裂痕",
  "created_at": "..."
}
```

## 8. Seed Data Strategy (D-01, D-13)

### 6 Business Scenarios

| # | Scenario | Order Status | Refund Status | Key Feature |
|---|----------|-------------|---------------|-------------|
| 1 | 未发货退款 | pending/paid | submitted | Simple case, auto-approvable |
| 2 | 签收后破损 | delivered | reviewing | Needs evidence (photos) |
| 3 | 虚拟商品不支持退款 | completed | rejected | Policy-based denial |
| 4 | 超售后期 | delivered | closed | Time-based rule |
| 5 | 高金额需审批 | delivered | submitted | Amount > threshold |
| 6 | 多次异常退款 | delivered | submitted | Risk pattern detection |

### Data Volume (per INFR-02 success criteria)

- 80+ orders (6 scenarios × ~14 orders each, varying merchants)
- 30+ refund cases
- 15+ policy documents/chunks
- 12+ users (across 4 roles, 2+ tenants)
- 5+ merchants

### UUID v5 Strategy

```python
MOCA_NAMESPACE = uuid.UUID("a1b2c3d4-...")  # Fixed namespace for project
tenant_id = uuid.uuid5(MOCA_NAMESPACE, "demo-tenant")
user_id = uuid.uuid5(MOCA_NAMESPACE, "user:admin_user")
order_id = uuid.uuid5(MOCA_NAMESPACE, "order:ORD-2024-001")
```

### Reset Command

```bash
uv run python scripts/seed_demo.py --reset
# 1. DELETE FROM ... WHERE tenant_id = demo_tenant_id (cascade)
# 2. Re-insert tenants, users, roles
# 3. Re-insert merchants, orders, refund_cases, tickets
# 4. Re-insert policy_documents, policy_chunks
```

## 9. Docker Compose Architecture (D-09)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: moca
      POSTGRES_USER: moca
      POSTGRES_PASSWORD: moca_dev
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moca"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+asyncpg://moca:moca_dev@postgres:5432/moca
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: dev-secret-change-in-prod
      ENABLE_DEMO_AUTH: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  pgdata:
```

## 10. Testing Strategy (D-12)

### Test Infrastructure

- `pytest-asyncio` for async test support
- `httpx.AsyncClient` for API integration tests
- Separate test database (or transaction rollback per test)
- `conftest.py` provides: test client, test db session, auth tokens for each role

### Required Test Cases (D-12)

1. Health check returns 200
2. Login success with valid credentials
3. Login failure with wrong password
4. demo-token disabled when ENABLE_DEMO_AUTH != "true"
5. GET /auth/me returns current user
6. Protected endpoint without token → 401
7. Endpoint with insufficient role → 403
8. Seed orders query returns data
9. Tenant isolation: user A cannot see user B's tenant data
10. Error responses match unified format

## 11. Observability — Phase 1 Scope (INFR-04, INFR-05)

Phase 1 implements lightweight observability:

- **trace_id**: Generated per request via middleware, included in all responses and audit_logs
- **audit_logs**: Record API operations (action, resource_type, resource_id, user_id, tenant_id)
- **Tool call logging**: Each tool endpoint logs to audit_logs with latency_ms and status
- **No agent_runs/agent_steps** — deferred to Phase 3

Implementation: FastAPI middleware generates trace_id → stored in request state → passed to repository layer → written to audit_logs.

## 12. Key Dependencies (pyproject.toml)

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.0",
    "pyjwt>=2.8",
    "passlib[bcrypt]>=1.7",
    "python-multipart>=0.0.9",
    "redis>=5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.5",
]
```

## 13. Migration Strategy

- Alembic with async support (`sqlalchemy.ext.asyncio`)
- Single initial migration creates all Phase 1 tables
- `alembic upgrade head` runs in Docker entrypoint or manually
- Seed script runs after migrations

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| pgvector extension not auto-installed | DB startup fails | Use `pgvector/pgvector:pg16` image (pre-installed) |
| Async SQLAlchemy complexity | Dev velocity | Start with simple patterns, avoid eager loading |
| UUID v5 collisions | Data integrity | Use unique string inputs per entity type |
| Docker healthcheck timing | Flaky startup | Conservative intervals + retries |
| Alembic + async driver | Migration errors | Use sync engine for migrations only |

## 15. Implementation Order Recommendation

1. **Project scaffolding** — pyproject.toml, Docker Compose, .env.example, .gitignore, Makefile
2. **Database layer** — SQLAlchemy models, Alembic migration, session factory
3. **Auth system** — JWT, login endpoint, dependencies, RBAC
4. **Repository layer** — Base class, order/refund/ticket repos with tenant scoping
5. **API endpoints** — Routers for orders, refund_cases, tickets with unified response
6. **Seed script** — 6 scenarios, deterministic UUIDs, reset capability
7. **Audit logging** — Middleware for trace_id, audit_logs writes
8. **Testing** — conftest, all D-12 test cases
9. **README** — Per D-14, concise version

---

## RESEARCH COMPLETE

*Phase 1 research covers all 19 mapped requirements. Key finding: DATA-04/DATA-05/partial DATA-06 are deferred per user decision D-05, reducing Phase 1 DB scope to business tables + audit_logs only.*
