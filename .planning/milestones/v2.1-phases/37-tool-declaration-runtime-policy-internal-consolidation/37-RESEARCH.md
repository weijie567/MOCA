# Phase 37: Tool Declaration + Runtime/Policy Internal Consolidation - Research

**Researched:** 2026-07-01
**Domain:** Internal tool platform declaration registry, runtime failure consolidation, and policy authorization gates
**Confidence:** HIGH

## Scope Summary

Phase 37 is the first v2.1 tool-platform hardening phase and must consolidate tool declarations plus internal runtime/policy structure without changing external contract shapes. [VERIFIED: .planning/ROADMAP.md:19-28] [VERIFIED: .planning/REQUIREMENTS.md:17-21]

The phase directly covers TPH-03 and TPH-04: TPH-03 requires a single-source tool registry or drift-checked derived lists, and TPH-04 requires a shared `ToolRuntime` failure helper plus declarative `ToolPolicyEngine.runtime_auth` gate sequence. [VERIFIED: .planning/REQUIREMENTS.md:17-21]

Primary recommendation: split planning into three small executable plans: registry/declaration consolidation, runtime `_fail` helper consolidation, and declarative policy-gate refactor with final validation. [VERIFIED: AGENTS.md:37-43] [VERIFIED: .planning/ROADMAP.md:23-27]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Single-source tool declarations | API / Backend | Graph-facing tool facade | `ToolCatalog` is the normative tool declaration source, `ToolPlatform` is graph-facing dispatch, and `UnifiedToolManager` is only a compatibility adapter. [CITED: docs/contract-spec.md:1312-1314] |
| Runtime failure result/projection/event tuple | API / Backend | Observability / Replay | `ToolRuntime.invoke` returns `(ToolResultV2, ToolPolicyDecision, event_id, ToolResultProjectionV1)` and emits runtime auth decision events when a session is available. [VERIFIED: src/tools/runtime.py:60-90] [VERIFIED: src/tools/runtime.py:274-315] |
| Runtime authorization checks | API / Backend | Database / Storage for decision-event persistence | `ToolPolicyEngine.runtime_auth` owns caller, permission, side-effect, resource scope, approval, safety snapshot, idempotency, and availability decisions before executor dispatch. [VERIFIED: src/tools/policy.py:280-366] |
| Prompt-safe planner visibility | API / Backend | Browser / Client is not involved | `ToolPlatform.visible_tools` returns `ToolViewV1` entries and stores full visibility decisions outside the prompt-facing list. [VERIFIED: src/tools/platform.py:84-110] |

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TPH-03 | Tool declarations resolve from a single-source registry; `_IDENTIFIER_SCHEMAS` and `INVESTIGATE_TOOL_NAMES` are derived from or checked against it. [VERIFIED: .planning/REQUIREMENTS.md:17] | Current drift points are `_IDENTIFIER_SCHEMAS` in `catalog.py` and `INVESTIGATE_TOOL_NAMES` in `manager.py`; both have narrow references and can be consolidated or drift-tested. [VERIFIED: src/tools/catalog.py:41-110] [VERIFIED: src/tools/catalog.py:132-133] [VERIFIED: src/tools/manager.py:17-26] [VERIFIED: src/tools/manager.py:70-79] |
| TPH-04 | `ToolRuntime` failure paths use one helper, and `runtime_auth` uses declarative gates with existing tests green and no external contract shape change. [VERIFIED: .planning/REQUIREMENTS.md:21] | Current `ToolRuntime.invoke` has seven explicit failure return blocks that repeat result creation, projection, event emission, and tuple return; current `runtime_auth` is an ordered if-chain. [VERIFIED: src/tools/runtime.py:73-198] [VERIFIED: src/tools/policy.py:293-343] |

</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md)

