---
phase: 54
slug: slot-resolution-gate-cutover
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
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
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/architecture/test_canonical_graph_baseline.py -q` |
| **Estimated runtime** | ~90 seconds focused suite, excluding optional DB-backed API tests |

---

## Sampling Rate

- **After every task commit:** Run the narrow command mapped below for the touched surface.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/architecture/test_canonical_graph_baseline.py -q`.
- **Before `$gsd-verify-work`:** Run the full suite command above plus `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture tests/test_graph_routing.py tests/test_trace_api.py`.
- **Max feedback latency:** 120 seconds for focused non-DB validation.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | CAGM-05 | T-54-01-01 | Current-turn and inherited slots are resolved by deterministic gate rules with explicit provenance, not by LLM authority. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py -q` | `tests/agent/test_required_slots.py` ✅ / `tests/agent/test_nodes/test_slot_resolution_gate.py` ❌ W0 | ⬜ pending |
| 54-01-02 | 01 | 1 | CAGM-05 | T-54-01-02 | Missing, invalidated, stale, incompatible, unresolved conflicting, malformed, or policy-mismatch slot state fails closed to clarification; validated current-turn replacement is tested separately as override-with-provenance. | unit/router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_slot_resolution_gate.py -q` | ✅ existing + ❌ W0 | ⬜ pending |
| 54-02-01 | 02 | 2 | CAGM-05 | T-54-02-01 | Active graph registers `slot_resolution_gate`, not `extract_slots`, and does not introduce `slot_extraction`. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` | ✅ | ⬜ pending |
| 54-02-02 | 02 | 2 | CAGM-05 | T-54-02-02 | `route_after_contextual_intent` returns `slot_resolution_gate` for slot-required intents, and active slot router is `route_after_slot_resolution`. | router/graph | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_graph.py::test_all_router_return_keys_have_edges -q` | ✅ | ⬜ pending |
| 54-02-03 | 02 | 2 | CAGM-05 | T-54-02-03 | Slot-satisfied graph paths reach `investigate`; reviewed-memory compatibility still reaches `long_term_memory_retrieve`; unsafe slot paths reach `clarification_gate`. | graph integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py::test_refund_path_preserves_business_context_facts tests/agent/test_graph.py::test_same_thread_session_memory_active_slots_feed_investigate tests/agent/test_graph.py::test_wrong_thread_or_stale_session_memory_routes_to_clarification tests/agent/test_graph.py::test_canonical_reviewed_memory_hint_reaches_existing_long_term_memory_node -q` | ✅ | ⬜ pending |
| 54-03-01 | 03 | 3 | CAGM-05 | T-54-03-01 | Runtime vocabulary marks canonical slot node/router as runtime and legacy names as compatibility aliases for historical projection only. | unit/API trace | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py::test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name -q` | ✅ | ⬜ pending |
| 54-03-02 | 03 | 3 | CAGM-05 | T-54-03-02 | Final artifact scan proves no new disallowed test entrypoint and no active `slot_extraction` graph node. | static scan | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import pathlib,re; pt='py'+'test'; roots=[pathlib.Path('.planning/phases/54-slot-resolution-gate-cutover'), pathlib.Path('docs/current-langgraph-architecture.md')]; bad=[]\ndef command_contexts(text):\n    contexts=[]\n    contexts += re.findall(r'<automated>(.*?)</automated>', text, flags=re.S)\n    contexts += [body for lang, body in re.findall(r'\`\`\`([A-Za-z0-9_-]*)\\n(.*?)\`\`\`', text, flags=re.S) if lang.lower() in {'bash','sh','zsh','shell','console'}]\n    for snippet in re.findall(chr(96)+r'([^'+chr(96)+r']*)'+chr(96), text):\n        stripped=snippet.strip()\n        if stripped.startswith('$ ') or stripped.startswith(pt+' ') or stripped.startswith('python -m '+pt+' '): contexts.append(stripped)\n    return contexts\nfor root in roots:\n    files=[root] if root.is_file() else [p for p in root.rglob('*') if p.is_file()]\n    for f in files:\n        for context in command_contexts(f.read_text(errors='ignore')):\n            for line in context.splitlines():\n                stripped=line.strip().lstrip('$ ').strip()\n                if stripped == pt or stripped.startswith(pt+' ') or stripped == 'python -m '+pt or stripped.startswith('python -m '+pt+' '): bad.append(f'{f}: {stripped}')\nprint('OK' if not bad else '\\n'.join(bad)); raise SystemExit(1 if bad else 0)"` and `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import ast,pathlib; tree=ast.parse(pathlib.Path('src/agent/graph.py').read_text()); nodes=set(); [nodes.add(n.args[0].value) for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr=='add_node']; assert 'slot_extraction' not in nodes; print('no slot_extraction node')"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_nodes/test_slot_resolution_gate.py` - canonical node unit tests for provenance payload, trace node name, legacy compatibility fields, and error/fail-closed output.
- [ ] `tests/agent/test_required_slots.py` - update route imports/assertions to prefer `route_after_slot_resolution`, while preserving one compatibility delegate assertion for `route_after_slots` if retained.
- [ ] `tests/architecture/graph_baseline.py` - update active graph baseline to remove active `extract_slots` and add active `slot_resolution_gate`.
- [ ] `tests/test_graph_routing.py`, `tests/agent/test_intent_routing.py`, `tests/agent/test_graph.py`, and `tests/agent/test_nodes/test_contextual_intent_resolve.py` - update active slot destination expectations from `extract_slots` to `slot_resolution_gate`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | CAGM-05 | Phase 54 graph/router/node behavior has automated validation surfaces. | All Phase 54 acceptance should be covered by focused pytest, ruff, and static scans. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers the missing canonical node test and expected route/baseline test updates.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 120s for focused suite.
- [ ] `nyquist_compliant: true` set in frontmatter after execution evidence is green.

**Approval:** pending
