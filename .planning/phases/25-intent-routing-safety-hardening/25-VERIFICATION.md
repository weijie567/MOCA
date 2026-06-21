---
phase: "25-intent-routing-safety-hardening"
phase_number: 25
phase_name: "Intent routing safety hardening"
verified: "2026-06-21T04:22:41Z"
status: passed
requirements_verified:
  IRS-01: verified
  IRS-02: verified
  IRS-03: verified
  IRS-04: verified
  IRS-05: verified
  IRS-06: verified
  IRS-07: verified
  IRS-08: verified_with_warning
  IRS-09: verified
  IRS-10: verified
  IRS-11: verified
  IRS-12: verified
blockers: []
warnings:
  - id: W-01
    area: gsd_closeout
    issue: "Resolved after verifier run: 25-SUMMARY.md was added and ROADMAP.md now marks Phase 25 complete."
    evidence:
      - ".planning/phases/25-intent-routing-safety-hardening/25-SUMMARY.md exists"
      - ".planning/ROADMAP.md marks Status: Complete"
      - ".planning/ROADMAP.md checks 25-01-PLAN.md"
  - id: W-02
    area: slot_metadata_confidence
    issue: "IRS-08 is satisfied for trusted provenance, scope, freshness, compatibility, explicit/inherited status, and invalidation, but optional SessionSlotV1.confidence is not regression-tested through active_slot_metadata projection."
    evidence:
      - "src/memory/schemas.py:51 defines optional SessionSlotV1.confidence"
      - "src/memory/service.py:85 projects trusted slot metadata without a confidence key"
      - "No focused test asserts confidence preservation in active_slot_metadata"
tests_reviewed:
  - command: "uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q"
    result: "47 passed, 1 warning"
  - command: "uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q"
    result: "9 passed, 8 warnings"
  - command: "uv run ruff check src/agent/intent_policy.py src/agent/schemas.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/classify_intent.py src/agent/routing.py src/agent/nodes/extract_slots.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py"
    result: "passed"
  - command: "git diff --check -- src/agent tests/agent .planning"
    result: "passed"
score: "12/12 requirements verified; 7/7 plan must-haves verified"
overrides_applied: 0
human_verification: []
---

# Phase 25 Verification Report

**Phase Goal:** Harden the ordinary-chat intent/routing contract so raw LLM classification remains advisory, deterministic policy produces effective classification/risk/route decisions, active workflow state can answer pending clarification turns before reclassification, and inherited slots can be traced and invalidated safely.

**Status:** passed
**Verified:** 2026-06-21T04:22:41Z
**Mode:** initial verification

## Goal Achievement

Phase 25 achieved its stated implementation goal in the code path under verification. The classifier preserves raw LLM output as trace data, computes effective policy state before routing, resolves risk tiers deterministically, consumes trusted pending-slot flow before LLM classification, blocks ambiguous approval/action replies, and prevents invalidated inherited business identifiers from satisfying required slots.

The verifier initially found two non-blocking warnings. The GSD closeout metadata warning was resolved after the verifier run by adding `25-SUMMARY.md` and updating roadmap/state files. The optional slot-confidence metadata warning remains a future hardening note.

## Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Trace output distinguishes raw LLM classification, pre-route, policy overrides, effective classification, risk tier, route, and reason codes. | VERIFIED | `intent_result_to_state` builds `classification_trace` with all required keys and stores it top-level plus under `llm_outputs.intent_classification` in `src/agent/nodes/classify_intent.py:226` and `src/agent/nodes/classify_intent.py:239`. |
| 2 | Business state and routing consume effective classification rather than raw LLM classification. | VERIFIED | Effective `primary_intent`/`requested_operation` are written into `update` before `route_after_intent(update)` at `src/agent/nodes/classify_intent.py:213` and `src/agent/nodes/classify_intent.py:225`; raw output remains only under trace/LLM output. |
| 3 | Risk policy classifies read-only, draft, suggestion, approval-required, and forbidden-in-chat requests. | VERIFIED | `RiskTierLiteral` exists in `src/agent/schemas.py:30`; `resolve_risk_tier` maps all required tiers in `src/agent/intent_policy.py:258`; parametrized tests cover all five tiers in `tests/agent/test_intent_routing.py:131`. |
| 4 | Pending required-slot clarification can consume short identifier replies before LLM classification. | VERIFIED | `receive_request` projects `active_flow_state` before reset at `src/agent/nodes/receive_request.py:48`; `classify_intent` returns deterministic pending-slot updates before `_get_llm()` at `src/agent/nodes/classify_intent.py:487`; test proves LLM is not called in `tests/agent/test_nodes/test_classify_intent.py:91`. |
| 5 | Ambiguous approval/continue replies fail closed in ordinary chat unless a trusted pending flow explicitly allows them. | VERIFIED | Short-reply guard routes unsupported clarification with forbidden tier for approval-like text in `src/agent/nodes/classify_intent.py:442` and `src/agent/nodes/classify_intent.py:453`; graph regression confirms `approve APR-1` produces clarification without tools in `tests/agent/test_graph.py:652`. |
| 6 | Slot metadata carries trusted provenance and invalidation prevents stale inherited order/refund/ticket identifiers from satisfying required slots. | VERIFIED_WITH_WARNING | `resolve_slots_with_metadata` accepts only trusted scoped session metadata and skips invalidated inherited slots in `src/agent/routing.py:93`; trust checks enforce tenant/user/thread, freshness, and compatibility in `src/agent/routing.py:367`; invalidation tests cover stale inheritance and replacement in `tests/agent/test_required_slots.py:134` and `tests/agent/test_required_slots.py:146`. Optional confidence projection is not tested; see W-02. |
| 7 | Focused regressions cover effective classification, route, risk tier, clarification reason, and memory inheritance/invalidation without weakening authority boundaries. | VERIFIED | Focused tests passed: 47 focused routing/node/slot tests and 9 graph/session tests. Approval boundary tests assert no tool calls and no approval/action state writes. |

**Score:** 12/12 requirements verified; 7/7 plan must-haves verified.

## Plan Must-Haves

