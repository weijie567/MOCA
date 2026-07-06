---
phase: 51-canonical-graph-baseline-guardrails-and-migration-matrix
reviewed: 2026-07-06T07:17:02Z
depth: deep
files_reviewed: 3
files_reviewed_list:
  - tests/architecture/__init__.py
  - tests/architecture/graph_baseline.py
  - tests/architecture/test_canonical_graph_baseline.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 51: Code Review Report

**Reviewed:** 2026-07-06T07:17:02Z
**Depth:** deep
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 51 architecture helper and guardrail tests against CAGM-02, the Phase 51 plans/context, and the current source graph in `src/agent/graph.py`, `src/agent/routing.py`, and `src/agent/graph_vocabulary.py`.

The reviewed files stay within Phase 51 scope: they add test-local static parsing and tests only, import no runtime graph from the helper, and protected runtime graph files have no diff. The current focused and architecture suites pass with the expected Phase 58 skip.

Two warning-level guardrail gaps remain. Both are false-negative risks in the static architecture tests rather than current runtime behavior changes.

## Warnings

### WR-01: Router coverage can pass when a router yields no parsed routes

**File:** `tests/architecture/graph_baseline.py:363`

**Issue:** `_router_route_values()` stores the collected route set without checking that the parser found any route values. If a future registered router accidentally loses all explicit returns, or is rewritten into a shape that contains no `Return` nodes, the helper returns `frozenset()`. The current coverage assertion in `test_router_return_values_are_covered_by_registered_path_maps` then passes vacuously because an empty set is a subset of every path map. That weakens the CAGM-02 router-route guardrail.

**Fix:**
```python
routes = _collect_router_routes_from_statements(
    function.body,
    string_sets=string_sets,
    guarded_names={},
    context=router_name,
)
if not routes:
    raise AssertionError(f"Router function has no discoverable route returns: {router_name}")
values[router_name] = routes
```

### WR-02: Conditional path-map destinations are not checked against registered nodes

**File:** `tests/architecture/test_canonical_graph_baseline.py:99`

**Issue:** `test_router_return_values_are_covered_by_registered_path_maps()` verifies that router return labels are present as path-map keys, but it does not verify that each path-map destination is an active registered graph node. The exact baseline test catches uncoordinated source drift, but if a future edit updates `CURRENT_CONDITIONAL_EDGE_BASELINE` together with a typo such as `"recommendation_generation": "generate_recommendations"`, these Phase 51 tests can still pass while the static guardrail misses a broken graph destination.

**Fix:**
```python
def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()

    assert set(router_routes) == {router for _source, router in route_maps}
    for (source, router), path_map in route_maps.items():
        assert source in registered_nodes, (source, router)
        assert path_map, (source, router)
        assert set(path_map.values()) <= registered_nodes, (source, router)
        assert router_routes[router], router
        assert router_routes[router] <= frozenset(path_map), router
```

## Validation

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` -> 9 passed, 1 skipped, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture -q` -> 79 passed, 2 skipped, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py` -> pass
- `git diff --check -- tests/architecture/__init__.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py` -> pass
- `git diff --exit-code -- src/agent/graph.py src/agent/routing.py src/agent/graph_vocabulary.py` -> pass

The pytest warning is the existing `LangChainPendingDeprecationWarning` emitted from the installed `langgraph` dependency, not from the reviewed files.

---

_Reviewed: 2026-07-06T07:17:02Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
