# Phase 30: BusinessFactService Boundary - Research

**Researched:** 2026-06-28 [VERIFIED: date command]
**Domain:** MOCA business fact authority boundary, ToolPlatform integration, merchant-scope no-leak authorization [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**Confidence:** HIGH for repository architecture and tests; MEDIUM for future action-path routing because Phase 33/34/35 hardening is explicitly downstream [VERIFIED: .planning/ROADMAP.md]

<user_constraints>
## User Constraints (from CONTEXT.md)

The following locked decisions, discretion notes, and deferred items are copied from `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md`; treat this whole block as user/orchestrator scope authority for planning. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

### Locked Decisions

#### Service Boundary And Ownership

- **D-01:** Add `BusinessFactService` as the authoritative domain service for current business facts under `src/business/`.
  - It may live alongside the current `BusinessToolService` in `src/business/service.py` or in an adjacent module, but downstream code should treat `BusinessFactService` as the new public boundary.
  - Keep `BusinessToolService` only as a compatibility/tool-facing adapter if needed; do not let new policy, ownership proof, or fact/ref projection keep accumulating there.
- **D-02:** `BusinessFactService` public methods should cover `fetch_context`, `get_order`, `get_refund_case`, `get_ticket`, and the catalog-declared business reads `get_logistics` / `get_merchant_risk` as unavailable or implemented typed reads according to existing data support.
  - Existing data-backed reads are order/refund/ticket; unsupported catalog business tools must not emit facts, refs, or prompt summaries that imply data exists.
- **D-03:** Repositories remain persistence helpers only. Graph nodes, ToolPlatform executors, and service consumers must not use raw business repositories or integration payloads as current business fact authority.
- **D-04:** API routes can preserve Phase 29.5 HTTP semantics, but any shared current-business-fact projection, ownership proof, and `BusinessFactRefV1` emission should be owned by `BusinessFactService`, not duplicated in routers.

#### Result Contracts

- **D-05:** Add a dedicated `BusinessFactResultV1` schema instead of treating `ToolResultV2` as the domain result contract.
  - Tool results may wrap or convert a `BusinessFactResultV1` for ToolPlatform compatibility, but the domain service contract should be stable independent of tool runtime.
- **D-06:** Keep `BusinessFactRefV1` as the canonical typed business fact provenance schema. It remains distinct from `EvidenceRefV1` and must not satisfy policy evidence, approval evidence, or action safety snapshot evidence requirements.
- **D-07:** `BusinessContextV1` should aggregate `BusinessFactResultV1` values and expose only safe facts, refs, missing facts, safe errors, status, and freshness. It must not include raw repository rows, raw adapter payloads, policy evidence refs, or memory-derived facts.
- **D-08:** `resource_version` and `data_freshness_at` may be nullable where current demo rows lack version/freshness metadata, but the fields must exist and tests must pin that null is an explicit MVP value, not omitted schema drift.

#### Scope Proof And No-Leak Semantics

- **D-09:** For business identifiers that require domain lookup (`order_no`, `refund_case_no`, `ticket_id`), scope proof must happen in `BusinessFactService` before facts or `BusinessFactRefV1` are emitted.
- **D-10:** Phase 30 should resolve the Phase 29 ToolPlatform `requires_domain_scope_check` marker for order/refund/ticket identifiers. It cannot remain a non-enforced annotation after this phase.
- **D-11:** For merchant-bound actors, same-merchant facts are allowed, out-of-merchant-scope facts are denied, missing merchant binding fails closed, unknown roles deny, and `admin` can read cross-merchant within tenant.
- **D-12:** Service/tool paths must be no-leak: denied business reads must not reveal whether an out-of-scope resource exists through `BusinessFactRefV1`, prompt summaries, graph facts, safe error text, or final response content.
  - The exact status mapping is left to planning where needed, but any `permission_denied` result must use a generic safe message and no refs/facts.
  - API-layer 403/404 behavior from Phase 29.5 must not be copied into agent/tool responses as an existence signal.
- **D-13:** Cross-tenant reads remain fail-closed. Tool/service results must not expose cross-tenant existence, raw ids beyond the caller-supplied identifier, or raw adapter errors.

#### ToolPlatform Integration

- **D-14:** `BusinessToolExecutor` should delegate business reads to `BusinessFactService`; raw demo integration adapters become implementation details behind the service, not authority exposed to graph/tool code.
- **D-15:** ToolPlatform runtime auth still owns descriptor permission, caller allowlist, side-effect, schema, approval, and idempotency gates. `BusinessFactService` owns domain ownership proof, freshness, result/ref projection, and no-leak business semantics.
- **D-16:** Tool result projection must consume the service-approved result only. If service scope proof fails, `ToolResultProjector`, `ToolResultPromptSummary`, `business_context`, and `last_business_context_refs` must all stay free of denied resource facts and refs.
- **D-17:** Existing compatibility manager paths may remain during the phase, but new tests should target the ToolPlatform -> BusinessToolExecutor -> BusinessFactService chain so the compatibility adapter cannot hide boundary violations.

#### Verification Strategy

- **D-18:** Start with RED tests for `BusinessFactResultV1`, `BusinessFactService` method contracts, no-leak permission denial, and `requires_domain_scope_check` enforcement.
- **D-19:** Regression coverage must include same-merchant allow, same-tenant cross-merchant deny/no-leak, cross-tenant fail-closed, missing merchant deny, unknown role deny, admin cross-merchant allow, invalid adapter response, timeout/unavailable, and unsupported logistics/risk behavior if those tools remain catalog-declared.
- **D-20:** Add authority-boundary tests proving RAG, memory, LLM inference, prompt summaries, and raw repository rows cannot substitute missing or denied business facts.
- **D-21:** Preserve existing Phase 29/29.5 behavior while moving the authority boundary: focused tests should cover `tests/business/`, `tests/tools/`, `tests/agent/test_nodes/test_investigate.py`, raw business tool tests, and the relevant API/integration route tests if routes are migrated.

### Claude's Discretion

- Exact file split is left to planning. Prefer small schemas/service/adapters modules under `src/business/` and compatibility shims only where needed.
- Exact error codes are flexible, but reason codes and safe messages must be deterministic and test-pinned.
- Exact migration sequence is left to planning, but the safest order is tests first, schema/service contract second, tool executor integration third, graph/API compatibility cleanup last.

### Deferred Ideas (OUT OF SCOPE)

- Memory merchant isolation and cross-merchant prompt contamination tests belong to Phase 31.
- AgentRun target merchant binding and manager same-merchant run visibility belong to Phase 32 / Phase 35.
- RAG claim verification for business-fact claims belongs to Phase 33.
- ApprovalRequest / ActionDraft target merchant binding and scoped manager approval queues belong to Phase 34.
- Replay/eval broad merchant leakage gates belong to Phase 35.
- DB constraints, RLS, role enum cleanup, and merchant-specific policy schema belong to Phase 36+ / future hardening.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-08 | Business fact reads expose `BusinessFactResultV1` / `BusinessFactRefV1` through domain service public methods, and graph/tool code cannot substitute memory, RAG, LLM inference, or raw repository rows for current business facts. [VERIFIED: .planning/REQUIREMENTS.md] | Implement `BusinessFactService` public methods, add `BusinessFactResultV1`, keep `BusinessFactRefV1` distinct from `EvidenceRefV1`, delegate `BusinessToolExecutor` through the service, and add boundary tests for memory/RAG/LLM/raw-row substitution. [VERIFIED: docs/contract-spec.md; src/tools/executors/business.py; tests/agent/rag_context/test_authority_boundaries.py] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Phase-level planning and larger changes use GSD plan/check/review flow with Codex cross-checking after GSD-native checks. [VERIFIED: CLAUDE.md]
- Any Codex review or execution result must be verified against real repository code, documents, and tests; `rg`/grep should locate evidence before reading snippets. [VERIFIED: CLAUDE.md]
- Debugging, startup, validation, UI manual testing, API testing, RAG/agent/memory/tool-call failures, environment pitfalls, and verification failures must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` after handling, in Chinese by default. [VERIFIED: CLAUDE.md]
- `docs/contract-spec.md` is the only normative MOCA contract source for contract semantics, but phase plans own concrete implementation scope and must record any MVP compromise or spec delta rather than silently diverging. [VERIFIED: CLAUDE.md]
- Deferred work must name a target phase, not a vague future bucket. [VERIFIED: CLAUDE.md]

## Source Handling Notes

- `docs/target-agent-platform-architecture-plan.md` was treated as a core architecture input for this research, especially §3 modular monolith/service-boundary principles and §5.2 module ownership matrix. [VERIFIED: docs/target-agent-platform-architecture-plan.md]
- The missing requested file `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-SUMMARY.md` was replaced by reading `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-01-SUMMARY.md` through `29.5-06-SUMMARY.md`, which are the implemented handoff summaries present in the repository. [VERIFIED: find .planning/phases/29.5-merchant-scope-role-model-alignment; VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-01-SUMMARY.md; VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-06-SUMMARY.md]

## Summary

Phase 30 should introduce `BusinessFactService` as the authoritative current-business-fact boundary and leave `BusinessToolService` as a compatibility/tool adapter only. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] This follows the target architecture rule that routers and graph nodes call service public methods, domain services own repository/adapter access, and cross-module calls pass stable schemas rather than raw rows or raw payloads. [VERIFIED: docs/target-agent-platform-architecture-plan.md] The existing `BusinessToolService` already centralizes order/refund/ticket dispatch, retries, `fetch_context`, and no-ref aggregation for denied reads, but it returns `ToolResultV2` directly and still relies on raw demo integration functions for order/refund/ticket domain ownership proof. [VERIFIED: src/business/service.py; src/business/adapters.py; src/integrations/demo_business/orders.py; src/integrations/demo_business/refunds.py; src/integrations/demo_business/tickets.py]

The correct planning move is tests-first migration: add `BusinessFactResultV1` and `BusinessFactService` contract tests, then route `BusinessToolExecutor` through service-approved results, then adjust projector/graph/API compatibility surfaces only where those surfaces currently depend on `ToolResultV2` or raw adapters. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; src/tools/executors/business.py; src/tools/projection.py; src/agent/nodes/investigate.py] Do not expand into memory, RAG claim verification, approval/action target merchant binding, replay/eval broad hardening, or DB/RLS work, because those are explicitly assigned to later phases. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; .planning/ROADMAP.md]

The most important risk is no-leak authorization: service/tool `permission_denied` must not reveal whether an out-of-scope resource exists, and no `BusinessFactRefV1`, prompt summary, graph fact, or `last_business_context_refs` entry may be emitted before BusinessFactService has proved scope. [VERIFIED: docs/contract-spec.md; .planning/todos/deferred/2026-06-27-merchant-scope-businessfactservice.md; tests/business/test_service.py] The current raw integration guard is an interim Phase 29.5 seam, not the target authority boundary. [VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-03-SUMMARY.md]

**Primary recommendation:** Plan one boundary-hardening wave: `BusinessFactResultV1` schema and `BusinessFactService` first, ToolPlatform executor adaptation second, graph/projection/API compatibility and static boundary checks third. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; docs/target-agent-platform-architecture-plan.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Current business fact reads for order/refund/ticket/logistics/merchant-risk | API / Backend domain service | Database / Storage adapters | Business facts are structured domain data that must flow through BusinessFactService public methods and owned repositories/adapters. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Runtime tool permission, caller allowlist, side-effect, schema, approval/idempotency gates | API / Backend platform service | Domain service only after allow | ToolPlatform/ToolRuntime already own descriptor lookup, input validation, runtime auth, executor dispatch, output validation, projection, and decision-event emission. [VERIFIED: src/tools/runtime.py; src/tools/platform.py] |
| Domain ownership proof for `order_no`, `refund_case_no`, and `ticket_id` | API / Backend domain service | Database / Storage helper queries | ToolPolicy currently annotates these identifiers with `requires_domain_scope_check`; Phase 30 must enforce that marker through BusinessFactService before refs/facts are emitted. [VERIFIED: src/tools/policy.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Prompt-safe graph accumulation | Browser / Client: none | API / Backend graph node | `investigate` consumes ToolPlatform projections and accumulates facts only from successful typed business refs; no frontend tier is involved. [VERIFIED: src/agent/nodes/investigate.py] |
| Tenant public policy retrieval | API / Backend KnowledgeService | ToolPlatform retrieval executor | Tenant public policy retrieval is separate from business merchant scope and cannot prove current business facts. [VERIFIED: docs/contract-spec.md; .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-04-SUMMARY.md] |
| Memory and case memory context | API / Backend MemoryContextService / memory executor | Graph orchestration | Memory remains contextual assistance and must not replace current business facts or policy evidence. [VERIFIED: docs/contract-spec.md; tests/agent/rag_context/test_authority_boundaries.py] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | 3.12.13 in `uv run`; project requires `>=3.12` [VERIFIED: uv run python; pyproject.toml] | Runtime language for service, schema, and tests. [VERIFIED: pyproject.toml] | Existing code and tests are Python and use async SQLAlchemy/FastAPI patterns. [VERIFIED: src/business/service.py; tests/conftest.py] |
| Pydantic | 2.13.4 installed in project env [VERIFIED: uv run python] | Strict public contracts such as `ToolCallContext`, `ToolResultV2`, `BusinessFactRefV1`, and new `BusinessFactResultV1`. [VERIFIED: src/tools/contracts.py; src/business/schemas.py] | Existing public schemas use `BaseModel` and `extra="forbid"` for contract safety. [VERIFIED: src/tools/contracts.py; src/business/schemas.py] |
| SQLAlchemy async | 2.0.49 installed in project env [VERIFIED: uv run python] | Async database/session boundary for current demo repositories and tests. [VERIFIED: tests/conftest.py; src/integrations/demo_business/orders.py] | Existing raw business reads and fixtures use `AsyncSession` and async repositories. [VERIFIED: src/integrations/demo_business/orders.py; tests/conftest.py] |
| ToolPlatform / ToolRuntime | Internal v1.9 boundary [VERIFIED: src/tools/platform.py; src/tools/runtime.py] | Graph-facing tool visibility, runtime authorization, executor dispatch, output validation, projection, and decision events. [VERIFIED: src/tools/runtime.py] | Phase 29 already established ToolPlatform as graph-facing public facade, so Phase 30 should integrate there rather than bypass it. [VERIFIED: src/tools/platform.py; .planning/ROADMAP.md] |
| BusinessFactRefV1 | `business_fact_ref.v1` [VERIFIED: src/tools/contracts.py] | Typed business fact provenance for order/refund/ticket/logistics/merchant-risk. [VERIFIED: src/tools/contracts.py; docs/contract-spec.md] | Existing tests already verify it is not coercible to `EvidenceRefV1`. [VERIFIED: tests/business/test_schemas.py; tests/agent/test_policy_retrieval_ownership.py] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| pytest | 9.0.3 through `uv run pytest` [VERIFIED: uv run pytest --version] | Contract, integration, boundary, and no-leak tests. [VERIFIED: pyproject.toml; tests/] | Use for all RED/GREEN Phase 30 tests. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| pytest-asyncio | 1.3.0 installed in project env [VERIFIED: uv run python] | Async service and repository tests. [VERIFIED: tests/conftest.py; tests/business/test_service.py] | Use for `BusinessFactService` methods that call async repositories/adapters. [VERIFIED: src/business/service.py] |
| ruff | 0.15.12 through `uv run ruff` [VERIFIED: uv run ruff --version] | Lint gate for changed source/test files. [VERIFIED: pyproject.toml] | Run after implementation edits. [VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-06-SUMMARY.md] |
| PostgreSQL test database via asyncpg | `postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test` [VERIFIED: tests/conftest.py] | DB-backed business and API tests. [VERIFIED: tests/conftest.py] | Needed for seeded merchant-scope integration tests. [VERIFIED: tests/conftest.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New external authorization library | Keep `TrustedContextFactory`, `MerchantScopeV1`, and `require_merchant_access` helpers | Existing Phase 29.5 role semantics are already locked and tested, so a new library would add drift without solving domain ownership proof. [VERIFIED: src/platform/trusted_context.py; src/auth/permissions.py; .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-02-SUMMARY.md] |
| Renaming `BusinessToolService` outright | Add `BusinessFactService` and keep `BusinessToolService` as compatibility adapter | Context allows either adjacent module or same file, but downstream should treat `BusinessFactService` as public boundary and avoid large unnecessary rename churn. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Emitting `BusinessFactRefV1` from ToolResultProjector heuristics | Emit refs only from service-approved `BusinessFactResultV1` / converted ToolResult envelope | Projector currently can infer resource refs from data keys; Phase 30 should avoid treating heuristic projection as authority. [VERIFIED: src/tools/projection.py; docs/contract-spec.md] |

**Installation:**

```bash
# No new dependency is required for Phase 30.
uv sync --extra dev
```

**Version verification:** `uv run python`, `uv run pytest --version`, and `uv run ruff --version` verified local tool versions; no package registry lookup is needed because Phase 30 should not add a new external dependency. [VERIFIED: local commands; pyproject.toml]

## Architecture Patterns

### System Architecture Diagram

```text
API/auth/run boundary
  -> TrustedContextFactory
      -> ToolCallContext projection
          -> ToolPlatform.visible_tools / ToolPlatform.invoke
              -> ToolRuntime descriptor + schema + runtime auth
                  -> BusinessToolExecutor
                      -> BusinessFactService public method
                          -> domain ownership proof
                              -> owned repository/adapter read
                                  -> BusinessFactResultV1
                                      -> ToolResultV2 compatibility wrapper
                                          -> ToolResultProjector
                                              -> investigate business_context / prompt-safe summaries / trace refs
```

This flow keeps graph nodes and tool runtime away from raw repositories and makes BusinessFactService the only place where current business fact projection and `BusinessFactRefV1` emission happen. [VERIFIED: docs/target-agent-platform-architecture-plan.md; docs/contract-spec.md; src/tools/runtime.py; src/tools/executors/business.py; src/agent/nodes/investigate.py]

### Recommended Project Structure

```text
src/business/
├── schemas.py        # BusinessFactResultV1 + BusinessContextV1 public contracts
├── service.py        # BusinessFactService public methods; BusinessToolService compatibility wrapper if retained
└── adapters.py       # Private projection helpers from owned demo repositories/raw adapters to facts/results

tests/business/
├── test_schemas.py   # BusinessFactResultV1 strict schema and ref/evidence separation
├── test_service.py   # BusinessFactService method contracts, scope proof, no-leak cases
└── test_adapters.py  # Private adapter invalid response/timeout/unavailable projection

tests/tools/
└── test_tool_platform.py  # requires_domain_scope_check enforcement through service boundary

tests/agent/
└── test_nodes/test_investigate.py  # graph consumes only service-approved ToolPlatform projections
```

This structure follows current file ownership while making `BusinessFactService` the public boundary and keeping adapters private. [VERIFIED: src/business/service.py; src/business/schemas.py; src/business/adapters.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

### Pattern 1: Service-First Business Fact Read

**What:** `BusinessFactService.get_order(...)`, `get_refund_case(...)`, `get_ticket(...)`, `get_logistics(...)`, and `get_merchant_risk(...)` return `BusinessFactResultV1`, not `ToolResultV2`. [VERIFIED: docs/contract-spec.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

**When to use:** Use for every current business fact read, including reads initiated by ToolPlatform, graph investigation, API sharing, or future claim verification. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**Example:**

```python
# Source: docs/contract-spec.md §8.4; src/tools/contracts.py
class BusinessFactResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_result.v1"] = "business_fact_result.v1"
    tenant_id: str
    status: Literal[
        "ok",
        "partial",
        "not_found",
        "permission_denied",
        "stale",
        "unavailable",
        "invalid_request",
    ]
    fact: dict[str, Any] | None
    business_fact_refs: list[BusinessFactRefV1]
    resource_version: str | None = None
    data_freshness_at: datetime | None = None
    source_system: str
    scope_check_result: Literal["allowed", "denied", "not_applicable", "unknown"]
    missing_required_facts: list[str]
    safe_errors: list[ToolError]
```

### Pattern 2: No-Leak Denial Helper

**What:** Denied service results must have `status="permission_denied"`, `fact=None`, no business refs, `scope_check_result="denied"`, and generic safe errors. [VERIFIED: docs/contract-spec.md; tests/business/test_service.py]

**When to use:** Use when merchant scope is empty, missing merchant binding, unknown role, cross-merchant ownership mismatch, invalid role/user proof, or any ambiguous ownership lookup failure that must fail closed. [VERIFIED: docs/contract-spec.md; src/integrations/demo_business/authz.py]

**Example:**

```python
# Source: docs/contract-spec.md §8.0.1 and §8.4
def _permission_denied_result(ctx: ToolCallContext, *, source_system: str) -> BusinessFactResultV1:
    return BusinessFactResultV1(
        tenant_id=ctx.tenant_id,
        status="permission_denied",
        fact=None,
        business_fact_refs=[],
        resource_version=None,
        data_freshness_at=None,
        source_system=source_system,
        scope_check_result="denied",
        missing_required_facts=[],
        safe_errors=[
            ToolError(
                code="BUSINESS_FACT_PERMISSION_DENIED",
                safe_message="Business resource unavailable for this request",
                retryable=False,
                source="policy",
            )
        ],
    )
```

### Pattern 3: Tool Adapter Wraps Service Result

**What:** `BusinessToolExecutor.execute(...)` should call BusinessFactService and adapt the result into `ToolResultV2` only at the tool boundary. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; src/tools/executors/business.py]

**When to use:** Use for all catalog business reads so ToolPlatform keeps its existing result envelope and projection contract. [VERIFIED: src/tools/runtime.py; src/tools/projection.py]

**Example:**

```python
# Source: src/tools/executors/business.py; docs/contract-spec.md §12.5
async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    fact_result = await self.service.invoke(name, args, ctx)
    return business_fact_result_to_tool_result(fact_result, tool_name=name)
```

### Anti-Patterns to Avoid

- **Letting `ToolPolicyEngine` enforce domain lookup identifiers by annotation only:** `requires_domain_scope_check` is currently a marker for order/refund/ticket identifiers, and Phase 30 must make it enforced by BusinessFactService before refs/facts are emitted. [VERIFIED: src/tools/policy.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
- **Using API 403/404 semantics in tool/service responses:** API routes can preserve tenant-first 404 and same-tenant 403, but service/tool `permission_denied` must not expose whether a resource exists. [VERIFIED: docs/contract-spec.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
- **Putting raw repository rows into graph state:** Graph nodes consume typed ToolPlatform projections and must not receive raw repositories or adapter payloads. [VERIFIED: docs/target-agent-platform-architecture-plan.md; tests/agent/test_nodes/test_investigate.py]
- **Treating `BusinessFactRefV1` as policy evidence:** Business refs are not assignable to `EvidenceRefV1` and cannot satisfy policy evidence or action safety snapshot evidence requirements. [VERIFIED: docs/contract-spec.md; tests/business/test_schemas.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trusted identity and merchant scope derivation | Custom role parsing in BusinessFactService, graph nodes, or executors | `TrustedContextFactory`, `MerchantScopeV1`, and `project_to_tool_context` | Phase 29.5 already locks support/manager/merchant/admin scope semantics and no-widening server overrides. [VERIFIED: src/platform/trusted_context.py; src/platform/context_projections.py] |
| Tool visibility/runtime auth | Executor-local permission checks replacing ToolPlatform | `ToolPlatform.invoke` / `ToolRuntime` / `ToolPolicyEngine` | Runtime auth already rechecks caller, permission, explicit merchant ID scope, side-effect, schema, safety snapshot, idempotency, and availability before dispatch. [VERIFIED: src/tools/runtime.py; src/tools/policy.py] |
| Policy evidence or current business fact authority | LLM inference, RAG citation membership, session memory, case memory, prompt summaries | Business facts from `BusinessFactService`; policy claims from Knowledge/RAG/claim verifier | Contract and tests separate current facts from policy evidence and contextual memory. [VERIFIED: docs/contract-spec.md; tests/agent/rag_context/test_authority_boundaries.py] |
| Raw-result redaction/projection | Ad hoc string filters in graph code | `ToolResultProjector` and `ToolResultPromptSummary` | Projector already strips raw sentinel keys from normalized, prompt, text, and debug projections. [VERIFIED: src/tools/projection.py; tests/tools/test_tool_platform.py] |
| Business ref/evidence ref conversion | Building fake `EvidenceRefV1` from order/refund/ticket facts | `BusinessFactRefV1` only, with `policy_evidence_refs=[]` for business reads | Existing schema tests reject `BusinessFactRefV1` as `EvidenceRefV1`. [VERIFIED: tests/business/test_schemas.py] |
| Unsupported `get_logistics` / `get_merchant_risk` facts | Placeholder facts or summaries implying real data exists | Typed unavailable/invalid_request `BusinessFactResultV1` with no facts/refs | Catalog declares both reads but current default business registry implements only order/refund/ticket. [VERIFIED: src/tools/catalog.py; src/business/service.py] |

**Key insight:** BusinessFactService should own only domain proof and stable fact projection; it should not duplicate ToolPlatform auth, KnowledgeService evidence validation, or MemoryContextService semantics. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | PostgreSQL test fixtures include orders, refund cases, tickets, merchants, users, and conversation/session records with `business_fact_refs_json` and `policy_evidence_refs_json`. [VERIFIED: tests/conftest.py; src/db/models.py] | No data migration is required for Phase 30 unless implementation changes persisted JSON shape; service reads must dynamically prove ownership against existing business rows before emitting new refs. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Live service config | No external live service configuration was found in the phase scope; current business reads use in-repo demo repositories/adapters and local DB sessions. [VERIFIED: src/integrations/demo_business/orders.py; src/integrations/demo_business/refunds.py; src/integrations/demo_business/tickets.py] | None. [VERIFIED: src/integrations/demo_business/orders.py] |
| OS-registered state | No OS-registered process, scheduler, or service name is part of this phase. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | None. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Secrets/env vars | Test DB URL is hardcoded in `tests/conftest.py`; no Phase 30 secret/env-var rename or key migration was identified. [VERIFIED: tests/conftest.py] | None for research/planning; keep DB credential handling out of Phase 30 unless tests expose a local validation issue. [VERIFIED: tests/conftest.py; AGENTS.md] |
| Build artifacts | No generated build artifact carrying the old service boundary name was identified; current imports expose `BusinessToolService` in `src/business/__init__.py`. [VERIFIED: src/business/__init__.py] | Update public exports only if implementation introduces `BusinessFactService`; no package reinstall is required for tests run through `uv run`. [VERIFIED: pyproject.toml; src/business/__init__.py] |

## Common Pitfalls

### Pitfall 1: Treating `requires_domain_scope_check` As Enforcement

**What goes wrong:** The policy decision carries `requires_domain_scope_check=True` for order/refund/ticket identifiers, but the runtime still dispatches if general permission/caller checks pass. [VERIFIED: src/tools/policy.py; src/tools/runtime.py]
**Why it happens:** ToolPolicy can see identifier strings but cannot prove the merchant that owns an order/refund/ticket without a domain lookup. [VERIFIED: src/tools/policy.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**How to avoid:** BusinessFactService must consume the marker semantics by performing lookup-based ownership proof before returning facts or refs. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**Warning signs:** A test can call `ToolPlatform.invoke("get_order", {"order_no": ...})` and receive a business ref without asserting BusinessFactService scope proof. [VERIFIED: src/tools/platform.py; tests/tools/test_tool_platform.py]

### Pitfall 2: No-Leak Failures Through Prompt Summaries

**What goes wrong:** A denied out-of-scope identifier leaks through `ToolResultPromptSummary`, `business_context.errors`, `last_business_context_refs`, or final response text. [VERIFIED: .planning/todos/deferred/2026-06-27-merchant-scope-businessfactservice.md; tests/business/test_service.py]
**Why it happens:** Tool/service layers can accidentally preserve caller-supplied identifiers or adapter messages in safe summaries. [VERIFIED: src/business/adapters.py; src/agent/nodes/investigate.py]
**How to avoid:** Permission-denied results must use generic safe messages, no refs, no facts, and no resource-specific success summary. [VERIFIED: docs/contract-spec.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**Warning signs:** Denied result serialization contains `ORD-...`, `RF-...`, or `TK-...` for a resource that was not scope-approved. [VERIFIED: tests/business/test_service.py]

### Pitfall 3: Mixing Business Facts With Policy Evidence

**What goes wrong:** Order/refund/ticket facts are represented as `EvidenceRefV1` or policy evidence is used to prove current business object state. [VERIFIED: docs/contract-spec.md; tests/agent/rag_context/test_authority_boundaries.py]
**Why it happens:** Both policy evidence and business facts travel through tool results and graph state, but they have different authority semantics. [VERIFIED: docs/contract-spec.md; src/agent/nodes/investigate.py]
**How to avoid:** Business read tools must leave `policy_evidence_refs=[]`, emit only service-approved `BusinessFactRefV1`, and keep claim-verification tests proving policy evidence cannot support business fact claims. [VERIFIED: src/business/adapters.py; tests/agent/rag_context/test_authority_boundaries.py]
**Warning signs:** A business fact ref validates as `EvidenceRefV1`, or a business fact claim passes with only RAG/case memory/model context. [VERIFIED: tests/business/test_schemas.py; tests/agent/rag_context/test_authority_boundaries.py]

### Pitfall 4: Unsupported Catalog Business Reads Becoming Fake Facts

**What goes wrong:** `get_logistics` or `get_merchant_risk` appears planner-visible and produces placeholder facts/refs even though there is no current data-backed service support. [VERIFIED: src/tools/catalog.py; src/business/service.py]
**Why it happens:** The catalog declares these tools, but `BUSINESS_READ_TOOLS` only registers `get_order`, `get_refund_case`, and `get_ticket`. [VERIFIED: src/tools/catalog.py; src/business/service.py]
**How to avoid:** BusinessFactService should return typed unavailable results or hide/mark unavailable through ToolPlatform availability until actual data support exists. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**Warning signs:** A logistics or merchant-risk response has `status=ok/success`, facts, refs, or prompt summary text implying a resource exists. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

### Pitfall 5: Expanding Phase 30 Into Downstream Phases

**What goes wrong:** The plan tries to implement memory isolation, RAG claim verification, approval/action binding, replay hardening, DB/RLS, or real execution while doing BusinessFactService. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; .planning/ROADMAP.md]
**Why it happens:** Business facts are upstream of those later systems, so their tests are tempting to broaden. [VERIFIED: .planning/ROADMAP.md]
**How to avoid:** Add only boundary tests that prove those systems cannot substitute current facts; leave full hardening to Phase 31, 33, 34, 35, or 36+. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
**Warning signs:** Phase 30 tasks modify approval state machines, memory write policy, RAG verifier internals, replay visibility, or DB constraints without a spec delta. [VERIFIED: CLAUDE.md; .planning/ROADMAP.md]

## Code Examples

Verified patterns from official repo sources:

### Current Tool Boundary To Preserve

```python
# Source: src/tools/runtime.py
descriptor = self._catalog.descriptor(tool_name)
validate_json_value(args, descriptor.input_schema)
decision = self._policy_engine.runtime_auth(tool_name=tool_name, args=args, ctx=ctx)
if decision.decision == "denied":
    return safe_denial_result
tool_result = await executor.execute(tool_name, args, ctx)
projection = self._projector.project(tool_name=tool_name, result=tool_result, tool_call_id=ctx.tool_call_id)
```

This pattern means Phase 30 should change the business executor/service behind ToolRuntime, not bypass ToolRuntime gates. [VERIFIED: src/tools/runtime.py]

### Existing Investigate Fact Accumulation

```python
# Source: src/agent/nodes/investigate.py
if result.status == "success":
    if result.business_fact_refs:
        for ref in result.business_fact_refs:
            context["business_fact_refs"].append(ref.model_dump(mode="json"))
            context["facts"][ref.resource_type] = normalized
```

This pattern is acceptable only if Phase 30 ensures `result.business_fact_refs` can originate only from service-approved `BusinessFactResultV1`. [VERIFIED: src/agent/nodes/investigate.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

### Existing Raw Guard To Retire From Public Authority

```python
# Source: src/integrations/demo_business/authz.py
if user.role in PLATFORM_ADMIN_ROLES:
    return True
if user.role not in MERCHANT_BOUND_ROLES:
    return False
return user.merchant_id is not None and user.merchant_id == merchant_id
```

This guard matches Phase 29.5 role semantics, but Phase 30 should make it an implementation detail behind BusinessFactService rather than the graph/tool authority seam. [VERIFIED: src/integrations/demo_business/authz.py; .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-03-SUMMARY.md]

### No-Leak Assertion Shape

```python
# Source: tests/business/test_service.py
assert denied_result.status == "permission_denied"
assert denied_result.business_fact_refs == []
assert denied_result.data is None
assert "ORD-TEST-002" not in prompt_summary.prompt_summary
assert "ORD-TEST-002" not in context.model_dump_json()
```

Phase 30 should duplicate this no-leak shape for `BusinessFactResultV1`, ToolPlatform outcomes, graph `business_context`, and unsupported catalog business reads. [VERIFIED: tests/business/test_service.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

## State of the Art

| Old Approach | Current / Target Approach | When Changed | Impact |
|--------------|---------------------------|--------------|--------|
| Business reads return `ToolResultV2` directly from `BusinessToolService`. [VERIFIED: src/business/service.py] | BusinessFactService returns `BusinessFactResultV1`; tool results wrap service-approved facts for ToolPlatform compatibility. [VERIFIED: docs/contract-spec.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | Targeted for Phase 30. [VERIFIED: .planning/ROADMAP.md] | Planner should add schema/service tests before executor migration. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Raw demo integration functions prove ownership and emit raw error codes. [VERIFIED: src/integrations/demo_business/orders.py; src/business/adapters.py] | BusinessFactService owns domain ownership proof, freshness, result/ref projection, and no-leak semantics. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | Phase 29.5 added interim raw guards; Phase 30 replaces them as authority. [VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-03-SUMMARY.md] | Raw integrations may remain private adapters but must not be public authority. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| ToolPolicy marks domain identifiers but cannot enforce ownership proof. [VERIFIED: src/tools/policy.py] | BusinessFactService resolves `requires_domain_scope_check` before facts/refs are emitted. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | Targeted for Phase 30. [VERIFIED: .planning/ROADMAP.md] | Add regression proving the marker cannot remain annotation-only. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| Memory/RAG/case memory may appear near fact claims in graph context. [VERIFIED: src/agent/nodes/investigate.py; tests/agent/rag_context/test_authority_boundaries.py] | Memory and RAG remain contextual/policy systems and cannot prove current business facts. [VERIFIED: docs/contract-spec.md; tests/agent/rag_context/test_authority_boundaries.py] | Existing tests already cover part of this boundary; Phase 30 should add raw-row and denied-fact substitution cases. [VERIFIED: tests/agent/rag_context/test_authority_boundaries.py; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | Planner should use focused authority-boundary tests, not implement Phase 33 verifier work. [VERIFIED: .planning/ROADMAP.md] |

**Deprecated/outdated:**

- Treating `BusinessToolService` as the stable current fact authority is outdated for Phase 30; it may remain only as a tool-facing compatibility adapter. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
- Letting order/refund/ticket domain ownership proof live only in `src/integrations/demo_business/*` is an interim Phase 29.5 guard and should not remain the public service boundary. [VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-03-SUMMARY.md]
- Using `EvidenceRefV1` for business facts is forbidden by contract and existing tests. [VERIFIED: docs/contract-spec.md; tests/business/test_schemas.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Planner may choose either same-file or adjacent-module implementation for `BusinessFactService`. [ASSUMED from user discretion and context wording] | Recommended Project Structure | Low; context explicitly allows adjacent or same-file placement, but exact split should follow planner/edit complexity. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |

## Open Questions

1. **Should API routes call `BusinessFactService` in Phase 30, or only preserve current API semantics while tools migrate first?** [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - What we know: API routes may preserve Phase 29.5 HTTP 403/404 semantics, and shared fact projection/ref emission should be service-owned where practical. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - What's unclear: The phase context leaves exact route migration sequence to planning. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - Recommendation: Plan API migration as last/optional compatibility cleanup after service and ToolPlatform tests pass. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
2. **How should `stale` be produced for demo rows with no freshness/version metadata?** [VERIFIED: docs/contract-spec.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - What we know: `resource_version` and `data_freshness_at` may be nullable for MVP demo rows, but fields must exist. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - What's unclear: No current repository field appears to provide row version/freshness for all resources. [VERIFIED: src/integrations/demo_business/orders.py; src/integrations/demo_business/refunds.py; src/integrations/demo_business/tickets.py]
   - Recommendation: Add explicit null-value tests and simulate `stale` via adapter/service test doubles for action-bound fail-closed routing. [VERIFIED: docs/eval-test-plan.md; .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
3. **Should `get_logistics` and `get_merchant_risk` stay planner-visible while unavailable?** [VERIFIED: src/tools/catalog.py; src/business/service.py]
   - What we know: Catalog declares both tools, but the default business registry only supports order/refund/ticket. [VERIFIED: src/tools/catalog.py; src/business/service.py]
   - What's unclear: The context allows unavailable or typed reads according to existing data support. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
   - Recommendation: Return typed unavailable `BusinessFactResultV1` with no facts/refs and test that prompt summaries do not imply data exists; hide only if ToolPlatform availability semantics become simpler to maintain. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Test and lint commands | Yes [VERIFIED: command -v uv] | 0.11.2 via shell; `uv run` project env active [VERIFIED: uv --version] | None needed. |
| Python | Runtime/test environment | Yes [VERIFIED: uv run python] | 3.12.13 inside `uv run`; system `python3` is 3.13.3 [VERIFIED: local commands] | Use `uv run` because project requires `>=3.12` and test env resolved 3.12.13. [VERIFIED: pyproject.toml] |
| PostgreSQL server | DB-backed tests | Yes by evidence: focused DB tests created/used `moca_test` and passed. [VERIFIED: focused pytest command] | CLI `psql`/`pg_isready` not installed; asyncpg connection works. [VERIFIED: command -v psql; focused pytest command] | Use test fixture `_ensure_test_database`; no CLI fallback required. [VERIFIED: tests/conftest.py] |
| pytest | Validation | Yes [VERIFIED: uv run pytest --version] | 9.0.3 [VERIFIED: uv run pytest --version] | None. |
| ruff | Lint | Yes [VERIFIED: uv run ruff --version] | 0.15.12 [VERIFIED: uv run ruff --version] | None. |

**Missing dependencies with no fallback:** None identified for Phase 30 planning/execution. [VERIFIED: focused pytest command; local environment commands]

**Missing dependencies with fallback:** `psql` and `pg_isready` CLIs are missing, but tests use asyncpg and passed without those CLIs. [VERIFIED: command -v psql; tests/conftest.py; focused pytest command]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0 [VERIFIED: uv run pytest --version; uv run python] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py -q --tb=short` [VERIFIED: existing test files] |
| Full phase-focused command | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` [VERIFIED: focused pytest command] |
| Current focused result | `143 passed, 1 warning in 78.20s` [VERIFIED: focused pytest command] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APF-08 | `BusinessFactResultV1` strict schema includes status, fact, refs, resource_version, data_freshness_at, source_system, scope_check_result, missing_required_facts, safe_errors. [VERIFIED: docs/contract-spec.md] | unit | `uv run pytest tests/business/test_schemas.py -q --tb=short` | Existing file; new tests needed. [VERIFIED: tests/business/test_schemas.py] |
| APF-08 | Same-merchant allow, cross-merchant no-leak deny, cross-tenant fail-closed, missing merchant deny, unknown role deny, admin cross-merchant allow through `BusinessFactService`. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | service/integration | `uv run pytest tests/business/test_service.py -q --tb=short` | Existing file; new service class tests needed. [VERIFIED: tests/business/test_service.py] |
| APF-08 | `BusinessToolExecutor` delegates business reads to `BusinessFactService` and wraps service-approved results to `ToolResultV2`. [VERIFIED: src/tools/executors/business.py] | unit/integration | `uv run pytest tests/tools/test_tool_platform.py tests/business/test_service.py -q --tb=short` | Existing files; new tests needed. [VERIFIED: tests/tools/test_tool_platform.py] |
| APF-08 | `requires_domain_scope_check` cannot remain annotation-only for order/refund/ticket identifiers. [VERIFIED: src/tools/policy.py] | integration/static | `uv run pytest tests/tools/test_tool_platform.py -q --tb=short` | Existing file; new enforcement tests needed. [VERIFIED: tests/tools/test_tool_platform.py] |
| APF-08 | No memory/RAG/LLM/raw repository row can substitute missing/denied business facts. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] | authority boundary | `uv run pytest tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` | Existing files; add raw-row substitution assertions. [VERIFIED: tests/agent/rag_context/test_authority_boundaries.py; tests/agent/test_policy_retrieval_ownership.py] |
| APF-08 | `permission_denied`, `stale`, and `unavailable` fail closed for action-bound paths. [VERIFIED: docs/contract-spec.md; docs/eval-test-plan.md] | graph/service route | `uv run pytest tests/agent/test_nodes/test_investigate.py tests/business/test_service.py -q --tb=short` | Existing files; add stale/unavailable BusinessFactResult tests. [VERIFIED: tests/agent/test_nodes/test_investigate.py] |

### Sampling Rate

- **Per task commit:** Run the quick business suite and any directly touched focused test file. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
- **Per wave merge:** Run the full phase-focused command above. [VERIFIED: focused pytest command]
- **Phase gate:** Run the full phase-focused command plus `uv run ruff check <changed files>`; whole suite is recommended before `/gsd-verify-work` because Phase 29.5 ended with a whole-suite gate. [VERIFIED: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-06-SUMMARY.md]

### Wave 0 Gaps

- [ ] `tests/business/test_schemas.py` — add `BusinessFactResultV1` strict schema/status/null-field tests for APF-08. [VERIFIED: docs/contract-spec.md]
- [ ] `tests/business/test_service.py` — add `BusinessFactService` public method tests, no-leak denial, unsupported logistics/risk, invalid adapter response, timeout/unavailable, and stale fixtures/test doubles. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md]
- [ ] `tests/tools/test_tool_platform.py` — add ToolPlatform -> BusinessToolExecutor -> BusinessFactService delegation and `requires_domain_scope_check` enforcement tests. [VERIFIED: src/tools/policy.py; src/tools/executors/business.py]
- [ ] `tests/agent/test_nodes/test_investigate.py` — add graph accumulation tests for service-approved refs only and stale/unavailable fail-closed action-bound context. [VERIFIED: src/agent/nodes/investigate.py; docs/eval-test-plan.md]
- [ ] `tests/agent/rag_context/test_authority_boundaries.py` or `tests/agent/test_policy_retrieval_ownership.py` — add raw repository row / prompt summary substitution negative tests. [VERIFIED: tests/agent/rag_context/test_authority_boundaries.py; tests/agent/test_policy_retrieval_ownership.py]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not disable `security_enforcement`. [VERIFIED: .planning/config.json]

OWASP ASVS 5.0.0 is the latest stable ASVS version dated May 2025, and OWASP recommends versioned requirement identifiers because identifiers can change between versions. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | Yes | Do not accept identity/scope from LLM, user payload, memory, checkpoint, frontend payload, or tool args; use TrustedContextFactory-derived identity only. [VERIFIED: docs/contract-spec.md; src/platform/trusted_context.py] |
| V3 Session Management | Yes | Same-thread/session context may provide continuity but cannot satisfy current business fact or action authority; stale/inherited slots must reload current business context for action-bound paths. [VERIFIED: docs/contract-spec.md] |
| V4 Access Control | Yes | Enforce merchant-bound role matrix in BusinessFactService before facts/refs are emitted; admin is the only platform-wide human business-data role. [VERIFIED: docs/contract-spec.md; src/platform/trusted_context.py] |
| V5 Input Validation | Yes | Keep ToolRuntime schema validation before runtime auth resource binding; validate BusinessFactResultV1/BusinessContextV1 with Pydantic `extra="forbid"`. [VERIFIED: src/tools/runtime.py; src/business/schemas.py] |
| V6 Cryptography | No new cryptography | Phase 30 does not introduce encryption/hashing; preserve existing evidence/business ref separation and do not hand-roll crypto. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md] |
| V8 Error Handling and Logging | Yes | Service/tool denials and adapter failures must use safe errors without raw adapter messages, resource existence leaks, or secrets. [VERIFIED: docs/contract-spec.md; src/business/adapters.py; tests/business/test_adapters.py] |
| V9 Data Protection | Yes | Raw business rows, raw adapter payloads, PII, and denied resource facts must not enter prompt, graph state, or conversation tool summaries. [VERIFIED: src/tools/projection.py; tests/tools/test_tool_platform.py; tests/agent/test_nodes/test_investigate.py] |

### Known Threat Patterns for MOCA Business Facts

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-merchant identifier probing through `order_no` / `refund_case_no` / `ticket_id` | Information Disclosure | Generic `permission_denied`, no refs/facts, and no resource-specific prompt/error text before scope proof. [VERIFIED: docs/contract-spec.md; tests/business/test_service.py] |
| Trusting forged role or user context | Spoofing / Elevation of Privilege | Use TrustedContextFactory / ToolCallContext projection; raw demo authz also verifies DB user id, tenant, active status, and role match. [VERIFIED: src/platform/trusted_context.py; src/integrations/demo_business/authz.py] |
| RAG/memory/model substitution for current facts | Tampering / Information Disclosure | Require BusinessFactRefV1 for business fact claims; keep memory/case memory contextual and policy evidence separate. [VERIFIED: docs/contract-spec.md; tests/agent/rag_context/test_authority_boundaries.py] |
| Raw adapter payload leakage | Information Disclosure | Strict adapter projection, invalid response discard, ToolResultProjector raw sentinel stripping, and graph projection-only accumulation. [VERIFIED: src/business/adapters.py; src/tools/projection.py; tests/tools/test_tool_platform.py] |
| Unsupported business read treated as success | Tampering / Repudiation | Typed unavailable result with no facts/refs and decision/event trace through ToolPlatform. [VERIFIED: src/tools/catalog.py; src/business/service.py; docs/eval-test-plan.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - locked decisions, discretion, deferred scope, and required Phase 30 outcomes.
- `.planning/REQUIREMENTS.md` - APF-08 requirement.
- `.planning/ROADMAP.md` - Phase 30 goal, success criteria, dependency on Phase 29.5, and downstream phase assignments.
- `.planning/STATE.md` - milestone state and Phase 29.5 completion context.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` and `29.5-01..06-SUMMARY.md` - merchant-bound role semantics and implemented handoff.
- `.planning/todos/deferred/2026-06-27-merchant-scope-businessfactservice.md` - Phase 30 required outcomes.
- `docs/contract-spec.md` - normative module ownership, TrustedContext, BusinessFactResultV1, BusinessContextV1, ToolResultV2, BusinessFactRefV1, and memory/authority boundaries.
- `docs/target-agent-platform-architecture-plan.md` - modular monolith boundary principles and BusinessFactService target API.
- `docs/eval-test-plan.md` - business fact contract cases and forbidden behavior expectations.
- `src/business/service.py`, `src/business/schemas.py`, `src/business/adapters.py`, `src/tools/*`, `src/agent/nodes/investigate.py`, and demo business integration files - current implementation evidence.
- Listed tests under `tests/business`, `tests/tools`, `tests/agent/test_nodes`, and authority-boundary tests - current validation evidence.
- Focused pytest command result: `143 passed, 1 warning in 78.20s`.

### Secondary (MEDIUM confidence)

- OWASP ASVS official project page and GitHub README - ASVS 5.0.0 latest stable version and requirement identifier guidance. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - verified from `pyproject.toml` and local `uv run` commands. [VERIFIED: pyproject.toml; local commands]
- Architecture: HIGH - locked by project context, contract spec, target architecture doc, and current code. [VERIFIED: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md; docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]
- Pitfalls: HIGH - derived from existing tests, deferred todo, and current implementation seams. [VERIFIED: tests/business/test_service.py; src/tools/policy.py; .planning/todos/deferred/2026-06-27-merchant-scope-businessfactservice.md]
- Security: MEDIUM - MOCA-specific controls are verified locally; ASVS category currency was checked against official OWASP sources but exact ASVS requirement IDs were not mapped in this research. [VERIFIED: docs/contract-spec.md; CITED: https://owasp.org/www-project-application-security-verification-standard/]

**Research date:** 2026-06-28 [VERIFIED: date command]
**Valid until:** 2026-07-05 for security/ASVS version references and 2026-07-28 for repository-bound implementation findings unless Phase 30 code changes land sooner. [ASSUMED]