- `docs/contract-spec.md` is the normative contract source, but spec changes are not part of Phase 37; any implementation/spec mismatch must be recorded rather than silently treated as solved. [VERIFIED: CLAUDE.md] [VERIFIED: AGENTS.md:101-109]
- Phase-level planning must be split when a phase spans multiple service boundaries, ownership domains, waves, or verification gates. [VERIFIED: AGENTS.md:37-43]
- MOCA validation commands must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `.venv/bin/pytest ...`, or `.venv/bin/python -m pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in this repo. [VERIFIED: AGENTS.md:18-20]
- If local debugging or validation uncovers an error, environment issue, unexpected response, or failed verification, the incident must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese after handling. [VERIFIED: AGENTS.md:10-13] [VERIFIED: CLAUDE.md]
- Plan/code review for phase-level work follows the GSD tool plus independent Codex cross-review workflow. [VERIFIED: AGENTS.md:27-35] [VERIFIED: CLAUDE.md]

## Current Code Findings with file/function evidence

### Tool Declaration Registry

| Finding | Evidence | Planning Guidance |
|---------|----------|-------------------|
| `ToolDescriptor` already includes implementation-only fields such as `executor`, `exposure`, `requires_approval`, `requires_safety_snapshot`, and `requires_idempotency_key`. [VERIFIED: src/tools/catalog.py:14-32] | The roadmap says Phase 37 must not change external contract shapes; Phase 39 owns spec reconciliation for these implemented fields. [VERIFIED: .planning/ROADMAP.md:43-51] | Keep descriptor field names and model shape stable; do not edit `docs/contract-spec.md` in Phase 37. |
| `_IDENTIFIER_SCHEMAS` is a separate module-level map for nine tools: eight read/retrieval investigate tools plus `create_coupon_grant_draft`. [VERIFIED: src/tools/catalog.py:41-110] | `_descriptor(...)` pulls `input_schema` from `_IDENTIFIER_SCHEMAS[name]` and sets `output_schema` to `_GENERIC_OBJECT_SCHEMA`. [VERIFIED: src/tools/catalog.py:127-145] | Move each input schema into the same registry row as the rest of the descriptor, or derive/check `_IDENTIFIER_SCHEMAS` from registry rows. Keep generic `output_schema` unchanged in Phase 37 because real output schemas belong to Phase 38. [VERIFIED: .planning/ROADMAP.md:31-39] |
| `_default_descriptors()` is the actual catalog declaration list used when `ToolCatalog()` is constructed. [VERIFIED: src/tools/catalog.py:148-244] | `ToolCatalog.descriptors()` and `ToolCatalog.descriptor(name)` expose descriptors from `self._tools`. [VERIFIED: src/tools/catalog.py:241-260] | Make the registry row/table feed `_default_descriptors()` or replace `_default_descriptors()` with registry-derived descriptors. |
| `manager.INVESTIGATE_TOOL_NAMES` duplicates the eight investigate tool names. [VERIFIED: src/tools/manager.py:17-26] | `UnifiedToolManager.descriptors("investigate")` filters on `descriptor.name in INVESTIGATE_TOOL_NAMES` in addition to `caller_allowlist`, `kind`, and `exposure`. [VERIFIED: src/tools/manager.py:70-79] | Prefer deriving `INVESTIGATE_TOOL_NAMES` from catalog descriptors where `caller_allowlist` contains `investigate`, `kind != "write"`, and `exposure == "planner_visible"`; if the public constant is retained for compatibility, add a drift check against catalog-derived names. |
| `UnifiedToolManager` delegates `invoke(...)` to `ToolPlatform.invoke(...)` and returns `outcome.tool_result` for legacy compatibility. [VERIFIED: src/tools/manager.py:95-98] | The spec allows `UnifiedToolManager` to remain a legacy compatibility adapter but forbids new policy/runtime ownership there. [CITED: docs/contract-spec.md:1386-1389] | Do not move runtime or policy logic into manager while removing duplicated name lists. |
| `search_sop` is declared but unavailable in current default execution because `KnowledgeToolExecutor.has_tool` returns true only for `search_policy`. [VERIFIED: src/tools/catalog.py:204-212] [VERIFIED: src/tools/executors/knowledge.py:27-38] | Existing tests expect declared future `search_sop` to return `unavailable`. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:281-290] | Preserve declared-but-unavailable behavior while deriving registry names. |

### ToolRuntime Failure Branches

`ToolRuntime.invoke` currently returns a tuple of `ToolResultV2`, `ToolPolicyDecision`, optional event id, and `ToolResultProjectionV1`. [VERIFIED: src/tools/runtime.py:60-71]

| Failure Path | Current Branch | Duplicated Work |
|--------------|----------------|-----------------|
| Descriptor missing | Calls `runtime_auth`, creates `not_found` result, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:73-90] | Result creation, projection, event emission, tuple assembly. |
| Input schema validation failure | Builds denied decision, creates `invalid_request`, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:92-112] | Result creation, projection, event emission, tuple assembly. |
| Runtime policy denial | Maps denial to safe result, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:122-131] | Projection, event emission, tuple assembly. |
| Executor unavailable | Builds denied decision with availability metadata, creates `unavailable`, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:133-153] | Result creation, projection, event emission, tuple assembly. |
| Executor exception | Creates `error`, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:155-168] | Result creation, projection, event emission, tuple assembly. |
| Executor returns non-`ToolResultV2` | Creates `invalid_response`, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:170-181] | Result creation, projection, event emission, tuple assembly. |
| Output schema validation failure | Creates `invalid_response`, projects, emits event, returns tuple. [VERIFIED: src/tools/runtime.py:183-198] | Result creation, projection, event emission, tuple assembly. |

The roadmap says "ten duplicated branches," but the current source audit found seven explicit `return error_result, decision, event_id, projection` failure branches in `ToolRuntime.invoke`; planning should target all failure exits, not hard-code the numeric wording. [VERIFIED: .planning/ROADMAP.md:25] [VERIFIED: src/tools/runtime.py:73-198]

Recommended helper shape: add a private async `_fail(...)` on `ToolRuntime` that accepts `tool_name`, `ctx`, `decision`, `session`, and either a prebuilt `ToolResultV2` or `status/summary/code/source`, then performs projection, `_emit_decision_event`, and tuple assembly in one place. [VERIFIED: src/tools/runtime.py:80-90] [VERIFIED: src/tools/runtime.py:102-112] [VERIFIED: src/tools/runtime.py:143-153]

Keep input schema validation before `runtime_auth`; current code explicitly avoids sending unvalidated args into resource scope binding or decision event resource refs. [VERIFIED: src/tools/runtime.py:25-31] [VERIFIED: src/tools/runtime.py:92-115]

### ToolPolicyEngine Runtime Auth Gates

| Current Check | Evidence | Required Preservation |
|---------------|----------|-----------------------|
| Descriptor missing is an immediate denial with `tool_unavailable`, empty required scopes, `runtime_available=False`, and not-registered summary. [VERIFIED: src/tools/policy.py:293-301] | This path has no descriptor, so it cannot be a normal descriptor-bound gate. [VERIFIED: src/tools/policy.py:291-301] | Keep as a preflight gate or a special descriptorless gate. |
| Availability false is an immediate denial with required permission, `runtime_available=False`, and unavailable summary. [VERIFIED: src/tools/policy.py:303-312] | Availability comes from `ToolRuntime._build_availability_map()`. [VERIFIED: src/tools/runtime.py:212-223] | Keep before normal reason accumulation, or preserve the same decision fields if folded into a gate. |
| Caller allowlist appends `caller_not_allowed`. [VERIFIED: src/tools/policy.py:316-318] | `caller_allowlist` lives on the descriptor. [VERIFIED: src/tools/catalog.py:25] | Gate sequence must preserve reason code and order. |
| Missing permission appends `missing_permission`. [VERIFIED: src/tools/policy.py:320-322] | Required permission is `tool:{name}` in `_descriptor(...)`. [VERIFIED: src/tools/catalog.py:136] | Gate sequence must preserve reason code and required scopes. |
| Write side effects outside the `action_draft` write path append `side_effect_blocked`. [VERIFIED: src/tools/policy.py:324-328] | `create_coupon_grant_draft` is `kind="write"`, `side_effect="write"`, `caller_allowlist=["action_draft"]`, and `exposure="node_only"`. [VERIFIED: src/tools/catalog.py:226-237] | Do not allow `investigate` to execute write tools. |
| Resource binding marks explicit out-of-scope `merchant_id` with `_scope_denied` and marks order/refund/ticket identifiers as requiring domain-scope proof. [VERIFIED: src/tools/policy.py:330-333] [VERIFIED: src/tools/policy.py:394-437] | Business domain no-leak enforcement already lives in `BusinessFactService`, not in this phase. [VERIFIED: .planning/STATE.md:51-52] [VERIFIED: src/business/service.py:68-87] | Do not rebuild domain ownership checks inside `ToolPolicyEngine`. |
| Missing approval, safety snapshot, or idempotency fields append `approval_required`, `safety_snapshot_required`, or `idempotency_required`. [VERIFIED: src/tools/policy.py:335-341] | Current write tool requires safety snapshot and idempotency key. [VERIFIED: src/tools/catalog.py:234-237] | Declarative gates must not add new gate semantics beyond the existing checks. |
| Any accumulated reason codes return one denied `ToolPolicyDecision`; otherwise an allowed decision returns reason `visible`, matched scope, resource binding, and availability metadata. [VERIFIED: src/tools/policy.py:343-366] | `ToolPolicyDecision` validates reason codes and forbids runtime-only reason codes in visibility decisions. [VERIFIED: src/tools/contracts.py:161-205] | Gate refactor must keep reason codes inside `TOOL_POLICY_CORE_REASON_CODES` or namespaced extension format. |

Recommended policy structure: define an ordered private gate sequence, for example immutable `RuntimeAuthGate` entries with `name`, `reason_code`, and `check(descriptor, args, ctx, resource_scope_binding) -> bool`; keep descriptor lookup and availability as preflight gates, build `resource_scope_binding` once before the scope gate, and aggregate reason codes in the current order. [VERIFIED: src/tools/policy.py:293-366]

### External Contract Shape and Consumers

`ToolCallContext`, `ToolResultV2`, `ToolViewV1`, `ToolPolicyDecision`, and `ToolInvocationOutcome` all use Pydantic `extra="forbid"`, so adding/removing/renaming fields is externally visible and test-breaking. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/contracts.py:71-97] [VERIFIED: src/tools/contracts.py:145-231]

`ToolCallContext` identity fields are projections of `TrustedContext` and must not be redefined, widened, or renamed. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:149-159] [VERIFIED: .planning/STATE.md:49-52]

`project_to_tool_context(...)` is the existing helper that constructs `ToolCallContext` from `TrustedContext`, including tool-call-local fields such as `request_id`, `tool_call_id`, `caller_node`, deadline, attempt, idempotency, approval, and safety refs. [VERIFIED: src/platform/context_projections.py:86-122]

`investigate` consumes `ToolPlatform.visible_tools`, `ToolPlatform.invoke`, `ToolInvocationOutcome.projection`, and `ToolResultV2` without needing contract-shape changes. [VERIFIED: src/agent/nodes/investigate.py:98-194]

`action_draft` invokes the action tool through `ToolPlatform.invoke` and consumes only `outcome.tool_result`. [VERIFIED: src/agent/nodes/action_draft.py:579-595]

Decision-event payloads for tool policy events are explicitly low-payload and reject raw args, raw output, input schema, required permission, and caller allowlist. [VERIFIED: tests/replay/test_tool_policy_events.py:29-40] [VERIFIED: tests/replay/test_tool_policy_events.py:130-197]

## Contract Constraints / Non-goals

- Do not add, remove, or rename fields on `ToolResultV2`, `ToolCallContext`, `ToolPolicyDecision`, `ToolViewV1`, or `ToolInvocationOutcome`. [VERIFIED: .planning/ROADMAP.md:23-27] [VERIFIED: src/tools/contracts.py:13-231]
- Do not redefine, widen, or rename `ToolCallContext` identity fields from section 8.0: `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, or `trace_id`. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:149-159]
- Do not implement real per-tool output schemas or output-validation semantics beyond preserving the current generic object schema path; Phase 38 owns real `output_schema` declaration and enforcement hardening. [VERIFIED: .planning/ROADMAP.md:31-39] [VERIFIED: src/tools/catalog.py:41] [VERIFIED: src/tools/catalog.py:133]
- Do not edit `docs/contract-spec.md` in Phase 37; Phase 39 owns section 12.5/12.6 reconciliation. [VERIFIED: .planning/ROADMAP.md:43-51]
- Do not add new tools, new executors, new policy gates, rate limits, or cost-budget gates. [VERIFIED: .planning/REQUIREMENTS.md:27-35]
- Do not rebuild domain ownership or merchant-scope enforcement in tool policy; BusinessFactService already owns domain no-leak checks. [VERIFIED: .planning/STATE.md:51-52] [VERIFIED: src/business/service.py:68-87] [VERIFIED: src/business/service.py:480-493]

