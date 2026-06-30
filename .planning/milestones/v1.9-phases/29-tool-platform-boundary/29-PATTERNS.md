# Phase 29: Tool Platform Boundary - Pattern Map

**Mapped:** 2026-06-23
**Scope:** APF-06 ToolView planner projection and APF-07 ToolPolicyDecision runtime authorization.
**Primary anchors:** `src/tools/*`, `src/agent/nodes/investigate.py`, `src/replay/*`, `src/conversation/*`, `src/agent/context/*`.

## Closest Analog Files

| New/Modified Target | Role / Data Flow | Closest Existing Analog | Match | Copy Pattern |
|---|---|---|---|---|
| `src/tools/platform.py` / `ToolPlatform` | facade, request-response | `src/tools/manager.py:36-73`, `src/agent/nodes/investigate.py:64-170` | role-match | Public graph-facing facade with `visible_tools(...)` and `invoke(...)`; keep graph call sites thin and preserve current manager compatibility. |
| `src/tools/policy.py` / `ToolPolicyEngine`, `ToolPolicyDecision` | policy service, request-response | `src/tools/catalog.py:14-32`, `src/tools/manager.py:73-102`, `src/platform/trusted_context.py:23-69`, `src/replay/decision_events.py:118-136` | partial | Strict Pydantic domain object, descriptor-derived policy fields, deny-before-dispatch checks, stable reason-code validation. |
| `src/tools/runtime.py` / `ToolRuntime` | service, request-response | `src/tools/manager.py:73-124`, `src/tools/validation.py:8-47`, `src/tools/manager_results.py:8-29` | exact | Current gate order: descriptor lookup, caller allowlist, side-effect, permission, input schema, approval/safety/idempotency, executor availability, dispatch, output schema, safe errors. |
| `src/tools/projection.py` / `ToolResultProjector` | projector, transform | `src/tools/contracts.py:111-142`, `src/agent/nodes/investigate.py:369-421`, `src/conversation/service.py:201-271`, `src/agent/context/projectors.py:148-178` | role-match | Convert `ToolResultV2` to normalized graph data, prompt summary, refs/audit links, and debug-only projection before graph/prompt use. |
| `ToolViewV1` contract | model, transform | `src/tools/catalog.py:14-32`, `src/tools/contracts.py:13-37`, `src/platform/context_projections.py:15-23` | role-match | Use `BaseModel` with `ConfigDict(extra="forbid")`; expose only prompt-safe fields and avoid descriptor metadata. |
| `UnifiedToolManager` compatibility | adapter, request-response | `src/tools/manager.py:36-73`, `src/tools/catalog.py:253-299` | exact | Keep public methods working, but delegate new visibility/runtime/projection logic to `ToolPlatform`; do not add new policy there. |
| `src/agent/nodes/investigate.py` integration | graph node, event-driven/request-response | `src/agent/nodes/investigate.py:64-170`, `src/agent/nodes/investigate.py:223-241`, `src/agent/nodes/investigate.py:467-502` | exact | Replace descriptor allowlist/invoke/projection call points without rewriting the loop, stop reasons, or deterministic fallback. |
| Tool policy events | event writer, append-only | `src/replay/decision_events.py:26-115`, `src/replay/validators.py:8-54`, `src/db/models.py:1228-1249`, `src/db/migrations/versions/010_replay_event_v3.py:23-53` | exact | Use Phase 28 `emit_decision_event(...)`; register any new event types in validators, ORM constraint, migration, and contract tests. |
| Projection into prompt context | projector, transform | `src/agent/context/projectors.py:99-178`, `src/agent/context/assembler.py:32-117`, `src/agent/working_state.py:54-67` | role-match | Prompt path consumes `ToolResultPromptSummary`/safe refs, not `ToolResultV2.data` or normalized graph payload. |

## Implementation Seam Map

### Descriptor and ToolView

