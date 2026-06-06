# Agent Architecture Migration Phase Decomposition

Source spec: `docs/agent-architecture-spec.md`

This document is the formal phase decomposition seed for the v1.1 Agent Architecture Migration milestone. Historical v1.0 remains archived as Phases 1-6. All phases in this document use the standard GSD roadmap identities `Phase 7` through `Phase 17`; there is no separate prefixed phase namespace.

This document is not an implementation plan for an individual phase. Each phase still requires its own implementation plan using the traceability requirements in spec Section 19.

## 1. Readiness Rules

Every phase plan must start from coverage extraction against `docs/agent-architecture-spec.md`, then produce a phase-specific coverage matrix, then run coverage verification before execution.

Section 19 of `docs/agent-architecture-spec.md` is the default planning source of truth, not an unquestionable proof of correctness. Every phase plan must check consistency between Section 19, this phase decomposition, current source evidence, and already generated planning artifacts. Any inconsistency must be raised explicitly in a `Spec Consistency Findings` / `Planning Deviations` section with original requirement, conflicting evidence, recommended handling, readiness impact, and owner.

Phase 7 treats inconsistency discovery as a primary output: its value is to prevent Phase 8/Phase 9 from planning on top of an incorrect or self-inconsistent migration route, not to prove Section 19 is all correct.

A phase plan is not executable if any relevant spec area is `MISSING`.

If Section 19 or any target contract appears unreasonable, unsupported by current evidence, or inconsistent with decomposition/source facts, the baseline must allow `PARTIAL` or `MISSING` instead of forcing `COVERED`. Do not silently normalize conflicts away.

`PARTIAL` and `DEFERRED_WITH_OWNER` are allowed only when the plan names the owner phase, explains why the gap is non-blocking for the current phase, and defines an acceptance gate.

