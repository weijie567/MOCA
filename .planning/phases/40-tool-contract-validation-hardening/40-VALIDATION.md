---
phase: 40
slug: tool-contract-validation-hardening
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-08
updated: 2026-07-08
---

# Phase 40 - Nyquist Validation

This artifact closes the missing Nyquist validation record for Phase 40 / TPH-05. `40-VERIFICATION.md` was human-valid evidence already; Phase 60 Plan 03 normalized its YAML metadata without changing the PASS verdict.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py -q` |
| **Full tool/architecture command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/ tests/architecture/ -q` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools/catalog.py src/tools/validation.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_execute_action.py` |

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | TPH-05 | T-40-01 | `create_coupon_grant_draft` uses a strict output schema for the real action draft payload. | unit / runtime | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py::test_action_output_schema_is_strict_after_action_output_hardening tests/tools/test_catalog.py::test_action_output_schema_accepts_current_action_draft_payload tests/tools/test_catalog.py::test_action_output_schema_rejects_invalid_action_draft_payloads -q` | yes | passed |
| 40-01-02 | 01 | 1 | TPH-05 | T-40-02 | Missing or malformed `draft_outcome` fails closed before action result leakage. | runtime / action boundary | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py::test_action_draft_tool_success_missing_draft_outcome_fails_closed tests/test_execute_action.py::test_action_draft_tool_success_invalid_draft_outcome_fails_closed -q` | yes | passed |
| 40-02-01 | 02 | 2 | TPH-05 | T-40-03 | Local JSON Schema helper enforces `maxLength`, `minimum`, `maximum`, and `exclusiveMaximum`. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py::test_json_schema_helper_enforces_string_max_length tests/tools/test_catalog.py::test_json_schema_helper_enforces_numeric_bounds -q` | yes | passed |
| 40-02-02 | 02 | 2 | TPH-05 | T-40-04 | Descriptor schemas are guarded against unsupported JSON Schema keywords. | architecture / meta guard | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py::test_all_descriptor_schemas_use_only_supported_validation_keywords -q` | yes | passed |
| 40-03-01 | 03 | 3 | TPH-05 | T-40-05 | Domain-scope ownership marker handoff is tied to BusinessFactService merchant-scope/no-leak enforcement. | architecture backstop | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_tool_contract_backstops.py -q` | yes | passed |
| 40-03-02 | 03 | 3 | TPH-05 | T-40-06 | Protected scope stays unchanged: `docs/contract-spec.md`, tool contracts, legacy manager compatibility, dependency files. | structural / no-diff | `git diff -- docs/contract-spec.md src/tools/contracts.py src/tools/manager.py src/tools/__init__.py pyproject.toml uv.lock` | yes | passed |

## Closeout Evidence

- `40-01-SUMMARY.md` records strict `create_coupon_grant_draft` output schema coverage and no diff to `docs/contract-spec.md` / `src/tools/contracts.py`.
- `40-02-SUMMARY.md` records JSON Schema subset enforcement and descriptor schema meta guard coverage.
- `40-03-SUMMARY.md` records domain-scope ownership marker backstop tests and final protected no-diff verification.
- `40-VERIFICATION.md` records final suite result: `147 passed, 1 skipped`.
- Phase 40 intentionally left `UnifiedToolManager` cleanup to Phase 41; this was a named residual risk, not a Phase 40 validation gap.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | TPH-05 | Phase 40 behavior is backend tool-contract validation with automated test and protected-diff evidence. | N/A |

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Wave 0 covers strict action output schema, domain-scope marker backstop, JSON Schema subset/meta guard, and protected no-diff boundaries.
- [x] Phase 40 verification metadata is normalized by Phase 60 without changing its verdict.
- [x] No watch-mode flags.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** complete.
