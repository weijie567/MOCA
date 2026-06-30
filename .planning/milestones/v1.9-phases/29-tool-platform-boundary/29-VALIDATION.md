---
phase: 29
slug: tool-platform-boundary
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-23
updated: 2026-06-23
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
| **Phase gate command** | `uv run pytest tests/tools/test_tool_platform.py tests/tools/test_tool_result_storage.py tests/replay/test_tool_policy_events.py tests/replay/test_replay_migration_contract.py tests/replay/test_decision_events.py tests/architecture/test_tool_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py::test_append_tool_result_stores_projector_normalized_data_without_raw_sentinels -q` |
| **Full targeted suite command** | `uv run pytest tests/tools tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py tests/replay tests/architecture/test_tool_boundaries.py -q` |
| **Estimated runtime** | Phase gate: ~45 seconds; full targeted suite: ~2 minutes on local Postgres |

---

## Sampling Rate

- **After every task commit:** Run the narrow touched test plus the relevant `tests/tools/test_tool_platform.py` subset.
- **After every plan wave:** Run the quick command.
- **Before `$gsd-verify-work`:** Run the full targeted suite and record any environment blocker in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Database test constraint:** Do not run multiple pytest processes that share `moca_test` in parallel; `tests/conftest.py::test_engine` performs `drop_all/create_all` against the shared test database.
- **Max feedback latency:** 90 seconds for quick feedback; full targeted suite may exceed this because it includes replay and conversation DB tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-W0 | 01 | 1 | APF-06, APF-07 | T-29-01 / T-29-02 / T-29-03 | RED tests encode ToolView prompt-safety, visibility decision audit, runtime auth recheck, and projection-before-graph boundaries before production code. | unit + integration + static | `uv run pytest tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/replay/test_decision_events.py tests/replay/test_replay_migration_contract.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/conversation/test_service.py::test_append_tool_result_stores_projector_normalized_data_without_raw_sentinels tests/architecture/test_tool_boundaries.py -q` | yes | green |
| 29-02-POLICY | 02 | 2 | APF-06, APF-07 | T-29-01 / T-29-02 / T-29-04 | `ToolViewV1`, `ToolPolicyDecision`, `ToolPolicyEngine`, prompt-safe schema projection, resource binding, and namespaced reason-code validation are implemented. | unit | `uv run pytest tests/tools/test_tool_platform.py::test_tool_view_exposes_only_prompt_safe_fields tests/tools/test_tool_platform.py::test_prompt_safe_schema_projection_strips_descriptor_policy_and_adapter_metadata tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_visibility_stage_forbids_runtime_only_reason_codes tests/replay/test_decision_events.py -q` | yes | green |
| 29-02-EVENTS | 02 | 2 | APF-07 | T-29-06 / T-29-07 | Visibility and runtime auth event types are registered with validators, retention classification, ORM check, Alembic migration, and migration-contract tests. | unit + migration/integration | `uv run pytest tests/replay/test_tool_policy_events.py tests/replay/test_replay_migration_contract.py -q` | yes | green |
| 29-03-RUNTIME | 03 | 3 | APF-06, APF-07 | T-29-02 / T-29-03 / T-29-04 / T-29-05 / T-29-08 | `ToolPlatform.visible_tools(...)`, `ToolRuntime.invoke(...)`, and `ToolResultProjector` enforce visibility, runtime auth, event emission, and projection boundaries. | unit + integration | `uv run pytest tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py -q` | yes | green |
| 29-04-BOUNDARY | 04 | 4 | APF-06, APF-07 | T-29-01..T-29-09 | `UnifiedToolManager` delegates to `ToolPlatform`, investigate/action_draft use platform boundaries, and no graph path imports executors or raw adapter payloads directly. | static + integration | `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_nodes/test_investigate.py tests/architecture/test_tool_boundaries.py tests/architecture/test_action_draft_boundaries.py -q` | yes | green |
| 29-04-PROJECTION | 04 | 4 | APF-06, APF-07 | T-29-08 / T-29-09 | Conversation storage and investigate graph state consume `ToolResultProjector` outputs; a fast conversation smoke runs before broader gates. | integration | `uv run pytest tests/tools/test_tool_result_storage.py tests/conversation/test_service.py::test_append_tool_result_stores_projector_normalized_data_without_raw_sentinels -q` | yes | green |

*Status values: pending / green / red / flaky.*

---

## Requirement Coverage

| Requirement | Coverage | Status |
|-------------|----------|--------|
| APF-06 | `ToolViewV1` contract tests, schema projection leakage tests, policy visibility plus runtime availability tests, manager delegation tests, investigate prompt tests proving no raw descriptor/policy-only fields or hidden/write tools leak into planner prompt. | covered |
| APF-07 | Runtime auth denial tests for caller, permission, schema, merchant scope, side-effect, approval, safety snapshot, idempotency, unavailable executor, decision event emission, result projection before graph/conversation state, and replay event/migration registration. | covered |

---

## Wave 0 Requirements

