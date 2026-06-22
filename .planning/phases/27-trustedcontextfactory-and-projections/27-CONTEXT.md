# Phase 27: TrustedContextFactory and Projections - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 27 --auto`

<domain>
## Phase Boundary

Phase 27 introduces the shared trusted context foundation for v1.9 Agent Platform Foundation. It must create canonical `TrustedContext` only from trusted API/auth/run boundaries and derive service-specific projections for tools, knowledge, memory, approval, replay, and intent policy.

This phase should not rewrite the whole graph, tool platform, knowledge service, memory platform, approval service, replay service, or business fact boundary. It should add the shared context contract/factory and the smallest integration points needed to prove downstream modules can consume one common trusted source.

</domain>

<decisions>
## Implementation Decisions

### Canonical TrustedContext Source

- **D-01:** `TrustedContext` must match `docs/contract-spec.md` §8.0 exactly: `schema_version`, `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, `trace_id`, and `locale`.
- **D-02:** The factory must only accept trusted API/auth/run inputs, such as authenticated user identity, verified token scopes, server-created thread/run/trace ids, session id, locale, and server-derived merchant scope. It must not accept LLM output, user payload fields, request body overrides, or graph state fields as authority for identity/scope.
- **D-03:** Canonical context must reject or ignore projection-local fields. `request_id`, `tool_call_id`, `caller_node`, `deadline_at`, `attempt`, `max_attempts`, `idempotency_key`, `approval_ref`, `safety_snapshot_ref`, `policy_snapshot_ref`, `effective_at`, `channel`, `policy_version`, `model_version`, `tool_version`, and artifact refs must not become canonical `TrustedContext` fields.
- **D-04:** `MerchantScopeV1` semantics from `contract-spec.md` §8.0 are in scope: deny-all for empty scope, wildcard only through explicit `"*"`, all-provided-dimensions matching, and no model/user widening.

### Projection APIs

- **D-05:** Expose projection methods for `ToolCallContext`, `KnowledgeContext`, `MemoryContext`, `ApprovalContext`, `ReplayContext`, and `IntentPolicyContext`. Projections may add consumer-local metadata, but all identity/scope fields must remain a direct subset/projection of canonical `TrustedContext`.
- **D-06:** `ToolCallContext` must preserve the existing `tool_context.v2` contract while moving trusted identity/scope/permission fields behind the factory. Tool-call-local fields remain caller-injected and projection-local.
- **D-07:** `KnowledgeContext` must keep `effective_at` as run-derived retrieval time, not trusted identity. Merchant filtering must use `merchant_scope` from trusted context, not user/model-provided filters.
- **D-08:** `MemoryContext` should carry tenant/user/thread/run identity plus memory-scope/retention inputs needed by later `MemoryContextService`, without making memory an authority for policy evidence, business facts, approval/action, or replay truth.
- **D-09:** `ApprovalContext` should carry actor/scope plus approval/action safety refs needed by `ApprovalService`, but ordinary chat and LLM output must still be unable to create approval truth.
- **D-10:** `ReplayContext` should carry run/thread/trace identity and version/artifact refs as replay metadata, without requiring Phase 27 to implement the Phase 28 decision event envelope.
- **D-11:** `IntentPolicyContext` should include tenant/role/locale/thread/run identity and projection-local `channel`; `channel` must not widen canonical identity.

### Integration Scope

- **D-12:** Prefer a dedicated shared context/factory module over adding more responsibilities to prompt projectors. Existing prompt projection code in `src/agent/context/projectors.py` stays focused on prompt-safe text projection.
- **D-13:** Keep integration minimal and compatibility-preserving: update the current API/search/tool/context construction seams enough to prove the factory is used, but do not migrate all graph nodes or split services in this phase.
- **D-14:** `AgentState` identity remains a projection and should not become the source for permissions or merchant scope. Service contexts that need permissions/scope must be built from trusted config/factory, not checkpointed state.
- **D-15:** Existing `ToolCallContext`, `KnowledgeContext`, `SessionMemoryBundleService`, `Approval*Command`, and replay schema tests should guide compatibility. Breaking public schema versions is out of scope unless `contract-spec.md` explicitly requires it.

### Intent and Slot Registry Freeze

- **D-16:** Freeze a read-only `IntentPolicyRegistry` / `SlotPolicyRegistry` catalog contract over the existing `INTENT_DEFINITIONS`, `REQUIRED_SLOT_POLICY`, route policy, and precedence data. Phase 27 should not change intent behavior or graph routing semantics beyond exposing stable read APIs.
- **D-17:** The registry must make it harder for Tool/Memory/RAG phases to invent temporary policy shape. It should be usable by later Phase 32 graph migration without forcing Phase 27 to split `IntentService`.

### Verification Strategy

- **D-18:** Add contract tests for exact canonical field set, `trusted_context.v1` schema version, no extra canonical fields, trusted-source construction, deny-all merchant scope, wildcard semantics, and model/user override rejection.
- **D-19:** Add projection tests proving `request_id`, `effective_at`, `channel`, and policy/model/tool versions stay projection-local or metadata and never appear in canonical `TrustedContext`.
- **D-20:** Add focused integration tests for the current seams that manually construct contexts today: search API `KnowledgeContext`, agent run trusted tool config / `ToolCallContext`, knowledge tool executor projection, and graph/run identity consistency.
- **D-21:** Add import/boundary checks or grep-verifiable tests proving prompt projectors and downstream modules consume projections rather than redefining trusted identity/scope contracts.

### the agent's Discretion

- Exact module path and class/function names are left to planning, as long as the design is a dedicated shared context/factory boundary and avoids circular imports.
- Exact migration ordering across call sites is left to planning; keep the first phase small enough to verify thoroughly.
- Exact test file split is left to planning, but tests must be focused and runnable with `uv run pytest`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 27 goal, APF-03/APF-04 mapping, success criteria, and dependency on Phase 26.
- `.planning/REQUIREMENTS.md` - APF-03/APF-04 requirements and v1.9 out-of-scope boundaries.
- `.planning/STATE.md` - v1.9 sequencing decisions and current GSD metadata caveats.
- `.planning/phases/26-architecture-contract-baseline/26-CONTEXT.md` - Phase 26 decisions about `contract-spec.md` authority and v1.9 implementation order.
- `.planning/phases/26-architecture-contract-baseline/26-01-SUMMARY.md` - Phase 26 completion summary, module ownership registry decisions, and validation caveats.

### Normative Architecture Contracts

- `docs/contract-spec.md` §0.2 - Normative module ownership boundary registry, including `TrustedContextFactory`.
- `docs/contract-spec.md` §8.0 - Canonical `TrustedContext`, `MerchantScopeV1`, and projection rules.
- `docs/contract-spec.md` §8.3 - `KnowledgeContext` as a `TrustedContext` projection plus run-derived `effective_at`.
- `docs/contract-spec.md` §10 - `AgentState` identity projection and lifecycle registry.
- `docs/contract-spec.md` §12.5 - `ToolCallContext` contract and tool-call-local fields.
- `docs/contract-spec.md` §17.2 - Minimal event envelope fields that later replay/decision-event work must source from trusted context.
- `docs/target-agent-platform-architecture-plan.md` §7 - Target `TrustedContextFactory` rationale and projection table.
- `docs/target-agent-platform-architecture-plan.md` "Phase 27" section - Implementation sequence and explicit non-goals.
- `docs/eval-test-plan.md` - Eval/contract test expectations for platform boundaries.

### Existing Implementation Seams

- `src/tools/contracts.py` - Current `ToolCallContext`, `ToolResultV2`, and business fact ref contracts.
- `src/knowledge/schemas.py` - Current `KnowledgeContext` and evidence projection behavior.
- `src/api/routers/search.py` - Current direct `KnowledgeContext` construction.
- `src/api/routers/agent.py` - Current `/agent/chat` trusted run/tool config construction.
- `src/api/routers/agent_runs.py` - Current `/agent-runs` trusted tool config, run id, and scope construction.
- `src/tools/executors/knowledge.py` - Current `ToolCallContext` to `KnowledgeContext` projection.
- `src/agent/graph.py` - Current run identity and trusted approval result checks.
- `src/agent/state.py` - Current AgentState identity fields and ephemeral/durable split.
- `src/agent/intent_policy.py` - Existing intent definitions and slot/route policy catalog.
- `src/agent/context/projectors.py` - Existing prompt-safe projection utilities that should not become trusted context authority.
- `src/agent/context/session_memory_bundle.py` and `src/memory/session_bundle.py` - Current session memory identity consumption and bundle projection seams.
- `src/approvals/schemas.py` - Approval trusted command/result contracts.
- `src/replay/schemas.py` - Replay event identity fields.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/tools/contracts.py::ToolCallContext` already has the target tool context schema version and most projection-local fields, but trusted identity/scope fields are still supplied ad hoc by callers.
- `src/knowledge/schemas.py::KnowledgeContext` already models a lightweight trusted projection plus `effective_at`, but direct construction exists in API and tool executor paths.
- `src/api/routers/agent_runs.py::_trusted_tool_config` already intersects verified token scopes with DB role scopes and derives merchant scope; this is a strong trusted-source input for the factory.
- `src/business/service.py::_merchant_scope_allows` already encodes deny-first/all-provided-dimensions merchant scope behavior that can inform `MerchantScopeV1` tests.
- `src/agent/intent_policy.py` already has a read-only data shape suitable for initial `IntentPolicyRegistry` / `SlotPolicyRegistry` wrappers.

