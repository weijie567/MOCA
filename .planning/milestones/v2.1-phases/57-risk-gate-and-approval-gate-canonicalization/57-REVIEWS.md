---
phase: 57
reviewers: [claude]
reviewed_at: 2026-07-07T20:47:39+08:00
plans_reviewed:
  - 57-01-PLAN.md
  - 57-02-PLAN.md
  - 57-03-PLAN.md
  - 57-04-PLAN.md
  - 57-05-PLAN.md
---

# Cross-AI Plan Review - Phase 57

## Claude Review

# Cross-AI Plan Review — Phase 57 Risk Gate and Approval Gate Canonicalization

## Overall Assessment

The five-plan split is directionally strong and matches the MOCA phase-granularity rule: canonical callable first, graph/router cutover second, approval resume hardening third, projection/UI/eval closeout fourth, docs/debt/validation fifth. The plans correctly center the key Phase 57 distinction: current-run authority must move to `risk_gate`, while `assess_risk_and_approval` may remain only as labeled historical/import/test compatibility until Phase 58. The biggest risks are not conceptual; they are execution-order and validation risks. In particular, Plan 57-02 may temporarily break trusted edit rerisk paths before Plan 57-03 canonicalizes `resume_route`, and Plan 57-05's doc validation is too weak because existing docs already contain `risk_gate` while still describing `assess_risk_and_approval` as current. Overall risk: **MEDIUM**, with a few **HIGH** concerns that should be fixed before execution.

---

# 57-01-PLAN.md — Canonical `risk_gate` Callable and Legacy Wrapper

## Summary

This plan is well-scoped and is the right first wave: create the canonical callable, preserve the old risk/action implementation through a narrow compatibility wrapper, and lock node-level identity behavior before graph cutover. It follows the Phase 56 wrapper pattern and avoids prematurely deleting legacy surfaces. The main risk is that the current implementation may contain many hard-coded `assess_risk_and_approval` keys beyond the planned `llm_outputs` / trace identity hook, so the shared helper refactor must audit all node-name writes, errors, final-response refs, trace steps, and state keys.

## Strengths

- Correctly separates **canonical owner** (`risk_gate`) from **legacy import/test compatibility** (`assess_risk_and_approval`).
- Keeps risk semantics in place rather than redesigning the risk policy engine.
- Uses TDD-style tests to lock current-run identity before graph wiring changes.
- Includes explicit Phase 58 delete metadata:
  - `PHASE_57_COMPATIBILITY_ALIAS`
  - `HISTORICAL_TRACE_PROJECTION`
  - `IMPORT_TEST_COMPATIBILITY`
  - `DELETE_BY_PHASE_58`
- Preserves Phase 56 claim/RAG fail-closed behavior as a must-have.
- Uses approved `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` commands.

## Concerns

- **HIGH — Identity hook may not cover every hard-coded legacy write.**  
  The plan names `output_key` and `trace_node`, but the current risk node may write legacy literals in more places: `node_errors`, trace step metadata, `llm_outputs`, approval plan metadata, final response fallback source, risk decision debug data, or test fixture expectations. If only the top-level trace and `llm_outputs` are parameterized, current `risk_gate` runs could still leak `assess_risk_and_approval` as current authority.

- **MEDIUM — `read_first` includes `src/agent/nodes/risk_gate.py` before it exists.**  
  Some executors tolerate missing files, some do not. This could create unnecessary friction.

- **MEDIUM — Tests based on “source contains literal metadata” are brittle.**  
  Literal-source assertions are acceptable for compatibility markers, but they should not be the only evidence. Behavioral tests should prove the wrapper emits legacy identity only when explicitly calling the legacy wrapper.

- **MEDIUM — `moca.egg-info/SOURCES.txt` update may be noisy or stale.**  
  If `moca.egg-info` is generated/tracked, updating is fine. If it is stale generated output, this can create low-value churn. The plan should confirm tracked status before requiring it.

- **LOW — Existing `test_assess_risk_and_approval.py` could become semantically confusing.**  
  After canonicalization, the legacy test file should clearly state it tests the compatibility wrapper, not current runtime authority.

## Suggestions

- Add an explicit audit checklist inside Task 2:
  - Search all `assess_risk_and_approval` literals in `src/agent/nodes/assess_risk_and_approval.py`.
  - Classify each as:
    - shared implementation internal constant,
    - legacy wrapper identity,
    - historical compatibility metadata,
    - bug to parameterize.