- `ToolDescriptor` is the declaration source in `src/tools/catalog.py:14-32`; descriptor-only fields include `risk_level`, `side_effect`, `required_permission`, `caller_allowlist`, `event_family`, `resource_type`, `executor`, `exposure`, and gate flags.
- Default descriptors live in `src/tools/catalog.py:139-229`; `create_coupon_grant_draft` is write, `caller_allowlist=["action_draft"]`, `exposure="node_only"`, and requires safety/idempotency at `src/tools/catalog.py:217-228`.
- Current planner discovery returns raw descriptors through `UnifiedToolManager.descriptors("investigate")` in `src/tools/manager.py:58-68`. Phase 29 should replace this planner surface with `ToolPlatform.visible_tools(...) -> list[ToolViewV1]`.
- `ToolViewV1` should copy the strict-model style from `src/tools/catalog.py:14-15` and `src/tools/contracts.py:13-14`, but expose only `name`, `description`, prompt-safe `input_schema`, `safe_usage_notes`, and `result_contract_version`.
- Schema projection should derive from descriptor schemas like `src/tools/catalog.py:41-100` but strip defaults, examples, executor/policy/resource metadata, adapter hints, and internal validation notes before prompt use.

### Runtime Authorization and Dispatch

- Current runtime gate order is concentrated in `UnifiedToolManager.invoke(...)`:
  - Descriptor lookup and not-found safe result: `src/tools/manager.py:73-76`.
  - Caller allowlist: `src/tools/manager.py:77-78`.
  - Side-effect gate: `src/tools/manager.py:79-84` plus `_side_effect_allowed(...)` in `src/tools/manager.py:162-167`.
  - Permission gate: `src/tools/manager.py:85-86`.
  - Input schema validation: `src/tools/manager.py:88-91`, backed by `src/tools/validation.py:8-47`.
  - Approval/safety/idempotency gates: `src/tools/manager.py:92-97`.
  - Executor availability: `src/tools/manager.py:99-101`.
  - Dispatch, exception mapping, output type/schema validation: `src/tools/manager.py:103-124`.
- Safe denial/error result shape should copy `src/tools/manager_results.py:8-29`, but Phase 29 should use policy-facing codes such as `missing_permission`, `schema_invalid`, `scope_denied`, `side_effect_blocked`, and `tool_unavailable` in `ToolPolicyDecision.reason_code`.
- Keep executors thin. Existing adapters only expose `has_tool(...)` and `execute(...)`: business `src/tools/executors/business.py:11-20`, knowledge `src/tools/executors/knowledge.py:17-90`, memory `src/tools/executors/memory.py:14-119`, action `src/tools/executors/action.py:13-97`.
- Explicit merchant-scope checks should use `MerchantScopeV1.allows(...)` in `src/platform/trusted_context.py:23-69`. `ToolCallContext.merchant_scope` is projected from trusted context in `src/platform/context_projections.py:86-122`; do not trust planner args or AgentState to widen it.
- Domain-lookup-dependent ids (`order_no`, `refund_case_no`, `ticket_id`) should be recorded as incomplete bindings / domain-scope-check-required in policy decisions, not treated as proven ownership in Phase 29.

### Investigate Integration

- Current graph construction point is `manager = ... UnifiedToolManager.with_defaults(session)` and `descriptors = manager.descriptors("investigate")` at `src/agent/nodes/investigate.py:64-70`.
- Current planner fallback depends on `.name` in `plan_next_step(...)` at `src/agent/nodes/investigate.py:34-61`. If `ToolViewV1` keeps `.name`, the fallback can remain structurally unchanged.
- Current planner validation uses `descriptor_names`, `manager.descriptor(...)`, module `ALLOWLIST`, and `descriptor.kind` in `src/agent/nodes/investigate.py:223-241`. Replace this with validation against returned `ToolViewV1` names plus runtime auth; do not reintroduce a second allowlist.
- Runtime invocation call point is `result = await manager.invoke(tool_name, args, tool_ctx)` at `src/agent/nodes/investigate.py:145`. Replace with `ToolPlatform.invoke(...)` while preserving the bounded loop, `max_attempts`, `deadline_at`, event lifecycle, and stop handling in `src/agent/nodes/investigate.py:90-177`.
- Existing tool lifecycle events are emitted in `_emit_tool_event(...)` at `src/agent/nodes/investigate.py:424-464`. Tool policy decision events are additional Phase 28 decision events and should not replace current `tool_call_*` / `rag_retrieval_*` lifecycle events unless the plan explicitly says so.