- [x] `tests/tools/test_tool_platform.py` - ToolView projection, visibility filtering, availability reason codes, runtime auth decisions, scope binding, denied dispatch prevention, and projection contract coverage.
- [x] `tests/replay/test_tool_policy_events.py` - policy decision event payload, redaction, reason-code validation, resource refs, and batch visibility event coverage for explicit tool-policy event types.
- [x] `tests/architecture/test_tool_boundaries.py` plus `tests/architecture/test_action_draft_boundaries.py` - graph nodes depend on `ToolPlatform` facade and do not import executors/adapters/raw services.
- [x] `tests/agent/test_nodes/test_investigate.py` - investigate prompt receives `ToolViewV1` only and graph state consumes projector output.
- [x] `tests/conversation/test_service.py` - conversation tool-result writes receive normalized projection data rather than raw `ToolResultV2.data`.
- [x] `tests/tools/test_tool_result_storage.py` - tool-result storage keeps normalized, prompt, resource, and audit layers separate.

---

## Manual-Only Verifications

All Phase 29 requirements have automated verification. Manual review is limited to confirming scope containment: Phase 29 does not implement future timeout/retry/rate-limit/artifact persistence work and does not migrate the full planner loop before Phase 32.

---

## Threat Model Requirements

| Threat ID | STRIDE | Behavior | Required Mitigation | Verification | Status |
|-----------|--------|----------|---------------------|--------------|--------|
| T-29-01 | Information Disclosure | Planner sees raw `ToolDescriptor` fields such as executor refs, required scopes, approval policy, caller allowlists, side-effect policy, or internal validation notes. | `ToolViewV1` is a strict prompt-safe projection with recursive schema-key allowlist and forbidden descriptor-only fields. | `tests/tools/test_tool_platform.py` and investigate prompt leakage tests. | green |
| T-29-02 | Elevation of Privilege | Planner treats visibility as authorization and calls hidden/write/denied tools. | `visible_tools(...)` returns only policy-visible and runtime-available views; runtime invoke always creates a new `decision_stage="runtime_auth"` decision. | Visible-but-denied runtime tests and hidden/write prompt tests. | green |
| T-29-03 | Elevation of Privilege | A tool call bypasses caller, permission, schema, resource scope, side-effect, approval, safety snapshot, or idempotency gates. | `ToolRuntime.invoke(...)` centralizes validation, policy decision, gates, executor dispatch, output validation, and safe errors. | Runtime denial matrix in `tests/tools/test_tool_platform.py`. | green |
| T-29-04 | Spoofing | Caller-controlled args or graph state widen tenant or merchant scope. | Runtime resource binding uses `ToolCallContext` and validated args; explicit merchant mismatch denies, domain lookup-dependent ids are marked incomplete and require domain scope check. | Scope-binding tests with explicit merchant mismatch and order/refund/ticket incomplete bindings. | green |
| T-29-05 | Repudiation | Hidden/unavailable decisions are absent from replay, making planner visibility impossible to audit. | Visibility produces a low-payload batched decision event for all catalog tools while prompt receives only visible/available views. | Batch visibility event tests. | green |
| T-29-06 | Tampering | Tool policy events create a parallel envelope or unregistered DB event type. | Emit `ToolPolicyDecision` through Phase 28 `emit_decision_event(...)`; register any new event types in validators, retention map, ORM constraint, Alembic migration, and migration tests. | Replay event and migration-contract tests. | green |
| T-29-07 | Information Disclosure | Decision events leak raw descriptors, raw args, adapter payloads, internal permission notes, or full input schemas. | Event payload contains only controlled `ToolPolicyDecision` fields, reason codes, policy version, availability status, data classification, and safe resource refs. | Negative redaction/resource-ref tests. | green |
| T-29-08 | Information Disclosure / Prompt Injection | Raw tool output enters graph state, prompt context, or conversation storage. | `ToolResultProjector` produces normalized result, structured prompt projection, audit/resource refs, and debug projection before any graph or prompt consumption. | Projector, graph, and conversation leakage tests. | green |
| T-29-09 | Tampering | `UnifiedToolManager` remains the primary policy owner and accumulates new logic after the facade split. | Manager is a legacy compatibility adapter delegating to `ToolPlatform`; new policy/runtime logic lives in `ToolPolicyEngine` and `ToolRuntime`. | Architecture boundary tests and compatibility tests. | green |

---

## Validation Audit 2026-06-23

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

| Evidence | Result |
|----------|--------|
| Phase gate command | `164 passed, 1 warning` |
| Full targeted suite command | `225 passed, 1 warning` |
| Phase 29 UAT | `6 passed, 0 issues` |
| Phase 29 security gate | `threats_open: 0`, 9/9 threats closed |
| Phase 29 code review | `29-REVIEW.md` clean, 0 findings |

Notes:

- No new tests were generated during this audit because all APF-06/APF-07 behaviors already had automated coverage.
- A local validation issue was recorded for zsh glob handling and parallel pytest database DDL races; the successful reruns were serial.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags.
- [x] Feedback latency < 90 seconds for quick checks after Wave 0.
- [x] `nyquist_compliant: true` set in frontmatter after Wave 0 tests exist and pass.

**Approval:** verified 2026-06-23
