# Phase 28: Decision Event Foundation - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 28 establishes the minimal `DecisionEventEnvelopeV1` / `minimal_event_envelope.v1` foundation for later platform services. It should add the explicit envelope contract, reason-code convention, redaction/resource-ref policy, and emitter foundation used by later Tool, Memory, RAG, Approval, Action, and Replay/Eval phases.

This phase must not create a parallel replay event format, must not widen the required envelope keys from `docs/contract-spec.md` §17.2, and must not implement dashboard UI, full replay service behavior, broad eval coverage, physical microservices, or real external execution.

</domain>

<decisions>
## Implementation Decisions

### Envelope Contract Surface

- **D-01:** Add an explicit `DecisionEventEnvelopeV1` Pydantic schema. The current `ReplayService.project_minimal_event()` dict projection and `src.agent.events` constants are too implicit for the Phase 28 foundation contract.
- **D-02:** Place the schema in `src/replay/decision_events.py`. Observability / Replay owns `DecisionEventEnvelopeV1`, `emit_decision_event`, and replay lifecycle events; do not put this contract under `src/platform/`.
- **D-03:** Lock the schema strictly: `schema_version="minimal_event_envelope.v1"`, required fields from `contract-spec.md` §17.2, `extra="forbid"`, registered `event_type` validation, and basic conditional validation such as operation lifecycle events requiring `operation_id`.
- **D-04:** Do not implement `ReplayEventV3` parent/attempt pairing in Phase 28; that remains full replay/event pairing responsibility.
- **D-05:** Do not change DB schema. Reuse existing `agent_trace_events` / `AgentTraceEvent` support for `minimal_event_envelope.v1` and `replay_event.v3` rows. Phase 28 should add the facade, emitter, normalization helpers, and tests.

### Emitter API And Trusted Identity

- **D-06:** Add `emit_decision_event(...)` in `src/replay/decision_events.py`. It should be the replay-owned entrypoint for minimal decision event emission and should call the existing `ReplayService.append_event(...)` persistence path.
- **D-07:** Keep `src.agent.events.emit_event` as a compatibility wrapper, but route it through the new replay-owned entrypoint so existing tool/memory/approval/action writers enter the unified contract without broad rewrites.
- **D-08:** Prefer `ReplayContext` / trusted projection as the identity source for new emitter usage. `run_id`, `tenant_id`, `thread_id`, and `trace_id` should come from Phase 27 trusted context projection, not caller-assembled ad hoc values.
- **D-09:** Identity/source failures must fail closed with a testable error. Decision events are audit/replay truth; do not write partial-identity events and do not silently skip event emission as a normal success path.
- **D-10:** Migrate only the thin wrapper and key path in Phase 28. Do not broadly rewrite all existing writer call sites; later domain phases own their service-specific event payload migrations.

### Reason-Code And Version Placement

- **D-11:** Standardize decision payloads on `reason_codes: list[str]`. Single-reason decisions still use a one-item list.
- **D-12:** Compatibility wrappers may accept legacy `reason_code` and normalize it into `reason_codes`, but downstream platform services should not continue producing split singular/plural formats.
- **D-13:** Normalize `reason_codes` with first-seen de-duplication. Preserve business priority order; `reason_codes[0]` carries primary-reason semantics. Do not alphabetically sort reason codes.
- **D-14:** Place policy/model/tool version metadata under `redacted_payload.versions`, for example `policy_version`, `model_version`, and `tool_version`. The envelope top level keeps only `redaction_policy_version`.
- **D-15:** Reason codes must be non-empty `snake_case` strings and de-duplicated. Phase 28 should add tests for this convention, but should not introduce a global allowlist because Phase 29-35 service-specific reason codes are not all known yet.

### Redaction, Resource Refs, And Initial Coverage

- **D-16:** Tighten common helpers and add focused key-path tests. Phase 28 should establish the foundation and necessary regressions, not pull full Tool/Memory/RAG/Approval/Action domain migrations into this phase.
- **D-17:** `resource_refs` must contain only stable typed refs, hashes, and ids. Continue patterns such as `action_payload_hash`, `safety_snapshot_hash`, approval revision refs, `draft_id`, tool names, and evidence/business fact refs.
- **D-18:** Do not store raw business payloads, tool arguments, prompts, user text, PII, or secrets in `resource_refs`. Business identifiers such as order/refund numbers should not be naked debug fields; when needed, use typed refs, hashes, or business fact / evidence refs.
- **D-19:** Redaction guard coverage must inspect both `redacted_payload` and `resource_refs`, so unsafe keys cannot bypass redaction through refs.
- **D-20:** Phase 28 tests should emphasize contract strictness, negative leakage, and wrapper compatibility: required/conditional fields, schema extra rejection, reason/version normalization, legacy `reason_code` conversion, forbidden key checks in payload and refs, and no regression in sequence allocation.

