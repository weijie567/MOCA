# Phase 13-17 Architecture Alignment

This document records the implementation stance for Phase 13-17 after the
tool-system refactor. The main lesson is that compatibility-first work can
hide ownership mistakes until they require a larger rewrite. For these phases,
MOCA should prefer clear architecture over preserving v1.0 shapes.

Phase numbers here follow the roadmap ownership:

- Phase 13: approval, SLA, risk policy, safety snapshot, canonical hash.
- Phase 14: demo action draft boundary.
- Phase 15: replay, lifecycle finalizer, observability event service.
- Phase 16: long-term profile memory and reviewed case memory.
- Phase 17: external action execution, outbox, reconciliation, compensation.

## Operating Rule

Do not use "minimum diff" as the default strategy for Phase 13-17. Use it only
inside a boundary that is already correct.

The default strategy is:

1. Define the owner and contract first.
2. Move or rewrite code to match the owner.
3. Delete or quarantine old paths in the same phase unless there is a dated
   removal plan.
4. Add architecture boundary tests before expanding feature behavior.

Compatibility layers are allowed only when all of these are true:

- They have a named owner.
- New code is forbidden from importing them.
- A test proves the canonical path is used.
- The phase document names the removal phase.

## Cross-Phase Boundaries

| Domain | Owns | Must not own |
| --- | --- | --- |
| Approval/Snapshot | Approval request state, levels, assignments, decisions, `ActionSafetySnapshot`, `CanonicalHashProfile v1`, approval events | Action draft persistence, external dispatch, replay storage |
| Action Draft | Durable demo draft, draft-only outcome, action idempotency, draft hash guards | Approval decisions, safety snapshot production, external execution |
| Replay/Observability | Event table/service, run lifecycle finalizer, replay read API, redaction, retention, sequence allocator enrichment | Business truth, approval state machine, action state machine, semantic memory |
| Memory | Session memory, future long-term profile memory, future reviewed case memory, memory-specific PII/tombstone/review/identity rules | Workflow checkpoint, trace/replay truth, policy evidence, approval/action authorization |
| External Action | Execution claim, outbox, adapter dispatch, unknown/reconciliation, compensation | Demo draft semantics, approval policy, safety snapshot production |

## Current Code Evidence

Current implementation has useful foundations but should not be treated as the
target architecture.

- `src/db/models.py` has `ApprovalRequest` and `ApprovalStep`, but they are
  single-record approve/reject state without request/level/assignment version
  CAS, revision binding, action hash, or safety snapshot hash.
- `src/api/routers/approvals.py` performs API role checks, repository updates,
  and graph resume in one router function. Phase 13 should move transition
  logic into an `ApprovalService`.
- `src/agent/nodes/approval_gate.py` creates an interrupt payload directly from
  `AgentState`; it does not create or bind a canonical safety snapshot.
- `src/actions/service.py` and `src/repositories/action_draft_repo.py` create a
  durable draft, but current idempotency is not bound to tenant + payload hash +
  safety snapshot hash.
- `src/db/models.py` has `AgentTraceEvent` with a minimal event envelope. This
  is the right foundation for Phase 15; `TraceRepository.build_timeline` remains
  a compatibility read model over `AgentStep`, approvals, and drafts.
- `src/memory/service.py` and `src/memory/repository.py` correctly scope current
  session memory. Phase 16 should add long-term/case memory beside this, not
  overload `session_memories`.
- `src/agent/nodes/long_term_memory_retrieve.py` is an empty adapter. This is a
  good seam for Phase 16, but it must stay non-authoritative until reviewed
  long-term/case memory exists.

## Phase 13: Approval / Snapshot / Hash

### Target

Phase 13 owns the safety contract that binds proposed action, evidence, policy
versions, risk versions, approval revision, and later action draft/execution.

The center of this phase should be:

- `src/approvals/` or equivalent domain package with `ApprovalService`,
  `ApprovalPolicy`, `ApprovalRepository`, and transition commands.
- `src/approvals/snapshots.py` or equivalent for `ActionSafetySnapshot`.
- `src/common/canonical_hash.py` or equivalent shared `CanonicalHashProfile v1`.

### Required Restructure

- Move approval transition logic out of `src/api/routers/approvals.py`.
- Keep the API router as a thin trusted-command boundary: parse request,
  authenticate actor, call `ApprovalService`, then resume graph only with a
  trusted service result.
- Do not let `approval_gate` be the source of approval truth. It may create an
  interrupt, but persistent request/revision/snapshot state belongs to
  `ApprovalService`.
- Introduce `ActionSafetySnapshot` before action draft consumes it. Phase 14
  must not invent its own snapshot or evidence hash fields.
- Add exact `action_payload_hash + safety_snapshot_hash` binding. Legacy
  `policy_snapshot_ref` and `evidence_snapshot_ref` may exist only as nullable
  aliases and must not authorize action.

### Deletion / Quarantine

