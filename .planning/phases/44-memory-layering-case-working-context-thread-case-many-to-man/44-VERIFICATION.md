---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
verified_at: 2026-07-02T19:05:35Z
status: passed
must_haves_checked: 15
passed: 15
gaps: 0
deferred:
  - truth: "Graph run-completion auto-update/read-active lifecycle hooks are not implemented in Phase 44."
    addressed_in: "Phase 45 memory lifecycle wiring"
    evidence: ".planning/ROADMAP.md Phase 44 goal and .planning/MEMORY-REDESIGN-DECISIONS.md:99 explicitly defer auto-update hook wiring to Phase 45."
---

# Phase 44 Verification Report

Verdict: PASSED. Phase 44 achieved its goal: the durable Case Working Context layer, thread<->case many-to-many association, callable audited write surface, spec alignment, review fixes, and red-line preservation are present in the current codebase. The graph run-completion auto-update/read-active lifecycle hooks are intentionally not implemented here and are documented as a named Phase 45 defer.

## Contract Checked

Source contract:

- Roadmap Phase 44 goal and 7 success criteria from `gsd-sdk query roadmap.get-phase 44 --raw`.
- Plan must-haves from `44-01-PLAN.md` through `44-04-PLAN.md`.
- Requirements `MEM-01` and `MEM-02` from `.planning/REQUIREMENTS.md`.
- Defer and red-line design record from `.planning/MEMORY-REDESIGN-DECISIONS.md`.
- Current code/tests at `HEAD` (`a5e59fe fix(44): normalize CWC provenance`) including review fix commit `189d601 fix(44): enforce tenant-safe memory links`.

## Goal Achievement