- Add tests that check:
  - `risk_gate(...)` does not write `node_errors[*].node == "assess_risk_and_approval"`.
  - `risk_gate(...)` does not append trace steps with legacy `node`.
  - fallback/fail-closed paths also emit canonical identity, not just happy path.
- Replace `read_first: src/agent/nodes/risk_gate.py` with “create if missing” wording.
- Make `moca.egg-info/SOURCES.txt` conditional:
  - “If tracked and missing the new module, update it.”
- Rename or annotate legacy tests clearly:
  - `test_assess_risk_and_approval_compatibility_wrapper_*`.

## Risk Assessment

**Risk: MEDIUM**

The scope is clean, but this is a sensitive refactor of a high-risk action boundary. The plan is safe if the helper identity parameterization is complete. Without a full literal audit inside the old node, current-run `risk_gate` could still emit legacy identity in hidden state or error paths.

---

# 57-02-PLAN.md — Active Graph / Router / Baseline Cutover

## Summary

This plan addresses the core CAGM-08 cutover: active graph registration and current router return values must use `risk_gate`. It correctly updates `src/agent/graph.py`, `src/agent/routing.py`, architecture baselines, and routing tests together, which is necessary to avoid path-map drift. The main blocker is dependency ordering with Plan 57-03: if Plan 57-02 removes the legacy graph destination before approval edit resume emits `risk_gate`, trusted edit rerisk may break between waves.

## Strengths

- Directly targets the most important Phase 57 success criterion:
  - active `StateGraph.add_node(...)` registration uses `risk_gate`;
  - `assess_risk_and_approval` is no longer active current-run graph identity.
- Updates graph registration, path maps, router allowlist, static architecture baseline, and integration tests in the same wave.
- Explicitly preserves Phase 56 RAG/claim fail-closed route rules.
- Good acceptance criteria around:
  - active node inclusion/exclusion,
  - claim verification path map,
  - `_CLAIM_VERIFY_ROUTES`.
- Correctly treats current router return values as canonical route vocabulary, not display-only strings.

## Concerns

- **HIGH — Wave ordering can break approval edit rerisk before 57-03 runs.**  
  Plan 57-02 updates the approval-gate path map to include `"risk_gate": "risk_gate"` and removes active legacy destinations. But current approval edit resume may still produce `resume_route == "assess_risk_and_approval"` until Plan 57-03. If any tests or runtime paths exercise edit rerisk after 57-02 but before 57-03, the graph can route to a missing destination or fail closed unexpectedly.

- **HIGH — `route_after_approval` behavior is split across Plan 57-02 and Plan 57-03.**  
  Plan 57-02 says the approval-gate path map includes `"risk_gate": "risk_gate"`, but Plan 57-03 says `route_after_approval(...)` returns `risk_gate` for trusted edit/superseded payloads. These two changes are coupled. They should not be separated unless Plan 57-02 keeps a temporary safe compatibility bridge and tests it.

- **MEDIUM — Acceptance criteria use exact `builder.add_node(...)` spelling.**  
  Provided current docs mention `workflow.add_node(...)` in examples, while the plan uses `builder.add_node(...)`. If the actual source uses `workflow`, exact string checks may fail even when behavior is correct.

- **MEDIUM — Self-loop route for `risk_gate` may be unnecessary.**  
  The plan includes a `route_after_risk` map with `"risk_gate": "risk_gate"`. Current research says the legacy self-loop existed but the router did not return it. Keeping an unreachable self-loop may be harmless, but it should be intentional and tested, not cargo-culted.

- **MEDIUM — `tests/agent/rag_context/test_routing.py` is included but not in the first verification command.**  
  Task 1 touches core routing; if this test family encodes route literals, it may fail after Task 1 and only be fixed in Task 2.

## Suggestions

- Fix the wave-order blocker in one of two ways:

  **Option A — Pull minimal approval route canonicalization into 57-02**
  - In Plan 57-02, update `route_after_approval(...)` to return `risk_gate` for trusted edit payloads.
  - Leave ApprovalService/API resume persistence changes for Plan 57-03.
  - Add a narrow graph routing test proving edit payload route is `risk_gate`.

  **Option B — Keep temporary compatibility only inside graph routing**
  - Plan 57-02 can accept legacy edit resume payloads only as an explicitly marked temporary bridge.
  - It must normalize to `risk_gate`.
  - Mark with `DELETE_BY_PHASE_58`.
  - Plan 57-03 then moves the source of new payloads to `risk_gate`.

  Option A is cleaner.

