# Phase 51: Canonical Graph Baseline Guardrails and Migration Matrix - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 4 planned/new-or-updated files
**Analogs found:** 4 / 4
**Scope note:** Phase 51 is guardrail/test/docs only. Do not rewire `src/agent/graph.py`, do not create new runtime nodes, and do not make the final no-debt gate fail before Phase 58.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/architecture/graph_baseline.py` | utility/test helper | file-I/O + transform | `tests/architecture/test_action_draft_boundaries.py` | role-match |
| `tests/architecture/test_canonical_graph_baseline.py` | test | file-I/O + transform | `tests/architecture/test_action_draft_boundaries.py` + `tests/architecture/test_phase32_static_contract.py` | exact |
| `.planning/ARCHITECTURE-DEBT.md` | documentation ledger | append-only documentation | `.planning/ARCHITECTURE-DEBT.md` current Agent Graph entry | exact |
| `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-SUMMARY.md` / `51-VALIDATION.md` updates | documentation | batch/static verification | `51-VALIDATION.md` current validation map + Phase 50 SPEC closeout style | role-match |

## Pattern Assignments

### `tests/architecture/graph_baseline.py` (utility/test helper, file-I/O + transform)

**Analog:** `tests/architecture/test_action_draft_boundaries.py` and `tests/architecture/test_phase33_rag_claim_boundaries.py`

**Imports and path convention** - copy from `tests/architecture/test_action_draft_boundaries.py` lines 1-17:

```python
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
```

For Phase 51 helper, keep imports smaller:

```python
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
```

**Source + AST helper pattern** - copy/adapt from `tests/architecture/test_action_draft_boundaries.py` lines 36-54:

```python
def _source(path: Path) -> str:
    return path.read_text()


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(_source(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports
```

Use `encoding="utf-8"` in the new helper for consistency with newer files such as `tests/architecture/test_phase34_approval_action_boundaries.py` lines 33-35:

```python
def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")
```

**AST literal extraction pattern** - copy/adapt from `tests/architecture/test_phase33_rag_claim_boundaries.py` lines 256-274:

```python
def _literal_dict_keys(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _function_source(path: Path, function_name: str) -> str:
    tree = ast.parse(_source(path))
    lines = _source(path).splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name:
            assert node.end_lineno is not None
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function not found: {function_name}")
```

**Recommended helper/module shape:**

```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        "investigate",
        "rag_context_build",
        "recommendation_generation",
        "claim_verify",
        "risk_gate",
        "approval_gate",
        "action_draft",
        "clarification_gate",
        "final_response",
    }
)

CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        "receive_request",
        "classify_intent",
        "session_memory_load",
        "extract_slots",
        "long_term_memory_retrieve",
        "investigate",
        "rag_context_build",
        "generate_recommendation",
        "claim_verify",
        "assess_risk_and_approval",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
    }
)

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "classify_intent": {"target": "contextual_intent_resolve", "delete_phase": "Phase 53"},
    "session_memory_load": {"target": "session_context_load", "delete_phase": "Phase 53"},
    "extract_slots": {"target": "slot_resolution_gate", "delete_phase": "Phase 54"},
    "long_term_memory_retrieve": {"target": "memory_context_load", "delete_phase": "Phase 55"},
    "generate_recommendation": {"target": "recommendation_generation", "delete_phase": "Phase 56"},
    "assess_risk_and_approval": {"target": "risk_gate", "delete_phase": "Phase 57"},
}

FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES = frozenset(
    {"slot_extraction", "normalize_input", "memory_write", "trace_close", "action_execution"}
)
```

**Graph source facts to parse** - source is `src/agent/graph.py` lines 280-293:

```python
builder.add_node("receive_request", receive_request)
builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
builder.add_node("session_memory_load", session_memory_load)
builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
builder.add_node("investigate", investigate)
builder.add_node("rag_context_build", rag_context_build)
builder.add_node("generate_recommendation", generate_recommendation, retry_policy=_llm_retry)
builder.add_node("claim_verify", claim_verify)
builder.add_node("assess_risk_and_approval", assess_risk_and_approval, retry_policy=_llm_retry)
builder.add_node("clarification_gate", clarification_gate)
builder.add_node("approval_gate", approval_gate)
builder.add_node("action_draft", action_draft)
builder.add_node("final_response", final_response, retry_policy=_llm_retry)
```

**Conditional edge source facts to parse** - source is `src/agent/graph.py` lines 297-372. The Phase 51 helper should parse `builder.add_conditional_edges(source, router, route_map)` literal string dicts, not regex them.

Recommended public helper names:

```python
def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]: ...
def graph_conditional_edge_mappings(path: Path = GRAPH_PATH) -> dict[tuple[str, str], dict[str, str]]: ...
```

Keep this module test-local. It should not import `src.agent.graph`, because compiling/importing the graph is unnecessary for source guardrails and can pull in runtime dependencies.

### `tests/architecture/test_canonical_graph_baseline.py` (test, file-I/O + transform)

**Analogs:** `tests/architecture/test_action_draft_boundaries.py`, `tests/architecture/test_phase32_static_contract.py`, `tests/architecture/test_phase34_approval_action_boundaries.py`, `tests/architecture/test_phase35_replay_eval_boundaries.py`

**Static source assertion pattern** - copy from `tests/architecture/test_action_draft_boundaries.py` lines 112-121:

```python
def test_graph_registers_canonical_action_draft_node_only() -> None:
    source = _source(GRAPH_PATH)

    assert "from src.agent.nodes.action_draft import action_draft" in source
    assert "from src.agent.nodes.execute_action import execute_action" not in source
    assert 'add_node("action_draft", action_draft)' in source
    assert 'add_node("execute_action"' not in source
    assert '"action_draft": "action_draft"' in source
    assert '"execute_action": "execute_action"' not in source
    assert 'add_edge("action_draft", "final_response")' in source
```

Use the same style for the forbidden drift tests:

```python
def test_forbidden_internal_or_lifecycle_names_are_not_registered_graph_nodes() -> None:
    active_nodes = graph_add_node_names()
    assert active_nodes.isdisjoint(FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES)
```

**Vocabulary compatibility assertion pattern** - copy from `tests/architecture/test_phase32_static_contract.py` lines 17-43:

```python
REQUIRED_MAPPINGS = [
    ("classify_intent", "node", "contextual_intent_resolve", "compatibility_alias", True),
    ("intent_classification", "node", "contextual_intent_resolve", "compatibility_alias", True),
    ("classify_intent:pre_route", "node", "safety_pre_route", "compatibility_alias", True),
    ("session_memory_load", "node", "session_context_load", "compatibility_alias", True),
    ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
    ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
    ("extract_slots", "node", "slot_resolution_gate", "compatibility_alias", True),
    ("slot_resolution_gate", "node", "slot_resolution_gate", "compatibility_alias", True),
    ("route_after_intent", "router", "route_after_contextual_intent", "compatibility_alias", True),
    ("route_after_slots", "router", "route_after_slot_resolution", "compatibility_alias", True),
]


def test_phase32_required_mapping_entries_match_graph_vocabulary() -> None:
    for legacy_name, kind, target_name, status, runnable in REQUIRED_MAPPINGS:
        entry = graph_vocabulary.graph_vocabulary_entry(legacy_name, kind=kind)  # type: ignore[arg-type]

        assert entry is not None, legacy_name
        assert entry.target_name == target_name
        assert graph_vocabulary.target_graph_name(legacy_name, kind=kind) == target_name  # type: ignore[arg-type]
        assert entry.status == status
        assert entry.runnable is runnable
```

For Phase 51, do not use `graph_vocabulary.py` as the only migration matrix source. `generate_recommendation -> recommendation_generation` is active in `src/agent/graph.py` but not currently present in `src/agent/graph_vocabulary.py`; the Phase 51 migration matrix should catch that by comparing parsed active nodes against `MIGRATION_MODE_LEGACY_NODE_MAP`.

**Risk alias pattern** - copy from `tests/architecture/test_phase34_approval_action_boundaries.py` lines 37-55:

```python
def test_phase34_risk_gate_runtime_alias_is_declared() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("assess_risk_and_approval", kind="node")

    assert entry is not None
    assert entry.target_name == "risk_gate"
    assert entry.status == "compatibility_alias"
    assert entry.runnable is True
    assert entry.reason_codes == ("RISK_GATE_PROJECTED_FROM_ASSESS_RISK_AND_APPROVAL",)
    assert graph_vocabulary.target_graph_name("assess_risk_and_approval", kind="node") == "risk_gate"


