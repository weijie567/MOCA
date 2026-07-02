# Phase 40 Verification: Tool Contract Validation Hardening

Date: 2026-07-02

## Verdict

PASS.

Phase 40 satisfies TPH-05:

- `create_coupon_grant_draft` now has a strict output schema for the real action draft success payload.
- No-data tools remain strict empty-object payloads.
- The local schema validator enforces `maxLength`, `minimum`, `maximum`, and `exclusiveMaximum`.
- Descriptor schemas are guarded against unsupported validation keywords.
- Domain-scope marker handoff has an architecture backstop tied to the business fact boundary.
- `docs/contract-spec.md`, `src/tools/contracts.py`, `src/tools/manager.py`, and `src/tools/__init__.py` have no diff.

## Evidence

### 40-01

Passed:

```bash
uv run pytest tests/tools/test_catalog.py::test_action_output_schema_is_strict_after_action_output_hardening tests/tools/test_catalog.py::test_action_output_schema_accepts_current_action_draft_payload tests/tools/test_catalog.py::test_action_output_schema_rejects_invalid_action_draft_payloads -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py::test_action_draft_caller_can_dispatch_action_tool tests/test_execute_action.py::test_action_draft_with_service_approval_result_creates_draft tests/test_execute_action.py::test_action_draft_tool_success_missing_draft_outcome_fails_closed tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q
uv run pytest tests/tools/test_catalog.py -q
uv run ruff check src/tools/catalog.py tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_execute_action.py
git diff -- src/tools/contracts.py docs/contract-spec.md
```

### 40-02

Passed:

```bash
uv run pytest tests/tools/test_catalog.py::test_json_schema_helper_enforces_string_max_length tests/tools/test_catalog.py::test_json_schema_helper_enforces_numeric_bounds tests/tools/test_catalog.py::test_all_descriptor_schemas_use_only_supported_validation_keywords -q
uv run pytest tests/tools/test_catalog.py -q
uv run ruff check src/tools/validation.py tests/tools/test_catalog.py
git diff -- pyproject.toml uv.lock docs/contract-spec.md src/tools/contracts.py
```

### 40-03 / Final

Passed:

```bash
uv run pytest tests/architecture/test_tool_contract_backstops.py -q
uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py -q
uv run pytest tests/agent/test_tools/test_unified_tool_manager.py::test_action_draft_caller_can_dispatch_action_tool tests/test_execute_action.py::test_action_draft_with_service_approval_result_creates_draft tests/test_execute_action.py::test_action_draft_tool_success_missing_draft_outcome_fails_closed tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q
uv run ruff check src/tools/catalog.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_execute_action.py
git diff -- docs/contract-spec.md src/tools/contracts.py src/tools/manager.py src/tools/__init__.py
uv run pytest tests/tools/ tests/architecture/ -q
```

Final suite result: `147 passed, 1 skipped`.

## Protected Scope

No diff:

- `docs/contract-spec.md`
- `src/tools/contracts.py`
- `src/tools/manager.py`
- `src/tools/__init__.py`
- `pyproject.toml`
- `uv.lock`

## Residual Risk

`UnifiedToolManager` cleanup remains intentionally deferred as a separate API decision. Phase 40 only preserves and regression-tests current compatibility behavior.
