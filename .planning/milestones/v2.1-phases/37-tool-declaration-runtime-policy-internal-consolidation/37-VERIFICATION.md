---
phase: 37-tool-declaration-runtime-policy-internal-consolidation
verified: 2026-07-08T12:36:55Z
status: passed
score: source-backed
overrides_applied: 0
requirements:
  - TPH-03
  - TPH-04
---

# Phase 37 Verification: Tool Declaration / Runtime / Policy Internal Consolidation

**Source-backed formal verification for TPH-03 and TPH-04. The historical DB-backed pytest note is resolved by Phase 60 Plan 04.**

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | TPH-03 single-source declaration rows exist in the catalog and feed descriptor construction. | VERIFIED | `_TOOL_DECLARATIONS` is the declaration table and `_descriptor(...)` consumes each declaration at `src/tools/catalog.py:326` and `src/tools/catalog.py:501`. Phase 37-01 records this as the single internal declaration table at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:61`. |
| 2 | `_IDENTIFIER_SCHEMAS` is retained only as a derived compatibility map, not a second hand-maintained schema source. | VERIFIED | The compatibility map derives directly from declarations at `src/tools/catalog.py:498`; Phase 37-01 explicitly records that decision at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:31`. |
| 3 | Planner-visible investigate tool names are derived from descriptor attributes. | VERIFIED | `investigate_tool_names(...)` filters descriptors by caller allowlist, non-write kind, and planner-visible exposure at `src/tools/catalog.py:526`; Phase 37-01 records the same catalog helper pattern at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:36`. |
| 4 | TPH-04 runtime failure exits are centralized through `_fail(...)`. | VERIFIED | `ToolRuntime.invoke(...)` routes descriptor missing, invalid input, policy denial, unavailable executor, executor exception, invalid executor response, and output schema failure through `await self._fail(...)` at `src/tools/runtime.py:84`, `src/tools/runtime.py:104`, `src/tools/runtime.py:124`, `src/tools/runtime.py:142`, `src/tools/runtime.py:155`, `src/tools/runtime.py:166`, and `src/tools/runtime.py:182`; `_fail(...)` assembles safe result, projection, decision event, and tuple return at `src/tools/runtime.py:266`. |
| 5 | Runtime auth uses a declarative ordered `RuntimeAuthGate` sequence without external contract-shape change. | VERIFIED | `RuntimeAuthGate` is defined at `src/tools/policy.py:104`; `_runtime_auth_gates` lists caller, permission, side-effect, resource scope, approval, safety snapshot, and idempotency gates at `src/tools/policy.py:244`; `runtime_auth(...)` iterates that sequence at `src/tools/policy.py:382` and `src/tools/policy.py:419`. |
| 6 | Contract-sensitive field sets were preserved during Phase 37. | VERIFIED | Phase 37-01 says no `ToolDescriptor`, `ToolResultV2`, `ToolCallContext`, `ToolPolicyDecision`, `ToolViewV1`, or `ToolInvocationOutcome` fields changed at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:85`; Phase 37-03 records empty `docs/contract-spec.md` / `src/tools/contracts.py` diff and contract-shape checks at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md:98`. |

**Score:** 6/6 observable truths source-backed; DB-backed pytest follow-up resolved by Phase 60 Plan 04.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `37-01-SUMMARY.md` | TPH-03 registry single-source implementation evidence. | VERIFIED | Provides declaration rows, derived identifier schema map, and catalog-derived investigate filtering at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:57`. |
| `37-02-SUMMARY.md` | Runtime `_fail(...)` consolidation evidence. | VERIFIED | Records seven runtime failure paths routed through `_fail(...)` at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-02-SUMMARY.md:59`. |
| `37-03-SUMMARY.md` | Declarative `RuntimeAuthGate` sequence evidence and final sweep. | VERIFIED | Records gate order, multi-denial regression, and final contract checks at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md:58`. |
| `37-VALIDATION.md` | Nyquist validation and DB-backed note disposition. | VERIFIED | It is complete and Nyquist-compliant; Phase 60 Plan 04 resolved the DB-backed pytest note with the current-equivalent archive command. |
| `37-REVIEW.md` | Code review evidence. | VERIFIED | Clean review with 0 findings at `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-REVIEW.md:15` and `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-REVIEW.md:32`. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/tools/catalog.py` | TPH-03 | `_TOOL_DECLARATIONS` -> `_descriptor(...)` -> derived `_IDENTIFIER_SCHEMAS` / `investigate_tool_names(...)`. | VERIFIED | `src/tools/catalog.py:326`, `src/tools/catalog.py:498`, `src/tools/catalog.py:526`. |
| `src/tools/runtime.py` | TPH-04 runtime helper | Failure branches -> `_fail(...)` -> projection and runtime-auth decision event. | VERIFIED | `src/tools/runtime.py:84`, `src/tools/runtime.py:266`, `src/tools/runtime.py:291`. |
| `src/tools/policy.py` | TPH-04 policy helper | `RuntimeAuthGate` declarations -> ordered gate iteration in `runtime_auth(...)`. | VERIFIED | `src/tools/policy.py:104`, `src/tools/policy.py:244`, `src/tools/policy.py:419`. |

## Behavioral Spot-Checks

| Behavior | Command Evidence | Result | Status |
|---|---|---|---|
| Current-equivalent Phase 37 catalog/platform/replay/architecture gate. | Resolved by Phase 60 Plan 04: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q`. | `108 passed, 1 warning in 30.42s`. | PASS |
| Historical non-DB focused evidence. | Existing validation evidence in summaries: 37-01 focused catalog/manager, 37-02 `_fail(...)`, and 37-03 `RuntimeAuthGate` checks. | Source summaries record focused passes before the historical DB fixture setup error, and Phase 60 Plan 04 now resolves the current-equivalent gate. | VERIFIED |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TPH-03 | Phase 37-01 | Single-source tool declarations and derived compatibility helpers. | VERIFIED | `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:39`, `src/tools/catalog.py:326`, `tests/tools/test_catalog.py:192`. |
| TPH-04 | Phase 37-02 / 37-03 | Shared runtime failure helper plus declarative runtime-auth gates. | VERIFIED | `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-02-SUMMARY.md:39`, `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md:40`, `tests/tools/test_tool_platform.py:646`, `tests/tools/test_tool_platform.py:751`, and Phase 60 Plan 04 DB-backed gate result `108 passed, 1 warning in 30.42s`. |

