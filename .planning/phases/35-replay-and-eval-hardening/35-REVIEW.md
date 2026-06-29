---
phase: 35-replay-and-eval-hardening
reviewed: 2026-06-29T16:43:35Z
depth: deep
files_reviewed: 22
files_reviewed_list:
  - docs/evaluation.md
  - eval/replay/dev-contract-manifest.v1.json
  - eval/replay/monitoring-gate.v1.json
  - eval/replay/phase35-coverage-matrix.v1.json
  - eval/replay/release-gate.v1.json
  - eval/replay/release-smoke-cases.v1.json
  - src/replay/lifecycle.py
  - src/replay/pairing.py
  - src/replay/phase35_eval_manifest.py
  - src/replay/phase35_matrix.py
  - src/replay/proof_projection.py
  - src/replay/service.py
  - src/replay/validators.py
  - tests/agent/test_trace.py
  - tests/architecture/test_phase35_replay_eval_boundaries.py
  - tests/eval/test_phase35_release_monitoring_manifests.py
  - tests/eval/test_phase35_replay_eval_gates.py
  - tests/replay/test_phase35_coverage_matrix.py
  - tests/replay/test_phase35_operation_identity.py
  - tests/replay/test_phase35_redaction_negatives.py
  - tests/replay/test_phase35_terminal_timelines.py
  - tests/replay/test_phase35_trace_replay_permissions.py
findings:
  critical: 1
  warning: 4
  info: 0
  total: 5
status: issues_found
---

# Phase 35: Code Review Report

**Reviewed:** 2026-06-29T16:43:35Z
**Depth:** deep
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Deep review covered the Phase 35 replay/eval manifests, replay projection services, operation pairing, redaction guards, owner/admin replay visibility tests, terminal timeline tests, and the referenced forbidden-behavior gate tests. Manifest hashes currently match their referenced artifacts, and the trace/replay API guard tests keep owner/admin-only visibility.

Issues remain around a direct replay error leakage path, incomplete operation-pair validation, spoofable replay authorization proof inputs, command-entrypoint validator bypasses, and an operation-identity test gap that can pass without exercising the production event emitter.

## Critical Issues

### CR-01: Replay error projections bypass redaction and leak through the replay API

**File:** `src/replay/service.py:253`

**Issue:** `append_event()` validates `redacted_payload` and `resource_refs`, but `error_json` is accepted at the append boundary, stored on the row, and projected as `error` without any redaction guard or safe-message normalization. A replay row with `error_json={"code": "...", "message": "Traceback ... sk_live_...", "retryable": false}` would be returned by `get_replay()` and then `/replay`, bypassing the Phase 35 no raw stack/secret/PII leakage contract.

**Fix:**
```python
def _safe_error_json(error_json: dict[str, Any] | None) -> dict[str, Any] | None:
    if error_json is None:
        return None
    guard_redacted_payload({"error": error_json})
    code = str(error_json.get("code") or "REPLAY_EVENT_ERROR")[:64]
    safe_message = str(error_json.get("safe_message") or code)[:256]
    return {"code": code, "message": safe_message, "retryable": error_json.get("retryable") is True}
```
Use the sanitizer before persistence and again before projection, and add a negative test that stores an unsafe `error_json` with a traceback/secret marker and proves `get_replay()` rejects or omits it.

## Warnings

### WR-01: Terminal operation pairing does not verify the started event family or attempt

**File:** `src/replay/pairing.py:61`

**Issue:** Terminal events only require some prior started event for the same `operation_id`. The validator does not prove that `tool_call_completed` pairs with `tool_call_started` rather than a different family, and the retry branch can accept a terminal event whose `attempt` differs from the started event for the same `operation_id`. This weakens deterministic replay timelines and can make retry/audit projections internally inconsistent.

**Fix:** Resolve the unique started event for the `operation_id`, then require the same operation family, attempt, and parent operation before returning `PAIRED`.

```python
started_event = _single_started_event(prior_events, operation_id)
if _operation_family(event_type) != _operation_family(_field(started_event, "event_type")):
    raise OperationPairingError("terminal event family must match started event")
if attempt != _field(started_event, "attempt"):
    raise OperationPairingError("terminal event attempt must match started event")
if parent_operation_id != _optional_uuid(_field(started_event, "parent_operation_id")):
    raise OperationPairingError("terminal event parent_operation_id must match started event")
```
Add negative tests for `tool_call_started` plus `rag_retrieval_completed`, and for retry terminal attempt mismatch.

### WR-02: Replay authorization proof treats spoofable BusinessFact inputs as resolved

**File:** `src/replay/proof_projection.py:158`

**Issue:** `_inspect_business_fact_refs()` accepts any payload that validates as `BusinessFactRefV1`, and `_inspect_business_fact_results()` accepts any `BusinessFactResultV1` with `status` ok/partial and allowed scope. Neither path validates trusted `source_system` values or proves the payload came from the BusinessFactService/tool platform. A user/LLM-injected state field can therefore produce `proof_status="resolved"` in a projection named and documented as replay authorization proof.

**Fix:** Reuse a single trusted-source predicate for refs and results, mark untrusted sources as `unknown`, and do not count them as allowed proof.

```python
TRUSTED_BUSINESS_FACT_SOURCES = {...}

if ref.source_system not in TRUSTED_BUSINESS_FACT_SOURCES:
    untrusted = True
    continue
```
Add tests where `source_system="llm"` or `source_system="user_payload"` is rejected even when tenant IDs match.

### WR-03: Required-command validation can miss a chained bare pytest invocation

**File:** `src/replay/phase35_eval_manifest.py:202`

**Issue:** `_contains_bare_pytest()` returns `False` as soon as a command starts with an approved prefix. A command like `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/a.py; pytest tests/b.py` would pass even though it includes a bare `pytest`, which MOCA treats as invalid verification. The matrix validator has the same pattern at `src/replay/phase35_matrix.py:201`, where any approved substring suppresses the bare-pytest scan for the entire value.

**Fix:** Scan every pytest occurrence or split shell snippets on separators before validating each command segment. Add regression tests for `approved && pytest ...`, `approved ; python -m pytest ...`, and mixed inline-code snippets.

### WR-04: Operation identity tests bypass the production event-emitter path

**File:** `tests/replay/test_phase35_operation_identity.py:47`

**Issue:** The Phase 35 operation identity tests call `ReplayService.append_event()` directly with `replay_event.v3` semantics and explicit attempts. Production tool/RAG event paths still go through the higher-level event emitter, which writes minimal envelopes without attempts and projects them as unresolved compatibility events. The test can pass while real tool invocation timelines fail to demonstrate the paired attempt semantics claimed by the Phase 35 gate.

**Fix:** Add an integration test through the production emitter or a representative graph/tool path, then assert the replay API timeline contains the required operation IDs, attempts, parent retry IDs, and paired terminal provenance. If minimal-envelope compatibility is still intentionally allowed for Phase 35, narrow the manifest/test assertion to that explicit compatibility behavior.

---

_Reviewed: 2026-06-29T16:43:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
