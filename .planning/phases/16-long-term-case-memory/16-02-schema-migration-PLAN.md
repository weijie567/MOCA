---
phase: 16
plan: 02
type: execute
wave: 2
depends_on:
  - 16-01-memory-identity-PLAN.md
files_modified:
  - src/db/models.py
  - src/db/migrations/versions/013_long_term_case_memory.py
  - tests/memory/test_memory_schema.py
  - tests/conversation/test_models.py
autonomous: false
requirements:
  - MEMSCHEMA-01
  - TOMBSTONE-01
  - MEMREVIEW-01
  - MEMEVAL-01
must_haves:
  - "`long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events` are separate durable tables."
  - "Schema supports migration rollback and downgrade preflight."
  - "Case memory uses existing PostgreSQL/pgvector stack."
  - "Active tombstone lookup is indexed by tenant, memory type, scope, and content/source identity."
---

# Plan 16-02: Reviewed Memory Schema And Migration

<objective>
Add durable SQLAlchemy models and Alembic migration for `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events`, including constraints, indexes, downgrade, and schema preflight verification.
</objective>

<threat_model>
- T-16-02-01 schema_authority_mixup: using `session_memories` for reviewed memory would blur same-thread continuity and long-term/case memory. Severity: high. Mitigation: new tables only; no migration mutates `session_memories`.
- T-16-02-02 prohibited_status_retrieval: missing DB checks could allow prohibited/rejected/deleted memory states to persist without clear lifecycle. Severity: high. Mitigation: check constraints for `review_status`, `pii_classification`, and `scope_type`.
- T-16-02-03 rollback_failure: migration without downgrade/preflight can strand deployments. Severity: medium. Mitigation: migration tests for upgrade and downgrade object presence.
- T-16-02-04 cross_tenant_tombstone_collision: tombstone indexes missing tenant/scope/type fields could block or leak memory across tenants. Severity: high. Mitigation: active tombstone indexes include tenant, memory type, scope, and content hash.
</threat_model>

<tasks>
<task id="16-02-01" type="tdd">
<name>Add memory schema contract tests</name>
<files>src/db/models.py, src/db/migrations/versions/013_long_term_case_memory.py, tests/memory/test_memory_schema.py, tests/conversation/test_models.py</files>
<read_first>
- src/db/models.py
- src/db/migrations/versions/011_memory_foundation_v2.py
- src/db/migrations/versions/012_thread_user_scope.py
- tests/conversation/test_models.py
- .planning/phases/16-long-term-case-memory/16-VALIDATION.md
</read_first>
<action>
Add failing schema tests that assert the ORM/migration exposes:
- table `long_term_memories`
- table `case_memories`
- table `memory_tombstones`
- table `memory_write_events`
- check constraint text containing `auto_approved`, `needs_review`, `approved`, `rejected`, `superseded`, `tombstoned`, `deleted`
- check constraint text containing `none`, `low`, `sensitive`, `prohibited`
- an active tombstone lookup index containing `tenant_id`, `memory_type`, `scope_type`, `scope_id`, `content_hash`
- downgrade removes Phase 16 tables in reverse dependency order
</action>
<acceptance_criteria>
- `tests/memory/test_memory_schema.py` contains `def test_phase16_memory_tables_exist`.
- `tests/memory/test_memory_schema.py` contains `def test_memory_lifecycle_check_constraints_exist`.
- `tests/memory/test_memory_schema.py` contains `def test_memory_tombstone_active_identity_index_exists`.
- `uv run pytest tests/memory/test_memory_schema.py -q` fails before model/migration implementation and passes after.
</acceptance_criteria>
<done>All acceptance criteria for 16-02-01 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_schema.py -q
</verify>
</task>

<task id="16-02-02" type="execute">
<name>Add Phase 16 ORM models</name>
<files>src/db/models.py, src/db/migrations/versions/013_long_term_case_memory.py, tests/memory/test_memory_schema.py, tests/conversation/test_models.py</files>
<read_first>
- src/db/models.py
- docs/contract-spec.md
- docs/phase-13-17-architecture-plan.md
- .planning/phases/16-long-term-case-memory/16-RESEARCH.md
</read_first>
<action>
Add SQLAlchemy models to `src/db/models.py`:
- `LongTermMemory`
- `CaseMemory`
- `MemoryTombstone`
- `MemoryWriteEvent`

Required columns:
- common: `id`, `tenant_id`, `schema_version`, `created_at`, `updated_at` where applicable, `deleted_at` where lifecycle needs soft delete.
- `LongTermMemory`: `scope_type`, `scope_id`, `memory_kind`, `content`, `content_hash`, `source_type`, `source_ref_json`, `source_identity_hash`, `confidence`, `pii_classification`, `review_status`, `version`, `supersedes`, `superseded_by`, `superseded_at`, `is_current`, `valid_from`, `expires_at`, `created_by_run_id`.
- `CaseMemory`: `scope_type`, `scope_id`, `case_type`, `summary`, `excerpt`, `applicability`, `outcome`, `caveats`, `policy_family`, `policy_version`, `policy_refs_json`, `source_ref_json`, `source_identity_hash`, `embedding` using `Vector(1024)`, `review_status`, `pii_classification`, `expires_at`, `created_by_run_id`.
- `MemoryTombstone`: `memory_type`, `scope_type`, `scope_id`, `content_hash`, `source_ref_json`, `source_identity_hash`, `reason_code`, `created_by_user_id`, `created_by_run_id`, `expires_at`, `deleted_at`.
- `MemoryWriteEvent`: `run_id`, `memory_type`, `memory_id`, `schema_version`, `decision`, `reason_code`, `pii_classification`, `candidate_hash`, `source_ref_json`, `created_at`.

