# Phase 36: Merchant-scope DB Hardening / Role Cleanup - Specification

**Created:** 2026-06-30
**Ambiguity score:** 0.11 (gate: <= 0.20)
**Requirements:** 10 locked

## Goal

MOCA hardens v1.9 merchant-bound business-role semantics at the database, migration, role-registry, and trace/replay-readiness boundary without widening run/status/evidence/trace/replay access beyond the existing owner/admin-only guard.

## Background

v1.9 completed the runtime contract for merchant-bound business roles, but the database still contains weaker or ambiguous facts that later authorization phases must not guess around.

The current contract says `support`, `manager`, and legacy `merchant` are merchant-bound roles, `admin` is the only human platform-wide business-data role, unknown roles are deny-all for business data, and `manager` is not a tenant-wide supervisor. It also keeps business-data AgentRun status/evidence/trace access limited to run owner and `admin` until a later phase proves same-merchant access through target merchant binding or scoped `BusinessFactRefV1`.

The current model still has several hardening gaps:

- `users.username` is globally unique while users already carry `tenant_id`.
- `users.merchant_id` is nullable, including for business roles.
- `AgentRun` has `tenant_id` and `user_id` but no persisted target merchant binding or explicit run scope classification.
- `ApprovalRequest` and `ActionDraft` already carry target merchant fields, but those fields need validity and consistency rules.
- `ActionSafetySnapshot` is an audit artifact tied to a run, but it does not expose an explicit target merchant binding or equivalent immutable scope proof.
- `RefundCase` and `Ticket` derive merchant ownership through `order_id -> orders.merchant_id`; they should not become competing merchant truth sources by accident.

Phase 36 turns these into falsifiable schema and migration requirements. Phase 37 can only expand same-merchant trace/replay authorization after Phase 36 produces a reliable readiness conclusion.

## Requirements

1. **Legacy merchant role deprecation**: Legacy `merchant` remains compatibility-only and support-equivalent for merchant-bound business data.
   - Current: The contract treats `merchant` as a legacy compatibility role, and permissions include it in merchant-bound roles.
   - Target: Role registry, contract-facing docs, seed data, and tests consistently mark `merchant` as deprecated compatibility, not a recommended new role, not tenant-wide, and not platform-wide.
   - Acceptance: Existing `merchant` users authenticate and retain support-equivalent same-merchant behavior; new role fixtures and seeds prefer `support` / `manager` / `admin`; tests prove `merchant` never receives wildcard business scope or manager-only visibility.

2. **Active business user merchant binding**: Active merchant-bound business users require valid merchant binding or fail closed.
   - Current: `users.merchant_id` is nullable, while the contract says missing merchant binding produces deny-all business scope.
   - Target: Active users with role `support`, `manager`, or legacy `merchant` are valid only with a tenant-consistent merchant binding. Historical active business users without a valid merchant binding are backfilled only from verified evidence, marked inactive/invalid, or left present but deny-all and blocked by migration/preflight policy.
   - Acceptance: Tests or migration gates reject newly active `support`, `manager`, or `merchant` users without valid merchant binding; invalid historical users do not receive guessed merchant scope; `admin` remains the only human role that can derive wildcard business merchant scope.

3. **Tenant-scoped username identity**: Username uniqueness becomes tenant-scoped with tenant-aware principal lookup.
   - Current: `users.username` is globally unique even though `users.tenant_id` exists.
   - Target: The unique principal key is tenant-scoped: duplicate usernames are rejected within one tenant and allowed across different tenants. Authentication and user lookup use a trusted tenant selector, tenant id, tenant slug, or equivalent tenant-resolved identity with username.
   - Acceptance: Same-tenant duplicate username creation fails; cross-tenant duplicate username creation succeeds; auth/user lookup tests prove username resolution cannot return an ambiguous principal without tenant context.

