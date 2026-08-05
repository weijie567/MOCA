# Phase 43: Intent Recognition Multi-Intent Tier A - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Source:** PRD Express Path (`.planning/intent-multi-a-codex-brief.md`)

<domain>
## Phase Boundary

This phase implements IDR-02 / ID-04 tier A only: intent recognition must preserve multi-intent utterances as a bounded ordered plan, execute only the safe read-only prefix in the current turn, and surface every later step as a deferred confirmation.

N=1 remains the dominant path and must be behavior-equivalent to the existing single-intent route surface. N>1 is a recognition and deferral feature, not an automatic execution-chain feature.

</domain>

<decisions>
## Implementation Decisions

### Locked Scope
- Add `TaskStep` and `TaskPlan` frozen dataclasses in `src/agent/intent_policy.py` beside the Phase 42 intent-layer contracts.
- Build a deterministic `TaskPlan` from the existing single LLM result (`primary_intent`, `secondary_intents`, `requested_operation`, `candidate_slots`) plus existing keyword signals. Do not add another LLM call.
- Preserve `IntentResultV3`, `docs/contract-spec.md`, and `src/agent/prompts.py` unchanged unless implementation discovers a direct conflict; if that happens, stop and report instead of editing them.
- Keep MOCA's existing five-tier `RiskTierLiteral`; do not introduce R0-R3 or any replacement risk taxonomy.
- Add `task_plan: dict | None` and `deferred_steps: list[dict]` to `AgentState` only. `AgentState` is `total=False`, so additive fields are safe.

### Task Plan Contract
- `TaskStep.step_id` uses stable readable IDs (`s1`, `s2`, `s3`).
- `TaskStep.intent` is an `IntentLiteral`; `operation` is a `RequestedOperationLiteral`; `entities` carries that step's slots/entities; `depends_on` records upstream step IDs; `relation` is one of `root`, `dependency`, `modifier`, or `parallel`.
- `TaskPlan.steps` contains normalized executable/deferred steps only. Modifier relations are folded/dropped before final `steps`, so `relation="modifier"` must not appear in final steps.
- `TaskPlan.terminal_step_id` points at the user's terminal delivery step and must refer to a real step.
- Plan size limit is 3 steps. Invalid plans fail closed to the existing single-intent path and trace `plan_invalid_fallback_single`.

### Normalization Rules
- The root step is the Phase 42 semantic effective intent/operation.
- Candidate secondary steps come from `IntentResultV3.secondary_intents`.
- `small_talk` as secondary is dropped and traced as `modifier_dropped:small_talk`.
- Secondary `complaint_escalation` is folded only when the root intent is one of `compensation_suggestion`, `refund_troubleshooting`, `ticket_reply_draft`, `order_status_inquiry`, or `policy_qa`; trace `modifier_folded:complaint_as_severity`.
- Folded complaint severity must leave a visible final-response safety note even when no deferred steps exist.
- `order_status_inquiry`, `refund_troubleshooting`, `policy_qa`, `ticket_reply_draft`, `compensation_suggestion`, `appeal_or_unban`, and `action_request` as secondary intents must remain independent steps unless another explicit locked rule says otherwise.
- Same-intent parallel mentions should merge into one step with combined entities where the existing entity shape allows this without losing data.

### Execution Semantics
- The executable prefix is the contiguous prefix from `s1` whose per-step `resolve_risk_decision(...).tier == "read_only"`.
- The current turn's effective single-intent fields remain the executable prefix's last step when the prefix is non-empty; if the prefix is empty, keep `s1` as the effective single-intent step and defer the rest.
- Every step after the executable prefix goes into `deferred_steps`.
- Draft, execute, escalation, approval, and other non-read-only work in `deferred_steps` must not run in this turn.
- Existing `route_after_intent`, `route_after_slots`, investigate, clarification, and risk surfaces should continue consuming the same single effective fields.

### Trace And Response
- `classification_trace` must include serialized `task_plan`, `executable_prefix`, `deferred_steps`, and `plan_normalization`.
- Final responses must visibly list deferred user requests and ask whether to continue.
- Deferred-step presentation is separate from `clarification_request` / missing-slot clarification and must not reuse the same reason channel.
- Folded complaint severity must be visible as a correction affordance, for example "已按'投诉情绪'处理本次诉求，如需正式升级请告知".

