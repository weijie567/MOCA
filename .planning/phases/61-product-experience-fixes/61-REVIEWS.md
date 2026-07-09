---
phase: 61
reviewers: [claude]
reviewed_at: 2026-07-09T11:10:00+08:00
plans_reviewed: ["61-01-PLAN.md", "61-02-PLAN.md", "61-03-PLAN.md", "61-04-PLAN.md", "61-05-PLAN.md"]
---

# Cross-AI Plan Review — Phase 61

## Claude Review

## Summary

The Phase 61 plan set is directionally strong: it preserves the existing graph shape, keeps `business_metric_query` as one generic intent, routes metric reads through ToolPlatform and BusinessFactService, and includes backend, frontend, golden, and Playwright validation. The plan split by ownership boundary is mostly sound. I found several issues that should be fixed before execution, mainly around requirement-completion metadata, contract/spec traceability, metric edge cases, and whether Playwright is truly live E2E rather than mocked UI-only coverage. None of the findings require changing the core design, but a few are execution blockers because they can produce false milestone completion or unsafe/ambiguous metric behavior.

## Strengths

- **Good plan decomposition.** The five-plan split follows the real ownership boundaries: response UX baseline, intent/slots, runtime/scope, graph/final response/SSE, and console/regression.
- **Generic metric intent is protected.** Plans repeatedly state that `business_metric_query` must remain one intent, with tests rejecting per-metric intents.
- **Correct authority boundaries.** Metric reads are planned behind `query_business_metric` through ToolPlatform and BusinessFactService, not direct DB reads from graph/final response.
- **No-leak scope behavior is a first-class concern.** Unauthorized merchant metric queries are handled as fail-closed responses without confirming merchant existence.
- **Frontend/UI contract is concrete.** `61-UI-SPEC.md` gives specific labels, subtitles, forbidden fields, spacing, and state-reset expectations.
- **Validation is layered.** Backend node tests, graph tests, service/tool tests, API/SSE tests, frontend tests, golden cases, and Playwright are all represented.

## Concerns

### HIGH — Requirement frontmatter can mark requirements complete too early

**References:**
- `61-02-PLAN.md` frontmatter: `requirements: SCOPE-01..SCOPE-04`
- `61-03-PLAN.md`, `61-04-PLAN.md`, `61-05-PLAN.md` repeat MET/SCOPE requirements
- GSD `execute-plan.md` marks completed requirements from PLAN frontmatter

The plans use `requirements` for partial/contract-level coverage, but the execution workflow marks those requirements complete from frontmatter. That means after Plan 61-02, SCOPE-01..SCOPE-04 could be marked complete before runtime enforcement exists in BusinessFactService/ToolPlatform. Similarly, MET-03 is only fully satisfied after Plan 61-04 final response, and CONSOLE/EVAL only after 61-05.

**Impact:** The milestone can appear complete before the actual behavior is implemented and verified.

**Fix:** Use `requirements_addressed` or plan body language for partial coverage, but keep frontmatter `requirements` only for requirements fully completed by that plan. Another safe pattern is:
- 61-01: only UX baseline requirements if truly complete at that point, or mark as partial in text.
- 61-02: MET-01/MET-02/MET-04 contract-level only should not auto-complete if runtime still missing.
- 61-03: SCOPE/MET runtime requirements only if final response not needed for completion.
- 61-04: MET-01..MET-04 and SCOPE-01..04 may become fully complete after graph/final response tests.
- 61-05: CONSOLE/EVAL and final cross-plan closure.

---

### HIGH — Contract/spec delta is not planned despite changing accepted contracts

**References:**
- `61-03-PLAN.md` modifies `src/tools/contracts.py`, `src/tools/catalog.py`, auth permissions, BusinessFactService schemas
- `61-CONTEXT.md` says `docs/contract-spec.md` remains canonical
- `AGENTS.md:94-101` requires traceable handling when implementation and spec differ

Plan 61-03 adds:
- new trusted scope `metrics:read`
- new tool permission `tool:query_business_metric`
- new ToolPlatform tool `query_business_metric`
- new `BusinessFactRefV1.resource_type = "business_metric"`
- new metric result contract

