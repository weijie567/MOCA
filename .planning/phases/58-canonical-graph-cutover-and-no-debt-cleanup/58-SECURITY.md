---
phase: 58
slug: canonical-graph-cutover-and-no-debt-cleanup
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-08
updated: 2026-07-08
---

# Phase 58 Security Verification

## Summary

| Metric | Count |
|--------|-------|
| Threats in plan registers | 37 |
| Mitigated and closed | 36 |
| Accepted risks | 1 |
| Open threats | 0 |
| ASVS level | 1 |

Scope verified: `58-01-PLAN.md` through `58-10-PLAN.md`, `58-01-SUMMARY.md` through `58-10-SUMMARY.md`, `58-VALIDATION.md`, `58-REVIEW.md`, `58-REVIEW-FIX.md`, and the implementation/test files needed to verify the declared mitigation patterns only.

## Trust Boundaries

| Plan | Trust boundaries summarized |
|------|-----------------------------|
| 58-01 | Source graph to static tests; historical trace names to graph vocabulary; strict classifier to closeout; public routing helpers to active route authority. |
| 58-02 | Legacy wrapper modules to canonical node modules; canonical risk node to approval/action authority; recommendation generation to RAG/citation boundary. |
| 58-03 | Deleted recommendation/risk wrappers to canonical node modules; direct node tests to runtime identity; static guards to cleanup proof. |
| 58-04 | Intent/session wrapper modules to canonical modules; legacy direct tests to canonical tests; classifier to cleanup proof. |
| 58-05 | Slot/memory wrapper modules to canonical modules; legacy direct tests to canonical tests; classifier to cleanup proof. |
| 58-06 | Test fixtures to production node modules; routing tests to graph route authority; graph tests to active runtime semantics. |
| 58-07 | Integration tests to production node modules; architecture tests to vocabulary contract; static guards to source cleanup. |
| 58-08 | Stored trace rows to API projection; SSE payload to frontend display; eval manifest to release gates. |
| 58-09 | Persisted approval metadata to API resume payload; API resume payload to LangGraph route; ordinary chat to approval resume. |
| 58-10 | Runtime implementation to docs; validation evidence to requirements closeout; planning metadata to downstream workflow. |

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-58-01-01 | Tampering | `src/agent/graph_vocabulary.py` | mitigate | closed | Runtime `_ENTRIES` contain final canonical nodes/routers only in `src/agent/graph_vocabulary.py:46`; no active compatibility aliases in `tests/agent/test_graph_vocabulary.py:96`. |
| T-58-01-02 | Repudiation | `tests/architecture/test_canonical_graph_baseline.py` | mitigate | closed | Final no-debt gate asserts exact final graph, no public legacy route defs, canonical route values, and runtime vocabulary in `tests/architecture/test_canonical_graph_baseline.py:249`. |
| T-58-01-03 | Repudiation / Tampering | `scripts/classify_phase58_legacy_hits.py` | mitigate | closed | Classifier scans legacy terms and roots in `scripts/classify_phase58_legacy_hits.py:13`, fails strict mode on active/current/unclassified rows in `scripts/classify_phase58_legacy_hits.py:117`, and returned `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`. |
| T-58-01-04 | Information disclosure | historical trace projection | accept | accepted | Historical stored names remain non-secret read/projection data only; mappings are non-runnable `historical_projection` entries in `src/agent/graph_vocabulary.py:74` and projected with raw implementation identity in `src/agent/graph_vocabulary.py:178`. Accepted risk logged below. |
| T-58-01-05 | Spoofing / Tampering | `src/agent/routing.py` | mitigate | closed | Public current routers are canonical `route_after_contextual_intent` and `route_after_slot_resolution` in `src/agent/routing.py:67` and `src/agent/routing.py:83`; final gate rejects public legacy defs in `tests/architecture/test_canonical_graph_baseline.py:253`. |
| T-58-02-01 | Tampering | `src/agent/nodes/recommendation_generation.py` | mitigate | closed | Canonical graph registers `recommendation_generation` in `src/agent/graph.py:280`; implementation owns citation validation/material claims in `src/agent/nodes/recommendation_generation.py:176`; tests assert canonical identity and no legacy output key in `tests/agent/test_nodes/test_recommendation_generation.py:284`. |
| T-58-02-02 | Elevation of privilege | `src/agent/nodes/risk_gate.py` | mitigate | closed | Canonical graph registers `risk_gate` in `src/agent/graph.py:282`; risk gate binds action hash, safety snapshot, business facts, and evidence refs in `src/agent/nodes/risk_gate.py:695`; tests cover approval bindings and fail-closed paths in `tests/agent/test_nodes/test_risk_gate.py:410`. |
| T-58-02-03 | Repudiation | legacy wrapper modules | mitigate | closed | Deleted wrapper path guards passed; later deletion tests assert removed recommendation/risk wrapper and direct-test files in `58-03-SUMMARY.md:93`, with canonical tests retained. |
| T-58-03-01 | Tampering | deleted recommendation/risk wrappers | mitigate | closed | Deleted wrapper files are absent and graph/tests use canonical modules; verification recorded in `58-03-SUMMARY.md:92` and architecture debt closeout in `.planning/ARCHITECTURE-DEBT.md:1355`. |
| T-58-03-02 | Repudiation | legacy direct test filenames | mitigate | closed | Legacy direct test filename deletion guards passed in `58-03-SUMMARY.md:93`; canonical replacements are in `tests/agent/test_nodes/test_recommendation_generation.py` and `tests/agent/test_nodes/test_risk_gate.py`. |
| T-58-03-03 | Tampering | static wrapper guards | mitigate | closed | Static guards reject deleted wrapper imports and Phase 56/57 compatibility markers in `58-03-SUMMARY.md:94` through `58-03-SUMMARY.md:97`; strict classifier passed. |
| T-58-04-01 | Tampering | intent/session wrapper modules | mitigate | closed | Intent/session wrapper deletion guards are in `tests/agent/test_nodes/test_contextual_intent_resolve.py:44` and `tests/agent/test_nodes/test_session_context_load.py:76`; canonical graph nodes are registered in `src/agent/graph.py:299`. |
| T-58-04-02 | Repudiation | legacy-named direct tests | mitigate | closed | Legacy intent/session direct test filenames are asserted absent in `tests/agent/test_nodes/test_contextual_intent_resolve.py:44` and `tests/agent/test_nodes/test_session_context_load.py:76`; focused verification passed in `58-04-SUMMARY.md:116`. |
| T-58-04-03 | Tampering | classifier categories | mitigate | closed | Strict classifier includes `intent_classification` in `scripts/classify_phase58_legacy_hits.py:13`; regression proves runtime alias rows fail strict mode in `tests/architecture/test_canonical_graph_baseline.py:308`. |
| T-58-05-01 | Tampering | slot/memory wrapper modules | mitigate | closed | Slot/memory wrapper deletion guards are in `tests/agent/test_nodes/test_slot_resolution_gate.py:100` and `tests/agent/test_memory_context_load.py:87`; canonical memory output drops legacy helper metrics in `tests/agent/test_memory_context_load.py:129`. |
| T-58-05-02 | Repudiation | legacy-named direct tests | mitigate | closed | `test_extract_slots.py` and memory wrapper tests are asserted absent in `tests/agent/test_nodes/test_slot_resolution_gate.py:100` and `58-05-SUMMARY.md:117`. |
| T-58-05-03 | Tampering | classifier categories | mitigate | closed | Strict classifier passed with `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, and `unclassified_rows=0`; memory/slot canonical output tests reject legacy output keys in `tests/agent/test_memory_context_load.py:164` and `tests/agent/test_nodes/test_slot_resolution_gate.py:126`. |
| T-58-06-01 | Tampering | `tests/conftest.py` and graph tests | mitigate | closed | Graph tests assert active nodes exclude legacy graph names in `tests/agent/test_graph.py:1017`; summary records canonical patch seam migration and focused suite pass in `58-06-SUMMARY.md:95`. |
| T-58-06-02 | Spoofing / Tampering | routing tests | mitigate | closed | Routing tests enforce canonical helper names and route values only in `tests/test_graph_routing.py:234`; public current route helpers are canonical in `src/agent/routing.py:67` and `src/agent/routing.py:83`. |
| T-58-06-03 | Repudiation | active graph behavior tests | mitigate | closed | Graph/routing focused suites passed in `58-06-SUMMARY.md:97`; final broad backend gate passed in `58-VALIDATION.md:113`. |
| T-58-07-01 | Tampering | integration patch imports | mitigate | closed | Integration patch seams retarget canonical modules; representative guards include `tests/agent/test_phase22_recommendation_integration.py:26`, `tests/agent/test_phase22_action_boundary.py:21`, `tests/test_interception_rate.py:18`, and `tests/knowledge/test_facade_integration.py:31`. |
| T-58-07-02 | Repudiation | architecture compatibility expectations | mitigate | closed | Active vocabulary tests distinguish historical projections from runtime vocabulary in `tests/agent/test_graph_vocabulary.py:82`; architecture no-debt gate checks canonical route values in `tests/architecture/test_canonical_graph_baseline.py:257`. |
| T-58-07-03 | Tampering | static import/path guards | mitigate | closed | Current source/test/script/eval no-hit scans and strict classifier passed in `58-07-SUMMARY.md:137` through `58-07-SUMMARY.md:139`. |
| T-58-08-01 | Repudiation / Tampering | trace/API projection | mitigate | closed | Trace projection preserves `implementation_node` and emits canonical target/status fields in `src/agent/graph_vocabulary.py:178`; repository timelines project target nodes in `src/repositories/trace_repo.py:66`; trace/API projection tests passed. |
| T-58-08-02 | Tampering | `frontend/src/components/timeline/TimelineStep.tsx` | mitigate | closed | Frontend timeline labels current canonical nodes only, including `risk_gate`, in `frontend/src/components/timeline/TimelineStep.tsx:4`; frontend remains display-only over server-provided `node_name` in `frontend/src/components/timeline/TimelineStep.tsx:58`. |
| T-58-08-03 | Tampering | `eval/replay/dev-contract-manifest.v1.json` | mitigate | closed | Replay manifest references canonical `tests/agent/test_nodes/test_risk_gate.py` and has no deleted wrapper test paths in `eval/replay/dev-contract-manifest.v1.json:147`; eval tests verified in `58-08-SUMMARY.md:106`. |
| T-58-08-04 | Repudiation | historical trace tests | mitigate | closed | Historical trace tests assert old stored names map to non-runnable historical projections, e.g. risk history in `tests/agent/test_trace.py:289` and API timeline projection in `tests/test_trace_api.py:439`. |
| T-58-09-01 | Spoofing / Elevation of privilege | `src/api/routers/approvals.py` | mitigate | closed | Historical retry mapping is one constant to canonical `risk_gate` in `src/api/routers/approvals.py:53`; retry reconstruction requires approval/run/hash/version binding checks before emitting trusted resume payload in `src/api/routers/approvals.py:453` and `src/api/routers/approvals.py:565`. |
| T-58-09-02 | Elevation of privilege | `src/agent/graph.py::route_after_approval` | mitigate | closed | `route_after_approval` only reroutes edits to `risk_gate` when `_trusted_approval_result` passes and a new action payload hash exists in `src/agent/graph.py:133`; tenant/run/hash mismatches fail closed in `src/agent/graph.py:247`. |
| T-58-09-03 | Tampering | approval API tests | mitigate | closed | Fresh/current legacy resume route authority is rejected in `tests/test_graph_routing.py:656`; persisted historical retry metadata normalizes to `risk_gate` in `tests/test_approval_api.py:1116`; focused approval regression run passed `10 passed`. |
| T-58-09-04 | Repudiation | retry compatibility comments | mitigate | closed | Compatibility is named historical persisted data read only: `_historical_retry_resume_route_to_canonical` docstring at `src/api/routers/approvals.py:779` and guard test at `tests/test_approval_api.py:1241`. |
| T-58-10-01 | Repudiation | docs and README | mitigate | closed | Current docs record historical read boundaries and current route authority in `docs/current-langgraph-architecture.md:88`; strict classifier reports current docs authority zero in `58-VALIDATION.md:61`. |
| T-58-10-02 | Repudiation | `.planning/ARCHITECTURE-DEBT.md` | mitigate | closed | Chinese closeout entry records fixed state, evidence, historical-read caveats, and no remaining active runtime risk in `.planning/ARCHITECTURE-DEBT.md:1343`. |
| T-58-10-03 | Tampering | `58-VALIDATION.md` | mitigate | closed | Validation records exact approved strict classifier command/output in `58-VALIDATION.md:61`, broad backend gate in `58-VALIDATION.md:113`, and package metadata proof in `58-VALIDATION.md:177`. |
| T-58-10-04 | Repudiation | `docs/contract-spec.md` divergence | mitigate | closed | Validation records no-edit rationale in `58-VALIDATION.md:109`; contract spec current target graph includes canonical nodes and routers in `docs/contract-spec.md:434`. |
| T-58-10-05 | Tampering | planning metadata | mitigate | closed | Plan 58-10 summary records broad verification, classifier pass, current-doc assertion, metadata proof, and diff check before closeout in `58-10-SUMMARY.md:54` through `58-10-SUMMARY.md:61`. |
| T-58-10-06 | Tampering | `moca.egg-info/SOURCES.txt` | mitigate | closed | Package metadata proof recorded `tracked=False stale_hits=0` in `58-VALIDATION.md:177`; independent `git ls-files --error-unmatch moca.egg-info/SOURCES.txt` returned not tracked. |

## Accepted Risk Log

| Threat ID | Risk | Decision | Conditions | Residual risk |
|-----------|------|----------|------------|---------------|
| T-58-01-04 | Historical graph node/router names may remain in stored trace rows, old planning/docs, and projection/readability surfaces. | accepted | Accepted only as non-secret historical readability data. It must not become active graph registration, current route value, current resume route, current eval node, or current docs authority. Strict classifier must keep `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, and `unclassified_rows=0`. | Future edits could reintroduce old names as current authority; guarded by classifier, graph baseline tests, approval route tests, and docs review. |

