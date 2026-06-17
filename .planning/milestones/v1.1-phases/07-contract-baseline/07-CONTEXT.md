# Phase 7: Contract Baseline - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning
**Source:** `/gsd-plan-phase` request + Agent Architecture Migration milestone docs

<domain>
## Phase Boundary

Phase 7 is the contract-baseline phase for the Agent Architecture Migration milestone. It is not a renumbering of historical MOCA Phase 1 and continues the roadmap after archived Phases 1-6.

Phase 7 is docs-only. It must produce planning and review artifacts that downstream Phase 8 through Phase 17 can consume before source implementation starts.

Required outputs:

- Contract inventory.
- Current-vs-target evidence checklist.
- Initial coverage matrix.
- Spec consistency findings / planning deviations.
- Identifier semantics.
- Boris/GSD phase notes.
- Review checklist.
- Readiness verdict.
- Phase planning follow-up register disposition for every applicable item, using only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING` in the `Status` column.

Phase 7 must not change source code, schemas, migrations, tests, API contracts, or runtime behavior.
</domain>

<decisions>
## Implementation Decisions

### Phase Identity
- Use `Phase 7` in artifact names, headings, review reports, and suggested commit messages.
- Do not refer to this workstream phase as bare `Phase 1`.
- Store Phase 7 planning artifacts in `.planning/phases/07-contract-baseline/` because `gsd-sdk init.plan-phase` now maps Phase 7 through the registered v1.1 roadmap.

### Output Scope
- Phase 7 execution should create docs/artifacts only.
- Phase 7 plans must treat target architecture fields as target contracts unless current source evidence proves they are implemented.
- Current implementation evidence must cite concrete source files or docs.
- Target contract rows must include owner phase, tests/eval gate, migration/read-switch owner, and status discipline where applicable.
- Section 19 is a default planning source of truth, not proof that every target or owner assignment is correct.
- If Section 19, phase decomposition, current source evidence, or Phase 7 artifacts conflict, the baseline must record the inconsistency explicitly and assign readiness impact/owner.
- If a Section 19 item is unreasonable or unsupported, mark it `PARTIAL` or `MISSING` as appropriate instead of forcing `COVERED`.

### Status Vocabulary
- Coverage `Status` values must be exactly one of: `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `MISSING`.
- `N/A` is not allowed in any `Status` column.
- `N/A` may appear only in owner, impact, eval, migration, or read-switch fields with a reason.

### Follow-up Register
- Every item in `docs/agent-architecture-phase-decomposition.md` Section 6 must be explicitly dispositioned.
- For Phase 7, `Phase 7 baseline artifact names` is blocking and must be `COVERED` only after all required baseline artifact sections exist.
- Follow-up items owned by later phases must still be recorded as `DEFERRED_WITH_OWNER` with owner phase, rationale, and acceptance gate.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing Phase 7.

### Agent Architecture Migration milestone Source
- `docs/agent-architecture-spec.md` redirect index - target architecture, current-vs-target facts, contract schemas, lifecycle/state/router/tool/approval/action/replay requirements, traceability requirements.
- `docs/agent-architecture-phase-decomposition.md` - phase sequence, readiness rules, global coverage matrix, follow-up register, next planning order.
- `docs/agent-architecture-spec-review.md` - review findings that motivate contract-table completeness and migration/readiness discipline.

### Current MOCA Source Evidence
- `src/agent/graph.py` - current LangGraph nodes and conditional routes.
- `src/agent/state.py` - current AgentState persistent/ephemeral fields and dormant investigation fields.
- `src/agent/tools/contracts.py` - current tool registry/invocation result contract.
- `src/agent/tools/registry.py` - current registered investigator-visible read/retrieval tools and validation rules.
- `src/rag/schemas.py` - current retrieval/evidence result shape.
- `src/db/models.py` - current persisted AgentRun, AgentStep, ApprovalRequest, ApprovalStep, ActionDraft, business, policy, and audit models.
- `tests/` - existing verification surface for graph, RAG, approvals, tools, trace, and registry behavior.

### Planning State
- `.planning/ROADMAP.md` - v1.0 Phases 1-6 are archived and v1.1 Agent Architecture Migration is registered as Phases 7-17.
- `.planning/REQUIREMENTS.md` - v1.1 Agent Architecture Migration requirements and traceability.
- `.planning/STATE.md` - current GSD state; confirms Phase 7 completion and Phase 8/Phase 9 planning readiness.
</canonical_refs>

<specifics>
## Specific Evidence Already Confirmed

- `gsd-sdk query roadmap.analyze --raw` recognizes the registered v1.1 roadmap as standard Phases 7-17 and identifies Phase 8 as the next phase.
- `docs/agent-architecture-phase-decomposition.md` uses standard Phase 7-17 identities aligned with `.planning/ROADMAP.md`.
- `docs/agent-architecture-phase-decomposition.md` says Phase 7 acceptance gate is contract inventory, current-vs-target checklist, initial coverage matrix, and review checklist.
- `src/agent/state.py` currently has persistent memory fields, ephemeral fields, approval/action fields, and dormant future investigation fields.
- `src/agent/graph.py` currently has 10 graph nodes and simple risk/approval conditional routing.
- `src/agent/tools/contracts.py` and `src/agent/tools/registry.py` currently implement a typed registry for four investigator-visible read/retrieval tools.
- `src/rag/schemas.py` currently has `EvidenceItem` and `RetrievalResult`, but not canonical `EvidenceRefV1` with tenant/policy/hash/retrieval config fields.
- `src/db/models.py` currently has AgentRun/AgentStep, ApprovalRequest/ApprovalStep, ActionDraft, business data, policy data, and AuditLog models; it does not show the full Phase 7-17 target approval/action/replay/memory schema set.
</specifics>

<deferred>
## Deferred Ideas

These are not Phase 7 implementation work. They must be assigned to owner phases in the baseline artifacts:

- Knowledge facade and canonical EvidenceRefV1 implementation: Phase 8.
- BusinessToolService and ToolCallContext/ToolResultV2 implementation: Phase 9.
- AgentState lifecycle, trusted context, router totality, slot resolution migration: Phase 10.
- Intent/clarification contract implementation: Phase 11.
- Session memory implementation: Phase 12.
- Approval state machine, ActionSafetySnapshot, hash profile, needs_info, SLA/assignment semantics: Phase 13.
- Demo action executor boundary: Phase 14.
- ReplayEventV3/finalizer/redaction/retention: Phase 15.
- Long-term/case memory: Phase 16.
- External action/outbox/reconciliation/compensation: Phase 17.
</deferred>

---

*Phase: Phase 7-contract-baseline*
*Context gathered: 2026-06-06 via GSD plan-phase adaptation for Agent Architecture Migration milestone*
