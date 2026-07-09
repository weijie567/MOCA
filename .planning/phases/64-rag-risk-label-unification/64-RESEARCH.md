# Phase 64: RAG Risk Label Unification - Research

**Researched:** 2026-07-10
**Domain:** RAG evidence risk labels, deterministic verifier routing, registry-backed drift prevention
**Confidence:** HIGH

<user_constraints>
## User Constraints From CONTEXT.md

### Locked Decisions

- Create a RAG-specific registry under `src/agent/rag_context/`, preferably `src/agent/rag_context/risk_labels.py`.
- Do not put RAG evidence labels in `src.agent.safety.taxonomy`; Phase 63 owns write-safety action taxonomy and risk severity/disposition.
- Preserve existing label strings in the first pass: `authority_checked`, `conflict`, `freshness_risk`, `high_risk`, `latest_version_checked`, `manual_review_sensitive`, `ocr_low_confidence`, `provenance_available`, `source_locator_available`, `stale_evidence`.
- Fix the immediate drift where `manual_review_sensitive` is allowed by metrics/verifier/routing/recommendation but filtered by `builder.py`.
- Unknown labels remain fail-closed and are dropped.
- Phase 64 may centralize route-trigger reason-code groups only where needed for RAG label/routing consistency.
- Do not rewrite deterministic domain-rule algorithms such as `negation_conflict` and `policy_hierarchy_conflict`.

### Out Of Scope

- Frontend Timeline/Details labels and trace console label registry: Phase 65.
- Trace/replay event type registry: Phase 65.
- Action taxonomy and risk severity/disposition: Phase 63.
- DB CHECK/state-machine hardening: Phase 67.
- Broad semantic verifier quality rewrite, new retrieval tools, or external services.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| RAG risk label vocabulary | API/Backend | Tests | Labels affect prompt-safe context, verifier routing, metrics, and recommendation generation; backend must own deterministic allowlists. |
| Prompt-safe label projection | API/Backend | Tests | `ContextBuilder` decides which labels can enter prompt/final/verifier contexts. |
| Semantic/manual-review trigger groups | API/Backend | Tests | Verifier/routing/metrics must share deterministic trigger semantics. |
| Drift prevention | Tests | API/Backend | Architecture tests should prevent local `_SAFE_*` label sets from reappearing after migration. |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 64 is a registry consolidation phase, not a RAG algorithm phase. The correct implementation is to create one immutable RAG label registry and migrate the current local sets in `builder.py`, `metrics.py`, `verifier.py`, `routing.py`, and `recommendation_generation.py` to consume it. This preserves Phase 22/33 deterministic evidence safety while removing the current label drift.

The most important current bug is concrete: `src/agent/rag_context/builder.py` defines `_SAFE_RISK_LABELS` without `manual_review_sensitive`, while `metrics.py`, `verifier.py`, `routing.py`, and `recommendation_generation.py` all treat `manual_review_sensitive` as a valid trigger. This means a risk hint can be lost before it reaches prompt-safe citations or downstream safe contexts.

**Primary recommendation:** implement `src/agent/rag_context/risk_labels.py` as the canonical owner, add RED tests for `manual_review_sensitive` builder propagation and registry parity, migrate callers, and add an architecture guard forbidding migrated callers from recreating `_SAFE_RISK_LABELS`, `_SAFE_EVIDENCE_RISK_LABELS`, or `_ROUTING_RISK_LABELS`.
</research_summary>

<source_facts>
## Source Facts

### Current Drift

