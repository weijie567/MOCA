---
phase: 37
slug: tool-declaration-runtime-policy-internal-consolidation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-01
---

# Phase 37 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` |
| **Full suite command** | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q` |
| **Estimated runtime** | ~60 seconds for focused suite; environment-dependent for DB-backed tests |

---

## Sampling Rate

- **After every task commit:** Run the narrow pytest command for the touched area.
- **After every plan wave:** Run the full relevant suite command above.
- **Before `$gsd-verify-work`:** Full relevant suite and ruff must be green.
- **Max feedback latency:** 90 seconds for focused validation, excluding local DB startup or migration waits.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | TPH-03 | T-37-01 | Tool declarations derive from one registry row/table; no second hand-maintained schema/name list is required. | unit / structural | `uv run pytest tests/tools/test_catalog.py -q` | yes | pending |
| 37-01-02 | 01 | 1 | TPH-03 | T-37-01 | `UnifiedToolManager.descriptors("investigate")` matches catalog-derived planner-visible read/retrieval descriptors and excludes write tools. | unit / compatibility | `uv run pytest tests/agent/test_tools/test_unified_tool_manager.py -q` | yes | pending |
| 37-02-01 | 02 | 2 | TPH-04 | T-37-02 | Every `ToolRuntime.invoke` failure exit uses the shared `_fail` path while preserving safe result/projection/event tuple behavior. | unit / structural / behavior | `uv run pytest tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py -q` | yes | pending |
| 37-02-02 | 02 | 2 | TPH-04 | T-37-03 | Runtime auth events remain low-payload and omit raw args, raw tool output, input schema, required permission, and caller allowlist. | integration | `uv run pytest tests/replay/test_tool_policy_events.py -q` | yes | pending |
| 37-03-01 | 03 | 3 | TPH-04 | T-37-04 | `ToolPolicyEngine.runtime_auth` uses an ordered declarative gate sequence preserving caller, permission, side-effect, scope, approval, safety snapshot, idempotency, and availability decisions. | unit / structural / behavior | `uv run pytest tests/tools/test_tool_platform.py -q` | yes | pending |
| 37-03-02 | 03 | 3 | TPH-03, TPH-04 | T-37-01 / T-37-04 | External contract models keep the same field names and forbid unexpected fields. | regression | `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/tools/test_catalog.py` - registry/schema/name drift coverage for TPH-03.
- [ ] `tests/tools/test_tool_platform.py` - structural coverage for `_fail(...)` and declarative runtime-auth gates for TPH-04.
- [ ] `tests/agent/test_tools/test_unified_tool_manager.py` - compatibility assertions compare against catalog-derived expectations, not a second hand-maintained list.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | TPH-03, TPH-04 | All required behavior has source-level or pytest coverage. | N/A |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags.
- [ ] Feedback latency target documented.
- [ ] `nyquist_compliant: true` set in frontmatter after executor fills final task IDs and all validation commands pass.

**Approval:** pending