### Result Projection

- Existing contracts already separate storage and prompt summary surfaces in `src/tools/contracts.py:111-142`.
- Existing local graph projection is `_project_tool_result(...)` and `_safe_prompt_summary(...)` in `src/agent/nodes/investigate.py:369-421`; move this ownership into `ToolResultProjector`.
- Current graph accumulation writes prompt-safe projections to `context["tool_results"]` at `src/agent/nodes/investigate.py:474`, but also writes `context["facts"][ref.resource_type] = _without_raw_payload(result.data or {})` at `src/agent/nodes/investigate.py:482`. Phase 29 should replace that with projector-owned `normalized_result`; graph state must not read raw `ToolResultV2.data` directly.
- Current conversation storage sets `normalized_result_json = result.data or {}` at `src/conversation/service.py:222` and persists it at `src/conversation/service.py:252`. Phase 29 should route this through projector-normalized data and keep raw artifact refs optional.
- Prompt context already formats only safe tool summaries in `src/agent/context/projectors.py:148-178`, and `ContextAssembler` adds `tool_summaries` via `project_tool_result_summary(...)` in `src/agent/context/assembler.py:86-117`. Preserve that boundary: prompts should consume projector prompt fields, not normalized graph fields.
- Working-state prompt projection accepts only allowlisted tool result keys in `src/agent/working_state.py:54-67` and `WorkingToolResultRef` at `src/agent/working_state.py:90-103`; projector output should match those keys for prompt paths.

### Replay and Policy Event Emission

- `DecisionEventEnvelopeV1` is strict and envelope-only in `src/replay/decision_events.py:26-56`. `ToolPolicyDecision` must not include `event_id`, `sequence`, `occurred_at`, `run_id`, or `tenant_id`.
- `emit_decision_event(...)` resolves trusted/replay identity, normalizes payload, guards redacted payload/resource refs, persists through `ReplayService.append_event(...)`, and validates the envelope in `src/replay/decision_events.py:59-115`.
- Reason codes are normalized in `src/replay/decision_events.py:118-136`. Current regex only accepts snake_case (`src/replay/decision_events.py:20-23`, `src/replay/decision_events.py:132-133`), so Phase 29 must update this if namespaced extension codes like `business.permission_denied` are supported.
- Redaction guards reject unsafe keys such as `data`, `raw`, `arguments`, `prompt`, `raw_args`, `raw_payload`, `raw_tool_output`, `secret`, and `pii` in `src/replay/validators.py:56-80`, with recursive checks in `src/replay/validators.py:88-119`. Tool policy event payloads must avoid those keys.
- Use `ReplayContext` projection from `src/platform/context_projections.py:241-266` for identity/version propagation when available. Tests prove replay context identity wins over caller identity in `tests/replay/test_decision_events.py:177-214`.

## Tests To Mirror

