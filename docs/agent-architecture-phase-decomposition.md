# Agent Architecture Migration Phase Decomposition

Source spec: `docs/agent-architecture-spec.md`

This document is the formal phase decomposition seed for the Agent Architecture Migration workstream. It does not renumber, replace, or override historical MOCA roadmap/demo phases. All phases in this document must be referenced as `AAM-P1` through `AAM-P11` in GSD planning, execution, review reports, and commit messages. Do not refer to these phases by bare `Phase 1`, `Phase 2`, etc.

This document is not an implementation plan for an individual phase. Each AAM phase still requires its own implementation plan using the traceability requirements in spec Section 19.

## 1. Readiness Rules

Every phase plan must start from coverage extraction against `docs/agent-architecture-spec.md`, then produce a phase-specific coverage matrix, then run coverage verification before execution.

Section 19 of `docs/agent-architecture-spec.md` is the default planning source of truth, not an unquestionable proof of correctness. Every AAM phase plan must check consistency between Section 19, this phase decomposition, current source evidence, and already generated planning artifacts. Any inconsistency must be raised explicitly in a `Spec Consistency Findings` / `Planning Deviations` section with original requirement, conflicting evidence, recommended handling, readiness impact, and owner.

AAM-P1 treats inconsistency discovery as a primary output: its value is to prevent AAM-P2/AAM-P3 from planning on top of an incorrect or self-inconsistent migration route, not to prove Section 19 is all correct.

A phase plan is not executable if any relevant spec area is `MISSING`.

If Section 19 or any target contract appears unreasonable, unsupported by current evidence, or inconsistent with decomposition/source facts, the baseline must allow `PARTIAL` or `MISSING` instead of forcing `COVERED`. Do not silently normalize conflicts away.

`PARTIAL` and `DEFERRED_WITH_OWNER` are allowed only when the plan names the owner phase, explains why the gap is non-blocking for the current phase, and defines an acceptance gate.

