# Deferred: Merchant-scope database hardening and role cleanup

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phase: Phase 36+ hardening / future milestone

## Reason

Phase 29.5 and v1.9 can enforce the target model at API/service boundaries without large schema migration. Database hardening should wait until role semantics and BusinessFactService/Approval/Replay scope bindings are stable.

## Required outcome candidates

- Decide whether to delete or fully migrate legacy `merchant` role.
- Consider role naming migration or role enum/permission table.
- Consider constraining ordinary business users to non-null `merchant_id`.
- Consider changing username uniqueness from global to `(tenant_id, username)`.
- Consider denormalizing `merchant_id` onto `refund_cases`, `tickets`, `approval_requests`, `agent_runs`, and/or `action_drafts` if it reduces join risk.
- Consider PostgreSQL RLS for tenant/merchant strong isolation.
- Consider merchant-specific policy scope only after tenant public policy behavior remains stable.

## Verification entry

- Migration tests for constraints/indexes if introduced.
- Backfill tests for existing demo/user data.
- RLS or DB-level policy tests only if the hardening phase adopts database-enforced isolation.
