# Phase 44 Research — Case Working Context + thread↔case Many-to-Many

**Researched:** 2026-07-02
**Method:** Main-session repository verification (no subagent, per project rule). All facts below are grep/read-verified against `src/`, not doc-derived.
**Requirements:** MEM-01 (Case Working Context layer), MEM-02 (thread↔case many-to-many)
**Consumes:** `44-CONTEXT.md` (locked decisions D-CWC-*, D-MM-*, D-SCOPE-*, D-REDLINE, D-STORAGE)

> Purpose: answer "what must the planner know to plan Phase 44 well?" — verified current-state facts, reusable patterns, and the landmines Codex flagged (B1–B6), so plans bind to real code, not assumptions.

---

## 0. Codex pre-plan audit outcome (adjudicated)

Codex reviewed `44-CONTEXT.md` and raised 6 blockers. All 6 were adjudicated against the repo and **upheld** (zero false positives). B1 was my own factual error (now corrected in CONTEXT.md + decision record). B2–B6 are scope-tightening: necessary parts of delivering MEM-01/02 that must be explicit PLAN scope, not "planner's discretion". This research resolves the concrete facts each blocker needs. See §5 for the blocker→fact map.

---

## 1. Current-state facts (grep/read-verified)

### 1.1 thread↔case modeling — single string, no FK, never written with a case
- `ConversationThread.case_id` is `String(128)`, nullable, **no ForeignKey** (`src/db/models.py`). Index `ix_conversation_threads_case_id` exists.
- `ConversationSummary.case_id` is also `String(128)`, nullable.
- `SessionMemory` has **NO** `refund_case_id` / `case_id` column (verified full column list). The `refund_case_id` column lives on **`Ticket`** (UUID FK → `refund_cases.id`). (This corrects B1.)
- **B3 hard evidence:** `ConversationRepository.get_or_create_thread(..., case_id: str | None = None)` accepts a case_id, but `append_message()` calls `get_or_create_thread(tenant_id, user_id, thread_id)` **without passing case_id**. So after the first turn, a thread's `case_id` is whatever it was created with (often None) and is never back-filled. There is no lifecycle that associates a thread with additional cases. A join table with no writer would stay empty (the exact failure mode we already saw with long_term/case candidates).

### 1.2 Case identity is three-formed (B2)
- `refund_cases.id` = UUID (PK); `refund_cases.refund_case_no` = `String(64)` unique business number.
- Business/tool layer keys on **`refund_case_no`** (string): `src/business/service.py` `get_refund_case(refund_case_no)`, `src/tools/catalog.py`, `src/business/adapters.py` (`resource_id = refund_case_no`).
- `conversation_threads.case_id` = `String(128)`, no FK — free-form, not guaranteed to be either the UUID or the case_no.
- **Implication for planner:** the CWC scope key must be pinned. Decision to lock in PLAN: bind to `refund_cases.id` (UUID) as the canonical case identity, and define how a `refund_case_no`/thread `case_id` string resolves to it. Do NOT let the planner store a bare string of ambiguous form.

### 1.3 Existing memory write/audit machinery (reuse surface)
- `MemoryWriteService` (`src/memory/write_service.py`): `propose_candidates(state, *, requested_types=None)` (defaults to `{"session"}`), `evaluate_policy(candidate)`, `apply_policy_and_write(candidates)`, `apply_policy_and_write_all(candidates)`. Candidate union is `Session|LongTerm|Case`.
- `run_memory_side_effect_in_isolated_session` (`src/memory/write_isolation.py`): runs memory writes in a child DB session so a rollback can't poison the caller txn. CWC auto-update should reuse this.
- Identity helpers (`src/memory/identity.py`): `canonical_memory_content_hash`, `canonical_source_identity_hash`, `canonical_memory_candidate_hash`, with `ALLOWED_SOURCE_REF_KEYS` allowlist.
- `authority_class = "contextual_only"` is enforced in `src/memory/context_refs.py` as a hardcoded Literal on every ref model.

### 1.4 Audit enum is closed (B4)
- `memory_write_events.memory_type` CHECK = `IN ('session_slot','long_term_fact','case_memory','none')` (`src/db/models.py`, migration 020). It does **not** include a CWC type. Reusing the audit trail requires an explicit enum extension via migration + model + policy literal — cannot be left implicit.

### 1.5 Versioning gap (B5)
- `SessionMemory`/`LongTermMemory` carry an integer `version` and `LongTermMemory` has a supersede chain, but `memory_write_events` stores decisions, **not** old/new content snapshots. "History retained + human-correctable" for CWC has no existing snapshot mechanism — PLAN must define its own (candidate approach: monotonic `version` on the row + append-only revision rows, or a `case_working_context_revisions` table).

