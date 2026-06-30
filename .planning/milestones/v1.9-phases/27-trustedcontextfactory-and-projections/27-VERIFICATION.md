---
phase: "27-trustedcontextfactory-and-projections"
phase_number: 27
phase_name: "TrustedContextFactory and Projections"
verified: "2026-06-22T18:47:39Z"
status: passed
requirements_verified:
  APF-03: verified
  APF-04: verified
blockers: []
warnings:
  - id: W-01
    area: verifier_runtime
    issue: "The gsd-verifier subagent was attempted but hit the Codex usage limit before writing this artifact; orchestrator completed inline verification from committed code, summaries, review artifacts, and executed gates."
  - id: W-02
    area: security_gate
    issue: "workflow.security_enforcement=true and no Phase 27 SECURITY.md exists yet; run `$gsd-secure-phase 27` before advancing if security gate enforcement is required for this milestone step."
tests_reviewed:
  - command: "uv run pytest tests/platform -q"
    result: "47 passed, 1 warning"
  - command: "uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py -q"
    result: "131 passed, 1 warning"
  - command: "uv run pytest tests/test_execute_action.py -q"
    result: "22 passed, 1 warning"
  - command: "uv run ruff check <focused Phase 27 source and test scope>"
    result: "passed"
  - command: "uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q"
    result: "97 passed, 9 warnings"
  - command: "uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q"
    result: "47 passed, 1 warning"
  - command: "uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q"
    result: "9 passed, 8 warnings"
  - command: "gsd-sdk query verify.key-links .planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md"
    result: "3/3 passed"
  - command: "gsd-sdk query verify.schema-drift 27"
    result: "valid true; issues []"
review:
  status_before_fix: issues_found
  findings:
    critical: 0
    warning: 1
    info: 0
  fix_artifact: ".planning/phases/27-trustedcontextfactory-and-projections/27-REVIEW-FIX.md"
score: "2/2 requirements verified; 3/3 plan summaries complete; all key links verified"
human_verification: []
---

# Phase 27 Verification Report

**Status:** passed

Phase 27 achieved the TrustedContextFactory and projection foundation promised by APF-03/APF-04 for the current v1.9 scope. The implementation adds strict canonical trusted-context contracts, no-widening projection helpers, read-only intent/slot policy registries, and focused route/node/tool seam migration without implementing deferred Phase 28-35 platform services.

## Requirement Coverage

| Requirement | Status | Evidence |
|---|---|---|
| APF-03 | VERIFIED | `src/platform/trusted_context.py` defines `TrustedContext`, `MerchantScopeV1`, and `TrustedContextFactory.create_from_request(...)`. API boundaries in `src/api/routers/search.py`, `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`, and approval resume code in `src/api/routers/approvals.py` create canonical `trusted_context` from authenticated/server inputs. Factory tests cover authenticated identity, verified scopes, server ids, override rejection, permission intersection, and server-only tool permissions. |
| APF-04 | VERIFIED | `src/platform/context_projections.py` defines projections for tool, knowledge, memory, approval, replay, intent policy, canonical AgentState identity, and explicit legacy AgentState identity. `investigate`, `action_draft`, and `KnowledgeToolExecutor` consume projection helpers instead of reconstructing service contexts. AgentState identity projection excludes permissions and merchant scope. Code review WR-01 was fixed so structured restrictive merchant scopes fail closed when projected to legacy `KnowledgeContext` list scope. |

## Plan Must-Haves

| Plan | Must-have | Status |
|---|---|---|
| 27-01 | RED tests encode exact TrustedContext, MerchantScopeV1, projection, registry, boundary, and current seam expectations before production code. | VERIFIED |
| 27-02 | Platform contracts and registries turn core RED tests green without migrating route/node/tool seams. | VERIFIED |
| 27-03 | Current search, agent route, graph-node, approval resume, and knowledge-tool seams use factory/projection boundaries while preserving focused approval/replay behavior. | VERIFIED |

## Review And Fix

GSD code review produced one warning: `KnowledgeContext` projection could drop `categories` / `risk_levels` and widen a restrictive `MerchantScopeV1` into `["*"]`. This finding was confirmed and fixed in `fix(27): fail closed for restrictive knowledge scope projections`.

Evidence:

- `project_merchant_scope_for_knowledge(...)` now returns `[]` for structured scopes with category or risk restrictions that `KnowledgeContext` cannot represent.
- `tests/platform/test_context_projections.py::test_knowledge_projection_fails_closed_for_restrictive_scope_dimensions` covers both canonical and tool-context projection paths.
- Focused platform and seam regression gates pass after the fix.

## Regression Gates

Prior Phase 24 regression initially exposed that old graph test config lacked canonical `trusted_context`. Production route behavior already supplied `trusted_context`; the fix was limited to `tests/agent/test_graph.py::_config`, preserving production fail-closed behavior. The full Phase 24 command then passed (`97 passed, 9 warnings`), and Phase 25 commands passed (`47 passed`, `9 passed`).

## Warnings

1. `gsd-verifier` could not complete because the subagent hit the Codex usage limit. The artifact was produced inline after validating code, summaries, review artifacts, key links, schema drift, and regression gates.
2. Security enforcement is enabled, but no Phase 27 `SECURITY.md` exists. Run `$gsd-secure-phase 27` before advancing if this milestone requires security gate closure before Phase 28.
3. Test output still includes pre-existing `LangChainPendingDeprecationWarning` and LangGraph config typing warnings. They did not affect Phase 27 behavior.

## Verdict

No blockers or verification gaps remain for APF-03/APF-04 within Phase 27 scope. Phase 27 is ready for completion tracking and the next milestone phase, subject to the optional/security-gated `$gsd-secure-phase 27` follow-up.
