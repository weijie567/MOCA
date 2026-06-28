---
phase: 32
slug: intent-graph-migration
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Pytest 9.0.3 through `uv run`; project declares `pytest>=8.0`. |
| **Config file** | `pyproject.toml` with `asyncio_mode = "auto"`. |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py tests/platform/test_trusted_context_factory.py tests/platform/test_context_projections.py tests/architecture/test_phase32_static_contract.py -q --tb=short` |
| **Estimated runtime** | ~60-180 seconds, depending on DB-backed API test setup. |

---

## Sampling Rate

- **After every task commit:** Run the focused test file touched by the task plus `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short` for graph vocabulary tasks.
- **After every plan wave:** Run the quick run command above.
- **Before `$gsd-verify-work`:** Run the full suite command above, `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` for touched files, and `git diff --check`.
- **Max feedback latency:** 180 seconds for focused feedback.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 0 | APF-11 | T-32-01 | Legacy graph node/router names project to target canonical names while preserving legacy `trace_steps[].node` and graph edge keys. | unit/contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_graph.py -q --tb=short` | ✅ existing + W0 additions | ✅ green |
| 32-02-01 | 02 | 1 | APF-12 | T-32-02 | `IntentPolicyRegistry` is consumed for effective intent, route, risk, and required slots; LLM output remains candidate-only. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py -q --tb=short` | ✅ existing + W0 additions | ✅ green |
| 32-03-01 | 03 | 2 | APF-12 | T-32-03 | `SlotPolicyRegistry` owns required-slot and inherited-slot acceptance; stale, wrong-scope, or incompatible slots clarify. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py -q --tb=short` | ✅ existing + W0 additions | ✅ green |
| 32-04-01 | 04 | 3 | APF-11 / APF-12 | T-32-04 | AgentRun, trace, replay, and API projections expose safe target names and target merchant-context status without breaking existing `node_name` consumers or widening manager/supervisor access. | API/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_nodes/test_receive_request.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py -q --tb=short` | ✅ existing + W0 additions | ✅ green |
| 32-05-01 | 05 | 4 | APF-11 / APF-12 | T-32-05 | Final focused suite proves legacy compatibility, router totality, registry ownership, merchant visibility safety, and no fake Phase 33 RAG/claim implementation. | focused regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py tests/platform/test_trusted_context_factory.py tests/platform/test_context_projections.py tests/architecture/test_phase32_static_contract.py -q --tb=short` | ✅ existing + all W0 additions | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/agent/test_graph_vocabulary.py` — stubs for APF-11 target graph node/router alias projection, including deferred/non-runnable `rag_context_build` and `claim_verify`.
- [x] `tests/agent/test_intent_policy_registry.py` / `tests/agent/test_intent_routing.py` — registry-consumption tests that fail if `routing.py` or `classify_intent.py` bypasses `IntentPolicyRegistry`.
- [x] `tests/agent/test_required_slots.py` / `tests/agent/test_session_memory_integration.py` — registry-consumption and slot-resolution-gate tests that fail for stale, wrong-thread, invalidated, or intent-incompatible inherited slots.
- [x] `tests/test_agent_runs_api.py` / `tests/test_trace_api.py` / `tests/replay/test_replay_api.py` — target canonical projection and target merchant-context status tests preserving owner/admin-only access.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | APF-11 / APF-12 | Phase 32 behavior is backend contract, routing, trace/API projection, and authorization safety; all planned checks are automatable. | N/A |

---

## Security Threat Model

| Threat ID | Category | Component | Secure Behavior |
|-----------|----------|-----------|-----------------|
| T-32-01 | Tampering / Repudiation | Graph vocabulary and trace projection | Target canonical names are projected consistently from one helper; legacy persisted node names remain available for audit/debug. |
| T-32-02 | Elevation of privilege | Contextual intent resolution | LLM structured output is candidate-only; deterministic `IntentPolicyRegistry` owns effective route, risk, and required-slot policy. |
| T-32-03 | Information disclosure | Slot inheritance | Session context slots are inherited only when trusted metadata proves freshness, scope, and intent compatibility; unsafe inheritance clarifies. |
| T-32-04 | Information disclosure | AgentRun / trace / replay visibility | Target merchant-context status is evidence, not authorization; manager/supervisor-style business run visibility stays owner/admin-only until same-merchant proof is implemented. |
| T-32-05 | Tampering / Safety bypass | Future RAG/claim target names | `rag_context_build` and `claim_verify` are deferred/non-runnable target vocabulary entries in Phase 32; no fake successful Phase 33 behavior. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all MISSING references.
- [x] No watch-mode flags.
- [x] Feedback latency < 180s for focused feedback.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-28

---

## Validation Audit 2026-06-28

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved by existing automated coverage | 5 |
| Escalated | 0 |

Auditor result: existing automated tests cover APF-11/APF-12 for Phase 32. Post-fix reviewed scope passed with `PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest -p no:cacheprovider ... -q --tb=short`: 219 passed, 28 dependency/deprecation warnings.
