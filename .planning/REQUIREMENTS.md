# Requirements: MOCA v1.2 Long-term / Case Memory

**Defined:** 2026-06-17
**Core Value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Milestone Goal:** Implement reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 memory foundation without weakening policy evidence, session memory, approval/action authority, or replay/audit boundaries.

## v1.2 Requirements

Committed scope for the active v1.2 milestone. All requirements map to Phase 16.

### Identity & Schema

- [x] **MEMID-01**: Memory writes compute `memory_identity.v1` using canonical normalization and stable content/source hashing for long-term memories, case memories, tombstones, and candidate write events.
- [x] **MEMSCHEMA-01**: The database provides durable `long_term_memories`, `case_memories`, `memory_tombstones`, and `memory_write_events` storage with tenant/user/scope identity, review lifecycle, timestamps, and indexes/constraints needed for safe retrieval and migration rollback planning.

### Long-term Memory

- [x] **LONGMEM-01**: Long-term profile memory writes are accepted only from explicit user/admin/human-reviewed or deterministic durable sources, never from raw model guesses or unreviewed prompt inference.
- [x] **LONGMEM-02**: Long-term memory retrieval filters by tenant and allowed scope, approved/current status, freshness/expiry, and non-deleted/non-tombstoned/non-prohibited state.
- [x] **LONGMEM-03**: Long-term memory correction and supersede behavior is transactional and leaves exactly one current memory per identity.

### Case Memory

- [ ] **CASEMEM-01**: Reviewed case memory stores precedent summaries with stable case/source identity, outcome metadata, review status, and safe references back to authoritative records.
- [ ] **CASEMEM-02**: Case memory retrieval is distinct from long-term profile memory, session memory, policy evidence, and current business facts; it is surfaced only as reviewed precedent context.
- [ ] **CASEMEM-03**: The transitional `search_case_memory` surface no longer claims reviewed case memory unless backed by the new case memory store; old session-derived search is renamed, quarantined, or explicitly unavailable.

### Tombstone & Deletion

- [x] **TOMBSTONE-01**: Forget/delete operations create tombstone identities and retrieval excludes matching long-term or case memories immediately.
- [x] **TOMBSTONE-02**: Delayed or asynchronous candidate writes check tombstones in the same transaction before insert and emit `memory_write_event` records with a skip reason such as `tombstone_match` instead of rewriting deleted content.

### Prompt Context & Authority Boundary

- [ ] **MEMCTX-01**: `ContextAssembler` injects bounded long-term and case memory snippets with refs/summaries only, excluding raw memory records, raw tool payloads, policy full text, approval/action authority bodies, replay/debug blobs, and implicit dict/list stringification.
- [ ] **MEMCTX-02**: Memory cannot produce `EvidenceRefV1`, authorize actions, satisfy approval evidence, replace current business facts, alter replay/audit truth, or bypass approval/action safety contracts; tests enforce these negative boundaries.

### Review & Observability

- [x] **MEMREVIEW-01**: Memory candidate, approve/reject, write, skip, delete, supersede, and tombstone decisions are observable through review status and audit/replay-safe `memory_write_events`.
- [x] **MEMEVAL-01**: Contract tests and eval gates cover identity golden cases, retrieval predicates, correction/supersede, deletion/tombstone no-rewrite, authority-boundary negatives, and transitional `search_case_memory` behavior.

## Future Requirements

Tracked but not in the active v1.2 roadmap.

### User/Admin Memory UX

- **MEMUI-01**: User/admin memory management UI for reviewing, editing, deleting, and exporting memories.

### Retrieval Quality Expansion

- **MEMEMB-01**: Broader vector retrieval, reranking, and quality eval for memory after baseline predicates and lifecycle safety pass.

### External Execution

- **EXTERNAL-01**: External dispatch occurs only after transactional draft claim, execution creation, and committed outbox claim.
- **EXTERNAL-02**: Unknown/reconciling paths prevent unsafe retry with a new external idempotency key.
- **EXTERNAL-03**: Reconciliation, compensation, and duplicate execution/key guards are enforced.

### Policy Scope

- **POLICY-SCOPE-01**: Tenant-over-global global/default policy fallback with explicit schema and retrieval merge semantics.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real external action execution, outbox, reconciliation, and compensation | Remains owned by a future External Action Execution milestone; v1.2 must not blur demo draft-only safety. |
| Tenant-over-global global/default policy fallback | Requires a separate Policy Scope phase after external execution and must not be hidden inside memory retrieval. |
| Memory as policy evidence or approval/action authority | Violates the contract-spec boundary; memory is contextual assistance only. |
| Memory as current business fact source | Orders/refunds/tickets and policy KB remain authoritative; memory may only summarize reviewed context. |
| Full user-facing memory management UI | Useful later, but the v1.2 slice focuses on storage, review lifecycle, tombstones, retrieval predicates, and prompt integration. |
| New vector database service | PostgreSQL/pgvector remains the default unless Phase 16 planning proves a stronger need. |
| Storing raw prompts, raw tool payloads, private reasoning, or replay/debug blobs as memory | Conflicts with v1.1 prompt-safety, replay redaction, and storage boundaries. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEMID-01 | Phase 16 | Complete |
| MEMSCHEMA-01 | Phase 16 | Complete |
| LONGMEM-01 | Phase 16 | Complete |
| LONGMEM-02 | Phase 16 | Complete |
| LONGMEM-03 | Phase 16 | Complete |
| CASEMEM-01 | Phase 16 | Pending |
| CASEMEM-02 | Phase 16 | Pending |
| CASEMEM-03 | Phase 16 | Pending |
| TOMBSTONE-01 | Phase 16 | Complete |
| TOMBSTONE-02 | Phase 16 | Complete |
| MEMCTX-01 | Phase 16 | Pending |
| MEMCTX-02 | Phase 16 | Pending |
| MEMREVIEW-01 | Phase 16 | Complete |
| MEMEVAL-01 | Phase 16 | Complete |

**Coverage:**
- v1.2 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---
*Requirements defined: 2026-06-17*
*Last updated: 2026-06-17 after Phase 16 Plan 05 tombstone/supersede*
