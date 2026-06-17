---
created: 2026-06-17T10:38:23.355Z
title: Constrain AgentState memory expansion
area: general
files:
  - src/agent/state.py:48
  - src/agent/working_state.py:114
  - src/agent/nodes/receive_request.py:18
  - src/agent/context/assembler.py:25
---

## Problem

`AgentState` is still a wide LangGraph runtime/checkpoint bus. It mixes trusted identity, turn runtime fields, business context copies, policy evidence refs, session/long-term/case memory views, approval/action bindings, tool results, LLM outputs, node errors, and trace steps in one `TypedDict`.

The immediate risk is controlled by the current boundaries: `receive_request` resets per-turn fields, `WorkingStateV1` is the prompt-safe projection, and session memory/conversation/replay/approval/action facts have separate stores or services. However, Phase 16 long-term/case memory could make the mixed state worse if it stores full memory records or authority-bearing memory payloads directly in `AgentState.long_term_memory` or `AgentState.case_memory`.

## Solution

Do not start a standalone `AgentState` refactor before Phase 16 unless a concrete leak appears. Instead, make Phase 16 planning enforce that long-term/case memory writes and reads are owned by dedicated memory services/tables, while `AgentState` carries only bounded prompt-safe memory snippets or refs for the current turn.

Recommended constraints:

- Add a narrow memory context projection such as `MemoryContextV1` or `MemorySnippetV1`.
- Keep full long-term/case memory records out of `AgentState`.
- Keep memory separate from policy evidence, approval/action authority, current business facts, and replay/audit truth.
- Treat a deeper `AgentState` split as future architecture cleanup, likely before or during Phase 17 external execution if action authority state becomes harder to audit.
