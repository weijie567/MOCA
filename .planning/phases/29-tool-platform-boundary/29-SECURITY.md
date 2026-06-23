---
phase: 29
slug: tool-platform-boundary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-23
updated: 2026-06-23
---

# Phase 29 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Tool catalog to planner prompt | Raw `ToolDescriptor` entries are projected into `ToolViewV1` before prompt exposure. | Tool names, descriptions, prompt-safe input schema, safe usage notes |
| Graph node to tool platform | Graph nodes call `ToolPlatform.visible_tools(...)` and `ToolPlatform.invoke(...)` instead of direct executors. | Caller identity, tool args, tool context, projected results |
| Visibility decision to runtime authorization | Visibility only controls planner discovery; runtime invokes a fresh `runtime_auth` decision before dispatch. | Tool policy decisions, permissions, scope bindings |
| Runtime to executor | `ToolRuntime` validates descriptor, schema, auth, side-effect, approval, safety, idempotency, availability, executor response, and output schema before returning projections. | Validated args, safe denial results, executor `ToolResultV2` |
| Tool result to graph/prompt/conversation | `ToolResultProjector` creates normalized, prompt, audit, debug, and resource-ref surfaces. | Safe scalar fields, typed refs, bounded summaries, prompt text |
| Policy decision to replay event store | Visibility and runtime decisions are written through the Phase 28 replay event emitter using low-payload redacted events. | Event type, decision stage, reason codes, policy version, safe resource refs |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-29-01 | Information Disclosure | `ToolViewV1`, `ToolPlatform.visible_tools`, prompt-safe schemas | mitigate | `ToolViewV1` forbids extra fields (`src/tools/contracts.py:145`); schema projection strips internal/default/example metadata (`src/tools/policy.py:108`); visibility returns only tool views (`src/tools/platform.py:85`). Tests cover prompt-safe view leakage. | closed |
| T-29-02 | Elevation of Privilege | Visibility versus runtime auth | mitigate | `ToolPlatform.invoke(...)` always enters `ToolRuntime.invoke(...)` (`src/tools/platform.py:113`); runtime creates `decision_stage="runtime_auth"` decisions and denies before executor dispatch (`src/tools/runtime.py:117`, `src/tools/runtime.py:126`). | closed |
| T-29-03 | Elevation of Privilege | `ToolRuntime` boundary chain | mitigate | Runtime chain validates descriptor, input schema, auth, side effects, approval, safety, idempotency, executor availability, executor output, and projection (`src/tools/runtime.py:25`, `src/tools/runtime.py:95`, `src/tools/policy.py:316`, `src/tools/runtime.py:136`, `src/tools/runtime.py:186`). | closed |
| T-29-04 | Spoofing / Elevation of Privilege | Resource binding in runtime auth | mitigate | Resource binding uses `ToolCallContext.merchant_scope`, supports legacy list scopes, denies explicit merchant mismatch, and marks order/refund/ticket domain identifiers with `requires_domain_scope_check` for Phase 30 ownership proof (`src/tools/policy.py:394`). | closed |
| T-29-05 | Repudiation | Visibility and runtime decision events | mitigate | Visibility events are emitted as `tool_policy_visibility_recorded` (`src/tools/platform.py:153`); runtime auth events are emitted as `tool_policy_runtime_auth_recorded` (`src/tools/runtime.py:277`). | closed |
| T-29-06 | Tampering | Replay event registry, ORM check, Alembic migration | mitigate | Explicit tool policy event types are registered in replay validators (`src/replay/validators.py:8`), ORM event-type check (`src/db/models.py:1238`), and migration 017 (`src/db/migrations/versions/017_tool_policy_events.py:21`); static check confirms migration 017 creates no parallel table. | closed |
| T-29-07 | Information Disclosure | Tool policy event payload contract | mitigate | `ToolPolicyDecision` is a constrained contract (`src/tools/contracts.py:161`); forbidden replay payload keys include raw args, payloads, schemas, permission internals, PII, and secrets (`src/replay/validators.py:60`); emitted event payloads contain only controlled decision fields (`src/tools/platform.py:163`, `src/tools/runtime.py:303`). | closed |
| T-29-08 | Information Disclosure / Prompt Injection | Tool result projection, graph, prompt, conversation storage | mitigate | `ToolResultProjector` strips raw sentinel keys from normalized/prompt surfaces and nested case-memory refs (`src/tools/projection.py:9`, `src/tools/projection.py:159`, `src/tools/projection.py:209`); investigate and conversation storage consume projector-normalized output. | closed |
| T-29-09 | Tampering | `UnifiedToolManager` compatibility adapter and graph architecture | mitigate | `UnifiedToolManager` builds and delegates to `ToolPlatform` (`src/tools/manager.py:47`, `src/tools/manager.py:84`, `src/tools/manager.py:97`); graph nodes use platform entry points; architecture tests ban graph-node imports of `src.tools.executors.*`. | closed |

*Status: open / closed*
*Disposition: mitigate (implementation required) / accept (documented risk) / transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|

---

## Threat Flags

No Phase 29 `SUMMARY.md` file contains a `## Threat Flags` section. No unregistered threat flags were found.

---

## Verification Evidence

| Evidence | Result |
|----------|--------|
| `gsd-security-auditor` | `## SECURED`, threats closed 9/9, unregistered flags none |
| Phase 29 secure subset pytest | `111 passed, 1 warning` |
| Phase 29 UAT targeted gate | `225 passed, 1 warning` |
| Phase 29 code review | `29-REVIEW.md` clean, 0 critical / 0 warning / 0 info |
| Negative boundary grep | No graph-node direct executor imports in `investigate.py` or `action_draft.py` |
| Negative migration grep | Migration 017 creates no table |
| Deferred-scope grep | No `artifact_store`, `rate_limit`, `feature_flag`, or MCP implementation in `src/tools` |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-23 | 9 | 9 | 0 | Codex / gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-23
