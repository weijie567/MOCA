---
phase: 55
slug: memory-context-load-cutover
status: verified
security_enforcement: true
asvs_level: 1
block_on: high_severity_unless_mitigated
threats_total: 17
threats_closed: 17
threats_open: 0
accepted_risks: 0
transferred_risks: 0
created: 2026-07-07
updated: 2026-07-07
---

# Phase 55 — Security

Per-phase security verification for `memory_context_load` cutover. Scope is limited to threats declared in:

- `.planning/phases/55-memory-context-load-cutover/55-01-PLAN.md`
- `.planning/phases/55-memory-context-load-cutover/55-02-PLAN.md`
- `.planning/phases/55-memory-context-load-cutover/55-03-PLAN.md`

No implementation files were modified during this audit.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Reviewed memory scope boundary | `memory_context_load` delegates storage/service semantics to `reviewed_memory_context_retrieve` / `MemoryContextService`, which require trusted context and actor merchant scope. | Long-term preference memory, reviewed case memory, active CWC context. |
| Runtime graph boundary | Active runtime route is `slot_resolution_gate -> memory_context_load -> investigate`; `long_term_memory_retrieve` is not an active registered graph node. | Graph route decisions, trace steps, node metrics. |
| Authority boundary | Memory context is contextual-only. It cannot satisfy evidence, business fact, approval, action, or replay DTO contracts. | Memory labels/refs/metrics consumed by downstream claim/risk/action logic. |
| Trace/API projection boundary | Current runtime node is `memory_context_load`; legacy/helper names are retained compatibility surfaces projected to the canonical owner. | Agent run traces, SSE events, target graph names. |
| Deferred migration boundary | Phase 56/57 active legacy rows remain active by design; Phase 58 final no-debt cleanup remains deferred. | `generate_recommendation`, `assess_risk_and_approval`, retained Phase 55 aliases/wrappers. |

## Threat Register

| Threat ID | Category | Severity | Disposition | Status | Evidence |
|-----------|----------|----------|-------------|--------|----------|
| T-55-01-01 | Information Disclosure / Elevation of Privilege | HIGH | mitigate | closed | Canonical node delegates to reviewed-memory helper (`src/agent/nodes/memory_context_load.py:32`); helper passes trusted context to service (`src/agent/nodes/reviewed_memory_context_retrieve.py:63`); service fails closed for missing trusted context/scope and denied scopes (`src/memory/context_service.py:136`, `src/memory/context_service.py:147`, `src/memory/context_service.py:168`, `src/memory/context_service.py:446`); trusted-scope tests pass. |
| T-55-01-02 | Tampering | HIGH | mitigate | closed | Canonical metrics set `authority_class: contextual_only` and finite usage labels (`src/agent/nodes/memory_context_load.py:66`, `src/agent/nodes/memory_context_load.py:77`); tests assert exact labels and absence of legacy/helper metrics (`tests/agent/test_memory_context_load.py:144`). |
| T-55-01-03 | Elevation of Privilege | HIGH | mitigate | closed | Boundary tests reject memory metrics as `EvidenceRefV1`, `BusinessFactRefV1`, approval/action DTOs, and replay events (`tests/agent/test_memory_evidence_boundary.py:533`); contextual refs cannot authorize claims/actions (`tests/agent/test_memory_evidence_boundary.py:678`). |
| T-55-01-04 | Denial of Service | MEDIUM | mitigate | closed | Missing trusted context skips without exception (`tests/agent/test_memory_context_load.py:221`); service errors become `reviewed_memory_unavailable` and node errors are mapped to canonical node (`tests/agent/test_memory_context_load.py:235`); source classifier distinguishes unavailable/skipped (`src/agent/nodes/memory_context_load.py:94`). |
| T-55-01-05 | Repudiation | MEDIUM | mitigate | closed | Direct canonical trace maps helper node to `memory_context_load` (`src/agent/nodes/memory_context_load.py:104`); test asserts trace node and metrics JSON (`tests/agent/test_memory_context_load.py:160`). |
| T-55-02-01 | Tampering | HIGH | mitigate | closed | Router allowlist includes canonical route (`src/agent/routing.py:40`); active graph registers `memory_context_load`, path map targets it, and direct edge flows to `investigate` (`src/agent/graph.py:287`, `src/agent/graph.py:320`, `src/agent/graph.py:329`); architecture baseline covers route maps (`tests/architecture/test_canonical_graph_baseline.py:93`). |
| T-55-02-02 | Repudiation | HIGH | mitigate | closed | Active graph baseline includes `memory_context_load` and excludes `long_term_memory_retrieve` (`tests/architecture/test_canonical_graph_baseline.py:19`); source confirms active registration only for canonical node (`src/agent/graph.py:287`). |
| T-55-02-03 | Elevation of Privilege | HIGH | mitigate | closed | Plan 55-02 only changes routing identity; authority stays contextual-only through Plan 55-01 controls (`src/agent/nodes/memory_context_load.py:68`) and boundary tests (`tests/agent/test_memory_evidence_boundary.py:533`, `tests/agent/test_memory_evidence_boundary.py:678`). |
| T-55-02-04 | Information Disclosure | HIGH | mitigate | closed | Memory route preserves reviewed-memory service scope filtering; service denies out-of-scope merchants and unsupported tenant/global requests (`src/memory/context_service.py:157`, `src/memory/context_service.py:431`, `src/memory/context_service.py:526`); tests cover denied/out-of-authority scope (`tests/agent/test_reviewed_memory_context_retrieve.py:163`, `tests/memory/test_reviewed_memory_context_boundary.py:227`). |
| T-55-02-05 | Scope Creep / Tampering | MEDIUM | mitigate | closed | Phase 56/57 active rows remain unchanged (`src/agent/graph.py:290`, `src/agent/graph.py:292`); architecture baseline preserves active legacy migration rows and Phase 58 skip marker (`tests/architecture/test_canonical_graph_baseline.py:63`, `tests/architecture/test_canonical_graph_baseline.py:166`). |
| T-55-02-06 | Denial of Service | MEDIUM | mitigate | closed | Router catches exceptions and unknown routes to `clarification_gate` (`src/agent/routing.py:95`); malformed/missing slot state also fails closed (`src/agent/routing.py:482`, `src/agent/routing.py:487`, `src/agent/routing.py:493`); baseline covers router totality (`tests/architecture/test_canonical_graph_baseline.py:97`). |
| T-55-03-01 | Repudiation | HIGH | mitigate | closed | Vocabulary marks legacy/helper names as compatibility aliases with Phase 55 reason codes and `DELETE_BY_PHASE_58`, while `memory_context_load` is runtime (`src/agent/graph_vocabulary.py:48`, `src/agent/graph_vocabulary.py:98`, `src/agent/graph_vocabulary.py:114`); tests assert projection (`tests/agent/test_graph_vocabulary.py:175`, `tests/agent/test_trace.py:204`). |
| T-55-03-02 | Information Disclosure | MEDIUM | mitigate | closed | SSE label is concise (`src/api/routers/agent_runs.py:63`); SSE event adds only target node projection (`src/api/routers/agent_runs.py:1150`) and step payload extraction has no memory raw-content branch (`src/api/routers/agent_runs.py:1174`); API test rejects raw memory payload keys (`tests/test_agent_runs_api.py:1008`). |
| T-55-03-03 | Tampering | HIGH | mitigate | closed | Current-source docs distinguish runtime facts from target contract and compatibility surfaces (`docs/current-langgraph-architecture.md:3`, `docs/current-langgraph-architecture.md:70`, `docs/current-langgraph-architecture.md:88`); architecture debt ledger records Phase 55 fixes and residual deferred work (`.planning/ARCHITECTURE-DEBT.md:407`, `.planning/ARCHITECTURE-DEBT.md:433`, `.planning/ARCHITECTURE-DEBT.md:466`). |
| T-55-03-04 | Denial of Service | MEDIUM | mitigate | closed | Artifact command scan passed with no bare `pytest` or bare `python -m pytest` command in Phase 55 summaries/review/verification/validation; current audit commands use `UV_CACHE_DIR=/tmp/uv-cache uv run ...`. |
| T-55-03-05 | Scope Creep / Tampering | HIGH | mitigate | closed | Active graph still registers Phase 56/57 legacy nodes and does not execute Phase 58 cleanup (`src/agent/graph.py:290`, `src/agent/graph.py:292`; `tests/architecture/test_canonical_graph_baseline.py:63`, `tests/architecture/test_canonical_graph_baseline.py:166`); docs/debt explicitly defer those scopes (`docs/current-langgraph-architecture.md:106`, `.planning/ARCHITECTURE-DEBT.md:461`). |
| T-55-03-06 | Integrity | MEDIUM | mitigate | closed | Retained aliases have owner/reason/delete metadata (`src/agent/graph_vocabulary.py:48`, `src/agent/graph_vocabulary.py:98`); docs compatibility table states validation and Phase 58 delete phase (`docs/current-langgraph-architecture.md:92`, `docs/current-langgraph-architecture.md:104`); tests assert uniqueness and delete-phase reason codes (`tests/agent/test_graph_vocabulary.py:197`). |