These are contract-level changes, but no plan includes `docs/contract-spec.md` in `files_modified`, nor an explicit “no spec delta needed because...” decision.

**Impact:** Execution can silently drift from the normative contract source, which conflicts with the project rule that spec and phase implementation differences must be recorded.

**Fix:** Add a contract update task, probably in 61-03 or a small inserted 61-03a:
- update `docs/contract-spec.md` for metric tool, metric fact refs, trusted metrics permission, no-leak behavior, and MVP scope;
- or explicitly add an MVP scope note if the spec is target-state only.
Also add a verification grep/test that the spec names `query_business_metric`, `business_metric`, and `metrics:read`.

---

### HIGH — Refund-rate zero denominator is missing

**References:**
- `61-03-PLAN.md`, Task 3: `merchant_refund_rate`
- `61-CONTEXT.md:26-27`: refund rate formula

The plan defines numerator/denominator but does not say what happens when the denominator is zero for a merchant/time range with no orders.

**Impact:** Possible divide-by-zero, misleading `0%`, or unhelpful error. This is a user-facing metric edge case and likely appears in demo data if a narrowed scope/time has no orders.

**Fix:** Define and test a deterministic result:
- `denominator=0`, `value=null` or `rate=null`, `unit="percent"`, `display_value="暂无可计算退款率"`;
- final response should explain that there are no orders in the selected scope/time range;
- no RAG/policy evidence wording;
- no merchant existence leak.

---

### HIGH — Playwright plan can degrade into mocked UI tests despite “full Playwright E2E” being in scope

**References:**
- `61-05-PLAN.md`, Task 3
- `61-CONTEXT.md:56`, D-25
- `61-VALIDATION.md:54-58`

Task 3 says if backend orchestration is too heavy, “use route-level mocking only for frontend-only label tests and keep at least one live smoke test documented.” That weakens the user decision that full Playwright E2E is in scope. The acceptance criteria only require files and prompt expectations, not that `npm run e2e` exercises live API/SSE behavior.

**Impact:** CONSOLE/EVAL can pass with mocked frontend rendering while live Agent Console still fails.

**Fix:** Split Playwright coverage into two named tiers:
1. **Mocked frontend Playwright** for label/layout fast checks.
2. **Live Agent Console Playwright smoke** that starts or targets real backend/frontend and runs at least:
   - `你好`
   - `当前有多少订单` -> clarification
   - completed metric query
   - unsupported request
   - unauthorized merchant metric denial

Make `npm run e2e` include the live tier by default, or add `npm run e2e:live` and require it in final validation.

---

### MEDIUM — `metrics:read` is granted to merchant compatibility role without explicit requirement

**References:**
- `61-03-PLAN.md`, Task 1: “support, manager, merchant compatibility, and admin”
- Requirements mention support, manager, admin only

The plan extends metrics permission to merchant compatibility users. This may be valid, but the milestone requirements and role/scope section only call out support, manager, and admin.

**Impact:** Scope expansion may be intentional compatibility, but it should not happen silently.

**Fix:** Add an explicit decision:
- either include merchant role as compatibility-only and test it sees only its bound merchant;
- or remove merchant from `metrics:read` until a future requirement names it.

---

### MEDIUM — Time-window semantics are not tested deeply enough

**References:**
- `61-CONTEXT.md:23-25`, D-04/D-05
- `61-02-PLAN.md`, Task 2
- `61-03-PLAN.md`, Task 3

The plans list local business timezone semantics, but there are no explicit acceptance criteria for:
- inclusive start / exclusive end boundaries;
- Monday week start;
- quarter start;
- timezone-aware datetime normalization;
- invalid `start > end`;
- future date ranges;
- “当前” accepted only for snapshot metrics.

**Impact:** Metric answers can be off by one day/week or depend on server UTC behavior.

**Fix:** Add service-level tests in 61-03 for each preset boundary and invalid range behavior. Define:
- `start_at <= created_at < end_at`;
- local demo timezone source;
- error/clarification behavior for invalid ranges.

---

### MEDIUM — `status_filter` is named but not defined