| Must-have | Status | Evidence |
|---|---|---|
| Raw LLM classification remains visible but advisory; effective classification drives business state. | VERIFIED | Trace/raw separation in `src/agent/nodes/classify_intent.py:226`; effective state drives route in `src/agent/nodes/classify_intent.py:225`; tests at `tests/agent/test_nodes/test_classify_intent.py:31` and `tests/agent/test_intent_routing.py:150`. |
| `RiskTier` is deterministic and derived from intent, requested operation, role, channel, and routing hints. | VERIFIED | `resolve_risk_tier` signature accepts all inputs and deterministically maps policy state in `src/agent/intent_policy.py:258`; role intentionally grants no ordinary-chat approval authority in this phase. |
| `HIGH_RISK_INTENTS` remains available for current callers while new risk-tier behavior is tested. | VERIFIED | `HIGH_RISK_INTENTS` remains derived from definitions in `src/agent/intent_policy.py:124`; test asserts derivation at `tests/agent/test_intent_routing.py:54`. |
| Pending required-slot clarification can consume short identifier replies without full conversation-history classification. | VERIFIED | Identifier-only pending-slot path returns before LLM call in `src/agent/nodes/classify_intent.py:388`; test uses a failing `_get_llm` sentinel at `tests/agent/test_nodes/test_classify_intent.py:91`. |
| Ambiguous approval/continue replies fail closed in ordinary chat unless a trusted pending flow explicitly allows them. | VERIFIED | Standalone `同意` uses short-reply guard and forbidden tier in `tests/agent/test_nodes/test_classify_intent.py:149`; pending `继续吧` re-asks for missing slot in `tests/agent/test_nodes/test_classify_intent.py:121`. |
| Inherited slots with invalidation markers cannot satisfy required slot completeness. | VERIFIED | Invalidation detection and metadata in `src/agent/routing.py:141`; invalidated inherited slot not resolved in `tests/agent/test_required_slots.py:134`. |
| Tests cover trace, risk tier, workflow-state-first, slot invalidation, and approval/action boundary regressions. | VERIFIED | Focused and graph/session pytest commands passed; see test commands in frontmatter. |

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| IRS-01 | VERIFIED | Trace keys are constructed in `src/agent/nodes/classify_intent.py:226`; tests assert raw/effective/route visibility in `tests/agent/test_nodes/test_classify_intent.py:41`. |
| IRS-02 | VERIFIED | Effective state is used for `route_after_intent(update)` in `src/agent/nodes/classify_intent.py:225`; policy override visibility asserted in `tests/agent/test_intent_routing.py:170`. |
| IRS-03 | VERIFIED | `resolve_risk_tier` exists and maps all required tiers in `src/agent/intent_policy.py:258`; tests cover all tier outputs in `tests/agent/test_intent_routing.py:131`. |
| IRS-04 | VERIFIED | Approval chat pre-route forces `unsupported`/`forbidden_in_chat` and filters forbidden state writes in `src/agent/nodes/classify_intent.py:186` and `src/agent/nodes/classify_intent.py:66`; tests assert no approval state in `tests/agent/test_nodes/test_classify_intent.py:73`. |
| IRS-05 | VERIFIED | `HIGH_RISK_INTENTS` remains exported in `src/agent/intent_policy.py:124`; test asserts compatibility view in `tests/agent/test_intent_routing.py:54`. |
| IRS-06 | VERIFIED | Active flow projection happens before per-turn reset in `src/agent/nodes/receive_request.py:48`; graph ordering keeps `receive_request` before `classify_intent` in `src/agent/graph.py:148`. |
| IRS-07 | VERIFIED | Short ambiguous approval/action replies bypass LLM and route to clarification in `src/agent/nodes/classify_intent.py:442`; standalone `同意` test in `tests/agent/test_nodes/test_classify_intent.py:149`. |
| IRS-08 | VERIFIED_WITH_WARNING | Trusted inherited metadata includes source/scope/freshness/expiry/compatibility in `src/memory/service.py:85`; current-turn metadata includes explicit provenance and observed time in `src/agent/routing.py:166`; optional confidence projection lacks focused regression coverage. |
| IRS-09 | VERIFIED | Negation/context-switch detection exists in `src/agent/routing.py:141`; tests cover `不是这个订单`, replacement, refund switch, and broad switch in `tests/agent/test_required_slots.py:134` and `tests/agent/test_required_slots.py:163`. |
| IRS-10 | VERIFIED | Current-turn slots are resolved before inherited slots in `src/agent/routing.py:109`; inherited invalidated slots are skipped in `src/agent/routing.py:129`; replacement test passes in `tests/agent/test_required_slots.py:146`. |
| IRS-11 | VERIFIED | Focused tests verify primary intent, requested operation, route, risk tier, clarification reason, memory inheritance, invalidation, and replacement across `tests/agent/test_intent_routing.py`, `tests/agent/test_nodes/test_classify_intent.py`, `tests/agent/test_nodes/test_receive_request.py`, and `tests/agent/test_required_slots.py`. |
| IRS-12 | VERIFIED | Approval/action boundary tests assert no tool call or approval/action state on unsafe ordinary-chat input in `tests/agent/test_graph.py:652`; classifier forbidden-write filter remains in `src/agent/nodes/classify_intent.py:66`. |

## Artifact And Wiring Verification

