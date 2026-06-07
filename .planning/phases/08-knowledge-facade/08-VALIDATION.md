---
phase: 8
slug: knowledge-facade
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-07
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode = auto) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/knowledge -q` (new knowledge contract/golden tests) |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~quick: <15s knowledge tests; full suite longer (DB/integration) |

> Final new-test path (`tests/knowledge/` vs flat `tests/test_knowledge_*`) is fixed during planning; update the quick command if the planner chooses flat layout.

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched area (`uv run pytest tests/knowledge -q`, or the specific node test file).
- **After every plan wave:** Run `uv run pytest`.
- **Before `/gsd-verify-work`:** Full suite must be green, including the BLOCKING citation-membership eval.
- **Max feedback latency:** ~15 seconds for the knowledge contract/golden quick set.

---

## Per-Task Verification Map

> Each contract boundary the facade introduces maps to a deterministic golden/contract assertion. Task IDs are `{phase}-{plan}-{task}`. "File Exists" = ✅ when the test infra/file is created within the phase; ❌ W0 = created by a Wave 0 task in 08-01.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | KNOW-02 | — | evidence_text_hash.v1: NFC/strip/newline, no case-fold, sha256 lowercase | unit/golden | `uv run pytest tests/knowledge/test_text_hash.py -q` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | KNOW-02 | — | EvidenceRefV1 §8.3 field set; evidence_id = doc_key/chunk_id@policy_version; KnowledgeContext no extra identity fields | unit | `uv run pytest tests/knowledge/test_evidence_projection.py -q` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | KNOW-02 | — | canonical projection: score stripped, rank-aware sort; text_hash over full text; policy_version stable | unit/golden | `uv run pytest tests/knowledge/test_evidence_projection.py tests/knowledge/test_text_hash.py -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | KNOW-02 | — | config version literals retrieval.v3 / rerank.v2 | unit | `uv run python -c "import src.knowledge.config"` | ✅ | ⬜ pending |
| 08-02-02 | 02 | 2 | KNOW-02 | — | adapter maps chunk→EvidenceRefV1 with FULL-text hash, 1-based rank, v{version} | unit | `uv run pytest tests/knowledge/test_facade_status.py -q` | ✅ | ⬜ pending |
| 08-02-03 | 02 | 2 | KNOW-01 | — | facade preserves strong/partial/no_evidence; merchant_scope validation | contract | `uv run pytest tests/knowledge/test_facade_status.py tests/knowledge/test_tenant_scope.py -q` | ✅ | ⬜ pending |
| 08-02-04 | 02 | 2 | KNOW-01,KNOW-02 | T-mscope/T-tenant/T-efftime | status routing, full-text hash, effective_at determinism, tenant scope, merchant_scope reject | contract | `uv run pytest tests/knowledge/test_facade_status.py tests/knowledge/test_effective_time.py tests/knowledge/test_tenant_scope.py -q` | ✅ | ⬜ pending |
| 08-03-01 | 03 | 2 | KNOW-02 | — | validate_membership keys on evidence_id; empty citation → invalid; no LLM/DB | unit | `uv run pytest tests/knowledge/test_citation_membership.py -q` | ✅ | ⬜ pending |
| 08-03-02 | 03 | 2 | KNOW-02 | T-bare-chunk-id | present passes; absent/empty fails; same chunk_id diff evidence_id fails | unit | `uv run pytest tests/knowledge/test_citation_membership.py -q` | ✅ | ⬜ pending |
| 08-04-01 | 04 | 3 | KNOW-02 | — | AgentState.EvidenceRef carries canonical EvidenceRefV1 fields | unit | `uv run python -c "from src.agent.state import EvidenceRef; assert 'evidence_id' in EvidenceRef.__annotations__"` | ✅ | ⬜ pending |
| 08-04-02 | 04 | 3 | KNOW-01,KNOW-03 | T-safety-routing/T-merge-key/T-efftime | facade switch; merge by evidence_id; no_evidence/error routing preserved | node | `uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py -q` | ✅ | ⬜ pending |
| 08-04-03 | 04 | 3 | KNOW-02 | — | structured claims + evidence_id membership; all-invalid → citation_invalid | node | `uv run pytest tests/agent/test_nodes/test_generate_recommendation.py -q` | ✅ | ⬜ pending |
| 08-04-04 | 04 | 3 | KNOW-03 | T-safety-suppress | assess_risk suppresses proposed_action for citation_invalid/retrieval_error/insufficient_evidence | node | `uv run pytest tests/agent/test_nodes/test_assess_risk_and_approval.py -q` | ✅ | ⬜ pending |
| 08-04-05 | 04 | 3 | KNOW-02 | T-finalresp-keyerror | final_response renders EvidenceRefV1 refs without KeyError | node | `uv run pytest tests/agent/test_nodes/test_final_response.py -q` | ✅ | ⬜ pending |
| 08-04-06 | 04 | 3 | KNOW-01,KNOW-02 | — | node tests: strong/no_evidence/error; evidence_id merge; membership pass/fail; safety suppression | node | `uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q` | ✅ | ⬜ pending |
| 08-05-01 | 05 | 4 | KNOW-02 | T-dataset-drift | pinned dataset citation_membership.v1 with required cases | dataset | `uv run python -c "import json,pathlib; d=json.loads(pathlib.Path('tests/knowledge/datasets/citation_membership_v1.json').read_text()); assert d['version']=='citation_membership.v1'"` | ✅ | ⬜ pending |
| 08-05-02 | 05 | 4 | KNOW-02 | T-non-blocking/T-dataset-drift | BLOCKING membership eval; dataset hash pinned | eval (BLOCKING) | `uv run pytest tests/knowledge/test_citation_membership_eval.py -q` | ✅ | ⬜ pending |
| 08-05-03 | 05 | 4 | KNOW-01,KNOW-03 | T-safety-routing | e2e facade path: EvidenceRefV1 in state; no action on no_evidence/invalid | integration | `uv run pytest tests/knowledge/test_facade_integration.py -q` | ✅ | ⬜ pending |
| 08-05-04 | 05 | 4 | KNOW-01,KNOW-02,KNOW-03 | — | 08-EVAL-GATE.md records blocking/owner/version/hash + deferred owners | doc | manual review of `08-EVAL-GATE.md` | ✅ | ⬜ pending |
| 08-06-01 | 06 | 4 | KNOW-02 | T-evidence-undercount | trace.py evidence_count reads v2 evidence_refs | unit | `uv run pytest tests/agent/test_trace.py -q` | ✅ | ⬜ pending |
| 08-06-02 | 06 | 4 | KNOW-02 | T-evidence-undercount/T-dedupe-collapse | agent_runs evidence_count from evidence_refs; dedupe by evidence_id | api | `uv run pytest tests/test_agent_runs_api.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/knowledge/__init__.py` + `tests/knowledge/conftest.py` — shared fixtures (sample PolicyDocument/PolicyChunk, deterministic effective_at) for KNOW-01..03
- [ ] Golden fixture files for `evidence_text_hash.v1` and EvidenceRefV1 canonical projection
- [ ] Citation-membership eval dataset (owner = Phase 8) with pinned version + content hash
- [ ] No framework install needed — pytest 8.x + pytest-asyncio already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tenant-over-global precedence | KNOW-02 (deferred) | No global-policy schema in MVP (PolicyDocument.tenant_id NOT NULL); DEFERRED_WITH_OWNER to later policy-scope phase | Not validated in Phase 8 — owner + schema-and-query acceptance gate recorded in plan; no P8 test |
| Semantic groundedness/support | KNOW-02 (deferred) | Separate deferred eval; membership must NOT be treated as semantic support | Owned by separate deferred eval (eval-test-plan §20); not inferred from membership gate |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (every task carries an inline `uv run` verify command; Wave 0 = 08-01 infra + golden fixtures, 08-05 eval dataset)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests/knowledge module + conftest + golden fixtures in 08-01; eval dataset in 08-05)
- [x] No watch-mode flags
- [x] Feedback latency < 15s for knowledge quick set
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-07

> Note: plans express per-task verification via `<verify>` with an inline `uv run pytest ...` command rather than a literal `<automated>` tag. The content satisfies the Nyquist sampling intent (deterministic, automated, per-task). The executor treats each `<verify>` command as the task's automated gate.
