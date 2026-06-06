# AAM-P1: Contract Baseline - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning
**Source:** `/gsd-plan-phase` request + AAM workstream docs

<domain>
## Phase Boundary

AAM-P1 is the contract-baseline phase for the Agent Architecture Migration workstream. It is not historical MOCA Phase 1 and must not renumber or replace `.planning/ROADMAP.md` phases 1-11.

AAM-P1 is docs-only. It must produce planning and review artifacts that downstream AAM-P2 through AAM-P11 can consume before source implementation starts.

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

AAM-P1 must not change source code, schemas, migrations, tests, API contracts, or runtime behavior.
</domain>

<decisions>
## Implementation Decisions

### Phase Identity
- Use `AAM-P1` in artifact names, headings, review reports, and suggested commit messages.
- Do not refer to this workstream phase as bare `Phase 1`.
- Store AAM-P1 planning artifacts in `.planning/phases/AAM-P1-contract-baseline/` because `gsd-sdk init.plan-phase` does not map `AAM-P1` to the historical MOCA roadmap phase directories.

### Output Scope
- AAM-P1 execution should create docs/artifacts only.
- AAM-P1 plans must treat target architecture fields as target contracts unless current source evidence proves they are implemented.
- Current implementation evidence must cite concrete source files or docs.
- Target contract rows must include owner phase, tests/eval gate, migration/read-switch owner, and status discipline where applicable.
- Section 19 is a default planning source of truth, not proof that every target or owner assignment is correct.
- If Section 19, phase decomposition, current source evidence, or AAM-P1 artifacts conflict, the baseline must record the inconsistency explicitly and assign readiness impact/owner.
- If a Section 19 item is unreasonable or unsupported, mark it `PARTIAL` or `MISSING` as appropriate instead of forcing `COVERED`.

### Status Vocabulary
- Coverage `Status` values must be exactly one of: `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `MISSING`.
- `N/A` is not allowed in any `Status` column.
- `N/A` may appear only in owner, impact, eval, migration, or read-switch fields with a reason.

### Follow-up Register
- Every item in `docs/agent-architecture-phase-decomposition.md` Section 6 must be explicitly dispositioned.
- For AAM-P1, `AAM-P1 baseline artifact names` is blocking and must be `COVERED` only after all required baseline artifact sections exist.
- Follow-up items owned by later phases must still be recorded as `DEFERRED_WITH_OWNER` with owner phase, rationale, and acceptance gate.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing AAM-P1.

### AAM Workstream Source
- `docs/agent-architecture-spec.md` - target architecture, current-vs-target facts, contract schemas, lifecycle/state/router/tool/approval/action/replay requirements, traceability requirements.
- `docs/agent-architecture-phase-decomposition.md` - AAM phase sequence, readiness rules, global coverage matrix, follow-up register, next planning order.
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
- `.planning/ROADMAP.md` - historical MOCA roadmap; must not be renumbered or overwritten by AAM-P1.
- `.planning/REQUIREMENTS.md` - v1.1 Agentic Investigation requirements; useful current-state context but not the AAM phase source of truth.
- `.planning/STATE.md` - current GSD state; confirms current focus on historical Phase 08 and recent Phase 07 completion.
</canonical_refs>

<specifics>
## Specific Evidence Already Confirmed

- `gsd-sdk query init.plan-phase "AAM-P1 ..."` returned `phase_found=false` and no `phase_dir`; AAM-P1 is not a normal MOCA roadmap phase.
- `docs/agent-architecture-phase-decomposition.md` says all phases in this workstream must be referenced as `AAM-P1` through `AAM-P11`, not bare phase numbers.
- `docs/agent-architecture-phase-decomposition.md` says AAM-P1 acceptance gate is contract inventory, current-vs-target checklist, initial coverage matrix, and review checklist.
- `src/agent/state.py` currently has persistent memory fields, ephemeral fields, approval/action fields, and dormant future investigation fields.
- `src/agent/graph.py` currently has 10 graph nodes and simple risk/approval conditional routing.
- `src/agent/tools/contracts.py` and `src/agent/tools/registry.py` currently implement a typed registry for four investigator-visible read/retrieval tools.
- `src/rag/schemas.py` currently has `EvidenceItem` and `RetrievalResult`, but not canonical `EvidenceRefV1` with tenant/policy/hash/retrieval config fields.
- `src/db/models.py` currently has AgentRun/AgentStep, ApprovalRequest/ApprovalStep, ActionDraft, business data, policy data, and AuditLog models; it does not show the full AAM target approval/action/replay/memory schema set.
</specifics>

<deferred>
## Deferred Ideas

These are not AAM-P1 implementation work. They must be assigned to owner phases in the baseline artifacts:

- Knowledge facade and canonical EvidenceRefV1 implementation: AAM-P2.
- BusinessToolService and ToolCallContext/ToolResultV2 implementation: AAM-P3.
- AgentState lifecycle, trusted context, router totality, slot resolution migration: AAM-P4.
- Intent/clarification contract implementation: AAM-P5.
- Session memory implementation: AAM-P6.
- Approval state machine, ActionSafetySnapshot, hash profile, needs_info, SLA/assignment semantics: AAM-P7.
- Demo action executor boundary: AAM-P8.
- ReplayEventV3/finalizer/redaction/retention: AAM-P9.
- Long-term/case memory: AAM-P10.
- External action/outbox/reconciliation/compensation: AAM-P11.
</deferred>

---

*Phase: AAM-P1-contract-baseline*
*Context gathered: 2026-06-06 via GSD plan-phase adaptation for AAM workstream*