| # | Must-have | Status | Evidence |
|---|---|---|---|
| 1 | Migrations 021/022 exist and are linear with a single Alembic head. | PASS | `021_thread_case_links.py` has `revision="021_thread_case_links"` and `down_revision="020_memory_write_event_policy_audit"` at lines 17-18. `022_case_working_context.py` has `revision="022_case_working_context"` and `down_revision="021_thread_case_links"` at lines 17-18. `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` returned `022_case_working_context (head)`. |
| 2 | `thread_case_links` table binds conversation threads to `refund_cases.id` UUID and supports active dedup. | PASS | Migration 021 creates `thread_case_links` with tenant/thread/case UUID columns, `case_id` FK to `refund_cases.id`, tenant composite FKs, link-source check, and active unique index at `src/db/migrations/versions/021_thread_case_links.py:49-94`. ORM mirrors this at `src/db/models.py:1254-1302`. |
| 3 | `case_working_contexts` table is scoped by `(tenant_id, case_id)` and distinct from existing memory tables. | PASS | Migration 022 creates `case_working_contexts` with tenant/case UUID FKs, active unique scope, structured JSONB columns, `version`, `updated_by_run_id`, and `source_ref_json` at `src/db/migrations/versions/022_case_working_context.py:41-142`. ORM model is separate from `session_memories`, `case_memories`, and `long_term_memories` at `src/db/models.py:583-657`. |
| 4 | `case_working_context_revisions` append-only history table exists. | PASS | Migration 022 creates `case_working_context_revisions` with `snapshot_json`, `edit_source`, `source_ref_json`, `created_at`, and no `updated_at`/`deleted_at` at `src/db/migrations/versions/022_case_working_context.py:144-197`. ORM model mirrors it at `src/db/models.py:660-710`. |
| 5 | `memory_write_events` accepts `case_working_context` and downgrade is guarded. | PASS | Migration widens the CHECK at `src/db/migrations/versions/022_case_working_context.py:199-204`; downgrade blocks if CWC audit rows exist at lines 207-223. ORM CHECK includes the value at `src/db/models.py:774-790`. Schema test covers guarded downgrade at `tests/db/test_phase44_schema.py:281-303`. |
| 6 | Case identity resolver maps refund case number/UUID to canonical `refund_cases.id` or typed not-found/invalid. | PASS | `resolve_case_id` strips blank input, resolves UUID tenant-scoped, and reuses `RefundRepository.get_by_case_no` for case numbers at `src/memory/case_identity.py:23-50`. Tests cover case number, UUID, unknown, blank/None, and tenant scope in `tests/memory/test_case_identity.py`. |
| 7 | CWC schemas keep claims and verified facts separate, require provenance, and keep policy refs as refs only. | PASS | Claim/fact/action/commitment/policy/evidence models are typed in `src/memory/case_working_context_schemas.py:12-101`; claims require `verified` and `source_ref`, verified facts require `observed_at`, commitments require `confirmed_by_staff`, and policy refs hold `doc_id/chunk_id/version` only. Tests cover separation and source requirements at `tests/memory/test_case_working_context_repo.py:164-280`. |
| 8 | CWC repository reads active context by `(tenant_id, case_id)`, serializes writes, bumps versions, and snapshots prior content. | PASS | `read_active` filters by tenant/case/deleted_at at `src/memory/case_working_context.py:48-61`. Writes assert tenant ownership, take advisory lock, write version 1, detect expected-version conflicts, and append prior-content revisions before bumping version at lines 63-155. Tests cover version 1/no revision, update/revision, conflict/no clobber, field mapping, read miss, and concurrent first writes at `tests/memory/test_case_working_context_repo.py:286-490`. |
| 9 | Thread<->case write lifecycle is explicit, deduped, tenant-safe, and many-to-many. | PASS | `ThreadCaseLinkRepository.link_thread_to_case` validates link source, locks scope, validates tenant-owned thread/case/run, returns existing active row when present, and writes otherwise at `src/memory/thread_case_links.py:19-62`. Bidirectional reads are at lines 64-96. Tests cover dedup, M:N reads, invalid source, cross-tenant case/thread, and concurrent first writes at `tests/memory/test_thread_case_links.py:114-340`. |
| 10 | `ConversationRepository.link_case` exists as the explicit linkage point; `append_message` does not auto-link. | PASS | `append_message` calls `get_or_create_thread` without a case link at `src/conversation/repository.py:68-95`; `link_case` explicitly creates the thread then calls `ThreadCaseLinkRepository` at lines 97-121. Test proves `append_message` leaves zero link rows and repeated `link_case` dedups at `tests/memory/test_thread_case_links.py:343-397`. |
| 11 | CWC write service emits audit events, uses isolated session, trusted provenance, PII block, conflict skip, and tenant guards. | PASS | Service validates required inputs and matching run before isolation at `src/memory/case_working_context_service.py:47-163`; validates tenant-owned run/case at lines 58-68 and 188-217; normalizes trusted run/case source refs at lines 166-185; blocks `sensitive/prohibited` PII at lines 76-98; writes through repository and emits `memory_write_events(memory_type="case_working_context")` at lines 100-146 and 245-275. Tests cover all of these at `tests/memory/test_case_working_context_service.py:179-607`. |
| 12 | Every persisted CWC is contextual-only and stores claim/fact separation without authority escalation. | PASS | DB CHECK pins `authority_class = 'contextual_only'` at `src/db/migrations/versions/022_case_working_context.py:122-127` and ORM model at `src/db/models.py:592-597`; repository sets/preserves contextual-only on create/update at `src/memory/case_working_context.py:82-128`; high-consequence content test confirms claims/commitments/recommendations remain contextual and staff-correctable at `tests/memory/test_case_working_context_service.py:531-570`. |
| 13 | Red lines held: no `case_memories` / `long_term_memories` rename and no destructive `conversation_threads.case_id` change. | PASS | `git grep -n "case_memories\|long_term_memories" -- src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py` returned no matches. Current ORM still has `ConversationThread.case_id: String(128)` at `src/db/models.py:1225` and only the existing index appears in the Phase 44 migration/red-line search (`src/db/models.py:1251`). |
| 14 | Contract spec and DEFER trace are aligned. | PASS | `docs/contract-spec.md` Section 13 defines CWC as contextual-only, not `EvidenceRefV1`, distinct from `case_memory`, versioned, refs-only, and additive M:N at lines 1422-1436 and 1514-1526. Alignment tests assert the contract/red-line/defer strings at `tests/memory/test_phase44_contract_alignment.py:22-80`. Decision record has the Phase 45 defer at `.planning/MEMORY-REDESIGN-DECISIONS.md:99`. |
| 15 | Clean post-fix review exists and fixes are present. | PASS | `44-REVIEW.md` status is `clean` with zero findings. Current code contains the reviewed fixes: tenant-safe link/CWC checks (`src/memory/thread_case_links.py:115-153`, `src/memory/case_working_context.py:157-175`), trusted CWC provenance normalization (`src/memory/case_working_context_schemas.py:104-155`, `src/memory/case_working_context_service.py:166-185`), and staff-manual revision preservation (`src/memory/case_working_context.py:205-208`). |

