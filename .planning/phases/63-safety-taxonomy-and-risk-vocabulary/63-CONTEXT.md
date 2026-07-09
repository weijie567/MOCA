# Phase 63: Safety Taxonomy And Risk Vocabulary - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 63 delivers a single safety/action taxonomy and risk vocabulary used by `risk_gate`, `action_draft`, `intent_policy`, approval schemas, and focused tests. It should remove duplicated action canonicalization and clarify the difference between:

- executable action types, such as `issue_coupon`, `approve_refund`, `partial_refund`, and future external actions;
- non-executable dispositions, such as `manual_review` and `blocked`;
- risk severity, such as low/medium/high;
- risk routing/disposition, such as allow, approval required, manual review, or blocked.

This phase must preserve the current safety posture. It is not an external execution phase, not a new approval workflow phase, not a broad state-machine registry phase, and not the RAG risk-label unification phase.

</domain>

<decisions>
## Implementation Decisions

### Taxonomy Ownership

- **D-63-01:** Create one canonical owner for action taxonomy and risk vocabulary. `risk_gate.py`, `action_draft.py`, and `intent_policy.py` should consume it rather than keeping duplicate local sets or `_canonical_action_type` functions.
- **D-63-02:** Split executable actions from dispositions. `manual_review` is a safety disposition/routing outcome, not an executable external action type.
- **D-63-03:** Keep current executable-action coverage conservative. Phase 63 should model the currently used action types and compatibility aliases, but should not introduce new write tools or real external execution.
- **D-63-04:** The taxonomy owner should expose stable helpers for canonicalization, alias matching, keyword classification, and allowed-action checks. Callers should not hand-roll keyword sets after the migration.

### Risk Severity And Disposition

- **D-63-05:** Risk severity and risk disposition must be modeled separately. The current `RiskAssessment.risk_level` schema allows `low|medium|high`, while runtime code also writes `manual_review` and `blocked`; Phase 63 should stop expanding severity strings to carry routing decisions.
- **D-63-06:** Preserve backward compatibility where existing persisted or API-facing payloads still contain `risk_level`, but introduce explicit fields or normalization helpers for disposition/routing semantics.
- **D-63-07:** Approval/action contracts should continue accepting existing `RiskDecisionV1.risk_level` strings during compatibility, but new code should not rely on `risk_level == "manual_review"` or `risk_level == "blocked"` as a severity check.

### Safety Routing And Intent Policy

- **D-63-08:** Evidence-required/action-bound intent routing should derive from `INTENT_DEFINITIONS` or a safety policy registry. Runtime routing must not maintain a separate hand-written fallback set that can drift from `intent_policy.py`.
- **D-63-09:** Deterministic pre-route action keyword detection should consume the shared taxonomy/alias data. The current English/Chinese action terms in `intent_policy.py` should not remain a separate source of truth.
- **D-63-10:** Existing critical safety behavior must stay fail-closed: ordinary chat approval decisions remain untrusted, action/execute/escalate requests continue routing through risk/approval gates, and non-allow verification continues blocking action drafts.

### Extraction Boundaries

- **D-63-11:** Money/risk extraction assumptions in `risk_gate.py` should be named and tested. Phase 63 may centralize extraction helpers if it reduces drift, but should not invent broad natural-language action execution.
- **D-63-12:** LLM risk assessment output remains advisory/structured input. Backend deterministic policy remains responsible for action canonicalization, rule matching, approval requirement, blocking, and proposal/draft safety binding.

### Tests And Migration

- **D-63-13:** Start with failing parity tests that prove the duplicated `risk_gate` and `action_draft` action canonicalization behavior is captured before migration.
- **D-63-14:** Add tests for severity/disposition separation, including manual-review and blocked verifier routes, so the system no longer depends on invalid `risk_level` values.
- **D-63-15:** Add drift tests for action aliases, executable action allowlists, non-executable dispositions, evidence-required intents, and pre-route action keyword classification.
- **D-63-16:** Keep migration scoped. If a DB CHECK/status-machine hardening issue appears, record it for the suggested Phase 67/state-machine phase unless it is directly required to make Phase 63 safe.

### the agent's Discretion

- Exact module name is implementation discretion, but the plan should name one owner, likely under `src/agent/safety/`, `src/agent/taxonomy/`, or another existing codebase-consistent package.
- Exact Pydantic model names are planner discretion. The important boundary is semantic separation, caller migration, and compatibility tests.
- The plan may split into multiple small plans if needed: taxonomy foundation, risk vocabulary migration, intent/routing migration, and final parity/eval/documentation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope And Prior Decisions

