# Phase 14: Demo Action Executor Boundary - Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.
> Decisions are captured in `14-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 14-demo-action-executor-boundary
**Areas discussed:** Draft schema and migration, compatibility output and wording, idempotency and conflict behavior, graph and naming boundary, trace/replay event surface

---

## Draft Schema and Migration

| Option | Description | Selected |
| --- | --- | --- |
| Full target draft schema | Add target `action_draft.v2` fields for new drafts. | yes |
| Minimum blocking fields | Add only hash/snapshot/outcome fields. | |
| Service-only validation | Keep the table mostly as-is and rely on service validation. | |

**User's choice:** Full target draft schema, persist `draft_outcome.v1`, no legacy backfill, and no `action_executions` table in Phase 14.

**Notes:** User corrected the initial rationale after inspecting code: Phase 13 already implemented service-level hash/snapshot validation. Phase 14 schema work should make draft rows self-describing and replay-friendly, not duplicate that validation. Legacy draft rows may remain pre-v2 and nullable; only new Phase 14 drafts must be v2-complete.

---

## Compatibility Output and Wording

| Option | Description | Selected |
| --- | --- | --- |
| Prefer `draft_outcome.v1` | Use draft outcome as the success signal; keep `action_result` only as deprecated compatibility. | yes |
| Dual output | Add draft outcome but keep `action_result.status=success`. | |
| Hard replace | Remove `action_result` from demo draft path entirely. | |

**User's choice:** Prefer `draft_outcome.v1`, explicitly say draft created and not executed, defer frontend timeline copy, and use strict forbidden-phrase tests.

**Notes:** User identified an implementation trap: replacing `action_result.status="success"` with another string would break existing success checks in `approvals.py` and `final_response.py`. Those checks must migrate to draft-outcome-created semantics in the same implementation slice.

---

## Idempotency and Conflict Behavior

| Option | Description | Selected |
| --- | --- | --- |
| Server constructs trusted key | Key built from trusted tenant/run/revision/action/target/hash fields. | yes |
| Caller passes key | Service validates caller-provided key shape. | |
| Keep node-generated key | Add hash to the current node-generated key. | |

**User's choice:** Server constructs trusted key, different payload hash creates a different draft, exact key reuse requires binding consistency, and auto-allowed drafts use an explicit `auto_allowed` marker.

**Notes:** Superseded by post-plan review on 2026-06-16. The final Phase 14 plan must follow `docs/contract-spec.md` Section 18.3 and use `unique (tenant_id, idempotency_key)`, not a global unique `idempotency_key`. Key hit still requires exact binding checks, including safety snapshot hash consistency. Missing `target_id` must fail instead of falling back to `"unknown"`.

---

## Graph and Naming Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Rename node to `action_draft` | Align the registered graph node with the canonical contract now. | yes |
| Keep `execute_action` internally | Make outputs draft-only but defer rename. | |
| Planner discretion | Let planner decide after research. | |

**User's choice:** Rename the registered node to `action_draft`, keep `create_coupon_grant_draft`, hard-quarantine backend execute wording, and do not rename `requested_operation="execute_action"`.

**Notes:** User distinguished graph node naming from intent taxonomy. The user's requested operation may remain "execute action" while the system internally creates a draft in demo mode. If a compatibility alias remains, it must have an owner, forbidden new references, tests, and a dated removal gate.

---

## Trace/Replay Event Surface

| Option | Description | Selected |
| --- | --- | --- |
| Emit minimal event now | Write `action_draft_created` using the existing minimal event envelope. | yes |
| Persist outcome only | Let Phase 15 backfill or read draft outcome later. | |
| Full event-store switch | Move trace/replay reads to event store now. | |

**User's choice:** Emit minimal `action_draft_created`, include safe refs only, update `/trace` with `draft_outcome`, and test no-execution across DB, event, and wording surfaces.

**Notes:** User explicitly deferred ReplayEventV3 enrichment, lifecycle finalizer, event-store read switch, retention, and richer replay API to Phase 15. The Phase 14 event should not contain raw action payload.

---

## the agent's Discretion

- Exact migration file split and model names may follow local conventions.
- Exact compatibility shim shape is planner discretion if it satisfies named owner, forbidden references, tests, and removal gate.
- Exact test organization may follow existing backend test layout.

## Deferred Ideas

- Frontend timeline wording cleanup: Phase 15/replay UI work.
- ReplayEventV3 and event-store read switch: Phase 15.
- External execution/outbox/reconciliation/compensation: Phase 17.
- Generic action-draft tool naming: revisit when more action types exist.
