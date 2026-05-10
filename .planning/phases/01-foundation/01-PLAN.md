---
phase: 1
plan_id: "01"
title: "Project Scaffolding + Docker Compose + Database Layer"
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - Dockerfile
  - docker-entrypoint.sh
  - docker-compose.yml
  - .env.example
  - .gitignore
  - Makefile
  - alembic.ini
  - src/__init__.py
  - src/config.py
  - src/db/__init__.py
  - src/db/models.py
  - src/db/session.py
  - src/db/migrations/env.py
  - src/db/migrations/versions/001_initial_schema.py
autonomous: true
requirements: [DATA-01, DATA-02, DATA-03, DATA-06, DATA-07, DATA-08, INFR-01]
---

# Plan 01: Project Scaffolding + Docker Compose + Database Layer

<objective>
Set up the complete project skeleton: Python package with uv, Docker Compose (Postgres 16 + pgvector, Redis 7, FastAPI), SQLAlchemy 2.0 async models for all Phase 1 tables, Alembic migration, and pydantic-settings config.
</objective>

<tasks>

<task id="01-01">
<title>Create pyproject.toml with all Phase 1 dependencies</title>
<read_first>
- (none — greenfield)
</read_first>
<action>
Create `pyproject.toml` with:
- name: "moca"
- requires-python: ">=3.12"
- dependencies:
  - fastapi>=0.115
  - uvicorn[standard]>=0.30
  - sqlalchemy[asyncio]>=2.0
  - asyncpg>=0.29
  - alembic>=1.13
  - pydantic-settings>=2.0
  - pyjwt>=2.8
  - passlib[bcrypt]>=1.7
  - python-multipart>=0.0.9
  - redis>=5.0
  - pgvector>=0.3
- [project.optional-dependencies] dev:
  - pytest>=8.0
  - pytest-asyncio>=0.23
  - httpx>=0.27
  - ruff>=0.5
- [tool.ruff] line-length = 120, target-version = "py312"
- [tool.pytest.ini_options] asyncio_mode = "auto"
</action>
<acceptance_criteria>
- pyproject.toml contains `requires-python = ">=3.12"`
- pyproject.toml contains `fastapi>=0.115`
- pyproject.toml contains `sqlalchemy[asyncio]>=2.0`
- pyproject.toml contains `asyncpg>=0.29`
- pyproject.toml contains `pyjwt>=2.8`
- pyproject.toml contains `passlib[bcrypt]>=1.7`
- pyproject.toml contains `pgvector>=0.3`
- pyproject.toml contains `ruff>=0.5` under dev dependencies
- pyproject.toml contains `asyncio_mode = "auto"`
</acceptance_criteria>
</task>

<task id="01-02">
<title>Create Dockerfile for FastAPI service</title>
<read_first>
- pyproject.toml
</read_first>
<action>
Create `Dockerfile`:
- Base: python:3.12-slim
- Install uv via pip
- WORKDIR /app
- Copy pyproject.toml and uv.lock (if exists)
- RUN uv sync --frozen (or uv pip install -e .)
- Copy src/, scripts/, and alembic.ini
- COPY docker-entrypoint.sh /app/docker-entrypoint.sh
- RUN chmod +x /app/docker-entrypoint.sh
- EXPOSE 8000
- ENTRYPOINT ["/app/docker-entrypoint.sh"]
- CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

Create `docker-entrypoint.sh`:
```bash
#!/bin/bash
set -e
echo "Running migrations..."
uv run alembic upgrade head
echo "Migrations complete. Starting server..."
exec "$@"
```

This ensures migrations always run before the API starts (addresses review: "healthy API without schema").
</action>
<acceptance_criteria>
- Dockerfile contains `FROM python:3.12-slim`
- Dockerfile contains `EXPOSE 8000`
- Dockerfile contains `ENTRYPOINT`
- Dockerfile contains `docker-entrypoint.sh`
- docker-entrypoint.sh contains `alembic upgrade head`
- docker-entrypoint.sh contains `exec "$@"`
</acceptance_criteria>
</task>

<task id="01-03">
<title>Create docker-compose.yml with postgres, redis, api</title>
<read_first>
- Dockerfile
</read_first>
<action>
Create `docker-compose.yml` with 3 services:

postgres:
  image: pgvector/pgvector:pg16
  ports: ["5432:5432"]
  environment:
    POSTGRES_DB: moca
    POSTGRES_USER: moca
    POSTGRES_PASSWORD: moca_dev
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U moca"]
    interval: 5s, timeout: 5s, retries: 5
  volumes: [pgdata:/var/lib/postgresql/data]

