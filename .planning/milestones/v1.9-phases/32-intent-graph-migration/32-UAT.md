---
status: complete
phase: 32-intent-graph-migration
source:
  - 32-01-SUMMARY.md
  - 32-02-SUMMARY.md
  - 32-03-SUMMARY.md
  - 32-04-SUMMARY.md
  - 32-05-SUMMARY.md
started: 2026-06-28T15:10:52Z
updated: 2026-06-28T16:33:02Z
mode: self-check
---

## Current Test

[testing complete]

## Tests

### 1. Target Graph Vocabulary Projection
expected: |
  Trace/eval/API contract projection can map legacy implementation names to target canonical graph names while preserving legacy runtime/debug names. `rag_context_build` and `claim_verify` appear only as deferred, non-runnable Phase 33 target entries.
result: pass
evidence:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_graph.py -q --tb=short` - 45 passed in `32-01-SUMMARY.md`.
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_trace.py tests/architecture/test_phase32_static_contract.py tests/replay/test_replay_api.py tests/test_agent_runs_api.py tests/test_trace_api.py -q --tb=short` - 225 passed, 28 dependency/config warnings on 2026-06-28T16:33Z.
  - Clean deep code review `c1915ca` confirmed runtime legacy names remain preserved while contract surfaces expose target vocabulary fields.

### 2. Intent Registry Owns Effective Routing Decisions
expected: |
  `IntentPolicyRegistry` and `SlotPolicyRegistry` are consumed by `classify_intent` and `route_after_intent`; LLM output remains candidate-only, and invalid/raising registry paths fail closed.
result: pass
evidence:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` - 48 passed in `32-02-SUMMARY.md`.
  - Code review fix `e5f9e7d` moved `receive_request` active-flow recovery to `INTENT_POLICY_REGISTRY` / `SLOT_POLICY_REGISTRY`; clean review `c1915ca` confirmed no direct policy-constant regression.

### 3. Slot Resolution Gate Semantics
expected: |
  Required-slot and inherited-slot acceptance are owned by `SlotPolicyRegistry`; unsafe stale, wrong-thread, invalidated, or incompatible inherited slots clarify instead of satisfying required business identifiers. Target `slot_resolution_gate` / `route_after_slot_resolution` projection is testable while legacy route keys remain intact.
result: pass
evidence:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py -q --tb=short` - 48 passed in `32-03-SUMMARY.md`.
  - Latest self-check suite includes `tests/agent/test_required_slots.py`, `tests/agent/test_session_memory_integration.py`, and graph projection tests: 225 passed, 28 dependency/config warnings.

### 4. Trace/API Projection And Merchant Context Safety
expected: |
  Trace summary, SSE events, trace API, and replay/timeline surfaces expose target graph projection fields without removing legacy fields. `target_merchant_context.v1` reports safe status evidence only, accepts service-approved business fact refs including approved demo adapters, rejects spoofed raw IDs, and never broadens AgentRun/trace/replay authorization.
result: pass
evidence:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_nodes/test_receive_request.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` - 91 passed in `32-04-SUMMARY.md`.
  - Code review fixes `3a4994f` and `08fa32f` closed trace timeline router projection and explicit `target_merchant_context` metadata sanitization gaps.
  - Latest self-check suite includes `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/replay/test_replay_api.py`, and `tests/test_agent_runs_api.py`: 225 passed, 28 dependency/config warnings.
  - Clean deep code review `c1915ca` confirmed no `target_merchant_context` authorization broadening and no trace/replay/API contract regression.

### 5. Final Phase 32 Static Contract Gate
expected: |
  Final static contract tests prove no runnable Phase 33 `rag_context_build` / `claim_verify` behavior, no direct policy-constant consumption in migrated consumers, no invalid bare pytest validation commands, mapping doc/source consistency, and no target merchant-context authorization usage.
result: pass
evidence:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py -q --tb=short` - 6 passed in `32-05-SUMMARY.md`.
  - Final focused suite in `32-05-SUMMARY.md` - 267 passed.
  - Code review fix `e79f4dc` made the static command scanner catch bullet inline-code commands such as ``- `pytest tests/foo.py` - passed``.
  - Latest self-check ran `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` on the Phase 32 review scope: All checks passed.
  - `git diff --check` passed.
  - Security report `.planning/phases/32-intent-graph-migration/32-SECURITY.md` is `status: verified` with `threats_open: 0`.
  - Clean deep code review `c1915ca` reported `status: clean`, 0 critical, 0 warning, 0 info.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[]
