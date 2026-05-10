---
phase: 1
reviewers: [codex]
reviewed_at: "2026-05-09T14:44:49Z"
plans_reviewed: [01-PLAN.md, 02-PLAN.md, 03-PLAN.md, 04-PLAN.md, 05-PLAN.md]
---

# Cross-AI Plan Review — Phase 1

## Codex Review (GPT-5.4)

**Summary**

The Phase 1 plan set is well decomposed and mostly implementable, but as written it does not cleanly satisfy the stated Phase 1 contract. The biggest gaps are scope alignment (`CRUD` goal vs mostly read/list endpoints), operational completeness (`docker compose up` does not appear to guarantee migrations are applied), and a few design inconsistencies between auth, roles, seed data, and tests. With those corrected, this is a solid Phase 1 foundation; without them, there is a real risk of "green plans, broken first-run experience."

**Strengths**

- Clear wave-based decomposition with sensible separation between infra, auth, repositories, seed data, and tests.
- Acceptance criteria are concrete enough to execute against.
- Tenant isolation is treated as a first-class concern across repositories, routers, and tests.
- Deterministic seed data is a strong choice for demos, debugging, and integration tests.
- Threat models are present in each plan instead of being deferred.
- Plan 03 includes both detail and list endpoints in the actual doc, which is enough for useful Phase 1 read flows.
- README scope is intentionally constrained, which helps keep Phase 1 shippable.

**Concerns**

- HIGH: The stated phase goal says "authenticated CRUD endpoints," but the plans only cover auth plus read/list endpoints. That is a direct scope mismatch.
- HIGH: `docker compose up` does not appear to ensure Alembic migrations run before the API is considered usable. A healthy API without schema is not a completed foundation.
- HIGH: The auth model is inconsistent. Plan 01 defines `roles` + `user_roles`, but Plan 02/03 behave like each user has a single `user.role` field carried in JWTs.
- HIGH: The test strategy bypasses the real schema path. `create_all/drop_all` does not validate Alembic migrations and may fail for `pgvector` because the `vector` extension is not created.
- HIGH: The auth fixtures in Plan 05 mint fake JWTs with arbitrary `sub` values, while `get_current_user` is supposed to look users up in the database. Those tests will not exercise the real auth path correctly.
- HIGH: The API container healthcheck uses `curl`, but `python:3.12-slim` does not include `curl` by default. That can make the service permanently unhealthy.
- MEDIUM: Plan 04 depends on Plan 03, but the seed script only needs schema/session and probably auth hashing. That dependency lengthens the critical path unnecessarily.
- MEDIUM: `demo-token` is too permissive as described. If enabled, it can mint arbitrary roles/usernames without proving the target user exists.
- MEDIUM: Authorization appears to trust the role embedded in the JWT. If roles change in the database, old tokens may retain privileges until expiry.
- MEDIUM: `AuditRepository.log()` commits on every request. That creates avoidable write latency on read endpoints and can couple successful reads to audit-write success.
- MEDIUM: Pagination queries have no explicit ordering, so list endpoints can be unstable across requests.
- MEDIUM: Unique constraints appear global for fields like `order_no` and `refund_case_no`; in a multi-tenant system those are usually tenant-scoped unless global uniqueness is intentional.
- LOW: There is spec drift between overview and plan details, especially user counts in seed data and "all tables have tenant_id" vs the actual table definitions.

**Suggestions**

- Either change the Phase 1 goal from `CRUD` to `authenticated read/list APIs`, or add at least one create/update path so the phase contract is true.
- Add a migration step to the runtime path: a dedicated `migrate` service, an entrypoint that runs `alembic upgrade head`, or a startup gate that refuses readiness until schema is current.
- Simplify RBAC for Phase 1: either keep a single `role` column on `users`, or fully implement `roles/user_roles` and derive permissions from DB state instead of token claims alone.
- Change integration tests to use Alembic against a disposable Postgres database with `CREATE EXTENSION vector`; do not use `create_all/drop_all` as the main validation path.
- Seed real users in tests or override auth deliberately; do not fabricate tokens that reference nonexistent users if `get_current_user` is DB-backed.
- Tighten `demo-token`: default off, non-prod only, and only issue tokens for existing seeded demo users.
- Replace the API healthcheck command with something guaranteed to exist in the image, or install `curl` explicitly.
- Move Plan 04 earlier: depend on `01` plus whatever is needed for password hashing, not `03`.
- Add deterministic ordering and a small index review for list/join-heavy paths (`merchant_id`, `order_id`, `refund_case_id`, maybe `trace_id`).

**Risk Assessment**

HIGH. The plan set is close, but as written there are several implementation-blocking issues that can prevent the phase from meeting its own success criteria on first run.

---

## Gemini Review

Skipped — Gemini API quota exhausted (`insufficient_quota`).

---

## Consensus Summary

### Agreed Strengths (from Codex)
- Wave decomposition is clean and logical
- Acceptance criteria are grep-verifiable
- Tenant isolation is first-class
- Deterministic seed data is strong for demos
- Threat models present in every plan

### Top Concerns (Priority Order)
1. **Healthcheck uses `curl` not available in python:3.12-slim** — will break `docker compose up`
2. **No auto-migration on startup** — healthy API without schema = broken first-run
3. **Auth model inconsistency** — `roles` + `user_roles` tables vs single `role` in JWT
4. **Tests bypass Alembic** — `create_all` won't create pgvector extension
5. **Test auth fixtures fabricate tokens** — won't exercise real `get_current_user` DB lookup
6. **"CRUD" goal but only read endpoints** — scope mismatch with phase contract

### Divergent Views
N/A — only one reviewer completed successfully.

---

*Review completed: 2026-05-09*
*Reviewers: Codex (GPT-5.4). Gemini skipped (quota exhausted).*
