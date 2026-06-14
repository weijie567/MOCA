# Agent Architecture Migration Phase Decomposition

Normative contract source: `docs/contract-spec.md`

Migration/process source: `docs/migration-plan.md` Section 19

This document is the formal phase decomposition seed for the v1.1 Agent Architecture Migration milestone. Historical v1.0 remains archived as Phases 1-6. All phases in this document use the standard GSD roadmap identities `Phase 7` through `Phase 17`; there is no separate prefixed phase namespace.

This document is not an implementation plan for an individual phase. Each phase still requires its own implementation plan using the traceability requirements in `docs/migration-plan.md` Section 19.

## 1. Readiness Rules

Every phase plan must start from coverage extraction against `docs/contract-spec.md`, `docs/migration-plan.md` Section 19, `docs/eval-test-plan.md`, and `docs/architecture-overview.md`, then produce a phase-specific coverage matrix, then run coverage verification before execution.

`docs/migration-plan.md` Section 19 is the default planning source of truth, not an unquestionable proof of correctness. Every phase plan must check consistency between Section 19, this phase decomposition, current source evidence, and already generated planning artifacts. Any inconsistency must be raised explicitly in a `Spec Consistency Findings` / `Planning Deviations` section with original requirement, conflicting evidence, recommended handling, readiness impact, and owner.

Phase 7 treats inconsistency discovery as a primary output: its value is to prevent Phase 8/Phase 9 from planning on top of an incorrect or self-inconsistent migration route, not to prove Section 19 is all correct.

A phase plan is not executable if any relevant spec area is `MISSING`.

If Section 19 or any target contract appears unreasonable, unsupported by current evidence, or inconsistent with decomposition/source facts, the baseline must allow `PARTIAL` or `MISSING` instead of forcing `COVERED`. Do not silently normalize conflicts away.

`PARTIAL` and `DEFERRED_WITH_OWNER` are allowed only when the plan names the owner phase, explains why the gap is non-blocking for the current phase, and defines an acceptance gate.

