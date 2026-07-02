---
phase: 43
slug: intent-recognition-multi-intent-tier-a
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-02
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q` |
| **Full suite command** | `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` |
| **Lint command** | `uv run ruff check src/agent tests/agent` |
| **Estimated runtime** | quick: under 30 seconds; full: under 2 minutes on the current local environment |

---

## Sampling Rate

- **After every task commit:** Run the smallest focused `uv run pytest ... -q` command covering touched tests, then `uv run ruff check` for touched `src/agent` / `tests/agent` paths when code changed.
- **After every plan wave:** Run the full suite command and lint command above.
- **Before `$gsd-verify-work`:** Full suite and lint must be green.
- **Max feedback latency:** 2 minutes for the required full local suite.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | IDR-02 | T-43-01 / T-43-02 | Plan contracts serialize to state-safe dict/list values; invalid plans fail closed | unit | `uv run pytest tests/agent/test_intent_task_plan.py -q` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 1 | IDR-02 | T-43-02 | Non-read-only secondary steps are deferred, not executed | unit | `uv run pytest tests/agent/test_intent_task_plan.py::test_high_risk_second_step_deferred -q` | ❌ W0 | ⬜ pending |
| 43-02-01 | 02 | 2 | IDR-02 | T-43-02 / T-43-03 | N=1 route fields remain equivalent; valid multi-target plans do not get blocked by legacy clarification | node | `uv run pytest tests/agent/test_nodes/test_classify_intent.py -q` | ✅ | ⬜ pending |
| 43-02-02 | 02 | 2 | IDR-02 | T-43-03 | `receive_request` resets `task_plan` and `deferred_steps` each turn | node | `uv run pytest tests/agent/test_nodes/test_receive_request.py -q` | ✅ | ⬜ pending |
| 43-03-01 | 03 | 3 | IDR-02 | T-43-02 / T-43-04 | Deferred confirmations and complaint-folding safety notes are visible in final response branches | node | `uv run pytest tests/agent/test_nodes/test_final_response.py -q` | ✅ | ⬜ pending |
| 43-03-02 | 03 | 3 | IDR-02 | T-43-02 | Existing graph routes and static architecture contracts do not regress | integration/static | `uv run pytest tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_intent_task_plan.py` — new policy/normalization/read-prefix/fail-closed tests for IDR-02.
- [ ] `tests/agent/test_nodes/test_classify_intent.py` — extend existing node tests for N=1 equivalence, task-plan trace/state serialization, multi-target guard handling, and high-risk deferral.
- [ ] `tests/agent/test_nodes/test_final_response.py` — extend deferred confirmation and complaint safety-note coverage across representative response branches.
- [ ] `tests/agent/test_nodes/test_receive_request.py` — extend per-turn reset coverage for `task_plan` and `deferred_steps`.

---

## Manual-Only Verifications

All Phase 43 behaviors have automated verification. Manual review is still required for the plan/code-review gates because this phase touches an authorization boundary.

---

## Threat References

| Ref | Threat | Mitigation To Verify |
|-----|--------|----------------------|
| T-43-01 | Dataclass objects or unsupported values leak into persisted graph state/trace | Serialize `TaskPlan`, `TaskStep`, executable prefix, deferred steps, and normalization records to plain dict/list values before state writes. |
| T-43-02 | High-risk secondary work is smuggled behind a read request and executes in the same turn | Use per-step `resolve_risk_decision(...).tier == "read_only"` for executable prefix; all later steps remain in `deferred_steps`. |
| T-43-03 | Legacy `multi_target_request` clarification blocks valid tier-A safe-prefix execution | Clear only the multi-target clarification path after a valid plan is built; never clear approval or safety-sensitive pre-route guards. |
| T-43-04 | Deferred-step or complaint-folding notes disappear on final-response early returns | Route all final-response text through one decoration helper and keep `llm_outputs["final_response"]["response_text"]` synchronized. |
| T-43-05 | Stale deferred plan state leaks across turns | Reset `task_plan` and `deferred_steps` in `receive_request`. |

---

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 2 minutes.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-07-02 for planning; execution must update task statuses as tests land.
