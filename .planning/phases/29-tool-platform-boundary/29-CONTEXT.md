# Phase 29: Tool Platform Boundary - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 29 replaces scattered tool allowlists with descriptor-driven planner views, runtime authorization, result projection, and decision events.

This phase owns APF-06 and APF-07: planner-visible tools must be prompt-safe `ToolView` projections derived from `ToolDescriptor`, and runtime invocation must recheck authorization, resource scope, side-effect class, schema validity, and result projection through `ToolPolicyDecision`.

This phase does not implement the Phase 30 `BusinessFactService` authority boundary, full target graph migration, full external execution, MCP/dynamic external tool discovery, or a new artifact store.

</domain>

<decisions>
## Implementation Decisions

### Planner-visible `ToolView`

- **D-01:** Phase 29 uses a minimal `ToolViewV1` for planner visibility. It exposes only `name`, `description`, prompt-safe `input_schema`, `safe_usage_notes`, and `result_contract_version`. `docs/contract-spec.md` §12.6 has been aligned to this Phase 29 decision by removing the old prompt-visible `ToolView.schema_version` field; this is a spec correction, not an MVP divergence.
- **D-02:** Read/retrieval/action-style guidance may appear only as controlled natural language or restricted descriptions in `safe_usage_notes`. Raw policy/runtime fields such as `data_classification`, `side_effect`, `required_permission`, `caller_allowlist`, executor refs, event family, or internal permission reasons must not enter the planner view.
- **D-03:** `ToolView.input_schema` is a prompt-safe schema projection, not raw `ToolDescriptor.input_schema` passthrough. It keeps planner argument-construction essentials: field names, types, required fields, basic constraints, and short descriptions.
- **D-04:** `ToolView.input_schema` must strip defaults, examples, internal validation notes, permission/resource policy, adapter/upstream details, and any descriptor-only or policy-only metadata.
- **D-05:** `ToolView` is not an authorization result. Runtime invocation must still generate and enforce `ToolPolicyDecision(decision_stage="runtime_auth")`.
- **D-06:** Planner visibility equals policy visibility intersected with runtime availability. Executor-unregistered, dependency-missing, feature-flag-disabled, and target-placeholder tools must not enter the planner prompt.
- **D-07:** Policy-hidden, runtime-denied, and runtime-unavailable are distinct states. `hidden` is a visibility-stage policy decision, `denied` is a runtime auth decision, and `unavailable` is an availability/health reason.
- **D-08:** `visible_tools(...)` records the full low-payload visibility decision set for all catalog tools, preferably batched. The planner prompt receives only visible and available `ToolView` entries.

### `ToolPolicyDecision` Semantics

- **D-09:** `ToolPolicyDecision` is a domain-level tool policy object. It does not contain event envelope fields such as `event_id`, `sequence`, `occurred_at`, `run_id`, or `tenant_id`.
- **D-10:** Phase 29 writes `ToolPolicyDecision` objects through the Phase 28 replay-owned `DecisionEventEnvelopeV1` / `emit_decision_event(...)` path as controlled `redacted_payload` sub-objects. Phase 29 must not create a parallel event envelope or table.
- **D-11:** Visibility decisions may be batched in one low-payload event. Runtime auth decisions are usually one decision event per `invoke(...)`.
- **D-12:** Core Phase 29 `reason_codes` use a small stable enum and are contract-tested. Required core codes include: `visible`, `hidden_by_policy`, `caller_not_allowed`, `missing_permission`, `scope_denied`, `side_effect_blocked`, `schema_invalid`, `approval_required`, `safety_snapshot_required`, `idempotency_required`, and `tool_unavailable`.
- **D-13:** Future service-specific reason codes may use `<namespace>.<snake_case>` extension codes such as `business.permission_denied`, `rag.invalid_scope`, `memory.retention_blocked`, or `action.payload_hash_mismatch`. Freeform unknown codes are forbidden in contract paths.
- **D-14:** Visibility-stage decisions must not emit runtime-only reason codes such as `schema_invalid`, `approval_required`, `safety_snapshot_required`, or `idempotency_required`.
- **D-15:** `policy_version` comes from the `ToolPolicyEngine` stable policy/registry version, not from the model or caller.
- **D-16:** `data_classification` comes from a controlled `ToolDescriptor` field or catalog default mapping, not from LLM output or freeform call arguments.
- **D-17:** `resource_scope_binding` is produced by runtime from current args plus `ToolCallContext`. Visibility decisions may omit concrete resource binding; runtime auth decisions must include per-call binding where applicable.
- **D-18:** Runtime auth denial returns a safe `ToolResultV2` error such as `permission_denied`, `invalid_request`, or `unavailable`, and also writes a runtime auth decision event. Graph code continues to consume `ToolResultV2`; raw policy decisions are not business facts.
- **D-19:** Programmer or contract failures, such as invalid trusted context, invalid policy object construction, or missing event identity, may raise and should be caught by tests rather than silently mapped as normal tool results.

