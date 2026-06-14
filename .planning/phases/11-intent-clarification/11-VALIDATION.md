---
phase: 11
slug: intent-clarification
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-14
---

# Phase 11 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_clarification_gate.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~60-120 seconds for focused Phase 11 tests; full suite depends on integration services |

---

## Sampling Rate

- **After every task commit:** Run the focused test file for the changed seam plus `uv run ruff check <changed files>`.
- **After every plan wave:** Run `uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_clarification_gate.py -q`.
- **Before `$gsd-verify-work`:** Run `uv run pytest -q` and `uv run ruff check src/agent tests/agent`.
- **Max feedback latency:** 120 seconds for focused checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | INTENT-01 | T-11-01 | Classifier output maps through an explicit adapter and cannot whole-object merge trusted fields. | unit | `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_nodes/test_classify_intent.py -q` | no W0 | pending |
| 11-02-01 | 02 | 2 | INTENT-01, CLARIFY-01 | T-11-01 | Approval-looking ordinary chat routes to a safe clarification/unsupported path and never creates `approval_result` or resume commands. | unit/golden | `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q` | no W0 | pending |
| 11-03-01 | 03 | 3 | INTENT-02 | T-11-02 | Required-slot completeness uses explicit/extracted slots only; `candidate_slots` cannot satisfy required slots. | unit | `uv run pytest tests/agent/test_required_slots.py -q` | no W0 | pending |
| 11-03-02 | 03 | 3 | INTENT-01, INTENT-02 | T-11-02 | Graph uses deterministic `route_after_intent` and `route_after_slots` conditional edges. | integration | `uv run pytest tests/agent/test_graph.py tests/agent/test_intent_routing.py -q` | partial | pending |
| 11-04-01 | 04 | 4 | CLARIFY-01 | T-11-03 | Ordinary clarification writes `clarification_request` and safe response fields only. | unit | `uv run pytest tests/agent/test_clarification_gate.py -q` | no W0 | pending |
| 11-05-01 | 05 | 5 | INTENT-01, INTENT-02, CLARIFY-01 | T-11-04 | Intent manifest and golden dataset metadata are machine-checkable, hash-owned, and fail stale or incomplete coverage. | contract/eval | `uv run pytest tests/agent/test_intent_manifest.py -q` | no W0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/agent/test_intent_adapter.py` - covers `IntentResultV3 -> AgentState`, confidence/calibrated-confidence separation, no whole-object merge, and forbidden writes.
- [ ] `tests/agent/test_intent_routing.py` - covers deterministic pre-router, precedence conflicts, low-confidence gates, approval-looking chat, and valid router keys.
- [ ] `tests/agent/test_required_slots.py` - covers `all_of`, `any_of`, `optional`, empty Phase 10 session adapter behavior, and candidate-slot non-completeness.
- [ ] `tests/agent/test_clarification_gate.py` - covers minimal ordinary questions, `clarification_request_id`, no tool/permission error leakage, and no approval lifecycle writes.
- [ ] `tests/agent/test_intent_manifest.py` - covers manifest source-of-truth coverage, stale dataset/hash metadata, `small_talk`/`unsupported` exemptions, per-class gates, and Wilson status precedence.
- [ ] `eval/intent/intent-golden.v1.json`, `eval/intent/coverage-manifest.v1.json`, and `eval/intent/intent-consistency.v1.json` - include owner/version/hash fields.

---

## Manual-Only Verifications

All Phase 11 behaviors must have automated verification. Manual review is limited to confirming the plan and source-of-truth traceability before execution.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 120 seconds for focused checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
