# Deferred: AgentRun, trace, and replay merchant scope

Origin: Phase 29.5 Merchant Scope / Role Model Alignment

Target phases: Phase 32 Intent Graph Migration and Phase 35 Replay and Eval Hardening

## Reason

Phase 29.5 should not force final manager-scoped run listing before runs, business refs, memory, and replay artifacts have reliable target merchant binding. However, Phase 29.5 must add an interim guard: `manager` must not remain a tenant-wide supervisor for business-data run/evidence/trace visibility. Current `SUPERVISOR_ROLES` includes `manager`, which is incompatible with the target model unless scoped by merchant or target business refs.

Current graph code may construct fallback visibility context outside `TrustedContextFactory`. Phase 29.5 must remove or fail-close any business-data fallback that fabricates `merchant_scope={"merchant_ids":["*"]}`; later phases may restore explicit system-owned wildcard only through a separate trusted system context contract.

## Required outcome

- AgentRun creation or derived context records target merchant where business data is involved, or explicitly marks runs as policy-only / merchant-not-required.
- Phase 29.5 interim guard: business-data AgentRun status/evidence/trace access is owner/admin-only until target merchant binding exists.
- Phase 29.5 removes tenant-wide visibility from ghost supervisor roles such as `supervisor` and `approval_manager`; unknown role deny-all applies until a role is explicitly classified.
- Phase 29.5 removes or blocks graph/tool/checkpoint fallback paths that create wildcard business merchant scope outside `TrustedContextFactory`.
- Later phases restore manager same-merchant run listing and trace access only after target merchant or scoped `BusinessFactRefV1` evidence is available.
- Trace and replay views preserve merchant scope and do not leak tool results, business refs, approval state, or memory across merchants.
- Decision events record enough scope metadata/reason codes to audit allow/deny decisions.

## Verification entry

- Phase 29.5 regression or static guard that no business-data path outside `TrustedContextFactory` fabricates `merchant_ids=["*"]`.
- Tests for manager A unable to list/view merchant B business runs or traces.
- Tests for manager unable to view non-owner business run/evidence/trace before target merchant binding exists.
- Tests for admin cross-merchant trace access.
- Replay/eval gates that catch cross-merchant leakage through AgentRun, trace detail, tool result records, and replay artifacts.
