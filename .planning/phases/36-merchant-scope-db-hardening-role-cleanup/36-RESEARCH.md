# Phase 36: Merchant-scope DB Hardening / Role Cleanup - Research

**Researched:** 2026-06-30  
**Domain:** PostgreSQL/Alembic schema hardening, merchant-scope authorization facts, run/approval/action audit consistency  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

The following locked decisions, discretion areas, and deferred ideas are copied from Phase 36 CONTEXT.md. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]

### Locked Decisions

#### AgentRun Scope Facts
- **D-01:** Phase 36 should make `AgentRun` the primary persisted run-level target merchant fact for future Phase 37. Planner should not rely on `requested_by -> user.merchant_id`, thread id, prompt text, memory, RAG evidence, or LLM output to prove run merchant scope.
- **D-02:** Use an explicit run scope classification with the SPEC states: `business_merchant`, `policy_only` / `merchant_not_required`, and `unknown_legacy`. Null target merchant is valid only when paired with a non-business or fail-closed classification.
- **D-03:** Phase 36 should keep multi-merchant runs as invalid / out of scope. If creation or backfill detects mixed merchant proof, classify fail-closed or block migration rather than attempting partial scope slicing.
- **D-04:** `target_merchant_context` and `replay_authorization_proof` remain projection/safety metadata only. They may be used for readiness evidence or consistency checks, but they must not override a missing or contradictory AgentRun-level target merchant binding.
- **D-05:** For current run creation paths, planner should locate the earliest trustworthy business-scope source in the graph/tool/business-fact flow and persist target merchant scope there. Do not backfill from run owner identity unless the plan first proves the row is explicitly a user-owned object and records that product/security exception.

#### Role, User, and Login Identity
- **D-06:** Keep `users.role` as the compatibility/runtime source for this phase unless planning finds a small, low-risk way to centralize registry constants. Do not convert the system to a new `roles` / `user_roles` authority model in Phase 36.
- **D-07:** Legacy `merchant` stays enabled for existing users and support-equivalent for merchant-bound business data. New seeds, fixtures, and examples should prefer `support`, `manager`, and `admin`; any user-creation path that still accepts `merchant` must mark it deprecated or reject/map it by an explicit validation rule.
- **D-08:** Active `support`, `manager`, and legacy `merchant` users must have a tenant-consistent merchant binding. Historical active business users without a binding should fail preflight or remain deny-all/invalid; do not guess a merchant.
- **D-09:** Username identity should move toward `(tenant_id, username)`. Current auth routes query by `User.username` alone, so planning must include a tenant-resolution decision for login/demo-token/token helpers before relaxing global username uniqueness.
- **D-10:** If there is no product-ready tenant selector in the current API, planning may define a transitional tenant-resolution contract, but it must keep same-tenant duplicate usernames impossible and make the temporary limitation explicit in tests/docs.

#### Migration and Backfill Gates
- **D-11:** Use Alembic preflight style already present in migrations such as `016_agent_run_memory_idempotency.py`: detect unsafe rows before adding hard constraints or indexes and raise actionable migration errors.
- **D-12:** Backfill may use only authoritative merchant proof: `orders.merchant_id`, validated approval/action target merchant bindings, trusted Phase 34 binding material, or verified scoped `BusinessFactRefV1`. Ambiguous rows become `unknown_legacy` / invalid or block migration.
- **D-13:** Migration tests should include clean data, null active business user, same-tenant duplicate username, malformed target merchant ref, contradictory target merchant binding, ambiguous legacy run, and downgrade/reupgrade behavior.
- **D-14:** Rollback/downgrade does not need to preserve newly inferred target merchant metadata if that is impossible, but any irreversible loss must be explicit and the migration must not silently destroy legacy business data.
- **D-15:** PostgreSQL RLS is explicitly deferred. Planner should not introduce session tenant variables, RLS policies, or per-connection context as part of Phase 36 verification.

#### Authorization/Audit Root Consistency and Readiness
- **D-16:** `ApprovalRequest` and `ActionDraft` already carry Phase 34 target merchant fields; Phase 36 should harden validity and consistency rather than redesign Phase 34 approval semantics.
- **D-17:** `ActionSafetySnapshot` needs a target merchant binding or immutable scope proof if it is used as an authorization/audit root. Planner should prefer consistency with the existing snapshot/hash boundary and avoid relying on raw `snapshot_json` as authorization proof.
- **D-18:** Refund and ticket merchant ownership should remain derived through `order_id -> orders.merchant_id` unless a redundant field is explicitly added as non-authoritative and checked against the order merchant.
- **D-19:** Existing run/status/evidence/trace/replay guards must remain owner/admin-only for non-admin actors. Any test changes that grant same-merchant manager access belong to Phase 37, not Phase 36.
- **D-20:** Phase 36 completion must produce one readiness value for Phase 37: `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`. Prefer `ready_with_agent_run_binding` only if AgentRun-level scope is persisted and consistency/regression tests pass.

### Claude's Discretion
- Exact helper/module names for scope classification, migration preflight helpers, and readiness-report generation are left to planner discretion as long as they follow existing boundaries.
- Planner may choose specific index names and constraint names, but they should be explicit and stable enough for migration-contract tests.
- Planner may decide whether scope classification literals live near ORM models, schemas, or a small domain helper, provided `docs/contract-spec.md` and tests stay aligned.
- Planner may split work into multiple plans. Given this phase spans DB schema, auth, graph/run persistence, migration gates, and regression coverage, a single large plan is discouraged by project planning rules.

