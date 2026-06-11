# Phase 10: State Lifecycle + Routing Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 10-state-lifecycle-routing-migration
**Areas discussed:** P10 scope (investigate merge), permission-denied semantics, RAG event classification, termination_reason canonical, max_iterations shape

---

## P10 Scope — does investigate merge belong to Phase 10?

| Option | Description | Selected |
|--------|-------------|----------|
| P10 absorbs investigate merge | state lifecycle + router totality + merge three nodes into investigate bounded-loop | ✓ |
| P10 stays narrow | only ROADMAP-literal state/router; agentic merge a separate phase | |

**User's choice:** P10 absorbs investigate merge
**Notes:** Surfaced as head decision because of a real cross-phase conflict: ROADMAP P10 goal text names only state+router; Phase 9 CONTEXT locked "drop investigator / no bounded caller". Both recorded as deviations P10-DEV-01 (scope expansion) and P10-DEV-02 (owner drift) in CONTEXT.

---

## permission-denied semantics in route_after_investigate

| Option | Description | Selected |
|--------|-------------|----------|
| Fine-grained: block only denied part | preserve other legit facts from same loop; denied resource not in reply, no inference leak | ✓ |
| One-shot → final | keep draft's blanket permission denied -> final | |

**User's choice:** Fine-grained
**Notes:** Replaces §9 draft ⚠️待替换 placeholder. Enterprise RBAC: agent may be authorized for orders but not merchant-risk; blanket block over-blocks. TrustedContext scope checks retained.

---

## RAG vs tool event classification (Phase 15 contract)

| Option | Description | Selected |
|--------|-------------|----------|
| By call nature | search_* → rag_retrieval_*; get_* → tool_call_*; no double-emit | ✓ |
| All tool_call_* | unify event family | |

**User's choice:** By call nature
**Notes:** search_case_memory decided → rag_retrieval_* (retrieval by nature). Avoids Phase 15 started/terminal pairing ambiguity.

---

## termination_reason as canonical state

| Option | Description | Selected |
|--------|-------------|----------|
| Into canonical field | §9.4 State writes + §10.1 registry, reset each turn | ✓ |
| Payload only | only redacted_payload | |

**User's choice:** Into canonical field
**Notes:** §9.5 route_after_investigate Reads already lists termination_reason; routers read state not trace payload, so it must be canonical state.

---

## max_iterations configuration shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-intent + global ceiling | GAD-02 intent-admission field + backstop; default 3/ceiling 5 = discussion params only | ✓ |
| Global fixed value | single value, not per-intent | |

**User's choice:** Per-intent + global ceiling
**Notes:** Aligns with GAD-02 (max_iterations is an intent-admission field). Default/ceiling numbers non-normative, set during planning/eval.

---

## Claude's Discretion

- **long_term_memory_retrieve stays independent** (not merged into loop) — Phase 16 identity/scope semantics, pre-load not fetch-on-demand.
- **iteration annotation lands in Phase 10 emitter at first emit** (redacted_payload, non-breaking) — runtime fact, backfill can't reconstruct.

## Deferred Ideas

- Spec promotion (§9 draft → contract-spec.md, 12 blocks) sequenced AFTER discuss定稿 + Codex cross-review, BEFORE Phase 10 implementation against live spec.
- migration-plan.md:16 "不引入自由 ReAct" acceptance line reworded during promotion.
- No scope creep raised during discussion — all items clarified HOW to implement the decided merge.
