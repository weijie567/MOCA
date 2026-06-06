# Phase 7: Contract Baseline - Research

**Date:** 2026-06-06
**Phase:** Phase 7 Contract baseline
**Mode:** Planning research only; no source implementation

## Research Question

What does Phase 7 need to produce so later Agent Architecture Migration phases can implement contracts safely without confusing target architecture with current MOCA implementation?

## Findings

### 1. Phase 7 is an Agent Architecture Migration milestone phase, not a MOCA roadmap phase

Evidence:

- `docs/agent-architecture-phase-decomposition.md` states that phases must be referenced as `Phase 7` through `Phase 17` and must not be referred to as bare `Phase 1`, `Phase 2`, etc.
- The current `.planning/ROADMAP.md` historical phases are v1.0 phases 1-6 and v1.1 phases 7-11.
- Phase 7 was originally produced before the Agent Architecture Migration sequence was registered. It is now migrated into the standard `.planning/phases/07-contract-baseline/` identity and recognized by the roadmap.

Planning implication:

- Phase 7 artifacts should live in a dedicated standard phase directory such as `.planning/phases/07-contract-baseline/`.
- Final status and next-step commands must use `Phase 7`, not `1`.

### 2. Phase 7 acceptance gate is artifact completeness, not runtime behavior

Evidence:

- `docs/agent-architecture-phase-decomposition.md` lists Phase 7 primary acceptance gate as: `Contract inventory, current-vs-target checklist, initial coverage matrix, review checklist`.
- The user request adds a required readiness verdict.
- `docs/agent-architecture-phase-decomposition.md` says Phase 7 is `Spec-to-plan inventory and evidence baseline`.

Planning implication:

- Phase 7 should produce one baseline document containing all required sections, or clearly named companion docs.
- It should not implement KnowledgeService, BusinessToolService, new schemas, migrations, or tests.

### 3. Status discipline is a blocking readiness rule

Evidence:

- `docs/agent-architecture-phase-decomposition.md` Section 1 says a phase plan is not executable if any relevant spec area is `MISSING`.
- `PARTIAL` and `DEFERRED_WITH_OWNER` require owner phase, non-blocking rationale, and acceptance gate.
- `Status` must use only `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, or `MISSING`.
- `N/A` is allowed only in owner/impact/eval/read-switch fields with a reason, not as a status.

Planning implication:

- Phase 7 plan must include grep-verifiable checks for forbidden `N/A` in `Status` cells and allowed vocabulary.
- The output must include a readiness verdict that blocks later phases if any relevant item remains `MISSING`.

### 4. Current source already implements some v1.1 contract pieces, but not the full Phase 7-17 target contracts

Confirmed current evidence:

- `src/agent/state.py` defines current `AgentState` with persistent memory, ephemeral context, approval/action fields, dormant investigation fields, `current_run_id`, and `trace_steps`.
- `src/agent/graph.py` defines current graph nodes: `receive_request`, `classify_intent`, `extract_slots`, `load_business_context`, `retrieve_policy_evidence`, `generate_recommendation`, `assess_risk_and_approval`, `approval_gate`, `execute_action`, `final_response`, plus `route_after_risk` and `route_after_approval`.
- `src/agent/tools/contracts.py` defines `ToolInvocationContext`, `ToolRegistryEntry`, `ToolExecutionResult`, `ToolExecutionError`, and current narrow tool status/error enums.
- `src/agent/tools/registry.py` registers `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`, validates investigator allowlist/safety metadata, and returns structured rejections.
- `src/rag/schemas.py` defines `EvidenceItem`, `RetrievalResult`, `CitationValidation`, and `SearchRequest`.
- `src/db/models.py` includes `AgentRun`, `AgentStep`, `ApprovalRequest`, `ApprovalStep`, `ActionDraft`, policy/business tables, and `AuditLog`.

Target contracts not proven implemented by current source evidence:

- Independent `KnowledgeService` facade and canonical `EvidenceRefV1` with tenant/policy/hash/retrieval config identity.
- Independent `BusinessToolService` facade with target `ToolCallContext` / `ToolResultV2` statuses.
- Full target AgentState lifecycle registry, trusted field enforcement, router totality, and reset/merge property tests.
- IntentResultV3 precedence, confidence/calibration gates, required-slot expression completeness, and approval command separation.
- Session memory service, long-term memory, case memory, tombstone identity, memory write policy.
- Versioned multi-level approval request/level/assignment/decision/event model, CAS semantics, accept/edit/respond/ignore, needs_info revision protocol, SLA scanner.
- ActionSafetySnapshot, canonical hash profile, action payload hash, demo/external action mode separation, external outbox/reconciliation/compensation.
- ReplayEventV3 event store, finalizer, complete lifecycle statuses, redaction/retention contract.
- Per-phase eval gates with dataset owner/version/hash and blocking status.

Planning implication:

- Phase 7 must create a current-vs-target evidence checklist that prevents downstream agents from treating target spec text as implemented fact.

### 5. Baseline document should become the shared source for Phase 8/Phase 9 planning

Evidence:

- `docs/agent-architecture-phase-decomposition.md` next order says write Phase 7 plan, use Phase 7 outputs to produce contract inventory and initial coverage verification, then plan Phase 8 and Phase 9.
- Phase 8 and Phase 9 can run in parallel only after Phase 7.

Planning implication:

- The Phase 7 execution artifact should include phase-owner mappings clear enough for Phase 8/Phase 9 to consume independently.
- It should include follow-up register dispositions and baseline status rows for all major spec areas.

### 6. Section 19 must be audited, not blindly proven

Evidence:

- `docs/agent-architecture-spec.md` Section 19 is a migration-route design section, not runtime evidence.
- Phase 7 exists before Phase 8/Phase 9 so downstream phases do not plan on an incorrect or self-inconsistent route.
- The user explicitly requires that unreasonable Section 19 items can be marked `PARTIAL` or `MISSING`, and that inconsistencies must be raised rather than silently normalized.

Planning implication:

- Phase 7 should include `## Spec Consistency Findings` / `## Planning Deviations` as a first-class output.
- For each inconsistency, record original Section 19 requirement, conflicting evidence, recommended handling, readiness impact, owner, and status.
- If no inconsistency is found, write `None found after checking docs/agent-architecture-spec.md, docs/agent-architecture-phase-decomposition.md, current source evidence, and Phase 7 artifacts`.
- Do not force `COVERED` for target contracts that are unsupported, unreasonable, or inconsistent.

