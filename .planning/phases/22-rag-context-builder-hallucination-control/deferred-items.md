# Phase 22 Deferred Items

## Out-of-Scope RED Tests

- **Found during:** Plan 22-04 final verification
- **Item:** `tests/agent/rag_context/test_routing.py` still fails because `src.agent.rag_context.routing` is not implemented.
- **Disposition:** Deferred to Plan 22-05, which owns deterministic verifier routing and action-boundary route mapping.
- **Verification note:** Plan 22-04 focused verifier tests pass; the failing broader `tests/agent/rag_context` run is limited to the already-planned 22-05 routing module.