## Recommended Plan Decomposition

### 37-01 Registry Single Source and Drift Guard

Objective: make the catalog registry the only place a tool's descriptor-level declaration is edited, while preserving the public behavior of `ToolCatalog`, `ToolPlatform`, and `UnifiedToolManager`. [VERIFIED: src/tools/catalog.py:148-260] [VERIFIED: src/tools/manager.py:35-98]

Implementation guidance:

- Introduce a single internal registry row/table in `src/tools/catalog.py` that holds name, description, kind, input schema, output schema, side effect, caller allowlist, event family, resource type, executor, exposure, and required runtime fields. [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/catalog.py:41-110]
- Derive `ToolDescriptor` instances from that registry; keep default `output_schema` as `{"type": "object"}` until Phase 38. [VERIFIED: src/tools/catalog.py:41] [VERIFIED: .planning/ROADMAP.md:31-39]
- Derive `INVESTIGATE_TOOL_NAMES` from catalog descriptors or add a drift check that fails when the manager list and catalog-derived investigate set diverge. [VERIFIED: src/tools/manager.py:17-26] [VERIFIED: src/tools/manager.py:70-79]
- Preserve declared-but-unavailable `search_sop` behavior. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:281-290]

Acceptance focus:

- Add/extend tests in `tests/tools/test_catalog.py` proving registry-derived input schemas and investigate names are consistent. [VERIFIED: tests/tools/test_catalog.py:32-53]
- Add/extend tests in `tests/agent/test_tools/test_unified_tool_manager.py` proving `UnifiedToolManager.descriptors("investigate")` matches catalog-derived planner-visible read/retrieval descriptors without a second hand-maintained name list. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:107-123]

