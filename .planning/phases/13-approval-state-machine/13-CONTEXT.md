# Phase 13: Approval State Machine - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 13 --all` with codebase/docs-first analysis and explicit user preferences

<domain>
## Phase Boundary

Phase 13 implements the approval/snapshot/hash safety contract for high-risk action candidates. It owns versioned approval requests, levels, assignments, decisions, approval events, `ActionSafetySnapshot`, `CanonicalHashProfile v1`, exact `action_payload_hash + safety_snapshot_hash` authorization binding, and trusted `needs_info` resume semantics.

This phase may make large v1.0 approval changes when that produces a simpler and more stable architecture. It must not preserve old approval boundaries just to minimize diff.

In scope:
- Single-level runtime approval flow with multi-level-compatible request/level/assignment/decision/event schema.
- Request/level/assignment version CAS, revision invalidation, stale guard failures, self-approval and tenant isolation.
- `ActionSafetySnapshot` normalized persistence and golden hash contract.
- `CanonicalHashProfile v1` implementation and golden bytes.
- Approval API/router cutover to an `ApprovalService` trusted-command boundary.
- Approval minimal-envelope event additions: `approval_requested`, `approval_decided`, `approval_expired`, `approval_resumed`.
- `respond` -> `needs_info` and `edit` -> `superseded` with revalidation/re-snapshot rules.
- SLA scanner implemented feature-disabled, with ownership and event-shape tests.

Out of scope:
- Phase 14 `draft_outcome.v1`, demo action wording cleanup, and action draft schema completion beyond Phase 13 approval/snapshot guard handoff.
- Phase 15 full ReplayEventV3 service, replay read API, lifecycle finalizer, retention/backfill, and V3 enrichment.
- Phase 17 external action execution, outbox, reconciliation, compensation, and real side effects.
- Phase 16 long-term/case memory, `memory_identity.v1`, tombstones, and memory review workflow.
- Multi-level production UI/work queue richness beyond schema-compatible single-level runtime.

</domain>

<decisions>
## Implementation Decisions

### Owner Package and Module Boundaries
- **D-01:** Add `src/approvals/` as the canonical approval/snapshot domain package. It owns `ApprovalService`, approval command/result schemas, `ApprovalPolicy`, approval state machine transitions, assignment resolution, approval repository access, `ActionSafetySnapshot` schema/builder, and approval event emission.
- **D-02:** `src/api/routers/approvals.py`, `src/api/routers/agent.py`, and `src/api/routers/agent_runs.py` must stop creating/updating approval truth directly. They may authenticate, parse HTTP/SSE inputs, construct trusted server-side command objects from authenticated actor context, call `ApprovalService`, and invoke graph resume only with a service-produced trusted resume payload.
- **D-03:** Implement `CanonicalHashProfile v1` in `src/common/canonical_hash.py`. Although Phase 13 produces the profile, it is shared by approvals, actions, replay, and future memory identity work. Consumers must import the shared module, not import approval internals or define their own serializer.
- **D-04:** Implement `ActionSafetySnapshot` schema and builder in `src/approvals/snapshots.py` or an equivalent `src/approvals/` module. The builder imports the canonical `EvidenceRefV1` from `src/knowledge/schemas.py`; it must not define a reduced snapshot-only evidence schema.
- **D-05:** Move or replace `src/repositories/approval_repo.py` with a package-owned repository such as `src/approvals/repository.py`. If a compatibility shim remains, it is owned by `src/approvals/`, forbidden for new imports, covered by a static import-boundary test, and removed in Phase 13 unless a concrete removal commit is recorded.
- **D-06:** `ApprovalPolicy` owns role/assignment resolution, self-approval policy, SLA due time calculation, and single-level default assignment behavior. Hard-coded router constants such as `APPROVAL_ROLES` are compatibility inputs, not the long-term policy source.

