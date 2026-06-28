# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [x] **v1.1 Agent Architecture Migration** - Shipped on 2026-06-17. Full archive: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [x] **v1.2 Long-term / Case Memory** - Shipped on 2026-06-17. Scope: Phase 16.
- [x] **v1.3 RAG Hybrid Retrieval** - Shipped on 2026-06-18. Full archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- [x] **v1.4 RAG Production Ingestion + OCR** - Shipped on 2026-06-19. Full archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- [x] **v1.5 RAG Context Builder + Hallucination Control** - Shipped on 2026-06-19. Full archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- [x] **v1.6 RAG Reranker + Query Rewrite** - Shipped on 2026-06-20. Full archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- [x] **v1.7 Short-term Memory Unification** - Completed on 2026-06-20. Goal: complete the short-term memory chain for the current Agent Console `/api/v1/agent-runs + SSE` path.
- [x] **v1.8 Intent Routing Safety Hardening** - Completed on 2026-06-21. Goal: harden ordinary-chat intent/routing traceability, risk tiering, workflow-state-first routing, and slot invalidation.
- [ ] 🚧 **v1.9 Agent Platform Foundation** - Started on 2026-06-22. Goal: turn MOCA into a microservice-ready modular monolith with trusted context, decision events, platform service boundaries, target graph contracts, deterministic RAG context build, claim verification, and safe approval/action draft boundaries.

## Phases

<details>
<summary>Shipped phases through v1.8</summary>

- v1.0 MVP: Phases 1-6
- v1.1 Agent Architecture Migration: Phases 7-15.2
- v1.2 Long-term / Case Memory: Phase 16
- v1.3 RAG Hybrid Retrieval: Phase 20
- v1.4 RAG Production Ingestion + OCR: Phase 21
- v1.5 RAG Context Builder + Hallucination Control: Phase 22
- v1.6 RAG Reranker + Query Rewrite: Phase 23
- v1.7 Short-term Memory Unification: Phase 24
- v1.8 Intent Routing Safety Hardening: Phase 25

</details>

<details>
<summary>Detailed shipped Phase 24 record</summary>

### Phase 24: Agent Runs Short-term Memory Parity

**Status:** Complete
**Milestone:** v1.7 Short-term Memory Unification
**Requirements:** STM-01, STM-02, STM-03, STM-04, STM-05, STM-06, STM-07, STM-08, STM-09, STM-10, STM-11, STM-12, STM-13, STM-14
**Plans:** 9/9 plans complete

**Goal:** Make the current `/api/v1/agent-runs + SSE` path persist and consume the same short-term memory surfaces expected by Agent Console follow-up turns: conversation messages, prompt-safe tool summaries, rolling thread summaries, and PostgreSQL-backed session slots.

**Success criteria:**

1. `/api/v1/agent-runs` creates or resolves a conversation thread, persists exactly one user message per submitted query, and passes trusted conversation identifiers into graph execution.
2. Completed runs persist exactly one assistant message and update the rolling thread summary from committed messages and eligible prompt-safe tool summaries.
3. Follow-up runs can load recent messages, latest prior rolling summary, prompt-safe tool summaries, and session slot memory into prompt context.
4. Explicit current-turn slots override inherited trusted session slots, and stale or scope-mismatched inherited memory fails closed.
5. Error, cancelled, approval-interrupted, retried, and re-opened stream states are idempotent and do not produce false completed summaries or duplicated records.
6. Memory surfaces remain contextual only and cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth.
7. Regression tests and an integration or live smoke flow prove a three-turn Agent Console conversation can use both slot continuity and rolling-summary context.

Plans:
- [x] 24-01-PLAN.md — Wave 0 API/SSE RED scaffolding for create, config, finalizer, retry, and smoke behavior
- [x] 24-02-PLAN.md — Wave 0 prompt context, session slot, prompt-safety, and authority-boundary RED scaffolding
- [x] 24-03-PLAN.md — DB-backed idempotency indexes and blocking Alembic verification
- [x] 24-04-PLAN.md — Shared conversation and rolling-summary idempotency helpers
- [x] 24-05-PLAN.md — `/agent-runs` user-message creation and trusted SSE graph config
- [x] 24-06-PLAN.md — Completed-run assistant, summary, and bounded session-memory finalizer
- [x] 24-07-PLAN.md — Error/cancel/interruption and retry/reopen completed-only safeguards
- [x] 24-08-PLAN.md — Prompt-context parity and memory authority-boundary protections
- [x] 24-09-PLAN.md — Legacy compatibility, focused regression, and three-turn smoke

