# Phase 14: Demo Action Executor Boundary - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 14`

<domain>
## Phase Boundary

Phase 14 makes the demo action path explicit, durable, and honest. MOCA may create a durable action draft and `draft_outcome.v1`, but demo mode must not execute coupons, refunds, bans, ticket closures, external adapters, outbox rows, or `action_executions`.

This phase consumes Phase 13 approval and snapshot work. It validates exact `action_payload_hash + safety_snapshot_ref + safety_snapshot_hash` binding against Phase 13 records, but it must not recompute, mutate, or re-own `ActionSafetySnapshot` or `CanonicalHashProfile v1`.

External execution, outbox, reconciliation, compensation, and real side effects remain Phase 17. Full ReplayEventV3 enrichment, lifecycle finalizer, event-store read switch, retention, and richer replay API remain Phase 15.

</domain>

<decisions>
## Implementation Decisions

### Draft Schema and Migration
- **D-01:** Implement the Phase 14 `action_draft.v2` persistence shape for new Phase 14 drafts. This includes self-describing draft fields such as `schema_version`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `draft_outcome`, version/lifecycle/retention fields, and existing approval linkage where applicable.
- **D-02:** Treat Phase 14 schema work as draft-row persistence and replay readiness, not a reimplementation of Phase 13 validation. Current `ActionService` already requires binding fields and validates them against `ActionSafetySnapshot`; Phase 14 persists those validated fields on the draft row.
- **D-03:** Persist `draft_outcome.v1` on `action_drafts`. Demo outcome must carry `status=not_executed_demo` and `external_side_effect=false`.
- **D-04:** Do not backfill legacy draft rows into complete `action_draft.v2`. New columns may be nullable for old rows; contract tests should assert v2 completeness only for drafts created after Phase 14. Old pre-v2 rows are not an authorization surface.
- **D-05:** Do not create `action_executions`, outbox, reconciliation, or compensation tables in Phase 14. Add negative tests proving demo mode writes no execution rows or external-only records.
- **D-28:** Keep the spec/phase boundary explicit in implementation and coverage artifacts. `docs/contract-spec.md` remains the normative contract source; Phase 14 implementation extensions such as `target_id`, `approval_revision_ref`, `execution_mode`, `draft_version`, `lifecycle_status`, `retention_policy`, and persisted `draft_outcome` must be documented as implementation fields unless a separate spec revision updates the contract.

### Compatibility Output and Wording
- **D-06:** Prefer `draft_outcome.v1` as the graph/API success signal for draft creation. Any retained `action_result` field is deprecated compatibility output only and must not use `status=success` to imply external execution.
- **D-07:** Migrate existing success sentinels together. `src/api/routers/approvals.py` and `src/agent/nodes/final_response.py` currently depend on `action_result.status == "success"`; Phase 14 must change those checks to `draft_outcome` created/not-executed semantics so valid drafts are not misclassified as failures.
- **D-08:** Final backend/API responses must say a draft was created and no coupon/refund/ticket action was executed. Do not use wording such as waiting for final issuance, issued coupon, refunded, closed ticket, executed, or external success.
- **D-09:** Keep frontend/timeline copy changes out of Phase 14 except where required by backend contract tests. Record `frontend/src/components/timeline/TimelineStep.tsx` wording for `execute_action` as a known UI/replay wording difference deferred to Phase 15.
- **D-10:** Add strict forbidden-phrase tests for backend/final/API output to prevent external-success claims in demo mode.

### Idempotency and Conflict Behavior
- **D-11:** The server/service boundary constructs the draft idempotency key from trusted fields only. Do not let callers or the graph node supply arbitrary key shape.
- **D-12:** Target key shape: `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}`.
- **D-13:** Missing `target_id` must fail validation instead of falling back to `"unknown"`, because unknown-target keys can collide across distinct actions.
- **D-14:** Same target/action with a different `action_payload_hash` represents a distinct draft intent or revision and should create a distinct draft key.
- **D-15:** Exact key reuse returns the existing draft only when binding remains exact. Because the key embeds tenant, run, revision/auto marker, action type, target id, and payload hash, the additional required reuse check is `safety_snapshot_hash` consistency. A key hit with mismatched snapshot hash must return an idempotency conflict.
- **D-16:** Use explicit `auto_allowed` as the no-approval revision marker for low-risk auto-allowed drafts. Do not collapse auto-allowed drafts into the current `no_approval` marker.
- **D-17:** Use the canonical contract constraint `unique (tenant_id, idempotency_key)` for action drafts. Even though the Phase 14 service-built key embeds `tenant_id`, the database uniqueness model must follow `docs/contract-spec.md` Section 18.3 so tenant isolation, draft reuse semantics, and future Phase 17 external idempotency remain aligned with the normative contract.

