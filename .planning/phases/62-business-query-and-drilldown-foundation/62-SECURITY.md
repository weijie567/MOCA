---
phase: 62
slug: business-query-and-drilldown-foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-10
updated: 2026-07-10
---

# Phase 62 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LLM to business-query schema | Natural-language metric and drilldown requests become registry-backed `BusinessQuerySpec` payloads. | Untrusted user language to controlled query schema |
| ToolPlatform policy boundary | `business_query` execution is only available through trusted tool permissions and strict descriptor validation. | Trusted scope, caller, and schema-validated tool arguments |
| BusinessFactService read boundary | Read execution is owned by `BusinessFactService` and `BusinessQueryCompiler`, not graph nodes or frontend code. | Scoped merchant reads, SQLAlchemy statements, bounded rows |
| Answer-context boundary | Same-thread drilldown state stores only replayable safe specs, answer context, cursor metadata, and binding fingerprints. | Safe context across turns |
| Projection/API/SSE boundary | Normalized business-query facts become final response text, prompt summaries, and API/SSE payloads. | Prompt-safe and UI-safe business facts |
| Agent console boundary | Frontend renders only typed backend-projected fields and labels. | API/SSE payload to timeline/details UI |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-62-01 | Tampering | `src/business/query/registry.py` and parser consumers | mitigate | Frozen descriptors and registry parity tests cover taxonomy immutability and consumer derivation (`62-01-SUMMARY.md`; `tests/business/test_business_query_registry.py`). | closed |
| T-62-02 | Information Disclosure | parser and catalog schema generation | mitigate | Registry excludes tenant/scope/raw SQL/raw cursor/draft/execute fields and covered parser/catalog consumers derive allowed values from it. | closed |
| T-62-03 | Denial of Service | list/detail field and limit descriptors | mitigate | Registry field/limit descriptors feed strict schema/runtime limits; runtime and projection tests cover bounded list behavior. | closed |
| T-62-04 | Tampering | `BusinessQuerySpec` | mitigate | Strict Pydantic schema rejects authority fields, arbitrary filters, raw SQL, raw cursor strings, unknown operations/resources, and oversized limits (`62-02-SUMMARY.md`). | closed |
| T-62-05 | Information Disclosure | list/detail schema inputs | mitigate | Runtime no-existence-leak behavior landed in 62-04; API/UI safe projection landed in 62-06/62-07. | closed |
| T-62-06 | Tampering | business read operation taxonomy | mitigate | Schema/contract tests exclude draft and execute from business-query operations. | closed |
| T-62-07 | Repudiation | `docs/contract-spec.md` | mitigate | Contract delta records Phase 62 semantics and explicit deferrals; summary and review artifacts preserve implementation evidence. | closed |
| T-62-08 | Elevation of Privilege | `TrustedContextFactory` and ToolPolicy | mitigate | `business:query` maps to `tool:business_query` only through trusted context; policy tests cover missing permission and wrong caller denial. | closed |
| T-62-09 | Information Disclosure | ToolCatalog schema | mitigate | Tool descriptor excludes authority/raw database fields and rejects malformed args before dispatch. | closed |
| T-62-10 | Tampering | ToolPolicy | mitigate | ToolPlatform tests prove malformed args and wrong callers are denied before executor work. | closed |
| T-62-11 | Information Disclosure | `query_business_metric` compatibility path | mitigate | Compatibility path maps into validated `BusinessQuerySpec` and preserves read-only policy boundaries. | closed |
| T-62-12 | Tampering | `BusinessQueryCompiler` | mitigate | Compiler builds SQLAlchemy expressions only from registry descriptors; architecture tests reject raw SQL and generic list helpers. | closed |
| T-62-13 | Elevation of Privilege | `BusinessFactService.query_business` | mitigate | Merchant scope is derived from trusted `ToolCallContext`; untrusted tenant/scope fields are rejected. | closed |
| T-62-14 | Information Disclosure | list/detail runtime | mitigate | Scope-before-existence tests cover denied/out-of-scope identifiers and no-leak detail/list behavior. | closed |
| T-62-15 | Denial of Service | list/cursor runtime | mitigate | Runtime enforces registry max limit, deterministic ordering, and limit-plus-one cursor detection. | closed |
| T-62-16 | Information Disclosure | `last_answer_context` | mitigate | Agent state stores safe refs, fields, summaries, cursor capability, and binding fingerprints only; raw rows/scope internals are excluded. | closed |
| T-62-17 | Spoofing | same-thread follow-up state | mitigate | `receive_request` binding validation clears stale context on tenant/user/role/thread/session/scope mismatch. | closed |
| T-62-18 | Tampering | derived drilldown spec | mitigate | Drilldown specs are derived through registry allowlists and revalidated by `BusinessQuerySpec` and BusinessFactService. | closed |
| T-62-19 | Information Disclosure | cursor and field drilldown | mitigate | Field/cursor requests use structured expected-slot types; raw cursor tokens and unallowlisted fields are rejected. | closed |
| T-62-20 | Information Disclosure | `final_response.py` | mitigate | Business-query answer text uses safe projection and no-existence-leak copy; tests cover denied and sensitive-id stripping. | closed |
| T-62-21 | Information Disclosure | `agent_runs.py` API/SSE payload | mitigate | API payload allowlist strips raw rows, filters, prompt payloads, tool args, scope internals, and raw cursor tokens. | closed |
| T-62-22 | Information Disclosure | `ToolResultProjector` | mitigate | Projection strips raw rows, args, payloads, tenant, scope internals, stack traces, and denied identifiers. | closed |
| T-62-23 | Repudiation | eval/golden coverage | mitigate | Deterministic Phase 62 eval fixture records drilldown, permission boundary, no-leak, breakdown, compare, clarification, and unsupported categories. | closed |
| T-62-24 | Information Disclosure | frontend payload rendering | mitigate | Frontend consumes typed safe fields only; unit/e2e tests assert raw sentinel values are not rendered. | closed |
| T-62-25 | Information Disclosure | Result tab cursor/drilldown controls | mitigate | UI renders cursor/drilldown affordances from backend safe labels/capabilities, never raw cursor tokens. | closed |
| T-62-26 | Denial of Service | frontend list/detail rendering | mitigate | UI renders bounded rows and mocked desktop/mobile Playwright gates cover the Phase 62 result states. | closed |
| T-62-27 | Spoofing | stale SSE updates | mitigate | Existing `useAgentRun` generation guard is preserved and covered by frontend tests. | closed |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-10 | 27 | 27 | 0 | Codex |

## Verification Evidence

- `.planning/phases/62-business-query-and-drilldown-foundation/62-01-SUMMARY.md` through `62-07-SUMMARY.md` report no unplanned threat flags and document mitigations implemented for the planned threat model.
- `.planning/phases/62-business-query-and-drilldown-foundation/62-REVIEW.md` is clean after two fixer iterations.
- `.planning/phases/62-business-query-and-drilldown-foundation/62-UAT.md` reports 7/7 UAT checks passed and zero issues.
- Backend security-relevant regression: `421 passed, 36 warnings`.
- Deterministic eval: `Phase 62 business-query golden validation passed: 9 cases`.
- Frontend gates: `npm --prefix frontend test`, `npm --prefix frontend run build`, and `npm --prefix frontend run e2e` passed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-10