### Deferred Ideas (OUT OF SCOPE)
- Same-merchant manager run/status/evidence/trace/replay safe projection — future Phase 37.
- Same-merchant support visibility for peer runs — separate product authorization phase if desired.
- Stream event visibility for managers — separate surface matrix because `/events` currently executes/claims runs and is owner-only.
- PostgreSQL RLS policies and DB-session tenant context — future hardening after schema facts stabilize.
- Physical deletion or full migration away from legacy `merchant` role — later product-approved cleanup phase.
- Multi-merchant runs and cross-merchant partial projection slicing — separate product/security spec.
- `TrustedSystemContext` / system wildcard actor model — separate contract.
- Real external action execution/outbox/reconciliation/compensation — future external action milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MSH-01 | Legacy `merchant` role is documented and enforced as deprecated compatibility-only, semantically equivalent to merchant-bound `support` for business-data access and never platform-wide. [VERIFIED: .planning/REQUIREMENTS.md] | Use existing role constants in `src/auth/permissions.py` and `src/platform/trusted_context.py`; both include `merchant` in merchant-bound roles and only `admin` in platform-admin roles. [VERIFIED: src/auth/permissions.py; src/platform/trusted_context.py] |
| MSH-02 | Active business users with `support`, `manager`, or legacy `merchant` role have a valid merchant binding, while invalid or ambiguous legacy users fail closed instead of receiving guessed scope. [VERIFIED: .planning/REQUIREMENTS.md] | Current runtime already denies empty/wrong merchant access; migration and fixtures need active-user preflight checks before constraints. [VERIFIED: tests/platform/test_merchant_scope.py; src/auth/permissions.py] |
| MSH-03 | Username identity is tenant-scoped or guarded by an explicit transitional tenant-resolution contract, with tests preventing same-tenant duplicate principal ambiguity. [VERIFIED: .planning/REQUIREMENTS.md] | `users.username` is currently globally unique and login/token/demo-token query by username alone, so tenant resolution must precede any uniqueness relaxation. [VERIFIED: src/db/models.py; src/api/routers/auth.py] |
| MSH-04 | `AgentRun` records have an unambiguous target merchant binding model and explicit scope classification for `business_merchant`, `policy_only` / `merchant_not_required`, and `unknown_legacy` runs. [VERIFIED: .planning/REQUIREMENTS.md] | `AgentRun` currently has tenant/user/thread/input/status fields but no target merchant or scope classification; Phase 36 needs schema, classifier, migration, and runtime write points. [VERIFIED: src/db/models.py; src/api/routers/agent_runs.py; src/agent/trace.py] |
| MSH-05 | Authorization and audit root records with target merchant scope, including approval requests, action drafts, and safety snapshots, cannot contradict each other when linked to the same business-scoped run. [VERIFIED: .planning/REQUIREMENTS.md] | Approval/action tables already carry target merchant fields; safety snapshots do not. Phase 36 should add run/snapshot consistency around Phase 34 fields. [VERIFIED: src/db/models.py; src/actions/service.py; tests/actions/test_phase34_action_draft_bindings.py] |
| MSH-06 | Migration and backfill gates only use authoritative sources for merchant scope, classify ambiguous legacy records as fail-closed, and reject unsafe data before applying hard constraints. [VERIFIED: .planning/REQUIREMENTS.md] | Reuse the Alembic preflight pattern from migration 016 and the Phase 34 migration-contract test style. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py; tests/approvals/test_migration_contract.py] |
| MSH-07 | Existing runtime authorization behavior does not regress: merchant-bound users remain same-merchant-only for business facts, tenant public policy retrieval remains separate, and run/status/evidence/trace/replay visibility remains owner/admin-only. [VERIFIED: .planning/REQUIREMENTS.md] | Preserve `require_merchant_access`, order-derived refund/ticket ownership, policy/business-scope separation, and Phase 35 owner/admin-only run/trace/replay tests. [VERIFIED: src/auth/permissions.py; src/api/routers/refund_cases.py; src/api/routers/tickets.py; tests/replay/test_phase35_trace_replay_permissions.py; docs/contract-spec.md] |
| MSH-08 | Phase 36 emits a trace/replay authorization readiness conclusion for future Phase 37, using one of `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`. [VERIFIED: .planning/REQUIREMENTS.md] | Completion should generate a readiness fact from persisted AgentRun binding plus consistency/regression tests; projection-only metadata is insufficient authority. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; src/agent/merchant_context.py] |
</phase_requirements>

## Summary

Phase 36 should be planned as a database and boundary-hardening phase, not a runtime visibility-expansion phase. The locked scope is to persist merchant-scope facts, harden legacy role/user identity semantics, add migration gates, and produce Phase 37 readiness without allowing same-merchant manager/support access to run/status/evidence/trace/replay. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md]

The highest-risk dependency order is: tenant-aware identity before username uniqueness changes; AgentRun target scope before readiness; approval/action/snapshot consistency after run scope exists; migration preflight before hard constraints; regression tests around Phase 35 owner/admin-only access before any API guard edits. [VERIFIED: src/api/routers/auth.py; src/db/models.py; tests/replay/test_phase35_trace_replay_permissions.py; src/db/migrations/versions/016_agent_run_memory_idempotency.py]

**Primary recommendation:** split Phase 36 into multiple numbered plans: role/user identity, AgentRun scope model/runtime persistence, approval/action/snapshot consistency, migration/backfill gates, and readiness/regression validation. [VERIFIED: AGENTS.md; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]

## Project Constraints (from CLAUDE.md / AGENTS.md)