</details>

## Current Status

v1.9 is active. The milestone uses `docs/contract-spec.md` and `docs/target-agent-platform-architecture-plan.md` as the planning baseline for agent platform foundations: canonical trusted context, decision event envelope, tool policy decisions, memory context boundaries, target graph vocabulary, deterministic RAG context build, claim verification, business fact authority, and approval/action draft hardening.

## Requirement Coverage

| Requirement | Phase | Coverage |
|-------------|-------|----------|
| APF-01 | Phase 26 | Contract/spec/eval baseline alignment |
| APF-02 | Phase 26 | Module ownership and dependency boundaries |
| APF-03 | Phase 27 | Canonical TrustedContext factory |
| APF-04 | Phase 27 | Service-safe context projections |
| APF-05 | Phase 28 | Decision event envelope and emitter foundation |
| APF-06 | Phase 29 | ToolView planner projection |
| APF-07 | Phase 29 | ToolPolicyDecision runtime authorization |
| MER-01 | Phase 29.5 | Merchant-bound role and business-data scope alignment |
| APF-08 | Phase 30 | BusinessFactResultV1 domain service facade |
| APF-09 | Phase 31 | SessionContextMemory projection |
| APF-10 | Phase 31 | Memory layer and authority separation |
| APF-11 | Phase 32 | Target graph vocabulary migration |
| APF-12 | Phase 32 | Intent and slot policy registries |
| APF-13 | Phase 33 | VerifiedEvidencePackageV1 and route_after_rag_context |
| APF-14 | Phase 33 | MaterialClaimV1 and ClaimVerificationBundleV1 |
| APF-15 | Phase 34 | Structured action proposal / draft binding |
| APF-16 | Phase 34 | Risk vs approval gate responsibility split |
| APF-17 | Phase 35 | Replay/trace coverage for platform decisions |
| APF-18 | Phase 35 | Dev/release/monitoring eval gates |

## Latest Phase Closeout

Phase 29 review, UAT, security, and validation are recorded in `.planning/phases/29-tool-platform-boundary/29-REVIEW.md`, `.planning/phases/29-tool-platform-boundary/29-UAT.md`, `.planning/phases/29-tool-platform-boundary/29-SECURITY.md`, and `.planning/phases/29-tool-platform-boundary/29-VALIDATION.md`. Phase 29.5 has been inserted before Phase 30 to lock merchant-bound role and business-data scope semantics before BusinessFactService planning.

## Deferred Work

- **17-prep: AgentState Surface Contracts + Authority Isolation** - preserved as `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md`; future candidate only if Phase 17 is reintroduced.
- **Phase 17: External Action Execution** - not active. Possible future scope: external execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards, and real side effects.
- **post-Phase 17 Policy Scope** - tenant-over-global global/default policy fallback and precedence merge.
- **Phase RAG-5: Optional External Search Backend** - Vespa/OpenSearch shadow testing and full external `SearchBackend` only if PostgreSQL hybrid no longer fits.
- **Policy Source Operations** - policy source upload/review/lifecycle UI, source document viewer, and admin review workflow.
- **Merchant scope deferred routing from Phase 29.5** - AgentRun, Approval, ActionDraft, Memory, Replay, and DB hardening merchant-scope follow-ups are indexed under `.planning/todos/deferred/2026-06-27-merchant-scope-*.md` and must be consumed by Phases 30-35 or Phase 36+ as assigned.

<details>
<summary>Detailed shipped Phase 24.2-25 records</summary>

### Phase 24.2: Unified Session Memory Bundle Read Path (INSERTED)

**Status:** Complete
**Goal:** Make `SessionMemoryBundle` the graph-facing session read model for rolling summary, recent messages, tool summaries, and slot continuity while preserving the existing `session_memory` slot-continuity contract.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.2-01-PLAN.md — Unified session memory bundle read path

### Phase 24.3: Memory Write Isolation Policy and Observability MVP (INSERTED)

**Status:** Complete
**Goal:** Extract and enforce the rule that memory side effects must not rollback or otherwise contaminate the main business transaction, and add minimal safe trace metrics for finalizer memory writes.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.3-01-PLAN.md — Memory write isolation policy and observability MVP

### Phase 24.4: Memory Eval MVP (INSERTED)

