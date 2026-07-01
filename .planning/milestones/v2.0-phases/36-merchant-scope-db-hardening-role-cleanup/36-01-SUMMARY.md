---
phase: 36-merchant-scope-db-hardening-role-cleanup
plan: 36-01
subsystem: auth
tags: [merchant-scope, roles, trusted-context, authorization, pytest, ruff]

requires:
  - phase: 29.5-merchant-scope-role-model-alignment
    provides: v1.9 runtime merchant-bound role semantics
provides:
  - Canonical runtime role scope constants and deprecated legacy merchant marker
  - Active business-user merchant binding helper with fail-closed scope tests
  - Route-helper and static wildcard regressions for merchant-bound roles
affects: [phase-36, trace-replay-readiness, merchant-scope, auth]

tech-stack:
  added: []
  patterns:
    - Canonical role constants live in src.platform.trusted_context
    - Auth route helper imports shared role constants instead of duplicating literals
    - Legacy merchant remains deprecated compatibility, support-equivalent, and non-wildcard

key-files:
  created:
    - .planning/phases/36-merchant-scope-db-hardening-role-cleanup/36-01-SUMMARY.md
  modified:
    - docs/contract-spec.md
    - scripts/seed_demo.py
    - src/auth/permissions.py
    - src/platform/trusted_context.py
    - tests/platform/test_merchant_scope.py
    - tests/tools/test_merchant_scope_static.py

key-decisions:
  - "Kept users.role as the compatibility/runtime authority; no roles/user_roles authority model was introduced."
  - "Preserved legacy merchant as deprecated merchant-bound compatibility instead of deleting it."
  - "Kept wildcard business merchant scope constructed only in TrustedContextFactory admin semantics."

patterns-established:
  - "Role registry: MERCHANT_BOUND_ROLES, PLATFORM_ADMIN_ROLES, DEPRECATED_COMPATIBILITY_ROLES, and ROLE_SCOPE_POLICY are centralized in trusted_context."
  - "Active binding invariant: requires_business_merchant_binding(role, is_active=True) identifies active merchant-bound business users that require merchant_id."
  - "Wildcard static guard: production wildcard merchant scope remains disallowed outside trusted_context.py."

requirements-completed: [MSH-01, MSH-02, MSH-07]

duration: 15min
completed: 2026-06-30
---

# Phase 36 Plan 36-01: Merchant Scope Role Semantics Summary

**Canonical merchant-bound role policy with deprecated legacy merchant compatibility and fail-closed active business-user binding tests**

## Performance

- **Duration:** 15min
- **Started:** 2026-06-30T06:37:04Z
- **Completed:** 2026-06-30T06:51:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Centralized merchant-bound/admin/deprecated role semantics in `src/platform/trusted_context.py`.
- Updated `require_merchant_access` to import the canonical runtime constants while preserving deny-first behavior.
- Marked legacy `merchant` in the contract and demo seed data as deprecated compatibility, support-equivalent, and not recommended for new examples.
- Added focused role matrix, missing-binding, non-admin wildcard override, and production wildcard static regressions.

## Task Commits

1. **Task 1 RED: Centralize role semantics tests** - `2b1df41` (test)
2. **Task 1 GREEN: Centralize role scope policy** - `32ee63d` (feat)
3. **Task 2 RED: Active binding fail-closed tests** - `b2766d2` (test)
4. **Task 2 GREEN: Active binding helper** - `511a489` (feat)

## Files Created/Modified

- `docs/contract-spec.md` - Records the Phase 36 implementation target for legacy `merchant` deprecation and non-wildcard semantics.
- `scripts/seed_demo.py` - Describes `merchant` as deprecated compatibility and keeps one bound legacy merchant demo user.
- `src/auth/permissions.py` - Imports `MERCHANT_BOUND_ROLES` and `PLATFORM_ADMIN_ROLES` from `trusted_context`.
- `src/platform/trusted_context.py` - Adds deprecated compatibility constants, role policy mapping, and active binding helper.
- `tests/platform/test_merchant_scope.py` - Covers role policy, admin-only wildcard, deny-all missing bindings, route-level 403s, and manager non-tenant-wide behavior.
- `tests/tools/test_merchant_scope_static.py` - Expands static wildcard coverage over Phase 36 high-risk production surfaces.

## Decisions Made

- Kept `users.role` as the runtime compatibility source per D-06; no new role authority table/model was added.
- Preserved `merchant` role compatibility with support-equivalent merchant-bound access rather than removing legacy users or the role row.
- Treated the initial invalid pytest environment resolution as a local command-entry issue; after priming the repo dev extra, the exact plan commands resolved to the worktree venv and passed.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` - PASS, 35 passed, 1 third-party warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/platform/trusted_context.py src/auth/permissions.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py` - PASS.
- Positive acceptance greps for deprecated role policy, seed/contract language, active binding helper, missing `merchant_id`, `server_merchant_scope`, manager not tenant-wide, and wildcard coverage - PASS.
- Negative acceptance greps for duplicated constants in `permissions.py`, new role-authority implementation, and wildcard construction outside `trusted_context.py` - PASS.
- Protected orchestrator artifacts `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/LOCAL-VALIDATION-ISSUES.md` - unchanged.

## TDD Gate Compliance

- RED gate present for Task 1: `2b1df41`.
- GREEN gate present for Task 1: `32ee63d`.
- RED gate present for Task 2: `b2766d2`.
- GREEN gate present for Task 2: `511a489`.
- Refactor gate was not needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial `uv run pytest` resolved to user-level Python 3.9 pytest because the worktree venv had not installed the repo `dev` extra. This produced an invalid `datetime.UTC` import failure. I primed the worktree environment with `uv run --extra dev pytest ...`, then reran the exact plan commands successfully from the repo venv.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Stub-pattern scan hits were legitimate deny-all scope assertions, test empty lists, type hints, or pre-existing contract examples, not placeholder implementation.

## Next Phase Readiness

Plan 36-02 can rely on a single runtime source for role scope constants and focused tests proving legacy `merchant` is deprecated merchant-bound compatibility, active merchant-bound users without binding fail closed, and wildcard business scope remains admin-only.

## Self-Check: PASSED

- Summary file exists.
- Task commits found: `2b1df41`, `32ee63d`, `b2766d2`, `511a489`.
- Protected orchestrator artifacts remain unchanged.

---
*Phase: 36-merchant-scope-db-hardening-role-cleanup*
*Completed: 2026-06-30*
