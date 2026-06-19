# Phase 22: RAG Context Builder + Hallucination Control - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `22-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 22-rag-context-builder-hallucination-control
**Areas discussed:** ContextBuilder boundary and outputs, MaterialClaim and authority binding, verifier levels and deterministic routing, acceptance gate and metrics

---

## Workflow Note

The GSD workflow attempted to use `request_user_input`, but the tool was unavailable in Codex Default mode. Per the skill fallback, all recommended gray areas were selected and the recommended defaults were recorded in `22-CONTEXT.md`.

---

## ContextBuilder Boundary And Outputs

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated RAG reasoning kernel | Extract evidence re-fetch, validation, citation map, risk labels, exclusion trace, and verifier projections into a dedicated ContextBuilder/ReasoningContext layer. | yes |
| Expand generic ContextAssembler | Put evidence validation and citation-map logic into the existing prompt-safe assembler. | |
| Keep node-local logic | Leave re-fetch/hash/snippet/citation behavior inside `generate_recommendation`. | |

**User's choice:** Fallback selected the recommended dedicated RAG reasoning kernel.
**Notes:** Existing `ContextAssembler` remains useful for final prompt-safe block assembly, but Phase 22 needs a reusable evidence/claim/verifier kernel shared by recommendation, final response, and safety routing.

---

## MaterialClaim And Authority Binding

| Option | Description | Selected |
|--------|-------------|----------|
| Three authority classes for MVP | Implement `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`; keep granular policy subtypes stretch-only. | yes |
| Full granular taxonomy now | Add many policy/risk/action claim subtypes as required Phase 22 scope. | |
| Free-text recommendation only | Keep structured recommendation output but do not introduce first-class claims. | |

**User's choice:** Fallback selected the recommended three authority classes for MVP.
**Notes:** Action recommendations require supported policy and supported current business facts, but still cannot bypass approval/action boundaries.

---

## Verifier Levels And Deterministic Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic Level 1 + low-cost Level 2 + risk-triggered Level 3 | Always run authority/freshness/hash/scope gates, use cheap lexical/span support for ordinary claims, and reserve semantic verification for risk-triggered cases. | yes |
| Semantic verification for every claim | Run Level 3 semantic support on all policy claims, including low-risk FAQ. | |
| Membership-only validation | Treat citation membership as sufficient support and defer semantic support entirely. | |

**User's choice:** Fallback selected the recommended tiered verifier.
**Notes:** Initial Level 3 defaults are 6 claims per run, 3 evidence snippets per claim, 12,000 verifier input characters per run, 15 second timeout, zero semantic-provider retries after provider/malformed-output failure, and explicit config versioning.

---

## Acceptance Gate And Metrics

| Option | Description | Selected |
|--------|-------------|----------|
| Safety golden cases block at 100%; aggregate support metrics at 95%+ | Require perfect pass on named safety/leakage/routing cases and 95%+ support accuracy on non-safety aggregate evals. | yes |
| Report metrics only | Add metrics but do not make them blocking. | |
| Live model eval required by default | Make live semantic-provider eval part of default automated acceptance. | |

**User's choice:** Fallback selected the recommended blocking safety gate with deterministic default tests.
**Notes:** Default tests should use deterministic fakes/mocks for semantic verifier behavior; live model/provider eval is optional or separately gated.

---

## the agent's Discretion

- Exact module names, class names, enum spelling, and file split.
- Exact Level 2 lexical/span support implementation.
- Exact prompt wording and final response template wording.
- Exact eval fixture filenames and command grouping.

## Deferred Ideas

- Bounded automatic regeneration attempt after support failure.
- Persisted claim dependency map for replay/eval summaries beyond state-level dependencies.
- Maintainer-facing verifier trace report or CLI.
- Granular policy claim subtypes beyond the three required authority classes.
- Phase 23 reranking/query rewrite, Phase 17 external execution, Phase RAG-5 backend replacement, and Policy Source Operations UI.
