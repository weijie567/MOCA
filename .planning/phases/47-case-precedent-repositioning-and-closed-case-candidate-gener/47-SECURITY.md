---
phase: 47
slug: case-precedent-repositioning-and-closed-case-candidate-gener
status: verified
threats_total: 20
unique_threat_ids: 6
threats_closed: 20
threats_open: 0
asvs_level: 2
block_on: open
created: 2026-07-04
verified: 2026-07-04
---

# Phase 47 - Security

Per-phase security verification for Phase 47: Case precedent repositioning and closed-case candidate generation.

This audit verified all threat registers from `47-01-PLAN.md` through `47-04-PLAN.md` against implemented code, docs, tests, review artifacts, and fresh local test execution. All registered threats have disposition `mitigate`; there are no accepted or transferred risks.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| docs/plans -> executor | Contract text and static tests define later runtime semantics. | Phase 47 case-memory contract, static red lines, validation commands |
| closed-case source type -> case memory policy | `closed_case_cwc_candidate` enters case-memory source classification. | Provenance, review status, source refs |
| trusted close caller -> internal service seam | Caller provides explicit terminal close inputs; no public close endpoint is introduced. | tenant id, case id, run id, close event id, close status, closed_at |
| business case row -> retrieval scope | Tenant-bound `RefundCase -> Order` lookup resolves merchant or exact case scope. | Refund case identity, merchant id |
| CWC snapshot -> case-memory candidate | Contextual-only CWC content is projected into prompt-safe reviewed-memory candidate fields. | CWC summaries, policy ref metadata, PII classification |
| projection service -> case memory service | Candidate persistence enters existing review/audit/dedupe policy. | `CaseMemoryWriteCandidate`, `MemorySourceRefV1`, write event |
| pending row -> reviewed retrieval | Approval is the only publication transition. | review status, retrieval filters |
| ToolCallContext -> search_case_memory | Planner-facing tool receives actor scope, not source case identity. | tenant/user/thread/merchant scope |
| docs/validation -> future phases | Phase closeout must not imply Phase 48 or schema/table rewrites. | final validation, DEFER-3 trace |

## Threat Flags

No unregistered flags.

All four summaries state `None beyond the plan threat model` in `## Threat Flags`. Review/fix artifacts introduced two fixed review findings, both covered by tests and verification:

- WR-01: distinct same-merchant generated precedents no longer collapse by generic summary; content identity now includes full projected text for `closed_case_cwc_candidate`.
- WR-02: reviewed-memory retrieval uses slot `issue_type` for case type, not `primary_intent`.

## Threat Verification

