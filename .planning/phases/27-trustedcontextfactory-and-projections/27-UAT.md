---
status: complete
phase: 27-trustedcontextfactory-and-projections
source:
  - .planning/phases/27-trustedcontextfactory-and-projections/27-01-SUMMARY.md
  - .planning/phases/27-trustedcontextfactory-and-projections/27-02-SUMMARY.md
  - .planning/phases/27-trustedcontextfactory-and-projections/27-03-SUMMARY.md
started: 2026-06-22T23:31:44Z
updated: 2026-06-22T23:50:25Z
---

## Current Test

[testing complete]

## Tests

### 1. Search API Trusted Context Boundary
expected: Calling `/api/v1/search` as an authenticated user uses the authenticated tenant/user/role and server-derived merchant scope. Request-body or query attempts to override tenant, user, permissions, or merchant scope do not widen access, and the response shape remains unchanged for normal searches.
result: pass

### 2. Agent Chat and Agent-Run Trusted Graph Context
expected: Starting `/api/v1/agent/chat` or `/api/v1/agent-runs` creates a canonical `trusted_context.v1` graph config from authenticated/server inputs. Legacy `current_run_id` compatibility follows the server-created run id, and persisted run/response state is not redirected by stale or spoofed graph state.
result: pass

### 3. Tool Nodes Use Trusted Context, Not AgentState Authority
expected: `investigate` and `action_draft` validate `configurable["trusted_context"]` and project tool contexts from it. Tool permissions, merchant scope, trace events, and action draft bindings use trusted context identity; missing trusted context fails closed instead of falling back to checkpointed AgentState.
result: pass

### 4. Knowledge Merchant Scope Projection Is Fail-Closed
expected: Knowledge search/tool execution uses the central trusted projection adapter. Authorized list merchant scopes keep working, unauthorized merchant filters deny before query, and restrictive structured scopes that cannot be represented by legacy `KnowledgeContext` fail closed rather than broadening to wildcard access.
result: pass

### 5. Approval Resume and Interrupt Identity Binding
expected: Approval resume supplies canonical trusted context and only explicit server-granted action-draft tool permission. Approval interrupts reject spoofed `proposed_action.run_id` or `proposed_action.tenant_id` with `APPROVAL_NOT_EXECUTABLE`, and no approval row is created for trusted or spoofed run ids on rejection.
result: pass

### 6. Read-Only Intent and Slot Policy Registry
expected: Downstream code can read intent definitions, route policy, precedence, direct-response/evidence/high-risk sets, and required slot policy through registry APIs. Returned registry data is read-only, and existing intent routing helper behavior remains unchanged.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
