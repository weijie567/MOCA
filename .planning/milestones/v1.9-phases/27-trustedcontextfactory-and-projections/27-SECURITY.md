---
phase: 27
slug: trustedcontextfactory-and-projections
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-23
---

# Phase 27 — Security

Per-phase security contract for Phase 27 TrustedContextFactory, MerchantScopeV1, service projections, route/node seam migration, and approval/replay-adjacent regression coverage.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| User/model payload -> trusted context | User request bodies, LLM outputs, and checkpoint state must not become identity, permission, or merchant-scope authority. | Identity, role, permissions, merchant scope, run ids |
| API/auth/run boundary -> TrustedContextFactory | Authenticated user, verified token scopes, server-created ids, and explicit server-only grants produce canonical TrustedContext. | Trusted identity/scope/run context |
| TrustedContext -> service projections | Projection helpers may add local metadata but must copy identity/scope from TrustedContext only. | Tool, knowledge, memory, approval, replay, intent contexts |
| Route graph config -> graph nodes | Nodes consume `configurable["trusted_context"]`; legacy graph keys remain derived compatibility outputs only. | Graph config and AgentState identity projection |
| ToolCallContext -> KnowledgeContext | Knowledge projection preserves authorized merchant scope and deny-before-query behavior. | Tenant, merchant scope, effective_at, trace/run ids |
| Approval/replay regression gates | Context projection metadata must not alter approval truth, action draft binding, or replay event truth. | Approval resume payloads, replay events, action draft bindings |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-27-01-01 | Spoofing / Elevation of Privilege | Wave 0 factory tests | mitigate | Negative tests cover request-body, LLM, and checkpoint override attempts before implementation. | closed | `tests/platform/test_trusted_context_factory.py:51`; `tests/test_agent_runs_api.py:1498`; `tests/test_agent_runs_api.py:1532` |
| T-27-01-02 | Tampering | Wave 0 projection tests | mitigate | Tests assert projection-local metadata does not enter canonical TrustedContext. | closed | `tests/platform/test_trusted_context.py:23`; `tests/platform/test_trusted_context.py:73`; `tests/platform/test_context_projections.py:151` |
| T-27-01-03 | Information Disclosure | Knowledge seam tests | mitigate | Tests assert unauthorized merchant filters deny before adapter query using trusted list projection. | closed | `tests/knowledge/test_tenant_scope.py:77`; `tests/knowledge/test_tenant_scope.py:96`; `src/tools/executors/knowledge.py:55` |
| T-27-01-04 | Tampering | Static boundary tests | mitigate | AST/source tests reject duplicate trusted context classes and prompt-projector authority imports. | closed | `tests/architecture/test_trusted_context_boundaries.py:33`; `tests/architecture/test_trusted_context_boundaries.py:51`; `tests/architecture/test_trusted_context_boundaries.py:58` |
| T-27-02-01 | Spoofing / Elevation of Privilege | TrustedContextFactory.create_from_request | mitigate | Factory signature uses explicit trusted inputs and tests reject payload/LLM/checkpoint override kwargs. | closed | `src/platform/trusted_context.py:107`; `src/platform/trusted_context.py:121`; `tests/platform/test_trusted_context_factory.py:63` |
| T-27-02-02 | Elevation of Privilege | MerchantScopeV1 | mitigate | Exact schema plus deny-all, explicit wildcard, all-provided-dimensions, invalid-value, and no-widening tests. | closed | `src/platform/trusted_context.py:23`; `src/platform/trusted_context.py:45`; `tests/platform/test_merchant_scope.py:9` |
| T-27-02-03 | Tampering / Information Disclosure | Projection helpers | mitigate | Projection helpers copy identity/scope from TrustedContext only and strict tests prevent metadata leakage. | closed | `src/platform/context_projections.py:86`; `src/platform/context_projections.py:149`; `tests/platform/test_context_projections.py:124` |
| T-27-02-04 | Repudiation / Tampering | AgentState identity helpers | mitigate | Canonical helper returns run_id, session_id, and trace_id; current_run_id appears only in explicit legacy helper. | closed | `src/platform/context_projections.py:299`; `src/platform/context_projections.py:311`; `tests/platform/test_context_projections.py:169` |
| T-27-02-05 | Tampering | Intent/slot registries | mitigate | Read-only return values and behavior-preservation tests prevent downstream mutation or routing drift. | closed | `src/agent/intent_policy.py:134`; `src/agent/intent_policy.py:152`; `tests/agent/test_intent_policy_registry.py:44` |
| T-27-03-01 | Spoofing / Elevation of Privilege | Search and agent routes | mitigate | Routes create TrustedContext from authenticated/server inputs and tests include override attempts. | closed | `src/api/routers/search.py:32`; `src/api/routers/agent.py:52`; `src/api/routers/agent_runs.py:197`; `tests/test_search_integration.py:73`; `tests/test_agent_runs_api.py:864` |
| T-27-03-02 | Elevation of Privilege | Investigate/action_draft nodes | mitigate | Nodes validate trusted graph config and grep/tests forbid permission or merchant_scope reads from AgentState. | closed | `src/agent/nodes/investigate.py:115`; `src/agent/nodes/action_draft.py:236`; `tests/agent/test_nodes/test_investigate.py:335`; `tests/test_execute_action.py:330` |
| T-27-03-03 | Information Disclosure | KnowledgeToolExecutor | mitigate | Central projection preserves list merchant_scope and knowledge service denies unauthorized merchant filters before adapter query. | closed | `src/tools/executors/knowledge.py:12`; `src/tools/executors/knowledge.py:55`; `tests/knowledge/test_tenant_scope.py:96`; `tests/agent/test_tools/test_unified_tool_manager.py:255` |
| T-27-03-04 | Tampering | Compatibility graph config keys | mitigate | Compatibility keys remain outputs derived from canonical trusted_context, not independent trust roots. | closed | `src/api/routers/agent_runs.py:74`; `src/api/routers/agent_runs.py:85`; `src/api/routers/agent.py:60`; `tests/test_agent_runs_api.py:889` |
| T-27-03-05 | Tampering / Repudiation | Approval/replay-adjacent projections | mitigate | Approval and replay gates catch approval/replay regressions without changing those services. | closed | `src/api/routers/agent_runs.py:829`; `src/api/routers/agent_runs.py:860`; `tests/test_agent_runs_api.py:1336`; `tests/test_approval_api.py:255`; `tests/replay/test_replay_service.py:327` |
| TF-27-03-01 | Elevation of Privilege | server_tool_permission_grant in src/platform/trusted_context.py | threat_flag | Mapped to T-27-03-05. TrustedContextFactory accepts explicit server-granted `tool:*` permissions for trusted server boundaries; input is restricted to `tool:*` strings and verified by tests. | closed | `src/platform/trusted_context.py:118`; `src/platform/trusted_context.py:166`; `src/api/routers/approvals.py:574`; `tests/platform/test_trusted_context_factory.py:85`; `tests/test_approval_api.py:185` |

## Accepted Risks Log

No accepted risks.

## Threat Flags

| Flag ID | Mapping | Status | Evidence |
|---------|---------|--------|----------|
| TF-27-03-01 | T-27-03-05 | informational, closed | `27-03-SUMMARY.md` records `server_tool_permission_grant`; current code restricts `server_tool_permissions` to `tool:*` strings and approval resume tests assert projection-derived permissions. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-23 | 15 | 15 | 0 | Codex / gsd-security-auditor |

## Verification

| Command | Result |
|---------|--------|
| `uv run pytest tests/platform tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py tests/test_execute_action.py -q` | Passed: 209 passed, 1 LangChainPendingDeprecationWarning |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-23