## Recommended Artifact Shape

A single execution artifact is sufficient and reduces drift:

- `.planning/phases/07-contract-baseline/07-CONTRACT-BASELINE.md`

Required sections:

1. `## Contract Inventory`
   - Contract/component name.
   - Spec source section.
   - Current evidence path(s).
   - Target owner phase.
   - Required tests/eval gate.
   - Migration/read-switch owner.
   - Status.

2. `## Current-vs-Target Evidence Checklist`
   - Current implementation evidence.
   - Current limitation.
   - Target contract.
   - Owner phase.
   - Proof required before marking covered.
   - Status.

3. `## Initial Coverage Matrix`
   - Spec area.
   - Covered by phase.
   - Required tests.
   - Migration owner.
   - Gap/owner gate.
   - Read-switch/rollback owner.
   - Eval gate.
   - Status.

4. `## Spec Consistency Findings`
   - Section 19 requirement.
   - Compared file/source evidence.
   - Consistency result.
   - Recommended handling.
   - Readiness impact.
   - Owner.
   - Status.

5. `## Identifier Semantics`
   - phase and milestone identifiers and runtime identifiers.
   - Current evidence.
   - Target meaning.
   - Owner phase.
   - Status.

6. `## Boris/GSD Phase Notes`
   - GSD controls phase workflow.
   - Boris-style review is used only for quality/scope checks.

7. `## Phase Planning Follow-up Register Disposition`
   - Follow-up item.
   - Disposition.
   - Owner/gate.
   - Rationale.
   - Status.

8. `## Review Checklist`
   - Checklist items for contract/source evidence separation, status vocabulary, owner phase, eval gate, schema migration ownership, consistency findings, and docs-only scope.

9. `## Readiness Verdict`
   - Spec verdict: `PASS`, `PARTIAL`, or `BLOCKED`.
   - Downstream planning status: `READY_FOR_Phase 8_P3_PLANNING`, `PARTIAL_WITH_DEFERRED_OWNER_GATES`, or `BLOCKED_MISSING_BASELINE`.
   - Count of `COVERED`, `PARTIAL`, `DEFERRED_WITH_OWNER`, `MISSING` rows.
   - Explicit rule: any `MISSING` in relevant Phase 7 outputs blocks downstream planning.

## Validation Strategy

Phase 7 validation can be deterministic and docs-focused:

- Check required section headings exist in `07-CONTRACT-BASELINE.md`.
- Check no `src/` files are modified.
- Check status vocabulary uses only allowed terms in baseline status fields.
- Check no `N/A` appears in `Status` table cells.
- Check every follow-up register item from `docs/agent-architecture-phase-decomposition.md` Section 6 appears in the baseline artifact.
- Check `## Spec Consistency Findings` exists and either lists findings or states no findings after checking the named files.
- Check readiness verdict exists and names spec verdict plus downstream gate effect.

## Security / Safety Notes

Phase 7 has no runtime security effect because it is docs-only. Its safety value is preventing unsafe downstream migration by requiring:

- Trusted context boundaries to be inventoried before implementation.
- Tool/action separation to be documented before write/external actions are introduced.
- Approval and action hash/snapshot contracts to be assigned to owner phases.
- Replay/audit/redaction requirements to be present before trace implementation changes.

## Open Questions / Risks

- The standard GSD roadmap tooling does not understand `Phase 7`; this plan handles it via a dedicated directory. Future phases may need the same convention unless roadmap tooling is extended.
- `docs/agent-architecture-spec.md` is large; Phase 7 execution must be careful to extract contract rows, not copy the whole spec blindly.
- If the baseline artifact marks too many target rows as `COVERED` without current evidence, later execution may assume contracts already exist. The plan should bias unknown implementation state toward `PARTIAL` or `DEFERRED_WITH_OWNER`, not `COVERED`.

## RESEARCH COMPLETE
