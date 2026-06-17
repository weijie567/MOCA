---
phase: 16
plan: 09
type: execute
wave: 9
depends_on:
  - 16-06-reviewed-case-memory-PLAN.md
  - 16-08-memory-retrieval-integration-PLAN.md
files_modified:
  - src/tools/catalog.py
  - src/tools/executors/memory.py
  - src/tools/manager.py
  - src/agent/events.py
  - tests/tools/test_catalog.py
  - tests/agent/test_policy_retrieval_ownership.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/memory/test_session_precedent_search.py
  - tests/agent/test_memory_evidence_boundary.py
autonomous: true
requirements:
  - CASEMEM-03
  - CASEMEM-02
  - MEMCTX-02
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "The planner-visible `search_case_memory` name is backed by reviewed case memory only."
  - "The old session-derived search is renamed to legacy/debug-only and cannot claim reviewed case memory."
  - "Case memory is not `EvidenceRefV1` and not approval/action authority."
  - "Final verification covers identity, schema, retrieval predicates, tombstones, prompt safety, authority negatives, and legacy transition behavior."
---

# Plan 16-09: Legacy Search Transition And Eval Closure

<objective>
Back planner-visible `search_case_memory` with the reviewed case memory store, quarantine the old session-derived search as legacy/debug-only, then close Phase 16 with authority-boundary, catalog/tool, and requirement-coverage verification.
</objective>

<threat_model>
- T-16-09-01 legacy_misrepresentation: the existing session-derived `search_case_memory` could continue to claim reviewed case memory. Severity: high. Mitigation: planner-visible `search_case_memory` routes to reviewed case memory only; old session-derived search is renamed legacy/debug-only.
- T-16-09-02 retrieval_event_confusion: event family changes could break RAG/retrieval observability. Severity: medium. Mitigation: event tests preserve intended retrieval classification while text clarifies precedent status.
- T-16-09-03 authority_boundary_regression: memory tool output could satisfy evidence or action authorization in downstream nodes. Severity: high. Mitigation: boundary tests across memory, tools, and agent graph.
- T-16-09-04 incomplete_requirement_exit: Phase 16 could appear planned/implemented while requirements lack automated coverage. Severity: medium. Mitigation: final eval manifest/checklist maps all requirement IDs to tests.
</threat_model>

<tasks>
<task id="16-09-01" type="tdd">
<name>Add legacy search transition tests</name>
<files>src/tools/catalog.py, src/tools/executors/memory.py, src/tools/manager.py, src/agent/events.py, tests/tools/test_catalog.py, tests/agent/test_policy_retrieval_ownership.py, tests/agent/test_tools/test_unified_tool_manager.py, tests/memory/test_session_precedent_search.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/tools/catalog.py
- src/tools/executors/memory.py
- src/tools/manager.py
- tests/tools/test_catalog.py
- tests/agent/test_policy_retrieval_ownership.py
- tests/memory/test_session_precedent_search.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Add failing tests for the locked transition rule:
- catalog description for `search_case_memory` says it retrieves reviewed case memory precedents from the reviewed case store.
- `search_case_memory` executor path uses `CaseMemoryService.retrieve_reviewed` or equivalent reviewed-store method.
- reviewed case-memory-backed path returns reviewed precedent fields and does not read `session_memories`.
- old session-derived search is renamed internally to `LegacySessionPrecedentSearchService` and returns `legacy session-derived precedent` only through debug/unavailable legacy paths, not the planner-visible `search_case_memory`.
</action>
<acceptance_criteria>
- `tests/tools/test_catalog.py` contains a test that checks `search_case_memory` wording.
- `tests/agent/test_policy_retrieval_ownership.py` contains a test that reviewed case memory is not policy evidence.
- `tests/memory/test_session_precedent_search.py` is updated to expect `legacy session-derived precedent` from the renamed legacy/debug-only service.
</acceptance_criteria>
<done>All acceptance criteria for 16-09-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/memory/test_session_precedent_search.py -q
</verify>
</task>

