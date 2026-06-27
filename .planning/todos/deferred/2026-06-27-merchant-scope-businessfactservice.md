# Deferred: BusinessFactService merchant scope and domain ownership proof

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phase: Phase 30 BusinessFactService Boundary

## Reason

Phase 29.5 locks role and merchant-scope semantics but does not make BusinessFactService the authority for current business facts. Phase 30 owns `BusinessFactResultV1` / `BusinessFactRefV1`, so order/refund/ticket scope checks should be completed there rather than half-implemented in API routes only.

## Required outcome

- BusinessFactService reads consume trusted `tenant_id`, `merchant_scope`, `role`, and `permissions`.
- `support`, `manager`, and legacy `merchant` can only receive facts for their own merchant.
- `admin` is the only platform-wide human business-data role.
- `order_no`, `refund_case_no`, and `ticket_id` undergo domain ownership proof before facts are returned.
- `BusinessFactResultV1.permission_denied` does not reveal whether the underlying resource exists.
- `BusinessFactRefV1` is emitted only after scope checks pass.
- ToolPlatform `requires_domain_scope_check` is resolved by BusinessFactService, not left as a marker.
- Prompt summaries, graph business facts, and final response business-fact claims are emitted only after domain ownership proof passes.
- API-layer 403/404 semantics are not reused as service/tool existence signals; service/tool permission denial remains no-leak.

## Verification entry

- Tests for same-merchant allow, same-tenant cross-merchant deny, cross-tenant not found/no-leak, missing merchant deny, and admin cross-merchant allow.
- Tests that no `BusinessFactRefV1`, graph fact, or prompt summary is emitted before scope pass.
- Tests that RAG, memory, LLM inference, and raw repository rows cannot substitute missing or out-of-scope business facts.
