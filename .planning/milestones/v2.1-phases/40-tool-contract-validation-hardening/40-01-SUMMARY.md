# Plan 40-01 Summary: Strict Action Output Schema

Date: 2026-07-02

## Outcome

Completed.

`create_coupon_grant_draft` no longer uses the generic output schema. Its catalog declaration now validates the stable action draft success payload shape emitted by `ActionService.create_coupon_grant_draft`, including:

- top-level draft metadata;
- full `action_draft` envelope;
- `draft_outcome`;
- demo `execution_mode`;
- compatibility `action_result`.

The existing no-data schemas for unavailable tools were not changed.

## Files Changed

- `src/tools/catalog.py`
- `tests/tools/test_catalog.py`
- `tests/agent/test_tools/test_unified_tool_manager.py`
- `tests/test_execute_action.py`

## Notes

- Action fake payloads were upgraded to the strict contract rather than weakening the schema.
- Tests that remove or corrupt `draft_outcome` now fail earlier through runtime output-schema validation as `INVALID_EXECUTOR_RESPONSE`, which is the intended Phase 40 fail-closed path.
- `docs/contract-spec.md` and `src/tools/contracts.py` were not modified.

## Verification

Passed:

```bash
uv run pytest tests/tools/test_catalog.py::test_action_output_schema_is_strict_after_action_output_hardening tests/tools/test_catalog.py::test_action_output_schema_accepts_current_action_draft_payload tests/tools/test_catalog.py::test_action_output_schema_rejects_invalid_action_draft_payloads -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py::test_action_draft_caller_can_dispatch_action_tool tests/test_execute_action.py::test_action_draft_with_service_approval_result_creates_draft tests/test_execute_action.py::test_action_draft_tool_success_missing_draft_outcome_fails_closed tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q
uv run pytest tests/tools/test_catalog.py -q
uv run ruff check src/tools/catalog.py tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_execute_action.py
git diff -- src/tools/contracts.py docs/contract-spec.md
```

Results:

- `tests/tools/test_catalog.py`: 40 passed.
- Focused action/legacy adapter tests: 4 passed.
- Ruff: all checks passed.
- Protected spec/contracts diff: empty.
