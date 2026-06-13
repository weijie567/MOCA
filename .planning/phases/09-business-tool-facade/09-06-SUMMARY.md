---
phase: 09-business-tool-facade
plan: 06
subsystem: auth-permissions
tags: [jwt-scopes, token-intersection, trusted-context, confused-deputy, no-widening]

requires:
  - phase: 09-05
    provides: Live read-switch and router trusted config projection
provides:
  - Verified JWT scopes preserved in trusted request context
  - Token/role scope intersection before tool-permission mapping
  - API-level no-widening regression tests
affects: [agent-run-streaming, permission-model]

tech-stack:
  added: []
  patterns:
    - Verified token scopes as frozenset on request.state.verified_token_scopes
    - Token/role intersection: set(token_scopes) & set(ROLE_SCOPES[user.role])

key-files:
  modified:
    - src/auth/permissions.py
    - src/api/routers/agent_runs.py
    - tests/integration/test_auth.py
    - tests/test_agent_runs_api.py
    - tests/agent/test_nodes/test_load_business_context.py

key-decisions:
  - "Verified token scopes are preserved as immutable frozenset on request.state after all auth checks pass."
  - "Tool permissions derive from the exact intersection of verified token scopes and current DB role scopes."
  - "Fail closed: if verified_token_scopes is absent from request.state, permissions default to empty."

patterns-established:
  - "get_current_user preserves verified JWT scopes in request.state.verified_token_scopes without mutating User ORM."
  - "_trusted_tool_config computes set(token_scopes) & set(ROLE_SCOPES[user.role]) before SCOPE_TO_TOOL_PERMISSION mapping."

requirements-completed: [TOOL-01, TOOL-02]

duration: ~8 min
completed: 2026-06-13
---

# Phase 09 Plan 06: Verified-Token Confused-Deputy Gap Closure Summary

**JWT scope least-privilege now survives authentication and intersects with DB role scopes before tool permissions are granted**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-13T00:04:00Z
- **Completed:** 2026-06-13T00:12:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `request: Request` parameter to `get_current_user` and assigned `frozenset(token_scopes)` to `request.state.verified_token_scopes` after all authentication and scope checks pass.
- Validated JWT `scopes` claim as a collection of strings before preservation; malformed claims fail authentication.
- Changed `_trusted_tool_config` to accept explicit `token_scopes` and compute `set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))` before mapping through `SCOPE_TO_TOOL_PERMISSION`.
- Updated `stream_agent_run_events` to read `verified_token_scopes` from `request.state`, failing closed with empty list if absent.
- Added integration tests proving a valid `agent:chat`-only token preserves exactly `{"agent:chat"}` and rejected tokens do not populate trusted scopes.
- Added API-level tests proving `agent:chat`-only support token gets `permissions=[]` and `agent:chat+orders:read` gets exactly `["tool:get_order"]`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Preserve verified JWT scopes in trusted request context** - `44a2ebe` (feat)
2. **Task 2: Intersect verified token scopes with current role scopes for live tool config** - `af574e5` (feat)

## Files Created/Modified

- `src/auth/permissions.py` - Added Request parameter, JWT scopes validation, frozenset preservation on request.state.
- `src/api/routers/agent_runs.py` - Changed `_trusted_tool_config` to accept token_scopes and compute intersection; updated `stream_agent_run_events` to read from request.state.
- `tests/integration/test_auth.py` - Added scope preservation and rejection safety tests.
- `tests/test_agent_runs_api.py` - Added no-widening and positive intersection tests for `_trusted_tool_config`.
- `tests/agent/test_nodes/test_load_business_context.py` - Updated existing `_trusted_tool_config` callers to pass token_scopes.

## Decisions Made

- Used `frozenset` for verified token scopes to enforce immutability after authentication.
- Fail closed: if `verified_token_scopes` is absent from request.state (e.g., future endpoints that bypass `get_current_user`), permissions default to empty list.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing tests calling _trusted_tool_config with old signature**
- **Found during:** Task 2 verification
- **Issue:** `tests/agent/test_nodes/test_load_business_context.py` had 2 tests calling `_trusted_tool_config(user, trace_id)` without `token_scopes`
- **Fix:** Updated callers to pass `ROLE_SCOPES.get(user.role, [])` as token_scopes
- **Files modified:** `tests/agent/test_nodes/test_load_business_context.py`
- **Commit:** af574e5

## Known Stubs

None. All data flows are complete.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-09-06-01 mitigated | `src/auth/permissions.py` | Verified scopes preserved only after all auth checks; rejected tokens never populate trusted context |
| T-09-06-02 mitigated | `src/api/routers/agent_runs.py` | Token/role intersection prevents both token-only and role-only privilege widening |
| T-09-06-03 mitigated | `src/auth/permissions.py` | Malformed scopes claim (non-list, non-string elements) fails authentication |

## Self-Check: PASSED

- Confirmed `src/auth/permissions.py` contains `Request`, `verified_token_scopes`, and `frozenset`.
- Confirmed no `setattr(user` or `user.*scopes` patterns in permissions.py.
- Confirmed `src/api/routers/agent_runs.py` contains `token_scopes`, `ROLE_SCOPES`, `SCOPE_TO_TOOL_PERMISSION` intersection.
- Confirmed no `trusted_scopes = ROLE_SCOPES` direct assignment.
- Confirmed `tests/integration/test_auth.py` contains `agent:chat.*verified_token_scopes` assertion.
- Confirmed `tests/test_agent_runs_api.py` contains `permissions.*== []` and `tool:get_order` assertions.
- Confirmed task commits `44a2ebe` and `af574e5` exist.
- Confirmed full Phase 9 regression passes (88 passed, 9 warnings).

---
*Phase: 09-business-tool-facade*
*Completed: 2026-06-13*