### 37-02 Runtime Failure Helper

Objective: consolidate every `ToolRuntime.invoke` failure exit through one helper that creates or accepts the error result, projects it, emits the decision event, and returns the outcome tuple. [VERIFIED: src/tools/runtime.py:73-198]

Implementation guidance:

- Add a private async `_fail(...)` helper near `_safe_denial_result` / `_emit_decision_event` in `src/tools/runtime.py`. [VERIFIED: src/tools/runtime.py:225-315]
- Refactor descriptor missing, schema invalid, policy denied, executor unavailable, executor exception, malformed executor return, and output-schema invalid branches to call `_fail(...)`. [VERIFIED: src/tools/runtime.py:73-198]
- Keep `safe_result(...)` for safe `ToolResultV2` construction unless the helper wraps it directly. [VERIFIED: src/tools/manager_results.py:8-29]
- Keep the successful path unchanged: project successful results, emit the runtime auth decision event, and return the same tuple shape. [VERIFIED: src/tools/runtime.py:200-210]

Acceptance focus:

- Existing behavior tests for unknown tool, invalid input, missing permission, malformed executor return, and output schema failure must remain green. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:364-529]
- Add one structural or targeted unit test proving failure branches route through `_fail(...)`; this is appropriate because TPH-04 is an internal-consolidation requirement, not only a black-box behavior requirement. [VERIFIED: .planning/REQUIREMENTS.md:21]

### 37-03 Declarative Runtime Auth Gates and Final Validation

Objective: express `ToolPolicyEngine.runtime_auth` checks as an ordered declarative sequence while preserving current `ToolPolicyDecision` contents and denial ordering. [VERIFIED: src/tools/policy.py:280-366]

Implementation guidance:

- Keep descriptor lookup and availability as preflight decisions or as special gates that preserve their current immediate-denial outputs. [VERIFIED: src/tools/policy.py:293-312]
- Build `resource_scope_binding` once and use a scope gate to append `scope_denied` when `_scope_denied` is present. [VERIFIED: src/tools/policy.py:330-333] [VERIFIED: src/tools/policy.py:394-437]
- Use an ordered gate list for caller allowlist, permission, write side-effect, explicit merchant scope, approval, safety snapshot, and idempotency checks. [VERIFIED: src/tools/policy.py:316-341]
- Keep allowed decisions as reason `visible`, matched scope equal to required permission, and `runtime_available=True`. [VERIFIED: src/tools/policy.py:353-366]

Acceptance focus:

- Existing runtime auth tests for missing permission, scope denial, legacy list merchant scope, and action idempotency must remain green. [VERIFIED: tests/tools/test_tool_platform.py:385-449] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:392-417] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:465-484]
- Add a focused test that inspects or exercises the gate sequence so a future hardcoded if-chain regression fails. [VERIFIED: .planning/REQUIREMENTS.md:21]

## Standard Stack / Existing Infrastructure