## Evidence Anchors

- `.planning/REQUIREMENTS.md:19` - TPH-03 requirement text.
- `.planning/REQUIREMENTS.md:23` - TPH-04 requirement text.
- `.planning/v2.1-MILESTONE-AUDIT.md:14` - Phase 37 missing formal verification gap for TPH-03.
- `.planning/v2.1-MILESTONE-AUDIT.md:15` - Phase 37 missing formal verification and DB-backed pytest note for TPH-04.
- `.planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:23` - D-05 assigns DB-backed pytest note resolution/carry-forward to Phase 60.
- `src/tools/catalog.py:326` - declaration table.
- `src/tools/catalog.py:498` - derived `_IDENTIFIER_SCHEMAS`.
- `src/tools/catalog.py:526` - catalog-derived investigate names.
- `src/tools/runtime.py:266` - shared `_fail(...)` helper.
- `src/tools/policy.py:244` - ordered `RuntimeAuthGate` declarations.
- `tests/tools/test_catalog.py:192` - registry drift guard.
- `tests/tools/test_tool_platform.py:646` - runtime auth gate sequence test.
- `tests/tools/test_tool_platform.py:751` - runtime failure helper structural test.

## Human Verification Required

None for this formal artifact. Phase 37 behavior is backend/tool-platform behavior with source, test, review, and summary evidence.

## Gaps Summary

None. Phase 37 / TPH-04 DB-backed pytest note is resolved by Phase 60 Plan 04 with the current-equivalent archive command.

## Final Status

`37-VERIFICATION.md` now closes the formal verification artifact gap for TPH-03 and TPH-04. The DB-backed pytest note is resolved by Phase 60 Plan 04 with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q` -> `108 passed, 1 warning in 30.42s`.
