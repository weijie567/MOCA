---
phase: 07-tool-registry-contracts
reviewed: 2026-06-04T13:28:42Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/agent/tools/contracts.py
  - src/agent/tools/registry.py
  - src/agent/tools/adapters.py
  - src/agent/schemas.py
  - src/agent/state.py
  - src/agent/nodes/receive_request.py
  - tests/agent/test_tools/test_tool_contracts.py
  - tests/agent/test_tools/test_registry.py
  - tests/agent/test_tools/test_tool_adapters.py
  - tests/agent/test_graph.py
  - tests/test_agent_runs_api.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-06-04T13:28:42Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the full Phase 7 source/test scope against the locked spec, context, summaries, and verification report. The registry allowlist, structured rejection paths, malformed-output containment, caller-aware side-effect gates, dormant state reset, and API payload regression tests are present. The prior verification gaps are closed and are not repeated here.

One contract mismatch remains: sanitized registry evidence refs omit `section`, but the new `InvestigationResult` citation schema requires it. That makes the future investigator unable to construct valid investigation citations from the registry's prompt-facing result alone without reaching back into raw evidence payloads.

## Warnings

### WR-01: Sanitized Registry Evidence Refs Drop Required Citation Section

**File:** `src/agent/tools/registry.py:260`
**Issue:** `_evidence_refs_from_data(...)` builds prompt-facing `ToolExecutionResult.evidence_refs` with `doc_key`, `chunk_id`, `title`, and `confidence`, but drops the policy evidence `section`. The Phase 7 `InvestigationResult` schema uses `EvidenceRefSchema`, where `section` is required. A future investigator that only sees sanitized registry results cannot produce a valid `InvestigationResult.evidence_refs` citation without using raw retrieved evidence, which undermines the Phase 7 sanitized boundary.
**Fix:**
```python
class ToolEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_key: str | None = None
    chunk_id: str | None = None
    title: str | None = None
    section: str | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


refs.append(
    {
        "doc_key": str(doc_key),
        "chunk_id": str(chunk_id),
        "title": item.get("title"),
        "section": item.get("section"),
        "confidence": item.get("score"),
    }
)
```
Add a registry sanitization assertion that `result.evidence_refs[0].section == "S1"` while raw `text` remains absent.

## Verification

- Sandboxed run: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_tool_contracts.py tests/agent/test_tools/test_registry.py tests/agent/test_tools/test_tool_adapters.py tests/agent/test_graph.py tests/test_agent_runs_api.py -q --tb=short` reached 55 passed, then API tests errored on local PostgreSQL socket access with `PermissionError: [Errno 1] Operation not permitted`.
- Escalated local-DB run of the same listed-file suite: 63 passed, 1 existing LangGraph deprecation warning.

---

_Reviewed: 2026-06-04T13:28:42Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
