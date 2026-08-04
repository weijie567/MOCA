# Phase 40: Tool Contract Validation Hardening - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 40 closes source-confirmed validation and backstop gaps left after Phase 38/39. It hardens `create_coupon_grant_draft` output validation, adds a guard for advisory domain-scope markers, and aligns the local JSON Schema subset with the schema keywords descriptor authors are allowed to use.

This phase does not delete or deprecate `UnifiedToolManager`, does not invent payload semantics for unavailable tools, does not rebuild BusinessFactService merchant ownership checks, and does not modify `docs/contract-spec.md` unless implementation proves the spec itself is wrong and the phase stops for the dual-AI spec-review workflow.

</domain>

<decisions>
## Implementation Decisions

### Scope Locks
- **D-01:** Keep this phase limited to correctness/security validation hardening: strict action-tool output schema, ownership-marker backstop testing, validator keyword support, and descriptor schema meta guards.
- **D-02:** Keep `UnifiedToolManager` cleanup/API removal out of scope. It is a separate breaking cleanup decision because `src.tools.__all__` exports it and `docs/contract-spec.md` currently defines it as a legacy compatibility adapter.
- **D-03:** Keep `docs/contract-spec.md` unchanged in this phase. If implementation discovers a spec error, stop and run the MOCA dual-AI spec review workflow before changing the spec.
- **D-04:** Preserve `ToolResultV2` envelope fields and `ToolCallContext` §8.0 identity fields exactly. This phase only validates `ToolResultV2.data` shapes and local schema semantics.

### Action Output Hardening
- **D-05:** Replace `create_coupon_grant_draft`'s `_GENERIC_OBJECT_SCHEMA` with a strict schema derived from the real `ActionService.create_coupon_grant_draft` success payload.
- **D-06:** The schema must include the top-level success data fields returned by `src/actions/service.py`: `draft_id`, `idempotency_key`, `status`, `created`, `idempotent_reused`, `action_draft`, `draft_outcome`, `execution_mode`, and `action_result`.
- **D-07:** The schema should use `additionalProperties: False` where the current payload contract is stable. Nested dynamic business payload objects may remain typed as object only when their keys are intentionally domain payload data, but unexpected raw/debug fields must fail validation.
- **D-08:** Existing action fake payloads in tests must be upgraded to the real contract shape instead of weakening the schema to fit simplified fakes.

### No-Data Tools
- **D-09:** Keep `get_logistics`, `get_merchant_risk`, and `search_sop` on `_NO_DATA_OUTPUT_SCHEMA` because their current executors are unavailable/no-payload paths. Do not create speculative schemas for future payloads.

### Ownership Marker Backstop
- **D-10:** Keep the runtime architecture split: policy records `requires_domain_scope_check`, while BusinessFactService performs merchant-scope/ownership enforcement and no-leak projection when it touches business data.
- **D-11:** Do not change runtime policy behavior to look up order/refund/ticket ownership. Instead, add an architecture/backstop test that fails if domain-lookup business read tools drift away from the BusinessFactService boundary and merchant-scope/no-leak checks.
- **D-12:** The backstop should cover current domain-lookup reads (`get_order`, `get_refund_case`, `get_ticket`) and the code path `ToolPlatform -> BusinessToolExecutor -> BusinessToolService/BusinessFactService`.

### JSON Schema Subset
- **D-13:** Do not introduce the `jsonschema` dependency. Continue using the local `validate_json_value` subset because current descriptor schemas are shallow and fail-closed behavior is easy to audit.
- **D-14:** Implement the currently advertised-but-missing validation keywords: string `maxLength`, numeric `minimum`, `maximum`, and `exclusiveMaximum`. Apply numeric bounds to both `integer` and `number` types.
- **D-15:** Add a descriptor schema meta guard that walks every registered `input_schema` and `output_schema` and fails if unsupported JSON Schema keywords appear anywhere. This prevents constraints that look real but are silently ignored.
- **D-16:** Keep `pattern`, `format`, `oneOf`, `anyOf`, and similar full-draft features out of scope until an actual descriptor needs them.

### Verification
- **D-17:** Use MOCA's required test entrypoints only: `uv run pytest ...` or `.venv/bin/pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid in this repository.
- **D-18:** Focused verification must include `tests/tools/` and `tests/architecture/`. If action output hardening touches graph/action tests, include the affected `tests/test_execute_action.py` and `tests/agent/test_tools/test_create_coupon_grant_draft.py` paths.
- **D-19:** Final verification must include a no-diff guard for `docs/contract-spec.md`, `ToolResultV2` envelope fields, `ToolCallContext` §8.0 identity fields, and `UnifiedToolManager` compatibility behavior.

