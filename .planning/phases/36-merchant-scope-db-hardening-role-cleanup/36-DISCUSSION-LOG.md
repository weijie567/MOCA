# Phase 36: Merchant-scope DB Hardening / Role Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30T03:58:31Z
**Phase:** 36-merchant-scope-db-hardening-role-cleanup
**Areas discussed:** AgentRun scope facts, role/user/login identity, migration/backfill gates, authorization/audit root consistency and readiness

---

## Workflow Note

The normal interactive selection UI was unavailable in the current Codex Default mode. Per the GSD skill adapter fallback, the discussion used the recommended default path: cover all identified gray areas and adopt the conservative implementation decisions already supported by Phase 36 SPEC.md, the user's Phase 36/37 refinement, and codebase scouting.

No scope was added beyond Phase 36.

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Discuss all recommended areas | Cover AgentRun scope facts, role/auth identity, migration/backfill gates, and cross-table consistency/readiness. | yes |
| Discuss only high-risk items | Cover AgentRun scope, migration/backfill, and auth tenant lookup only. | |
| Write context directly | Adopt all recommended defaults without area-by-area analysis. | |

**User's choice:** Fallback selected "Discuss all recommended areas" because interactive selection was unavailable.
**Notes:** Phase 36 SPEC.md already locked WHAT; discussion only captured HOW constraints for planning.

---

## AgentRun Scope Facts

| Option | Description | Selected |
|--------|-------------|----------|
| AgentRun-level binding | Make AgentRun the primary persisted target merchant fact for future trace/replay authorization. | yes |
| Derived refs only | Depend on BusinessFactRefV1 / approval refs without run-level binding. | |
| Owner inference | Infer from requested_by/user merchant identity. | |

**Selected decision:** AgentRun-level target merchant binding and explicit scope classification are the recommended planning target.
**Notes:** Owner inference remains disallowed. Derived refs may support consistency/readiness but should not widen visibility without a trusted run-level binding.

---

## Role, User, and Login Identity

| Option | Description | Selected |
|--------|-------------|----------|
| Compatibility role model | Keep `users.role` as runtime compatibility source; deprecate but do not delete legacy `merchant`. | yes |
| Full role registry migration | Make `roles` / `user_roles` authoritative in this phase. | |
| Remove legacy merchant | Physically delete or migrate all legacy merchant users now. | |

**Selected decision:** Keep compatibility model and harden semantics/tests. Do not perform a full role authority migration in Phase 36.
**Notes:** Username identity moves toward `(tenant_id, username)`, but auth routes currently query username alone; planning must include tenant-resolution or a documented transitional invariant.

---

## Migration and Backfill Gates

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed preflight | Detect unsafe data before hard constraints; block or classify ambiguous rows. | yes |
| Best-effort guessing | Infer merchant scope from owner/thread/prompt-like weak signals. | |
| RLS-first hardening | Introduce PostgreSQL RLS while doing schema hardening. | |

**Selected decision:** Use fail-closed Alembic preflight/backfill gates and defer PostgreSQL RLS.
**Notes:** Existing migrations such as `016_agent_run_memory_idempotency.py` provide the local preflight pattern.

---

## Authorization/Audit Root Consistency and Readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Consistency hardening only | Harden approval/action/snapshot target merchant facts while keeping runtime authorization unchanged. | yes |
| Phase 37 access expansion | Open same-merchant manager trace/replay after adding fields. | |
| Broad denormalization | Add merchant_id to every related business table as a new authority. | |

**Selected decision:** Harden cross-table consistency and produce a Phase 37 readiness result without widening runtime visibility.
**Notes:** Refund/ticket merchant ownership remains order-derived by default. ActionSafetySnapshot needs explicit binding or immutable scope proof if used as authorization/audit root.

---

## the agent's Discretion

- Exact helper/module names for scope classification and migration preflight helpers.
- Exact index and constraint names, as long as they are stable and covered by migration-contract tests.
- Exact plan split, with a strong preference for multiple small plans rather than one large plan.

## Deferred Ideas

- Phase 37 same-merchant manager trace/replay safe projection.
- PostgreSQL RLS.
- Physical deletion of legacy `merchant`.
- Same-merchant support visibility.
- Stream event visibility expansion.
- Multi-merchant run support.
- Trusted system wildcard actor model.
- Real external action execution.
