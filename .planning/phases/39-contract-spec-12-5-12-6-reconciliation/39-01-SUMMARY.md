---
phase: 39-contract-spec-12-5-12-6-reconciliation
plan: 01
subsystem: contract-spec
tags: [docs, tool-platform, contract-spec, TPH-02]

requires:
  - phase: 38-output-schema-declaration-runtime-output-validation-enforcem
    provides: output_schema declaration and runtime enforcement final implementation state
provides:
  - docs-only reconciliation of contract-spec §8.0, §12.5, and §12.6 with implemented tool contract fields
  - validation evidence for TPH-02 field parity and protected identity-field preservation
  - Dual-AI review gate record with Claude independent review and Codex adjudication
affects: [docs/contract-spec.md, tool-platform-contracts, TPH-02]

tech-stack:
  added: []
  patterns: [docs-only contract reconciliation, structural rg validation, focused pytest validation]

key-files:
  created:
    - .planning/phases/39-contract-spec-12-5-12-6-reconciliation/39-01-SUMMARY.md
  modified:
    - docs/contract-spec.md

key-decisions:
  - "Preserved §8.0 as the owner of ToolCallContext identity/scope/permission semantics."
  - "Documented ToolCallContext.effective_at as str | None because the implemented Pydantic model uses str | None."
  - "Documented ToolDescriptor.description: str = \"\" because Phase 39 chose exact current model parity."

patterns-established:
  - "Spec-catches-up-to-code reconciliation: use implemented Pydantic/catalog fields as evidence, then patch the normative spec only."
  - "Dual-review adjudication: second-AI findings are accepted only after repository-backed verification."

requirements-completed: [TPH-02]

duration: 4 min
completed: 2026-07-02
---

# Phase 39 Plan 01: contract-spec §12.5/§12.6 Reconciliation Summary

**Docs-only reconciliation of MOCA tool platform contract fields for TPH-02, preserving §8.0 TrustedContext ownership.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-02T03:20:59Z
- **Completed:** 2026-07-02T03:24:59Z
- **Tasks:** 3/3 attempted and completed
- **Files modified:** 1 implementation file plus this summary

## Accomplishments

- Updated `docs/contract-spec.md` §8.0 projection note and §12.5 `ToolCallContext` to include `effective_at`, `approval_ref`, and `safety_snapshot_ref` as tool-call-local/action-safety fields.
- Updated §12.6 `ToolDescriptor` with `description`, `event_family` including `"action"` with `| None`, `executor`, `exposure`, and action-safety booleans.
- Updated §12.6 `ToolPolicyDecision` with `runtime_available` and `availability_summary`.
- Preserved the protected §8.0 identity/scope/permission fields: `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, and `trace_id`.

## Task Commits

1. **Task 1: Reconfirm pre-edit commit and implementation evidence** - no commit; evidence-only task.
2. **Task 2: Patch §8.0 note, §12.5, and §12.6** - `38afe8a` (`docs`)
3. **Task 3: Run structural validation, focused tests, and review gate record** - no source commit; validation/review evidence recorded here.

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `docs/contract-spec.md` - reconciled §8.0 projection note, §12.5 `ToolCallContext`, and §12.6 `ToolDescriptor` / `ToolPolicyDecision`.
- `.planning/phases/39-contract-spec-12-5-12-6-reconciliation/39-01-SUMMARY.md` - execution, validation, and review record.

## Validation

Pre-edit evidence:

- `git show --stat --oneline 4dcb673 -- docs/contract-spec.md` showed `docs/contract-spec.md | 5 ++++-`.
- `git show --unified=80 4dcb673 -- docs/contract-spec.md` showed only the `memory_write_events` hunk.
- The no-§12.5/§12.6 guard exited cleanly for `ToolCallContext|ToolDescriptor|ToolPolicyDecision|### 12.5|### 12.6`.
- Runtime field inventory confirmed the target implemented fields on `ToolCallContext`, `ToolDescriptor`, and `ToolPolicyDecision`.