**References:**
- `61-02-PLAN.md`, Task 2
- `61-03-PLAN.md`, Task 3
- MET-02 requires status filter support

The plan says metric slots include `status_filter`, but it does not lock accepted status values per metric:
- order statuses;
- refund statuses;
- ticket statuses;
- action draft statuses;
- whether unsupported status values clarify or fail.

**Impact:** MET-02 can be nominally present but not useful or safe.

**Fix:** Add a small status-filter contract table:
- `order_count`: allowed order statuses from current model/demo values.
- `refund_case_count`: allowed refund statuses.
- `pending_ticket_count`: fixed `open|in_progress` snapshot unless future plan adds status overrides.
- `coupon_record_count`: allowed draft/record statuses or all `issue_coupon` records with caveat.
- `merchant_refund_rate`: clarify whether status filter applies to orders, refund cases, or is unsupported for MVP.

---

### MEDIUM — `resource type` slot coverage is ambiguous

**References:**
- MET-02: “metric, resource type, time range, status filter, merchant filter slots”
- `61-02-PLAN.md`, Task 2 focuses on `metric_id`, time, status, merchant

The plan may treat `metric_id` as encoding resource type, e.g. `refund_case_count`, but this is not stated. If MET-02 expects explicit resource parsing, this should be documented.

**Impact:** Requirement coverage may be disputed later.

**Fix:** Add a contract note:
- either `resource_type` is an explicit normalized slot;
- or `metric_id` is the canonical normalized combination of metric + resource for MVP, with `resource_type` derived and included in tool input/result.

---

### MEDIUM — No explicit test that tool args cannot carry/widen merchant scope

**References:**
- `61-CONTEXT.md:34`, D-12
- `61-03-PLAN.md`, Task 3
- `61-03-PLAN.md` threat model T-61-03-02

The plan says trusted context controls scope, but should explicitly test malicious tool inputs such as:
- `merchant_scope=["*"]`
- `tenant_id` in args
- unauthorized `merchant_id`
- frontend-provided scope label

**Impact:** A future executor implementation might accidentally trust tool input scope.

**Fix:** Add acceptance criteria:
- metric tool input schema must not accept tenant/merchant scope authority fields;
- service ignores/rejects any scope-like input;
- only `ToolCallContext.merchant_scope` controls final scope.

---

### MEDIUM — Coupon metric “record/draft count” is under-specified

**References:**
- `61-CONTEXT.md:26`, D-07
- `61-03-PLAN.md`, Task 3
- `61-04-PLAN.md`, Task 2

The plan says count `ActionDraft.action_type == "issue_coupon"` records/drafts, but does not define which statuses count. The final answer caveat is required, but the calculation口径 also needs to be stable.

**Impact:** Tests may lock a count without explaining whether rejected/expired/cancelled drafts count.

**Fix:** Define MVP formula:
- all `issue_coupon` action drafts/records created in range, any status; or
- only selected statuses, with the status list named.
Return `filters.status` in metric result and mention it in final response if not “all statuses.”

---

### MEDIUM — `read_status` may be a poor operation label for analytics metrics

**References:**
- `61-02-PLAN.md`, Task 1: “Use existing requested operation `read_status`”

This may work technically, but event-count/rate metrics are not status reads. If operation drives risk tiering, route policy, or audit semantics, `read_status` may blur the contract.

**Impact:** Low runtime risk if policy only needs read-only, but it can confuse future audits and tests.

**Fix:** Prefer a read-only operation such as `read_metric` / `read_business_metric` if the operation enum can be extended cleanly. If not, record an explicit MVP compromise in plan/spec notes.

---

### LOW — `61-01` may temporarily improve unsupported copy in a way that becomes obsolete in 61-02

**References:**
- `61-01-PLAN.md`, Task 1
- `61-02-PLAN.md`, Task 4

Plan 61-01 keeps temporary aggregate-order unsupported behavior, while 61-02 changes `当前有多少订单` to metric clarification. This is acceptable, but tests should be clearly marked as temporary so 61-02 does not fight 61-01.

**Fix:** Name the 61-01 aggregate-order test with `temporary_until_phase61_metric_intent` or similar, and delete/replace it in 61-02.

---