### The Agent's Discretion

- Exact class/helper names are flexible as long as `DecisionEventEnvelopeV1` and `emit_decision_event(...)` exist at the replay boundary and the existing `src.agent.events.emit_event` compatibility path remains usable.
- Exact test file split is flexible. Prefer focused tests near `tests/replay/` and compatibility regressions for `tests/agent/test_events.py` or equivalent existing event tests.
- Exact error class names are left to planning, but identity and contract failures must be explicit and testable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Prior Decisions

- `.planning/ROADMAP.md` - Phase 28 goal, APF-05 mapping, dependency on Phase 27, and success criteria.
- `.planning/REQUIREMENTS.md` - APF-05 requirement and v1.9 out-of-scope boundaries.
- `.planning/STATE.md` - Current v1.9 sequencing decisions and Phase 28 readiness.
- `.planning/phases/26-architecture-contract-baseline/26-CONTEXT.md` - `contract-spec.md` authority, microservice-ready modular monolith direction, and implementation order.
- `.planning/phases/26-architecture-contract-baseline/26-01-SUMMARY.md` - Phase 26 completion note that Phase 28 must use `contract-spec.md` §17.2, not the architecture document mirror, as execution contract.
- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - TrustedContext source rules, projection-local version metadata, and Phase 28 event identity dependency.

### Normative Architecture Contracts

- `docs/contract-spec.md` §0.2 - Observability / Replay ownership over `DecisionEventEnvelopeV1`, `emit_decision_event`, replay artifacts, sequence allocator, and redaction policy.
- `docs/contract-spec.md` §8.0 - Canonical `TrustedContext` identity/scope source; user/LLM payloads cannot override trusted run/tenant/thread/trace identity.
- `docs/contract-spec.md` §17.2 - Minimal event envelope fields, event type registry, per-run sequence allocator contract, and redaction requirements.
- `docs/contract-spec.md` §18.4 - Event table transition strategy and existing `agent_trace_events` minimal/V3 coexistence.
- `docs/target-agent-platform-architecture-plan.md` §14 - Architecture mirror for Observability / Replay and decision event coverage rationale; yields to `contract-spec.md` on conflict.
- `docs/target-agent-platform-architecture-plan.md` Phase 28 section - Explicit Phase 28 non-goals and service-level-field placement guidance.

### Existing Implementation Anchors

- `src/replay/service.py` - Existing `ReplayService.append_event(...)`, sequence allocation, minimal event projection, and V3 projection behavior.
- `src/replay/schemas.py` - Strict `ReplayEventV3` pattern to mirror for the minimal envelope facade style.
- `src/replay/validators.py` - Current event type registry, redaction guard, and retention classification.
- `src/agent/events.py` - Existing Phase 10 compatibility wrapper to route through the new replay-owned entrypoint.
- `src/platform/context_projections.py` - Existing `ReplayContext` and `project_to_replay_context(...)` projection with policy/model/tool version metadata.
- `src/platform/trusted_context.py` - Canonical trusted identity and scope source rules.
- `src/db/models.py::AgentTraceEvent` - Existing event table ORM model supporting `minimal_event_envelope.v1` and `replay_event.v3`.
- `src/replay/lifecycle.py` - Existing run lifecycle writer and reason-code usage that should remain compatible.
- `src/approvals/events.py` - Existing approval event helper with approval resource-ref patterns.
- `src/agent/nodes/investigate.py` - Existing tool/RAG event emission path and operation/iteration payload behavior.
- `src/agent/nodes/memory_write.py` - Existing memory write event path and memory reason-code payload behavior.

### Tests To Reuse Or Extend

