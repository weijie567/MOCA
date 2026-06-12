---
phase: 09-business-tool-facade
verified: 2026-06-12T21:01:31Z
status: gaps_found
score: 7/10 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Trusted caller context preserves verified caller permissions without widening."
    status: failed
    reason: "The authentication dependency validates JWT scopes but returns only User; the run router then reconstructs tool permissions from all ROLE_SCOPES for the database role. An agent:chat-only support token is widened to every business/retrieval read permission."
    artifacts:
      - path: "src/auth/permissions.py"
        issue: "get_current_user discards token_scopes after endpoint-scope validation."
      - path: "src/api/routers/agent_runs.py"
        issue: "_trusted_tool_config derives permissions exclusively from ROLE_SCOPES[user.role]."
    missing:
      - "Preserve verified token scopes in the authenticated principal/request context."
      - "Derive tool permissions from the intersection of verified token scopes and current role scopes."
      - "Add an integration test proving an agent:chat-only support token receives no business-tool permissions."
  - truth: "All business and retrieval tools run through one registry/service contract."
    status: failed
    reason: "Business reads use BusinessToolService, but live policy retrieval calls PolicyKnowledgeService directly. The new ToolRegistry declares search_policy/search_sop/search_case_memory without adapters, so retrieval execution does not use the single registry/service entry."
    artifacts:
      - path: "src/business_tools/registry.py"
        issue: "All retrieval descriptors are registered with adapter=None."
      - path: "src/agent/nodes/retrieve_policy_evidence.py"
        issue: "Live search_policy behavior bypasses BusinessToolService/ToolRegistry and calls PolicyKnowledgeService.search directly."
    missing:
      - "Wire executable retrieval tools through the chosen single registry/service contract, or add an accepted verification override narrowing the goal to business reads only."
  - truth: "Strict merchant-scope enforcement survives trusted config projection across live retrieval paths."
    status: failed
    reason: "The router injects merchant_scope as a structured dict, but retrieve_policy_evidence accepts only a list and converts the dict to None before PolicyKnowledgeService.search."
    artifacts:
      - path: "src/api/routers/agent_runs.py"
        issue: "Injects merchant_scope as {'merchant_ids': [...]}."
      - path: "src/agent/nodes/retrieve_policy_evidence.py"
        issue: "Silently discards every non-list merchant_scope value."
    missing:
      - "Extract merchant_ids from the structured scope or provide separate compatible projections."
      - "Add a graph/router integration test proving merchant scope reaches KnowledgeContext."
---

# Phase 9: Business Tool Facade Verification Report

**Phase Goal:** All business/retrieval tools run through a single registry/service contract with trusted caller context, typed ToolResultV2 outcomes, strict scope enforcement, and write/action tools excluded from the read facade.
**Verified:** 2026-06-12T21:01:31Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Live business reads use BusinessToolService. | VERIFIED | `load_business_context.py:77-80` constructs the default service and awaits `fetch_context`; no concrete business read imports exist in the node. |
| 2 | All business and retrieval tools use one registry/service contract. | FAILED | Retrieval descriptors have no adapters; `retrieve_policy_evidence.py:125-126` calls PolicyKnowledgeService directly. |
| 3 | Trusted caller permissions are not widened. | FAILED | `permissions.py:59-66` discards verified scopes; `agent_runs.py:57-63` rebuilds permissions from the full role allowlist. |
| 4 | ToolCallContext and ToolResultV2 are strict typed contracts. | VERIFIED | Six strict Pydantic contracts exist; `latency_ms` is required; focused schema tests pass. |
| 5 | Registry declaration, dispatch, validation, and gate ordering are substantive. | VERIFIED | `registry.py:205-315` resolves then blocks writes, caller, permission, input, adapter, and output in order. |
| 6 | Permission and strict scope contracts pass across the live path. | FAILED | Token permissions widen and structured merchant scope is discarded by policy retrieval. |
| 7 | Status, timeout, partial-success, and invalid-response outcomes are typed. | VERIFIED | Adapter/service tests cover deterministic mappings, retries, aggregation, and invalid responses. |
| 8 | Raw invalid upstream payloads are not exposed. | VERIFIED | Adapters and registry construct fresh data-free safe errors; sentinel no-leak tests pass. |
| 9 | Business and policy provenance remain separate. | VERIFIED | Canonical EvidenceRefV1 import and BusinessFactRefV1 separation are implemented and tested. |
| 10 | Write/action execution remains outside the read facade. | VERIFIED | Registry blocks write descriptors before adapter execution; live action node calls its separate action tool path. |

