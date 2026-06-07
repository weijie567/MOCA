# Phase 8 Knowledge Facade Eval Gate

## Citation Membership Eval Gate

- Eval name: Citation membership.
- Blocking status: **BLOCKING**.
- Dataset owner: Phase 8.
- Dataset version: citation_membership.v1.
- Dataset content hash: `sha256:3ac980b66024b2e4ebd404690aa22722a3818ff22c2f9015134f1eda57ac681b`.
- Definition: every cited `evidence_id` must be present in `evidence_refs`; evaluation is deterministic and uses no LLM.
- Failure impact: a `no_evidence` or failed-membership result MUST NOT emit a deterministic action recommendation. Citation membership MUST NOT be counted as semantic claim support.

The blocking runner is `tests/knowledge/test_citation_membership_eval.py`. It verifies the pinned dataset bytes and fails the suite when any fixture verdict differs from `validate_membership`.

## AI-SPEC Disposition

AI-SPEC is intentionally **ABSENT**. Phase 8 is a refactor: the LangGraph + pgvector RAG framework and deterministic eval gate are already locked in `docs/contract-spec.md` §8.3 and `08-CONTEXT.md`. Recording this disposition prevents downstream review from misclassifying the absence as an implementation gap.

## Deferred: Semantic Groundedness/Support Eval

- Status: **DEFERRED_WITH_OWNER**.
- Owner: separate deferred RAG groundedness/support eval defined in `docs/eval-test-plan.md` §20.
- Rationale: semantic support requires a separate eval or reviewed rule-based claim-to-evidence mapping; it is NOT inferred from citation membership.
- Dependency: a labelled semantic-support dataset.
- Acceptance gate: the support eval passes on its own dataset; the citation-membership gate does not substitute for it.

## Spec Consistency Findings (Phase 8 consolidated)

| Finding | Evidence | Handling | Owner | Status |
| --- | --- | --- | --- | --- |
| `policy_version = v{version}` rather than the date-like spec JSON example | `src/db/models.py` `PolicyDocument.version` versus `docs/contract-spec.md` §8.3 example | Pinned derivation plus golden test in 08-01 | Phase 8 | COVERED |
| Ingestion did not bump version on content change (B1) | `src/rag/ingestion.py` previously overwrote `doc.content` without a version bump | Content-conditional bump in the same transaction plus 08-01 tests | Phase 8 | COVERED |
| Tenant-over-global deferred | `PolicyDocument.tenant_id` is NOT NULL; no global scope and no Phase 8 migration | Deterministic tenant-scoped behavior only; later schema-and-query gate | later policy-scope phase | DEFERRED_WITH_OWNER |
| `merchant_id` is not applicable as a policy DB filter (B4) | No merchant column on policy tables; `search_similar` takes no `merchant_id` | Facade validates `merchant_id` against `merchant_scope` as an authorization gate only; merchant-scoped policy query deferred | later policy-scope phase | DEFERRED_WITH_OWNER |
| Effective-time filter versus LIMIT ordering | `search_similar` orders and limits without an effective predicate | Adapter filters `effective_date` before final `top_k` truncation in 08-02 | Phase 8 | COVERED |
| `assess_risk_and_approval` only suppressed `insufficient_evidence` (B2) | Node previously built proposed actions for `citation_invalid` and `retrieval_error` | Extended no-action set to all three states in 08-04 task 5 | Phase 8 | COVERED |
| Observability consumers read legacy `data.evidence` or deduplicated by `chunk_id` | `src/agent/trace.py`, `src/api/routers/agent_runs.py` | Migrate to `evidence_refs` / `evidence_id` with legacy fallback in 08-06 | Phase 8 | COVERED |
| Legacy `src/rag/citation_validator.py` retained internally; new evidence-ID validator is `src/knowledge/citation.py` | D-C3 in `08-CONTEXT.md` | Keep legacy validator unmodified | Phase 8 | COVERED |
| `trace_id` / `merchant_scope` are not yet AgentState fields | `src/agent/state.py` | Build `KnowledgeContext` from trusted sources; full convergence in Phase 10 | Phase 10 | DEFERRED_WITH_OWNER |
| migration-plan §19 / Phase 7 baseline rollback | §19 Phase 8 row and Phase 7 baseline state direct cutover plus retained-adapter rollback, with no read-switch | **CONSISTENT**; no change needed | Phase 8 | COVERED |

## Requirements Coverage

- KNOW-01: 08-02 facade status contract plus 08-04 node switch.
- KNOW-02: 08-01 EvidenceRefV1/projection/version pin, 08-03 membership validator, 08-04 state/consumer migration, and 08-06 observability migration.
- KNOW-03: 08-04 facade switch with git-revert/adapter rollback and B2 no-action gate; no persistence/schema change; this plan's blocking eval gate.