| Artifact | Status | Wiring/Data Flow |
|---|---|---|
| `src/agent/schemas.py` | VERIFIED | `RiskTierLiteral` and strict `IntentResultV3` schema exist; classifier imports and uses them. |
| `src/agent/intent_policy.py` | VERIFIED | `resolve_risk_tier`, `detect_pre_route`, precedence, required-slot, and high-risk policy are imported by classifier/routing and covered by focused tests. |
| `src/agent/state.py` | VERIFIED | Adds `risk_tier`, `classification_trace`, and `active_flow_state`; receive/classify/routing nodes write and consume these fields. |
| `src/agent/nodes/receive_request.py` | VERIFIED | Projects pending required-slot flow before clearing ephemeral state; graph starts with `receive_request`. |
| `src/agent/nodes/classify_intent.py` | VERIFIED | Builds effective state and trace, blocks forbidden state writes, handles deterministic active-flow/short-reply paths before LLM. |
| `src/agent/routing.py` | VERIFIED | Routes effective state, resolves slots with trusted metadata, rejects invalidated inherited slots, and fails closed on mismatched required slots. |
| `src/agent/nodes/extract_slots.py` | VERIFIED | Calls `resolve_slots_with_metadata` after extraction and writes `active_slots`/`active_slot_metadata`. |
| Focused tests | VERIFIED | Tests are not orphaned; all reviewed pytest commands passed under `uv run`. |

## Data-Flow Trace

| Flow | Source | Consumer | Status |
|---|---|---|---|
| Raw LLM -> effective classification -> route | `IntentResultV3` in classifier | `route_after_intent(update)` and graph conditional edge | VERIFIED |
| Previous clarification -> active flow -> deterministic classification | `receive_request._project_active_flow_state` | `classify_intent._deterministic_context_update` | VERIFIED |
| Session memory slot metadata -> trusted slot resolution -> required-slot completeness | `session_memory_load` / `MemoryService.load_session_memory` | `resolve_slots_with_metadata` and `route_after_slots` | VERIFIED_WITH_WARNING |
| Invalidated inherited slot -> metadata only, not resolved value | `detect_slot_invalidations` | `missing_required_slots` via `resolve_slots_for_completeness` | VERIFIED |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused routing/classifier/receive/slot suite | `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py -q` | 47 passed, 1 warning | PASS |
| Approval boundary and session-memory integration | `uv run pytest tests/agent/test_graph.py::test_approval_chat_routes_to_clarification_without_tools tests/agent/test_session_memory_integration.py -q` | 9 passed, 8 warnings | PASS |
| Lint reviewed files | `uv run ruff check ...` | All checks passed | PASS |
| Whitespace/diff hygiene | `git diff --check -- src/agent tests/agent .planning` | No output, exit 0 | PASS |

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|---|---|---|---|
| reviewed files | Empty dict/list initializers and test assertions found by broad grep | info | Benign initial state/default containers and tests; no placeholder, TODO, no-op handler, hardcoded user-visible stub, or orphaned implementation found. |

## Disconfirmation Pass

| Check | Result |
|---|---|
| Partial requirement | IRS-08 has a narrow coverage/projection caveat for optional slot confidence; current trusted scope/freshness/compatibility/invalidation behavior is verified. |
| Misleading test | No misleading focused test found; key tests assert behavioral outputs and several use failing LLM/tool sentinels to prove bypass/no-side-effect behavior. |
| Untested error path | Classifier and slot extraction broad exception fallback paths are not newly expanded in Phase 25 tests, but existing fallback behavior is outside the phase's primary success criteria. |

## Warnings

1. **W-01: GSD closeout metadata not updated.** Resolved after the verifier run: `25-SUMMARY.md` now exists and `.planning/ROADMAP.md` marks Phase 25 complete with the plan checked.
2. **W-02: Optional confidence projection is not pinned.** `SessionSlotV1` supports `confidence`, but trusted active slot metadata projection does not explicitly include or test that field. Since current writers do not populate confidence, this did not block the verified current path, but it should be pinned before confidence becomes meaningful slot provenance.

## Final Verdict

No blockers found. Phase 25 achieved the stated goal and all listed IRS requirements for the current implementation path. The phase is ready to proceed once the non-blocking GSD closeout metadata is updated.

---

_Verified: 2026-06-21T04:22:41Z_
_Verifier: Codex (gsd phase verifier)_