- Tests, Ruff, and temporary Python tooling must use `uv run ...` or `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid in MOCA. [VERIFIED: AGENTS.md; CLAUDE.md]
- Debug/local validation issues are normally appended to `.planning/LOCAL-VALIDATION-ISSUES.md`, but this research turn was explicitly instructed not to touch that file. [VERIFIED: AGENTS.md; user request]
- For phase-level plans and large changes, MOCA uses a dual-review workflow, and planning must explicitly check plan granularity. [VERIFIED: AGENTS.md]
- A single plan is a blocker if it spans contracts, migration, compatibility, callsites, permissions/security boundaries, and final verification. [VERIFIED: AGENTS.md]
- `docs/contract-spec.md` is the normative contract source for role/business-scope semantics, but implementation scope still belongs to the phase; any implementation/spec divergence must leave a decision trace. [VERIFIED: AGENTS.md; docs/contract-spec.md]
- Phase 36 must not modify source code during research; this artifact is planning input only. [VERIFIED: user request]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Role registry and legacy `merchant` compatibility | API / Backend | Database / Storage | Runtime authority currently comes from `users.role`, `MERCHANT_BOUND_ROLES`, `PLATFORM_ADMIN_ROLES`, and `TrustedContextFactory`; database constraints should prevent invalid active business users. [VERIFIED: src/auth/permissions.py; src/platform/trusted_context.py; src/db/models.py] |
| Tenant-scoped username identity | API / Backend | Database / Storage | Login/token/demo-token currently query username alone, while token validation already checks `User.id` and `tenant_id`; uniqueness/index changes depend on API tenant resolution. [VERIFIED: src/api/routers/auth.py; src/auth/permissions.py; src/db/models.py] |
| AgentRun target merchant scope | API / Backend | Database / Storage | Run creation/completion and trace writing own run lifecycle persistence; schema must store target merchant and classification for future authorization readiness. [VERIFIED: src/api/routers/agent_runs.py; src/agent/trace.py; src/db/models.py] |
| Approval/action/snapshot target consistency | API / Backend | Database / Storage | `ApprovalRequest` and `ActionDraft` already persist Phase 34 target bindings; `ActionSafetySnapshot` is the missing audit-root scope binding surface. [VERIFIED: src/db/models.py; src/actions/service.py; docs/contract-spec.md] |
| Refund/ticket merchant ownership | API / Backend | Database / Storage | Refund and ticket APIs derive merchant ownership through `order_id -> orders.merchant_id`, then call `require_merchant_access`; ownership should remain derived. [VERIFIED: src/api/routers/refund_cases.py; src/api/routers/tickets.py; src/db/models.py] |
| Run/status/evidence/trace/replay visibility | API / Backend | - | The current guard is owner/admin-only and Phase 36 must preserve it; same-merchant visibility is deferred. [VERIFIED: src/api/routers/agent_runs.py; src/api/routers/traces.py; tests/replay/test_phase35_trace_replay_permissions.py] |
| Migration/backfill/readiness facts | Database / Storage | API / Backend | Alembic migrations should preflight unsafe historical data before applying constraints; readiness is a derived outcome from persisted facts and regression tests. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.13 | Runtime and test interpreter | Project requires Python `>=3.12`, and local `uv run python` resolves 3.12.13. [VERIFIED: pyproject.toml; uv run python] |
| SQLAlchemy | 2.0.49 | ORM models, constraints, indexes, async sessions | Existing models and tests use SQLAlchemy ORM/Core metadata; SQLAlchemy supports PostgreSQL partial indexes via `postgresql_where`. [VERIFIED: uv run python; src/db/models.py; CITED: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html] |
| Alembic | 1.18.4 | Database migrations | Existing migrations use Alembic `op.add_column`, `op.create_index`, `op.create_check_constraint`, and downgrade functions. [VERIFIED: uv run python; src/db/migrations/versions/018_phase34_approval_action_bindings.py; CITED: https://alembic.sqlalchemy.org/en/latest/ops.html] |
| FastAPI | 0.136.1 | Auth and API route layer | Current auth/routes use FastAPI dependencies, `Security`, and OAuth2 scopes; official docs support `SecurityScopes` in dependencies. [VERIFIED: uv run python; src/auth/permissions.py; CITED: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/] |
| Pydantic | 2.13.4 | Strict schema validation for trusted bindings | Existing trusted schemas use `ConfigDict(extra="forbid")` and validators; Pydantic v2 documents forbidding extra fields via `ConfigDict(extra='forbid')`. [VERIFIED: uv run python; src/approvals/schemas.py; src/platform/trusted_context.py; CITED: https://docs.pydantic.dev/latest/api/config/] |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Test fixtures create async SQLAlchemy engines against PostgreSQL via `postgresql+asyncpg`. [VERIFIED: uv run python; tests/conftest.py] |
| pytest / pytest-asyncio | pytest 9.0.3; asyncio mode auto | Validation framework | Project test config sets `asyncio_mode = "auto"` and dev dependency includes pytest/pytest-asyncio. [VERIFIED: uv run python; pyproject.toml] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| uv | 0.11.2 | Project command runner and dependency environment | Use for every test/lint/Python command: `UV_CACHE_DIR=/tmp/uv-cache uv run ...`. [VERIFIED: command -v uv; uv --version; AGENTS.md] |
| Docker | 29.4.2 | Local PostgreSQL fallback | Use `docker compose up -d postgres` if no local PostgreSQL service is available. [VERIFIED: docker --version; docker-compose.yml; tests/conftest.py] |
| PostgreSQL | Configured service, CLI not on PATH | Target database | Project config and tests use PostgreSQL URLs; `psql`/`pg_isready` were not found locally, so plans should not require PostgreSQL CLI commands. [VERIFIED: alembic.ini; docker-compose.yml; tests/conftest.py; command -v psql; command -v pg_isready] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `users.role` runtime source | New `roles` / `user_roles` authority model | Explicitly out of scope; existing tables exist, but CONTEXT locks Phase 36 to compatibility/runtime `users.role`. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; src/db/models.py] |
| AgentRun-level target binding | Derive from `requested_by`, thread, prompt, memory, RAG, raw tool payload, or LLM output | Locked out because those sources are non-authoritative or ambiguous for run merchant scope. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md] |
| PostgreSQL RLS | Session tenant variables and RLS policies | Explicitly deferred to later hardening; Phase 36 should not introduce DB session context. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md] |
| Broad `merchant_id` denormalization into refunds/tickets | Add redundant merchant columns everywhere | Refund and ticket ownership is currently derived from order; redundant fields would need consistency checks and are not necessary for Phase 36. [VERIFIED: src/db/models.py; src/api/routers/refund_cases.py; src/api/routers/tickets.py] |

**Installation / environment sync:**

```bash
uv sync --extra dev
docker compose up -d postgres
```

The first command prepares the existing Python project dependencies; the second command is only needed when local PostgreSQL is not already running. [VERIFIED: pyproject.toml; docker-compose.yml; tests/conftest.py]

**Version verification:** Versions above were verified from the local environment with `uv run python` import metadata and CLI version checks, not inferred from training data. [VERIFIED: uv run python; uv --version; docker --version]

## Architecture Patterns

### System Architecture Diagram

```text
Auth request + tenant selector
  -> API auth lookup by tenant + username
  -> User row: tenant_id, username, role, merchant_id, is_active
  -> TrustedContextFactory / require_merchant_access
      -> admin: explicit wildcard scope
      -> support|manager|merchant: bound merchant or deny-all
      -> unknown role: deny-all
  -> AgentRun creation and graph execution
      -> policy-only path: classification = policy_only / merchant_not_required, target_merchant_id = null
      -> trusted BusinessFactRef / Phase 34 binding path: classification = business_merchant, target_merchant_id = authoritative merchant
      -> ambiguous or mixed proof: classification = unknown_legacy or migration block
  -> ApprovalRequest / ActionDraft / ActionSafetySnapshot consistency checks
  -> Migration preflight and readiness conclusion
  -> Run/status/evidence/trace/replay API guards remain owner/admin-only
```

The data flow starts at auth, persists run-level scope facts only from trusted sources, and keeps visibility guards separate from readiness metadata. [VERIFIED: src/api/routers/auth.py; src/platform/trusted_context.py; src/api/routers/agent_runs.py; src/actions/service.py; src/api/routers/traces.py]

### Recommended Project Structure

```text
src/
├── auth/                         # role registry constants, auth lookup, merchant access helpers
├── platform/                     # TrustedContextFactory and MerchantScopeV1 remain canonical runtime scope
├── agent/                        # run-scope classifier/persistence integration near graph/run lifecycle
├── approvals/                    # target binding schemas and approval/snapshot consistency helpers
├── actions/                      # action draft binding validation against approval/run/snapshot facts
└── db/
    ├── models.py                 # ORM columns, indexes, constraints
    └── migrations/versions/019_* # Phase 36 Alembic preflight/backfill/schema migration