Coverage `Status` must use only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING`. `N/A` may appear only in owner/impact/eval/read-switch fields with a reason; it is not a valid status.

## 2. Global Phase Sequence

| Phase | Name | Capability boundary | Depends on | MVP gate? | Primary acceptance gate |
| --- | --- | --- | --- | --- | --- |
| Phase 7 | Contract baseline | Spec-to-plan inventory and evidence baseline | none | yes | Contract inventory, current-vs-target checklist, initial coverage matrix, review checklist |
| Phase 8 | Knowledge facade | Knowledge/RAG service boundary and EvidenceRefV1/citation contract | Phase 7 | yes | Agent reads policy evidence through KnowledgeService facade with strong/partial/no-evidence contract tests |
| Phase 9 | Business tool facade | Read business tool service boundary and ToolCallContext/ToolResultV2 | Phase 7 | yes | Read tools go through BusinessToolService with permission/scope/error status contract tests |
| Phase 10 | State lifecycle + routing migration | AgentState lifecycle, trusted context, deterministic routers, slot resolution seam | Phase 8 and Phase 9 | yes | State reset/property tests and router totality/determinism pass |
| Phase 11 | Intent / clarification | Intent precedence, required-slot policy, ordinary clarification path | Phase 10 | yes | Intent golden set, confidence/slot clarification tests, ordinary chat cannot create trusted approval decision |
| Phase 12 | Session memory | PostgreSQL-backed same-thread session memory and active slot continuity; excludes long-term/case memory, memory_identity.v1, tombstones, embeddings, async extraction, review workflow, and authoritative Redis memory | Phase 10 and Phase 11 | yes | Session memory CAS, same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests |
| Phase 13 | Approval state machine | Versioned approval request/level/assignment/decision/events and ActionSafetySnapshot owner | Phase 11 | yes | Single-level approval runtime passes transition/revision/snapshot/hash/needs_info tests; multi-level-compatible schema/contract planning is verified; active SLA scanner remains deferred to the Phase 13 SLA scanner follow-up gate |
| Phase 14 | Demo action executor boundary | Durable draft-only demo action path and action draft snapshot binding | Phase 13 | yes | Demo creates draft/draft_outcome only, no external side effect, no action_executions row |
| Phase 15 | Replay event contract | ReplayEventV3, finalizer, sequence allocator, redaction/retention | Phase 10, Phase 12, Phase 13, Phase 14 | yes | `/replay` returns V3 lifecycle timeline for normal/interrupted/resumed/responded/rejected/expired/error/cancelled paths |
| Phase 16 | Long-term/case memory | Deferred long-term and case memory service, memory_identity.v1, tombstone enforcement | Phase 12, Phase 15 | no | Memory identity/tombstone/review workflow contract tests pass without changing session memory fallback |
| Phase 17 | External action execution | External adapters, action_executions, outbox, reconciliation, compensation | Phase 14, Phase 15 | no | Outbox claim-before-dispatch, unknown/reconciling, compensation authorization, duplicate execution/key guards pass |

## 3. Dependency Notes

- Phase 8 and Phase 9 may run in parallel after Phase 7.
- Phase 10 must wait for Phase 8 and Phase 9 because routing/state migration depends on stable service boundaries.
- Phase 11 must wait for Phase 10 because intent precedence and clarification rely on deterministic routing and slot resolution.
- Phase 12 must wait for Phase 10/Phase 11 so session memory can inherit slots only after intent/slot contracts are stable. Phase 12 uses PostgreSQL as the authoritative session memory store and must not introduce Redis as authoritative session memory.
- Phase 12 explicitly excludes long-term memory, case memory, `memory_identity.v1`, tombstones, embeddings, asynchronous memory extraction, and review workflow; those remain owned by Phase 16.
- Phase 13 must wait for Phase 11 because approval planning depends on validated intent/action/risk semantics.
- Phase 14 must wait for Phase 13 because demo action drafts must bind exact approval payload and safety snapshot hashes.
- Phase 15 must wait for Phase 10, Phase 12, Phase 13, and Phase 14 because ReplayEventV3 must cover routing, memory write failure, approval, and action draft lifecycle.
- Phase 16 is deferred beyond MVP and must not block Phase 12 session memory fallback.
- Phase 17 is deferred beyond MVP and must not weaken Phase 14 demo draft safety.

## 4. Schema / Migration Ownership

| Schema area | Owner phase | Notes |
| --- | --- | --- |
| Knowledge facade persistence, if introduced | Phase 8 | If Phase 8 adds any persisted Knowledge facade schema, cache, audit, or adapter mapping table, Phase 8 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the Phase 8 plan |
| BusinessTool facade audit persistence, if introduced | Phase 9 | If Phase 9 adds tool audit, adapter result cache, or facade mapping tables, Phase 9 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the Phase 9 plan |
| `session_memories`, version CAS | Phase 12 | Must support same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests. PostgreSQL is authoritative; Redis is not used for Phase 12 session memory. |
| Approval request/level/assignment/decision/event versioning | Phase 13 | Request/level/assignment CAS and mismatch transaction tests are required |
| `action_safety_snapshots` | Phase 13 | Unique canonical snapshot/hash target; Phase 14 references and validates it, Phase 15 may add replay FK/backfill |
| `action_drafts` version/retention/snapshot binding fields | Phase 14 | Demo path must not create `action_executions` |
| `agent_trace_events`, operation correlation, sequence/backfill/retention indexes | Phase 15 | Approval/action replay FKs remain nullable until backfill verification |
| Long-term/case memory tables, `memory_tombstones`, memory identity/review indexes | Phase 16 | Deferred beyond MVP; must not become policy evidence source |
| `action_executions`, `action_outbox_events`, `action_reconciliation_jobs`, `action_compensation_records` | Phase 17 | External-only; outbox claim/lock indexes and retention indexes required |

All cross-phase FKs use nullable column -> deterministic backfill -> deferred nullable FK. Historical rows that cannot be resolved remain null and must be recorded in a migration report.

## 5. Global Coverage Matrix

| Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AgentState lifecycle | Phase 10 | State reset/property tests; trusted field merge tests | N/A | none | Router/state rollback owner in Phase 10 | Non-blocking unless state changes alter eval routes | COVERED |
| Router totality | Phase 10 | Totality, determinism, invalid-state fallback tests | N/A | none | Router rollback owner in Phase 10 | Intent route eval depends on this | COVERED |
| Intent/slot/ordinary clarification | Phase 11, with Phase 12 session continuity | Intent golden set; required-slot accuracy; clarification precision | N/A | Session continuity deferred to Phase 12 with gate | Prompt/classifier rollback owner in Phase 11 | Blocking for high-risk intent classes once Phase 11 exits | COVERED |
| Approval needs_info resume | Phase 13 | Wrong clarification id, wrong tenant/thread, stale version, payload/evidence changed, timeout/cancelled, old revision cannot execute | Phase 13 approval schemas | none | Approval state rollback owner in Phase 13 | Blocking for approval lifecycle golden flows | COVERED |
| EvidenceRefV1/citation/canonical hash | Phase 8, Phase 13 snapshot/hash | Retrieval/citation contract tests; canonical hash golden sample; score/rank projection tests | Phase 13 for snapshot; Phase 8 for knowledge facade schemas if persisted | none | Knowledge read-switch owner in Phase 8; snapshot rollback owner in Phase 13 | RAG groundedness/citation eval blocking for policy/action gates | COVERED |
| ToolCallContext/ToolResultV2 | Phase 9 | Permission/scope, not_found, timeout, partial_success, invalid_response, raw payload forbidden | N/A unless tool audit tables added | none | BusinessToolService adapter rollback owner in Phase 9 | Tool selection eval non-blocking unless route safety affected | COVERED |
| Session memory CAS | Phase 12 | Same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, CAS conflict deterministic merge, session memory unavailable fallback, and memory-is-not-policy-evidence negative tests | Phase 12 | Redis is excluded from authoritative session memory; long-term/case/identity/tombstone/embeddings/async extraction/review workflow deferred to Phase 16 | Session memory read-switch/fallback owner in Phase 12; rollback disables session memory reads/writes and falls back to checkpointer-only behavior with telemetry | Phase 12 slot/session-memory route safety; memory write quality non-blocking unless slot inheritance changes route safety | COVERED |
| Long-term/case memory + memory_identity.v1 + tombstone | Phase 16 | Identity normalization, source_ref normalization, tombstone no-rewrite, review workflow, retrieval predicate tests | Phase 16 | Deferred beyond MVP; must not block session memory | Phase 16 owner; rollback by memory type | Blocking only for Phase 16 exit | DEFERRED_WITH_OWNER |
| Approval assignment/SLA/revision invalidation | Phase 13 | Single-level assignment/version CAS, self approval, edit/respond invalidation, expired no resume; multi-level-compatible schema/contract tests; active SLA scanner follow-up gate | Phase 13 | Multi-level runtime aggregation is not required for MVP Phase 13; active SLA scanner deferred to Phase 13 SLA scanner follow-up slice with replay-visible reminder/escalation/expire events as gate | Phase 13 owner | Blocking for Phase 13 approval readiness except deferred scanner automation gate | PARTIAL |
| `action_safety_snapshots` owner | Phase 13 | Snapshot JSON/hash contract, unique tenant/hash, payload/snapshot mismatch invalidation | Phase 13 | none | Phase 13 owner; Phase 14 only references/validates | Blocking for Phase 13/Phase 14 safety gates | COVERED |
| Demo action boundary | Phase 14 | Demo no side effect, no execution row, draft_outcome only, final response wording, hash mismatch forbidden | Phase 14 action_draft fields | none | Demo draft rollback owner in Phase 14 | Action safety eval blocks Phase 14 exit | COVERED |
| External action/outbox/reconciliation/compensation | Phase 17 | Claim-before-dispatch, duplicate active execution/key, unknown/reconciling, no-new-key retry, compensation authorization | Phase 17 | Deferred beyond MVP with Phase 17 owner | Phase 17 owner; rollback per adapter | Blocking only for Phase 17 exit | DEFERRED_WITH_OWNER |
| ReplayEventV3/finalizer/redaction/retention | Phase 15 | V3 shape, sequence allocator, lifecycle completeness for normal/interrupted/resumed/responded/rejected/expired/error/cancelled, redaction, retention, access control | Phase 15 | none | `/trace` compatibility fallback owner in Phase 15 | Replay completeness eval blocks Phase 15 exit | COVERED |
| Cross-table enforcement matrix | Phase 13, Phase 14, Phase 17 | Relevant relationship rows and mismatch transaction tests copied into each phase plan | Phase 13, Phase 14, Phase 17 | Global owner exists, but each phase plan must copy exact relevant Section 18.2 rows and mismatch tests; missing row mapping blocks that phase | Relevant owner phase | Blocking for affected schema phase exit | PARTIAL |
| Migration rollout protocol | All schema phases | Backfill report, row-count/hash equality, tenant/run ownership, read-switch/fallback telemetry, negative mismatch tests | Relevant schema owner | none | Relevant schema owner | Non-blocking unless contract/eval gate says blocking | COVERED |
| Contract tests | Every phase | Phase-specific contract matrix rows | Relevant owner | none | N/A | As defined per phase | COVERED |
| Integration golden flows | Phase 11, Phase 13, Phase 14, Phase 15, Phase 17 | Policy QA, refund troubleshooting, approval edit/respond/reject, demo action, external unknown, replay timelines | Relevant owner | Some external flows deferred to Phase 17 | Relevant owner | Blocking for owning phase | COVERED |
| Eval gates | Phase 8, Phase 11, Phase 12, Phase 13, Phase 14, Phase 15, Phase 16, Phase 17 as applicable | Phase 8 RAG groundedness/citation; Phase 11 risk-weighted intent and clarification; Phase 12 slot/session-memory route safety; Phase 13 approval policy accuracy; Phase 14 action safety; Phase 15 replay completeness; Phase 16 memory write quality; Phase 17 external action safety | N/A | Each phase plan must mark blocking/non_blocking, dataset owner/version/hash, and failure impact; until then this row remains PARTIAL | N/A | Explicit per phase before execution | PARTIAL |
| Explicit non-goals | Every phase | Review checklist and coverage verification | N/A | none | N/A | N/A | COVERED |
| Phase planning follow-up register | Every phase | Each phase plan outputs disposition for applicable follow-up items; missing disposition becomes MISSING | N/A | Register exists globally; each phase plan must mark every applicable item as covered, deferred with owner, or not applicable in owner/impact fields while Status remains one of the four allowed statuses | N/A | N/A | PARTIAL |

## 6. Phase Planning Follow-up Register

These items must remain visible during phase decomposition. They are not optional notes from a prior review; they are inputs to coverage extraction.

| Follow-up item | Required handling during phase decomposition | Owner / gate |
| --- | --- | --- |
| Phase 7 baseline artifact names | Phase 7 plan must expand `Contract baseline` into contract inventory, current-vs-target evidence checklist, initial coverage matrix, and review checklist. | Phase 7 acceptance gate |
| Read-switch owner/config visibility | Any schema/service migration phase must name read-switch owner, config/feature flag, fallback telemetry, and rollback behavior; write `N/A` with reason when absent. | Relevant schema owner phase |
| Redis memory boundary | Phase 12 and any later memory-related phase must record that PostgreSQL is the authoritative memory store. Redis may only be used for non-authoritative short TTL lock, rate limit, debounce, SSE buffer, worker hint, or temporary cache; keys must be scoped, TTL mandatory, Postgres fallback required, Redis loss must not affect correctness, and Postgres CAS remains the session memory correctness boundary. | Phase 12/Phase 16 acceptance gates as applicable |
| Phase 13 internal slices | Phase 13 plan must split approval schema/CAS, snapshot builder/hash golden tests, `needs_info` resume, and SLA/assignment semantics. | Phase 13 acceptance gate |
| Cross-table enforcement row mapping | Phase 13/Phase 14/Phase 17 plans must copy relevant rows from the spec Section 18.2 cross-table enforcement matrix and list required mismatch tests. | Phase 13/Phase 14/Phase 17 acceptance gates |
| PARTIAL/deferred status discipline | Every `PARTIAL` / `DEFERRED_WITH_OWNER` row must name owner phase, non-blocking rationale, blocking dependency, and acceptance gate. Otherwise it becomes `MISSING`. | Each phase readiness verdict |
| Eval gate blocking status | Every relevant eval gate must name blocking/non_blocking status, dataset owner/version/hash, and phase exit impact. | Relevant phase exit criteria |

## 7. Next Planning Order

1. Write Phase 7 implementation plan.
2. Use Phase 7 to produce the contract inventory and initial coverage verification artifact.
3. Plan Phase 8 and Phase 9, which may execute in parallel after Phase 7 exits.
4. Plan Phase 10 only after Phase 8/Phase 9 service boundary outputs are accepted.
5. Continue sequentially through MVP Phase 11 through Phase 15.
6. Keep Phase 16 and Phase 17 as deferred owner phases unless a later milestone explicitly pulls them forward.
