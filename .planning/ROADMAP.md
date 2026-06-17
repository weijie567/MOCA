# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** - Shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [ ] **v1.1 Agent Architecture Migration** - Phases 7-17 migrate the existing demo toward explicit service, state, approval, action, memory, replay, migration, and evaluation contracts.

## Phases

<details>
<summary>v1.0 MVP (Phases 1-6) - SHIPPED 2026-05-22</summary>

- [x] Phase 1: Foundation
- [x] Phase 2: RAG Pipeline
- [x] Phase 3: LangGraph Core
- [x] Phase 4: Approval Workflow & Audit
- [x] Phase 5: Frontend & SSE
- [x] Phase 6: Evaluation & Polish

</details>

### v1.1 Agent Architecture Migration (Phases 7-17)

- [x] **Phase 7: Contract Baseline** - Contract inventory, current-vs-target evidence, coverage matrix, follow-up disposition, and readiness verdict. Completed 2026-06-06.
- [x] **Phase 8: Knowledge Facade** - KnowledgeService boundary and canonical EvidenceRefV1/citation contract. Completed 2026-06-11.
- [x] **Phase 9: Business Tool Facade** - BusinessToolService boundary and ToolCallContext/ToolResultV2 contract. ✓ Verified 2026-06-13 — 9/9 plans complete, 14/14 must-haves verified.
- [x] **Phase 10: State Lifecycle + Routing Migration** - AgentState lifecycle/trusted fields, deterministic total routers, empty session-memory adapter, and bounded investigate graph wiring. Completed 2026-06-14.
- [x] **Phase 11: Intent / Clarification** - Intent precedence, required-slot policy, confidence gates, and ordinary clarification. Completed 2026-06-14.
- [x] **Phase 12: Session Memory** - PostgreSQL-authoritative session memory CAS, optional Redis hot cache, and safe slot continuity. ✓ Verified 2026-06-14 — 5/5 plans complete, 10/10 must-haves verified.
- [x] **Phase 13: Approval State Machine** - Versioned approval lifecycle and ActionSafetySnapshot ownership. ✓ Verified 2026-06-15 — 8/8 plans complete, 12/12 must-haves verified.
- [x] **Phase 14: Demo Action Executor Boundary** - Durable draft-only demo behavior and snapshot/hash binding. ✓ Verified 2026-06-16 — 7/7 plans complete, 10/10 must-haves verified.
- [x] **Phase 15: Replay Event Contract** - ReplayEventV3, lifecycle finalizer, sequence allocation, redaction, retention, and replay read-switch. Final gates passed 2026-06-16; ready for GSD verification.
- [x] **Phase 15.1: Memory Foundation V2 (INSERTED)** - Conversation log, tool call/result storage, WorkingStateV1, thread summaries, ContextAssembler, token budget, and trace/audit ID alignment before Phase 16. (completed 2026-06-17)
- [ ] **Phase 16: Long-term / Case Memory** - memory_identity.v1, tombstones, review workflow, and long-term/case memory. Deferred beyond the MVP completion gate.
- [ ] **Phase 17: External Action Execution** - External execution, outbox, reconciliation, and compensation. Deferred beyond the MVP completion gate.

**Phase 13-17 planning standard:** Every Phase 13-17 plan, including inserted Phase 15.1, must read `docs/phase-13-17-architecture-plan.md` before task decomposition and include an Architecture Alignment section. The section must identify the canonical owner package, schema owner, old-path quarantine/deletion strategy, forbidden new imports/references, boundary tests, and the exact Phase 13/14/15/15.1/16/17 non-overlap. The goal is stable owner/contract architecture first, not minimum-diff compatibility.

## Phase Details

### Phase 7: Contract Baseline
**Goal**: Establish an implementation-aware contract baseline so later phases cannot omit target contracts or mistake target design for implemented behavior.
**Depends on**: Phase 6
**Requirements**: BASE-01, BASE-02, BASE-03, BASE-04
**Success Criteria**:
  1. Contract inventory, current-vs-target evidence checklist, initial coverage matrix, and follow-up register disposition exist.
  2. Every gap has an owner phase and acceptance gate; no relevant row is `MISSING`.
  3. Phase 8 and Phase 9 are explicitly ready to plan.
**Plans**: 1/1 complete

### Phase 8: Knowledge Facade
**Goal**: Route policy evidence retrieval through KnowledgeService with canonical EvidenceRefV1, citation validation, effective-time, and tenant-over-global behavior.
**Depends on**: Phase 7
**Requirements**: KNOW-01, KNOW-02, KNOW-03
**Success Criteria**:
  1. Knowledge reads use the facade while the existing RAG path remains an adapter/fallback.
  2. Strong/partial/no-evidence and claim-support contracts pass.
  3. Any persistence or read-switch has an owned migration, telemetry, and rollback.
