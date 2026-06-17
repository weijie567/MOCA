---
phase: 16
plan: 05
type: tdd
wave: 5
depends_on:
  - 16-03-long-term-memory-service-PLAN.md
  - 16-04-semantic-episode-PLAN.md
files_modified:
  - src/memory/long_term.py
  - src/memory/tombstones.py
  - src/memory/repository.py
  - tests/memory/test_memory_tombstones.py
  - tests/memory/test_long_term_memory_service.py
autonomous: true
requirements:
  - LONGMEM-03
  - TOMBSTONE-01
  - TOMBSTONE-02
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "Tombstone matching uses canonical content identity and allowed source identity only."
  - "No semantic similarity matching for deletion/no-rewrite."
  - "Same-transaction write path checks active tombstones before insert."
  - "`reason_code=\"tombstone_match\"` is emitted for blocked rewrites."
---

# Plan 16-05: Tombstones, No-rewrite, And Supersede

<objective>
Implement transactional tombstone matching, same-transaction no-rewrite protection, and correction/supersede behavior that leaves exactly one current long-term memory per identity.
</objective>

<threat_model>
- T-16-05-01 resurrection_race: delayed candidate writers can resurrect deleted content if tombstones are checked outside the insert transaction. Severity: high. Mitigation: same-transaction tombstone check and evented skip.
- T-16-05-02 overbroad_semantic_delete: semantic similarity deletion can remove unrelated memories. Severity: high. Mitigation: tombstones match canonical identity or allowed source identity only.
- T-16-05-03 multi_current_profile: correction can leave multiple current rows for one identity. Severity: medium. Mitigation: transactional supersede with one-current tests.
- T-16-05-04 eventless_forget: deletes without `memory_write_events` cannot be audited or replayed. Severity: medium. Mitigation: forget/delete/tombstone paths emit write events.
</threat_model>

<tasks>
<task id="16-05-01" type="tdd">
<name>Add tombstone and supersede tests</name>
<files>src/memory/long_term.py, src/memory/tombstones.py, src/memory/repository.py, tests/memory/test_memory_tombstones.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- src/memory/identity.py
- src/memory/long_term.py
- src/db/models.py
- tests/memory/test_long_term_memory_service.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Create `tests/memory/test_memory_tombstones.py` with failing tests for:
- `forget_long_term_memory` creates an active `memory_tombstones` row and excludes the memory from retrieval immediately.
- a candidate write with matching `(tenant_id, memory_type, scope_type, scope_id, content_hash)` is skipped in the same transaction and emits `reason_code == "tombstone_match"`.
- a candidate write with missing content hash but matching allowed source identity is skipped and emits `reason_code == "tombstone_match"`.
- a similar but non-identical content string is not blocked by semantic similarity alone.
- correction/supersede leaves exactly one `is_current == True` long-term memory for the identity.
</action>
<acceptance_criteria>
- `tests/memory/test_memory_tombstones.py` contains `test_tombstone_blocks_same_transaction_rewrite_by_content_hash`.
- `tests/memory/test_memory_tombstones.py` contains `test_tombstone_blocks_rewrite_by_source_identity_fallback`.
- `tests/memory/test_memory_tombstones.py` contains `test_tombstone_does_not_use_semantic_similarity`.
- `tests/memory/test_memory_tombstones.py` contains `test_supersede_leaves_exactly_one_current_memory`.
</acceptance_criteria>
<done>All acceptance criteria for 16-05-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_tombstones.py -q
</verify>
</task>

<task id="16-05-02" type="execute">
<name>Implement tombstone matching</name>
<files>src/memory/long_term.py, src/memory/tombstones.py, src/memory/repository.py, tests/memory/test_memory_tombstones.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- src/memory/identity.py
- src/memory/long_term.py
- src/db/models.py
- tests/memory/test_memory_tombstones.py
</read_first>
<action>
Implement tombstone repository/service functions:
- `create_tombstone(...)`
- `active_tombstone_matches(...)`
- `check_tombstone_before_write(...)`
- `forget_memory(...)`

Matching order:
1. canonical identity `(tenant_id, memory_type, scope_type, scope_id, content_hash)`
2. fallback `source_identity_hash` built only from allowed source refs
Do not add embedding or semantic similarity to tombstone matching.
</action>
<acceptance_criteria>
- Source contains `tombstone_match`.
- Source contains `source_identity_hash`.
- Source does not contain `.cosine_distance` in tombstone logic.
- `uv run pytest tests/memory/test_memory_tombstones.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-05-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_tombstones.py -q
</verify>
</task>

<task id="16-05-03" type="execute">
<name>Implement supersede transaction</name>
<files>src/memory/long_term.py, src/memory/tombstones.py, src/memory/repository.py, tests/memory/test_memory_tombstones.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- src/memory/long_term.py
- src/db/models.py
- tests/memory/test_long_term_memory_service.py
- tests/memory/test_memory_tombstones.py
</read_first>
<action>
Add correction/supersede transaction behavior:
- mark previous current row `is_current=False`
- set previous row `review_status="superseded"`
- set `superseded_by` and `superseded_at`
- insert replacement row with `is_current=True`
- emit a `memory_write_events` row with `decision="supersede"`
Use one database transaction for previous-row update, replacement insert, and event insert.
</action>
<acceptance_criteria>
- Source contains `review_status=\"superseded\"` or equivalent assignment.
- Source contains `superseded_by`.
- Tests assert exactly one current row after correction.
- Tests assert a `decision == "supersede"` write event.
</acceptance_criteria>
<done>All acceptance criteria for 16-05-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_long_term_memory_service.py -q
</verify>
</task>

<task id="16-05-04" type="execute">
<name>Add delayed rewrite concurrency coverage</name>
<files>src/memory/long_term.py, src/memory/tombstones.py, src/memory/repository.py, tests/memory/test_memory_tombstones.py, tests/memory/test_long_term_memory_service.py</files>
<read_first>
- tests/memory/test_memory_tombstones.py
- tests/conftest.py
- src/memory/long_term.py
</read_first>
<action>
Add separate-session concurrency coverage for tombstone/no-rewrite risks. Use two async sessions or explicit transaction boundaries where the test infrastructure supports it:
- session A creates tombstone and commits.
- session B attempts delayed candidate write with matching source identity.
- B returns skipped/tombstone_match and does not insert a retrievable memory row.
If the current test fixture cannot safely open two DB sessions, add a deterministic service-level transaction test and document the fixture limitation in the test name/comment.
</action>
<acceptance_criteria>
- `tests/memory/test_memory_tombstones.py` contains `delayed` or `separate_session` in a test name.
- Test asserts no retrievable memory row after tombstone match.
- Test asserts `memory_write_events.reason_code == "tombstone_match"`.
</acceptance_criteria>
<done>All acceptance criteria for 16-05-04 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_tombstones.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/memory/test_memory_tombstones.py tests/memory/test_long_term_memory_service.py -q`.
- Run `uv run pytest tests/memory -q`.
</verification>

<success_criteria>
- Tombstones exclude matching long-term/case memory immediately.
- Tombstones block delayed/asynchronous rewrites in the write transaction.
- Correction/supersede leaves exactly one current long-term memory.
- Tombstone and supersede decisions are observable through write events.
</success_criteria>

<must_haves>
- Tombstone matching uses canonical content identity and allowed source identity only.
- No semantic similarity matching for deletion/no-rewrite.
- Same-transaction write path checks active tombstones before insert.
- `reason_code="tombstone_match"` is emitted for blocked rewrites.
</must_haves>
