---
phase: 37
slug: tool-declaration-runtime-policy-internal-consolidation
status: complete_pending_db_note
nyquist_compliant: false
wave_0_complete: true
created: 2026-07-01
updated: 2026-07-08
---

# Phase 37 - Nyquist Validation Refresh

This artifact replaces the original draft validation strategy with archive-gate validation evidence for TPH-03 and TPH-04.

Phase 37 implementation evidence is source-backed and formally verified by `37-VERIFICATION.md`, but the historical DB-backed pytest note is not closed here. DB-backed pytest note final disposition is owned by Phase 60 Plan 04 per D-05.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` |
| **Current-equivalent archive command for 60 Plan 04** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/tools tests/tools tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py` |
| **DB-backed note** | Pending final disposition in Phase 60 Plan 04; this file intentionally keeps `nyquist_compliant: false`. |

## Sampling Rate

- **After every task commit:** Phase 37 plans recorded focused tool-catalog, tool-platform, replay, architecture, and Ruff checks.
- **After every plan wave:** Phase 37 attempted the full relevant gate; DB fixture setup was blocked by local PostgreSQL connection refusal.
- **Archive refresh:** Phase 60 Plan 03 maps the validation surface to current files because the historical `tests/agent/test_tools/test_unified_tool_manager.py` compatibility file was removed by Phase 41.
- **Before archive closure:** Phase 60 Plan 04 must either pass the current-equivalent archive command above or record named accepted debt with exact environment evidence.

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | TPH-03 | T-37-01 | Tool declarations resolve from `_TOOL_DECLARATIONS`; `_IDENTIFIER_SCHEMAS` is derived rather than separately maintained. | unit / structural | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | source-backed; formal verification passed |
| 37-01-02 | 01 | 1 | TPH-03 | T-37-01 | Planner-visible investigate tool names derive from catalog descriptors and planner exposure. | unit / structural | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py -q` | yes | source-backed; formal verification passed |
| 37-02-01 | 02 | 2 | TPH-04 | T-37-02 | `ToolRuntime.invoke` failure exits share `_fail(...)` for safe result, projection, decision event, and outcome tuple construction. | unit / structural / behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | source-backed; formal verification passed |
| 37-02-02 | 02 | 2 | TPH-04 | T-37-03 | Runtime-auth event payloads remain low-payload and omit raw args/output/schema details. | replay regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_tool_policy_events.py -q` | yes | source-backed; formal verification passed |
| 37-03-01 | 03 | 3 | TPH-04 | T-37-04 | `ToolPolicyEngine.runtime_auth` evaluates ordered `RuntimeAuthGate` declarations for caller, permission, side-effect, scope, approval, safety snapshot, idempotency, and availability decisions. | unit / structural / behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py -q` | yes | source-backed; formal verification passed |
| 37-03-02 | 03 | 3 | TPH-03, TPH-04 | T-37-01 / T-37-04 | External tool contract models keep their field names and reject unexpected fields; output-schema hardening stays Phase 38-owned. | regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` | yes | pending final DB-backed disposition in 60 Plan 04 |

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
- [ ] Phase 60 Plan 04 closes or explicitly carries the DB-backed pytest note.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None for source-backed TPH-03/TPH-04 behavior | TPH-03, TPH-04 | The required behavior has source-level, test, review, summary, and formal verification evidence. | N/A |
| DB-backed environment disposition | TPH-04 | Historical Phase 37 final gate was blocked by local PostgreSQL availability; Phase 60 Plan 04 owns the rerun or accepted-debt decision. | Run the current-equivalent archive command with local PostgreSQL available, or record named debt with exact evidence. |

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity is documented from Phase 37 summaries.
- [x] Wave 0 covers TPH-03 and TPH-04 behavior.
- [x] No watch-mode flags.
- [x] Feedback latency target is bounded to focused suites; DB-backed final disposition is explicitly separated.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.
- [ ] `nyquist_compliant: true` is intentionally not set until Phase 60 Plan 04 resolves or carries the DB-backed note.

**Approval:** complete_pending_db_note.