### LOW — Validation strategy remains `status: draft` and `Approval: pending`

**References:**
- `61-VALIDATION.md:4`, `61-VALIDATION.md:69`

The plans rely on this validation strategy, but the artifact itself says draft/pending.

**Impact:** Process ambiguity rather than code risk.

**Fix:** Before execution, mark the validation strategy approved or note that these five plans are the approval mechanism.

## Suggestions

1. **Fix requirement metadata before execution.** Keep `requirements` frontmatter aligned with auto-completion semantics. Put partial coverage in `requirements_addressed` or body text.
2. **Add a contract/spec task.** Include `docs/contract-spec.md` updates for `business_metric_query`, `query_business_metric`, `metrics:read`, `business_metric` fact refs, and no-leak metric behavior.
3. **Add metric edge-case contract tests.**
   - zero denominator refund rate;
   - empty authorized scope;
   - unauthorized requested merchant;
   - invalid time range;
   - local timezone boundaries;
   - unsupported metric/status.
4. **Define `status_filter` and coupon count口径.** Add a small table to 61-02 or 61-03.
5. **Make Playwright live E2E non-optional.** Keep mocked UI tests, but require at least one live backend/SSE flow in the automated or final validation path.
6. **Explicitly test scope authority.** Add tests proving user text, LLM candidate slots, frontend payload, and tool args cannot widen merchant scope.
7. **Clarify merchant role permission.** Either remove merchant compatibility from metrics permission or record it as a deliberate compatibility case with tests.
8. **Clarify `resource_type`.** Decide whether it is explicit or derived from `metric_id`.

## Risk Assessment

**Overall risk: MEDIUM-HIGH before revisions; MEDIUM after fixes.**

The architecture direction is correct and the plan set is likely executable. The main risk is not conceptual design but execution fidelity: premature requirement completion, missing spec traceability, and metric edge cases could allow the phase to “pass” while key product/security requirements remain only partially implemented. The no-leak and trusted-context boundaries are well represented, but they need sharper tests against malicious scope-bearing inputs. The frontend plan is solid for labels and state reset, but Playwright must be tightened so it validates live Agent Console behavior, not just mocked rendering.

No issue requires scrapping the plan structure. Fixing the metadata/spec/test gaps should be enough to make Phase 61 ready for execution.


---

## Consensus Summary

Only Claude was requested for this autopilot plan review. Codex must adjudicate every actionable finding before plan repair and execution.

### Agreed Strengths

- The five-plan split follows clear ownership boundaries.
- `business_metric_query` remains one generic intent.
- Runtime metric reads stay behind ToolPlatform and BusinessFactService.
- Role/scope and no-existence-leak concerns are represented in the plan set.

### Agreed Concerns

- Requirement frontmatter may allow premature requirement completion.
- Contract/spec traceability for metric tool/scope changes is missing.
- Several metric edge cases need explicit planned tests and semantics.
- Playwright E2E must prove live Agent Console behavior, not only mocked rendering.

### Divergent Views

None yet. Codex adjudication follows in `61-PLAN-REVIEW-DECISIONS.md`.

---

## Claude Review Loop 2

Source: `/tmp/gsd-review-claude-61-loop2.md`

### Summary

Claude re-reviewed the repaired Phase 61 plans and returned **READY for execution**. It found no remaining pre-execution blockers.

### Remaining Warnings

- LOW: execution must make `npm run e2e` and `npm run e2e:live` responsibilities explicit. If `e2e` is mocked/layout-only, `e2e:live` must remain a hard final validation gate and must exercise real `/api/v1/agent-runs` SSE.
- LOW: implementation must fix the authoritative local business/demo timezone source in service/helper/tests, rather than accidentally using host local time or raw UTC defaults.

### Loop 1 Resolution Check

Claude marked all accepted Loop 1 findings resolved after Codex repair, including requirement frontmatter, contract/spec delta, refund-rate zero denominator, Playwright live E2E, merchant compatibility guard, time-window semantics, `status_filter`, `resource_type`, scope-like tool args, coupon count口径, `read_status` MVP compromise, temporary aggregate-order baseline, and validation approval status.

### Readiness

**READY for execution.**
