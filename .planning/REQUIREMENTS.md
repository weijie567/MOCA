# Requirements: MOCA v2.0 Merchant Scope Hardening

**Defined:** 2026-06-30
**Core Value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.

## v2.0 Requirements

### Merchant Scope Hardening

- [ ] **MSH-01**: Legacy `merchant` role is documented and enforced as deprecated compatibility-only, semantically equivalent to merchant-bound `support` for business-data access and never platform-wide.
- [ ] **MSH-02**: Active business users with `support`, `manager`, or legacy `merchant` role have a valid merchant binding, while invalid or ambiguous legacy users fail closed instead of receiving guessed scope.
- [ ] **MSH-03**: Username identity is tenant-scoped or guarded by an explicit transitional tenant-resolution contract, with tests preventing same-tenant duplicate principal ambiguity.
- [ ] **MSH-04**: `AgentRun` records have an unambiguous target merchant binding model and explicit scope classification for `business_merchant`, `policy_only` / `merchant_not_required`, and `unknown_legacy` runs.
- [ ] **MSH-05**: Authorization and audit root records with target merchant scope, including approval requests, action drafts, and safety snapshots, cannot contradict each other when linked to the same business-scoped run.
- [ ] **MSH-06**: Migration and backfill gates only use authoritative sources for merchant scope, classify ambiguous legacy records as fail-closed, and reject unsafe data before applying hard constraints.
- [ ] **MSH-07**: Existing runtime authorization behavior does not regress: merchant-bound users remain same-merchant-only for business facts, tenant public policy retrieval remains separate, and run/status/evidence/trace/replay visibility remains owner/admin-only.
- [ ] **MSH-08**: Phase 36 emits a trace/replay authorization readiness conclusion for future Phase 37, using one of `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`.

## Future Requirements

### Trace / Replay Authorization

- **TRR-01**: Same-merchant manager visibility for run status, evidence summary, trace safe projection, and replay safe projection is implemented only after Phase 36 proves a trustworthy run-level merchant binding.

### Database Isolation

- **RLS-01**: PostgreSQL Row Level Security may be introduced in a later hardening phase after Phase 36 schema and scope facts are stable.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Same-merchant manager run/trace/replay authorization expansion | Future Phase 37; Phase 36 must not widen visibility. |
| Manager live stream execution or observation | `/events` currently claims/executes pending runs and remains owner-only. |
| PostgreSQL RLS enablement | Too large for Phase 36; this milestone prepares schema constraints and migration gates only. |
| Physical deletion of legacy `merchant` role | High rollback/product risk; Phase 36 deprecates and preserves compatibility. |
| Tenant-wide manager/supervisor visibility | Contradicts v1.9 MER-01 role semantics. |
| Merchant-specific policy retrieval | Tenant public policy scope remains separate from business merchant scope. |
| Trusted system wildcard actor model | Requires a separate `TrustedSystemContext` contract. |
| Real external action execution | Still outside MOCA's current demo/action-draft boundary. |
| Multi-merchant run support | Requires a separate product and projection spec. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MSH-01 | Phase 36 | Pending |
| MSH-02 | Phase 36 | Pending |
| MSH-03 | Phase 36 | Pending |
| MSH-04 | Phase 36 | Pending |
| MSH-05 | Phase 36 | Pending |
| MSH-06 | Phase 36 | Pending |
| MSH-07 | Phase 36 | Pending |
| MSH-08 | Phase 36 | Pending |

**Coverage:**
- v2.0 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after milestone v2.0 initialization*
