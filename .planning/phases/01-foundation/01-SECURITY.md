---
phase: 1
slug: foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-10
---

# Phase 1 - Foundation Security

Per-phase security verification for MOCA Phase 1. Scope is limited to the declared threat register entries T-01-01 through T-01-14.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Developer machine to Docker services | Local FastAPI, Postgres, and Redis compose stack | Dev credentials, JWT secret, demo data |
| API client to FastAPI | Login and read-tool API requests | Credentials, bearer tokens, tenant-scoped business data |
| FastAPI to database | SQLAlchemy async session and repositories | Orders, refund cases, tickets, users, audit logs |
| Seed script to database | Demo reset and deterministic seed writes | Demo tenants, users, orders, refunds, tickets, policies |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-01 | Config/Secrets | docker-compose.yml | mitigate | Dev-only defaults documented in `.env.example`; `.env` ignored | closed | `docker-compose.yml:9`, `.env.example:1`, `.gitignore:3` |
| T-01-02 | Config/Secrets | src/config.py | mitigate | Default JWT secret is marked as dev; settings load from `.env` | closed | `src/config.py:8`, `src/config.py:15` |
| T-01-03 | Tampering/Injection | repository/application DB access | mitigate | Application queries use SQLAlchemy expressions; no raw SQL found in repositories/read routers | closed | `src/repositories/base.py:20`, `src/repositories/order_repo.py:15`, `src/repositories/refund_repo.py:15`, `src/repositories/ticket_repo.py:15` |
| T-01-04 | Network Exposure | docker-compose.yml Postgres port | accept | Accepted for local dev compose; production must use internal networking | closed | Accepted risk AR-01 |
| T-01-05 | Authentication | auth login endpoint | accept | Accepted for Phase 1; Phase 2+ must add Redis-backed rate limiting | closed | Accepted risk AR-02 |
| T-01-06 | Config/Secrets | JWT config | mitigate | JWT secret is loaded from settings/env; `.env` ignored | closed | `src/config.py:8`, `src/auth/jwt.py:26`, `.gitignore:3` |
| T-01-07 | Session/Auth | JWT token lifecycle | accept | Accepted for demo context with 60 minute default token expiry | closed | Accepted risk AR-03 |
| T-01-08 | Transport/Auth | login request body | accept | Accepted for localhost/dev; production requires HTTPS termination | closed | Accepted risk AR-04 |
| T-01-09 | Authentication | password verification | mitigate | Password verification uses bcrypt `checkpw` | closed | `src/auth/jwt.py:33`, `src/auth/jwt.py:34`, `src/api/routers/auth.py:27` |
| T-01-10 | Authorization/IDOR | repositories and read APIs | mitigate | Repository lookups include tenant filters; cross-tenant order test expects 404 | closed | `src/repositories/base.py:20`, `src/repositories/order_repo.py:15`, `src/repositories/refund_repo.py:17`, `src/repositories/ticket_repo.py:15`, `tests/integration/test_tenant_isolation.py:9` |
| T-01-11 | Authorization | merchant read APIs | mitigate | Routers check merchant ownership before returning data | closed | `src/api/routers/orders.py:31`, `src/api/routers/refund_cases.py:49`, `src/api/routers/tickets.py:47` |
| T-01-12 | Audit/Repudiation | tool read endpoints | mitigate | Read endpoints call `AuditRepository.record_tool_call` | closed | `src/api/routers/orders.py:37`, `src/api/routers/orders.py:52`, `src/api/routers/refund_cases.py:32`, `src/api/routers/refund_cases.py:55`, `src/api/routers/tickets.py:32`, `src/api/routers/tickets.py:53` |
| T-01-13 | Data Safety | scripts/seed_demo.py | accept | `demo` and `other` tenants are synthetic demo data owned by the seed script; reset clears all seeded state by design | closed | Accepted risk AR-06 |
| T-01-14 | Demo Credentials | scripts/seed_demo.py README.md tests | accept | Accepted for demo/local context only; production requires non-default credentials and random IDs | closed | Accepted risk AR-05 |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-04 | Postgres `5432` is exposed only by the local development compose stack; production must not publish the database port. | gsd-security-auditor | 2026-05-10 |
| AR-02 | T-01-05 | Login rate limiting is intentionally deferred from Phase 1 and should be implemented with Redis in Phase 2+. | gsd-security-auditor | 2026-05-10 |
| AR-03 | T-01-07 | No refresh-token lifecycle is acceptable for the Phase 1 demo because access tokens expire after 60 minutes by default. | gsd-security-auditor | 2026-05-10 |
| AR-04 | T-01-08 | Passwords in JSON request bodies are acceptable for localhost/dev only; production requires HTTPS. | gsd-security-auditor | 2026-05-10 |
| AR-05 | T-01-14 | Default demo passwords, deterministic demo IDs, README demo credentials, and local test DB credentials are acceptable only for demo/local usage. | gsd-security-auditor | 2026-05-10 |
| AR-06 | T-01-13 | Both `demo` and `other` tenants are synthetic demo data created and owned by `scripts/seed_demo.py`; `--reset` intentionally clears all seeded state before reinserting it, which keeps repeated seed runs consistent. | user | 2026-05-10 |

## Unregistered Flags

None. The `## Threat Flags` section was absent from all Phase 1 summary files.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-10 | 14 | 13 | 1 | gsd-security-auditor |
| 2026-05-10 | 14 | 14 | 0 | user accepted T-01-13 |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-10
