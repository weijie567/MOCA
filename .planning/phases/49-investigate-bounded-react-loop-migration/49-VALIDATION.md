---
phase: 49
slug: investigate-bounded-react-loop-migration
status: complete_with_accepted_limitation
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-08
updated: 2026-07-08
requirements:
  - GAD-01-IMPL
---

# Phase 49 - Nyquist Validation

This validation closes the Phase 49 archive-evidence gap for GAD-01-IMPL as `implemented_with_accepted_limitation`.

Phase 49 implemented the bounded read-only ReAct main path for `investigate`, preserved deterministic fallback and downstream authority boundaries, and intentionally keeps the replay parent-operation limitation visible. Phase 60 does not erase or fix that limitation; it records the validation state honestly for archive review.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Primary investigate command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py tests/tools/test_tool_platform.py tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q` |
| **No-regression command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q` |
| **Lint command used during Phase 49** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/investigate.py src/agent/nodes/investigate_planner.py src/tools/projection.py tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py` |

## Sampling Rate

- **After each implementation plan:** Phase 49 summaries record focused tests for planner schema, bounded loop behavior, ToolPlatform visibility, replay metadata, graph safety, intent, memory, and approval/action no-regression.
- **After the closeout plan:** Phase 49-04 reran graph, investigate, intent, memory, and approval/action slices with MOCA-approved `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` commands.
- **Archive validation:** Phase 60 validates that the formal Phase 49 verification exists, the limitation remains explicit, and recommended current-equivalent commands avoid deleted or historical files.

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 49-01-01 | 01 | 1 | GAD-01-IMPL | T-49-01 | Structured planner output is exactly one action shape or one stop shape, and invalid planner output fails closed before dispatch. | unit / schema | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` | yes | passed in `49-01-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-01-02 | 01 | 1 | GAD-01-IMPL | T-49-02 | Planner allowlist is limited to the eight read/retrieval tools; write/action tools are rejected. | unit / authorization | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` | yes | passed in `49-01-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-02-01 | 02 | 2 | GAD-01-IMPL | T-49-03 | The ReAct loop is bounded by max iterations, deadline, and attempt counts. | unit / behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` | yes | passed in `49-02-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-02-02 | 02 | 2 | GAD-01-IMPL | T-49-04 | Observation-to-slot feedback is loop-local only and does not mutate `active_slots`, `extracted_slots`, `candidate_slots`, memory, or slot registry state. | unit / boundary | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py -q` | yes | passed in `49-02-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-03-01 | 03 | 3 | GAD-01-IMPL | T-49-05 | Tool dispatch remains exclusively through `ToolPlatform`, including the exact eight-tool planner-visible read/retrieval surface. | integration / architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` | yes | passed in `49-03-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-03-02 | 03 | 3 | GAD-01-IMPL | T-49-06 | Planner-facing observations use projected summaries only; raw payload sentinel text does not enter planner context. | unit / information-boundary | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q` | yes | passed in `49-03-SUMMARY.md`; verified in `49-VERIFICATION.md` |
| 49-03-03 | 03 | 3 | GAD-01-IMPL | T-49-07 | Replay can distinguish loop operations by iteration, attempt, and tool_call_id; parent-operation identity remains accepted limitation. | replay regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q` | yes | passed in `49-03-SUMMARY.md`; limitation preserved below |
| 49-04-01 | 04 | 4 | GAD-01-IMPL | T-49-08 | Graph-level safety regressions prove planner output cannot authorize routing, approval, action, or memory behavior. | graph / no-regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py -q` | yes | `81 passed, 25 warnings` in `49-04-SUMMARY.md` |
| 49-04-02 | 04 | 4 | GAD-01-IMPL | T-49-09 | Intent, memory, approval/action, and evidence authority remain outside the ReAct loop. | no-regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q` | yes | individual slices passed in `49-04-SUMMARY.md` |

## Closeout Evidence

- `49-VERIFICATION.md` formally verifies 8/8 observable truths and records Phase 49 as `implemented_with_accepted_limitation`.
- `49-04-SUMMARY.md` records graph/investigate closeout: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py -q` -> `81 passed, 25 warnings`.
- `49-04-SUMMARY.md` records intent regression: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py -q` -> `47 passed, 1 warning`.
- `49-04-SUMMARY.md` records memory regression: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py -q` -> `41 passed, 4 warnings`.
- `49-04-SUMMARY.md` records approval/action regression: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q` -> `31 passed, 1 warning`.
- `49-03-SUMMARY.md` records replay proof: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q` -> `23 passed, 1 warning`.

## Accepted Limitation

Phase 49 remains implemented with an accepted parent-operation replay limitation. Replay parent-operation identity is populated when graph/configurable context supplies `node_operation_id` or `investigate_operation_id`; Phase 49 did not add graph-level node operation emission for every investigate call. This is recorded in `.planning/DEFERRED-DECISIONS.md` and in `49-VERIFICATION.md`.

This limitation does not block Nyquist validation because the requirement text closes GAD-01-IMPL as implemented with replay parent-operation limitation. A future post-v2.1 hardening phase may add graph-level node operation emission if stricter replay parent identity is needed.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None for archive validation | GAD-01-IMPL | Phase 49 behavior has automated unit, graph, replay, memory, intent, approval/action, and source-backed formal verification evidence. | N/A |

## Validation Sign-Off

- [x] All implementation tasks have automated verification evidence.
- [x] Wave 0 dependencies are satisfied by planner schema, ToolPlatform, replay, graph, memory, intent, and approval/action regression slices.
- [x] `nyquist_compliant: true` is set in frontmatter.
- [x] Accepted parent-operation limitation remains explicit and is not erased.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.

**Approval:** complete_with_accepted_limitation.