4. **AgentRun target merchant binding**: Business-scoped runs expose a persisted target merchant binding and explicit scope classification.
   - Current: `AgentRun` has no target merchant field or run scope classification; later authorization would need unsafe inference from owner, thread, prompt, or trace state.
   - Target: Every AgentRun is classified as exactly one of `business_merchant`, `policy_only` / `merchant_not_required`, or `unknown_legacy`. `business_merchant` requires exactly one trusted target merchant binding. `policy_only` / `merchant_not_required` uses no business merchant binding and must not become same-merchant business-visible later. `unknown_legacy` has no trusted binding and remains fail-closed.
   - Acceptance: Tests prove business runs cannot be classified without one target merchant; null target merchant is never ambiguous; unknown legacy and policy-only runs remain owner/admin-only; multi-merchant runs are not accepted in Phase 36.

5. **Authorization/audit root consistency**: Approval, action, and safety snapshot roots cannot contradict a linked business-scoped run.
   - Current: `ApprovalRequest` and `ActionDraft` contain target merchant fields, while `ActionSafetySnapshot` relies on run linkage and snapshot JSON/hash rather than an explicit scope proof.
   - Target: Approval requests, action drafts, and action safety snapshots have a target merchant binding or equivalent immutable scope proof whenever they are business-scoped. When linked to the same business-scoped run, their target merchant facts are consistent with the run.
   - Acceptance: Tests or migration gates reject or classify invalid any approval request, action draft, or safety snapshot whose target merchant contradicts its linked business-scoped run or linked approval/action root.

6. **Refund and ticket merchant ownership remains derived from order**: Refund and ticket rows do not become independent merchant truth sources by default.
   - Current: Refund cases and tickets point to orders, and orders carry canonical `merchant_id`.
   - Target: Refund and ticket merchant ownership continues to derive from `order_id -> orders.merchant_id`. Any redundant merchant field introduced for performance or consistency is explicitly non-authoritative and must be checked against the order merchant.
   - Acceptance: Business access tests continue to resolve refund/ticket merchant ownership through order ownership, and no test or service path treats a refund/ticket-local merchant value as a second source of truth.

7. **Authoritative backfill only**: Migration/backfill never guesses merchant scope from weak signals.
   - Current: Legacy rows may lack target merchant binding, and no Phase 36 migration contract exists.
   - Target: Backfill writes merchant target values only from authoritative sources: `orders.merchant_id`, existing approval/action target merchant fields after validation, trusted Phase 34 target merchant binding, or verified scoped `BusinessFactRefV1`. Backfill must not infer merchant scope from `requested_by -> user.merchant_id`, username, role name, thread id, free text, LLM output, memory content, RAG evidence, prompt text, or raw tool payload.
   - Acceptance: Migration tests cover clean data, invalid null business user, same-tenant duplicate username, contradictory target merchant facts, ambiguous legacy run, and invalid/malformed target merchant reference. Ambiguous rows become `unknown_legacy` / invalid or block migration; they are never silently guessed.

8. **No PostgreSQL RLS in Phase 36**: Phase 36 prepares DB facts but does not enable row-level security.
   - Current: The app enforces scope through services and authorization helpers, not PostgreSQL RLS.
   - Target: Phase 36 may add schema constraints, indexes, foreign keys, checks, migration gates, and tests, but it does not introduce RLS policies, database-session tenant variables, or request/session DB context enforcement.
   - Acceptance: No Phase 36 plan or test requires RLS to pass; future RLS remains a separately scoped phase consuming Phase 36's hardened facts.

9. **Runtime authorization does not widen**: Existing v1.9 runtime boundaries continue to pass after DB hardening.
   - Current: Merchant-bound users can access only their merchant's business facts; tenant public policy retrieval is separate; run/status/evidence/trace/replay access is intentionally owner/admin-only for non-admin actors.
   - Target: Phase 36 changes data facts and migration gates only. It does not open same-merchant manager run/status/evidence/trace/replay visibility, does not redo Phase 34 approval semantics, does not make manager tenant-wide, and does not let memory/RAG/LLM/tool payloads prove current business facts.
   - Acceptance: Regression tests prove BusinessFactService authority, memory contextual-only boundaries, RAG/claim boundaries, tenant public policy retrieval, Phase 34 approval same-merchant access, cross-tenant 404/no-leak, same-tenant cross-merchant 403, and owner/admin-only run/trace/replay behavior remain unchanged.

