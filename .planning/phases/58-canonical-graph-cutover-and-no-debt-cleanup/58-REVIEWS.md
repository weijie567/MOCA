---
phase: 58
reviewers: [claude]
reviewed_at: 2026-07-07T23:51:02Z
plans_reviewed:
  - 58-01-PLAN.md
  - 58-02-PLAN.md
  - 58-03-PLAN.md
  - 58-04-PLAN.md
  - 58-05-PLAN.md
  - 58-06-PLAN.md
---

# Cross-AI Plan Review — Phase 58

## Claude Review

### Summary

The six-plan structure is directionally correct and materially better than a single large cleanup plan. It follows ownership boundaries, keeps approval retry authority canonical, avoids bulk historical DB rewrites, and uses approved MOCA command entrypoints. However, the review does not consider the plan clean. The largest concern is incomplete Phase 58 legacy cleanup coverage: the plans emphasize `generate_recommendation` and `assess_risk_and_approval`, but do not clearly delete, internalize, or historical-only reclassify other migration surfaces such as `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `route_after_intent`, and `route_after_slots`. That gap can prevent CAGM-09 from closing as a true no-debt migration.

### Strengths

- Plan granularity is good: six plans across graph/vocabulary, canonical implementation ownership, wrapper/import cleanup, projection/eval/frontend, approval retry, and docs/validation closeout.
- Dependency ordering is mostly correct: `58-01 -> 58-02 -> 58-03 -> 58-04/58-05 -> 58-06`.
- Approval retry design is strong: persisted historical metadata is separated from current graph route authority and must emit canonical `risk_gate`.
- Historical production data is not bulk-rewritten.
- Verification commands use approved MOCA entrypoints (`UV_CACHE_DIR=/tmp/uv-cache uv run ...` and frontend npm build).
- Final validation has broad coverage: pytest, ruff, frontend build, strict classifier, `git diff --check`, metadata closeout, and Chinese architecture debt entry.

### Concerns

#### HIGH — Remaining Legacy Wrapper / Helper Cleanup Is Incomplete

Affected plan area: `58-03-PLAN.md`

`58-03` currently focuses on deleting:

- `src/agent/nodes/generate_recommendation.py`
- `src/agent/nodes/assess_risk_and_approval.py`

The review says Phase 58 still needs an explicit task or plan decision for:

- `src/agent/nodes/classify_intent.py`
- `src/agent/nodes/session_memory_load.py`
- `src/agent/nodes/extract_slots.py`
- `src/agent/nodes/long_term_memory_retrieve.py`
- `src/agent/routing.py::route_after_intent`
- `src/agent/routing.py::route_after_slots`

Required change: each surface must be deleted, moved behind canonical/private implementation, or retained only as explicitly internal/historical with static proof that it is not active runtime compatibility.

#### HIGH — Route Delegate Removal Is Not a Concrete Task

Affected plan areas: `58-01-PLAN.md`, `58-03-PLAN.md`, `58-06-PLAN.md`

`58-01` removes `route_after_intent` / `route_after_slots` from graph vocabulary, but no plan clearly modifies `src/agent/routing.py` to remove or internalize the public compatibility delegates. Deleting vocabulary aliases alone does not close source-level route helper debt.

Required change: add acceptance criteria that `src/agent/routing.py` no longer defines public `route_after_intent` / `route_after_slots`, or explicitly documents them as internal historical-only helpers with a strong reason and static classifier category.

#### HIGH — Legacy-Named Test Strategy Conflicts With Wave 0

Affected plan areas: `58-VALIDATION.md`, `58-03-PLAN.md`, `58-06-PLAN.md`

Wave 0 says tests whose filenames encode deleted legacy node names should be renamed or rewritten. The plans still preserve `tests/agent/test_nodes/test_generate_recommendation.py` and include it in final broad verification. If wrapper deletion succeeds, that legacy-named test can force a permanent classifier exception.

Recommended change:

- Rename `tests/agent/test_nodes/test_generate_recommendation.py` to `tests/agent/test_nodes/test_recommendation_generation.py`, or explicitly justify and classify it as canonical despite the name.
- Delete or migrate `tests/agent/test_nodes/test_assess_risk_and_approval.py`.
- Apply the same strategy to any retained `test_classify_intent.py`, `test_extract_slots.py`, or similar legacy-named tests.

#### MEDIUM — Historical Projection API Boundary Needs More Detail

Affected plan area: `58-01-PLAN.md`

The plan correctly asks to split active runtime vocabulary from historical projection, but it does not make downstream call-site expectations concrete enough. Existing callers may depend on `graph_vocabulary_entry()` / `target_graph_name()` for both current runtime and historical trace projection.

Recommended change: `58-01` should explicitly define:

- current runtime vocabulary API behavior;
- historical projection API behavior;
- how `project_trace_step_for_contract()` handles old stored rows;
- which downstream files must be read/adapted in later plans (`src/agent/trace.py`, `src/repositories/trace_repo.py`, `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, trace/API tests).

#### MEDIUM — Static Classifier Strict Mode Semantics Need to Be Explicit

Affected plan areas: `58-01-PLAN.md`, downstream verification commands

The review agrees with strict classifier usage only if `--strict` means:

