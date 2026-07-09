---
phase: 64
slug: rag-risk-label-unification
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-10
updated: 2026-07-10
---

# Phase 64 - Security

Per-phase security verification for RAG risk label unification. Scope is limited to the threats registered in the four Phase 64 PLAN.md threat models.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Raw risk hints to registry filters | Untrusted or caller-provided `risk_hints` / evidence `risk_labels` enter registry helpers before safe projection. | RAG risk labels; unknown labels must fail closed. |
| Safe RAG context projections | `ContextBuilder` projects labels into prompt, final response, memory, replay, business fact, and action snapshot safe contexts. | Prompt-safe evidence labels and snippets. |
| Verifier / routing / metrics trigger semantics | Backend verifier, route map, and eval metrics consume registry-owned trigger groups and small RAG-coupled route reason groups. | Risk labels, route reason codes, metric trigger markers. |
| Planning and validation artifacts | Phase summaries, validation, review, UAT, and security records document commands and file paths. | Non-customer planning metadata; no tenant/customer payloads expected. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Evidence | Status |
|-----------|----------|-----------|-------------|------------------------|--------|
| T-64-01 | Tampering | RAG label groups | mitigate | Immutable `frozenset` registry groups preserve compatibility labels in `src/agent/rag_context/risk_labels.py:14`; parity tests assert exact labels in `tests/agent/rag_context/test_risk_labels.py:24` and immutability in `tests/agent/rag_context/test_risk_labels.py:136`. | closed |
| T-64-02 | Information Disclosure | prompt-safe label filtering | mitigate | Registry filtering keeps only allowed labels in `src/agent/rag_context/risk_labels.py:112` and `src/agent/rag_context/risk_labels.py:136`; tests assert `raw_debug_secret` is dropped in `tests/agent/rag_context/test_risk_labels.py:58`. | closed |
| T-64-03 | Repudiation | future label changes | mitigate | Current label and trigger contracts are explicit in `tests/agent/rag_context/test_risk_labels.py:40`, `tests/agent/rag_context/test_risk_labels.py:47`, and `tests/agent/rag_context/test_risk_labels.py:89`. | closed |
| T-64-04 | Tampering | `ContextBuilder` label projection | mitigate | `ContextBuilder` imports `filter_prompt_safe_risk_labels` in `src/agent/rag_context/builder.py:25` and uses it in `_risk_labels_by_evidence_id` at `src/agent/rag_context/builder.py:421`; regression coverage is in `tests/agent/rag_context/test_context_builder.py:181`. | closed |
| T-64-05 | Information Disclosure | prompt/final context labels | mitigate | Safe projections derive filtered citation labels in `src/agent/rag_context/builder.py:159`; the regression asserts `raw_debug_secret` is absent from safe surfaces in `tests/agent/rag_context/test_context_builder.py:209`. | closed |
| T-64-06 | Elevation of Privilege | recommendation risk hints | mitigate | Recommendation generation imports `filter_safe_evidence_risk_labels` in `src/agent/nodes/recommendation_generation.py:17` and filters evidence labels at `src/agent/nodes/recommendation_generation.py:453`; architecture guard covers the migrated caller path in `tests/architecture/test_rag_risk_label_boundaries.py:12`. | closed |
| T-64-07 | Tampering | verifier trigger labels | mitigate | Verifier imports `requires_semantic_review_for_risk_hints` in `src/agent/rag_context/verifier.py:15` and uses it in both semantic trigger checks at `src/agent/rag_context/verifier.py:381` and `src/agent/rag_context/verifier.py:1031`. | closed |
| T-64-08 | Denial of Service | semantic verifier/domain rules | mitigate | Domain-rule verification still delegates to `DomainRuleVerifier` in `src/agent/rag_context/verifier.py:607`; focused verifier/domain tests passed in the Phase 64 gate below. | closed |
| T-64-09 | Repudiation | routing/eval semantics | mitigate | Routing aliases registry reason groups in `src/agent/rag_context/routing.py:11`; metrics imports registry helpers in `src/agent/rag_context/metrics.py:11` and uses routing/level-3 helpers at `src/agent/rag_context/metrics.py:343` and `src/agent/rag_context/metrics.py:466`; tests pin groups in `tests/agent/rag_context/test_risk_labels.py:89` and metric triggers in `tests/agent/rag_context/test_metrics.py:21`. | closed |
| T-64-10 | Tampering | future caller edits | mitigate | Architecture guard enumerates migrated caller paths in `tests/architecture/test_rag_risk_label_boundaries.py:12`, forbids local source-of-truth set names in `tests/architecture/test_rag_risk_label_boundaries.py:19`, and asserts no duplicate assignments in `tests/architecture/test_rag_risk_label_boundaries.py:83`. | closed |
| T-64-11 | Repudiation | architecture debt history | mitigate | `.planning/ARCHITECTURE-DEBT.md:1832` records the Phase 64 fix, caller migration, architecture guard, and named Phase 65 deferral through `.planning/ARCHITECTURE-DEBT.md:1860`. | closed |
| T-64-12 | Information Disclosure | validation artifacts | accept | Accepted risk documented below. Phase summaries and validation record file paths and command results only; final verification evidence appears in `.planning/phases/64-rag-risk-label-unification/64-04-SUMMARY.md:29` and `.planning/phases/64-rag-risk-label-unification/64-VALIDATION.md:60`. | closed |