### 1.6 Contract-spec gap (B6)
- `docs/contract-spec.md` memory-layer section has no CWC entry. Per project "spec supports, phase decides" rule, PLAN must either add a normative CWC contract note (authority_class = contextual_only, NOT an EvidenceRef, distinct from case_memory precedent) or record an explicit MVP-scope annotation with a target phase.

---

## 2. Migration + table style to match (so the new table looks native)

- **Latest migration:** `020_memory_write_event_policy_audit.py` (alter-column style). **Build-a-table template:** `013_long_term_case_memory.py` (creates `long_term_memories`, `case_memories`, `memory_tombstones`, `memory_write_events`).
- Next revision id: `021_...`; `down_revision = "020_memory_write_event_policy_audit"`.
- Table idioms from 013 (`case_memories` block) the new table should mirror:
  - `id` UUID PK; `tenant_id` UUID FK→tenants.id NOT NULL; `schema_version String(48)` with `server_default` (e.g. `case_working_context.v1`).
  - JSONB columns via `postgresql.JSONB(astext_type=sa.Text())` with `server_default=_jsonb_empty_array()` / `_jsonb_empty_object()` helpers.
  - `created_by_run_id` UUID FK→agent_runs.id; `deleted_at` soft-delete; `*_timestamps()` helper for created/updated.
  - `sa.CheckConstraint(...)` for enum-like columns, named `ck_<table>_<field>`; partial indexes via `postgresql_where=sa.text("deleted_at IS NULL")`.
  - Model side (`src/db/models.py`) mirrors with `Mapped[...]` + shared `MEMORY_*_CHECK` constants where applicable.

---

## 3. thread↔case M:N — additive design constraints

- **26 files reference `case_id`** across agent/business/tools/api/replay (full list captured during research). The M:N table must be **additive**: keep `conversation_threads.case_id` as-is so no existing reader breaks; the association table is a new parallel structure.
- Planner must define, for MEM-02: the association table shape (tenant_id, thread_id, case_id UUID FK, timestamps, uniqueness), **who writes it and when** (the missing lifecycle from §1.1 — candidate: write on thread/case linkage points, not silently in append_message), and dedup (unique constraint on tenant+thread+case).
- **Do NOT** migrate existing readers off `case_id` in this phase — that would explode blast radius across 26 files. Keep reads working; add the M:N as the new source of truth for "which cases has this thread touched", to be adopted incrementally in later phases.

---

## 4. Reuse vs build decision inputs (for planner)

| Concern | Reuse | Build new |
|---|---|---|
| Isolated write txn | `run_memory_side_effect_in_isolated_session` | — |
| Identity/source hashing | `src/memory/identity.py` helpers + `ALLOWED_SOURCE_REF_KEYS` | possibly add CWC source_type(s) to allowlist |
| Audit trail | `memory_write_events` | **extend** memory_type enum (B4) + optional CWC-specific reason codes |
| authority_class contextual_only | `context_refs.py` Literal pattern | new CWC ref model following same pattern |
| Versioning/history | integer `version` idiom | **new** snapshot/revision mechanism (B5) |
| Write orchestration | `MemoryWriteService` candidate pattern | CWC candidate type + `requested_types` wiring |

---

## 5. Blocker → resolved-fact map (planner MUST honor)

| # | Blocker | Resolved fact / required PLAN action |
|---|---|---|
| B1 | session→case FK assumed | **False** — no such column; corrected. thread↔case is the only linkage surface. |
| B2 | case identity ambiguous | Three forms exist. PLAN locks CWC scope to `refund_cases.id` (UUID) + defines string→UUID resolution. |
| B3 | join table has no writer | `append_message` drops case_id. PLAN must define the M:N write lifecycle + dedup. |
| B4 | audit enum closed | PLAN adds CWC `memory_type` value via migration + model + policy literal. |
| B5 | no snapshot/version store | PLAN defines CWC version/history storage explicitly. |
| B6 | no spec contract entry | PLAN adds contract-spec CWC note or explicit MVP-scope annotation w/ target phase. |

---

## 6. Open items the planner must decide (within locked CONTEXT)

- CWC structured fields: JSONB blob vs relational split (CONTEXT leaves to discretion; recommend JSONB for the nested claim/fact/action arrays, relational for scope/provenance/version columns).
- Whether the auto-update hook lands this phase or is scaffolded (read/write + manual update) first — CONTEXT requires the planner to state this explicitly.
- Whether CWC write reuses `MemoryWriteService.propose_candidates` (`requested_types={"case_working_context"}`) or a dedicated service — reuse preferred for audit consistency.

---

*Research complete. All §1 facts source-verified. Companion: 44-CONTEXT.md, MEMORY-REDESIGN-DECISIONS.md.*