| Behavior | Existing Test Pattern | Phase 29 Extension |
|---|---|---|
| Catalog is single source; action tool stays node-only | `tests/tools/test_catalog.py:32-76` | Add ToolView tests proving hidden/write/node-only descriptor fields do not appear in planner views. |
| JSON schema helper and declaration-only catalog fail closed | `tests/tools/test_catalog.py:86-122` | Add prompt-safe schema projection tests that keep construction essentials but strip defaults/examples/policy metadata. |
| Descriptor discovery and event family compatibility | `tests/agent/test_tools/test_unified_tool_manager.py:106-128` | Update manager tests to assert compatibility adapter delegates to `ToolPlatform` and does not own new policy logic. |
| Runtime gates deny before executor dispatch | `tests/agent/test_tools/test_unified_tool_manager.py:336-376`, `tests/agent/test_tools/test_unified_tool_manager.py:424-443` | Add `ToolRuntime`/`ToolPolicyDecision` matrix for caller, permission, side effect, schema, approval, safety, idempotency, merchant scope, and unavailable executor. |
| Output validation and generated errors are safe | `tests/agent/test_tools/test_unified_tool_manager.py:446-489` | Assert denied/invalid runtime calls emit decision events and return safe `ToolResultV2` with no raw args or descriptor internals. |
| Trusted tool context projection | `tests/platform/test_context_projections.py:37-70`, `tests/platform/test_context_projections.py:124-153` | Add policy/runtime tests proving permissions and merchant scope come from `ToolCallContext` projected from trusted context. |
| Investigate uses trusted event identity | `tests/agent/test_nodes/test_investigate.py:380-425` | Preserve lifecycle event identity after switching from manager to platform. |
| Unavailable tools are tracked and not retried | `tests/agent/test_nodes/test_investigate.py:453-470` | Ensure unavailable tools are absent from `visible_tools(...)` prompts and recorded as visibility decisions. |
| Tool result state is prompt-safe | `tests/agent/test_nodes/test_investigate.py:571-600` | Strengthen to assert graph/business context receives projector `normalized_result`, not filtered `ToolResultV2.data`. |
| Tool lifecycle event payloads stay redacted | `tests/agent/test_nodes/test_investigate.py:628-647` | Add separate tool policy event tests; lifecycle events should remain raw-argument-free. |
| Conversation prompt summaries exclude raw data | `tests/tools/test_tool_result_storage.py:70-135`, `tests/tools/test_tool_result_storage.py:138-187`, `tests/conversation/test_service.py:420-540` | Update storage assertions so `normalized_result_json` is projector-normalized and prompt summaries remain raw-free. |
| Prompt assembler excludes raw payloads | `tests/agent/context/test_assembler.py:105-166` | Mirror for new `ToolResultProjector.prompt_projection` and `text_for_prompt`. |
| Working state drops raw tool payloads | `tests/agent/test_working_state.py:88-184` | Ensure projector prompt output matches `WorkingToolResultRef` fields. |
| Decision envelope is strict | `tests/replay/test_decision_events.py:87-160` | Add tests that `ToolPolicyDecision` is not an event envelope and is emitted only through `emit_decision_event(...)`. |
| Decision event identity, reason, version, redaction | `tests/replay/test_decision_events.py:177-286`, `tests/replay/test_decision_events.py:390-485` | Add visibility/runtime policy event tests with low-payload `redacted_payload`, core reason codes, and no raw descriptor/schema/args. |
| Event writers share sequence allocation | `tests/replay/test_sequence_allocator.py:176-238` | Add policy decision writer to multi-writer sequence test if it uses new event types. |
| Event registry and DB migration stay aligned | `tests/replay/test_replay_migration_contract.py:98-101` | If new event types are added, update registry, ORM check, Alembic migration, and this test together. |
| Architecture boundaries | `tests/architecture/test_tool_boundaries.py:134-154` | Extend to require graph nodes use `ToolPlatform` facade and domain packages do not import platform runtime internals. |

## Anti-Patterns To Avoid

- Do not feed `ToolDescriptor` objects into planner prompts. `src/tools/manager.py:58-68` is the legacy raw-descriptor surface to replace.
- Do not preserve `ALLOWLIST = TOOL_CALL_TOOLS | RAG_RETRIEVAL_TOOLS` as planner authorization in `src/agent/nodes/investigate.py:10-24`; planner visibility should be descriptor-derived via `ToolPlatform.visible_tools(...)`.
- Do not treat a visible `ToolViewV1` as authorization. Runtime must create/enforce a fresh `ToolPolicyDecision(decision_stage="runtime_auth")` before executor dispatch.
- Do not add new runtime/policy branches to `UnifiedToolManager.invoke(...)`; move them to `ToolRuntime` / `ToolPolicyEngine` and keep manager as a compatibility adapter.
- Do not move planner visibility, runtime auth, event writing, or result projection into business/knowledge/memory/action executors. Existing executor pattern is thin dispatch only.
- Do not store or prompt with unprojected `ToolResultV2.data`. Current `src/conversation/service.py:222` and `src/agent/nodes/investigate.py:482` are replacement points, not patterns to keep.
- Do not emit raw args, full schemas, raw descriptors, adapter payloads, or permission internals in policy decision events; replay guards reject keys like `data`, `arguments`, `raw_payload`, and `raw_tool_output`.
- Do not create a parallel policy event envelope/table. Use `DecisionEventEnvelopeV1` / `emit_decision_event(...)` and existing `agent_trace_events`.
- Do not overclaim resource ownership for `order_no`, `refund_case_no`, or `ticket_id`; mark domain lookup requirements for Phase 30 instead.
- Do not introduce generic feature flags, retry/rate-limit framework, artifact store, external runtime, or MCP discovery in this phase.