**Plans**: 9/9 complete

### Phase 9: Business Tool Facade
**Goal**: Route read business tools through BusinessToolService using trusted ToolCallContext and typed ToolResultV2.
**Depends on**: Phase 7
**Requirements**: TOOL-01, TOOL-02, TOOL-03
**Success Criteria**:
  1. Read tools use the facade without exposing raw invalid upstream payloads.
  2. Permission, scope, status, timeout, partial-success, and invalid-response contracts pass.
  3. Write/action execution remains outside this facade.
**Plans**: 9/9 complete

### Phase 10: State Lifecycle + Routing Migration
**Goal**: Enforce AgentState reset/merge/trusted-writer rules, deterministic router totality, and the investigation segment agentic merge (single `investigate` bounded-loop node + `route_after_investigate`). Scope expansion P10-DEV-01: the investigate merge is added by the §9 promotion (commit ad17301) beyond the original state+router goal text.
**Depends on**: Phase 8, Phase 9 (Phase 9 BusinessToolService is the bounded loop's read-tool dependency; Phase 10 is planned now as a loop-ready design input — see Plan 04 "Phase 9 loop-facing contract requirements". P10-DEV-02 reverses Phase 9 CONTEXT's "no bounded caller" lock.)
**Requirements**: STATE-01, STATE-02, ROUTE-01, ROUTE-02
**Success Criteria**:
  1. State lifecycle/property tests and trusted-field merge tests pass.
  2. Every router is deterministic, side-effect free, total for valid state, and safe for invalid state.
  3. Empty session-memory adapter routing exists without claiming session continuity.
**Plans**: 5/5 complete
  - [x] 10-01-PLAN.md — AgentState §10.1 lifecycle fields + per-turn reset + STATE-01/02 tests (Wave 1)
  - [x] 10-02-PLAN.md — Minimal event envelope + per-run sequence allocator + base table (§17.2, Wave 1)
  - [x] 10-03-PLAN.md — route_after_investigate pure router + totality/fallback tests (Wave 2)
  - [x] 10-04-PLAN.md — investigate bounded-loop node + D-03..D-08 guardrail tests (Wave 2, Phase 9 facade available)
  - [x] 10-05-PLAN.md — Graph wiring: register investigate, route_after_investigate, fallback stubs, SC-3 (Wave 3)

### Phase 11: Intent / Clarification
**Goal**: Implement deterministic intent precedence, required-slot expressions, confidence safety gates, and ordinary clarification.
**Depends on**: Phase 10
**Requirements**: INTENT-01, INTENT-02, CLARIFY-01
**Success Criteria**:
  1. Intent and required-slot golden tests pass.
  2. Low-confidence/high-risk routes use safe clarification or risk paths.
  3. Ordinary chat cannot create trusted approval decisions or resume commands.
**Plans**: 5/5 complete
  - [x] 11-01-PLAN.md — IntentResultV3 schema, prompt contract, and explicit AgentState adapter (Wave 1)
  - [x] 11-02-PLAN.md — Deterministic pre-router, precedence helpers, and confidence safety defaults (Wave 2)
  - [x] 11-03-PLAN.md — RequiredSlotExpression completeness, route_after_intent/route_after_slots, and graph wiring (Wave 3)
  - [x] 11-04-PLAN.md — Ordinary clarification gate and approval lifecycle separation (Wave 4)
  - [x] 11-05-PLAN.md — Intent consistency manifest, golden dataset, Wilson gates, and phase validation (Wave 5)

### Phase 12: Session Memory
**Goal**: Implement PostgreSQL-authoritative same-thread session memory with CAS and safe slot inheritance. Redis, if introduced, is only a non-authoritative TTL hot cache with PostgreSQL fallback.
**Depends on**: Phase 10, Phase 11
**Requirements**: SESSION-01, SESSION-02, SESSION-03
**Success Criteria**:
  1. Same-thread continuity and cross-thread/user/tenant isolation pass.
  2. CAS conflicts use deterministic merge or return conflict, never silent last-write-wins.
  3. Session memory is not policy evidence and can be disabled with observable fallback; Redis loss/cache miss falls back to PostgreSQL if Redis is introduced.
**Plans**: 5/5 complete

