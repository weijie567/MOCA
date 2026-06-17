---
phase: 16
plan: 07
type: tdd
wave: 7
depends_on:
  - 16-03-long-term-memory-service-PLAN.md
  - 16-06-reviewed-case-memory-PLAN.md
files_modified:
  - src/agent/context/assembler.py
  - src/agent/context/budget.py
  - src/agent/context/projectors.py
  - tests/agent/context/test_assembler.py
autonomous: true
requirements:
  - MEMCTX-01
  - MEMCTX-02
  - LONGMEM-02
  - CASEMEM-02
  - MEMEVAL-01
must_haves:
  - "Profile memory max 3 items and case memory max 3 items."
  - "Combined memory block hard cap is 1600 chars."
  - "Memory blocks are non-protected and cannot evict protected policy/business/current-user blocks."
  - "ContextAssembler memory projectors keep compact safe refs for traceability but never leak raw payloads, hashes, or authority objects."
---

# Plan 16-07: ContextAssembler Memory Blocks

<objective>
Extend `ContextAssembler` with bounded prompt-safe profile and case memory blocks while preserving protected policy/business/current-user authority.
</objective>

<threat_model>
- T-16-07-01 prompt_authority_escalation: memory could override current user instructions, current business facts, policy evidence, or tool results. Severity: high. Mitigation: memory blocks are non-protected and lower authority than protected business/policy/current-user blocks.
- T-16-07-02 raw_payload_leakage: memory rows could stringify raw JSON, hashes, tool payloads, or authority bodies into prompts. Severity: high. Mitigation: explicit memory projectors carry only bounded text plus compact safe refs and tests for forbidden strings.
- T-16-07-03 budget_starvation: memory could evict policy refs or current user message. Severity: high. Mitigation: memory blocks are non-protected with 1600-char hard cap and lower priority than protected blocks.
</threat_model>

<tasks>
<task id="16-07-01" type="tdd">
<name>Add memory prompt projection tests</name>
<files>src/agent/context/assembler.py, src/agent/context/budget.py, src/agent/context/projectors.py, tests/agent/context/test_assembler.py</files>
<read_first>
- src/agent/context/assembler.py
- src/agent/context/budget.py
- src/agent/context/projectors.py
- tests/agent/context/test_assembler.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Extend `tests/agent/context/test_assembler.py` with failing tests for:
- `ContextAssembler.assemble(...)` accepts `profile_memory_snippets` and `case_memory_snippets`.
- profile memory max 3 items.
- case memory max 3 items.
- total memory prompt text max 1600 chars.
- prompt text contains block names `profile_memory` and `case_memory`.
- case memory prompt text keeps compact traceability via `case_memory_id`, bounded `source_refs`, and bounded `policy_refs`.
- memory blocks do not contain raw payload, full policy text, approval authority body, action authority body, replay/debug blob, `sha256:`, or implicit dict/list repr.
- protected blocks `system_prompt`, `safety_constraints`, `business_ids`, `policy_refs`, and `current_user_message` remain present when memory is oversized.
</action>
<acceptance_criteria>
- `tests/agent/context/test_assembler.py` contains `test_context_assembler_injects_bounded_memory_blocks`.
- `tests/agent/context/test_assembler.py` contains `test_memory_blocks_cannot_evict_protected_policy_or_user_blocks`.
- `uv run pytest tests/agent/context/test_assembler.py -q` fails before implementation and passes after.
</acceptance_criteria>
<done>ContextAssembler tests encode memory count caps, 1600-char total cap, non-protected behavior, and raw/authority leakage exclusions.</done>
<verify>
uv run pytest tests/agent/context/test_assembler.py -q
</verify>
</task>