## Accepted Risks Log

No accepted risks. All Phase 55 threat-model entries use `mitigate`; no `accept` or `transfer` dispositions were present.

## Unregistered Flags

None. `55-03-SUMMARY.md` declares no threat flags, and `55-01-SUMMARY.md` / `55-02-SUMMARY.md` did not contain additional `## Threat Flags` entries.

## Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-07 | 17 | 17 | 0 | Codex security auditor |

Commands run during this audit:

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_context_load.py tests/agent/test_memory_evidence_boundary.py::test_memory_context_load_metrics_reject_authority_dto_parsing tests/agent/test_memory_evidence_boundary.py::test_contextual_only_memory_refs_do_not_become_evidence_ref_v1_or_business_authority tests/agent/test_graph.py::test_graph_compiles_with_investigate tests/agent/test_graph.py::test_canonical_reviewed_memory_hint_reaches_memory_context_load tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py::test_trace_summary_projects_phase55_memory_runtime_and_compatibility_names tests/test_agent_runs_api.py::test_sse_event_projects_runtime_memory_context_load_node_identity_without_memory_payload -q --tb=short
```

Result: `69 passed, 1 skipped, 3 warnings`.

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_fails_closed_without_trusted_context tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_fails_closed_without_actor_merchant_scope tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_denies_out_of_scope_merchant tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_does_not_use_session_memory_to_create_scope tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_does_not_use_candidate_slots_to_create_scope tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_uses_actor_scope_for_canonical_reviewed_memory_hint -q --tb=short
```

Result: `6 passed, 1 warning`.

```text
UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
# Static mitigation scan over graph/router/vocabulary/API/docs/debt and Phase 55 artifact command forms.
PY
```

Result: `phase55_security_static_checks=passed checks=26 artifacts_scanned=7`.

Earlier static audit attempts used overly narrow literal assertions and failed before the final corrected scan. Those local validation-script false starts are recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` and are not implementation security gaps.

## Sign-Off

- [x] All declared HIGH/MEDIUM threats classified.
- [x] All `mitigate` dispositions verified against implementation and tests.
- [x] No `accept` risks required.
- [x] No `transfer` risks required.
- [x] Threat flags incorporated; no unregistered flags.
- [x] `threats_open: 0` confirmed.
