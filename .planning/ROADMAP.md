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
- [ ] **Phase 8: Knowledge Facade** - KnowledgeService boundary and canonical EvidenceRefV1/citation contract.
- [ ] **Phase 9: Business Tool Facade** - BusinessToolService boundary and ToolCallContext/ToolResultV2 contract.
- [ ] **Phase 10: State Lifecycle + Routing Migration** - AgentState lifecycle/trusted fields and deterministic total routers.
- [ ] **Phase 11: Intent / Clarification** - Intent precedence, required-slot policy, confidence gates, and ordinary clarification.
- [ ] **Phase 12: Session Memory** - PostgreSQL-backed session memory CAS and safe slot continuity.
- [ ] **Phase 13: Approval State Machine** - Versioned approval lifecycle and ActionSafetySnapshot ownership.
- [ ] **Phase 14: Demo Action Executor Boundary** - Durable draft-only demo behavior and snapshot/hash binding.
- [ ] **Phase 15: Replay Event Contract** - ReplayEventV3, lifecycle finalizer, sequence allocation, redaction, retention, and replay read-switch.
- [ ] **Phase 16: Long-term / Case Memory** - memory_identity.v1, tombstones, review workflow, and long-term/case memory. Deferred beyond the MVP completion gate.
- [ ] **Phase 17: External Action Execution** - External execution, outbox, reconciliation, and compensation. Deferred beyond the MVP completion gate.

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
**Plans**: 1/6 complete

### Phase 9: Business Tool Facade
**Goal**: Route read business tools through BusinessToolService using trusted ToolCallContext and typed ToolResultV2.
**Depends on**: Phase 7
**Requirements**: TOOL-01, TOOL-02, TOOL-03
**Success Criteria**:
  1. Read tools use the facade without exposing raw invalid upstream payloads.
  2. Permission, scope, status, timeout, partial-success, and invalid-response contracts pass.
  3. Write/action execution remains outside this facade.
**Plans**: TBD

### Phase 10: State Lifecycle + Routing Migration
**Goal**: Enforce AgentState reset/merge/trusted-writer rules and deterministic router totality.
**Depends on**: Phase 8, Phase 9
**Requirements**: STATE-01, STATE-02, ROUTE-01, ROUTE-02
**Success Criteria**:
  1. State lifecycle/property tests and trusted-field merge tests pass.
  2. Every router is deterministic, side-effect free, total for valid state, and safe for invalid state.
  3. Empty session-memory adapter routing exists without claiming session continuity.
**Plans**: TBD

### Phase 11: Intent / Clarification
**Goal**: Implement deterministic intent precedence, required-slot expressions, confidence safety gates, and ordinary clarification.
**Depends on**: Phase 10
**Requirements**: INTENT-01, INTENT-02, CLARIFY-01
**Success Criteria**:
  1. Intent and required-slot golden tests pass.
  2. Low-confidence/high-risk routes use safe clarification or risk paths.
  3. Ordinary chat cannot create trusted approval decisions or resume commands.
**Plans**: TBD

### Phase 12: Session Memory
**Goal**: Implement PostgreSQL-backed same-thread session memory with CAS and safe slot inheritance.
**Depends on**: Phase 10, Phase 11
**Requirements**: SESSION-01, SESSION-02, SESSION-03
**Success Criteria**:
  1. Same-thread continuity and cross-thread/user/tenant isolation pass.
  2. CAS conflicts use deterministic merge or return conflict, never silent last-write-wins.
  3. Session memory is not policy evidence and can be disabled with observable fallback.
**Plans**: TBD

### Phase 13: Approval State Machine
**Goal**: Implement versioned approval requests/levels/assignments/decisions/events and the canonical ActionSafetySnapshot.
**Depends on**: Phase 11
**Requirements**: APPROVAL-01, APPROVAL-02, APPROVAL-03, SNAPSHOT-01
**Success Criteria**:
  1. Single-level runtime transition, CAS, revision invalidation, and needs_info resume tests pass.
  2. Action payload and safety snapshot hashes bind approval to the exact revision.
  3. Multi-level-compatible schema/contracts are verified; active SLA scanner remains an owned follow-up gate.
**Plans**: TBD

### Phase 14: Demo Action Executor Boundary
**Goal**: Enforce the durable draft-only demo boundary with exact approval/snapshot binding.
**Depends on**: Phase 13
**Requirements**: DEMO-01, DEMO-02
**Success Criteria**:
  1. Demo mode creates only action draft and draft_outcome.
  2. Demo mode creates no action execution row or external side effect.
  3. Hash/revision mismatches are rejected and final response wording never claims real execution.
**Plans**: TBD

### Phase 15: Replay Event Contract
**Goal**: Implement ReplayEventV3, run lifecycle finalizer, shared sequence allocator, redaction/retention, and replay read-switch.
**Depends on**: Phase 10, Phase 12, Phase 13, Phase 14
**Requirements**: REPLAY-01, REPLAY-02, REPLAY-03
**Success Criteria**:
  1. Normal/interrupted/resumed/responded/rejected/expired/error/cancelled timelines are complete.
  2. Sequence and operation pairing contracts pass under concurrent writers and retries.
  3. `/replay` reads V3 while `/trace` remains the rollback fallback.
**Plans**: TBD

### Phase 16: Long-term / Case Memory
**Goal**: Implement reviewed long-term/case memory with canonical identity and tombstone enforcement.
**Depends on**: Phase 12, Phase 15
**Requirements**: MEMORY-01, MEMORY-02
**Success Criteria**:
  1. memory_identity.v1 and tombstone no-rewrite tests pass.
  2. Long-term and case retrieval predicates remain distinct.
  3. Session-memory fallback and policy-evidence authority remain unchanged.
**Plans**: Deferred

### Phase 17: External Action Execution
**Goal**: Implement external action execution with transactional claim/outbox, reconciliation, and compensation.
**Depends on**: Phase 14, Phase 15
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
| 8. Knowledge Facade | 1/6 | In Progress | - |
| 9. Business Tool Facade | 0/TBD | Ready to plan | - |
| 10. State Lifecycle + Routing Migration | 0/TBD | Blocked by 8/9 | - |
| 11. Intent / Clarification | 0/TBD | Pending | - |
| 12. Session Memory | 0/TBD | Pending | - |
| 13. Approval State Machine | 0/TBD | Pending | - |
| 14. Demo Action Executor Boundary | 0/TBD | Pending | - |
| 15. Replay Event Contract | 0/TBD | Pending | - |
| 16. Long-term / Case Memory | 0/TBD | Deferred beyond MVP gate | - |
| 17. External Action Execution | 0/TBD | Deferred beyond MVP gate | - |

---
*Updated: 2026-06-06. v1.1 is registered as the Agent Architecture Migration roadmap. Source code, tests, and git history were not rolled back.*
