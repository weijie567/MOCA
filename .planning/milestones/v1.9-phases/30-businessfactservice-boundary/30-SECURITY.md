---
phase: 30
slug: businessfactservice-boundary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-28
updated: 2026-06-28
---

# Phase 30 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `ToolCallContext` to `BusinessFactService` | Trusted runtime identity, tenant, permissions, and merchant scope enter the business fact domain service. User/model payload must not override this context. | User id, tenant id, role, permissions, merchant scope, business identifiers |
| `BusinessFactService` to adapters | Private adapter calls can touch raw rows or upstream payloads, but service output must be strict, typed, and no-leak. | Adapter arguments, raw business rows, `BusinessFactResultV1` |
| `BusinessFactResultV1` to `BusinessContextV1` | Domain results are aggregated into prompt-safe business context only when facts and service-approved refs exist. | Facts, `BusinessFactRefV1`, missing facts, safe errors, freshness |
| `ToolRuntime` to `BusinessToolExecutor` | Runtime authorization is complete before dispatch; domain ownership proof starts after dispatch through the service boundary. | Validated tool args, `ToolCallContext`, `ToolResultV2` |
| `BusinessFactService` to `ToolResultV2` wrapper | Domain results become tool envelopes; denied, stale, unavailable, and unsupported statuses must stay fail-closed. | Safe status, summary, errors, business fact refs |
| `ToolPolicyEngine` marker to domain proof | `requires_domain_scope_check` is a marker only; business ownership proof must still be enforced by `BusinessFactService`. | Redacted resource scope binding, domain identifiers |
| `ToolResultV2` envelope to `ToolResultProjector` | Only envelope refs may become business/resource refs in graph and prompt projections. | `business_fact_refs`, normalized result, prompt projection |
| Tool invocation outcome to investigate graph state | Graph consumes projected results and fact-bearing statuses without raw data authority. | Prompt summaries, business context, claim dependency map |
| Memory/RAG/LLM/prompt/raw rows to business fact claims | Contextual sources cannot satisfy current business fact authority without service-approved `BusinessFactRefV1`. | Memory snippets, policy evidence, prompt summaries, raw rows, material claims |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Evidence | Status |
|-----------|----------|-----------|-------------|------------------------|--------|
| T-30-01 | Information Disclosure | `BusinessFactService.get_order/get_refund_case/get_ticket` | mitigate | Denials use `NO_LEAK_BUSINESS_RESOURCE_MESSAGE`, `fact=None`, `business_fact_refs=[]`, and no resource-existence-specific safe error (`src/business/service.py:480`, `src/business/service.py:499`). Tests cover cross-merchant denial, no facts/refs, no denied identifier in prompt/context serialization (`tests/business/test_service.py:443`, `tests/business/test_service.py:801`). | closed |
| T-30-02 | Spoofing / Elevation of Privilege | `ToolCallContext` consumption in `BusinessFactService` | mitigate | Domain reads use the system-supplied `ToolCallContext`; merchant scope is parsed deny-first and invalid/non-matching scope returns false (`src/business/service.py:68`, `src/business/service.py:237`). Adapter invocation receives the trusted context, not user/model-provided scope (`src/business/service.py:306`). Tests cover empty/no-widening/legacy list merchant scope and service denial behavior (`tests/business/test_service.py:210`, `tests/business/test_service.py:247`, `tests/business/test_service.py:257`, `tests/business/test_service.py:801`). | closed |
| T-30-03 | Tampering | `BusinessFactResultV1` schema | mitigate | `BusinessFactResultV1` is strict with `extra="forbid"` and explicit status, refs, freshness, scope check, missing facts, and safe errors (`src/business/schemas.py:20`). Schema tests cover extra-field rejection and explicit null freshness serialization (`tests/business/test_schemas.py:137`, `tests/business/test_schemas.py:144`, `tests/business/test_schemas.py:153`). | closed |
| T-30-04 | Information Disclosure | Unsupported logistics/risk reads | mitigate | `get_logistics` and `get_merchant_risk` return typed `unavailable` domain results with no facts/refs and generic safe errors (`src/business/service.py:123`, `src/business/service.py:136`). Tests cover domain unavailable results and ToolPlatform-safe unavailable wrappers (`tests/business/test_service.py:842`, `tests/tools/test_tool_platform.py:531`). | closed |
| T-30-05 | Elevation of Privilege | `BusinessToolExecutor` | mitigate | Executor imports and delegates through `BusinessFactService`/`BusinessToolService` only (`src/tools/executors/business.py:7`, `src/tools/executors/business.py:30`). Static tests forbid raw demo integration and repository imports in the executor (`tests/tools/test_tool_platform.py:452`, `tests/agent/test_policy_retrieval_ownership.py:311`). | closed |
| T-30-06 | Information Disclosure | `BusinessFactResultV1` to `ToolResultV2` wrapper | mitigate | Wrapper maps denied/stale/unavailable/unsupported failures to safe `ToolResultV2` with `data=None`, `business_fact_refs=[]`, and generic safe errors (`src/business/service.py:645`, `src/business/service.py:696`, `src/business/service.py:705`). Tests cover fail-closed domain failure wrapping and identifier redaction (`tests/business/test_service.py:688`, `tests/business/test_service.py:694`, `tests/business/test_service.py:745`). | closed |
| T-30-07 | Tampering | `requires_domain_scope_check` marker | mitigate | `ToolPolicyEngine` records only `requires_domain_scope_check=True` for domain lookup identifiers and does not serialize order/refund/ticket identifiers into the policy binding (`src/tools/policy.py:394`, `src/tools/policy.py:426`). ToolPlatform tests assert marker presence and service-enforced denial before data/refs are emitted (`tests/tools/test_tool_platform.py:477`, `tests/tools/test_tool_platform.py:503`). | closed |
| T-30-08 | Spoofing / Elevation of Privilege | ToolPlatform vs `BusinessFactService` responsibility split | mitigate | Tool policy remains responsible for runtime auth, permissions, side-effect, approval, safety snapshot, and idempotency gates (`src/tools/policy.py:320`, `src/tools/policy.py:324`, `src/tools/policy.py:335`). Domain proof remains in `BusinessFactService` and wrapper aggregation (`src/business/service.py:237`, `src/business/service.py:554`). Tests cover runtime marker/denial split and no-widening service scope (`tests/tools/test_tool_platform.py:477`, `tests/business/test_service.py:247`, `tests/business/test_service.py:801`). | closed |
| T-30-09 | Information Disclosure | `src/tools/projection.py` | mitigate | `ToolResultProjector` builds business/resource refs only from `ToolResultV2.business_fact_refs`, not raw `result.data` (`src/tools/projection.py:120`, `src/tools/projection.py:149`, `src/tools/projection.py:269`). Tests prove data-only business ids are ignored and raw sentinels are stripped from prompt/graph surfaces (`tests/agent/test_nodes/test_investigate.py:1042`, `tests/agent/test_nodes/test_investigate.py:1117`, `tests/agent/test_nodes/test_investigate.py:1139`). | closed |
| T-30-10 | Information Disclosure | Investigate graph state and prompt summaries | mitigate | Investigate accumulates facts/refs/dependencies only for fact-bearing statuses with service-approved refs; non-fact statuses add safe errors instead (`src/agent/nodes/investigate.py:540`, `src/agent/nodes/investigate.py:550`, `src/agent/nodes/investigate.py:582`). Tests cover permission denied, unavailable, and stale results producing no facts, refs, prompt id leak, or dependencies (`tests/agent/test_nodes/test_investigate.py:739`, `tests/agent/test_nodes/test_investigate.py:767`, `tests/agent/test_nodes/test_investigate.py:793`). | closed |
| T-30-11 | Tampering | Material business fact claims | mitigate | Material claim verification requires current `BusinessFactRefV1` authority for business facts and rejects policy evidence, memory, model knowledge, prompt summaries, provenance, and raw repository rows as substitutes (`src/agent/rag_context/verifier.py:387`, `src/agent/rag_context/verifier.py:436`, `src/agent/rag_context/verifier.py:681`). Tests cover policy/provenance rejection, wrong tenant refs, missing trusted tenant, memory/model/prompt/raw-row substitution, and action recommendation fail-closed policy evidence membership (`tests/agent/rag_context/test_authority_boundaries.py:146`, `tests/agent/rag_context/test_authority_boundaries.py:183`, `tests/agent/rag_context/test_authority_boundaries.py:205`, `tests/agent/rag_context/test_authority_boundaries.py:228`, `tests/agent/rag_context/test_authority_boundaries.py:280`). | closed |
| T-30-12 | Elevation of Privilege | Graph and executor source boundaries | mitigate | Static ownership tests prevent investigate graph imports of `BusinessFactService`, `BusinessToolService`, raw demo integrations, or business repositories; executor may import the service boundary but not raw repositories/integrations (`tests/agent/test_policy_retrieval_ownership.py:294`, `tests/agent/test_policy_retrieval_ownership.py:311`). | closed |

