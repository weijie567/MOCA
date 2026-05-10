# MOCA

MOCA is a demo-first backend for merchant refund operations: FastAPI APIs, PostgreSQL + pgvector, Redis, tenant-scoped repositories, JWT auth, audit logging, and deterministic Chinese seed data.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

API docs: `http://localhost:8000/docs`

## Local Commands

```bash
make dev
make migrate
make seed
make test
make lint
```

## Demo Accounts

All seeded demo users share password `moca2024`.

- `admin_user` — admin
- `cs_zhang` — support
- `mgr_li` — manager
- `merchant_wang` — merchant
- `merchant_chen` — merchant

## Included in Phase 1

- Docker Compose for `postgres`, `redis`, and `api`
- Alembic migration for business tables and audit logs
- JWT login, `/api/v1/auth/me`, and demo-token support
- Repository-backed read APIs for orders, refund cases, and tickets
- Deterministic seed data with six core Chinese refund scenarios
- Integration test scaffold for health, auth, tenant isolation, and error format

## Current Status

Phase 1 establishes the operational foundation. Later phases add RAG retrieval, LangGraph orchestration, approval interrupts, frontend, and evaluation.
