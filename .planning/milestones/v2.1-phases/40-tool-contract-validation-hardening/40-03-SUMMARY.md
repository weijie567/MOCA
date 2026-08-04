# Plan 40-03 Summary: Ownership Marker Backstop and Final Verification

Date: 2026-07-02

## Outcome

Completed.

Added architecture backstop tests for the `requires_domain_scope_check` handoff:

- marker-bearing catalog tools are exactly `get_order`, `get_refund_case`, and `get_ticket`;
- those tools must remain `read` tools routed through the `business` executor with the expected resource types;
- `BusinessToolExecutor` delegates to the business service boundary;
- invalid merchant scope is denied in `BusinessFactService` before adapter invocation and without leaking the requested identifier.

No runtime ownership behavior was changed. Policy still marks domain identifiers; BusinessFactService/business adapters remain responsible for data-coupled ownership and no-leak behavior.

## Files Changed

- `tests/architecture/test_tool_contract_backstops.py`

## Verification

Passed:

```bash
uv run pytest tests/architecture/test_tool_contract_backstops.py -q
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py::test_action_draft_caller_can_dispatch_action_tool tests/test_execute_action.py::test_action_draft_with_service_approval_result_creates_draft tests/test_execute_action.py::test_action_draft_tool_success_missing_draft_outcome_fails_closed tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q
uv run ruff check src/tools/catalog.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_execute_action.py
git diff -- docs/contract-spec.md src/tools/contracts.py src/tools/manager.py src/tools/__init__.py
uv run pytest tests/tools/ tests/architecture/ -q
```

Results:

- New architecture test file: 3 passed.
- Focused tools/tool_platform/architecture suite: 76 passed.
- Focused action/legacy adapter regressions: 4 passed.
- Ruff: all checks passed.
- Protected spec/contracts/manager/API diff: empty.
- Full `tests/tools/ tests/architecture/`: 147 passed, 1 skipped.

No new `.planning/LOCAL-VALIDATION-ISSUES.md` entry was needed.
