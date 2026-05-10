# Phase 1: Foundation — Validation Strategy

**Created:** 2026-05-09
**Phase:** 01-foundation

## 1. Environment Validation

- `docker compose up --build` starts postgres and api services
- All healthchecks pass within 60 seconds
- `curl http://localhost:8000/health` returns 200

## 2. Database Validation

- `alembic upgrade head` completes without errors
- All Phase 1 tables exist: tenants, users, roles, user_roles, merchants, orders, refund_cases, tickets, policy_documents, policy_chunks, audit_logs
- `uv run python scripts/seed_demo.py --reset` is idempotent — running twice produces identical state

## 3. Auth Validation

- POST /api/v1/auth/login with valid credentials returns access_token
- POST /api/v1/auth/login with wrong password returns 401
- POST /api/v1/auth/demo-token works when ENABLE_DEMO_AUTH=true
- POST /api/v1/auth/demo-token returns 403/404 when ENABLE_DEMO_AUTH is unset or false

## 4. RBAC Validation

- support role can GET /orders, /refund-cases, /tickets
- manager role has same read access as support
- merchant role can only see data linked to their merchant_id
- admin role can access all endpoints including admin-only APIs
- Any role accessing an endpoint beyond their permission gets 403

## 5. Tenant Isolation Validation

- User in tenant A cannot retrieve orders/refund_cases/tickets belonging to tenant B
- Repository layer enforces tenant_id filter on every query
- Attempting cross-tenant access returns empty result or 404 (not 403, to avoid information leakage)

## 6. Read Tool Validation

- GET /api/v1/orders/{id} returns order with relation_hints (has_active_refund, latest_refund_case_id, has_open_ticket, latest_ticket_id)
- GET /api/v1/refund-cases/{id} returns refund case with reason_code, reason_text, status, requested_amount
- GET /api/v1/tickets/{id} returns ticket with summary, channel, status

## 7. Error Contract Validation

- Request without Authorization header → `{"success": false, "error": {"code": "UNAUTHORIZED", ...}, "trace_id": "..."}`
- Request with invalid/expired token → 401 with unified format
- Request with insufficient role → `{"success": false, "error": {"code": "FORBIDDEN", ...}, "trace_id": "..."}`
- Request for non-existent resource → `{"success": false, "error": {"code": "ORDER_NOT_FOUND", ...}, "trace_id": "..."}`
- All error responses include trace_id

## 8. API Smoke Validation

- GET /health → 200
- GET /api/v1/auth/me with valid token → 200 with user info
- GET /api/v1/orders/ with valid token → 200 with paginated results
- GET /api/v1/refund-cases/ with valid token → 200
- GET /api/v1/tickets/ with valid token → 200

## 9. Test Validation

- `uv run pytest` passes all tests covering:
  - health check
  - login success / login failure
  - demo-token env gating
  - auth/me
  - 401 without token
  - 403 role denial
  - seed data query
  - tenant isolation
  - unified error format

## 10. Non-Goal Validation (Negative Scope)

Phase 1 does NOT require:
- Agent workflow or LangGraph integration
- RAG retrieval or embedding generation
- Redis usage beyond service startup
- Celery or background workers
- Frontend or UI
- agent_runs, agent_steps, approval_requests, approval_steps, llm_usage_events tables

---

*Phase: 01-foundation*
*Validation strategy created: 2026-05-09*