Structural and diff checks:

- `rg -n "effective_at|approval_ref|safety_snapshot_ref" docs/contract-spec.md` passed.
- `rg -n "executor|exposure|requires_approval|requires_safety_snapshot|requires_idempotency_key" docs/contract-spec.md` passed.
- `rg -n "event_family: Literal\\[.*action|runtime_available|availability_summary" docs/contract-spec.md` passed.
- Worktree diff check after commit was clean for the scoped files; committed task diff `38afe8a` showed `docs/contract-spec.md` only, a docs-only diff.
- `git diff --check` passed.
- Protected-field guard over the docs diff found no changed type lines for the nine locked identity/scope/permission fields.

Tests:

- `uv run pytest tests/architecture/test_trusted_context_boundaries.py -q` -> `4 passed, 1 warning`.
- `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order -q` -> `8 passed, 1 warning`.
- `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` -> `72 passed, 1 warning`.

The warning in all pytest runs is the existing third-party LangGraph pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

## Dual-AI Review Gate

GSD-native / structural gate:

- `command -v gsd-plan-checker` returned no shell command in this Codex runtime.
- `gsd-sdk query agent-skills gsd-plan-checker` returned agent metadata, but there is no callable subagent interface exposed to this executor.
- The available GSD-native substitute was the plan's structural validation suite above; all required checks passed.

Independent cross-review:

- Ran `claude -p` with tools disabled against the committed `docs/contract-spec.md` diff.
- Claude Code version: `2.1.198`.
- Result: no blockers; two warnings.

Adjudication:

- **Warning 1:** `effective_at` is `str | None` rather than `datetime | None`.
  - **Decision:** not accepted as a defect. Repository evidence shows `src.tools.contracts.ToolCallContext.model_fields["effective_at"].annotation` is `str | None`; the plan explicitly required `effective_at: str | None = None`.
- **Warning 2:** `ToolDescriptor.description` defaults to an empty string.
  - **Decision:** not accepted as a Phase 39 defect. Repository evidence shows `src.tools.catalog.ToolDescriptor.model_fields["description"].default == ""`; exact current model parity was required by the plan. Current catalog descriptors also include existing empty descriptions, so adding a non-empty rule would exceed this docs-only reconciliation scope.

Outcome: Dual-AI review gate completed with no blocking issue. The only unavailable piece was a shell-callable `gsd-plan-checker`; this is recorded explicitly and not represented as having run.

## Deviations from Plan

None - plan executed exactly as written for the docs patch. Review tooling availability was recorded under `Dual-AI Review Gate` rather than fabricated.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep; production and test files were untouched.

## Issues Encountered

- `gsd-plan-checker` was not available as a shell command in this runtime. This did not block completion because the plan accepted GSD-native plan/checker or structural validation evidence, and an independent Claude review was obtained.
- `.planning/LOCAL-VALIDATION-ISSUES.md` was dirty before Phase 39 execution and was not staged or committed. No new local validation/tooling failure required appending a new entry during this plan.

## Known Stubs

None. The `description: str = ""` text added to the spec is an intentional implemented model default, not a placeholder UI/data stub.

## Threat Flags

None. The only implementation diff is documentation; no new endpoint, auth path, file access path, or trust-boundary code surface was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

TPH-02 is covered by the spec patch, docs-only validation evidence, and review/adjudication record. Phase 39 is ready for metadata tracking and milestone-level closure.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/39-contract-spec-12-5-12-6-reconciliation/39-01-SUMMARY.md`.
- Task commit `38afe8a` exists in git history.
- Required summary markers are present: `Dual-AI Review Gate`, `4dcb673`, `docs-only diff`, and `TPH-02`.
- Summary entrypoint scan found no invalid MOCA pytest command wording.
- Scoped worktree diff for production/test files is clean after the task commit.

---
*Phase: 39-contract-spec-12-5-12-6-reconciliation*
*Completed: 2026-07-02*