### Phase 13: Approval State Machine
**Goal**: Implement versioned approval requests/levels/assignments/decisions/events and the canonical ActionSafetySnapshot.
**Depends on**: Phase 11
**Mandatory architecture input**: `docs/phase-13-17-architecture-plan.md`
**Requirements**: APPROVAL-01, APPROVAL-02, APPROVAL-03, SNAPSHOT-01
**Success Criteria**:
  1. Single-level runtime transition, CAS, revision invalidation, and needs_info resume tests pass.
  2. Action payload and safety snapshot hashes bind approval to the exact revision.
  3. Multi-level-compatible schema/contracts are verified; active SLA scanner remains an owned follow-up gate.
**Plans**: 8/8 complete; verified 2026-06-15 with 12/12 must-haves
Plans:
  - [x] 13-01-PLAN.md — CanonicalHashProfile v1 and ActionSafetySnapshot golden contracts (Wave 1)
  - [x] 13-02-PLAN.md — Approval/snapshot ORM, Alembic migration, legacy non-executable report (Wave 2)
  - [x] 13-03-PLAN.md — ApprovalService policy/repository/CAS transitions and exact hash binding (Wave 3)
  - [x] 13-04-PLAN.md — Approval API, chat/SSE, and graph cutover to trusted service commands (Wave 4)
  - [x] 13-05-PLAN.md — needs_info, edit, and attach_info revision revalidation (Wave 5)
  - [x] 13-06-PLAN.md — Approval events and feature-disabled SLA scanner (Wave 6)
  - [x] 13-07-PLAN.md — Legacy quarantine, boundary tests, and v1 test rewrites (Wave 7)
  - [x] 13-08-PLAN.md — Coverage, eval manifest, and final verification gates (Wave 8)

### Phase 14: Demo Action Executor Boundary
**Goal**: Enforce the durable draft-only demo boundary with exact approval/snapshot binding.
**Depends on**: Phase 13
**Mandatory architecture input**: `docs/phase-13-17-architecture-plan.md`
**Requirements**: DEMO-01, DEMO-02
**Success Criteria**:
  1. Demo mode creates only action draft and draft_outcome.
  2. Demo mode creates no action execution row or external side effect.
  3. Hash/revision mismatches are rejected and final response wording never claims real execution.
**Plans**: 7/7 complete; verified 2026-06-16 with 10/10 must-haves verified after gap closure plan 14-07 enforced exact payload/hash binding, no-approval fail-closed behavior, and write-tool permission ownership.
Plans:
  - [x] 14-01-PLAN.md — action_draft.v2 schema, draft_outcome contract, and blocking Alembic upgrade (Wave 1)
  - [x] 14-02-PLAN.md — ActionService-owned idempotency, exact binding reuse, draft outcome persistence, and state reset (Wave 2)
  - [x] 14-03-PLAN.md — canonical action_draft graph node, tool allowlist, and execute_action shim quarantine (Wave 3)
  - [x] 14-04-PLAN.md — approval resume and final/API draft_outcome wording migration (Wave 4)
  - [x] 14-05-PLAN.md — safe action_draft_created event and /trace draft_outcome projection (Wave 4)
  - [x] 14-06-PLAN.md — negative boundary coverage and final source audit gate (Wave 5)
  - [x] 14-07-PLAN.md — verified gap closure for payload/hash binding, omitted-approval fail-closed authorization, and write-tool permission enforcement (Wave 6)

### Phase 15: Replay Event Contract
**Goal**: Implement ReplayEventV3, run lifecycle finalizer, shared sequence allocator, redaction/retention, and replay read-switch.
**Depends on**: Phase 10, Phase 12, Phase 13, Phase 14
**Mandatory architecture input**: `docs/phase-13-17-architecture-plan.md`
**Requirements**: REPLAY-01, REPLAY-02, REPLAY-03
**Success Criteria**:
  1. Normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines are complete.
  2. Sequence and operation pairing contracts pass under concurrent writers and retries.
  3. `/replay` reads V3 while `/trace` remains the rollback fallback.
**Plans**:
  - [x] 15-01-PLAN.md — ReplayEventV3 schema, baseline replay enum, ORM/migration expansion, and blocking Alembic gate (Wave 1)
  - [x] 15-02-PLAN.md — ReplayService append/projection boundary, redaction/retention validation, compatibility wrapper, and pre-lifecycle allocator coverage (Wave 2)
  - [x] 15-03-PLAN.md — operation pairing, retry, and unresolved legacy projection rules (Wave 3)
  - [x] 15-04-PLAN.md — RunLifecycleService, real run-status persistence/API seams, lifecycle allocator coverage, and disabled SLA scanner gate (Wave 4)
  - [x] 15-05-PLAN.md — `/replay` event-store-first API, access control, read-switch, and `/trace` rollback fallback (Wave 5)
  - [x] 15-06-PLAN.md — replay-facing demo draft cleanup, redaction/retention safety, coverage artifact, and final verification gate (Wave 6)