### Tool Platform Component Boundary

- **D-20:** Phase 29 directly establishes the target tool platform component boundaries: `ToolPlatform`, `ToolPolicyEngine`, `ToolRuntime`, and `ToolResultProjector`.
- **D-21:** These components are minimum public contracts and ownership boundaries, not a mandate to implement every future runtime capability in Phase 29.
- **D-22:** `ToolPlatform` is the graph-facing public facade. New graph/tool-platform integration after Phase 29 should target `ToolPlatform.visible_tools(...)` and `ToolPlatform.invoke(...)`. `docs/contract-spec.md` §9 / §12.6 has been aligned to this Phase 29 decision by naming `ToolPlatform` as the graph-facing dispatch boundary and `UnifiedToolManager` as a legacy compatibility adapter.
- **D-23:** `ToolPolicyEngine` owns visibility and runtime auth decisions. It does not call executors, write graph state, persist conversation records, or project prompt content.
- **D-24:** `ToolRuntime` owns the execution chain: input schema validation, runtime auth decision checkpoint, side-effect gate, approval/safety/idempotency required-field gates, executor dispatch, output schema validation, result projection, safe error mapping, and decision event emission.
- **D-25:** Phase 29 reuses existing `deadline_at` and `max_attempts` semantics. It does not introduce a new generic retry system, rate limiter, full timeout wrapper, feature-flag platform, DB artifact store, or full raw artifact persistence layer.
- **D-26:** `UnifiedToolManager` becomes a legacy compatibility adapter that delegates to `ToolPlatform`. It should not receive new policy/runtime logic.
- **D-27:** Existing business, knowledge, memory, and action executors should stay thin. Phase 29 should not rewrite domain executor internals or convert Phase 30 business fact scope into tool runtime logic.
- **D-28:** `investigate` migration is limited to the tool-platform integration points: use `ToolPlatform.visible_tools(...)` to provide planner `ToolView` entries and `ToolPlatform.invoke(...)` for runtime calls.
- **D-29:** The current bounded loop, `plan_next_step(...)`, termination semantics, business/RAG/memory executor behavior, and graph state accumulation should remain compatible. Broader planner-loop and target graph migration belongs to Phase 32.

### Runtime Resource Scope

- **D-30:** Phase 29 performs platform-layer resource binding and clear scope-deny checks only.
- **D-31:** Runtime should identify bindable args such as `tenant_id`, `merchant_id`, `order_id` / `order_no`, `refund_id` / `refund_case_no`, and `ticket_id`, and record the derived binding in `ToolPolicyDecision.resource_scope_binding`.
- **D-32:** If a call explicitly provides a `merchant_id` outside `ToolCallContext.merchant_scope`, runtime auth must deny before executor dispatch.
- **D-33:** When a resource id requires domain lookup to prove merchant ownership, Phase 29 must not fake a full authorization decision. `ToolPolicyDecision.resource_scope_binding` must indicate incomplete binding or `requires_domain_scope_check=true`.
- **D-34:** Domain ownership, freshness, not-found/permission-denied anti-enumeration behavior, and stable current business fact authority belong to Phase 30 `BusinessFactService`.