### Database Strategy
- **D-07:** Phase 13 creates the normalized `action_safety_snapshots` table now. Phase 14 must not invent snapshot/evidence hash fields independently. The table is the only canonical target snapshot store, with `unique (tenant_id, immutable_hash)`.
- **D-08:** Phase 13 directly introduces target approval tables: `approval_levels`, `approval_assignments`, `approval_decisions`, and `approval_events`, while extending `approval_requests` to `approval_request.v2`. Do not stop at only expanding the v1 single-row `approval_requests` shape.
- **D-09:** Runtime may remain single-level in Phase 13, but it must run through the new level/assignment/decision model. Multi-level behavior is schema-compatible and contract-tested; full multi-level UI/queue optimization can remain later.
- **D-10:** New active `approval_requests` records must be non-null for `schema_version`, `tenant_id`, `run_id`, `thread_id`, `status`, `approval_policy_id`, `policy_version`, `revision`, `version`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `risk_level`, `requested_by`, `created_at`, and `updated_at`.
- **D-11:** New active `approval_levels` records must be non-null for request FK, schema version, level number, version, status, required role, mode, and timestamps. New active `approval_assignments` must be non-null for level FK, schema version, assigned role, status, version, and timestamps; `assigned_to_user_id` may be nullable when assigned by role.
- **D-12:** `approval_decisions` and `approval_events` are append-only audit truth. They must carry redundant tenant/run/revision/version fields where needed to validate cross-table ownership in one transaction.
- **D-13:** Immutable after creation: request `tenant_id`, `run_id`, `thread_id`, `requested_by`, `revision`, `approval_policy_id`, `policy_version`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`; snapshot `snapshot_json`, `immutable_hash`, `action_payload_hash`, config versions, evidence refs; level identity fields; assignment identity fields; decision/event content. Status/version/timestamps may transition only through service CAS.
- **D-14:** Historical v1 approval rows may keep nullable hash/snapshot/version fields during migration, but they cannot authorize action. They may be displayed, rejected, cancelled, expired, or superseded. Approving a historical row requires revalidation into a new v2 revision with a fresh action payload hash and safety snapshot hash.
- **D-15:** Legacy aliases `policy_snapshot_ref` and `evidence_snapshot_ref`, if retained or added for migration, are nullable compatibility aliases only. They are never authorization guards and cannot replace `safety_snapshot_hash`.
- **D-16:** `approval_events.replay_event_id` is nullable. Since `agent_trace_events` already exists, Phase 13 may write it when available; unresolved historical/backfill refs stay null for Phase 15.

### ApprovalService Boundary
- **D-17:** `ApprovalService` is the only component allowed to perform approval state transitions. It owns transaction order: lock/CAS request -> current level -> assignment -> insert decision/event -> emit minimal approval event -> return typed result.
- **D-18:** Router code must not call `ApprovalRepository.decide(...)`, `mark_expired(...)`, or raw SQL transition helpers directly. Add a static boundary test proving approval routers and agent run routers do not import the repository compatibility path.
- **D-19:** `ApprovalDecisionCommand` is constructed server-side from authenticated user, tenant, request body, and expected versions. User text, LLM output, ordinary chat payload, or raw resume payload cannot set trusted markers, request versions, `approval_result`, or graph resume data.
- **D-20:** `ApprovalService.decide(command)` returns a typed `ApprovalDecisionResult` containing status, transition outcome, exact revision/version refs, hashes, event refs, and an optional service-built `approval_result.v1` resume payload. The router may wrap this in `Command(resume=...)`; it must not assemble the dict itself.
- **D-21:** Current router responsibilities for self-approval, expiration, stale decision idempotency, conflict handling, step/event writing, and post-resume trace/run persistence must move behind service/domain helpers. The router remains an HTTP boundary and trusted command invoker.
- **D-22:** `respond` writes request status `needs_info`, creates/returns a clarification reference, emits an approval decision event, and leaves the run interrupted. It must not resume the old approval into `action_draft`.
- **D-23:** `edit` marks the old request revision `superseded`, persists edited proposed action material as a new candidate/revision, and routes back through risk/snapshot validation. It cannot directly approve or draft an edited action.

### Snapshot and Hash Contract
- **D-24:** The first implementation slice should be `CanonicalHashProfile v1` plus golden tests, followed immediately by `ActionSafetySnapshot` schema/builder plus golden tests. Do not start API/router migration before golden bytes fix the serialization contract.
- **D-25:** `CanonicalHashProfile v1` follows `docs/contract-spec.md` exactly: SHA-256 output as `sha256:<lowercase hex>`, input bytes `hash_profile.v1\n<schema_version>\n<canonical_json>`, Unicode-code-point key ordering, no insignificant whitespace, UTF-8, no runtime default serializer dependency, no bare JSON float, normalized money strings, fixed-millisecond UTC datetimes, explicit nullable fields, and unknown fields rejected.
- **D-26:** `proposed_action.v1` canonical hash is the only `action_payload_hash`. ApprovalService, snapshot builder, ActionDraftService, and future ActionExecutor must compute the same value for the same proposed action.
- **D-27:** `ActionSafetySnapshot.immutable_hash` covers the canonical projection that excludes only `immutable_hash`, lifecycle fields, and `EvidenceRefV1.score`; it retains `rank` when present and uses rank-aware evidence sorting from `docs/contract-spec.md` Section 8.3.
- **D-28:** Runtime order: proposed action canonicalization -> `action_payload_hash` -> risk/approval policy -> `ActionSafetySnapshot` row -> approval request or auto-allowed action path. `approval_gate`, action draft, and future external execution validate snapshot/hash; they do not produce new snapshots except when `ApprovalService` creates a new revision from `edit` or `needs_info`.
- **D-29:** Approval authorization requires exact match of `action_payload_hash + safety_snapshot_hash`. Stale revision, changed payload, changed evidence text/hash/ref/rank, changed policy/risk/retrieval config version, missing snapshot, or mismatched hash all fail closed and must not enter action.
- **D-30:** Snapshot and replay/approval events must not contain raw prompt, raw tool args, raw action payload, raw tool output, secrets, credentials, or unredacted PII. They may contain IDs, refs, hashes, versions, safe summaries, status enums, and redacted audit metadata.

### Old Path Quarantine and Deletion
- **D-31:** `ApprovalRepository.decide(...)` is an obsolete v1 transition API. Prefer deleting it during Phase 13. If kept briefly for migration, make it package-private, route it only through `ApprovalService`, add a no-router-import test, and name Phase 13 as its removal phase.
- **D-32:** `ApprovalStep` is a compatibility audit row for current `/trace` timeline only. The final approval event model is `approval_events` plus minimal `agent_trace_events` approval additions. Do not add new target behavior to `ApprovalStep`.
- **D-33:** `TraceRepository.build_timeline` may continue to compose legacy `AgentStep` / `ApprovalStep` / `ActionDraft` rows as a read fallback until Phase 15. New Phase 13 approval events should be emitted to `approval_events` and the minimal event envelope first.
- **D-34:** `approval_gate` may retain LangGraph interrupt/resume orchestration and append node trace summaries. It may show a service-generated approval wait payload. It cannot be the source of approval truth, cannot compute hashes, cannot decide expiry/self-approval, cannot mutate request status directly, and cannot accept untrusted chat state as an approval result.
- **D-35:** Current agent chat and SSE interruption handlers must stop creating `ApprovalRequest` rows from raw interrupt payloads. If LangGraph mechanics still surface an interrupt payload at API time, the handler must pass typed payload data to `ApprovalService.create_request(...)` and persist only the service result.
- **D-36:** Phase 13 must not implement Phase 14/15/17 behavior under approval names. No `draft_outcome.v1`, no `action_executions`, no outbox, no external adapter, no full replay read API, no lifecycle finalizer, and no compensation records.

### Acceptance Test Floor
- **D-37:** `canonical_hash` golden bytes for `proposed_action.v1` must reproduce the `docs/contract-spec.md` sample exactly, including `canonical_json`, `hash_input`, and expected SHA-256.
- **D-38:** `action_safety_snapshot.v1` must have its own golden bytes test with fixed canonical JSON, hash input bytes, and expected SHA-256.
- **D-39:** Hash negative tests are blocking: unknown fields, null vs absent, money scale, datetime precision, evidence order, score stripping, key order stability, changed payload, changed snapshot hash, changed evidence hash/ref/rank, and changed config version.
- **D-40:** Approval transition tests are blocking: stale request version, stale level version, stale assignment version, stale revision, self-approval, expired approval, wrong tenant, wrong assignment-level/request binding, and CAS conflict all fail closed.
- **D-41:** `respond` -> `needs_info` tests must prove no action is drafted or resumed from the old approval, the clarification identity/scope/version is bound, and timeout/cancel/wrong tenant/wrong thread all fail closed.
- **D-42:** `edit` tests must prove old revision becomes `superseded`, the edited action gets a new payload hash, risk/snapshot validation reruns, and the old revision cannot execute.
- **D-43:** Event/redaction tests must prove approval event additions are registered in the minimal envelope and that snapshot/replay/approval event payloads contain no raw prompt, raw args, raw payload, raw tool output, or PII-heavy fields.
- **D-44:** Boundary tests must prove routers do not perform approval transitions directly and graph nodes do not import raw external/action/business adapters for approval decisions.

### the agent's Discretion
- Exact file names inside `src/approvals/` may follow local conventions if ownership stays clear.
- Planner may decide whether to physically delete `src/repositories/approval_repo.py` or leave a temporary import shim, but the shim must be forbidden for new references and removed in Phase 13 unless an explicit exception is recorded.
- Planner may choose the exact Pydantic dataclass names for commands/results/snapshots, but schema versions and field semantics are fixed by `docs/contract-spec.md`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 13 Primary Architecture Inputs
- `docs/phase-13-17-architecture-plan.md` - Phase 13 target, required restructure, deletion/quarantine rules, gate tests, and implementation sequence.
- `docs/agent-architecture-phase-decomposition.md` - Phase 13 internal slices 13a/13b/13c, SLA scanner feature-disabled rule, schema ownership, cross-table enforcement planning gate, and eval gate discipline.
- `.planning/ROADMAP.md` - Phase 13 goal, dependencies, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` - `APPROVAL-01`, `APPROVAL-02`, `APPROVAL-03`, `SNAPSHOT-01`.
- `.planning/STATE.md` - Current focus and blocker note that active SLA scanner must remain an explicit owned follow-up gate.