## Migration/Event Pattern Notes

- If Phase 29 adds explicit event types such as `tool_policy_visibility_recorded` and `tool_policy_runtime_auth_recorded`, update all of:
  - `src/replay/validators.py:8-54` (`REPLAY_EVENT_TYPES` and `EVENT_RETENTION_CLASSIFICATION`).
  - `src/db/models.py:1238-1246` (`ck_agent_trace_events_event_type` ORM check).
  - A new Alembic migration under `src/db/migrations/versions/` modelled after `src/db/migrations/versions/010_replay_event_v3.py:23-53` and `src/db/migrations/versions/010_replay_event_v3.py:73-82`.
  - `tests/replay/test_replay_migration_contract.py:98-101` so migration check values equal the replay registry.
  - `tests/agent/test_events.py:205-235` if compatibility-level event type exposure is expected through `MINIMAL_EVENT_TYPES`.
- Current operation-id requirement only applies to prefixes in `src/replay/decision_events.py:22` via `_requires_operation_id(...)` at `src/replay/decision_events.py:139-140`. If tool policy event types should require `operation_id`, either choose an existing operation prefix or update this rule and tests.
- `emit_decision_event(...)` stores versions under `redacted_payload["versions"]`, not envelope top-level fields, as tested in `tests/replay/test_decision_events.py:390-415`.
- Current reason-code validation accepts arbitrary snake_case (`tests/replay/test_decision_events.py:288-305`). Phase 29 requires a stable core enum plus namespaced extension format; plan tests should tighten this for tool policy contract paths while preserving or intentionally migrating generic replay compatibility.
- Visibility decisions should be batched and low-payload: include tool names, stage, allowed/visible state, reason codes, policy version, data classification, availability summary, and safe refs only. Do not include schemas or descriptor internals.
- Runtime-auth decisions should be emitted per invocation attempt, including denied attempts, before returning safe `ToolResultV2` errors.

## Suggested File/Test Classification

| File | Role | Data Flow | Closest Analog |
|---|---|---|---|
| `src/tools/platform.py` | facade | request-response | `src/tools/manager.py` |
| `src/tools/policy.py` | service/model | request-response | `src/tools/manager.py`, `src/replay/decision_events.py` |
| `src/tools/runtime.py` | service | request-response | `src/tools/manager.py` |
| `src/tools/projection.py` | projector | transform | `src/agent/nodes/investigate.py`, `src/conversation/service.py`, `src/agent/context/projectors.py` |
| `src/tools/contracts.py` | model | transform/request-response | existing strict Pydantic contracts in the same file |
| `src/tools/manager.py` | compatibility adapter | request-response | existing manager; delegate to platform |
| `src/agent/nodes/investigate.py` | graph node | event-driven/request-response | existing investigate loop |
| `src/replay/validators.py` | config/registry | event-driven | existing replay registry |
| `src/db/models.py` + new migration | model/migration | event-driven persistence | `010_replay_event_v3.py` |
| `tests/tools/test_tool_platform.py` | test | request-response/transform | catalog + manager + projection tests above |
| `tests/replay/test_tool_policy_events.py` | test | event-driven | `tests/replay/test_decision_events.py` |
| `tests/architecture/test_tool_platform_boundaries.py` or extension | test | static | `tests/architecture/test_tool_boundaries.py` |