10. **Phase 37 readiness conclusion**: Phase 36 ends with an explicit trace/replay authorization readiness result.
    - Current: Future same-merchant trace/replay access is known to be deferred, but no concrete readiness result exists.
    - Target: Phase 36 produces exactly one readiness conclusion for Phase 37: `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`. The conclusion lists the facts Phase 37 may trust, the facts it must not trust, and any blockers.
    - Acceptance: Phase completion artifacts contain one of the three readiness values with evidence. If the result is not `ready_with_agent_run_binding`, Phase 37 remains blocked or must explicitly reduce scope before enabling manager access.

## Boundaries

**In scope:**

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

**Out of scope:**

- Same-merchant manager AgentRun/status/evidence/trace/replay authorization expansion - future Phase 37.
- Manager live stream observation or event subscription expansion - stream execution and event safety need separate surface rules.
- PostgreSQL RLS enablement - future hardening after schema facts and test harness are stable.
- Physical deletion of legacy `merchant` role - high rollback/product risk; this phase deprecates and preserves compatibility.
- Tenant-wide manager or supervisor semantics - contradicts v1.9 MER-01 contract.
- Same-merchant `support` trace/replay visibility - distinct product decision from manager review.
- Merchant-specific policy retrieval - tenant public policy scope remains separate.
- `TrustedSystemContext` or system wildcard actor model - requires a separate contract.
- Real external action execution - still outside the current approval/action-draft boundary.
- Multi-merchant run support - requires separate product and projection rules.
- Broad merchant_id denormalization into every table - Phase 36 only hardens target facts where they are authorization/audit roots.
- Raw trace/replay/prompt/tool payload projection changes - Phase 37 projection spec owns that surface.

## Constraints

