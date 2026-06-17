---
phase: 09-business-tool-facade
verified: 2026-06-13T06:31:40Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed_incorrectly
  previous_score: 10/10
  gaps_closed:
    - "Restricted JWT permissions are enforced before live policy retrieval."
    - "Missing, empty, and unauthorized merchant scope denies before policy adapter execution."
    - "Merchant users without merchant_id receive explicit deny-all scope."
    - "Both /agent-runs/{run_id}/events and legacy /agent/chat inject trusted tool config."
  gaps_remaining: []
  regressions: []
human_verification: []
---

# Phase 9: Business Tool Facade Verification Report

**Phase Goal:** Route read business tools through BusinessToolService using trusted ToolCallContext and typed ToolResultV2.
**Verified:** 2026-06-13T06:31:40Z
**Status:** passed
**Re-verification:** Yes, after gap closure plans 09-06 through 09-09 and independent full-regression review

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Read business tools execute through BusinessToolService without exposing raw invalid upstream payloads. | VERIFIED | `load_business_context.py` calls `BusinessToolService.fetch_context`; adapter and registry no-leak regressions pass. |
| 2 | Permission, scope, status, timeout, partial-success, and invalid-response contracts pass. | VERIFIED | Full Phase 9 regression passes with 132 tests. |
| 3 | Write/action execution remains outside the read facade. | VERIFIED | Registry blocks write descriptors before adapter execution; ownership regression passes. |
| 4 | Verified JWT scopes survive authentication only in trusted request context. | VERIFIED | `permissions.py` stores immutable `request.state.verified_token_scopes`; auth tests pass. |
| 5 | Tool permissions equal the verified-token/current-role scope intersection. | VERIFIED | `_trusted_tool_config` intersects token scopes with `ROLE_SCOPES` before mapping permissions. |
| 6 | An `agent:chat`-only support token receives no business or retrieval permissions. | VERIFIED | Live SSE endpoint regression captures `configurable.permissions == []`. |
| 7 | Missing `tool:search_policy` denies before policy service execution. | VERIFIED | `retrieve_policy_evidence.py` returns `PERMISSION_DENIED`; tests assert `PolicyKnowledgeService.search` is not awaited. |
| 8 | Structured trusted merchant scope reaches KnowledgeContext without widening. | VERIFIED | Projection and graph-path regressions pass. |
| 9 | Missing or malformed structured merchant scope becomes explicit deny-all. | VERIFIED | `_knowledge_merchant_scope` returns `[]` for invalid inputs. |
| 10 | Missing or empty merchant scope denies before policy adapter execution. | VERIFIED | `PolicyKnowledgeService.search` returns `no_evidence`; tests assert adapter non-invocation for both `None` and `[]`. |
| 11 | Unauthorized explicit merchant filters deny before policy adapter execution. | VERIFIED | Service tests assert `no_evidence` and adapter non-invocation. |
| 12 | Merchant users without merchant identity receive deny-all scope, never `"None"`. | VERIFIED | Router projects `{"merchant_ids": []}`; regression passes. |
| 13 | Both live API entry points inject trusted permissions and merchant scope. | VERIFIED | Restricted-token regressions capture empty tool permissions from both SSE and legacy `/agent/chat` graph configs. |
| 14 | Policy retrieval remains Phase 8-owned while Phase 9 retrieval descriptors remain declaration-only. | VERIFIED | `retrieve_policy_evidence` calls `PolicyKnowledgeService`; ownership regression passes. |

**Score:** 14/14 truths verified

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Read tools use the facade without exposing raw invalid upstream payloads. | VERIFIED | Business facade and no-leak suites pass. |
| 2 | Permission, scope, status, timeout, partial-success, and invalid-response contracts pass. | VERIFIED | Execution-boundary permission and merchant-scope denial are now enforced and tested. |
| 3 | Write/action execution remains outside this facade. | VERIFIED | Write-block and ownership tests pass. |

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `src/auth/permissions.py` | VERIFIED | Preserves verified token scopes in trusted request state. |
| `src/api/routers/agent_runs.py` | VERIFIED | Intersects scopes and projects safe merchant scope for SSE runs. |
| `src/api/routers/agent.py` | VERIFIED | Projects the same trusted config into legacy `/agent/chat`. |
| `src/agent/nodes/retrieve_policy_evidence.py` | VERIFIED | Enforces `tool:search_policy` before service execution. |
| `src/knowledge/service.py` | VERIFIED | Enforces missing/empty/unauthorized merchant-scope denial before adapter execution. |
| `src/business_tools/registry.py` | VERIFIED | Enforces ordered business-tool gates and write blocking. |
| `src/business_tools/service.py` | VERIFIED | Provides live business-read facade, retry, and aggregation. |
| `tests/test_agent_runs_api.py` | VERIFIED | Covers restricted-token projection through both live API paths and missing merchant identity. |
| `tests/knowledge/test_service.py` | VERIFIED | Covers adapter non-invocation for denied merchant scope. |
| `tests/agent/test_nodes/test_retrieve_policy_evidence.py` | VERIFIED | Covers permission denial and service non-invocation. |
| `tests/test_approval_integration.py` | VERIFIED | Covers legacy `/agent/chat` trusted-config compatibility. |
| `tests/agent/test_policy_retrieval_ownership.py` | VERIFIED | Protects Phase 8/9 ownership boundary. |

### Behavioral Verification

| Gate | Result | Status |
|---|---|---|
| Phase 9 exact regression | 152 passed, 11 warnings | PASS |
| Approval integration | 5 passed, 1 warning | PASS |
| Full non-integration regression | 348 passed, 11 warnings | PASS |
| Changed-file Ruff | All checks passed | PASS |
| Independent code review | 1 contract gap and 1 test gap found and fixed | PASS |

The 11 warnings are existing LangGraph deprecation and `AsyncMock` warnings outside the Phase 9 authorization changes.

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| TOOL-01 | SATISFIED | Business reads use BusinessToolService; trusted config is projected through both live API paths. |
| TOOL-02 | SATISFIED | Typed outcomes and execution-boundary permission/scope enforcement pass. |
| TOOL-03 | SATISFIED | Write/action tools remain outside the read facade. |

### Gaps Summary

No gaps remain. Plans 09-06 and 09-07 fixed trusted-context projection, Plan 09-08 dispositioned the ownership boundary, and Plan 09-09 completed most missing execution-boundary enforcement. Independent re-review then fixed the legacy `/agent/chat` trusted-config omission and the remaining `merchant_scope=None` fail-open behavior before final acceptance.

---

*Verified: 2026-06-13T06:31:40Z*
*Verifier: Codex independent re-verification*
