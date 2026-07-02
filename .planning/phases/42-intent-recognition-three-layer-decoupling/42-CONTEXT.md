# Phase 42 Context: Intent Recognition Three-Layer Decoupling (retroactive registration)

## What this phase is

Phase 42 formally registers the **intent-recognition three-layer decoupling** that was
designed by Claude, implemented by Codex, and verified — but landed *before* it was
recorded as a GSD phase. This CONTEXT exists to keep the planning record honest about how
the work actually happened.

**This is a retroactive registration, not a plan-then-execute phase.** There is deliberately
no `42-01-PLAN.md` / `42-PLAN-REVIEW.md`: the code was already complete and green when this
phase directory was created, so a "plan" written now would be fiction. The authority artifacts
for this phase are `42-01-SUMMARY.md` (what was done) and `42-VERIFICATION.md` (evidence it is
correct), anchored to a real commit.

## Why it lives in v2.1

v2.1 was rescoped on 2026-07-02 from "Tool Platform Hardening" to **Core Subsystem Hardening**
— a long-lived umbrella for clearing architecture debt across the four core subsystems tracked
in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory). Tool
platform (Phase 37-41) was the first subsystem cleared; intent recognition is the second.
See the "Rescope note" and standing rule in `.planning/STATE.md`.

## Design authority

- Design spec (Claude-authored, Codex-executed): `.planning/intent-layering-codex-brief.md`.
- Architecture-debt ledger entries this phase resolves/updates: `.planning/ARCHITECTURE-DEBT.md`
  §2 ID-01 (✅), ID-03 (✅), ID-DESIGN (🟡 partially landed), ID-02 (🔴 interface placeholder only).

## What the decoupling did (one-paragraph orientation; detail in SUMMARY)

Split the intent pipeline's three tangled responsibilities into three explicit, single-direction,
independently-testable contracts:
- **[1] semantic layer** `SemanticIntent` — "what does the user want" (effective intent/operation +
  entities + raw confidence + keyword signals + arbitration record). Keyword scanning
  (`derive_keyword_signals`) is split from winner selection (`arbitrate_intent`); this is the ID-01 fix.
- **[2] risk/authorization layer** `RiskDecision` — "what is allowed given identity/channel", resolved
  from a declarative `RISK_POLICY_TABLE` instead of an if-elif chain; this is the ID-03 fix.
- **[3] confidence/clarification layer** `ClarificationDecision` — "confident enough, or ask?" with a
  `calibrated_confidence` parameter slot reserved but not implemented (ID-02 stays open).

## Scope boundary (what this phase did NOT do)

- No multi-intent / TaskPlan / DAG / plan executor (that is the next phase, multi-intent tier A).
- No change to `IntentResultV3` wire schema, `src/agent/prompts.py` few-shot, or `docs/contract-spec.md`.
- No real confidence calibration (ID-02 remains 🔴, interface placeholder only).
- One deliberate behavior change, logged in the brief's exemption list: the keyword "投诉" in a
  negated/quoted query no longer overrides a high-confidence LLM classification.

## Verification posture

Because this is retroactive, verification was re-run live at registration time rather than trusted
from the ledger's earlier record. See `42-VERIFICATION.md` for the commit anchor and the exact
`uv run pytest` / `ruff` results captured on 2026-07-02.