- Replace exact string acceptance with behavior/source intent:
  - “Graph source contains active node registration for `risk_gate` and no active node registration for `assess_risk_and_approval`.”
- Decide whether the `risk_gate -> risk_gate` self-loop is required:
  - If no router branch returns `risk_gate`, remove the map entry.
  - If retained for future/pending behavior, document why and test that it is not used as current policy authority.
- Include `tests/agent/rag_context/test_routing.py` in Task 1 verification if its assertions are affected by the route literal change.

## Risk Assessment

**Risk: HIGH until the 57-02 / 57-03 ordering issue is fixed; otherwise MEDIUM**

This plan touches the active graph spine. The graph/router cutover is required, but route maps and resume payloads must change atomically enough that no intermediate wave breaks trusted edit rerisk.

---

# 57-03-PLAN.md — Trusted Approval Resume and Approval-Gate Separation

## Summary

This is the most security-sensitive plan and it targets the right boundary: new trusted edit resumes must rerisk through `risk_gate`, while ordinary chat approval-like text remains untrusted. It also correctly preserves stored legacy `resume_route == "assess_risk_and_approval"` as historical retry compatibility. The main issue is that the plan should be stricter about where legacy route acceptance is allowed: ideally only API retry reconstruction or explicitly marked historical paths normalize legacy to canonical. The graph should not broadly accept legacy payloads as normal current-run input.

## Strengths

- Correctly updates new edit decisions to `resume_route="risk_gate"`.
- Preserves persisted legacy edit retry compatibility instead of deleting it.
- Explicitly rejects direct edit-to-`action_draft` paths.
- Keeps `approval_gate` focused on interrupt/request/resume lifecycle.
- Includes ordinary chat spoofing regressions across safety pre-route, intent routing, clarification, and graph tests.
- Uses existing trusted schemas and service boundaries rather than adding a chat approval parser.

## Concerns

- **HIGH — Legacy `resume_route` acceptance could leak into current graph authority.**  
  The plan says: “if accepting legacy payloads in graph routing, route them to `risk_gate` and label the branch historical compatibility only.” This is risky unless the graph can distinguish API retry/historical source from current trusted resume payload. Otherwise, a current-run malformed or stale trusted payload with legacy route could still pass as accepted.

- **MEDIUM — `_should_resume_graph(...)` behavior needs exact source separation.**  
  The plan says `_should_resume_graph` should require current edit route `risk_gate`, while legacy is accepted only in retry compatibility branch. That is good, but the acceptance criteria should explicitly reject legacy route in new request/service results.

- **MEDIUM — Static “no risk imports in approval_gate.py” tests can be noisy.**  
  Static tests that reject imports from risk helpers are useful, but they should be scoped to production code imports and avoid blocking harmless type-only or doc references.

- **MEDIUM — Trusted approval schema validation should include hash/version mismatch negatives.**  
  The plan mentions payload hash, snapshot, and versions, but the test tasks focus more on route values and chat spoofing. Existing tests may already cover this, but the plan should explicitly preserve those negative cases.

- **LOW — Plan modifies `src/agent/graph.py` after Plan 57-02.**  
  This is fine if Plan 57-02 only does graph registration/path maps. But because approval routing is coupled, the split should be clarified.

## Suggestions

- Make the legacy path rule explicit:

  ```text
  New ApprovalService decisions:
    only resume_route == "risk_gate"

  API normal decision response:
    accepts only "risk_gate"

  API retry reconstruction from persisted event metadata:
    accepts "assess_risk_and_approval" only when event metadata predates Phase 57,
    records compatibility marker,
    normalizes graph resume to "risk_gate"

  route_after_approval:
    current canonical route is "risk_gate";
    legacy route accepted only if payload has server-side compatibility marker
    or not accepted at graph layer at all.
  ```

- Add negative tests:
  - New edit decision must not emit legacy route.
  - Normal API decision payload with legacy route is rejected or not treated as current.
  - Stored legacy event retry normalizes to `risk_gate`.
  - Edited action without `new_action_payload_hash` fails closed.
  - Approved payload with mismatched action hash or snapshot hash does not reach `action_draft`.
- If legacy is handled only in API retry reconstruction, do not add graph-level legacy acceptance.
- Add a static test that `approval_gate.py` does not import:
  - risk rules,
  - snapshot creation helpers,
  - proposed-action builders,
  - approval-plan builders.

## Risk Assessment