redis:
  image: redis:7-alpine
  ports: ["6379:6379"]
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s, timeout: 5s, retries: 5

api:
  build: .
  ports: ["8000:8000"]
  depends_on:
    postgres: {condition: service_healthy}
    redis: {condition: service_healthy}
  environment:
    DATABASE_URL: postgresql+asyncpg://moca:moca_dev@postgres:5432/moca
    REDIS_URL: redis://redis:6379/0
    JWT_SECRET: dev-secret-change-in-prod
    ENABLE_DEMO_AUTH: "true"
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 10s, timeout: 5s, retries: 5, start_period: 30s

volumes:
  pgdata:
</action>
<acceptance_criteria>
- docker-compose.yml contains `pgvector/pgvector:pg16`
- docker-compose.yml contains `redis:7-alpine`
- docker-compose.yml contains `service_healthy`
- docker-compose.yml contains `DATABASE_URL: postgresql+asyncpg://moca:moca_dev@postgres:5432/moca`
- docker-compose.yml contains `ENABLE_DEMO_AUTH`
</acceptance_criteria>
</task>

<task id="01-04">
<title>Create .env.example, .gitignore, Makefile</title>
<read_first>
- docker-compose.yml
</read_first>
<action>
.env.example:
  DATABASE_URL=postgresql+asyncpg://moca:moca_dev@localhost:5432/moca
  REDIS_URL=redis://localhost:6379/0
  JWT_SECRET=dev-secret-change-in-prod
  JWT_EXPIRE_MINUTES=60
  ENABLE_DEMO_AUTH=true

.gitignore:
  __pycache__/, *.pyc, .env, .venv/, *.egg-info/, dist/, .ruff_cache/,
  .pytest_cache/, .coverage, htmlcov/, .DS_Store, pgdata/

Makefile targets:
  up: docker compose up --build
  down: docker compose down
  migrate: uv run alembic upgrade head
  seed: uv run python scripts/seed_demo.py --reset
  test: uv run pytest
  lint: uv run ruff check src/ tests/
  format: uv run ruff format src/ tests/
  dev: uv run fastapi dev src/api/main.py
</action>
<acceptance_criteria>
- .env.example contains `DATABASE_URL=postgresql+asyncpg://`
- .env.example contains `JWT_SECRET=`
- .env.example contains `ENABLE_DEMO_AUTH=true`
- .gitignore contains `__pycache__`
- .gitignore contains `.env`
- Makefile contains `docker compose up --build`
- Makefile contains `uv run alembic upgrade head`
- Makefile contains `uv run pytest`
</acceptance_criteria>
</task>

<task id="01-05">
<title>Create src/config.py with pydantic-settings</title>
<read_first>
- .env.example
</read_first>
<action>
Create `src/__init__.py` (empty).
Create `src/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-prod"
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    enable_demo_auth: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
```
</action>
<acceptance_criteria>
- src/config.py contains `class Settings(BaseSettings)`
- src/config.py contains `database_url: str`
- src/config.py contains `jwt_secret: str`
- src/config.py contains `enable_demo_auth: bool`
- src/config.py contains `settings = Settings()`
- src/__init__.py exists
</acceptance_criteria>
</task>

<task id="01-06">
<title>Create SQLAlchemy 2.0 async models for all Phase 1 tables</title>
<read_first>
- src/config.py
- .planning/ARCHITECTURE.md (Database Schema section, State Enumerations)
</read_first>
<action>
Create `src/db/__init__.py` (empty).
Create `src/db/models.py` with SQLAlchemy 2.0 declarative models:

Base = DeclarativeBase with uuid_pk mixin.

Tables (all with tenant_id FK except tenants):
- Tenant: id(UUID PK), name(String), status(String, default="active"), created_at
- User: id(UUID PK), tenant_id(FK), username(String unique per tenant), password_hash(String), role(String, one of: support/manager/merchant/admin), merchant_id(FK nullable, set when role=merchant), is_active(bool), created_at
- Merchant: id(UUID PK), tenant_id(FK), merchant_name(String), category(String), risk_level(String default="low"), created_at
- Order: id(UUID PK), tenant_id(FK), merchant_id(FK), order_no(String), amount(Numeric(12,2)), product_name(String), status(String default="pending"), created_at, delivered_at(nullable)
- RefundCase: id(UUID PK), tenant_id(FK), order_id(FK), refund_case_no(String), reason_code(String), reason_text(String), status(String default="submitted"), requested_amount(Numeric(12,2)), created_at
- Ticket: id(UUID PK), tenant_id(FK), order_id(FK), refund_case_id(FK nullable), channel(String), status(String default="open"), summary(Text), created_at
- PolicyDocument: id(UUID PK), tenant_id(FK), doc_type(String), title(String), effective_date(Date), risk_level(String), version(Integer default=1), created_at
- PolicyChunk: id(UUID PK), tenant_id(FK), doc_id(FK), chunk_id(String), section(String), content(Text), risk_level(String), effective_date(Date), embedding(Vector(1536) nullable)
- AuditLog: id(UUID PK), tenant_id(FK), user_id(FK nullable), role(String nullable), action(String), resource_type(String), resource_id(String nullable), trace_id(String), created_at