def test_phase34_route_after_risk_is_runtime_router() -> None:
    entry = graph_vocabulary.graph_vocabulary_entry("route_after_risk", kind="router")

    assert entry is not None
    assert entry.target_name == "route_after_risk"
    assert entry.status == "runtime"
    assert entry.runnable is True
```

**Route allowlist and side-effect-free test pattern** - copy/adapt from `tests/architecture/test_phase33_rag_claim_boundaries.py` lines 99-153:

```python
def test_rag_and_claim_routers_are_total_and_side_effect_free() -> None:
    assert RAG_CONTEXT_STATUSES == {
        "not_required",
        "verified",
        "partial",
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }

    rag_routes = {
        route_after_rag_context(
            {
                "rag_context_status": status,
                "evidence_policy": {"evidence_required": status != "not_required"},
                "primary_intent": "policy_qa",
                "requested_operation": "advise",
            }
        )
        for status in RAG_CONTEXT_STATUSES
    }

    assert rag_routes <= {"recommendation_generation", "clarification_gate", "final_response"}
```

For Phase 51, prefer source-baseline tests over exhaustive runtime route tests. If the planner adds route totality checks, keep them side-effect-free and state-only, matching `src/agent/routing.py` lines 21-38 and 295-378.

**Violation collection pattern** - copy from `tests/architecture/test_phase35_replay_eval_boundaries.py` lines 79-92 and 95-104:

```python
def test_production_code_does_not_define_parallel_replay_event_envelopes() -> None:
    violations: list[str] = []

    for path in _production_python_paths():
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name not in PARALLEL_EVENT_ENVELOPE_CLASS_NAMES:
                continue
            if path not in REPLAY_ENVELOPE_ALLOWED_MODULES:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:class {node.name}")

    assert violations == []
```

Use this pattern if Phase 51 needs to scan for forbidden imports or active registrations across `src/agent`, but keep the primary graph-node check targeted to `src/agent/graph.py`.

**Skipped future-gate pattern** - copy from `tests/architecture/test_phase32_static_contract.py` lines 46-49:

```python
def test_phase32_mapping_document_matches_graph_vocabulary_when_present() -> None:
    if not MAPPING_DOC.exists():
        pytest.skip("32-MVP-TARGET-MAPPING.md is created by Phase 32 Plan 05 Task 2")
```

For Phase 51, the final exact 15-node no-debt equality should be present but skipped until Phase 58:

```python
def test_final_no_debt_gate_is_marked_future_until_phase58() -> None:
    pytest.skip("Phase 58 cutover enforces exact canonical graph node set; Phase 51 only records the future gate.")
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
```

**Recommended Phase 51 tests:**

```python
def test_current_active_graph_node_set_matches_phase51_baseline() -> None: ...
def test_target_canonical_graph_node_set_is_exact_phase50_contract() -> None: ...
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None: ...
def test_current_router_mappings_match_source_baseline() -> None: ...
def test_forbidden_internal_or_lifecycle_names_are_not_registered_graph_nodes() -> None: ...
def test_slot_extraction_drift_is_explicitly_rejected() -> None: ...
def test_final_no_debt_gate_is_marked_future_until_phase58() -> None: ...
```

**Validation command pattern:** use only approved MOCA entrypoints:

```bash
uv run pytest tests/architecture/test_canonical_graph_baseline.py -q
uv run pytest tests/architecture -q
git diff --check
```

Never write bare `pytest` or bare `python -m pytest` in Phase 51 plans or summaries.

### `.planning/ARCHITECTURE-DEBT.md` (documentation ledger, append-only documentation)

**Analog:** `.planning/ARCHITECTURE-DEBT.md` current Agent Graph entry.

**Ledger writing rules** - source `.planning/ARCHITECTURE-DEBT.md` lines 6-11:

```markdown
## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
- 每条目尽量给：问题现象 / 根因、影响、处理状态、证据（phase / commit / 文件:行）、剩余风险。
- 只写「基于仓库真实代码、测试、planning artifact 核对过」的内容。未核实的写「未确认」，不编。
- 目标态 vs 已实现要分清：`docs/contract-spec.md` 是目标契约，不等于已实现事实。
```

**Existing Agent Graph debt context** - source `.planning/ARCHITECTURE-DEBT.md` lines 22-31:

```markdown
# 0. 跨子系统目标架构收敛（Agent Graph / Intent / RAG / Memory / Risk）

