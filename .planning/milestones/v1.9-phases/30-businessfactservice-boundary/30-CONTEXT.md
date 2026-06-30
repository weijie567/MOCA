# Phase 30: BusinessFactService Boundary - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning
**Source:** `$gsd-next` -> `$gsd-discuss-phase 30` (text fallback; conservative defaults selected because interactive question UI was unavailable)

<domain>
## Phase Boundary

Phase 30 makes current business facts available through a stable domain service boundary. The phase owns `BusinessFactService`, `BusinessFactResultV1`, `BusinessFactRefV1`, `BusinessContextV1`, resource freshness/scope checks, and the handoff from ToolPlatform business read tools into authoritative business fact reads.

This phase must consume Phase 29.5 merchant-scope semantics: `support`, `manager`, and legacy `merchant` are merchant-bound; `admin` is platform-wide for business data; tenant public policy remains separate. It must close the current gap where order/refund/ticket identifier reads still depend on raw integration seams for domain ownership proof before emitting business facts or refs.

This phase should not implement Memory Platform, Intent Graph migration, RAG claim verification, approval/action target merchant binding, replay/eval hardening, physical microservices, DB/RLS hardening, or real external execution.

</domain>

<decisions>
## Implementation Decisions

### Service Boundary And Ownership

- **D-01:** Add `BusinessFactService` as the authoritative domain service for current business facts under `src/business/`.
  - It may live alongside the current `BusinessToolService` in `src/business/service.py` or in an adjacent module, but downstream code should treat `BusinessFactService` as the new public boundary.
  - Keep `BusinessToolService` only as a compatibility/tool-facing adapter if needed; do not let new policy, ownership proof, or fact/ref projection keep accumulating there.
- **D-02:** `BusinessFactService` public methods should cover `fetch_context`, `get_order`, `get_refund_case`, `get_ticket`, and the catalog-declared business reads `get_logistics` / `get_merchant_risk` as unavailable or implemented typed reads according to existing data support.
  - Existing data-backed reads are order/refund/ticket; unsupported catalog business tools must not emit facts, refs, or prompt summaries that imply data exists.
- **D-03:** Repositories remain persistence helpers only. Graph nodes, ToolPlatform executors, and service consumers must not use raw business repositories or integration payloads as current business fact authority.
- **D-04:** API routes can preserve Phase 29.5 HTTP semantics, but any shared current-business-fact projection, ownership proof, and `BusinessFactRefV1` emission should be owned by `BusinessFactService`, not duplicated in routers.

### Result Contracts

- **D-05:** Add a dedicated `BusinessFactResultV1` schema instead of treating `ToolResultV2` as the domain result contract.
  - Tool results may wrap or convert a `BusinessFactResultV1` for ToolPlatform compatibility, but the domain service contract should be stable independent of tool runtime.
- **D-06:** Keep `BusinessFactRefV1` as the canonical typed business fact provenance schema. It remains distinct from `EvidenceRefV1` and must not satisfy policy evidence, approval evidence, or action safety snapshot evidence requirements.
- **D-07:** `BusinessContextV1` should aggregate `BusinessFactResultV1` values and expose only safe facts, refs, missing facts, safe errors, status, and freshness. It must not include raw repository rows, raw adapter payloads, policy evidence refs, or memory-derived facts.
- **D-08:** `resource_version` and `data_freshness_at` may be nullable where current demo rows lack version/freshness metadata, but the fields must exist and tests must pin that null is an explicit MVP value, not omitted schema drift.

### Scope Proof And No-Leak Semantics

- **D-09:** For business identifiers that require domain lookup (`order_no`, `refund_case_no`, `ticket_id`), scope proof must happen in `BusinessFactService` before facts or `BusinessFactRefV1` are emitted.
- **D-10:** Phase 30 should resolve the Phase 29 ToolPlatform `requires_domain_scope_check` marker for order/refund/ticket identifiers. It cannot remain a non-enforced annotation after this phase.
- **D-11:** For merchant-bound actors, same-merchant facts are allowed, out-of-merchant-scope facts are denied, missing merchant binding fails closed, unknown roles deny, and `admin` can read cross-merchant within tenant.
- **D-12:** Service/tool paths must be no-leak: denied business reads must not reveal whether an out-of-scope resource exists through `BusinessFactRefV1`, prompt summaries, graph facts, safe error text, or final response content.
  - The exact status mapping is left to planning where needed, but any `permission_denied` result must use a generic safe message and no refs/facts.
  - API-layer 403/404 behavior from Phase 29.5 must not be copied into agent/tool responses as an existence signal.