Coverage `Status` must use only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING`. `N/A` may appear only in owner/impact/eval/read-switch fields with a reason; it is not a valid status.

### Deviation Handling Protocol

When phase planning finds a conflict between the blueprint, Section 19, phase decomposition, current source evidence, or prior planning artifacts, the phase plan must treat it as a formal `Spec Consistency Finding` / `Planning Deviation`, not silently normalize it.

Required deviation table fields:

| Field | Required meaning |
| --- | --- |
| `ID` | Stable phase-local id, for example `P8-SCF-01` or `P10-DEV-02` |
| `Source requirement` | Original requirement with file/section reference |
| `Conflicting evidence` | Conflicting doc/code/planning evidence with file/section or source path |
| `Type` | `SPEC_CONFLICT`, `CODE_MISMATCH`, `UNSUPPORTED_ASSUMPTION`, `OWNER_DRIFT`, or `PHASE_BOUNDARY_RISK` |
| `Recommended handling` | Blueprint update, phase-boundary adjustment, fallback/degraded implementation, defer-with-owner, or block |
| `Readiness impact` | `NON_BLOCKING`, `BLOCKS_EXECUTION`, `BLOCKS_EXIT`, or `REQUIRES_BLUEPRINT_UPDATE` |
| `Owner` | Current phase, downstream owner phase, or blueprint/docs owner |
| `Status` | `OPEN`, `ACCEPTED_DEVIATION`, `RESOLVED`, or `DEFERRED_WITH_OWNER` |

Execution rules:

- A phase may continue planning when every deviation has an owner, a readiness impact, and an acceptance gate.
- A phase may continue execution only when deviations are `NON_BLOCKING` for that phase's exit criteria, fallback behavior is explicit, and tests verify the actual behavior.
- A phase must pause before execution when any relevant deviation is `MISSING`, ownerless, weakens a security/safety boundary, reverses a phase dependency, or makes the phase output contradict `docs/contract-spec.md`.
- If a deviation changes a normative contract, update `docs/contract-spec.md`; if it changes owner/sequencing, update this decomposition and `docs/migration-plan.md`; if it changes eval/test gates, update `docs/eval-test-plan.md` and the phase plan.
- Do not mark a row `COVERED` while an unresolved deviation affects that row's contract, owner, migration/read-switch, test gate, or current-vs-target evidence.

## 2. Global Phase Sequence

| Phase | Name | Capability boundary | Depends on | MVP gate? | Primary acceptance gate |
| --- | --- | --- | --- | --- | --- |
| Phase 7 | Contract baseline | Spec-to-plan inventory, evidence baseline, and shared foundation contracts | none | yes | Contract inventory, current-vs-target checklist, initial coverage matrix, review checklist, and shared contract freeze |
| Phase 8 | Knowledge facade | Knowledge/RAG service boundary and EvidenceRefV1/citation contract | Phase 7 | yes | Agent reads policy evidence through KnowledgeService facade with strong/partial/no-evidence contract tests |
| Phase 9 | Business tool facade | Read business tool service boundary and ToolCallContext/ToolResultV2 | Phase 7 | yes | Read tools go through BusinessToolService with permission/scope/error status contract tests |
| Phase 10 | State lifecycle + routing migration | Implement the Phase-7-frozen AgentState identity/router seam and trusted-context projections; deterministic routers and slot resolution; minimal event emitter/allocator/base table | Phase 8 and Phase 9 | yes | Full state reset/property tests and router totality/determinism pass; minimal event emitter + per-run sequence allocator land |
| Phase 11 | Intent / clarification | Intent precedence, required-slot policy, ordinary clarification path | Phase 10 | yes | Intent golden set, confidence/slot clarification tests, ordinary chat cannot create trusted approval decision |
| Phase 12 | Session memory | PostgreSQL-authoritative same-thread session memory and active slot continuity; Redis is optional only as a non-authoritative hot cache with TTL and Postgres fallback; excludes long-term/case memory, memory_identity.v1, tombstones, embeddings, async extraction, review workflow, and authoritative Redis memory | Phase 10 and Phase 11 | yes | Session memory CAS, same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, Redis/cache-miss fallback if used, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests |
| Phase 13 | Approval state machine | Internal slices only: 13a approval state machine/CAS/revision; 13b ActionSafetySnapshot + CanonicalHashProfile + hash binding; 13c `needs_info` resume; SLA scanner implemented feature-disabled | Phase 11 | yes | Slices 13a/13b/13c pass transition/revision/snapshot/hash/needs_info tests; multi-level-compatible schema/contract planning is verified; SLA scanner remains feature-disabled until Phase 15 replay is in place |
| Phase 14 | Demo action executor boundary | Durable draft-only demo action path and action draft snapshot binding | Phase 13 | yes | Demo creates draft/draft_outcome only, no external side effect, no action_executions row |
| Phase 15 | Full replay service | Full ReplayEventV3 lifecycle, finalizer, redaction/retention, and `/replay` API on the Phase-7/Phase-10 minimal event envelope | Phase 10, Phase 12, Phase 13, Phase 14 | yes | `/replay` returns V3 lifecycle timeline for normal/interrupted/resumed/responded/rejected/expired/error/cancelled paths |
| Phase 16 | Long-term/case memory | Deferred long-term and case memory service, memory_identity.v1, tombstone enforcement | Phase 12, Phase 15 | no | Memory identity/tombstone/review workflow contract tests pass without changing session memory fallback |
| Phase 17 | External action execution | External adapters, action_executions, outbox, reconciliation, compensation | Phase 14, Phase 15 | no | Outbox claim-before-dispatch, unknown/reconciling, compensation authorization, duplicate execution/key guards pass |

### Shared Contracts (Phase 7-owned prerequisite, consumed before Phase 8)

- Canonical `TrustedContext`.
- Canonical Schema Ownership rule.
- Minimal Event Envelope.
- AgentState identity/router-seam contract.

这些 shared contracts 不是新 phase number；它们是 Phase-7-owned prerequisites。Phase 8 与 Phase 9 在 shared contract 冻结后可并行；Phase 9 business tool results 使用独立 business_fact_refs，不复用 policy EvidenceRefV1。Foundation contracts 必须先于 capability facades（B4/F7）；Phase 10 保留完整 reset/property/totality tests 和实现迁移责任。

## 3. Dependency Notes

- Phase 8 and Phase 9 may run in parallel after Phase 7 once the canonical TrustedContext, schema ownership rule, minimal event envelope, and AgentState identity/router-seam contract are frozen. Phase 9 business tool results carry their own `business_fact_refs` provenance and do not reuse the policy EvidenceRefV1, so Phase 9 has no schema dependency on Phase 8.
- Phase 10 must wait for Phase 8 and Phase 9 because routing/state migration depends on stable service boundaries.
- Phase 10 is split into internal slices (no new top-level phase numbers): 10a trusted-context/state lifecycle, 10b routing/slot seam, 10c minimal event foundation (emitter/append API/per-run sequence allocator/base table). Each slice has its own acceptance gate; allocator concurrency tests and state/router totality tests must not share a single ambiguous gate.

| Slice | Scope | Acceptance gate |
| --- | --- | --- |
| 10a trusted-context/state lifecycle | TrustedContext projection construction from graph/run config; AgentState identity/reset/merge lifecycle | Trusted fields not LLM-overwritable; no stale permissions/merchant_scope persisted in AgentState; reset/property tests pass |
| 10b routing/slot seam | deterministic routers, slot resolution, empty long-term/case memory read seam | router totality/determinism tests; required-slot expression tests; empty-adapter seam present |
| 10c minimal event foundation | minimal envelope emitter, append API, per-run sequence allocator, base event table | minimal envelope shape tests; allocator concurrency tests; monotonic sequence; read-switch/rollback owner named |

- Phase 11 must wait for Phase 10 because intent precedence and clarification rely on deterministic routing and slot resolution.
- Phase 10 and Phase 11 must reserve an empty-adapter read seam for `long_term_memory` / `case_memory`, so Phase 16 does not re-open router or recommendation contracts.
- Phase 12 must wait for Phase 10/Phase 11 so session memory can inherit slots only after intent/slot contracts are stable. Phase 12 uses PostgreSQL as the authoritative session memory store. Redis may be added only as a non-authoritative hot cache with tenant/user/thread-scoped keys, mandatory TTL, Postgres fallback, and no correctness dependency.
- Phase 12 explicitly excludes long-term memory, case memory, `memory_identity.v1`, tombstones, embeddings, asynchronous memory extraction, and review workflow; those remain owned by Phase 16.
- Phase 13 must wait for Phase 11 because approval planning depends on validated intent/action/risk semantics. Phase 13 is split only into internal slices: 13a approval state machine/CAS/revision, 13b ActionSafetySnapshot + CanonicalHashProfile + hash binding, and 13c `needs_info` resume; the SLA scanner is implemented feature-disabled in Phase 13 and enabled only after Phase 15 replay is in place, not as a new phase number.

| Slice | Scope | Schema owner | Required tests | Exit gate |
| --- | --- | --- | --- | --- |
| 13a approval state machine/CAS/revision | Approval request/level/assignment/decision transitions, CAS, revision invalidation | Phase 13 approval schemas | transition table, CAS conflict, self-approval, stale revision tests | Single-level runtime and multi-level-compatible contracts pass |
| 13b ActionSafetySnapshot + CanonicalHashProfile + hash binding | Snapshot schema, canonical projection/hash, exact action/snapshot binding | Phase 13 snapshot/hash schemas | snapshot golden, canonical hash, payload/evidence/config mismatch tests | Exact payload and snapshot hash guards pass |
| 13c `needs_info` resume | Trusted clarification binding, revalidation, revisioned resume | Phase 13 approval/resume contracts | wrong id/scope/version, changed payload/evidence, timeout/cancel tests | Old revision cannot execute; validated revision resumes safely |
| SLA scanner | Implement reminder/escalation/expire scanner feature-disabled in Phase 13 | Phase 13 SLA/event contracts | disabled-by-default and event-shape tests | Remains feature-disabled in Phase 13; enabled only after Phase 15 replay is in place |

- Phase 14 must wait for Phase 13 because demo action drafts must bind exact approval payload and safety snapshot hashes.
- The minimal event envelope is a Phase-7/Phase-10 prerequisite used by Phase 10-14 event emitters. Phase 10 owns the minimal emitter, append API, per-run sequence allocator, base event table, event registry mechanism, and base node/tool/RAG/LLM lifecycle events. Phase 12 registers memory-write event additions; Phase 13 registers approval event additions; Phase 14 registers `action_draft_created`. These additions use the Phase 10 envelope/allocator/redaction rules and are registered before emitters are enabled. Phase 15 waits for Phase 10, Phase 12, Phase 13, and Phase 14 and owns full ReplayEventV3 enrichment, read API, redaction/retention, validation/backfill, plus external-action/reconciliation event additions deferred to Phase 17.
- Phase 16 is deferred beyond MVP and must not block Phase 12 session memory fallback.
- Phase 17 is deferred beyond MVP and must not weaken Phase 14 demo draft safety.

## 4. Schema / Migration Ownership

| Schema area | Owner phase | Notes |
| --- | --- | --- |
| Knowledge facade persistence, if introduced | Phase 8 | If Phase 8 adds any persisted Knowledge facade schema, cache, audit, or adapter mapping table, Phase 8 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the Phase 8 plan |
| BusinessTool facade audit persistence, if introduced | Phase 9 | If Phase 9 adds tool audit, adapter result cache, or facade mapping tables, Phase 9 owns its migration/backfill/read-switch; otherwise write `N/A` with reason in the Phase 9 plan |
| `session_memories`, version CAS | Phase 12 | Must support same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, read-switch/fallback telemetry, and memory-is-not-policy-evidence negative tests. PostgreSQL is authoritative; Redis has no schema ownership and, if used, is only a TTL hot cache with PostgreSQL fallback. |
| Approval request/level/assignment/decision/event versioning | Phase 13 | Request/level/assignment CAS and mismatch transaction tests are required |
| `action_safety_snapshots` | Phase 13 | Unique canonical snapshot/hash target; Phase 14 references and validates it, Phase 15 may add replay FK/backfill |
| `action_drafts` version/retention/snapshot binding fields | Phase 14 | Demo path must not create `action_executions` |
| Minimal event base table + per-run sequence allocator | Phase 10 | Phase 10 owns the minimal-envelope base event table (initial `agent_trace_events` column subset) and the per-run sequence allocator/append API used by Phase 10-14 emitters |
| Domain event registry additions | Phase 10 / Phase 12 / Phase 13 / Phase 14 | Phase 10 owns base node/tool/RAG/LLM lifecycle events; Phase 12 owns memory-write additions; Phase 13 owns approval additions; Phase 14 owns `action_draft_created`; all register on the Phase-10 event registry before emitters are enabled |
| `agent_trace_events` full V3 extension, operation correlation, sequence/backfill/retention indexes | Phase 15 | Phase 15 extends the Phase-10 base table with full ReplayEventV3 columns; approval/action replay FKs remain nullable until backfill verification |
| Long-term/case memory tables, `memory_tombstones`, memory identity/review indexes | Phase 16 | Deferred beyond MVP; must not become policy evidence source |
| `action_executions`, `action_outbox_events`, `action_reconciliation_jobs`, `action_compensation_records` | Phase 17 | External-only; outbox claim/lock indexes and retention indexes required |

All cross-phase FKs use nullable column -> deterministic backfill -> deferred nullable FK. Historical rows that cannot be resolved remain null and must be recorded in a migration report.

## 5. Planning Ownership Coverage Matrix

`COVERED` means planning ownership/acceptance is defined, not that the capability is implemented.

| Spec area | Covered by phase | Required tests | Migration owner | Gap / owner gate | Read-switch / rollback owner | Eval gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AgentState lifecycle | Phase 10 | State reset/property tests; trusted field merge tests | N/A | none | Router/state rollback owner in Phase 10 | Non-blocking unless state changes alter eval routes | COVERED |
| Router totality | Phase 10 | Totality, determinism, invalid-state fallback tests | N/A | none | Router rollback owner in Phase 10 | Intent route eval depends on this | COVERED |
| Intent/slot/ordinary clarification | Phase 11, with Phase 12 session continuity | Intent golden set; required-slot accuracy; clarification precision | N/A | Session continuity deferred to Phase 12 with gate | Prompt/classifier rollback owner in Phase 11 | Blocking for high-risk intent classes once Phase 11 exits | COVERED |
| Approval needs_info resume | Phase 13 | Wrong clarification id, wrong tenant/thread, stale version, payload/evidence changed, timeout/cancelled, old revision cannot execute | Phase 13 approval schemas | none | Approval state rollback owner in Phase 13 | Blocking for approval lifecycle golden flows | COVERED |
| EvidenceRefV1/citation/canonical hash | Phase 8, Phase 13 snapshot/hash | Retrieval/citation contract tests; canonical hash golden sample; score/rank projection tests | Phase 13 for snapshot; Phase 8 for knowledge facade schemas if persisted | none | Knowledge read-switch owner in Phase 8; snapshot rollback owner in Phase 13 | RAG groundedness/citation eval blocking for policy/action gates | COVERED |
| ToolCallContext/ToolResultV2 | Phase 9 | Permission/scope, not_found, timeout, partial_success, invalid_response, raw payload forbidden | N/A unless tool audit tables added | none | BusinessToolService adapter rollback owner in Phase 9 | Tool selection eval non-blocking unless route safety affected | COVERED |
| Session memory CAS | Phase 12 | Same-thread continuity, cross-thread/user/tenant isolation, stale slot exclusion, explicit slot override, typed `session_slots.v1`, CAS conflict deterministic merge, session memory unavailable/cache-miss fallback, and memory-is-not-policy-evidence negative tests | Phase 12 | Redis is excluded from authoritative session memory and may only be a TTL hot cache; long-term/case/identity/tombstone/embeddings/async extraction/review workflow deferred to Phase 16 | Session memory read-switch/fallback owner in Phase 12; rollback disables session memory reads/writes and falls back to checkpointer-only behavior with telemetry; Redis loss must fall back to Postgres if Redis is introduced | Phase 12 slot/session-memory route safety; memory write quality non-blocking unless slot inheritance changes route safety | COVERED |
| Long-term/case memory + memory_identity.v1 + tombstone | Phase 16 | Identity normalization, source_ref normalization, tombstone no-rewrite, review workflow, retrieval predicate tests | Phase 16 | Deferred beyond MVP; must not block session memory | Phase 16 owner; rollback by memory type | Blocking only for Phase 16 exit | DEFERRED_WITH_OWNER |
| Approval assignment/SLA/revision invalidation | Phase 13 | Single-level assignment/version CAS, self approval, edit/respond invalidation, expired no resume; multi-level-compatible schema/contract tests; SLA scanner disabled-by-default tests | Phase 13 | Multi-level runtime aggregation is not required for MVP Phase 13; SLA scanner is implemented feature-disabled in Phase 13 and enabled only after Phase 15 replay is in place | Phase 13 owner | Blocking for Phase 13 approval readiness; scanner enablement gated by Phase 15 | PARTIAL |
| `action_safety_snapshots` owner | Phase 13 | Snapshot JSON/hash contract, unique tenant/hash, payload/snapshot mismatch invalidation | Phase 13 | none | Phase 13 owner; Phase 14 only references/validates | Blocking for Phase 13/Phase 14 safety gates | COVERED |
| Demo action boundary | Phase 14 | Demo no side effect, no execution row, draft_outcome only, final response wording, hash mismatch forbidden | Phase 14 action_draft fields | none | Demo draft rollback owner in Phase 14 | Action safety eval blocks Phase 14 exit | COVERED |
| External action/outbox/reconciliation/compensation | Phase 17 | Claim-before-dispatch, duplicate active execution/key, unknown/reconciling, no-new-key retry, compensation authorization | Phase 17 | Deferred beyond MVP with Phase 17 owner | Phase 17 owner; rollback per adapter | Blocking only for Phase 17 exit | DEFERRED_WITH_OWNER |
| Minimal event foundation (emitter/allocator/base table) | Phase 10 | Per-run sequence allocator concurrency, minimal envelope shape, started/terminal pairing on base table | Phase 10 | none | Phase 10 owner | Non-blocking unless event gaps block replay eval | COVERED |
| ReplayEventV3/finalizer/redaction/retention | Phase 15 | V3 extension shape, lifecycle completeness for normal/interrupted/resumed/responded/rejected/expired/error/cancelled, redaction, retention, access control | Phase 10 for allocator/base table; Phase 15 for V3 extension/backfill | none | Phase 15 owns V3 read API/retention/backfill rollback; Phase 10 owns base-table rollback | Replay completeness eval blocks Phase 15 exit | COVERED |
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
| Read-switch owner/config visibility | Type-split rule: (a) schema-introducing phases 10/12/13/14/15/17 must name read-switch owner, config/feature flag, fallback telemetry, and rollback behavior; Phase 10's minimal event base table follows the schema-introducing read-switch/rollback discipline; (b) service-only refactor phases 8/9 default to direct cutover with rollback by git revert + retained adapter and may write `N/A with reason: service-only refactor` in the read-switch field. | Relevant schema owner phase or Phase 8/Phase 9 service owner |
| Redis memory boundary | Phase 12 and any later memory-related phase must record that PostgreSQL is the authoritative memory/checkpoint source of truth. Redis may only be used for non-authoritative active-session hot cache, active-run hot checkpoint cache, short TTL lock, rate limit, debounce, SSE buffer, worker hint, or temporary cache; keys must be scoped, TTL mandatory, Postgres fallback required, Redis loss must not affect correctness/audit/replay/approval/action safety, and Postgres CAS remains the session memory correctness boundary. | Phase 12/Phase 16 acceptance gates as applicable |
| Phase 13 internal slices | Phase 13 plan must formalize internal slices only: 13a approval state machine/CAS/revision; 13b ActionSafetySnapshot + CanonicalHashProfile + hash binding; 13c `needs_info` resume. The SLA scanner is implemented feature-disabled in Phase 13 and enabled after Phase 15 replay is in place. No new top-level phase numbers. | Phase 13 acceptance gate; Phase 15 enablement gate |
| Deferred memory read seam | Phase 10/Phase 11 must reserve an empty-adapter `long_term_memory` / `case_memory` read seam before Phase 16 implementation. | Phase 10/Phase 11 acceptance gates; Phase 16 consumer |
| Cross-table enforcement row mapping | Phase 13/Phase 14/Phase 17 plans must copy relevant rows from the `docs/contract-spec.md` Section 18.2 cross-table enforcement matrix and list required mismatch tests. | Phase 13/Phase 14/Phase 17 acceptance gates |
| PARTIAL/deferred status discipline | Every `PARTIAL` / `DEFERRED_WITH_OWNER` row must name owner phase, non-blocking rationale, blocking dependency, and acceptance gate. Otherwise it becomes `MISSING`. | Each phase readiness verdict |
| Eval gate blocking status | Every relevant eval gate must name blocking/non_blocking status, dataset owner/version/hash, and phase exit impact. | Relevant phase exit criteria |

## 7. Next Planning Order

1. Write Phase 7 implementation plan.
2. Use Phase 7 to produce the contract inventory and initial coverage verification artifact.
3. Plan Phase 8 and Phase 9; they may execute in parallel after Phase 7 exits (Phase 9 business tool results use their own business_fact_refs, no Phase 8 EvidenceRefV1 dependency).
4. Plan Phase 10 only after Phase 8/Phase 9 service boundary outputs are accepted.
5. Continue sequentially through MVP Phase 11 through Phase 15.
6. Keep Phase 16 and Phase 17 as deferred owner phases unless a later milestone explicitly pulls them forward.