Status vocabulary: `closed` means the declared mitigation, accepted-risk entry, or transfer evidence is present. No Phase 64 threats are open.

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-64-01 | T-64-12 | Phase validation artifacts necessarily include repository file paths and command summaries. This is accepted because the reviewed Phase 64 artifacts contain implementation paths and aggregate command results, not tenant/customer payloads. | Phase 64 PLAN disposition; verified by Codex security auditor | 2026-07-10 |

## Evidence

| Evidence Type | Result |
|---------------|--------|
| Threat model extraction | T-64-01 through T-64-12 extracted from `64-01-PLAN.md:113`, `64-02-PLAN.md:117`, `64-03-PLAN.md:141`, and `64-04-PLAN.md:122`. |
| Summary threat flags | No `## Threat Flags` section found in `64-01-SUMMARY.md`, `64-02-SUMMARY.md`, `64-03-SUMMARY.md`, or `64-04-SUMMARY.md`. |
| Local duplicate-set grep | No matches for migrated caller-local `_SAFE_RISK_LABELS`, `_SAFE_EVIDENCE_RISK_LABELS`, `_ROUTING_RISK_LABELS`, `_ROUTE_MANUAL_REVIEW_REASONS =`, or `_ROUTE_STALE_OR_OCR_REASONS =` in the migrated implementation files. |
| Registry import grep | Migrated callers import the declared helpers/groups from `src.agent.rag_context.risk_labels`; see `builder.py:25`, `recommendation_generation.py:17`, `verifier.py:15`, `routing.py:11`, and `metrics.py:11`. |
| Architecture debt closeout | `.planning/ARCHITECTURE-DEBT.md:1832` records Phase 64 as fixed and verified, with display/trace consistency deferred to Phase 65 at `.planning/ARCHITECTURE-DEBT.md:1860`. |
| Code review | `.planning/phases/64-rag-risk-label-unification/64-REVIEW.md:17` reports 0 critical, 0 warning, 0 info findings and clean status. |
| UAT | `.planning/phases/64-rag-risk-label-unification/64-UAT.md:60` reports 4 total tests, 4 passed, 0 issues. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-10 | 12 | 12 | 0 | Codex security auditor |

## Verification

| Command | Result |
|---------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_risk_labels.py tests/agent/rag_context/test_context_builder.py tests/agent/test_nodes/test_recommendation_generation.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py tests/architecture/test_rag_risk_label_boundaries.py -q --tb=short` | `128 passed, 1 warning` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/rag_context/risk_labels.py src/agent/rag_context/builder.py src/agent/rag_context/verifier.py src/agent/rag_context/routing.py src/agent/rag_context/metrics.py src/agent/nodes/recommendation_generation.py tests/agent/rag_context/test_risk_labels.py tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_metrics.py tests/agent/test_nodes/test_recommendation_generation.py tests/architecture/test_rag_risk_label_boundaries.py` | `All checks passed!` |

## Sign-Off

- [x] All threats have a disposition: 11 mitigate, 1 accept, 0 transfer.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-07-10.