### Graph and Naming Boundary
- **D-18:** Rename the registered graph node from `execute_action` to `action_draft` in Phase 14. Update graph registration, conditional edges, imports, trace/node-name contracts, and route naming to align with the canonical node.
- **D-19:** Before renaming, check whether LangGraph checkpoints or replay/timeline compatibility store node names. If old names are persisted, document legacy run behavior and add compatibility handling only as a named shim.
- **D-20:** Keep the tool name `create_coupon_grant_draft`; it is already draft-explicit and node-only. Do not introduce a generic `create_action_draft` abstraction until additional action types justify it.
- **D-21:** Hard-quarantine backend "execute" language for demo draft semantics. New backend call sites, output fields, and docs should use draft/action_draft wording except for named compatibility shims.
- **D-22:** Any retained `execute_action` alias must have a named owner, forbidden new references, boundary tests, and a dated removal phase/gate.
- **D-23:** Do not rename `requested_operation="execute_action"` in Phase 14. Intent taxonomy is a Phase 11 contract. The user's requested operation may remain "execute action" while the graph maps that intent to safe draft creation after risk and approval guards.

### Trace and Replay Event Surface
- **D-24:** Emit `action_draft_created` in Phase 14 through the existing Phase 10 minimal `AgentTraceEvent` envelope after successful draft creation.
- **D-25:** The event must use safe refs only. Suggested shape: `resource_refs={draft_id, target_id, action_payload_hash, safety_snapshot_hash}` and `redacted_payload={action_type, execution_mode:"demo", external_side_effect:false}`. Do not include raw action payload, raw tool args, or full `ActionDraft.payload`.
- **D-26:** Update backend `/trace` action draft output to include `draft_outcome` from `action_drafts`. Do not add a new replay API, ReplayEventV3 read switch, retention model, or event-store-first trace read in Phase 14.
- **D-27:** Add negative tests across persistence, events, and wording: no `action_executions` rows or writes, no `action_execution_*` events, no external refs, and no external success wording.

### the agent's Discretion
- Exact column names may follow `docs/contract-spec.md` target names and existing SQLAlchemy conventions.
- If existing storage uses `payload`/`payload_json` for the contract `proposed_action` body, the executor must document that mapping in `14-COVERAGE.md` instead of treating the naming difference as either a contract change or an omitted field.
- Exact compatibility shim shape is planner discretion, but only if it satisfies D-19 and D-22.
- Exact test file split may follow current tests under `tests/test_execute_action.py`, `tests/agent/test_tools/`, `tests/test_trace_api.py`, and approval integration tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Phase 14 Architecture Inputs
- `docs/phase-13-17-architecture-plan.md` - Phase 14 target, required restructure, deletion/quarantine rules, and gate tests.
- `.planning/ROADMAP.md` - Phase 14 goal, dependency on Phase 13, DEMO-01/02 requirements, and success criteria.
- `.planning/REQUIREMENTS.md` - `DEMO-01`, `DEMO-02`, plus planning requirements for schema owner, tests, rollback, and coverage.
- `.planning/phases/13-approval-state-machine/13-CONTEXT.md` - Phase 13 snapshot/hash/approval binding handoff and explicit Phase 14 deferred scope.

### Normative Contract Sections
- `docs/contract-spec.md` Section 9.0-9.5 - canonical node/router vocabulary, `action_draft`, `action_execution`, and routing boundaries.
- `docs/contract-spec.md` Section 10.1 - AgentState action fields including `action_draft`, `draft_outcome`, `action_result`, and `execution_mode`.
- `docs/contract-spec.md` Section 15.3-15.4 - proposed action, approval result, and hash binding consumed by action drafts.
- `docs/contract-spec.md` Section 16.1-16.4 - action draft, demo mode, `draft_outcome.v1`, compatibility `action_result` caveat, and idempotency key shape.
- `docs/contract-spec.md` Section 17.2 - `action_draft_created` event ownership and no `action_execution_*` events in demo mode.
- `docs/contract-spec.md` Section 18.2-18.3 - action draft target schema, cross-table consistency, external-only table ownership, and demo-mode execution prohibition.
- `docs/contract-spec.md` Section 19 - trace/replay display and redaction restrictions for action draft payloads.
- `docs/eval-test-plan.md` - action contract and golden-flow expectations for demo draft only, no external side effect, and no external success wording.

