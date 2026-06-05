---
phase: 07-tool-registry-contracts
secured: 2026-06-05
asvs_level: 1
threats_total: 16
threats_closed: 16
threats_open: 0
status: secured
block_on: high
---

# Phase 07: Security Verification

## Summary

All 16 registered Phase 07 threats are mitigated in implementation and covered by focused regression tests. No accepted-risk or transfer dispositions were declared. Summary threat flags are all `None`, and the post-review evidence-ref sanitization warning was fixed in `07-REVIEW-FIX.md`.

Verification command:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short
```

Result: `63 passed, 1 warning`.

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-07-01 | T | mitigate | CLOSED | `ToolRegistryEntry` requires all declared metadata in `src/agent/tools/contracts.py:25`; missing-field regression in `tests/agent/test_tools/test_tool_contracts.py:68`. |
| T-07-02 | I | mitigate | CLOSED | Prompt-facing models use `extra="forbid"` in `src/agent/tools/contracts.py:50`, `src/agent/tools/contracts.py:61`, and `src/agent/tools/contracts.py:69`; raw field rejection in `tests/agent/test_tools/test_tool_contracts.py:174`. |
| T-07-03 | E | mitigate | CLOSED | Strict literals are defined in `src/agent/tools/contracts.py:8`; invalid literal regressions are in `tests/agent/test_tools/test_tool_contracts.py:93`, `tests/agent/test_tools/test_tool_contracts.py:123`, and `tests/agent/test_tools/test_tool_contracts.py:135`. |
| T-07-04 | E | mitigate | CLOSED | Investigator allowlist constant and caller gate are in `src/agent/tools/registry.py:28` and `src/agent/tools/registry.py:202`; exact allowlist test is `tests/agent/test_tools/test_registry.py:48`. |
| T-07-05 | T | mitigate | CLOSED | Registry construction validates schema, output wrapper, prompt metadata, allowlist, risk, and side effect in `src/agent/tools/registry.py:178`; fail-fast tests are `tests/agent/test_tools/test_registry.py:73`, `tests/agent/test_tools/test_registry.py:80`, and `tests/agent/test_tools/test_registry.py:98`. |
| T-07-06 | D | mitigate | CLOSED | `invoke` returns structured `not_found`, `unsafe_tool_request`, and `validation_error` before adapter execution in `src/agent/tools/registry.py:155`; non-execution tests are `tests/agent/test_tools/test_registry.py:117`, `tests/agent/test_tools/test_registry.py:128`, and `tests/agent/test_tools/test_registry.py:148`. |
| T-07-07 | T | mitigate | CLOSED | Adapters wrap existing functions without changing their signatures in `src/agent/tools/adapters.py:33`; forwarding tests are `tests/agent/test_tools/test_tool_adapters.py:30`, `tests/agent/test_tools/test_tool_adapters.py:42`, `tests/agent/test_tools/test_tool_adapters.py:54`, and `tests/agent/test_tools/test_tool_adapters.py:66`. |
| T-07-08 | I | mitigate | CLOSED | Registry conversion summarizes only declared fields and evidence refs in `src/agent/tools/registry.py:226`; raw policy text exclusion is tested in `tests/agent/test_tools/test_registry.py:239`. |
| T-07-09 | E | mitigate | CLOSED | Adapters forward `tenant_id`, `user_id`, `role`, and `session` from `ToolInvocationContext` in `src/agent/tools/adapters.py:33`; exact forwarding assertions are in `tests/agent/test_tools/test_tool_adapters.py:31`. |
| T-07-10 | T | mitigate | CLOSED | Strict versioned `InvestigationResult` schema is in `src/agent/schemas.py:64`; invalid confidence, stop reason, schema version, and extra-field tests are in `tests/agent/test_tools/test_tool_contracts.py:257`. |
| T-07-11 | D | mitigate | CLOSED | Dormant optional state fields exist only in `AgentState` at `src/agent/state.py:70` and are reset in `receive_request` at `src/agent/nodes/receive_request.py:40`; graph compatibility assertions are in `tests/agent/test_graph.py:161`. |
| T-07-12 | I | mitigate | CLOSED | API/event payload guard is in `tests/test_agent_runs_api.py:178`; final-response and approval-event negative assertions are in `tests/test_agent_runs_api.py:319` and `tests/test_agent_runs_api.py:386`. |
| T-07-13 | T | mitigate | CLOSED | `ToolOutput.status` is typed as `ToolResultStatus` in `src/agent/tools/registry.py:35`; malformed `status="pending"` regression is `tests/agent/test_tools/test_registry.py:161`. |
| T-07-14 | D | mitigate | CLOSED | `ToolRegistry.invoke` catches output conversion validation failures at `src/agent/tools/registry.py:173`; containment regression is `tests/agent/test_tools/test_registry.py:176`. |
| T-07-15 | E | mitigate | CLOSED | Non-investigator caller side-effect policy is enforced in `src/agent/tools/registry.py:210`; mismatch regressions are `tests/agent/test_tools/test_registry.py:189` and `tests/agent/test_tools/test_registry.py:214`. |
| T-07-16 | I | mitigate | CLOSED | `receive_request` resets all dormant investigation fields to `None` in `src/agent/nodes/receive_request.py:40`; same-thread stale checkpoint regression is `tests/agent/test_graph.py:303`. |

## Unregistered Flags

None. `07-02-SUMMARY.md`, `07-03-SUMMARY.md`, `07-04-SUMMARY.md`, and `07-05-SUMMARY.md` all report no threat flags. `07-01-SUMMARY.md` has no `## Threat Flags` section and no executor-reported new attack surface.

## Review Follow-Up

`07-REVIEW.md` reported one warning: sanitized registry evidence refs dropped `section`. `07-REVIEW-FIX.md` records this as fixed in commit `bc85cfc`; current code includes `ToolEvidenceRef.section` and preserves sanitized `section` while excluding raw `text` (`src/agent/tools/contracts.py:50`, `src/agent/tools/registry.py:253`, `tests/agent/test_tools/test_registry.py:283`).

## Accepted Risks

None.

## Transferred Risks

None.
