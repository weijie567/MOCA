# Requirements: MOCA v1.9 Agent Platform Foundation

**Defined:** 2026-06-22
**Milestone:** v1.9 Agent Platform Foundation

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure any risky action goes through approval before execution -- never silently executing something irreversible.

## Milestone Goal

Turn MOCA's agent runtime into a microservice-ready modular monolith: platform/domain services expose stable public contracts, graph nodes orchestrate through those services, trusted context and decision events become common foundations, RAG evidence and claim verification become deterministic gates, and approval/action boundaries stay safe without implementing full real external execution.

## v1 Requirements

### Architecture Contract Baseline

- [x] **APF-01:** The target architecture plan, `contract-spec.md`, and eval plan define the same target graph vocabulary, service boundaries, AgentState RAG/claim fields, tool policy decisions, business fact results, and decision event foundation.
- [x] **APF-02:** Each platform/domain module has explicit ownership over schemas, repositories/adapters, public methods, downstream dependencies, forbidden imports, and decision events.

### Trusted Context and Decision Events

- [ ] **APF-03:** `TrustedContextFactory` produces canonical `TrustedContext` from trusted API/auth/run boundaries without accepting LLM or user-payload overrides.
- [ ] **APF-04:** `TrustedContextFactory` derives prompt-safe and service-safe projections for tool calls, knowledge retrieval, memory loading, approval decisions, replay, and intent policy without widening canonical identity/scope fields.
- [ ] **APF-05:** A minimal `DecisionEventEnvelopeV1` / event emitter foundation records stable reason codes, policy/model/tool versions, redaction policy, and run/tenant/trace identity for later platform service decisions.

### Tool and Business Fact Boundaries

- [ ] **APF-06:** Tool planner visibility is generated from `ToolDescriptor` into prompt-safe `ToolView` rather than exposing raw descriptors, adapters, internal permission reasons, or side-effect capabilities.
- [ ] **APF-07:** Runtime tool invocation emits `ToolPolicyDecision` and rechecks authorization, resource scope, side-effect class, and input/output schema even when the tool was visible to the planner.
- [ ] **APF-08:** Business fact reads expose `BusinessFactResultV1` / `BusinessFactRefV1` through domain service public methods, and graph/tool code cannot substitute memory, RAG, LLM inference, or raw repository rows for current business facts.

### Memory Platform Boundaries

- [ ] **APF-09:** Session context loading exposes agent-facing `SessionContextMemory` for same-thread continuity while keeping `SessionContinuityStore` as an internal storage concern.
- [ ] **APF-10:** Memory context APIs separate session context, long-term memory, case memory, conversation log, workflow checkpoint, working state, and memory write candidates, with explicit authority tags that prevent memory from satisfying policy evidence, current business fact, approval, action, or replay truth.

### Intent and Graph Migration

- [ ] **APF-11:** The graph can map legacy nodes/routers to target canonical vocabulary for `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `rag_context_build`, and `claim_verify`.
- [ ] **APF-12:** Intent and slot policy registries drive contextual intent resolution and slot inheritance decisions, with LLM output limited to candidates and deterministic policy owning effective route/slot decisions.

### RAG Context Build and Claim Verification

- [ ] **APF-13:** `rag_context_build` validates candidate policy evidence into `VerifiedEvidencePackageV1` with identity/scope/hash/version/effective-date checks, separated prompt/verifier/replay/debug projections, and deterministic `route_after_rag_context`.
- [ ] **APF-14:** `claim_verify` consumes `MaterialClaimV1` outputs and produces `ClaimVerificationBundleV1` with rules-first support status, hard gates for unsupported user-visible/action claims, and fail-closed behavior for high-risk/action-bound verifier errors.

### Approval and Action Draft Boundary

- [ ] **APF-15:** Action proposals, approval decisions, and action drafts bind structured payloads to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots.
- [ ] **APF-16:** `risk_gate` owns blocked/approval-required/auto-draft decisions, while `approval_gate` only executes approval plans, trusted resume, interrupt, and revision state machine behavior.

### Replay and Eval Hardening

- [ ] **APF-17:** Replay/trace coverage records platform decisions for trusted context projection, intent/slot policy, memory load/write policy, tool visibility/auth, RAG validation, claim verification, risk/approval, and action draft boundaries.
- [ ] **APF-18:** Contract tests and eval gates distinguish dev-contract, release, and monitoring gates for the new platform boundaries, including negative cases for scope leaks, unsupported claims, unsafe action paths, and raw payload exposure.

## v2 / Future Requirements

- [ ] **APF-FUT-01:** Extract selected platform/domain services into separately deployed microservices once call boundaries, schemas, and operational needs justify deployment separation.
- [ ] **APF-FUT-02:** Build full real external execution with outbox, idempotent dispatch, reconciliation, compensation, and external side-effect audit.
- [ ] **APF-FUT-03:** Add dynamic external tool/MCP discovery after `ToolPolicyDecision`, side-effect gates, and prompt-safe projections are stable.
- [ ] **APF-FUT-04:** Build policy source operations UI for upload, review, lifecycle management, and source-document inspection.
- [ ] **APF-FUT-05:** Add tenant-over-global policy precedence and global/default fallback in a dedicated Policy Scope phase.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full real external execution | This milestone preserves action/execution boundaries but does not implement outbox dispatch, reconciliation, or real side effects. |
| Physical microservice deployment | The target is a microservice-ready modular monolith; deployment split is a later operational decision. |
| Replacing the whole graph in one phase | Graph migration must preserve legacy compatibility and land after context, event, tool, memory, and contract foundations. |
| Letting LLMs own routing, authorization, memory publication, or claim support | Violates deterministic policy and authority boundaries. |
| Treating memory as policy evidence, current business fact, approval/action authority, or replay truth | Memory remains contextual assistance only. |
| External search backend replacement | Deferred to Phase RAG-5 unless PostgreSQL hybrid retrieval stops fitting the project scale. |
| Policy source operations UI | Deferred to Policy Source Operations. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| APF-01 | Phase 26 | Complete |
| APF-02 | Phase 26 | Complete |
| APF-03 | Phase 27 | Pending |
| APF-04 | Phase 27 | Pending |
| APF-05 | Phase 28 | Pending |
| APF-06 | Phase 29 | Pending |
| APF-07 | Phase 29 | Pending |
| APF-08 | Phase 30 | Pending |
| APF-09 | Phase 31 | Pending |
| APF-10 | Phase 31 | Pending |
| APF-11 | Phase 32 | Pending |
| APF-12 | Phase 32 | Pending |
| APF-13 | Phase 33 | Pending |
| APF-14 | Phase 33 | Pending |
| APF-15 | Phase 34 | Pending |
| APF-16 | Phase 34 | Pending |
| APF-17 | Phase 35 | Pending |
| APF-18 | Phase 35 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-06-22 for v1.9 Agent Platform Foundation.*