### Current Code Evidence
- `src/actions/service.py` - existing ActionService binding validation against `ActionSafetySnapshot`; currently returns tool-style success/error.
- `src/actions/drafts.py` and `src/repositories/action_draft_repo.py` - current durable draft store and idempotency behavior.
- `src/db/models.py` - current `ActionDraft`, `ActionSafetySnapshot`, `ApprovalRequest`, and `AgentTraceEvent` models.
- `src/agent/nodes/execute_action.py` - current node to rename/replace with `action_draft`; currently constructs idempotency key and maps draft success into `action_result.status == "success"`.
- `src/agent/graph.py` - current graph registration and conditional edges using `execute_action`.
- `src/tools/executors/action.py` and `src/tools/catalog.py` - node-only `create_coupon_grant_draft` path and safety-snapshot requirements.
- `src/api/routers/approvals.py` - approval resume reconciliation currently checks `action_result.status == "success"`.
- `src/agent/nodes/final_response.py` - current final wording and `action_result.status == "success"` handling.
- `src/api/routers/traces.py` and `src/repositories/trace_repo.py` - current `/trace` action draft read model, to extend with `draft_outcome`.
- `src/agent/events.py` - minimal event envelope and sequence allocator to reuse for `action_draft_created`.
- `frontend/src/components/timeline/TimelineStep.tsx` - known frontend label difference deferred to Phase 15.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ActionService._validate_action_binding` already validates `tenant_id`, `run_id`, `approval_request_id`, `action_payload_hash`, `safety_snapshot_ref`, and `safety_snapshot_hash` against Phase 13 approval/snapshot rows.
- `ActionDraftRepository.create_or_get` already centralizes draft creation and idempotent lookup.
- `AgentTraceEvent` and `emit_event` already provide a minimal event writer and per-run sequence allocator.
- `/trace` already loads action drafts; Phase 14 can extend the existing read shape rather than building a replay API.

### Established Patterns
- Route handlers should stay thin and call domain services rather than mutating draft/approval truth directly.
- Agent write-capable tools are node-only and go through `UnifiedToolManager -> ActionToolExecutor -> ActionService`.
- Tests already cover binding rejection and approval/draft behavior; Phase 14 should extend them rather than creating parallel harnesses.

### Integration Points
- Rename and wire `action_draft` in `src/agent/graph.py`, replacing current `execute_action` graph node usage.
- Move idempotency key construction into `ActionService` or an action-domain helper at the service trust boundary.
- Persist v2 draft fields and `draft_outcome` in the SQLAlchemy model and Alembic migration.
- Return `draft_outcome` from the draft node and update approval reconciliation/final response to use it as the success sentinel.
- Emit `action_draft_created` after successful draft creation with safe resource refs and redacted payload only.
- Extend trace API action draft output with `draft_outcome`.

</code_context>

<specifics>
## Specific Ideas

- The core product wording is "draft created, not executed." This is required even if the user originally asked to execute an action.
- Keep intent-layer `requested_operation="execute_action"` because it captures what the user requested; graph-layer `action_draft` captures what the system safely does in demo mode.
- Do not over-generalize the coupon draft tool name in Phase 14. Generic action-draft naming can wait until more action types exist.
- Treat retained `action_result` as a temporary compatibility field only; do not let it remain the source of truth for draft success.

</specifics>

<deferred>
## Deferred Ideas

- Frontend timeline label cleanup for `execute_action` is deferred to Phase 15/replay UI work unless planning finds it blocks backend contract tests.
- Full ReplayEventV3 enrichment, lifecycle finalizer, event-store-first `/trace` or `/replay` reads, retention, and richer replay API are Phase 15.
- External action execution, `action_executions`, outbox, reconciliation, compensation, external idempotency keys, and real side effects are Phase 17.
- Generic `create_action_draft` naming can be reconsidered when more action types are implemented.

</deferred>

---

*Phase: 14-demo-action-executor-boundary*
*Context gathered: 2026-06-15*