- Quarantine direct `ApprovalRepository.decide(...)` use outside
  `ApprovalService`.
- Quarantine direct graph resume from approval API until the service returns a
  typed trusted resume payload.
- Do not add more behavior to `ApprovalStep` as if it were the final event
  model. It is a compatibility audit row until approval events and replay event
  refs are wired.

### Gate Tests

- Canonical hash golden bytes for `proposed_action.v1`.
- Canonical hash golden bytes for `action_safety_snapshot.v1`.
- Hash failure cases: key order, unknown fields, null vs absent, money scale,
  datetime precision, evidence sorting, score stripping.
- Approval accept authorizes only the exact `action_payload_hash` and
  `safety_snapshot_hash`.
- Stale revision, stale request version, expired request, wrong tenant,
  self-approval, and changed payload all fail closed.
- `respond` enters `needs_info` and cannot resume the old approval into action.
- `edit` supersedes the old approval and reroutes through risk/snapshot
  validation.

## Phase 14: Demo Action Draft Boundary

### Target

Phase 14 should make the demo action path explicit and honest: MOCA creates a
durable draft only. It does not execute coupons, refunds, bans, or ticket
closures.

### Required Restructure

- Rename service language around `execute_action` where necessary so the current
  path is understood as create-draft, not external execution.
- Add `draft_outcome.v1` semantics: `status=not_executed_demo`,
  `external_side_effect=false`.
