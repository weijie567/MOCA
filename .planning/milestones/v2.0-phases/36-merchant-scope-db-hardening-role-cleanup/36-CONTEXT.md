# Phase 36: Merchant-scope DB Hardening / Role Cleanup - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 36 converts v1.9 merchant-bound business-role semantics into database, migration, role-registry, and trace/replay-readiness facts. It hardens role/user binding, tenant-scoped username identity, AgentRun target merchant scope, authorization/audit root consistency, and migration gates. It must not expand run/status/evidence/trace/replay visibility beyond the existing owner/admin-only guard.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**10 requirements are locked.** See `36-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `36-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- Role registry and contract alignment for `support`, `manager`, legacy `merchant`, `admin`, and unknown roles.
- Deprecated compatibility treatment for existing legacy `merchant` users.
- Active business-user merchant binding validity.
- Tenant-scoped username principal semantics.
- AgentRun target merchant binding and scope classification.
- Target merchant consistency for approval requests, action drafts, and action safety snapshots.
- Migration/backfill preflight gates, fail-closed classification, idempotence, and downgrade/rollback expectations.
- Indexes, uniqueness rules, constraints, and tests needed to enforce the locked database facts.
- Regression coverage that proves existing runtime authorization behavior does not widen.
- Phase 37 readiness conclusion.

**Out of scope (from SPEC.md):**
- Same-merchant manager AgentRun/status/evidence/trace/replay authorization expansion.
- Manager live stream observation or event subscription expansion.
- PostgreSQL RLS enablement.
- Physical deletion of legacy `merchant` role.
- Tenant-wide manager or supervisor semantics.
- Same-merchant `support` trace/replay visibility.
- Merchant-specific policy retrieval.
- `TrustedSystemContext` or system wildcard actor model.
- Real external action execution.
- Multi-merchant run support.
- Broad merchant_id denormalization into every table.
- Raw trace/replay/prompt/tool payload projection changes.

</spec_lock>

<decisions>
## Implementation Decisions

### AgentRun Scope Facts
- **D-01:** Phase 36 should make `AgentRun` the primary persisted run-level target merchant fact for future Phase 37. Planner should not rely on `requested_by -> user.merchant_id`, thread id, prompt text, memory, RAG evidence, or LLM output to prove run merchant scope.
- **D-02:** Use an explicit run scope classification with the SPEC states: `business_merchant`, `policy_only` / `merchant_not_required`, and `unknown_legacy`. Null target merchant is valid only when paired with a non-business or fail-closed classification.
- **D-03:** Phase 36 should keep multi-merchant runs as invalid / out of scope. If creation or backfill detects mixed merchant proof, classify fail-closed or block migration rather than attempting partial scope slicing.
- **D-04:** `target_merchant_context` and `replay_authorization_proof` remain projection/safety metadata only. They may be used for readiness evidence or consistency checks, but they must not override a missing or contradictory AgentRun-level target merchant binding.
- **D-05:** For current run creation paths, planner should locate the earliest trustworthy business-scope source in the graph/tool/business-fact flow and persist target merchant scope there. Do not backfill from run owner identity unless the plan first proves the row is explicitly a user-owned object and records that product/security exception.

### Role, User, and Login Identity
- **D-06:** Keep `users.role` as the compatibility/runtime source for this phase unless planning finds a small, low-risk way to centralize registry constants. Do not convert the system to a new `roles` / `user_roles` authority model in Phase 36.
- **D-07:** Legacy `merchant` stays enabled for existing users and support-equivalent for merchant-bound business data. New seeds, fixtures, and examples should prefer `support`, `manager`, and `admin`; any user-creation path that still accepts `merchant` must mark it deprecated or reject/map it by an explicit validation rule.
- **D-08:** Active `support`, `manager`, and legacy `merchant` users must have a tenant-consistent merchant binding. Historical active business users without a binding should fail preflight or remain deny-all/invalid; do not guess a merchant.
- **D-09:** Username identity should move toward `(tenant_id, username)`. Current auth routes query by `User.username` alone, so planning must include a tenant-resolution decision for login/demo-token/token helpers before relaxing global username uniqueness.
- **D-10:** If there is no product-ready tenant selector in the current API, planning may define a transitional tenant-resolution contract, but it must keep same-tenant duplicate usernames impossible and make the temporary limitation explicit in tests/docs.

