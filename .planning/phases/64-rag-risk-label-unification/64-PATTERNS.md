# Phase 64: RAG Risk Label Unification - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** planned RAG registry, five RAG callers, tests, and architecture guard

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/rag_context/risk_labels.py` | utility / registry | label normalization and group lookup | `src/agent/safety/taxonomy.py`, `src/business/query/registry.py` | exact |
| `src/agent/rag_context/builder.py` | RAG context projection | risk hints -> prompt/final/verifier safe contexts | existing `builder.py` | exact |
| `src/agent/nodes/recommendation_generation.py` | LangGraph node helper | state/evidence labels -> material claim risk hints | existing recommendation node + `src/agent/intent_policy.py` registry use | exact |
| `src/agent/rag_context/verifier.py` | deterministic verifier | risk hints -> semantic review decision | existing verifier helper style | exact |
| `src/agent/rag_context/routing.py` | deterministic route mapper | reason codes -> route decision | existing route constants | exact |
| `src/agent/rag_context/metrics.py` | eval metrics | case labels/status -> level3 trigger metrics | existing metrics helper style | exact |
| `tests/agent/rag_context/test_risk_labels.py` | unit/parity test | registry groups and compatibility | `tests/agent/test_safety_taxonomy.py` | exact |
| `tests/architecture/test_rag_risk_label_boundaries.py` | static drift guard | AST/source scan | `tests/architecture/test_safety_taxonomy_boundaries.py` | exact |

## Pattern Assignments

### Registry Module

Copy the Phase 63 immutable registry style:

- `from __future__ import annotations`
- `@dataclass(frozen=True, slots=True)` descriptors where useful
- module-level `frozenset` groups for immutable public sets
- `MappingProxyType` only if exposing mappings
- helper functions returning `frozenset`, tuple, or bool, never mutable sets/lists
- explicit `__all__`

The registry should define named groups, not caller-specific names:

- `SAFE_EVIDENCE_RISK_LABELS`
- `PROMPT_SAFE_RISK_LABELS`
- `SEMANTIC_REVIEW_RISK_LABELS`
- `MANUAL_REVIEW_TRIGGER_RISK_LABELS`
- `ROUTING_RISK_LABELS`
- `METRIC_LEVEL3_TRIGGER_LABELS`
- `ROUTE_MANUAL_REVIEW_REASONS`
- `ROUTE_STALE_OR_OCR_REASONS`

### Caller Migration

Callers should import registry helpers, not duplicate sets:

- `builder.py`: use `filter_prompt_safe_risk_labels` or `is_prompt_safe_risk_label`.
- `recommendation_generation.py`: use `filter_safe_evidence_risk_labels` and `routing_risk_labels`.
- `verifier.py`: use `semantic_review_risk_labels` / `requires_semantic_review_for_risk_hints`.
- `routing.py`: use route reason groups from registry.
- `metrics.py`: use safe evidence labels and metric level-3 trigger labels from registry.

### Architecture Guard

Copy the targeted guard style from `tests/architecture/test_safety_taxonomy_boundaries.py`:

- enumerate migrated caller paths exactly
- parse assignments with `ast`
- fail only on local source-of-truth assignment names such as `_SAFE_RISK_LABELS`, `_SAFE_EVIDENCE_RISK_LABELS`, `_ROUTING_RISK_LABELS`, `_ROUTE_MANUAL_REVIEW_REASONS`, `_ROUTE_STALE_OR_OCR_REASONS`
- do not fail on fixtures, test data, or valid use of label string values in assertions

## Pitfalls To Avoid

- Do not add a broad grep that bans `manual_review_sensitive`, `conflict`, or `stale_evidence` everywhere.
- Do not move labels into `src.agent.safety.taxonomy`.
- Do not change Pydantic schemas for RAG context unless a test proves the current projection cannot carry the label.
- Do not alter domain-rule reason codes such as `negation_conflict` or `policy_hierarchy_conflict`.
