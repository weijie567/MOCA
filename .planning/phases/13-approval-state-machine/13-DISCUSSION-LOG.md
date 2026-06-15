# Phase 13: Approval State Machine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `13-CONTEXT.md` - this log preserves alternatives considered.

**Date:** 2026-06-15
**Phase:** 13-Approval State Machine
**Mode:** `$gsd-discuss-phase 13 --all`
**Areas discussed:** Owner package and module boundaries, DB strategy, ApprovalService boundary, snapshot/hash contract, old path quarantine, acceptance test floor

---

## Owner Package and Module Boundaries

| Option | Description | Selected |
| --- | --- | --- |
| Add `src/approvals/` as owner package | ApprovalService, approval policy, commands/results, repository, state machine, snapshots, events live under one domain boundary. | yes |
| Keep approvals split across API router and `src/repositories/` | Minimum diff, but preserves current owner drift. | |
| Put hash/snapshot entirely under `src/actions/` | Makes Phase 14 own a Phase 13 safety contract and risks rework. | |

**Choice:** Add `src/approvals/`; put `CanonicalHashProfile v1` in shared `src/common/canonical_hash.py`; put `ActionSafetySnapshot` builder/schema under `src/approvals/`.
**Notes:** User explicitly prefers architecture clarity over minimum diff and wants to avoid the tool-system style compatibility trap.

---

## Database Strategy

| Option | Description | Selected |
| --- | --- | --- |
| Extend v1 `approval_requests` only | Fastest path, but delays level/assignment/decision/event ownership and invites another migration. | |
| Introduce target approval tables now | Adds `approval_levels`, `approval_assignments`, `approval_decisions`, `approval_events`, and v2 request fields while runtime remains single-level. | yes |
| Defer `action_safety_snapshots` to Phase 14 | Lets action draft invent its own binding fields; contradicts Phase 13 ownership. | |

**Choice:** Create `action_safety_snapshots` and target approval tables in Phase 13. Existing v1 rows may remain nullable/read-only for migration, but cannot authorize action without revalidation into a v2 revision.
**Notes:** New active records require non-null action payload hash and safety snapshot hash. Historical rows with missing hashes may be rejected/cancelled/expired/superseded, not approved into action.

---

## ApprovalService Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Router continues transition and graph resume | Current behavior, but router owns too much truth and builds raw resume dicts. | |
| Service owns transitions and returns trusted resume payload | Router authenticates/parses, constructs trusted command, calls service, then resumes graph only with typed service result. | yes |
| Graph node owns transition truth | Centralizes around LangGraph but makes interrupt payload authoritative and hard to test transactionally. | |

**Choice:** `ApprovalService` owns create/decide/respond/edit/expire transitions, CAS, event writing, and trusted `approval_result.v1` resume payload production.
**Notes:** Router must not call `ApprovalRepository.decide(...)` or assemble resume dicts. Ordinary chat and LLM output cannot create trusted approval state.

---

## Snapshot and Hash Contract

| Option | Description | Selected |
| --- | --- | --- |
| Start with service/router migration | Moves behavior before hash contract is fixed; high risk of mismatched serialization. | |
| Start with canonical hash and snapshot golden tests | Freezes bytes and schema projection before approval/action consumers depend on them. | yes |
| Reuse legacy policy/evidence refs as guard | Compatibility-first, but aliases cannot prove exact payload/evidence/config binding. | |

**Choice:** Implement `CanonicalHashProfile v1` golden tests first, then `ActionSafetySnapshot` golden tests, then service/API integration.
**Notes:** Authorization requires exact `action_payload_hash + safety_snapshot_hash`. `policy_snapshot_ref` and `evidence_snapshot_ref` are nullable aliases only.

---

## Old Path Quarantine

| Option | Description | Selected |
| --- | --- | --- |
| Keep `ApprovalRepository.decide(...)` public | Easy migration but allows routers/tests to keep using old transition truth. | |
| Delete or package-private quarantine it | Forces all transitions through `ApprovalService` and adds static tests against new imports. | yes |
| Keep `ApprovalStep` as final event model | Avoids a table now but blocks target approval event/replay refs. | |

**Choice:** Delete or quarantine old transition APIs in Phase 13; keep `ApprovalStep` only as compatibility audit row for existing trace fallback.
**Notes:** New approval lifecycle truth is `approval_events` plus minimal `agent_trace_events` approval additions.

---

## Acceptance Test Floor

| Option | Description | Selected |
| --- | --- | --- |
| Preserve current approve/reject tests and add a few happy paths | Too weak for revision/hash safety. | |
| Add golden bytes, fail-closed mismatch tests, service transaction tests, and boundary tests | Matches Phase 13 risk and prevents compatibility drift. | yes |
| Push mismatch/hash tests to Phase 14/15 | Defers the core safety contract beyond its owner phase. | |

**Choice:** Phase 13 planning must include canonical hash golden bytes, snapshot golden bytes, stale revision/version/hash tests, wrong tenant/self/expired tests, respond/edit semantics, and raw payload redaction tests.
**Notes:** No raw prompt, raw args, raw payload, raw tool output, secrets, or unredacted PII may enter snapshot or replay event payloads.

---

## the agent's Discretion

- Exact module names under `src/approvals/`.
- Whether the old approval repository file is physically deleted or left as a temporary shim, as long as no new imports are allowed and Phase 13 owns removal.
- Exact command/result Pydantic class names, provided schema versions and trust boundaries follow `docs/contract-spec.md`.

## Deferred Ideas

- Phase 14: demo draft outcome, action draft v2 completion, final response wording, and draft-only guarantee.
- Phase 15: full ReplayEventV3 service, lifecycle finalizer, retention/backfill, and replay API.
- Phase 17: real external execution, outbox, reconciliation, compensation.
- Phase 16: long-term/case memory and memory identity/tombstones.