| Component | Current Version / Shape | Use in Phase 37 |
|-----------|-------------------------|-----------------|
| Python | Project requires Python `>=3.12`; local `uv run python --version` returned Python 3.12.13. [VERIFIED: pyproject.toml:5] [VERIFIED: local command `uv run python --version`] | Use current Python features already present in repo; do not introduce compatibility shims for older Python. |
| Pydantic | Tool contracts and descriptors use `BaseModel` with `ConfigDict(extra="forbid")`. [VERIFIED: src/tools/catalog.py:9-15] [VERIFIED: src/tools/contracts.py:8-14] | Preserve exact external models; use Pydantic validation rather than ad hoc dict envelopes. |
| JSON schema subset validator | `validate_json_value(...)` validates the current descriptor schema subset. [VERIFIED: src/tools/validation.py:8-47] | Reuse existing validation helper; do not add a new schema library for Phase 37. |
| pytest / pytest-asyncio | Dev dependencies require pytest `>=8.0` and pytest-asyncio `>=0.23`; local `uv run pytest --version` returned pytest 9.0.3. [VERIFIED: pyproject.toml:34-40] [VERIFIED: local command `uv run pytest --version`] | Use `uv run pytest ...` for all verification commands. |
| Ruff | Dev dependency requires ruff `>=0.5`; local `uv run ruff --version` returned ruff 0.15.12. [VERIFIED: pyproject.toml:34-40] [VERIFIED: local command `uv run ruff --version`] | Use `uv run ruff check ...` if the implementation changes style-sensitive Python files. |

## Architecture Patterns

### Current Data Flow

```text
Tool caller (investigate/action_draft)
  -> ToolPlatform.visible_tools or ToolPlatform.invoke
  -> ToolCatalog descriptor lookup
  -> ToolRuntime input validation
  -> ToolPolicyEngine.runtime_auth
  -> executor dispatch by descriptor.executor
  -> output validation
  -> ToolResultProjector projection
  -> optional tool_policy_runtime_auth_recorded decision event
  -> ToolInvocationOutcome / legacy ToolResultV2
```

This data flow is implemented by `ToolPlatform`, `ToolRuntime`, `ToolPolicyEngine`, executor classes, and `ToolResultProjector`. [VERIFIED: src/tools/platform.py:36-133] [VERIFIED: src/tools/runtime.py:60-210] [VERIFIED: src/tools/policy.py:280-366] [VERIFIED: src/tools/projection.py]

### Recommended Project Structure

```text
src/tools/
  catalog.py          # single-source registry rows and descriptor derivation
  manager.py          # compatibility adapter; no new runtime/policy ownership
  runtime.py          # shared _fail helper and runtime invocation chain
  policy.py           # declarative runtime auth gate sequence
  contracts.py        # external contract models; no shape changes in Phase 37
tests/tools/
  test_catalog.py     # registry and drift checks
  test_tool_platform.py # runtime/policy behavior and structural consolidation tests
tests/agent/test_tools/
  test_unified_tool_manager.py # legacy compatibility behavior
tests/replay/
  test_tool_policy_events.py # decision-event payload safety
```

The listed files are the current tool platform and test locations relevant to Phase 37. [VERIFIED: `rg --files src/tools tests/tools tests/agent/test_tools tests/replay`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| External tool result envelopes | New dict-shaped result objects or alternate dataclasses | Existing `ToolResultV2` and `safe_result(...)` | `ToolResultV2` is the external result contract and uses `extra="forbid"`. [VERIFIED: src/tools/contracts.py:71-97] [VERIFIED: src/tools/manager_results.py:8-29] |
| Service context construction | Direct `ToolCallContext(...)` construction in production seams | `project_to_tool_context(...)` | Architecture tests already forbid direct service-context construction at current seams. [VERIFIED: src/platform/context_projections.py:86-122] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] |
| Runtime auth events | Custom replay/event payloads in policy code | Existing `_emit_decision_event(...)` path and `emit_decision_event(...)` validators | Tool policy event tests enforce low-payload, redacted event content. [VERIFIED: src/tools/runtime.py:274-315] [VERIFIED: tests/replay/test_tool_policy_events.py:130-197] |
| JSON validation library changes | New dependency for Phase 37 | Existing `validate_json_value(...)` | Phase 37 is declaration/internal consolidation; output-schema enforcement hardening belongs to Phase 38. [VERIFIED: src/tools/validation.py:8-47] [VERIFIED: .planning/ROADMAP.md:31-39] |

## Test and Verification Strategy

### Focused Tests to Extend

| Area | Existing Closest Tests | Needed Extension |
|------|------------------------|------------------|
| Registry no-drift | `tests/tools/test_catalog.py::test_descriptor_table_is_single_source_for_investigate_names_and_resource_types` verifies the catalog-derived investigate set and resource types. [VERIFIED: tests/tools/test_catalog.py:32-53] | Add a drift test that fails if registry rows, derived descriptors, `_IDENTIFIER_SCHEMAS` compatibility surface, or `INVESTIGATE_TOOL_NAMES` compatibility surface diverge. [VERIFIED: .planning/REQUIREMENTS.md:17] |
| Manager compatibility | `tests/agent/test_tools/test_unified_tool_manager.py::test_descriptor_discovery_returns_investigate_allowlist_only` and `test_descriptor_discovery_uses_business_registry_catalog` verify investigate descriptor behavior. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:107-123] | Update tests so the expected manager set is compared to catalog-derived planner-visible investigate descriptors, not a second hand-edited list. [VERIFIED: src/tools/manager.py:70-79] |
| Runtime failure helper | Unknown tool, invalid input, missing permission, malformed executor return, output-schema failure, and secret-free errors are already covered. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:364-529] | Add a structural test or helper-level unit test proving failures call `_fail(...)` and still return safe result/projection/event tuple shape. [VERIFIED: .planning/REQUIREMENTS.md:21] |
| Policy declarative gates | `test_runtime_auth_rechecks_visible_tool_before_dispatch`, `test_runtime_auth_handles_legacy_list_merchant_scope`, and action idempotency tests cover existing behavior. [VERIFIED: tests/tools/test_tool_platform.py:385-449] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:392-417] | Add a focused test that the ordered gate sequence exists and produces current reason-code order for multi-denial cases. [VERIFIED: src/tools/policy.py:316-343] |
| Event payload safety | `tests/replay/test_tool_policy_events.py` registers and validates tool policy decision event payloads. [VERIFIED: tests/replay/test_tool_policy_events.py:80-197] | Re-run after runtime helper refactor because `_fail(...)` still emits runtime auth decision events. [VERIFIED: src/tools/runtime.py:274-315] |
| Trusted context boundary | `tests/architecture/test_trusted_context_boundaries.py` enforces projection helpers at current seams. [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] | Re-run if implementation touches context construction or imports. [VERIFIED: src/platform/context_projections.py:86-122] |

