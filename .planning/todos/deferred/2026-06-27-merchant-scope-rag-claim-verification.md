# Deferred: RAG claim verification and scoped business-fact authority

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phase: Phase 33 RAG Context Build and Claim Verification

## Reason

Phase 29.5 separates tenant public policy retrieval from business merchant scope and adds interim guards so merchant-bound users cannot read out-of-merchant business data. It does not make RAG claim verification authoritative for scoped business facts.

Phase 33 owns the deeper RAG/claim boundary: policy evidence, business facts, and generated claims must preserve their source authority and merchant scope through context build, claim verification, and final response composition.

## Required outcome

- Tenant public policy evidence remains tenant-scoped and is not filtered by business `merchant_scope=[]`.
- Business-fact claims rely on scoped `BusinessFactRefV1` / BusinessFactService authority, not raw tool summaries or LLM inference.
- Claim verification rejects or downgrades business claims when scoped business facts are missing, denied, or out of merchant scope.
- Prompt summaries, RAG context snippets, and final answers do not convert denied resource identifiers into asserted business facts.
- Phase 33 consumes Phase 29.5 role/merchant-scope semantics and Phase 30 BusinessFactService no-leak results.

## Verification entry

- Tests where support/manager can retrieve tenant public policy but cannot use policy or memory context to assert facts about another merchant's order/refund/ticket.
- Tests where denied or missing scoped business facts prevent final response business claims.
- Tests that `BusinessFactRefV1` authority, policy evidence, and memory context remain distinguishable in claim verification.