| Plan | Threat ID | Category | Component | Disposition | Status | Evidence |
|------|-----------|----------|-----------|-------------|--------|----------|
| 47-01 | T-47-03 | T/I | `src/memory/policy.py`, `src/memory/schemas.py` | mitigate | closed | `CaseMemorySourceType` includes `closed_case_cwc_candidate` in `src/memory/schemas.py:263`; review-required only in `src/memory/policy.py:71-88`; tests assert `needs_review` and not auto-approved in `tests/memory/test_memory_policy.py:84-97`. |
| 47-01 | T-47-04 | I | contract/static tests | mitigate | closed | Contract forbids policy body text, raw tool payloads, authority bodies, replay/debug blobs, and sensitive raw PII in `docs/contract-spec.md:1523`; static/doc tests cover required terms and forbidden imports in `tests/memory/test_phase47_case_precedent_alignment.py:43-54` and `193-207`. |
| 47-01 | T-47-06 | E/T | CWC/case-memory boundary | mitigate | closed | Contract states generated precedent is not policy/current fact/action/audit/replay authority in `docs/contract-spec.md:1519-1527`; CWC stays contextual-only in `docs/contract-spec.md:1531-1535`. |
| 47-01 | T-47-01 | S/E | AgentRun finalizer and CWC finalizer | mitigate | closed | Static guard forbids `generate_closed_case_precedent_candidate`, `ClosedCasePrecedentService`, and `closed_case_cwc_candidate` in completed-run/CWC-finalizer paths at `tests/memory/test_phase47_case_precedent_alignment.py:143-151`; grep found no public close-route hook. |
| 47-01 | T-47-05 | R/T | source-ref identity | mitigate | closed | `MemorySourceRefV1` remains fixed in `src/memory/schemas.py:13-25`; `ALLOWED_SOURCE_REF_KEYS` remains fixed in `src/memory/identity.py:19-31`; tests reject `cwc_version` and `closed_at` keys in `tests/memory/test_phase47_case_precedent_alignment.py:171-190`. |
| 47-02 | T-47-01 | S/E | `ClosedCasePrecedentService.generate_closed_case_precedent_candidate` | mitigate | closed | Terminal allowlist is exactly `closed/refunded/rejected` at `src/memory/case_precedent.py:18`; non-terminal statuses skip before lookup at `src/memory/case_precedent.py:72-80`; tests cover `open`, `reviewing`, and unknown status in `tests/memory/test_case_precedent_generation.py:220-239`; no public close endpoint grep matches. |
| 47-02 | T-47-02 | I | scope resolution and refund repo | mitigate | closed | `RefundRepository.get_by_id_with_order` filters by `case_id` and `tenant_id` and loads order at `src/repositories/refund_repo.py:23-33`; active CWC is read by tenant/case at `src/memory/case_precedent.py:92-95`; scope resolver returns merchant or exact case only at `src/memory/case_precedent.py:148-153`; tests cover merchant scope and exact-case fallback in `tests/memory/test_case_precedent_generation.py:292-337` and `578-585`. |
| 47-02 | T-47-04 | I | `_project_closed_case_candidate` | mitigate | closed | Projection maps policy refs to `doc_key/chunk_id/policy_version` only at `src/memory/case_precedent.py:221-236`; bounded text strips forbidden markers at `src/memory/case_precedent.py:302-311`; tests cover claim/fact separation, ref mapping, marker stripping, and blocked PII in `tests/memory/test_case_precedent_generation.py:588-658`. |
| 47-02 | T-47-06 | T/E | claim/fact projection | mitigate | closed | Fixed caveat text is defined at `src/memory/case_precedent.py:19-22`; excerpt labels claims and verified facts separately at `src/memory/case_precedent.py:239-253`; tests assert labels and caveat at `tests/memory/test_case_precedent_generation.py:588-621`. |
| 47-02 | T-47-03 | I/T | future candidate write path | mitigate | closed | Candidate source is `closed_case_cwc_candidate` at `src/memory/case_precedent.py:180` and `211`; Phase 47-03 completed the write path through `CaseMemoryService.submit_case_memory_candidate(...)` at `src/memory/case_precedent.py:113`. |
| 47-03 | T-47-03 | T/I | `ClosedCasePrecedentService`, `CaseMemoryService.submit_case_memory_candidate` | mitigate | closed | Accepted terminal projections call `submit_case_memory_candidate` only at `src/memory/case_precedent.py:113`; service policy/write/event lifecycle is in `src/memory/case_memory.py:490-620`; pending hidden until approval is tested at `tests/memory/test_case_precedent_generation.py:518-575`; review API coverage is in `tests/test_memory_review_api.py:88-150`. |
| 47-03 | T-47-05 | R/T | source identity and duplicate handling | mitigate | closed | Source identity uses allowed `event_id` and `outcome_id` at `src/memory/case_precedent.py:282-299`; duplicate checks reuse existing service behavior at `src/memory/case_memory.py:555-586`; WR-01 content identity fix hashes full generated text at `src/memory/case_memory.py:786-799`; tests cover duplicate and same-merchant distinct content at `tests/memory/test_case_precedent_generation.py:340-456`. |
| 47-03 | T-47-04 | I | PII-blocked CWC rows | mitigate | closed | Sensitive/prohibited CWC rows submit fixed non-sensitive blocked text at `src/memory/case_precedent.py:168-187`; existing service emits `pii_blocked` skip event without row insert at `src/memory/case_memory.py:531-553`; tests cover event and no-row behavior in `tests/memory/test_case_precedent_generation.py:485-515`. |
| 47-03 | T-47-02 | I | reviewed retrieval tenant/scope filters | mitigate | closed | Retrieval filters tenant, scope, published status, active rows, and prompt-safe PII at `src/memory/case_memory.py:409-458`; tests exclude wrong merchant, cross-tenant, needs-review, rejected, deleted, expired, tombstoned, sensitive, and prohibited rows in `tests/memory/test_case_memory_retrieval.py:515-648`. |
| 47-03 | T-47-06 | E/T | candidate caveats and source refs | mitigate | closed | Caveats persist from projection at `src/memory/case_precedent.py:19-22` and search output keeps safe source/policy refs only at `src/memory/case_memory.py:957-987`; tests assert retrieved policy refs after approval at `tests/memory/test_case_precedent_generation.py:562-575`. |
| 47-04 | T-47-02 | I | reviewed memory context and `search_case_memory` retrieval | mitigate | closed | Approved generated precedents retrieve without embeddings under merchant and exact case scopes in `tests/memory/test_case_memory_retrieval.py:515-689`; reviewed memory context returns approved generated precedent at `tests/memory/test_reviewed_memory_context_boundary.py:522-560`; planner tool builds tenant/user/thread/merchant scopes only at `src/tools/executors/memory.py:62-84`. |
| 47-04 | T-47-03 | T/I | reviewed retrieval publication boundary | mitigate | closed | `CaseMemoryRepository.search_reviewed` only publishes `auto_approved`/`approved` rows at `src/memory/case_memory.py:409-458`; generated `needs_review` is hidden until approval in `tests/memory/test_case_precedent_generation.py:518-575`. |
| 47-04 | T-47-04 | I | prompt-safe retrieval output | mitigate | closed | Search item output passes through safe policy/source ref projection at `src/memory/case_memory.py:957-987`; tool schema rejects raw tool payload in `tests/tools/test_catalog.py:507-540`; focused suite includes reviewed context and tool tests. |
| 47-04 | T-47-06 | E/T | docs and tool contract | mitigate | closed | Contract states precedent is contextual assistance only and not authority at `docs/contract-spec.md:1519-1527`; `ToolCallContext` has no `case_id` at `src/tools/contracts.py:13-37`; tests reject `case_id` and assert tenant/user/thread/merchant scope construction in `tests/tools/test_catalog.py:349-376`. |
| 47-04 | T-47-05 | R/T | validation artifact and ledgers | mitigate | closed | `47-VALIDATION.md` is complete and records approved commands/results at `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-VALIDATION.md:79-104`; DEFER-3 remains Phase 48 in `.planning/MEMORY-REDESIGN-DECISIONS.md:107`; no Phase 47 migration exists by migration listing and static guard. |