Coverage `Status` must use only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING`. `N/A` may appear only in owner/impact/eval/read-switch fields with a reason; it is not a valid status.

## 2. Global Phase Sequence

| Phase | Name | Capability boundary | Depends on | MVP gate? | Primary acceptance gate |
| --- | --- | --- | --- | --- | --- |
| AAM-P1 | Contract baseline | Spec-to-plan inventory and evidence baseline | none | yes | Contract inventory, current-vs-target checklist, initial coverage matrix, review checklist |
| AAM-P2 | Knowledge facade | Knowledge/RAG service boundary and EvidenceRefV1/citation contract | AAM-P1 | yes | Agent reads policy evidence through KnowledgeService facade with strong/partial/no-evidence contract tests |
| AAM-P3 | Business tool facade | Read business tool service boundary and ToolCallContext/ToolResultV2 | AAM-P1 | yes | Read tools go through BusinessToolService with permission/scope/error status contract tests |
| AAM-P4 | State lifecycle + routing migration | AgentState lifecycle, trusted context, deterministic routers, slot resolution seam | AAM-P2-3 | yes | State reset/property tests and router totality/determinism pass |
| AAM-P5 | Intent / clarification | Intent precedence, required-slot policy, ordinary clarification path | AAM-P4 | yes | Intent golden set, confidence/slot clarification tests, ordinary chat cannot create trusted approval decision |
| AAM-P6 | Session memory | PostgreSQL-backed same-thread session memory and active slot continuity; excludes long-term/case memory, memory_identity.v1, tombstones, embeddings, async extraction, review workflow, and authoritative Redis memory | AAM-P4-5 | yes | Session memory CAS, same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests |
| AAM-P7 | Approval state machine | Versioned approval request/level/assignment/decision/events and ActionSafetySnapshot owner | AAM-P5 | yes | Single-level approval runtime passes transition/revision/snapshot/hash/needs_info tests; multi-level-compatible schema/contract planning is verified; active SLA scanner remains deferred to the AAM-P7 SLA scanner follow-up gate |
| AAM-P8 | Demo action executor boundary | Durable draft-only demo action path and action draft snapshot binding | AAM-P7 | yes | Demo creates draft/draft_outcome only, no external side effect, no action_executions row |
| AAM-P9 | Replay event contract | ReplayEventV3, finalizer, sequence allocator, redaction/retention | AAM-P4, AAM-P6, AAM-P7, AAM-P8 | yes | `/replay` returns V3 lifecycle timeline for normal/interrupted/resumed/responded/rejected/expired/error/cancelled paths |
| AAM-P10 | Long-term/case memory | Deferred long-term and case memory service, memory_identity.v1, tombstone enforcement | AAM-P6, AAM-P9 | no | Memory identity/tombstone/review workflow contract tests pass without changing session memory fallback |
| AAM-P11 | External action execution | External adapters, action_executions, outbox, reconciliation, compensation | AAM-P8, AAM-P9 | no | Outbox claim-before-dispatch, unknown/reconciling, compensation authorization, duplicate execution/key guards pass |

## 3. Dependency Notes

- AAM-P2 and AAM-P3 may run in parallel after AAM-P1.
- AAM-P4 must wait for AAM-P2 and AAM-P3 because routing/state migration depends on stable service boundaries.
- AAM-P5 must wait for AAM-P4 because intent precedence and clarification rely on deterministic routing and slot resolution.
- AAM-P6 must wait for AAM-P4/AAM-P5 so session memory can inherit slots only after intent/slot contracts are stable. AAM-P6 uses PostgreSQL as the authoritative session memory store and must not introduce Redis as authoritative session memory.
- AAM-P6 explicitly excludes long-term memory, case memory, `memory_identity.v1`, tombstones, embeddings, asynchronous memory extraction, and review workflow; those remain owned by AAM-P10.
- AAM-P7 must wait for AAM-P5 because approval planning depends on validated intent/action/risk semantics.
- AAM-P8 must wait for AAM-P7 because demo action drafts must bind exact approval payload and safety snapshot hashes.
- AAM-P9 must wait for AAM-P4, AAM-P6, AAM-P7, and AAM-P8 because ReplayEventV3 must cover routing, memory write failure, approval, and action draft lifecycle.
- AAM-P10 is deferred beyond MVP and must not block AAM-P6 session memory fallback.
- AAM-P11 is deferred beyond MVP and must not weaken AAM-P8 demo draft safety.

## 4. Schema / Migration Ownership

| Schema area | Owner phase | Notes |
| --- | --- | --- |
| Knowledge facade persistence, if introduced | AAM-P2 | If AAM-P2 adds any persisted Knowledge facade schema, cache, audit, or adapter mapping table, AAM-P2 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the AAM-P2 plan |
| BusinessTool facade audit persistence, if introduced | AAM-P3 | If AAM-P3 adds tool audit, adapter result cache, or facade mapping tables, AAM-P3 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the AAM-P3 plan |
| `session_memories`, version CAS | AAM-P6 | Must support same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests. PostgreSQL is authoritative; Redis is not used for AAM-P6 session memory. |
| Approval request/level/assignment/decision/event versioning | AAM-P7 | Request/level/assignment CAS and mismatch transaction tests are required |
| `action_safety_snapshots` | AAM-P7 | Unique canonical snapshot/hash target; AAM-P8 references and validates it, AAM-P9 may add replay FK/backfill |
| `action_drafts` version/retention/snapshot binding fields | AAM-P8 | Demo path must not create `action_executions` |
| `agent_trace_events`, operation correlation, sequence/backfill/retention indexes | AAM-P9 | Approval/action replay FKs remain nullable until backfill verification |
| Long-term/case memory tables, `memory_tombstones`, memory identity/review indexes | AAM-P10 | Deferred beyond MVP; must not become policy evidence source |
| `action_executions`, `action_outbox_events`, `action_reconciliation_jobs`, `action_compensation_records` | AAM-P11 | External-only; outbox claim/lock indexes and retention indexes required |

All cross-phase FKs use nullable column -> deterministic backfill -> deferred nullable FK. Historical rows that cannot be resolved remain null and must be recorded in a migration report.

## 5. Global Coverage Matrix

| Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AgentState lifecycle | AAM-P4 | State reset/property tests; trusted field merge tests | N/A | none | Router/state rollback owner in AAM-P4 | Non-blocking unless state changes alter eval routes | COVERED |
| Router totality | AAM-P4 | Totality, determinism, invalid-state fallback tests | N/A | none | Router rollback owner in AAM-P4 | Intent route eval depends on this | COVERED |
| Intent/slot/ordinary clarification | AAM-P5, with AAM-P6 session continuity | Intent golden set; required-slot accuracy; clarification precision | N/A | Session continuity deferred to AAM-P6 with gate | Prompt/classifier rollback owner in AAM-P5 | Blocking for high-risk intent classes once AAM-P5 exits | COVERED |
| Approval needs_info resume | AAM-P7 | Wrong clarification id, wrong tenant/thread, stale version, payload/evidence changed, timeout/cancelled, old revision cannot execute | AAM-P7 approval schemas | none | Approval state rollback owner in AAM-P7 | Blocking for approval lifecycle golden flows | COVERED |
| EvidenceRefV1/citation/canonical hash | AAM-P2, AAM-P7 snapshot/hash | Retrieval/citation contract tests; canonical hash golden sample; score/rank projection tests | AAM-P7 for snapshot; AAM-P2 for knowledge facade schemas if persisted | none | Knowledge read-switch owner in AAM-P2; snapshot rollback owner in AAM-P7 | RAG groundedness/citation eval blocking for policy/action gates | COVERED |
| ToolCallContext/ToolResultV2 | AAM-P3 | Permission/scope, not_found, timeout, partial_success, invalid_response, raw payload forbidden | N/A unless tool audit tables added | none | BusinessToolService adapter rollback owner in AAM-P3 | Tool selection eval non-blocking unless route safety affected | COVERED |
| Session memory CAS | AAM-P6 | Same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, CAS conflict deterministic merge, session memory unavailable fallback, and memory-is-not-policy-evidence negative tests | AAM-P6 | Redis is excluded from authoritative session memory; long-term/case/identity/tombstone/embeddings/async extraction/review workflow deferred to AAM-P10 | Session memory read-switch/fallback owner in AAM-P6; rollback disables session memory reads/writes and falls back to checkpointer-only behavior with telemetry | AAM-P6 slot/session-memory route safety; memory write quality non-blocking unless slot inheritance changes route safety | COVERED |
| Long-term/case memory + memory_identity.v1 + tombstone | AAM-P10 | Identity normalization, source_ref normalization, tombstone no-rewrite, review workflow, retrieval predicate tests | AAM-P10 | Deferred beyond MVP; must not block session memory | AAM-P10 owner; rollback by memory type | Blocking only for AAM-P10 exit | DEFERRED_WITH_OWNER |
| Approval assignment/SLA/revision invalidation | AAM-P7 | Single-level assignment/version CAS, self approval, edit/respond invalidation, expired no resume; multi-level-compatible schema/contract tests; active SLA scanner follow-up gate | AAM-P7 | Multi-level runtime aggregation is not required for MVP AAM-P7; active SLA scanner deferred to AAM-P7 SLA scanner follow-up slice with replay-visible reminder/escalation/expire events as gate | AAM-P7 owner | Blocking for AAM-P7 approval readiness except deferred scanner automation gate | PARTIAL |
| `action_safety_snapshots` owner | AAM-P7 | Snapshot JSON/hash contract, unique tenant/hash, payload/snapshot mismatch invalidation | AAM-P7 | none | AAM-P7 owner; AAM-P8 only references/validates | Blocking for AAM-P7/8 safety gates | COVERED |
| Demo action boundary | AAM-P8 | Demo no side effect, no execution row, draft_outcome only, final response wording, hash mismatch forbidden | AAM-P8 action_draft fields | none | Demo draft rollback owner in AAM-P8 | Action safety eval blocks AAM-P8 exit | COVERED |
| External action/outbox/reconciliation/compensation | AAM-P11 | Claim-before-dispatch, duplicate active execution/key, unknown/reconciling, no-new-key retry, compensation authorization | AAM-P11 | Deferred beyond MVP with AAM-P11 owner | AAM-P11 owner; rollback per adapter | Blocking only for AAM-P11 exit | DEFERRED_WITH_OWNER |
| ReplayEventV3/finalizer/redaction/retention | AAM-P9 | V3 shape, sequence allocator, lifecycle completeness for normal/interrupted/resumed/responded/rejected/expired/error/cancelled, redaction, retention, access control | AAM-P9 | none | `/trace` compatibility fallback owner in AAM-P9 | Replay completeness eval blocks AAM-P9 exit | COVERED |
| Cross-table enforcement matrix | AAM-P7, AAM-P8, AAM-P11 | Relevant relationship rows and mismatch transaction tests copied into each AAM phase plan | AAM-P7, AAM-P8, AAM-P11 | Global owner exists, but each AAM phase plan must copy exact relevant Section 18.2 rows and mismatch tests; missing row mapping blocks that AAM phase | Relevant owner AAM phase | Blocking for affected schema AAM phase exit | PARTIAL |
| Migration rollout protocol | All schema phases | Backfill report, row-count/hash equality, tenant/run ownership, read-switch/fallback telemetry, negative mismatch tests | Relevant schema owner | none | Relevant schema owner | Non-blocking unless contract/eval gate says blocking | COVERED |
| Contract tests | Every phase | Phase-specific contract matrix rows | Relevant owner | none | N/A | As defined per phase | COVERED |
| Integration golden flows | AAM-P5, AAM-P7, AAM-P8, AAM-P9, AAM-P11 | Policy QA, refund troubleshooting, approval edit/respond/reject, demo action, external unknown, replay timelines | Relevant owner | Some external flows deferred to AAM-P11 | Relevant owner | Blocking for owning AAM phase | COVERED |
| Eval gates | AAM-P2, AAM-P5, AAM-P6, AAM-P7, AAM-P8, AAM-P9, AAM-P10, AAM-P11 as applicable | AAM-P2 RAG groundedness/citation; AAM-P5 risk-weighted intent and clarification; AAM-P6 slot/session-memory route safety; AAM-P7 approval policy accuracy; AAM-P8 action safety; AAM-P9 replay completeness; AAM-P10 memory write quality; AAM-P11 external action safety | N/A | Each AAM phase plan must mark blocking/non_blocking, dataset owner/version/hash, and failure impact; until then this row remains PARTIAL | N/A | Explicit per AAM phase before execution | PARTIAL |
| Explicit non-goals | Every phase | Review checklist and coverage verification | N/A | none | N/A | N/A | COVERED |
| Phase planning follow-up register | Every phase | Each phase plan outputs disposition for applicable follow-up items; missing disposition becomes MISSING | N/A | Register exists globally; each phase plan must mark every applicable item as covered, deferred with owner, or not applicable in owner/impact fields while Status remains one of the four allowed statuses | N/A | N/A | PARTIAL |

## 6. Phase Planning Follow-up Register

These items must remain visible during phase decomposition. They are not optional notes from a prior review; they are inputs to coverage extraction.

| Follow-up item | Required handling during phase decomposition | Owner / gate |
| --- | --- | --- |
| AAM-P1 baseline artifact names | AAM-P1 plan must expand `Contract baseline` into contract inventory, current-vs-target evidence checklist, initial coverage matrix, and review checklist. | AAM-P1 acceptance gate |
| Read-switch owner/config visibility | Any schema/service migration phase must name read-switch owner, config/feature flag, fallback telemetry, and rollback behavior; write `N/A` with reason when absent. | Relevant schema owner phase |
| Redis memory boundary | AAM-P6 and any later memory-related phase must record that PostgreSQL is the authoritative memory store. Redis may only be used for non-authoritative short TTL lock, rate limit, debounce, SSE buffer, worker hint, or temporary cache; keys must be scoped, TTL mandatory, Postgres fallback required, Redis loss must not affect correctness, and Postgres CAS remains the session memory correctness boundary. | AAM-P6/AAM-P10 acceptance gates as applicable |
| AAM-P7 internal slices | AAM-P7 plan must split approval schema/CAS, snapshot builder/hash golden tests, `needs_info` resume, and SLA/assignment semantics. | AAM-P7 acceptance gate |
| Cross-table enforcement row mapping | AAM-P7/8/11 plans must copy relevant rows from the spec Section 18.2 cross-table enforcement matrix and list required mismatch tests. | AAM-P7/8/11 acceptance gates |
| PARTIAL/deferred status discipline | Every `PARTIAL` / `DEFERRED_WITH_OWNER` row must name owner phase, non-blocking rationale, blocking dependency, and acceptance gate. Otherwise it becomes `MISSING`. | Each phase readiness verdict |
| Eval gate blocking status | Every relevant eval gate must name blocking/non_blocking status, dataset owner/version/hash, and phase exit impact. | Relevant phase exit criteria |

## 7. Next Planning Order

1. Write AAM-P1 implementation plan.
2. Use AAM-P1 to produce the contract inventory and initial coverage verification artifact.
3. Plan AAM-P2 and AAM-P3, which may execute in parallel after AAM-P1 exits.
4. Plan AAM-P4 only after AAM-P2/AAM-P3 service boundary outputs are accepted.
5. Continue sequentially through MVP AAM-P5 through AAM-P9.
6. Keep AAM-P10 and AAM-P11 as deferred owner phases unless a later milestone explicitly pulls them forward.
