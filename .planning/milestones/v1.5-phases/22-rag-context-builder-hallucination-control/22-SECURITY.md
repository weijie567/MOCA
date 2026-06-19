---
phase: 22
slug: rag-context-builder-hallucination-control
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-20
verified: 2026-06-20
---

# Phase 22 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 22 implements RAG Context Builder and hallucination-control boundaries. The 22-01 through 22-06 plan summaries recorded no new threat flags beyond the planned STRIDE register. This review consolidated the repeated plan threat models into seven phase-level threats and verified each mitigation against the implemented code, regression tests, and deterministic evals.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Retrieval candidate to canonical evidence | Untrusted evidence refs become prompt/verifier/final evidence only after tenant, scope, hash, freshness, and current-version checks. | Policy evidence refs, canonical chunk metadata, snippets |
| Model output to verifier route | Model-produced recommendation text cannot choose allow/non-allow routing; backend verifier output owns the route map. | Claims, citations, route status, reason codes |
| Verifier route to action boundary | Only allow routes may create proposed actions, approvals, drafts, or safety snapshots. | Verification route, approval state, action payload bindings |
| Internal debug/provenance to user surfaces | Prompt, final response, memory, replay, action, and eval surfaces receive redacted safe projections rather than raw provenance or private verifier state. | Citation refs, snippets, safe reason codes, metrics |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-22-01 | Information Disclosure / Elevation of Privilege | RAG evidence inclusion | mitigate | Tenant and scope validation run before inclusion in `src/agent/rag_context/builder.py:83`; canonical service gates run in `src/knowledge/service.py:300`; regressions cover wrong tenant/scope in `tests/agent/rag_context/test_context_builder.py:243`. Residual risk: canonical repository rows must remain trustworthy. | closed |
| T-22-02 | Tampering | Evidence integrity and freshness | mitigate | Hash/latest/freshness/scope reason codes are enforced in `src/knowledge/service.py:337` and `src/agent/rag_context/builder.py:465`; duplicate/hash/latest/stale cases are covered in `tests/knowledge/test_phase22_evidence_validation.py:194`. Residual risk: freshness semantics depend on supplied `effective_at`. | closed |
| T-22-03 | Information Disclosure | Prompt/final/memory/replay/action surfaces | mitigate | Safe projections use `RagSafeContext` in `src/agent/rag_context/builder.py:171`; leakage tests cover raw OCR, provenance, private reasoning, tool payload, and debug sentinels in `tests/agent/rag_context/test_leakage.py:249`. Residual risk: `debug_context` must remain non-user-facing. | closed |
| T-22-04 | Spoofing / Tampering | Claim authority verification | mitigate | Business facts require Tool System refs in `src/agent/rag_context/verifier.py:610`; memory/model/provenance authority rejections are in `src/agent/rag_context/verifier.py:655`; tests cover wrong authority sources in `tests/agent/rag_context/test_authority_boundaries.py:115`. Residual risk: future authority classes need matching verifier gates. | closed |
| T-22-05 | Elevation of Privilege | Backend route selection | mitigate | Route DTOs are backend-owned in `src/agent/rag_context/routing.py:20`; route map failures fail closed in `src/agent/rag_context/routing.py:100`; graph routing uses backend verifier route in `src/agent/routing.py:157`; tests cover backend-owned routing in `tests/agent/rag_context/test_routing.py:121`. Residual risk: unknown states route to manual review rather than allow. | closed |
| T-22-06 | Tampering / Elevation of Privilege | Action and approval boundary | mitigate | Non-allow routes clear action/approval/snapshot state in `src/agent/nodes/assess_risk_and_approval.py:444`; action drafts reject non-allow routes with `VERIFIER_NOT_ALLOW` in `src/agent/nodes/action_draft.py:200`; regressions cover stale binding and non-allow blocking in `tests/agent/test_phase22_action_boundary.py:115`. Residual risk: future direct action nodes must keep this guard. | closed |
| T-22-07 | Information Disclosure | Semantic verifier and eval reporting | mitigate | Semantic verifier failures are redacted in `tests/agent/rag_context/test_semantic_verifier.py:128`; eval report redaction is covered in `tests/agent/rag_context/test_leakage.py:144`; safe eval output is built in `src/agent/rag_context/metrics.py:521`. Residual risk: live provider behavior remains outside the deterministic local gate. | closed |

*Status: open - closed*
*Disposition: mitigate (implementation required) - accept (documented risk) - transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-20 | 7 | 7 | 0 | Codex + `gsd-security-auditor` |

Verification evidence:

- `gsd-security-auditor`: `## SECURED`, threats closed `7/7`, `threats_open: 0`.
- Phase 22 targeted security review: no open threat flags in 22-01 through 22-06 summaries.
- Auditor verification runs: `uv run pytest ...phase22... -q` reported `93 passed, 1 warning`; `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds` reported `status: pass`, 24 cases, `leakage_count: 0`, no threshold failures.
- Prior Phase 22 UAT gates recorded 6/6 pass in `22-UAT.md`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-20
