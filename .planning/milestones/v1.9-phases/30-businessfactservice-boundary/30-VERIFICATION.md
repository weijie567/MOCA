---
phase: 30-businessfactservice-boundary
status: passed
verified_at: 2026-06-28T08:32:25+0800
requirements_verified: [APF-08]
automated_checks:
  focused_phase30: passed
  ruff: passed
  diff_check: passed
  code_review: clean
uat_status: complete
human_verification_required: false
security_review_required: false
---

# Phase 30 Verification - BusinessFactService Boundary

## Verdict

Phase 30 passes verification. APF-08 is implemented across the domain service, ToolPlatform integration, graph projection, investigate aggregation, and material-claim authority boundaries.

This verification was refreshed after all Phase 30 code-review fixes through `62bd0d0` and the clean deep review report `2ac1da6` / `ad4ac69` follow-up state. The previous verification artifact contained stale post-review-fix evidence; this version reflects the current repository.

## Requirements

| Requirement | Status | Evidence |
|-------------|--------|----------|
| APF-08 | PASSED | Business fact reads expose `BusinessFactResultV1` / `BusinessFactRefV1` through `BusinessFactService`; ToolPlatform and graph code cannot substitute memory, RAG/policy evidence, model knowledge, prompt summaries, raw repository-row-shaped data, or raw tool data for current business facts. |

## Success Criteria Verification

### 1. BusinessFactResultV1 and BusinessFactService Domain Reads

Status: PASSED

Evidence:

- `src/business/schemas.py` defines strict `BusinessFactResultV1` with `schema_version="business_fact_result.v1"`, `scope_check_result`, `missing_required_facts`, and `safe_errors`.
- `src/business/service.py` defines `BusinessFactService` public methods for `fetch_context`, order, refund case, ticket, logistics, and merchant-risk reads.
- Service tests cover allowed same-merchant/admin reads, same-tenant cross-merchant denial, unknown/missing merchant scope denial, unsupported reads, stale/unavailable fail-closed results, wrong-tenant refs, missing refs, and legacy list merchant scope.

### 2. ToolPlatform Business-Read Boundary

Status: PASSED

Evidence:

- `src/tools/executors/business.py` imports and delegates through the service boundary.
- `src/tools/policy.py` preserves `requires_domain_scope_check` while redacting raw domain identifiers from serialized policy bindings.
- `tests/tools/test_tool_platform.py` proves service-approved refs are emitted only after domain proof and denied/unavailable paths emit no data and no refs.

### 3. Projection and Investigate No-Leak Behavior

Status: PASSED

Evidence:

- `src/tools/projection.py` sources business refs from `ToolResultV2.business_fact_refs`, not raw `result.data` identifiers.
- `src/agent/nodes/investigate.py` accumulates facts/refs only from fact-bearing success statuses with service-approved refs.
- Tests prove denied, stale, unavailable, and raw-data-shaped business identifiers do not populate prompt summaries, `business_context`, `last_business_context_refs`, or `claim_dependency_map`.

### 4. Authority-Substitution Boundaries

Status: PASSED

Evidence:

- `tests/agent/rag_context/test_authority_boundaries.py` covers memory, RAG/policy evidence, model knowledge, prompt summaries, raw repository rows, wrong tenant refs, missing trusted tenant, and missing policy evidence membership.
- `tests/agent/test_policy_retrieval_ownership.py` verifies graph nodes do not import `BusinessFactService`, `BusinessToolService`, raw demo integrations, or business repositories; the business executor imports the service boundary without raw repositories/integrations.
- Latest review fix `62bd0d0` prevents action recommendations from opening allow flags when Level 1 policy evidence membership fails.

### 5. Scope Exclusions

Status: PASSED

Evidence:

- No implementation work was added for Phase 31 memory platform isolation, Phase 33 full RAG claim verification, Phase 34 approval/action binding, Phase 35 replay/eval broad hardening, Phase 36+ DB/RLS work, physical microservices, or real external execution.
- Authority-boundary changes remain narrow APF-08 negative coverage and verifier fail-closed behavior.

## Automated Verification

Commands run:

```bash
uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short

uv run ruff check src/business/schemas.py src/business/service.py src/business/__init__.py src/tools/executors/business.py src/tools/policy.py src/tools/projection.py src/agent/nodes/investigate.py src/agent/rag_context/verifier.py tests/business/test_schemas.py tests/business/test_service.py tests/business/test_adapters.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py

git diff --check
```

Results:

- Full Phase 30 focused suite: `203 passed, 1 warning`
- Ruff: passed
- `git diff --check`: passed

The warning is the existing LangGraph `allowed_objects` pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`; it is not a Phase 30 failure.

## Review Gate

Code review is clean:

- `.planning/phases/30-businessfactservice-boundary/30-REVIEW.md`
- Status: `clean`
- Findings: `0 critical`, `0 warning`, `0 info`

Latest review-fix chain:

- `cc046a4` - enforce tenant scope for business fact authority
- `c51b174` - remove dead projection migration helpers
- `62bd0d0` - fail closed missing policy evidence

## UAT / Self-Check

Automated self-check UAT is complete:

- `.planning/phases/30-businessfactservice-boundary/30-UAT.md`
- Status: `complete`
- Passed: 6
- Issues: 0
- Blocked: 0

No human-only verification is required for Phase 30; behaviors are covered by automated tests and source-boundary checks.

## Artifact Scan

`audit-open --json` found no current Phase 30 UAT gaps, verification gaps, or context open questions. It reported one unrelated global planning TODO for old phase-directory archive cleanup.

## Security Gate

Security review is complete:

- `.planning/phases/30-businessfactservice-boundary/30-SECURITY.md`
- Status: `verified`
- Threats total: 12
- Threats closed: 12
- Threats open: 0
- Accepted risks: none
- Auditor verdict: `SECURED`

## Final Status

PASSED. Phase 30 has no open verification, code-review, UAT, or security findings.