- **D-13:** Cross-tenant reads remain fail-closed. Tool/service results must not expose cross-tenant existence, raw ids beyond the caller-supplied identifier, or raw adapter errors.

### ToolPlatform Integration

- **D-14:** `BusinessToolExecutor` should delegate business reads to `BusinessFactService`; raw demo integration adapters become implementation details behind the service, not authority exposed to graph/tool code.
- **D-15:** ToolPlatform runtime auth still owns descriptor permission, caller allowlist, side-effect, schema, approval, and idempotency gates. `BusinessFactService` owns domain ownership proof, freshness, result/ref projection, and no-leak business semantics.
- **D-16:** Tool result projection must consume the service-approved result only. If service scope proof fails, `ToolResultProjector`, `ToolResultPromptSummary`, `business_context`, and `last_business_context_refs` must all stay free of denied resource facts and refs.
- **D-17:** Existing compatibility manager paths may remain during the phase, but new tests should target the ToolPlatform -> BusinessToolExecutor -> BusinessFactService chain so the compatibility adapter cannot hide boundary violations.

### Verification Strategy

- **D-18:** Start with RED tests for `BusinessFactResultV1`, `BusinessFactService` method contracts, no-leak permission denial, and `requires_domain_scope_check` enforcement.
- **D-19:** Regression coverage must include same-merchant allow, same-tenant cross-merchant deny/no-leak, cross-tenant fail-closed, missing merchant deny, unknown role deny, admin cross-merchant allow, invalid adapter response, timeout/unavailable, and unsupported logistics/risk behavior if those tools remain catalog-declared.
- **D-20:** Add authority-boundary tests proving RAG, memory, LLM inference, prompt summaries, and raw repository rows cannot substitute missing or denied business facts.
- **D-21:** Preserve existing Phase 29/29.5 behavior while moving the authority boundary: focused tests should cover `tests/business/`, `tests/tools/`, `tests/agent/test_nodes/test_investigate.py`, raw business tool tests, and the relevant API/integration route tests if routes are migrated.

### Agent Discretion

- Exact file split is left to planning. Prefer small schemas/service/adapters modules under `src/business/` and compatibility shims only where needed.
- Exact error codes are flexible, but reason codes and safe messages must be deterministic and test-pinned.
- Exact migration sequence is left to planning, but the safest order is tests first, schema/service contract second, tool executor integration third, graph/API compatibility cleanup last.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 30 goal, success criteria, dependency on Phase 29.5, and downstream Phase 31-35 sequence.
- `.planning/REQUIREMENTS.md` - APF-08 and MER-01 requirement traceability.
- `.planning/STATE.md` - Current milestone state and Phase 29.5 completion context.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Merchant-bound role semantics and Phase 30 handoff.
- `.planning/todos/deferred/2026-06-27-merchant-scope-businessfactservice.md` - Required Phase 30 domain ownership proof and no-leak outcomes.

### Normative Contracts

- `docs/contract-spec.md` §0.2 - BusinessFactService ownership row and forbidden access patterns.
- `docs/contract-spec.md` §8.0 / §8.0.1 - TrustedContext, MerchantScopeV1, and Phase 29.5 role-to-merchant-scope semantics.
- `docs/contract-spec.md` §8.4 - BusinessToolService / BusinessFactResultV1 / BusinessContextV1 target contract.
- `docs/contract-spec.md` §9 - Investigate / route-after-investigate graph semantics and business fact response paths.
- `docs/contract-spec.md` §10 - AgentState business context fields and authority boundaries.
- `docs/contract-spec.md` §12.5 / §12.6 - ToolResultV2, BusinessFactRefV1, ToolCatalog, ToolPlatform, and descriptor/resource-type consistency.
- `docs/target-agent-platform-architecture-plan.md` §3 / §5.2 - Modular monolith service-boundary principles and module ownership matrix.
- `docs/eval-test-plan.md` - Platform boundary eval/test gate expectations.

### Prior Phase Context

- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - Trusted identity/scope projection rules.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - Decision event identity/resource-ref/redaction rules.
- `.planning/phases/29-tool-platform-boundary/29-CONTEXT.md` - ToolPlatform, ToolRuntime, ToolResultProjector, and `requires_domain_scope_check` handoff.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-SPEC.md` - Locked Phase 29.5 role model and deferred routing.

### Current Code Sites

- `src/business/service.py` - Current `BusinessToolService`, aggregation, retry, merchant-scope prechecks, and `fetch_context` behavior.
- `src/business/schemas.py` - Current `BusinessContextV1` compatibility exports.
- `src/business/adapters.py` - Current raw demo integration projection into `ToolResultV2` and `BusinessFactRefV1`.
- `src/tools/contracts.py` - Current `ToolCallContext`, `ToolResultV2`, `BusinessFactRefV1`, `ToolResultPromptSummary`, and `ToolPolicyDecision`.
- `src/tools/catalog.py` - Catalog-declared business read descriptors and resource types.
- `src/tools/policy.py` - Runtime auth resource binding and `requires_domain_scope_check` marker.
- `src/tools/runtime.py` - Runtime invocation chain before executor dispatch and decision-event emission.
- `src/tools/executors/business.py` - Current business tool executor integration point.
- `src/tools/projection.py` - Prompt/audit/resource projection and raw sentinel stripping.
- `src/agent/nodes/investigate.py` - Current graph-facing business context accumulation and prompt summary handling.
- `src/integrations/demo_business/authz.py` - Phase 29.5 interim raw authorization seam.
- `src/integrations/demo_business/orders.py`, `src/integrations/demo_business/refunds.py`, `src/integrations/demo_business/tickets.py` - Current raw business reads behind adapters.

### Tests To Inspect

- `tests/business/test_service.py`
- `tests/business/test_adapters.py`
- `tests/business/test_schemas.py`
- `tests/tools/test_tool_platform.py`
- `tests/agent/test_nodes/test_investigate.py`
- `tests/agent/test_tools/test_get_order.py`
- `tests/agent/test_tools/test_get_refund_case.py`
- `tests/agent/test_tools/test_get_ticket.py`
- `tests/agent/rag_context/test_authority_boundaries.py`
- `tests/agent/test_policy_retrieval_ownership.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src.business.service.BusinessToolService` already centralizes business read dispatch, retry caps, `fetch_context`, and aggregation, but it is still a tool facade rather than the target business fact authority.
- `src.tools.contracts.BusinessFactRefV1` already exists and should remain the typed ref schema.
- `src.tools.contracts.ToolResultV2` and `src.tools.projection.ToolResultProjector` already provide safe tool/prompt/audit surfaces that can wrap service-approved facts.
- `src.tools.policy.ToolPolicyEngine` already identifies identifier arguments needing domain proof via `requires_domain_scope_check`.
- `src.integrations.demo_business.authz.merchant_can_access` already enforces Phase 29.5 merchant role semantics as an interim seam.

### Established Patterns

- Strict public contracts use Pydantic models with `extra="forbid"`.
- Trusted identity and scope come from `TrustedContextFactory` / projections, not AgentState, user payload, checkpoint state, memory, RAG, or LLM output.
- ToolPlatform owns planner visibility and runtime policy; domain services own domain facts and domain ownership proof.
- Prompt-facing tool summaries must be bounded and ref-based; raw adapter payloads and safe-error internals stay out of prompts.
- Tests should pin both allow paths and negative no-leak paths.

### Integration Points

- `BusinessToolExecutor.execute(...)` is the main place to connect ToolPlatform business reads to `BusinessFactService`.
- `BusinessToolService.fetch_context(...)` is the current aggregation behavior that can either move behind `BusinessFactService.fetch_context(...)` or become a compatibility wrapper.
- `investigate._accumulate_tool_result(...)` and `_project_tool_result(...)` consume `ToolResultV2`/projection outputs; they must not need raw business rows after Phase 30.
- API route migration, if included, should preserve Phase 29.5 HTTP semantics while sharing service-owned ownership proof/projection where practical.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 30 as the boundary hardening phase, not a feature-expansion phase. The goal is stable contracts and no-leak authority, not new business data domains.
- Unsupported catalog business tools (`get_logistics`, `get_merchant_risk`) should either get minimal typed unavailable service results or be made consistently unavailable; they must not be visible as usable fact sources without service support.
- Keep service/tool no-leak wording generic, for example "Business resource unavailable for this request", rather than "resource exists but is outside your merchant".

</specifics>

<deferred>
## Deferred Ideas

- Memory merchant isolation and cross-merchant prompt contamination tests belong to Phase 31.
- AgentRun target merchant binding and manager same-merchant run visibility belong to Phase 32 / Phase 35.
- RAG claim verification for business-fact claims belongs to Phase 33.
- ApprovalRequest / ActionDraft target merchant binding and scoped manager approval queues belong to Phase 34.
- Replay/eval broad merchant leakage gates belong to Phase 35.
- DB constraints, RLS, role enum cleanup, and merchant-specific policy schema belong to Phase 36+ / future hardening.

</deferred>

---

*Phase: 30-businessfactservice-boundary*
*Context gathered: 2026-06-27*
