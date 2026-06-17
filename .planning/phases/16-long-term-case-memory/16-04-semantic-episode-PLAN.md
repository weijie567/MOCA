---
phase: 16
plan: 04
type: tdd
wave: 4
depends_on:
  - 16-03-long-term-memory-service-PLAN.md
files_modified:
  - src/memory/semantic_episode.py
  - src/memory/schemas.py
  - src/memory/long_term.py
  - tests/memory/test_semantic_episode_projection.py
  - tests/memory/test_long_term_memory_service.py
autonomous: true
requirements:
  - LONGMEM-01
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "Semantic Episode Layer is implemented as a candidate projection only, not an authoritative fact store."
  - "Semantic episode candidates enter long-term memory as needs_review and are never directly retrievable."
  - "Semantic episode projection does not alter session_memories semantics."
---

# Plan 16-04: Semantic Episode Candidate Layer

<objective>
Implement the minimal Semantic Episode Layer from Context decisions D-04, D-05, and D-07 as a candidate-only projection that feeds review, not an authoritative memory store.
</objective>

<threat_model>
- T-16-04-01 semantic_episode_authority_drift: semantic episode projections could be mistaken for reviewed case memory or business truth. Severity: high. Mitigation: semantic output is candidate-only and service tests force `needs_review`.
- T-16-04-02 session_memory_pollution: semantic candidates could alter `session_memories` same-thread slot semantics. Severity: high. Mitigation: projection uses separate module/helpers and tests assert no `session_memories` writes.
- T-16-04-03 raw_payload_leakage: projection could carry raw conversation/tool payloads into memory review or prompts. Severity: high. Mitigation: prompt-safe source summaries only and forbidden-field tests.
</threat_model>

<tasks>
<task id="16-04-01" type="tdd">
<name>Add semantic episode projection tests</name>
<files>src/memory/semantic_episode.py, src/memory/schemas.py, src/memory/long_term.py, tests/memory/test_semantic_episode_projection.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- .planning/phases/16-long-term-case-memory/16-CONTEXT.md
- src/db/models.py
- src/memory/thread_summary.py
- src/conversation/repository.py
- src/memory/schemas.py
- tests/memory/test_thread_summary.py
- tests/memory/test_long_term_memory_service.py
</read_first>
<action>
Create `tests/memory/test_semantic_episode_projection.py` with failing tests for:
- semantic projection creates candidates only, not persisted reviewed memory.
- output candidate kinds include `cross_case_pattern`, `similar_case_hint`, `strategy_hint`, and `preference_candidate` where source data supports them.
- output source type is `semantic_episode_candidate`.
- semantic candidates passed to `LongTermMemoryService` become `review_status="needs_review"`.
- projection does not mutate or write `session_memories`.
- projection output contains no raw tool payload, full policy text, approval/action authority body, replay/debug blob, or `EvidenceRefV1`.
</action>
<acceptance_criteria>
- `tests/memory/test_semantic_episode_projection.py` contains `test_semantic_episode_projection_creates_candidates_only`.
- `tests/memory/test_semantic_episode_projection.py` contains `test_semantic_episode_candidate_requires_review_before_retrieval`.
- `tests/memory/test_semantic_episode_projection.py` contains `test_semantic_episode_projection_does_not_modify_session_memory`.
- `uv run pytest tests/memory/test_semantic_episode_projection.py -q` fails before implementation and passes after.
</acceptance_criteria>
<done>Semantic episode tests prove the layer is candidate-only, review-gated, prompt-safe, and separate from session_memories.</done>
<verify>
uv run pytest tests/memory/test_semantic_episode_projection.py -q
</verify>
</task>

<task id="16-04-02" type="execute">
<name>Implement semantic episode candidate projection</name>
<files>src/memory/semantic_episode.py, src/memory/schemas.py, src/memory/long_term.py, tests/memory/test_semantic_episode_projection.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- src/memory/thread_summary.py
- src/conversation/repository.py
- src/memory/schemas.py
- src/memory/long_term.py
- tests/memory/test_semantic_episode_projection.py
</read_first>
<action>
Implement the minimal Semantic Episode Layer:
- Add `src/memory/semantic_episode.py` with `SemanticEpisodeCandidate` and `project_semantic_episode_candidates(...)`.
- Input may use existing `ConversationSummary.summary_type`, `ConversationSummary.summary_json`, prompt-safe tool summaries, and future case outcome summaries.
- Output candidate kinds may include `cross_case_pattern`, `similar_case_hint`, `strategy_hint`, and `preference_candidate`.
- Output source type must be `semantic_episode_candidate`.
- `LongTermMemoryService` must map semantic episode candidates to `review_status="needs_review"` only.
- Do not create a new authoritative semantic episode table in Phase 16.
- Do not modify `session_memories` semantics.
- Do not allow semantic episode output to become business truth, policy evidence, approval/action authority, or reviewed case memory.
</action>
<acceptance_criteria>
- `src/memory/semantic_episode.py` contains `class SemanticEpisodeCandidate`.
- `src/memory/semantic_episode.py` contains `project_semantic_episode_candidates`.
- `src/memory/semantic_episode.py` contains `semantic_episode_candidate`.
- `src/memory/semantic_episode.py` does not contain `EvidenceRefV1`, `ApprovalRequest`, or `ActionDraft`.
- `uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_long_term_memory_service.py -q` exits 0.
</acceptance_criteria>
<done>Semantic episode projection exists as a candidate-only layer and semantic candidates enter long-term memory as needs_review, never as directly retrievable memory.</done>
<verify>
uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_long_term_memory_service.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/memory/test_semantic_episode_projection.py tests/memory/test_long_term_memory_service.py -q`.
- Run `uv run ruff check src/memory/semantic_episode.py tests/memory/test_semantic_episode_projection.py`.
</verification>

<success_criteria>
- Semantic episode projection exists as a candidate-only layer.
- Semantic candidates feed review through `needs_review`.
- No new authoritative semantic episode fact store is created.
- `session_memories` semantics remain unchanged.
</success_criteria>

<must_haves>
- Semantic Episode Layer is implemented as a candidate projection only, not an authoritative fact store.
- Semantic episode candidates enter long-term memory as needs_review and are never directly retrievable.
- Semantic episode projection does not alter session_memories semantics.
</must_haves>

