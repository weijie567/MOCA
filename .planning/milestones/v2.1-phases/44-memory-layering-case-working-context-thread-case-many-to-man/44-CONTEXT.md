# Phase 44: Memory Layering — Case Working Context + thread↔case Many-to-Many - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Source:** Synthesized from `.planning/MEMORY-REDESIGN-DECISIONS.md` (Claude↔user design discussion — this replaces a discuss-phase run; the discussion already happened).

<domain>
## Phase Boundary

This phase adds **one new memory layer** (`case_working_contexts`) and **one new relationship model** (thread↔case). "Two requirements" does NOT mean "just two tables": per D-SCOPE below, delivering MEM-01/MEM-02 correctly necessarily includes the case-identity resolution, the association-table write lifecycle, the audit-enum/version-history storage, and the contract-spec delta. Those are in scope as the *substance* of the two requirements — not scope creep.

**In scope (this phase does ONLY these two):**
1. **MEM-01 — Case Working Context layer**: a new `case_working_contexts` table plus its case-scoped read/write service. It aggregates the *current working state of one refund case* so the case survives across conversation threads and agent/staff handoffs.
2. **MEM-02 — thread↔case many-to-many**: a new association table replacing the current single nullable `case_id` foreign-key modeling, so a thread may touch multiple cases AND a case may span multiple threads/handoffs.

**Explicitly OUT of scope — deferred to later phases (recorded in `.planning/MEMORY-REDESIGN-DECISIONS.md` §"Deferred"):**
- ① Session memory (`session_memories`) changes — basically untouched this phase.
- ③ `case_memories` repositioning as reviewed precedent + closed-case precedent-candidate extraction.
- Narrow `long_term_memories` explicit-preference extraction path.
- Any automatic precedent publishing, vector/semantic retrieval work, Redis caching.

## Why (the core judgment driving this phase)

MOCA's real core memory is the **case-scoped "current case working context"**, not merchant profile / cross-case patterns. The business skeleton is already case-centric (`refund_cases`, `tickets`), but memory is scoped by `thread` and the case-scoped aggregate view does not exist. Fields for it are scattered (`tickets.summary`, `session_memories.session_summary` / `active_slots_json` / `unresolved_questions_json` / `last_business_context_refs_json`) with no case-scoped aggregation. This phase creates that missing layer.
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### D-CWC-1 — Case Working Context is a standalone table (P2)
- New table `case_working_contexts` (NOT a JSON column on `refund_cases`). Rationale: clean, versionable, auditable, matches the existing identity/audit governance style of `src/memory/`.
- Scope key is the **case** (tenant + case identity), NOT thread. It must survive across threads and handoffs.

### D-CWC-2 — Content it stores
Structured working state for one case:
- `customer_request` / `issue_type`
- `claims[]` — user assertions; each carries `verified: bool` + `source_ref`
- `verified_facts[]` — system-confirmed; each carries `source_ref` + `observed_at`
- `missing_info[]`
- `evidence_refs[]`
- `actions_taken[]` (with source_ref)
- `policy_refs[]` (doc_id / chunk_id / version — references only)
- `agent_recommendations[]` + `staff_decision` per recommendation
- `pending_tasks[]`
- `commitments[]` (with `confirmed_by_staff`)
- `next_action` (recommended_step + blocked_by)
- provenance: `updated_by_run_id`, `updated_at`, `version`

### D-CWC-3 — Authority & correctness constraints (LOCKED, safety-critical)
- **Non-authoritative**: the layer/its refs are `authority_class = "contextual_only"`, consistent with the existing memory contract. It is a hint surface, never an authoritative fact/decision source.
- **claim vs fact are stored separately** (a user claim must never silently become a verified fact).
- **tool-derived facts store only a reference/summary + `observed_at`**, never replacing the business system; the agent must still re-query the source system when it needs authority.
- **Never store**: policy body text, sensitive raw PII text.
- **Human-correctable**: staff can edit/override entries.
- **Versioned + provenance-bound**: every write records `run_id` / `source_ref` and bumps version; history retained.

### D-CWC-4 — Auto-update allowed, but bounded
- A completed run MAY auto-update the case working context (it is current-case working state, not generalized knowledge), subject to D-CWC-3.
- Required on write: tenant id + case id + source_ref present; claim/fact separated; tool facts carry observed_at.
- **Auto-updating a commitment or a transfer/escalation decision must be treated carefully** — these are high-consequence; prefer marking source/verified and allow staff correction rather than asserting them as authoritative.

### D-MM-1 — thread↔case many-to-many (P1)
- Add a thread↔case association table (both directions many). Replaces reliance on the single nullable `conversation_threads.case_id` (a `String(128)` with no FK) as the sole modeling. NOTE (verified against src/db/models.py): `session_memories` has NO `refund_case_id` column — that column lives on the `tickets` table (UUID FK → refund_cases.id). Do not assume a session→case FK exists.
- Existing single-FK columns: decide in planning whether to keep for back-compat or migrate reads through the association table. Do NOT silently break existing readers.

### D-REDLINE — Naming untouched (D5, hard red line)
- **DO NOT rename `case_memories` or `long_term_memories`.** They carry migration 011/013, identity hashes, replay identity contract, and eval manifest (`phase35_eval_manifest.py`) dependencies. Renaming = destructive multi-file schema change + replay-contract change → forbidden this phase.
- Semantic clarification (that `case_memories` = reviewed precedent, NOT active case state) is done via doc/comment only, and the NEW layer takes the new name `case_working_contexts` so it never collides with the old name.

