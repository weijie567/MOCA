---
phase: 16
plan: 06
type: tdd
wave: 6
depends_on:
  - 16-05-tombstone-supersede-PLAN.md
files_modified:
  - src/memory/case_memory.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/knowledge/retrieval.py
  - src/repositories/policy_chunk_repo.py
  - tests/memory/test_case_memory_retrieval.py
autonomous: true
requirements:
  - CASEMEM-01
  - CASEMEM-02
  - CASEMEM-03
  - TOMBSTONE-01
  - TOMBSTONE-02
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "Case memory is reviewed precedent context only, not evidence or authority."
  - "Case candidate, approve, reject, write, skip, delete, and tombstone decisions emit observable review/write events."
  - "Metadata filters include tenant, status, tombstone/deletion, case type, policy compatibility, and expiry."
  - "Pgvector is used only after hard filters."
  - "Legacy session-derived search is not reused as reviewed case memory."
---

# Plan 16-06: Reviewed Case Memory Storage And Retrieval

<objective>
Implement reviewed case memory storage and metadata-first + pgvector retrieval, separate from session memory, long-term profile memory, policy evidence, and current business facts.
</objective>

<threat_model>
- T-16-06-01 policy_evidence_confusion: case memory precedent could be mistaken for policy evidence. Severity: high. Mitigation: returned views use precedent fields only and never `EvidenceRefV1`.
- T-16-06-02 filter_after_vector_leak: vector search before tenant/status/policy filters could retrieve cross-tenant or unreviewed cases. Severity: high. Mitigation: repository applies hard metadata filters before/inside vector query and tests rejected/cross-tenant rows.
- T-16-06-03 legacy_session_pollution: session-derived `search_case_memory` could be treated as reviewed case memory. Severity: high. Mitigation: reviewed case service is separate; legacy transition handled in Plan 09.
- T-16-06-04 raw_payload_leakage: case precedent prompt snippets could expose raw business/tool payloads. Severity: high. Mitigation: fixed prompt-safe fields only: `case_memory_id`, `excerpt`, `applicability`, `outcome`, `caveats`, score/rank metadata, and compact safe refs.
- T-16-06-05 unobservable_review_decision: case candidates could move from review to retrieval without an auditable approve/reject decision. Severity: high. Mitigation: tests require `needs_review -> approved/rejected` transitions, reviewer metadata or reason codes, and `memory_write_events` for candidate/write/approve/reject paths.
</threat_model>

<tasks>
<task id="16-06-01" type="tdd">
<name>Add reviewed case retrieval tests</name>
<files>src/memory/case_memory.py, src/memory/repository.py, src/memory/schemas.py, src/knowledge/retrieval.py, src/repositories/policy_chunk_repo.py, tests/memory/test_case_memory_retrieval.py</files>
<read_first>
- src/repositories/policy_chunk_repo.py
- src/knowledge/retrieval.py
- src/memory/search.py
- src/db/models.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Create `tests/memory/test_case_memory_retrieval.py` with failing tests that assert:
- reviewed case memory candidates are created as `needs_review` when they are not deterministic/human-reviewed and are excluded from retrieval before approval.
- submitting a case memory candidate emits `memory_write_events(memory_type="case_memory", decision="needs_review", ...)` with reason/source metadata.
- approved reviewed case memory can be inserted with stable `content_hash`, source identity, outcome metadata, reviewer metadata or decision reason, and prompt-safe excerpt fields.
- case memory review lifecycle supports `needs_review -> approved` and `needs_review -> rejected`; approve/reject decisions emit `memory_write_events` with `memory_type="case_memory"` and decision/reason metadata.
- retrieval excludes rejected, needs_review, deleted, expired, prohibited, tombstoned, cross-tenant, wrong case_type, and policy-version-incompatible rows.
- retrieval does not inspect `session_memories`.
- retrieval output has exactly `excerpt`, `applicability`, `outcome`, `caveats`, `case_memory_id`, `score`, and safe refs fields; no raw payload fields.
- returned case memory cannot be converted to `EvidenceRefV1`.
</action>
<acceptance_criteria>
- `tests/memory/test_case_memory_retrieval.py` contains `test_case_memory_retrieval_applies_metadata_filters_before_results`.
- `tests/memory/test_case_memory_retrieval.py` contains `test_case_memory_candidate_requires_review_before_retrieval`.
- `tests/memory/test_case_memory_candidate_event_is_observable`.
- `tests/memory/test_case_memory_reject_decision_is_observable`.
- `tests/memory/test_case_memory_retrieval.py` contains `test_case_memory_is_separate_from_session_memory`.
- `tests/memory/test_case_memory_retrieval.py` contains `test_case_memory_view_is_not_evidence_ref`.
- `uv run pytest tests/memory/test_case_memory_retrieval.py -q` fails before implementation and passes after.
</acceptance_criteria>
<done>All acceptance criteria for 16-06-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_case_memory_retrieval.py -q
</verify>
</task>