- `tests/agent/test_events.py` - Existing minimal event, sequence, redaction, event family, and compatibility coverage.
- `tests/replay/test_sequence_allocator.py` - Shared allocator coverage across graph, memory, approval, action draft, replay backfill, and lifecycle writers.
- `tests/replay/test_replay_migration_contract.py` - Existing minimal/V3 migration coexistence expectations.
- `tests/replay/test_replay_service.py` - Replay projection behavior.
- `tests/platform/test_context_projections.py` - Projection-local version metadata and no TrustedContext widening.
- `tests/platform/test_trusted_context.py` and `tests/platform/test_trusted_context_factory.py` - Trusted identity/source guarantees.
- `tests/agent/test_nodes/test_investigate.py` - Tool/RAG event emission integration expectations.
- `tests/agent/test_tools/test_create_coupon_grant_draft.py` - Action draft event payload/resource-ref safety expectations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `ReplayService.append_event(...)` already owns persistence, advisory-lock sequence allocation, event-id generation, redaction guard invocation, and minimal/V3 projection switching.
- `ReplayService.project_minimal_event(...)` already returns the target minimal envelope shape, but as an untyped dict. Phase 28 should wrap this shape in `DecisionEventEnvelopeV1`.
- `AgentTraceEvent` already stores the required minimal fields and V3 extension fields in one table. Its schema/version check supports both `minimal_event_envelope.v1` and `replay_event.v3`.
- `src.agent.events.emit_event(...)` already acts as the current graph/tool/memory compatibility surface. It is the right place for a thin wrapper migration.
- `ReplayContext` already carries trusted run/tenant/thread/trace identity plus projection-local version metadata from Phase 27.
- `guard_redacted_payload(...)` and `REPLAY_EVENT_TYPES` provide a starting point for shared validation. Phase 28 should expand the guard approach to `resource_refs`.
- Existing sequence allocator tests already cover concurrent writers and cross-writer ordering; Phase 28 should preserve them rather than replace allocator behavior.

### Established Patterns

- Strict contract schemas use Pydantic with `extra="forbid"`.
- Trusted identity comes from `TrustedContextFactory` and service-safe projections, not from user payloads, LLM outputs, or checkpointed `AgentState`.
- Replay/decision events are audit truth. Memory, prompt context, raw tool payloads, and private reasoning remain contextual or debug-only and must not become replay authority.
- Current code favors incremental compatibility wrappers before broad service migrations.
- Tests cover both happy paths and negative leakage/authority-boundary cases.

### Integration Points

- `src/replay/decision_events.py` should introduce `DecisionEventEnvelopeV1`, normalization helpers, redaction/resource-ref guards, and `emit_decision_event(...)`.
- `src.agent.events.emit_event(...)` should call the new replay-owned emitter while preserving existing call signatures enough for current writers.
- `ReplayService.project_minimal_event(...)` should validate/project through `DecisionEventEnvelopeV1` or otherwise prove exact schema alignment.
- Existing tool/RAG, memory, approval, action draft, and lifecycle event writers should continue to work through the compatibility path while gaining strict envelope/redaction/reason/version behavior where applicable.
- Tests should prove no new top-level envelope keys are added for service-level metadata; service metadata belongs in `redacted_payload`, `redacted_payload.versions`, or `resource_refs`.

</code_context>

<specifics>
## Specific Ideas

- User explicitly prefers `DecisionEventEnvelopeV1` as a visible foundation contract because a dict projection is too implicit for downstream planning.
- User cited `src/replay/service.py`, `src/agent/events.py`, `src/replay/schemas.py`, `src/replay/validators.py`, `src/platform/context_projections.py`, and `src/platform/trusted_context.py` as concrete implementation anchors.
- Example normalized payload shape:

```json
{
  "reason_codes": ["scope_denied", "missing_permission"],
  "versions": {
    "policy_version": "tool_policy.v1",
    "tool_version": "refund_lookup.v2",
    "redaction_policy_version": "redaction.v1"
  }
}
```

- `reason_codes[0]` should preserve primary-reason semantics; deterministic first-seen de-duplication is preferred over alphabetic sorting.
- Phase 28 should intentionally avoid making a global reason-code allowlist because later service phases will add service-specific reasons.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within Phase 28 scope. Full Tool/Memory/RAG/Approval/Action event payload migrations remain owned by their later phases, and full ReplayEventV3 enrichment/replay service behavior remains outside Phase 28.

</deferred>

---

*Phase: 28-decision-event-foundation*
*Context gathered: 2026-06-23*