- `.planning/ROADMAP.md` — Phase 63 goal, dependency on Phase 62, and success criteria.
- `.planning/STATE.md` — Current chain status and Phase 62 completion context.
- `.planning/ARCHITECTURE-DEBT.md` — hardcoding/debt record that motivated Phase 63.
- `.planning/phases/62-business-query-and-drilldown-foundation/62-CONTEXT.md` — explicit deferral D-62-17: risk/action taxonomy unification belongs to Phase 63.
- `.planning/phases/62-business-query-and-drilldown-foundation/62-SECURITY.md` — Phase 62 safety boundary; Phase 63 must not weaken business-query safety.

### Accepted Architecture Contracts

- `docs/contract-spec.md` §11.1-11.2 — intent taxonomy, ordinary-chat approval trust boundary, requested-operation separation.
- `docs/contract-spec.md` §12.3 and §16.8 — write/action tool taxonomy and note that `manual_review` is better modeled as disposition/routing result.
- `docs/architecture-overview.md` — backend-owned safety boundaries.
- `docs/current-langgraph-architecture.md` — current graph routing and node responsibilities.

### Source Anchors For Planning

- `src/agent/nodes/risk_gate.py` — current duplicated action taxonomy, `_canonical_action_type`, risk-level/disposition mixing, rule matching, and proposal/snapshot binding.
- `src/agent/nodes/action_draft.py` — current duplicate `_canonical_action_type`, action allowlist, and draft ToolPlatform boundary.
- `src/agent/intent_policy.py` — current intent definitions, risk tiers, deterministic pre-route action keywords, and evidence-required derivation.
- `src/agent/routing.py` — route decisions that consume evidence-required/action-bound classifications.
- `src/agent/schemas.py` — `RiskAssessment` schema currently restricts `risk_level` to low/medium/high.
- `src/approvals/schemas.py` — `RiskDecisionV1` and approval create command compatibility surface.
- `src/actions/schemas.py` — action draft compatibility payloads and draft status fields.

### Test Anchors

- `tests/agent/test_intent_routing.py` — current intent/risk-tier/evidence-required behavior.
- `tests/agent/test_intent_policy_registry.py` — existing registry/parity tests for intent policy.
- `tests/agent/test_nodes/test_risk_gate.py` or the closest risk-gate test files — target for severity/disposition and canonical action behavior.
- `tests/actions/test_action_draft_v2.py` and `tests/actions/test_phase34_action_draft_bindings.py` — action draft binding and compatibility expectations.
- `tests/approvals/test_hash_binding.py` — approval/risk decision binding expectations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `IntentDefinition` already carries `evidence_required`, `high_risk`, and `critical_route_class`; Phase 63 should derive routing policy from it or a nearby registry instead of duplicating runtime sets.
- `RiskDecisionV1`, `AutoAllowedActionBindingV1`, and action draft schemas already provide durable safety binding surfaces. Phase 63 should keep those durable contracts compatible while improving vocabulary clarity.
- Existing intent-policy registry tests already prove a local pattern for parity tests and can be extended for safety taxonomy drift checks.

### Established Patterns

- Deterministic backend gates decide safety. LLM output can suggest or classify, but backend policy controls canonical action, approval requirement, blocking, and draft creation.
- `manual_review` appears in several contexts today; Phase 63 must normalize its meaning instead of making every occurrence an executable action.
- Compatibility fields may remain temporarily, but new code should consume explicit semantic helpers rather than parsing ad hoc strings.

### Integration Points

- `risk_gate` should call shared taxonomy helpers for `_is_actionable_recommendation`, `_canonical_action_type`, full/partial/refund/coupon classification, and disposition mapping.
- `action_draft` should call the same canonicalization helper as `risk_gate` and should reject non-executable dispositions before ToolPlatform write-tool invocation.
- `intent_policy` pre-route keyword detection should consume taxonomy aliases or a shared resolver.
- `routing` and recommendation-generation paths should derive evidence/action-bound intent decisions from policy definitions instead of maintaining separate hardcoded sets.

</code_context>

<specifics>
## Specific Ideas

- The first migration target should be duplicated `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, and `_canonical_action_type` in `risk_gate.py` and `action_draft.py`.
- The safest compatibility approach is additive: introduce explicit severity/disposition helpers and migrate call sites, while keeping old payload keys populated until tests prove downstream surfaces are ready.
- The plan should explicitly test that `manual_review` can be a disposition without becoming a callable/executable action.
- The phase should include static drift guards so future action aliases or risk dispositions cannot be added in only one of risk, draft, or intent layers.

</specifics>

<deferred>
## Deferred Ideas

- Phase 64 owns RAG risk label registry and labels such as `manual_review_sensitive`, `conflict`, and `stale_evidence`.
- Phase 65 owns trace event type, response-kind, node label, tool label, and console label registry work.
- Phase 66 owns dev/test/config/demo constants and settings hygiene.
- Suggested future Phase 67 owns broader run/action/approval/memory/replay state-machine registry and DB/API/frontend status constraints.

</deferred>

---

*Phase: 63-safety-taxonomy-and-risk-vocabulary*
*Context gathered: 2026-07-10*
