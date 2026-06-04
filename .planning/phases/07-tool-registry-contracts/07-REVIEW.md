---
phase: 07-tool-registry-contracts
reviewed: 2026-06-04T06:49:52Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/agent/schemas.py
  - src/agent/state.py
  - src/agent/tools/adapters.py
  - src/agent/tools/contracts.py
  - src/agent/tools/registry.py
  - tests/agent/test_graph.py
  - tests/agent/test_tools/test_registry.py
  - tests/agent/test_tools/test_tool_adapters.py
  - tests/agent/test_tools/test_tool_contracts.py
  - tests/test_agent_runs_api.py
findings:
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-06-04T06:49:52Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the strict tool contract, registry, adapter, dormant investigation state, and related graph/API tests. The default happy path is covered, but there are several contract-boundary issues where malformed tool metadata or stale dormant state can bypass the intended safety guarantees. No critical security issue was found in the default registered tools.

Verification note: `uv run pytest tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` passed 50 non-DB tests, then the API tests failed under sandboxed local database access. Rerunning `tests/test_agent_runs_api.py` with local DB access reached PostgreSQL but failed because the test schema was not prepared and then collided during create/drop (`relation "tenants" does not exist`, followed by DDL deadlocks/duplicate type errors). I treated that as an environment/setup failure, not a source finding.

## Warnings

### WR-01: Malformed Adapter Output Can Be Silently Promoted To Success

**File:** `src/agent/tools/registry.py:34`
**Issue:** `ToolOutput.status` is typed as plain `str`, and `_to_execution_result` treats every status other than exactly `"error"` as success. A tool returning `"pending"`, `"failed"`, or another malformed status would produce a prompt-facing success result with whatever summary fields happen to be present, which weakens the strict contract guarantee.
**Fix:** Type the legacy wrapper status with the same result literal and let invalid statuses become structured tool errors.

```python
from src.agent.tools.contracts import ToolResultStatus

class ToolOutput(BaseModel):
    status: ToolResultStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
```

Also add a regression test that an adapter returning `{"status": "pending", "data": {}, "error": {}}` yields a `validation_error` or `tool_error`, not success.

### WR-02: Output Schema Validation Can Escape `invoke` As An Exception

**File:** `src/agent/tools/registry.py:212`
**Issue:** `invoke` catches input validation failures and adapter exceptions, but output validation happens after the guarded adapter call. If an adapter returns a malformed result, or if a custom `ToolRegistryEntry.output_schema` is a valid `BaseModel` that does not expose `status/data/error`, `_to_execution_result` can raise `ValidationError` or `AttributeError` instead of returning a structured `ToolExecutionResult`. That is a behavioral regression risk for any future graph caller that relies on registry errors being contained.
**Fix:** Constrain output schemas to the wrapper shape used by `_to_execution_result`, and catch conversion failures inside `invoke`.

```python
try:
    return self._to_execution_result(tool.entry, raw_result)
except (ValidationError, AttributeError, TypeError) as exc:
    return self._rejection("validation_error", str(exc))
```

For stricter metadata, either require `issubclass(output_schema, ToolOutput)` in `_validate_registered_tool`, or replace the current dynamic `output_schema` field with a registry-owned wrapper schema and reserve tool-specific output models for `data`.

### WR-03: Non-Investigator Caller Gates Ignore Side-Effect Metadata

**File:** `src/agent/tools/registry.py:204`
**Issue:** `load_business_context` and `retrieve_policy_evidence` authorization checks only compare tool name and `risk_level`. A registered allowlisted name with mismatched side-effect metadata, such as `name="get_order", risk_level="read", side_effect="write"`, would be callable by the non-investigator branch even though the registry is meant to enforce safe tool contracts.
**Fix:** Include side-effect checks in the caller gates and cover the negative cases in registry tests.

```python
if context.caller == "load_business_context":
    return (
        entry.name in _READ_CONTEXT_TOOL_NAMES
        and entry.risk_level == "read"
        and entry.side_effect in {"none", "read_only"}
    )
if context.caller == "retrieve_policy_evidence":
    return (
        entry.name in _RETRIEVAL_CONTEXT_TOOL_NAMES
        and entry.risk_level == "retrieval"
        and entry.side_effect == "retrieval"
    )
```

### WR-04: Dormant Investigation State Is Marked Ephemeral But Not Reset

**File:** `src/agent/state.py:70`
**Issue:** The new investigation fields are placed under the `AgentState` ephemeral-context section, but the current reset path only clears the older ephemeral keys. In a checkpointed thread that already contains `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, or `investigation_path`, those dormant values can persist into a later normal graph turn. That violates the phase boundary that current graph/API behavior should not change and risks stale investigation data leaking once the fields are written by a future or manual path.
**Fix:** Add these keys to the per-turn reset output in `receive_request`, and add a graph test that seeds stale investigation fields and asserts they are absent or `None` after the next turn.

```python
return {
    # existing resets...
    "investigation_result": None,
    "investigation_steps": None,
    "investigation_trigger_reason": None,
    "investigation_path": None,
}
```

---

_Reviewed: 2026-06-04T06:49:52Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