### Recommended Commands

```bash
uv run pytest tests/tools/test_catalog.py -q
uv run pytest tests/tools/test_tool_platform.py -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py -q
uv run pytest tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q
uv run ruff check src/tools tests/tools tests/agent/test_tools tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py
```

All recommended commands use `uv run` because project rules reject bare `pytest` and bare `python -m pytest`. [VERIFIED: AGENTS.md:18-20]

## Validation Architecture

Nyquist validation is enabled in `.planning/config.json`, so this phase should include automated validation coverage in Wave 0 and final gates. [VERIFIED: .planning/config.json:19]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio; local pytest version is 9.0.3. [VERIFIED: pyproject.toml:34-40] [VERIFIED: local command `uv run pytest --version`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"`. [VERIFIED: pyproject.toml:54-55] |
| Quick run command | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` [VERIFIED: AGENTS.md:18-20] |
| Full relevant suite command | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q` [VERIFIED: AGENTS.md:18-20] |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TPH-03 | Registry-derived descriptor declarations and no drift between catalog schemas and manager investigate names. [VERIFIED: .planning/REQUIREMENTS.md:17] | Unit / structural | `uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py -q` | Yes. [VERIFIED: tests/tools/test_catalog.py] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py] |
| TPH-04 | Runtime failures route through shared `_fail` helper while preserving safe result/projection/event tuple behavior. [VERIFIED: .planning/REQUIREMENTS.md:21] | Unit / behavior / structural | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` | Yes. [VERIFIED: tests/tools/test_tool_platform.py] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py] |
| TPH-04 | `runtime_auth` declarative gate sequence preserves existing denial decisions and reason codes. [VERIFIED: .planning/REQUIREMENTS.md:21] | Unit / behavior / structural | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` | Yes. [VERIFIED: tests/tools/test_tool_platform.py] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py] |
| TPH-04 | Tool policy decision events remain redacted and low payload after runtime refactor. [VERIFIED: src/tools/runtime.py:274-315] | Integration | `uv run pytest tests/replay/test_tool_policy_events.py -q` | Yes. [VERIFIED: tests/replay/test_tool_policy_events.py] |

### Sampling Rate

- Per task commit: run the narrow command for the touched area, such as `uv run pytest tests/tools/test_catalog.py -q` for registry work. [VERIFIED: AGENTS.md:18-20]
- Per wave merge: run the full relevant suite command above. [VERIFIED: .planning/config.json:19]
- Phase gate: run the full relevant suite plus `uv run ruff check ...` before `/gsd-verify-work`. [VERIFIED: pyproject.toml:50-55]

### Wave 0 Gaps

- Add or update `tests/tools/test_catalog.py` for registry/schema/name drift. [VERIFIED: tests/tools/test_catalog.py:32-53]
- Add or update `tests/tools/test_tool_platform.py` for `_fail(...)` structural coverage and declarative gate sequence coverage. [VERIFIED: tests/tools/test_tool_platform.py:385-449]
- Add or update `tests/agent/test_tools/test_unified_tool_manager.py` only if manager compatibility assertions need to stop mirroring a hardcoded expected set. [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:28-37] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py:107-123]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None expected; Phase 37 does not rename persisted event types, tool result schema versions, run IDs, tenant IDs, or database columns. [VERIFIED: .planning/ROADMAP.md:23-27] [VERIFIED: src/tools/contracts.py:13-231] | No data migration. |
| Live service config | None found in repo scope; the phase changes internal Python declaration/runtime/policy code and no external service configuration files were identified in the requested code areas. [VERIFIED: user-provided likely code areas] [VERIFIED: `rg --files src/tools tests/tools tests/agent/test_tools tests/replay`] | No API patch or manual service config update. |
| OS-registered state | None; no launchd/systemd/pm2/task-scheduler registration is part of the Phase 37 scope. [VERIFIED: .planning/ROADMAP.md:19-28] | None. |
| Secrets/env vars | None; no secret or environment variable names are being renamed by this phase. [VERIFIED: .planning/REQUIREMENTS.md:17-21] | None. |
| Build artifacts / installed packages | None; no package name, CLI entry point, or dependency version change is part of Phase 37. [VERIFIED: pyproject.toml:1-55] [VERIFIED: .planning/ROADMAP.md:19-28] | No reinstall expected beyond normal test environment use. |

## Security Domain

