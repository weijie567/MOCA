# Requirements: MOCA v2.1 Tool Platform Hardening

**Defined:** 2026-07-01
**Core Value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.

**Milestone goal:** Clean up the tool-call platform's contract debt and implementation gaps so tool contracts are as sound as the codebase allows, and so `docs/contract-spec.md` and the implementation agree.

## v2.1 Requirements

### Tool Contract Integrity

- [x] **TPH-01**: Each of the eight registered tools (`get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, `get_merchant_risk`, `search_policy`, `search_sop`, `search_case_memory`) declares a real `output_schema` for `ToolResultV2.data`, and the `ToolRuntime` output-validation gate enforces it — an executor result whose `data` fails the declared schema is mapped to an `invalid_response` `ToolResultV2` instead of passing through, replacing the current no-op `{"type":"object"}`.
- [ ] **TPH-02**: `docs/contract-spec.md` §12.5/§12.6 normative type definitions match the implemented contract fields — adding the implemented-but-unspecified fields (`ToolDescriptor.executor` / `exposure` / `requires_approval` / `requires_safety_snapshot` / `requires_idempotency_key`, `event_family` value `action`, `ToolPolicyDecision.runtime_available` / `availability_summary`, `ToolCallContext.effective_at` / `approval_ref` / `safety_snapshot_ref`) — without redefining, widening, or renaming any §8.0-locked `TrustedContext`-projected identity field. Spec change goes through the dual-AI review workflow.

### Tool Declaration Consolidation

- [x] **TPH-03**: Tool declarations resolve from a single-source registry; duplicate hardcoded lists (`catalog._IDENTIFIER_SCHEMAS`, `manager.INVESTIGATE_TOOL_NAMES`) are either derived from that registry or consistency-checked against it, so adding or changing a tool does not require hand-editing multiple lists (satisfies spec §12.6 single-declaration / no-drift rule).

### Runtime / Policy Internal Convergence

- [x] **TPH-04**: `ToolRuntime` failure paths produce their `(error result, projection, decision event, outcome tuple)` through one shared helper rather than ten duplicated branches, and `ToolPolicyEngine.runtime_auth` expresses its authorization checks as a declarative gate sequence — with existing tool-platform, policy, and runtime tests remaining green and no change to any external contract shape.

## Future Requirements

_None. This milestone is a bounded, pre-scoped cleanup._

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changing `ToolCallContext` identity fields | Locked by spec §8.0 as `TrustedContext` projections — MUST NOT redefine/widen/rename. |
| Rebuilding domain ownership / merchant-scope enforcement | Already implemented in BusinessFactService (`_merchant_scope_allows` + no-leak); not a gap. |
| High-blast-radius `ToolResultV2` field additions/removals | 7 external consumers; defer envelope field changes, keep this milestone to `output_schema` (data-shape) enforcement only. |
| New tools or new executors | Milestone is contract/impl hardening of existing 8 tools, not capability expansion. |
| New policy gates (rate limit, cost budget) | TPH-04 only makes the gate pipeline declarative to enable future gates; it does not add them. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TPH-03 | Phase 37 | Complete |
| TPH-04 | Phase 37 | Complete; DB-backed pytest pending local PostgreSQL |
| TPH-01 | Phase 38 | Complete; DB-backed pytest pending local PostgreSQL |
| TPH-02 | Phase 39 | Pending |

**Coverage:** 4/4 v2.1 requirements mapped, each to exactly one phase. 3 complete, 1 pending. No orphans, no duplicates.
