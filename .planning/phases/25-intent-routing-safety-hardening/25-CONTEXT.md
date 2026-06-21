# Phase 25: Intent Routing Safety Hardening - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning
**Source:** User-approved four-part hardening scope from intent design review

<domain>
## Phase Boundary

Phase 25 hardens the existing Phase 11 ordinary-chat intent and clarification contract. It does not replace deterministic routing with LLM-selected routing, does not introduce real external execution, and does not redesign the approval lifecycle. The phase focuses on auditable classification traces, risk tiers, active workflow state before classification, and safe slot provenance/invalidation.
</domain>

<decisions>
## Implementation Decisions

### Classification Trace

- Keep raw LLM classification advisory only.
- Business state and routing must use effective classification after deterministic pre-route and policy overrides.
- Trace must expose this chain:
  - `raw_llm_classification`
  - `pre_route_decision`
  - `policy_overrides`
  - `effective_classification`
  - `risk_tier`
  - `route_decision`
  - `reason_codes`
- The trace can live in `llm_outputs.intent_classification.classification_trace` and may also be projected into state if useful, but it must not let LLM output write forbidden state fields.

### Risk Tier

- Replace new call sites' reliance on intent-level high-risk booleans with a deterministic risk tier resolver.
- Required tiers:
  - `read_only`
  - `draft_only`
  - `suggest_action`
  - `approval_required`
  - `forbidden_in_chat`
- Inputs are primary intent, requested operation, role, channel, and routing hints.
- Keep `HIGH_RISK_INTENTS` available for backward compatibility during this phase.
- Ordinary chat cannot accept approval decisions or direct execution approvals from user text.

### Workflow-State-First

- Add a structured active-flow projection before ordinary classification, derived from checkpointed state before per-turn reset.
- Do not send full conversation history to the classifier.
- If previous state was waiting for required slots and the new query is a likely identifier answer, preserve last effective intent/operation/required slots and route to slot extraction rather than reclassifying from scratch.
- Short ambiguous replies like `继续吧`, `同意`, and `就按上面的处理` must fail closed to clarification when no trusted pending flow exists.

### Slot Provenance and Invalidation

- Current-turn explicit slots remain authoritative over inherited memory slots.
- Inherited slots must keep trusted provenance fields: source, confidence if known, observed_at/expires_at, tenant/user/thread scope, compatible intents, explicit_current_turn.
- Deterministic invalidation must handle negation/context switch phrases such as:
  - `不是这个订单`
  - `不是 ORD-...`
  - `换另一个`
  - `换成 ORD-...`
  - `我说的是另外一个工单`
- Invalidated slots must not satisfy required slot completeness.
</decisions>

<canonical_refs>
## Canonical References

### Intent and Routing

- `src/agent/intent_policy.py` — taxonomy, pre-route, precedence, high-risk compatibility.
- `src/agent/nodes/classify_intent.py` — raw LLM classification conversion into graph state.
- `src/agent/routing.py` — route decisions and trusted slot resolution.
- `src/agent/graph.py` — graph ordering from receive_request through classify/session/slots.
- `src/agent/schemas.py` — intent/operation/clarification schema literals.
- `src/agent/state.py` — graph state contract.

### Workflow and Memory

- `src/agent/nodes/receive_request.py` — per-turn reset point that can preserve structured active flow before clearing ephemeral fields.
- `src/agent/nodes/extract_slots.py` — slot extraction output and active slot projection.
- `src/agent/nodes/clarification_gate.py` — clarification reasons and blocked nodes.
- `src/agent/nodes/memory_write.py` — last intent and unresolved question write behavior.

### Tests

- `tests/agent/test_intent_routing.py` — deterministic intent/pre-route/route unit coverage.
- `tests/agent/test_graph.py` — graph-level ordinary chat and approval boundary coverage.
- `tests/agent/test_required_slots.py` — slot completeness and trusted memory behavior.
- `tests/agent/test_session_memory_integration.py` — session slot continuity integration coverage.
- `tests/agent/test_nodes/test_receive_request.py` — per-turn reset behavior.
- `tests/agent/test_nodes/test_classify_intent.py` — classify node behavior.
</canonical_refs>

<specifics>
## Specific Ideas

- Default channel is `ordinary_chat`.
- Default role comes from `state["role"]`; if missing, treat as ordinary support role, not supervisor authority.
- `approval_chat_not_trusted` maps to `forbidden_in_chat`.
- `execute_action` in ordinary chat maps to `approval_required` or `forbidden_in_chat`; direct approval decisions are forbidden in chat.
- `draft_reply` maps to `draft_only`.
- `draft_action` and compensation advice map to `suggest_action` unless pre-route or channel policy upgrades it.
</specifics>

<deferred>
## Deferred Ideas

- Intent-owned manifest blockers and pattern groups are deferred to `IRS-FUT-01`.
- Full `ResponseMode` taxonomy is deferred to `IRS-FUT-02`.
- New-intent PR admission checklist is deferred to `IRS-FUT-03`.
- Real external execution remains future Phase 17 scope.
</deferred>

---

*Phase: 25-intent-routing-safety-hardening*
*Context gathered: 2026-06-21*
