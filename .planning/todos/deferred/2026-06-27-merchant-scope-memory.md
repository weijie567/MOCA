# Deferred: Memory merchant scope and cross-merchant contamination guards

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phase: Phase 31 Memory Platform Boundary

## Reason

Phase 29.5 defines merchant-bound roles but does not fully redesign memory APIs. Phase 31 owns session context, long-term memory, case memory, conversation log, workflow checkpoint, working state, and memory write policy boundaries.

Phase 29.5 still changes the input scope consumed by current memory executors: `support` / `manager` move from wildcard-style scope to `[merchant_id]` or deny-all `[]`. Any existing memory code that consumes merchant scope immediately must fail closed and should get a Phase 29.5 smoke regression; the full cross-merchant memory redesign remains Phase 31.

## Required outcome

- Memory context load/write APIs preserve tenant and merchant boundaries.
- Phase 29.5 does not leave memory reads/writes with broader scope than the newly derived trusted merchant scope.
- Same-thread session memory cannot carry merchant A slots, summaries, or tool summaries into merchant B context.
- Long-term and case memory candidates include explicit scope tags that cannot satisfy policy evidence, current business fact, approval/action authority, or replay truth.
- Merchant-bound users with missing `merchant_id` do not write business-object memory.
- Admin/platform-wide reads remain explicit and auditable.

## Verification entry

- Phase 29.5 smoke test that memory executor/projection follows the new `merchant_scope=[merchant_id]` / `[]` semantics and does not retain wildcard behavior for `support` / `manager`.
- Tests for cross-merchant memory isolation, stale/wrong-scope slot rejection, prompt context no-leak, and memory authority-boundary preservation.
