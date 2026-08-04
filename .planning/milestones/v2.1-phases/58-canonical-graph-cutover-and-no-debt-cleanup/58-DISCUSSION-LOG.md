# Phase 58: Canonical Graph Cutover and No-Debt Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 58-canonical-graph-cutover-and-no-debt-cleanup
**Mode:** `--auto`
**Areas discussed:** Final no-debt scope, compatibility alias cleanup, trace/API/eval/docs cleanup, validation strategy

---

## Final No-Debt Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Close Phase 50 Final No-Debt Gate exactly | Use the Phase 50 checklist as the hard completion contract and avoid silent exceptions. | ✓ |
| Only clean obvious source aliases | Faster but risks leaving migration debt in projections/tests/docs. | |
| Reopen target graph semantics | Out of scope unless current sources prove the accepted spec is wrong. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Current code evidence shows active graph registrations already equal the 15 canonical nodes and route maps have no legacy destinations. Phase 58 should preserve that state and remove remaining migration scaffolding.

---

## Compatibility Alias Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Delete or internalize all `DELETE_BY_PHASE_58` surfaces | Close every explicit compatibility marker with tests and classification. | ✓ |
| Keep wrappers for test convenience | Preserves debt and contradicts CAGM-09. | |
| Convert all historical references to canonical names | Too risky for historical row readability and may rewrite facts. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Historical production data should not be bulk-mutated. Current-run behavior must be canonical; historical readability can remain only as bounded historical/data projection, not active graph compatibility.

---

## Trace/API/Eval/Docs Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical for current runs, historical-only for old rows | Keeps current contract simple while preserving old trace readability. | ✓ |
| Preserve legacy names in UI/API tests | Makes current-run vocabulary ambiguous. | |
| Remove all old-name tests blindly | Could lose historical projection coverage without replacement. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Projection tests should either assert canonical current-run behavior or explicitly model historical rows. Current docs should not present legacy names as runtime authority.

---

## Validation Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Static classifier plus broad closeout suite | Verifies no active runtime legacy debt remains and keeps scan evidence auditable. | ✓ |
| Rely on existing Phase 57 suite | Insufficient because Phase 57 intentionally left Phase 58 deletion candidates. | |
| Manual inspection only | Not acceptable for final migration gate. | |

**User's choice:** Auto-selected recommended default.
**Notes:** All commands must use MOCA-approved Python/pytest entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.

---

## the agent's Discretion

- Split Phase 58 planning by ownership boundary rather than making a single oversized plan.
- Choose exact focused test sets per cleanup slice, then run a broad closeout suite.

## Deferred Ideas

None.