**Risk: MEDIUM**

The plan addresses the right security boundary. Risk becomes **LOW-MEDIUM** if legacy route acceptance is constrained to persisted historical retry handling and never treated as normal current-run approval authority.

---

# 57-04-PLAN.md — Vocabulary / API / Frontend / Eval / Diagnostic Closeout

## Summary

This plan covers the necessary projection layer after runtime cutover: graph vocabulary, API/SSE labels, frontend timeline labels, eval harnesses, diagnostics, and static checks. This is the right kind of closeout, because Phase 57 is incomplete if current runs still display or evaluate `assess_risk_and_approval` as current authority. The main concern is scope size: this plan crosses backend projection, API, frontend, eval, diagnostics, and architecture checks. It is not a “single giant phase plan,” but it is a broad closeout wave and needs stronger verification, especially for frontend changes.

## Strengths

- Correctly distinguishes:
  - `risk_gate` as runtime/runnable;
  - `assess_risk_and_approval -> risk_gate` as compatibility alias.
- Covers API/SSE risk payload extraction, which is easy to miss.
- Covers frontend labels, eval harnesses, and latency diagnostics.
- Keeps historical traces readable without rewriting stored `AgentStep.node_name`.
- Adds static guardrails so eval/diagnostics do not keep treating the legacy node as current.
- Matches Phase 56 projection closeout pattern.

## Concerns

- **MEDIUM — Closeout plan is broad.**  
  Backend vocabulary, API/SSE, frontend TSX, eval script, diagnostics script, trace tests, API tests, and architecture tests are all in one plan. This may be acceptable as a closeout wave, but it is near the plan-size limit.

- **MEDIUM — No frontend verification command is listed.**  
  The plan edits `frontend/src/components/timeline/TimelineStep.tsx`, but verification only runs Python tests. If the frontend has an existing typecheck/build/test command, the plan should include it.

- **MEDIUM — API risk payload extraction must preserve historical readability.**  
  Changing extraction to only `node_name == "risk_gate"` can break historical traces that still have `node="assess_risk_and_approval"`. The plan says to keep legacy extraction if tests prove it is needed; given stored traces can contain old names, this should be required, not optional.

- **MEDIUM — Eval script has multiple legacy occurrences.**  
  The provided `scripts/eval_agent.py` excerpt contains expected node `assess_risk_and_approval` in CI expected nodes. The plan covers this, but static checks must catch all current-run lists, not just one constant.

- **LOW — Frontend historical label policy needs clarity.**  
  Keeping a frontend label for `assess_risk_and_approval` may be fine for historical timelines, but it must not be used for current runtime progress.

## Suggestions

- Consider splitting 57-04 into two sub-waves if execution starts getting large:
  - 57-04A: graph vocabulary + API/SSE + trace tests.
  - 57-04B: frontend + eval + diagnostics + static checks.
- Add frontend verification if available, for example:
  - `npm --prefix frontend run typecheck`
  - or `npm --prefix frontend run build`
  - or the repo’s established frontend test command.
- Make historical API extraction mandatory:
  - current `risk_gate` extracts risk payload;
  - historical `assess_risk_and_approval` extracts risk payload but projects `target_node_name="risk_gate"` and marks compatibility.
- Add static tests that scan specific current-run lists:
  - eval expected node sequences,
  - fake LLM patch target modules,
  - diagnostic mock nodes,
  - frontend current label map if it distinguishes current vs historical.
- Require `scripts/eval_agent.py` CI expected nodes to include `risk_gate`, especially for approval-required / approved / rejected categories.

## Risk Assessment

**Risk: MEDIUM**

The plan is needed and mostly well-shaped, but it touches many consumer surfaces. Risk is manageable if the plan adds frontend verification and makes historical trace readability a required behavior.

---

# 57-05-PLAN.md — Docs / Architecture Debt / Validation / Static Legacy-Hit Classification

## Summary

This plan is a necessary closeout wave: current-source docs, README, architecture debt, validation artifacts, and static legacy-hit classification must reflect that `risk_gate` is now current runtime identity and `assess_risk_and_approval` is historical/compatibility only. The plan’s biggest weakness is validation quality. The proposed doc check only verifies that files contain `risk_gate`, but the provided docs already contain `risk_gate` while still describing `assess_risk_and_approval` as the current active node. That check can pass without actually closing the documentation gap.

## Strengths