tests/
├── platform/                     # role/scope runtime invariants
├── integration/                  # tenant-aware auth/login/token tests
├── approvals/                    # migration and cross-table binding contract tests
├── actions/                      # action draft consistency tests
├── agent/                        # run-scope classifier/runtime persistence tests
└── replay/                       # no-widening/readiness regression tests
```

This structure follows existing ownership boundaries and avoids moving Phase 36 into a new authority model. [VERIFIED: src/auth/permissions.py; src/platform/trusted_context.py; src/db/models.py; tests/approvals/test_migration_contract.py]

### Pattern 1: Preflight Before Constraint

**What:** Detect unsafe rows with `op.get_bind().execute(sa.text(...)).mappings().first()` and raise an actionable `RuntimeError` before adding unique indexes/checks. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py]

**When to use:** Use before `(tenant_id, username)` uniqueness changes, active business-user merchant binding constraints, AgentRun scope classification checks, and approval/action/snapshot consistency constraints. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; src/db/models.py]

**Example:**

```python
# Source: src/db/migrations/versions/016_agent_run_memory_idempotency.py
duplicate = (
    bind.execute(sa.text("""SELECT tenant_id, run_id, role, COUNT(*) AS duplicate_count ..."""))
    .mappings()
    .first()
)
if duplicate is not None:
    raise RuntimeError("Cannot create ... duplicate rows ...")
```

### Pattern 2: Explicit Scope Classification

**What:** Store a classification enum/literal alongside `AgentRun.target_merchant_id` instead of interpreting null as a business decision. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]

**When to use:** Use for all run rows and migration backfill outcomes: `business_merchant`, `policy_only` or `merchant_not_required`, and `unknown_legacy`. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md]

**Example:**

```python
# Source: Phase 36 CONTEXT.md; implement as planner-chosen model/helper names.
RUN_SCOPE_CLASSIFICATIONS = {
    "business_merchant",
    "policy_only",
    "merchant_not_required",
    "unknown_legacy",
}
```

### Pattern 3: Projection Metadata Is Not Authority

**What:** Use `target_merchant_context` and replay authorization proof only as readiness/projection evidence; never let those projections grant API visibility. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; tests/replay/test_phase35_trace_replay_permissions.py]

**When to use:** Any code touching `project_target_merchant_context`, `project_replay_authorization_proof`, trace/replay routers, or run status/evidence guards. [VERIFIED: src/agent/merchant_context.py; src/replay/proof_projection.py; src/api/routers/traces.py; src/api/routers/agent_runs.py]

**Example:**

```python
# Source: src/api/routers/traces.py
if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

### Pattern 4: Order-Derived Merchant Ownership

**What:** Refund and ticket APIs derive merchant ownership via `Order.merchant_id` and then call `require_merchant_access`. [VERIFIED: src/api/routers/refund_cases.py; src/api/routers/tickets.py]

**When to use:** Preserve for MSH-07 regression and avoid adding merchant truth to refund/ticket rows unless non-authoritative and checked. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; src/db/models.py]

**Example:**

```python
# Source: src/api/routers/refund_cases.py
merchant_id = (
    await session.execute(
        select(Order.merchant_id).where(Order.id == refund_case.order_id, Order.tenant_id == user.tenant_id)
    )
).scalar_one_or_none()
require_merchant_access(user, merchant_id, resource_name="refund cases")
```

### Anti-Patterns to Avoid

- **Relaxing username uniqueness before tenant-aware login:** Current auth queries username alone; duplicate usernames would make login ambiguous or error-prone. [VERIFIED: src/api/routers/auth.py; src/db/models.py]
- **Backfilling AgentRun scope from owner identity:** CONTEXT forbids `requested_by -> user.merchant_id` and equivalent owner-based inference as merchant-scope proof. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]
- **Using memory/RAG/LLM text as merchant proof:** The contract says memory is contextual assistance and cannot replace current business facts or approval/action/replay truth. [VERIFIED: docs/contract-spec.md]
- **Adding RLS while touching scope schema:** RLS/session tenant context is explicitly deferred and would expand the phase into Phase 37/RLS scope. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]
- **Granting same-merchant manager trace/replay access:** Phase 35 tests prove same-merchant managers still get 403; Phase 36 must keep that behavior. [VERIFIED: tests/replay/test_phase35_trace_replay_permissions.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Migration DDL and partial indexes | Raw ad hoc schema scripts outside Alembic | Alembic `op.add_column`, `op.create_index`, `op.create_check_constraint`, SQLAlchemy `Index(..., postgresql_where=...)` | Existing project migrations use Alembic, and official docs cover these operations. [VERIFIED: src/db/migrations/versions/018_phase34_approval_action_bindings.py; CITED: https://alembic.sqlalchemy.org/en/latest/ops.html; CITED: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html] |
| Merchant scope validation | Request-body scope, frontend scope, LLM-inferred scope | `TrustedContextFactory`, `MerchantScopeV1`, `require_merchant_access` | Contract requires trusted server-derived scope and deny-all on empty/unknown scope. [VERIFIED: docs/contract-spec.md; src/platform/trusted_context.py; src/auth/permissions.py] |
| Approval/action binding validation | Raw JSON equality against unvalidated dicts only | Existing `TargetMerchantBindingV1`, `BusinessFactRefV1`, `EvidenceRefV1`, `AutoAllowedActionBindingV1` schemas plus service checks | Existing tests already reject invalid/mismatched Phase 34 binding data. [VERIFIED: src/approvals/schemas.py; src/actions/service.py; tests/actions/test_phase34_action_draft_bindings.py] |
| Snapshot/audit proof | Raw `snapshot_json` as authorization source | Immutable hash boundary plus exact `action_payload_hash`/`safety_snapshot_hash` checks | Contract says snapshots are immutable audit roots and guards must compare exact hashes. [VERIFIED: docs/contract-spec.md; src/actions/service.py] |
| Run/trace/replay authorization | Same-merchant shortcut using target projections | Existing owner/admin-only guards until Phase 37 | Phase 36 readiness does not implement Phase 37 visibility. [VERIFIED: src/api/routers/traces.py; tests/replay/test_phase35_trace_replay_permissions.py] |
| Refund/ticket ownership | Independent merchant truth on refund/ticket rows | `order_id -> orders.merchant_id` derivation | Current ORM and APIs use order-derived ownership, matching CONTEXT D-18. [VERIFIED: src/db/models.py; src/api/routers/refund_cases.py; src/api/routers/tickets.py] |

**Key insight:** Phase 36 is about making future authorization proof possible; it is not the phase that consumes that proof to widen run/trace/replay access. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; tests/replay/test_phase35_trace_replay_permissions.py]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | PostgreSQL-backed tables in scope: `users`, `agent_runs`, `approval_requests`, `action_drafts`, `action_safety_snapshots`, `orders`, `refund_cases`, and `tickets`. [VERIFIED: src/db/models.py; tests/conftest.py] | Add Alembic preflight/backfill tasks; distinguish clean data, invalid active business users, duplicate username risk, ambiguous legacy runs, contradictory target bindings, and downgrade/reupgrade behavior. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] |
| Live service config | No external service configuration in git controls Phase 36 merchant-scope facts; `rg` found Docker/env config but no n8n/Datadog/Cloudflare/Tailscale runtime dependency for this phase. [VERIFIED: rg n8n/Datadog/Cloudflare/Tailscale; docker-compose.yml] | None for Phase 36 planning, except Docker Compose can supply PostgreSQL for tests. [VERIFIED: docker-compose.yml; tests/conftest.py] |
| OS-registered state | Study-related launchd plists exist under `scripts/study/launchd`, but they are not tied to Phase 36 merchant-scope DB/auth/runtime facts. [VERIFIED: find . -name '*.plist'] | None for Phase 36; do not change launchd state. [VERIFIED: phase SPEC; scripts/study/launchd] |
| Secrets/env vars | `DATABASE_URL`, `POSTGRES_*`, `JWT_SECRET`, and demo auth env config appear in Docker Compose; no Phase 36 secret-key rename is required. [VERIFIED: docker-compose.yml; rg DATABASE_URL/POSTGRES/JWT] | Do not rename secrets; if tenant-aware login needs a temporary feature flag, keep it explicit and documented in plan/tests. [VERIFIED: src/api/routers/auth.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] |
| Build artifacts | No installed package/build artifact rename is part of this phase; source/package name remains `moca`. [VERIFIED: pyproject.toml; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md] | None. [VERIFIED: pyproject.toml] |