Add check constraints for review status, pii classification, scope type, memory type, confidence range, and no `global` scope in MVP.
</action>
<acceptance_criteria>
- `src/db/models.py` contains `class LongTermMemory`.
- `src/db/models.py` contains `class CaseMemory`.
- `src/db/models.py` contains `class MemoryTombstone`.
- `src/db/models.py` contains `class MemoryWriteEvent`.
- `src/db/models.py` contains `policy_family`.
- `src/db/models.py` contains `policy_version`.
- `src/db/models.py` contains `Vector(1024)` in or near `CaseMemory`.
- `src/db/models.py` contains `ck_long_term_memories_review_status`.
- `src/db/models.py` contains `ck_case_memories_review_status`.
- `src/db/models.py` contains `ck_memory_tombstones_memory_type`.
- `src/db/models.py` contains `ck_memory_write_events_decision`.
</acceptance_criteria>
<done>All acceptance criteria for 16-02-02 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_schema.py -q
</verify>
</task>

<task id="16-02-03" type="execute">
<name>Add Alembic memory migration</name>
<files>src/db/models.py, src/db/migrations/versions/013_long_term_case_memory.py, tests/memory/test_memory_schema.py, tests/conversation/test_models.py</files>
<read_first>
- src/db/migrations/versions/012_thread_user_scope.py
- src/db/models.py
- alembic.ini
- Makefile
</read_first>
<action>
Create Alembic migration `src/db/migrations/versions/013_long_term_case_memory.py` with:
- `revision = "013_long_term_case_memory"`
- `down_revision = "012_thread_user_scope"`
- `upgrade()` creating `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events`
- indexes for active retrieval predicates, active tombstone identity, source identity lookup, write-event tenant/run, case metadata filters, and case embedding vector search where supported
- case metadata filter index must include `tenant_id`, `scope_type`, `scope_id`, `case_type`, `policy_family`, `policy_version`, `review_status`, and `expires_at` where practical
- `downgrade()` dropping indexes and tables in reverse dependency order
Do not alter or backfill `session_memories`.
</action>
<acceptance_criteria>
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `revision = "013_long_term_case_memory"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `down_revision = "012_thread_user_scope"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `op.create_table("long_term_memories"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `op.create_table("case_memories"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `policy_family`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `policy_version`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `op.create_table("memory_tombstones"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `op.create_table("memory_write_events"`.
- `src/db/migrations/versions/013_long_term_case_memory.py` contains `op.drop_table("memory_write_events")` before dropping memory/tombstone tables.
- `src/db/migrations/versions/013_long_term_case_memory.py` does not contain `session_memories`.
</acceptance_criteria>
<done>All acceptance criteria for 16-02-03 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_schema.py -q
</verify>
</task>

<task id="16-02-04" type="execute">
<name>Run blocking migration readiness gate</name>
<files>src/db/models.py, src/db/migrations/versions/013_long_term_case_memory.py, tests/memory/test_memory_schema.py, tests/conversation/test_models.py</files>
<read_first>
- src/db/migrations/versions/013_long_term_case_memory.py
- tests/memory/test_memory_schema.py
- Makefile
</read_first>
<action>
[BLOCKING] Apply/check the migration after schema files are complete:
- Run pure migration/schema tests with `uv run pytest tests/memory/test_memory_schema.py -q`.
- Run DB-backed migration application with `make migrate` when local PostgreSQL is available.
- If local DB is unavailable, record the exact DB error in the phase execution summary and keep pure schema tests green; do not mark the DB-backed check as silently passed.
Add or update tests so downgrade/preflight behavior is covered by an automated test when possible.
</action>
<acceptance_criteria>
- Execution summary for this task records either `make migrate` exit 0 or the exact unavailable-DB error.
- `uv run pytest tests/memory/test_memory_schema.py -q` exits 0.
- `src/db/migrations/versions/013_long_term_case_memory.py` has both `upgrade()` and `downgrade()`.
</acceptance_criteria>
<done>All acceptance criteria for 16-02-04 are met and the verify command exits 0.</done>
<verify>
uv run pytest tests/memory/test_memory_schema.py -q
make migrate
</verify>
</task>
</tasks>

<verification>
- Run `uv run pytest tests/memory/test_memory_schema.py -q`.
- Run `make migrate` if local PostgreSQL is available.
- Run `uv run ruff check src/db/models.py src/db/migrations/versions/013_long_term_case_memory.py tests/memory/test_memory_schema.py`.
</verification>

<success_criteria>
- Four Phase 16 tables exist in ORM and Alembic migration.
- Review, PII, memory type, scope type, and confidence constraints are present.
- Tombstone and retrieval indexes include tenant and scope dimensions.
- Migration has downgrade and no destructive changes to `session_memories`.
</success_criteria>

<must_haves>
- `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events` are separate durable tables.
- Schema supports migration rollback and downgrade preflight.
- Case memory uses existing PostgreSQL/pgvector stack.
- Active tombstone lookup is indexed by tenant, memory type, scope, and content/source identity.
</must_haves>
