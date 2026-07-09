---
phase: 64
slug: rag-risk-label-unification
status: complete
mode: auto-discuss
created: 2026-07-10
---

# Phase 64 Context — RAG Risk Label Unification

## Phase Boundary

Phase 64 unifies RAG risk label vocabulary and routing semantics across:

- `src/agent/rag_context/builder.py`
- `src/agent/rag_context/metrics.py`
- `src/agent/rag_context/verifier.py`
- `src/agent/rag_context/routing.py`
- `src/agent/nodes/recommendation_generation.py`
- related `tests/agent/rag_context/` and recommendation-generation tests

It must not expand into Phase 65 trace/frontend label work, Phase 63 action taxonomy, Phase 66 config/demo hygiene, or Phase 67 state-machine/DB CHECK hardening.

## Locked Decisions

### 1. Canonical Owner

Create a RAG-specific registry module, preferably `src/agent/rag_context/risk_labels.py`, as the single owner for:

- prompt-safe evidence risk labels
- routing/manual-review trigger labels
- semantic-review trigger labels
- eval/metrics label allowlists
- label-to-route/reason-code grouping helpers where currently duplicated

Do not put these labels in `src.agent.safety.taxonomy`; that module owns action/risk vocabulary for write-safety and intent routing, not RAG evidence labels.

### 2. Compatibility

Keep existing label strings compatible in the first pass:

- `authority_checked`
- `conflict`
- `freshness_risk`
- `high_risk`
- `latest_version_checked`
- `manual_review_sensitive`
- `ocr_low_confidence`
- `provenance_available`
- `source_locator_available`
- `stale_evidence`

The immediate bug to fix is that `manual_review_sensitive` is allowed by metrics/verifier/routing/recommendation, but filtered out by `builder.py`. The registry must make `manual_review_sensitive` prompt-safe where the existing downstream pipeline already treats it as a manual-review trigger.

If a label is renamed later, this phase must add explicit migration/alias notes and tests. The preferred Phase 64 scope is no renames.

### 3. Label Groups

The registry should expose named groups instead of callers rebuilding set literals:

- all safe evidence labels
- labels allowed to pass from evidence refs / risk hints into prompt-safe RAG context
- labels that trigger semantic review
- labels that trigger manual-review routing
- labels used by metrics for level-3 trigger / safe metric projection

Callers should consume helpers or immutable sets from the registry. Existing unknown-label filtering behavior should remain fail-closed: unknown labels are dropped, not passed through.

### 4. Reason Codes Versus Risk Labels

Risk labels and verifier reason codes are related but not identical.

Phase 64 may centralize small route-trigger reason-code groups if that is required to remove duplicate label/reason semantics, especially around:

- `manual_review_sensitive`
- `conflict` / `conflicting_evidence`
- `stale_evidence`
- `ocr_low_confidence`
- semantic provider timeout/error/malformed reason codes

Do not rewrite the domain-rule algorithms themselves. Rules such as `negation_conflict` and `policy_hierarchy_conflict` should remain deterministic verifier/domain-rule outputs; Phase 64 should ensure their downstream routing/eval semantics are explicitly covered, not replace them with an LLM or generic rule engine.

### 5. Tests First

Planner should require RED tests before implementation:

- `manual_review_sensitive` survives `ContextBuilder` risk hints into citation/safe/verifier context.
- builder/metrics/verifier/routing/recommendation consume the same registry-owned label sets.
- no migrated caller keeps `_SAFE_RISK_LABELS`, `_SAFE_EVIDENCE_RISK_LABELS`, or `_ROUTING_RISK_LABELS` local source-of-truth sets after migration.
- semantic/manual-review trigger labels stay consistent across verifier and recommendation generation.
- unknown labels remain filtered out.

### 6. Scope Exclusions

Do not implement:

- frontend Timeline/Details label work
- trace event or replay event type registry
- action taxonomy or risk severity/disposition changes
- DB CHECK/state-machine hardening
- broad policy semantic algorithm rewrites
- new RAG retrieval tools or external services

These belong to Phase 65, Phase 63, Phase 67, or future RAG quality phases.

## Source Facts Already Verified

- `src/agent/rag_context/builder.py` has `_SAFE_RISK_LABELS` without `manual_review_sensitive`, so it filters that label from risk hints.
- `src/agent/rag_context/metrics.py` has `_SAFE_EVIDENCE_RISK_LABELS` and `_ROUTING_RISK_LABELS` including `manual_review_sensitive`.
- `src/agent/rag_context/verifier.py` treats `manual_review_sensitive`, `conflict`, `stale_evidence`, and `ocr_low_confidence` as semantic/manual-review triggers.
- `src/agent/rag_context/routing.py` routes `manual_review_sensitive` to manual review and has separate hardcoded reason-code groups.
- `src/agent/nodes/recommendation_generation.py` has `_SAFE_EVIDENCE_RISK_LABELS` and `_ROUTING_RISK_LABELS` including `manual_review_sensitive`.
- Tests already reference these labels in `tests/agent/rag_context/` and `tests/agent/test_nodes/test_recommendation_generation.py`, but they do not fully protect builder parity for `manual_review_sensitive`.

## Canonical Refs

- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/ARCHITECTURE-DEBT.md`
- `.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-SECURITY.md`
- `.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-VALIDATION.md`
- `src/agent/rag_context/builder.py`
- `src/agent/rag_context/metrics.py`
- `src/agent/rag_context/verifier.py`
- `src/agent/rag_context/routing.py`
- `src/agent/rag_context/domain_rules.py`
- `src/agent/rag_context/schemas.py`
- `src/agent/nodes/recommendation_generation.py`
- `tests/agent/rag_context/test_context_builder.py`
- `tests/agent/rag_context/test_verifier.py`
- `tests/agent/rag_context/test_routing.py`
- `tests/agent/rag_context/test_semantic_verifier.py`
- `tests/agent/test_nodes/test_recommendation_generation.py`

## Deferred Ideas

- Full semantic verifier quality improvements beyond label routing.
- Frontend/backend display label registry for RAG labels, if needed, belongs in Phase 65.
- State-machine and DB/API/frontend status registries remain a suggested Phase 67 concern.
