---
phase: 29
slug: tool-platform-boundary
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 29 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 under `uv run` |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/replay/test_decision_events.py -q` |
| **Full suite command** | `uv run pytest tests/tools tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py tests/replay tests/architecture/test_tool_boundaries.py -q` |
| **Estimated runtime** | Quick: ~60 seconds after Wave 0 tests exist; full targeted suite: ~2-3 minutes with local services available |

---

## Sampling Rate

- **After every task commit:** Run the narrow touched test plus `uv run pytest tests/tools/test_tool_platform.py -q` once Wave 0 creates it.
- **After every plan wave:** Run the quick command.
- **Before `$gsd-verify-work`:** Run the full targeted suite and record any environment blocker in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Max feedback latency:** 90 seconds for quick feedback after Wave 0; integration feedback may exceed this when replay DB tests are included.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-W0 | 01 | 0 | APF-06, APF-07 | T-29-01 / T-29-02 / T-29-03 | RED tests encode ToolView prompt-safety, visibility decision audit, runtime auth recheck, and projection-before-graph boundaries before production code. | unit + integration + static | `uv run pytest tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/agent/test_nodes/test_investigate.py -q` | No - Wave 0 creates/extends | pending |
| 29-01-PLATFORM | 01 | 1 | APF-06 | T-29-01 / T-29-02 | `ToolPlatform.visible_tools(...)` returns only prompt-safe `ToolViewV1` for policy-visible and runtime-available tools, while hidden/unavailable decisions are recorded outside the prompt. | unit + integration | `uv run pytest tests/tools/test_tool_platform.py -q` | No - Wave 0 creates | pending |
| 29-01-RUNTIME | 01 | 1 | APF-07 | T-29-03 / T-29-04 / T-29-05 | `ToolRuntime.invoke(...)` validates args, derives a fresh runtime `ToolPolicyDecision`, enforces side-effect/approval/safety/idempotency/resource gates, and never dispatches denied calls. | unit + integration | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` | Partial - manager tests exist | pending |
| 29-01-EVENTS | 01 | 1 | APF-07 | T-29-06 / T-29-07 | Visibility and runtime auth decisions are emitted through Phase 28 decision events with controlled payloads, safe reason codes, and no raw descriptors or raw args. | unit + migration/integration | `uv run pytest tests/replay/test_tool_policy_events.py tests/replay/test_decision_events.py tests/replay/test_replay_migration_contract.py -q` | No - Wave 0 creates if new event types are added | pending |
| 29-01-PROJECTION | 01 | 2 | APF-06, APF-07 | T-29-08 / T-29-09 | `ToolResultProjector` produces normalized, prompt, audit/resource, and debug projections; graph and conversation state never store unprojected `ToolResultV2.data`. | integration | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py -q` | Partial - existing files need projector assertions | pending |
| 29-01-BOUNDARY | 01 | 2 | APF-06, APF-07 | T-29-01..T-29-09 | `UnifiedToolManager` delegates to `ToolPlatform`, investigate uses platform seams only, and no graph path imports executors or raw adapter payloads directly. | static + integration | `uv run pytest tests/architecture/test_tool_boundaries.py tests/agent/test_nodes/test_investigate.py -q` | Partial - architecture file exists | pending |

*Status values: pending / green / red / flaky.*

---

## Requirement Coverage

| Requirement | Planned Coverage |
|-------------|------------------|
| APF-06 | `ToolViewV1` contract tests, schema projection leakage tests, policy visibility plus runtime availability tests, investigate prompt tests proving no raw descriptor/policy-only fields or hidden/write tools leak into planner prompt. |
| APF-07 | Runtime auth denial tests for caller, permission, schema, merchant scope, side-effect, approval, safety snapshot, idempotency, unavailable executor, decision event emission, and result projection before graph/conversation state. |

---

## Wave 0 Requirements

- [ ] `tests/tools/test_tool_platform.py` - ToolView projection, visibility filtering, availability reason codes, runtime auth decisions, scope binding, denied dispatch prevention, and projection contract coverage.
- [ ] `tests/replay/test_tool_policy_events.py` - policy decision event payload, redaction, reason-code validation, resource refs, and batch visibility event coverage if explicit tool-policy event types are introduced.
- [ ] `tests/architecture/test_tool_platform_boundaries.py` or extensions to `tests/architecture/test_tool_boundaries.py` - graph nodes depend on `ToolPlatform` facade and do not import executors/adapters/raw services.
- [ ] `tests/agent/test_nodes/test_investigate.py` additions - investigate prompt receives `ToolViewV1` only and graph state consumes projector output.
- [ ] `tests/conversation/test_service.py` additions - conversation tool-result writes receive normalized projection data rather than raw `ToolResultV2.data`.

---

## Manual-Only Verifications

All Phase 29 behaviors should have automated verification. Manual review is limited to confirming that the plan does not expand into future timeout/retry/rate-limit/artifact persistence work and does not migrate the full planner loop before Phase 32.

---

## Threat Model Requirements

| Threat ID | STRIDE | Behavior | Required Mitigation | Verification |
|-----------|--------|----------|---------------------|--------------|
| T-29-01 | Information Disclosure | Planner sees raw `ToolDescriptor` fields such as executor refs, required scopes, approval policy, caller allowlists, side-effect policy, or internal validation notes. | `ToolViewV1` is a strict prompt-safe projection with recursive schema-key allowlist and forbidden descriptor-only fields. | `tests/tools/test_tool_platform.py` and investigate prompt leakage tests. |
| T-29-02 | Elevation of Privilege | Planner treats visibility as authorization and calls hidden/write/denied tools. | `visible_tools(...)` returns only policy-visible and runtime-available views; runtime invoke always creates a new `decision_stage="runtime_auth"` decision. | Visible-but-denied runtime tests and hidden/write prompt tests. |
| T-29-03 | Elevation of Privilege | A tool call bypasses caller, permission, schema, resource scope, side-effect, approval, safety snapshot, or idempotency gates. | `ToolRuntime.invoke(...)` centralizes validation, policy decision, gates, executor dispatch, output validation, and safe errors. | Runtime denial matrix in `tests/tools/test_tool_platform.py`. |
| T-29-04 | Spoofing | Caller-controlled args or graph state widen tenant or merchant scope. | Runtime resource binding uses `ToolCallContext` and validated args; explicit merchant mismatch denies, domain lookup-dependent ids are marked incomplete and require domain scope check. | Scope-binding tests with explicit merchant mismatch and order/refund/ticket incomplete bindings. |
| T-29-05 | Repudiation | Hidden/unavailable decisions are absent from replay, making planner visibility impossible to audit. | Visibility produces a low-payload batched decision event for all catalog tools while prompt receives only visible/available views. | Batch visibility event tests. |
| T-29-06 | Tampering | Tool policy events create a parallel envelope or unregistered DB event type. | Emit `ToolPolicyDecision` through Phase 28 `emit_decision_event(...)`; register any new event types in validators, retention map, ORM constraint, Alembic migration, and migration tests. | Replay event and migration-contract tests. |
| T-29-07 | Information Disclosure | Decision events leak raw descriptors, raw args, adapter payloads, internal permission notes, or full input schemas. | Event payload contains only controlled `ToolPolicyDecision` fields, reason codes, policy version, availability status, data classification, and safe resource refs. | Negative redaction/resource-ref tests. |
| T-29-08 | Information Disclosure / Prompt Injection | Raw tool output enters graph state, prompt context, or conversation storage. | `ToolResultProjector` must produce normalized result, structured prompt projection, audit/resource refs, and debug projection before any graph or prompt consumption. | Projector and graph/conversation leakage tests. |
| T-29-09 | Tampering | `UnifiedToolManager` remains the primary policy owner and accumulates new logic after the facade split. | Manager is a legacy compatibility adapter delegating to `ToolPlatform`; new policy/runtime logic lives in `ToolPolicyEngine` and `ToolRuntime`. | Architecture boundary tests and compatibility tests. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 90 seconds for quick checks after Wave 0.
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 tests exist and pass.

**Approval:** pending
