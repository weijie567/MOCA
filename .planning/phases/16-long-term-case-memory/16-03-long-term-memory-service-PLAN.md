---
phase: 16
plan: 03
type: tdd
wave: 3
depends_on:
  - 16-02-schema-migration-PLAN.md
files_modified:
  - src/memory/long_term.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - tests/memory/test_long_term_memory_service.py
  - tests/memory/test_long_term_memory_repository.py
autonomous: true
requirements:
  - LONGMEM-01
  - LONGMEM-02
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "LLM and semantic candidates never become directly retrievable memory."
  - "Deterministic/explicit sources may auto-approve only through named source types."
  - "Retrieval excludes rejected, deleted, tombstoned, prohibited, superseded, stale, and out-of-scope records."
  - "Write events exist for both persisted and skipped decisions."
---

# Plan 16-03: Long-term Profile Memory Service

<objective>
Implement reviewed long-term profile memory write/review/retrieval services with deterministic source policy, observable write events, and strict retrieval predicates.
</objective>

<threat_model>
- T-16-03-01 model_guess_persistence: raw LLM inference could become durable profile memory. Severity: high. Mitigation: service sends model/summary/semantic candidates to `needs_review`.
- T-16-03-02 prohibited_pii_storage: prohibited PII could be persisted as profile memory. Severity: high. Mitigation: skip prohibited candidates and emit write event.
- T-16-03-03 stale_or_rejected_retrieval: rejected, expired, deleted, tombstoned, or superseded memory could enter prompts. Severity: high. Mitigation: repository retrieval predicate tests.
- T-16-03-04 audit_gap: skipped/rejected/deleted writes without events cannot be reviewed. Severity: medium. Mitigation: `memory_write_events` emitted for candidate, write, skip, approve, reject, and delete paths.
</threat_model>

<tasks>
<task id="16-03-01" type="tdd">
<name>Add long-term memory service tests</name>
<files>src/memory/long_term.py, src/memory/repository.py, src/memory/schemas.py, tests/memory/test_long_term_memory_service.py, tests/memory/test_long_term_memory_repository.py</files>
<read_first>
- src/memory/service.py
- src/memory/repository.py
- src/memory/schemas.py
- src/db/models.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Create failing tests:
- `tests/memory/test_long_term_memory_service.py`
- `tests/memory/test_long_term_memory_repository.py`

Tests must assert:
- explicit user remember request writes `review_status == "auto_approved"` when PII classification is not prohibited.
- deterministic durable source writes `review_status == "auto_approved"`.
- LLM/summary/semantic candidate writes `review_status == "needs_review"`.
- prohibited PII candidate returns skipped result with `reason_code == "pii_blocked"` and no retrievable memory row.
- every write/skip path creates a `memory_write_events` row.
- retrieval returns only approved or auto-approved, current, non-expired, non-deleted, non-tombstoned, non-prohibited records in matching tenant/scope.
</action>
<acceptance_criteria>
- `tests/memory/test_long_term_memory_service.py` contains `test_llm_candidate_requires_review`.
- `tests/memory/test_long_term_memory_service.py` contains `test_prohibited_pii_candidate_is_skipped_and_evented`.
- `tests/memory/test_long_term_memory_repository.py` contains `test_retrieve_profile_memory_excludes_unpublished_states`.
- `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q` fails before implementation and passes after.
</acceptance_criteria>
<done>All acceptance criteria for 16-03-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q
</verify>
</task>

<task id="16-03-02" type="execute">
<name>Implement long-term memory service boundary</name>
<files>src/memory/long_term.py, src/memory/repository.py, src/memory/schemas.py, tests/memory/test_long_term_memory_service.py, tests/memory/test_long_term_memory_repository.py</files>
<read_first>
- src/memory/identity.py
- src/memory/service.py
- src/memory/repository.py
- src/memory/schemas.py
- src/db/models.py
</read_first>
<action>
Implement long-term memory schemas and service boundary:
- `LongTermMemoryWriteCandidate`
- `LongTermMemoryWriteResult`
- `LongTermMemoryView`
- `LongTermMemoryRepository`
- `LongTermMemoryService`