### Tests And Verification
- Add focused non-DB tests covering N=1 equivalence, dependency deferral, complaint folding plus safety note, independent-query non-folding, high-risk deferral, fail-closed fallback, deferred response visibility, and small-talk dropping.
- Required verification commands:
  - `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q`
  - `uv run ruff check src/agent tests/agent`
- MOCA forbids bare `pytest` and bare `python -m pytest`.

### the agent's Discretion
- Exact helper/function names are implementation discretion, except the dataclass field names are contractual.
- Exact Chinese final-response phrasing is implementation discretion as long as each deferred intent is visible and the response asks whether to continue.
- Plan split is planner discretion, but the first version must respect MOCA plan granularity rules: if implementation spans contracts, classification wiring, final-response presentation, and verification, split into dependency-ordered plans rather than one oversized plan.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Input
- `.planning/intent-multi-a-codex-brief.md` — normative execution brief for tier-A multi-intent recognition.
- `.planning/ARCHITECTURE-DEBT.md` — ID-04 / ID-DESIGN debt context and tier decision.
- `.planning/REQUIREMENTS.md` — IDR-02 requirement mapping.
- `.planning/ROADMAP.md` — Phase 43 goal, dependency, and success criteria.

### Phase 42 Foundation
- `.planning/intent-layering-codex-brief.md` — prior three-layer decoupling brief and non-goals.
- `.planning/phases/42-intent-recognition-three-layer-decoupling/42-CONTEXT.md` — retroactive Phase 42 context.
- `.planning/phases/42-intent-recognition-three-layer-decoupling/42-VERIFICATION.md` — Phase 42 verification evidence anchored at `a0a98e4`.

### Source Files
- `src/agent/intent_policy.py` — Phase 42 semantic/risk/clarification contracts and policy registry.
- `src/agent/nodes/classify_intent.py` — LLM classification-to-state orchestration and deterministic active-slot continuation path.
- `src/agent/state.py` — `AgentState` additive fields.
- `src/agent/routing.py` — existing route consumers of single effective intent/risk fields.
- `src/agent/nodes/clarification_gate.py` — existing missing-slot clarification surface; deferred steps must remain distinct.
- `src/agent/schemas.py` — `IntentResultV3` wire schema, explicitly out of scope for changes.
- `src/agent/prompts.py` — few-shot prompts, explicitly out of scope for changes.

### Regression Tests
- `tests/agent/test_intent_adapter.py`
- `tests/agent/test_intent_policy_registry.py`
- `tests/agent/test_intent_golden_contract.py`
- `tests/agent/test_intent_routing.py`
- `tests/agent/test_nodes/test_classify_intent.py`
- `tests/agent/test_graph.py`
- `tests/architecture/test_phase32_static_contract.py`

</canonical_refs>

<specifics>
## Specific Ideas

- Use Phase 42 `SemanticIntent` as the source of the effective root step.
- Use `resolve_risk_decision(...).tier == "read_only"` as the only allowed read-prefix gate; do not hard-code operation names as a substitute for risk-layer policy.
- Serialize dataclasses to plain dict/list values before writing into `AgentState` or `classification_trace`.
- Add tests at the policy/normalization layer and at the classify-node/final-response integration layer so failures identify whether the bug is plan construction, state wiring, or presentation.

</specifics>

<deferred>
## Deferred Ideas

- Tier B automatic dependency execution (`read -> read`, `read -> draft`) is deferred until tier A data/evals justify it.
- Tier C full DAG, resume, interruption, parallel execution, and per-step approval gates are deferred.
- ID-02 confidence calibration remains open; the existing `calibrated_confidence` placeholder is not a calibration implementation.
- Any contract-spec update, prompt few-shot change, or `IntentResultV3` schema change is out of scope for Phase 43.

</deferred>

---

*Phase: 43-intent-recognition-multi-intent-tier-a*
*Context gathered: 2026-07-02 via PRD Express Path*