<task id="16-09-02" type="execute">
<name>Implement reviewed search_case_memory transition</name>
<files>src/tools/catalog.py, src/tools/executors/memory.py, src/tools/manager.py, src/agent/events.py, tests/tools/test_catalog.py, tests/agent/test_policy_retrieval_ownership.py, tests/agent/test_tools/test_unified_tool_manager.py, tests/memory/test_session_precedent_search.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/tools/catalog.py
- src/tools/executors/memory.py
- src/tools/manager.py
- src/memory/case_memory.py
- src/memory/search.py
- tests/agent/test_tools/test_unified_tool_manager.py
</read_first>
<action>
Implement the locked transition:
- Keep the planner-visible tool name `search_case_memory`.
- Route `search_case_memory` to `CaseMemoryService.retrieve_reviewed` or equivalent reviewed case-memory store method.
- Rename the current session-derived service/class/summary to `LegacySessionPrecedentSearchService`.
- Make the legacy path debug-only or unavailable from planner-visible tool dispatch.
- Preserve read-only behavior for planner-visible memory retrieval.
- Do not add write tools to the investigate allowlist.
</action>
<acceptance_criteria>
- `src/tools/catalog.py` text for `search_case_memory` contains `reviewed case memory`.
- `src/tools/executors/memory.py` calls `CaseMemoryService` or a reviewed case-memory adapter for planner-visible `search_case_memory`.
- `src/tools/executors/memory.py` does not return a summary containing `reviewed case memory` from `SessionMemoryRepository`.
- `uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-09-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q
</verify>
</task>

<task id="16-09-03" type="execute">
<name>Preserve retrieval event classification</name>
<files>src/tools/catalog.py, src/tools/executors/memory.py, src/tools/manager.py, src/agent/events.py, tests/tools/test_catalog.py, tests/agent/test_policy_retrieval_ownership.py, tests/agent/test_tools/test_unified_tool_manager.py, tests/memory/test_session_precedent_search.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/agent/events.py
- src/tools/catalog.py
- tests/agent/test_events.py
- tests/agent/test_policy_retrieval_ownership.py
</read_first>
<action>
Preserve retrieval event classification:
- Keep planner-visible `search_case_memory` in `RAG_RETRIEVAL_TOOLS`.
- Ensure emitted events remain retrieval events.
- Do not introduce a second reviewed case memory tool name in Phase 16 unless compatibility tests require a shim.
- Do not classify memory retrieval as policy evidence.
</action>
<acceptance_criteria>
- Event tests assert the final case-memory tool name classifies as retrieval.
- Boundary tests assert case memory does not create `EvidenceRefV1`.
- `uv run pytest tests/agent/test_events.py tests/agent/test_policy_retrieval_ownership.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-09-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/agent/test_events.py tests/agent/test_policy_retrieval_ownership.py -q
</verify>
</task>

<task id="16-09-04" type="execute">
<name>Run final Phase 16 eval closure</name>
<files>src/tools/catalog.py, src/tools/executors/memory.py, src/tools/manager.py, src/agent/events.py, tests/tools/test_catalog.py, tests/agent/test_policy_retrieval_ownership.py, tests/agent/test_tools/test_unified_tool_manager.py, tests/memory/test_session_precedent_search.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
- .planning/REQUIREMENTS.md
- tests/memory
- tests/agent/context
- tests/agent/test_memory_evidence_boundary.py
</read_first>
<action>
Add final Phase 16 eval/coverage closure:
- Ensure every requirement ID in `.planning/REQUIREMENTS.md` has at least one automated test or documented DB-backed migration check.
- Add a lightweight requirement coverage test or documented manifest if the repository already has a pattern for phase eval manifests.
- Run the focused Phase 16 suite:
  `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py -q`
- Run `uv run pytest -q` before final verification when time allows.
</action>
<acceptance_criteria>
- `.planning/phases/16-long-term-case-memory/16-VALIDATION.md` remains consistent with implemented test file names or is updated in the phase summary.
- Focused Phase 16 suite exits 0.
- Full suite result is recorded in execution summary; if full suite cannot run due environment, exact error is recorded.
</acceptance_criteria>
<done>All acceptance criteria for 16-09-04 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py -q
uv run pytest -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q`.
- Run `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py -q`.
- Run `uv run pytest -q` before final phase verification.
</verification>

<success_criteria>
- `search_case_memory` no longer claims reviewed case memory unless it is backed by the reviewed case-memory store.
- Memory retrieval stays read-only and separate from policy evidence.
- Event classification remains explicit and tested.
- Phase 16 requirements have focused automated verification coverage.
</success_criteria>

<must_haves>
- The planner-visible `search_case_memory` name is backed by reviewed case memory only.
- The old session-derived search is renamed to legacy/debug-only and cannot claim reviewed case memory.
- Case memory is not `EvidenceRefV1` and not approval/action authority.
- Final verification covers identity, schema, retrieval predicates, tombstones, prompt safety, authority negatives, and legacy transition behavior.
</must_haves>