### Established Patterns

- Contracts are explicit Pydantic models with `extra="forbid"` where strictness matters.
- Tests use focused pytest modules and usually assert both positive contract behavior and negative leakage/override cases.
- Agent prompt projection utilities are intentionally prompt-safe and should remain separate from trusted identity/scope authority.
- API routes and graph nodes should get thinner over v1.9, but Phase 27 should not attempt broad router/graph migration.

### Integration Points

- `/api/v1/search` currently creates `KnowledgeContext` directly from authenticated user and request state.
- `/api/v1/agent/chat` and `/api/v1/agent-runs` currently create input state and configurable trusted tool metadata manually.
- `KnowledgeToolExecutor` currently converts `ToolCallContext` to `KnowledgeContext`, including `effective_at` fallback.
- `SessionMemoryBundleService` currently loads by tenant/user/thread/run identity; later `MemoryContextService` can consume a `MemoryContext` projection.
- `graph.py::_trusted_approval_result` already enforces approval result tenant/run/hash consistency and should remain fail-closed.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 27 as a foundation phase: add shared contracts and migration seams first, not a broad behavior rewrite.
- The most important negative tests are no-widening tests: user/model/request payloads cannot overwrite tenant/user/role/permissions/merchant_scope/thread/run/trace.
- Projection-local fields should be deliberately present in projection tests so failures are obvious if they leak into canonical context.

</specifics>

<deferred>
## Deferred Ideas

- Decision event envelope implementation belongs to Phase 28.
- Tool descriptor/policy runtime migration belongs to Phase 29.
- Business fact authority migration belongs to Phase 30.
- Full MemoryContextService platform migration belongs to Phase 31.
- Target graph vocabulary migration and `IntentService` split belong to Phase 32.
- RAG verified context build / claim verification belongs to Phase 33.
- Approval/action boundary hardening beyond context projection belongs to Phase 34.
- Replay/eval hardening belongs to Phase 35.
- Physical microservice extraction remains post-v1.9 / future scope.

</deferred>

---

*Phase: 27-trustedcontextfactory-and-projections*
*Context gathered: 2026-06-22*
