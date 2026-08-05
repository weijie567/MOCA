---
phase: 54
slug: slot-resolution-gate-cutover
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-07
completed: 2026-07-07
---

# Phase 54 - Validation Strategy

> Phase 54 验证重点：证明 active runtime graph 已从 `extract_slots` / `route_after_slots` 切到 canonical `slot_resolution_gate` / `route_after_slot_resolution`，同时 slot provenance、fail-closed routing、Phase 53 WR-01 invariant 和 legacy trace/API projection 仍可验证。

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py -q` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_session_memory_integration.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_canonical_graph_baseline.py -q` |
| **Estimated runtime** | ~90 seconds focused suite, excluding optional DB-backed API tests |

---

## Sampling Rate

- **After every task commit:** Run the narrow command mapped below for the touched surface.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/architecture/test_canonical_graph_baseline.py -q`.
- **Before `$gsd-verify-work`:** Run the full suite command above plus `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py`.
- **Max feedback latency:** 120 seconds for focused non-DB validation.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | CAGM-05 | T-54-01-01 | Current-turn and inherited slots are resolved by deterministic gate rules with explicit provenance, not by LLM authority. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py -q` | `tests/agent/test_required_slots.py` ✅ / `tests/agent/test_nodes/test_receive_request.py` ✅ / `tests/agent/test_nodes/test_slot_resolution_gate.py` ✅ | ✅ green |
| 54-01-02 | 01 | 1 | CAGM-05 | T-54-01-02 | Missing, invalidated, stale, incompatible, unresolved conflicting, malformed, LLM extraction error, or policy-mismatch slot state fails closed to clarification; validated current-turn replacement is tested separately as override-with-provenance. | unit/router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py -q` | ✅ existing | ✅ green |
| 54-02-01 | 02 | 2 | CAGM-05 | T-54-02-01 | Active graph registers `slot_resolution_gate`, not `extract_slots`, and does not introduce `slot_extraction`. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` | ✅ | ✅ green |
| 54-02-02 | 02 | 2 | CAGM-05 | T-54-02-02 | `route_after_contextual_intent` returns `slot_resolution_gate` for slot-required intents, and active slot router is `route_after_slot_resolution`. | router/graph | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph.py::test_all_router_return_keys_have_edges -q` | ✅ | ✅ green |
| 54-02-03 | 02 | 2 | CAGM-05 | T-54-02-03 | Slot-satisfied graph paths reach `investigate`; reviewed-memory compatibility still reaches `long_term_memory_retrieve`; unsafe slot paths reach `clarification_gate`. | graph integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py::test_refund_path_preserves_business_context_facts tests/agent/test_graph.py::test_same_thread_session_memory_active_slots_feed_investigate tests/agent/test_graph.py::test_wrong_thread_or_stale_session_memory_routes_to_clarification tests/agent/test_graph.py::test_canonical_reviewed_memory_hint_reaches_existing_long_term_memory_node -q` | ✅ | ✅ green |
| 54-03-01 | 03 | 3 | CAGM-05 | T-54-03-01 | Runtime vocabulary marks canonical slot node/router as runtime and legacy names as compatibility aliases for historical projection only. | unit/API trace | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q` | ✅ | ✅ green |
| 54-03-02 | 03 | 3 | CAGM-05 | T-54-03-02 | Final artifact scan proves no new disallowed test entrypoint and no active `slot_extraction` graph node. | static scan | final static graph scan and artifact entrypoint scan, see evidence below | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/agent/test_nodes/test_slot_resolution_gate.py` - canonical node unit tests for provenance payload, trace node name, legacy compatibility fields, and error/fail-closed output.
- [x] `tests/agent/test_required_slots.py` - update route imports/assertions to prefer `route_after_slot_resolution`, while preserving one compatibility delegate assertion for `route_after_slots` if retained.
- [x] `tests/architecture/graph_baseline.py` - update active graph baseline to remove active `extract_slots` and add active `slot_resolution_gate`.
- [x] `tests/test_graph_routing.py`, `tests/agent/test_intent_routing.py`, `tests/agent/test_graph.py`, `tests/agent/test_nodes/test_contextual_intent_resolve.py`, and `tests/agent/test_session_memory_integration.py` - update active slot destination expectations from `extract_slots` to `slot_resolution_gate`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | CAGM-05 | Phase 54 graph/router/node behavior has automated validation surfaces. | All Phase 54 acceptance should be covered by focused pytest, ruff, and static scans. |

---

## Final Execution Evidence

### Handled Validation Failures

- Initial Task 3 full focused suite run failed because `tests/agent/test_session_memory_integration.py::test_pending_slot_short_reply_uses_pre_intent_same_thread_session_context` still asserted active `extract_slots`. This was corrected to assert active `slot_resolution_gate`; the compatibility wrapper test for `extract_slots` remains.
- Two local validation command issues were caused by shell quoting around Markdown backticks in scan commands. They were logged in `.planning/LOCAL-VALIDATION-ISSUES.md` and rerun with safe quoting.

Initial failed focused suite output:

```text
1 failed, 1451 passed, 1 skipped, 35 warnings in 57.42s
```

### Final Green Commands

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_session_memory_integration.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short`

```text
1452 passed, 1 skipped, 35 warnings in 56.07s
```

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q --tb=short`

```text
1 passed, 1 warning in 0.02s
```

`UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/api/routers/agent_runs.py tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py`

```text
All checks passed!
```

`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "active graph AST scan from 54-03 plan"`

```text
54-03 active graph scan OK
```

`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "artifact command-entrypoint scan from 54-03 plan, rerun with shell-safe quoting"`

```text
OK
```

### Final Scan Conclusions

- Active graph includes `slot_resolution_gate`.
- Active graph excludes `extract_slots`, `slot_extraction`, `memory_context_load`, `recommendation_generation`, and `risk_gate`.
- Active graph has no conditional edge source/router pair `("extract_slots", "route_after_slots")`.
- Phase 54 artifacts and `docs/current-langgraph-architecture.md` contain no disallowed bare test runner command contexts.
- `extract_slots` and `route_after_slots` are retained only as compatibility aliases with delete phase no later than Phase 58.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers the missing canonical node test and expected route/baseline test updates.
- [x] No watch-mode flags.
- [x] Feedback latency < 120s for focused suite.
- [x] `nyquist_compliant: true` set in frontmatter after execution evidence is green.

**Approval:** complete

## Validation Audit 2026-07-07

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Audit rerun evidence:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_session_memory_integration.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` -> `1453 passed, 1 skipped, 35 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q --tb=short` -> `1 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/api/routers/agent_runs.py tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py` -> `All checks passed!`
- Active graph scan -> `54 audit active graph scan OK`
- Artifact command-entrypoint scan -> `54 audit artifact entrypoint scan OK`

Audit conclusion: CAGM-05 planned behaviors across 54-01, 54-02, and 54-03 remain covered by automated tests/scans; `nyquist_compliant: true` remains justified. One audit-command quoting failure was logged in `.planning/LOCAL-VALIDATION-ISSUES.md`; it was rerun green and did not expose a coverage gap.