Security enforcement is enabled by default because `.planning/config.json` does not set `security_enforcement: false`. [VERIFIED: .planning/config.json]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No direct auth implementation in Phase 37. [VERIFIED: .planning/ROADMAP.md:19-28] | Preserve trusted `ToolCallContext` projection fields; do not create auth identities. [CITED: docs/contract-spec.md:37-39] |
| V3 Session Management | No direct session-management implementation in Phase 37. [VERIFIED: .planning/ROADMAP.md:19-28] | Preserve `session_id`, `thread_id`, and `run_id` projection behavior. [VERIFIED: src/platform/context_projections.py:86-122] |
| V4 Access Control | Yes. [VERIFIED: src/tools/policy.py:280-366] | Preserve caller allowlist, required permission, side-effect, merchant-scope, approval, safety snapshot, and idempotency gates. [VERIFIED: src/tools/policy.py:316-341] |
| V5 Input Validation | Yes. [VERIFIED: src/tools/runtime.py:92-115] | Keep descriptor input schema validation before runtime auth; keep output validation branch behavior unchanged until Phase 38. [VERIFIED: src/tools/runtime.py:92-198] |
| V6 Cryptography | No cryptography implementation in Phase 37. [VERIFIED: .planning/ROADMAP.md:19-28] | Do not introduce custom cryptographic logic. |

### Known Threat Patterns for Tool Platform

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Planner-visible tool treated as runtime authorization | Elevation of privilege | `ToolPlatform.invoke` must rerun `runtime_auth` before dispatch. [CITED: docs/contract-spec.md:1388-1389] [VERIFIED: tests/tools/test_tool_platform.py:385-401] |
| Unvalidated args included in resource binding or decision events | Tampering / Information disclosure | Keep input schema validation before `runtime_auth`. [VERIFIED: src/tools/runtime.py:92-115] |
| Merchant scope widened by explicit `merchant_id` args | Elevation of privilege / Information disclosure | `_build_resource_binding` checks explicit `merchant_id` against trusted `ctx.merchant_scope`. [VERIFIED: src/tools/policy.py:409-435] |
| Raw tool payload leaks into prompts or replay events | Information disclosure | Use `ToolResultProjector` and existing event redaction validators. [VERIFIED: tests/tools/test_tool_platform.py:560-690] [VERIFIED: tests/replay/test_tool_policy_events.py:29-40] |
| Write tool execution through investigate loop | Elevation of privilege | Preserve side-effect/write gates and node-only descriptor exposure. [VERIFIED: src/tools/policy.py:324-328] [VERIFIED: src/tools/catalog.py:226-237] |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Approved MOCA command runner | Yes. [VERIFIED: local command `command -v uv && uv --version`] | 0.11.2 | `.venv/bin/...` only after confirming the venv belongs to this repo. [VERIFIED: AGENTS.md:18-20] |
| Python | Runtime and tests | Yes. [VERIFIED: local command `uv run python --version`] | 3.12.13 | None needed. |
| pytest | Automated tests | Yes. [VERIFIED: local command `uv run pytest --version`] | 9.0.3 | None needed. |
| ruff | Lint check | Yes. [VERIFIED: local command `uv run ruff --version`] | 0.15.12 | Manual code review if ruff is unavailable, but local command is available. |

Missing dependencies with no fallback: none. [VERIFIED: local tool probes]

Missing dependencies with fallback: none. [VERIFIED: local tool probes]

## Risk / Pitfalls

### Pitfall 1: Treating TPH-03 as only a test update

What goes wrong: tests may assert current drift without removing the second source of truth. [VERIFIED: src/tools/catalog.py:41-110] [VERIFIED: src/tools/manager.py:17-26]

How to avoid: make descriptor creation and investigate-name derivation use the same registry data, then keep a compatibility drift test. [VERIFIED: .planning/REQUIREMENTS.md:17]

### Pitfall 2: Accidentally doing Phase 38 output-schema work

What goes wrong: adding real per-tool `output_schema` declarations changes the scope and may expose output-validation behavior changes ahead of the planned Phase 38 gate. [VERIFIED: .planning/ROADMAP.md:31-39]

How to avoid: keep generic `{"type": "object"}` output schemas in Phase 37 and leave output-schema content to Phase 38. [VERIFIED: src/tools/catalog.py:41] [VERIFIED: src/tools/catalog.py:133]

### Pitfall 3: Moving input validation after runtime auth

What goes wrong: unvalidated args can enter `resource_scope_binding` or decision-event resource refs. [VERIFIED: src/tools/runtime.py:25-31]

How to avoid: preserve the current order: descriptor lookup -> input validation -> runtime auth. [VERIFIED: src/tools/runtime.py:73-120]

### Pitfall 4: Making declarative gates change reason-code order

What goes wrong: multi-denial cases could change observed `ToolPolicyDecision.reason_codes`, safe error mapping, or tests. [VERIFIED: src/tools/policy.py:316-343] [VERIFIED: src/tools/runtime.py:250-272]

How to avoid: encode gates in the current order and add a multi-denial order test. [VERIFIED: tests/tools/test_tool_platform.py:385-449]

### Pitfall 5: Letting structural tests become too brittle

What goes wrong: internal consolidation requirements need structural proof, but over-specific source-count assertions can fail on harmless formatting changes. [VERIFIED: .planning/REQUIREMENTS.md:21]

How to avoid: test stable private seams such as existence/use of `_fail(...)` and `_runtime_auth_gates`, plus behavior tests for every failure/gate outcome. [VERIFIED: src/tools/runtime.py:73-198] [VERIFIED: src/tools/policy.py:280-366]