## 2026-07-06 — 目标 Agent Graph 架构落 phase 前仍需收敛的 10 项边界

- **子系统**：意图识别 / 工具调用 / RAG / 记忆 / 审批风险主链
- **问题现象/根因**：`docs/target-agent-platform-architecture-plan.md` 的目标 graph 方向合理，但若直接落 phase，仍存在若干实现级 contract 未硬化...
- **影响**：后续 phase plan 可能把当前厚 `classify_intent` 改名但不瘦身...
- **处理状态**：已完成文档/spec 收敛但 runtime 迁移未开始...
- **证据**：`docs/target-agent-platform-architecture-plan.md` §6.1 / §19；`docs/contract-spec.md` §9；`.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md`...
- **剩余风险**：Phase 50 只是迁移总规约，runtime graph 仍未切到 canonical 15-node final state...
```

Phase 51 should append or narrow this entry only if implementation actually adds guardrails/matrix coverage. Wording must say runtime graph remains legacy/canonical mixed until later phases.

### `51-SUMMARY.md` / `51-VALIDATION.md` updates (documentation, batch/static verification)

**Analog:** existing `51-VALIDATION.md` plus Phase 50 SPEC validation section.

Copy the Phase 51 validation command names exactly from `51-VALIDATION.md`:

```bash
uv run pytest tests/architecture/test_canonical_graph_baseline.py -q
uv run pytest tests/architecture -q
git diff --check
```

When summarizing, include:

- Current active graph remains mixed legacy/canonical.
- Phase 51 added static guardrails and migration matrix only.
- Final exact target-node no-debt gate remains Phase 58 scope.
- Any `.planning/ARCHITECTURE-DEBT.md` entry is based on source/test/planning artifacts, not target docs alone.

## Shared Patterns

### Static Source Inspection

**Source:** `tests/architecture/test_action_draft_boundaries.py` lines 36-54, `tests/architecture/test_phase35_replay_eval_boundaries.py` lines 146-155
**Apply to:** `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`

Use `Path(__file__).resolve().parents[2]`, `path.read_text(encoding="utf-8")`, `ast.parse(...)`, and violation lists. Avoid importing/compiling the graph.

### Current Graph Baseline

**Source:** `src/agent/graph.py` lines 280-293 and 297-372
**Apply to:** current active node and router mapping tests

Current source registers 14 active nodes and maps some canonical route labels to legacy destinations, for example `recommendation_generation -> generate_recommendation` in `src/agent/graph.py` lines 318-335. Test this exactly during migration mode.

### Target Graph Contract

**Source:** `docs/contract-spec.md` lines 434-437 and 446-464; Phase 50 SPEC lines 17-35
**Apply to:** `TARGET_CANONICAL_GRAPH_NODES`, forbidden-node drift tests

The target node set is exactly 15 registered nodes. `normalize_input`, slot candidate extraction / `slot_extraction`, `memory_write`, `trace_close`, and `action_execution` are not current target main-chain registered graph nodes.

### Migration Matrix

**Source:** Phase 50 SPEC lines 140-162 and 164-175
**Apply to:** `MIGRATION_MODE_LEGACY_NODE_MAP`, migration-mode tests

Map every current active legacy node to a canonical target and named delete phase:

| Legacy active node | Canonical target | Delete/cutover phase |
|--------------------|------------------|----------------------|
| `classify_intent` | `contextual_intent_resolve` | Phase 53 |
| `session_memory_load` | `session_context_load` | Phase 53 |
| `extract_slots` | `slot_resolution_gate` | Phase 54 |
| `long_term_memory_retrieve` | `memory_context_load` | Phase 55 |
| `generate_recommendation` | `recommendation_generation` | Phase 56 |
| `assess_risk_and_approval` | `risk_gate` | Phase 57 |

### Vocabulary Compatibility

**Source:** `src/agent/graph_vocabulary.py` lines 41-103 and `tests/architecture/test_phase32_static_contract.py` lines 35-43
**Apply to:** optional compatibility cross-checks only

Use `graph_vocabulary_entry(...)` and `target_graph_name(...)` for entries that already exist. Do not treat vocabulary coverage as complete for Phase 51 because `generate_recommendation` is active in `graph.py` but absent from `_ENTRIES`.

### Final No-Debt Gate

**Source:** Phase 50 SPEC lines 229-250
**Apply to:** future skipped/xfail gate in `test_canonical_graph_baseline.py`

The final gate checks for exact canonical nodes, no active legacy node registrations, no legacy router return values, no graph imports of legacy node functions, and no active compatibility aliases. In Phase 51 it must be documented but skipped or xfailed until Phase 58.

## Anti-Patterns to Avoid

| Anti-pattern | Why it is wrong for Phase 51 | Use instead |
|--------------|------------------------------|-------------|
| Regex-only parsing of `builder.add_node(...)` or `add_conditional_edges(...)` | False positives from comments/strings and brittle formatting assumptions | Python `ast` helpers using literal string constants |
| Importing or compiling `src.agent.graph.build_graph(...)` | Requires runtime graph setup/checkpointer and can pull provider/service dependencies | Static source inspection of `src/agent/graph.py` |
| Using `graph_vocabulary.py` as the only migration matrix | It currently lacks active `generate_recommendation -> recommendation_generation` coverage | Parse active graph nodes, then compare to explicit test-local matrix |
| Treating target docs as current implementation facts | Contract docs describe target state; current source is still mixed | Keep separate `CURRENT_ACTIVE_GRAPH_NODES_BASELINE` and `TARGET_CANONICAL_GRAPH_NODES` |
| Failing exact 15-node no-debt equality in Phase 51 | Runtime rewiring starts later and final cleanup belongs to Phase 58 | Keep a skipped/xfail future gate with a Phase 58 note |
| Adding `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, or `action_execution` as registered graph nodes | Phase 50/51 explicitly exclude these from current target main-chain nodes | Assert they are absent from parsed `add_node(...)` names |
| Modifying `src/agent/graph.py` or `src/agent/routing.py` in Phase 51 | Phase 51 is guardrail/test/docs only | New tests/helpers/docs only |
| Bare `pytest` or bare `python -m pytest` in plans/summaries | Invalid MOCA validation entrypoint | `uv run pytest ...` or approved `.venv/bin/...` entrypoints |
| One broad plan covering helper, tests, docs, ledger, and verification all together | Violates MOCA plan granularity guidance for multi-domain phases | Split helper/matrix, architecture tests, and docs/ledger closeout plans |