## Threat Flags

No unregistered threat flags were found. Summaries 58-02 through 58-09 explicitly report no new threat flags; 58-01 and 58-10 did not contain separate unregistered flag entries, and their declared threat-register items are covered above.

## Verification Commands

| Command | Result |
|---------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` | Passed during this audit: `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only tests/test_approval_api.py::test_decide_edit_retry_normalizes_persisted_legacy_route_before_graph_resume tests/test_graph_routing.py::test_route_after_approval_sends_edit_to_risk_reroute_not_action_draft tests/test_graph_routing.py::test_route_after_approval_rejects_legacy_risk_resume_route_authority tests/test_graph_routing.py::test_route_after_approval_fails_closed_on_hash_mismatch tests/test_graph_routing.py::test_route_after_approval_fails_closed_when_tenant_or_run_mismatches_state tests/test_graph_routing.py::test_route_after_approval_fails_closed_when_revision_binding_missing -q --tb=short` | `10 passed, 1 warning`. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope tests/architecture/test_canonical_graph_baseline.py::test_phase58_legacy_hit_classifier_exposes_main_and_strict_report_fields tests/architecture/test_canonical_graph_baseline.py::test_phase58_legacy_hit_classifier_strict_fails_active_runtime_rows tests/architecture/test_canonical_graph_baseline.py::test_phase58_legacy_hit_classifier_strict_fails_intent_classification_runtime_alias tests/agent/test_graph_vocabulary.py::test_active_vocabulary_has_no_compatibility_alias_rows_or_phase58_delete_markers tests/test_graph_routing.py::test_phase58_routing_tests_use_canonical_helpers_and_route_values_only -q --tb=short` | `6 passed, 1 warning`. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py::test_trace_summary_projects_historical_stored_graph_names_without_rewriting_rows tests/agent/test_trace.py::test_trace_summary_projects_phase55_memory_runtime_and_historical_stored_names tests/agent/test_trace.py::test_trace_summary_projects_phase56_recommendation_runtime_and_historical_stored_names tests/agent/test_trace.py::test_trace_summary_projects_phase57_risk_runtime_and_historical_stored_names tests/test_trace_api.py::test_build_timeline_projects_historical_router_step_target_node tests/test_trace_api.py::test_build_timeline_projects_phase57_risk_runtime_and_historical_node_identities tests/test_agent_runs_api.py::test_sse_event_projects_phase57_risk_gate_node_and_label_current_runtime tests/test_agent_runs_api.py::test_sse_event_preserves_unexpected_legacy_risk_node_without_translation -q --tb=short` | `9 passed, 1 warning`. |

## Security Audit Trail

| Date | Auditor | Scope | Result |
|------|---------|-------|--------|
| 2026-07-08 | Codex security auditor | Verified all declared Phase 58 threat-register mitigations and accepted risk disposition against plans, summaries, validation, review artifacts, implementation slices, classifier output, and focused approved-entrypoint tests. | 37/37 threats closed or accepted; `threats_open=0`; ASVS Level 1. |

## Sign-off Checklist

- [x] All Phase 58 `T-58-*` threats from plans 58-01 through 58-10 are represented.
- [x] Each `mitigate` disposition has code, test, validation, or classifier evidence.
- [x] Accepted risk log contains only T-58-01-04.
- [x] Summary threat flags were reviewed; no unregistered flags were found.
- [x] Historical graph names are accepted only as bounded historical/projection/readability references classified by strict mode.
- [x] Approval retry historical route mapping emits canonical `risk_gate` only after server-side binding/version/hash checks.
- [x] Fresh/current legacy approval resume values fail closed.
- [x] Review modified only this SECURITY artifact; implementation/source/test files were not edited.
- [x] `threats_open: 0`.
