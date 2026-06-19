# Phase 23: RAG Reranker + Query Rewrite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20T01:45:20+08:00
**Phase:** 23-RAG Reranker + Query Rewrite
**Areas discussed:** Query rewrite boundary, candidate generation, reranker contract, provider and diagnostics, eval and latency, boundary preservation

Because the interactive question tool is unavailable in the current execution mode, each gray area was resolved with the recommended default based on `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, archived v1.3/v1.4/v1.5 artifacts, and current code anchors.

---

## Query Rewrite Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic bounded rewrite | Rule-first synonym/intent expansion, typed internal plan, original query preserved, no live provider needed for tests. | yes |
| Provider-first rewrite | LLM/provider creates rewritten queries by default, with fallback on errors. | |
| No rewrite in baseline | Keep current hybrid retrieval and defer rewrite to a later phase. | |

**User's choice:** Recommended default selected by agent.
**Notes:** This satisfies QRW-01..QRW-03 without introducing live-provider dependency or trusted-scope widening.

---

## Candidate Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Original plus optional rewritten channels | Always run original query; run rewrite channels only when allowed; apply all filters to every channel; merge before ranking. | yes |
| Rewrite replaces original | Run only the rewritten query when rewrite triggers. | |
| Rerank current top-5 only | Avoid extra candidate generation and only reorder current final hits. | |

**User's choice:** Recommended default selected by agent.
**Notes:** Original-plus-rewrite protects current recall/fallback behavior and gives evals an ablation point for rewrite contribution.

---

## Reranker Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Project-owned local-first interface | Add internal reranker DTO/interface before `EvidenceRefV1` construction, deterministic default, optional provider adapter later. | yes |
| External adapter as primary contract | Make cross-encoder/external API the main reranking abstraction from the start. | |
| Reuse verifier scoring | Let MaterialClaimVerifier or semantic support scores drive ranking. | |

**User's choice:** Recommended default selected by agent.
**Notes:** Reranker relevance and verifier support must stay separate. The insertion point is `retrieve_hits()`/internal candidates, not post-ContextBuilder support verification.

---

## Provider And Diagnostics

| Option | Description | Selected |
|--------|-------------|----------|
| Config-gated provider seam plus redacted diagnostics | Provider adapters are optional, timeout/retry/budget bounded, and expose only safe maintainer/eval diagnostics. | yes |
| Always-on provider diagnostics | Include provider payloads/prompts/scores in ordinary search outputs for debugging. | |
| No provider seam | Keep only local reranking and defer external providers entirely. | |

**User's choice:** Recommended default selected by agent.
**Notes:** This keeps Phase 23 compatible with no-live-provider default tests while still allowing a safe adapter seam if planning accepts it.

---

## Eval And Latency

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic ablation eval with latency gates | Compare dense/sparse/fuzzy/RRF/rewrite/rerank/rewrite+rerank, report rank metrics, no-evidence precision, fallback, unsafe retrieval, and latency percentiles. | yes |
| Hit@5-only extension | Only add more golden cases to the current Hit@5 script. | |
| Provider benchmark | Focus on provider reranker quality and cost first. | |

**User's choice:** Recommended default selected by agent.
**Notes:** Current `scripts/eval_rag_hit_at_5.py` is a useful base but not sufficient for Phase 23 ablation/latency requirements.

---

## Boundary Preservation

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow Phase 23 allowlist | Update static guards to permit Phase 23-owned rewrite/rerank files only; keep EvidenceRefV1 exact and all Phase 17/RAG-5/Policy Source bans. | yes |
| Remove old Phase 21/22 guards | Delete static guards that mention deferred Phase 23 symbols. | |
| Broaden AgentState/replay surfaces | Store detailed rewrite/rerank traces in general state for later debugging. | |

**User's choice:** Recommended default selected by agent.
**Notes:** Existing guards are valuable. Phase 23 should revise them precisely rather than weakening them.

---

## the agent's Discretion

- Exact DTO, interface, module, and config names.
- Whether to extend `scripts/eval_rag_hit_at_5.py` or create a dedicated Phase 23 eval script.
- Deterministic local reranker formula, as long as tests pin ranking and safe score-component behavior.

## Deferred Ideas

- 17-prep AgentState Surface Contracts + Authority Isolation.
- Phase 17 external action execution/outbox/reconciliation/compensation.
- Phase RAG-5 external `SearchBackend`, Vespa/OpenSearch, or vector database replacement.
- Policy Source Operations UI/workflow.
- Live default-demo cross-encoder provider, maintainer CLI trace reports, and eval-driven auto-tuning unless accepted as stretch during planning.