### Normative Contract Sections
- `docs/contract-spec.md` Section 8.3 - Canonical `EvidenceRefV1`, score stripping, rank retention, rank-aware evidence sorting, and evidence text hash normalization.
- `docs/contract-spec.md` Section 9.3-9.5 - Approval/action route semantics, `approval_gate`, `action_draft`, and `route_after_approval` behavior.
- `docs/contract-spec.md` Section 10.1 - AgentState approval/snapshot fields, trusted writers, reset/merge rules, and approval revision refs.
- `docs/contract-spec.md` Section 15.3 - Approval plan contract, `ActionSafetySnapshot`, `CanonicalHashProfile v1`, hashable schemas, and golden hash sample.
- `docs/contract-spec.md` Section 15.4 - Approval state machine, transition table, request statuses, response type semantics, SLA/escalation rules.
- `docs/contract-spec.md` Section 15.7 - Approval storage target and retention rules.
- `docs/contract-spec.md` Section 17.2 - Minimal event envelope, approval event additions, per-run sequence allocator, and redaction requirements.
- `docs/contract-spec.md` Section 18.2 - `action_safety_snapshots`, approval target tables, constraints/indexes, immutable fields, cross-table consistency, and enforcement matrix.
- `docs/contract-spec.md` Section 18.3 - Action draft/execution target fields consumed by Phase 14/17 and legacy alias limitations.