**Nothing found in category:** OS/service/secrets/build artifact changes are not required for this migration-hardening phase; stored PostgreSQL data is the only runtime state category requiring migration work. [VERIFIED: phase SPEC; rg/finder audits listed above]

## Common Pitfalls

### Pitfall 1: Username Ambiguity During Tenant-Scoped Identity
**What goes wrong:** Relaxing `users.username` global uniqueness before `/login`, `/token`, and `/demo-token` accept or resolve tenant causes ambiguous auth lookup. [VERIFIED: src/api/routers/auth.py; src/db/models.py]  
**Why it happens:** Current login queries use `select(User).where(User.username == ...)` while the target identity is `(tenant_id, username)`. [VERIFIED: src/api/routers/auth.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**How to avoid:** First decide tenant-resolution API shape or transitional invariant, then migrate/index username semantics. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**Warning signs:** Tests create cross-tenant duplicate usernames but auth payloads have no tenant selector. [VERIFIED: tests/integration/test_auth.py; tests/conftest.py]

### Pitfall 2: Null Target Merchant Becomes Implicit Policy
**What goes wrong:** `target_merchant_id IS NULL` is treated as either non-business or unrestricted depending on caller. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**Why it happens:** `AgentRun` has no scope classification today. [VERIFIED: src/db/models.py]  
**How to avoid:** Add explicit run scope classification and check constraints coupling null/non-null target merchant to classification. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md; CITED: https://alembic.sqlalchemy.org/en/latest/ops.html]  
**Warning signs:** Code branches check only `target_merchant_id is None` without classification. [VERIFIED: source audit]

### Pitfall 3: Forbidden Backfill Sources Sneak In
**What goes wrong:** Historical runs are backfilled from owner/user merchant, username, thread id, prompt text, memory, RAG, raw tool payload, or LLM output. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**Why it happens:** These sources may correlate with merchant but are not authoritative merchant proof. [VERIFIED: docs/contract-spec.md]  
**How to avoid:** Restrict backfill to orders, validated approval/action target bindings, trusted Phase 34 binding material, and verified scoped `BusinessFactRefV1`. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**Warning signs:** Migration SQL joins `agent_runs.user_id` to `users.merchant_id` for scope inference. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]

### Pitfall 4: Readiness Proof Accidentally Widens Runtime Access
**What goes wrong:** A helper added for Phase 37 readiness is used by current trace/replay/status/evidence guards. [VERIFIED: tests/replay/test_phase35_trace_replay_permissions.py]  
**Why it happens:** `target_merchant_context` and replay proof projections sound like authorization proof but are currently projection/safety metadata only. [VERIFIED: src/agent/merchant_context.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**How to avoid:** Keep run visibility guards owner/admin-only and add static tests that reject projection shortcut patterns. [VERIFIED: tests/replay/test_phase35_trace_replay_permissions.py]  
**Warning signs:** `target_merchant_context`, `project_replay_authorization_proof`, or `requested_by.*merchant` appears in API guard code. [VERIFIED: tests/replay/test_phase35_trace_replay_permissions.py]

### Pitfall 5: Constraints Added Before Historical Data Classification
**What goes wrong:** Alembic migration fails halfway or blocks deploy without actionable diagnosis. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py]  
**Why it happens:** Hard constraints/indexes are added before duplicate/null/contradictory rows are detected or classified. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
**How to avoid:** Use preflight functions before each hardening step and include the first conflicting row in the error. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py]  
**Warning signs:** Migration directly calls `op.create_index(unique=True)` without preceding duplicate detection. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py]

### Pitfall 6: Snapshot Scope Bound to Raw JSON
**What goes wrong:** `ActionSafetySnapshot.snapshot_json` is treated as authorization proof even when target binding/hash consistency is not verified. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md]  
**Why it happens:** Snapshot JSON is durable, but contract authority comes from immutable hash and exact action/safety binding, not arbitrary raw JSON inspection. [VERIFIED: docs/contract-spec.md; src/actions/service.py]  
**How to avoid:** Prefer immutable scope proof or target binding fields consistent with existing snapshot/hash boundary. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md]  
**Warning signs:** Service checks parse `snapshot_json` target data but do not compare `action_payload_hash` and `safety_snapshot_hash`. [VERIFIED: docs/contract-spec.md]

