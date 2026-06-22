---
phase: "26"
name: "Architecture Contract Baseline"
created: 2026-06-22
status: ready_for_planning
---

# Phase 26: Architecture Contract Baseline - Context

## Phase Boundary

Phase 26 is the baseline contract phase for v1.9 Agent Platform Foundation. It should make the planning/spec/eval architecture internally consistent and executable before implementation phases begin.

This phase should not implement runtime code. It may update architecture/spec/eval/planning documents and create verification artifacts that later phases must follow.

## Locked Decisions

### Architecture Direction

- MOCA should use a microservice-ready modular monolith: boundaries should be clear enough to split later, but physical microservice deployment is not part of v1.9.
- Full real external execution remains deferred. v1.9 hardens action draft, approval, evidence, claim verification, and safety snapshot boundaries only.
- `docs/contract-spec.md` remains the normative contract source. `docs/target-agent-platform-architecture-plan.md` records target architecture and rationale, but any executable contract must either already exist in `contract-spec.md` or be explicitly synchronized there.
- Phase 26 should not treat current implementation compromises as normative truth. If implementation and spec differ, the phase should record whether the spec is wrong or the implementation is intentionally partial/MVP.

### Phase 26 Deliverables

- Confirm `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and `docs/eval-test-plan.md` agree on target graph vocabulary, AgentState fields, RAG context build, claim verification, tool policy decisions, business fact result contracts, decision events, approval/action boundary, and eval gate levels.
- Make module ownership actionable: for each platform/domain service, define owned schemas/tables/events, public methods, allowed downstream dependencies, and forbidden imports or access patterns.
- Preserve legacy alias mappings where needed, especially graph node/router vocabulary migration from old names to target names.
- Make future implementation order executable without requiring physical microservices or full real execution.
- Record any remaining spec delta, MVP scope note, or deferred item with a named target phase. Do not use vague "later" wording.

### GSD Metadata Decision

- `gsd-sdk query init.new-milestone`, `state.load`, `roadmap.analyze`, and `init.plan-phase 26` now read v1.9 correctly after ROADMAP/MILESTONES format repair.
- `gsd-sdk query validate.health` still reports non-blocking warnings because old completed Phase 24/24.x/25 directories remain in `.planning/phases` and future Phase 26-35 directories are not all present.
- Do not use `phases.clear --confirm`; it deletes instead of archiving.
- Old phase directory archival is captured as a separate pending cleanup todo and should not block Phase 26 planning.

## Canonical References

Downstream agents must read these before planning or implementing Phase 26:

- `AGENTS.md` - MOCA project workflow rules, especially GSD and cross-review expectations.
- `.planning/PROJECT.md` - current milestone and shipped milestone context.
- `.planning/REQUIREMENTS.md` - APF-01 and APF-02 requirements.
- `.planning/ROADMAP.md` - Phase 26 goal, success criteria, and v1.9 phase order.
- `.planning/STATE.md` - current decisions, pending todos, and known GSD metadata caveats.
- `docs/contract-spec.md` - normative contract source.
- `docs/target-agent-platform-architecture-plan.md` - target platform architecture and rationale.
- `docs/eval-test-plan.md` - eval gate levels and test strategy.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - local GSD/state validation issues and known tooling pitfalls.

## Specific Planning Guidance

- Prefer focused documentation/contract verification tasks over broad implementation tasks.
- Include checks that prove all APF-01 and APF-02 requirements are covered.
- Include validation commands for GSD metadata queries and Markdown formatting.
- Include a final review task that confirms no code files were modified unless the plan explicitly justifies a code-level test or helper.
- Account for the future implementation sequence: Phase 27 TrustedContextFactory, Phase 28 DecisionEvent foundation, Phase 29 ToolPlatform, Phase 30 BusinessFactService, Phase 31 Memory platform, Phase 32 Intent graph, Phase 33 RAG/ClaimVerifier, Phase 34 Approval/ActionDraft, Phase 35 Replay/Eval hardening.

## Deferred Ideas

- Archive old completed Phase 24/24.x/25 directories into milestone-specific phase archives after Phase 26 planning is stable.
- Physical microservice extraction is a deployment decision after the modular monolith boundaries are proven.
- Full real external action execution remains deferred beyond v1.9.