<task id="16-07-02" type="execute">
<name>Implement memory prompt projectors</name>
<files>src/agent/context/budget.py, src/agent/context/projectors.py, tests/agent/context/test_assembler.py</files>
<read_first>
- src/agent/context/budget.py
- src/agent/context/projectors.py
- tests/agent/context/test_assembler.py
</read_first>
<action>
Update prompt context types and projectors:
- Add `profile_memory` and `case_memory` block names to `BlockName` if the literal list remains enforced.
- Do not add memory block names to `PROTECTED_BLOCK_NAMES`.
- Add `project_profile_memory_for_prompt(snippets)` and `project_case_memory_for_prompt(snippets)` in `src/agent/context/projectors.py`.
- Project profile memory as at most 3 bounded constraints/preferences of 150-200 chars each.
- Project case memory as at most 3 items with fields `case_memory_id`, `excerpt`, `applicability`, `outcome`, `caveats`, compact `source_refs`, and compact `policy_refs`.
- `source_refs` and `policy_refs` must be bounded prompt-safe identifiers/summaries only; they must not contain `EvidenceRefV1`, full policy text, raw tool output, raw business payloads, approval bodies, action authority bodies, hashes, or replay/debug blobs.
- Enforce total combined memory text limit of 1600 chars before constructing prompt blocks.
</action>
<acceptance_criteria>
- `src/agent/context/budget.py` contains `"profile_memory"`.
- `src/agent/context/budget.py` contains `"case_memory"`.
- `PROTECTED_BLOCK_NAMES` does not contain `profile_memory`.
- `PROTECTED_BLOCK_NAMES` does not contain `case_memory`.
- `src/agent/context/projectors.py` contains `project_profile_memory_for_prompt`.
- `src/agent/context/projectors.py` contains `project_case_memory_for_prompt`.
- Case memory projection tests assert `case_memory_id`, compact `source_refs`, and compact `policy_refs` are retained.
- Case memory projection tests assert `EvidenceRefV1`, raw policy/tool/business payloads, hashes, approval bodies, and action authority bodies are excluded.
- `uv run pytest tests/agent/context/test_assembler.py -q` exits 0.
</acceptance_criteria>
<done>Memory projectors produce only bounded prompt-safe text and memory block names remain non-protected.</done>
<verify>
uv run pytest tests/agent/context/test_assembler.py -q
</verify>
</task>

<task id="16-07-03" type="execute">
<name>Wire memory blocks into ContextAssembler</name>
<files>src/agent/context/assembler.py, src/agent/context/projectors.py, tests/agent/context/test_assembler.py</files>
<read_first>
- src/agent/context/assembler.py
- src/agent/context/projectors.py
- tests/agent/context/test_assembler.py
</read_first>
<action>
Update `ContextAssembler.assemble` signature to accept:
- `profile_memory_snippets: Sequence[Any] | None = None`
- `case_memory_snippets: Sequence[Any] | None = None`

Insert prompt blocks so the effective prompt order is:
1. system prompt
2. safety constraints
3. business IDs/state
4. policy refs
5. working state / business context / thread summary / tool summaries as existing prompt-safe facts
6. profile memory
7. case memory
8. recent messages
9. current user message

Memory blocks must be non-protected and lower priority than policy refs, business IDs, and current user message.
</action>
<acceptance_criteria>
- `ContextAssembler.assemble` has parameter `profile_memory_snippets`.
- `ContextAssembler.assemble` has parameter `case_memory_snippets`.
- `tests/agent/context/test_assembler.py` asserts `profile_memory` and `case_memory` are present when snippets are passed.
- Prompt text does not contain forbidden raw payload marker strings from tests.
- `uv run pytest tests/agent/context/test_assembler.py -q` exits 0.
</acceptance_criteria>
<done>ContextAssembler accepts memory snippet parameters and emits bounded non-protected memory blocks without raw/authority leakage.</done>
<verify>
uv run pytest tests/agent/context/test_assembler.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/agent/context/test_assembler.py -q`.
- Run `uv run ruff check src/agent/context tests/agent/context`.
</verification>

<success_criteria>
- `ContextAssembler` can include bounded profile and case memory snippets.
- Memory snippets keep compact safe refs for traceability and never leak raw payloads, hashes, or authority objects.
- Memory remains lower authority than policy/business/current-user context.
</success_criteria>

<must_haves>
- Profile memory max 3 items and case memory max 3 items.
- Combined memory block hard cap is 1600 chars.
- Memory blocks are non-protected and cannot evict protected policy/business/current-user blocks.
- ContextAssembler memory projectors keep compact safe refs for traceability but never leak raw payloads, hashes, or authority objects.
</must_haves>