### Phase 15.1: Memory Foundation V2 (INSERTED)

**Goal:** Establish the pre-Phase 16 memory foundation: complete conversation log, tool call/result layering, prompt-safe WorkingStateV1, thread rolling summaries, ContextAssembler, token budgeting, and trace/audit/conversation ID alignment.
**Depends on:** Phase 12, Phase 15
**Non-goals:** No long-term memory write gate, memory tombstones, user-manageable memory, case memory vector search, or case precedent retrieval.
**Requirements**: MEMORY-FOUNDATION-01, MEMORY-FOUNDATION-02, MEMORY-FOUNDATION-03
**Success Criteria**:
  1. Conversation threads/messages and tool call/result records capture what happened without replacing business tables, policy KB, approval/action tables, or redacted replay.
  2. WorkingStateV1 and ContextAssembler provide prompt-safe current-run context without raw tool payloads, policy full text, approval/action authority objects, or trace/debug blobs.
  3. Thread rolling summaries are derived from conversation messages/tool summaries with source ranges and remain distinct from session slot memory and future Phase 16 case/long-term memory.
**Plans**: 6/6 planned; 6/6 complete.

Plans:
- [x] 15.1-01-PLAN.md — conversation/tool/summary schema, migration rollout, ConversationService, and chat message append wiring (Wave 1) — completed 2026-06-17
- [x] 15.1-02-PLAN.md — four-layer tool call/result storage and prompt-safe tool result state projection (Wave 2) — completed 2026-06-17
- [x] 15.1-03-PLAN.md — WorkingStateV1 prompt-safe current-run projection and authority boundary tests (Wave 3) — completed 2026-06-17
- [x] 15.1-04-PLAN.md — thread rolling summaries, source ranges, session-memory separation, and prompt-context loading (Wave 4) — completed 2026-06-17
- [x] 15.1-05-PLAN.md — ContextAssembler, token budgeting, prompt projectors, and live prompt-node wiring (Wave 5) — completed 2026-06-17
- [x] 15.1-06-PLAN.md — replay/audit/conversation ID alignment, boundary regressions, and final phase verification (Wave 6) — completed 2026-06-17

### Phase 16: Long-term / Case Memory
**Goal**: Implement reviewed long-term/case memory with canonical identity and tombstone enforcement.
**Depends on**: Phase 12, Phase 15, Phase 15.1
**Mandatory architecture input**: `docs/phase-13-17-architecture-plan.md`
**Requirements**: MEMORY-01, MEMORY-02
**Success Criteria**:
  1. memory_identity.v1 and tombstone no-rewrite tests pass.
  2. Long-term and case retrieval predicates remain distinct.
  3. Session-memory fallback and policy-evidence authority remain unchanged.
**Plans**: Deferred

### Phase 17: External Action Execution
**Goal**: Implement external action execution with transactional claim/outbox, reconciliation, and compensation.
**Depends on**: Phase 14, Phase 15
**Mandatory architecture input**: `docs/phase-13-17-architecture-plan.md`
**Requirements**: EXTERNAL-01, EXTERNAL-02, EXTERNAL-03
**Success Criteria**:
  1. Adapter dispatch occurs only after committed outbox claim.
  2. Unknown/reconciling paths do not create unsafe new-key retries.
  3. Duplicate execution/key and unauthorized compensation guards pass.
**Plans**: Deferred

## Progress

| Phase | Plans Complete | Status | Completed |
| --- | --- | --- | --- |
| 7. Contract Baseline | 1/1 | Complete | 2026-06-06 |
| 8. Knowledge Facade | 9/9 | Complete | 2026-06-11 |
| 9. Business Tool Facade | 9/9 | Complete | 2026-06-13 |
| 10. State Lifecycle + Routing Migration | 5/5 | Complete | 2026-06-14 |
| 11. Intent / Clarification | 5/5 | Complete | 2026-06-14 |
| 12. Session Memory | 5/5 | Complete | 2026-06-14 |
| 13. Approval State Machine | 8/8 | Complete    | 2026-06-15 |
| 14. Demo Action Executor Boundary | 7/7 | Complete    | 2026-06-16 |
| 15. Replay Event Contract | 6/6 | Complete    | 2026-06-16 |
| 15.1 Memory Foundation V2 | 6/6 | Complete    | 2026-06-17 |
| 16. Long-term / Case Memory | 0/TBD | Deferred beyond MVP gate | - |
| 17. External Action Execution | 0/TBD | Deferred beyond MVP gate | - |

---
*Updated: 2026-06-17 — Phase 15.1 Memory Foundation V2 verified and complete; Phase 16 ready to plan when resumed.*