## Accepted Risks Log

No accepted risks.

## Transferred Risks Log

No transferred risks.

## Validation Evidence

Fresh command run during this security audit:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -q
```

Result: `123 passed, 1 warning in 122.19s (0:02:02)`. The warning is the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

Additional relied-on artifacts:

- `47-VERIFICATION.md`: verifier passed 6/6 must-haves and recorded no gaps.
- `47-VALIDATION.md`: final Phase 47 gate recorded `151 passed, 1 warning`; Phase 45/46 alignment recorded `20 passed, 1 warning`; Ruff recorded `All checks passed!`.
- `47-REVIEW.md`: deep re-review found no critical or warning issues; only info-only doc drift remained and is now covered by `tests/memory/test_phase47_case_precedent_alignment.py:57-82`.
- `47-REVIEW-FIX.md`: WR-01 and WR-02 were fixed and covered by focused tests.

All test command references use the MOCA-approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` entrypoint. No invalid local test-entrypoint result is used as evidence.

## Security Audit Trail

| Audit Date | Threat Entries | Unique Threat IDs | Closed | Open | Run By |
|------------|----------------|-------------------|--------|------|--------|
| 2026-07-04 | 20 | 6 | 20 | 0 | Codex gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition.
- [x] All `mitigate` threats were verified against code, docs, tests, or validation artifacts.
- [x] Accepted risks documented: none.
- [x] Transfer documentation required: none.
- [x] Summary threat flags incorporated.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-07-04
