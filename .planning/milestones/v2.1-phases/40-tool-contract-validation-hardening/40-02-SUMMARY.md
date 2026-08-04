# Plan 40-02 Summary: Validator Keyword Support and Meta Guard

Date: 2026-07-02

## Outcome

Completed.

`validate_json_value` now enforces the advertised string and numeric bounds:

- `maxLength`
- `minimum`
- `maximum`
- `exclusiveMaximum`

Numeric bounds apply to both `integer` and `number`; existing non-finite number rejection remains in place for `number`.

The descriptor schema meta guard now recursively checks every default catalog descriptor `input_schema` and `output_schema` against `SUPPORTED_JSON_SCHEMA_KEYS`, so unsupported keywords cannot silently enter descriptors.

## Files Changed

- `src/tools/validation.py`
- `tests/tools/test_catalog.py`

## Verification

Passed:

```bash
uv run pytest tests/tools/test_catalog.py::test_json_schema_helper_enforces_string_max_length tests/tools/test_catalog.py::test_json_schema_helper_enforces_numeric_bounds tests/tools/test_catalog.py::test_all_descriptor_schemas_use_only_supported_validation_keywords -q
uv run pytest tests/tools/test_catalog.py -q
uv run ruff check src/tools/validation.py tests/tools/test_catalog.py
git diff -- pyproject.toml uv.lock docs/contract-spec.md src/tools/contracts.py
```

Results:

- `tests/tools/test_catalog.py`: 43 passed.
- Ruff: all checks passed.
- Protected dependency/spec/contracts diff: empty.
