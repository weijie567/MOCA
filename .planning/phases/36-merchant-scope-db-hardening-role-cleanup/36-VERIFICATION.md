---
phase: 36-merchant-scope-db-hardening-role-cleanup
status: passed
verified: 2026-06-30T13:27:00Z
requirements:
  - MSH-01
  - MSH-02
  - MSH-03
  - MSH-04
  - MSH-05
  - MSH-06
  - MSH-07
  - MSH-08
must_haves_verified: 8
gaps_found: 0
human_verification_required: 0
security_review_required: true
---

# Phase 36 Verification

## Verdict

Phase 36 passes goal-backward verification. The implemented code, migrations, tests, readiness artifact, validation evidence, and post-code-review fixes satisfy the phase goal: merchant-bound role semantics are hardened at database, migration, and authorization-readiness boundaries without widening run/status/evidence/trace/replay visibility.

No functional verification gaps remain.

Security enforcement is enabled by workflow default and no `36-SECURITY.md` artifact exists yet. Run `$gsd-secure-phase 36` before advancing if this milestone requires the security gate to be closed.

## Requirement Verification

| Requirement | Status | Evidence |
|-------------|--------|----------|
| MSH-01 | PASSED | `src/platform/trusted_context.py` defines `DEPRECATED_COMPATIBILITY_ROLES`, `ROLE_SCOPE_POLICY`, merchant-bound role constants, and admin-only wildcard behavior. `src/auth/permissions.py` imports the canonical constants. `tests/platform/test_merchant_scope.py` covers support/manager/legacy merchant as merchant-bound and admin as the only wildcard human role. |
| MSH-02 | PASSED | Active business-user missing binding fails closed in runtime role tests, migration preflight, and business fact service tests. `src/db/models.py` declares user/merchant tenant consistency metadata and `ck_users_active_business_role_has_merchant`; migration 019 preflights invalid active business users. |
| MSH-03 | PASSED | `src/api/schemas/auth.py` adds optional `tenant_id`; `src/api/routers/auth.py::_resolve_user_for_login` resolves `(tenant_id, username)` when provided and rejects ambiguous username-only resolution. `tests/integration/test_auth.py` covers tenant selectors and duplicate username ambiguity. |
| MSH-04 | PASSED | `src/agent/run_scope.py` defines the four scope classifications and fail-closed classification rules. `src/db/models.py` persists `AgentRun.target_merchant_id`, `target_merchant_ref`, and `scope_classification` with `ck_agent_runs_scope_target_consistency`. `src/agent/trace.py` persists classifier results. |
| MSH-05 | PASSED | Approval, action draft, and action safety snapshot rows carry target merchant binding material. `src/approvals/service.py`, `src/actions/service.py`, `src/approvals/snapshots.py`, and `src/approvals/snapshot_service.py` reject run/approval/action/snapshot contradictions. Code-review fixes also cover auto-allowed draft timing and risk-decision binding. |
| MSH-06 | PASSED | `src/db/migrations/versions/019_phase36_merchant_scope_hardening.py` includes explicit preflight helpers for active business-user binding, same-tenant username duplicates, AgentRun scope safety, authorization-root consistency, and forbidden weak-source backfills. Tests assert owner/requested_by/thread/prompt/memory/RAG/LLM/raw payload are not used as scope backfill authority. |
| MSH-07 | PASSED | Focused no-regression tests cover merchant-bound business facts, tenant public policy separation, memory contextual-only limits, RAG/claim boundaries, approval API boundaries, owner/admin-only trace/replay, and no-widening static checks. Phase 36 did not implement same-merchant manager visibility. |
| MSH-08 | PASSED | `src/replay/phase36_readiness.py`, `eval/replay/phase36-readiness.v1.json`, and `tests/replay/test_phase36_readiness.py` validate the strict readiness artifact. Current result is `ready_with_agent_run_binding`; weak facts remain explicitly untrusted. |

## Plan Verification

| Plan | Status | Verification |
|------|--------|--------------|
| 36-01 | PASSED | Role semantics and deprecated legacy `merchant` compatibility are centralized and tested. |
| 36-02 | PASSED | Tenant-aware username resolution and DB tenant consistency metadata are implemented and tested. |
| 36-03 | PASSED | AgentRun target merchant scope model, persistence, projection, and owner/admin-only visibility preservation are implemented and tested. |
| 36-04 | PASSED | Approval/action/snapshot target merchant consistency checks are implemented and tested, including post-review auto-allowed hardening. |
| 36-05 | PASSED | Migration 019, preflight checks, ORM alignment, and downgrade/round-trip coverage are implemented and tested. |
| 36-06 | PASSED | Readiness artifact, no-widening regression checks, final focused/full-suite evidence, and code-review remediation are complete. |

## Verification Evidence

- `gsd-sdk query phase-plan-index 36` -> all six plans have summaries; `incomplete: []`.
- `gsd-sdk query verify.schema-drift 36` -> `valid: true`, `issues: []`, `checked: 6`.
- Phase 36 focused gate: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` -> 287 passed, 3 warnings.
- Full suite: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` -> 2125 passed, 4 skipped, 44 warnings.
- Ruff: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> All checks passed.
- Post-code-review gates recorded in `36-REVIEW.md` and `36-VALIDATION.md`: 49 passed, 112 passed, 175 passed, final focused gate rerun 287 passed.
- No-RLS scan recorded in `36-VALIDATION.md`: `rg -n "ROW LEVEL SECURITY|CREATE POLICY|ENABLE ROW LEVEL SECURITY|SET LOCAL|current_setting" src/db src/api src/auth src/platform src/agent src/replay` -> no matches.

## No-Widening Check

Verified no Phase 36 implementation widened run/status/evidence/trace/replay authorization. `tests/replay/test_phase35_trace_replay_permissions.py` keeps `ADMIN_RUN_VISIBILITY_ROLES == {"admin"}` and statically checks that `target_merchant_id`, `scope_classification`, `target_merchant_context`, `phase36_readiness`, and `project_replay_authorization_proof` are not used as authorization guards in Phase 36 route code.

`eval/replay/phase36-readiness.v1.json` explicitly marks owner identity, requested_by, thread id, prompt text, memory, RAG, LLM output, raw tool payload, `target_merchant_context`, and `replay_authorization_proof` as non-authorizing facts.

## Review Closure

The code-review gate initially found three true warnings. They are resolved in commit `c138459`:

- Real business reads now include authorized `merchant_id` in strict adapter projections.
- Auto-allowed action draft creation can promote an empty `unknown_legacy` run to `business_merchant` only after validated snapshot and auto-allowed binding proof.
- Auto-allowed draft creation validates submitted `risk_decision` payload semantics before persistence.

`36-REVIEW.md` status is `clean`.

## Remaining Follow-Up

- Run `$gsd-secure-phase 36` before advancing if the project requires security-gate closure for this phase. No `36-SECURITY.md` exists at verification time.
- Phase 37 may use persisted AgentRun target merchant binding as the primary authorization fact for planned same-merchant read-only visibility, but Phase 36 does not implement that visibility.