### Migration and Backfill Gates
- **D-11:** Use Alembic preflight style already present in migrations such as `016_agent_run_memory_idempotency.py`: detect unsafe rows before adding hard constraints or indexes and raise actionable migration errors.
- **D-12:** Backfill may use only authoritative merchant proof: `orders.merchant_id`, validated approval/action target merchant bindings, trusted Phase 34 binding material, or verified scoped `BusinessFactRefV1`. Ambiguous rows become `unknown_legacy` / invalid or block migration.
- **D-13:** Migration tests should include clean data, null active business user, same-tenant duplicate username, malformed target merchant ref, contradictory target merchant binding, ambiguous legacy run, and downgrade/reupgrade behavior.
- **D-14:** Rollback/downgrade does not need to preserve newly inferred target merchant metadata if that is impossible, but any irreversible loss must be explicit and the migration must not silently destroy legacy business data.
- **D-15:** PostgreSQL RLS is explicitly deferred. Planner should not introduce session tenant variables, RLS policies, or per-connection context as part of Phase 36 verification.

### Authorization/Audit Root Consistency and Readiness
- **D-16:** `ApprovalRequest` and `ActionDraft` already carry Phase 34 target merchant fields; Phase 36 should harden validity and consistency rather than redesign Phase 34 approval semantics.
- **D-17:** `ActionSafetySnapshot` needs a target merchant binding or immutable scope proof if it is used as an authorization/audit root. Planner should prefer consistency with the existing snapshot/hash boundary and avoid relying on raw `snapshot_json` as authorization proof.
- **D-18:** Refund and ticket merchant ownership should remain derived through `order_id -> orders.merchant_id` unless a redundant field is explicitly added as non-authoritative and checked against the order merchant.
- **D-19:** Existing run/status/evidence/trace/replay guards must remain owner/admin-only for non-admin actors. Any test changes that grant same-merchant manager access belong to Phase 37, not Phase 36.
- **D-20:** Phase 36 completion must produce one readiness value for Phase 37: `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`. Prefer `ready_with_agent_run_binding` only if AgentRun-level scope is persisted and consistency/regression tests pass.

### the agent's Discretion
- Exact helper/module names for scope classification, migration preflight helpers, and readiness-report generation are left to planner discretion as long as they follow existing boundaries.
- Planner may choose specific index names and constraint names, but they should be explicit and stable enough for migration-contract tests.
- Planner may decide whether scope classification literals live near ORM models, schemas, or a small domain helper, provided `docs/contract-spec.md` and tests stay aligned.
- Planner may split work into multiple plans. Given this phase spans DB schema, auth, graph/run persistence, migration gates, and regression coverage, a single large plan is discouraged by project planning rules.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked Phase Scope
- `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md` — Locked requirements, boundaries, constraints, and acceptance criteria for Phase 36.
- `.planning/REQUIREMENTS.md` — v2.0 `MSH-01` through `MSH-08` requirements and future `TRR-01` / `RLS-01` boundaries.
- `.planning/ROADMAP.md` — Active Phase 36 goal, success criteria, dependencies, and future Phase 37/RLS candidates.
- `.planning/STATE.md` — Current milestone context and accumulated decisions from v1.9.

### Normative Contract
- `docs/contract-spec.md` §8.0.1 — Role-to-merchant scope policy, legacy `merchant`, admin wildcard, server override rules, owner/admin-only interim run/trace guard.
- `docs/contract-spec.md` §8.0.2 — Separation between business merchant scope and tenant public policy scope.