- `src/agent/rag_context/builder.py` has `_SAFE_RISK_LABELS` at lines 30-42 and omits `manual_review_sensitive`.
- `src/agent/rag_context/builder.py` filters `risk_hints[*].labels` through `_SAFE_RISK_LABELS` in `_risk_labels_by_evidence_id` at lines 433-441.
- `src/agent/rag_context/metrics.py` has `_SAFE_EVIDENCE_RISK_LABELS` at lines 37-50 and includes `manual_review_sensitive`.
- `src/agent/rag_context/metrics.py` treats `manual_review_sensitive` as a level-3/manual-review trigger in `_level3_triggered` at lines 480-487.
- `src/agent/rag_context/verifier.py` sends `manual_review_sensitive`, `conflict`, `stale_evidence`, and `ocr_low_confidence` to `NEEDS_SEMANTIC_REVIEW` at lines 373-385 and `should_run_level3_semantic_verification` at lines 1017-1031.
- `src/agent/rag_context/routing.py` keeps manual-review route reasons at lines 53-66, including `manual_review_sensitive`, and stale/OCR reasons at line 67.
- `src/agent/nodes/recommendation_generation.py` duplicates `_SAFE_EVIDENCE_RISK_LABELS` at lines 40-53 and `_ROUTING_RISK_LABELS` at line 54, both including `manual_review_sensitive`.

### Existing Test Coverage

- `tests/agent/rag_context/test_context_builder.py` covers propagation of `high_risk`, `provenance_available`, and `ocr_low_confidence`, but lacks a builder regression for `manual_review_sensitive`.
- `tests/agent/rag_context/test_semantic_verifier.py` already treats `manual_review_sensitive` as semantic/manual-review sensitive.
- `tests/agent/rag_context/test_routing.py` already has route coverage for `manual_review_sensitive`.
- `tests/agent/test_nodes/test_recommendation_generation.py` already expects state/evidence risk hints to merge `manual_review_sensitive` and `ocr_low_confidence`.

### Existing Patterns To Reuse

- `src/agent/safety/taxonomy.py` uses frozen dataclasses, `frozenset`, and `MappingProxyType` for a single source of truth introduced in Phase 63.
- `src/business/query/registry.py` uses the same immutable registry pattern for business query descriptors.
- `tests/architecture/test_safety_taxonomy_boundaries.py` is the closest architecture guard pattern for forbidding migrated callers from recreating local source-of-truth sets.
</source_facts>

<plan_breakdown>
## Recommended Plan Breakdown

1. Registry foundation: add RED unit/parity tests and implement `src/agent/rag_context/risk_labels.py`.
2. Context builder and recommendation generation migration: fix the known `manual_review_sensitive` propagation bug and remove local safe label sets from prompt/recommendation code.
3. Verifier, routing, and metrics migration: consume the same registry groups for semantic review, manual-review routing, and metric triggers.
4. Drift guard and closeout: add architecture tests, update architecture debt, and run focused verification.
</plan_breakdown>

<validation_architecture>
## Validation Architecture

### Primary Test Lanes

- Registry/unit lane: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_risk_labels.py -q --tb=short`
- Builder/recommendation lane: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short`
- Verifier/routing/metrics lane: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py -q --tb=short`
- Drift guard lane: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short`
- Focused phase lane: combine the above plus ruff on changed files.

### Required RED Tests

- `manual_review_sensitive` survives `ContextBuilder` risk hints into prompt/final/verifier safe context.
- Unknown risk labels are still dropped.
- All migrated callers use registry-owned groups.
- Semantic-review and manual-review trigger sets stay consistent across verifier, routing, metrics, and recommendation generation.
- No migrated caller keeps local `_SAFE_RISK_LABELS`, `_SAFE_EVIDENCE_RISK_LABELS`, or `_ROUTING_RISK_LABELS`.
</validation_architecture>

<common_pitfalls>
## Common Pitfalls

- Treating RAG labels as Phase 63 action taxonomy. They are different domains and should not share a module.
- Renaming labels while fixing drift. Compatibility is the phase goal; no label migration is needed now.
- Only adding `manual_review_sensitive` to `builder.py`. That fixes the symptom but leaves multiple future drift points.
- Scanning broadly for words like `conflict` or `stale_evidence` in tests. These strings are valid fixtures and reason codes; the drift guard should target source-of-truth local set assignments in migrated callers.
- Changing deterministic verifier/domain-rule algorithms. Phase 64 only clarifies label/reason group ownership.
</common_pitfalls>

<open_questions>
## Open Questions

None blocking. Reason-code groups are not identical to risk labels, so the plan should centralize only the route-trigger groups currently duplicated in routing/verifier/metrics/recommendation behavior, without claiming every reason code is a risk label.
</open_questions>

## RESEARCH COMPLETE
