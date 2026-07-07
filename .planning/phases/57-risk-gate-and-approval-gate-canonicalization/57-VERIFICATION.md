---
phase: 57-risk-gate-and-approval-gate-canonicalization
verified: 2026-07-07T16:28:58Z
status: passed
score: "19/19 must-haves verified"
overrides_applied: 0
---

# Phase 57: Risk Gate and Approval Gate Canonicalization Verification Report

**Phase Goal:** Replace active `assess_risk_and_approval` with canonical `risk_gate` while preserving the separation between action-risk policy and `approval_gate` pending/trusted-resume state machine.
**Verified:** 2026-07-07T16:28:58Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `risk_gate` is the active registered graph node for blocked/manual-review/approval-required/auto-draft decisions. | VERIFIED | `src/agent/graph.py:282` registers `risk_gate`; `tests/architecture/graph_baseline.py:31` includes `risk_gate`; `tests/architecture/test_canonical_graph_baseline.py:23` checks the active set. |
| 2 | `approval_gate` only handles request creation/resume, pending self-loop, edit rerisk, approved draft path, and terminal/failure finalization. | VERIFIED | `src/agent/graph.py:365` maps `approval_gate` to `approval_gate`, `risk_gate`, `action_draft`, and `final_response`; `src/agent/graph.py:133` validates trusted results and routes pending to `approval_gate`, edit to `risk_gate`, approved to `action_draft`, else `final_response`. |
| 3 | Ordinary chat approval text cannot become trusted approval. | VERIFIED | `tests/agent/test_graph.py:1188` and `tests/agent/test_graph.py:1200` cover approval-like chat stopping before tools, approval gate, or action draft; `tests/agent/test_nodes/test_safety_pre_route.py:103` covers standalone approval-like replies. |
| 4 | Active runtime no longer uses `assess_risk_and_approval` as a registered graph node after cutover except explicit temporary compatibility. | VERIFIED | `src/agent/graph.py` has no active `add_node("assess_risk_and_approval")`; `tests/architecture/test_canonical_graph_baseline.py:34` and `tests/agent/test_graph.py:1053` reject it as active. |
| 5 | Current-run risk/action node execution can be called as `risk_gate` and emits `risk_gate` identity. | VERIFIED | `src/agent/nodes/risk_gate.py:19` delegates with `output_key` and `trace_node` set to `risk_gate`; `tests/agent/test_nodes/test_risk_gate.py:42` checks current-run identity and no legacy identity. |
| 6 | Retained `assess_risk_and_approval` behavior is import/test compatibility only and records owner, reason, trace projection, validation, and `DELETE_BY_PHASE_58`. | VERIFIED | `src/agent/nodes/assess_risk_and_approval.py:53` defines legacy/canonical constants and `PHASE_57_COMPATIBILITY_ALIAS`; `tests/agent/test_nodes/test_assess_risk_and_approval.py:244` validates metadata. |
| 7 | Risk policy semantics, fail-closed binding behavior, and Phase 56 claim/RAG safety gates are preserved. | VERIFIED | `src/agent/graph.py:71` fails closed on verification, snapshot, approval-plan, and auto-allowed binding gaps; `tests/agent/test_nodes/test_risk_gate.py:67` and `tests/test_graph_routing.py:535` cover fail-closed paths. |
| 8 | `claim_verify` and `approval_gate` route maps target active `risk_gate` for current rerisk paths. | VERIFIED | `src/agent/graph.py:348` maps `claim_verify` to `risk_gate`; `src/agent/graph.py:365` maps `approval_gate` edit rerisk to `risk_gate`; manual spot-check `graph_static_spotcheck: pass`. |
| 9 | Current router return values no longer use `assess_risk_and_approval` as a normal current-run route. | VERIFIED | `src/agent/routing.py:28` allowlist is `{"risk_gate", "final_response"}`; `src/agent/routing.py:581` returns `risk_gate`; static grep found no `return "assess_risk_and_approval"` in active graph/routing files. |
| 10 | New trusted approval edit rerisk payloads and `route_after_approval` use `risk_gate`. | VERIFIED | `src/approvals/service.py:546` emits `CANONICAL_RISK_ROUTE`; `src/agent/graph.py:140` routes trusted edit/superseded payloads with `resume_route == "risk_gate"` to `risk_gate`; `tests/test_graph_routing.py:594` covers this. |
| 11 | Phase 56 RAG/claim fail-closed gates still prevent unsupported action claims from reaching risk/action paths. | VERIFIED | `src/agent/routing.py:581` requires verified/allowed action recommendation before `risk_gate`; `tests/test_graph_routing.py:274` verifies positive routing and existing negative tests cover unsupported proposed actions. |
| 12 | Historical persisted `resume_route="assess_risk_and_approval"` is accepted only for API retry reconstruction or server-labeled historical compatibility, never ordinary current authority. | VERIFIED | `src/api/routers/approvals.py:779` normalizes persisted legacy retry metadata to `risk_gate`; `_should_resume_graph` at `src/api/routers/approvals.py:771` rejects current legacy edit routes; `tests/test_approval_api.py:1128` and `tests/test_approval_api.py:1233` cover both. |
| 13 | `approval_gate` does not decide risk or create action recommendations/snapshots. | VERIFIED | `src/agent/nodes/approval_gate.py:48` only builds display interrupt payload and validates trusted resume; `tests/test_approval_gate.py:243` AST-checks no risk/action/snapshot runtime coupling. |
| 14 | Current-run vocabulary, API/SSE payloads, frontend labels, eval expected nodes, and diagnostics use `risk_gate`. | VERIFIED | `src/agent/graph_vocabulary.py:173`, `src/api/routers/agent_runs.py:67`, `frontend/src/components/timeline/TimelineStep.tsx:12`, `scripts/eval_agent.py:64`, and `scripts/diagnose_latency.py:112` all use `risk_gate`; diagnostic mock spot-check emitted `risk_gate`. |
| 15 | Historical `assess_risk_and_approval` traces remain readable through compatibility projection labeled for Phase 58 deletion. | VERIFIED | `src/agent/graph_vocabulary.py:174` maps legacy to `risk_gate` as non-runnable compatibility; `src/api/routers/agent_runs.py:1188` preserves risk payload extraction for historical rows with a deletion comment; `tests/agent/test_graph_vocabulary.py:292` covers projection. |
| 16 | Static current-run vocabulary checks reject `assess_risk_and_approval` as runtime/eval/diagnostic authority. | VERIFIED | `tests/architecture/test_canonical_graph_baseline.py:172` rejects legacy eval/current-run surfaces; `tests/architecture/test_canonical_graph_baseline.py:205` checks diagnostic mock output. |
| 17 | Current-source docs describe `risk_gate` as current runtime risk/action owner and `approval_gate` as request/resume-only. | VERIFIED | `README.md:43` and `docs/current-langgraph-architecture.md:5` identify `risk_gate` as current active graph risk owner and legacy names as compatibility only; docs guard in `57-VALIDATION.md` passed. |
| 18 | Architecture debt records Phase 57 delivered state, evidence, and remaining Phase 58 deletion work. | VERIFIED | `.planning/ARCHITECTURE-DEBT.md:1330` records Phase 57 docs/validation closeout and `.planning/ARCHITECTURE-DEBT.md:1352` records Phase 58 residual deletion work. |
| 19 | Phase validation includes the five-plan wave map, approved-entrypoint commands, and static legacy-hit classification. | VERIFIED | `57-VALIDATION.md:27` lists five waves; `57-VALIDATION.md:47` records final commands; `57-VALIDATION.md:56` records 421 legacy hits, 49 files, and `unclassified_rows: 0`. |

