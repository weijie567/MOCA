# Phase 52: Safety Pre-route Node - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-07-06
**Phase:** 52-safety-pre-route-node
**Mode:** Auto-selected recommended defaults from repository context; no interactive questions.
**Areas discussed:** Graph insertion boundary, Safety disposition policy, Trace and compatibility projection, Validation and plan granularity

---

## Graph Insertion Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal Phase 52 extraction | Register `safety_pre_route` after `receive_request`, route safe requests to legacy `classify_intent` until Phase 53. | yes |
| Full entry rewrite | Also move `session_context_load` before intent and replace `classify_intent` in the same phase. | no |
| Test-only alias | Add vocabulary/tests but no runtime graph node. | no |

**User's choice:** Auto-selected minimal Phase 52 extraction.
**Notes:** This matches the roadmap dependency order and avoids collapsing Phase 52 and Phase 53 into one broad migration.

---

## Safety Disposition Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic request-risk only | Extract `detect_pre_route(...)`, untrusted approval chat, approval-bypass, and approval-like short reply guards; no LLM, memory, tools, risk gate, or approval/action state. | yes |
| Broad semantic unsupported detection | Move general unsupported intent classification into safety pre-route. | no |
| Risk gate pre-evaluation | Let pre-route evaluate proposed-action risk and approval needs. | no |

**User's choice:** Auto-selected deterministic request-risk only.
**Notes:** Broad unsupported intent and contextual intent remain Phase 53+ intent work. Risk, approval, and action draft authority stay downstream deterministic gates.

---

## Trace and Compatibility Projection

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical trace with temporary legacy mirror | Emit/project `safety_pre_route` as its own trace-visible decision while allowing `classify_intent` to keep temporary `pre_route_decision` compatibility until Phase 53. | yes |
| Hide pre-route inside classification trace | Keep all evidence of pre-route under `intent_classification`. | no |
| Immediate no-compat cleanup | Remove all classify-intent pre-route compatibility in Phase 52. | no |

**User's choice:** Auto-selected canonical trace with temporary legacy mirror.
**Notes:** Phase 50 requires temporary compatibility metadata. Immediate removal risks crossing into Phase 53 ownership.

---

## Validation and Plan Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Split into focused plans | Separate node/router extraction, graph/architecture guardrail update, and closeout/docs validation. | yes |
| One broad runtime rewrite plan | Cover all source, tests, docs, compatibility, and validation in one plan. | no |
| Defer architecture tests | Rely on node unit tests only and leave baseline updates for later. | no |

**User's choice:** Auto-selected split into focused plans.
**Notes:** This follows the MOCA plan granularity rule and Phase 51's guardrail pattern.

---

## the agent's Discretion

- Exact internal module/file names for the new node.
- Exact state-field name for the safety decision, as long as it is deterministic and trace-visible.
- Whether each fail-closed disposition routes to `clarification_gate` or `final_response`, as long as route choice is deterministic and tested.

## Deferred Ideas

- Phase 53: session context before intent and `contextual_intent_resolve` cutover.
- Phase 54: `slot_resolution_gate` cutover.
- Phase 55: `memory_context_load` cutover.
- Phase 56: `recommendation_generation` canonicalization.
- Phase 57: `risk_gate` / `approval_gate` canonicalization.
- Phase 58: final no-debt cleanup.
