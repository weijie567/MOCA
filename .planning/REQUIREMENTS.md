# Requirements: MOCA v1.1 Agent Architecture Migration

**Defined:** 2026-06-06
**Source:** `docs/agent-architecture-spec.md` and `docs/agent-architecture-phase-decomposition.md`

## Contract Requirements

- [x] **BASE-01**: Produce a contract inventory and current-vs-target evidence checklist.
- [x] **BASE-02**: Produce an initial coverage matrix using only the allowed readiness statuses.
- [x] **BASE-03**: Persist follow-up items with owner phases and acceptance gates.
- [x] **BASE-04**: Confirm Phase 8 and Phase 9 may proceed with no `MISSING` baseline rows.
- [x] **KNOW-01**: Knowledge reads use KnowledgeService with strong/partial/no-evidence semantics.
- [x] **KNOW-02**: EvidenceRefV1, claim-support citation, canonical projection, effective-time, and tenant-over-global contracts are enforced.
- [x] **KNOW-03**: Knowledge migration/read-switch, if introduced, has owner, telemetry, fallback, and rollback.
- [x] **TOOL-01**: Read business tools use BusinessToolService and trusted ToolCallContext.
- [x] **TOOL-02**: ToolResultV2 covers permission/scope/status/timeout/partial/invalid-response behavior without raw invalid payload exposure.
- [x] **TOOL-03**: Write/action tools remain outside the read-tool facade.
- [x] **STATE-01**: AgentState lifecycle enforces trusted writers, reset, merge, persistence, and cross-scope isolation.
- [x] **STATE-02**: Trusted identity/approval/action fields cannot be overwritten by user or LLM output.
- [x] **ROUTE-01**: Routers are deterministic, total, side-effect free, and return only valid node keys.
- [x] **ROUTE-02**: Invalid or unsafe state routes to explicit safe fallback.
- [x] **INTENT-01**: Intent precedence and requested-operation safety routing are deterministic and tested.
- [x] **INTENT-02**: RequiredSlotExpression and slot completeness rules are enforced.
- [x] **CLARIFY-01**: Ordinary clarification and trusted approval needs_info resume remain separate contracts.
- [x] **SESSION-01**: PostgreSQL session memory uses version CAS and deterministic merge.
- [x] **SESSION-02**: Slot inheritance enforces scope, freshness, compatibility, and explicit override.
- [x] **SESSION-03**: Session memory is not policy evidence and supports observable fallback/read-switch rollback; Redis, if used, is non-authoritative and falls back to PostgreSQL.
- [x] **APPROVAL-01**: Approval transitions, request/level/assignment CAS, and revision invalidation are enforced.
- [x] **APPROVAL-02**: Approval needs_info resume validates clarification identity, scope, versions, changed facts, and old-revision prohibition.
- [x] **APPROVAL-03**: Single-level runtime is complete and multi-level-compatible contracts are verified; active SLA scanner remains an owned gate.
- [x] **SNAPSHOT-01**: ActionSafetySnapshot and CanonicalHashProfile bind approval, draft, and execution to exact payload/evidence/config hashes.
- [x] **DEMO-01**: Demo mode creates durable draft and draft_outcome only, with no execution row or external side effect.
- [x] **DEMO-02**: Demo wording and hash/revision guards cannot claim or authorize real execution.
- [ ] **REPLAY-01**: ReplayEventV3 and lifecycle finalizer cover all required completed/interrupted/terminal paths.
- [ ] **REPLAY-02**: Shared per-run sequence allocator and operation pairing/retry contracts are enforced.
- [ ] **REPLAY-03**: Replay redaction, retention, access control, read-switch, fallback, and rollback are defined.
- [ ] **MEMORY-01**: Long-term/case memory uses memory_identity.v1, review workflow, and distinct retrieval predicates.
- [ ] **MEMORY-02**: Tombstones prevent retrieval and asynchronous rewrite of deleted memory.
- [ ] **EXTERNAL-01**: External dispatch occurs only after transactional draft claim, execution creation, and committed outbox claim.
- [ ] **EXTERNAL-02**: Unknown/reconciling paths prevent unsafe retry with a new external idempotency key.
- [ ] **EXTERNAL-03**: Reconciliation, compensation, and duplicate execution/key guards are enforced.

## Planning Requirements

- Every phase plan must include spec coverage, schema/migration owner, service/API owner, state/router impact, required tests, acceptance criteria, rollback/non-goals/deferred items, and a coverage matrix.
- Phase 13-17 plans must read `docs/phase-13-17-architecture-plan.md` before planning and include an Architecture Alignment section that applies its operating rule: define owner/contract first, move or rewrite code to match the owner, delete or quarantine old paths, and add boundary tests before expanding behavior.
- Phase 13-17 plans must not default to minimum diff. Compatibility layers are allowed only when the plan names an owner, forbids new references, adds tests protecting the canonical path, and names the removal phase.
- A phase plan with any relevant `MISSING` row is blocked from execution.
- Every `PARTIAL` or `DEFERRED_WITH_OWNER` row must name owner, non-blocking rationale, dependency, and acceptance gate.
- Every schema/service migration phase must instantiate the migration rollout protocol and name read-switch/fallback/rollback ownership.
- Every relevant eval gate must name blocking status, dataset owner/version/hash, and failure impact.

## Traceability

| Requirement group | Phase | Status |
| --- | --- | --- |
| BASE-01..04 | Phase 7 | Complete |
| KNOW-01..03 | Phase 8 | Complete |
| TOOL-01..03 | Phase 9 | Complete |
| STATE-01..02, ROUTE-01..02 | Phase 10 | Complete |
| INTENT-01..02, CLARIFY-01 | Phase 11 | Complete |
| SESSION-01..03 | Phase 12 | Complete |
| APPROVAL-01..03, SNAPSHOT-01 | Phase 13 | Complete |
| DEMO-01..02 | Phase 14 | Complete |
| REPLAY-01..03 | Phase 15 | Pending |
| MEMORY-01..02 | Phase 16 | Deferred beyond MVP gate |
| EXTERNAL-01..03 | Phase 17 | Deferred beyond MVP gate |

---
*Updated: 2026-06-16 after Phase 14 completed with final negative boundary coverage and source audit.*