### the agent's Discretion
- The exact file placement for the ownership marker backstop test may follow existing `tests/architecture/` conventions.
- The exact schema helper name for the implemented-keyword set may be chosen by the implementer, as long as descriptor meta tests use the same source of truth.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning And Scope
- `.planning/ROADMAP.md` — Phase 40 goal, dependencies, success criteria, and out-of-scope boundaries.
- `.planning/REQUIREMENTS.md` — TPH-05 requirement and traceability.
- `.planning/STATE.md` — v2.1 tool-platform context, §8.0 lock, BusinessFactService ownership split, and Phase 40 exclusions.

### Normative Contract Guardrails
- `docs/contract-spec.md` §8.0, §12.5, §12.6 — normative tool/context contract source. Must be read for no-diff guardrails, but should not be edited in this phase.

### Tool Platform Source
- `src/tools/catalog.py` — tool descriptors, current output schemas, no-data schemas, and `create_coupon_grant_draft` generic output gap.
- `src/tools/runtime.py` — input/output validation gate and `invalid_response` mapping.
- `src/tools/validation.py` — local JSON Schema subset to extend.
- `src/tools/policy.py` — `requires_domain_scope_check` marker and prompt-safe schema keyword whitelist.
- `src/tools/platform.py` — canonical graph-facing facade.
- `src/tools/executors/action.py` — `ActionToolExecutor` wrapping `ActionService` results into `ToolResultV2`.
- `src/tools/executors/business.py` — business executor boundary to BusinessFactService.

### Action Output Source
- `src/actions/service.py` — real `create_coupon_grant_draft` success data payload and helper projections.
- `src/actions/schemas.py` — `ActionDraftV2Data`, `DraftOutcomeV1`, and action compatibility result models.
- `src/db/models.py` — `ActionDraft` persistence fields if schema details need confirmation.

### Ownership Boundary Source
- `src/business/service.py` — `_merchant_scope_allows`, no-leak permission denial, `BusinessFactService`, and `BusinessToolService` wrapping.
- `tests/tools/test_tool_platform.py` — existing marker/no-leak behavior coverage.
- `tests/architecture/test_action_draft_boundaries.py` — architecture-test style for boundary guards.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src.tools.validation.validate_json_value` already validates shallow object/array/string/integer/number/boolean/null schemas, `required`, `enum`, finite numbers, `minLength`, `exclusiveMinimum`, and `additionalProperties: False`.
- `ToolRuntime.invoke` already validates output after executor dispatch and maps schema failures to safe `invalid_response`.
- `ActionService.create_coupon_grant_draft` already validates and emits complete action draft projections using Pydantic models.

### Established Patterns
- Catalog tests in `tests/tools/test_catalog.py` assert descriptor schema shapes and helper acceptance/rejection payloads.
- Runtime tests in `tests/tools/test_tool_platform.py` assert safe output validation behavior and domain-scope marker/no-leak behavior.
- Architecture tests use source/AST/string checks for boundary rules where runtime behavior alone cannot prevent future drift.

### Integration Points
- Strict action output schema belongs in `src/tools/catalog.py` beside existing output schemas.
- Validator keyword support belongs in `src/tools/validation.py`.
- Descriptor meta guard likely belongs in `tests/tools/test_catalog.py`.
- Ownership marker backstop likely belongs in `tests/architecture/`, with focused assertions against `src/tools/executors/business.py` and `src/business/service.py`.

</code_context>

<specifics>
## Specific Ideas

- `create_coupon_grant_draft` is the only currently implemented write/action tool and its output flows into approval/action-draft handling, so it is the highest-risk remaining generic output schema.
- The no-data tools are not gaps while their executors do not emit payloads; their strict empty schema is the current correct contract.
- The dangerous JSON Schema failure mode is silent non-enforcement: descriptor authors may write a keyword that prompt-safe projection preserves, while the validator ignores it.

</specifics>

<deferred>
## Deferred Ideas

- `UnifiedToolManager` API cleanup/removal is intentionally deferred to a separate breaking cleanup phase. That future phase must first decide whether to update `docs/contract-spec.md` to cancel the legacy compatibility adapter contract.
- Runtime consumption of `requires_domain_scope_check` by an executor base class is deferred. Phase 40 uses a backstop test rather than changing runtime ownership behavior.
- Full JSON Schema dependency or support for `pattern`, `format`, `oneOf`, `anyOf`, and related draft features is deferred until real descriptor needs justify the added dependency/complexity.

</deferred>

---

*Phase: 40-tool-contract-validation-hardening*
*Context gathered: 2026-07-02*