**Status:** Complete
**Goal:** Create a focused deterministic pytest suite that acts as MOCA's first memory quality gate for short-term recall, slot expiry, tombstone forgetting, and authority contamination.
**Requirements**: Memory consolidation follow-up
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 24.4-01-PLAN.md — Memory eval MVP

### Phase 25: Intent routing safety hardening

**Status:** Complete
**Milestone:** v1.8 Intent Routing Safety Hardening
**Goal:** Harden the ordinary-chat intent/routing contract so raw LLM classification remains advisory, deterministic policy produces effective classification/risk/route decisions, active workflow state can answer pending clarification turns before reclassification, and inherited slots can be traced and invalidated safely.
**Requirements:** IRS-01, IRS-02, IRS-03, IRS-04, IRS-05, IRS-06, IRS-07, IRS-08, IRS-09, IRS-10, IRS-11, IRS-12
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

**Success criteria:**

1. Trace output clearly distinguishes raw LLM classification, deterministic pre-route, policy overrides, effective classification, risk tier, and final route.
2. Risk policy can classify read-only, draft, suggestion, approval-required, and ordinary-chat-forbidden requests from intent/operation/role/channel inputs.
3. Pending clarification state can consume short identifier replies before ordinary intent classification, while unsafe short approvals or "continue" replies fail closed.
4. Slot metadata includes trusted provenance and deterministic invalidation prevents stale order/refund/ticket identifiers from satisfying required slots.
5. Golden/focused regression tests cover effective classification, route, risk tier, clarification reason, and memory inheritance/invalidation outcomes without weakening existing authority boundaries.

Plans:
- [x] 25-01-PLAN.md — Intent routing safety hardening

</details>

### v1.9 Agent Platform Foundation

### Phase 26: Architecture Contract Baseline

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Close the architecture/spec/eval baseline so target service boundaries, graph vocabulary, RAG/claim state fields, tool policy decisions, business fact results, and decision events are aligned before implementation phases.
**Requirements**: APF-01, APF-02
**Depends on:** Phase 25
**Plans:** 1/1 plans complete

**Success Criteria**:

