---
phase: 36-merchant-scope-db-hardening-role-cleanup
plan: 36-02
subsystem: auth-database
tags: [auth, sqlalchemy, tenant-scope, username, merchant-binding]

requires:
  - phase: 29.5-merchant-scope-role-model-alignment
    provides: merchant-bound support/manager/legacy-merchant role semantics
  - phase: 34-approval-and-actiondraft-boundary-hardening
    provides: target merchant binding and safety snapshot boundary contracts
provides:
  - Tenant-aware JSON login and demo-token request contracts with optional tenant_id.
  - Shared fail-closed username resolver for login, OAuth2 token, and demo-token auth paths.
  - ORM metadata for tenant-scoped username uniqueness.
  - ORM metadata for tenant-consistent nullable user merchant binding.
affects: [auth, database, alembic-migrations, phase-36-05]

tech-stack:
  added: []
  patterns:
    - Optional trusted tenant selector on JSON auth requests.
    - Username-only transitional auth fails closed when resolution is ambiguous.
    - SQLAlchemy table-level composite FK for tenant-consistent nullable merchant binding.

key-files:
  created:
    - .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-02-SUMMARY.md
  modified:
    - src/api/schemas/auth.py
    - src/api/routers/auth.py
    - src/db/models.py
    - tests/integration/test_auth.py
    - tests/approvals/test_migration_contract.py

key-decisions:
  - "JSON /login and /demo-token accept optional tenant_id; OAuth2 /token remains username-only and fails closed on ambiguous usernames."
  - "User.username is no longer globally unique in ORM metadata; tenant-scoped uniqueness is expressed by uq_users_tenant_username."
  - "User.merchant_id remains nullable but participates in fk_users_merchant_tenant with users.tenant_id."

patterns-established:
  - "Auth username resolution uses a shared helper instead of route-local username-only scalar lookup."
  - "Phase 36 ORM metadata changes are covered by static migration-contract tests before Alembic migration work in 36-05."

requirements-completed: [MSH-02, MSH-03, MSH-07]

duration: 24 min
completed: 2026-06-30
---

# Phase 36 Plan 02: Tenant-Aware Username Identity and Auth Resolution Contract Summary

**Tenant-qualified auth resolution with fail-closed ambiguous username handling and tenant-consistent user merchant ORM metadata.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-06-30T06:36:43Z
- **Completed:** 2026-06-30T07:00:36Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added optional `tenant_id` to JSON login and demo-token request schemas.
- Added `_resolve_user_for_login` and routed `/login`, `/token`, and `/demo-token` through it.
- Replaced global `User.username` ORM uniqueness with `uq_users_tenant_username`.
- Added `uq_merchants_id_tenant` and `fk_users_merchant_tenant` while keeping `User.merchant_id` nullable.
- Added integration and migration-contract tests for same-tenant duplicate rejection, cross-tenant duplicate login, ambiguous username fail-closed behavior, and cross-tenant user merchant mismatch rejection.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: tenant-aware auth tests** - `d716507` (test)
2. **Task 1 GREEN: tenant-aware auth resolver** - `dd7127d` (feat)
3. **Task 2 RED: tenant-scoped username metadata tests** - `27f22c4` (test)
4. **Task 2 GREEN: tenant-scoped user identity metadata** - `750908e` (feat)

## Files Created/Modified

- `src/api/schemas/auth.py` - Added optional `tenant_id` to `LoginRequest` and `DemoTokenRequest`.
- `src/api/routers/auth.py` - Added shared tenant-aware username resolver and removed route-local username-only scalar lookups.
- `src/db/models.py` - Added tenant-scoped username uniqueness plus composite user merchant tenant FK metadata.
- `tests/integration/test_auth.py` - Added tenant selector, ambiguity, duplicate username, and merchant tenant mismatch auth coverage.
- `tests/approvals/test_migration_contract.py` - Added ORM metadata assertions for Phase 36 username and merchant-binding constraints.
- `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-02-SUMMARY.md` - Plan outcome record.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py -q --tb=short` -> 16 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/approvals/test_migration_contract.py -q --tb=short` -> 29 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/db/models.py src/api/schemas/auth.py src/api/routers/auth.py tests/integration/test_auth.py tests/approvals/test_migration_contract.py` -> passed.
- Required `rg` acceptance checks passed; forbidden username-only scalar lookup and old `merchant_id` column-level FK patterns returned no matches.

## Decisions Made

- Kept OAuth2 form `/token` username-only because `OAuth2PasswordRequestForm` has no tenant field; it now fails closed if username-only lookup finds multiple principals.
- Preserved demo-token compatibility for unique usernames while allowing explicit tenant-qualified demo-token requests.
- Kept `User.merchant_id` nullable for admins and invalid legacy rows, with tenant consistency enforced when a merchant binding exists.
- Scoped live Alembic migration work to Plan 36-05; this plan updates ORM contract metadata and tests only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Corrected composite FK metadata assertion**
- **Found during:** Task 2 GREEN
- **Issue:** The RED contract test asserted `users.merchant_id.foreign_keys` was empty, but SQLAlchemy exposes table-level composite FK elements through the participating column.
- **Fix:** Changed the assertion to require exactly one named `fk_users_merchant_tenant` constraint involving `merchant_id`.
- **Files modified:** `tests/approvals/test_migration_contract.py`
- **Verification:** Focused pytest and Ruff both passed.
- **Committed in:** `750908e`

---

**Total deviations:** 1 auto-fixed test bug.
**Impact on plan:** No scope change. The corrected assertion more accurately verifies the planned table-level composite FK contract.

## Issues Encountered

- Initial `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` in this fresh worktree resolved to a global Python 3.9 `pytest` script because the local venv had not installed the project `dev` extra. This produced an invalid `datetime.UTC` collection failure. I fixed the environment with `UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev`; subsequent `uv run pytest` used local Python 3.12 / pytest 9.0.3 and reached valid test results. `.planning/LOCAL-VALIDATION-ISSUES.md` was not touched per orchestrator instruction.

## Known Stubs

None. Stub scan found no plan-introduced placeholder UI/data flow stubs. Matches were existing empty test collections or pre-existing model defaults, not new incomplete behavior.

## User Setup Required

None - no external service configuration required.

## TDD Gate Compliance

- RED commit exists before GREEN for Task 1: `d716507` -> `dd7127d`.
- RED commit exists before GREEN for Task 2: `27f22c4` -> `750908e`.

## Next Phase Readiness

Ready for Plan 36-03. AgentRun target merchant scope can now rely on an explicit tenant-qualified principal path. Plan 36-05 still owns the Alembic migration that applies these ORM metadata constraints to live databases.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-02-SUMMARY.md`.
- Task commits exist: `d716507`, `dd7127d`, `27f22c4`, `750908e`.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/LOCAL-VALIDATION-ISSUES.md` were not modified.

---
*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Completed: 2026-06-30*
