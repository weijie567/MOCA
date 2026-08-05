---
phase: 57
slug: risk-gate-and-approval-gate-canonicalization
status: verified
threats_open: 0
asvs_level: 1
security_enforcement: true
created: 2026-07-08
---

# Phase 57 - Security

Per-phase security contract for Phase 57 risk-gate and approval-gate canonicalization.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Claim/RAG state -> `risk_gate` | Verified claim/evidence state gates whether action-risk processing can start. | `claim_verification_bundle`, evidence refs, blocked claims, recommendation/action draft state. |
| `risk_gate` -> approval/action state | Deterministic risk/action bindings become downstream authority. | Proposed action, action hash, snapshot refs/hashes, risk decision, approval plan, auto-allowed binding. |
| Legacy risk surface -> current runtime identity | `assess_risk_and_approval` remains compatibility-only and must not become active graph authority. | Import/test wrapper identity, historical trace projection, Phase 58 delete metadata. |
| Router return value -> StateGraph destination | Route strings must match registered canonical graph node keys. | `risk_gate`, `approval_gate`, `action_draft`, `final_response` route values. |
| Authenticated approval API -> ApprovalService | User/API input becomes trusted command only after auth, scope, version, hash, and assignment validation. | Approval decision body, edited action, expected versions, actor role/scope, approval request bindings. |
| ApprovalService -> graph resume | Server-constructed approval result crosses into graph resume state. | `TrustedApprovalResultV1`, `resume_route`, new action hash, tenant/run/hash/snapshot bindings. |
| Stored trace node names -> API/SSE/frontend display | Historical node names remain readable without rewriting audit history. | `implementation_node`, `target_node_name`, risk-level display payloads, historical compatibility labels. |
| Runtime implementation -> docs/validation/debt | Current-source docs and phase handoff must not describe compatibility names as current authority. | Architecture docs, validation evidence, architecture debt Phase 58 residuals. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Evidence | Status |
|-----------|----------|-----------|-------------|---------------------|--------|
| T-57-01-01 | Tampering | `risk_gate` shared implementation | mitigate | Claim bundle fail-closed checks in `src/agent/nodes/assess_risk_and_approval.py:225`; blocked state clears action/snapshot outputs at `src/agent/nodes/assess_risk_and_approval.py:268`; snapshot/evidence/binding failures fail closed at `src/agent/nodes/assess_risk_and_approval.py:932`; route tests cover missing plan/hash/snapshot bindings in `tests/test_graph_routing.py:511`. | closed |
| T-57-01-02 | Elevation of privilege | `risk_gate` LLM output path | mitigate | LLM result is written under injected identity, but deterministic high-risk override runs before binding at `src/agent/nodes/assess_risk_and_approval.py:1205`; route choice remains deterministic in `src/agent/graph.py:71`; approval/auto-allowed bindings are checked at `src/agent/graph.py:160` and `src/agent/graph.py:193`. | closed |
| T-57-01-03 | Repudiation | `assess_risk_and_approval` compatibility wrapper | mitigate | Compatibility metadata records legacy owner, canonical owner, reason, trace projection, validation tests, and delete phase at `src/agent/nodes/assess_risk_and_approval.py:53`; legacy wrapper is labeled compatibility at `src/agent/nodes/assess_risk_and_approval.py:1128`. | closed |
| T-57-01-04 | Information disclosure | Trace and `llm_outputs` identity split | mitigate | Canonical wrapper delegates with `output_key` and `trace_node` set to `risk_gate` at `src/agent/nodes/risk_gate.py:19`; shared implementation writes `llm_outputs` and trace through the injected keys at `src/agent/nodes/assess_risk_and_approval.py:1224`; legacy wrapper uses only legacy identity at `src/agent/nodes/assess_risk_and_approval.py:1128`. | closed |
| T-57-02-01 | Tampering | `route_after_claim_verify` | mitigate | Claim route allowlist is exactly `{"risk_gate", "final_response"}` at `src/agent/routing.py:28`; wrapper falls back to `final_response` on exceptions or unexpected values at `src/agent/routing.py:534`. | closed |
| T-57-02-02 | Elevation of privilege | Claim verification -> risk gate | mitigate | Claim router requires continue plus verified/not-required status and verified action recommendation before `risk_gate` at `src/agent/routing.py:581`; action path rechecks claim bundle allow rules at `src/agent/graph.py:105`; regression tests cover unsupported claims and positive route at `tests/test_graph_routing.py:267`. | closed |
| T-57-02-03 | Denial of service | Graph path-map mismatch | mitigate | Active graph registers `risk_gate` at `src/agent/graph.py:282`; path maps use `risk_gate` for `claim_verify`, risk source, and approval edit rerisk at `src/agent/graph.py:348`; architecture tests compare static route maps and reject legacy destinations at `tests/architecture/test_canonical_graph_baseline.py:143`. | closed |
| T-57-02-04 | Repudiation | Active graph baseline | mitigate | Baseline test requires `risk_gate` and excludes `assess_risk_and_approval` at `tests/architecture/test_canonical_graph_baseline.py:23`; legacy risk row is not in migration active map at `tests/architecture/test_canonical_graph_baseline.py:82`; vocabulary maps old name to `risk_gate` as compatibility only at `src/agent/graph_vocabulary.py:173`. | closed |
| T-57-02-05 | Denial of service | Approval edit rerisk cutover | mitigate | New edit decisions emit `resume_route=CANONICAL_RISK_ROUTE` in event metadata and result at `src/approvals/service.py:535`; current API resume accepts only canonical edit route at `src/api/routers/approvals.py:771`; graph routes trusted edit rerisk to `risk_gate` at `src/agent/graph.py:140`. | closed |
| T-57-03-01 | Spoofing | Ordinary chat approval text | mitigate | Approval-like chat stops before classifier/tools/approval/action in `tests/agent/test_graph.py:1188` and `tests/agent/test_graph.py:1200`; contaminated approval/action authority is cleared on new turn at `src/agent/nodes/receive_request.py:126`. | closed |
| T-57-03-02 | Tampering | API retry reconstruction | mitigate | Retry validates approval decision type, revision, action hash, snapshot hash, expected request/level/assignment versions, edited action, new action hash, and canonical route at `src/api/routers/approvals.py:445` and `src/api/routers/approvals.py:565`; legacy route normalization is Phase 58-marked and read-only at `src/api/routers/approvals.py:779`; mismatch tests are in `tests/test_approval_api.py:1183`. | closed |
| T-57-03-03 | Elevation of privilege | Approval edit rerisk | mitigate | `route_after_approval` sends edit/superseded with canonical route and new hash to `risk_gate`, not `action_draft`, at `src/agent/graph.py:140`; tests assert edit rerisk and reject current legacy edit route at `tests/test_graph_routing.py:594`. | closed |
| T-57-03-04 | Repudiation | Approval resume audit trail | mitigate | ApprovalService writes canonical `resume_route` and new action hash in approval events/results at `src/approvals/service.py:535`; API retry reconstructs `TrustedApprovalResultV1` from persisted event metadata at `src/api/routers/approvals.py:591`; API response echoes `resume_route` from trusted result at `src/api/routers/approvals.py:854`; tests cover canonical and historical retry echo at `tests/test_approval_api.py:884` and `tests/test_approval_api.py:1116`. | closed |
| T-57-03-05 | Tampering | Trusted result schema | mitigate | Graph validates `TrustedApprovalResultV1` and tenant/run/hash/snapshot bindings before routing at `src/agent/graph.py:247`; `approval_gate` independently validates schema and same bindings before setting `approval_result` at `src/agent/nodes/approval_gate.py:28`; invalid payload tests are in `tests/test_approval_gate.py:176`. | closed |
| T-57-04-01 | Repudiation | Trace projection | mitigate | Vocabulary maps `risk_gate` as runtime and `assess_risk_and_approval -> risk_gate` as non-runnable compatibility at `src/agent/graph_vocabulary.py:173`; projection preserves `implementation_node` while adding target fields at `src/agent/graph_vocabulary.py:227`; tests assert no stored-node rewrite at `tests/agent/test_graph_vocabulary.py:291`. | closed |
| T-57-04-02 | Tampering | Eval harness current node list | mitigate | Eval/static guard tests require current fake LLM keys, expected nodes, and patch target to use `risk_gate` and reject legacy current-run authority at `tests/architecture/test_canonical_graph_baseline.py:172`; actual eval harness has `risk_gate` in current patched nodes and fake LLMs at `scripts/eval_agent.py:60` and `scripts/eval_agent.py:171`. | closed |
| T-57-04-03 | Information disclosure | API/SSE risk payload extraction | mitigate | SSE events add `target_node_name` via vocabulary at `src/api/routers/agent_runs.py:1139`; risk payload extraction for current and historical risk nodes emits risk level only, with the historical branch labeled `DELETE_BY_PHASE_58`, at `src/api/routers/agent_runs.py:1176`. | closed |
| T-57-04-04 | Denial of service | Frontend/eval stale node labels | mitigate | Frontend label map includes `risk_gate` and labels legacy as historical/Phase 58 at `frontend/src/components/timeline/TimelineStep.tsx:5`; static tests check frontend labels, eval nodes, and diagnostic mock output at `tests/architecture/test_canonical_graph_baseline.py:162`; diagnostic mock emits `risk_gate` at `scripts/diagnose_latency.py:111`. | closed |
| T-57-05-01 | Repudiation | Docs and debt ledger | mitigate | Current docs describe `risk_gate` current graph and legacy non-active compatibility at `docs/current-langgraph-architecture.md:45` and `docs/current-langgraph-architecture.md:88`; architecture debt records fixed state and Phase 58 residual work at `.planning/ARCHITECTURE-DEBT.md:1330`. | closed |
| T-57-05-02 | Tampering | Validation artifact | mitigate | Validation frontmatter is `nyquist_compliant: true`; approved-entrypoint evidence records pytest, ruff, frontend build, and diff-check commands at `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md:47`; static classifier records 421 hits and `unclassified_rows: 0` at `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md:56`. | closed |
| T-57-05-03 | Elevation of privilege | Approval/risk boundary docs | mitigate | Target docs state `risk_gate` owns risk/action policy and `approval_gate` does not decide auto draft, blocked, or approval-required status at `docs/target-agent-platform-architecture-plan.md:374`; docs restate approval input is structured, not LLM/free text, at `docs/target-agent-platform-architecture-plan.md:1623`; static tests reject approval gate risk/action coupling at `tests/test_approval_gate.py:243`. | closed |
| T-57-05-04 | Denial of service | Phase 58 handoff | mitigate | Validation records the five-wave closeout and static legacy-hit classification with no unclassified rows at `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md:29` and `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md:56`; architecture debt lists specific Phase 58 deletion/reclassification residuals at `.planning/ARCHITECTURE-DEBT.md:1351`. | closed |

