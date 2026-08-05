---
phase: 39
slug: contract-spec-12-5-12-6-reconciliation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
---

# Phase 39 - Validation Strategy

Per-phase validation contract for `docs/contract-spec.md` section 12.5/12.6 reconciliation.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest via `uv run pytest` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order -q` |
| Full suite command | `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` |
| Estimated runtime | 15-30 seconds |

## Sampling Rate

- After every task commit: run the quick run command and the structural `rg` checks below.
- After every plan wave: run the full suite command and `git diff --check`.
- Before `$gsd-verify-work`: full suite and structural doc checks must be green.
- Max feedback latency: 30 seconds for quick checks.

## Structural Checks

Run these with project-approved entrypoints and standard shell tools:

```bash
rg -n "effective_at|approval_ref|safety_snapshot_ref" docs/contract-spec.md
rg -n "executor|exposure|requires_approval|requires_safety_snapshot|requires_idempotency_key" docs/contract-spec.md
rg -n "event_family: Literal\\[.*action|runtime_available|availability_summary" docs/contract-spec.md
git show --stat --oneline 4dcb673 -- docs/contract-spec.md
git show --unified=80 4dcb673 -- docs/contract-spec.md
git diff --name-only -- docs/contract-spec.md src/tools/contracts.py src/tools/catalog.py src/tools/policy.py src/tools/runtime.py tests
git diff --check
```

The final `git diff --name-only` check should show `docs/contract-spec.md` only unless the plan explicitly justifies a non-doc change.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | TPH-02 | T-39-01 | Commit `4dcb673` is checked and current §12.5/§12.6 edit starts from on-disk spec state. | git/doc evidence | `git show --stat --oneline 4dcb673 -- docs/contract-spec.md && git show --unified=80 4dcb673 -- docs/contract-spec.md` | yes | pending |
| 39-01-02 | 01 | 1 | TPH-02 | T-39-02 | §12.5 adds only tool-call-local fields `effective_at`, `approval_ref`, and `safety_snapshot_ref`; §8.0 identity fields are not redefined. | docs + architecture tests | `rg -n "effective_at|approval_ref|safety_snapshot_ref" docs/contract-spec.md && uv run pytest tests/architecture/test_trusted_context_boundaries.py -q` | yes | pending |
| 39-01-03 | 01 | 1 | TPH-02 | T-39-03 | §12.6 documents implemented descriptor metadata and action event family without changing production code. | docs + unit tests | `rg -n "executor|exposure|requires_approval|requires_safety_snapshot|requires_idempotency_key|event_family: Literal\\[.*action" docs/contract-spec.md && uv run pytest tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency -q` | yes | pending |
| 39-01-04 | 01 | 1 | TPH-02 | T-39-04 | §12.6 documents policy availability metadata while preserving decision/event envelope boundary. | docs + unit tests | `rg -n "runtime_available|availability_summary" docs/contract-spec.md && uv run pytest tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order -q` | yes | pending |
| 39-01-05 | 01 | 1 | TPH-02 | T-39-05 | Phase diff is doc-only and whitespace clean. | structural diff | `git diff --name-only -- docs/contract-spec.md src/tools/contracts.py src/tools/catalog.py src/tools/policy.py src/tools/runtime.py tests && git diff --check` | yes | pending |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All Phase 39 behavior has automated or structural verification. The required dual-AI plan/code review remains a process gate, not a manual product test.

## Validation Sign-Off

- [x] All tasks have automated verify or structural checks.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target < 30s for quick checks.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: pending
