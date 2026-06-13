---
phase: 09-business-tool-facade
verified: 2026-06-13T12:00:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 8/10
  gaps_closed:
    - "Trusted caller context preserves verified caller permissions without widening."
    - "Strict merchant-scope enforcement survives trusted config projection across live retrieval paths."
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "All business and retrieval tools run through one registry/service contract."
    addressed_in: "Phase 9 (09-08 ownership boundary disposition)"
    evidence: "09-08 plan and 09-OWNERSHIP-BOUNDARY.md explicitly disposes this as a scope conflict, not an implementation gap. The authoritative Phase 9 goal is 'Route read business tools through BusinessToolService' -- policy retrieval remains Phase 8 PolicyKnowledgeService's responsibility. Retrieval descriptors are declaration-only (adapter=None) in the Phase 9 registry."
human_verification: []
---

# Phase 9: Business Tool Facade Verification Report

**Phase Goal:** Route read business tools through BusinessToolService using trusted ToolCallContext and typed ToolResultV2.
**Verified:** 2026-06-13T12:00:00Z
**Status:** passed
**Re-verification:** Yes -- after gap closure plans 09-06, 09-07, and 09-08 executed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Read tools use the facade without exposing raw invalid upstream payloads. | VERIFIED | `load_business_context.py:77-78` constructs `BusinessToolService.with_default_registry` and awaits `fetch_context`; adapters construct fresh data-free safe errors via `registry.py:317-338`. |
| 2 | Permission, scope, status, timeout, partial-success, and invalid-response contracts pass. | VERIFIED | `permissions.py:74` preserves `frozenset(token_scopes)` on `request.state.verified_token_scopes`; `agent_runs.py:60` computes `set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))`; `retrieve_policy_evidence.py:90-116` `_knowledge_merchant_scope()` returns `[]` for invalid scope, never `None`; 122 tests pass. |
| 3 | Write/action execution remains outside this facade. | VERIFIED | `registry.py:244-250` blocks `kind="write"` descriptors before adapter execution; `test_policy_retrieval_ownership.py` asserts write descriptor blocked. |
| 4 | Verified JWT scopes survive authentication and remain available only in trusted request context. | VERIFIED | `permissions.py:74` assigns `frozenset(token_scopes)` to `request.state.verified_token_scopes` after all auth checks pass; `test_auth.py:74-101` proves `agent:chat`-only token preserves exactly `{"agent:chat"}`. |
| 5 | Tool permissions are derived from the intersection of verified token scopes and the current database role allowlist. | VERIFIED | `agent_runs.py:60` computes `trusted_scopes = set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))`; `test_agent_runs_api.py:465-487` proves `agent:chat`-only support token gets `permissions=[]` and `agent:chat+orders:read` gets exactly `["tool:get_order"]`. |
| 6 | A support-role token containing only agent:chat receives no business or retrieval tool permissions. | VERIFIED | `test_agent_runs_api.py:465-475` asserts `config["permissions"] == []` for `agent:chat`-only support token. |
| 7 | Structured trusted merchant_scope is projected compatibly into KnowledgeContext without being dropped or widened. | VERIFIED | `retrieve_policy_evidence.py:90-116` `_knowledge_merchant_scope()` extracts `merchant_ids` from structured dict; `test_retrieve_policy_evidence.py:139-184` proves structured dict reaches `KnowledgeContext.merchant_scope` unchanged; 9 malformed variants fail closed with `[]`. |
| 8 | Malformed or missing structured merchant scope fails closed instead of becoming unrestricted None. | VERIFIED | `retrieve_policy_evidence.py:108-109` returns `[]` for non-list or empty `raw_ids`; `test_retrieve_policy_evidence.py:192-212` covers `None`, non-list, empty, non-string variants. No `merchant_scope = None` pattern exists in source. |
| 9 | Phase 9 verification evaluates business reads through BusinessToolService and does not require policy knowledge execution through that facade. | VERIFIED | `test_policy_retrieval_ownership.py:55-101` proves `retrieve_policy_evidence` calls `PolicyKnowledgeService.search` (not `BusinessToolService`); retrieval descriptors are declaration-only (`adapter=None`). |
| 10 | Policy retrieval remains executable through Phase 8 PolicyKnowledgeService while Phase 9 retrieval descriptors remain declaration-only. | VERIFIED | `retrieve_policy_evidence.py:154` creates `PolicyKnowledgeService(LegacyRagKnowledgeAdapter(session))`; `registry.py:155-178` declares `search_policy/search_sop/search_case_memory` as `kind="retrieval"` with no adapter; `test_policy_retrieval_ownership.py:161-170` asserts `search_policy` returns `status="unavailable"` through registry. |

