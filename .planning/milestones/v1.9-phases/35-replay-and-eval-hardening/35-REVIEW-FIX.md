---
phase: 35-replay-and-eval-hardening
fixed_at: 2026-06-29T16:57:34Z
review_path: .planning/phases/35-replay-and-eval-hardening/35-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 35: Code Review Fix Report

**Fixed at:** 2026-06-29T16:57:34Z
**Source review:** .planning/phases/35-replay-and-eval-hardening/35-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Replay error projections bypass redaction and leak through the replay API

**Status:** fixed
**Files modified:** `src/replay/service.py`, `tests/replay/test_phase35_redaction_negatives.py`
**Commit:** efbd03b
**Applied fix:** Added `_safe_error_json()` and used it before persistence and projection, so stored replay errors only expose `code`, safe `message`, and `retryable`. Added negative coverage for unsafe error keys and stored traceback/secret markers.
**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('src/replay/service.py','tests/replay/test_phase35_redaction_negatives.py')]"`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_redaction_negatives.py -q`

### WR-01: Terminal operation pairing does not verify the started event family or attempt

**Status:** fixed: requires human verification
**Files modified:** `src/replay/pairing.py`, `tests/replay/test_phase35_operation_identity.py`
**Commit:** 34bb927
**Applied fix:** Terminal operation validation now resolves a unique started event and requires matching operation family, attempt, and parent operation before returning `paired`. Added negative tests for cross-family terminal pairing and retry attempt mismatch.
**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('src/replay/pairing.py','tests/replay/test_phase35_operation_identity.py')]"`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_operation_identity.py -q`

### WR-02: Replay authorization proof treats spoofable BusinessFact inputs as resolved

**Status:** fixed: requires human verification
**Files modified:** `src/replay/proof_projection.py`, `tests/agent/test_trace.py`
**Commit:** 6f7e3ae
**Applied fix:** Added a trusted BusinessFact source predicate shared by refs and results. Untrusted `source_system` values no longer count as allowed proof and project `unknown` with `REPLAY_AUTHORIZATION_PROOF_UNTRUSTED_STATUS`. Added `llm` and `user_payload` spoofing regressions.
**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('src/replay/proof_projection.py','tests/agent/test_trace.py')]"`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q`

### WR-03: Required-command validation can miss a chained bare pytest invocation

**Status:** fixed: requires human verification
**Files modified:** `src/replay/phase35_eval_manifest.py`, `src/replay/phase35_matrix.py`, `tests/eval/test_phase35_replay_eval_gates.py`, `tests/replay/test_phase35_coverage_matrix.py`
**Commit:** a5460ca
**Applied fix:** Updated both Phase 35 command validators to scan every pytest entrypoint occurrence instead of suppressing the whole string when one approved entrypoint is present. Added chained-command and inline-snippet regressions.
**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('src/replay/phase35_eval_manifest.py','src/replay/phase35_matrix.py','tests/eval/test_phase35_replay_eval_gates.py','tests/replay/test_phase35_coverage_matrix.py')]"`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/replay/test_phase35_coverage_matrix.py -q`

### WR-04: Operation identity tests bypass the production event-emitter path

**Status:** fixed
**Files modified:** `tests/replay/test_phase35_operation_identity.py`, `eval/replay/phase35-coverage-matrix.v1.json`, `eval/replay/dev-contract-manifest.v1.json`
**Commit:** 5b119c9
**Applied fix:** Added production `emit_event()` coverage documenting Phase 35 minimal-envelope compatibility: operation IDs project through replay, while attempts and paired provenance remain unresolved. Narrowed the coverage matrix note to distinguish strict V3 append pairing from minimal-emitter compatibility and updated the manifest matrix hash.
**Verification:**
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast, json, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ('tests/replay/test_phase35_operation_identity.py',)]; [json.loads(pathlib.Path(p).read_text()) for p in ('eval/replay/phase35-coverage-matrix.v1.json','eval/replay/dev-contract-manifest.v1.json')]"`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_coverage_matrix.py tests/eval/test_phase35_replay_eval_gates.py -q`

---

_Fixed: 2026-06-29T16:57:34Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