1. `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and `docs/eval-test-plan.md` agree on target graph nodes/routers, AgentState fields, and platform schema names.
2. Module ownership boundaries identify schema/table/event ownership, allowed downstream calls, and forbidden imports for every platform/domain service in scope.
3. The phase records any remaining legacy alias mappings and confirms no implementation phase can introduce new fields/nodes without spec delta.

Plans:
- [x] 26-01-PLAN.md — Architecture contract baseline

### Phase 27: TrustedContextFactory and Projections

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Make canonical trusted identity/scope/run context and service-specific projections the shared foundation for tool, knowledge, memory, approval, replay, and intent policy.
**Requirements**: APF-03, APF-04
**Depends on:** Phase 26
**Plans:** 3/3 plans complete

**Success Criteria**:

1. Canonical `TrustedContext` is produced only from trusted API/auth/run boundaries and matches `contract-spec.md` §8.0.
2. Projection APIs expose `ToolCallContext`, `KnowledgeContext`, `MemoryContext`, `ApprovalContext`, `ReplayContext`, and intent policy context without widening identity/scope fields.
3. Tests prove `request_id`, `effective_at`, `channel`, and policy/model/tool versions remain projection-local or metadata, not canonical trusted identity.

Plans:
- [x] 27-01-PLAN.md — Wave 0 trusted-context and projection RED tests
- [x] 27-02-PLAN.md — Platform trusted-context contracts and read-only registries
- [x] 27-03-PLAN.md — Current seam migrations and focused integration gates

### Phase 28: Decision Event Foundation

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Establish the minimal decision event envelope, reason-code convention, redaction policy, and emitter foundation used by later platform services.
**Requirements**: APF-05
**Depends on:** Phase 27
**Plans:** 1/1 plans complete

**Success Criteria**:

1. `DecisionEventEnvelopeV1` maps to the existing minimal event envelope and does not create a parallel replay event format.
2. Event emission records run/tenant/thread/trace identity, operation id, reason codes, policy/model/tool versions, redaction policy, and prompt-safe payload references.
3. Contract tests cover ordering, redaction, missing required fields, and service-level event payload extension.

Plans:
- [x] 28-01-PLAN.md — Decision event foundation

### Phase 29: Tool Platform Boundary

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Replace scattered tool allowlists with descriptor-driven planner views, runtime authorization, result projection, and decision events.
**Requirements**: APF-06, APF-07
**Depends on:** Phase 28
**Plans:** 4/4 plans complete

**Success Criteria**:

1. Planner-visible tools are exposed as prompt-safe `ToolView` projections derived from `ToolDescriptor`.
2. Runtime invocation rechecks `ToolPolicyDecision` for caller, permission, resource scope, side-effect class, and schema validation.
3. Tests prove visible does not imply allowed, hidden/write tools do not leak into planner prompts, and raw adapter payloads stay out of graph state.

Plans:
- [x] 29-01-PLAN.md — Wave 0 tool platform RED tests
- [x] 29-02-PLAN.md — Tool contracts, policy engine, and replay event registration
- [x] 29-03-PLAN.md — Tool runtime, platform facade, and result projector
- [x] 29-04-PLAN.md — Manager, investigate, conversation integration, and final gates

### Phase 29.5: Merchant Scope / Role Model Alignment (INSERTED)

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Align MOCA's single-tenant MVP identity model so `support`, `manager`, and legacy `merchant` are merchant-bound business users, `admin` is the only platform-wide business-data role, and tenant public policy remains readable by ordinary business users.
**Requirements**: MER-01
**Depends on:** Phase 29
**Plans:** 6/6 plans complete

**Success Criteria**:

1. `support`, `manager`, and legacy `merchant` are defined as `merchant_bound_roles`; `admin` is defined as the only `platform_admin_roles` member for business data scope.
2. `docs/contract-spec.md` contains the normative role-to-merchant-scope policy, including unknown role deny-all and business-scope vs tenant-public-policy separation; Phase 29.5 reconciles old contract text, current code, tests, and the accepted MER-01 product model rather than treating historical contract text as automatically correct.
3. `TrustedContextFactory` generates merchant scope from trusted user role and `merchant_id`: merchant-bound users get `[merchant_id]` or deny-all `[]`; `admin` gets `["*"]`.
4. `server_merchant_scope` cannot widen a non-admin human actor to wildcard and wildcard override is rejected rather than silently narrowed; `server_tool_permissions` cannot expand merchant scope; system-owned wildcard scope remains deferred until a separate `TrustedSystemContext` exists.
5. Order, RefundCase, and Ticket APIs use a unified merchant access helper with 404 for cross-tenant resources and 403 for same-tenant out-of-merchant-scope or missing merchant binding; current order/refund/ticket tool/raw business reads enforce the same merchant-bound interim guard and denied reads do not emit `BusinessFactRefV1`.
6. Tenant public policy retrieval remains available to authenticated ordinary business users with `knowledge:read`, including deny-all business scope `[]`; business merchant scope must not be misused as a tenant-public policy filter, while business-scoped policy filters and business data still fail closed.
7. Manager approval list/get/decide and approval resume no longer retain tenant-wide visibility or wildcard merchant scope; Phase 29.5 uses admin-only / fail-closed interim behavior and does not implement a `requested_by -> user.merchant_id` approximation until Phase 34 target merchant binding exists.
8. Manager AgentRun status/evidence/trace access no longer remains tenant-wide; ghost supervisor roles such as `supervisor` / `approval_manager` do not grant business-data run visibility; business run details are owner/admin-only until Phase 32/35 can prove same-merchant access.
9. Seed/demo data and tests cover at least two merchants with `support` + `manager`, admin cross-merchant access, legacy merchant compatibility, tenant isolation, and merchant isolation.
10. AgentRun, Approval, ActionDraft, Memory, Replay, and DB hardening merchant-scope work is explicitly deferred to the assigned Phase 30-35 or Phase 36+ entries with interim guards where needed; no graph/tool fallback outside `TrustedContextFactory` may fabricate wildcard business merchant scope.

Plans:
- [x] 29.5-01-PLAN.md — Traceability, contract, seed, and fixture alignment
- [x] 29.5-02-PLAN.md — TrustedContextFactory and merchant access helper
- [x] 29.5-03-PLAN.md — Order, refund, and ticket API/tool merchant guards
- [x] 29.5-04-PLAN.md — Policy-only knowledge scope and memory smoke guard
- [x] 29.5-05-PLAN.md — Approval, AgentRun, trace, replay, and investigate interim guards
- [x] 29.5-06-PLAN.md — Static wildcard guard and final focused verification

**Verification:** Phase 29.5 final gate passed on 2026-06-27: focused suite `341 passed`, whole suite `1590 passed, 1 skipped`, static wildcard guard passed, and `git diff --check` passed.

### Phase 30: BusinessFactService Boundary

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Make current business facts available only through stable domain service public methods and `BusinessFactResultV1` / `BusinessFactRefV1` contracts.
**Requirements**: APF-08
**Depends on:** Phase 29.5
**Plans:** 3/3 plans complete

**Success Criteria**:

1. Order, refund, ticket, logistics, and merchant-risk reads project to `BusinessFactResultV1` with status, freshness, scope check, resource version, refs, and safe errors.
2. Graph/tool code cannot use memory, RAG, LLM inference, or raw repository rows as current business fact authority.
3. Tests cover permission denied no-leak behavior, stale/unavailable fail-closed routes for action-bound paths, and no `EvidenceRefV1`/`BusinessFactRefV1` mixing.
4. Business fact reads consume Phase 29.5 merchant scope semantics: `support` / `manager` / legacy `merchant` are merchant-bound, `admin` is platform-wide, and order/refund/ticket identifiers require domain ownership proof before `BusinessFactRefV1` is emitted.
5. Tool/service `permission_denied` is no-leak and must not expose whether an out-of-scope resource exists; `BusinessFactRefV1`, prompt summaries, and graph facts are emitted only after scope checks pass.
6. ToolPlatform `requires_domain_scope_check` markers for order/refund/ticket identifiers are resolved by BusinessFactService and cannot remain as non-enforced annotations.

Plans:
- [x] 30-01-PLAN.md — Domain contract and BusinessFactService service boundary
- [x] 30-02-PLAN.md — Compatibility and ToolPlatform business executor integration
- [x] 30-03-PLAN.md — Projection, graph authority boundaries, and focused verification

### Phase 31: Memory Platform Boundary

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Separate session context, long-term memory, case memory, conversation log, workflow checkpoint, working state, and memory write policy behind clear memory service APIs.
**Requirements**: APF-09, APF-10
**Depends on:** Phase 30
**Plans:** 6/6 plans complete

**Success Criteria**:

1. `SessionContextMemory` becomes the agent-facing same-thread projection, while `SessionContinuityStore` remains an internal storage concern.
2. Memory context loading distinguishes early session context for intent from post-slot long-term/case memory bundles.
3. Tests prove memory cannot satisfy policy evidence, current business fact, approval/action snapshot, or replay truth requirements.
4. Memory load/write policy preserves Phase 29.5 merchant boundaries so one merchant's conversation, case, or long-term memory cannot contaminate another merchant's prompt context.

Plans:
- [x] 31-01-PLAN.md — Wave 0 session-context and authority-boundary RED tests
- [x] 31-02-PLAN.md — Wave 0 reviewed-memory scope and write-policy RED tests
- [x] 31-03-PLAN.md — Memory context DTOs and facade contracts
- [x] 31-04-PLAN.md — SessionContextMemory graph-facing node and compatibility aliases
- [x] 31-05-PLAN.md — Reviewed memory trusted-scope retrieval boundary
- [x] 31-06-PLAN.md — Memory write decision status and final authority verification

### Phase 32: Intent Graph Migration

**Status:** Complete
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Migrate the graph toward target canonical safety, session context, contextual intent, slot resolution, and memory context nodes while preserving legacy compatibility.
**Requirements**: APF-11, APF-12
**Depends on:** Phase 31
**Plans:** 5/5 plans complete

**Success Criteria**:

1. Legacy `intent_classification`, `session_memory_load`, `route_after_intent`, and `route_after_slots` behavior maps to target canonical node/router names in trace/eval projections.
2. `IntentPolicyRegistry` and `SlotPolicyRegistry` own effective route and slot inheritance decisions; LLM output remains candidate-only.
3. Router totality tests cover safety pre-route, low confidence, direct response, slot required, missing/stale/incompatible slots, and memory context load paths.
4. AgentRun and graph routing work records how target merchant context is resolved or deferred, and manager/supervisor-style access must not remain implicitly tenant-wide without target merchant or business fact refs.

Plans:
- [x] 32-01-PLAN.md — Graph vocabulary and projection helper
- [x] 32-02-PLAN.md — Intent policy registry consumption
- [x] 32-03-PLAN.md — Slot policy gate and target router projection
- [x] 32-04-PLAN.md — Trace/eval/API and target merchant-context evidence
- [x] 32-05-PLAN.md — Final focused verification and no Phase 33 scope creep

### Phase 33: RAG Context Build and Claim Verification

**Status:** Pending
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Split RAG into investigate-time candidate retrieval, deterministic verified evidence package construction, and post-generation claim verification.
**Requirements**: APF-13, APF-14
**Depends on:** Phase 32
**Plans:** 0/1 plans complete

**Success Criteria**:

1. `rag_context_build` produces `VerifiedEvidencePackageV1`, status, citation map, evidence map, projections, and rejected/stale/conflict refs.
2. `claim_verify` consumes `MaterialClaimV1` and outputs `ClaimVerificationBundleV1` with rules-first support, safe refs, blocked claims, and fail-closed high-risk behavior.
3. Tests prove candidate refs do not enter prompt/action directly, invalid scope/hash fails closed, unsupported action recommendations cannot reach risk/approval/action, and business fact claims require `BusinessFactRefV1`.
4. Tenant public policy remains separate from business merchant scope, while business fact and action recommendation claims require merchant-scoped `BusinessFactRefV1` authority.

Plans:
- [ ] 33-01-PLAN.md — RAG context build and claim verification

### Phase 34: Approval and ActionDraft Boundary Hardening

**Status:** Pending
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Bind action proposals, approval decisions, and action drafts to verified facts/evidence/claims/risk/snapshots while preserving the no-real-execution boundary.
**Requirements**: APF-15, APF-16
**Depends on:** Phase 33
**Plans:** 0/1 plans complete

**Success Criteria**:

1. Action proposals and drafts bind structured payloads to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots.
2. `risk_gate` owns blocked/approval-required/auto-draft routing, while `approval_gate` only executes approval plan, trusted resume, interrupt, and revision state machine behavior.
3. Tests prove ordinary chat cannot forge approval/action authority, payload changes invalidate old approval, and no full real external execution is introduced.
4. ApprovalRequest and ActionDraft bind target merchant or scoped `BusinessFactRefV1`; manager approval queues and resume paths cannot use wildcard `server_merchant_scope` unless the actor is `admin`.
5. Any future system-owned wildcard approval/action job must use a separate trusted system context contract, not `TrustedContextFactory.create_from_request(user=...)`.

Plans:
- [ ] 34-01-PLAN.md — Approval and ActionDraft boundary hardening

### Phase 35: Replay and Eval Hardening

**Status:** Pending
**Milestone:** v1.9 Agent Platform Foundation
**Goal:** Close observability and eval coverage for the new platform boundaries so future implementation phases can be judged by deterministic contract gates.
**Requirements**: APF-17, APF-18
**Depends on:** Phase 34
**Plans:** 0/1 plans complete

**Success Criteria**:

1. Platform decisions for context projection, intent/slot policy, memory load/write, tool visibility/auth, RAG validation, claim verification, risk/approval, and action draft produce replayable event coverage.
2. Eval gates distinguish dev-contract, release, and monitoring gates and cover forbidden behavior for scope leaks, unsupported claims, unsafe action paths, and raw payload exposure.
3. Final milestone verification proves all APF requirements are mapped, tested, and documented without implementing physical microservices or full real execution.
4. Replay, trace, and eval views preserve Phase 29.5 merchant scope boundaries and prove no cross-merchant leakage through run listing, trace detail, tool result records, approval views, memory, or replay artifacts.

Plans:
- [ ] 35-01-PLAN.md — Replay and eval hardening

## Backlog

### Phase 999.1: Evaluate mem0 Memory Backend Spike (BACKLOG)

**Status:** Backlog
**Goal:** Spike whether mem0 can serve as an optional backend behind `MemoryContextService` for reviewed long-term/case memory only.
**Requirements:** TBD
**Plans:** 0 plans

**Success Criteria**:

1. Evaluation treats mem0 only as a backend candidate behind a MOCA adapter; agents must not call mem0 directly.
2. mem0 is not used for session context and must not become evidence, business fact, approval/action, material-claim, or replay authority.
3. Adapter design requires tenant, merchant, user, thread, and case filters derived from trusted MOCA context before any read/write.
4. Writes must pass through `MemoryWriteDecisionV2`; retrieved items must be projected as `ReviewedMemoryRef(authority_class="contextual_only")`.
5. Spike explicitly verifies tombstone, supersede, review status, PII, merchant isolation, and replay/audit boundary implications before promotion.

Plans:
- [ ] TBD (promote with `$gsd-review-backlog` when ready)

---
*Updated: 2026-06-27 after inserting Phase 29.5 Merchant Scope / Role Model Alignment.*
