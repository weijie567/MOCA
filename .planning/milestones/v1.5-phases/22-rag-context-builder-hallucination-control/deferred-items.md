# Phase 22 Deferred Items

## Resolved Items

- **Found during:** Plan 22-04 final verification
- **Item:** `tests/agent/rag_context/test_routing.py` still fails because `src.agent.rag_context.routing` is not implemented.
- **Disposition:** Resolved by Plan 22-05, which added deterministic verifier routing and action-boundary route mapping.
- **Verification note:** `uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/test_graph_routing.py -q` passed with 89 tests.
