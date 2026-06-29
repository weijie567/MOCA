# Phase 35: Replay and Eval Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 35-replay-and-eval-hardening
**Areas discussed:** Replay coverage model, Trace and replay visibility, Eval gate placement, Golden and negative datasets

---

## Replay Coverage Model

| Option | Description | Selected |
|--------|-------------|----------|
| Coverage matrix + blocking tests | Build deterministic acceptance coverage for platform boundaries, replay events, trace projections, eval gates, and forbidden behavior. | yes |
| Patch only key gaps | Fix only visible missing replay/trace/eval gaps. | |
| Audit view first | Prioritize `/replay` and trace readability over blocking contract coverage. | |

**User's choice:** Coverage matrix + blocking tests.

**Notes:** The user emphasized that this is the Phase 35 deterministic acceptance layer, not a rebuild of platform infrastructure. The matrix must cover existing platform boundary decision events, ordering, redaction, terminal timelines, permission isolation, and forbidden behavior. Real execution, envelope rebuilds, and raw payload persistence remain out of scope.

---

## Trace and Replay Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Continue owner/admin-only | Keep trace/replay access unchanged and only test current isolation. | |
| Restore manager same-merchant | Open manager same-merchant access when target merchant proof exists. | |
| Add proof fields but keep permissions closed | Build the proof chain for future same-merchant access while keeping Phase 35 API access owner/admin-only. | yes |

**User's choice:** Add proof fields but keep permissions closed.

**Notes:** The user wants Phase 35 to add target merchant / scoped business fact proof fields and fail-closed tests before opening manager same-merchant trace/replay access. `requested_by.user.merchant_id` must not be used as an authorization shortcut.

---

## Eval Gate Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Dev-contract blocking, release/monitoring as artifacts | Block on deterministic contract gates; produce release and monitoring manifests without blocking on sample insufficiency. | yes |
| Dev-contract and release both blocking | Block on deterministic contract tests plus statistical release thresholds. | |
| All local gates non-blocking | Generate reports only, with no local hard gate. | |

**User's choice:** Dev-contract blocking, release/monitoring as artifacts.

**Notes:** The user defined Phase 35's hard line as deterministic `dev-contract` coverage: schema, platform event coverage, event order, terminal timelines, redaction, permissions, forbidden behavior, and manifest format. Release and monitoring gates must be produced as artifacts with status and gaps but not block because of sample size or missing production data.

---

## Golden and Negative Datasets

| Option | Description | Selected |
|--------|-------------|----------|
| Replay terminal + forbidden behavior first | Prioritize terminal replay timelines and deterministic negative cases for the dev-contract gate. | yes |
| Balanced expansion across all domains | Add a few cases across intent, memory, tool, RAG, claim, approval/action, and replay. | |
| Release dataset first | Expand statistical release datasets for intent/RAG/action safety first. | |

**User's choice:** Replay terminal + forbidden behavior first.

**Notes:** P0 golden cases should cover normal, interrupted, resumed, rejected, responded, expired, error, and cancelled replay timelines. P0 negatives should cover raw prompt/tool/PII/action payload leakage, owner/admin-only access, cross-tenant/cross-merchant denial, invalid same-merchant proof approximations, unsupported claim/action path, no-evidence/action path, stale/wrong-scope business refs, invalid-scope evidence, and approval payload hash mismatch.

---

## the agent's Discretion

- Exact file names for the matrix, reports, and manifests are left to planning.
- Exact event additions are left to planning if they use replay-owned registries and redaction rules.
- Exact focused test split is left to planning, but tests must use MOCA's valid `uv run pytest ...` or `.venv/bin/pytest ...` entrypoint.

## Deferred Ideas

- Broader statistical release dataset expansion for intent hard negatives, RAG claim support, and approval/action safety.
- Future manager same-merchant trace/replay visibility once proof chain is stable.