### D-STORAGE — Postgres only (D2)
- Both new artifacts live in Postgres. No Redis. Rationale + scale math in decision record (≈167 QPS for the modeled load; Postgres has ample headroom; Redis conflicts with the persist+audit nature of this data).

### D-SCOPE — Codex review blockers folded into required scope (B2–B6, LOCKED)
These are NOT new capabilities beyond MEM-01/MEM-02 — they are the necessary implementation substance of those two requirements. A Codex cross-review (2026-07-02) confirmed all six against source; B1 was a factual error (already corrected: no `session_memories.refund_case_id`). The PLAN MUST cover each of the following; none may be left to "figure out during execution":

- **[B2] Canonical case identity is LOCKED to `refund_cases.id` (UUID).** The CWC scope key and the association table MUST bind to `refund_cases.id`, NOT to the `String(128)` `conversation_threads.case_id` (which currently holds the business number `refund_case_no`) and NOT to `refund_case_no` directly. The PLAN MUST define how the existing `conversation_threads.case_id` (refund_case_no string) resolves to `refund_cases.id` (UUID) — the tool layer passes `refund_case_no`, so a resolution/mapping step is mandatory, not optional.
- **[B3] Association-table write lifecycle MUST be defined.** Current `get_or_create_thread(case_id=None)` only writes the single legacy value; append-message / append-tool-call paths pass no case. The PLAN MUST specify who writes the thread↔case link, at what point in the flow, and how duplicates are de-duped. An association table with no writer is out of the question.
- **[B4] Audit enum extension is mandatory if reusing `memory_write_events`.** The DB CHECK on `memory_write_events.memory_type` only allows `session_slot | long_term_fact | case_memory | none` (verified src/db/models.py:647). Reusing that audit path REQUIRES an explicit migration to add a `case_working_context` value (and to widen the source-identity allowlist as needed). If the planner instead chooses a dedicated CWC audit trail, that is acceptable — but the choice MUST be explicit, not implicit.
- **[B5] Version-history storage MUST have a defined scheme.** `memory_write_events` records write *decisions*, not old/new content snapshots. "Versioned + history retained + human-correctable" (D-CWC-3) therefore needs an explicit storage design (e.g. version column + append-only revision rows, or a history table). The PLAN MUST state the chosen scheme.
- **[B6] Contract-spec delta MUST be addressed.** `docs/contract-spec.md` has no CWC entry. Per the project's spec↔phase rule, the PLAN MUST include either a spec update giving CWC a normative definition (authority `contextual_only`, NOT an `EvidenceRef`, distinct from `case_memory` reviewed precedent), or an explicit MVP-scope annotation in the spec pointing at the target phase. Silent divergence is forbidden.

### Claude's Discretion (planner decides, within the above)
- Exact column layout / JSONB vs relational split for the structured fields (within B5's chosen versioning scheme).
- Whether the write path reuses `memory_write_events` audit (with the B4 enum migration) or a dedicated CWC audit trail — explicit either way.
- Migration numbering (next after 020) and index design.
- Whether the auto-update hook lands in this phase or is scaffolded read/write + manual-update first (planner should call this out explicitly if it proposes to defer the auto hook).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design authority for this phase
- `.planning/MEMORY-REDESIGN-DECISIONS.md` — the full decision record (D1–D5, P1/P2/P3, deferred items). Primary design input.
- `.planning/ARCHITECTURE-DEBT.md` — memory subsystem debt context (this phase is the first memory cut).

### Contract / spec
- `docs/contract-spec.md` — normative contract source. Check whether the new layer needs a contract note; memory `authority_class = contextual_only` semantics live in the memory contract.

### Existing memory subsystem (patterns to match, NOT to rename)
- `src/db/models.py` — `SessionMemory`, `CaseMemory`, `LongTermMemory`, `MemoryTombstone`, `MemoryWriteEvent`, `RefundCase`, `Ticket`, `ConversationThread` table definitions; the `MEMORY_SCOPE_CHECK` / `MEMORY_REVIEW_STATUS_CHECK` / `MEMORY_PII_CLASSIFICATION_CHECK` constraint idioms.
- `src/memory/` — `schemas.py`, `identity.py`, `policy.py`, `repository.py`, `write_service.py`, `write_isolation.py`, `context_refs.py` (authority_class = contextual_only enforcement lives here).
- `src/db/migrations/versions/` — migration style; latest is `020_memory_write_event_policy_audit.py`.

### Business entities the case scope binds to
- `refund_cases`, `tickets`, `conversation_threads` (already carry `case_id` — the many-to-many replaces single-FK reliance).
</canonical_refs>

<specifics>
## Specific Ideas
- Example working-context JSON shape is in `.planning/MEMORY-REDESIGN-DECISIONS.md` (the user-provided sample with claims/verified_facts/missing_info/actions_taken/policy_refs/decision_trace/pending_tasks/commitments/next_action).
- ②③ are NOT fallbacks for each other: case working context (this case's live state) must never be backfilled from case precedent (other closed cases' experience).
</specifics>

<deferred>
## Deferred Ideas
- ① session memory changes; ③ case_memories precedent repositioning + closed-case precedent-candidate extraction; long_term narrow explicit-preference extraction; vector/semantic retrieval; Redis caching; automatic precedent publishing.
- All recorded with target-phase intent in `.planning/MEMORY-REDESIGN-DECISIONS.md`.
</deferred>

---

*Phase: 44-memory-layering-case-working-context-thread-case-many-to-man*
*Context synthesized 2026-07-02 from MEMORY-REDESIGN-DECISIONS.md (Claude↔user discussion in lieu of discuss-phase)*
