---
phase: 56
slug: recommendation-generation-and-rag-claim-status-alignment
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-07
updated: 2026-07-07
---

# Phase 56 — Security

Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Graph route value to StateGraph node | Active graph route-map destinations now target canonical `recommendation_generation`. | Internal route keys and node names. |
| RAG evidence to generation route | `route_after_rag_context` decides whether verified or partial evidence may reach generation. | Verified evidence package status, RAG context status, evidence policy flags. |
| Claim verification to risk/action path | `route_after_claim_verify`, `route_after_risk`, `assess_risk_and_approval`, and `action_draft` decide whether recommendations can become action drafts. | `claim_verification_bundle`, material claims, proposed actions, risk/approval state. |
| Trace/API/frontend projection | Runtime and historical graph node names are projected to API/SSE/frontend/eval surfaces. | Persisted step names, target graph names, timeline labels, payload extraction. |
| Legacy compatibility surface | Historical `generate_recommendation` import/trace/API surfaces remain readable until Phase 58. | Compatibility metadata and legacy wrapper identity. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-56-01 | Tampering | `src/agent/nodes/recommendation_generation.py`, `src/agent/graph.py` | mitigate | Canonical callable emits `recommendation_generation`; active graph registers `recommendation_generation`; static and graph tests reject active `generate_recommendation`. Evidence: `56-01-SUMMARY.md`, `56-02-SUMMARY.md`, clean code review. | closed |
| T-56-02 | Tampering / elevation of privilege | `route_after_rag_context`, final/API projection | mitigate | Router uses schema-owned RAG status vocabulary; missing, unknown, unsafe, stale, conflicting, invalid, and build-error states fail closed; final/API projection uses safe canonical fields. Evidence: `56-03-SUMMARY.md`, `56-04-SUMMARY.md`, UAT tests 3 and 5. | closed |
| T-56-03 | Elevation of privilege | `route_after_claim_verify` | mitigate | Proposed actions require explicit allowed `action_recommendation` support before entering risk/action routing; low-risk verified action recommendations still enter risk for binding. Evidence: fix commits `f24c108`, `12f8223`, clean review. | closed |
| T-56-04 | Tampering / information disclosure | legacy verifier fields, `final_response.py`, `action_draft.py` | mitigate | Legacy verifier fields cannot override missing/blocked canonical bundles; current-run final response prioritizes canonical bundles/packages; `action_draft` also requires positive action-claim authority. Evidence: commits `2abf5c7`, `ba1d649`, `cb3ec9a`, clean review. | closed |
| T-56-05 | Tampering | Phase 57/58 boundary | mitigate | Phase 56 preserves `assess_risk_and_approval` as the only active legacy row and does not introduce `risk_gate`; docs/debt explicitly defer risk rename to Phase 57 and compatibility deletion to Phase 58. Evidence: `tests/architecture/test_canonical_graph_baseline.py`, `docs/current-langgraph-architecture.md`, `docs/architecture-overview.md`. | closed |
| T-56-06 | Availability | `graph_vocabulary.py`, trace/API projection, legacy import surface | mitigate | Historical `generate_recommendation` rows/imports remain readable via Phase 56 compatibility alias and Phase 58 delete metadata; current runtime projects `recommendation_generation`. Evidence: `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`. | closed |

## Accepted Risks Log

No accepted risks.

## Residual Named Deferrals

| Deferral | Owner Phase | Security Impact |
|----------|-------------|-----------------|
| `assess_risk_and_approval -> risk_gate` active rename | Phase 57 | Not open for Phase 56 because the current risk/action boundary was hardened under its existing node name. |
| Delete `generate_recommendation` compatibility wrapper/projection | Phase 58 | Not open for Phase 56 because compatibility metadata is explicit, tested, and non-authoritative for current runtime routing. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-07 | 6 | 6 | 0 | Codex autopilot |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-07