## Code Examples

Verified patterns from project and official sources:

### Alembic Add Column / Index / Preflight

```python
# Source: src/db/migrations/versions/018_phase34_approval_action_bindings.py
op.add_column("approval_requests", sa.Column("target_merchant_id", sa.String(length=128)))
op.create_index(
    "ix_approval_requests_tenant_target_merchant",
    "approval_requests",
    ["tenant_id", "target_merchant_id"],
)
```

Alembic documents `Operations.add_column()` and `Operations.create_index()` for this pattern. [CITED: https://alembic.sqlalchemy.org/en/latest/ops.html]

### SQLAlchemy PostgreSQL Partial Index

```python
# Source: src/db/models.py
Index(
    "uq_conversation_messages_active_tenant_run_role",
    ConversationMessage.tenant_id,
    ConversationMessage.run_id,
    ConversationMessage.role,
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND run_id IS NOT NULL AND role IN ('user', 'assistant')"),
)
```

SQLAlchemy documents PostgreSQL partial indexes with the `postgresql_where` keyword. [CITED: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html]

### Strict Binding Schema

```python
# Source: src/approvals/schemas.py
class TargetMerchantBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["target_merchant_binding.v1"] = "target_merchant_binding.v1"
    target_merchant_id: str
    source: Literal["business_fact_ref", "business_fact_result"]
    business_fact_ref: dict[str, Any]
```

Pydantic v2 documents `ConfigDict(extra='forbid')` to reject unknown fields. [CITED: https://docs.pydantic.dev/latest/api/config/]

### Owner/Admin-Only Trace Guard

```python
# Source: src/api/routers/traces.py
if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

This guard is the regression baseline for Phase 36. [VERIFIED: src/api/routers/traces.py; tests/replay/test_phase35_trace_replay_permissions.py]

## State of the Art

| Old Approach | Current Approach | When Changed / Locked | Impact |
|--------------|------------------|------------------------|--------|
| Global username uniqueness and username-only login | Move toward `(tenant_id, username)` or an explicit transitional tenant-resolution contract | Phase 36 locked context, 2026-06-30 [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] | Auth plans must update lookup semantics before uniqueness changes. [VERIFIED: src/api/routers/auth.py; src/db/models.py] |
| Runtime role semantics only | Persist DB constraints/facts for merchant-bound roles and active user binding | Phase 36 locked scope [VERIFIED: 36-SPEC.md; .planning/ROADMAP.md] | Migration preflight becomes required for existing active business users. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] |
| Projection-only `target_merchant_context` | AgentRun-level persisted target merchant and explicit classification | Phase 36 locked scope [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] | Future Phase 37 can evaluate readiness from persisted facts, not projections. [VERIFIED: src/agent/merchant_context.py] |
| Approval/action target binding added in Phase 34 | Cross-table consistency with AgentRun and ActionSafetySnapshot | Phase 36 locked scope [VERIFIED: src/db/migrations/versions/018_phase34_approval_action_bindings.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] | Existing Phase 34 service tests should be extended, not replaced. [VERIFIED: tests/actions/test_phase34_action_draft_bindings.py] |
| Future same-merchant run visibility | Still owner/admin-only in Phase 36 | Phase 35/36 constraints [VERIFIED: tests/replay/test_phase35_trace_replay_permissions.py; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md] | No API guard should grant same-merchant manager access in this phase. [VERIFIED: src/api/routers/traces.py; src/api/routers/agent_runs.py] |

**Deprecated/outdated:**
- Treating `merchant` as a recommended new role is deprecated; it remains compatibility/support-equivalent for existing users only. [VERIFIED: docs/contract-spec.md; .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]
- Treating `manager` as tenant-wide supervisor is outdated; the contract says manager is merchant-bound and not tenant-wide. [VERIFIED: docs/contract-spec.md]
- Using raw memory, RAG, prompt, thread id, user identity, or LLM output as authorization proof is prohibited for this phase. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md]

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| - | None. | - | All implementation-scope claims are sourced from the phase artifacts, local code, local environment probes, or official docs. [VERIFIED: source audit] |

## Open Questions (RESOLVED)

1. **What is the tenant selector for login/token/demo-token?**  
   - What we know: username identity should move toward `(tenant_id, username)`, but current auth payloads query username alone. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; src/api/routers/auth.py]  
   - What's unclear: whether the transitional selector should be request body field, header, tenant slug, demo-only default, or temporary "global unique until product selector" invariant. [VERIFIED: src/api/schemas/auth.py; src/api/routers/auth.py]  
   - Recommendation: make this Plan 1's explicit decision and test same-tenant duplicate prevention before relaxing the global unique constraint. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]
   - **Resolved decision:** Plan 36-02 uses optional trusted `tenant_id` in JSON `/login` and `/demo-token` requests. Username-only JSON login/demo-token remains a transitional path and fails closed when more than one principal matches. OAuth2 form `/token` remains username-only because `OAuth2PasswordRequestForm` has no tenant field; it also fails closed on duplicate usernames. Same-tenant duplicate usernames remain forbidden by `uq_users_tenant_username`, and cross-tenant duplicate usernames require the explicit JSON `tenant_id` selector.

2. **Where should AgentRun scope classification literals live?**  
   - What we know: CONTEXT leaves helper/module names and classification location to planner discretion. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
   - What's unclear: whether the codebase will prefer model-adjacent constants, a new `src/agent/run_scope.py`, or schema-level literals. [VERIFIED: source audit]  
   - Recommendation: choose one small domain helper and import it from ORM/tests/services to avoid string drift. [VERIFIED: tests/approvals/test_migration_contract.py pattern]
   - **Resolved decision:** Plan 36-03 uses `src/agent/run_scope.py` as the small domain helper/module. It owns the exact scope literals, `AgentRunScopeFacts`, and `classify_agent_run_scope`; ORM and migration tests assert the corresponding DB constraint names to prevent string drift.

3. **How much historical data can be backfilled to `business_merchant`?**  
   - What we know: allowed sources are orders, validated approval/action target merchant bindings, trusted Phase 34 binding material, or verified scoped `BusinessFactRefV1`. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]  
   - What's unclear: actual production/local DB row distribution is unknown from source research alone. [VERIFIED: source-only research scope]  
   - Recommendation: migration preflight should report counts and block or classify ambiguous legacy rows as `unknown_legacy` rather than guessing. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md]
   - **Resolved decision:** Plan 36-05 migration preflight/backfill uses only authoritative sources named in D-12. Ambiguous rows become `unknown_legacy` only when they do not already claim `business_merchant`; missing, malformed, contradictory, or unsafe business-scoped rows block migration. The migration must not guess from weak sources such as owner identity, requested_by/user merchant binding, thread id, prompt/final text, memory, RAG, LLM output, raw tool payload, `target_merchant_context`, or `replay_authorization_proof`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Tests, Python tooling, env isolation | yes | 0.11.2 | None needed. [VERIFIED: command -v uv; uv --version] |
| Python | App/tests | yes | 3.12.13 via `uv run python` | None needed. [VERIFIED: uv run python] |
| SQLAlchemy | ORM/migration tests | yes | 2.0.49 | None needed. [VERIFIED: uv run python] |
| Alembic | Migrations | yes | 1.18.4 | None needed. [VERIFIED: uv run python] |
| FastAPI | Auth/API tests | yes | 0.136.1 | None needed. [VERIFIED: uv run python] |
| Pydantic | Binding schemas | yes | 2.13.4 | None needed. [VERIFIED: uv run python] |
| pytest | Validation | yes | 9.0.3 | None needed. [VERIFIED: uv run python] |
| Docker | Local PostgreSQL service | yes | 29.4.2 | None needed. [VERIFIED: docker --version] |
| PostgreSQL CLI (`psql`, `pg_isready`) | Manual DB probing | no | - | Use Docker Compose plus SQLAlchemy/asyncpg-based tests; do not require CLI commands in the plan. [VERIFIED: command -v psql; command -v pg_isready; tests/conftest.py] |

**Missing dependencies with no fallback:**
- None for planning; PostgreSQL CLI tools are missing but not blocking because tests use SQLAlchemy/asyncpg and Docker Compose can supply the DB service. [VERIFIED: tests/conftest.py; docker-compose.yml]

**Missing dependencies with fallback:**
- PostgreSQL CLI tools: fallback to `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` and Docker Compose. [VERIFIED: AGENTS.md; docker-compose.yml]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio auto mode. [VERIFIED: uv run python; pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options] asyncio_mode = "auto"`. [VERIFIED: pyproject.toml] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/integration/test_auth.py tests/approvals/test_migration_contract.py tests/actions/test_phase34_action_draft_bindings.py tests/replay/test_phase35_trace_replay_permissions.py -q` [VERIFIED: AGENTS.md; listed test files exist] |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` [VERIFIED: AGENTS.md; pyproject.toml] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| MSH-01 | `merchant` remains merchant-bound compatibility role; no new tenant-wide/platform-wide semantics. [VERIFIED: .planning/REQUIREMENTS.md] | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py -q` | Existing partial; extend for deprecated-seed behavior. [VERIFIED: tests/platform/test_merchant_scope.py; tests/conftest.py] |
| MSH-02 | Active `support`/`manager`/`merchant` users require valid tenant-consistent merchant binding or fail closed. [VERIFIED: .planning/REQUIREMENTS.md] | unit + migration contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/approvals/test_migration_contract.py -q` | Existing partial; migration preflight tests needed. [VERIFIED: tests/platform/test_merchant_scope.py; tests/approvals/test_migration_contract.py] |
| MSH-03 | Tenant-scoped username identity or explicit transitional tenant-resolution contract. [VERIFIED: .planning/REQUIREMENTS.md] | integration + migration contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/approvals/test_migration_contract.py -q` | Existing auth tests; tenant duplicate/selector tests needed. [VERIFIED: tests/integration/test_auth.py] |
| MSH-04 | AgentRun target merchant binding and explicit scope classification. [VERIFIED: .planning/REQUIREMENTS.md] | unit + integration + migration contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py -q` | New file needed. [VERIFIED: source audit] |
| MSH-05 | Approval/action/snapshot target scope cannot contradict linked business-scoped run. [VERIFIED: .planning/REQUIREMENTS.md] | service + migration contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/approvals/test_phase36_scope_consistency.py -q` | Existing Phase 34 tests; new consistency file needed. [VERIFIED: tests/actions/test_phase34_action_draft_bindings.py] |
| MSH-06 | Migration/backfill uses only authoritative sources and rejects unsafe data. [VERIFIED: .planning/REQUIREMENTS.md] | migration contract + live DB migration smoke | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py -q` | Existing migration contract; new preflight smoke file needed. [VERIFIED: tests/approvals/test_migration_contract.py] |
| MSH-07 | Runtime auth does not widen: business facts same-merchant only; public policy separate; run/status/evidence/trace/replay owner/admin-only. [VERIFIED: .planning/REQUIREMENTS.md] | regression/integration/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/business/test_service.py tests/replay/test_phase35_trace_replay_permissions.py tests/test_trace_api.py -q` | Existing regression coverage; extend if guard files change. [VERIFIED: tests/platform/test_merchant_scope.py; tests/business/test_service.py; tests/replay/test_phase35_trace_replay_permissions.py; tests/test_trace_api.py] |
| MSH-08 | Readiness conclusion is exactly one of the three locked values. [VERIFIED: .planning/REQUIREMENTS.md] | unit/static/artifact test | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase36_readiness.py -q` | New file needed. [VERIFIED: source audit] |

### Sampling Rate

- **Per task commit:** run the focused command for touched surface, always through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md]
- **Per wave merge:** run the quick command in the Test Framework table. [VERIFIED: listed test files]
- **Phase gate:** run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` before `/gsd-verify-work` if local PostgreSQL is available; otherwise record DB availability as a verification blocker. [VERIFIED: AGENTS.md; tests/conftest.py]

### Wave 0 Gaps

- [ ] `tests/agent/test_phase36_run_scope.py` - covers MSH-04 runtime classifier and persisted AgentRun scope behavior. [VERIFIED: source audit]
- [ ] `tests/approvals/test_phase36_scope_consistency.py` - covers MSH-05 run/approval/action/snapshot contradictions. [VERIFIED: source audit]
- [ ] `tests/db/test_phase36_migration_preflight.py` or equivalent extension to `tests/approvals/test_migration_contract.py` - covers MSH-02/MSH-03/MSH-06 migration preflight cases. [VERIFIED: tests/approvals/test_migration_contract.py]
- [ ] `tests/replay/test_phase36_readiness.py` - covers MSH-08 readiness enum and no-widening regression linkage. [VERIFIED: source audit]
- [ ] Auth tests for tenant selector/transitional contract in `tests/integration/test_auth.py`. [VERIFIED: tests/integration/test_auth.py]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Tenant-aware principal lookup, JWT `sub` + `tenant_id` validation, FastAPI security dependencies. [VERIFIED: src/api/routers/auth.py; src/auth/permissions.py; CITED: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/] |
| V3 Session Management | limited | Bearer-token request auth is in scope; browser session/cookie management is not the Phase 36 surface. [VERIFIED: src/auth/permissions.py; src/auth/jwt.py] |
| V4 Access Control | yes | `TrustedContextFactory`, `require_merchant_access`, owner/admin-only run guards, cross-tenant 404 behavior. [VERIFIED: src/platform/trusted_context.py; src/auth/permissions.py; src/api/routers/traces.py; tests/replay/test_phase35_trace_replay_permissions.py] |
| V5 Input Validation | yes | Pydantic strict schemas, SQLAlchemy parameterized statements, Alembic preflight validation. [VERIFIED: src/approvals/schemas.py; src/db/migrations/versions/016_agent_run_memory_idempotency.py; CITED: https://docs.pydantic.dev/latest/api/config/] |
| V6 Cryptography | yes | Existing JWT/password hashing remains in scope as auth substrate; Phase 36 should not introduce custom cryptography. [VERIFIED: src/auth/jwt.py; tests/integration/test_auth.py] |

### Known Threat Patterns for MOCA Phase 36

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant run/resource existence leak | Information Disclosure | Tenant-filtered lookups return 404 for cross-tenant resources; keep owner/admin-only run/trace/replay guards. [VERIFIED: src/api/routers/traces.py; tests/replay/test_phase35_trace_replay_permissions.py] |
| Privilege escalation through legacy `merchant` or unknown roles | Elevation of Privilege | Keep `merchant` merchant-bound/support-equivalent; unknown roles deny-all. [VERIFIED: docs/contract-spec.md; src/platform/trusted_context.py] |
| Confused deputy via `server_merchant_scope` wildcard | Elevation of Privilege | Non-admin wildcard override must be rejected; wildcard only from trusted admin/system context. [VERIFIED: docs/contract-spec.md; src/platform/trusted_context.py] |
| Data poisoning via LLM/memory/RAG evidence | Tampering / Elevation of Privilege | Use only authoritative merchant proof for backfill and run scope; memory/RAG/LLM are not merchant authority. [VERIFIED: .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md; docs/contract-spec.md] |
| Approval/action/snapshot contradiction | Tampering / Repudiation | Compare target merchant, business fact refs, evidence refs, action payload hash, and safety snapshot hash across linked records. [VERIFIED: src/actions/service.py; docs/contract-spec.md] |
| Unsafe migration locks in bad history | Tampering / Availability | Preflight duplicate/null/contradictory rows and raise actionable migration errors before hard constraints. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-SPEC.md` - locked Phase 36 requirements and boundaries. [VERIFIED: local file]
- `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-CONTEXT.md` - locked decisions D-01 through D-20, discretion, deferred scope. [VERIFIED: local file]
- `.planning/REQUIREMENTS.md` - MSH-01 through MSH-08 requirement text. [VERIFIED: local file]
- `.planning/ROADMAP.md` - Phase 36 roadmap scope and success criteria. [VERIFIED: local file]
- `.planning/STATE.md` - v1.9/v2.0 project decisions and Phase 29.5/34/35 boundaries. [VERIFIED: local file]
- `docs/contract-spec.md` - normative role, business-scope, memory authority, action snapshot, and replay contracts. [VERIFIED: local file]
- `AGENTS.md` and `CLAUDE.md` - MOCA workflow, plan granularity, and test command rules. [VERIFIED: local files]
- `src/db/models.py`, `src/auth/permissions.py`, `src/platform/trusted_context.py`, `src/api/routers/auth.py`, `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/agent/trace.py`, `src/agent/merchant_context.py`, `src/approvals/schemas.py`, `src/actions/service.py` - implementation inventory. [VERIFIED: local files]
- `tests/conftest.py`, `tests/platform/test_merchant_scope.py`, `tests/integration/test_auth.py`, `tests/approvals/test_migration_contract.py`, `tests/actions/test_phase34_action_draft_bindings.py`, `tests/replay/test_phase35_trace_replay_permissions.py`, `tests/test_approval_api.py`, `tests/test_trace_api.py` - validation inventory. [VERIFIED: local files]
- Alembic official Operations docs - `add_column`, `create_index`, `create_check_constraint`, `drop_index`. [CITED: https://alembic.sqlalchemy.org/en/latest/ops.html]
- SQLAlchemy 2.0 PostgreSQL dialect docs - partial indexes via `postgresql_where`. [CITED: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html]
- Pydantic v2 docs - `ConfigDict(extra='forbid')`. [CITED: https://docs.pydantic.dev/latest/api/config/]
- FastAPI OAuth2 scopes docs - `SecurityScopes` and OAuth2 security dependencies. [CITED: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/]
- Context7 CLI fallback resolved/fetched Alembic, SQLAlchemy, Pydantic, and FastAPI documentation because Context7 MCP tools were not exposed in this agent environment. [VERIFIED: npx --yes ctx7@latest ...]

### Secondary (MEDIUM confidence)
- None needed; all critical planning claims were verified against local source or official documentation. [VERIFIED: source audit]

### Tertiary (LOW confidence)
- None. [VERIFIED: source audit]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions and tooling were verified from the local `uv` environment and project config; official docs verified relevant APIs. [VERIFIED: uv run python; pyproject.toml; cited docs]
- Architecture: HIGH - boundaries are locked in SPEC/CONTEXT and supported by local code inspection. [VERIFIED: 36-SPEC.md; 36-CONTEXT.md; source audit]
- Pitfalls: HIGH - each pitfall maps to existing code, locked decisions, or existing regression tests. [VERIFIED: source audit; tests/replay/test_phase35_trace_replay_permissions.py]
- Migration strategy: HIGH - existing Alembic preflight and Phase 34 migration-contract patterns provide direct local precedent. [VERIFIED: src/db/migrations/versions/016_agent_run_memory_idempotency.py; tests/approvals/test_migration_contract.py]
- Runtime state inventory: MEDIUM - repository-visible runtime state was audited, but actual production/local database row contents require migration preflight at execution time. [VERIFIED: source audit; tests/conftest.py]

**Research date:** 2026-06-30  
**Valid until:** 2026-07-07 for dependency versions and code topology; locked phase decisions remain valid until CONTEXT/SPEC changes. [VERIFIED: current_date; 36-CONTEXT.md]