Allowed source policy:
- `explicit_user_preference`, `explicit_admin_preference`, `human_reviewed`, `deterministic_tool_result`, `confirmed_business_outcome`, `approved_approval_state` may become `auto_approved`.
- `llm_candidate`, `semantic_episode_candidate`, `summary_candidate`, `cross_case_pattern_candidate`, `behavior_inference` must become `needs_review`.
- `pii_classification == "prohibited"` must skip persistence and emit `reason_code="pii_blocked"`.
</action>
<acceptance_criteria>
- Source file contains `class LongTermMemoryService`.
- Source file contains `class LongTermMemoryRepository` or an equivalent repository class.
- Source file contains string literal `needs_review`.
- Source file contains string literal `auto_approved`.
- Source file contains string literal `pii_blocked`.
- `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-03-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q
</verify>
</task>

<task id="16-03-03" type="execute">
<name>Implement long-term retrieval predicates</name>
<files>src/memory/long_term.py, src/memory/repository.py, src/memory/schemas.py, tests/memory/test_long_term_memory_service.py, tests/memory/test_long_term_memory_repository.py</files>
<read_first>
- src/memory/long_term.py
- src/db/models.py
- tests/memory/test_long_term_memory_repository.py
</read_first>
<action>
Implement retrieval predicate method, for example `retrieve_profile_memory(...)`, with exact filters:
- matching `tenant_id`
- matching allowed `scope_type` / `scope_id`
- `review_status in ("auto_approved", "approved")`
- `deleted_at is None`
- `is_current is True`
- `expires_at is None or expires_at > now`
- `pii_classification != "prohibited"`
- no active matching tombstone
Return bounded prompt-safe views only, not raw ORM rows.
</action>
<acceptance_criteria>
- Repository retrieval query contains `review_status.in_`.
- Repository retrieval query contains `deleted_at.is_(None)`.
- Repository retrieval query contains `expires_at`.
- Repository retrieval query excludes `prohibited`.
- Tests assert rejected, deleted, expired, prohibited, superseded, and cross-tenant rows are not returned.
</acceptance_criteria>
<done>All acceptance criteria for 16-03-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_long_term_memory_repository.py -q
</verify>
</task>

<task id="16-03-04" type="execute">
<name>Emit long-term memory write events</name>
<files>src/memory/long_term.py, src/memory/repository.py, src/memory/schemas.py, tests/memory/test_long_term_memory_service.py, tests/memory/test_long_term_memory_repository.py</files>
<read_first>
- src/memory/long_term.py
- src/db/models.py
- tests/memory/test_long_term_memory_service.py
</read_first>
<action>
Add write-event emission for candidate, write, skip, approve, reject, delete, and retrieval-blocking decisions. Ensure event fields include `tenant_id`, `run_id`, `memory_type="long_term_fact"`, `decision`, `reason_code`, `pii_classification`, `candidate_hash`, and `source_ref_json`. Generate `candidate_hash` only through `canonical_memory_candidate_hash(...)` from Plan 16-01 using the candidate's tenant, memory type, scope, `content_hash`, and nullable `source_identity_hash`; do not hash raw payloads directly in the service.
</action>
<acceptance_criteria>
- Tests assert `memory_write_events.reason_code == "pii_blocked"` for prohibited skip.
- Tests assert a successful auto-approved write creates a `memory_write_events` row with `decision == "write"`.
- Source contains `memory_type=\"long_term_fact\"` or equivalent constant.
- Source contains `canonical_memory_candidate_hash`.
</acceptance_criteria>
<done>All acceptance criteria for 16-03-04 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_long_term_memory_service.py -q
</verify>
</task>

</tasks>

<verification>
- Run `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py -q`.
- Run `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_memory_schema.py -q`.
- Run `uv run ruff check src/memory tests/memory`.
</verification>

<success_criteria>
- Long-term memory writes respect source review policy.
- Long-term memory retrieval filters unsafe and unpublished states.
- Write/review/skip decisions are observable through `memory_write_events`.
- Returned views are prompt-safe and bounded.
</success_criteria>

<must_haves>
- LLM and semantic candidates never become directly retrievable memory.
- Deterministic/explicit sources may auto-approve only through named source types.
- Retrieval excludes rejected, deleted, tombstoned, prohibited, superseded, stale, and out-of-scope records.
- Write events exist for both persisted and skipped decisions.
</must_haves>