Score: 15/15 must-haves verified.

## Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `src/db/migrations/versions/021_thread_case_links.py` | PASS | Exists, substantive DDL, chained to 020, creates `thread_case_links` and indexes. |
| `src/db/migrations/versions/022_case_working_context.py` | PASS | Exists, substantive DDL, chained to 021, creates CWC tables, widens audit CHECK, guarded downgrade. |
| `src/db/models.py` | PASS | Contains `ThreadCaseLink`, `CaseWorkingContext`, `CaseWorkingContextRevision`, and widened `MemoryWriteEvent` CHECK. |
| `src/memory/case_identity.py` | PASS | Resolver implemented and uses `RefundRepository.get_by_case_no`. |
| `src/memory/case_working_context_schemas.py` | PASS | Typed schemas and source-ref normalization implemented. |
| `src/memory/case_working_context.py` | PASS | Versioned repository, active read, advisory lock, revision append, hydration/dehydration mapping. |
| `src/memory/thread_case_links.py` | PASS | Link repository, dedup, bidirectional reads, tenant guards. |
| `src/memory/case_working_context_service.py` | PASS | Callable write service, isolated session, audit event emission, PII/conflict paths. |
| `src/conversation/repository.py` | PASS | Explicit `link_case` added; legacy `append_message`/`case_id` behavior remains additive. |
| `docs/contract-spec.md` | PASS | CWC and additive M:N contract text present in Section 13. |
| `tests/db/test_phase44_schema.py` and `tests/memory/test_*phase44*`/CWC/link tests | PASS | Current full Phase 44 test surface passes. |

`gsd-sdk query verify.artifacts` passed all declared artifacts for 44-01 through 44-04. `verify.key-links` passed 44-02 and 44-03. It false-negatived two shorthand links (`022_case_working_context.py` and `docs/contract-spec.md Section 13`) as "source file not found"; both were manually verified above.

## Key Link Verification

| Link | Status | Evidence |
|---|---|---|
| 022 migration -> 021 migration | PASS | `down_revision = "021_thread_case_links"` at `src/db/migrations/versions/022_case_working_context.py:18`. |
| ORM -> `refund_cases.id` UUID | PASS | CWC and thread links use UUID `ForeignKey("refund_cases.id")` at `src/db/models.py:602`, `src/db/models.py:1279`. |
| Resolver -> refund repository | PASS | `RefundRepository(session).get_by_case_no(...)` at `src/memory/case_identity.py:46`. |
| Repository -> revision table | PASS | `CaseWorkingContextRevision(...)` insert before update at `src/memory/case_working_context.py:109-120`. |
| Link lifecycle -> active unique/dedup | PASS | Active link lookup and return existing row at `src/memory/thread_case_links.py:43-49`, backed by active unique index at `src/db/models.py:1295-1302`. |
| CWC service -> audit events | PASS | `_emit_write_event` writes `memory_type=CASE_WORKING_CONTEXT_MEMORY_TYPE` at `src/memory/case_working_context_service.py:245-275`. |
| Contract spec -> implementation | PASS | Spec names `case_working_contexts`, `case_working_context_revisions`, and `thread_case_links` at `docs/contract-spec.md:1518-1526`; schema implements those tables. |

## Data-Flow Trace

| Surface | Data variable/source | Produces real data | Status |
|---|---|---|---|
| CWC active read | `CaseWorkingContextRepository.read_active(tenant_id, case_id)` queries `case_working_contexts` by tenant/case and `deleted_at IS NULL`. | Yes | PASS |
| CWC write | `CaseWorkingContextService.write_case_working_context` creates a trusted candidate, calls repository, and emits `MemoryWriteEvent`. | Yes | PASS |
| CWC revision path | Repository snapshots `dehydrate_content(hydrate_content(row))` into `case_working_context_revisions` before update. | Yes | PASS |
| Thread<->case link read/write | `ThreadCaseLinkRepository` writes and reads actual `thread_case_links` rows. | Yes | PASS |
| Graph auto-update/read-active hook | No graph node calls the CWC service or `link_case`; `src/agent/nodes/memory_write.py` still uses the existing `MemoryWriteService` path. | Intentionally absent | DEFERRED to Phase 45 |

## Commands and Results

Commands run in this verification:

