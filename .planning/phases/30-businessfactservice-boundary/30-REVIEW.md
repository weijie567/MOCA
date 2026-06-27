---
phase: 30
status: findings
files_reviewed: 14
finding_counts:
  critical: 0
  warning: 1
  info: 0
  total: 1
reviewed: 2026-06-27T19:43:57Z
depth: standard
files_reviewed_list:
  - src/agent/nodes/investigate.py
  - src/agent/rag_context/verifier.py
  - src/business/__init__.py
  - src/business/schemas.py
  - src/business/service.py
  - src/tools/executors/business.py
  - src/tools/policy.py
  - src/tools/projection.py
  - tests/agent/rag_context/test_authority_boundaries.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_policy_retrieval_ownership.py
  - tests/business/test_schemas.py
  - tests/business/test_service.py
  - tests/tools/test_tool_platform.py
---

# Phase 30 Code Review Report

**Reviewed:** 2026-06-27T19:43:57Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** findings

## Summary

Reviewed the Phase 30 BusinessFactService boundary, ToolPlatform wrapping, projection, investigate graph accumulation, verifier authority checks, and related tests. The main no-leak paths for default order/refund/ticket adapters are conservative: denied, stale, unavailable, and unsupported reads emit no facts or refs through ToolResultV2, projection refs come from the envelope, and investigate does not import business repositories or fabricate denied dependencies.

One boundary gap remains in `BusinessFactService` for domain-result adapters: the service enforces the "success requires `BusinessFactRefV1`" rule for `ToolResultV2` adapter successes, but not for `BusinessFactResultV1` successes.

## Warnings

### WR-01: Domain Success Results Can Bypass The BusinessFactRef Requirement

**File:** `src/business/service.py:416`

**Issue:** `_sanitize_domain_result()` trusts adapter-provided `BusinessFactResultV1` values with `status in {"ok", "partial"}` and returns them as allowed after only overriding `tenant_id` and `scope_check_result`. That skips the fail-closed check used for `ToolResultV2` successes at `src/business/service.py:350-361`, where missing `business_fact_refs` becomes `unavailable`.

Because `BusinessFactService.get_order()`, `get_refund_case()`, and `get_ticket()` are public domain methods, a domain adapter or test double can return `BusinessFactResultV1(status="ok", fact={...}, business_fact_refs=[])` and the service will expose a fact without service-approved `BusinessFactRefV1` authority. The same path also does not reject mismatched ref tenants. This violates the Phase 30 APF-08 contract that current business facts must be carried by service-approved refs, not raw or adapter-shaped data.

**Fix:** Apply the same fail-closed success validation to domain results before returning them. At minimum, require non-empty refs for `ok`/`partial`, require `fact is not None`, and reject refs whose `tenant_id` does not match the call context.

```python
if result.status in {"ok", "partial"}:
    refs_allowed = result.fact is not None and result.business_fact_refs
    refs_allowed = refs_allowed and all(ref.tenant_id == tenant_id for ref in result.business_fact_refs)
    if not refs_allowed:
        return self._safe_result(
            "unavailable",
            resource_name=resource_name,
            tenant_id=tenant_id,
            source_system=result.source_system,
            scope_check_result="unknown",
            code="BUSINESS_FACT_UNAVAILABLE",
            safe_message="Business fact is unavailable",
            error_source="adapter",
        )
    return result.model_copy(update={"tenant_id": tenant_id, "scope_check_result": "allowed"})
```

Add a regression test with a domain adapter returning `BusinessFactResultV1(status="ok", fact={...}, business_fact_refs=[])` and assert both `BusinessFactService.get_order()` and `BusinessToolService.invoke_tool()` fail closed with no facts or refs.

---

_Reviewer: Codex (gsd-code-reviewer)_