### Pitfall 6: Leaking descriptor internals into planner prompt or decision events

What goes wrong: descriptor fields such as `required_permission`, `caller_allowlist`, `executor`, or raw schemas can leak into prompt-visible or replay-visible surfaces. [VERIFIED: tests/tools/test_tool_platform.py:42-81] [VERIFIED: tests/replay/test_tool_policy_events.py:29-40]

How to avoid: continue using `ToolViewV1` projection and low-payload decision events. [VERIFIED: src/tools/policy.py:235-274] [VERIFIED: src/tools/runtime.py:300-308]

## Open Questions (RESOLVED)

1. RESOLVED: `INVESTIGATE_TOOL_NAMES` may remain as a compatibility constant only if it is derived from catalog descriptors, preferably via a helper such as `investigate_tool_names()`. It must not remain a hand-maintained literal set. [VERIFIED: src/tools/manager.py:17-26]
   - What we know: only `src/tools/manager.py` currently references `INVESTIGATE_TOOL_NAMES`. [VERIFIED: `rg -n "INVESTIGATE_TOOL_NAMES" .`]
   - Final plan choice: derive the compatibility value from `ToolCatalog().descriptors()` / catalog helper, and make `UnifiedToolManager.descriptors("investigate")` filter by descriptor attributes (`caller_allowlist`, `kind != "write"`, `exposure == "planner_visible"`) rather than depending on a hardcoded name set. [VERIFIED: src/tools/manager.py:70-79]

2. RESOLVED: `_IDENTIFIER_SCHEMAS` may remain as a private compatibility surface only if it is derived from the single `_TOOL_DECLARATIONS` registry rows. It must not remain a second hand-maintained map. [VERIFIED: src/tools/catalog.py:41-110]
   - What we know: only `catalog.py` references `_IDENTIFIER_SCHEMAS`. [VERIFIED: `rg -n "_IDENTIFIER_SCHEMAS" .`]
   - Final plan choice: store `input_schema` on each registry row and derive `_IDENTIFIER_SCHEMAS = {declaration.name: declaration.input_schema for declaration in _TOOL_DECLARATIONS}` if the private name is kept. [VERIFIED: src/tools/catalog.py:132-133]

## Assumptions Log

All material findings in this research were verified from project files, code grep, local command probes, or cited contract docs. No `[ASSUMED]` claims are required for planning. [VERIFIED: source audit in this session]

## Sources

### Primary (HIGH confidence)

- `.planning/ROADMAP.md` - Phase 37 scope, success criteria, Phase 38/39 boundaries. [VERIFIED: .planning/ROADMAP.md:1-61]
- `.planning/REQUIREMENTS.md` - TPH-03, TPH-04, and out-of-scope constraints. [VERIFIED: .planning/REQUIREMENTS.md:1-46]
- `.planning/STATE.md` - current milestone context, blast-radius constraints, locked identity fields, sequencing rationale. [VERIFIED: .planning/STATE.md:45-105]
- `docs/contract-spec.md` - section 8.0 trusted context, section 12.5/12.6 tool contracts, and replay event family rules. [CITED: docs/contract-spec.md:37-159] [CITED: docs/contract-spec.md:1260-1407] [CITED: docs/contract-spec.md:2156-2164]
- `src/tools/catalog.py` - descriptor model, schema map, default descriptors, catalog API. [VERIFIED: src/tools/catalog.py:1-308]
- `src/tools/runtime.py` - runtime invocation chain, duplicated failure branches, event emission. [VERIFIED: src/tools/runtime.py:1-315]
- `src/tools/policy.py` - visibility logic, current `runtime_auth` if-chain, resource binding, reason-code validation. [VERIFIED: src/tools/policy.py:1-437]
- `src/tools/manager.py` - hardcoded investigate list and compatibility adapter delegation. [VERIFIED: src/tools/manager.py:1-140]
- `src/tools/contracts.py` - external contract model shapes. [VERIFIED: src/tools/contracts.py:1-234]

### Secondary (MEDIUM confidence)

- Existing tests under `tests/tools/`, `tests/agent/test_tools/`, `tests/agent/test_nodes/`, `tests/replay/`, and `tests/architecture/` identify current behavioral guards and closest extension points. [VERIFIED: tests/tools/test_catalog.py] [VERIFIED: tests/tools/test_tool_platform.py] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py] [VERIFIED: tests/replay/test_tool_policy_events.py] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py]

### Tertiary (LOW confidence)

- None. [VERIFIED: source audit in this session]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - project config and local tool probes confirmed Python, pytest, ruff, and uv availability. [VERIFIED: pyproject.toml:1-55] [VERIFIED: local tool probes]
- Architecture: HIGH - source code and normative contract docs agree on `ToolCatalog`, `ToolPlatform`, `ToolRuntime`, `ToolPolicyEngine`, and `UnifiedToolManager` responsibilities. [CITED: docs/contract-spec.md:1312-1394] [VERIFIED: src/tools/platform.py:1-215] [VERIFIED: src/tools/runtime.py:1-315]
- Pitfalls: HIGH - risks are tied to existing tests, source branches, roadmap boundaries, and requirement text. [VERIFIED: .planning/ROADMAP.md:23-51] [VERIFIED: .planning/REQUIREMENTS.md:17-35] [VERIFIED: tests/tools/test_tool_platform.py]

**Research date:** 2026-07-01
**Valid until:** 2026-07-31
