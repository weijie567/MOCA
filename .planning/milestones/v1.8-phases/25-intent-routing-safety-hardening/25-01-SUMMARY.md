# Phase 25 Summary: Intent Routing Safety Hardening

## Goal

Harden MOCA's ordinary-chat intent/routing layer so raw LLM classification is advisory, deterministic policy produces the effective classification/risk/route, pending clarification state is handled before reclassification, and inherited slots can be traced and invalidated safely.

## Delivered

- `src/agent/schemas.py`
  - Added `RiskTierLiteral`.
  - Removed unused legacy `IntentResult` with obsolete taxonomy values.
- `src/agent/intent_policy.py`
  - Added deterministic `resolve_risk_tier`.
  - Kept `HIGH_RISK_INTENTS` compatibility.
  - Fixed precedence to include `secondary_intents` and normalize requested operation from the selected effective intent.
- `src/agent/nodes/classify_intent.py`
  - Added raw-to-effective `classification_trace`.
  - Added `risk_tier` state output.
  - Added active-flow-first deterministic handling for pending required-slot answers.
  - Added short-reply guard for standalone approval/action confirmations.
  - Forced safety-sensitive execution/escalation pre-route decisions into safe effective intents.
- `src/agent/nodes/receive_request.py`
  - Projects a scoped `active_flow_state` before clearing per-turn state.
- `src/agent/routing.py`
  - Added slot invalidation detection for order/refund/ticket context switches.
  - Normalized current-turn slot provenance metadata.
  - Prevented invalidated inherited slots from satisfying required slots.
- Tests updated in:
  - `tests/agent/test_intent_routing.py`
  - `tests/agent/test_nodes/test_classify_intent.py`
  - `tests/agent/test_nodes/test_receive_request.py`
  - `tests/agent/test_required_slots.py`

## Verification

```bash
uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q
uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q
uv run ruff check src/agent/intent_policy.py src/agent/schemas.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/routing.py src/agent/nodes/extract_slots.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py
git diff --check -- src/agent tests/agent .planning
```

Results:

- Focused routing/classifier/receive/slot suite: 47 passed.
- Graph/session boundary suite: 9 passed.
- Ruff: passed.
- Diff hygiene: passed.

## Review

- Code review: `.planning/phases/25-intent-routing-safety-hardening/25-REVIEW.md`
  - Initial findings: 0 critical, 2 warning, 1 info.
  - All findings fixed in `aa10082`.
- Goal-backward verification: `.planning/phases/25-intent-routing-safety-hardening/25-VERIFICATION.md`
  - Status: passed.
  - Requirements verified: IRS-01 through IRS-12.
  - Must-haves verified: 7/7.

## Boundary Notes

- Ordinary chat still cannot approve, execute, or bypass approval state.
- Memory remains contextual only and cannot provide policy evidence, business-fact authority, approval/action authority, or replay truth.
- Optional slot confidence projection is not pinned because current session slot writers do not populate confidence; this is a future hardening candidate before confidence becomes a meaningful provenance field.