### Architecture Mirrors and Prior Decisions
- `docs/architecture-overview.md` - Illustrative architecture mirror; use only as reading aid when aligned with contract spec. Relevant sections: canonical schema ownership and module responsibility matrix.
- `.planning/phases/08-knowledge-facade/08-CONTEXT.md` - EvidenceRefV1 producer-side projection rule: Knowledge may keep `score`, Phase 13 snapshot/hash must strip it and retain `rank`.
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` - Minimal event foundation, deterministic router boundaries, and write-action red line.
- `.planning/phases/11-intent-clarification/11-CONTEXT.md` - Ordinary chat cannot create trusted approval decisions; approval/result/resume remain trusted endpoint concerns.
- `.planning/phases/12-session-memory/12-CONTEXT.md` - Session memory is not policy evidence and cannot satisfy approval/action/snapshot authority.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/events.py` - Existing minimal event envelope, event registry set, redaction guard, and per-run sequence allocator. Phase 13 should register approval event additions here and reuse `emit_event`.
- `src/db/models.py` - Current `ApprovalRequest`, `ApprovalStep`, `ActionDraft`, and `AgentTraceEvent` models. They are useful migration foundations but not the target approval architecture.
- `src/knowledge/schemas.py` - Canonical `EvidenceRefV1` producer schema to import into snapshot builder.
- `src/agent/state.py` - Existing approval/snapshot field placeholders and EvidenceRef typed projection.
- `src/agent/nodes/assess_risk_and_approval.py` - Current risk/proposed-action producer. Phase 13 should attach canonical proposed action hash and snapshot creation at this boundary or behind an approvals/risk service seam.
- `src/agent/nodes/approval_gate.py` - Current LangGraph interrupt node. Keep interrupt mechanics, remove truth ownership.
- `src/agent/nodes/execute_action.py` and `src/tools/executors/action.py` - Current action draft path and node-only tool dispatch. Phase 13 may add hash/snapshot guard handoff, but Phase 14 owns full demo draft boundary.