## Naming and File Layout Recommendations

- Prefer `tests/architecture/graph_baseline.py` for reusable constants and AST helpers.
- Prefer `tests/architecture/test_canonical_graph_baseline.py` for all Phase 51 architecture tests.
- Keep helper names explicit: `graph_add_node_names`, `graph_conditional_edge_mappings`, `TARGET_CANONICAL_GRAPH_NODES`, `CURRENT_ACTIVE_GRAPH_NODES_BASELINE`, `MIGRATION_MODE_LEGACY_NODE_MAP`, `FORBIDDEN_MAIN_CHAIN_REGISTERED_NODES`, `CURRENT_CONDITIONAL_EDGE_BASELINE`.
- Keep constants test-local unless the planner explicitly scopes a no-behavior `graph_vocabulary.py` projection update and validates trace projection impact.
- If `graph_vocabulary.py` is touched despite the recommendation, copy the `_entry(...)` tuple style from `src/agent/graph_vocabulary.py` lines 41-103 and add a separate focused plan/task for projection validation.
- Test names should say whether they assert current baseline, target contract, migration mode, forbidden drift, or future no-debt gate.
- Put failure messages on drift tests that tell future phases to update `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and Phase 50 SPEC before promoting forbidden helper/lifecycle names.

## No Analog Found

No planned Phase 51 file lacks a usable local analog. The only missing exact analog is a ready-made `add_conditional_edges(...)` AST parser; derive it from the existing AST helper patterns above and keep it in `tests/architecture/graph_baseline.py`.

## Metadata

**Analog search scope:** `tests/architecture/`, `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/graph_vocabulary.py`, Phase 50/51 planning artifacts, target graph docs, architecture debt ledger.
**Architecture test files scanned:** 10
**Strong analogs selected:** 5 (`test_action_draft_boundaries.py`, `test_phase32_static_contract.py`, `test_phase33_rag_claim_boundaries.py`, `test_phase34_approval_action_boundaries.py`, `test_phase35_replay_eval_boundaries.py`)
**Pattern extraction date:** 2026-07-06