<task id="16-06-02" type="execute">
<name>Implement case memory service boundary</name>
<files>src/memory/case_memory.py, src/memory/repository.py, src/memory/schemas.py, src/knowledge/retrieval.py, src/repositories/policy_chunk_repo.py, tests/memory/test_case_memory_retrieval.py</files>
<read_first>
- src/memory/identity.py
- src/memory/schemas.py
- src/db/models.py
- tests/memory/test_case_memory_retrieval.py
</read_first>
<action>
Implement case memory schemas and service boundary:
- `CaseMemoryWriteCandidate`
- `CaseMemoryReviewDecision`
- `CaseMemoryWriteResult`
- `CaseMemorySearchRequest`
- `CaseMemorySearchItem`
- `CaseMemorySearchResult`
- `CaseMemoryRepository`
- `CaseMemoryService`
Use structured `policy_family` and `policy_version` fields from `case_memories` for compatibility filtering; do not rely on unindexed arbitrary JSON keys for this filter.

Implement explicit case review/write methods:
- `submit_case_memory_candidate(...)` stores or records a candidate with `review_status="needs_review"` unless the source is explicitly human-reviewed/deterministic and permitted to auto-approve; for `needs_review` candidates it emits `memory_write_events(memory_type="case_memory", decision="needs_review", reason_code=..., source_ref_json=...)`.
- `approve_case_memory(...)` moves an existing `needs_review` row to `approved`, records reviewer metadata or `review_reason`, and emits a `memory_write_events` row with `decision="approve"`.
- `reject_case_memory(...)` moves an existing `needs_review` row to `rejected`, records reviewer metadata or `review_reason`, emits `decision="reject"`, and guarantees rejected rows are not retrieved.
- write/skip/delete/tombstone paths for case memory emit `memory_write_events(memory_type="case_memory", decision=..., reason_code=...)` just like long-term memory.

