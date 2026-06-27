# Deferred: Approval and ActionDraft merchant binding

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phase: Phase 34 Approval and ActionDraft Boundary Hardening

## Reason

ApprovalRequest and ActionDraft currently lack a complete target merchant binding suitable for full manager-scoped queues. Phase 29.5 must not half-implement final approval visibility by inferring from incomplete data, but it also must not leave manager tenant-wide approval visibility or wildcard resume active. Phase 34 owns final approval/action boundary hardening.

## Required outcome

- ApprovalRequest binds target merchant or scoped `BusinessFactRefV1`.
- ActionDraft binds target merchant, business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots.
- `manager` can list/decide only approvals for own merchant.
- Approval resume cannot use wildcard `server_merchant_scope` for non-admin human actors.
- ACTION_DRAFT_PERMISSION may be injected by trusted server code, but it must not widen merchant scope.
- Admin/platform-wide review remains explicit and auditable.
- Phase 29.5 interim guard: manager approval list/get/decide is admin-only / fail-closed until Phase 34 target merchant binding exists. Phase 29.5 must not use `requested_by -> user.merchant_id` as a temporary authorization approximation.
- System-owned wildcard approval/action scope is not allowed through `TrustedContextFactory.create_from_request(user=...)`; it requires a future trusted system context contract.

## Verification entry

- Tests for Phase 34 target state: manager A cannot see or decide merchant B approvals once target merchant binding exists.
- Tests for Phase 29.5 interim guard: manager cannot list/get/decide approvals; admin can.
- Tests for approval resume using target merchant binding instead of `{"merchant_ids":["*"]}` for manager.
- Tests that ordinary chat cannot forge approval/action authority or merchant scope.
