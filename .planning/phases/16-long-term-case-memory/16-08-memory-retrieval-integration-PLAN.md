---
phase: 16
plan: 08
type: tdd
wave: 8
depends_on:
  - 16-06-reviewed-case-memory-PLAN.md
  - 16-07-context-assembler-memory-PLAN.md
files_modified:
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/agent/state.py
  - src/agent/graph.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/assess_risk_and_approval.py
  - tests/agent/test_graph.py
  - tests/agent/test_memory_evidence_boundary.py
autonomous: true
requirements:
  - MEMCTX-01
  - MEMCTX-02
  - LONGMEM-02
  - CASEMEM-02
  - MEMEVAL-01
must_haves:
  - "long_term_memory_retrieve returns reviewed prompt-safe memory snippets or safe empty results without false continuity."
  - "Prompt-generating nodes pass reviewed memory snippets into ContextAssembler without raw ORM rows."
  - "Retrieved memory cannot create EvidenceRefV1, approval evidence, action authorization, current business truth, or replay truth."
---

# Plan 16-08: Reviewed Memory Retrieval Integration

<objective>
Wire reviewed long-term and case memory services into the graph retrieval seam and prompt call sites after the ContextAssembler memory block contract exists.
</objective>

<threat_model>
- T-16-08-01 false_continuity: empty or unavailable reviewed memory could claim continuity. Severity: medium. Mitigation: node returns safe empty result with `continuity_claimed=False`.
- T-16-08-02 authority_escalation: retrieved memory could satisfy policy evidence, approval evidence, or action authorization. Severity: high. Mitigation: graph/boundary tests assert memory stays contextual only.
- T-16-08-03 raw_row_leakage: graph state or prompt call sites could pass ORM rows directly into prompts. Severity: high. Mitigation: node returns prompt-safe view dicts only and call sites pass those snippets.
- T-16-08-04 service_unavailable_crash: missing DB/session config could break normal graph routes. Severity: medium. Mitigation: safe unavailable fallback with trace metadata.
</threat_model>

<tasks>
<task id="16-08-01" type="tdd">
<name>Add reviewed memory retrieval graph tests</name>
<files>src/agent/nodes/long_term_memory_retrieve.py, src/agent/state.py, src/agent/graph.py, tests/agent/test_graph.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/agent/nodes/long_term_memory_retrieve.py
- src/agent/state.py
- src/agent/graph.py
- tests/agent/test_graph.py
- tests/agent/test_memory_evidence_boundary.py
</read_first>
<action>
Add failing tests for:
- safe empty behavior when reviewed memory services are unavailable or no reviewed rows exist.
- reviewed profile/case snippets appear in `long_term_memory` / `case_memory` state when services return reviewed snippets.
- `continuity_claimed` is false for unavailable/no-reviewed-memory and true only when at least one reviewed snippet is returned.
- retrieved memory state contains no `EvidenceRefV1`, approval authority body, action authority body, raw tool payload, or replay/debug blob.
</action>
<acceptance_criteria>
- `tests/agent/test_graph.py` contains a test for reviewed memory retrieval or updates the existing empty adapter seam test.
- `tests/agent/test_memory_evidence_boundary.py` contains a reviewed memory authority-boundary test.
- `uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q` fails before implementation and passes after.
</acceptance_criteria>
<done>Graph tests prove reviewed memory retrieval has safe empty behavior, true continuity only for reviewed snippets, and no authority leakage.</done>
<verify>
uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q
</verify>
</task>

<task id="16-08-02" type="execute">
<name>Replace empty memory adapter with reviewed retrieval</name>
<files>src/agent/nodes/long_term_memory_retrieve.py, src/agent/state.py, src/agent/graph.py, tests/agent/test_graph.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/agent/nodes/long_term_memory_retrieve.py
- src/agent/state.py
- src/agent/graph.py
- src/memory/long_term.py
- src/memory/case_memory.py
- tests/agent/test_graph.py
- tests/agent/test_memory_evidence_boundary.py
</read_first>
<action>
Replace the empty adapter with safe reviewed retrieval:
- Resolve session/service dependencies from graph config only when available.
- Call long-term profile retrieval and reviewed case retrieval services.
- If services are disabled, unavailable, or no reviewed memory exists, return `long_term_memory=[]`, `case_memory=[]`, `continuity_claimed=False`, and source `reviewed_memory_unavailable` or `no_reviewed_memory`.
- If reviewed snippets exist, return prompt-safe list values only.
- Do not write memory in this node.
- Do not import `EvidenceRefV1`, approval services, action services, replay writer, or raw tool payload types.
</action>
<acceptance_criteria>
- `src/agent/nodes/long_term_memory_retrieve.py` no longer reports `source == "empty_adapter"` when reviewed services are configured.
- Tests keep safe empty behavior when no reviewed records exist.
- Tests assert retrieved memory state contains no `EvidenceRefV1`.
- `uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q` exits 0.
</acceptance_criteria>
<done>long_term_memory_retrieve uses reviewed services when configured and otherwise returns safe empty prompt-safe state.</done>
<verify>
uv run pytest tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q
</verify>
</task>

<task id="16-08-03" type="execute">
<name>Pass memory snippets into prompt call sites</name>
<files>src/agent/nodes/generate_recommendation.py, src/agent/nodes/extract_slots.py, src/agent/nodes/assess_risk_and_approval.py, tests/agent/test_memory_evidence_boundary.py</files>
<read_first>
- src/agent/nodes/generate_recommendation.py
- src/agent/nodes/extract_slots.py
- src/agent/nodes/assess_risk_and_approval.py
- src/agent/context/assembler.py
- tests/agent/test_memory_evidence_boundary.py
</read_first>
<action>
Pass retrieved memory snippets into all `ContextAssembler.assemble` call sites that generate prompts after memory retrieval:
- `profile_memory_snippets=state.get("long_term_memory") or []`
- `case_memory_snippets=state.get("case_memory") or []`
Preserve existing policy/business/tool arguments. Do not pass raw ORM rows or write-event rows.
</action>
<acceptance_criteria>
- `rg -n "profile_memory_snippets|case_memory_snippets" src/agent/nodes` shows updated prompt call sites.
- Existing policy/tool/business arguments remain present in the same call sites.
- Tests assert memory cannot satisfy policy evidence or action authority.
- `uv run pytest tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py -q` exits 0.
</acceptance_criteria>
<done>Prompt-generating nodes pass reviewed memory snippets into ContextAssembler while preserving policy/tool/business context.</done>
<verify>
uv run pytest tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/agent/context/test_assembler.py tests/agent/test_graph.py tests/agent/test_memory_evidence_boundary.py -q`.
- Run `uv run pytest tests/memory tests/agent/context -q`.
- Run `uv run ruff check src/agent src/memory tests/agent`.
</verification>

<success_criteria>
- `long_term_memory_retrieve` returns reviewed prompt-safe memory snippets or safe empty results.
- Prompt call sites include memory snippets through ContextAssembler only.
- Memory remains contextual assistance only.
</success_criteria>

<must_haves>
- long_term_memory_retrieve returns reviewed prompt-safe memory snippets or safe empty results without false continuity.
- Prompt-generating nodes pass reviewed memory snippets into ContextAssembler without raw ORM rows.
- Retrieved memory cannot create EvidenceRefV1, approval evidence, action authorization, current business truth, or replay truth.
</must_haves>