`CaseMemorySearchItem` must expose prompt-safe fields:
- `case_memory_id`
- `excerpt`
- `applicability`
- `outcome`
- `caveats`
- `score`
- `policy_refs`
- `source_refs`
It must not expose raw business payloads, raw tool output, full policy text, approval/action authority bodies, replay/debug blobs, or ORM row objects.
</action>
<acceptance_criteria>
- Source contains `class CaseMemoryService`.
- Source contains `class CaseMemoryReviewDecision`.
- Source contains `submit_case_memory_candidate`.
- Source contains `approve_case_memory`.
- Source contains `reject_case_memory`.
- Source contains `class CaseMemorySearchItem`.
- Source contains `excerpt`.
- Source contains `applicability`.
- Source contains `outcome`.
- Source contains `caveats`.
- Source does not expose a field named `raw_payload`.
- Tests assert `needs_review` case rows are excluded before approval and rejected rows remain excluded after review.
- Tests assert candidate submission creates `memory_write_events` with `memory_type="case_memory"` and `decision="needs_review"`.
- Tests assert case review decisions create `memory_write_events` with `memory_type="case_memory"`.
- `uv run pytest tests/memory/test_case_memory_retrieval.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-06-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_case_memory_retrieval.py -q
</verify>
</task>

<task id="16-06-03" type="execute">
<name>Implement metadata-first vector retrieval</name>
<files>src/memory/case_memory.py, src/memory/repository.py, src/memory/schemas.py, src/knowledge/retrieval.py, src/repositories/policy_chunk_repo.py, tests/memory/test_case_memory_retrieval.py</files>
<read_first>
- src/repositories/policy_chunk_repo.py
- src/knowledge/retrieval.py
- src/memory/case_memory.py
- src/db/models.py
- tests/memory/test_case_memory_retrieval.py
</read_first>
<action>
Implement metadata-first + pgvector retrieval:
- Filter by `tenant_id`.
- Filter by allowed `scope_type` / `scope_id` or merchant/case scope.
- Filter by `review_status in ("auto_approved", "approved")`.
- Filter `deleted_at is None`.
- Filter `expires_at is None or expires_at > now`.
- Filter `pii_classification != "prohibited"`.
- Filter compatible `case_type`.
- Filter compatible structured `policy_family` / `policy_version` columns when present in request/row metadata.
- Exclude active tombstone matches by `content_hash` or `source_identity_hash`.
- Then apply `CaseMemory.embedding.cosine_distance(query_embedding)` for vector ranking when query embedding is provided.
- Apply light rerank fields: semantic similarity, policy match, recency. Do not implement full RRF/hybrid lexical retrieval in Phase 16.
</action>
<acceptance_criteria>
- Retrieval source contains `review_status.in_`.
- Retrieval source contains `cosine_distance`.
- Retrieval source contains `policy_version` or equivalent compatibility field.
- Retrieval source uses `policy_family` and `policy_version` fields defined by Plan 16-02.
- Retrieval source contains no RRF implementation or `reciprocal_rank_fusion`.
- Tests assert rejected/cross-tenant/tombstoned rows are not returned.
- Tests assert session-derived memories do not appear in reviewed case retrieval.
</acceptance_criteria>
<done>All acceptance criteria for 16-06-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_case_memory_retrieval.py -q
</verify>
</task>

<task id="16-06-04" type="execute">
<name>Apply tombstone checks to case memory</name>
<files>src/memory/case_memory.py, src/memory/repository.py, src/memory/schemas.py, src/knowledge/retrieval.py, src/repositories/policy_chunk_repo.py, tests/memory/test_case_memory_retrieval.py</files>
<read_first>
- src/memory/case_memory.py
- src/memory/tombstones.py
- tests/memory/test_case_memory_retrieval.py
- tests/memory/test_memory_tombstones.py
</read_first>
<action>
Extend tombstone/no-rewrite checks to case memory writes:
- case write path computes/stores `content_hash` and checks active tombstones by canonical content identity or allowed source identity in the same transaction.
- blocked case write emits `memory_write_events(memory_type="case_memory", reason_code="tombstone_match")`.
- case retrieval excludes tombstoned rows immediately.
</action>
<acceptance_criteria>
- `tests/memory/test_case_memory_retrieval.py` contains a tombstoned case exclusion test.
- Tests assert tombstone matching blocks case writes by both `content_hash` and `source_identity_hash`.
- Source emits `memory_type="case_memory"` or equivalent constant for case write events.
- `uv run pytest tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q` exits 0.
</acceptance_criteria>
<done>All acceptance criteria for 16-06-04 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q`.
- Run `uv run pytest tests/memory -q`.
- Run `uv run ruff check src/memory tests/memory`.
</verification>

<success_criteria>
- Reviewed case memory stores precedent summaries with safe source refs and outcome metadata.
- Case memory review lifecycle is observable through `memory_write_events` and unapproved candidates are not retrievable.
- Case retrieval uses hard metadata filters before semantic ranking.
- Case retrieval remains separate from session memory, long-term profile memory, policy evidence, and current business facts.
- Case memory output is fixed-shape and prompt-safe.
</success_criteria>

<must_haves>
- Case memory is reviewed precedent context only, not evidence or authority.
- Case candidate, approve, reject, write, skip, delete, and tombstone decisions emit observable review/write events.
- Metadata filters include tenant, status, tombstone/deletion, case type, policy compatibility, and expiry.
- Pgvector is used only after hard filters.
- Legacy session-derived search is not reused as reviewed case memory.
</must_haves>