### v1.9 Closure Evidence
- `.planning/milestones/v1.9-ROADMAP.md` — Phase 29.5/34/35 decisions that made DB hardening and same-merchant trace/replay future scope.
- `.planning/milestones/v1.9-REQUIREMENTS.md` — MER-01 runtime scope closure and future database hardening boundary.
- `.planning/milestones/v1.9-MILESTONE-AUDIT.md` — Audit conclusion that same-merchant manager trace/replay remains intentionally closed.

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` — Ownership boundaries for `src/db`, `src/auth`, `src/platform`, `src/api`, `src/approvals`, `src/actions`, `src/replay`.
- `.planning/codebase/ARCHITECTURE.md` — Layering, persistence flow, approval snapshot hash flow, and cross-cutting tenant/safety concerns.
- `.planning/codebase/TESTING.md` — Required test commands and existing test organization.
- `.planning/codebase/CONVENTIONS.md` — Thin routes, repository/service boundaries, and trace-safe response conventions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/platform/trusted_context.py` — `TrustedContextFactory`, `MerchantScopeV1`, merchant-bound/admin role constants, server-scope narrowing, and unknown-role deny-all behavior.
- `src/auth/permissions.py` — Current API auth dependency and `require_merchant_access` helper for same-merchant business resources.
- `src/approvals/schemas.py` — `TargetMerchantBindingV1`, `RiskDecisionV1`, and `AutoAllowedActionBindingV1` contracts.
- `src/actions/service.py` — Existing canonical target merchant/business fact/evidence/risk binding comparison helpers for action/approval consistency.
- `src/agent/merchant_context.py` — Existing safe `target_merchant_context` projection; useful for readiness metadata but not an authorization source.
- `src/api/routers/agent_runs.py` and `src/api/routers/traces.py` — Current owner/admin-only run/status/evidence/trace/replay guards.
- `src/db/migrations/versions/016_agent_run_memory_idempotency.py` — Preflight-before-constraint migration pattern with actionable errors.
- `tests/approvals/test_migration_contract.py` — Existing migration/ORM contract-test style for schema fields and constraints.

### Established Patterns
- API routes stay thin and delegate persistence/service behavior to repositories or domain services.
- Current auth login routes query by username alone; tenant-scoped username identity requires an explicit login/tenant resolution change or a transitional invariant.
- Current run visibility guard is `run.user_id == user.id` or `user.role in {"admin"}`; Phase 36 must preserve this guard.
- Approval/action target merchant fields are currently string-based with JSON target refs; Phase 36 can harden validity/consistency without changing product semantics.
- Migration files use Alembic, explicit revision ids, downgrade functions, SQLAlchemy/PostgreSQL dialect columns, and named indexes/checks.
- Tests must be run through `uv run pytest ...` or `.venv/bin/pytest ...`; bare pytest results are invalid for MOCA.

### Integration Points
- `src/db/models.py` — User, AgentRun, ActionSafetySnapshot, ApprovalRequest, ActionDraft, RefundCase, Ticket, Order ORM facts.
- `src/db/migrations/versions/` — New Phase 36 schema/preflight migration should revise `018_phase34_approval_action_bindings`.
- `src/api/routers/auth.py` — Login/token/demo-token username lookup needs tenant-aware behavior or an explicit transitional contract.
- `scripts/seed_demo.py` and `tests/conftest.py` — Seeds/fixtures currently include legacy `merchant` users and globally unique usernames.
- `src/agent/trace.py` and `src/api/routers/agent_runs.py` — AgentRun creation/update paths where run-level scope facts must be persisted.
- `src/api/routers/traces.py` and `src/api/routers/agent_runs.py` — Regression surfaces proving no same-merchant manager trace/replay widening in Phase 36.
- `tests/test_approval_api.py`, `tests/test_trace_api.py`, `tests/approvals/` — Existing approval manager access and owner/admin trace guard regression coverage.

</code_context>

<specifics>
## Specific Ideas

- Use fail-closed language consistently: ambiguous legacy data becomes `unknown_legacy`, invalid, or migration-blocked; it is never guessed.
- Treat Phase 36 as a foundation phase that may need several small plans: role/user identity, AgentRun scope, authorization/audit root consistency, migration/backfill, and regression/readiness.
- Keep Phase 37 readiness explicit. A green Phase 36 does not automatically mean Phase 37 is implemented.

</specifics>

<deferred>
## Deferred Ideas

- Same-merchant manager run/status/evidence/trace/replay safe projection — future Phase 37.
- Same-merchant support visibility for peer runs — separate product authorization phase if desired.
- Stream event visibility for managers — separate surface matrix because `/events` currently executes/claims runs and is owner-only.
- PostgreSQL RLS policies and DB-session tenant context — future hardening after schema facts stabilize.
- Physical deletion or full migration away from legacy `merchant` role — later product-approved cleanup phase.
- Multi-merchant runs and cross-merchant partial projection slicing — separate product/security spec.
- `TrustedSystemContext` / system wildcard actor model — separate contract.
- Real external action execution/outbox/reconciliation/compensation — future external action milestone.

</deferred>

---

*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Context gathered: 2026-06-30*