### Tool Result Projection

- **D-35:** `ToolResultProjector` emits four projection layers without adding a new artifact store: `normalized_result` for graph/service state, structured prompt projection plus `text_for_prompt` for LLM prompts, `audit_refs` / `resource_refs` for replay/conversation linking, and `debug_projection` for tests/developer diagnostics.
- **D-36:** `raw_artifact_ref` and `raw_artifact_hash` may be reserved as optional reference fields, but Phase 29 must not add DB schema or commit to full artifact persistence.
- **D-37:** `ToolResultV2.data` is treated as untrusted/raw-ish for every tool class, including read and retrieval tools. It may contain PII, upstream error text, prompt injection text, internal fields, or over-broad business payloads.
- **D-38:** Graph state must not receive unprojected `ToolResultV2.data`. AgentState may consume only projector outputs such as `normalized_result`, structured prompt projection, `business_fact_refs`, policy candidate/evidence refs, `resource_refs`, and safe error summaries.
- **D-39:** Prompt projection should be structured first, with a bounded text compatibility field. Suggested fields include `tool_name`, `status`, `summary`, `business_fact_refs`, `policy_candidate_refs`, `resource_refs`, `warnings`, `safe_error`, `redaction_applied`, and `text_for_prompt`.
- **D-40:** LLM prompts must not consume `normalized_result` or raw `ToolResultV2.data` directly.
- **D-41:** `ToolResultProjector` does not own event emission. `ToolPolicyEngine` / `ToolRuntime` write policy decision events. Projector outputs carry linking refs such as `tool_call_id`, `tool_result_id`, `policy_decision_ref` or event id, `audit_ref`, and `resource_refs`.
- **D-42:** Projection-level events are out of scope for Phase 29 and may be reconsidered in Phase 35 Replay and Eval Hardening if needed.

### the agent's Discretion

- Exact module paths, class signatures, helper names, and test file splits are left to planning as long as the ownership boundaries above are preserved.
- Exact event type names are left to planning, but they must use the Phase 28 `DecisionEventEnvelopeV1` path, be registered/valid, and keep payloads low-volume and prompt-safe.
- Exact shape of `debug_projection` is flexible, but it must not become prompt input by default and must not contain raw adapter payloads, secrets, PII, or internal permission details.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Prior Decisions

- `.planning/ROADMAP.md` - Phase 29 goal, APF-06/APF-07 mapping, dependency on Phase 28, and success criteria.
- `.planning/REQUIREMENTS.md` - APF-06/APF-07 requirements and v1.9 out-of-scope boundaries.
- `.planning/PROJECT.md` - v1.9 modular-monolith platform direction and safety-boundary constraints.
- `.planning/STATE.md` - Current milestone state, Phase 29 readiness, and accumulated decisions.
- `.planning/phases/26-architecture-contract-baseline/26-CONTEXT.md` - `contract-spec.md` authority, modular-monolith direction, and named deferral discipline.
- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - `TrustedContext` source rules and `ToolCallContext` projection constraints.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - `DecisionEventEnvelopeV1`, replay-owned emitter, reason/version normalization, and no parallel event envelope.

### Normative Tool Platform Contracts