- Correctly avoids editing `docs/contract-spec.md` unless an actual source/spec conflict is found.
- Updates the right current-source docs:
  - `docs/current-langgraph-architecture.md`
  - `docs/architecture-overview.md`
  - `docs/target-agent-platform-architecture-plan.md`
  - `README.md`
- Includes `.planning/ARCHITECTURE-DEBT.md`, which matches MOCA project rules for core subsystem architecture debt.
- Requires Chinese architecture debt entry with status, evidence, and Phase 58 residuals.
- Requires static classification for remaining `assess_risk_and_approval` hits.
- Includes full phase closeout test command, ruff, and `git diff --check`.

## Concerns

- **HIGH — Doc verification is too weak and can falsely pass.**  
  The command only checks whether each doc contains `risk_gate`. The provided docs already contain `risk_gate` but still state current runtime uses `assess_risk_and_approval` in multiple current-source sections. This would pass while leaving stale current docs.

- **HIGH — Static legacy-hit classification is described but not enforced by an actual scan artifact.**  
  The plan says every remaining hit must be classified, but the verification only checks for the string `Static Legacy-Hit Classification`. It does not prove the scan ran or that every hit was classified.

- **MEDIUM — Current-source docs must distinguish “previous state” from “current state.”**  
  `docs/current-langgraph-architecture.md` is explicitly a current source snapshot. After Phase 57, any line saying active graph node is `assess_risk_and_approval` must be updated or moved to a previous-state/compatibility table.

- **MEDIUM — `README.md` current workflow diagram currently uses `assess_risk_and_approval`.**  
  The plan says update it, but the weak check would not catch a missed diagram edge because `README.md` could contain both names.

- **MEDIUM — Validation artifact should not set `nyquist_compliant: true` based only on text markers.**  
  It should require recorded evidence from the actual approved commands, not just marker presence.

- **LOW — Plan 57-05 is broad but acceptable.**  
  It spans docs, debt, and validation, but all are closeout artifacts. This is broad, yet still coherent as a final wave.

## Suggestions

- Replace the doc verification with stricter checks, for example:
  - `docs/current-langgraph-architecture.md` current graph node list contains `risk_gate` and does not list `assess_risk_and_approval` as active.
  - README current workflow diagram contains `risk_gate` and does not contain `G[assess_risk_and_approval]`.
  - Any remaining `assess_risk_and_approval` in docs appears near phrases like “historical”, “compatibility”, “previous”, “Phase 58”, or “legacy”.
- Add an actual static scan step:
  - Generate a list of all remaining `assess_risk_and_approval` hits.
  - Paste or summarize them into `57-VALIDATION.md`.
  - Classify each hit under exactly one allowed category.
- Add validation markers that include command output status:
  - command,
  - pass/fail,
  - date,
  - files/areas covered.
- Require `nyquist_compliant: true` only after:
  - full pytest suite passes,
  - ruff passes or known exceptions are recorded,
  - `git diff --check` passes,
  - static legacy-hit classification is complete.
- In `.planning/ARCHITECTURE-DEBT.md`, include a clear Phase 58 handoff:
  - remove compatibility wrapper/import surfaces,
  - remove graph vocabulary alias if no longer needed,
  - remove historical frontend labels if policy allows,
  - remove retry compatibility for legacy approval event metadata only if migration/support policy allows.

## Risk Assessment

**Risk: MEDIUM-HIGH until validation is strengthened; otherwise LOW-MEDIUM**

This is documentation and validation work, but stale current-source docs can mislead Phase 58 and future reviewers. The false-pass risk is real because the current docs already contain both target and legacy terms.

---

# Cross-Plan Concerns

## HIGH

- **57-02 / 57-03 dependency ordering can leave the graph in a broken intermediate state.**  
  Graph path maps and `route_after_approval` / approval resume payloads are coupled. Trusted edit rerisk must not depend on a later wave to become routable.

- **Legacy `resume_route == "assess_risk_and_approval"` must not be accepted as normal current-run authority.**  
  It should be accepted only from persisted historical retry metadata, normalized to `risk_gate`, and marked `DELETE_BY_PHASE_58`.

- **Doc and validation checks can falsely pass.**  
  Checking for the presence of `risk_gate` is not enough. The plan must check that legacy names are not described as current runtime authority.

## MEDIUM

- **Identity parameterization in 57-01 needs a full literal audit.**  
  `output_key` and `trace_node` may not cover all legacy name writes.

- **57-04 touches frontend without frontend verification.**  
  Add a frontend build/typecheck/test command if the repo has one.