| Command | Result |
|---|---|
| `gsd-sdk query roadmap.get-phase 44 --raw` | Loaded Phase 44 goal and 7 roadmap success criteria. |
| `gsd-sdk query verify.artifacts .../44-01-PLAN.md` | `all_passed: true`, 3/3 artifacts. |
| `gsd-sdk query verify.artifacts .../44-02-PLAN.md` | `all_passed: true`, 3/3 artifacts. |
| `gsd-sdk query verify.artifacts .../44-03-PLAN.md` | `all_passed: true`, 2/2 artifacts. |
| `gsd-sdk query verify.artifacts .../44-04-PLAN.md` | `all_passed: true`, 1/1 artifact. |
| `gsd-sdk query verify.key-links .../44-02-PLAN.md` | `all_verified: true`, 2/2 links. |
| `gsd-sdk query verify.key-links .../44-03-PLAN.md` | `all_verified: true`, 2/2 links. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py -q` | `48 passed, 5 warnings in 30.85s`. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` | `022_case_working_context (head)`. |
| `git show --stat --oneline 189d601` | Confirmed review fix commit `fix(44): enforce tenant-safe memory links` touches schema, services, tests, docs. |
| `git show --stat --oneline a5e59fe` | Confirmed review fix commit `fix(44): normalize CWC provenance` touches CWC schemas/service/repo/tests. |
| `git grep -n "case_memories\|long_term_memories" -- src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py` | No matches, confirming Phase 44 migrations did not rename/touch those table names. |
| `rg -n "alter_column\\(.*case_id|drop_column\\(.*case_id|conversation_threads.*case_id|case_id.*conversation_threads" src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py src/db/models.py` | Only `src/db/models.py:1251` existing `ix_conversation_threads_case_id` index; no destructive migration hit. |
| `rg -n "CaseWorkingContextService|write_case_working_context|link_case\\(|read_active\\(|case_working_context" src/agent src/memory src/conversation -g '*.py'` | Production hits are callable CWC/link surfaces only; no agent graph hook calls the CWC service. |

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| MEM-01 | PASS | Standalone `case_working_contexts` exists, keyed by tenant/case UUID, contextual-only, versioned, read/write service, audit event, trusted provenance, PII block, revisions, and Phase 45 hook defer. |
| MEM-02 | PASS | `thread_case_links` implements additive M:N; explicit write lifecycle and bidirectional reads are present; legacy single `conversation_threads.case_id` is not dropped/retyped/replaced. |

No orphaned Phase 44 requirements found: `.planning/REQUIREMENTS.md` maps MEM-01 and MEM-02 to Phase 44, and both are claimed by all four plans.

## Anti-Patterns and Residual Risk

No blocker anti-patterns were found in Phase 44 files. Grep hits for empty lists/`return []` were benign test/default/read-helper patterns, not stubs flowing to user-visible output.

Residual, non-blocking risks from `44-REVIEW.md` remain accurate:

- The service blocks `sensitive` and `prohibited` PII classifications but does not semantically scan arbitrary free text. This is acceptable for Phase 44 because the implemented gate is classification-based and the callable service is the delivered boundary.
- `staff_manual` provenance preservation is verified with a tenant-valid run id; caller authorization for manual edits is outside this phase.
- Raw SQL can bypass application-level tenant/run checks; covered repository/service paths enforce them.

## Human Verification

None required for this backend/schema/docs phase. There is no UI or external service behavior to visually inspect. The Phase 44 spec/review checkpoint is satisfied by the clean `44-REVIEW.md` post-fix review and the passing contract-alignment test.

## Deferred Items

The following is intentionally not a gap:

| Item | Addressed in | Evidence |
|---|---|---|
| Graph run-completion auto-update hook, CWC read-active consumer wiring, and real run/staff caller wiring for lifecycle hooks. | Phase 45 memory lifecycle wiring | Roadmap Phase 44 goal explicitly defers graph run-completion auto-update hook wiring. `.planning/MEMORY-REDESIGN-DECISIONS.md:99` states "auto-update hook wiring deferred to Phase 45 memory lifecycle wiring." Code search confirms no production graph hook calls the new CWC service. |

## Gaps Summary

No gaps remain. Phase 44 is complete with the Phase 45 lifecycle hook as a named defer.

---

Verified: 2026-07-02T19:05:35Z
Verifier: Codex (gsd-verifier)
