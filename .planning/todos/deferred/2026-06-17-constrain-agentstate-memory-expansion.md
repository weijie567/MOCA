---
created: 2026-06-17T10:38:23.355Z
title: "17-prep: AgentState Surface Contracts + Authority Isolation"
area: architecture
target_phase: 17-prep
timing: before Phase 17 External Action Execution
status: deferred
deferred_on: 2026-06-20
deferred_reason: "Phase 17 is not active. Preserve this as future planning context only."
files:
  - src/agent/state.py:48
  - src/agent/working_state.py:114
  - src/agent/nodes/receive_request.py:18
  - src/agent/context/assembler.py:25
---

## Problem

This is not current work after v1.6 closeout. Keep it as a future candidate only if Phase 17 or real external action execution is reintroduced.

`AgentState` is still a wide LangGraph runtime/checkpoint bus. It mixes trusted identity, turn runtime fields, business context copies, policy evidence refs, session/long-term/case memory views, approval/action bindings, tool results, LLM outputs, node errors, and trace steps in one `TypedDict`.

The immediate risk is controlled by the current boundaries: `receive_request` resets per-turn fields, `WorkingStateV1` is the prompt-safe projection, and session memory/conversation/replay/approval/action facts have separate stores or services. Phase 16 and Phase 22 also added service-owned reviewed memory, prompt-safe memory projection, and tests proving memory cannot become policy, business, approval, action, replay, or audit authority.

The remaining cleanup is architectural: before Phase 17 introduces real external action execution, the state surfaces that carry memory context, verifier route state, approval/action bindings, and debug traces should be made easier to audit.

## Solution

Do not start a broad standalone `AgentState` rewrite. Keep `AgentState` as the LangGraph transport, but add typed surface contracts around high-risk areas before Phase 17 external execution.

Recommended 17-prep scope:

- Add a narrow memory context projection such as `MemoryContextV1` or `MemorySnippetV1`.
- Add or formalize `VerifierRouteStateV1` for route/status/safe reasons/metrics only.
- Add or formalize `ActionBoundaryStateV1` for approval/action/safety snapshot refs only.
- Keep full long-term/case memory records out of `AgentState`; state may carry only bounded prompt-safe memory snippets or refs for the current turn.
- Keep memory separate from policy evidence, approval/action authority, current business facts, and replay/audit truth.
- Add boundary tests for checkpoint serialization, prompt projection, replay/audit projection, and approval/action snapshots.
- Keep this as pre-Phase 17 safety cleanup, not a v1.5 blocker.

Out of scope:

- No business behavior changes.
- No retrieval ranking changes.
- No rewrite of Phase 16 memory services or Phase 22 verifier routing.
- No external action execution implementation.