- fail when `active_runtime_legacy > 0`;
- fail when `unclassified_rows > 0`;
- do not require `total_hits == 0` during early waves or for legitimate historical/docs rows.

Required change: add explicit acceptance criteria to avoid executors deleting all legacy strings indiscriminately.

#### MEDIUM — `moca.egg-info/SOURCES.txt` Is Not Addressed

Affected plan areas: `58-03-PLAN.md`, `58-06-PLAN.md`

Research noted stale legacy module filenames may appear in `moca.egg-info/SOURCES.txt`, but the plans do not say whether the file is tracked or how to handle it.

Required change: check `git ls-files moca.egg-info/SOURCES.txt`. If tracked, regenerate/update or classify it deliberately; if ignored/untracked, record why it is outside source-contract scan.

#### MEDIUM — Docs Guard Is Too Brittle

Affected plan area: `58-06-PLAN.md`

The inline docs guard checks a small exact `bad_terms` list and may miss Chinese/current wording or force awkward node-list stuffing into docs. The review recommends using `scripts/classify_phase58_legacy_hits.py` as the main docs/current-wording guard instead of fragile exact string checks.

Required change: make docs guard rely on classifier categories for old-name rows, especially distinguishing historical/reference rows from active/current authority rows.

#### LOW — Intermediate Legacy Wrapper Stubs Need Care

Affected plan area: `58-02-PLAN.md`

The two-step approach is safe, but `58-02` should ensure legacy wrapper files are no longer used by tests after implementation ownership moves, so `58-03` can delete them without a larger follow-up diff.

#### LOW — Frontend Build Is Acceptable But Frontend-Specific Tests Are Not Mentioned

Affected plan area: `58-04-PLAN.md`

`npm --prefix frontend run build` is acceptable if no frontend timeline unit test exists. If a frontend test script exists, consider running it. Otherwise, record in the summary that frontend behavior is verified through build plus backend payload tests.

### Suggestions

- Add a dedicated task or plan for all remaining legacy wrappers/helpers and route delegates.
- Rename or explicitly classify legacy-named tests so the final classifier does not depend on unclear exceptions.
- Make the static classifier the primary docs/current-wording gate.
- Clarify the historical projection API split in `58-01`.
- Check and decide `moca.egg-info/SOURCES.txt`.
- Add explicit approval retry negative test names such as `test_fresh_legacy_resume_route_fails_closed` and `test_persisted_historical_retry_route_canonicalizes_to_risk_gate`.

### Risk Assessment

Overall risk: MEDIUM-HIGH.

The direction and sequencing are solid, and approval security is well-covered. The main risk is that "no-debt cleanup" becomes a partial cleanup: active graph nodes and `generate_recommendation` / `assess_risk_and_approval` can be cleaned while older intent/session/slot/memory wrappers and route delegates remain as Phase 58 debt. The plan should be revised before execution.

---

## Consensus Summary

Only Claude review was requested by autopilot at this stage.

### Agreed Strengths

- Six-plan split satisfies the plan-granularity requirement better than the initial oversized cleanup plan.
- Approval retry route authority is correctly treated as security-sensitive and canonical-only.
- Validation commands follow the MOCA `uv run` rule.

### Agreed Concerns

- Legacy cleanup coverage must include all Phase 52-57 compatibility surfaces, not just recommendation/risk wrappers.
- Static classifier semantics and docs guard must be strong enough to distinguish active debt from historical references.
- Legacy-named tests/build metadata need explicit treatment to avoid permanent no-debt exceptions.

### Divergent Views

None recorded; only one external reviewer ran.

---

## Claude Re-Review After 10-Plan Repair

Reviewed after the original `58-03` cleanup plan was split into ten active plans and GSD plan-checker passed.

Verdict: NOT CLEAN

### Blocker

- `58-VALIDATION.md` and `58-10-PLAN.md` still used a bare `git ls-files ... && ! rg ...` command as the `moca.egg-info/SOURCES.txt` metadata proof. Claude classified this as a phase-gate command that must use an approved MOCA entrypoint. Required repair: wrap the proof in `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...` or make the strict classifier cover the metadata proof directly.

### Warnings

- `.planning/ROADMAP.md` summary table still said Phase 58 was `0/TBD | Not planned` while detailed Phase 58 planning listed ten plans.
- `58-10-PLAN.md` said approved entrypoints were required "where applicable", which left the metadata proof ambiguous.

### Clean Areas Confirmed

- The ten-plan split was dependency-ordered and below the plan-size blocker threshold.
- Legacy cleanup coverage included all reviewed wrapper/helper and route delegate surfaces.
- Legacy-named test migration, current-runtime versus historical projection split, strict classifier semantics, classifier-based docs guard, metadata handling, and frontend build/test verification were explicitly planned.

## Claude Final Re-Review After Metadata-Proof Repair

Reviewed after commit `ee6b90d` replaced the bare metadata proof with an approved `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...` command and updated the stale roadmap summary.

Verdict: CLEAN

### Confirmed

- The prior metadata-proof blocker is closed in both `58-VALIDATION.md` and `58-10-PLAN.md`.
- Python, pytest, ruff, and classifier gates use approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` entrypoints.
- Remaining `rg` references are acceptance criteria or source-audit text, not metadata phase-gate commands.
- No execution-blocking plan repair items remain.