## Threat Flags

No unregistered flags.

All five plan summaries report `## Threat Flags` as `None`:

| Summary | Evidence |
|---------|----------|
| 57-01 | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-01-SUMMARY.md:126` |
| 57-02 | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-02-SUMMARY.md:138` |
| 57-03 | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-03-SUMMARY.md:143` |
| 57-04 | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-04-SUMMARY.md:159` |
| 57-05 | `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-05-SUMMARY.md:161` |

## Accepted Risks Log

No accepted risks.

## Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Notes |
|------------|---------------|--------|------|--------|-------|
| 2026-07-08 | 22 | 22 | 0 | Codex gsd-security-auditor | Source/read-only verification against 57-01 through 57-05 threat models, summaries, validation, verification, review, and line-level code/test evidence. |

Supporting closeout artifacts:

| Artifact | Evidence |
|----------|----------|
| Validation | Final approved-entrypoint evidence includes `437 passed, 1 skipped, 29 warnings`, ruff pass, frontend build pass, and diff-check pass in `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md:47`. |
| Verification | Phase verifier reports `status: passed` and `score: "19/19 must-haves verified"` in `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VERIFICATION.md:1`. |
| Review | Code review reports `status: clean`, no findings, and targeted verification pass in `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-REVIEW.md:52`. |

## Sign-Off

- [x] All threats have a disposition.
- [x] All mitigations were verified against implementation or recorded closeout evidence.
- [x] No accepted risks are required.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.
- [x] Implementation files were not modified during this security audit.

**Approval:** verified 2026-07-08