- **Static scan classification must be concrete.**  
  A heading in `57-VALIDATION.md` is not evidence that every hit was classified.

- **Exact source-string acceptance criteria may be brittle.**  
  Prefer AST/static helper checks or behavior-focused tests where possible.

## LOW

- **`moca.egg-info/SOURCES.txt` should be conditional on tracked/generated status.**
- **Legacy test names should be clearly marked as compatibility tests.**
- **Self-loop route entries should be intentional, not carried forward by default.**

---

# Recommendations Before Execution

1. **Patch 57-02 / 57-03 ordering**
   - Move minimal `route_after_approval` canonical edit routing into 57-02, or make a very narrow temporary compatibility bridge.
   - New current route must be `risk_gate`.

2. **Constrain legacy approval route handling**
   - New service/API decisions: `risk_gate` only.
   - Persisted legacy event retry: accept `assess_risk_and_approval`, mark compatibility, normalize to `risk_gate`.
   - Do not let ordinary current payloads use legacy route.

3. **Strengthen 57-01 identity audit**
   - Require search/classification of all `assess_risk_and_approval` literals inside the risk node implementation.
   - Add fail-closed path tests for canonical identity.

4. **Strengthen 57-04 verification**
   - Add frontend typecheck/build if available.
   - Require historical trace readability for legacy node names.

5. **Rewrite 57-05 validation checks**
   - Assert current docs no longer describe `assess_risk_and_approval` as active runtime.
   - Add actual static scan output and per-hit classification.
   - Set `nyquist_compliant: true` only after command evidence is recorded.

---

# Overall Risk Assessment

**Overall Risk: MEDIUM**

The plans are well-decomposed and target the right Phase 57 goals. They avoid the major anti-pattern of one giant plan and preserve the critical distinction between current-run `risk_gate` authority and historical `assess_risk_and_approval` compatibility. The phase should achieve CAGM-08 if the ordering and validation gaps are fixed. Without those fixes, the main failure modes are:

- edit approvals temporarily or silently fail to rerisk;
- legacy approval route remains accepted as current authority;
- docs/validation claim Phase 57 is complete while current-source artifacts still describe the legacy node as active.

---

## Consensus Summary

Only the Claude reviewer was requested for this autopilot pass, so there is no multi-reviewer consensus. The actionable review themes to adjudicate are:

### Agreed Strengths
- The five-plan split matches MOCA phase-granularity expectations.
- The plans correctly separate current-run `risk_gate` authority from historical/import/test `assess_risk_and_approval` compatibility.
- The trusted approval boundary and ordinary-chat untrusted boundary are treated as security-sensitive.

### Agreed Concerns
- The `57-02` graph/router cutover and `57-03` approval resume changes may be too coupled if edit rerisk is not canonicalized before removing legacy graph routes.
- Legacy `resume_route == "assess_risk_and_approval"` needs a narrow historical retry compatibility boundary, not normal current-run authority.
- `57-05` doc/static validation must prove legacy names are no longer described as current runtime authority, not merely that docs contain `risk_gate`.

### Divergent Views
- None; single reviewer only.

---

## Claude Review Loop 2

Reviewed at: 2026-07-07T21:13:12+08:00

Result: PASS

Claude confirmed no remaining blockers after Codex repairs and GSD plan-checker Loop 2:

- `57-02` / `57-03` ordering is now safe: minimal edit rerisk cutover moved into `57-02`, while `57-03` handles persisted legacy retry compatibility and trusted boundary hardening.
- Legacy `assess_risk_and_approval` compatibility is constrained to historical trace projection, direct import/test compatibility, persisted legacy approval retry, or Phase 58 deletion candidates.
- Impacted tests are in scope, including approval API/service tests, Phase 33 claim-boundary tests, RAG routing tests, and graph routing tests.
- `TimelineStep.tsx` frontend verification includes `npm --prefix frontend run build`.
- Docs/static validation is materially stronger and requires total hit counts, classification rows/summaries, and zero `UNCLASSIFIED`.
- Python validation commands use approved MOCA entrypoints.
- The five-plan split remains executable; `57-04` and `57-05` are broad but have clear closeout targets and gates.

Non-blocking warnings for execution:

- `57-05` doc checks are still string-pattern checks, so execution summaries must include the real scan command, total count, and classification results instead of only saying "checked".
- `57-03` should normalize persisted legacy retry routes to canonical `risk_gate` before graph resume and preserve the legacy route only as metadata/historical marker.