*Status: open / closed*
*Disposition: mitigate (implementation required) / accept (documented risk) / transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|

---

## Threat Flags

No unregistered Phase 30 threat flags are open.

- `30-03-SUMMARY.md` contains `## Threat Flags` with `None`.
- `30-01-SUMMARY.md` and `30-02-SUMMARY.md` do not contain a `## Threat Flags` section; their deviations were fail-closed security fixes and are represented in the threat evidence above.

---

## Verification Evidence

| Evidence | Result |
|----------|--------|
| `gsd-security-auditor` | `SECURED`, threats closed 12/12, open risks none |
| Main-thread source cross-check | Confirmed service fail-closed behavior, ToolPolicy marker redaction, executor source boundary, projector envelope-ref behavior, investigate no-leak aggregation, and authority verifier fail-closed gates |
| Focused Phase 30 pytest | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` passed: `203 passed, 1 warning` |
| Ruff | `uv run ruff check` on Phase 30 source/tests passed |
| Whitespace | `git diff --check` passed |
| Code review gate | `30-REVIEW.md` status `clean`, 0 critical / 0 warning / 0 info |
| UAT gate | `30-UAT.md` status `complete`, 6 passed, 0 issues |
| Verification gate | `30-VERIFICATION.md` status `passed`; APF-08 verified |
| Implementation files | Read-only security audit; no implementation files were modified |

The single pytest warning is the existing LangGraph `allowed_objects` pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`; it is not a Phase 30 security failure.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-28 | 12 | 12 | 0 | Codex / gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] Implementation files were not modified
- [x] Unregistered threat flags incorporated

**Approval:** verified 2026-06-28
