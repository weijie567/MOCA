---
phase: 35-replay-and-eval-hardening
nyquist_compliant: true
apf_17_status: covered
apf_18_status: covered
---

# Phase 35 Validation

Final closure evidence for Phase 35 replay and eval hardening. This artifact records the exact focused/static/eval gates used to close APF-17 and APF-18 without adding runtime behavior, external execution, outbox, reconciliation, physical microservice deployment, or replay-by-rerun scope.

## Command Evidence

| Gate | Command | Exit | Observed result |
| --- | --- | --- | --- |
| Replay focused closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_coverage_matrix.py tests/replay/test_phase35_trace_replay_permissions.py tests/replay/test_phase35_terminal_timelines.py tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_redaction_negatives.py -q --tb=short` | 0 | `73 passed, 1 warning in 38.29s` |
| Eval and architecture closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short` | 0 | `16 passed, 1 warning in 0.41s` |
| Replay/API regression closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_trace_api.py tests/test_agent_runs_api.py tests/replay/test_replay_api.py tests/replay/test_replay_service.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_operation_pairing.py tests/replay/test_replay_redaction_retention.py tests/replay/test_tool_policy_events.py -q --tb=short` | 0 | `120 passed, 1 warning in 171.21s` |
| Agent/action regression closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_memory_write_node.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py -q --tb=short` | 0 | `86 passed, 1 warning in 23.94s` |
| Scoped replay/eval ruff gate | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay tests/replay tests/eval tests/architecture/test_phase35_replay_eval_boundaries.py` | 0 | `All checks passed!` |

No validation command failed during Task 1, so no new `.planning/LOCAL-VALIDATION-ISSUES.md` record was required for this task.