**Score:** 19/19 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/agent/nodes/risk_gate.py` | Canonical callable delegating to shared risk/action implementation | VERIFIED | Exists, substantive, imports shared implementation, and calls `_assess_risk_and_approval_with_identity` with canonical identity. |
| `src/agent/nodes/assess_risk_and_approval.py` | Shared implementation plus Phase 58-scoped legacy wrapper | VERIFIED | Exists, substantive, exports legacy wrapper, includes `PHASE_57_COMPATIBILITY_ALIAS` and `DELETE_BY_PHASE_58`. |
| `tests/agent/test_nodes/test_risk_gate.py` | Canonical identity and fail-closed coverage | VERIFIED | Imports and executes `risk_gate`; checks `llm_outputs`, trace, node error, and no-current-legacy identity. |
| `tests/agent/test_nodes/test_assess_risk_and_approval.py` | Legacy compatibility metadata/wrapper coverage | VERIFIED | Tests metadata and direct legacy import/test compatibility behavior. |
| `src/agent/graph.py` | Active graph registration and route maps for `risk_gate` | VERIFIED | Registers `risk_gate`; routes `claim_verify` and approval edit rerisk to `risk_gate`; no active legacy registration. |
| `src/agent/routing.py` | Claim router returns `risk_gate` or `final_response` | VERIFIED | `_CLAIM_VERIFY_ROUTES` and `_route_after_claim_verify` use canonical route values. |
| `src/approvals/service.py` | New edit decisions emit canonical rerisk route | VERIFIED | `CANONICAL_RISK_ROUTE = "risk_gate"` and edit decisions set that route. |
| `src/api/routers/approvals.py` | API resume adapter accepts canonical route and normalizes historical retry metadata | VERIFIED | `_should_resume_graph` accepts only current `risk_gate`; `_canonical_retry_resume_route` normalizes persisted legacy retry only. |
| `tests/architecture/graph_baseline.py` | Static active graph baseline | VERIFIED | Current baseline includes `risk_gate`, excludes `assess_risk_and_approval`, and has canonical edge maps. |
| `tests/architecture/test_canonical_graph_baseline.py` | Architecture guard for active legacy risk node/routes | VERIFIED | Rejects active legacy registration/routes and current eval/diagnostic legacy authority. |
| `tests/architecture/test_phase33_rag_claim_boundaries.py` | Claim/RAG boundary guard updated for `risk_gate` | VERIFIED | Included in final validation suite; preserves side-effect and fail-closed boundary checks. |
| `tests/approvals/test_needs_info_resume.py` | Approval edit/needs-info regressions | VERIFIED | Included in final validation suite and plan artifact check. |
| `tests/approvals/test_service_transitions.py` | ApprovalService edit transition regressions | VERIFIED | Included in final validation suite and plan artifact check. |
| `tests/test_approval_api.py` | Current edit resume, persisted retry, mismatch, and current legacy rejection tests | VERIFIED | Contains historical retry normalization and current legacy rejection coverage. |
| `tests/test_graph_routing.py` | Trusted/untrusted approval and risk route tests | VERIFIED | Covers canonical edit rerisk, current legacy rejection, fail-closed risk routing, and durable snapshot bindings. |
| `src/agent/graph_vocabulary.py` | Runtime `risk_gate` and legacy compatibility alias metadata | VERIFIED | `risk_gate` runtime entry and non-runnable legacy alias to `risk_gate` are present. |
| `src/api/routers/agent_runs.py` | Current API/SSE label and risk payload extraction | VERIFIED | Includes `risk_gate` label, `target_node_name` projection, and historical risk payload compatibility. |
| `frontend/src/components/timeline/TimelineStep.tsx` | Timeline label for `risk_gate` | VERIFIED | Adds `risk_gate` label; legacy label is explicitly historical and marked `DELETE_BY_PHASE_58`. |
| `scripts/eval_agent.py` | Current eval expected nodes and fake LLM patching | VERIFIED | Expected nodes and patch targets use `risk_gate`; static tests reject legacy eval authority. |
| `scripts/diagnose_latency.py` | Diagnostic mock current node names | VERIFIED | Mock report includes `risk_gate`; spot-check output showed no legacy risk node. |
| Docs and planning closeout artifacts | Current-source docs, debt ledger, validation artifact | VERIFIED | Docs, `.planning/ARCHITECTURE-DEBT.md`, and `57-VALIDATION.md` record current `risk_gate` and Phase 58 residuals. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/agent/nodes/risk_gate.py` | `src/agent/nodes/assess_risk_and_approval.py` | Shared helper call | WIRED | GSD key-link check passed; source calls `_assess_risk_and_approval_with_identity`. |
| `tests/agent/test_nodes/test_risk_gate.py` | `src/agent/nodes/risk_gate.py` | Import and execute canonical callable | WIRED | GSD key-link check passed; tests call `risk_gate_module.risk_gate`. |
| `src/agent/routing.py` | `src/agent/graph.py` | `route_after_claim_verify` return value appears in graph path map | WIRED | GSD pattern check missed the cross-file link, but manual source check and `graph_static_spotcheck: pass` verified `risk_gate` return and path-map destination. |
| `src/agent/graph.py` | `tests/architecture/graph_baseline.py` | Static active graph baseline | WIRED | GSD key-link check passed; baseline mirrors active `risk_gate` graph. |
| `src/approvals/service.py` | `src/api/routers/approvals.py` | `ApprovalDecisionResult.resume_payload["resume_route"]` | WIRED | Service emits `risk_gate`; API accepts canonical edit route and rejects current legacy route. |
| `src/api/routers/approvals.py` | `src/agent/graph.py` | Trusted resume payload consumed by `route_after_approval` | WIRED | API constructs trusted resume payload; graph reroutes trusted edit to `risk_gate`. |
| `src/agent/graph_vocabulary.py` | `src/api/routers/agent_runs.py` | `target_graph_name(node_name, kind="node")` | WIRED | API adds `target_node_name` using graph vocabulary. |
| `scripts/eval_agent.py` | `src.agent.nodes.risk_gate` | Fake LLM patch target | WIRED | Eval imports and patches canonical `risk_gate` module. |
| `57-VALIDATION.md` | `.planning/ARCHITECTURE-DEBT.md` | Legacy-hit classification and Phase 58 residual reference | WIRED | Validation and debt ledger both record Phase 57 delivered state and Phase 58 cleanup. |
| `docs/current-langgraph-architecture.md` | `README.md` | Current graph vocabulary | WIRED | Both documents describe current runtime `risk_gate`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/agent/nodes/risk_gate.py` | `llm_outputs["risk_gate"]`, `trace_steps[*].node`, risk/action bindings | Shared risk implementation with LLM/rules/snapshot persistence, using canonical identity parameters | Yes | FLOWING |
| `src/agent/routing.py` -> `src/agent/graph.py` | `route_after_claim_verify` route value | `claim_verification_bundle`, proposed action, verified action recommendation checks | Yes | FLOWING |
| `src/approvals/service.py` -> `src/api/routers/approvals.py` -> `src/agent/graph.py` | Trusted edit `resume_route` and new action hash | ApprovalService decision/event metadata and API retry reconstruction | Yes | FLOWING |
| `src/agent/nodes/approval_gate.py` -> `route_after_approval` | `approval_result` | LangGraph interrupt resume, validated by `TrustedApprovalResultV1` and tenant/run/hash bindings | Yes | FLOWING |
| `src/api/routers/agent_runs.py` -> `frontend/src/components/timeline/TimelineStep.tsx` | `node_name` and `target_node_name` | SSE event construction from stream updates plus graph vocabulary projection | Yes | FLOWING |
| `scripts/eval_agent.py` and `scripts/diagnose_latency.py` | Expected/current node sequences | Eval case expectations and diagnostic mock nodes | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Active static graph exposes `risk_gate`, not legacy registered node/path source. | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... graph_add_node_names ... graph_conditional_edge_mappings ..."` | `graph_static_spotcheck: pass` | PASS |
| Vocabulary maps current and historical risk names correctly. | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... graph_vocabulary_entry ..."` | `vocabulary_spotcheck: pass` | PASS |
| Approval API accepts only current canonical edit resume route as fresh/current authority. | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... _should_resume_graph ..."` | `approval_resume_spotcheck: pass` | PASS |
| Diagnostic mock emits current `risk_gate` node name. | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/diagnose_latency.py --mock \| rg 'risk_gate\|assess_risk_and_approval'` | Output contained `risk_gate` and no legacy risk node. | PASS |
| Approval pending self-loop remains routable. | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... route_after_approval pending ..."` | `approval_pending_self_loop_spotcheck: pass` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAGM-08 | 57-01 through 57-05 | `risk_gate` replaces active `assess_risk_and_approval` graph naming and preserves separation between deterministic risk/action policy and `approval_gate` pending/trusted-resume state machine. | SATISFIED | `.planning/REQUIREMENTS.md:60` and `.planning/REQUIREMENTS.md:103` mark complete; code evidence verifies active graph, routing, approval boundary, projection, docs, validation, and tests. |

No orphaned Phase 57 requirement IDs were found. `.planning/REQUIREMENTS.md` maps only `CAGM-08` to Phase 57; `CAGM-09` is mapped to Phase 58.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | No blocker or warning anti-patterns found in touched runtime surfaces. Empty return/default scans were helper fallbacks, API payload initialization, or tests/fixtures. | None | No impact. |

### Human Verification Required

None. This phase is backend/architecture canonicalization with automated UAT, static guardrails, code review, final pytest evidence, ruff, frontend build, and verifier spot-checks.

### Gaps Summary

No blocking gaps found. All ROADMAP success criteria, plan-level must-haves, declared artifacts, key links, and CAGM-08 requirement coverage are verified. Phase 58 retains explicitly documented no-debt cleanup for remaining compatibility aliases and historical projection surfaces; that residual work is not a Phase 57 gap.

---

_Verified: 2026-07-07T16:28:58Z_
_Verifier: Codex (gsd-verifier)_