- Bind `ActionDraft` to Phase 13 fields:
  `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, and
  optional `approval_request_id`.
- Update idempotency to include tenant, run, approval revision or auto marker,
  action type, target id, and `action_payload_hash`.
- Keep `UnifiedToolManager -> ActionToolExecutor -> ActionService` as the
  node-only action path.

### Deletion / Quarantine

- Do not create `action_executions` in demo mode.
- Do not use `action_result.status=success` or any compatibility action result
  field to mean external success. If a graph-facing compatibility field remains,
  it must be draft-only, owned by the action draft boundary, forbidden for new
  callers, covered by wording tests, and have a named deletion/replacement gate.
- Do not let final response say an external business action was executed.
- Do not let action draft service recompute or mutate `ActionSafetySnapshot`.
  It validates Phase 13 snapshot/hash only.

### Gate Tests

- Demo action creates exactly one draft and no execution row.
- Reused idempotency key with same hash returns the existing draft.
- Same target with different amount/hash creates a distinct key or fails a hash
  conflict; it must not silently reuse the old draft.
- Missing or mismatched approval hash/snapshot hash fails.
- Final response says draft created, not coupon issued or refund executed.
- Any retained `action_result` compatibility output says draft/not-executed demo,
  never external success, and has owner/deletion coverage in the Phase 14 plan.
- Graph node still reaches action through `UnifiedToolManager`, not raw action
  adapter.

## Phase 15: Replay / Observability / Lifecycle

### Target

Phase 15 should make replay a first-class event store and lifecycle service, not
an API-time composition of unrelated tables.

`AgentTraceEvent` already gives a minimal envelope. Phase 15 should enrich and
standardize it rather than invent another timeline model.

### Required Restructure

- Introduce a `ReplayService` or `TraceEventService` that owns append/read,
  redaction, retention, event registry validation, and sequence allocation.
- Keep `TraceRepository.build_timeline` as a legacy read model only during
  migration. New events should read from `agent_trace_events` first.
- Add full V3 fields as needed: parent operation, attempt, error, node/tool
  resource refs, retention class.
- Add a `RunLifecycleService` or finalizer. Run status cannot depend only on a
  happy-path graph tail.
- Ensure Phase 13/14 events write typed resource refs on first emit. Phase 15
  must not fabricate actor/resource refs during backfill.

### Deletion / Quarantine

- Quarantine new writes to `trace_steps`/`AgentStep.metrics_json` as the only
  replay source. They can remain as compatibility summaries.
- Do not let replay store raw prompt, raw tool args, raw tool output, approval
  payload, secrets, or unredacted PII.
- Do not let replay own business state transitions. It records what happened.

### Gate Tests

- Per-run sequence is strictly monotonic across graph run, approval resume,
  memory write, and action draft.
- Bounded investigate loop emits multiple child tool/RAG events with iteration.
- Started/terminal operation pairing validates; unresolved backfill is marked,
  not invented.
- Interrupted, approved-resumed, rejected, expired, needs-info, error, and
  cancelled timelines are represented.
- Redaction guard rejects forbidden raw payload keys.
- `/trace` or `/replay` reads event-store data first, with legacy timeline only
  as fallback during migration.

## Phase 16: Long-Term / Case Memory

### Target

Phase 16 adds semantic memory beyond the current session memory. It must not
turn memory into policy evidence or action authorization.

Target package shape should keep `src/memory` as the semantic memory domain:

- session memory remains current same-thread continuity;
- long-term profile memory stores reviewed durable scoped facts/preferences;
- case memory stores reviewed precedent;
- PII, tombstone, review, identity, TTL, correction, and supersede rules live
  inside memory domain.

### Required Restructure

- Add new tables/models for `long_term_memories`, `case_memories`,
  `memory_tombstones`, and `memory_write_events`. Do not overload
  `session_memories`.
- Implement `memory_identity.v1` canonical content/source identity before
  adding async extraction.
- Implement retrieval predicates first:
  reviewed/approved, not deleted, not tombstoned, not expired, scope allowed.
- Wire `long_term_memory_retrieve` only after real retrieval exists. The empty
  adapter should not pretend continuity was found.
- Keep `search_case_memory` distinct from policy retrieval. It returns precedent
  references, not `EvidenceRefV1`.

### Deletion / Quarantine

- Do not store approval decisions, action authorization, policy rules, or
  single-order facts as long-term memory.
- Do not write unreviewed model guesses as durable long-term facts.
- Do not use memory retrieval to satisfy policy evidence, approval evidence,
  risk evidence, action safety snapshots, or replay truth.
- Do not introduce Redis as authoritative memory.

### Gate Tests

- `memory_identity.v1` golden normalization and hash tests.
- Tombstone match blocks reinsert in the same transaction.
- Correction/supersede leaves exactly one current long-term memory.
- Case memory is append-only unless a separate versioning model is introduced.
- Retrieval excludes deleted, tombstoned, rejected, prohibited, expired, and
  unreviewed records.
- Memory refs are not assignable to `EvidenceRefV1`.
- `long_term_memory_retrieve` returns empty/safe result when no reviewed memory
  exists.

## Phase 17: External Action Execution

### Target

Phase 17 is the first phase allowed to introduce real external side effects.
It must be architected as a claimed execution/outbox system, not as a graph node
calling an adapter.

### Required Restructure

- Add `ActionExecutor` for external mode separate from demo draft creation.
- Add `action_executions`, `action_outbox_events`,
  `action_reconciliation_jobs`, and `action_compensation_records`.
- External dispatch only consumes a committed and claimed outbox event.
- Execution creation must validate draft, approval, action hash, safety
  snapshot hash/content, idempotency key, tenant/run binding, and action
  allowlist in one transaction.
- Unknown/reconciling results must default to status checks and reconciliation,
  not blind redispatch.

### Deletion / Quarantine

- Do not let graph nodes call external adapters directly.
- Do not dispatch before execution/outbox rows are committed.
- Do not reuse demo-mode `ActionService.create_coupon_grant_draft` as external
  execution service.
- Do not treat `unknown` as `failed` or `executed`.
- Do not create compensation without reconciliation or human confirmation.

### Gate Tests

- Draft CAS claim prevents duplicate active execution.
- Wrong tenant/run/hash/snapshot/idempotency binding rolls back and does not
  dispatch.
- Outbox worker dispatches only claimed rows.
- Duplicate worker claim cannot double dispatch.
- Timeout produces `unknown` and schedules reconciliation.
- Reconciliation does not create a new idempotency key by default.
- Compensation records require resolved execution context and actor/reason.

## Implementation Sequence

Use this sequence inside each phase:

1. Alignment audit over current code and spec.
2. Contract/schema definitions and golden tests.
3. Domain service and repository transaction boundary.
4. Graph/API integration through thin callers.
5. Event/replay emission using the current envelope.
6. Delete or quarantine legacy call paths.
7. Architecture/static tests that protect the boundary.

For Phase 13 specifically, start with:

1. Add canonical hash module and golden tests.
2. Add `ActionSafetySnapshot` schema/builder and golden tests.
3. Introduce `ApprovalService` and move router transition logic behind it.
4. Add approval revision/hash fields or normalized target tables.
5. Make `approval_gate` consume service-produced request/snapshot data.
6. Update action path to require snapshot/hash context.

## Non-Negotiable Architecture Tests

These tests should exist by the end of the relevant phases:

- No API router performs approval state transitions directly.
- No graph node imports raw action, business, knowledge, memory, or external
  integration adapters.
- No demo action path writes external execution rows.
- No external adapter can be reached without a claimed outbox event.
- No memory result can be treated as policy `EvidenceRefV1`.
- No replay event can contain raw prompt, raw args, raw tool result, secret, or
  unredacted PII.
- No approval can authorize an action if payload hash or safety snapshot hash
  changed.
- No stale approval revision can resume into action.

## Review Checklist Before Coding a Phase

Before implementation starts, answer these in the phase plan:

- What is the canonical owner package?
- Which current modules are compatibility only?
- Which imports become forbidden?
- Which database rows are authoritative?
- Which fields are immutable after creation?
- Which old tests protect obsolete behavior and must be rewritten?
- Which boundary tests fail before implementation and pass after?
- Which compatibility layer is removed in this phase?

If these answers are unclear, do not start feature coding.
