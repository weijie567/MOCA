---
phase: 27
slug: trustedcontextfactory-and-projections
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/platform/test_trusted_context.py tests/agent/test_intent_policy_registry.py -q` |
| **Focused integration command** | `uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py tests/test_approval_api.py tests/replay/test_replay_service.py -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | Quick: ~10-30s after Wave 0 tests exist; focused integration depends on local PostgreSQL availability |

---

## Sampling Rate

- **After every task commit:** Run the narrow test for the touched module plus `uv run pytest tests/platform -q` once platform tests exist.
- **After every plan wave:** Run the focused integration command.
- **Before `$gsd-verify-work`:** Full suite must be green, or environment blockers must be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- **Max feedback latency:** 30 seconds for unit/platform contract checks when local dependencies are available.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-W0 | 01 | 0 | APF-03, APF-04 | TC-01 / TC-02 | Canonical `TrustedContext` rejects non-trusted and projection-local fields; projections keep metadata local | unit contract | `uv run pytest tests/platform -q` | No - Wave 0 | pending |
| 27-01-FACTORY | 01 | 1 | APF-03 | TC-01 | Factory derives identity/scope only from authenticated user, verified token scopes, server run/thread/trace/session ids, and server-derived merchant scope | unit + API integration | `uv run pytest tests/platform/test_trusted_context_factory.py tests/test_agent_runs_api.py -q` | No - Wave 0 for platform tests | pending |
| 27-01-PROJ | 01 | 1 | APF-04 | TC-02 / TC-03 | Tool, knowledge, memory, approval, replay, and intent projections do not widen canonical identity/scope | unit contract | `uv run pytest tests/platform/test_context_projections.py -q` | No - Wave 0 | pending |
| 27-01-SEAMS | 01 | 2 | APF-03, APF-04 | TC-01 / TC-04 | Search, agent run, investigate/action draft, and knowledge-tool seams consume factory projections rather than local trust roots | integration | `uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py -q` | Existing integration tests present; new assertions pending | pending |
| 27-01-REG | 01 | 2 | APF-04 | TC-05 | Intent/slot registry exposes read-only catalog APIs without changing runtime route semantics | unit contract | `uv run pytest tests/agent/test_intent_policy_registry.py -q` | No - Wave 0 | pending |
| 27-01-BOUNDARY | 01 | 2 | APF-03, APF-04 | TC-06 | Prompt projectors and downstream modules do not redefine canonical trusted identity/scope contracts | static boundary | `uv run pytest tests/architecture/test_trusted_context_boundaries.py -q` | No - Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Threat References

| Ref | Threat | Required Mitigation |
|-----|--------|---------------------|
| TC-01 | User-payload, LLM output, or checkpoint state spoofs tenant/user/role/permission/merchant scope | Factory input excludes request-body/model/checkpoint authority and uses authenticated server-side inputs only |
| TC-02 | Projection-local metadata leaks into canonical `TrustedContext` | Exact field-set tests and strict `extra="forbid"` models |
| TC-03 | `effective_at`, `channel`, policy/model/tool versions, or artifact refs widen identity/scope | Projection tests assert those fields appear only on consumer contexts or metadata |
| TC-04 | Knowledge/tool consumers keep local trust roots and bypass shared factory | Integration tests assert current construction seams use factory projections |
| TC-05 | Downstream phases invent temporary intent/slot policy shapes | Read-only registry tests cover existing definitions, slot policy, precedence, and route policy |
| TC-06 | Prompt projectors or service-local schemas redefine trusted identity | Static boundary tests / grep checks catch duplicate canonical models and projector authority |

---

## Wave 0 Requirements

- [ ] `tests/platform/test_trusted_context.py` — canonical schema, exact field set, extra-field rejection, trusted-source construction.
- [ ] `tests/platform/test_merchant_scope.py` — deny-all, explicit wildcard, all-provided-dimensions, no model/user widening.
- [ ] `tests/platform/test_context_projections.py` — tool, knowledge, memory, approval, replay, and intent projection-local metadata boundaries.
- [ ] `tests/agent/test_intent_policy_registry.py` — read-only registry wrappers over existing intent/slot policy constants.
- [ ] `tests/architecture/test_trusted_context_boundaries.py` — no prompt-projector authority and no duplicate trusted-context models.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL-backed API/integration command availability | APF-03, APF-04 | Local database may not be running in every execution environment | If focused integration command fails due to DB connectivity, record the exact error in `.planning/LOCAL-VALIDATION-ISSUES.md`, run unit/platform contract tests, and rerun integration once local DB is available |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 30s for platform contract tests.
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 is complete and mapped to final PLAN tasks.

**Approval:** pending