**Score:** 7/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/business_tools/schemas.py` | Strict v2 context/result/provenance contracts | VERIFIED | Exists, substantive, imported by registry/service/node, and contract tests pass. |
| `src/business_tools/registry.py` | Single descriptor and gate pipeline | PARTIAL | Business-read path is wired; retrieval descriptors are declaration-only and live retrieval bypasses it. |
| `src/business_tools/adapters.py` | Safe raw business-read normalization | VERIFIED | Real order/refund/ticket imports, strict projections, typed safe results. |
| `src/business_tools/service.py` | Facade dispatch, scope checks, retries, aggregation | VERIFIED | Wired to registry/adapters and live business node; data flows from raw reads to BusinessContextV1. |
| `src/agent/nodes/load_business_context.py` | Live business read-switch | VERIFIED | Uses trusted config projection and BusinessToolService; returns ToolResultV2 objects. |
| `src/api/routers/agent_runs.py` | Trusted authorization projection | FAILED | Role-based projection widens restricted JWT scopes. |
| `src/agent/nodes/retrieve_policy_evidence.py` | Scope-preserving retrieval consumer | FAILED | Structured merchant scope is converted to None. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `load_business_context.py` | `service.py` | `BusinessToolService.fetch_context` | WIRED | Live business node awaits facade. |
| `service.py` | `registry.py` | `registry.invoke` | WIRED | Per-attempt dispatch delegates with stable logical call identity. |
| `registry.py` | `adapters.py` | default order/refund/ticket adapters | WIRED | Three executable business reads have real adapters. |
| `adapters.py` | raw business tools | import-in-place calls | WIRED | Raw results are projected into ToolResultV2. |
| verified JWT scopes | ToolCallContext.permissions | router trusted config | NOT_WIRED | Verified token scopes are lost before permission projection. |
| structured merchant scope | KnowledgeContext.merchant_scope | policy retrieval node | NOT_WIRED | Dict scope is discarded as incompatible. |
| retrieval descriptors | live retrieval execution | ToolRegistry/BusinessToolService | NOT_WIRED | Live retrieval bypasses the registry/service. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `load_business_context.py` | `context.facts`, `context.tool_results` | BusinessToolService -> registry -> real adapters -> raw reads | Yes | FLOWING |
| `agent_runs.py` | configurable `permissions` | ROLE_SCOPES only, not verified token scopes | Over-broad data | FAILED |
| `retrieve_policy_evidence.py` | `KnowledgeContext.merchant_scope` | structured router scope | Discarded to None | HOLLOW |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 9 behavior suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business_tools/ tests/agent/test_nodes/test_load_business_context.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_contracts.py tests/agent/test_graph.py -q --tb=short` | 73 passed, 9 warnings | PASS |
| Restricted support token projection | Direct `_trusted_tool_config` invocation for support principal representing agent:chat-only token | Returned all four read permissions | FAIL |
| Retrieval registry wiring | Inspect default ToolRegistry retrieval entries | search_policy/search_sop/search_case_memory all have `adapter=None` | FAIL |
| Write facade exclusion | Inspect write descriptor and registry tests | Empty caller allowlist and pre-adapter hard block | PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| TOOL-01 | 09-01, 09-02, 09-04, 09-05 | Read business tools use BusinessToolService and trusted ToolCallContext. | BLOCKED | Business reads use the facade, but caller permissions are widened after JWT validation, so the context is not a faithful trusted projection. |
| TOOL-02 | 09-01, 09-03, 09-04 | ToolResultV2 covers permission/scope/status/timeout/partial/invalid-response without raw exposure. | BLOCKED | Typed outcomes and no-leak behavior pass, but live permission/scope enforcement is broken at router/retrieval integration. |
| TOOL-03 | 09-02, 09-05 | Write/action tools remain outside the read facade. | SATISFIED | Write descriptor is hard-denied before adapters; action execution remains on a separate node/tool path. |

No Phase 9 requirement IDs are orphaned: TOOL-01, TOOL-02, and TOOL-03 all appear in PLAN frontmatter and REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/api/routers/agent_runs.py` | 58 | Reconstructs authorization from role after token validation | Blocker | Widens least-privilege JWT permissions. |
| `src/agent/nodes/retrieve_policy_evidence.py` | 96 | Incompatible scope shape silently becomes None | Blocker | Breaks merchant-scope authorization contract. |
| `tests/agent/test_graph.py` | multiple | AsyncMock coroutine warnings in recommendation generation | Warning | Focused suite passes, but warnings can hide incorrectly mocked async behavior. |

### Human Verification Required

None. The blocking gaps are directly demonstrated by code tracing and executable spot-checks.

### Gaps Summary

The business-read facade itself is implemented and well tested, including typed results, safe adapter normalization, aggregation, and write exclusion. Phase goal achievement is blocked by authorization integration: verified JWT scopes are widened at the router, structured merchant scope is discarded by live policy retrieval, and retrieval execution remains outside the claimed single registry/service contract.

The retrieval split appears intentional in the plans, but no verification override exists and no later roadmap phase clearly moves retrieval execution into BusinessToolService. Accepting that narrower scope requires an explicit override; it cannot be treated as achieved under the supplied phase goal.

---

_Verified: 2026-06-12T21:01:31Z_
_Verifier: Codex (gsd-verifier)_
