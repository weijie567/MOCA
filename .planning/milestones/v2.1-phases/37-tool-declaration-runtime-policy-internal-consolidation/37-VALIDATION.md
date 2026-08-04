---
phase: 37
slug: tool-declaration-runtime-policy-internal-consolidation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-01
updated: 2026-07-08
---

# Phase 37 - Nyquist Validation Refresh

This artifact replaces the original draft validation strategy with archive-gate validation evidence for TPH-03 and TPH-04.

Phase 37 implementation evidence is source-backed and formally verified by `37-VERIFICATION.md`. The historical DB-backed pytest note is resolved by Phase 60 Plan 04 with the current-equivalent archive command recorded below.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` |
| **Current-equivalent archive command for 60 Plan 04** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools tests/tools tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py` |
| **DB-backed note** | Resolved by Phase 60 Plan 04: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` -> `108 passed, 1 warning in 30.42s`. |

## Sampling Rate

- **After every task commit:** Phase 37 plans recorded focused tool-catalog, tool-platform, replay, architecture, and Ruff checks.
- **After every plan wave:** Phase 37 attempted the full relevant gate; DB fixture setup was blocked by local PostgreSQL connection refusal.
- **Archive refresh:** Phase 60 Plan 03 maps the validation surface to current files because the historical `tests/agent/test_tools/test_unified_tool_manager.py` compatibility file was removed by Phase 41.
- **Before archive closure:** Phase 60 Plan 04 passed the current-equivalent archive command above, resolving the DB-backed pytest note.

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | TPH-03 | T-37-01 | Tool declarations resolve from `_TOOL_DECLARATIONS`; `_IDENTIFIER_SCHEMAS` is derived rather than separately maintained. | unit / structural | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | source-backed; formal verification passed |
| 37-01-02 | 01 | 1 | TPH-03 | T-37-01 | Planner-visible investigate tool names derive from catalog descriptors and planner exposure. | unit / structural | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | source-backed; formal verification passed |
| 37-02-01 | 02 | 2 | TPH-04 | T-37-02 | `ToolRuntime.invoke` failure exits share `_fail(...)` for safe result, projection, decision event, and outcome tuple construction. | unit / structural / behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | source-backed; formal verification passed |
| 37-02-02 | 02 | 2 | TPH-04 | T-37-03 | Runtime-auth event payloads remain low-payload and omit raw args/output/schema details. | replay regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_tool_policy_events.py -q` | yes | source-backed; formal verification passed |
| 37-03-01 | 03 | 3 | TPH-04 | T-37-04 | `ToolPolicyEngine.runtime_auth` evaluates ordered `RuntimeAuthGate` declarations for caller, permission, side-effect, scope, approval, safety snapshot, idempotency, and availability decisions. | unit / structural / behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | source-backed; formal verification passed |
| 37-03-02 | 03 | 3 | TPH-03, TPH-04 | T-37-01 / T-37-04 | External tool contract models keep their field names and reject unexpected fields; output-schema hardening stays Phase 38-owned. | regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` | yes | resolved by Phase 60 Plan 04; `108 passed, 1 warning in 30.42s` |

## Evidence Links

- `37-VERIFICATION.md` records 6/6 observable truths for TPH-03 and source-backed TPH-04 behavior, with `status: passed_with_followup`.
- `37-01-SUMMARY.md` records `_TOOL_DECLARATIONS`, derived `_IDENTIFIER_SCHEMAS`, catalog-derived investigate filtering, and drift tests.
- `37-02-SUMMARY.md` records seven runtime failure paths routed through `_fail(...)` and low-payload runtime-auth replay regression coverage.
- `37-03-SUMMARY.md` records the ordered `RuntimeAuthGate` sequence and the final protected contract-shape checks.
- `37-REVIEW.md` records a clean review with 0 findings.

## Wave 0 Requirements

- [x] `tests/tools/test_catalog.py` covers registry/schema/name drift for TPH-03.
- [x] `tests/tools/test_tool_platform.py` covers `_fail(...)` and declarative runtime-auth gates for TPH-04.
- [x] Current archive validation does not rely on deleted legacy manager tests.
- [x] Phase 60 Plan 04 closes the DB-backed pytest note with the current-equivalent archive command.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None for source-backed TPH-03/TPH-04 behavior | TPH-03, TPH-04 | The required behavior has source-level, test, review, summary, and formal verification evidence. | N/A |
| None for DB-backed environment disposition | TPH-04 | Historical Phase 37 final gate was blocked by local PostgreSQL availability, but Phase 60 Plan 04 reran the current-equivalent command successfully. | N/A |

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity is documented from Phase 37 summaries.
- [x] Wave 0 covers TPH-03 and TPH-04 behavior.
- [x] No watch-mode flags.
- [x] Feedback latency target is bounded to focused suites; DB-backed final disposition is explicitly separated.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.
- [x] `nyquist_compliant: true` is set after Phase 60 Plan 04 resolved the DB-backed note.

## Closeout Evidence

- DB-backed pytest note resolved by Phase 60 Plan 04.
- Command: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q`
- Result: `108 passed, 1 warning in 30.42s`.

**Approval:** complete.
