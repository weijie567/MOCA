---
phase: 07
slug: tool-registry-contracts
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-04
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py -q` |
| **Full suite command** | `uv run pytest tests/agent/test_tools tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q` |
| **Estimated runtime** | ~30-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py -q`
- **After every plan wave:** Run `uv run pytest tests/agent/test_tools tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q`
- **Before `/gsd-verify-work`:** Full suite plus lint must be green: `uv run ruff check src/ tests/`
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | REG-01, REG-09, STATE-02, STATE-03 | T-07-01 | Prompt-facing contracts reject unknown fields and invalid literals | unit | `uv run pytest tests/agent/test_tools/test_tool_contracts.py -q` | ✅ | ⬜ pending |
| 07-02-01 | 02 | 1 | REG-02, REG-03, REG-04, REG-05, REG-07 | T-07-02 | Unsafe or disallowed tools cannot be investigator-allowed or executed | unit | `uv run pytest tests/agent/test_tools/test_registry.py -q` | ✅ | ⬜ pending |
| 07-03-01 | 03 | 1 | REG-06, REG-08, TEST-01 | T-07-03 | Allowed adapters call existing tools and sanitize raw payloads | unit | `uv run pytest tests/agent/test_tools/test_tool_adapters.py -q` | ✅ | ⬜ pending |
| 07-04-01 | 04 | 2 | STATE-01, STATE-04 | T-07-04 | Dormant state fields do not change current graph/API behavior | regression | `uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/test_agent_runs_api.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- `pyproject.toml` already configures pytest async mode.
- `tests/agent/test_tools/` already exists for tool-focused tests.
- `tests/agent/test_graph.py`, `tests/agent/test_nodes/test_retrieve_policy_evidence.py`, and `tests/test_agent_runs_api.py` already provide targeted v1.0 regression coverage.
- No database schema push or migration is required for this phase.

---

## Manual-Only Verifications

All Phase 7 behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-04