### Established Patterns
- API routers currently use FastAPI dependencies, authenticated `User`, `AsyncSession`, and response envelopes. Phase 13 should preserve response shape while thinning transition logic.
- Existing repository tests use real DB fixtures and should be expanded into service transaction tests.
- Existing event tests prove redaction and sequence behavior. Phase 13 approval event tests should follow the same style.
- Static/boundary tests are already used in prior phases to prevent owner drift; use the same pattern for no router direct repository transition imports.

### Current Gaps To Plan Against
- `src/api/routers/approvals.py` performs role checks, self-approval, expiry, repository transition, graph resume payload construction, run status update, and trace step persistence in one route.
- `src/repositories/approval_repo.py` has v1 `decide(...)` that updates a single row without request/level/assignment version CAS or hash binding.
- `src/api/schemas/approvals.py` only accepts `approve|reject`; Phase 13 must add `accept|approve|edit|respond|reject|ignore` command semantics with expected versions.
- `approval_gate` interrupt payload contains proposed action and risk context but no approval revision, action payload hash, safety snapshot ref/hash, assignment versions, or trusted result marker.
- `ActionDraft` and `ActionDraftRepository.create_or_get(...)` currently bind only idempotency key and payload JSON, not payload hash or safety snapshot hash.
- `AgentTraceEvent` exists, but approval event additions are not registered yet.
- Current tests validate v1 behavior such as idempotent `ApprovalRepository.decide(...)` and router-built resume dict. Phase 13 must rewrite those tests around `ApprovalService` and typed trusted resume payloads.

</code_context>

<specifics>
## Specific Ideas

- User explicitly prefers clear, stable architecture over minimum diff. Large v1.0 approval rewrites are acceptable.
- Compatibility layers are allowed only with named owner, forbidden new references, test protection, and removal phase. For Phase 13, default to deleting/quarantining old approval transitions in the same phase.
- Treat `ActionSafetySnapshot` as a safety contract, not a cache. It should be small, immutable, hashable, and free of raw payloads.
- Treat `approval_result.v1` as a trusted server object. Ordinary chat, LLM output, and client-provided JSON cannot manufacture it.
- The Phase 13 plan should likely slice work in this order: canonical hash golden tests, snapshot golden tests, schema/migrations, ApprovalService transaction boundary, API/graph integration, event emission, quarantine/static tests, old test rewrite.

</specifics>

<deferred>
## Deferred Ideas

- Phase 14 owns `draft_outcome.v1`, final response demo wording, `action_drafts` v2 completion, and draft-only action boundary.
- Phase 15 owns full replay read API, lifecycle finalizer, V3 enrichment, retention/backfill, and `/replay` read-switch.
- Phase 17 owns real external action execution, execution/outbox/reconciliation/compensation tables, worker claim semantics, and real side effects.
- Phase 16 owns long-term/case memory and must not be used for approval evidence or snapshot truth.

</deferred>

---

*Phase: 13-approval-state-machine*
*Context gathered: 2026-06-15*