- `docs/contract-spec.md` remains the normative contract source; Phase 36 must record any required contract correction rather than silently diverging.
- All validation commands in MOCA must use project-scoped entry points such as `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid verification.
- Cross-tenant business resources remain no-leak 404 at API paths; same-tenant out-of-merchant-scope business resources remain 403; service/tool permission-denied paths must not reveal resource existence.
- `server_merchant_scope` remains trusted narrowing only and cannot widen non-admin human actors.
- Admin wildcard business scope cannot be reused as system job wildcard scope.
- Migration/backfill must be idempotent: rerunning on unchanged data produces the same classification.
- Rollback/downgrade behavior must be documented and tested where reversible; any irreversible downgrade must be explicit and must not silently destroy legacy business data.
- Phase 36 must not treat target-state spec text as already implemented fact during planning or verification.

## Acceptance Criteria

- [ ] Role registry, contract-facing docs, seeds, and tests identify legacy `merchant` as deprecated compatibility, support-equivalent, and non-wildcard.
- [ ] Existing legacy `merchant` users retain same-merchant support-equivalent access, while new fixtures/seeds prefer `support`, `manager`, and `admin`.
- [ ] Active `support`, `manager`, and legacy `merchant` users require valid tenant-consistent merchant binding or fail closed.
- [ ] Unknown roles remain deny-all for business data.
- [ ] `admin` remains the only human role that can derive wildcard business merchant scope.
- [ ] Manager is not treated as tenant-wide supervisor in tests.
- [ ] Username uniqueness is tenant-scoped: same-tenant duplicate usernames fail, cross-tenant duplicate usernames pass.
- [ ] Auth and user lookup tests prove username principal resolution includes trusted tenant context or equivalent tenant-resolved identity.
- [ ] Business-scoped AgentRuns persist trusted target merchant binding and explicit scope classification.
- [ ] `policy_only` / `merchant_not_required` runs do not become same-merchant business-visible.
- [ ] `unknown_legacy` runs remain owner/admin-only.
- [ ] Null target merchant is never interpreted as both policy-only and unknown legacy.
- [ ] Approval request, action draft, and action safety snapshot target merchant facts do not contradict linked business-scoped run facts.
- [ ] Cross-table target merchant contradictions are rejected, migration-blocked, or classified invalid.
- [ ] Refund/ticket merchant ownership remains derived from order ownership unless a redundant copy is explicitly checked against order merchant.
- [ ] Backfill uses only authoritative merchant proof sources and never guesses from requested-by user, prompt, thread, LLM output, memory, RAG evidence, free text, or raw tool payload.
- [ ] Migration/preflight tests cover clean data, null active business user, same-tenant duplicate username, malformed target merchant ref, contradictory target merchant binding, and ambiguous legacy run.
- [ ] Backfill is idempotent.
- [ ] Rollback/downgrade behavior is documented and tested or explicitly blocked when data-preserving downgrade is impossible.
- [ ] PostgreSQL RLS is not enabled and no test requires DB-session tenant context.
- [ ] BusinessFactService remains current business fact authority.
- [ ] Memory remains contextual-only and cannot satisfy current business fact, approval/action, or replay truth.
- [ ] RAG/claim verification boundaries remain unchanged.
- [ ] Tenant public policy retrieval still works for authenticated ordinary business users and is not filtered by business merchant scope.
- [ ] Phase 34 approval same-merchant manager behavior still passes existing regression tests.
- [ ] Run/status/evidence/trace/replay manager visibility remains owner/admin-only after Phase 36.
- [ ] Cross-tenant business resources still do not leak existence.
- [ ] Same-tenant out-of-merchant-scope business resources still deny access.
- [ ] No new wildcard merchant scope path is introduced outside trusted admin role semantics.
- [ ] Phase completion artifacts record exactly one Phase 37 readiness result: `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`.

## Ambiguity Report

| Dimension           | Score | Min   | Status | Notes |
|---------------------|-------|-------|--------|-------|
| Goal Clarity        | 0.92  | 0.75  | PASS   | Goal is limited to DB/role/migration/readiness hardening and explicitly excludes access widening. |
| Boundary Clarity    | 0.90  | 0.70  | PASS   | Phase 37, RLS, stream visibility, system wildcard, and raw replay projection are explicit non-goals. |
| Constraint Clarity  | 0.84  | 0.65  | PASS   | Contract, no-leak, test-entry, migration, downgrade, and no-RLS constraints are named. |
| Acceptance Criteria | 0.86  | 0.70  | PASS   | Criteria map to role, user, username, run scope, audit roots, migration, regression, and readiness checks. |
| **Ambiguity**       | 0.11  | <=0.20| PASS   | User-provided Phase 36/37 refinement resolved major product and security boundaries. |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | What remains after v1.9 MER-01 and Phase 35? | Runtime merchant scope and owner/admin-only trace/replay guard are done; DB hardening, role cleanup, and trace/replay readiness remain. |
| 2 | Boundary Keeper | Should Phase 36 open same-merchant trace/replay access? | No. Phase 36 must not widen run/status/evidence/trace/replay visibility; Phase 37 owns that expansion. |
| 3 | Security Reviewer | What proof can future trace/replay authorization trust? | Phase 36 must create or validate run-level target merchant binding and explicit scope classification; missing or ambiguous legacy proof fails closed. |
| 4 | Data Model Reviewer | Which records need target merchant truth? | AgentRun and authorization/audit roots need explicit binding or immutable scope proof; refund/ticket remain order-derived by default. |
| 5 | Product Reviewer | What happens to legacy `merchant` role? | Keep as deprecated compatibility, support-equivalent, and non-wildcard; physical deletion is deferred. |
| 6 | Migration Reviewer | How should unsafe legacy data be handled? | Backfill only from authoritative proof; ambiguous data becomes `unknown_legacy` / invalid or blocks migration, never guessed. |
| 7 | Operations Reviewer | Should Phase 36 introduce PostgreSQL RLS? | No. RLS is deferred; Phase 36 prepares stable DB facts and tests only. |

---

*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Spec created: 2026-06-30*
*Next step: $gsd-discuss-phase 36 - implementation decisions (how to build the locked requirements above)*
