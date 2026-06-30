---
phase: 27
slug: trustedcontextfactory-and-projections
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-22
updated: 2026-06-23
validation_audited: 2026-06-23
coverage_state: state_a_existing_validation_updated
test_gaps_open: 0
manual_only_count: 0
---

# Phase 27 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This audit updates the original draft validation map after Phase 27 execution, verification, security review, and follow-up review regression coverage. It validates the current worktree state, including the pending Phase 27 review-fix regression tests for approval/action identity binding.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/platform -q` |
| **Focused integration command** | `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py tests/test_execute_action.py -q` |
| **Review regression command** | `uv run pytest tests/test_agent_runs_api.py::test_event_generator_rejects_spoofed_interrupt_proposed_action_identity tests/test_agent_runs_api.py::test_agent_chat_persists_trusted_run_id_when_graph_returns_stale_current_run_id tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_agent_runs_api.py::test_agent_chat_interrupt_rejects_proposed_action_identity_mismatch tests/agent/test_nodes/test_investigate.py::test_investigate_events_use_trusted_context_identity_not_agentstate tests/test_execute_action.py::test_action_draft_authorizes_approval_against_trusted_context_not_legacy_state -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | Quick: <2s; focused integration: ~2m20s with local PostgreSQL available |

---

## Sampling Rate

- **After every platform contract/projection change:** Run `uv run pytest tests/platform -q`.
- **After every API route, graph-node, approval, replay, or knowledge-tool seam change:** Run the focused integration command.
- **After approval/action identity-binding changes:** Run the review regression command.
- **Before `$gsd-verify-work`:** Run the focused integration command and record any environment blocker in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Max feedback latency:** <30s for platform tests; integration feedback depends on local PostgreSQL and is expected to exceed 30s.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-W0 | 01 | 0 | APF-03, APF-04 | T-27-01-01..04 / TC-01..06 | RED tests encode exact `TrustedContext`, `MerchantScopeV1`, projection, registry, boundary, and current seam expectations before production code | unit + static + seam | `uv run pytest tests/platform tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py -q` | yes | green |
| 27-02-FACTORY | 02 | 1 | APF-03 | T-27-02-01 / T-27-02-02 | Factory derives canonical identity/scope only from authenticated user, verified scopes, server ids, and server-derived merchant scope; generic override kwargs are rejected | unit contract | `uv run pytest tests/platform/test_trusted_context.py tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py -q` | yes | green |
| 27-02-PROJREG | 02 | 1 | APF-04 | T-27-02-03..05 | Projection helpers do not widen identity/scope; canonical AgentState identity excludes permissions and merchant scope; registries are read-only | unit contract | `uv run pytest tests/platform/test_context_projections.py tests/agent/test_intent_policy_registry.py -q` | yes | green |
| 27-03-ROUTES | 03 | 2 | APF-03, APF-04 | T-27-03-01 / T-27-03-04 | Search, chat, agent-runs, and approval resume routes build canonical `trusted_context` from authenticated/server inputs and expose legacy fields only as derived compatibility outputs | API integration + static | `uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/architecture/test_trusted_context_boundaries.py -q` | yes | green |
| 27-03-NODES | 03 | 2 | APF-04 | T-27-03-02 / T-27-03-03 | `investigate`, `action_draft`, and `KnowledgeToolExecutor` consume projection helpers and do not source permissions or merchant scope from AgentState | node/tool integration | `uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_execute_action.py -q` | yes | green |
| 27-03-APPROVAL-REPLAY | 03 | 2 | APF-03, APF-04 | T-27-03-05 / TF-27-03-01 | Approval resume and replay-adjacent projection metadata preserve approval truth, action draft binding, and replay event truth | API + replay integration | `uv run pytest tests/test_approval_api.py tests/replay/test_replay_service.py tests/test_execute_action.py -q` | yes | green |
| 27-REVIEW-WR01 | review fix | 2 | APF-04 | WR-01 | Structured restrictive `MerchantScopeV1` fails closed when projected to legacy `KnowledgeContext` list scope | unit regression | `uv run pytest tests/platform/test_context_projections.py::test_knowledge_projection_fails_closed_for_restrictive_scope_dimensions -q` | yes | green |
| 27-REVIEW-CR01 | review fix | 2 | APF-03, APF-04 | CR-01 | Shared approval interrupt path rejects spoofed `proposed_action.run_id` and `proposed_action.tenant_id` before approval creation | API regression | `uv run pytest tests/test_agent_runs_api.py::test_event_generator_rejects_spoofed_interrupt_proposed_action_identity tests/test_agent_runs_api.py::test_agent_chat_interrupt_rejects_proposed_action_identity_mismatch -q` | yes | green |
| 27-TRACE-EVENTS | review fix | 2 | APF-03, APF-04 | T-27-03-02 / T-27-03-04 | Tool trace events emitted by `investigate` use trusted context identity, not checkpointed AgentState identity | node integration | `uv run pytest tests/agent/test_nodes/test_investigate.py::test_investigate_events_use_trusted_context_identity_not_agentstate -q` | yes | green |

*Status values: pending / green / red / flaky.*

---

## Requirement Coverage

| Requirement | Coverage | Evidence |
|-------------|----------|----------|
| APF-03 | COVERED | `TrustedContextFactory` contract tests, search/chat/agent-run/approval route integration tests, graph config `trusted_context.v1` assertions, override rejection tests, and review regression tests for proposed-action identity spoofing |
| APF-04 | COVERED | Projection contract tests, no-widening metadata tests, restrictive merchant-scope fail-closed regression, node/tool projection integration tests, AgentState identity projection tests, and static boundary tests |

---

## Wave 0 Requirements

- [x] `tests/platform/test_trusted_context.py` - canonical schema, exact field set, extra-field rejection, trusted-source construction.
- [x] `tests/platform/test_merchant_scope.py` - deny-all, explicit wildcard, all-provided-dimensions, invalid value rejection.
- [x] `tests/platform/test_context_projections.py` - tool, knowledge, memory, approval, replay, intent, and AgentState projection-local metadata boundaries.
- [x] `tests/agent/test_intent_policy_registry.py` - read-only registry wrappers over existing intent/slot policy constants.
- [x] `tests/architecture/test_trusted_context_boundaries.py` - no prompt-projector authority, no duplicate trusted-context models, and migrated seam boundary checks.
- [x] `tests/test_search_integration.py`, `tests/test_agent_runs_api.py`, `tests/agent/test_nodes/test_investigate.py`, `tests/agent/test_tools/test_unified_tool_manager.py`, and `tests/knowledge/test_tenant_scope.py` - current seam integration coverage.

---

## Manual-Only Verifications

All Phase 27 requirement behaviors have automated verification.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| none | APF-03, APF-04 | N/A | N/A |

---

## Environment Notes

- PostgreSQL-backed API/integration tests require the local test database to be available.
- Do not run multiple independent PostgreSQL-backed pytest processes in parallel against the same test schema; this can race during `Base.metadata.create_all`. See `.planning/LOCAL-VALIDATION-ISSUES.md` entries 46 and 47.
- The only warning observed during this audit is the pre-existing `LangChainPendingDeprecationWarning` from `langgraph.checkpoint.serde.encrypted`.

---

## Validation Audit 2026-06-23

| Metric | Count |
|--------|-------|
| Automated requirement gaps found | 0 |
| Documentation/status gaps resolved | 9 |
| New test files generated by this audit | 0 |
| Existing/current worktree test additions mapped | 3 |
| Escalated/manual-only gaps | 0 |

Commands run during this audit:

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_agent_runs_api.py::test_event_generator_rejects_spoofed_interrupt_proposed_action_identity tests/test_agent_runs_api.py::test_agent_chat_persists_trusted_run_id_when_graph_returns_stale_current_run_id tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_agent_runs_api.py::test_agent_chat_interrupt_rejects_proposed_action_identity_mismatch tests/agent/test_nodes/test_investigate.py::test_investigate_events_use_trusted_context_identity_not_agentstate tests/test_execute_action.py::test_action_draft_authorizes_approval_against_trusted_context_not_legacy_state -q` | passed: 9 passed, 1 warning |
| `uv run pytest tests/platform -q` | passed: 47 passed, 1 warning |
| `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py tests/test_execute_action.py -q` | passed: 162 passed, 1 warning |
| `uv run ruff check src/api/routers/agent.py src/api/routers/agent_runs.py src/agent/nodes/action_draft.py src/agent/nodes/investigate.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/test_execute_action.py` | passed |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all previously missing references.
- [x] No watch-mode flags.
- [x] Feedback latency <30s for platform contract tests.
- [x] Integration feedback recorded with exact command and result.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-23