- `docs/contract-spec.md` §0.2 - ToolPlatform ownership row and forbidden raw adapter / prompt leakage access pattern.
- `docs/contract-spec.md` §8.0 - Canonical `TrustedContext` source for tool identity/scope projection.
- `docs/contract-spec.md` §12.4 - Node-level tool allowlist, event-family split, and no write tools in `investigate`.
- `docs/contract-spec.md` §12.5 - `ToolCallContext`, `ToolRequest`, `ToolResultV2`, `ToolError`, and business/policy ref separation.
- `docs/contract-spec.md` §12.6 - `ToolDescriptor`, `ToolView`, `ToolPolicyDecision`, catalog/manager rules, planner visibility, runtime auth, and descriptor-derived tool catalog.
- `docs/contract-spec.md` §17.2 - Decision event envelope fields and redaction/event obligations.
- `docs/target-agent-platform-architecture-plan.md` §10 - Target ToolPlatform structure, planner view/runtime auth split, runtime responsibilities, and result projection layers.
- `docs/target-agent-platform-architecture-plan.md` "Phase 29" section - Implementation sequence for tool catalog, policy engine, runtime, platform facade, view, and projector.
- `docs/eval-test-plan.md` - Tool policy decision contract tests and negative cases for prompt leakage and visible-does-not-imply-allowed.

### Existing Implementation Anchors

- `src/tools/catalog.py` - Current `ToolDescriptor`, `RegisteredTool`, default descriptors, exposure fields, and declaration-only catalog.
- `src/tools/manager.py` - Current `UnifiedToolManager` dispatch, descriptor filtering, runtime gates, executor registry, side-effect checks, schema validation, and safe error mapping.
- `src/tools/contracts.py` - Current `ToolCallContext`, `ToolResultV2`, `ToolError`, `BusinessFactRefV1`, `ToolResultPromptSummary`, and storage/projection contracts.
- `src/tools/validation.py` - JSON schema validation helper currently used by manager runtime gates.
- `src/platform/context_projections.py` - `project_to_tool_context(...)`, `project_to_replay_context(...)`, and projection-local metadata patterns.
- `src/platform/trusted_context.py` - Canonical trusted identity/scope schema and merchant-scope semantics.
- `src/replay/decision_events.py` - Phase 28 `DecisionEventEnvelopeV1`, `emit_decision_event(...)`, reason-code normalization, and version placement.
- `src/agent/nodes/investigate.py` - Current graph tool loop, descriptor prompt surface, runtime invoke path, event emission, tool result projection helpers, and graph-state accumulation.
- `src/agent/events.py` - Current event family classification and compatibility emitter.
- `src/tools/executors/business.py` - Existing thin business executor path.
- `src/tools/executors/knowledge.py` - Existing knowledge/RAG retrieval executor path and `ToolCallContext` to `KnowledgeContext` projection.
- `src/tools/executors/memory.py` - Existing reviewed case memory retrieval executor path.
- `src/tools/executors/action.py` - Existing action tool executor path for node-only draft creation.

### Tests To Reuse Or Extend

- `tests/tools/test_catalog.py` - Catalog descriptor single-source, action node-only, and declaration-only behavior.
- `tests/agent/test_tools/test_unified_tool_manager.py` - Current manager dispatch, permissions, side-effect gates, schema validation, output validation, unavailable behavior, and projected tool context.
- `tests/agent/test_nodes/test_investigate.py` - Current investigate loop, trusted context source, event emission, prompt-safe tool result refs, raw payload stripping, and invalid planner output rejection.
- `tests/platform/test_context_projections.py` - Tool context projection, no canonical widening, and projection-local fields.
- `tests/replay/test_decision_events.py` and `tests/agent/test_events.py` - Decision event envelope validation, reason-code normalization, redaction/resource-ref guards, and compatibility emitter behavior.
- `tests/replay/test_sequence_allocator.py` - Sequence allocation consistency for multiple event writers.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `ToolCatalog` already provides a single descriptor list with `kind`, `side_effect`, `required_permission`, `caller_allowlist`, `event_family`, `resource_type`, `executor`, `exposure`, and safety/idempotency flags.
- `UnifiedToolManager.invoke(...)` already implements many runtime checks that `ToolRuntime` can reuse or move behind the new boundary: descriptor lookup, caller allowlist, side-effect gate, permission check, input schema validation, approval/safety/idempotency field checks, executor dispatch, output schema validation, safe error mapping, and event family selection.
- `project_to_tool_context(...)` already derives `ToolCallContext` from canonical `TrustedContext`; Phase 29 should keep using this projection rather than accepting permissions/scope from AgentState.
- `emit_decision_event(...)` already provides the replay-owned event envelope and redaction/resource-ref guard path required for visibility/runtime decisions.
- `investigate._project_tool_result(...)`, `_safe_prompt_summary(...)`, `_without_raw_payload(...)`, and conversation tool call/result persistence are useful starting points for `ToolResultProjector`, but they should stop being the only projection boundary after Phase 29.