Note: Phase 1 uses a single `role` column on `users` instead of a separate roles/user_roles join table. This keeps the JWT claim (`role`) consistent with the DB state. If dynamic RBAC is needed in v2, a permissions table can be added then.

All UUID PKs use `server_default=text("gen_random_uuid()")`.
All created_at use `server_default=func.now()`.
Indexes: tenant_id on all tables, order_no on orders, refund_case_no on refund_cases.
</action>
<acceptance_criteria>
- src/db/models.py contains `class Tenant`
- src/db/models.py contains `class User`
- src/db/models.py contains `role: Mapped[str]` on User model
- src/db/models.py contains `merchant_id` on User model
- src/db/models.py contains `class Merchant`
- src/db/models.py contains `class Order`
- src/db/models.py contains `class RefundCase`
- src/db/models.py contains `class Ticket`
- src/db/models.py contains `class PolicyDocument`
- src/db/models.py contains `class PolicyChunk`
- src/db/models.py contains `class AuditLog`
- src/db/models.py contains `Numeric(12, 2)`
- src/db/models.py contains `Vector`
- src/db/models.py contains `tenant_id`
</acceptance_criteria>
</task>

<task id="01-07">
<title>Create async session factory</title>
<read_first>
- src/config.py
- src/db/models.py
</read_first>
<action>
Create `src/db/session.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```
</action>
<acceptance_criteria>
- src/db/session.py contains `create_async_engine`
- src/db/session.py contains `async_sessionmaker`
- src/db/session.py contains `async def get_session`
- src/db/session.py contains `settings.database_url`
</acceptance_criteria>
</task>

<task id="01-08">
<title>Set up Alembic with async support and initial migration</title>
<read_first>
- src/db/models.py
- src/db/session.py
</read_first>
<action>
Create `alembic.ini` pointing to src/db/migrations.
Create `src/db/migrations/` directory with:
- env.py: configured for async (run_async_migrations pattern), imports all models from src.db.models, uses settings.database_url
- script.py.mako: standard template
- versions/001_initial_schema.py: auto-generated migration creating all 11 Phase 1 tables with proper columns, constraints, indexes

The migration must:
- CREATE EXTENSION IF NOT EXISTS vector (for pgvector)
- Create all tables with correct types
- Add indexes on tenant_id columns
- Add unique constraints (username per tenant, order_no, refund_case_no)
</action>
<acceptance_criteria>
- alembic.ini exists and contains `script_location = src/db/migrations`
- src/db/migrations/env.py contains `run_async_migrations`
- src/db/migrations/env.py contains `from src.db.models import`
- src/db/migrations/versions/ contains at least one .py file
- Migration file contains `CREATE EXTENSION` or `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`
- Migration file contains `op.create_table("tenants"`
- Migration file contains `op.create_table("audit_logs"`
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv sync` installs all dependencies without errors
- `docker compose up -d postgres redis` starts both services with healthy status
- `uv run alembic upgrade head` creates all 9 tables
- `docker compose up --build` starts all 3 services; entrypoint runs migrations; /health returns 200
</verification>

<must_haves>
- Docker Compose starts Postgres (pgvector), Redis, and FastAPI with healthchecks
- Entrypoint runs `alembic upgrade head` before API starts
- All 9 Phase 1 tables created via Alembic migration
- Every table (except tenants) has tenant_id column
- User model has single `role` column (no separate roles/user_roles tables)
- Monetary fields use DECIMAL(12,2)
- pgvector extension enabled
</must_haves>

<threat_model>
| Threat | Severity | Mitigation |
|--------|----------|-----------|
| DB credentials in docker-compose.yml | Medium | Dev-only defaults; .env.example documents; .gitignore excludes .env |
| JWT_SECRET hardcoded default | Medium | Default is clearly marked "dev-secret-change-in-prod"; config loads from env |
| SQL injection via raw queries | High | SQLAlchemy ORM only; no raw SQL in application code |
| Postgres exposed on 5432 | Low | Dev environment only; production uses internal networking |
</threat_model>
