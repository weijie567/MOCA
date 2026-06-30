---
phase: 32
slug: intent-graph-migration
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-28
updated: 2026-06-28
---

# Phase 32 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Legacy runtime graph -> target contract projection | Legacy node/router names are projected to target graph vocabulary without changing runtime execution or audit truth. | Graph step names, trace summary fields, API/SSE projection metadata |
| LLM/session memory -> effective intent and slot decisions | Model and memory outputs remain candidates/context; deterministic registries own effective route and slot inheritance decisions. | Intent classification, required slots, inherited slot metadata |
| Business fact refs -> target merchant context status | Only service-approved business fact refs can produce resolved merchant-context status. | BusinessFactRefV1-shaped refs, safe status/reason metadata |
| Target merchant-context status -> run/trace/replay authorization | Status metadata must not grant AgentRun, trace, replay, or stream visibility. | API authorization guards, role constants, target merchant-context projection |
| Phase 32 implementation -> Phase 33 RAG/claim behavior | Phase 33 target names may be cataloged but must remain non-runnable in Phase 32. | Graph vocabulary entries, graph registration/static contract tests |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-32-01-01 | Tampering / Repudiation | `src/agent/graph_vocabulary.py` | mitigate | Immutable typed entries and tests for required aliases. Evidence: `src/agent/graph_vocabulary.py:13`, `:98`; `tests/agent/test_graph_vocabulary.py:16`. | closed |
| T-32-01-02 | Spoofing / Elevation of Privilege | Deferred `rag_context_build` / `claim_verify` entries | mitigate | Entries remain `deferred_non_runnable`, `runnable=False`, and graph registration tests reject runnable nodes. Evidence: `src/agent/graph_vocabulary.py:77`, `:85`; `tests/agent/test_graph.py:732`; `tests/architecture/test_phase32_static_contract.py:39`. | closed |
| T-32-01-03 | Repudiation | Trace projection helper | mitigate | Projection preserves legacy `node` and adds implementation/target fields. Evidence: `src/agent/graph_vocabulary.py:122`, `:127`, `:128`; `tests/agent/test_graph_vocabulary.py:131`. | closed |
| T-32-02-01 | Elevation of Privilege / Spoofing | `classify_intent` | mitigate | Raw LLM classification remains candidate-only and trace records deterministic `policy_owner`. Evidence: `src/agent/nodes/classify_intent.py:134`, `:232`, `:234`; `tests/agent/test_nodes/test_classify_intent.py:45`. | closed |
| T-32-02-02 | Tampering | `route_after_intent` | mitigate | Route decisions consume registry API and retain finite legacy route-key guard. Evidence: `src/agent/routing.py:22`, `:61`, `:230`; `tests/agent/test_intent_routing.py:284`, `:322`. | closed |
| T-32-02-03 | Elevation of Privilege | Approval-like chat and short replies | mitigate | Phase 25 fail-closed paths remain covered. Evidence: `src/agent/nodes/classify_intent.py:470`; `tests/agent/test_intent_routing.py:195`; `tests/agent/test_nodes/test_classify_intent.py:209`. | closed |
| T-32-03-01 | Information Disclosure / Tampering | `resolve_slots_with_metadata` | mitigate | Slot registry rejects stale, mismatched, invalidated, untrusted, or incompatible inherited slots. Evidence: `src/agent/intent_policy.py:274`, `:284`, `:289`, `:301`, `:303`, `:306`; `src/agent/routing.py:120`; `tests/agent/test_required_slots.py:99`. | closed |
| T-32-03-02 | Spoofing | `extract_slots` | mitigate | LLM extraction remains candidate data; resolved active slots come from deterministic registry merge. Evidence: `src/agent/nodes/extract_slots.py:80`, `:81`, `:84`; `tests/agent/test_required_slots.py:118`. | closed |
| T-32-03-03 | Denial of Service / Tampering | `route_after_slots` | mitigate | Router keeps finite legacy edge-key guard and target projection tests. Evidence: `src/agent/routing.py:23`, `:69`, `:239`; `tests/agent/test_graph.py:779`, `:780`. | closed |
| T-32-04-01 | Repudiation / Tampering | `src/agent/trace.py` | mitigate | Legacy `nodes_executed` remains and target projection fields are additive. Evidence: `src/agent/trace.py:243`, `:245`, `:276`, `:277`, `:278`; `tests/agent/test_trace.py:110`, `:122`. | closed |
| T-32-04-02 | Information Disclosure | `src/agent/merchant_context.py` | mitigate | Merchant-context projection returns allowlisted fields, rejects raw identifiers/spoofing, and accepts only approved business fact refs. Evidence: `src/agent/merchant_context.py:35`, `:96`, `:98`, `:104`, `:143`, `:152`, `:158`; `tests/agent/test_trace.py:151`, `:177`, `:219`. | closed |
| T-32-04-03 | Elevation of Privilege | AgentRun/trace/replay routers | mitigate | Owner/admin-only visibility remains and guards do not consume `target_merchant_context`. Evidence: `src/api/routers/agent_runs.py:46`, `:1145`, `:1148`; `src/api/routers/traces.py:20`, `:37`, `:88`; `tests/test_agent_runs_api.py:1130`, `:1131`. | closed |
| T-32-05-01 | Tampering / Safety bypass | `src/agent/graph.py` | mitigate | Static tests fail if Phase 33 RAG/claim target names are registered as runnable graph nodes. Evidence: `src/agent/graph.py:135`; `tests/architecture/test_phase32_static_contract.py:39`, `:44`; `32-05-SUMMARY.md:104`. | closed |
| T-32-05-02 | Repudiation | Phase 32 planning and summary artifacts | mitigate | Static test scans command-bearing artifact lines for invalid direct pytest conclusions. Evidence: `tests/architecture/test_phase32_static_contract.py:94`, `:98`; `32-05-SUMMARY.md:108`. | closed |
| T-32-05-03 | Elevation of Privilege | API visibility guards | mitigate | Static tests fail if target merchant context appears in auth allow branches or admin-only role constants change. Evidence: `tests/architecture/test_phase32_static_contract.py:80`, `:81`, `:82`, `:91`; `src/api/routers/agent_runs.py:1148`; `src/api/routers/traces.py:37`. | closed |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-28 | 15 | 15 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-28