### Established Patterns

- Strict contracts use Pydantic models with `extra="forbid"`.
- Trusted identity/scope comes from `TrustedContextFactory` and projections, not from user payload, model output, or checkpointed AgentState.
- Graph nodes should get thinner over v1.9 and call service/platform boundaries rather than duplicating policy logic.
- Tool errors are returned to graph as safe `ToolResultV2` statuses, not raw exceptions or upstream payloads.
- Prompt-facing content must use allowlisted projections and bounded summaries; raw tool data, private/debug fields, permission internals, and authority bodies must not enter prompts.

### Integration Points

- `investigate` currently calls `manager.descriptors("investigate")` and validates planner selections against descriptor names. Phase 29 should replace this planner surface with `ToolPlatform.visible_tools(...)` and `ToolView` objects.
- `investigate` currently calls `manager.invoke(...)`. Phase 29 should route this through `ToolPlatform.invoke(...)` / `ToolRuntime`.
- `UnifiedToolManager` should remain temporarily usable by existing tests/callers but delegate new behavior to `ToolPlatform`.
- Existing `BusinessToolExecutor`, `KnowledgeToolExecutor`, `MemoryToolExecutor`, and `ActionToolExecutor` should remain dispatch adapters. They should not own planner visibility or runtime authorization.
- Result projection should preserve current conversation tool record compatibility while making projection ownership explicit in `ToolResultProjector`.

</code_context>

<specifics>
## Specific Ideas

- The user intentionally chose a constrained full component split for Phase 29: `ToolPlatform`, `ToolPolicyEngine`, `ToolRuntime`, and `ToolResultProjector` should be named platform boundaries now, but the phase must not build every future runtime capability.
- `UnifiedToolManager` should be treated as a legacy compatibility adapter after Phase 29, not as the place where new policy/runtime logic accumulates.
- `ToolView` should be small enough that tests can assert descriptor-only fields are absent: executor refs, required scopes, approval policy internals, audit event family, allowed callers, internal permission reasons, and hidden side-effect capability.
- Runtime auth should be explainable in replay: "planner could see this tool" and "this invocation with these args/context was allowed or denied" are separate decisions.
- Scope binding should avoid overclaiming. `merchant_id` can be denied directly when explicit and out of scope; `order_no` ownership needs domain lookup and therefore belongs to Phase 30.

</specifics>

<deferred>
## Deferred Ideas

- Full target graph/planner-loop migration belongs to Phase 32 Intent Graph Migration.
- Full current business fact authority, domain ownership checks, freshness, and not-found/permission-denied anti-enumeration behavior belong to Phase 30 BusinessFactService Boundary.
- Generic retry/rate-limit/feature-flag/runtime policy infrastructure is not part of Phase 29 unless required for the minimal hard gate.
- DB-backed raw artifact persistence and a full artifact store are deferred to a named post-v1.9 ArtifactStore phase, only if Phase 35 Replay and Eval Hardening identifies a replay/eval retention need.
- Projection-level replay events are deferred to Phase 35 Replay and Eval Hardening if needed.
- Dynamic external tool/MCP discovery remains future APF-FUT-03 after tool policy decisions, side-effect gates, and prompt-safe projections are stable.

</deferred>

---

*Phase: 29-tool-platform-boundary*
*Context gathered: 2026-06-23*
