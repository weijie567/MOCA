---
phase: 30
source_review: 30-REVIEW.md
status: complete
findings_addressed: 1
created: 2026-06-28
---

# Phase 30 Code Review Fix Summary

## Findings Addressed

### WR-01: Domain Success Results Can Bypass The BusinessFactRef Requirement

**Verdict:** Confirmed.

`BusinessFactService._sanitize_domain_result(...)` previously accepted adapter-provided
`BusinessFactResultV1(status="ok" | "partial")` values after only normalizing tenant and
scope fields. That allowed a domain adapter or test double to return facts with no
`BusinessFactRefV1`, or refs for another tenant, bypassing the fail-closed check used for
`ToolResultV2` adapter successes.

**Fix commit:** `747d9f2 fix(30): reject unreferenced domain fact successes`

**Files changed:**

- `src/business/service.py`
- `tests/business/test_service.py`

## Fix

- Added domain-result success validation in `BusinessFactService._sanitize_domain_result(...)`.
- `ok` / `partial` domain results now require:
  - `fact is not None`
  - at least one `BusinessFactRefV1`
  - all refs match the trusted call `tenant_id`
- Invalid domain successes now return safe `unavailable` with no facts and no refs.
- Added regression tests for:
  - domain success with missing refs
  - domain success with wrong-tenant refs
  - compatibility `BusinessToolService.invoke_tool(...)` wrapping the unsafe domain success as no-fact/no-ref unavailable.

## Verification

```bash
uv run pytest tests/business/test_service.py -q --tb=short -k 'domain_success_without_service_refs or domain_success_with_wrong_tenant_ref'
uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py -q --tb=short
uv run ruff check src/business/service.py tests/business/test_service.py
git diff --check
```

Results:

- Targeted regression: `2 passed, 34 deselected, 1 warning`
- Business/tool focused suite: `65 passed, 1 warning`
- Ruff: passed
- `git diff --check`: passed