**Score:** 10/10 truths verified

### Deferred Items

Items not yet met but explicitly addressed by the Phase 9 ownership boundary disposition.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Retrieval single-facade claim | Phase 9 (09-08 disposition) | 09-OWNERSHIP-BOUNDARY.md disposes as scope conflict. Policy retrieval is Phase 8's domain. |

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Read tools use the facade without exposing raw invalid upstream payloads. | VERIFIED | `load_business_context.py:77-78` uses `BusinessToolService.with_default_registry`; adapters construct fresh safe errors; sentinel no-leak tests pass. |
| 2 | Permission, scope, status, timeout, partial-success, and invalid-response contracts pass. | VERIFIED | Token/role intersection in `agent_runs.py:60`; merchant scope fail-closed in `retrieve_policy_evidence.py:90-116`; `ToolResultV2` covers all 10 statuses; 122 tests pass. |
| 3 | Write/action execution remains outside this facade. | VERIFIED | `registry.py:244-250` blocks write descriptors; `test_policy_retrieval_ownership.py` asserts write descriptor blocked. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/auth/permissions.py` | Verified JWT scopes preservation in request.state | VERIFIED | `frozenset(token_scopes)` assigned to `request.state.verified_token_scopes` at line 74 after all auth checks pass. |
| `src/api/routers/agent_runs.py` | Token/role scope intersection before tool-permission mapping | VERIFIED | `_trusted_tool_config` at line 58-65 computes `set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))` and maps through `SCOPE_TO_TOOL_PERMISSION`. |
| `src/agent/nodes/retrieve_policy_evidence.py` | Compatible structured merchant-scope projection | VERIFIED | `_knowledge_merchant_scope()` at line 90-116 extracts `merchant_ids` from structured dict or validates legacy list; returns `[]` for invalid input. |
| `src/business_tools/registry.py` | Single descriptor and gate pipeline | VERIFIED | Write-blocking at line 244-250; retrieval descriptors declared as `kind="retrieval"` with `adapter=None`; gate ordering at line 227-315. |
| `src/business_tools/service.py` | Facade dispatch, scope checks, retries, aggregation | VERIFIED | `BusinessToolService.with_default_registry` used by `load_business_context.py`; wired to registry/adapters. |
| `src/agent/nodes/load_business_context.py` | Live business read-switch | VERIFIED | Uses `BusinessToolService.with_default_registry` at line 77; no direct tool imports remain. |
| `tests/integration/test_auth.py` | Scope preservation and rejection safety tests | VERIFIED | `test_verified_token_scopes_preserved_on_request_state` at line 74; insufficient-scope rejection at line 106. |
| `tests/test_agent_runs_api.py` | No-widening and positive intersection tests | VERIFIED | `agent:chat`-only gets `permissions=[]` at line 465; `agent:chat+orders:read` gets `["tool:get_order"]` at line 479. |
| `tests/agent/test_nodes/test_retrieve_policy_evidence.py` | Focused scope preservation and fail-closed regressions | VERIFIED | 13 tests covering structured dict, legacy list, missing, and 9 malformed scope variants. |
| `tests/agent/test_policy_retrieval_ownership.py` | Executable ownership regression guard | VERIFIED | 18 tests proving PolicyKnowledgeService ownership and declaration-only retrieval descriptors. |
| `tests/agent/test_graph.py` | Graph-path assertion for structured scope propagation | VERIFIED | `test_structured_merchant_scope_reaches_knowledge_context` at line 378 asserts `KnowledgeContext.merchant_scope == ["merchant-graph"]`. |
| `.planning/phases/09-business-tool-facade/09-OWNERSHIP-BOUNDARY.md` | Durable re-verification contract | VERIFIED | 7564 bytes; contains authoritative boundary, Phase 8 ownership, and disposition of expanded verifier claim. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `permissions.py` | `agent_runs.py` | `request.state.verified_token_scopes` | WIRED | `permissions.py:74` assigns; `agent_runs.py:154` reads via `getattr(request.state, "verified_token_scopes", None)`. |
| `agent_runs.py` | `SCOPE_TO_TOOL_PERMISSION` | Token/role intersection mapping | WIRED | `agent_runs.py:60-65` computes intersection and maps through `SCOPE_TO_TOOL_PERMISSION`. |
| `retrieve_policy_evidence.py` | `PolicyKnowledgeService` | `service.search(request, context)` | WIRED | `retrieve_policy_evidence.py:154-155` creates service and awaits search. |
| `configurable.merchant_scope` | `KnowledgeContext.merchant_scope` | `_knowledge_merchant_scope()` | WIRED | `retrieve_policy_evidence.py:125` calls helper; line 134 passes result to `KnowledgeContext`. |
| `load_business_context.py` | `BusinessToolService` | `service.fetch_context` | WIRED | `load_business_context.py:77-78` constructs and awaits facade. |
| `registry.py` | `adapters.py` | default order/refund/ticket adapters | WIRED | Three executable business reads have real adapters; retrieval descriptors have `adapter=None`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `agent_runs.py` `_trusted_tool_config` | `permissions` | `set(token_scopes) & set(ROLE_SCOPES[user.role])` | Yes -- real JWT scopes from authentication | FLOWING |
| `retrieve_policy_evidence.py` | `merchant_scope` | `_knowledge_merchant_scope(configurable.get("merchant_scope"))` | Yes -- structured dict from router injection | FLOWING |
| `load_business_context.py` | `business_context` | `BusinessToolService.fetch_context` | Yes -- real order/refund/ticket data via adapters | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full Phase 9 regression suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business_tools/ tests/agent/test_nodes/test_load_business_context.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_graph.py tests/test_agent_runs_api.py tests/integration/test_auth.py -q --tb=short` | 122 passed, 11 warnings | PASS |
| No `merchant_scope = None` in retrieval | `grep -n 'merchant_scope = None' src/agent/nodes/retrieve_policy_evidence.py` | No matches | PASS |
| No direct `ROLE_SCOPES` assignment in router | `grep -n 'trusted_scopes = ROLE_SCOPES' src/api/routers/agent_runs.py` | No matches | PASS |
| Verified token scopes wired across auth/router | `grep -n 'verified_token_scopes' src/auth/permissions.py src/api/routers/agent_runs.py` | 3 matches (1 in permissions, 2 in router) | PASS |
| No anti-patterns in key files | `grep -rn 'TODO\|FIXME\|PLACEHOLDER' src/auth/permissions.py src/api/routers/agent_runs.py src/agent/nodes/retrieve_policy_evidence.py` | No matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOOL-01 | 09-06, 09-08 | Read business tools use BusinessToolService and trusted ToolCallContext. | SATISFIED | `load_business_context.py` uses `BusinessToolService.with_default_registry`; `ToolCallContext` is the typed contract; `permissions.py` preserves verified scopes. |
| TOOL-02 | 09-06, 09-07 | ToolResultV2 covers permission/scope/status/timeout/partial/invalid-response behavior without raw invalid payload exposure. | SATISFIED | Token/role intersection in `agent_runs.py`; merchant scope fail-closed in `retrieve_policy_evidence.py`; `ToolResultV2` covers 10 statuses; safe error construction in `registry.py:317-338`. |
| TOOL-03 | Existing 09-02/09-05; ownership regression 09-08 | Write/action tools remain outside the read-tool facade. | SATISFIED | `registry.py:244-250` blocks write descriptors; `test_policy_retrieval_ownership.py` asserts write descriptor blocked. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (none) | - | - | - | No anti-patterns found in key files. |

### Human Verification Required

No human verification items identified. All checks are programmatically verified.

### Gaps Summary

No gaps found. All 10 observable truths verified. All roadmap success criteria satisfied. All requirements (TOOL-01, TOOL-02, TOOL-03) satisfied. The two authorization defects identified in the previous verification (verified-token scope widening and merchant-scope dropping) have been closed by gap-closure plans 09-06 and 09-07. The ownership boundary scope conflict has been dispositioned by plan 09-08 as a scope conflict, not an implementation gap. Full Phase 9 regression suite passes with 122 tests.

---

*Verified: 2026-06-13T12:00:00Z*
*Verifier: Claude (gsd-verifier)*
